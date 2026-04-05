import os, re, time, requests
import cloudscraper
from datetime import datetime, timezone, date

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

FS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://fr.soccerway.com/",
    "x-fsign": "SW9D1eZo",
}

PROJECT = "2043"

# IDs Soccerway/Flashscore des clubs Ligue 1 Algérie
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
    "Ben-Aknoun":       "ES Ben Aknoun",
    "Ben Aknoun":       "ES Ben Aknoun",
    "Khenchela":        "USM Khenchela",
    "Rouissat":         "MB Rouissat",
    "Paradou":          "Paradou AC",
    "Mostaganem":       "ES Mostaganem",
    "El-Bayadh":        "MC El Bayadh",
    "El Bayadh":        "MC El Bayadh",
    "Akbou":            "Olympique Akbou",
}

def normalize_team_name(name):
    if name in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[name]
    for k, v in TEAM_NAME_MAP.items():
        if k.lower() in name.lower() or name.lower() in k.lower():
            return v
    return name

def parse_feed(text):
    """Parse le format Flashscore: KEY÷VALUE¬KEY÷VALUE~"""
    blocks = text.split("~")
    result = []
    for block in blocks:
        if not block.strip():
            continue
        fields = {}
        for field in block.split("¬"):
            if "÷" in field:
                key, _, val = field.partition("÷")
                fields[key.strip()] = val.strip()
        if fields:
            result.append(fields)
    return result

def get_today_matches():
    """
    Récupère les matchs Ligue 1 Algérie du jour depuis Flashscore.
    URL page du jour → chercher les IDs des clubs algériens.
    """
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    matches = []

    url = "https://fr.soccerway.com/matches/{}/{}/{}/".format(
        today.strftime("%Y"), today.strftime("%m"), today.strftime("%d")
    )
    print("URL:", url)

    try:
        r = scraper.get(url, timeout=20)
        print("Status:", r.status_code, "| Taille:", len(r.text))
        html = r.text

        # Chercher les liens /match/ avec IDs algériens
        for a_match in re.findall(r'/match/([^"\'<>\s/]+)/([^"\'<>\s/]+)/', html):
            home_slug, away_slug = a_match
            home_is_algeria = any(sw_id in home_slug for sw_id in ALGERIA_SW_IDS)
            away_is_algeria = any(sw_id in away_slug for sw_id in ALGERIA_SW_IDS)

            if not home_is_algeria and not away_is_algeria:
                continue

            # Extraire mid depuis le HTML (chercher autour du slug)
            mid_pattern = re.search(
                re.escape(home_slug) + r'.{0,200}?\?mid=([A-Za-z0-9]{6,12})',
                html, re.DOTALL
            )
            if not mid_pattern:
                # Chercher globalement
                mid_pattern = re.search(r'\?mid=([A-Za-z0-9]{6,12})', html)

            mid = mid_pattern.group(1) if mid_pattern else home_slug + "_" + away_slug

            home_name = re.sub(r'-[A-Za-z0-9]{6,10}$', '', home_slug).replace("-", " ").title()
            away_name = re.sub(r'-[A-Za-z0-9]{6,10}$', '', away_slug).replace("-", " ").title()

            if not any(m["mid"] == mid for m in matches):
                matches.append({
                    "mid": mid,
                    "home": normalize_team_name(home_name),
                    "away": normalize_team_name(away_name),
                    "date": today_str
                })
                print(f"  ✅ {home_name} vs {away_name} | mid={mid}")

    except Exception as e:
        print("Erreur get_today_matches:", e)

    # Fallback: chercher via l'API Flashscore feed du jour
    if not matches:
        print("Fallback: recherche via feeds Flashscore...")
        try:
            # Feed liste des matchs du sport football
            feed_url = f"https://{PROJECT}.flashscore.ninja/46/x/feed/f_1_0_3_fr_1"
            r2 = scraper.get(feed_url, headers=FS_HEADERS, timeout=10)
            print("Feed status:", r2.status_code, "| Taille:", len(r2.text))
            if r2.status_code == 200 and len(r2.text) > 10:
                # Chercher les IDs algériens dans le feed
                for sw_id in ALGERIA_SW_IDS:
                    if sw_id in r2.text:
                        print(f"  ID algérien trouvé dans feed: {sw_id}")
                        # Extraire le mid associé
                        idx = r2.text.find(sw_id)
                        context = r2.text[max(0, idx-200):idx+200]
                        mid_m = re.search(r'([A-Za-z0-9]{8})', context)
                        if mid_m:
                            print(f"  Contexte: {context[:200]}")
        except Exception as e:
            print("Erreur fallback:", e)

    return matches

