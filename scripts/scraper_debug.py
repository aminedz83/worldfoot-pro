import cloudscraper, re
from datetime import date

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

PROJECT = "2043"
FS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://fr.soccerway.com/",
    "x-fsign": "SW9D1eZo",
}

today = date.today().strftime("%Y-%m-%d")
print("Date:", today)

# Depuis l'URL du match El Bayadh vs JSK on sait que:
# - tournament ID Flashscore = Iylbph6E (depuis l'URL ligue)
# https://fr.soccerway.com/algerie/ligue-1/#/Iylbph6E/classements/global/

TOURNAMENT_ID = "Iylbph6E"  # ID Flashscore Ligue 1 Algérie !

print(f"\n=== Test feeds avec tournament ID {TOURNAMENT_ID} ===")

feed_urls = [
    f"https://{PROJECT}.flashscore.ninja/46/x/feed/f_1_{TOURNAMENT_ID}_3_fr_1",
    f"https://{PROJECT}.flashscore.ninja/46/x/feed/f_1_{TOURNAMENT_ID}_0_fr_1",
    f"https://{PROJECT}.flashscore.ninja/46/x/feed/t_{TOURNAMENT_ID}_fr_1",
    f"https://{PROJECT}.flashscore.ninja/46/x/feed/to_{TOURNAMENT_ID}_fr_1",
    f"https://{PROJECT}.flashscore.ninja/46/x/feed/ls_{TOURNAMENT_ID}_3_fr_1",
    f"https://{PROJECT}.flashscore.ninja/46/x/feed/f_1_{TOURNAMENT_ID}_3_en_1",
]

for url in feed_urls:
    try:
        r = scraper.get(url, headers=FS_HEADERS, timeout=10)
        print(f"\n{url[-50:]}")
        print(f"Status: {r.status_code} | Taille: {len(r.text)}")
        if r.status_code == 200 and len(r.text) > 5:
            print(f"Contenu: {r.text[:400]}")
    except Exception as e:
        print(f"Erreur: {e}")

# Aussi chercher l'ID numérique de la ligue depuis l'URL du match
# El Bayadh vs JSK: /match/el-bayadh-S6H5xCS1/kabylie-Wfaskwf0/?mid=IiwUv5Er
# Récupérer la page du match et extraire l'ID du tournoi
print("\n=== Extraction ID tournoi depuis page match ===")
url_match = "https://fr.soccerway.com/match/el-bayadh-S6H5xCS1/kabylie-Wfaskwf0/?mid=IiwUv5Er"
r = scraper.get(url_match, timeout=20)
html = r.text

# Chercher l'ID du tournoi dans le JS
patterns = [
    r'"tournament_id"\s*:\s*"([^"]+)"',
    r'"tournamentId"\s*:\s*"([^"]+)"',
    r'Iylbph6E',  # ID qu'on a dans l'URL
    r'"league_id"\s*:\s*"([^"]+)"',
    r'ZEE÷([A-Za-z0-9]+)',
    r'/football/algeria/[^"\'<>\s]+',
]

for pat in patterns:
    for m in re.finditer(pat, html):
        val = m.group(1) if m.lastindex else m.group(0)
        if len(val) > 3 and len(val) < 50:
            print(f"  [{pat[:30]}] → {val}")