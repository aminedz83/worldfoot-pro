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
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-FR,fr;q=0.9"
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

def get_today_fixtures():
    """
    Scrape la page /algeria/ligue-1/ sur ca.soccerway.com
    qui retourne 200 et contient les matchs du jour ET les résultats
    """
    today_str = date.today().strftime("%Y-%m-%d")
    matches = []

    # Cette URL retourne 200 depuis GitHub Actions
    urls = [
        "https://ca.soccerway.com/algeria/ligue-1/fixtures/",
        "https://ca.soccerway.com/algeria/ligue-1/results/",
        "https://ca.soccerway.com/national/algeria/ligue-professionnelle-1/2025-2026/regular-season/matches/",
    ]

    seen_mids = set()

    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            print(f"URL: {url[:60]} → {r.status_code}")
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            # Debug: combien de liens avec mid= ?
            mid_links = soup.find_all("a", href=re.compile(r"mid="))
            print(f"  Liens mid= trouvés: {len(mid_links)}")

            # Debug: afficher les 3 premiers liens mid=
            for lnk in mid_links[:3]:
                print(f"  ex: {lnk.get('href','')[:80]}")

            # Debug: toutes les dates trouvées dans les td
            date_tds = soup.find_all("td", class_=re.compile(r"date"))
            dates_found = set()
            for td in date_tds[:10]:
                dates_found.add(td.get_text(strip=True))
            print(f"  Dates dans page: {dates_found}")

            for link in mid_links:
                href = link.get("href", "")
                mid_m = re.search(r"mid=([A-Za-z0-9]+)", href)
                if not mid_m:
                    continue
                mid = mid_m.group(1)
                if mid in seen_mids:
                    continue

                row = link.find_parent("tr")
                if not row:
                    continue

                # Date
                match_date = None
                dc = row.find("td", class_=re.compile(r"date"))
                if dc:
                    for fmt in ["%d/%m/%Y", "%d/%m/%y"]:
                        try:
                            match_date = datetime.strptime(dc.get_text(strip=True), fmt).strftime("%Y-%m-%d")
                            break
                        except:
                            pass

                # Si pas de date dans la ligne → supposer aujourd'hui
                if not match_date:
                    match_date = today_str

                if match_date != today_str:
                    continue

                team_links = row.find_all("a", href=re.compile(r"/teams/"))
                if len(team_links) < 2:
                    continue
                home_sw = team_links[0].get_text(strip=True)
                away_sw = team_links[1].get_text(strip=True)
                home_api = normalize_team_name(home_sw)
                away_api = normalize_team_name(away_sw)

                seen_mids.add(mid)
                print(f"  ✅ {home_api} vs {away_api} | mid={mid}")
                matches.append({
                    "mid": mid, "home": home_api, "away": away_api, "date": match_date
                })

        except Exception as e:
            print(f"  Erreur: {e}")

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

def scrape_lineups(mid):
    url = "https://ca.soccerway.com/game/x/x/summary/lineups/?mid=" + mid
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  Lineups status: {r.status_code}")
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

def get_fixture_id(home_api, away_api, match_date):
    try:
        check = requests.get(
            SB_URL + "/rest/v1/algeria_lineups?home_team=eq." + requests.utils.quote(home_api) +
            "&away_team=eq." + requests.utils.quote(away_api) +
            "&match_date=eq." + match_date + "&select=fixture_id",
            headers=SB_HEADERS
        ).json()
        if check and check[0].get("fixture_id") and check[0]["fixture_id"] != 0:
            return check[0]["fixture_id"]
    except:
        pass
    return 0

print("=== Algeria Lineups", datetime.now().strftime("%H:%M:%S"), "===")
matches = get_today_fixtures()
print("Matchs aujourd'hui:", len(matches))
if not matches:
    print("Aucun match aujourd'hui - OK")
    exit(0)

for match in matches:
    mid, home, away, match_date = match["mid"], match["home"], match["away"], match["date"]
    print(f"\n--- {home} vs {away} ---")
    try:
        check = requests.get(
            SB_URL + "/rest/v1/algeria_lineups?soccerway_mid=eq." + mid + "&select=id,home_players",
            headers=SB_HEADERS
        ).json()
        if check and check[0].get("home_players") and len(check[0]["home_players"]) > 0:
            print("  Deja scraped")
            continue
    except:
        pass
    lineups = scrape_lineups(mid)
    if lineups:
        fixture_id = get_fixture_id(home, away, match_date)
        res = requests.post(SB_URL + "/rest/v1/algeria_lineups", headers=SB_HEADERS, json={
            "fixture_id": fixture_id, "soccerway_mid": mid,
            "home_team": home, "away_team": away, "match_date": match_date,
            "home_players": lineups["home_players"], "away_players": lineups["away_players"],
            "home_subs": lineups.get("home_subs", []), "away_subs": lineups.get("away_subs", []),
            "scraped_at": datetime.now(timezone.utc).isoformat()
        })
        print(f"  Sauvegarde: {res.status_code}")
    else:
        print("  Pas encore disponible")
print("=== Termine ===")