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

PROJECT = "2043"
FS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://www.flashscore.ca/",
    "x-fsign": "SW9D1eZo",
}

TEAM_NAME_MAP = {
    "Kabylie": "JS Kabylie", "CR Belouizdad": "CR Belouizdad",
    "Belouizdad": "CR Belouizdad", "MC Alger": "MC Alger",
    "USM Alger": "USM Alger", "Constantine": "CS Constantine",
    "CS Constantine": "CS Constantine", "ES Setif": "ES Setif",
    "Setif": "ES Setif", "Oran": "MC Oran", "MC Oran": "MC Oran",
    "ASO Chlef": "ASO Chlef", "Chlef": "ASO Chlef",
    "Saoura": "JS Saoura", "JS Saoura": "JS Saoura",
    "Ben Aknoun": "ES Ben Aknoun", "ES Ben Aknoun": "ES Ben Aknoun",
    "Khenchela": "USM Khenchela", "USM Khenchela": "USM Khenchela",
    "Rouisset": "MB Rouissat", "Rouissat": "MB Rouissat",
    "Paradou": "Paradou AC", "Paradou AC": "Paradou AC",
    "Mostaganem": "ES Mostaganem", "ES Mostaganem": "ES Mostaganem",
    "El Bayadh": "MC El Bayadh", "MC El Bayadh": "MC El Bayadh",
    "Olympique Akbou": "Olympique Akbou",
}

def normalize(name):
    if name in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[name]
    for k, v in TEAM_NAME_MAP.items():
        if k.lower() in name.lower():
            return v
    return name

def lh_to_pos(lh):
    """Déduire la position depuis l'index LH"""
    if lh == 0: return "G"
    if lh <= 4:  return "D"
    if lh <= 7:  return "M"
    return "A"

def parse_events(mid):
    """
    Récupère buts et cartons depuis df_sui.
    IE=3 → But, IE=1 → Carton jaune, IE=6 → Carton rouge
    IM = player_id, IB = minute, IA = équipe (1=dom, 2=ext)
    """
    url = f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_sui_1_{mid}_1_fr_1"
    events = {"goals": {}, "yellow": {}, "red": {}}
    try:
        r = scraper.get(url, headers=FS_HEADERS, timeout=10)
        if r.status_code != 200 or len(r.text) < 5:
            return events

        for block in r.text.split("~"):
            fields = {}
            for field in block.split("¬"):
                if "÷" in field:
                    k, _, v = field.partition("÷")
                    fields[k.strip()] = v.strip()

            event_type = fields.get("IE", "")
            player_id = fields.get("IM", "")
            minute = fields.get("IB", "")

            if not player_id:
                continue

            if event_type == "3":  # But
                if player_id not in events["goals"]:
                    events["goals"][player_id] = []
                events["goals"][player_id].append(minute)
            elif event_type == "1":  # Carton jaune
                events["yellow"][player_id] = minute
            elif event_type == "6":  # Carton rouge
                events["red"][player_id] = minute

    except Exception as e:
        print(f"  Erreur events: {e}")
    return events

def get_lineups(mid):
    """
    Récupère lineups + positions + buts + cartons.
    LH = index position (0=GK,1-4=DEF,5-7=MID,8-10=ATT)
    LK = 1 titulaire (LK=15 aussi), 2 = remplaçant
    """
    url = f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_li_1_{mid}_1_fr_1"
    try:
        r = scraper.get(url, headers=FS_HEADERS, timeout=10)
        if r.status_code != 200 or len(r.text) < 10:
            print(f"  Lineups pas dispo (status={r.status_code}, taille={len(r.text)})")
            return None

        # Récupérer les événements
        events = parse_events(mid)
        print(f"  Buts: {len(events['goals'])} | Cartons J: {len(events['yellow'])} | Cartons R: {len(events['red'])}")

        home_starters, away_starters = [], []
        home_subs, away_subs = [], []
        current_team = 1

        for block in r.text.split("~"):
            fields = {}
            for field in block.split("¬"):
                if "÷" in field:
                    k, _, v = field.partition("÷")
                    fields[k.strip()] = v.strip()

            if "LC" in fields and "LI" not in fields:
                current_team = int(fields.get("LC", 1))
                continue
            if "LI" not in fields:
                continue

            lh = int(fields.get("LH", 99))
            player_id = fields.get("LP", "")
            lk = fields.get("LK", "1")
            is_sub = lk == "2"
            is_starter = lk in ["1", "15"]
            is_gk = fields.get("LS", "") == "Вратарь" or "(В)" in fields.get("LR", "")

            # Position depuis LH (seulement pour titulaires)
            pos = "G" if is_gk else (lh_to_pos(lh) if is_starter else "")

            player = {
                "name": fields.get("LI", ""),
                "number": fields.get("LJ", ""),
                "sw_player_id": player_id,
                "is_gk": is_gk,
                "is_captain": "(C)" in fields.get("LR", ""),
                "pos": pos,
                # Enrichissement avec événements
                "goals": len(events["goals"].get(player_id, [])),
                "yellow": player_id in events["yellow"],
                "red": player_id in events["red"],
            }

            if current_team == 1:
                home_subs.append(player) if is_sub else home_starters.append(player)
            else:
                away_subs.append(player) if is_sub else away_starters.append(player)

        if home_starters or away_starters:
            print(f"  ✅ Dom: {len(home_starters)} tit + {len(home_subs)} rempl")
            print(f"  ✅ Ext: {len(away_starters)} tit + {len(away_subs)} rempl")
            return {
                "home_players": home_starters[:11],
                "away_players": away_starters[:11],
                "home_subs": home_subs[:9],
                "away_subs": away_subs[:9],
            }
        return None

    except Exception as e:
        print(f"  Erreur lineups: {e}")
        return None

