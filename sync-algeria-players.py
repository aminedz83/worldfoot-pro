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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Connection": "keep-alive"
}

# 16 clubs Ligue 1 algérienne - IDs Soccerway confirmés
CLUBS = [
    ("JS Kabylie",      "kabylie",          "Wfaskwf0"),
    ("CR Belouizdad",   "belouizdad",       "vNJLB2jP"),
    ("MC Alger",        "mc-alger",         "tnY2Lfcp"),
    ("USM Alger",       "usm-alger",        "zXBidj5t"),
    ("CS Constantine",  "constantine",      "nBionu2l"),
    ("ES Setif",        "setif",            "EDgC6qYp"),
    ("MC Oran",         "oran",             "CrCmB35M"),
    ("ASO Chlef",       "chlef",            "Aobolc96"),
    ("JS Saoura",       "saoura",           "nimcBvel"),
    ("ES Ben Aknoun",   "es-ben-aknoun",    "QmvZvxCB"),
    ("USM Khenchela",   "khenchela",        "lYuJtBj9"),
    ("MB Rouissat",     "rouisset",         "hGHHy7Am"),
    ("Paradou AC",      "paradou",          "WIyffF3J"),
    ("ES Mostaganem",   "mostaganem",       "j9T7TM2E"),
    ("MC El Bayadh",    "el-bayadh",        "S6H5xCS1"),
    ("Olympique Akbou", "olympique-akbou",  "dhMQsMOh"),
]

pos_map = {
    "gardien": "G", "goalkeeper": "G", "portier": "G", "portiers": "G",
    "défenseur": "D", "defender": "D", "défenseurs": "D", "defence": "D",
    "milieu": "M", "midfielder": "M", "milieux": "M", "midfield": "M",
    "attaquant": "F", "forward": "F", "attaquants": "F", "striker": "F",
}

def scrape_squad(team_name, team_slug, team_sw_id):
    urls = [
        f"https://fr.soccerway.com/equipe/{team_slug}/{team_sw_id}/effectif/",
        f"https://int.soccerway.com/teams/algeria/{team_slug}/{team_sw_id}/squad/",
        f"https://ca.soccerway.com/teams/algeria/{team_slug}/{team_sw_id}/squad/",
    ]
    
    for url in urls:
        try:
            print(f"  Essai: {url}")
            r = requests.get(url, headers=HEADERS, timeout=20)
            print(f"  Status: {r.status_code}")
            if r.status_code != 200:
                continue
            
            soup = BeautifulSoup(r.text, "html.parser")
            players = []
            current_pos = ""
            
            for table in soup.find_all("table"):
                # Détecter position depuis heading précédent
                prev = table.find_previous(["h2", "h3", "h4"])
                if prev:
                    heading = prev.get_text(strip=True).lower()
                    for key, pos in pos_map.items():
                        if key in heading:
                            current_pos = pos
                            break
                
                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue
                    
                    # Chercher lien joueur
                    player_link = row.find("a", href=re.compile(r"/joueur/|/player/"))
                    if not player_link:
                        continue
                    
                    name = player_link.get_text(strip=True)
                    href = player_link.get("href", "")
                    
                    # ID Soccerway joueur
                    sw_id_match = re.search(r"/(?:joueur|player)/[^/]+/([^/]+)/", href)
                    sw_player_id = sw_id_match.group(1) if sw_id_match else None
                    
                    # Numéro maillot
                    number = cells[0].get_text(strip=True)
                    if not number.isdigit():
                        number = ""
                    
                    # Date de naissance
                    dob = None
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        m = re.search(r"(\d{2}/\d{2}/\d{4})", text)
                        if m:
                            try:
                                dob = datetime.strptime(m.group(1), "%d/%m/%Y").strftime("%Y-%m-%d")
                            except:
                                pass
                    
                    # Valeur marchande
                    market_value = None
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        m = re.search(r"(\d+(?:[.,]\d+)?)\s*([kKmM])", text)
                        if m:
                            try:
                                val = float(m.group(1).replace(",", "."))
                                suffix = m.group(2).lower()
                                if suffix == "k": val *= 1000
                                elif suffix == "m": val *= 1000000
                                market_value = int(val)
                            except:
                                pass
                    
                    # Photo
                    photo_url = None
                    img = row.find("img")
                    if img:
                        src = img.get("src", "")
                        if any(x in src for x in ["player", "joueur", "portrait", "person"]):
                            photo_url = src
                    
                    # Nationalité
                    nationality = ""
                    flag = row.find("img", src=re.compile(r"/flags/|/images/flags/"))
                    if flag:
                        nationality = flag.get("alt", "") or flag.get("title", "")
                    
                    if name and len(name) > 1:
                        players.append({
                            "name": name,
                            "number": number,
                            "position": current_pos,
                            "nationality": nationality,
                            "date_of_birth": dob,
                            "market_value": market_value,
                            "photo_url": photo_url,
                            "soccerway_url": "https://fr.soccerway.com" + href if href.startswith("/") else href,
                            "soccerway_player_id": sw_player_id
                        })
            
            if players:
                print(f"  → {len(players)} joueurs trouvés")
                return players
            else:
                print(f"  → 0 joueurs, essai suivant")
                
        except Exception as e:
            print(f"  Erreur: {e}")
            continue
    
    return []

def save_to_supabase(players, team_name):
    saved = 0
    for p in players:
        data = {
            "soccerway_name": p["name"],
            "team_name": team_name,
            "position": p.get("position", ""),
            "jersey_number": p.get("number", ""),
            "nationality": p.get("nationality", ""),
            "date_of_birth": p.get("date_of_birth") or None,
            "market_value": p.get("market_value"),
            "photo_url": p.get("photo_url"),
            "soccerway_url": p.get("soccerway_url"),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        res = requests.post(
            f"{SB_URL}/rest/v1/algeria_players_sw",
            headers=SB_HEADERS,
            json=data
        )
        if res.status_code in [200, 201]:
            saved += 1
        else:
            print(f"  Erreur save: {res.status_code} - {res.text[:100]}")
    return saved

# MAIN
print(f"=== Sync Algeria Players (Soccerway) - {datetime.now().strftime('%H:%M:%S')} ===")
print(f"Clubs: {len(CLUBS)}")

total = 0
for team_name, team_slug, team_sw_id in CLUBS:
    print(f"\n--- {team_name} ({team_sw_id}) ---")
    players = scrape_squad(team_name, team_slug, team_sw_id)
    if players:
        saved = save_to_supabase(players, team_name)
        total += saved
        print(f"  ✓ {saved}/{len(players)} sauvegardés")
    else:
        print(f"  ✗ Aucun joueur trouvé")
    time.sleep(2)

print(f"\n=== Terminé: {total} joueurs synchronisés ===")