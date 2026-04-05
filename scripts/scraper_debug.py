import requests, re
from bs4 import BeautifulSoup
from datetime import date

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": "https://fr.soccerway.com/"
}

today = date.today()
url = "https://fr.soccerway.com/matches/{}/{}/{}/".format(
    today.strftime("%Y"), today.strftime("%m"), today.strftime("%d")
)
print("URL:", url)
r = requests.get(url, headers=HEADERS, timeout=20)
print("Status:", r.status_code, "| Taille:", len(r.text))

# Chercher TOUS les liens /match/ dans le HTML brut
print("\n=== Tous les /match/ dans le HTML ===")
matches_found = re.findall(r'/match/[^"\'<>\s]+', r.text)
print("Total liens /match/:", len(matches_found))
for m in matches_found[:20]:
    print(" ", m)

# Chercher algeria dans le HTML
print("\n=== Algérie dans le HTML ===")
if "algeri" in r.text.lower() or "kabylie" in r.text.lower() or "belouizdad" in r.text.lower():
    print("✅ Algérie/Kabylie trouvé dans le HTML!")
    # Trouver le contexte
    idx = r.text.lower().find("kabylie")
    if idx > 0:
        print("Contexte:", r.text[max(0,idx-200):idx+200])
else:
    print("❌ Aucune référence à l'Algérie dans le HTML")

# Chercher les IDs Soccerway algériens
ALGERIA_SW_IDS = ["Wfaskwf0","vNJLB2jP","tnY2Lfcp","zXBidj5t","nBionu2l",
                   "EDgC6qYp","CrCmB35M","Aobolc96","nimcBvel","QmvZvxCB",
                   "lYuJtBj9","hGHHy7Am","WIyffF3J","j9T7TM2E","S6H5xCS1","dhMQsMOh"]

print("\n=== IDs algériens dans le HTML ===")
found_ids = []
for sw_id in ALGERIA_SW_IDS:
    if sw_id in r.text:
        found_ids.append(sw_id)
        print("  ✅ Trouvé:", sw_id)
if not found_ids:
    print("  ❌ Aucun ID algérien trouvé")

# Afficher les 3000 premiers chars pour voir la structure
print("\n=== Structure HTML (3000 chars) ===")
print(r.text[1000:4000])