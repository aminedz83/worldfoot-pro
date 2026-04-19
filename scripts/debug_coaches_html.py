#!/usr/bin/env python3
import cloudscraper
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

url = "https://fr.besoccer.com/competition/entreineurs/algeria-league-one"
print(f"Fetch: {url}")
r = scraper.get(url, timeout=20)
print(f"Status: {r.status_code} | Size: {len(r.text)} chars")

soup = BeautifulSoup(r.text, "html.parser")

print("\n--- TITRES ---")
for t in soup.find_all(["h1","h2","h3"]):
    print(f"  <{t.name}>: '{t.get_text(strip=True)[:80]}'")

print("\n--- CLASSES <li> ---")
li_cls = list(set([" ".join(l.get("class",[])) for l in soup.find_all("li") if l.get("class")]))
for c in li_cls[:20]:
    print(f"  '{c}'")

print("\n--- LIENS /coach/ ou /trainer/ ou /entraineur/ ---")
for a in soup.select("a[href*='/coach/'], a[href*='/trainer/'], a[href*='/entraineur/'], a[href*='/staff/']")[:10]:
    print(f"  {a.get('href','')} → '{a.get_text(strip=True)[:50]}'")

print("\n--- PREMIERS 5 li avec contenu coach ---")
for li in soup.find_all("li")[:30]:
    txt = li.get_text(" ", strip=True)
    if len(txt) > 10 and any(w in txt.lower() for w in ["fc","sc","js","mc","cr","usm","es "]):
        print(f"  class='{' '.join(li.get('class',[]))}' → '{txt[:120]}'")

print("\n--- HTML brut premier ul non-vide (800 chars) ---")
for ul in soup.find_all("ul"):
    lis = ul.find_all("li")
    if len(lis) > 3:
        total_text = ul.get_text(strip=True)
        if len(total_text) > 100:
            print(f"UL classes: {ul.get('class')}")
            print(ul.decode()[:1000])
            break

print("\n--- TEXTE body (600 chars) ---")
body = soup.find("body")
if body:
    print(body.get_text(" ", strip=True)[:600])

with open("coaches_raw.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("\nHTML sauvé: coaches_raw.html")