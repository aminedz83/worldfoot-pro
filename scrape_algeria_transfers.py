"""
scrape_algeria_transfers.py
============================
Scrape les transferts Ligue 1 Algérie depuis Flashscore.

MODE 1 — Tous les transferts (vue globale ligue) :
    python3 scrape_algeria_transfers.py --mode all

MODE 2 — Transferts par club :
    python3 scrape_algeria_transfers.py --mode clubs

Sauvegarde : Supabase table algeria_transfers + JSON local
"""

import os, re, sys, time, json, argparse, requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone, date

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

BASE_FLASHSCORE = "https://www.flashscore.fr"

# Clubs Ligue 1 Algérie avec leurs slugs et IDs Flashscore
CLUBS = [
    {"name": "JS Kabylie",       "slug": "kabylie",        "id": "Wfaskwf0"},
    {"name": "CR Belouizdad",    "slug": "belouizdad",     "id": "vNJLB2jP"},
    {"name": "MC Alger",         "slug": "mc-alger",       "id": "tnY2Lfcp"},
    {"name": "USM Alger",        "slug": "usm-alger",      "id": "zXBidj5t"},
    {"name": "CS Constantine",   "slug": "constantine",    "id": "nBionu2l"},
    {"name": "ES Setif",         "slug": "setif",          "id": "EDgC6qYp"},
    {"name": "MC Oran",          "slug": "mc-oran",        "id": "CrCmB35M"},
    {"name": "ASO Chlef",        "slug": "chlef",          "id": "Aobolc96"},
    {"name": "JS Saoura",        "slug": "saoura",         "id": "nimcBvel"},
    {"name": "ES Ben Aknoun",    "slug": "ben-aknoun",     "id": "QmvZvxCB"},
    {"name": "USM Khenchela",    "slug": "khenchela",      "id": "lYuJtBj9"},
    {"name": "MB Rouissat",      "slug": "rouissat",       "id": "hGHHy7Am"},
    {"name": "Paradou AC",       "slug": "paradou",        "id": "WIyffF3J"},
    {"name": "ES Mostaganem",    "slug": "mostaganem",     "id": "j9T7TM2E"},
    {"name": "MC El Bayadh",     "slug": "el-bayadh",      "id": "S6H5xCS1"},
    {"name": "Olympique Akbou",  "slug": "akbou",          "id": "dhMQsMOh"},
]

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# ══════════════════════════════════════════════
# FETCH AVEC RETRY
# ══════════════════════════════════════════════

def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            r = scraper.get(url, timeout=30)
            if r.status_code == 200:
                print(f"  ✅ GET 200 : {url}")
                return r
            print(f"  ⚠️  GET {r.status_code} (tentative {attempt+1}/{retries})")
        except Exception as e:
            print(f"  ❌ Erreur (tentative {attempt+1}/{retries}) : {e}")
        if attempt < retries - 1:
            time.sleep(3)
    print(f"  ❌ Échec après {retries} tentatives : {url}")
    return None

# ══════════════════════════════════════════════
# PARSER LES TRANSFERTS D'UNE PAGE HTML
# ══════════════════════════════════════════════

def parse_transfers(html, club_name=None):
    soup      = BeautifulSoup(html, "html.parser")
    rows      = soup.select("div.transferTab__row--team")
    transfers = []

    for row in rows:
        # Skip header row
        if "transferTab__row--main" in row.get("class", []):
            continue

        # Date
        date_el = row.select_one(".transferTab__date")
        date_raw = date_el.get_text(strip=True) if date_el else ""

        # Joueur
        player_el   = row.select_one(".transferTab__teamHref")
        player_name = player_el.get_text(strip=True) if player_el else ""
        player_href = player_el.get("href", "") if player_el else ""
        # Extraire player_id depuis href ex: /equipe/nom-prenom/AbCdEfGh/
        pid_match   = re.search(r"/equipe/[^/]+/([^/]+)/?$", player_href)
        player_id   = pid_match.group(1) if pid_match else ""

        # Direction : IN ou OUT
        is_out = bool(row.select_one(".transferTab__typeIcon--out"))
        is_in  = bool(row.select_one(".transferTab__typeIcon--in"))

        # Club de destination/provenance
        team_el   = row.select_one(".transferTab__team .transferTab__teamName")
        team_name = team_el.get_text(strip=True) if team_el else ""

        # Logo club destination
        logo_el   = row.select_one(".transferTab__teamLogo image")
        team_logo = logo_el.get("href", "") if logo_el else ""

        # Montant
        fee_el   = row.select_one(".transferTab__feePrize")
        fee      = fee_el.get_text(strip=True) if fee_el else None
        if fee == "" or fee == "-":
            fee = None

        # Type de transfert
        fee_type_el = row.select_one(".transferTab__feePrizeType")
        fee_type    = fee_type_el.get_text(strip=True) if fee_type_el else ""

        # Construire club_depart / club_arrivee
        if club_name:
            if is_out:
                club_depart  = club_name
                club_arrivee = team_name
            else:
                club_depart  = team_name
                club_arrivee = club_name
        else:
            # Mode all : pas de club_name, on lit les deux colonnes
            clubs_el = row.select(".transferTab__team .transferTab__teamName")
            if len(clubs_el) >= 2:
                club_depart  = clubs_el[0].get_text(strip=True)
                club_arrivee = clubs_el[1].get_text(strip=True)
            elif is_out:
                club_depart  = ""
                club_arrivee = team_name
            else:
                club_depart  = team_name
                club_arrivee = ""

        if not player_name or not date_raw:
            continue

        transfers.append({
            "date":         date_raw,
            "player_name":  player_name,
            "player_id":    player_id,
            "direction":    "out" if is_out else "in",
            "club_depart":  club_depart,
            "club_arrivee": club_arrivee,
            "team_logo":    team_logo,
            "montant":      fee,
            "type":         fee_type,
            "club_source":  club_name or "",
        })

    return transfers

