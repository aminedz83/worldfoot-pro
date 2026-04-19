#!/usr/bin/env python3
"""
Script de debug : dump le HTML brut de la page transferts BeSoccer
pour analyser la vraie structure et corriger les sélecteurs.
"""

import os, json
import cloudscraper
from bs4 import BeautifulSoup

SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# On teste sur CR Belouizdad (club populaire = plus de transferts)
CLUBS_TO_DEBUG = [
    {"name": "CR Belouizdad", "slug": "belouizdad", "bs_id": 11507},
    {"name": "JS Kabylie",    "slug": "kabylie",    "bs_id": 11506},
    {"name": "USM Alger",     "slug": "usm-alger",  "bs_id": 11504},
]

debug = {}

for club in CLUBS_TO_DEBUG:
    url = f"https://www.besoccer.com/team/transfers/{club['slug']}/{club['bs_id']}/2026"
    print(f"\nFetch: {url}")
    r = scraper.get(url, timeout=20)
    print(f"Status: {r.status_code} | Size: {len(r.text)} chars")

    soup = BeautifulSoup(r.text, "html.parser")

    # 1. Tous les h2/h3/h4 de la page
    titles = [t.get_text(strip=True) for t in soup.find_all(["h2","h3","h4"])]
    print(f"Titres h2/h3/h4: {titles}")

    # 2. Tous les éléments avec class contenant "transfer"
    transfer_els = soup.find_all(class_=lambda c: c and "transfer" in " ".join(c).lower())
    print(f"Éléments class='*transfer*': {len(transfer_els)}")
    for el in transfer_els[:3]:
        print(f"  <{el.name} class='{' '.join(el.get('class',[]))}'>: {el.get_text(' ', strip=True)[:100]}")

    # 3. Tous les liens /player/ (= joueurs)
    player_links = soup.select("a[href*='/player/']")
    print(f"Liens /player/: {len(player_links)}")
    for a in player_links[:5]:
        print(f"  {a.get('href','')} → '{a.get_text(strip=True)}'")

    # 4. Tous les liens /team/ (= clubs)
    team_links = soup.select("a[href*='/team/']")
    print(f"Liens /team/: {len(team_links)}")
    for a in team_links[:5]:
        print(f"  {a.get('href','')} → '{a.get_text(strip=True)}'")

    # 5. Classes uniques de tous les <li> et <tr>
    li_classes = list(set([" ".join(el.get("class",[])) for el in soup.find_all("li") if el.get("class")]))
    tr_classes = list(set([" ".join(el.get("class",[])) for el in soup.find_all("tr") if el.get("class")]))
    print(f"Classes <li>: {li_classes[:10]}")
    print(f"Classes <tr>: {tr_classes[:10]}")

    # 6. Sauver un extrait HTML (2000 premiers chars du body)
    body = soup.find("body")
    body_text = body.get_text(" ", strip=True)[:500] if body else ""
    print(f"Body text: {body_text}")

    debug[club["name"]] = {
        "url": url,
        "status": r.status_code,
        "size": len(r.text),
        "titles": titles,
        "player_links_count": len(player_links),
        "team_links_count": len(team_links),
        "li_classes": li_classes[:20],
        "tr_classes": tr_classes[:20],
        # HTML brut des 8000 premiers chars pour inspection manuelle
        "html_head": r.text[:8000],
    }

with open("transfers_html_debug.json", "w", encoding="utf-8") as f:
    json.dump(debug, f, ensure_ascii=False, indent=2)
print("\nSauvé: transfers_html_debug.json")