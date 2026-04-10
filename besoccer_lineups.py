"""
besoccer_lineups.py
===================
Scrape les compositions Ligue 1 Algérie depuis BeSoccer.
Stratégie : URLs des matchs construites depuis algeria_lineups (Flashscore)
+ lookup BeSoccer via /match/home-slug/away-slug/ID
"""

import os, re, time, requests, json
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

# Mapping Supabase → slugs BeSoccer (home/away dans l'URL)
TEAM_SLUG = {
    "MC Alger":        "mc-alger",
    "CR Belouizdad":   "belouizdad",
    "JS Kabylie":      "kabylie",
    "USM Alger":       "usm-alger",
    "ES Setif":        "es-setif",
    "CS Constantine":  "cs-constantine",
    "Paradou AC":      "paradou",
    "ASO Chlef":       "chlef",
    "MC Oran":         "mc-oran",
    "JS Saoura":       "js-saoura",
    "MC El Bayadh":    "el-bayadh",
    "USM Khenchela":   "usm-khenchela",
    "Olympique Akbou": "oued-akbou",
    "ES Mostaganem":   "es-mostaganem",
    "MB Rouissat":     "mb-rouisset",
    "ES Ben Aknoun":   "ben-aknoun",
}

# ══════════════════════════════════════════════
# CLOUDSCRAPER
# ══════════════════════════════════════════════

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

def fetch(url):
    try:
        r = scraper.get(url, timeout=20)
        print(f"  GET {r.status_code} : {url}")
        return r if r.status_code == 200 else None
    except Exception as e:
        print(f"  Erreur: {e}")
        return None

def extract_player_id(href):
    if not href: return None
    m = re.search(r"/player/[^/]+-(\d+)/?$", href)
    if m: return m.group(1)
    m = re.search(r"/player/([^/]+)/?$", href)
    return m.group(1) if m else None

# ══════════════════════════════════════════════
# TROUVER L'ID BESOCCER D'UN MATCH
# ══════════════════════════════════════════════

def find_besoccer_match_id(home_team, away_team, match_date):
    """
    Cherche l'ID BeSoccer d'un match via la page de l'équipe domicile.
    URL format : /team/matches/slug/id/
    On connaît le format de l'ID BeSoccer : 2026XXXXXX (6 chiffres après 2026)
    """
    home_slug = TEAM_SLUG.get(home_team, "")
    away_slug = TEAM_SLUG.get(away_team, "")
    if not home_slug or not away_slug:
        print(f"  ⚠️  Slug manquant: {home_team} / {away_team}")
        return None, None

    # Chercher dans la page matches de l'équipe domicile
    club_ids = {
        "MC Alger": 11505, "CR Belouizdad": 11507, "JS Kabylie": 11506,
        "USM Alger": 11504, "ES Setif": 11501, "CS Constantine": 11510,
        "Paradou AC": 59336, "ASO Chlef": 11511, "MC Oran": 11509,
        "JS Saoura": 20933, "MC El Bayadh": 11729, "USM Khenchela": 11530,
        "Olympique Akbou": 11522, "ES Mostaganem": 13715,
        "MB Rouissat": 100882, "ES Ben Aknoun": 11519,
    }
    club_id = club_ids.get(home_team)
    if not club_id:
        return None, None

    url = f"https://www.besoccer.com/team/matches/{home_slug}/{club_id}/"
    r = fetch(url)
    if not r:
        return None, None

    # Chercher les liens de matchs contenant away_slug
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.select(f"a[href*='/match/'][href*='{away_slug}']"):
        href = a.get("href", "")
        # Extraire l'ID numérique
        m = re.search(r"/match/[^/]+/[^/]+/(\d+)/?", href)
        if m:
            match_id = m.group(1)
            match_url = "https://www.besoccer.com" + href if href.startswith("/") else href
            # Vérifier que c'est bien le bon match (date dans le texte parent)
            parent = a.find_parent(["tr", "li", "div"])
            row_text = parent.get_text(" ") if parent else ""
            # Chercher la date
            date_formats = [
                date.today().strftime("%-d %b. %Y"),
                date.today().strftime("%d/%m/%Y"),
                date.today().strftime("%Y-%m-%d"),
            ]
            if any(d in row_text for d in date_formats) or match_date in match_id[:4]:
                print(f"  ✅ Trouvé: {match_url}")
                return match_id, match_url

    # Fallback : prendre l'ID le plus grand (matchs de ligue > matchs de coupe)
    best_id = None
    best_url = None
    for a in soup.select(f"a[href*='/match/'][href*='{away_slug}']"):
        href = a.get("href", "")
        m = re.search(r"/match/[^/]+/[^/]+/(\d+)/?", href)
        if m:
            mid = m.group(1)
            try:
                if best_id is None or int(mid) > int(best_id):
                    best_id = mid
                    best_url = "https://www.besoccer.com" + href if href.startswith("/") else href
            except:
                pass
    if best_id:
        print(f"  ✅ Trouvé (best id): {best_url}")
        return best_id, best_url

    return None, None

