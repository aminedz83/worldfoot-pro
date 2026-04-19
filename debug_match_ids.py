#!/usr/bin/env python3
import cloudscraper, re
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# 1. Page resultats Ligue 1 avec saison
url = "https://fr.besoccer.com/competition/resultats/algeria-league-one/2026"
print(f"Fetch: {url}")
r = scraper.get(url, timeout=20)
print(f"Status: {r.status_code} | Size: {len(r.text)}")

soup = BeautifulSoup(r.text, "html.parser")

# Chercher les liens /match/ qui contiennent des slugs algériens
print("\n--- Liens /match/ avec équipes algériennes ---")
ALG_SLUGS = ["kabylie","belouizdad","mc-alger","usm-alger","es-setif","cs-constantine",
             "mc-oran","js-saoura","paradou","chlef","el-bayadh","usm-khenchela",
             "oued-akbou","es-mostaganem","mb-rouisset","ben-aknoun"]

all_match_links = soup.select("a[href*='/match/']")
print(f"Total liens /match/ : {len(all_match_links)}")

alg_matches = []
for a in all_match_links:
    href = a.get("href","")
    if any(s in href for s in ALG_SLUGS):
        txt = a.get_text(" ", strip=True)[:60]
        print(f"  ✅ {href}")
        print(f"     '{txt}'")
        # Extraire l'ID (dernier segment numérique)
        m = re.search(r"/match/[^/]+/[^/]+/(\d+)/?$", href)
        if m:
            alg_matches.append({"href": href, "id": m.group(1), "text": txt})

print(f"\n→ {len(alg_matches)} matchs algériens trouvés")

# 2. HTML brut d'un bloc match (pour voir la structure date+équipes)
print("\n--- HTML brut premier li/div de match (600 chars) ---")
for a in all_match_links[:20]:
    href = a.get("href","")
    if any(s in href for s in ALG_SLUGS):
        parent = a.parent
        for _ in range(3):
            if parent and len(parent.decode()) > 100:
                print(parent.decode()[:600])
                break
            parent = parent.parent if parent else None
        break

# 3. Chercher aussi par date dans le texte
print("\n--- Recherche dates dans les textes ---")
for tag in soup.find_all(string=re.compile(r'\d{1,2}\s+\w+\s+2026')):
    print(f"  Date trouvée: '{tag.strip()[:60]}'")

with open("match_ids_raw.html", "w") as f:
    f.write(r.text)
print("\nHTML sauvé")