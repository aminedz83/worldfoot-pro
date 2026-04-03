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
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

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

def get_today_fixtures():
    today_str = date.today().strftime("%Y-%m-%d")
    matches = []

    # 1. Essai SofaScore scheduled events
    sf_url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today_str}"
    try:
        r = requests.get(sf_url, headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
            "Accept": "application/json",
            "Referer": "https://www.sofascore.com/"
        }, timeout=15)
        print(f"SofaScore status: {r.status_code}")
        if r.status_code == 200:
            events = r.json().get("events", [])
            alg = [e for e in events if e.get("tournament", {}).get("id") == 841]
            print(f"Matchs Ligue 1 Algérie: {len(alg)}")
            for e in alg:
                home = normalize_team_name(e["homeTeam"]["name"])
                away = normalize_team_name(e["awayTeam"]["name"])
                print(f"  {home} vs {away}")
                matches.append({"home": home, "away": away, "date": today_str, "fixture_id": 0})
    except Exception as e:
        print(f"SofaScore erreur: {e}")

    # 2. Fallback : construire depuis les matchs connus du jour
    # On scrape la page résumé Soccerway de la Ligue 1 — qui retourne 200
    if not matches:
        print("Fallback: scrape page résumé Soccerway...")
        try:
            r = requests.get("https://ca.soccerway.com/algeria/ligue-1/", headers=HEADERS, timeout=15)
            print(f"Soccerway résumé: {r.status_code} — {len(r.text)} chars")
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                # Chercher matchs avec date aujourd'hui
                for row in soup.find_all("tr", class_=re.compile(r"match")):
                    dc = row.find("td", class_=re.compile(r"date"))
                    if not dc:
                        continue
                    match_date = None
                    for fmt in ["%d/%m/%Y", "%d/%m/%y"]:
                        try:
                            match_date = datetime.strptime(dc.get_text(strip=True), fmt).strftime("%Y-%m-%d")
                            break
                        except:
                            pass
                    if match_date != today_str:
                        continue
                    mid_link = row.find("a", href=re.compile(r"mid="))
                    if not mid_link:
                        continue
                    mid = re.search(r"mid=([A-Za-z0-9]+)", mid_link["href"]).group(1)
                    tlinks = row.find_all("a", href=re.compile(r"/teams/"))
                    if len(tlinks) >= 2:
                        home = normalize_team_name(tlinks[0].get_text(strip=True))
                        away = normalize_team_name(tlinks[1].get_text(strip=True))
                        print(f"  ✅ {home} vs {away} mid={mid}")
                        matches.append({"home": home, "away": away, "date": today_str, "fixture_id": 0, "mid": mid})
        except Exception as e:
            print(f"Erreur fallback: {e}")

    return matches

def get_mid_from_soccerway(home_name, away_name):
    home_info = SW_CLUBS.get(home_name)
    away_info = SW_CLUBS.get(away_name)
    if not home_info or not away_info:
        print(f"  IDs manquants: {home_name}={home_name in SW_CLUBS} {away_name}={away_name in SW_CLUBS}")
        return None
    url = f"https://fr.soccerway.com/match/{away_info['slug']}-{away_info['sw_id']}/{home_info['slug']}-{home_info['sw_id']}/"
    print(f"  SW URL: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        print(f"  SW status: {r.status_code} url_finale: {r.url[-60:]}")
        if r.status_code != 200:
            return None
        for pattern in [r"mid=([A-Za-z0-9]+)", r'"mid":"([A-Za-z0-9]+)"', r"data-mid=\"([A-Za-z0-9]+)\""]:
            m = re.search(pattern, r.url + r.text)
            if m:
                return m.group(1)
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
    for base in ["https://fr.soccerway.com", "https://ca.soccerway.com"]:
        url = f"{base}/game/x/x/summary/lineups/?mid={mid}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            print(f"  Lineups {base[-10:]}: {r.status_code}")
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            if not soup.find(string=re.compile(r"STARTING LINEUP", re.I)):
                print(f"  Pas encore de lineups pour mid={mid}")
                continue
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
                print(f"  ✅ Titulaires: {len(home_starters)} dom, {len(away_starters)} ext")
                return {
                    "home_players": home_starters[:11], "away_players": away_starters[:11],
                    "home_subs": home_subs[:9], "away_subs": away_subs[:9]
                }
        except Exception as e:
            print(f"  Erreur: {e}")
    return None

print("=== Algeria Lineups", datetime.now().strftime("%H:%M:%S"), "===")
today_str = date.today().strftime("%Y-%m-%d")

matches = get_today_fixtures()
print(f"Matchs trouvés: {len(matches)}")

if not matches:
    print("Aucun match aujourd'hui - OK")
    exit(0)

for match in matches:
    home, away = match["home"], match["away"]
    print(f"\n--- {home} vs {away} ---")

    # mid déjà connu (depuis fallback Soccerway) ou à chercher
    mid = match.get("mid")

    # Vérifier si déjà scraped
    try:
        check = requests.get(
            SB_URL + "/rest/v1/algeria_lineups?home_team=eq." + requests.utils.quote(home) +
            "&away_team=eq." + requests.utils.quote(away) +
            "&match_date=eq." + today_str + "&select=id,home_players",
            headers=SB_HEADERS
        ).json()
        if check and check[0].get("home_players") and len(check[0]["home_players"]) > 0:
            print("  Déjà scraped")
            continue
    except:
        pass

    if not mid:
        mid = get_mid_from_soccerway(home, away)

    if not mid:
        print(f"  Mid introuvable — skip")
        continue

    print(f"  Mid: {mid}")
    lineups = scrape_lineups(mid)
    if lineups:
        res = requests.post(SB_URL + "/rest/v1/algeria_lineups", headers=SB_HEADERS, json={
            "fixture_id": match.get("fixture_id", 0),
            "soccerway_mid": mid,
            "home_team": home, "away_team": away,
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