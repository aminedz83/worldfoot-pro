"""
besoccer_lineups.py
===================
Scrape les compositions Ligue 1 Algérie depuis BeSoccer.
Utilise l'endpoint AJAX réel : POST /ajax/getCompetitionRounds
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

# ══════════════════════════════════════════════
# CLOUDSCRAPER
# ══════════════════════════════════════════════

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

def fetch_html(url):
    try:
        r = scraper.get(url, timeout=20)
        print(f"  GET {r.status_code} : {url}")
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
        return None
    except Exception as e:
        print(f"  Erreur: {e}")
        return None

def post_ajax(data_params, round_num=None):
    """
    Appelle POST /ajax/getCompetitionRounds comme le fait le JS de BeSoccer.
    data_params = le contenu de data-params du div#data_params
    """
    req = dict(data_params)
    if round_num:
        req["round"] = str(round_num)

    payload = {
        "dataInfo":     json.dumps(req),
        "offsetName":   "Africa/Algiers",
        "onchange":     "false",
        "isCompetition": "1"
    }

    headers = {
        "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept":       "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer":      "https://www.besoccer.com/competition/scores/ligue_1_algeria/2026",
        "Origin":       "https://www.besoccer.com",
    }

    try:
        r = scraper.post(
            "https://www.besoccer.com/ajax/getCompetitionRounds",
            data=payload,
            headers=headers,
            timeout=20
        )
        print(f"  AJAX POST {r.status_code}")
        if r.status_code == 200:
            result = json.loads(r.text)
            return result.get("html", "")
        return None
    except Exception as e:
        print(f"  Erreur AJAX: {e}")
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
# MATCHS DU JOUR
# ══════════════════════════════════════════════

def get_data_params():
    """Récupère les data-params depuis la page de la compétition."""
    soup = fetch_html("https://www.besoccer.com/competition/ligue_1_algeria")
    if not soup:
        return None
    div = soup.select_one("#data_params")
    if not div:
        return None
    try:
        params = json.loads(div.get("data-params", "{}"))
        return params.get("req", {})
    except:
        return None

def get_today_matches():
    today     = date.today().strftime("%Y-%m-%d")
    today_apr = date.today().strftime("%-d %b. %Y")   # "10 Apr. 2026"
    today_dmy = date.today().strftime("%d/%m/%Y")
    matches   = []
    seen      = set()

    print(f"\nRecherche matchs du {today}...")

    # Récupérer les data-params
    data_params = get_data_params()
    if not data_params:
        print("  ❌ Impossible de récupérer data-params")
        return []

    current_round = int(data_params.get("round", 26))
    print(f"  Round actuel: {current_round}")

    # Essayer round actuel + voisins
    for round_num in [current_round, current_round - 1, current_round + 1]:
        print(f"  Essai round {round_num}...")
        html = post_ajax(data_params, round_num)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        # Chercher les liens de matchs avec leur date
        for a in soup.select("a[href*='/match/']"):
            href     = a.get("href", "")
            match_id = extract_match_id(href)
            if not match_id or match_id in seen:
                continue

            # Vérifier la date dans le parent
            parent    = a.find_parent(["tr", "li", "div", "article"])
            row_text  = parent.get_text(" ") if parent else ""
            date_el   = parent.select_one(".date, time, [class*='date']") if parent else None
            date_text = date_el.get_text(strip=True) if date_el else ""

            is_today = any(d in row_text or d in date_text
                          for d in [today, today_apr, today_dmy])

            if not is_today:
                continue

            seen.add(match_id)
            match_url = "https://www.besoccer.com" + href if href.startswith("/") else href

            # Noms équipes
            home_el = parent.select_one(".team-name.ta-r, .local .team-name") if parent else None
            away_el = parent.select_one(".team-name.ta-l, .visitor .team-name") if parent else None

            matches.append({
                "match_id":  match_id,
                "url":       match_url,
                "home_team": home_el.get_text(strip=True) if home_el else "",
                "away_team": away_el.get_text(strip=True) if away_el else "",
                "date":      today
            })
            print(f"  ✅ Match trouvé: {match_id} | {match_url}")

        time.sleep(1)

    return matches

# ══════════════════════════════════════════════
# DÉTECTION COMPO OFFICIELLE
# ══════════════════════════════════════════════

def is_official(soup):
    if not soup:
        return False
    text = soup.get_text(" ").lower()
    official_kw = ["alineacion oficial", "official lineup", "confirmed",
                   "confirmé", "alineación oficial"]
    probable_kw = ["probable", "predicted", "prevista", "prévu", "expected"]
    has_official = any(k in text for k in official_kw)
    has_probable = any(k in text for k in probable_kw)

    lineup_section = soup.select_one(
        ".match-lineup, .lineup, [class*='lineup'], .alineacion"
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
    soup = fetch_html(match["url"])
    if not soup:
        return None

    if not is_official(soup):
        print(f"  ⏳ Compos pas encore officielles")
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

    # Formation
    formations = [f.get_text(strip=True) for f in soup.select(".formation, [class*='formation']")
                  if re.match(r"\d-\d", f.get_text(strip=True))]
    if len(formations) >= 1: result["home_formation"] = formations[0]
    if len(formations) >= 2: result["away_formation"] = formations[1]

    # Sections équipes
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
print(f"\nMatchs aujourd'hui : {len(matches)}")

if not matches:
    print("Aucun match — OK")
    exit(0)

for match in matches:
    print(f"\n--- {match.get('home_team','?')} vs {match.get('away_team','?')} | id={match['match_id']} ---")
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