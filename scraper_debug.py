import requests
from datetime import date

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "x-fsign": "SW9D1eZo",  # Signature Flashscore publique
    "Referer": "https://www.flashscore.com/",
}

today = date.today()

# API Flashscore pour les matchs d'une compétition
# Tournament ID Ligue 1 Algérie sur Flashscore = algo à trouver
# Essayons plusieurs endpoints

urls = [
    # Endpoint matchs du jour par compétition
    "https://d.flashscore.com/x/feed/f_1_0_3_en_1",
    # API matchs Algérie
    "https://d.flashscore.com/x/feed/tr_1_ME_1_en_1",
    # Tournoi Ligue 1 Algérie (ID à trouver)
    "https://d.flashscore.com/x/feed/t_ME_186_en_1",
]

for url in urls:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        print(f"URL: {url}")
        print(f"Status: {r.status_code}")
        print(f"Content: {r.text[:500]}")
        print("---")
    except Exception as e:
        print(f"Erreur: {e}")

# Test API SofaScore pour Ligue 1 Algérie
print("\n=== SofaScore API ===")
sofa_url = "https://api.sofascore.com/api/v1/tournament/841/season/79568/events/round/25"
sofa_headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
    "Accept": "application/json",
}
try:
    r = requests.get(sofa_url, headers=sofa_headers, timeout=10)
    print("SofaScore status:", r.status_code)
    if r.status_code == 200:
        data = r.json()
        events = data.get("events", [])
        print("Matchs trouvés:", len(events))
        for e in events[:5]:
            home = e.get("homeTeam", {}).get("name", "?")
            away = e.get("awayTeam", {}).get("name", "?")
            ts = e.get("startTimestamp", 0)
            from datetime import datetime
            match_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            print(f"  {match_date} | {home} vs {away}")
except Exception as e:
    print("Erreur SofaScore:", e)