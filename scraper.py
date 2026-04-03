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
    "Rouisset":         "MB Rouissat",
    "Rouissat":         "MB Rouissat",
    "Paradou":          "Paradou AC",
    "Mostaganem":       "ES Mostaganem",
    "El Bayadh":        "MC El Bayadh",
    "Olympique Akbou":  "Olympique Akbou",
    "Akbou":            "Olympique Akbou",
}

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
    
    # URLs à essayer dans l'ordre — la page du jour est plus fiable que /fixtures/
    urls_to_try = [
        # URL avec date du jour explicite
        f"https://ca.soccerway.com/matches/{today.year}/{today.month:02d}/{today.day:02d}/algeria/ligue-professionnelle-1/",
        f"https://ca.soccerway.com/matches/{today.year}/{today.month:02d}/{today.day:02d}/algeria/ligue-1/",
        # Page fixtures classique
        "https://ca.soccerway.com/algeria/ligue-1/fixtures/",
        # Page résultats du jour
        "https://ca.soccerway.com/algeria/ligue-1/results/",
    ]
    
    matches = []
    
    for url in urls_to_try:
        print(f"Essai URL: {url}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            print(f"  Status: {r.status_code} — taille: {len(r.text)}")
            
            if r.status_code != 200:
                continue
                
            soup = BeautifulSoup(r.text, "html.parser")
            
            # Debug: afficher les matchs trouvés avec leurs dates
            rows_found = soup.find_all("tr", class_=re.compile(r"match"))
            print(f"  Lignes 'match' trouvées: {len(rows_found)}")
            
            for row in rows_found:
                try:
                    # Chercher le mid
                    mid = None
                    for link in row.find_all("a", href=True):
                        href = link.get("href", "")
                        s = re.search(r"mid=([A-Za-z0-9]+)", href)
                        if not s:
                            # Format alternatif /game/xxx/
                            s = re.search(r"/game/[^/]+/[^/]+/([A-Za-z0-9]+)/", href)
                        if s:
                            mid = s.group(1)
                            break
                    
                    if not mid:
                        continue
                    
                    # Équipes
                    team_links = row.find_all("a", href=re.compile(r"/teams/"))
                    if len(team_links) < 2:
                        continue
                    home_sw = team_links[0].get_text(strip=True)
                    away_sw = team_links[1].get_text(strip=True)
                    
                    # Date du match
                    match_date = today_str  # Par défaut aujourd'hui
                    dc = row.find("td", class_=re.compile(r"date"))
                    if dc:
                        dt = dc.get_text(strip=True)
                        for fmt in ["%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"]:
                            try:
                                match_date = datetime.strptime(dt, fmt).strftime("%Y-%m-%d")
                                break
                            except:
                                pass
                    
                    print(f"  Trouvé: {home_sw} vs {away_sw} — date={match_date} mid={mid}")
                    
                    if match_date == today_str and mid and home_sw:
                        home_api = normalize_team_name(home_sw)
                        away_api = normalize_team_name(away_sw)
                        matches.append({
                            "mid": mid,
                            "home": home_api,
                            "away": away_api,
                            "home_sw": home_sw,
                            "away_sw": away_sw,
                            "date": match_date
                        })
                        print(f"  ✅ Match ajouté: {home_api} vs {away_api}")
                except Exception as e:
                    print(f"  Erreur ligne: {e}")
                    continue
            
            if matches:
                print(f"  {len(matches)} matchs trouvés sur cette URL — stop")
                break
                
        except Exception as e:
            print(f"  Erreur: {e}")
            continue
    
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
            print("Pas encore de lineups pour mid=" + mid)
            return None
        home_starters, away_starters = [], []
        home_subs, away_subs = [], []
        for table in soup.find_all("table"):
            prev = table.find_previous(string=re.compile(r"STARTING LINEUP|SUBSTITUTES", re.I))
            is_sub_table = prev and "SUBSTITUTE" in prev.upper() if prev else False
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
            print("Titulaires:", len(home_starters), "dom,", len(away_starters), "ext")
            print("Remplaçants:", len(home_subs), "dom,", len(away_subs), "ext")
            return {
                "home_players": home_starters[:11],
                "away_players": away_starters[:11],
                "home_subs": home_subs[:9],
                "away_subs": away_subs[:9]
            }
        return None
    except Exception as e:
        print("Erreur lineups:", e)
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
    print("\n---", home, "vs", away, "---")
    try:
        check = requests.get(
            SB_URL + "/rest/v1/algeria_lineups?soccerway_mid=eq." + mid + "&select=id,home_players",
            headers=SB_HEADERS
        ).json()
        if check and len(check) > 0 and check[0].get("home_players") and len(check[0]["home_players"]) > 0:
            print("Deja scraped")
            continue
    except:
        pass
    lineups = scrape_lineups(mid)
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