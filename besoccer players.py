"""
besoccer players.py
===================
Scrape joueurs + photos + stats de Ligue 1 Algérie depuis BeSoccer.
Sauvegarde dans Supabase : besoccer_players (UPSERT)
"""

import os, re, time, requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# ══════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL       = "https://iqeqlsxjiklygywjirqs.supabase.co"

# Headers standard
SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates"
}

# Slugs corrigés depuis les vraies URLs BeSoccer
CLUBS = [
    {"name": "MC Alger",        "slug": "mc-alger",      "id": 11505},
    {"name": "CR Belouizdad",   "slug": "belouizdad",    "id": 11507},
    {"name": "JS Kabylie",      "slug": "kabylie",       "id": 11506},
    {"name": "USM Alger",       "slug": "usm-alger",     "id": 11504},
    {"name": "ES Sétif",        "slug": "es-setif",      "id": 11501},
    {"name": "CS Constantine",  "slug": "cs-constantine","id": 11510},
    {"name": "Paradou AC",      "slug": "paradou",       "id": 59336},
    {"name": "ASO Chlef",        "slug": "chlef",        "id": 11511},  # à corriger si 404
    {"name": "MC Oran",         "slug": "mc-oran",       "id": 11509},
    {"name": "JS Saoura",       "slug": "js-saoura",     "id": 20933},
    {"name": "MC El Bayadh",    "slug": "el-bayadh",     "id": 11729},
    {"name": "USM Khenchela",   "slug": "usm-khenchela", "id": 11530},
    {"name": "Olympique Akbou", "slug": "oued-akbou",    "id": 11522},
    {"name": "ES Mostaganem",   "slug": "es-mostaganem", "id": 13715},
    {"name": "MB Rouissat",     "slug": "mb-rouisset",   "id": 100882},
    {"name": "ES Ben Aknoun",   "slug": "ben-aknoun",    "id": 11519},
]

# ══════════════════════════════════════════════
# SCRAPER
# ══════════════════════════════════════════════

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

def fetch(url):
    try:
        r = scraper.get(url, timeout=20)
        print(f"  Status {r.status_code}")
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
        return None
    except Exception as e:
        print(f"  Erreur: {e}")
        return None

def extract_id_from_url(href):
    if not href:
        return None
    m = re.search(r"/player/[^/]+-(\d+)/?$", href)
    if m:
        return m.group(1)
    m = re.search(r"/player/([^/]+)/?$", href)
    if m:
        return m.group(1)
    return None

# ══════════════════════════════════════════════
# SCRAPE UN CLUB
# ══════════════════════════════════════════════

def scrape_club(club):
    url  = f"https://www.besoccer.com/team/squad/{club['slug']}/{club['id']}/"
    soup = fetch(url)
    if not soup:
        return []

    players       = []
    seen          = set()
    current_poste = ""

    for row in soup.select("tr"):

        # Ligne en-tête → poste courant
        if "row-head" in row.get("class", []):
            th = row.select_one("th.main")
            if th:
                current_poste = th.get_text(strip=True)
            continue

        if "row-body" not in row.get("class", []):
            continue

        name_td = row.select_one("td.name a")
        if not name_td:
            continue

        href      = name_td.get("href", "")
        nom       = name_td.get_text(strip=True)
        player_id = extract_id_from_url(href)

        if not player_id or not nom or player_id in seen:
            continue
        seen.add(player_id)

        # Photo
        photo_td = row.select_one("td.player-img img")
        if photo_td and photo_td.get("src"):
            photo = photo_td["src"].replace("size=60x", "size=120x")
            if photo.startswith("//"):
                photo = "https:" + photo
        else:
            photo = f"https://cdn.resfu.com/img_data/players/medium/{player_id}.jpg?size=120x&lossy=1"

        # Numéro maillot
        num_td = row.select_one("td.number-box div")
        numero = num_td.get_text(strip=True) if num_td else ""

        # Stats performance
        perf_tds  = row.select("td[data-content-tab='team_performance']")
        matchs    = int(perf_tds[0].get_text(strip=True) or 0) if len(perf_tds) > 0 else 0
        buts      = int(perf_tds[2].get_text(strip=True) or 0) if len(perf_tds) > 2 else 0
        cartons_j = int(perf_tds[3].get_text(strip=True) or 0) if len(perf_tds) > 3 else 0
        cartons_r = int(perf_tds[4].get_text(strip=True) or 0) if len(perf_tds) > 4 else 0

        # Age
        info_tds = row.select("td[data-content-tab='team_info']")
        age = ""
        if info_tds:
            age_text = info_tds[0].get_text(strip=True)
            if re.match(r"^\d{2}$", age_text):
                age = age_text

        players.append({
            "club":        club["name"],
            "besoccer_id": str(player_id),
            "nom":         nom,
            "url_photo":   photo,
            "poste":       current_poste,
            "numero":      numero,
            "age":         age,
            "matchs":      matchs,
            "buts":        buts,
            "cartons_j":   cartons_j,
            "cartons_r":   cartons_r,
            "scraped_at":  datetime.now(timezone.utc).isoformat()
        })

    print(f"  ✅ {len(players)} joueurs")
    return players

# ══════════════════════════════════════════════
# SAUVEGARDE SUPABASE — UPSERT (évite les doublons)
# ══════════════════════════════════════════════

def save_players(players):
    if not players:
        return

    # UPSERT : on_conflict=besoccer_id → met à jour si déjà existant
    res = requests.post(
        SB_URL + "/rest/v1/besoccer_players",
        headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
        params={"on_conflict": "besoccer_id"},
        json=players
    )
    code = res.status_code
    if code in [200, 201, 204]:
        print(f"  Supabase: ✅ OK ({code})")
    else:
        print(f"  Supabase: ❌ {code} → {res.text[:200]}")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

print("=== BeSoccer Players Scraper ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print(f"{len(CLUBS)} clubs\n")

total = 0
errors = 0

for club in CLUBS:
    print(f"\n📋 {club['name']}")
    try:
        players = scrape_club(club)
        if players:
            save_players(players)
            total += len(players)
        else:
            print(f"  ⚠️  Aucun joueur — vérifier le slug")
            errors += 1
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        errors += 1
    time.sleep(3)

print(f"\n=== Terminé : {total} joueurs | {errors} clubs ignorés ===")