import cloudscraper, re, json

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

url = "https://fr.soccerway.com/match/el-bayadh-S6H5xCS1/kabylie-Wfaskwf0/?mid=IiwUv5Er"
r = scraper.get(url, timeout=20)
html = r.text

# Chercher le token d'authentification
print("=== Tokens dans le HTML ===")
patterns = [
    r'"token"\s*:\s*"([^"]+)"',
    r'"auth"\s*:\s*"([^"]+)"',
    r'"key"\s*:\s*"([^"]+)"',
    r'x-fsign["\s:]+([^"\'<>\s]+)',
    r'"fsign"\s*:\s*"([^"]+)"',
    r'sign["\s:]+([A-Za-z0-9]{8,})',
    r'"_hash"\s*:\s*"([^"]+)"',
    r'hash["\s:]+([A-Za-z0-9]{4,20})',
    r'ninja[^"]{0,100}"([^"]{10,50})"',
    r'46/x/feed[^"]{0,50}"([^"]+)"',
    r'"sport_id"\s*:\s*(\d+)',
    r'"project_id"\s*:\s*(\d+)',
]

for pat in patterns:
    for m in re.finditer(pat, html, re.IGNORECASE):
        val = m.group(1)
        if len(val) > 3:
            print(f"  [{pat[:30]}] → {val[:80]}")

# Chercher spécifiquement dans window.environment
print("\n=== window.environment complet ===")
env_match = re.search(r'window\.environment\s*=\s*({.+?});\s*\n', html, re.DOTALL)
if env_match:
    try:
        env = json.loads(env_match.group(1))
        print(json.dumps(env, indent=2)[:3000])
    except:
        print(env_match.group(1)[:2000])

# Chercher l'URL ninja avec token
print("\n=== URLs ninja dans le HTML ===")
ninja_urls = re.findall(r'flashscore\.ninja[^"\'<>\s]+', html)
for u in ninja_urls[:10]:
    print(" ", u)

# Chercher le numéro du datacenter (2043)
print("\n=== Config datacenter ===")
dc_patterns = re.findall(r'2043[^"\'<>\s]{0,100}', html)
for d in dc_patterns[:5]:
    print(" ", d[:100])

# Tester l'API GraphQL correctement
print("\n=== Test GraphQL ===")
graphql_url = "https://2043.ds.lsapp.eu/pq_graphql"
# Requête pour les lineups
query = {
    "operationName": "MatchLineups",
    "query": """query MatchLineups($eventId: String!) {
        event(id: $eventId) {
            lineups { home { players { player { name } position } } away { players { player { name } position } } }
        }
    }""",
    "variables": {"eventId": "IiwUv5Er"}
}
try:
    r2 = scraper.post(graphql_url, json=query, timeout=10)
    print("GraphQL status:", r2.status_code)
    print("Réponse:", r2.text[:500])
except Exception as e:
    print("Erreur:", e)