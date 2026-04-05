import cloudscraper, re
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

ALGERIA_SW_IDS = [
    "Wfaskwf0", "vNJLB2jP", "tnY2Lfcp", "zXBidj5t",
    "nBionu2l", "EDgC6qYp", "CrCmB35M", "Aobolc96",
    "nimcBvel", "QmvZvxCB", "lYuJtBj9", "hGHHy7Am",
    "WIyffF3J", "j9T7TM2E", "S6H5xCS1", "dhMQsMOh",
]

# Test 1: Page du jour
print("=== Test page du jour ===")
url = "https://fr.soccerway.com/matches/2026/04/05/"
r = scraper.get(url, timeout=20)
print("Status:", r.status_code, "| Taille:", len(r.text))

# Chercher IDs algériens
found = [sw_id for sw_id in ALGERIA_SW_IDS if sw_id in r.text]
print("IDs algériens trouvés:", found)

# Tous les liens /match/
matches = re.findall(r'/match/[^"\'<>\s]+', r.text)
print("Total liens /match/:", len(matches))
for m in matches[:5]:
    print(" ", m)

# Test 2: Page Ligue 1 Algérie avec cloudscraper
print("\n=== Test Ligue 1 Algérie ===")
url2 = "https://fr.soccerway.com/national/algeria/ligue-professionnelle-1/2025-2026/regular-season/r76191/"
r2 = scraper.get(url2, timeout=20)
print("Status:", r2.status_code, "| Taille:", len(r2.text))

soup = BeautifulSoup(r2.text, "html.parser")
trs = soup.find_all("tr")
print("Nombre de <tr>:", len(trs))

# Chercher les classes des TR
classes = set()
for tr in trs:
    cls = tr.get("class", [])
    if cls:
        classes.add(" ".join(cls))
print("Classes TR:", classes)

# Chercher tous les liens de matchs
all_links = []
for a in soup.find_all("a", href=True):
    href = a.get("href", "")
    if "/match/" in href or re.search(r"/\d{5,8}/?$", href):
        all_links.append(href)
print("Liens matchs:", all_links[:10])

# Chercher kabylie dans le HTML
if "kabylie" in r2.text.lower():
    idx = r2.text.lower().find("kabylie")
    print("\nContexte Kabylie:")
    print(r2.text[max(0,idx-100):idx+200])