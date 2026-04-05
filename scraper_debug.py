import cloudscraper, re
from bs4 import BeautifulSoup
from datetime import date, datetime

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

today = date.today()
today_str = today.strftime("%Y-%m-%d")
print("=== Test Soccerway avec cloudscraper ===")
print("Date:", today_str)

# Test 1: Page équipe JSK (comme valeurs marchandes)
# On sait que ça marche !
print("\n--- Page équipe JSK ---")
url_jsk = "https://fr.soccerway.com/equipe/js-kabylie/Wfaskwf0/"
r = scraper.get(url_jsk, timeout=20)
print("Status:", r.status_code, "| Taille:", len(r.text))

soup = BeautifulSoup(r.text, "html.parser")

# Chercher les matchs dans la page équipe
print("\nRecherche matchs dans page équipe...")
# Liens de matchs
match_links = []
for a in soup.find_all("a", href=True):
    href = a.get("href", "")
    # Format: /matches/2026/04/05/algeria/ligue-1/xxx/yyy/ID/
    if re.search(r"/matches/\d{4}/\d{2}/\d{2}/", href):
        match_links.append(href)

print("Liens matchs trouvés:", len(match_links))
for lnk in match_links[:10]:
    print(" ", lnk)

# Test 2: URL matches avec format pays/compétition
print("\n--- Page matches Algérie ---")
url_matches = f"https://fr.soccerway.com/matches/{today.strftime('%Y/%m/%d')}/algeria/"
r2 = scraper.get(url_matches, timeout=20)
print("Status:", r2.status_code, "| Taille:", len(r2.text))
if r2.status_code == 200:
    soup2 = BeautifulSoup(r2.text, "html.parser")
    links2 = [a.get("href","") for a in soup2.find_all("a", href=re.compile(r"/matches/\d{4}/\d{2}/\d{2}/"))]
    print("Liens matchs:", len(links2))
    for l in links2[:5]:
        print(" ", l)

# Test 3: URL directe d'un match connu (format ancien Soccerway)
print("\n--- Test URL match direct ---")
# Khenchela vs Paradou 05/04/2026
urls_to_try = [
    "https://fr.soccerway.com/matches/2026/04/05/algeria/ligue-professionnelle-1/usm-khenchela/paradou-ac/",
    "https://fr.soccerway.com/matches/2026/04/05/algeria/",
    "https://fr.soccerway.com/national/algeria/ligue-professionnelle-1/2025-2026/regular-season/r76191/matches/",
]
for url in urls_to_try:
    r3 = scraper.get(url, timeout=20)
    print(f"URL: {url}")
    print(f"Status: {r3.status_code} | Taille: {len(r3.text)}")
    if r3.status_code == 200 and len(r3.text) > 100000:
        soup3 = BeautifulSoup(r3.text, "html.parser")
        trs = soup3.find_all("tr")
        print(f"  TR trouvés: {len(trs)}")
        match_hrefs = [a.get("href","") for a in soup3.find_all("a", href=re.compile(r"/matches/\d{4}/\d{2}/\d{2}/"))]
        print(f"  Liens matchs: {len(match_hrefs)}")
        for h in match_hrefs[:3]:
            print(f"    {h}")
    print()