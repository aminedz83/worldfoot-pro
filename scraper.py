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
    Utilise l'URL Soccerway avec la date du jour pour trouver les matchs.
    URL format: https://fr.soccerway.com/matches/2026/04/05/
    """
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    matches = []

    # URL principale avec la date du jour
    url = "https://fr.soccerway.com/matches/{}/{}/{}/".format(
        today.strftime("%Y"),
        today.strftime("%m"),
        today.strftime("%d")
    )
    print("URL matchs du jour:", url)

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print("Status:", r.status_code)
        if r.status_code != 200:
            return []

        soup = BeautifulSoup(r.text, "html.parser")

        # Chercher la section Algérie / Ligue 1
        # Soccerway groupe les matchs par compétition
        current_competition = ""
        is_algeria_ligue1 = False

        for tag in soup.find_all(["h2", "h3", "th", "tr"]):
            # Détecter la compétition
            if tag.name in ["h2", "h3"]:
                text = tag.get_text(strip=True)
                current_competition = text
                is_algeria_ligue1 = ("algeri" in text.lower() and "ligue" in text.lower()) or \
                                     "ligue professionnelle" in text.lower()
                if is_algeria_ligue1:
                    print("Compétition trouvée:", text)
                continue

            # Chercher les lignes de match dans la section Algérie
            if tag.name == "tr" and is_algeria_ligue1:
                # Chercher le lien du match
                match_link = tag.find("a", href=re.compile(r"/matches/\d{4}/\d{2}/\d{2}/"))
                if not match_link:
                    continue

                href = match_link.get("href", "")
                # Extraire mid numérique
                mid_m = re.search(r"/(\d{5,8})/?$", href)
                if not mid_m:
                    continue
                mid = mid_m.group(1)

                # Extraire les équipes
                team_links = tag.find_all("a", href=re.compile(r"/teams/"))
                if len(team_links) < 2:
                    continue

                home_sw = team_links[0].get_text(strip=True)
                away_sw = team_links[1].get_text(strip=True)

                if not home_sw or not away_sw:
                    continue

                home_api = normalize_team_name(home_sw)
                away_api = normalize_team_name(away_sw)

                if not any(m["mid"] == mid for m in matches):
                    matches.append({
                        "mid": mid,
                        "home": home_api,
                        "away": away_api,
                        "home_sw": home_sw,
                        "away_sw": away_sw,
                        "date": today_str
                    })
                    print("  ✅ Match:", home_sw, "vs", away_sw, "| mid=", mid)

        if matches:
            return matches

    except Exception as e:
        print("Erreur URL date:", e)

    # Fallback: URL de la Ligue 1 Algérie directement
    print("Fallback: URL Ligue 1 Algérie...")
    fallback_urls = [
        "https://fr.soccerway.com/national/algeria/ligue-professionnelle-1/2025-2026/regular-season/r76191/",
        "https://int.soccerway.com/national/algeria/ligue-professionnelle-1/2025-2026/regular-season/r76191/",
    ]

    for url in fallback_urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            print("Fallback status:", r.status_code, url)
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            # Chercher matchs d'aujourd'hui
            for row in soup.find_all("tr", class_=re.compile(r"match")):
                # Vérifier la date
                date_cell = row.find("td", class_=re.compile(r"date"))
                if date_cell:
                    date_text = date_cell.get_text(strip=True)
                    try:
                        match_date = datetime.strptime(date_text, "%d/%m/%Y").strftime("%Y-%m-%d")
                        if match_date != today_str:
                            continue
                    except:
                        pass

                # Chercher mid
                mid = None
                for link in row.find_all("a", href=True):
                    href = link.get("href", "")
                    s = re.search(r"/(\d{5,8})/?$", href)
                    if s:
                        mid = s.group(1)
                        break
                    s2 = re.search(r"mid=([A-Za-z0-9]+)", href)
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
                home_api = normalize_team_name(home_sw)
                away_api = normalize_team_name(away_sw)

                if not any(m["mid"] == mid for m in matches):
                    matches.append({
                        "mid": mid,
                        "home": home_api,
                        "away": away_api,
                        "home_sw": home_sw,
                        "away_sw": away_sw,
                        "date": today_str
                    })
                    print("  ✅ Fallback match:", home_sw, "vs", away_sw, "| mid=", mid)

            if matches:
                break

        except Exception as e:
            print("Erreur fallback:", e)
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
    urls = [
        "https://fr.soccerway.com/matches/{}/lineups/".format(mid),
        "https://fr.soccerway.com/game/x/x/summary/lineups/?mid={}".format(mid),
        "https://ca.soccerway.com/game/x/x/summary/lineups/?mid={}".format(mid),
        "https://int.soccerway.com/matches/{}/lineups/".format(mid),
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                print("  Status", r.status_code, "pour", url)
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            if not soup.find(string=re.compile(r"STARTING LINEUP|TITULAIRES|Starting XI", re.I)):
                print("  Pas encore de lineups pour mid=" + mid)
                continue

            home_starters, away_starters = [], []
            home_subs, away_subs = [], []

            for table in soup.find_all("table"):
                prev = table.find_previous(string=re.compile(
                    r"STARTING LINEUP|SUBSTITUTES|TITULAIRES|REMPLAÇANTS|Starting XI|Substitutes", re.I))
                is_sub_table = prev and any(x in prev.upper() for x in ["SUBSTITUTE", "REMPLAÇ", "SUBSTITUTES"]) if prev else False

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
                print("  Remplaçants:", len(home_subs), "dom,", len(away_subs), "ext")
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