def get_today_matches():
    today_str = date.today().strftime("%Y-%m-%d")
    matches = []
    seen = set()
    try:
        r = scraper.get(
            "https://www.flashscore.ca/soccer/algeria/ligue-1/fixtures/",
            timeout=20
        )
        print(f"Flashscore status: {r.status_code} | Taille: {len(r.text)}")
        for block in r.text.split("~"):
            if "AA÷" not in block:
                continue
            fields = {}
            for field in block.split("¬"):
                if "÷" in field:
                    k, _, v = field.partition("÷")
                    fields[k.strip()] = v.strip()
            mid = fields.get("AA", "")
            ts = int(fields.get("AD", 0))
            if not mid or mid in seen:
                continue
            if ts:
                match_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                if match_date != today_str:
                    continue
            seen.add(mid)
            home = normalize(fields.get("CX", fields.get("WM", "")))
            away = normalize(fields.get("AF", fields.get("WN", "")))
            matches.append({"mid": mid, "home": home, "away": away, "date": today_str})
            print(f"  ✅ {home} vs {away} | mid={mid}")
    except Exception as e:
        print(f"Erreur: {e}")
    return matches

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

# ══════════════════════════
print("=== Algeria Lineups Scraper", datetime.now().strftime("%H:%M:%S"), "===")
matches = get_today_matches()
print(f"\nMatchs aujourd'hui: {len(matches)}")

if not matches:
    print("Aucun match - OK")
    exit(0)

for match in matches:
    mid, home, away, match_date = match["mid"], match["home"], match["away"], match["date"]
    print(f"\n--- {home} vs {away} (mid={mid}) ---")
    try:
        check = requests.get(
            SB_URL + "/rest/v1/algeria_lineups?soccerway_mid=eq." + requests.utils.quote(mid) +
            "&select=id,home_players", headers=SB_HEADERS
        ).json()
        if check and check[0].get("home_players") and len(check[0]["home_players"]) > 0:
            print("Déjà scrapé ✓")
            continue
    except:
        pass

    lineups = get_lineups(mid)
    if lineups:
        fixture_id = get_fixture_id(home, away, match_date)
        upsert_headers = dict(SB_HEADERS)
        upsert_headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        res = requests.post(SB_URL + "/rest/v1/algeria_lineups", headers=upsert_headers, json={
            "fixture_id": fixture_id,
            "soccerway_mid": mid,
            "home_team": home,
            "away_team": away,
            "match_date": match_date,
            "home_players": lineups["home_players"],
            "away_players": lineups["away_players"],
            "home_subs": lineups["home_subs"],
            "away_subs": lineups["away_subs"],
            "scraped_at": datetime.now(timezone.utc).isoformat()
        })
        print(f"Sauvegarde: {res.status_code} ({'OK' if res.status_code in [200,201,204] else 'ERREUR'})")
        if res.status_code == 409:
            # Forcer la mise à jour
            patch_res = requests.patch(
                SB_URL + "/rest/v1/algeria_lineups?soccerway_mid=eq." + requests.utils.quote(mid),
                headers=SB_HEADERS,
                json={
                    "home_players": lineups["home_players"],
                    "away_players": lineups["away_players"],
                    "home_subs": lineups["home_subs"],
                    "away_subs": lineups["away_subs"],
                    "scraped_at": datetime.now(timezone.utc).isoformat()
                }
            )
            print(f"  PATCH: {patch_res.status_code}")
    else:
        print("Pas encore dispo")
    time.sleep(1)

print("\n=== Terminé ===")