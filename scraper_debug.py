import requests, re
from bs4 import BeautifulSoup
from datetime import date

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": "https://fr.soccerway.com/"
}

url = "https://fr.soccerway.com/national/algeria/ligue-professionnelle-1/2025-2026/regular-season/r76191/"
r = requests.get(url, headers=HEADERS, timeout=20)
print("Status:", r.status_code)
print("Taille HTML:", len(r.text))

soup = BeautifulSoup(r.text, "html.parser")

# Afficher toutes les classes des <tr> trouvés
print("\n=== Classes des TR ===")
classes_found = set()
for tr in soup.find_all("tr"):
    cls = tr.get("class", [])
    if cls:
        classes_found.add(" ".join(cls))
for c in sorted(classes_found)[:30]:
    print(" ", c)

# Chercher tous les liens qui ressemblent à des matchs
print("\n=== Liens matchs ===")
for a in soup.find_all("a", href=True):
    href = a.get("href", "")
    if re.search(r"/\d{5,8}/?$", href) or "match" in href.lower():
        print(" ", href[:80])

# Afficher les 500 premiers chars du HTML pour voir la structure
print("\n=== Début HTML ===")
print(r.text[:2000])