# ══════════════════════════════════════════════
# MATCHS DU JOUR depuis Supabase algeria_lineups
# ══════════════════════════════════════════════

def get_today_matches():
    today   = date.today().strftime("%Y-%m-%d")
    matches = []
    seen    = set()

    print(f"\nRecherche matchs du {today}...")

    # Chercher les matchs du jour dans algeria_lineups (source Flashscore)
    try:
        r = requests.get(
            SB_URL + f"/rest/v1/algeria_lineups?match_date=eq.{today}&select=home_team,away_team,fixture_id",
            headers={**SB_HEADERS, "Prefer": ""}
        )
        rows = r.json() if r.status_code == 200 else []
        print(f"  {len(rows)} matchs dans algeria_lineups")
    except Exception as e:
        print(f"  Erreur Supabase: {e}")
        rows = []

    # Si pas de données dans algeria_lineups, utiliser les IDs BeSoccer connus
    # IDs découverts manuellement depuis les pages de match BeSoccer
    if not rows:
        print("  Utilisation IDs BeSoccer connus...")
        today = date.today().strftime("%Y-%m-%d")
        KNOWN_IDS = {
            "2026-04-10": [
                {"home_team": "ES Ben Aknoun",   "away_team": "ASO Chlef",       "bs_id": "2026264208", "bs_home": "ben-aknoun",    "bs_away": "chlef"},
                {"home_team": "ES Mostaganem",   "away_team": "USM Khenchela",   "bs_id": "2026264210", "bs_home": "es-mostaganem", "bs_away": "usm-khenchela"},
                {"home_team": "JS Kabylie",      "away_team": "CS Constantine",  "bs_id": "2026264214", "bs_home": "kabylie",       "bs_away": "cs-constantine"},
            ],
            "2026-04-11": [
                {"home_team": "Olympique Akbou", "away_team": "ES Setif",        "bs_id": "2026264207", "bs_home": "oued-akbou",    "bs_away": "es-setif"},
                {"home_team": "Paradou AC",      "away_team": "JS Saoura",       "bs_id": "2026264211", "bs_home": "paradou",       "bs_away": "js-saoura"},
            ],
            "2026-04-16": [
                {"home_team": "CS Constantine",  "away_team": "MC Alger",        "bs_id": "2026264221", "bs_home": "cs-constantine","bs_away": "mc-alger"},
            ],
            "2026-04-17": [
                {"home_team": "MB Rouissat",     "away_team": "JS Kabylie",      "bs_id": "2026264220", "bs_home": "mb-rouisset",   "bs_away": "kabylie"},
                {"home_team": "ASO Chlef",       "away_team": "Olympique Akbou", "bs_id": "2026264215", "bs_home": "chlef",         "bs_away": "oued-akbou"},
                {"home_team": "MC El Bayadh",    "away_team": "Paradou AC",      "bs_id": "2026264216", "bs_home": "el-bayadh",     "bs_away": "paradou"},
                {"home_team": "JS Saoura",       "away_team": "USM Khenchela",   "bs_id": "2026264219", "bs_home": "js-saoura",     "bs_away": "usm-khenchela"},
                {"home_team": "ES Setif",        "away_team": "MC Oran",         "bs_id": "2026264222", "bs_home": "es-setif",      "bs_away": "mc-oran"},
            ],
            "2026-05-09": [
                {"home_team": "JS Kabylie",      "away_team": "ES Setif",        "bs_id": "2026264223", "bs_home": "kabylie",       "bs_away": "es-setif"},
                {"home_team": "ES Mostaganem",   "away_team": "JS Saoura",       "bs_id": "2026264224", "bs_home": "es-mostaganem", "bs_away": "js-saoura"},
                {"home_team": "MC Alger",        "away_team": "MB Rouissat",     "bs_id": "2026264225", "bs_home": "mc-alger",      "bs_away": "mb-rouisset"},
                {"home_team": "Paradou AC",      "away_team": "CS Constantine",  "bs_id": "2026264226", "bs_home": "paradou",       "bs_away": "cs-constantine"},
                {"home_team": "USM Khenchela",   "away_team": "MC El Bayadh",    "bs_id": "2026264227", "bs_home": "usm-khenchela", "bs_away": "el-bayadh"},
                {"home_team": "ES Ben Aknoun",   "away_team": "USM Alger",       "bs_id": "2026264228", "bs_home": "ben-aknoun",    "bs_away": "usm-alger"},
                {"home_team": "MC Oran",         "away_team": "ASO Chlef",       "bs_id": "2026264229", "bs_home": "mc-oran",       "bs_away": "chlef"},
                {"home_team": "Olympique Akbou", "away_team": "CR Belouizdad",   "bs_id": "2026264230", "bs_home": "oued-akbou",    "bs_away": "belouizdad"},
            ],
            "2026-05-15": [
                {"home_team": "MC El Bayadh",    "away_team": "JS Saoura",       "bs_id": "2026264231", "bs_home": "el-bayadh",     "bs_away": "js-saoura"},
                {"home_team": "CS Constantine",  "away_team": "USM Khenchela",   "bs_id": "2026264232", "bs_home": "cs-constantine","bs_away": "usm-khenchela"},
                {"home_team": "ES Setif",        "away_team": "MC Alger",        "bs_id": "2026264233", "bs_home": "es-setif",      "bs_away": "mc-alger"},
                {"home_team": "CR Belouizdad",   "away_team": "MC Oran",         "bs_id": "2026264234", "bs_home": "belouizdad",    "bs_away": "mc-oran"},
                {"home_team": "USM Alger",       "away_team": "Olympique Akbou", "bs_id": "2026264235", "bs_home": "usm-alger",     "bs_away": "oued-akbou"},
                {"home_team": "ASO Chlef",       "away_team": "JS Kabylie",      "bs_id": "2026264236", "bs_home": "chlef",         "bs_away": "kabylie"},
                {"home_team": "ES Ben Aknoun",   "away_team": "ES Mostaganem",   "bs_id": "2026264237", "bs_home": "ben-aknoun",    "bs_away": "es-mostaganem"},
                {"home_team": "MB Rouissat",     "away_team": "Paradou AC",      "bs_id": "2026264238", "bs_home": "mb-rouisset",   "bs_away": "paradou"},
            ],
            "2026-05-22": [
                {"home_team": "ES Mostaganem",   "away_team": "MC El Bayadh",    "bs_id": "2026264432", "bs_home": "es-mostaganem", "bs_away": "el-bayadh"},
                {"home_team": "JS Saoura",       "away_team": "CS Constantine",  "bs_id": "2026264433", "bs_home": "js-saoura",     "bs_away": "cs-constantine"},
                {"home_team": "USM Khenchela",   "away_team": "MB Rouissat",     "bs_id": "2026264434", "bs_home": "usm-khenchela", "bs_away": "mb-rouisset"},
                {"home_team": "Paradou AC",      "away_team": "ES Setif",        "bs_id": "2026264435", "bs_home": "paradou",       "bs_away": "es-setif"},
                {"home_team": "MC Alger",        "away_team": "ASO Chlef",       "bs_id": "2026264436", "bs_home": "mc-alger",      "bs_away": "chlef"},
                {"home_team": "JS Kabylie",      "away_team": "CR Belouizdad",   "bs_id": "2026264437", "bs_home": "kabylie",       "bs_away": "belouizdad"},
                {"home_team": "MC Oran",         "away_team": "USM Alger",       "bs_id": "2026264438", "bs_home": "mc-oran",       "bs_away": "usm-alger"},
                {"home_team": "Olympique Akbou", "away_team": "ES Ben Aknoun",   "bs_id": "2026264439", "bs_home": "oued-akbou",    "bs_away": "ben-aknoun"},
            ],
        }
        day_matches = KNOWN_IDS.get(today, [])
        for m in day_matches:
            rows.append({"home_team": m["home_team"], "away_team": m["away_team"],
                         "bs_id": m.get("bs_id"), "bs_home": m.get("bs_home"), "bs_away": m.get("bs_away")})

    # Construire l'index des IDs connus pour aujourd'hui
    known_today = {f"{m['home_team']}_{m['away_team']}": m
                   for m in KNOWN_IDS.get(today, [])}

    for row in rows:
        home = row.get("home_team", "")
        away = row.get("away_team", "")
        if not home or not away:
            continue

        key = f"{home}_{away}"
        if key in seen:
            continue
        seen.add(key)

        print(f"\n  🔍 {home} vs {away}")

        # Priorité 1 : ID connu dans KNOWN_IDS
        known = known_today.get(key)
        if known and known.get("bs_id"):
            bs_id   = known["bs_id"]
            bs_home = known["bs_home"]
            bs_away = known["bs_away"]
            match_url = f"https://www.besoccer.com/match/{bs_home}/{bs_away}/{bs_id}"
            print(f"  ✅ ID connu: {match_url}")
            match_id = bs_id
        # Priorité 2 : ID dans le row (depuis Supabase)
        elif row.get("bs_id"):
            bs_id   = row["bs_id"]
            bs_home = row.get("bs_home", TEAM_SLUG.get(home, ""))
            bs_away = row.get("bs_away", TEAM_SLUG.get(away, ""))
            match_url = f"https://www.besoccer.com/match/{bs_home}/{bs_away}/{bs_id}"
            print(f"  ✅ ID direct: {match_url}")
            match_id = bs_id
        # Priorité 3 : chercher sur BeSoccer
        else:
            match_id, match_url = find_besoccer_match_id(home, away, today[:4])

        if match_id:
            matches.append({
                "match_id":  match_id,
                "url":       match_url,
                "home_team": home,
                "away_team": away,
                "date":      today
            })
        else:
            print(f"  ⚠️  Match BeSoccer non trouvé pour {home} vs {away}")

        time.sleep(1)

    return matches

