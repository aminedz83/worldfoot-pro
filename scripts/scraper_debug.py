import cloudscraper, re

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

mid = "IiwUv5Er"
PROJECT = "2043"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://fr.soccerway.com/",
    "x-fsign": "SW9D1eZo",
}

# Récupérer le feed lineups complet
url = f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_li_1_{mid}_1_fr_1"
r = scraper.get(url, headers=headers, timeout=10)
print("=== Feed Lineups Complet ===")
print("Taille:", len(r.text))
print(r.text)
print("\n=== Parsing ===")

# Parser le format ¬ 
# Format: KEY÷VALUE¬KEY÷VALUE~KEY÷VALUE
def parse_feed(text):
    players = []
    current = {}
    
    # Splitter par ~ (séparateur de joueurs) puis par ¬ (séparateur de champs)
    blocks = text.split("~")
    for block in blocks:
        if not block.strip():
            continue
        fields = {}
        for field in block.split("¬"):
            if "÷" in field:
                key, _, val = field.partition("÷")
                fields[key.strip()] = val.strip()
        if fields:
            players.append(fields)
    return players

entries = parse_feed(r.text)

print(f"Total entrées: {len(entries)}")
print("\nDétail:")
for e in entries:
    if "LI" in e:  # LI = nom joueur
        name = e.get("LI", "?")
        pos = e.get("LS", "?")
        num = e.get("LJ", "?")
        team = e.get("LH", "?")  # 0=dom, 1=ext
        player_id = e.get("LP", "?")
        side = "DOM" if team == "0" else "EXT"
        print(f"  [{side}] #{num} {name} ({pos}) | ID={player_id}")
    elif "LB" in e:
        print(f"\n--- {e.get('LB')} ---")