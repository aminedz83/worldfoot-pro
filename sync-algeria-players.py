import requests, os, json, time
from datetime import datetime, timezone

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
APIFY_TOKEN = os.environ["APIFY_TOKEN"]
SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# 16 clubs avec URLs SofaScore squad
CLUBS = [
    {"name": "JS Kabylie",      "sf_id": 42202,  "slug": "js-kabylie"},
    {"name": "CR Belouizdad",   "sf_id": 42207,  "slug": "cr-belouizdad"},
    {"name": "MC Alger",        "sf_id": 42204,  "slug": "mc-alger"},
    {"name": "USM Alger",       "sf_id": 42206,  "slug": "usm-alger"},
    {"name": "CS Constantine",  "sf_id": 55393,  "slug": "cs-constantine"},
    {"name": "ES Setif",        "sf_id": 41756,  "slug": "es-setif"},
    {"name": "MC Oran",         "sf_id": 45001,  "slug": "mc-oran"},
    {"name": "ASO Chlef",       "sf_id": 42201,  "slug": "aso-chlef"},
    {"name": "JS Saoura",       "sf_id": 79565,  "slug": "js-saoura"},
    {"name": "ES Ben Aknoun",   "sf_id": 133444, "slug": "es-ben-aknoun"},
    {"name": "USM Khenchela",   "sf_id": 238384, "slug": "usm-khenchela"},
    {"name": "MB Rouissat",     "sf_id": 238383, "slug": "mb-rouisset"},
    {"name": "Paradou AC",      "sf_id": 212197, "slug": "paradou-ac"},
    {"name": "ES Mostaganem",   "sf_id": 186100, "slug": "es-mostaganem"},
    {"name": "MC El Bayadh",    "sf_id": 133466, "slug": "mc-el-bayadh"},
    {"name": "Olympique Akbou", "sf_id": 306567, "slug": "olympique-akbou"},
]

def run_apify(url):
    """Lancer SofaScore Scraper PRO sur Apify"""
    resp = requests.post(
        f"https://api.apify.com/v2/acts/VzKtdb1t0Qnc07X8V/runs?token={APIFY_TOKEN}",
        json={"startUrls": [{"url": url}]},
        timeout=30
    )
    if resp.status_code not in [200, 201]:
        print(f"  Erreur Apify: {resp.status_code}")
        return None

    run_id = resp.json().get("data", {}).get("id")
    if not run_id:
        return None
    print(f"  Run ID: {run_id}")

    # Attendre la fin
    for i in range(30):
        time.sleep(10)
        status = requests.get(
            f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
        ).json().get("data", {}).get("status", "UNKNOWN")
        print(f"  Status [{i+1}]: {status}")
        if status in ["SUCCEEDED", "FAILED", "ABORTED"]:
            break

    if status != "SUCCEEDED":
        return None

    items = requests.get(
        f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items?token={APIFY_TOKEN}"
    ).json()
    return items

def save_players(items, team_name, sf_team_id):
    """Extraire et sauvegarder les joueurs depuis le résultat Apify"""
    saved = 0
    
    for item in items:
        data = item.get("data", {})
        if not data:
            continue
        
        # Les joueurs sont dans data.players ou directement dans data
        players_list = data.get("players", [])
        if not players_list and isinstance(data, list):
            players_list = data
        
        for player_item in players_list:
            p = player_item.get("player", player_item)
            sf_id = p.get("id")
            if not sf_id:
                continue

            # Valeur marchande
            mv = None
            if p.get("proposedMarketValueRaw"):
                mv = p["proposedMarketValueRaw"].get("value")
            elif p.get("proposedMarketValue"):
                mv = p["proposedMarketValue"]

            # Date fin contrat
            contract_until = None
            if p.get("contractUntilTimestamp"):
                try:
                    contract_until = datetime.fromtimestamp(
                        p["contractUntilTimestamp"], tz=timezone.utc
                    ).isoformat()
                except:
                    pass

            # Position
            pos_map = {"G": "G", "D": "D", "M": "M", "F": "F"}
            position = pos_map.get(p.get("position", ""), p.get("position", ""))

            # Photo
            photo_url = f"https://api.sofascore.com/api/v1/player/{sf_id}/image"

            # Nationalité
            nationality = ""
            if p.get("country"):
                nationality = p["country"].get("name", "")

            record = {
                "sofascore_id": sf_id,
                "soccerway_name": p.get("name", ""),
                "short_name": p.get("shortName", ""),
                "slug": p.get("slug", ""),
                "team_name": team_name,
                "sofascore_team_id": sf_team_id,
                "position": position,
                "jersey_number": str(p.get("shirtNumber", "") or ""),
                "nationality": nationality,
                "market_value": mv,
                "contract_until": contract_until,
                "photo_url": photo_url,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

            res = requests.post(
                f"{SB_URL}/rest/v1/algeria_players_sw",
                headers=SB_HEADERS,
                json=record
            )
            if res.status_code in [200, 201]:
                saved += 1
            else:
                print(f"  Erreur save {record['soccerway_name']}: {res.status_code} - {res.text[:100]}")

    return saved

# MAIN
print(f"=== Sync Algeria Players via Apify SofaScore ===")
print(f"Heure: {datetime.now().strftime('%H:%M:%S')}")

total = 0
for club in CLUBS:
    print(f"\n--- {club['name']} ---")
    url = f"https://www.sofascore.com/team/football/{club['slug']}/{club['sf_id']}#tab:squad"
    print(f"  URL: {url}")

    items = run_apify(url)
    if not items:
        print(f"  Aucun résultat")
        continue

    print(f"  {len(items)} items reçus")
    saved = save_players(items, club["name"], club["sf_id"])
    total += saved
    print(f"  ✓ {saved} joueurs sauvegardés")
    time.sleep(3)

print(f"\n=== Terminé: {total} joueurs synchronisés ===")