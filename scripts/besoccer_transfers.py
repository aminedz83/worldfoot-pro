#!/usr/bin/env python3
"""
besoccer_transfers.py
=====================
Scrape les transferts Ligue 1 Algérie depuis BeSoccer.
Stocke dans Supabase `algeria_transfers`.

Structure HTML réelle BeSoccer (vérifiée 19/04/2026) :
  - li.elem-title       → titre de section ("New signings" / "Transfers out")
  - li.sign-list        → une ligne de transfert
  - a[href*='/player/'] → lien joueur (dans sign-list)
  - div.data-transfer   → type + montant ("Transfer. 0,1M.€" / "Free transfer." / "Loan.")
  - a[href*='/team/']   → club adverse (dans sign-list)
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
# CLUBS — slugs + IDs BeSoccer réels
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
    return hashlib.md5(raw.encode()).hexdigest()[:16]

def parse_type_montant(data_transfer_text):
    """
    Exemples réels :
      'Transfer. 0,1M.€'  → type='Transfert', montant='0,1M.€'
      'Free transfer.'    → type='Libre', montant=''
      'Loan.'             → type='Prêt', montant=''
      'Released.'         → type='Résiliation', montant=''
      'Free agent.'       → type='Libre', montant=''
    """
    t = data_transfer_text.strip().lower()
    montant = ""

    # Extraire montant
    m = re.search(r"([\d,.]+\s*m\.?\s*[€$£]|[€$£]\s*[\d,.]+)", data_transfer_text, re.I)
    if m:
        montant = m.group(0).strip()

    if "free transfer" in t or "free agent" in t:
        return "Libre", montant
    if "loan" in t:
        return "Prêt", montant
    if "released" in t:
        return "Résiliation", montant
    if "end of loan" in t or "fin de prêt" in t:
        return "Fin de prêt", montant
    if "transfer" in t:
        return "Transfert", montant
    return "Transfert", montant

def clean_logo(src):
    if not src:
        return ""
    if src.startswith("//"):
        return "https:" + src
    return src

# ══════════════════════════════════════════════
# PARSE UNE PAGE DE TRANSFERTS
# ══════════════════════════════════════════════

# Mots-clés BeSoccer pour détecter direction
IN_KEYWORDS  = ["new signing", "new signings", "arrivals", "signings", "in"]
OUT_KEYWORDS = ["transfers out", "departures", "out", "left the club"]

def detect_direction(title_text):
    t = title_text.strip().lower()
    if any(w in t for w in OUT_KEYWORDS):
        return "out"
    if any(w in t for w in IN_KEYWORDS):
        return "in"
    return None

def scrape_club_transfers(club, season):
    url = f"https://www.besoccer.com/team/transfers/{club['slug']}/{club['bs_id']}/{season}"
    r = fetch(url)
    if not r:
        url = f"https://www.besoccer.com/team/transfers/{club['slug']}/{season}"
        r = fetch(url)
        if not r:
            print(f"  ⚠️ Page inaccessible pour {club['name']}")
            return []

    soup = BeautifulSoup(r.text, "html.parser")
    transfers = []
    current_dir = None

    # Itérer sur les <li> dans l'ordre du document
    # li.elem-title  → nouveau titre de section → met à jour current_dir
    # li.sign-list   → un transfert            → parser si current_dir connu
    for li in soup.select("li.elem-title, li.sign-list"):
        classes = li.get("class", [])

        # ── Titre de section ──────────────────────────────────────
        if "elem-title" in classes:
            title = li.get_text(strip=True)
            d = detect_direction(title)
            if d:
                current_dir = d
                print(f"  Section → {current_dir.upper()} : '{title}'")
            continue

        # ── Ligne de transfert ────────────────────────────────────
        if "sign-list" not in classes or current_dir is None:
            continue

        # Joueur
        player_link = li.select_one("a[href*='/player/']")
        if not player_link:
            continue
        player_href = player_link.get("href", "")
        player_id   = extract_player_id(player_href)
        # Le texte du lien joueur contient aussi date/type — prendre juste le nom
        # Structure : <p class="name">N. Benzid</p> dans le lien
        name_el = player_link.select_one("p.name") or player_link.select_one("p")
        if name_el:
            player_name = name_el.get_text(strip=True)
        else:
            # Fallback : premier texte avant la date
            raw = player_link.get_text("|", strip=True).split("|")[0]
            player_name = raw.strip()
        if not player_name or len(player_name) < 2:
            continue

        # Photo joueur
        photo = ""
        img = li.select_one("img[src*='img_data/players'], img[src*='resfu']")
        if img:
            photo = clean_logo(img.get("src", "") or img.get("data-src", ""))
        if not photo and player_id:
            photo = f"https://cdn.resfu.com/img_data/players/medium/{player_id}.jpg?size=120x&lossy=1"

        # Club adverse
        other_club_name = ""
        other_club_logo = ""
        for a in li.select("a[href*='/team/']"):
            href = a.get("href", "")
            if club["slug"] in href:
                continue
            other_club_name = a.get_text(strip=True)
            img_team = a.find("img")
            if img_team:
                other_club_logo = clean_logo(img_team.get("src","") or img_team.get("data-src",""))
            break

        # Type + montant depuis div.data-transfer
        transfer_type = "Transfert"
        montant       = ""
        dt = li.select_one("div.data-transfer")
        if dt:
            transfer_type, montant = parse_type_montant(dt.get_text(strip=True))

        uid = make_uid(club["name"], player_name, current_dir, season)

        transfers.append({
            "id":             uid,
            "season":         season,
            "club_source":    club["name"],
            "club_logo":      club["api_logo"],
            "player_name":    player_name,
            "player_id":      player_id or "",
            "photo":          photo,
            "direction":      current_dir,
            "club_depart":    club["name"]    if current_dir == "out" else other_club_name,
            "club_arrivee":   other_club_name if current_dir == "out" else club["name"],
            "club_dest_logo": other_club_logo,
            "type":           transfer_type,
            "montant":        montant,
            "scraped_at":     datetime.now(timezone.utc).isoformat(),
        })

    # Déduplication
    seen = set()
    unique = []
    for t in transfers:
        if t["id"] not in seen:
            seen.add(t["id"])
            unique.append(t)

    print(f"  → {len(unique)} transfert(s) [{club['name']}]")
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