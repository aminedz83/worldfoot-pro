import requests, os, json, time
from datetime import datetime, timezone

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

SF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/"
}

# 16 clubs Ligue 1 algérienne avec leurs IDs SofaScore
CLUBS = [
    {"name": "MC Alger",        "sofascore_id": 42204},
    {"name": "JS Saoura",       "sofascore_id": 79565},
    {"name": "Olympique Akbou", "sofascore_id": 306567},
    {"name": "CS Constantine",  "sofascore_id": 55393},
    {"name": "MC Oran",         "sofascore_id": 45001},
    {"name": "CR Belouizdad",   "sofascore_id": 42207},
    {"name": "JS Kabylie",      "sofascore_id": 42202},
    {"name": "ES Ben Aknoun",   "sofascore_id": 133444},
    {"name": "USM Alger",       "sofascore_id": 42206},
    {"name": "USM Khenchela",   "sofascore_id": 238384},
    {"name": "ASO Chlef",       "sofascore_id": 42201},
    {"name": "MB Rouissat",     "sofascore_id": 238383},
    {"name": "ES Setif",        "sofascore_id": 41756},
    {"name": "Paradou AC",      "sofascore_id": 212197},
    {"name": "ES Mostaganem",   "sofascore_id": 186100},
    {"name": "MC El Bayadh",    "sofascore_id": 133466},
]

def fetch_team_players(team_id, team_name):
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/players"
    try:
        r = requests.get(url, headers=SF_HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"Erreur {r.status_code} pour {team_name}")
            return []
        data = r.json()
        players = data.get("players", [])
        print(f"{team_name}: {len(players)} joueurs")
        return players
    except Exception as e:
        print(f"Erreur {team_name}: {e}")
        return []

def save_players(players, team_name, team_sofascore_id):
    saved = 0
    for item in players:
        p = item.get("player", {})
        if not p.get("id"):
            continue
        
        # Date de naissance
        dob = None
        if p.get("dateOfBirth"):
            dob = p["dateOfBirth"]
        
        # Date fin contrat
        contract_until = None
        if p.get("contractUntilTimestamp"):
            contract_until = datetime.fromtimestamp(
                p["contractUntilTimestamp"], tz=timezone.utc
            ).isoformat()
        
        data = {
            "sofascore_id": p["id"],
            "name": p.get("name", ""),
            "short_name": p.get("shortName", ""),
            "slug": p.get("slug", ""),
            "sofascore_team_id": team_sofascore_id,
            "team_name": team_name,
            "position": p.get("position", ""),
            "jersey_number": str(p.get("jerseyNumber", "") or p.get("shirtNumber", "") or ""),
            "date_of_birth": dob,
            "height": p.get("height"),
            "preferred_foot": p.get("preferredFoot", ""),
            "nationality": p.get("country", {}).get("name", "") if p.get("country") else "",
            "market_value": p.get("proposedMarketValueRaw", {}).get("value") if p.get("proposedMarketValueRaw") else None,
            "contract_until": contract_until,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        res = requests.post(
            f"{SB_URL}/rest/v1/algeria_players",
            headers=SB_HEADERS,
            json=data
        )
        if res.status_code in [200, 201]:
            saved += 1
        
    print(f"  → {saved} joueurs sauvegardés")
    return saved

print("=== Sync Algeria Players depuis SofaScore ===")
print(f"Heure: {datetime.now().strftime('%H:%M:%S')}")
print(f"Clubs à synchroniser: {len(CLUBS)}")

total = 0
for club in CLUBS:
    print(f"\n--- {club['name']} ---")
    players = fetch_team_players(club["sofascore_id"], club["name"])
    if players:
        saved = save_players(players, club["name"], club["sofascore_id"])
        total += saved
    time.sleep(1)  # Respecter le rate limit SofaScore

print(f"\n=== Terminé: {total} joueurs synchronisés ===")