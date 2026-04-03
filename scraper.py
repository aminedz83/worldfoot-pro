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

SW_CLUBS = {
    "JS Kabylie":      {"sw_id": "Wfaskwf0", "slug": "kabylie"},
    "CR Belouizdad":   {"sw_id": "vNJLB2jP", "slug": "belouizdad"},
    "MC Alger":        {"sw_id": "tnY2Lfcp", "slug": "mc-alger"},
    "USM Alger":       {"sw_id": "zXBidj5t", "slug": "usm-alger"},
    "CS Constantine":  {"sw_id": "nBionu2l", "slug": "constantine"},
    "ES Setif":        {"sw_id": "EDgC6qYp", "slug": "setif"},
    "MC Oran":         {"sw_id": "CrCmB35M", "slug": "oran"},
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
    """Récupère matchs du jour via SofaScore tournament endpoint"""
    today_str = date.today().strftime("%Y-%m-%d")
    matches = []

    # Essai SofaScore scheduled events
    try:
        r = requests.get(
            f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today_str}",
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
                     "Accept": "application/json", "Referer": "https://www.sofascore.com/"},
            timeout=15
        )
        print(f"SofaScore: {r.status_code}")
        if r.status_code == 200:
            alg = [e for e in r.json().get("events", []) if e.get("tournament", {}).get("id") == 841]
            print(f"Matchs Ligue 1: {len(alg)}")
            for e in alg:
                home = normalize_team_name(e["homeTeam"]["name"])
                away = normalize_team_name(e["awayTeam"]["name"])
                print(f"  {home} vs {away}")
                matches.append({"home": home, "away": away, "date": today_str})
            return matches
    except Exception as e:
        print(f"SofaScore erreur: {e}")

    return matches

def get_mid_from_flashscore(home_name, away_name):
    """
    Flashscore = Soccerway même base de données
    URL: /game/soccer/{home-slug}-{home-id}/{away-slug}-{away-id}/
    Le mid est dans le HTML ou l'URL
    """
    home_info = SW_CLUBS.get(home_name)
    away_info = SW_CLUBS.get(away_name)
    if not home_info or not away_info:
        print(f"  IDs manquants")
        return None

    # Tester plusieurs domaines Flashscore
    bases = [
        "https://www.flashscore.com/game/soccer",
        "https://www.flashscore.ca/game/soccer",
        "https://d.flashscore.com/x/feed/df_lin_1_",  # endpoint données
    ]

    headers_list = [
        # Headers Flashscore
        {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Accept-Language": "fr-FR,fr;q=0.9",
            "Referer": "https://www.flashscore.com/",
        },
        # Headers Soccerway
        {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "fr-FR,fr;q=0.9",
            "Referer": "https://www.soccerway.com/",
        },
    ]

    slug = f"{home_info['slug']}-{home_info['sw_id']}/{away_info['slug']}-{away_info['sw_id']}"

    for base in bases[:2]:
        url = f"{base}/{slug}/"
        print(f"  TEST: {url}")
        try:
            for hdrs in headers_list:
                r = requests.get(url, headers=hdrs, timeout=15, allow_redirects=True)
                print(f"  Status: {r.status_code} — url: {r.url[-60:]}")
                if r.status_code == 200:
                    # Chercher mid
                    for pattern in [r"mid=([A-Za-z0-9]+)", r'"mid"\s*:\s*"([A-Za-z0-9]+)"',
                                    r"data-mid=['\"]([A-Za-z0-9]+)['\"]", r"/([A-Za-z0-9]{8})/lineups"]:
                        m = re.search(pattern, r.url + r.text[:5000])
                        if m and len(m.group(1)) == 8:
                            print(f"  mid trouvé: {m.group(1)}")
                            return m.group(1)
                    print(f"  mid non trouvé — sample: {r.text[1500:1800]}")
                    break
        except Exception as e:
            print(f"  Erreur: {e}")

    return None

