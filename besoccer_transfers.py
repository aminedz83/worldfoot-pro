#!/usr/bin/env python3
"""
besoccer_transfers.py
=====================
Scrape les transferts Ligue 1 Algérie depuis BeSoccer.
Stocke dans la table Supabase `algeria_transfers`.
Planifié via sync-transfers.yml (1x/jour à 6h UTC).

Pattern identique à besoccer_lineups.py :
- cloudscraper (contourne le 403 BeSoccer)
- slugs BeSoccer réels (pas les noms API-football)
- IDs BeSoccer internes pour construire les URLs équipes
"""

import os, re, time, json, hashlib, requests
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

SEASON = int(os.environ.get("TRANSFER_SEASON", datetime.now().year))

# ══════════════════════════════════════════════
# CLUBS — slugs et IDs BeSoccer réels
# Copiés depuis besoccer_lineups.py TEAM_SLUG + club_ids
# ══════════════════════════════════════════════

CLUBS = [
    {"name": "MC Alger",        "slug": "mc-alger",        "bs_id": 11505, "api_logo": "https://media.api-sports.io/football/teams/906.png"},
    {"name": "CR Belouizdad",   "slug": "belouizdad",      "bs_id": 11507, "api_logo": "https://media.api-sports.io/football/teams/904.png"},
    {"name": "JS Kabylie",      "slug": "kabylie",         "bs_id": 11506, "api_logo": "https://media.api-sports.io/football/teams/918.png"},
    {"name": "USM Alger",       "slug": "usm-alger",       "bs_id": 11504, "api_logo": "https://media.api-sports.io/football/teams/910.png"},
    {"name": "ES Setif",        "slug": "es-setif",        "bs_id": 11501, "api_logo": "https://media.api-sports.io/football/teams/905.png"},
    {"name": "CS Constantine",  "slug": "cs-constantine",  "bs_id": 11510, "api_logo": "https://media.api-sports.io/football/teams/911.png"},
    {"name": "Paradou AC",      "slug": "paradou",         "bs_id": 59336, "api_logo": "https://media.api-sports.io/football/teams/915.png"},
    {"name": "ASO Chlef",       "slug": "chlef",           "bs_id": 11511, "api_logo": "https://media.api-sports.io/football/teams/925.png"},
    {"name": "MC Oran",         "slug": "mc-oran",         "bs_id": 11509, "api_logo": "https://media.api-sports.io/football/teams/907.png"},
    {"name": "JS Saoura",       "slug": "js-saoura",       "bs_id": 20933, "api_logo": "https://media.api-sports.io/football/teams/914.png"},
    {"name": "MC El Bayadh",    "slug": "el-bayadh",       "bs_id": 11729, "api_logo": ""},
    {"name": "USM Khenchela",   "slug": "usm-khenchela",   "bs_id": 11530, "api_logo": ""},
    {"name": "Olympique Akbou", "slug": "oued-akbou",      "bs_id": 11522, "api_logo": ""},
    {"name": "ES Mostaganem",   "slug": "es-mostaganem",   "bs_id": 13715, "api_logo": ""},
    {"name": "MB Rouissat",     "slug": "mb-rouisset",     "bs_id": 100882,"api_logo": ""},
    {"name": "ES Ben Aknoun",   "slug": "ben-aknoun",      "bs_id": 11519, "api_logo": ""},
]

# ══════════════════════════════════════════════
# CLOUDSCRAPER — même config que besoccer_lineups.py
# ══════════════════════════════════════════════

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

def fetch(url):
    try:
        r = scraper.get(url, timeout=20)
        print(f"  GET {r.status_code} : {url}")
        return r if r.status_code == 200 else None
    except Exception as e:
        print(f"  Erreur: {e}")
        return None

# ══════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════

def extract_player_id(href):
    if not href:
        return None
    m = re.search(r"/player/[^/]+-(\d+)/?$", href)
    if m:
        return m.group(1)
    m = re.search(r"/player/([^/]+)/?$", href)
    return m.group(1) if m else None

