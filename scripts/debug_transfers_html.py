#!/usr/bin/env python3
"""
Debug : sauvegarde le HTML brut de la page transferts BeSoccer
+ analyse rapide de la structure pour corriger les sélecteurs.
"""

import cloudscraper
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# CR Belouizdad — club avec le plus de transferts probables
url = "https://www.besoccer.com/team/transfers/belouizdad/11507/2026"
print(f"Fetch: {url}")
r = scraper.get(url, timeout=20)
print(f"Status: {r.status_code} | Size: {len(r.text)} chars")

# Sauver le HTML brut complet
with open("besoccer_transfers_raw.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("HTML sauvé : besoccer_transfers_raw.html")

# Analyse rapide
soup = BeautifulSoup(r.text, "html.parser")

print("\n--- TITRES (h1/h2/h3/h4) ---")
for t in soup.find_all(["h1","h2","h3","h4"]):
    print(f"  <{t.name}>: '{t.get_text(strip=True)[:80]}'")

print("\n--- LIENS /player/ ---")
for a in soup.select("a[href*='/player/']")[:10]:
    print(f"  {a.get('href','')} → '{a.get_text(strip=True)[:40]}'")

print("\n--- LIENS /team/ ---")
for a in soup.select("a[href*='/team/']")[:10]:
    print(f"  {a.get('href','')} → '{a.get_text(strip=True)[:40]}'")

print("\n--- CLASSES <li> ---")
li_classes = list(set([" ".join(el.get("class",[])) for el in soup.find_all("li") if el.get("class")]))
for c in li_classes[:15]:
    print(f"  '{c}'")

print("\n--- CLASSES <div> contenant 'transfer' ou 'alta' ou 'baja' ---")
for el in soup.find_all(class_=True):
    cls = " ".join(el.get("class",[]))
    if any(w in cls.lower() for w in ["transfer","alta","baja","ficha","signing"]):
        print(f"  <{el.name} class='{cls}'>: '{el.get_text(' ',strip=True)[:80]}'")

print("\n--- PREMIER <main> ou <article> (500 chars) ---")
main = soup.find("main") or soup.find("article") or soup.find("div", id="content")
if main:
    print(main.get_text(" ", strip=True)[:500])