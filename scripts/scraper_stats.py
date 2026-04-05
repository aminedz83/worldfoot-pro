"""
scraper_stats.py - Enrichit les matchs avec les minutes jouées depuis Flashscore
IE=6 → joueur sort | IE=7 → joueur entre
"""
import requests, os, re, time
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

def parse_minute(minute_str):
    if not minute_str:
        return None
    m = re.search(r'(\d+)(?:\+(\d+))?', minute_str)
    if m:
        return int(m.group(1)) + (int(m.group(2)) if m.group(2) else 0)
    return None

def get_matches_without_minutes():
    try:
        r = requests.get(
            SB_URL + "/rest/v1/algeria_lineups?select=id,soccerway_mid,home_players,away_players,home_subs,away_subs,match_date,home_team,away_team&order=match_date.desc&limit=50",
            headers={**SB_HEADERS, "Prefer": ""},
            timeout=15
        )
        rows = r.json()
        print(f"  Total rows Supabase: {len(rows)}")
        to_update = []
        for row in rows:
            hp = row.get("home_players") or []
            home = row.get("home_team", "?")
            away = row.get("away_team", "?")
            if not hp or len(hp) == 0:
                print(f"  Skip {home} vs {away}: pas de joueurs")
                continue
            first = hp[0]
            keys = list(first.keys())
            print(f"  Check {home} vs {away}: {keys}")
            # Traiter si données incomplètes
            needs_update = (
                "minutes" not in first
                or first.get("minutes") is None
                or "sw_player_id" not in first
                or "yellow" not in first
            )
            if needs_update:
                print(f"    → A traiter!")
                to_update.append(row)
            else:
                print(f"    → OK (minutes={first.get('minutes')})")
        return to_update
    except Exception as e:
        print("Erreur fetch:", e)
        return []

def get_minutes_from_feed(mid):
    url = f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_sui_1_{mid}_1_fr_1"
    minutes_out = {}
    minutes_in = {}
    try:
        r = scraper.get(url, headers=FS_HEADERS, timeout=10)
        if r.status_code != 200 or len(r.text) < 5:
            return {}, {}
        for block in r.text.split("~"):
            fields = {}
            for field in block.split("¬"):
                if "÷" in field:
                    k, _, v = field.partition("÷")
                    fields[k.strip()] = v.strip()
            ie = fields.get("IE", "")
            minute = parse_minute(fields.get("IB", ""))
            pid = fields.get("IM", "")
            if ie == "6" and pid and minute:
                minutes_out[pid] = minute
            if ie == "7" and pid and minute:
                minutes_in[pid] = minute
    except Exception as e:
        print(f"  Erreur feed: {e}")
    return minutes_out, minutes_in

def enrich_players(players, minutes_out, minutes_in, is_sub=False):
    enriched = []
    for p in players:
        new_p = dict(p)
        pid = p.get("sw_player_id", "")
        if not is_sub:
            new_p["minutes"] = minutes_out.get(pid, 90)
        else:
            new_p["minutes"] = (90 - minutes_in[pid]) if pid in minutes_in else 0
        enriched.append(new_p)
    return enriched

def update_match(row_id, home_players, away_players, home_subs, away_subs):
    try:
        r = requests.patch(
            SB_URL + "/rest/v1/algeria_lineups?id=eq." + str(row_id),
            headers={**SB_HEADERS, "Prefer": "return=minimal"},
            json={
                "home_players": home_players,
                "away_players": away_players,
                "home_subs": home_subs,
                "away_subs": away_subs,
                "scraped_at": datetime.now(timezone.utc).isoformat()
            },
            timeout=15
        )
        return r.status_code in [200, 204]
    except Exception as e:
        print(f"  Erreur: {e}")
        return False

# ══════════════════════
print("=== Sync Minutes Joueurs (Flashscore) ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

matches = get_matches_without_minutes()
print(f"\n{len(matches)} matchs sans minutes à traiter\n")

updated = 0
errors = 0

for match in matches:
    mid = match.get("soccerway_mid", "")
    home = match.get("home_team", "?")
    away = match.get("away_team", "?")
    date = match.get("match_date", "?")
    print(f"\n📋 {home} vs {away} ({date}) | mid={mid}")

    minutes_out, minutes_in = get_minutes_from_feed(mid)
    print(f"  Sortants: {len(minutes_out)} | Entrants: {len(minutes_in)}")

    hp = enrich_players(match.get("home_players") or [], minutes_out, minutes_in, is_sub=False)
    ap = enrich_players(match.get("away_players") or [], minutes_out, minutes_in, is_sub=False)
    hs = enrich_players(match.get("home_subs") or [], minutes_out, minutes_in, is_sub=True)
    as_ = enrich_players(match.get("away_subs") or [], minutes_out, minutes_in, is_sub=True)

    mins = [p.get("minutes") for p in hp]
    print(f"  Dom minutes: {mins}")

    ok = update_match(match["id"], hp, ap, hs, as_)
    print(f"  {'✅ OK' if ok else '❌ Erreur'}")
    if ok:
        updated += 1
    else:
        errors += 1
    time.sleep(1)

print(f"\n=== Terminé: {updated} mis à jour, {errors} erreurs ===")