#!/usr/bin/env python3
import cloudscraper
from bs4 import BeautifulSoup
from datetime import date

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# Tester les URLs possibles avec fr. et slugs variés
urls = [
    "https://fr.besoccer.com/competition/matchs/algeria-league-one",
    "https://fr.besoccer.com/competition/matchs/ligue-1-algerienne",
    "https://fr.besoccer.com/competition/resultats/algeria-league-one",
    "https://fr.besoccer.com/competition/calendar/algeria-league-one",
    "https://www.besoccer.com/competition/matches/algeria-league-one-2026",
    "https://fr.besoccer.com/competition/algeria-league-one",
    # Depuis la page entraîneurs on sait que algeria-league-one existe
    # Essayons les onglets de cette compétition
    "https://fr.besoccer.com/competition/matchs/algeria-league-one/2026",
]

for url in urls:
    r = scraper.get(url, timeout=15)
    print(f"[{r.status_code}] {url}")
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, "html.parser")
        match_links = soup.select("a[href*='/match/']")
        print(f"  → {len(match_links)} liens /match/")
        for a in match_links[:3]:
            print(f"    {a.get('href','')[:80]}")
        # Chercher aussi les liens de navigation de la compétition
        nav = soup.select("a[href*='algeria-league-one']")
        for a in nav[:8]:
            print(f"  NAV: {a.get('href','')} → '{a.get_text(strip=True)[:30]}'")
        if match_links:
            with open("match_ids_raw.html", "w") as f:
                f.write(r.text)
            print("  HTML sauvé ✅")
            break

# Si rien trouvé, chercher via la page du club
print("\n--- Via page matchs d'un club ---")
url2 = "https://www.besoccer.com/team/matches/kabylie/11506/"
r2 = scraper.get(url2, timeout=15)
print(f"[{r2.status_code}] {url2}")
if r2.status_code == 200:
    soup2 = BeautifulSoup(r2.text, "html.parser")
    match_links2 = soup2.select("a[href*='/match/']")
    print(f"  → {len(match_links2)} liens /match/")
    for a in match_links2[:5]:
        href = a.get("href","")
        txt = a.get_text(" ", strip=True)[:50]
        print(f"    {href} → '{txt}'")