def make_uid(club_name, player_name, direction, season):
    raw = f"{club_name}|{player_name}|{direction}|{season}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]

def parse_transfer_type(text):
    t = text.lower()
    if "fin de prêt" in t or "fin de prestamo" in t or "return" in t:
        return "Fin de prêt"
    if "prêt" in t or "prestamo" in t or "loan" in t or "cedido" in t:
        return "Prêt"
    if "libre" in t or "free" in t or "agente libre" in t:
        return "Libre"
    if "rescisi" in t:
        return "Résiliation"
    return "Transfert"

def parse_amount(text):
    m = re.search(r"[\d,.]+\s*[MmKk]?\s*[€$£]|[€$£]\s*[\d,.]+\s*[MmKk]?", text)
    return m.group(0).strip() if m else ""

def clean_logo(src):
    if not src:
        return ""
    if src.startswith("//"):
        return "https:" + src
    return src

# ══════════════════════════════════════════════
# PARSE UN ROW DE TRANSFERT
# ══════════════════════════════════════════════

def parse_transfer_row(row, club, season, direction):
    """Parse un <li> ou <tr> BeSoccer en dict transfert."""
    text = row.get_text(" ", strip=True)
    if not text or len(text) < 3:
        return None

    # Lien joueur obligatoire
    player_link = row.select_one("a[href*='/player/']")
    if not player_link:
        return None
    player_name = player_link.get_text(strip=True)
    if not player_name or len(player_name) < 2:
        return None

    player_id = extract_player_id(player_link.get("href", ""))

    # Photo joueur
    photo = ""
    for img in row.select("img"):
        src = img.get("src", "") or img.get("data-src", "")
        if "img_data/players" in src or "resfu.com" in src:
            photo = clean_logo(src)
            break
    if not photo and player_id:
        photo = f"https://cdn.resfu.com/img_data/players/medium/{player_id}.jpg?size=120x&lossy=1"

    # Club adverse + logo
    other_club_name = ""
    other_club_logo = ""
    for a in row.select("a[href*='/team/']"):
        href = a.get("href", "")
        # Ignorer le club algérien lui-même
        if club["slug"] in href:
            continue
        other_club_name = a.get_text(strip=True)
        img_adj = a.find("img")
        if img_adj:
            src = img_adj.get("src", "") or img_adj.get("data-src", "")
            other_club_logo = clean_logo(src)
        break

    # Fallback nom club adverse depuis texte
    if not other_club_name:
        m = re.search(r"(?:de|depuis|vers|→|->|from|to)\s+([A-ZÀ-Ü][^|•\n]{2,40})", text)
        if m:
            other_club_name = m.group(1).strip()

    transfer_type = parse_transfer_type(text)
    montant       = parse_amount(text)

    # Logo du club algérien : API-sports en fallback
    club_logo = club.get("api_logo", "")

    return {
        "id":             make_uid(club["name"], player_name, direction, season),
        "season":         season,
        "club_source":    club["name"],
        "club_logo":      club_logo,
        "player_name":    player_name,
        "player_id":      player_id or "",
        "photo":          photo,
        "direction":      direction,
        "club_depart":    club["name"]    if direction == "out" else other_club_name,
        "club_arrivee":   other_club_name if direction == "out" else club["name"],
        "club_dest_logo": other_club_logo,
        "type":           transfer_type,
        "montant":        montant,
        "scraped_at":     datetime.now(timezone.utc).isoformat(),
    }

# ══════════════════════════════════════════════
# SCRAPE UN CLUB
# ══════════════════════════════════════════════

