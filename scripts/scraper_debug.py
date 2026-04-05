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

ALGERIA_SW_IDS = [
    "Wfaskwf0", "vNJLB2jP", "tnY2Lfcp", "zXBidj5t",
    "nBionu2l", "EDgC6qYp", "CrCmB35M", "Aobolc96",
    "nimcBvel", "QmvZvxCB", "lYuJtBj9", "hGHHy7Am",
    "WIyffF3J", "j9T7TM2E", "S6H5xCS1", "dhMQsMOh",
]

# Récupérer le feed du jour
print("=== Feed matchs du jour ===")
url = f"https://{PROJECT}.flashscore.ninja/46/x/feed/f_1_0_3_fr_1"
r = scraper.get(url, headers=FS_HEADERS, timeout=15)
print(f"Status: {r.status_code} | Taille: {len(r.text)}")

feed = r.text

# Chercher les IDs algériens
print("\n=== IDs algériens dans le feed ===")
for sw_id in ALGERIA_SW_IDS:
    if sw_id in feed:
        idx = feed.find(sw_id)
        context = feed[max(0,idx-300):idx+300]
        print(f"\n✅ Trouvé: {sw_id}")
        print(f"Contexte: {context}")

# Afficher les 2000 premiers chars pour comprendre le format
print("\n=== Format du feed (2000 chars) ===")
print(feed[:2000])

# Chercher "Algerie" ou "Algeria" dans le feed
print("\n=== Algérie dans le feed ===")
for keyword in ["Algerie", "Algeria", "algeri", "Ligue 1", "ligue-1"]:
    if keyword.lower() in feed.lower():
        idx = feed.lower().find(keyword.lower())
        print(f"✅ '{keyword}' trouvé!")
        print(feed[max(0,idx-100):idx+300])
        print("---")