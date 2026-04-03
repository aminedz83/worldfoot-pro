import requests, os, re, json
from datetime import datetime, timezone, date
from bs4 import BeautifulSoup

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

API_KEY = "3a14b1347c177458e2f23bea7899e9cf"
LEAGUE_ID = 186  # Ligue 1 Algérie

# IDs Soccerway des clubs — slug exact depuis les vraies URLs
SW_CLUBS = {
    "JS Kabylie":      {"sw_id": "Wfaskwf0", "slug": "kabylie"},
    "CR Belouizdad":   {"sw_id": "vNJLB2jP", "slug": "belouizdad"},
    "MC Alger":        {"sw_id": "tnY2Lfcp", "slug": "mc-alger"},
    "USM Alger":       {"sw_id": "zXBidj5t", "slug": "usm-alger"},
    "CS Constantine":  {"sw_id": "nBionu2l", "slug": "constantine"},
    "ES Setif":        {"sw_id": "EDgC6qYp", "slug": "setif"},
    "MC Oran":         {"sw_id": "CrCmB35M", "slug": "mc-oran"},
    "ASO Chlef":       {"sw_id": "Aobolc96", "slug": "chlef"},
    "JS Saoura":       {"sw_id": "nimcBvel", "slug": "saoura"},
    "ES Ben Aknoun":   {"sw_id": "QmvZvxCB", "slug": "es-ben-aknoun"},
    "USM Khenchela":   {"sw_id": "lYuJtBj9", "slug": "khenchela"},
    "MB Rouissat":     {"sw_id": "hGHHy7Am", "slug": "rouisset"},
    "Paradou AC":      {"sw_id": "WIyffF3J", "slug": "paradou"},
    "ES Mostaganem":   {"sw_id": "j9T7TM2E", "slug": "mostaganem"},
    "MC El Bayadh":    {"sw_id": "S6H5xCS1", "slug": "el-bayadh"},
    "Olympique Akbou": {"sw_id": "dhMQsMOh", "slug": "olympique-akbou"},
}

TEAM_NAME_MAP = {
    "Kabylie": "JS Kabylie", "Belouizdad": "CR Belouizdad",
    "MC Alger": "MC Alger", "USM Alger": "USM Alger",
    "Constantine": "CS Constantine", "Setif": "ES Setif",
    "Oran": "MC Oran", "Chlef": "ASO Chlef", "Saoura": "JS Saoura",
    "Ben Aknoun": "ES Ben Aknoun", "Khenchela": "USM Khenchela",
    "Rouisset": "MB Rouissat", "Rouissat": "MB Rouissat",
    "Paradou": "Paradou AC", "Mostaganem": "ES Mostaganem",
    "El Bayadh": "MC El Bayadh", "Olympique Akbou": "Olympique Akbou",
    "Akbou": "Olympique Akbou",
}

def normalize_team_name(sw_name):
    if sw_name in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[sw_name]
    for key, val in TEAM_NAME_MAP.items():
        if key.lower() in sw_name.lower():
            return val
    return sw_name

def get_today_fixtures_from_api():
    """Récupère les matchs du jour depuis l'API football.com"""
    today_str = date.today().strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?league={LEAGUE_ID}&season=2024&date={today_str}"
    try:
        r = requests.get(url, headers={"x-apisports-key": API_KEY}, timeout=15)
        print(f"API football status: {r.status_code}")
        data = r.json()
        fixtures = data.get("response", [])
        print(f"Matchs API football aujourd'hui: {len(fixtures)}")
        matches = []
        for f in fixtures:
            home = f["teams"]["home"]["name"]
            away = f["teams"]["away"]["name"]
            fid  = f["fixture"]["id"]
            print(f"  {home} vs {away} (fixture_id={fid})")
            matches.append({
                "home": home, "away": away,
                "fixture_id": fid, "date": today_str
            })
        return matches
    except Exception as e:
        print(f"Erreur API football: {e}")
        return []

def get_mid_from_soccerway(home_name, away_name):
    """
    Construit l'URL Soccerway depuis les IDs clubs et récupère le mid.
    Format URL: /match/{away-slug}-{away-id}/{home-slug}-{home-id}/
    Le mid est dans le HTML de la page ou dans l'URL après redirection.
    """
    home_info = SW_CLUBS.get(home_name)
    away_info = SW_CLUBS.get(away_name)

    if not home_info or not away_info:
        print(f"  IDs Soccerway manquants pour {home_name} ou {away_name}")
        return None

    # Format exact des vraies URLs Soccerway
    url = f"https://fr.soccerway.com/match/{away_info['slug']}-{away_info['sw_id']}/{home_info['slug']}-{home_info['sw_id']}/"
    print(f"  URL Soccerway: {url}")

    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        print(f"  Status: {r.status_code} — URL finale: {r.url[:100]}")

        if r.status_code != 200:
            return None

        # Chercher le mid dans l'URL finale ou dans le HTML
        mid_in_url = re.search(r"mid=([A-Za-z0-9]+)", r.url)
        if mid_in_url:
            return mid_in_url.group(1)

        # Chercher dans le HTML
        soup = BeautifulSoup(r.text, "html.parser")
        mid_links = soup.find_all("a", href=re.compile(r"mid="))
        if mid_links:
            m = re.search(r"mid=([A-Za-z0-9]+)", mid_links[0]["href"])
            if m:
                return m.group(1)

        # Chercher dans les scripts JS
        mid_in_js = re.search(r"['\"]mid['\"]:\s*['\"]([A-Za-z0-9]+)['\"]", r.text)
        if mid_in_js:
            return mid_in_js.group(1)

        # Chercher dans data attributes
        mid_in_data = re.search(r'data-mid="([A-Za-z0-9]+)"', r.text)
        if mid_in_data:
            return mid_in_data.group(1)

        print(f"  Mid non trouvé dans la page — sample HTML: {r.text[1000:1300]}")
        return None

    except Exception as e:
        print(f"  Erreur: {e}")
        return None

