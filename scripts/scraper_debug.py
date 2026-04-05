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

url = f"https://{PROJECT}.flashscore.ninja/46/x/feed/f_1_0_3_fr_1"
r = scraper.get(url, headers=FS_HEADERS, timeout=15)
feed = r.text

print("=== Recherche Algeria dans le feed ===")
keywords = ["algeria", "algerie", "algérie", "/algeria/", "alger", "kabylie", 
            "belouizdad", "ligue-professionnelle", "ligue professionnelle"]

for kw in keywords:
    if kw.lower() in feed.lower():
        idx = feed.lower().find(kw.lower())
        print(f"\n✅ '{kw}' trouvé!")
        print(feed[max(0,idx-200):idx+400])
        print("---")

# Format: ZA=compétition, ZL=URL, AA=matchID, CX=home, AF=away
# Chercher toutes les ligues dans le feed
print("\n=== Toutes les compétitions (ZL=URL) ===")
leagues = re.findall(r'ZL÷([^¬]+)', feed)
for l in leagues:
    if "alger" in l.lower():
        print(f"✅ ALGÉRIE: {l}")

# Chercher le tournoi Ligue 1 Algérie par son ID Flashscore
# On sait que sur SofaScore c'est 841 mais sur Flashscore c'est différent
print("\n=== URLs contenant 'alger' ===")
alger_urls = [l for l in leagues if "alger" in l.lower()]
print(f"Total: {len(alger_urls)}")
for u in alger_urls:
    print(" ", u)

# Afficher toutes les compétitions africaines
print("\n=== Compétitions africaines ===")
african = [(l, re.search(r'ZA÷([^¬]+)', feed[max(0,feed.find(l)-500):feed.find(l)])) 
           for l in leagues if any(x in l.lower() for x in ["africa", "algeria", "maroc", "tunisi", "egypt", "senegal", "ghana", "cameroun"])]
for url, za in african:
    name = za.group(1) if za else "?"
    print(f"  {name} → {url}")