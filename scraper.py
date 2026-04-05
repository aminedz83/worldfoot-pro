import os, re, time
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone, date

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# ← Même technique que sync_market_values_sw.py
scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

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

ALGERIA_SW_IDS = [
    "Wfaskwf0", "vNJLB2jP", "tnY2Lfcp", "zXBidj5t",
    "nBionu2l", "EDgC6qYp", "CrCmB35M", "Aobolc96",
    "nimcBvel", "QmvZvxCB", "lYuJtBj9", "hGHHy7Am",
    "WIyffF3J", "j9T7TM2E", "S6H5xCS1", "dhMQsMOh",
]

def normalize_team_name(sw_name):
    if sw_name in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[sw_name]
    for sw_key, api_name in TEAM_NAME_MAP.items():
        if sw_key.lower() in sw_name.lower() or sw_name.lower() in sw_key.lower():
            return api_name
    return sw_name

def get_today_fixtures():
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    matches = []

    # URL matchs du jour Soccerway avec cloudscraper
    url = "https://fr.soccerway.com/matches/{}/{}/{}/".format(
        today.strftime("%Y"),
        today.strftime("%m"),
        today.strftime("%d")
    )
    print("URL:", url)

    try:
        r = scraper.get(url, timeout=20)
        print("Status:", r.status_code, "| Taille:", len(r.text))

        soup = BeautifulSoup(r.text, "html.parser")

        # Chercher liens /match/ avec IDs algériens
        for a in soup.find_all("a", href=re.compile(r"^/match/")):
            href = a.get("href", "")
            parts = href.strip("/").split("/")
            if len(parts) < 3:
                continue

            home_slug = parts[1]
            away_slug = parts[2]

            # Vérifier si club algérien
            home_is_algeria = any(sw_id in home_slug for sw_id in ALGERIA_SW_IDS)
            away_is_algeria = any(sw_id in away_slug for sw_id in ALGERIA_SW_IDS)

            if not home_is_algeria and not away_is_algeria:
                continue

            mid = home_slug + "_" + away_slug
            home_sw = re.sub(r'-[A-Za-z0-9]{6,10}$', '', home_slug).replace("-", " ").title()
            away_sw = re.sub(r'-[A-Za-z0-9]{6,10}$', '', away_slug).replace("-", " ").title()
            home_api = normalize_team_name(home_sw)
            away_api = normalize_team_name(away_sw)
            match_url = "https://fr.soccerway.com" + href

            if not any(m["mid"] == mid for m in matches):
                matches.append({
                    "mid": mid,
                    "match_url": match_url,
                    "home": home_api,
                    "away": away_api,
                    "date": today_str
                })
                print("  ✅", home_sw, "vs", away_sw)

    except Exception as e:
        print("Erreur URL date:", e)

    # Fallback: page Ligue 1 Algérie directe
    if not matches:
        print("Fallback: page Ligue 1 Algérie...")
        fallback_url = "https://fr.soccerway.com/national/algeria/ligue-professionnelle-1/2025-2026/regular-season/r76191/"
        try:
            r = scraper.get(fallback_url, timeout=20)
            print("Fallback status:", r.status_code)
            soup = BeautifulSoup(r.text, "html.parser")

            for row in soup.find_all("tr", class_=re.compile(r"match")):
                # Vérifier date
                date_cell = row.find("td", class_=re.compile(r"date"))
                if date_cell:
                    try:
                        match_date = datetime.strptime(date_cell.get_text(strip=True), "%d/%m/%Y").strftime("%Y-%m-%d")
                        if match_date != today_str:
                            continue
                    except:
                        pass

                mid = None
                for link in row.find_all("a", href=True):
                    href = link.get("href", "")
                    s = re.search(r"/(\d{5,8})/?$", href)
                    if s:
                        mid = s.group(1)
                        break
                if not mid:
                    continue

                team_links = row.find_all("a", href=re.compile(r"/teams/"))
                if len(team_links) < 2:
                    continue

                home_sw = team_links[0].get_text(strip=True)
                away_sw = team_links[1].get_text(strip=True)
                home_api = normalize_team_name(home_sw)
                away_api = normalize_team_name(away_sw)

                if not any(m["mid"] == mid for m in matches):
                    matches.append({
                        "mid": mid,
                        "match_url": "https://fr.soccerway.com/game/x/x/summary/lineups/?mid=" + mid,
                        "home": home_api,
                        "away": away_api,
                        "date": today_str
                    })
                    print("  ✅ Fallback:", home_sw, "vs", away_sw)

        except Exception as e:
            print("Erreur fallback:", e)

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

def scrape_lineups(match_url, mid):
    urls = [
        match_url.rstrip("/") + "/lineups/",
        match_url,
        "https://fr.soccerway.com/game/x/x/summary/lineups/?mid=" + str(mid),
    ]
    for url in urls:
        try:
            time.sleep(1)
            r = scraper.get(url, timeout=20)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            if not soup.find(string=re.compile(r"STARTING LINEUP|TITULAIRES|Starting XI", re.I)):
                print("  Pas encore de lineups")
                continue

            home_starters, away_starters = [], []
            home_subs, away_subs = [], []

            for table in soup.find_all("table"):
                prev = table.find_previous(string=re.compile(
                    r"STARTING LINEUP|SUBSTITUTES|TITULAIRES|REMPLAÇANTS", re.I))
                is_sub = prev and any(x in prev.upper() for x in ["SUBSTITUTE", "REMPLAÇ"]) if prev else False

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
                print("  Titulaires:", len(home_starters), "dom,", len(away_starters), "ext")
                return {
                    "home_players": home_starters[:11],
                    "away_players": away_starters[:11],
                    "home_subs": home_subs[:9],
                    "away_subs": away_subs[:9]
                }
        except Exception as e:
            print("  Erreur lineups:", e)
    return None

def get_fixture_id(home_api, away_api, match_date):
    try:
        import requests as req
        check = req.get(
            SB_URL + "/rest/v1/algeria_lineups?home_team=eq." + req.utils.quote(home_api) +
            "&away_team=eq." + req.utils.quote(away_api) +
            "&match_date=eq." + match_date + "&select=fixture_id",
            headers=SB_HEADERS
        ).json()
        if check and check[0].get("fixture_id"):
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
        import requests as req
        check = req.get(
            SB_URL + "/rest/v1/algeria_lineups?soccerway_mid=eq." + req.utils.quote(str(mid)) + "&select=id,home_players",
            headers=SB_HEADERS
        ).json()
        if check and len(check) > 0 and check[0].get("home_players") and len(check[0]["home_players"]) > 0:
            print("Deja scraped")
            continue
    except:
        pass

    lineups = scrape_lineups(match_url, mid)
    if lineups:
        import requests as req
        fixture_id = get_fixture_id(home, away, match_date)
        res = req.post(SB_URL + "/rest/v1/algeria_lineups", headers=SB_HEADERS, json={
            "fixture_id": fixture_id,
            "soccerway_mid": str(mid),
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