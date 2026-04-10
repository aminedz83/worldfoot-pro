"""
besoccer_lineups.py
===================
Scrape les compositions des matchs de Ligue 1 Algérie depuis BeSoccer.
Stratégie : cherche les matchs du jour depuis la page de la compétition.
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

# URL de la Ligue 1 Algérie sur BeSoccer
COMPETITION_URL = "https://www.besoccer.com/competition/ligue_1_algeria"

# ══════════════════════════════════════════════
# CLOUDSCRAPER
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
    m = re.search(r"/match/[^/]+/(\d+)/?", href)
    return m.group(1) if m else None

# ══════════════════════════════════════════════
# MATCHS DU JOUR — depuis la page compétition
# ══════════════════════════════════════════════

def get_today_matches():
    """
    Cherche les matchs du jour depuis la page de la Ligue 1 Algérie.
    BeSoccer affiche les matchs avec leurs liens directs.
    """
    today     = date.today().strftime("%Y-%m-%d")
    today_dmy = date.today().strftime("%d/%m/%Y")
    today_dmy2 = date.today().strftime("%d/%m/%y")
    matches   = []
    seen      = set()

    print(f"\nRecherche matchs du {today}...")

    # Page principale de la compétition
    soup = fetch(COMPETITION_URL)
    if not soup:
        print("  ❌ Impossible de charger la page compétition")
        return []

    # Chercher tous les liens de matchs
    for a in soup.select("a[href*='/match/']"):
        href     = a.get("href", "")
        match_id = extract_match_id(href)
        if not match_id or match_id in seen:
            continue

        # Vérifier si c'est un match d'aujourd'hui
        # Chercher la date dans le parent
        parent   = a.find_parent(["tr", "li", "div", "article"])
        row_text = parent.get_text(" ") if parent else a.get_text(" ")

        is_today = (
            today     in row_text or
            today_dmy in row_text or
            today_dmy2 in row_text
        )

        if not is_today:
            continue

        seen.add(match_id)
        match_url = "https://www.besoccer.com" + href if href.startswith("/") else href

        # Extraire les noms des équipes
        home_name = ""
        away_name = ""
        team_els = parent.select(".team-name, .local, .visitante, [class*='team']") if parent else []
        if len(team_els) >= 2:
            home_name = team_els[0].get_text(strip=True)
            away_name = team_els[1].get_text(strip=True)

        # Extraire depuis l'URL : /match/equipe1-equipe2/id/
        m = re.search(r"/match/([^/]+)/\d+/?", href)
        slugs = m.group(1) if m else ""

        matches.append({
            "match_id":  match_id,
            "url":       match_url,
            "slugs":     slugs,
            "home_team": home_name,
            "away_team": away_name,
            "date":      today
        })
        print(f"  ✅ Match trouvé: {slugs} | id={match_id}")

    # Si pas trouvé sur la page principale, essayer la page des résultats du jour
    if not matches:
        print("  Essai page résultats du jour...")
        today_url = COMPETITION_URL + "/results"
        soup2 = fetch(today_url)
        if soup2:
            for a in soup2.select("a[href*='/match/']"):
                href     = a.get("href", "")
                match_id = extract_match_id(href)
                if not match_id or match_id in seen:
                    continue
                parent   = a.find_parent(["tr", "li", "div", "article"])
                row_text = parent.get_text(" ") if parent else ""
                is_today = today in row_text or today_dmy in row_text or today_dmy2 in row_text
                if not is_today:
                    continue
                seen.add(match_id)
                match_url = "https://www.besoccer.com" + href if href.startswith("/") else href
                m = re.search(r"/match/([^/]+)/\d+/?", href)
                slugs = m.group(1) if m else ""
                matches.append({
                    "match_id": match_id,
                    "url":      match_url,
                    "slugs":    slugs,
                    "home_team": "",
                    "away_team": "",
                    "date":     today
                })
                print(f"  ✅ Match trouvé (results): {slugs} | id={match_id}")

    return matches

# ══════════════════════════════════════════════
# DÉTECTION COMPO OFFICIELLE
# ══════════════════════════════════════════════

def is_official(soup):
    if not soup:
        return False
    text = soup.get_text(" ").lower()
    official_kw = ["alineacion oficial", "official lineup", "confirmed",
                   "confirmé", "lineup confirmed", "composition officielle",
                   "alineación oficial"]
    probable_kw = ["probable", "predicted", "prevista", "prévu", "expected"]
    has_official = any(k in text for k in official_kw)
    has_probable = any(k in text for k in probable_kw)

    lineup_section = soup.select_one(
        ".match-lineup, .lineup, [class*='lineup'], .team-lineup, .alineacion"
    )
    if lineup_section:
        players = lineup_section.select("a[href*='/player/']")
        if len(players) >= 11 and not has_probable:
            return True

    return has_official and not has_probable

# ══════════════════════════════════════════════
# SCRAPE COMPOSITION
# ══════════════════════════════════════════════

def scrape_lineup(match):
    soup = fetch(match["url"])
    if not soup:
        return None

    if not is_official(soup):
        print(f"  ⏳ Compos pas encore officielles")
        return None

    today = date.today().strftime("%Y-%m-%d")

    result = {
        "match_id":       match["match_id"],
        "home_team":      match.get("home_team", ""),
        "away_team":      match.get("away_team", ""),
        "match_date":     today,
        "home_players":   [],
        "away_players":   [],
        "home_subs":      [],
        "away_subs":      [],
        "home_formation": "",
        "away_formation": "",
        "scraped_at":     datetime.now(timezone.utc).isoformat()
    }

    # Noms équipes
    team_names = soup.select(".team-name, .match-team-name, h2.team, .local .name, .visitante .name")
    if len(team_names) >= 2:
        result["home_team"] = result["home_team"] or team_names[0].get_text(strip=True)
        result["away_team"] = result["away_team"] or team_names[1].get_text(strip=True)

    # Formation — chercher dans le HTML
    formation_els = soup.select(".formation, [class*='formation'], .tactic, [class*='tactic']")
    formations = [f.get_text(strip=True) for f in formation_els if re.match(r"\d-\d", f.get_text(strip=True))]
    if len(formations) >= 1:
        result["home_formation"] = formations[0]
    if len(formations) >= 2:
        result["away_formation"] = formations[1]

    # Sections équipes
    team_sections = soup.select(
        ".lineup-team, .team-lineup, [class*='lineup-team'], "
        ".match-lineup .team, .alineacion .equipo, .local-lineup, .visitor-lineup"
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
    print(f"  ✅ Compo : {h} vs {a} titulaires | Formation: {result['home_formation']} / {result['away_formation']}")
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
print(f"\nMatchs aujourd'hui : {len(matches)}")

if not matches:
    print("Aucun match — OK")
    exit(0)

for match in matches:
    print(f"\n--- {match['slugs']} | id={match['match_id']} ---")

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