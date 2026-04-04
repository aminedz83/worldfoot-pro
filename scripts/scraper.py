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

def normalize_team_name(sw_name):
    if sw_name in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[sw_name]
    for sw_key, api_name in TEAM_NAME_MAP.items():
        if sw_key.lower() in sw_name.lower() or sw_name.lower() in sw_key.lower():
            return api_name
    return sw_name

def get_today_fixtures():
    """
    Cherche les matchs du jour sur Soccerway Ligue 1 Algérie.
    Essaie plusieurs URLs pour trouver les bons mid.
    """
    today_str = date.today().strftime("%Y-%m-%d")
    matches = []

    # URL principale fixtures Ligue 1 Algérie
    urls_to_try = [
        "https://fr.soccerway.com/national/algeria/ligue-professionnelle-1/2025-2026/regular-season/r76191/matches/",
        "https://fr.soccerway.com/algeria/ligue-1/fixtures/",
        "https://ca.soccerway.com/national/algeria/ligue-professionnelle-1/2025-2026/regular-season/r76191/matches/",
    ]

    for url in urls_to_try:
        try:
            print(f"Essai URL: {url}")
            r = requests.get(url, headers=HEADERS, timeout=20)
            print(f"Status: {r.status_code}")
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            # Chercher tous les liens de match
            # Soccerway: /matches/2026/04/05/algeria/ligue-1/xxx/xxx/1234567/
            for link in soup.find_all("a", href=re.compile(r"/matches/\d{4}/\d{2}/\d{2}/")):
                href = link.get("href", "")

                # Extraire le mid numérique à la fin de l'URL
                mid_match = re.search(r"/(\d{5,8})/?$", href)
                if not mid_match:
                    continue
                mid = mid_match.group(1)

                # Extraire la date du lien
                date_match = re.search(r"/matches/(\d{4})/(\d{2})/(\d{2})/", href)
                if not date_match:
                    continue
                match_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

                # Seulement les matchs d'aujourd'hui
                if match_date != today_str:
                    continue

                # Trouver les noms des équipes dans la ligne du tableau
                row = link.find_parent("tr")
                if not row:
                    continue

                team_links = row.find_all("a", href=re.compile(r"/teams/"))
                if len(team_links) < 2:
                    continue

                home_sw = team_links[0].get_text(strip=True)
                away_sw = team_links[1].get_text(strip=True)

                if not home_sw or not away_sw:
                    continue

                home_api = normalize_team_name(home_sw)
                away_api = normalize_team_name(away_sw)

                # Éviter les doublons
                if any(m["mid"] == mid for m in matches):
                    continue

                matches.append({
                    "mid": mid,
                    "home": home_api,
                    "away": away_api,
                    "home_sw": home_sw,
                    "away_sw": away_sw,
                    "date": match_date
                })
                print(f"  ✅ Match trouvé: {home_sw} vs {away_sw} | mid={mid}")

            if matches:
                print(f"Total: {len(matches)} matchs trouvés")
                return matches

        except Exception as e:
            print(f"Erreur URL {url}: {e}")
            continue

    # Fallback: ancienne méthode avec mid= dans les paramètres
    if not matches:
        print("Fallback: ancienne méthode...")
        try:
            r = requests.get("https://fr.soccerway.com/algeria/ligue-1/fixtures/", headers=HEADERS, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            for row in soup.find_all("tr", class_=re.compile(r"match")):
                try:
                    mid = None
                    for link in row.find_all("a", href=True):
                        href = link.get("href", "")
                        # Chercher mid= dans l'URL
                        s = re.search(r"mid=([A-Za-z0-9]+)", href)
                        if s:
                            mid = s.group(1)
                            break
                        # Ou mid numérique à la fin
                        s2 = re.search(r"/(\d{5,8})/?$", href)
                        if s2:
                            mid = s2.group(1)
                            break
                    if not mid:
                        continue

                    team_links = row.find_all("a", href=re.compile(r"/teams/"))
                    if len(team_links) < 2:
                        continue
                    home_sw = team_links[0].get_text(strip=True)
                    away_sw = team_links[1].get_text(strip=True)

                    match_date = today_str
                    dc = row.find("td", class_=re.compile(r"date"))
                    if dc:
                        try:
                            match_date = datetime.strptime(dc.get_text(strip=True), "%d/%m/%Y").strftime("%Y-%m-%d")
                        except:
                            pass

                    if match_date == today_str and mid and home_sw:
                        home_api = normalize_team_name(home_sw)
                        away_api = normalize_team_name(away_sw)
                        if not any(m["mid"] == mid for m in matches):
                            matches.append({
                                "mid": mid,
                                "home": home_api,
                                "away": away_api,
                                "home_sw": home_sw,
                                "away_sw": away_sw,
                                "date": match_date
                            })
                            print(f"  ✅ Fallback match: {home_sw} vs {away_sw} | mid={mid}")
                except:
                    continue
        except Exception as e:
            print(f"Erreur fallback: {e}")

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
    url = "https://fr.soccerway.com/matches/" + mid + "/?ICID=PL_3N_06"
    # Essayer aussi avec l'URL directe
    urls = [
        f"https://fr.soccerway.com/game/x/x/summary/lineups/?mid={mid}",
        f"https://ca.soccerway.com/game/x/x/summary/lineups/?mid={mid}",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            if not soup.find(string=re.compile(r"STARTING LINEUP|TITULAIRES", re.I)):
                print(f"  Pas encore de lineups pour mid={mid}")
                continue

            home_starters, away_starters = [], []
            home_subs, away_subs = [], []

            for table in soup.find_all("table"):
                prev = table.find_previous(string=re.compile(r"STARTING LINEUP|SUBSTITUTES|TITULAIRES|REMPLAÇANTS", re.I))
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
                print(f"  Titulaires: {len(home_starters)} dom, {len(away_starters)} ext")
                print(f"  Remplaçants: {len(home_subs)} dom, {len(away_subs)} ext")
                return {
                    "home_players": home_starters[:11],
                    "away_players": away_starters[:11],
                    "home_subs": home_subs[:9],
                    "away_subs": away_subs[:9]
                }
        except Exception as e:
            print(f"  Erreur lineups: {e}")
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
    print(f"\n--- {home} vs {away} ---")
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
        print(f"Sauvegarde: {res.status_code} - {home} vs {away}")
    else:
        print("Pas encore disponible")

print("=== Termine ===")