import cloudscraper, re, json

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

mid = "IiwUv5Er"

print("=== Test APIs Flashscore/Soccerway ===")

# Extraire les URLs d'API depuis le HTML
url = "https://fr.soccerway.com/match/el-bayadh-S6H5xCS1/kabylie-Wfaskwf0/?mid=IiwUv5Er"
r = scraper.get(url, timeout=20)
html = r.text

# Chercher les endpoints dans le JS
print("--- Endpoints dans le HTML ---")
endpoints = re.findall(r'["\']([^"\']*(?:lineup|squad|player|formation)[^"\']*)["\']', html, re.IGNORECASE)
for e in set(endpoints):
    if len(e) > 5 and len(e) < 200:
        print(" ", e[:100])

# Chercher les URLs de données
print("\n--- URLs de données ---")
data_urls = re.findall(r'["\']https?://[^"\']+["\']', html)
unique_data = set()
for u in data_urls:
    u = u.strip("\"'")
    if any(x in u for x in ["api", "data", "feed", "graphql", "json"]):
        unique_data.add(u)
for u in sorted(unique_data)[:20]:
    print(" ", u[:100])

# Tester l'API Flashscore directe (ds.lsapp.eu = datacenter Livesport)
print("\n--- Test API Livesport/Flashscore ---")
apis = [
    f"https://2043.ds.lsapp.eu/pq_graphql?_hash=el&category=football&event_id={mid}&tab=lineups",
    f"https://2043.ds.lsapp.eu/pq_graphql?_hash=el&event_id={mid}",
    f"https://2043.flashscore.ninja/46/x/feed/dc_1_{mid}",
    f"https://2043.flashscore.ninja/46/x/feed/df_st_1_{mid}",
    f"https://d.flashscore.com/x/feed/dc_1_{mid}",
    f"https://d.flashscore.com/x/feed/df_sui_{mid}_1_en_1",
]

headers_fs = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://fr.soccerway.com/",
    "x-fsign": "SW9D1eZo",
}

for api in apis:
    try:
        r2 = scraper.get(api, timeout=10)
        print(f"\n{api[:80]}")
        print(f"Status: {r2.status_code} | Taille: {len(r2.text)}")
        if r2.status_code == 200 and len(r2.text) > 50:
            print("Contenu:", r2.text[:400])
    except Exception as e:
        print(f"Erreur: {e}")