import cloudscraper, re, json

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# D'abord extraire toutes les URLs d'API depuis le HTML du match
print("=== Extraction APIs internes Soccerway ===")
url = "https://fr.soccerway.com/match/el-bayadh-S6H5xCS1/kabylie-Wfaskwf0/?mid=IiwUv5Er"
r = scraper.get(url, timeout=20)
html = r.text

# Chercher toutes les URLs d'API dans le JS
api_patterns = [
    r'https?://[^"\']+/api/[^"\']+',
    r'https?://[^"\']+/lineups[^"\']*',
    r'https?://[^"\']+/lineup[^"\']*',
    r'/[^"\']+/lineups[^"\']*',
    r'ajax[^"\']*url[^"\']*:[^"\']*"([^"\']+)"',
    r'"url"\s*:\s*"([^"]+lineup[^"]*)"',
    r'fetch\(["\']([^"\']+)["\']',
    r'\.get\(["\']([^"\']+lineup[^"\']*)["\']',
]

print("APIs trouvées:")
found_apis = set()
for pat in api_patterns:
    for m in re.finditer(pat, html, re.IGNORECASE):
        api = m.group(1) if m.lastindex else m.group(0)
        if api not in found_apis:
            found_apis.add(api)
            print(" ", api[:100])

# Chercher le pattern de chargement des lineups
print("\n--- Pattern chargement data ---")
patterns_data = [
    r'IiwUv5Er[^}]{0,500}',
    r'event_id[^}]{0,300}',
    r'"lineup[^}]{0,500}',
    r'\/summary\/[^"\'<>\s]+',
    r'\/lineups\/[^"\'<>\s]+',
    r'data-[^=]+=.{0,50}IiwUv5Er',
]
for pat in patterns_data:
    m = re.search(pat, html, re.IGNORECASE)
    if m:
        print(f"\nPattern: {pat[:40]}")
        print(m.group(0)[:300])

# Tester l'API interne Soccerway connue
print("\n--- Test APIs internes Soccerway ---")
mid = "IiwUv5Er"
api_urls = [
    f"https://fr.soccerway.com/a/block/match-lineups?block_id=page_match_1_block_match_lineups_1&callback=loadBlockContent&match_id={mid}&format=json",
    f"https://fr.soccerway.com/a/block/match-lineups?match_id={mid}",
    f"https://fr.soccerway.com/match/el-bayadh-S6H5xCS1/kabylie-Wfaskwf0/lineups/",
    f"https://fr.soccerway.com/a/block/lineups?mid={mid}",
    f"https://fr.soccerway.com/summary/lineups/?mid={mid}",
    f"https://api.soccerway.com/lineups/{mid}",
]

for api_url in api_urls:
    try:
        r2 = scraper.get(api_url, timeout=10)
        print(f"\nURL: {api_url[:80]}")
        print(f"Status: {r2.status_code} | Taille: {len(r2.text)}")
        if r2.status_code == 200 and len(r2.text) > 100:
            print("Contenu:", r2.text[:300])
    except Exception as e:
        print(f"Erreur: {e}")