def scrape_club_transfers(club, season):
    """
    URL BeSoccer : /team/transfers/{slug}/{bs_id}/{season}
    Structure HTML : sections "Altas" (in) et "Bajas" (out)
    avec des <li> ou <tr> pour chaque joueur.
    """
    # URL principale avec bs_id
    url = f"https://www.besoccer.com/team/transfers/{club['slug']}/{club['bs_id']}/{season}"
    r = fetch(url)
    if not r:
        # Fallback sans bs_id
        url = f"https://www.besoccer.com/team/transfers/{club['slug']}/{season}"
        r = fetch(url)
        if not r:
            print(f"  ⚠️ Impossible de charger la page pour {club['name']}")
            return []

    soup = BeautifulSoup(r.text, "html.parser")
    transfers = []

    # BeSoccer utilise des sections avec titres "Altas" / "Bajas"
    # On cherche tous les h2/h3/h4 pour détecter le sens du courant
    current_dir = None
    for tag in soup.find_all(["h2", "h3", "h4", "div"]):
        classes = " ".join(tag.get("class", []))
        txt = tag.get_text(strip=True).lower()

        # Détection titre de section
        is_title = tag.name in ["h2", "h3", "h4"] or "title" in classes or "panel-title" in classes
        if not is_title:
            continue

        if any(w in txt for w in ["alta", "arrivée", "llegada", "entradas", "signing"]):
            current_dir = "in"
        elif any(w in txt for w in ["baja", "départ", "salida", "salidas", "leaving"]):
            current_dir = "out"

        if current_dir:
            # Chercher les rows dans le bloc suivant
            sibling = tag.find_next_sibling()
            while sibling:
                for row in sibling.select("li, tr"):
                    t = parse_transfer_row(row, club, season, current_dir)
                    if t:
                        transfers.append(t)
                sibling = sibling.find_next_sibling()
                # S'arrêter si on tombe sur un nouveau titre
                if sibling and sibling.name in ["h2", "h3", "h4"]:
                    break

    # Fallback : scan linéaire si les titres n'ont rien donné
    if not transfers:
        current_dir = None
        for tag in soup.find_all(True):
            if tag.name in ["h2", "h3", "h4"]:
                txt = tag.get_text(strip=True).lower()
                if any(w in txt for w in ["alta", "arrivée", "llegada", "entradas"]):
                    current_dir = "in"
                elif any(w in txt for w in ["baja", "départ", "salida", "salidas"]):
                    current_dir = "out"
                continue
            if current_dir and tag.name in ["li", "tr"]:
                # Éviter les doublons (les li imbriqués)
                if tag.find_parent(["li", "tr"]):
                    continue
                t = parse_transfer_row(tag, club, season, current_dir)
                if t:
                    transfers.append(t)

    # Déduplication
    seen = set()
    unique = []
    for t in transfers:
        if t["id"] not in seen:
            seen.add(t["id"])
            unique.append(t)

    print(f"  → {len(unique)} transfert(s) pour {club['name']}")
    return unique

# ══════════════════════════════════════════════
# SUPABASE UPSERT
# ══════════════════════════════════════════════

def upsert_transfers(rows):
    if not rows:
        return
    res = requests.post(
        SB_URL + "/rest/v1/algeria_transfers",
        headers=SB_HEADERS,
        json=rows,
        timeout=20
    )
    code = res.status_code
    if code in (200, 201, 204):
        print(f"  ✅ Supabase OK ({len(rows)} lignes)")
    else:
        print(f"  ❌ Supabase {code}: {res.text[:300]}")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

print("=== BeSoccer Transfers — Ligue 1 Algérie ===")
print(f"Saison : {SEASON}")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

all_transfers = []

for club in CLUBS:
    print(f"\n[{club['name']}]")
    try:
        rows = scrape_club_transfers(club, SEASON)
        if rows:
            upsert_transfers(rows)
            all_transfers.extend(rows)
    except Exception as e:
        print(f"  ⚠️ Exception: {e}")
    time.sleep(2)

print(f"\n=== TOTAL : {len(all_transfers)} transferts ===")

# Artifact debug pour GitHub Actions
with open("transfers_debug.json", "w", encoding="utf-8") as f:
    json.dump(all_transfers, f, ensure_ascii=False, indent=2)
print("Debug JSON : transfers_debug.json")