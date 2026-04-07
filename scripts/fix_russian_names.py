"""
fix_russian_names.py
Re-scrape les lineups des matchs existants pour remplacer les noms russes
par les noms en anglais (latin).
"""
import os, requests
import cloudscraper
from datetime import datetime, timezone

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
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

def has_cyrillic(text):
    return any('\u0400' <= c <= '\u04FF' for c in (text or ""))

def parse_feed(text):
    blocks = text.split("~")
    result = []
    for block in blocks:
        if not block.strip():
            continue
        fields = {}
        for field in block.split("¬"):
            if "÷" in field:
                k, _, v = field.partition("÷")
                fields[k.strip()] = v.strip()
        if fields:
            result.append(fields)
    return result

def lh_to_pos(lh):
    if lh == 0: return "G"
    if lh <= 4: return "D"
    if lh <= 7: return "M"
    return "A"

def get_events(mid):
    url = f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_sui_1_{mid}_1_en_1"
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
            ie = fields.get("IE", "")
            pid = fields.get("IM", "")
            minute = fields.get("IB", "")
            if not pid: continue
            if ie == "3":
                events["goals"].setdefault(pid, []).append(minute)
            elif ie == "1":
                events["yellow"][pid] = minute
            elif ie == "6":
                events["red"][pid] = minute
    except Exception as e:
        print(f"  Erreur events: {e}")
    return events

def scrape_lineups_en(mid):
    """Scraper les lineups EN ANGLAIS"""
    url = f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_li_1_{mid}_1_en_1"
    try:
        r = scraper.get(url, headers=FS_HEADERS, timeout=10)
        if r.status_code != 200 or len(r.text) < 10:
            return None

        events = get_events(mid)
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
            pid = fields.get("LP", "")
            lk = fields.get("LK", "1")
            is_sub = lk == "2"
            is_gk = fields.get("LS", "") == "Goalkeeper" or "(G)" in fields.get("LR", "") or "Вратарь" in fields.get("LS", "")

            player = {
                "name": fields.get("LI", ""),
                "number": fields.get("LJ", ""),
                "sw_player_id": pid,
                "is_gk": is_gk,
                "is_captain": "(C)" in fields.get("LR", ""),
                "pos": "G" if is_gk else (lh_to_pos(lh) if not is_sub else ""),
                "goals": len(events["goals"].get(pid, [])),
                "yellow": pid in events["yellow"],
                "red": pid in events["red"],
            }

            if current_team == 1:
                home_subs.append(player) if is_sub else home_starters.append(player)
            else:
                away_subs.append(player) if is_sub else away_starters.append(player)

        if home_starters or away_starters:
            return {
                "home_players": home_starters[:11],
                "away_players": away_starters[:11],
                "home_subs": home_subs[:9],
                "away_subs": away_subs[:9],
            }
        return None
    except Exception as e:
        print(f"  Erreur: {e}")
        return None

# ══════════════════════════
print("=== Fix noms russes → anglais ===")

# Récupérer tous les matchs
r = requests.get(
    SB_URL + "/rest/v1/algeria_lineups?select=id,soccerway_mid,home_team,away_team,home_players,away_players&order=match_date.desc&limit=50",
    headers={**SB_HEADERS, "Prefer": ""},
    timeout=15
)
rows = r.json()
print(f"Total matchs: {len(rows)}")

fixed = 0
for row in rows:
    mid = row.get("soccerway_mid", "")
    home = row.get("home_team", "")
    away = row.get("away_team", "")
    hp = row.get("home_players") or []

    # Vérifier si des noms sont en cyrillique
    has_russian = any(has_cyrillic(p.get("name", "")) for p in hp)
    if not has_russian:
        print(f"  ✅ {home} vs {away} - OK")
        continue

    print(f"\n  🔄 {home} vs {away} - noms russes détectés!")
    lineups = scrape_lineups_en(mid)
    if lineups:
        # Vérifier que les nouveaux noms sont en latin
        new_names = [p.get("name", "") for p in lineups["home_players"][:3]]
        print(f"  Nouveaux noms: {new_names}")

        res = requests.patch(
            SB_URL + "/rest/v1/algeria_lineups?id=eq." + str(row["id"]),
            headers={**SB_HEADERS, "Prefer": "return=minimal"},
            json={
                "home_players": lineups["home_players"],
                "away_players": lineups["away_players"],
                "home_subs": lineups["home_subs"],
                "away_subs": lineups["away_subs"],
                "scraped_at": datetime.now(timezone.utc).isoformat()
            },
            timeout=15
        )
        print(f"  Sauvegarde: {res.status_code}")
        if res.status_code in [200, 204]:
            fixed += 1
    else:
        print(f"  ❌ Impossible de re-scraper")

print(f"\n=== Terminé: {fixed} matchs corrigés ===")