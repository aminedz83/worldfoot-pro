"""
besoccer_lineups.py
===================
Scrape les compositions des matchs de Ligue 1 Algérie depuis BeSoccer.
Tourne toutes les 5 minutes pour détecter les compos officielles.
Sauvegarde dans Supabase : besoccer_lineups
"""

import os, re, time, requests
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

# Slugs corrigés (identiques au players scraper)
CLUBS = [
    {"name": "MC Alger",        "slug": "mc-alger",       "id": 11505},
    {"name": "CR Belouizdad",   "slug": "belouizdad",     "id": 11507},
    {"name": "JS Kabylie",      "slug": "kabylie",        "id": 11506},
    {"name": "USM Alger",       "slug": "usm-alger",      "id": 11504},
    {"name": "ES Sétif",        "slug": "es-setif",       "id": 11501},
    {"name": "CS Constantine",  "slug": "cs-constantine", "id": 11510},
    {"name": "Paradou AC",      "slug": "paradou",        "id": 59336},
    {"name": "ASO Chlef",       "slug": "chlef",          "id": 11511},
    {"name": "MC Oran",         "slug": "mc-oran",        "id": 11509},
    {"name": "JS Saoura",       "slug": "js-saoura",      "id": 20933},
    {"name": "MC El Bayadh",    "slug": "el-bayadh",      "id": 11729},
    {"name": "USM Khenchela",   "slug": "usm-khenchela",  "id": 11530},
    {"name": "Olympique Akbou", "slug": "oued-akbou",     "id": 11522},
    {"name": "ES Mostaganem",   "slug": "es-mostaganem",  "id": 13715},
    {"name": "MB Rouissat",     "slug": "mb-rouisset",    "id": 100882},
    {"name": "ES Ben Aknoun",   "slug": "ben-aknoun",     "id": 11519},
]

# ══════════════════════════════════════════════
# CLOUDSCRAPER (même config que players scraper)
# ══════════════════════════════════════════════

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

def fetch(url):
    try:
        r = scraper.get(url, timeout=20)
        print(f"  Status {r.status_code} : {url}")
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
        return None
    except Exception as e:
        print(f"  Erreur: {e}")
        return None

def extract_player_id(href):
    if not href:
        return None
    m = re.search(r"/player/[^/]+-(\d+)/?$", href)
    if m:
        return m.group(1)
    m = re.search(r"/player/([^/]+)/?$", href)
    return m.group(1) if m else None

def extract_match_id(href):
    if not href:
        return None
    # Format BeSoccer : /match/equipe1-equipe2/ID/
    m = re.search(r"/match/[^/]+/(\d+)/?", href)
    return m.group(1) if m else None

# ══════════════════════════════════════════════
# MATCHS DU JOUR
# ══════════════════════════════════════════════

def get_today_matches():
    """Cherche les matchs du jour pour chaque club."""
    today     = date.today().strftime("%Y-%m-%d")
    today_fmt = date.today().strftime("%d/%m/%Y")  # format BeSoccer
    matches   = []
    seen      = set()

    for club in CLUBS:
        url  = f"https://www.besoccer.com/team/matches/{club['slug']}/{club['id']}/"
        soup = fetch(url)
        if not soup:
            time.sleep(1)
            continue

        # Chercher les liens de matchs
        for a in soup.select("a[href*='/match/']"):
            href     = a.get("href", "")
            match_id = extract_match_id(href)
            if not match_id or match_id in seen:
                continue

            # Vérifier la date
            row      = a.find_parent(["tr", "li", "div"])
            row_text = row.get_text(" ") if row else ""

            if today not in row_text and today_fmt not in row_text:
                continue

            seen.add(match_id)

            # Construire l'URL du match
            match_url = "https://www.besoccer.com" + href if href.startswith("/") else href

            # Extraire les slugs depuis l'URL /match/slug1-slug2/id/
            m = re.search(r"/match/([^/]+)/\d+/?", href)
            slugs = m.group(1) if m else ""

            matches.append({
                "match_id":  match_id,
                "url":       match_url,
                "slugs":     slugs,
                "home_team": club["name"],
                "date":      today
            })
            print(f"  ✅ Match trouvé: {slugs} | id={match_id}")

        time.sleep(1)

    return matches

# ══════════════════════════════════════════════
# DÉTECTION COMPO OFFICIELLE
# ══════════════════════════════════════════════