# ══════════════════════════════════════════════
# SUPABASE
# ══════════════════════════════════════════════

def save_to_supabase(records, season):
    if not records:
        return
    now  = datetime.now(timezone.utc).isoformat()
    rows = []
    for r in records:
        rows.append({
            "season":       season,
            "date":         r.get("date"),
            "player_name":  r.get("player_name"),
            "player_id":    r.get("player_id"),
            "direction":    r.get("direction"),
            "club_depart":  r.get("club_depart"),
            "club_arrivee": r.get("club_arrivee"),
            "team_logo":    r.get("team_logo"),
            "montant":      r.get("montant"),
            "type":         r.get("type"),
            "club_source":  r.get("club_source"),
            "scraped_at":   now,
        })

    batch_size = 100
    total_ok   = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        res = requests.post(
            SB_URL + "/rest/v1/algeria_transfers",
            headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
            params={"on_conflict": "season,player_id,club_depart,club_arrivee,date"},
            json=batch
        )
        if res.status_code in [200, 201, 204]:
            total_ok += len(batch)
        else:
            print(f"  ❌ Supabase {res.status_code}: {res.text[:200]}")

    print(f"  ✅ Supabase: {total_ok}/{len(rows)} transferts sauvegardés")

def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  💾 JSON : {filename}")

# ══════════════════════════════════════════════
# SAISON AUTO
# ══════════════════════════════════════════════

def get_season():
    today = date.today()
    return today.year + 1 if today.month >= 8 else today.year

# ══════════════════════════════════════════════
# MODE 1 — TOUS LES TRANSFERTS
# ══════════════════════════════════════════════

def mode_all():
    season = get_season()
    print(f"\n{'='*50}")
    print(f"MODE 1 — Tous les transferts Ligue 1 (saison {season})")
    print(f"{'='*50}")

    url = f"{BASE_FLASHSCORE}/football/algerie/ligue-1/transferts/"
    r   = fetch(url)
    if not r:
        print("❌ Page inaccessible")
        return

    transfers = parse_transfers(r.text)
    print(f"\n📊 {len(transfers)} transferts trouvés")

    today    = date.today().strftime("%Y-%m-%d")
    filename = f"transferts_ligue1_tous_{today}.json"
    save_json(transfers, filename)
    save_to_supabase(transfers, season)

    print(f"\n✅ Mode 1 terminé — {len(transfers)} transferts")

# ══════════════════════════════════════════════
# MODE 2 — PAR CLUB
# ══════════════════════════════════════════════

def mode_clubs():
    season = get_season()
    print(f"\n{'='*50}")
    print(f"MODE 2 — Transferts par club (saison {season})")
    print(f"{'='*50}")

    all_transfers = []

    for club in CLUBS:
        print(f"\n🔍 {club['name']}...")
        url = f"{BASE_FLASHSCORE}/equipe/{club['slug']}/{club['id']}/transferts/"
        r   = fetch(url)
        if not r:
            print(f"  ⚠️  Page inaccessible pour {club['name']}")
            time.sleep(2)
            continue

        transfers = parse_transfers(r.text, club_name=club["name"])
        print(f"  📊 {len(transfers)} transferts")
        all_transfers.extend(transfers)
        time.sleep(2)

    print(f"\n📊 Total : {len(all_transfers)} transferts sur {len(CLUBS)} clubs")

    today    = date.today().strftime("%Y-%m-%d")
    filename = f"transferts_ligue1_par_club_{today}.json"
    save_json(all_transfers, filename)
    save_to_supabase(all_transfers, season)

    print(f"\n✅ Mode 2 terminé — {len(all_transfers)} transferts")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

print("=== Flashscore Algeria Transfers Scraper ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=["all", "clubs"], default="clubs",
                    help="all = tous les transferts | clubs = par club")
args = parser.parse_args()

if args.mode == "all":
    mode_all()
else:
    mode_clubs()

print("\n=== Terminé ===")