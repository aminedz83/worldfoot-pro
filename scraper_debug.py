import cloudscraper, re

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

mid = "IiwUv5Er"
PROJECT = "2043"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://fr.soccerway.com/",
    "x-fsign": "SW9D1eZo",
}

print("=== Recherche feed lineups ===")

# Tester tous les codes de feed possibles
feed_codes = [
    "df_sui",   # lineups ?
    "df_li",    # lineups ?
    "df_liom",  # lineups ?
    "df_fo",    # formation ?
    "df_line",  # lineups ?
    "dl_1",
    "dl_li",
    "di_1",
    "di_li",
    "dline",
    "df_ls",
    "df_lc",
    "df_la",
    "df_lb",
    "df_ld",
    "df_le",
    "df_lf",
    "df_lg",
    "df_lh",
    "df_lk",
    "df_ll",
    "df_lm",
    "df_ln",
    "df_lo",
    "df_lp",
    "df_lq",
    "df_lr",
    "df_lu",
    "df_lv",
    "df_lw",
]

for code in feed_codes:
    url = f"https://{PROJECT}.flashscore.ninja/46/x/feed/{code}_1_{mid}_1_fr_1"
    try:
        r = scraper.get(url, headers=headers, timeout=5)
        size = len(r.text)
        if r.status_code == 200 and size > 5:
            print(f"✅ {code}: Status={r.status_code} | Taille={size}")
            print(f"   Contenu: {r.text[:200]}")
        elif r.status_code != 200:
            print(f"❌ {code}: Status={r.status_code}")
    except Exception as e:
        print(f"  {code}: Erreur - {e}")

# Aussi tester sans le suffixe _1_fr_1
print("\n=== Sans suffixe ===")
for code in ["df_li", "df_sui", "df_liom", "df_fo", "dl_1", "di_1"]:
    url = f"https://{PROJECT}.flashscore.ninja/46/x/feed/{code}_{mid}"
    try:
        r = scraper.get(url, headers=headers, timeout=5)
        size = len(r.text)
        if r.status_code == 200 and size > 5:
            print(f"✅ {code}: Status={r.status_code} | Taille={size}")
            print(f"   Contenu: {r.text[:200]}")
    except:
        pass