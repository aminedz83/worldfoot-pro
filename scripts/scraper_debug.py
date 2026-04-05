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

# Joueurs connus avec leurs IDs
players = [
    ("Boudebouz R.", "jVdly9DL", "/player/boudebouz-ryad/jVdly9DL/"),
    ("Merbah G.", "tb5oS4uU", "/player/merbah-gaya/tb5oS4uU/"),
    ("Barkat A.", "babSxJzC", "/player/barkat-abdelilah/babSxJzC/"),
]

print("=== Test photos joueurs Flashscore ===")

# Format 1: image directe avec ID
for name, pid, url_path in players:
    photo_urls = [
        f"https://static.flashscore.com/res/image/data/{pid}.png",
        f"https://static.flashscore.com/res/image/data/{pid[:8]}.png",
        f"https://images.flashscore.com/res/image/data/{pid}.png",
    ]
    print(f"\n{name} (ID={pid})")
    for photo_url in photo_urls:
        r = scraper.get(photo_url, timeout=5)
        print(f"  {photo_url[-40:]}: {r.status_code} | {len(r.content)} bytes")

# Format 2: Page joueur Soccerway → chercher l'image
print("\n=== Page joueur Soccerway ===")
r2 = scraper.get("https://fr.soccerway.com/player/boudebouz-ryad/jVdly9DL/", timeout=15)
print(f"Status: {r2.status_code} | Taille: {len(r2.text)}")
if r2.status_code == 200:
    # Chercher l'image du joueur
    img_patterns = [
        r'<img[^>]+src="([^"]+(?:player|avatar|photo)[^"]*)"',
        r'"image"\s*:\s*"([^"]+)"',
        r'player[^"]*\.(?:jpg|png|webp)',
        r'OA÷([A-Za-z0-9_-]+\.(?:png|jpg))',
    ]
    for pat in img_patterns:
        m = re.search(pat, r2.text, re.IGNORECASE)
        if m:
            print(f"  Image trouvée: {m.group(1)[:100]}")

# Format 3: Feed joueur Flashscore
print("\n=== Feed joueur Flashscore ===")
for name, pid, _ in players:
    url = f"https://{PROJECT}.flashscore.ninja/46/x/feed/dp_1_{pid}_1_fr_1"
    r3 = scraper.get(url, headers=FS_HEADERS, timeout=5)
    print(f"\n{name}: status={r3.status_code} | taille={len(r3.text)}")
    if r3.status_code == 200 and len(r3.text) > 5:
        print(f"  Contenu: {r3.text[:300]}")
        # Chercher image dans le feed
        imgs = re.findall(r'[A-Za-z0-9_/-]+\.(?:png|jpg|webp)', r3.text)
        for img in imgs[:5]:
            print(f"  Image: {img}")