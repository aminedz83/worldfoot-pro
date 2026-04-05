import cloudscraper, re, json

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

mid = "IiwUv5Er"
TOKEN = "Y3uhIv5Ges46mMdAZm53akso95sYOogk"
SIGN = "SW9D1eZo"
PROJECT = "2043"

print("=== Test API Flashscore avec token ===")

# Headers avec token
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://fr.soccerway.com/",
    "x-fsign": SIGN,
    "Authorization": f"Bearer {TOKEN}",
}

# Test toutes les variantes d'API
apis = [
    # Flashscore ninja avec token
    f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_sui_{mid}_1_fr_1",
    f"https://{PROJECT}.flashscore.ninja/46/x/feed/dc_1_{mid}",
    f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_st_1_{mid}",
    f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_liom_1_{mid}_1_fr_1",
    # GraphQL GET
    f"https://{PROJECT}.ds.lsapp.eu/pq_graphql?_hash=el&event_id={mid}&sport=football&_token={TOKEN}",
    f"https://{PROJECT}.ds.lsapp.eu/pq_graphql?_hash=sui&event_id={mid}&_token={TOKEN}",
    # API directe avec token
    f"https://d.flashscore.com/x/feed/df_sui_{mid}_1_fr_1",
    f"https://d.flashscore.com/x/feed/dc_1_{mid}",
]

for api in apis:
    try:
        r = scraper.get(api, headers=headers, timeout=10)
        print(f"\n{api[:80]}")
        print(f"Status: {r.status_code} | Taille: {len(r.text)}")
        if r.status_code == 200 and len(r.text) > 5:
            print("Contenu:", r.text[:300])
    except Exception as e:
        print(f"Erreur: {e}")

# Chercher le JS qui charge les lineups pour trouver l'URL exacte
print("\n=== Chercher URL lineups dans le JS ===")
url_page = "https://fr.soccerway.com/match/el-bayadh-S6H5xCS1/kabylie-Wfaskwf0/?mid=IiwUv5Er"
r_page = scraper.get(url_page, timeout=20)

# Chercher les fichiers JS chargés
js_files = re.findall(r'src="(https://[^"]+\.js[^"]*)"', r_page.text)
print("Fichiers JS:", len(js_files))
for js in js_files[:5]:
    print(" ", js[:100])

# Télécharger le JS principal et chercher l'URL de lineups
for js_url in js_files[:3]:
    try:
        rjs = scraper.get(js_url, timeout=15)
        if "lineup" in rjs.text.lower() or "sui" in rjs.text:
            print(f"\nJS avec lineup: {js_url[:60]}")
            # Chercher le pattern d'URL
            urls_in_js = re.findall(r'["\']([^"\']*(?:lineup|sui|feed)[^"\']*)["\']', rjs.text)
            for u in urls_in_js[:10]:
                print(f"  {u[:100]}")
    except:
        pass