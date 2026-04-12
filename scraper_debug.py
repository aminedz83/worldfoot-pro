"""
scraper_debug.py - Inspecte HTML changements BeSoccer
"""
import os
import cloudscraper
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# JSK vs CSC — on sait qu'il y a des changements
URL = "https://www.besoccer.com/match/kabylie/cs-constantine/2026264214/events"

print(f"=== {URL} ===")
r = scraper.get(URL, timeout=20)
print(f"Status: {r.status_code} | {len(r.text)} chars")

soup = BeautifulSoup(r.text, "html.parser")

# Afficher TOUS les div.table-played-match avec leur contenu complet
rows = soup.select("div.table-played-match")
print(f"\n=== {len(rows)} events total ===")
for i, row in enumerate(rows):
    print(f"\n--- Event {i+1} ---")
    print(str(row)[:800])