#!/usr/bin/env python3
"""
Debug : trouve la structure de la page matchs BeSoccer Ligue 1
pour automatiser la découverte des IDs.
"""
import cloudscraper
from bs4 import BeautifulSoup
from datetime import date

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# Page matchs Ligue 1 Algérie sur BeSoccer
urls = [
    "https://www.besoccer.com/competition/matches/algeria-league-one",
    "https://www.besoccer.com/competition/calendar/algeria-league-one",
    f"https://www.besoccer.com/competition/matches/algeria-league-one/{date.today().year}",
]

for url in urls:
    r = scraper.get(url, timeout=15)
    print(f"[{r.status_code}] {url} | {len(r.text)} chars")
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Chercher les liens /match/
        match_links = soup.select("a[href*='/match/']")
        print(f"  Liens /match/ : {len(match_links)}")
        for a in match_links[:5]:
            print(f"    {a.get('href','')} → '{a.get_text(' ',strip=True)[:60]}'")
        
        # Chercher les liens avec les équipes algériennes
        for a in match_links[:10]:
            href = a.get("href","")
            if any(t in href for t in ["kabylie","belouizdad","alger","setif","oran","chlef","saoura"]):
                print(f"  ✅ MATCH ALGÉRIEN: {href}")
        
        # HTML brut premier match (500 chars)
        if match_links:
            parent = match_links[0].parent
            if parent:
                print(f"\n  HTML premier match:\n{parent.decode()[:500]}")
        break

with open("match_ids_raw.html", "w") as f:
    f.write(r.text)
print("\nHTML sauvé")