# ══════════════════════════════════════════════
# DÉTECTION COMPO OFFICIELLE
# ══════════════════════════════════════════════

def is_official(soup):
    if not soup: return False
    text = soup.get_text(" ").lower()
    official_kw = ["alineacion oficial", "official lineup", "confirmed",
                   "confirmé", "alineación oficial"]
    probable_kw = ["probable", "predicted", "prevista", "prévu", "expected"]
    has_official = any(k in text for k in official_kw)
    has_probable = any(k in text for k in probable_kw)
    lineup_section = soup.select_one(".match-lineup, .lineup, [class*='lineup'], .alineacion")
    if lineup_section:
        players = lineup_section.select("a[href*='/player/']")
        if len(players) >= 11 and not has_probable:
            return True
    return has_official and not has_probable

# ══════════════════════════════════════════════
# SCRAPE COMPOSITION
# ══════════════════════════════════════════════

def scrape_lineup(match):
    r = fetch(match["url"])
    if not r: return None
    soup = BeautifulSoup(r.text, "html.parser")

    # Log HTML pour debug lors du premier vrai match
    print(f"  HTML size: {len(r.text)} chars")

    if not is_official(soup):
        print(f"  ⏳ Compos pas encore officielles")
        # Log ce qu'on trouve pour debug
        lineup_els = soup.select("a[href*='/player/']")
        print(f"  Liens joueurs trouvés: {len(lineup_els)}")
        return None

    result = {
        "match_id":       match["match_id"],
        "home_team":      match.get("home_team", ""),
        "away_team":      match.get("away_team", ""),
        "match_date":     match["date"],
        "home_players":   [],
        "away_players":   [],
        "home_subs":      [],
        "away_subs":      [],
        "home_formation": "",
        "away_formation": "",
        "scraped_at":     datetime.now(timezone.utc).isoformat()
    }

    formations = [f.get_text(strip=True) for f in soup.select(".formation, [class*='formation']")
                  if re.match(r"\d-\d", f.get_text(strip=True))]
    if formations: result["home_formation"] = formations[0]
    if len(formations) >= 2: result["away_formation"] = formations[1]

    team_sections = soup.select(
        ".lineup-team, [class*='lineup-team'], .match-lineup .team, .alineacion .equipo"
    )

    for idx, section in enumerate(team_sections[:2]):
        key_pl  = "home_players" if idx == 0 else "away_players"
        key_sub = "home_subs"    if idx == 0 else "away_subs"
        starters, subs = [], []

        for i, link in enumerate(section.select("a[href*='/player/']")):
            player_id = extract_player_id(link.get("href", ""))
            nom       = link.get_text(strip=True)
            if not player_id or not nom: continue
            parent = link.find_parent(["li", "tr", "div"])
            pos_el = parent.select_one(".pos, .position, .demarcacion") if parent else None
            num_el = parent.select_one(".num, .number, .dorsal") if parent else None
            player = {
                "name": nom, "id": player_id,
                "number": num_el.get_text(strip=True) if num_el else "",
                "pos": pos_el.get_text(strip=True) if pos_el else "",
                "photo": f"https://cdn.resfu.com/img_data/players/medium/{player_id}.jpg?size=120x&lossy=1",
                "goals": 0, "yellow": False, "red": False,
                "minutes": 90 if i < 11 else 0,
            }
            (starters if i < 11 else subs).append(player)

        result[key_pl]  = starters
        result[key_sub] = subs

    h, a = len(result["home_players"]), len(result["away_players"])
    print(f"  ✅ Compo : {h} vs {a} | {result['home_formation']} / {result['away_formation']}")
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
    print(f"  Supabase: {'✅ OK' if code in [200,201,204] else '❌ '+str(code)+' '+res.text[:100]}")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

print("=== BeSoccer Lineups Scraper ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

matches = get_today_matches()
print(f"\nMatchs trouvés : {len(matches)}")

if not matches:
    print("Aucun match — OK")
    exit(0)

for match in matches:
    print(f"\n--- {match.get('home_team')} vs {match.get('away_team')} | id={match['match_id']} ---")
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