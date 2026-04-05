import cloudscraper, re
from datetime import date

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

FS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://www.flashscore.ca/",
    "x-fsign": "SW9D1eZo",
}

today = date.today().strftime("%Y-%m-%d")

# Test 1: Page calendrier Soccerway
print("=== Test Soccerway calendrier ===")
r1 = scraper.get("https://fr.soccerway.com/algerie/ligue-1/calendrier/", timeout=20)
print(f"Status: {r1.status_code} | Taille: {len(r1.text)}")
mids1 = re.findall(r'mid=([A-Za-z0-9]{6,12})', r1.text)
print(f"MIDs trouvés: {len(mids1)}")
for m in mids1[:10]:
    print(f"  {m}")

# Test 2: Page Flashscore fixtures
print("\n=== Test Flashscore fixtures ===")
r2 = scraper.get("https://www.flashscore.ca/soccer/algeria/ligue-1/fixtures/", timeout=20)
print(f"Status: {r2.status_code} | Taille: {len(r2.text)}")

# Chercher les MIDs dans Flashscore
mids2 = re.findall(r'AA÷([A-Za-z0-9]{8})', r2.text)
print(f"MIDs (AA÷) trouvés: {len(mids2)}")
for m in mids2[:10]:
    print(f"  {m}")

# Chercher dans le HTML brut
print("\n--- Contenu Flashscore (3000 chars) ---")
print(r2.text[1000:4000])

# Test 3: API Flashscore Canada avec tournament ID
print("\n=== Test feed Flashscore CA ===")
PROJECT_CA = "2035"  # Project ID pour Canada
for proj in ["2035", "2021", "2043", "2025"]:
    url = f"https://{proj}.flashscore.ninja/46/x/feed/f_1_Iylbph6E_4_en_1"
    try:
        r3 = scraper.get(url, headers=FS_HEADERS, timeout=10)
        if r3.status_code == 200 and len(r3.text) > 5:
            print(f"\n✅ Project {proj}: {len(r3.text)} bytes")
            print(r3.text[:500])
        else:
            print(f"Project {proj}: {r3.status_code} | {len(r3.text)}")
    except Exception as e:
        print(f"Project {proj}: Erreur - {e}")