import cloudscraper, re

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

PROJECT = "2043"
FS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://www.flashscore.ca/",
    "x-fsign": "SW9D1eZo",
}

# Match JS Saoura vs MC Alger
mid = "QHtxwqqe"
print(f"=== Feed df_sui pour {mid} ===")
r = scraper.get(f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_sui_1_{mid}_1_fr_1", headers=FS_HEADERS, timeout=10)
print(f"Status: {r.status_code} | Taille: {len(r.text)}")
print(r.text)

# Analyser tous les IE présents
print("\n=== Tous les types d'événements IE ===")
for block in r.text.split("~"):
    fields = {}
    for field in block.split("¬"):
        if "÷" in field:
            k, _, v = field.partition("÷")
            fields[k.strip()] = v.strip()
    if "IE" in fields:
        print(f"  IE={fields.get('IE')} | IB={fields.get('IB','')} | IF={fields.get('IF','')} | IM={fields.get('IM','')} | IV={fields.get('IV','')} | IK={fields.get('IK','')}")

# Aussi tester El Bayadh vs JSK qu'on sait qui a des événements
print(f"\n=== Feed df_sui pour IiwUv5Er (El Bayadh vs JSK) ===")
r2 = scraper.get(f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_sui_1/IiwUv5Er_1_fr_1", headers=FS_HEADERS, timeout=10)
print(f"Status: {r2.status_code} | Taille: {len(r2.text)}")
for block in r2.text.split("~"):
    fields = {}
    for field in block.split("¬"):
        if "÷" in field:
            k, _, v = field.partition("÷")
            fields[k.strip()] = v.strip()
    if "IE" in fields:
        print(f"  IE={fields.get('IE')} | IB={fields.get('IB','')} | IF={fields.get('IF','')} | IM={fields.get('IM','')} | IV={fields.get('IV','')} | IK={fields.get('IK','')}")