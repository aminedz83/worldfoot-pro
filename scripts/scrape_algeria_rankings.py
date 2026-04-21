"""
scrape_algeria_rankings.py
==========================
Scrape les 5 classements BeSoccer Ligue 1 Algérie.

MODE 1 — Saison en cours (quotidien via cron) :
    python3 scrape_algeria_rankings.py

MODE 2 — Toutes les saisons (historique, une seule fois) :
    python3 scrape_algeria_rankings.py --all

Cron (Mode 1, quotidien à 3h) :
    0 3 * * * /usr/bin/python3 /path/to/scrape_algeria_rankings.py

Supabase : table algeria_rankings
Colonnes  : type, season, rank, name, player_id, photo, team, team_logo,
            position, value1, value2, value3, scraped_at
"""

import os, re, sys, time, json, requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone, date

# ══════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL       = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS   = {
    "apikey":        SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates"
}

BASE_URL = "https://fr.besoccer.com/competition/rankings/algeria-league-one"

RANKINGS = [
    {"type": "buteurs",          "slug": "buteurs",           "cols": ["goals",    "matches", "ratio"]},
    {"type": "minutes_par_but",  "slug": "plus-minutes",      "cols": ["min_goal", "minutes", "goals"]},
    {"type": "buteurs_penalty",  "slug": "buteurs-penalty",   "cols": ["pen_goals","penalties","ratio"]},
    {"type": "penaltys_manques", "slug": "penaltys-manques",  "cols": ["missed",   "penalties","ratio"]},
    {"type": "meilleurs_gardiens","slug": "meilleurs-gardiens","cols": ["goals_conceded","matches","ratio"]},
]

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# ══════════════════════════════════════════════
# FETCH AVEC RETRY
# ══════════════════════════════════════════════

def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            r = scraper.get(url, timeout=30)
            if r.status_code == 200:
                print(f"  ✅ GET 200 : {url}")
                return r
            print(f"  ⚠️  GET {r.status_code} (tentative {attempt+1}/{retries}) : {url}")
        except Exception as e:
            print(f"  ❌ Erreur (tentative {attempt+1}/{retries}) : {e}")
        if attempt < retries - 1:
            time.sleep(3)
    return None

# ══════════════════════════════════════════════
# PARSER UNE LIGNE JOUEUR
# ══════════════════════════════════════════════

def extract_player_id(url):
    m = re.search(r"-(\d+)/?$", url)
    return m.group(1) if m else None

def parse_row(tr, col_names):
    try:
        # ── Données ld+json (nom, poste, club, url, photo) ──────────
        script = tr.select_one('script[type="application/ld+json"]')
        if not script:
            return None
        data = json.loads(script.string)

        name      = data.get("name", "").strip()
        position  = data.get("jobTitle", "").strip()
        team      = data.get("worksFor", "").strip()
        photo     = data.get("image", "").strip()
        player_url= data.get("url", "").strip()
        player_id = extract_player_id(player_url)

        if not name or not player_id:
            return None

        # ── Logo club ────────────────────────────────────────────────
        shield = tr.select_one("img.shield, img.align-middle.shield")
        team_logo = shield["src"] if shield and shield.get("src") else ""

        # ── Valeurs numériques (colonnes td) ─────────────────────────
        tds = tr.select("td")
        # td[0] = photo, td[1] = nom+club, td[2..] = stats
        values = [td.get_text(strip=True) for td in tds[2:]]

        result = {
            "name":      name,
            "player_id": player_id,
            "photo":     photo,
            "team":      team,
            "team_logo": team_logo,
            "position":  position,
            "player_url": player_url,
        }
        for i, col in enumerate(col_names):
            result[col] = values[i] if i < len(values) else None

        return result

    except Exception as e:
        print(f"    ⚠️  Erreur parse_row: {e}")
        return None

# ══════════════════════════════════════════════
# SCRAPER UN CLASSEMENT
# ══════════════════════════════════════════════

def scrape_ranking(ranking_type, slug, col_names, season):
    url = f"{BASE_URL}/{season}/{slug}"
    r   = fetch(url)
    if not r:
        print(f"  ❌ Impossible de scraper {ranking_type} saison {season}")
        return []

    soup    = BeautifulSoup(r.text, "html.parser")
    rows    = soup.select("table tbody tr")
    results = []

    for rank, tr in enumerate(rows, start=1):
        player = parse_row(tr, col_names)
        if player:
            player["rank"]   = rank
            player["type"]   = ranking_type
            player["season"] = season
            results.append(player)

    print(f"  📊 {ranking_type} saison {season} : {len(results)} joueurs")
    return results

# ══════════════════════════════════════════════
# RÉCUPÉRER LES SAISONS DISPONIBLES
# ══════════════════════════════════════════════

def get_available_seasons():
    url = f"{BASE_URL}/2026/buteurs"
    r   = fetch(url)
    if not r:
        return [2026]

    soup    = BeautifulSoup(r.text, "html.parser")
    sel     = soup.select_one("select#season")
    if not sel:
        return [2026]

    seasons = []
    for opt in sel.select("option"):
        val = opt.get("value", "").strip()
        if val and val.isdigit():
            seasons.append(int(val))

    seasons.sort(reverse=True)
    print(f"  📅 {len(seasons)} saisons trouvées : {seasons[0]} → {seasons[-1]}")
    return seasons