def is_official(soup):
    """Vérifie si les compositions sont officielles."""
    if not soup:
        return False

    text = soup.get_text(" ").lower()

    # Signaux officiels
    official_kw = ["alineacion oficial", "official lineup", "confirmed",
                   "confirmé", "lineup confirmed", "composition officielle"]
    probable_kw = ["probable", "predicted", "prevista", "prévu", "expected"]

    has_official = any(k in text for k in official_kw)
    has_probable = any(k in text for k in probable_kw)

    # Vérifier section lineup avec au moins 11 joueurs sans mot "probable"
    lineup_section = soup.select_one(
        ".match-lineup, .lineup, [class*='lineup'], .team-lineup, .alineacion"
    )
    if lineup_section:
        players = lineup_section.select("a[href*='/player/']")
        if len(players) >= 11 and not has_probable:
            return True

    return has_official and not has_probable

# ══════════════════════════════════════════════
# SCRAPE COMPOSITIONS
# ══════════════════════════════════════════════

def scrape_lineup(match):
    """Scrape la composition d'un match depuis BeSoccer."""
    soup = fetch(match["url"])
    if not soup:
        return None

    if not is_official(soup):
        print(f"  ⏳ Compos pas encore officielles")
        return None

    result = {
        "match_id":       match["match_id"],
        "home_team":      "",
        "away_team":      "",
        "match_date":     match["date"],
        "home_players":   [],
        "away_players":   [],
        "home_subs":      [],
        "away_subs":      [],
        "home_formation": "",
        "away_formation": "",
        "scraped_at":     datetime.now(timezone.utc).isoformat()
    }

    # Noms équipes
    team_names = soup.select(".team-name, .match-team-name, h2.team, .local, .visitante")
    if len(team_names) >= 2:
        result["home_team"] = team_names[0].get_text(strip=True)
        result["away_team"] = team_names[1].get_text(strip=True)

    # Formations
    formations = soup.select(".formation, [class*='formation']")
    if len(formations) >= 1:
        result["home_formation"] = formations[0].get_text(strip=True)
    if len(formations) >= 2:
        result["away_formation"] = formations[1].get_text(strip=True)

    # Sections équipes
    team_sections = soup.select(
        ".lineup-team, .team-lineup, [class*='lineup-team'], "
        ".match-lineup .team, .alineacion .equipo"
    )

    for idx, section in enumerate(team_sections[:2]):
        key_pl  = "home_players" if idx == 0 else "away_players"
        key_sub = "home_subs"    if idx == 0 else "away_subs"

        starters = []
        subs     = []

        for i, link in enumerate(section.select("a[href*='/player/']")):
            href      = link.get("href", "")
            player_id = extract_player_id(href)
            nom       = link.get_text(strip=True)
            if not player_id or not nom:
                continue

            parent = link.find_parent(["li", "tr", "div"])
            pos_el = parent.select_one(".pos, .position, .demarcacion") if parent else None
            num_el = parent.select_one(".num, .number, .dorsal") if parent else None

            player = {
                "name":    nom,
                "id":      player_id,
                "number":  num_el.get_text(strip=True) if num_el else "",
                "pos":     pos_el.get_text(strip=True) if pos_el else "",
                "photo":   f"https://cdn.resfu.com/img_data/players/medium/{player_id}.jpg?size=120x&lossy=1",
                "goals":   0,
                "yellow":  False,
                "red":     False,
                "minutes": 90 if i < 11 else 0,
            }

            if i < 11:
                starters.append(player)
            else:
                subs.append(player)

        result[key_pl]  = starters
        result[key_sub] = subs

    h = len(result["home_players"])
    a = len(result["away_players"])
    print(f"  ✅ Compo officielle : {h} vs {a} titulaires")
    return result

# ══════════════════════════════════════════════
# SUPABASE
# ══════════════════════════════════════════════

def already_scraped(match_id):
    try:
        r = requests.get(
            SB_URL + f"/rest/v1/besoccer_lineups?match_id=eq.{match_id}&select=id,home_players",
            headers={**SB_HEADERS, "Prefer": ""}
        ).json()
        return bool(r and r[0].get("home_players") and len(r[0]["home_players"]) > 0)
    except:
        return False

def save_lineup(lineup):
    res = requests.post(
        SB_URL + "/rest/v1/besoccer_lineups",
        headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
        params={"on_conflict": "match_id"},
        json=lineup
    )
    code = res.status_code
    print(f"  Supabase: {'✅ OK' if code in [200,201,204] else '❌ '+str(code)} ({res.text[:100] if code not in [200,201,204] else ''})")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

print("=== BeSoccer Lineups Scraper ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

matches = get_today_matches()
print(f"\nMatchs aujourd'hui : {len(matches)}")

if not matches:
    print("Aucun match — OK")
    exit(0)

for match in matches:
    print(f"\n--- Match {match['match_id']} : {match['slugs']} ---")

    if already_scraped(match["match_id"]):
        print("  Déjà scrapé ✓")
        continue

    lineup = scrape_lineup(match)
    if lineup:
        save_lineup(lineup)
    else:
        print("  Pas encore dispo")

    time.sleep(2)

print("\n=== Terminé ===")