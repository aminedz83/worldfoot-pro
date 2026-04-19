#!/usr/bin/env python3
"""
besoccer_transfers.py
=====================
Scrape les transferts Ligue 1 Algérie depuis BeSoccer.
Stocke dans Supabase `algeria_transfers`.

Structure HTML réelle (vérifiée 19/04/2026) :
  div.signing-season.transfer-new
    div.panel
      table > tr > td.w-50p.va-t.br-right  → colonne IN (arrivées)
                   td.w-50p.va-t            → colonne OUT (départs)
        ul.item-list
          li.sign-list
            a.item-box[href=/player/...]
              div.row-img.player > img      → photo joueur
              div.left-content
                p.pl-name                   → nom joueur
                p.date                      → date
              div.right-content.data-box
                div.row-img.shield > img    → logo club adverse (alt=nom)
                div.data-transfer           → type + montant
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
# CLUBS
# ══════════════════════════════════════════════

CLUBS = [
    {"name": "MC Alger",        "slug": "mc-alger",       "bs_id": 11505, "api_logo": "https://media.api-sports.io/football/teams/906.png"},
    {"name": "CR Belouizdad",   "slug": "belouizdad",     "bs_id": 11507, "api_logo": "https://media.api-sports.io/football/teams/904.png"},
    {"name": "JS Kabylie",      "slug": "kabylie",        "bs_id": 11506, "api_logo": "https://media.api-sports.io/football/teams/918.png"},
    {"name": "USM Alger",       "slug": "usm-alger",      "bs_id": 11504, "api_logo": "https://media.api-sports.io/football/teams/910.png"},
    {"name": "ES Setif",        "slug": "es-setif",       "bs_id": 11501, "api_logo": "https://media.api-sports.io/football/teams/905.png"},
    {"name": "CS Constantine",  "slug": "cs-constantine", "bs_id": 11510, "api_logo": "https://media.api-sports.io/football/teams/911.png"},
    {"name": "Paradou AC",      "slug": "paradou",        "bs_id": 59336, "api_logo": "https://media.api-sports.io/football/teams/915.png"},
    {"name": "ASO Chlef",       "slug": "chlef",          "bs_id": 11511, "api_logo": "https://media.api-sports.io/football/teams/925.png"},
    {"name": "MC Oran",         "slug": "mc-oran",        "bs_id": 11509, "api_logo": "https://media.api-sports.io/football/teams/907.png"},
    {"name": "JS Saoura",       "slug": "js-saoura",      "bs_id": 20933, "api_logo": "https://media.api-sports.io/football/teams/914.png"},
    {"name": "MC El Bayadh",    "slug": "el-bayadh",      "bs_id": 11729, "api_logo": ""},
    {"name": "USM Khenchela",   "slug": "usm-khenchela",  "bs_id": 11530, "api_logo": ""},
    {"name": "Olympique Akbou", "slug": "oued-akbou",     "bs_id": 11522, "api_logo": ""},
    {"name": "ES Mostaganem",   "slug": "es-mostaganem",  "bs_id": 13715, "api_logo": ""},
    {"name": "MB Rouissat",     "slug": "mb-rouisset",    "bs_id": 100882,"api_logo": ""},
    {"name": "ES Ben Aknoun",   "slug": "ben-aknoun",     "bs_id": 11519, "api_logo": ""},
]

# ══════════════════════════════════════════════
# CLOUDSCRAPER
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
    return int(hashlib.md5(raw.encode()).hexdigest()[:15], 16)

def parse_type_montant(dt_text):
    """
    Textes réels BeSoccer :
      'Transfer.'          → Transfert
      'Transfer.0,1M.€'    → Transfert, 0,1M.€
      'Free transfer.'     → Libre
      'Free agent.'        → Libre
      'Loan.'              → Prêt
      'Released.'          → Résiliation
      'End of loan.'       → Fin de prêt
    """
    t = dt_text.strip().lower()
    m = re.search(r"([\d,.]+\s*m\.?\s*[€$£])", dt_text, re.I)
    montant = m.group(1).strip() if m else ""

    if "end of loan" in t or "fin de prêt" in t:
        return "Fin de prêt", montant
    if "free transfer" in t or "free agent" in t:
        return "Libre", montant
    if "loan" in t:
        return "Prêt", montant
    if "released" in t:
        return "Résiliation", montant
    if "transfer" in t:
        return "Transfert", montant
    return "Transfert", montant

def clean_src(src):
    if not src:
        return ""
    return "https:" + src if src.startswith("//") else src

def parse_sign_list(li, direction, club, season):
    """Parse un li.sign-list en dict transfert."""
    # Lien joueur
    a = li.select_one("a.item-box[href*='/player/']")
    if not a:
        return None

    player_href = a.get("href", "")
    player_id   = extract_player_id(player_href)

    # Nom : p.pl-name
    name_el = a.select_one("p.pl-name")
    if not name_el:
        return None
    player_name = name_el.get_text(strip=True)
    if not player_name:
        return None

    # Photo joueur : div.row-img.player > img
    photo = ""
    player_img = a.select_one("div.row-img.player img")
    if player_img:
        photo = clean_src(player_img.get("src", "") or player_img.get("data-src", ""))
    if not photo and player_id:
        photo = f"https://cdn.resfu.com/img_data/players/medium/{player_id}.jpg?size=120x&lossy=1"

    # Club adverse : div.row-img.shield > img  (alt = nom du club)
    other_club_name = ""
    other_club_logo = ""
    shield_img = a.select_one("div.row-img.shield img")
    if shield_img:
        other_club_name = shield_img.get("alt", "").strip()
        other_club_logo = clean_src(shield_img.get("src", "") or shield_img.get("data-src", ""))

    # Type + montant : div.data-transfer
    transfer_type = "Transfert"
    montant       = ""
    dt = a.select_one("div.data-transfer")
    if dt:
        transfer_type, montant = parse_type_montant(dt.get_text(strip=True))

    uid = make_uid(club["name"], player_name, direction, season)

    return {
        "id":             uid,
        "season":         season,
        "club_source":    club["name"],
        "club_logo":      club["api_logo"],
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
    url = f"https://www.besoccer.com/team/transfers/{club['slug']}/{club['bs_id']}/{season}"
    r = fetch(url)
    if not r:
        url = f"https://www.besoccer.com/team/transfers/{club['slug']}/{season}"
        r = fetch(url)
        if not r:
            print(f"  ⚠️ Page inaccessible")
            return []

    soup = BeautifulSoup(r.text, "html.parser")
    transfers = []

    # Structure : table > tr > td.br-right (IN) | td sans br-right (OUT)
    # Chaque td contient un ul.item-list > li.sign-list
    for tr in soup.select("div.signing-season table tr"):
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue

        for td in tds:
            classes = td.get("class", [])
            # td.br-right = colonne gauche = IN (arrivées)
            # td sans br-right = colonne droite = OUT (départs)
            direction = "in" if "br-right" in classes else "out"

            for li in td.select("li.sign-list"):
                t = parse_sign_list(li, direction, club, season)
                if t:
                    transfers.append(t)

    # Déduplication
    seen = set()
    unique = []
    for t in transfers:
        if t["id"] not in seen:
            seen.add(t["id"])
            unique.append(t)

    in_count  = sum(1 for t in unique if t["direction"] == "in")
    out_count = sum(1 for t in unique if t["direction"] == "out")
    print(f"  → {len(unique)} transfert(s) : {in_count} IN / {out_count} OUT")
    return unique

# ══════════════════════════════════════════════
# SUPABASE
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

with open("transfers_debug.json", "w", encoding="utf-8") as f:
    json.dump(all_transfers, f, ensure_ascii=False, indent=2)
print("Debug JSON : transfers_debug.json")