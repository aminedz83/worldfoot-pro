import requests
from bs4 import BeautifulSoup
import os
import time
import re
import json

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# Clubs Ligue 1 algérienne : API football ID → URL slug Transfermarkt
CLUBS = {
    918:  {"name": "JS Kabylie",        "tm_id": "3455",  "slug": "js-kabylie"},
    904:  {"name": "CR Belouizdad",     "tm_id": "3456",  "slug": "cr-belouizdad"},
    906:  {"name": "MC Alger",          "tm_id": "3457",  "slug": "mc-alger"},
    910:  {"name": "USM Alger",         "tm_id": "3459",  "slug": "usm-alger"},
    908:  {"name": "ES Setif",          "tm_id": "3461",  "slug": "es-setif"},
    916:  {"name": "CS Constantine",    "tm_id": "14280", "slug": "cs-constantine"},
    907:  {"name": "MC Oran",           "tm_id": "14281", "slug": "mc-oran"},
    905:  {"name": "ASO Chlef",         "tm_id": "14282", "slug": "aso-chlef"},
    917:  {"name": "JS Saoura",         "tm_id": "64706", "slug": "js-saoura"},
    919:  {"name": "ES Ben Aknoun",     "tm_id": "87944", "slug": "es-ben-aknoun"},
    920:  {"name": "USM Khenchela",     "tm_id": "87945", "slug": "usm-khenchela"},
    921:  {"name": "MB Rouissat",       "tm_id": "87946", "slug": "mb-rouissat"},
    922:  {"name": "Paradou AC",        "tm_id": "19718", "slug": "paradou-ac"},
    923:  {"name": "ES Mostaganem",     "tm_id": "87947", "slug": "es-mostaganem"},
    924:  {"name": "MC El Bayadh",      "tm_id": "87948", "slug": "mc-el-bayadh"},
    925:  {"name": "Olympique Akbou",   "tm_id": "87949", "slug": "olympique-akbou"},
}

SEASON = "2024"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.transfermarkt.com/",
    "Cache-Control": "no-cache",
}

def parse_market_value(mv_str):
    """Convertit '500 Th. €' ou '1,00 Mio. €' en entier euros"""
    if not mv_str:
        return None
    s = mv_str.strip().replace("\xa0", " ")
    try:
        if "Mio" in s or "M" in s:
            num = re.search(r"[\d,\.]+", s)
            if num:
                return int(float(num.group().replace(",", ".")) * 1000000)
        if "Th" in s or "K" in s or "k" in s:
            num = re.search(r"[\d,\.]+", s)
            if num:
                return int(float(num.group().replace(",", ".")) * 1000)
    except:
        pass
    return None

def scrape_club_players(tm_id, slug, club_name):
    url = f"https://www.transfermarkt.com/{slug}/kader/verein/{tm_id}/saison_id/{SEASON}/plus/1"
    print(f"  URL: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"  Status: {r.status_code}")
        if r.status_code != 200:
            print(f"  Body: {r.text[:200]}")
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        players = []

        # Tableau des joueurs dans Transfermarkt
        table = soup.find("table", {"class": lambda c: c and "items" in c})
        if not table:
            print(f"  Tableau non trouvé — vérifier la structure HTML")
            # Debug: afficher les classes de tables trouvées
            for t in soup.find_all("table")[:3]:
                print(f"  Table classe: {t.get('class')}")
            return []

        rows = table.find("tbody").find_all("tr", {"class": ["odd", "even"]})
        print(f"  Lignes trouvées: {len(rows)}")

        for row in rows:
            try:
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue

                # Numéro de maillot
                shirt = cells[0].get_text(strip=True) or None

                # Nom du joueur
                name_cell = row.find("td", {"class": "hauptlink"})
                name = name_cell.get_text(strip=True) if name_cell else None
                if not name:
                    continue

                # Lien pour récupérer l'ID TM du joueur
                link = name_cell.find("a") if name_cell else None
                player_tm_id = None
                if link and link.get("href"):
                    m = re.search(r"/(\d+)$", link["href"])
                    if m:
                        player_tm_id = m.group(1)

                # Position
                pos_cell = row.find("td", {"class": "posrela"})
                if not pos_cell:
                    pos_cells = [c for c in cells if c.get("class") and "zentriert" not in c.get("class", [])]
                position = None
                if pos_cell:
                    pos_tag = pos_cell.find("table")
                    if pos_tag:
                        position = pos_tag.find_all("tr")[-1].get_text(strip=True) if pos_tag.find_all("tr") else None

                # Age
                age = None
                for cell in cells:
                    txt = cell.get_text(strip=True)
                    if re.match(r"^\d{2}$", txt) and 15 <= int(txt) <= 45:
                        age = int(txt)
                        break

                # Valeur marchande — dernière colonne avec €
                mv = None
                for cell in reversed(cells):
                    txt = cell.get_text(strip=True)
                    if "€" in txt or "Mio" in txt or "Th." in txt:
                        mv = parse_market_value(txt)
                        break

                # Nationalité — drapeau img alt
                nat = None
                nat_imgs = row.find_all("img", {"class": lambda c: c and "flaggenrahmen" in str(c)})
                if not nat_imgs:
                    nat_imgs = row.find_all("img", title=True)
                if nat_imgs:
                    nat = nat_imgs[0].get("title") or nat_imgs[0].get("alt")

                if name:
                    players.append({
                        "tm_id":         player_tm_id or f"{tm_id}_{shirt}",
                        "api_team_id":   None,  # rempli après
                        "name":          name,
                        "short_name":    name,
                        "position":      position,
                        "shirt_number":  int(shirt) if shirt and shirt.isdigit() else None,
                        "market_value":  mv,
                        "contract_until": None,
                        "nationality":   nat,
                        "age":           age,
                    })
            except Exception as e:
                print(f"  Erreur ligne: {e}")
                continue

        return players

    except Exception as e:
        print(f"  Erreur scrape: {e}")
        return []

def upsert_supabase(rows):
    if not rows:
        return
    url = f"{SUPABASE_URL}/rest/v1/algeria_market_values"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    r = requests.post(url, headers=headers, json=rows, timeout=30)
    print(f"  Supabase: {r.status_code} — {len(rows)} joueurs")
    if r.status_code not in (200, 201):
        print(f"  Erreur: {r.text[:300]}")

def main():
    print("=== Sync Market Values Transfermarkt (scraping direct) → Supabase ===\n")

    total = 0
    for api_id, info in CLUBS.items():
        print(f"\n{info['name']} (API:{api_id} / TM:{info['tm_id']})")
        players = scrape_club_players(info["tm_id"], info["slug"], info["name"])

        if not players:
            time.sleep(3)
            continue

        print(f"  ✅ {len(players)} joueurs — ex: {players[0]['name']} MV={players[0]['market_value']}")

        rows = []
        for p in players:
            p["api_team_id"] = api_id
            rows.append(p)

        upsert_supabase(rows)
        total += len(rows)
        time.sleep(3)  # Pause polie entre clubs

    print(f"\n✅ Total: {total} joueurs synchronisés")

if __name__ == "__main__":
    main()