def scrape_lineups_flashscore(mid):
    """
    Flashscore endpoint lineups — même mid que Soccerway
    Tester différents endpoints Flashscore/Soccerway
    """
    endpoints = [
        f"https://www.flashscore.com/game/soccer/x/x/lineups/?mid={mid}",
        f"https://www.flashscore.ca/game/soccer/x/x/lineups/?mid={mid}",
        f"https://d.flashscore.com/x/feed/df_lin_1_{mid}",
        f"https://local-global.flashscore.ninja/2/x/feed/df_lin_1_{mid}",
        # Soccerway variantes
        f"https://ca.soccerway.com/game/x/x/summary/lineups/?mid={mid}",
        f"https://fr.soccerway.com/game/x/x/summary/lineups/?mid={mid}",
        f"https://uk.soccerway.com/game/x/x/summary/lineups/?mid={mid}",
    ]

    headers_fs = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Referer": "https://www.flashscore.com/",
        "x-fsign": "SW9D1eZo",  # Header Flashscore
    }

    for url in endpoints:
        try:
            r = requests.get(url, headers=headers_fs, timeout=15)
            print(f"  {url[-50:]}: {r.status_code} ({len(r.text)} chars)")
            if r.status_code != 200:
                continue

            # Endpoint JSON Flashscore
            if "flashscore.ninja" in url or "/feed/" in url:
                print(f"  Feed sample: {r.text[:300]}")
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            if not soup.find(string=re.compile(r"STARTING LINEUP", re.I)):
                print(f"  Pas de STARTING LINEUP — sample: {r.text[500:700]}")
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
                print(f"  ✅ {len(home_starters)} dom, {len(away_starters)} ext")
                return {
                    "home_players": home_starters[:11], "away_players": away_starters[:11],
                    "home_subs": home_subs[:9], "away_subs": away_subs[:9]
                }
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

print("=== Algeria Lineups", datetime.now().strftime("%H:%M:%S"), "===")
today_str = date.today().strftime("%Y-%m-%d")

# TEST direct avec mid connu
print("\n=== TEST lineups Constantine vs Oran (mid=OjLecDU9) ===")
lineups = scrape_lineups_flashscore("OjLecDU9")
if lineups:
    print(f"✅ LINEUPS OK!")
    res = requests.post(SB_URL + "/rest/v1/algeria_lineups", headers=SB_HEADERS, json={
        "fixture_id": 0, "soccerway_mid": "OjLecDU9",
        "home_team": "CS Constantine", "away_team": "MC Oran",
        "match_date": today_str,
        "home_players": lineups["home_players"], "away_players": lineups["away_players"],
        "home_subs": lineups.get("home_subs", []), "away_subs": lineups.get("away_subs", []),
        "scraped_at": datetime.now(timezone.utc).isoformat()
    })
    print(f"Sauvegarde: {res.status_code}")
else:
    print("❌ Aucun endpoint ne fonctionne")

# TEST get_mid via Flashscore
print("\n=== TEST get_mid Constantine vs Oran via Flashscore ===")
mid = get_mid_from_flashscore("CS Constantine", "MC Oran")
print(f"Mid: {mid}")

# Flux normal
print("\n=== FLUX NORMAL ===")
matches = get_today_fixtures()
print(f"Matchs: {len(matches)}")
if matches:
    for match in matches:
        home, away = match["home"], match["away"]
        print(f"\n--- {home} vs {away} ---")
        mid = get_mid_from_flashscore(home, away)
        if not mid:
            continue
        lineups = scrape_lineups_flashscore(mid)
        if lineups:
            res = requests.post(SB_URL + "/rest/v1/algeria_lineups", headers=SB_HEADERS, json={
                "fixture_id": 0, "soccerway_mid": mid,
                "home_team": home, "away_team": away, "match_date": today_str,
                "home_players": lineups["home_players"], "away_players": lineups["away_players"],
                "home_subs": lineups.get("home_subs", []), "away_subs": lineups.get("away_subs", []),
                "scraped_at": datetime.now(timezone.utc).isoformat()
            })
            print(f"  Sauvegarde: {res.status_code}")

print("=== Termine ===")