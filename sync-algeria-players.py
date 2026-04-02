import requests
import os
import json
import time
import random
from datetime import datetime, timezone

# Installer cloudscraper: pip install cloudscraper
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    print("⚠ cloudscraper non installé, utilisation de requests standard")
    CLOUDSCRAPER_AVAILABLE = False

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# 16 clubs Ligue 1 algérienne
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

def get_sofascore_headers():
    """Génère des headers réalistes"""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.sofascore.com/",
        "Origin": "https://www.sofascore.com",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
    }

def fetch_players_cloudscraper(team_id, team_name):
    """Utilise cloudscraper pour contourner Cloudflare"""
    if not CLOUDSCRAPER_AVAILABLE:
        return []
    
    for attempt in range(3):
        try:
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                }
            )
            
            url = f"https://api.sofascore.com/api/v1/team/{team_id}/players"
            response = scraper.get(url, headers=get_sofascore_headers(), timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                players = data.get("players", [])
                if players:
                    print(f"✓ {team_name}: {len(players)} joueurs (cloudscraper)")
                    return players
            else:
                print(f"⚠ Cloudscraper tentative {attempt+1}: Status {response.status_code}")
                time.sleep(3)
                
        except Exception as e:
            print(f"⚠ Cloudscraper erreur: {e}")
            time.sleep(3)
    
    return []

def fetch_players_requests_with_retry(team_id, team_name):
    """Version améliorée avec requests standard"""
    session = requests.Session()
    
    # Première visite pour obtenir des cookies
    try:
        session.get("https://www.sofascore.com/", headers=get_sofascore_headers(), timeout=10)
        time.sleep(1)
    except:
        pass
    
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/players"
    
    for attempt in range(5):
        try:
            headers = get_sofascore_headers()
            headers["X-Requested-With"] = "XMLHttpRequest"
            
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                players = data.get("players", [])
                if players:
                    print(f"✓ {team_name}: {len(players)} joueurs (requests)")
                    return players
            elif response.status_code == 403:
                wait_time = (attempt + 1) * 5
                print(f"⚠ 403 pour {team_name}, attente {wait_time}s...")
                time.sleep(wait_time)
            else:
                time.sleep(2)
                
        except Exception as e:
            print(f"⚠ Erreur: {e}")
            time.sleep(2)
    
    return []

def save_players(players, team_name, team_sofascore_id):
    """Sauvegarde dans Supabase"""
    saved = 0
    errors = 0
    
    for item in players:
        p = item.get("player", {})
        if not p.get("id"):
            continue
        
        # Nettoyer la date de naissance
        dob = p.get("dateOfBirth")
        if dob and len(dob) > 10:
            dob = dob[:10]
        
        # Gérer la valeur marchande
        market_value = None
        if p.get("proposedMarketValueRaw"):
            market_value = p["proposedMarketValueRaw"].get("value")
        
        # Gérer la date de contrat
        contract_until = None
        if p.get("contractUntilTimestamp"):
            try:
                contract_until = datetime.fromtimestamp(
                    p["contractUntilTimestamp"],
                    tz=timezone.utc
                ).isoformat()
            except:
                pass
        
        data = {
            "sofascore_id": p["id"],
            "name": (p.get("name") or "").strip(),
            "short_name": (p.get("shortName") or "").strip(),
            "slug": (p.get("slug") or "").strip(),
            "sofascore_team_id": team_sofascore_id,
            "team_name": team_name,
            "position": (p.get("position") or "").strip(),
            "jersey_number": str(p.get("jerseyNumber") or p.get("shirtNumber") or ""),
            "date_of_birth": dob,
            "height": p.get("height"),
            "preferred_foot": (p.get("preferredFoot") or "").strip(),
            "nationality": (p.get("country", {}).get("name", "") if p.get("country") else ""),
            "market_value": market_value,
            "contract_until": contract_until,
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
            else:
                errors += 1
        except:
            errors += 1
    
    print(f"  → {saved} sauvegardés, {errors} erreurs")
    return saved

# Main execution
print("=== Sync Algeria Players depuis SofaScore ===")
print(f"Heure: {datetime.now().strftime('%H:%M:%S')}")
print(f"Clubs à synchroniser: {len(CLUBS)}")
print(f"Cloudscraper disponible: {CLOUDSCRAPER_AVAILABLE}")
print()

total = 0
successful_clubs = 0

for idx, club in enumerate(CLUBS, 1):
    print(f"\n[{idx}/{len(CLUBS)}] --- {club['name']} ---")
    
    players = []
    
    # Stratégie 1: Cloudscraper (si disponible)
    if CLOUDSCRAPER_AVAILABLE:
        players = fetch_players_cloudscraper(club["sofascore_id"], club["name"])
    
    # Stratégie 2: Requests standard
    if not players:
        players = fetch_players_requests_with_retry(club["sofascore_id"], club["name"])
    
    if players:
        saved = save_players(players, club["name"], club["sofascore_id"])
        total += saved
        successful_clubs += 1
    else:
        print(f"  ❌ Échec total")
    
    # Pause entre les clubs
    time.sleep(random.uniform(2, 4))

print(f"\n{'='*50}")
print(f"✅ Terminé: {total} joueurs synchronisés")
print(f"✅ Clubs réussis: {successful_clubs}/{len(CLUBS)}")