import requests
import os
import json
import time
import random
from datetime import datetime, timezone

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# Headers SofaScore améliorés (version desktop complète)
SF_HEADERS = {
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

# Session avec cookies persistants
session = requests.Session()
session.headers.update(SF_HEADERS)

# Ajouter un cookie de session (optionnel mais aide parfois)
session.cookies.set("device", "desktop")
session.cookies.set("platform", "web")

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

def fetch_team_players(team_id, team_name):
    """Récupère les joueurs d'une équipe avec retry et backoff exponentiel"""
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/players"
    
    for attempt in range(5):  # 5 tentatives max
        try:
            # Délai progressif entre les tentatives
            if attempt > 0:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"  Attente {wait_time:.1f}s avant tentative {attempt+1}...")
                time.sleep(wait_time)
            
            # Nouvelle session à chaque tentative
            if attempt > 0:
                new_session = requests.Session()
                new_session.headers.update(SF_HEADERS)
                response = new_session.get(url, timeout=20, allow_redirects=True)
            else:
                response = session.get(url, timeout=20, allow_redirects=True)
            
            if response.status_code == 200:
                data = response.json()
                players = data.get("players", [])
                print(f"✓ {team_name}: {len(players)} joueurs récupérés")
                return players
            
            elif response.status_code == 403:
                print(f"⚠ Erreur 403 pour {team_name} (tentative {attempt+1}/5)")
                # En cas de 403, on attend plus longtemps
                time.sleep(5)
                
            elif response.status_code == 429:
                print(f"⚠ Rate limit pour {team_name}, pause plus longue...")
                time.sleep(15)
                
            else:
                print(f"⚠ Erreur {response.status_code} pour {team_name} (tentative {attempt+1}/5)")
                time.sleep(3)
                
        except requests.exceptions.Timeout:
            print(f"⚠ Timeout pour {team_name} (tentative {attempt+1}/5)")
            time.sleep(3)
        except requests.exceptions.ConnectionError:
            print(f"⚠ Erreur connexion pour {team_name} (tentative {attempt+1}/5)")
            time.sleep(5)
        except Exception as e:
            print(f"⚠ Erreur {team_name}: {str(e)[:50]} (tentative {attempt+1}/5)")
            time.sleep(3)
    
    print(f"✗ Échec pour {team_name} après 5 tentatives")
    return []

def fetch_team_players_alternative(team_name):
    """Alternative: utilise l'API publique de TheSportsDB (gratuite, pas de blocage)"""
    try:
        # TheSportsDB API (gratuite, sans clé pour les recherches basiques)
        url = f"https://www.thesportsdb.com/api/v1/json/3/searchplayers.php?t={team_name.replace(' ', '%20')}"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            players = data.get("player", [])
            if players:
                print(f"✓ {team_name} (TheSportsDB): {len(players)} joueurs")
                # Convertir au format attendu
                formatted_players = []
                for p in players:
                    formatted_players.append({
                        "player": {
                            "id": int(p.get("idPlayer", 0)),
                            "name": p.get("strPlayer", ""),
                            "shortName": p.get("strPlayer", "").split()[-1] if p.get("strPlayer") else "",
                            "slug": p.get("strPlayer", "").lower().replace(" ", "-"),
                            "position": p.get("strPosition", ""),
                            "jerseyNumber": p.get("strNumber", ""),
                            "dateOfBirth": p.get("dateBorn", ""),
                            "height": p.get("strHeight", ""),
                            "preferredFoot": p.get("strPreferredFoot", ""),
                            "country": {"name": p.get("strNationality", "")},
                            "proposedMarketValueRaw": None,
                            "contractUntilTimestamp": None
                        }
                    })
                return formatted_players
    except Exception as e:
        print(f"  Alternative échouée pour {team_name}: {e}")
    
    return []

def save_players(players, team_name, team_sofascore_id):
    """Sauvegarde les joueurs dans Supabase"""
    saved = 0
    errors = 0
    
    for item in players:
        p = item.get("player", {})
        if not p.get("id"):
            continue
        
        # Nettoyer les données
        dob = p.get("dateOfBirth")
        if dob and len(dob) > 10:
            dob = dob[:10]  # Garder seulement YYYY-MM-DD
        
        contract_until = None
        if p.get("contractUntilTimestamp"):
            try:
                contract_until = datetime.fromtimestamp(
                    p["contractUntilTimestamp"],
                    tz=timezone.utc
                ).isoformat()
            except:
                pass
        
        # Gérer la valeur marchande
        market_value = None
        if p.get("proposedMarketValueRaw"):
            market_value = p["proposedMarketValueRaw"].get("value")
        
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
        
        # Supprimer les champs None
        data = {k: v for k, v in data.items() if v is not None}
        
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
                if errors < 5:  # Ne pas spammer les logs
                    print(f"    Erreur save: {res.status_code}")
        except Exception as e:
            errors += 1
    
    print(f"  → {saved} sauvegardés, {errors} erreurs")
    return saved

def test_sofascore_connection():
    """Test si l'API SofaScore est accessible"""
    test_url = "https://api.sofascore.com/api/v1/team/42204/players"
    try:
        r = session.get(test_url, timeout=10)
        print(f"Test connexion SofaScore: Status {r.status_code}")
        if r.status_code == 200:
            print("✓ API SofaScore accessible")
            return True
        else:
            print("✗ API SofaScore bloquée, utilisation alternative...")
            return False
    except:
        print("✗ Impossible de contacter SofaScore")
        return False

# Main execution
print("=== Sync Algeria Players ===")
print(f"Heure: {datetime.now().strftime('%H:%M:%S')}")
print(f"Clubs à synchroniser: {len(CLUBS)}")
print()

# Test de connexion
sofascore_available = test_sofascore_connection()
print()

total = 0
failed_clubs = []

for idx, club in enumerate(CLUBS, 1):
    print(f"\n[{idx}/{len(CLUBS)}] --- {club['name']} ---")
    
    players = []
    
    # Essayer SofaScore d'abord si disponible
    if sofascore_available:
        players = fetch_team_players(club["sofascore_id"], club["name"])
    
    # Si SofaScore échoue, utiliser l'alternative
    if not players:
        print(f"  Utilisation de l'API alternative...")
        players = fetch_team_players_alternative(club["name"])
    
    if players:
        saved = save_players(players, club["name"], club["sofascore_id"])
        total += saved
    else:
        failed_clubs.append(club["name"])
        print(f"  ✗ Aucun joueur récupéré")
    
    # Délai variable pour éviter la détection
    delay = random.uniform(2, 5)
    if idx < len(CLUBS):
        time.sleep(delay)

# Rapport final
print("\n" + "="*50)
print(f"✓ Terminé: {total} joueurs synchronisés")
if failed_clubs:
    print(f"⚠ Échec pour {len(failed_clubs)} clubs:")
    for club in failed_clubs[:5]:  # Limiter l'affichage
        print(f"  - {club}")
    if len(failed_clubs) > 5:
        print(f"  ... et {len(failed_clubs)-5} autres")