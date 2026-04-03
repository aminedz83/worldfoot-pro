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

# Slugs réels Soccerway — depuis les URLs connues
# JSK: /equipe/kabylie/Wfaskwf0/
# MB Rouissat: visible dans URL match comme "rouisset-hGHHy7Am"
# Akbou: visible dans URL match comme "olympique-akbou-dhMQsMOh"
SW_CLUBS = {
    "JS Kabylie":       {"sw_id": "Wfaskwf0",  "slug": "kabylie"},
    "CR Belouizdad":    {"sw_id": "vNJLB2jP",  "slug": "belouizdad"},
    "MC Alger":         {"sw_id": "tnY2Lfcp",  "slug": "mc-alger"},
    "USM Alger":        {"sw_id": "zXBidj5t",  "slug": "usm-alger"},
    "CS Constantine":   {"sw_id": "nBionu2l",  "slug": "cs-constantine"},
    "ES Setif":         {"sw_id": "EDgC6qYp",  "slug": "es-setif"},
    "MC Oran":          {"sw_id": "CrCmB35M",  "slug": "mc-oran"},
    "ASO Chlef":        {"sw_id": "Aobolc96",  "slug": "aso-chlef"},
    "JS Saoura":        {"sw_id": "nimcBvel",  "slug": "js-saoura"},
    "ES Ben Aknoun":    {"sw_id": "QmvZvxCB",  "slug": "es-ben-aknoun"},
    "USM Khenchela":    {"sw_id": "lYuJtBj9",  "slug": "usm-khenchela"},
    "MB Rouissat":      {"sw_id": "hGHHy7Am",  "slug": "rouisset"},
    "Paradou AC":       {"sw_id": "WIyffF3J",  "slug": "paradou-ac"},
    "ES Mostaganem":    {"sw_id": "j9T7TM2E",  "slug": "es-mostaganem"},
    "MC El Bayadh":     {"sw_id": "S6H5xCS1",  "slug": "mc-el-bayadh"},
    "Olympique Akbou":  {"sw_id": "dhMQsMOh",  "slug": "olympique-akbou"},
}
SW_ID_TO_NAME = {v["sw_id"]: k for k, v in SW_CLUBS.items()}

TEAM_NAME_MAP = {
    "Kabylie": "JS Kabylie", "Belouizdad": "CR Belouizdad",
    "MC Alger": "MC Alger", "USM Alger": "USM Alger",
    "Constantine": "CS Constantine", "Setif": "ES Setif",
    "Oran": "MC Oran", "Chlef": "ASO Chlef", "Saoura": "JS Saoura",
    "Ben Aknoun": "ES Ben Aknoun", "Khenchela": "USM Khenchela",
    "Rouisset": "MB Rouissat", "Rouissat": "MB Rouissat",
    "Paradou": "Paradou AC", "Mostaganem": "ES Mostaganem",
    "El Bayadh": "MC El Bayadh", "Akbou": "Olympique Akbou",
    "Olympique Akbou": "Olympique Akbou",
}

def normalize_team_name(sw_name):
    if sw_name in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[sw_name]
    for key, val in TEAM_NAME_MAP.items():
        if key.lower() in sw_name.lower():
            return val
    return sw_name

def get_today_fixtures():
    today_str = date.today().strftime("%Y-%m-%d")
    matches = []
    seen_mids = set()

    print(f"Recherche matchs pour: {today_str}")

    # D'abord tester quelle URL fonctionne avec JSK
    test_urls = [
        f"https://ca.soccerway.com/equipe/kabylie/Wfaskwf0/matches/",
        f"https://fr.soccerway.com/equipe/kabylie/Wfaskwf0/matches/",
        f"https://int.soccerway.com/equipe/kabylie/Wfaskwf0/matches/",
        f"https://ca.soccerway.com/teams/algeria/js-kabylie/Wfaskwf0/matches/",
        f"https://ca.soccerway.com/national/algeria/ligue-professionnelle-1/2025-2026/regular-season/matches/",
        f"https://ca.soccerway.com/algeria/ligue-1/fixtures/",
    ]
    working_base = None
    working_pattern = None
    for test_url in test_urls:
        try:
            r = requests.get(test_url, headers=HEADERS, timeout=10)
            print(f"  TEST {test_url[:60]}: {r.status_code}")
            if r.status_code == 200:
                working_base = test_url
                # Afficher 500 chars du HTML pour debug
                print(f"  HTML sample: {r.text[500:900]}")
                break
        except Exception as e:
            print(f"  TEST erreur: {e}")

    if not working_base:
        print("  Aucune URL ne fonctionne!")
        return []

    for team_name, info in SW_CLUBS.items():
        sw_id = info["sw_id"]
        slug = info["slug"]
        # Construire URL avec le même pattern que celui qui fonctionne
        if "equipe/kabylie" in working_base:
            url = working_base.replace("kabylie/Wfaskwf0", f"{slug}/{sw_id}")
        elif "js-kabylie/Wfaskwf0" in working_base:
            url = working_base.replace("js-kabylie/Wfaskwf0", f"js-{slug}/{sw_id}")
        elif "fixtures" in working_base or "matches" in working_base:
            # Page de ligue — on scrape une seule fois
            if team_name != "JS Kabylie":
                continue
            url = working_base
        else:
            url = working_base
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                print(f"  {team_name}: {r.status_code} — {url}")
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            for link in soup.find_all("a", href=re.compile(r"mid=")):
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
                for td in row.find_all("td"):
                    txt = td.get_text(strip=True)
                    for fmt in ["%d/%m/%Y", "%d/%m/%y"]:
                        try:
                            match_date = datetime.strptime(txt, fmt).strftime("%Y-%m-%d")
                            break
                        except:
                            pass
                    if match_date:
                        break

                if match_date != today_str:
                    continue

                # Équipes depuis IDs dans l'URL
                ids_in_url = re.findall(r"-([A-Za-z0-9]{8})[/\?]", href)
                home_api, away_api = None, None
                for cid in ids_in_url:
                    if cid in SW_ID_TO_NAME:
                        if home_api is None:
                            home_api = SW_ID_TO_NAME[cid]
                        else:
                            away_api = SW_ID_TO_NAME[cid]

                # Fallback noms texte
                if not home_api or not away_api:
                    tlinks = row.find_all("a", href=re.compile(r"/equipe/"))
                    if len(tlinks) >= 2:
                        home_api = normalize_team_name(tlinks[0].get_text(strip=True))
                        away_api = normalize_team_name(tlinks[1].get_text(strip=True))

                if not home_api: home_api = team_name
                if not away_api: away_api = "?"

                seen_mids.add(mid)
                print(f"  ✅ {home_api} vs {away_api} | mid={mid}")
                matches.append({
                    "mid": mid, "home": home_api, "away": away_api, "date": today_str
                })

        except Exception as e:
            print(f"  Erreur {team_name}: {e}")

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
    url = "https://fr.soccerway.com/game/x/x/summary/lineups/?mid=" + mid
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  Lineups status: {r.status_code}")
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        if not soup.find(string=re.compile(r"STARTING LINEUP", re.I)):
            print(f"  Pas encore de lineups mid={mid}")
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