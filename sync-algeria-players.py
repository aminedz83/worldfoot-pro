import requests
import os
import json
import time
import random
import re
from datetime import datetime, timezone

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# Session avec headers complets
session = requests.Session()

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
    """Génère des headers dynamiques pour éviter la détection"""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.sofascore.com/",
        "Origin": "https://www.sofascore.com",
        "Connection": "keep-alive",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }

def fetch_team_players_via_webpage(team_id, team_name):
    """Récupère les joueurs depuis la page web SofaScore (contourne l'API)"""
    url = f"https://www.sofascore.com/fr/equipe/{team_name.lower().replace(' ', '-')}/{team_id}"
    
    for attempt in range(3):
        try:
            # Nouveaux headers à chaque tentative
            headers = get_sofascore_headers()
            
            # D'abord récupérer la page HTML
            response = session.get(url, headers=headers, timeout=20)
            
            if response.status_code == 200:
                html = response.text
                
                # Chercher les données JSON dans la page
                # Pattern pour trouver __NUXT__ ou window.__INITIAL_STATE__
                patterns = [
                    r'<script id="__NUXT_DATA__" type="application/json">(.*?)</script>',
                    r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
                    r'window\.__NUXT__\s*=\s*({.*?});'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, html, re.DOTALL)
                    if match:
                        data = json.loads(match.group(1))
                        # Extraire les joueurs du JSON (structure complexe)
                        players = extract_players_from_nuxt(data)
                        if players:
                            print(f"✓ {team_name}: {len(players)} joueurs (via page web)")
                            return players
            
            print(f"⚠ Tentative {attempt+1}/3 échouée pour {team_name}")
            time.sleep(3)
            
        except Exception as e:
            print(f"⚠ Erreur {team_name}: {e}")
            time.sleep(3)
    
    return []

def extract_players_from_nuxt(data):
    """Extrait les joueurs du JSON Nuxt"""
    players = []
    
    def recursive_search(obj, depth=0):
        if depth > 10:
            return
        if isinstance(obj, dict):
            # Chercher les clés qui contiennent des données joueurs
            if 'players' in obj and isinstance(obj['players'], list):
                for p in obj['players']:
                    if isinstance(p, dict) and 'player' in p:
                        players.append(p)
            elif 'roster' in obj and isinstance(obj['roster'], list):
                for p in obj['roster']:
                    if isinstance(p, dict):
                        players.append({'player': p})
            
            # Chercher dans les sous-objets
            for value in obj.values():
                recursive_search(value, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                recursive_search(item, depth + 1)
    
    recursive_search(data)
    return players

def fetch_team_players_via_api_with_cookies(team_id, team_name):
    """Tente l'API avec cookies et session persistante"""
    # D'abord visiter la page d'accueil pour obtenir des cookies
    try:
        session.get("https://www.sofascore.com/", headers=get_sofascore_headers(), timeout=10)
        time.sleep(1)
    except:
        pass
    
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/players"
    
    for attempt in range(5):
        try:
            headers = get_sofascore_headers()
            # Ajouter un token aléatoire
            headers["X-Requested-With"] = "XMLHttpRequest"
            
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                players = data.get("players", [])
                if players:
                    print(f"✓ {team_name}: {len(players)} joueurs (API)")
                    return players
            elif response.status_code == 403:
                # Attendre plus longtemps à chaque tentative
                wait_time = (attempt + 1) * 5
                print(f"⚠ 403 pour {team_name}, attente {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"⚠ Status {response.status_code} pour {team_name}")
                time.sleep(2)
                
        except Exception as e:
            print(f"⚠ Erreur {team_name}: {e}")
            time.sleep(2)
    
    return []

def fetch_with_selenium_style(team_id, team_name):
    """Simule un navigateur avec plus de persistence"""
    # Utiliser une session complètement nouvelle
    new_session = requests.Session()
    
    # Ajouter des cookies communs
    new_session.cookies.set("device", "desktop")
    new_session.cookies.set("platform", "web")
    new_session.cookies.set("cf_clearance", "dummy", domain=".sofascore.com")  # placeholder
    
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/players"
    headers = get_sofascore_headers()
    
    try:
        response = new_session.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data.get("players", [])
    except:
        pass
    
    return []

def save_players(players, team_name, team_sofascore_id):
    """Sauvegarde les joueurs dans Supabase"""
    saved = 0
    
    for item in players:
        p = item.get("player", {})
        if not p.get("id"):
            continue
        
        dob = p.get("dateOfBirth")
        if dob and len(dob) > 10:
            dob = dob[:10]
        
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
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Nettoyer les None
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
        except:
            pass
    
    return saved

# Main execution
print("=== Sync Algeria Players depuis SofaScore ===")
print(f"Heure: {datetime.now().strftime('%H:%M:%S')}")
print(f"Clubs à synchroniser: {len(CLUBS)}")
print("Note: Tentative de contournement des blocages SofaScore...")
print()

total = 0

for idx, club in enumerate(CLUBS, 1):
    print(f"\n[{idx}/{len(CLUBS)}] --- {club['name']} ---")
    
    players = []
    
    # Stratégie 1: API avec cookies
    print("  Stratégie 1: API avec session...")
    players = fetch_team_players_via_api_with_cookies(club["sofascore_id"], club["name"])
    
    # Stratégie 2: Extraction depuis page web
    if not players:
        print("  Stratégie 2: Extraction page web...")
        players = fetch_team_players_via_webpage(club["sofascore_id"], club["name"])
    
    # Stratégie 3: Simulation navigateur
    if not players:
        print("  Stratégie 3: Simulation avancée...")
        players = fetch_with_selenium_style(club["sofascore_id"], club["name"])
    
    if players:
        saved = save_players(players, club["name"], club["sofascore_id"])
        total += saved
        print(f"  ✅ {saved} joueurs sauvegardés")
    else:
        print(f"  ❌ Échec total pour {club['name']}")
    
    # Pause entre les clubs
    time.sleep(random.uniform(3, 6))

print(f"\n{'='*50}")
print(f"✅ Terminé: {total} joueurs synchronisés depuis SofaScore")