import requests, os, re
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": "https://fr.soccerway.com/"
}

TEAM_NAME_MAP = {
    "Kabylie":          "JS Kabylie",
    "Belouizdad":       "CR Belouizdad",
    "MC Alger":         "MC Alger",
    "USM Alger":        "USM Alger",
    "Constantine":      "CS Constantine",
    "Setif":            "ES Setif",
    "Oran":             "MC Oran",
    "Chlef":            "ASO Chlef",
    "Saoura":           "JS Saoura",
    "Ben Aknoun":       "ES Ben Aknoun",
    "Khenchela":        "USM Khenchela",
    "Rouissat":         "MB Rouissat",
    "Paradou":          "Paradou AC",
    "Mostaganem":       "ES Mostaganem",
    "El Bayadh":        "MC El Bayadh",
    "Akbou":            "Olympique Akbou",
    "Olympique Akbou":  "Olympique Akbou",
}

# IDs Soccerway des clubs — partie de l'URL /teams/slug-ID/
ALGERIA_SW_IDS = [
    "Wfaskwf0",  # JSK
    "vNJLB2jP",  # Belouizdad
    "tnY2Lfcp",  # MC Alger
    "zXBidj5t",  # USM Alger
    "nBionu2l",  # Constantine
    "EDgC6qYp",  # Setif
    "CrCmB35M",  # Oran
    "Aobolc96",  # Chlef
    "nimcBvel",  # Saoura
    "QmvZvxCB",  # Ben Aknoun
    "lYuJtBj9",  # Khenchela
    "hGHHy7Am",  # Rouissat
    "WIyffF3J",  # Paradou
    "j9T7TM2E",  # Mostaganem
    "S6H5xCS1",  # El Bayadh
    "dhMQsMOh",  # Akbou
]

def normalize_team_name(sw_name):
    if sw_name in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[sw_name]
    for sw_key, api_name in TEAM_NAME_MAP.items():
        if sw_key.lower() in sw_name.lower() or sw_name.lower() in sw_key.lower():
            return api_name
    return sw_name

def is_algeria_team(href):
    """Vérifie si un lien /teams/ correspond à un club algérien"""
    for sw_id in ALGERIA_SW_IDS:
        if sw_id in href:
            return True
    return False

def get_team_name_from_href(href):
    """Extrait le nom du club depuis l'URL Soccerway"""
    # Format: /teams/slug-name-SWID/
    parts = href.strip("/").split("/")
    if parts:
        slug = parts[-1] if parts[-1] else parts[-2]
        # Enlever l'ID à la fin du slug
        name = re.sub(r'-[A-Za-z0-9]{6,10}$', '', slug)
        name = name.replace("-", " ").title()
        return name
    return ""

def get_today_fixtures():
    """
    Scrape les matchs du jour depuis Soccerway.
    Nouveau format URL: /match/team1-ID/team2-ID/
    Filtre par IDs des clubs algériens.
    """
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    matches = []

    # URL matchs du jour avec la date
    url = "https://fr.soccerway.com/matches/{}/{}/{}/".format(
        today.strftime("%Y"),
        today.strftime("%m"),
        today.strftime("%d")
    )
    print("URL:", url)

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print("Status:", r.status_code, "| Taille:", len(r.text))

        soup = BeautifulSoup(r.text, "html.parser")

        # Nouveau format Soccerway: liens /match/team1-ID/team2-ID/
        for a in soup.find_all("a", href=re.compile(r"^/match/")):
            href = a.get("href", "")
            # Format: /match/kabylie-Wfaskwf0/ben-aknoun-QmvZvxCB/
            # Vérifier si un des IDs algériens est dans le lien
            home_id = None
            away_id = None
            for sw_id in ALGERIA_SW_IDS:
                if sw_id in href:
                    # Trouver position dans l'URL
                    parts = href.strip("/").split("/")
                    # parts = ["match", "team1-slug-ID", "team2-slug-ID"]
                    if len(parts) >= 3:
                        if sw_id in parts[1]:
                            home_id = sw_id
                        elif sw_id in parts[2]:
                            away_id = sw_id

            # Si au moins une équipe algérienne trouvée
            if not home_id and not away_id:
                continue

            # Extraire les slugs des équipes
            parts = href.strip("/").split("/")
            if len(parts) < 3:
                continue

            home_slug = parts[1]  # ex: "kabylie-Wfaskwf0"
            away_slug = parts[2]  # ex: "ben-aknoun-QmvZvxCB"

            # Le "mid" sera la combinaison des deux slugs (format Soccerway)
            mid = home_slug + "_" + away_slug

            # Extraire noms depuis slugs
            home_sw = re.sub(r'-[A-Za-z0-9]{6,10}$', '', home_slug).replace("-", " ").title()
            away_sw = re.sub(r'-[A-Za-z0-9]{6,10}$', '', away_slug).replace("-", " ").title()

            home_api = normalize_team_name(home_sw)
            away_api = normalize_team_name(away_sw)

            # URL complète du match pour scraper les lineups
            match_url = "https://fr.soccerway.com" + href

            if not any(m["mid"] == mid for m in matches):
                matches.append({
                    "mid": mid,
                    "match_url": match_url,
                    "home": home_api,
                    "away": away_api,
                    "home_sw": home_sw,
                    "away_sw": away_sw,
                    "date": today_str
                })
                print("  ✅ Match:", home_sw, "vs", away_sw)
                print("     URL:", match_url)

    except Exception as e:
        print("Erreur:", e)
        import traceback
        traceback.print_exc()

    return matches

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

