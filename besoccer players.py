"""
besoccer players.py
===================
Scrape joueurs + photos + stats de Ligue 1 Algérie depuis BeSoccer.
Sélecteurs basés sur le vrai HTML de BeSoccer.
Sauvegarde dans Supabase : besoccer_players
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
SB_HEADERS   = {
    "apikey":        SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates"
}

CLUBS = [
    {"name": "MC Alger",        "id": 11505,  "slug": "mc-alger"},
    {"name": "CR Belouizdad",   "id": 11507,  "slug": "cr-belouizdad"},
    {"name": "JS Kabylie",      "id": 11506,  "slug": "js-kabylie"},
    {"name": "USM Alger",       "id": 11504,  "slug": "usm-alger"},
    {"name": "ES Sétif",        "id": 11501,  "slug": "es-setif"},
    {"name": "CS Constantine",  "id": 11510,  "slug": "cs-constantine"},
    {"name": "Paradou AC",      "id": 59336,  "slug": "paradou-ac"},
    {"name": "ASO Chlef",       "id": 11511,  "slug": "aso-chlef"},
    {"name": "MC Oran",         "id": 11509,  "slug": "mc-oran"},
    {"name": "JS Saoura",       "id": 20933,  "slug": "js-saoura"},
    {"name": "MC El Bayadh",    "id": 11729,  "slug": "mc-el-bayadh"},
    {"name": "USM Khenchela",   "id": 11530,  "slug": "usm-khenchela"},
    {"name": "Olympique Akbou", "id": 11522,  "slug": "olympique-akbou"},
    {"name": "ES Mostaganem",   "id": 13715,  "slug": "es-mostaganem"},
    {"name": "MB Rouissat",     "id": 100882, "slug": "mb-rouissat"},
    {"name": "ES Ben Aknoun",   "id": 11519,  "slug": "es-ben-aknoun"},
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
    """
    Extrait l'ID depuis l'URL BeSoccer.
    Ex: /player/z-naidji-462650 → 462650
    Ex: /player/ayoub-abdellaoui → ayoub-abdellaoui (slug sans ID numérique)
    """
    if not href:
        return None
    # Cas 1 : URL avec ID numérique à la fin  /player/nom-123456
    m = re.search(r"/player/[^/]+-(\d+)/?$", href)
    if m:
        return m.group(1)
    # Cas 2 : URL slug sans ID  /player/ayoub-abdellaoui
    m = re.search(r"/player/([^/]+)/?$", href)
    if m:
        return m.group(1)
    return None

# ══════════════════════════════════════════════
# SCRAPE UN CLUB
# ══════════════════════════════════════════════

def scrape_club(club):
    url = f"https://www.besoccer.com/team/squad/{club['slug']}/{club['id']}/"
    print(f"\n📋 {club['name']} → {url}")

    soup = fetch(url)
    if not soup:
        return []

    players = []
    seen    = set()

    # Le poste courant est défini par les lignes d'en-tête tr.row-head
    current_poste = ""

    rows = soup.select("tr")

    for row in rows:
        # Ligne d'en-tête → met à jour le poste courant
        if "row-head" in row.get("class", []):
            th = row.select_one("th.main")
            if th:
                current_poste = th.get_text(strip=True)
            continue

        # Ligne joueur
        if "row-body" not in row.get("class", []):
            continue

        # Nom + lien depuis td.name
        name_td = row.select_one("td.name a")
        if not name_td:
            continue

        href      = name_td.get("href", "")
        nom       = name_td.get_text(strip=True)
        player_id = extract_id_from_url(href)

        if not player_id or not nom or player_id in seen:
            continue

        seen.add(player_id)

        # Photo depuis td.player-img img
        photo_td  = row.select_one("td.player-img img")
        if photo_td and photo_td.get("src"):
            photo = photo_td["src"]
            # Remplacer size=60x par size=120x pour meilleure qualité
            photo = photo.replace("size=60x", "size=120x")
            if photo.startswith("//"):
                photo = "https:" + photo
        else:
            photo = f"https://cdn.resfu.com/img_data/players/medium/{player_id}.jpg?size=120x&lossy=1"

        # Numéro de maillot depuis td.number-box
        num_td = row.select_one("td.number-box div")
        numero = num_td.get_text(strip=True) if num_td else ""

        # Stats depuis les td avec data-content-tab="team_performance"
        perf_tds = row.select("td[data-content-tab='team_performance']")
        matchs   = 0
        buts     = 0
        cartons_j = 0
        cartons_r = 0

        if len(perf_tds) >= 1:
            matchs    = int(perf_tds[0].get_text(strip=True) or 0)
        if len(perf_tds) >= 3:
            buts      = int(perf_tds[2].get_text(strip=True) or 0)
        if len(perf_tds) >= 4:
            cartons_j = int(perf_tds[3].get_text(strip=True) or 0)
        if len(perf_tds) >= 5:
            cartons_r = int(perf_tds[4].get_text(strip=True) or 0)

        # Age depuis td[data-content-tab="team_info"]
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

    print(f"  ✅ {len(players)} joueurs trouvés")
    return players

# ══════════════════════════════════════════════
# COACH
# ══════════════════════════════════════════════

def scrape_coach(soup, club_name):
    """Extrait le coach depuis la section .team-coach"""
    coaches = []
    coach_divs = soup.select(".team-coach")
    for div in coach_divs:
        link = div.select_one("a[href*='/coach/']")
        img  = div.select_one("img.player")
        if link:
            nom   = link.get_text(strip=True)
            photo = img["src"] if img and img.get("src") else ""
            if photo.startswith("//"):
                photo = "https:" + photo
            coaches.append({"club": club_name, "nom": nom, "url_photo": photo})
    return coaches

# ══════════════════════════════════════════════
# SAUVEGARDE SUPABASE
# ══════════════════════════════════════════════

def save_players(players):
    if not players:
        return
    res = requests.post(
        SB_URL + "/rest/v1/besoccer_players",
        headers=SB_HEADERS,
        json=players
    )
    status = res.status_code
    print(f"  Supabase players: {status} ({'OK' if status in [200,201,204] else res.text[:300]})")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

print("=== BeSoccer Players Scraper ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print(f"{len(CLUBS)} clubs à scraper\n")

total = 0
for club in CLUBS:
    try:
        soup = scraper.get(
            f"https://www.besoccer.com/team/squad/{club['slug']}/{club['id']}/",
            timeout=20
        )
        print(f"\n📋 {club['name']} → Status {soup.status_code}")

        if soup.status_code != 200:
            print(f"  ⚠️  Ignoré")
            time.sleep(3)
            continue

        bs = BeautifulSoup(soup.text, "html.parser")
        players = scrape_club(club)

        if players:
            save_players(players)
            total += len(players)
        else:
            print(f"  ⚠️  Aucun joueur")

    except Exception as e:
        print(f"  ❌ Erreur {club['name']}: {e}")

    time.sleep(3)

print(f"\n=== Terminé : {total} joueurs sauvegardés ===")