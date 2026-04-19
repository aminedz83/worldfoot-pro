#!/usr/bin/env python3
import cloudscraper
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

url = "https://www.besoccer.com/team/transfers/belouizdad/11507/2026"
print(f"Fetch: {url}")
r = scraper.get(url, timeout=20)
print(f"Status: {r.status_code} | Size: {len(r.text)} chars")

soup = BeautifulSoup(r.text, "html.parser")

# 1. Trouver le conteneur principal des transferts
print("\n--- div.signing-season ---")
for div in soup.select("div.signing-season"):
    print(f"  classes: {div.get('class')}")
    print(f"  text[:200]: {div.get_text(' ', strip=True)[:200]}")
    print()

# 2. HTML brut autour des 3 premiers li.sign-list (parent + siblings)
print("\n--- CONTEXTE HTML des 3 premiers li.sign-list ---")
for i, li in enumerate(soup.select("li.sign-list")[:3]):
    parent = li.parent
    print(f"\n[sign-list #{i+1}]")
    print(f"  Parent: <{parent.name} class='{' '.join(parent.get('class',[]))}'>")
    # Chercher le titre/header le plus proche avant ce li
    prev = li.find_previous_sibling()
    while prev:
        cls = " ".join(prev.get("class", []))
        txt = prev.get_text(strip=True)[:80]
        print(f"  Prev sibling: <{prev.name} class='{cls}'> '{txt}'")
        if txt:
            break
        prev = prev.find_previous_sibling()
    # Parent du parent
    gp = parent.parent
    if gp:
        print(f"  Grandparent: <{gp.name} class='{' '.join(gp.get('class',[]))}'>")

# 3. Lister TOUS les éléments dans le premier div.signing-season
print("\n--- ENFANTS DIRECTS du premier div.signing-season ---")
main_div = soup.select_one("div.signing-season")
if main_div:
    for child in main_div.children:
        if not hasattr(child, 'name') or not child.name:
            continue
        cls = " ".join(child.get("class", []))
        txt = child.get_text(" ", strip=True)[:100]
        print(f"  <{child.name} class='{cls}'>: '{txt}'")

# 4. HTML brut du premier ul contenant des li.sign-list
print("\n--- HTML brut premier UL avec sign-list (500 chars) ---")
for ul in soup.find_all("ul"):
    if ul.select("li.sign-list"):
        print(f"  UL classes: {ul.get('class')}")
        print(ul.decode()[:800])
        break

with open("besoccer_transfers_raw.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("\nHTML sauvé")