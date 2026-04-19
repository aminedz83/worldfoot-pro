#!/usr/bin/env python3
import cloudscraper
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# Tester plusieurs URLs possibles pour les coaches BeSoccer
urls = [
    "https://www.besoccer.com/team/staff/belouizdad/11507",
    "https://www.besoccer.com/team/squad/belouizdad/11507",
    "https://www.besoccer.com/team/belouizdad/11507",
    "https://www.besoccer.com/team/trainers/belouizdad/11507",
    "https://www.besoccer.com/team/coach/belouizdad/11507",
]

for url in urls:
    r = scraper.get(url, timeout=15)
    print(f"[{r.status_code}] {url}")
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, "html.parser")
        # Chercher liens vers staff/coach/entraineur
        coach_links = soup.select("a[href*='/coach/'], a[href*='/staff/'], a[href*='/trainer/']")
        print(f"  Coach links: {len(coach_links)}")
        for a in coach_links[:3]:
            print(f"    {a.get('href','')} → '{a.get_text(strip=True)[:40]}'")
        # Chercher le mot "coach" ou "staff" dans le texte
        text = soup.get_text(" ", strip=True).lower()
        if "coach" in text or "staff" in text or "entraineur" in text or "formateur" in text:
            print(f"  ✅ Contient coach/staff/formateur")
            # Sauver ce HTML
            with open("coaches_raw.html", "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"  HTML sauvé")
            # Afficher les titres
            for t in soup.find_all(["h1","h2","h3"]):
                print(f"  <{t.name}>: '{t.get_text(strip=True)[:80]}'")
            break
        else:
            print(f"  ❌ Pas de contenu coach")

# Aussi tester la page principale de l'équipe pour voir les liens disponibles
print("\n--- Liens nav depuis page principale ---")
r2 = scraper.get("https://www.besoccer.com/team/belouizdad", timeout=15)
print(f"[{r2.status_code}] page principale")
if r2.status_code == 200:
    soup2 = BeautifulSoup(r2.text, "html.parser")
    nav_links = soup2.select("nav a, div.team-nav a, ul.team-menu a, a[href*='belouizdad']")
    seen = set()
    for a in nav_links:
        href = a.get("href","")
        if href and href not in seen and "belouizdad" in href:
            seen.add(href)
            print(f"  {href} → '{a.get_text(strip=True)[:30]}'")