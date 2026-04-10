"""
besoccer players.py
===================
Scrape joueurs + photos + stats de Ligue 1 Algérie depuis BeSoccer.
Sauvegarde dans Supabase : besoccer_players
"""

import os, re, time, requests
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

# Headers complets qui imitent Chrome
HEADERS = {
    "User-Agent":                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language":           "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding":           "gzip, deflate, br",
    "Connection":                "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":            "document",
    "Sec-Fetch-Mode":            "navigate",
    "Sec-Fetch-Site":            "none",
    "Sec-Fetch-User":            "?1",
    "Cache-Control":             "max-age=0",
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
# SESSION avec cookies
# ══════════════════════════════════════════════

session = requests.Session()
session.headers.update(HEADERS)

def init_session():
    """Visite la page d'accueil pour obtenir les cookies."""
    try:
        r = session.get("https://www.besoccer.com/", timeout=15)
        print(f"  Session init: {r.status_code}")
        time.sleep(2)
    except Exception as e:
        print(f"  Erreur session init: {e}")

def fetch(url):
    try:
        # Simuler un vrai navigateur avec Referer
        session.headers.update({"Referer": "https://www.besoccer.com/"})
        r = session.get(url, timeout=15)
        print(f"  Status {r.status_code} : {url}")
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
        return None
    except Exception as e:
        print(f"  Erreur fetch: {e}")
        return None

def extract_id(href):
    if not href:
        return None
    m = re.search(r"/player/[^/]+/(\d+)/?", href)
    return m.group(1) if m else None

# ══════════════════════════════════════════════
# SCRAPE UN CLUB
# ══════════════════════════════════════════════

def scrape_club(club):
    url = f"https://www.besoccer.com/team/squad/{club['slug']}/{club['id']}/"
    print(f"\n📋 {club['name']}")

    soup = fetch(url)
    if not soup:
        return []

    players = []
    seen    = set()

    # Chercher toutes les lignes avec un lien joueur
    rows = soup.select("tr, li.player-item, .squad-player")

    for row in rows:
        link = row.select_one("a[href*='/player/']")
        if not link:
            continue

        href      = link.get("href", "")
        player_id = extract_id(href)
        nom       = link.get_text(strip=True)

        if not player_id or not nom or player_id in seen:
            continue

        # Ignorer coach
        row_text = row.get_text(" ").lower()
        if any(k in row_text for k in ["coach", "entrenador", "entraîneur", "manager"]):
            continue

        seen.add(player_id)

        # Photo
        img = row.select_one("img")
        if img and img.get("src") and any(k in img["src"] for k in ["player", "cdn", "resfu"]):
            photo = img["src"]
            if photo.startswith("//"):
                photo = "https:" + photo
            if photo.startswith("/"):
                photo = "https://www.besoccer.com" + photo
        else:
            photo = f"https://cdn.resfu.com/img_data/players/medium/{player_id}.jpg"

        # Poste
        pos_el = row.select_one("td.pos, .player-pos, span.pos, td.demarcation")
        poste  = pos_el.get_text(strip=True) if pos_el else ""

        # Age
        age_el = row.select_one("td.age, .player-age")
        age    = age_el.get_text(strip=True) if age_el else ""
        if not re.match(r"^\d{2}$", age):
            age = ""

        # Stats numériques
        tds  = row.select("td")
        nums = []
        for td in tds:
            t = td.get_text(strip=True)
            if re.match(r"^\d{1,4}$", t):
                nums.append(int(t))

        matchs  = 0
        minutes = 0
        buts    = 0

        for n in nums:
            if 0 < n <= 38 and matchs == 0:
                matchs = n
            elif n > 38 and n <= 3420 and minutes == 0:
                minutes = n
            elif 0 < n <= 50 and buts == 0 and n != matchs:
                buts = n

        players.append({
            "club":        club["name"],
            "besoccer_id": player_id,
            "nom":         nom,
            "url_photo":   photo,
            "poste":       poste,
            "age":         age,
            "matchs":      matchs,
            "minutes":     minutes,
            "buts":        buts,
            "cartons_j":   0,
            "cartons_r":   0,
            "scraped_at":  datetime.now(timezone.utc).isoformat()
        })

    print(f"  ✅ {len(players)} joueurs")
    return players

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
    print(f"  Supabase: {res.status_code} ({'OK' if res.status_code in [200,201,204] else res.text[:200]})")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

print("=== BeSoccer Players Scraper ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Initialiser la session avec cookies
print("\nInitialisation session...")
init_session()

total = 0
for club in CLUBS:
    try:
        players = scrape_club(club)
        if players:
            save_players(players)
            total += len(players)
        else:
            print(f"  ⚠️  Aucun joueur trouvé")
    except Exception as e:
        print(f"  ❌ Erreur {club['name']}: {e}")
    time.sleep(3)

print(f"\n=== Terminé : {total} joueurs sauvegardés ===")