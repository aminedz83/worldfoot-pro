import cloudscraper, re

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

PROJECT = "2043"
FS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://fr.soccerway.com/",
    "x-fsign": "SW9D1eZo",
}

mid = "IiwUv5Er"

# Feed lineups complet
print("=== Feed df_li (lineups) ===")
r = scraper.get(f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_li_1_{mid}_1_fr_1", headers=FS_HEADERS, timeout=10)
print(r.text)

# Feed événements (buts, cartons)
print("\n=== Feed df_sui (événements) ===")
r2 = scraper.get(f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_sui_1_{mid}_1_fr_1", headers=FS_HEADERS, timeout=10)
print(r2.text)

# Chercher la formation dans les feeds
print("\n=== Analyse positions et formation ===")
feed = r.text
# Tous les champs uniques
all_keys = set()
for block in feed.split("~"):
    for field in block.split("¬"):
        if "÷" in field:
            key = field.split("÷")[0].strip()
            all_keys.add(key)
print("Clés disponibles:", sorted(all_keys))

# Afficher le contenu de LS (position) pour chaque joueur
print("\nPositions (LS):")
for block in feed.split("~"):
    fields = {}
    for field in block.split("¬"):
        if "÷" in field:
            k, _, v = field.partition("÷")
            fields[k.strip()] = v.strip()
    if "LI" in fields and "LS" in fields:
        print(f"  {fields['LI']} → LS={fields['LS']} | LR={fields.get('LR','')} | LK={fields.get('LK','')}")