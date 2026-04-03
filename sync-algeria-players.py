import requests, os, re, time
from datetime import datetime, timezone
from bs4 import BeautifulSoup

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-FR,fr;q=0.9"
}

def get_all_teams():
    """Récupère tous les clubs de Ligue 1 depuis la page fixtures"""
    url = "https://ca.soccerway.com/algeria/ligue-1/fixtures/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        teams = {}
        for link in soup.find_all("a", href=re.compile(r"/teams/")):
            href = link.get("href", "")
            name = link.get_text(strip=True)
            # Extraire slug et ID depuis l'URL
            # Format: /teams/algeria/js-kabylie/42202/
            m = re.search(r"/teams/[^/]+/([^/]+)/(\d+)/", href)
            if m and name and name not in teams:
                teams[name] = {
                    "name": name,
                    "slug": m.group(1),
                    "soccerway_id": m.group(2),
                    "url": "https://ca.soccerway.com" + href if href.startswith("/") else href
                }
        print(f"Clubs trouvés: {len(teams)}")
        return list(teams.values())
    except Exception as e:
        print(f"Erreur get_all_teams: {e}")
        return []

def get_squad_url(team_slug, team_id):
    """Construire l'URL de l'effectif Soccerway"""
    # Essayer les deux formats
    urls = [
        f"https://fr.soccerway.com/equipes/algerie/{team_slug}/{team_id}/effectif/",
        f"https://ca.soccerway.com/teams/algeria/{team_slug}/{team_id}/squad/",
        f"https://int.soccerway.com/teams/algeria/{team_slug}/{team_id}/squad/"
    ]
    return urls

def scrape_squad(team_name, team_slug, team_id):
    """Scrape l'effectif complet d'un club"""
    urls = get_squad_url(team_slug, team_id)
    
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            players = []
            
            # Position actuelle (GK, DEF, MID, FWD)
            current_pos = ""
            pos_map = {
                "gardien": "G", "goalkeeper": "G", "portier": "G",
                "défenseur": "D", "defender": "D", "défense": "D",
                "milieu": "M", "midfielder": "M", "milieux": "M",
                "attaquant": "F", "forward": "F", "attaque": "F",
                "striker": "F"
            }
            
            # Chercher les sections par position
            for section in soup.find_all(["h2", "h3", "th"]):
                text = section.get_text(strip=True).lower()
                for key, pos in pos_map.items():
                    if key in text:
                        current_pos = pos
                        break
            
            # Scraper les joueurs dans les tableaux
            for table in soup.find_all("table"):
                # Détecter la position depuis le contexte du tableau
                prev_heading = table.find_previous(["h2", "h3", "h4"])
                if prev_heading:
                    heading_text = prev_heading.get_text(strip=True).lower()
                    for key, pos in pos_map.items():
                        if key in heading_text:
                            current_pos = pos
                            break
                
                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue
                    
                    # Numéro de maillot
                    number = cells[0].get_text(strip=True) if cells else ""
                    
                    # Nom + lien joueur
                    name_cell = None
                    player_url = None
                    for cell in cells:
                        link = cell.find("a", href=re.compile(r"/joueur/|/player/"))
                        if link:
                            name_cell = link.get_text(strip=True)
                            href = link.get("href", "")
                            # Extraire l'ID du joueur depuis l'URL
                            # Format: /joueur/boudebouz-ryad/jVdly9DL/
                            id_match = re.search(r"/(?:joueur|player)/[^/]+/([^/]+)/", href)
                            if id_match:
                                player_url = href
                            break
                    
                    if not name_cell:
                        continue
                    
                    # Nationalité (drapeau)
                    nationality = ""
                    flag = row.find("img", src=re.compile(r"/flags/|/images/flags/"))
                    if flag:
                        alt = flag.get("alt", "") or flag.get("title", "")
                        nationality = alt
                    
                    # Date de naissance / Age
                    dob = None
                    age = None
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        dob_match = re.search(r"(\d{2}/\d{2}/\d{4})", text)
                        if dob_match:
                            try:
                                dob = datetime.strptime(dob_match.group(1), "%d/%m/%Y").strftime("%Y-%m-%d")
                            except:
                                pass
                    
                    # Valeur marchande
                    market_value = None
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        mv_match = re.search(r"€?\s*(\d+(?:[.,]\d+)?)\s*([kKmM]?)", text)
                        if mv_match and ("€" in text or "k" in text.lower() or "m" in text.lower()):
                            try:
                                val = float(mv_match.group(1).replace(",", "."))
                                suffix = mv_match.group(2).lower()
                                if suffix == "k":
                                    val *= 1000
                                elif suffix == "m":
                                    val *= 1000000
                                market_value = int(val)
                            except:
                                pass
                    
                    # Photo
                    photo_url = None
                    img = row.find("img", src=re.compile(r"/player/|/joueur/|portrait"))
                    if img:
                        photo_url = img.get("src", "")
                    
                    if name_cell and len(name_cell) > 1:
                        players.append({
                            "name": name_cell,
                            "number": number,
                            "position": current_pos,
                            "nationality": nationality,
                            "date_of_birth": dob,
                            "market_value": market_value,
                            "photo_url": photo_url,
                            "player_url": player_url,
                            "team_name": team_name
                        })
            
            if players:
                print(f"  {url} → {len(players)} joueurs")
                return players
                
        except Exception as e:
            print(f"  Erreur {url}: {e}")
            continue
    
    return []

def save_players_to_supabase(players, team_name):
    """Sauvegarde les joueurs dans Supabase"""
    saved = 0
    for p in players:
        # Utiliser nom+équipe comme clé unique
        data = {
            "soccerway_name": p["name"],
            "team_name": team_name,
            "position": p.get("position", ""),
            "jersey_number": p.get("number", ""),
            "nationality": p.get("nationality", ""),
            "date_of_birth": p.get("date_of_birth"),
            "market_value": p.get("market_value"),
            "photo_url": p.get("photo_url"),
            "soccerway_url": p.get("player_url"),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        res = requests.post(
            f"{SB_URL}/rest/v1/algeria_players_sw",
            headers=SB_HEADERS,
            json=data
        )
        if res.status_code in [200, 201]:
            saved += 1
    
    return saved

# MAIN
print(f"=== Sync Algeria Players (Soccerway) - {datetime.now().strftime('%H:%M:%S')} ===")

# Étape 1: Récupérer tous les clubs
teams = get_all_teams()
if not teams:
    print("Aucun club trouvé")
    exit(1)

# Étape 2: Scraper l'effectif de chaque club
total = 0
for team in teams:
    print(f"\n--- {team['name']} (ID: {team['soccerway_id']}) ---")
    players = scrape_squad(team["name"], team["slug"], team["soccerway_id"])
    if players:
        saved = save_players_to_supabase(players, team["name"])
        total += saved
        print(f"  → {saved}/{len(players)} sauvegardés")
    else:
        print(f"  → Aucun joueur trouvé")
    time.sleep(2)

print(f"\n=== Terminé: {total} joueurs synchronisés ===")