def scrape_lineups(match_url):
    """Scrape depuis l'URL du match + /lineups/"""
    lineup_urls = [
        match_url.rstrip("/") + "/lineups/",
        match_url.rstrip("/") + "/",
    ]

    for url in lineup_urls:
        try:
            print("  Lineups URL:", url)
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            if not soup.find(string=re.compile(r"STARTING LINEUP|TITULAIRES|Starting XI|XI de départ", re.I)):
                print("  Pas encore de lineups")
                continue

            home_starters, away_starters = [], []
            home_subs, away_subs = [], []

            for table in soup.find_all("table"):
                prev = table.find_previous(string=re.compile(
                    r"STARTING LINEUP|SUBSTITUTES|TITULAIRES|REMPLAÇANTS|Starting XI|Substitutes", re.I))
                is_sub_table = prev and any(x in prev.upper() for x in ["SUBSTITUTE", "REMPLAÇ"]) if prev else False

                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue
                    lt = cells[0].get_text(strip=True)
                    rt = cells[-1].get_text(strip=True)
                    hp = parse_player(lt, "home")
                    ap = parse_player(rt, "away")
                    if is_sub_table:
                        if hp: home_subs.append(hp)
                        if ap: away_subs.append(ap)
                    else:
                        if hp: home_starters.append(hp)
                        if ap: away_starters.append(ap)

            if home_starters or away_starters:
                print("  Titulaires:", len(home_starters), "dom,", len(away_starters), "ext")
                return {
                    "home_players": home_starters[:11],
                    "away_players": away_starters[:11],
                    "home_subs": home_subs[:9],
                    "away_subs": away_subs[:9]
                }
        except Exception as e:
            print("  Erreur lineups:", e)
            continue
    return None

def get_fixture_id(home_api, away_api, match_date):
    try:
        check = requests.get(
            SB_URL + "/rest/v1/algeria_lineups?home_team=eq." + requests.utils.quote(home_api) +
            "&away_team=eq." + requests.utils.quote(away_api) +
            "&match_date=eq." + match_date + "&select=fixture_id",
            headers=SB_HEADERS
        ).json()
        if check and len(check) > 0 and check[0].get("fixture_id") and check[0]["fixture_id"] != 0:
            return check[0]["fixture_id"]
    except:
        pass
    return 0

# ══════════════════════════════════════
print("=== Algeria Lineups", datetime.now().strftime("%H:%M:%S"), "===")
matches = get_today_fixtures()
print("Matchs aujourd'hui:", len(matches))

if not matches:
    print("Aucun match aujourd'hui - OK")
    exit(0)

for match in matches:
    mid = match["mid"]
    home = match["home"]
    away = match["away"]
    match_date = match["date"]
    match_url = match.get("match_url", "")
    print("\n---", home, "vs", away, "---")

    try:
        check = requests.get(
            SB_URL + "/rest/v1/algeria_lineups?soccerway_mid=eq." + requests.utils.quote(mid) + "&select=id,home_players",
            headers=SB_HEADERS
        ).json()
        if check and len(check) > 0 and check[0].get("home_players") and len(check[0]["home_players"]) > 0:
            print("Deja scraped")
            continue
    except:
        pass

    lineups = scrape_lineups(match_url) if match_url else None
    if lineups:
        fixture_id = get_fixture_id(home, away, match_date)
        res = requests.post(SB_URL + "/rest/v1/algeria_lineups", headers=SB_HEADERS, json={
            "fixture_id": fixture_id,
            "soccerway_mid": mid,
            "home_team": home,
            "away_team": away,
            "match_date": match_date,
            "home_players": lineups["home_players"],
            "away_players": lineups["away_players"],
            "home_subs": lineups.get("home_subs", []),
            "away_subs": lineups.get("away_subs", []),
            "scraped_at": datetime.now(timezone.utc).isoformat()
        })
        print("Sauvegarde:", res.status_code, "-", home, "vs", away)
    else:
        print("Pas encore disponible")

print("=== Termine ===")