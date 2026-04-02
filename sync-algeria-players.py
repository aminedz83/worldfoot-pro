import requests
import os
import json
import time
import random
import sys
from datetime import datetime, timezone

# Installation automatique de cloudscraper si nécessaire
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
    print("✓ Cloudscraper chargé")
except ImportError:
    print("⚠ Installation de cloudscraper...")
    os.system('pip install -q cloudscraper')
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
    print("✓ Cloudscraper installé")

SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_KEY:
    print("❌ Erreur: SUPABASE_KEY non trouvée dans les variables d'environnement")
    sys.exit(1)

SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# 16 clubs de la Ligue 1 algérienne
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
    """
    Récupère les joueurs d'une équipe depuis l'API SofaScore
    Utilise cloudscraper pour contourner Cloudflare/Cloudfront
    """
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/players"
    
    # Créer un nouveau scraper pour chaque requête (évite la détection)
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True,
            'mobile': False
        }
    )
    
    # Headers réalistes
    headers = {
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
    
    for attempt in range(3):
        try:
            print(f"  Tentative {attempt + 1}/3...")
            response = scraper.get(url, headers=headers, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                players = data.get("players", [])
                if players:
                    print(f"  ✓ Récupéré {len(players)} joueurs")
                    return players
                else:
                    print(f"  ⚠ Aucun joueur trouvé")
                    return []
            elif response.status_code == 403:
                print(f"  ⚠ Erreur 403 (bloqué), tentative {attempt + 1}/3")
                time.sleep(3 * (attempt + 1))  # Attente croissante
            elif response.status_code == 429:
                print(f"  ⚠ Rate limit, attente 10s...")
                time.sleep(10)
            else:
                print(f"  ⚠ Erreur HTTP {response.status_code}")
                time.sleep(2)
                
        except requests.exceptions.Timeout:
            print(f"  ⚠ Timeout, tentative {attempt + 1}/3")
            time.sleep(3)
        except requests.exceptions.ConnectionError:
            print(f"  ⚠ Erreur connexion, tentative {attempt + 1}/3")
            time.sleep(3)
        except Exception as e:
            print(f"  ⚠ Erreur: {str(e)[:50]}")
            time.sleep(2)
    
    print(f"  ❌ Échec après 3 tentatives")
    return []

def save_players(players, team_name, team_sofascore_id):
    """
    Sauvegarde les joueurs dans Supabase
    """
    saved = 0
    errors = 0
    duplicates = 0
    
    for item in players:
        p = item.get("player", {})
        if not p.get("id"):
            continue
        
        # Nettoyer la date de naissance
        dob = p.get("dateOfBirth")
        if dob and len(dob) > 10:
            dob = dob[:10]
        
        # Récupérer la valeur marchande
        market_value = None
        if p.get("proposedMarketValueRaw"):
            market_value = p["proposedMarketValueRaw"].get("value")
        
        # Récupérer la date de fin de contrat
        contract_until = None
        if p.get("contractUntilTimestamp"):
            try:
                contract_until = datetime.fromtimestamp(
                    p["contractUntilTimestamp"],
                    tz=timezone.utc
                ).isoformat()
            except:
                pass
        
        # Préparer les données
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
            # Utiliser upsert pour éviter les doublons
            response = requests.post(
                f"{SB_URL}/rest/v1/algeria_players",
                headers=SB_HEADERS,
                json=data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                saved += 1
            elif response.status_code == 409:
                duplicates += 1
            else:
                errors += 1
                if errors <= 3:  # Limiter les logs d'erreur
                    print(f"    Erreur sauvegarde: {response.status_code}")
                    
        except Exception as e:
            errors += 1
    
    print(f"  → Sauvegardés: {saved} | Doublons: {duplicates} | Erreurs: {errors}")
    return saved

def test_connection():
    """
    Teste la connexion à Supabase et SofaScore
    """
    print("🔍 Test des connexions...")
    
    # Test Supabase
    try:
        test_data = {"test": True, "timestamp": datetime.now().isoformat()}
        response = requests.post(
            f"{SB_URL}/rest/v1/algeria_players",
            headers=SB_HEADERS,
            json=test_data,
            timeout=5
        )
        if response.status_code in [200, 201, 409]:
            print("  ✓ Supabase: OK")
        else:
            print(f"  ⚠ Supabase: Status {response.status_code}")
    except Exception as e:
        print(f"  ❌ Supabase: {e}")
        return False
    
    # Test SofaScore avec cloudscraper
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get("https://api.sofascore.com/api/v1/team/42204/players", timeout=10)
        if response.status_code == 200:
            print("  ✓ SofaScore: OK")
        else:
            print(f"  ⚠ SofaScore: Status {response.status_code}")
    except Exception as e:
        print(f"  ⚠ SofaScore: {e}")
    
    return True

# ==================== MAIN ====================

def main():
    print("=" * 60)
    print("   SYNC ALGERIA PLAYERS - SOFASCORE")
    print("=" * 60)
    print(f"Date/Heure: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Clubs à traiter: {len(CLUBS)}")
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Cloudscraper: {'OK' if CLOUDSCRAPER_AVAILABLE else 'NON'}")
    print("=" * 60)
    
    # Test de connexion
    test_connection()
    print()
    
    total_players = 0
    success_clubs = 0
    failed_clubs = []
    
    start_time = time.time()
    
    for idx, club in enumerate(CLUBS, 1):
        print(f"\n[{idx}/{len(CLUBS)}] --- {club['name']} (ID: {club['sofascore_id']}) ---")
        
        # Récupérer les joueurs
        players = fetch_team_players(club["sofascore_id"], club["name"])
        
        if players:
            # Sauvegarder les joueurs
            saved = save_players(players, club["name"], club["sofascore_id"])
            total_players += saved
            success_clubs += 1
        else:
            failed_clubs.append(club["name"])
            print(f"  ❌ Aucun joueur récupéré")
        
        # Pause entre les requêtes pour éviter le rate limiting
        if idx < len(CLUBS):
            delay = random.uniform(1.5, 3.5)
            time.sleep(delay)
    
    # Calcul du temps d'exécution
    elapsed_time = time.time() - start_time
    
    # Rapport final
    print("\n" + "=" * 60)
    print("   RAPPORT FINAL")
    print("=" * 60)
    print(f"✅ Joueurs synchronisés: {total_players}")
    print(f"✅ Clubs réussis: {success_clubs}/{len(CLUBS)}")
    print(f"⏱️  Temps d'exécution: {elapsed_time:.1f} secondes")
    
    if failed_clubs:
        print(f"\n⚠ Clubs en échec ({len(failed_clubs)}):")
        for club in failed_clubs[:10]:
            print(f"   - {club}")
        if len(failed_clubs) > 10:
            print(f"   ... et {len(failed_clubs) - 10} autres")
    
    print("\n" + "=" * 60)
    
    # Code de sortie
    if total_players == 0:
        print("❌ ERREUR: Aucun joueur synchronisé")
        sys.exit(1)
    else:
        print("✅ Synchronisation terminée avec succès")
        sys.exit(0)

if __name__ == "__main__":
    main()