def get_lineups_from_feed(mid):
    """
    Récupère les lineups depuis l'API Flashscore ninja.
    Feed: df_li_1_{mid}_1_fr_1
    Format: LH=index, LC=équipe(1=dom,2=ext), LI=nom, LJ=numéro, LP=ID, LK=1=titulaire/2=remplaçant
    """
    url = f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_li_1_{mid}_1_fr_1"
    try:
        r = scraper.get(url, headers=FS_HEADERS, timeout=10)
        if r.status_code != 200 or len(r.text) < 10:
            return None

        entries = parse_feed(r.text)

        home_starters, away_starters = [], []
        home_subs, away_subs = [], []
        current_team = 1  # 1=dom, 2=ext

        for e in entries:
            # LB = header (Titulaires/Remplaçants)
            if "LB" in e and "LI" not in e:
                continue

            # LC = changement d'équipe
            if "LC" in e and "LI" not in e:
                current_team = int(e.get("LC", 1))
                continue

            # LI = nom joueur
            if "LI" not in e:
                continue

            name = e.get("LI", "")
            number = e.get("LJ", "")
            player_id = e.get("LP", "")
            pos_raw = e.get("LS", "")
            is_gk = "Вратарь" in pos_raw or "(В)" in e.get("LR", "")
            is_sub = e.get("LK", "1") == "2"

            player = {
                "name": name,
                "number": number,
                "sw_player_id": player_id,
                "is_gk": is_gk,
                "is_captain": "(C)" in e.get("LR", ""),
            }

            if current_team == 1:  # Domicile
                if is_sub:
                    home_subs.append(player)
                else:
                    home_starters.append(player)
            else:  # Extérieur
                if is_sub:
                    away_subs.append(player)
                else:
                    away_starters.append(player)

        if home_starters or away_starters:
            print(f"  Titulaires: {len(home_starters)} dom, {len(away_starters)} ext")
            print(f"  Remplaçants: {len(home_subs)} dom, {len(away_subs)} ext")
            return {
                "home_players": home_starters[:11],
                "away_players": away_starters[:11],
                "home_subs": home_subs[:9],
                "away_subs": away_subs[:9],
            }
        return None

    except Exception as e:
        print(f"  Erreur lineups feed: {e}")
        return None

def get_fixture_id(home, away, match_date):
    try:
        r = requests.get(
            SB_URL + "/rest/v1/algeria_lineups?home_team=eq." + requests.utils.quote(home) +
            "&away_team=eq." + requests.utils.quote(away) +
            "&match_date=eq." + match_date + "&select=fixture_id",
            headers=SB_HEADERS
        ).json()
        if r and r[0].get("fixture_id"):
            return r[0]["fixture_id"]
    except:
        pass
    return 0

# ══════════════════════════════════════════════════
print("=== Algeria Lineups (Flashscore API)", datetime.now().strftime("%H:%M:%S"), "===")
matches = get_today_matches()
print(f"Matchs aujourd'hui: {len(matches)}")

if not matches:
    print("Aucun match aujourd'hui - OK")
    exit(0)

for match in matches:
    mid = match["mid"]
    home = match["home"]
    away = match["away"]
    match_date = match["date"]
    print(f"\n--- {home} vs {away} (mid={mid}) ---")

    # Vérifier si déjà scrapé
    try:
        check = requests.get(
            SB_URL + "/rest/v1/algeria_lineups?soccerway_mid=eq." + requests.utils.quote(str(mid)) +
            "&select=id,home_players",
            headers=SB_HEADERS
        ).json()
        if check and check[0].get("home_players") and len(check[0]["home_players"]) > 0:
            print("Déjà scrapé")
            continue
    except:
        pass

    lineups = get_lineups_from_feed(mid)
    if lineups:
        fixture_id = get_fixture_id(home, away, match_date)
        res = requests.post(SB_URL + "/rest/v1/algeria_lineups", headers=SB_HEADERS, json={
            "fixture_id": fixture_id,
            "soccerway_mid": str(mid),
            "home_team": home,
            "away_team": away,
            "match_date": match_date,
            "home_players": lineups["home_players"],
            "away_players": lineups["away_players"],
            "home_subs": lineups["home_subs"],
            "away_subs": lineups["away_subs"],
            "scraped_at": datetime.now(timezone.utc).isoformat()
        })
        print(f"Sauvegarde: {res.status_code}")
    else:
        print("Lineups pas encore disponibles")

    time.sleep(1)

print("=== Terminé ===")