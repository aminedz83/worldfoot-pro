import cloudscraper
from bs4 import BeautifulSoup
import re

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# Test 1 — page effectif JSK
print("=== Test page effectif JSK ===")
url = "https://fr.soccerway.com/equipe/kabylie/Wfaskwf0/"
r = scraper.get(url, timeout=20)
print(f"Status: {r.status_code}, Size: {len(r.text)}")
soup = BeautifulSoup(r.text, "html.parser")
player_links = soup.find_all("a", href=re.compile(r"/joueur/"))
print(f"Liens joueurs: {len(player_links)}")
for lnk in player_links[:5]:
    print(f"  {lnk.get('href')} — {lnk.get_text(strip=True)}")

# Test 2 — page joueur Hadid
print("\n=== Test page joueur Hadid ===")
r2 = scraper.get("https://fr.soccerway.com/joueur/hadid-mohamed-idir/As8Cxr8H/", timeout=20)
print(f"Status: {r2.status_code}, Size: {len(r2.text)}")

# Chercher valeur marchande et contrat
soup2 = BeautifulSoup(r2.text, "html.parser")
# Soccerway affiche la MV dans un span ou div spécifique
for tag in soup2.find_all(string=re.compile(r'[Vv]aleur|[Mm]arché|[Mm]arket')):
    print(f"Tag MV: {tag.parent}")

# Chercher directement dans le texte
mv_patterns = [
    r'€\s*[\d,.]+\s*[kKmM]?',
    r'[\d,.]+\s*[kKmM]?\s*€',
    r'309',  # valeur connue de Hadid
]
for pat in mv_patterns:
    m = re.search(pat, r2.text)
    if m:
        start = max(0, m.start()-50)
        print(f"Pattern '{pat}': ...{r2.text[start:m.end()+50]}...")
        break

print(f"\nSample 2000-2500: {r2.text[2000:2500]}")