def parse_player(text, side):
    if not text or len(text) < 2:
        return None
    text = text.strip()
    is_gk = "(G)" in text or "(GK)" in text
    is_cap = "(C)" in text
    clean = re.sub(r'\(G\)|\(GK\)|\(C\)', '', text).strip()
    if side == "home":
        m = re.match(r'^(\d{1,2})\s+(.+)$', clean)
        if m:
            return {"number": m.group(1), "name": m.group(2).strip(), "is_gk": is_gk, "is_captain": is_cap}
    else:
        m = re.match(r'^(.+?)\s+(\d{1,2})$', clean)
        if m:
            return {"number": m.group(2), "name": m.group(1).strip(), "is_gk": is_gk, "is_captain": is_cap}
    return None

def scrape_lineups(mid):
    url = "https://fr.soccerway.com/game/x/x/summary/lineups/?mid=" + mid
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"  Lineups status: {r.status_code}")
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        if not soup.find(string=re.compile(r"STARTING LINEUP", re.I)):
            print(f"  Pas encore de lineups pour mid={mid}")
            return None
        home_starters, away_starters, home_subs, away_subs = [], [], [], []
        for table in soup.find_all("table"):
            prev = table.find_previous(string=re.compile(r"STARTING LINEUP|SUBSTITUTES", re.I))
            is_sub = prev and "SUBSTITUTE" in prev.upper() if prev else False
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                hp = parse_player(cells[0].get_text(strip=True), "home")
                ap = parse_player(cells[-1].get_text(strip=True), "away")
                if is_sub:
                    if hp: home_subs.append(hp)
                    if ap: away_subs.append(ap)
                else:
                    if hp: home_starters.append(hp)
                    if ap: away_starters.append(ap)
        if home_starters or away_starters:
            print(f"  Titulaires: {len(home_starters)} dom, {len(away_starters)} ext")
            return {
                "home_players": home_starters[:11], "away_players": away_starters[:11],
                "home_subs": home_subs[:9], "away_subs": away_subs[:9]
            }
        return None
    except Exception as e:
        print(f"  Erreur lineups: {e}")
        return None

print("=== Algeria Lineups", datetime.now().strftime("%H:%M:%S"), "===")
today_str = date.today().strftime("%Y-%m-%d")

# Étape 1: matchs du jour depuis API football.com
api_matches = get_today_fixtures_from_api()

if not api_matches:
    print("Aucun match aujourd'hui - OK")
    exit(0)

# Étape 2: pour chaque match, trouver le mid Soccerway
for match in api_matches:
    home = match["home"]
    away = match["away"]
    fixture_id = match["fixture_id"]
    print(f"\n--- {home} vs {away} ---")

    # Vérifier si déjà scraped
    try:
        check = requests.get(
            SB_URL + "/rest/v1/algeria_lineups?fixture_id=eq." + str(fixture_id) + "&select=id,home_players",
            headers=SB_HEADERS
        ).json()
        if check and check[0].get("home_players") and len(check[0]["home_players"]) > 0:
            print("  Déjà scraped")
            continue
    except:
        pass

    # Trouver le mid Soccerway
    mid = get_mid_from_soccerway(home, away)
    if not mid:
        print(f"  Mid Soccerway introuvable pour {home} vs {away}")
        continue

    print(f"  Mid trouvé: {mid}")

    # Scraper les lineups
    lineups = scrape_lineups(mid)
    if lineups:
        res = requests.post(SB_URL + "/rest/v1/algeria_lineups", headers=SB_HEADERS, json={
            "fixture_id": fixture_id,
            "soccerway_mid": mid,
            "home_team": home,
            "away_team": away,
            "match_date": today_str,
            "home_players": lineups["home_players"],
            "away_players": lineups["away_players"],
            "home_subs": lineups.get("home_subs", []),
            "away_subs": lineups.get("away_subs", []),
            "scraped_at": datetime.now(timezone.utc).isoformat()
        })
        print(f"  Sauvegarde: {res.status_code}")
    else:
        print("  Lineups pas encore disponibles")

print("=== Termine ===")