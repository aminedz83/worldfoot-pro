"""
scraper_debug.py - Inspecte la structure HTML des joueurs vedettes BeSoccer
"""
import os
import cloudscraper
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# Akbou vs Setif — on sait qu'il a des joueurs vedettes
URL = "https://www.besoccer.com/match/oued-akbou/es-setif/2026264207/preview"

print(f"=== {URL} ===")
r = scraper.get(URL, timeout=25)
print(f"Status: {r.status_code} | {len(r.text)} chars")

soup = BeautifulSoup(r.text, "html.parser")

# Trouver le tab featured
tab = soup.select_one("#tab-featured-competition")
if not tab:
    print("Tab #tab-featured-competition non trouvé")
    # Chercher alternatives
    for sel in ["div[id*='featured']", "div.featured", "div[id*='vedette']"]:
        els = soup.select(sel)
        if els:
            print(f"Alternatif [{sel}]: {len(els)} elements")
else:
    print(f"\nTab trouvé: {len(str(tab))} chars")
    # Afficher les premières sections
    for i, section in enumerate(tab.select("div.mb15")[:3]):
        print(f"\n=== Section {i+1} ===")
        print(str(section)[:1000])