# ══════════════════════════════════════════════
# SUPABASE — SAUVEGARDER
# ══════════════════════════════════════════════

def save_to_supabase(records):
    if not records:
        return

    # Aplatir pour Supabase (une ligne = un joueur dans un classement)
    rows = []
    now  = datetime.now(timezone.utc).isoformat()
    for r in records:
        rows.append({
            "type":           r.get("type"),
            "season":         r.get("season"),
            "rank":           r.get("rank"),
            "name":           r.get("name"),
            "player_id":      r.get("player_id"),
            "photo":          r.get("photo"),
            "team":           r.get("team"),
            "team_logo":      r.get("team_logo"),
            "position":       r.get("position"),
            "player_url":     r.get("player_url"),
            "value1":         r.get(list(r.keys())[7]) if len(r) > 7 else None,
            "value2":         r.get(list(r.keys())[8]) if len(r) > 8 else None,
            "value3":         r.get(list(r.keys())[9]) if len(r) > 9 else None,
            "col1_name":      r.get("_col1"),
            "col2_name":      r.get("_col2"),
            "col3_name":      r.get("_col3"),
            "scraped_at":     now,
        })

    # Envoyer par batch de 100
    batch_size = 100
    total_ok   = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        res = requests.post(
            SB_URL + "/rest/v1/algeria_rankings",
            headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
            params={"on_conflict": "type,season,rank"},
            json=batch
        )
        if res.status_code in [200, 201, 204]:
            total_ok += len(batch)
        else:
            print(f"  ❌ Supabase erreur {res.status_code}: {res.text[:200]}")

    print(f"  ✅ Supabase: {total_ok}/{len(rows)} lignes sauvegardées")

# ══════════════════════════════════════════════
# SAUVEGARDER EN JSON LOCAL
# ══════════════════════════════════════════════

def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  💾 Fichier : {filename}")

# ══════════════════════════════════════════════
# MODE 1 — SAISON EN COURS
# ══════════════════════════════════════════════

def mode_current_season():
    today  = date.today()
    season = today.year if today.month >= 7 else today.year
    # BeSoccer utilise l'année de fin de saison (2026 = saison 2025-26)
    # Ajustement : si on est après juillet, c'est la saison year+1
    season = today.year + 1 if today.month >= 7 else today.year

    print(f"\n{'='*50}")
    print(f"MODE 1 — Saison en cours : {season}")
    print(f"{'='*50}")

    all_records = []
    for ranking in RANKINGS:
        print(f"\n🔍 Scraping {ranking['type']}...")
        records = scrape_ranking(
            ranking["type"],
            ranking["slug"],
            ranking["cols"],
            season
        )
        # Ajouter les noms de colonnes
        for r in records:
            r["_col1"] = ranking["cols"][0] if len(ranking["cols"]) > 0 else None
            r["_col2"] = ranking["cols"][1] if len(ranking["cols"]) > 1 else None
            r["_col3"] = ranking["cols"][2] if len(ranking["cols"]) > 2 else None
        all_records.extend(records)
        time.sleep(2)

    # JSON local
    filename = f"algeria_rankings_{today.strftime('%Y-%m-%d')}.json"
    save_json({"season": season, "date": today.isoformat(), "data": all_records}, filename)

    # Supabase
    print(f"\n💾 Sauvegarde Supabase ({len(all_records)} entrées)...")
    save_to_supabase(all_records)

    print(f"\n✅ Mode 1 terminé — {len(all_records)} entrées")

# ══════════════════════════════════════════════
# MODE 2 — TOUTES LES SAISONS
# ══════════════════════════════════════════════

def mode_all_seasons():
    print(f"\n{'='*50}")
    print("MODE 2 — Toutes les saisons (historique)")
    print(f"{'='*50}")

    seasons    = get_available_seasons()
    global_data = {}
    total      = 0

    for season in seasons:
        print(f"\n{'─'*40}")
        print(f"📅 Saison {season}")
        print(f"{'─'*40}")

        season_records = []
        for ranking in RANKINGS:
            print(f"\n  🔍 {ranking['type']}...")
            records = scrape_ranking(
                ranking["type"],
                ranking["slug"],
                ranking["cols"],
                season
            )
            for r in records:
                r["_col1"] = ranking["cols"][0] if len(ranking["cols"]) > 0 else None
                r["_col2"] = ranking["cols"][1] if len(ranking["cols"]) > 1 else None
                r["_col3"] = ranking["cols"][2] if len(ranking["cols"]) > 2 else None
            season_records.extend(records)
            time.sleep(2)

        # JSON par saison
        filename = f"algeria_rankings_{season}.json"
        save_json({"season": season, "data": season_records}, filename)

        # Supabase
        if season_records:
            print(f"\n  💾 Supabase saison {season}...")
            save_to_supabase(season_records)

        global_data[str(season)] = season_records
        total += len(season_records)
        print(f"  ✅ Saison {season} : {len(season_records)} entrées")
        time.sleep(2)

    # JSON global consolidé
    save_json(global_data, "algeria_rankings_all_seasons.json")
    print(f"\n✅ Mode 2 terminé — {total} entrées au total sur {len(seasons)} saisons")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

print("=== BeSoccer Algeria Rankings Scraper ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

if "--all" in sys.argv:
    mode_all_seasons()
else:
    mode_current_season()

print("\n=== Terminé ===")