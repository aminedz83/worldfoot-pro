import cloudscraper, re
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# Test 1: Page match El Bayadh vs JSK
print("=== Test page match ===")
url = "https://fr.soccerway.com/match/el-bayadh-S6H5xCS1/kabylie-Wfaskwf0/?mid=IiwUv5Er"
r = scraper.get(url, timeout=20)
print("Status:", r.status_code, "| Taille:", len(r.text))

if r.status_code == 200:
    soup = BeautifulSoup(r.text, "html.parser")
    
    # Chercher lineups
    has_lineup = bool(soup.find(string=re.compile(r"STARTING LINEUP|TITULAIRES|Starting XI|XI de départ", re.I)))
    print("Lineups trouvés:", has_lineup)
    
    # Chercher les joueurs
    player_links = soup.find_all("a", href=re.compile(r"/joueur/|/players/"))
    print("Liens joueurs:", len(player_links))
    for p in player_links[:5]:
        print(" ", p.get_text(strip=True), "|", p.get("href","")[:50])
    
    # Chercher tables
    tables = soup.find_all("table")
    print("Tables:", len(tables))
    
    # Chercher TR
    trs = soup.find_all("tr")
    print("TR:", len(trs))
    
    # Afficher un bout du HTML
    print("\nHTML (2000 chars):")
    print(r.text[5000:7000])

# Test 2: URL lineups directe avec mid
print("\n=== Test lineups avec mid ===")
mid = "IiwUv5Er"
lineup_urls = [
    f"https://fr.soccerway.com/game/x/x/summary/lineups/?mid={mid}",
    f"https://fr.soccerway.com/match/el-bayadh-S6H5xCS1/kabylie-Wfaskwf0/lineups/?mid={mid}",
]
for url in lineup_urls:
    r2 = scraper.get(url, timeout=20)
    print(f"URL: {url}")
    print(f"Status: {r2.status_code} | Taille: {len(r2.text)}")
    if r2.status_code == 200:
        soup2 = BeautifulSoup(r2.text, "html.parser")
        trs = soup2.find_all("tr")
        print(f"TR: {len(trs)}")
        has_lineup = bool(soup2.find(string=re.compile(r"STARTING|TITULAIRES|Starting XI", re.I)))
        print(f"Lineup text: {has_lineup}")
    print()

# Test 3: Page ligue Algérie
print("=== Test page ligue ===")
url3 = "https://fr.soccerway.com/algerie/ligue-1/#/Iylbph6E/classements/global/"
r3 = scraper.get(url3, timeout=20)
print("Status:", r3.status_code, "| Taille:", len(r3.text))
soup3 = BeautifulSoup(r3.text, "html.parser")
trs3 = soup3.find_all("tr")
print("TR:", len(trs3))
# Chercher mid dans le HTML
mids = re.findall(r'mid=([A-Za-z0-9]{6,12})', r3.text)
print("MIDs trouvés:", mids[:10])