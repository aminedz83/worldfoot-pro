import requests
import os
import json
import time
from datetime import datetime, timezone

SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_KEY:
    print("❌ Erreur: SUPABASE_KEY non trouvée")
    exit(1)

SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# 16 clubs Ligue 1 algérienne avec noms pour recherche
CLUBS = [
    {"name": "MC Alger",        "search": "MC Alger",        "sofascore_id": 42204},
    {"name": "JS Saoura",       "search": "JS Saoura",       "sofascore_id": 79565},
    {"name": "Olympique Akbou", "search": "Olympique Akbou", "sofascore_id": 306567},
    {"name": "CS Constantine",  "search": "CS Constantine",  "sofascore_id": 55393},
    {"name": "MC Oran",         "search": "MC Oran",         "sofascore_id": 45001},
    {"name": "CR Belouizdad",   "search": "CR Belouizdad",   "sofascore_id": 42207},
    {"name": "JS Kabylie",      "search": "JS Kabylie",      "sofascore_id": 42202},
    {"name": "ES Ben Aknoun",   "search": "Ben Aknoun",      "sofascore_id": 133444},
    {"name": "USM Alger",       "search": "USM Alger",       "sofascore_id": 42206},
    {"name": "USM Khenchela",   "search": "USM Khenchela",   "sofascore_id": 238384},
    {"name": "ASO Chlef",       "search": "ASO Chlef",       "sofascore_id": 42201},
    {"name": "MB Rouissat",     "search": "MB Rouissat",     "sofascore_id": 238383},
    {"name": "ES Setif",        "search": "ES Setif",        "sofascore_id": 41756},
    {"name": "Paradou AC",      "search": "Paradou AC",      "sofascore_id": 212197},
    {"name": "ES Mostaganem",   "search": "ES Mostaganem",   "sofascore_id": 186100},
    {"name": "MC El Bayadh",    "search": "MC El Bayadh",    "sofascore_id": 133466},
]

def fetch_team_players_thesportsdb(team_name, search_name):
    """Récupère les joueurs depuis TheSportsDB (gratuit, sans blocage)"""
    url = f"https://www.thesportsdb.com/api/v1/json/3/searchplayers.php?t={search_name.replace(' ', '%20')}"
    
    try:
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            players = data.get("player", [])
            
            if not players:
                # Essayer avec un nom plus court
                short_name = search_name.split()[-1] if len(search_name.split()) > 1 else search_name
                url2 = f"https://www.thesportsdb.com/api/v1/json/3/searchplayers.php?t={short_name}"
                response2 = requests.get(url2, timeout=15)
                if response2.status_code == 200:
                    data = response2.json()
                    players = data.get("player", [])
            
            if players:
                print(f"{team_name}: {len(players)} joueurs (TheSportsDB)")
                return players
            else:
                print(f"{team_name}: Aucun joueur trouvé")
                return []
        else:
            print(f"Erreur {response.status_code} pour {team_name}")
            return []
            
    except Exception as e:
        print(f"Erreur {team_name}: {e}")
        return []

def convert_to_sofascore_format(player, team_name, team_sofascore_id):
    """Convertit le format TheSportsDB vers le format SofaScore"""
    return {
        "player": {
            "id": int(player.get("idPlayer", 0)),
            "name": player.get("strPlayer", ""),
            "shortName": player.get("strPlayer", "").split()[-1] if player.get("strPlayer") else "",
            "slug": player.get("strPlayer", "").lower().replace(" ", "-"),
            "position": player.get("strPosition", ""),
            "jerseyNumber": player.get("strNumber", ""),
            "shirtNumber": player.get("strNumber", ""),
            "dateOfBirth": player.get("dateBorn", ""),
            "height": player.get("strHeight", ""),
            "preferredFoot": player.get("strPreferredFoot", ""),
            "country": {"name": player.get("strNationality", "")},
            "proposedMarketValueRaw": None,
            "contractUntilTimestamp": None
        }
    }

def save_players(players_data, team_name, team_sofascore_id):
    """Sauvegarde les joueurs dans Supabase"""
    saved = 0
    
    for player in players_data:
        # Convertir au format attendu
        p = player if "player" in player else convert_to_sofascore_format(player, team_name, team_sofascore_id)
        p_data = p.get("player", p)
        
        if not p_data.get("id"):
            continue
        
        # Date de naissance
        dob = p_data.get("dateOfBirth")
        if dob and len(dob) > 10:
            dob = dob[:10]
        
        data = {
            "sofascore_id": p_data["id"],
            "name": p_data.get("name", ""),
            "short_name": p_data.get("shortName", ""),
            "slug": p_data.get("slug", ""),
            "sofascore_team_id": team_sofascore_id,
            "team_name": team_name,
            "position": p_data.get("position", ""),
            "jersey_number": str(p_data.get("jerseyNumber", "") or p_data.get("shirtNumber", "") or ""),
            "date_of_birth": dob,
            "height": p_data.get("height"),
            "preferred_foot": p_data.get("preferredFoot", ""),
            "nationality": p_data.get("country", {}).get("name", "") if p_data.get("country") else "",
            "market_value": None,
            "contract_until": None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Supprimer les champs vides
        data = {k: v for k, v in data.items() if v is not None and v != ""}
        
        try:
            res = requests.post(
                f"{SB_URL}/rest/v1/algeria_players",
                headers=SB_HEADERS,
                json=data,
                timeout=10
            )
            if res.status_code in [200, 201]:
                saved += 1
        except Exception as e:
            pass
        
    print(f"  → {saved} joueurs sauvegardés")
    return saved

print("=== Sync Algeria Players depuis TheSportsDB ===")
print(f"Heure: {datetime.now().strftime('%H:%M:%S')}")
print(f"Clubs à synchroniser: {len(CLUBS)}")
print("(Alternative à SofaScore - API bloquée sur GitHub Actions)")
print()

total = 0
for club in CLUBS:
    print(f"\n--- {club['name']} ---")
    players = fetch_team_players_thesportsdb(club["name"], club["search"])
    
    if players:
        saved = save_players(players, club["name"], club["sofascore_id"])
        total += saved
    else:
        print(f"  → 0 joueur sauvegardé")
    
    time.sleep(0.5)  # Petit délai entre les requêtes

print(f"\n=== Terminé: {total} joueurs synchronisés ===")