import cloudscraper, re, json
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

print("=== Analyse HTML page match ===")
url = "https://fr.soccerway.com/match/el-bayadh-S6H5xCS1/kabylie-Wfaskwf0/?mid=IiwUv5Er"
r = scraper.get(url, timeout=20)
print("Status:", r.status_code, "| Taille:", len(r.text))

html = r.text

# Chercher les données JSON dans les scripts
print("\n--- JSON dans les scripts ---")
# Souvent les données sont dans window.__INITIAL_STATE__ ou similar
patterns = [
    r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
    r'window\.__data__\s*=\s*({.+?});',
    r'"lineups"\s*:\s*(\{.+?\})',
    r'"startXI"\s*:\s*(\[.+?\])',
    r'"players"\s*:\s*(\[.+?\])',
    r'STARTING LINEUP(.{0,2000})',
]

for pat in patterns:
    m = re.search(pat, html, re.DOTALL)
    if m:
        print(f"\nPattern trouvé: {pat[:40]}")
        print(m.group(0)[:500])

# Chercher tous les noms de joueurs algériens connus
print("\n--- Noms joueurs dans HTML ---")
players_to_find = ["Merbah", "Hadid", "Mahious", "Boudebouz", "Benchaa", "Nechat", "Bada"]
for name in players_to_find:
    if name.lower() in html.lower():
        idx = html.lower().find(name.lower())
        print(f"✅ {name} trouvé! Contexte:")
        print(html[max(0,idx-100):idx+200])
        print("---")

# Chercher les scripts avec données
print("\n--- Scripts avec données joueurs ---")
soup = BeautifulSoup(html, "html.parser")
for script in soup.find_all("script"):
    src = script.get("src", "")
    content = script.string or ""
    if "lineup" in content.lower() or "player" in content.lower() or "merbah" in content.lower():
        print("Script trouvé!")
        print(content[:1000])
        print("---")

# Chercher dans le HTML brut autour de "STARTING"
print("\n--- Contexte autour de STARTING LINEUP ---")
idx = html.find("STARTING LINEUP")
if idx > 0:
    print(html[max(0,idx-200):idx+1000])