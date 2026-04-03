import requests
import os
import time

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

CLUBS = {
    918:  {"name": "JS Kabylie",        "tm_id": "3455"},
    904:  {"name": "CR Belouizdad",     "tm_id": "3456"},
    906:  {"name": "MC Alger",          "tm_id": "3457"},
    910:  {"name": "USM Alger",         "tm_id": "3459"},
    908:  {"name": "ES Setif",          "tm_id": "3461"},
    916:  {"name": "CS Constantine",    "tm_id": "14280"},
    907:  {"name": "MC Oran",           "tm_id": "14281"},
    905:  {"name": "ASO Chlef",         "tm_id": "14282"},
    917:  {"name": "JS Saoura",         "tm_id": "64706"},
    919:  {"name": "ES Ben Aknoun",     "tm_id": "87944"},
    920:  {"name": "USM Khenchela",     "tm_id": "87945"},
    921:  {"name": "MB Rouissat",       "tm_id": "87946"},
    922:  {"name": "Paradou AC",        "tm_id": "19718"},
    923:  {"name": "ES Mostaganem",     "tm_id": "87947"},
    924:  {"name": "MC El Bayadh",      "tm_id": "87948"},
    925:  {"name": "Olympique Akbou",   "tm_id": "87949"},
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WorldFootPro/1.0)"}
TM_API = "https://transfermarkt-api.fly.dev"

def fetch_club_players(tm_id, club_name):
    url = f"{TM_API}/clubs/{tm_id}/players"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"  TM {tm_id} ({club_name}): status={r.status_code}")
        if r.status_code == 200:
            return r.json().get("players", [])
        print(f"  Body: {r.text[:200]}")
        return []
    except Exception as e:
        print(f"  Erreur: {e}")
        return []

def find_tm_id(club_name):
    url = f"{TM_API}/clubs/search/{requests.utils.quote(club_name)}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                print(f"  Search trouvé: {results[0]}")
                return str(results[0].get("id",""))
    except Exception as e:
        print(f"  Search error: {e}")
    return None

def parse_mv(mv_str):
    if not mv_str:
        return None
    try:
        s = str(mv_str).replace("€","").replace(",",".").strip().lower()
        if "m" in s:
            return int(float(s.replace("m","").strip()) * 1000000)
        if "th" in s or "k" in s:
            return int(float(s.replace("th.","").replace("k","").strip()) * 1000)
        return int(float(s))
    except:
        return None

def upsert_supabase(rows):
    if not rows:
        return
    url = f"{SUPABASE_URL}/rest/v1/algeria_market_values"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    r = requests.post(url, headers=headers, json=rows, timeout=30)
    print(f"  Supabase: {r.status_code} — {len(rows)} joueurs")
    if r.status_code not in (200, 201):
        print(f"  Erreur: {r.text[:300]}")

def main():
    print("=== Sync Market Values Transfermarkt → Supabase ===\n")

    # Test API
    print("Test API...")
    try:
        r = requests.get(f"{TM_API}/clubs/search/JS%20Kabylie", headers=HEADERS, timeout=15)
        print(f"Search JSK: {r.status_code} → {r.text[:300]}\n")
    except Exception as e:
        print(f"Test échoué: {e}\n")

    total = 0
    for api_id, info in CLUBS.items():
        print(f"\n{info['name']} (API:{api_id} / TM:{info['tm_id']})")
        players = fetch_club_players(info["tm_id"], info["name"])

        if not players:
            real_id = find_tm_id(info["name"])
            if real_id:
                players = fetch_club_players(real_id, info["name"])

        if not players:
            time.sleep(2)
            continue

        print(f"  {len(players)} joueurs")
        rows = []
        for p in players:
            contract = p.get("contract") or {}
            until = contract.get("until") or p.get("contractExpiry") or ""
            cy = None
            if until:
                try: cy = int(str(until)[:4])
                except: pass
            rows.append({
                "tm_id":          str(p.get("id","")),
                "api_team_id":    api_id,
                "name":           p.get("name") or p.get("playerName"),
                "short_name":     p.get("name") or p.get("playerName"),
                "position":       p.get("position"),
                "shirt_number":   p.get("shirtNumber") or p.get("jerseyNumber"),
                "market_value":   parse_mv(p.get("marketValue")),
                "contract_until": cy,
                "nationality":    p.get("nationality") or (p.get("nationalities",[None])[0] if p.get("nationalities") else None),
                "age":            p.get("age"),
            })
        upsert_supabase(rows)
        total += len(rows)
        time.sleep(2)

    print(f"\n✅ Total: {total} joueurs")

if __name__ == "__main__":
    main()