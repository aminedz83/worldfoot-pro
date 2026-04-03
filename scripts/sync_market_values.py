import requests
import os
import time
import json

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# Clubs Ligue 1 algérienne : API football ID → SofaScore ID
CLUBS = {
    918:  42202,  # JS Kabylie
    904:  42207,  # CR Belouizdad
    906:  42204,  # MC Alger
    910:  42206,  # USM Alger
    908:  41756,  # ES Setif
    916:  55393,  # CS Constantine
    907:  45001,  # MC Oran
    905:  42201,  # ASO Chlef
    917:  79565,  # JS Saoura
    919: 133444,  # ES Ben Aknoun
    920: 238384,  # USM Khenchela
    921: 238383,  # MB Rouissat
    922: 212197,  # Paradou AC
    923: 186100,  # ES Mostaganem
    924: 133466,  # MC El Bayadh
    925: 306567,  # Olympique Akbou
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

def fetch_team_players(sf_team_id):
    url = f"https://api.sofascore.com/api/v1/team/{sf_team_id}/players"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        print(f"  SofaScore {sf_team_id}: status={r.status_code}")
        if r.status_code == 200:
            return r.json().get("players", [])
        return []
    except Exception as e:
        print(f"  Erreur fetch SofaScore {sf_team_id}: {e}")
        return []

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
    print(f"  Supabase upsert: {r.status_code} — {len(rows)} joueurs")
    if r.status_code not in (200, 201):
        print(f"  Erreur: {r.text[:200]}")

def main():
    print("=== Sync Market Values SofaScore → Supabase ===")
    total = 0

    for api_team_id, sf_team_id in CLUBS.items():
        print(f"\nClub API:{api_team_id} / SF:{sf_team_id}")
        players = fetch_team_players(sf_team_id)

        if not players:
            print("  Aucun joueur récupéré, skip.")
            time.sleep(2)
            continue

        rows = []
        for entry in players:
            p = entry.get("player", {})
            mv_raw = p.get("proposedMarketValueRaw")
            mv = mv_raw.get("value") if mv_raw else None

            contract_ts = p.get("contractUntilTimestamp")
            contract_year = None
            if contract_ts:
                from datetime import datetime
                contract_year = datetime.utcfromtimestamp(contract_ts).year

            rows.append({
                "sofascore_id":  p.get("id"),
                "api_team_id":   api_team_id,
                "sf_team_id":    sf_team_id,
                "name":          p.get("name"),
                "short_name":    p.get("shortName"),
                "slug":          p.get("slug"),
                "position":      p.get("position"),
                "shirt_number":  p.get("shirtNumber"),
                "market_value":  mv,
                "contract_until": contract_year,
                "nationality":   p.get("nationality", {}).get("name") if p.get("nationality") else None,
                "age":           p.get("age"),
            })

        upsert_supabase(rows)
        total += len(rows)

        # Pause entre clubs pour ne pas se faire bloquer
        time.sleep(3)

    print(f"\n✅ Total: {total} joueurs synchronisés")

if __name__ == "__main__":
    main()