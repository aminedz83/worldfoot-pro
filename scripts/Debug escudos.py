#!/usr/bin/env python3
"""
Vérifie les vrais IDs escudos BeSoccer pour chaque club Ligue 1.
Scrape la page transferts de chaque club et lit l'escudo du club lui-même.
"""
import cloudscraper, re
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

CLUBS = [
    ("MC Alger",        "mc-alger",       11505),
    ("CR Belouizdad",   "belouizdad",     11507),
    ("JS Kabylie",      "kabylie",        11506),
    ("USM Alger",       "usm-alger",      11504),
    ("ES Setif",        "es-setif",       11501),
    ("CS Constantine",  "cs-constantine", 11510),
    ("Paradou AC",      "paradou",        59336),
    ("ASO Chlef",       "chlef",          11511),
    ("MC Oran",         "mc-oran",        11509),
    ("JS Saoura",       "js-saoura",      20933),
    ("MC El Bayadh",    "el-bayadh",      11729),
    ("USM Khenchela",   "usm-khenchela",  11530),
    ("Olympique Akbou", "oued-akbou",     11522),
    ("ES Mostaganem",   "es-mostaganem",  13715),
    ("MB Rouissat",     "mb-rouisset",    100882),
    ("ES Ben Aknoun",   "ben-aknoun",     11519),
]

print("# Résultats — escudo BeSoccer par club")
print("# Format: NomClub → escudos/medium/ID.jpg")
print()

for name, slug, bs_id in CLUBS:
    # Page info du club (pas transferts) — contient l'escudo du club lui-même
    url = f"https://www.besoccer.com/team/{slug}/{bs_id}"
    r = scraper.get(url, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    
    # Chercher l'escudo principal du club
    escudo_id = None
    for img in soup.select("img[src*='escudos']"):
        src = img.get("src", "")
        # Prendre le premier escudo qui apparaît (= celui du club)
        m = re.search(r"escudos/medium/(\d+)", src)
        if m:
            escudo_id = m.group(1)
            break
    
    if escudo_id:
        logo_url = f"https://cdn.resfu.com/img_data/escudos/medium/{escudo_id}.jpg?size=80x&lossy=1"
        print(f'  "{name}": "{logo_url}",  # ID={escudo_id}')
    else:
        print(f'  "{name}": "",  # ❌ escudo non trouvé')
    
    import time; time.sleep(1)