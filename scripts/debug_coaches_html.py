#!/usr/bin/env python3
import cloudscraper
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# Page formateurs CR Belouizdad
url = "https://www.besoccer.com/team/coaches/belouizdad/11507"
print(f"Fetch: {url}")
r = scraper.get(url, timeout=20)
print(f"Status: {r.status_code} | Size: {len(r.text)} chars")

soup = BeautifulSoup(r.text, "html.parser")

print("\n--- TITRES ---")
for t in soup.find_all(["h1","h2","h3"]):
    print(f"  <{t.name}>: '{t.get_text(strip=True)[:80]}'")

print("\n--- LIENS /coach/ ou /staff/ ---")
for a in soup.select("a[href*='/coach/'], a[href*='/staff/']")[:10]:
    print(f"  {a.get('href','')} → '{a.get_text(strip=True)[:50]}'")

print("\n--- CLASSES li ---")
li_cls = list(set([" ".join(l.get("class",[])) for l in soup.find_all("li") if l.get("class")]))
for c in li_cls[:15]:
    print(f"  '{c}'")

print("\n--- HTML brut premier ul avec coach (600 chars) ---")
for ul in soup.find_all("ul"):
    if ul.select("li") and any("coach" in str(li).lower() or "formateur" in str(li).lower() for li in ul.select("li")):
        print(ul.decode()[:800])
        break

# Chercher entraîneur actuel
print("\n--- TEXTE body (500 chars) ---")
body = soup.find("body")
if body:
    print(body.get_text(" ", strip=True)[:500])

with open("coaches_raw.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("\nHTML sauvé: coaches_raw.html")