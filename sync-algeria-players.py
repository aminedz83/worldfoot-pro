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
SF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/"
}

# 16 clubs Ligue 1 algérienne
CLUBS = [
    {"name": "JS Kabylie",       "sf_id": 42202},
    {"name": "CR Belouizdad",    "sf_id": 42207},
    {"name": "MC Alger",         "sf_id": 42204},
    {"name": "USM Alger",        "sf_id": 42206},
    {"name": "CS Constantine",   "sf_id": 55393},
    {"name": "ES Setif",         "sf_id": 41756},
    {"name": "MC Oran",          "sf_id": 45001},
    {"name": "ASO Chlef",        "sf_id": 42201},
    {"name": "JS Saoura",        "sf_id": 79565},
    {"name": "ES Ben Aknoun",    "sf_id": 133444},
    {"name": "USM Khenchela",    "sf_id": 238384},
    {"name": "MB Rouissat",      "sf_id": 238383},
    {"name": "Paradou AC",       "sf_id": 212197},
    {"name": "ES Mostaganem",    "sf_id": 186100},
    {"name": "MC El Bayadh",     "sf_id": 133466},
    {"name": "Olympique Akbou",  "sf_id": 306567},
]

def get_team_players(sf_id, team_name):
    """Récupérer l'effectif d'un club depuis SofaScore API"""
    url = f"https://api.sofascore.com/api/v1/team/{sf_id}/players"
    try:
        r = requests.get(url, headers=SF_HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"  Erreur {r.status_code}")
            return []
        data = r.json()
        players = data.get("players", [])
        print(f"  {len(players)} joueurs trouvés")
        return players
    except Exception as e:
        print(f"  Erreur: {e}")
        return []

def build_sofascore_urls(players):
    """Construire les URLs SofaScore pour chaque joueur"""
    urls = []
    for item in players:
        p = item.get("player", {})
        if p.get("id") and p.get("slug"):
            url = f"https://www.sofascore.com/football/player/{p['slug']}/{p['id']}"
            urls.append({
                "url": url,
                "sf_id": p["id"],
                "name": p.get("name", ""),
                "slug": p.get("slug", "")
            })
    return urls

def run_apify_scraper(urls_batch):
    """Lancer le SofaScore Scraper PRO sur Apify"""
    start_urls = [{"url": u["url"]} for u in urls_batch]
    
    resp = requests.post(
        f"https://api.apify.com/v2/acts/azzouzana~sofascore-scraper-pro/runs?token={APIFY_TOKEN}",
        json={"startUrls": start_urls},
        timeout=30
    )
    print(f"  Apify status: {resp.status_code}")
    if resp.status_code not in [200, 201]:
        print(f"  Erreur Apify: {resp.text[:200]}")
        return None
    
    run_data = resp.json()
    run_id = run_data.get("data", {}).get("id")
    if not run_id:
        print(f"  Pas de run_id")
        return None
    
    print(f"  Run ID: {run_id}")
    
    # Attendre la fin du run
    for i in range(60):
        time.sleep(10)
        status_resp = requests.get(
            f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
        ).json()
        status = status_resp.get("data", {}).get("status", "UNKNOWN")
        print(f"  Status [{i+1}]: {status}")
        if status in ["SUCCEEDED", "FAILED", "ABORTED"]:
            break
    
    if status != "SUCCEEDED":
        print(f"  Run échoué: {status}")
        return None
    
    # Récupérer les résultats
    items = requests.get(
        f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items?token={APIFY_TOKEN}"
    ).json()
    
    print(f"  {len(items)} joueurs scrapés")
    return items

def save_players(items, team_name, sf_team_id, all_players_info):
    """Sauvegarder les joueurs dans Supabase"""
    saved = 0
    for item in items:
        data_field = item.get("data", {})
        if not data_field:
            continue
        
        sf_id = data_field.get("id")
        if not sf_id:
            continue
        
        # Trouver les infos supplémentaires
        player_info = next((p for p in all_players_info if p.get("sf_id") == sf_id), {})
        
        # Valeur marchande
        mv = None
        if data_field.get("proposedMarketValueRaw"):
            mv = data_field["proposedMarketValueRaw"].get("value")
        elif data_field.get("proposedMarketValue"):
            mv = data_field["proposedMarketValue"]
        
        # Date fin contrat
        contract_until = None
        if data_field.get("contractUntilTimestamp"):
            contract_until = datetime.fromtimestamp(
                data_field["contractUntilTimestamp"], tz=timezone.utc
            ).isoformat()
        
        # Photo URL
        photo_url = f"https://api.sofascore.com/api/v1/player/{sf_id}/image"
        
        # Position
        position = data_field.get("position", "")
        pos_map = {"G": "G", "D": "D", "M": "M", "F": "F",
                   "Goalkeeper": "G", "Defender": "D", "Midfielder": "M", "Forward": "F"}
        position = pos_map.get(position, position)

        data = {
            "sofascore_id": sf_id,
            "soccerway_name": data_field.get("name", ""),
            "short_name": data_field.get("shortName", ""),
            "slug": data_field.get("slug", ""),
            "team_name": team_name,
            "sofascore_team_id": sf_team_id,
            "position": position,
            "jersey_number": str(data_field.get("shirtNumber", "") or ""),
            "nationality": data_field.get("country", {}).get("name", "") if data_field.get("country") else "",
            "market_value": mv,
            "contract_until": contract_until,
            "photo_url": photo_url,
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
            print(f"  Erreur save {data['soccerway_name']}: {res.status_code}")
    
    return saved

# MAIN
print(f"=== Sync Algeria Players via SofaScore + Apify ===")
print(f"Heure: {datetime.now().strftime('%H:%M:%S')}")

total = 0
for club in CLUBS:
    print(f"\n--- {club['name']} (SF ID: {club['sf_id']}) ---")
    
    # 1. Récupérer l'effectif depuis SofaScore API
    players = get_team_players(club["sf_id"], club["name"])
    if not players:
        print(f"  Aucun joueur - on passe")
        continue
    
    # 2. Construire les URLs
    urls_info = build_sofascore_urls(players)
    print(f"  {len(urls_info)} URLs construites")
    
    # 3. Lancer Apify par batch de 20
    batch_size = 20
    all_items = []
    for i in range(0, len(urls_info), batch_size):
        batch = urls_info[i:i+batch_size]
        print(f"  Batch {i//batch_size + 1}: {len(batch)} joueurs")
        items = run_apify_scraper(batch)
        if items:
            all_items.extend(items)
        time.sleep(2)
    
    # 4. Sauvegarder dans Supabase
    if all_items:
        saved = save_players(all_items, club["name"], club["sf_id"], urls_info)
        total += saved
        print(f"  ✓ {saved}/{len(all_items)} sauvegardés")
    
    time.sleep(3)

print(f"\n=== Terminé: {total} joueurs synchronisés ===")