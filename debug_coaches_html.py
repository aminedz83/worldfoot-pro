#!/usr/bin/env python3
import cloudscraper
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

url = "https://fr.besoccer.com/competition/entreineurs/algeria-league-one"
r = scraper.get(url, timeout=20)
soup = BeautifulSoup(r.text, "html.parser")

print("--- TOUTES LES IMGS près des liens /entraineur/ ---")
for a in soup.select("a[href*='/entraineur/']"):
    imgs = a.find_all("img")
    # Aussi chercher img dans le parent
    parent = a.parent
    if parent:
        imgs += parent.find_all("img")
    name_text = a.get_text("|", strip=True).split("|")[0]
    for img in imgs:
        src = img.get("src","") or img.get("data-src","") or img.get("loading","")
        if src and src != "lazy":
            print(f"  {name_text} → {src}")

print("\n--- HTML brut d'un bloc entraineur (1000 chars) ---")
for a in soup.select("a[href*='/entraineur/']")[:2]:
    parent = a.parent
    if parent:
        print(parent.decode()[:600])
        print("---")

with open("coaches_raw.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("HTML sauvé")