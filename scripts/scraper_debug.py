"""
scraper_debug.py
================
Inspecte la structure HTML de la page events BeSoccer
pour trouver les bons sélecteurs CSS.
"""

import os
import cloudscraper
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# Akbou vs Setif — match terminé avec des events connus
URL = "https://www.besoccer.com/match/oued-akbou/es-setif/2026264207/events"

print(f"=== Fetch: {URL} ===")
r = scraper.get(URL, timeout=20)
print(f"Status: {r.status_code} | Taille: {len(r.text)} chars")

soup = BeautifulSoup(r.text, "html.parser")

# ── Score ──────────────────────────────────────────────
print("\n=== SCORE ===")
for sel in ["div.match-score", "span.match-score", "div.score-cont",
            "div.match-result", "span.score", "div.result",
            "div.team-result", "p.score", "div.match-info"]:
    els = soup.select(sel)
    if els:
        print(f"  [{sel}] → '{els[0].get_text(strip=True)}'")

# ── Conteneurs d'événements ────────────────────────────
print("\n=== CONTENEURS EVENTS ===")
for sel in ["div.table-played-match", "div.all-events", "li.event-row",
            "div.event-item", "div.events-list", "ul.events",
            "div.match-events", "div.event", "tr.event",
            "div[class*='event']", "li[class*='event']"]:
    els = soup.select(sel)
    if els:
        print(f"  [{sel}] → {len(els)} elements")
        print(f"    Premier: {str(els[0])[:300]}")
        print()

# ── Images d'événements ───────────────────────────────
print("\n=== IMAGES EVENTS ===")
for sel in ["img[src*='accion']", "img[src*='tarjeta']", "img[src*='cambio']",
            "img[src*='event']", "img.ic-bench", "img[alt*='goal']",
            "img[alt*='Goal']", "img[alt*='yellow']", "img[alt*='Yellow']",
            "img[alt*='sub']", "img[alt*='Sub']"]:
    els = soup.select(sel)
    if els:
        print(f"  [{sel}] → {len(els)} images")
        for img in els[:3]:
            print(f"    src={img.get('src','')[:80]} alt={img.get('alt','')}")

# ── HTML brut section events ──────────────────────────
print("\n=== HTML BRUT autour des events ===")
body = soup.find("body")
if body:
    text = str(body)
    for keyword in ["accion1", "tarjeta", "cambio", "ic-bench"]:
        idx = text.lower().find(keyword)
        if idx >= 0:
            print(f"  Keyword '{keyword}' trouvé à index {idx}:")
            print(text[max(0,idx-300):idx+600])
            print("---")
            break
    else:
        print("  Aucun keyword trouvé — voici le début du body:")
        print(text[:3000])