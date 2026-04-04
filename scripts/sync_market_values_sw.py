import os, re, time, requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

SW_CLUBS = {
    "JS Kabylie":      {"sw_id": "Wfaskwf0", "slug": "kabylie"},
    "CR Belouizdad":   {"sw_id": "vNJLB2jP", "slug": "belouizdad"},
    "MC Alger":        {"sw_id": "tnY2Lfcp", "slug": "mc-alger"},
    "USM Alger":       {"sw_id": "zXBidj5t", "slug": "usm-alger"},
    "CS Constantine":  {"sw_id": "nBionu2l", "slug": "constantine"},
    "ES Setif":        {"sw_id": "EDgC6qYp", "slug": "setif"},
    "MC Oran":         {"sw_id": "CrCmB35M", "slug": "oran"},
    "ASO Chlef":       {"sw_id": "Aobolc96", "slug": "chlef"},
    "JS Saoura":       {"sw_id": "nimcBvel", "slug": "saoura"},
    "ES Ben Aknoun":   {"sw_id": "QmvZvxCB", "slug": "es-ben-aknoun"},
    "USM Khenchela":   {"sw_id": "lYuJtBj9", "slug": "khenchela"},
    "MB Rouissat":     {"sw_id": "hGHHy7Am", "slug": "rouisset"},
    "Paradou AC":      {"sw_id": "WIyffF3J", "slug": "paradou"},
    "ES Mostaganem":   {"sw_id": "j9T7TM2E", "slug": "mostaganem"},
    "MC El Bayadh":    {"sw_id": "S6H5xCS1", "slug": "el-bayadh"},
    "Olympique Akbou": {"sw_id": "dhMQsMOh", "slug": "olympique-akbou"},
}

def parse_market_value(text):
    if not text:
        return None
    text = text.strip().replace(" ", "").replace(",", ".")
    m = re.search(r'€?([\d.]+)\s*([kKmM]?)', text)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2).lower()
    if unit == 'k':
        return int(val * 1000)
    elif unit == 'm':
        return int(val * 1000000)
    return int(val)

def parse_contract_date(text):
    if not text:
        return None
    text = text.strip()
    for fmt in ["%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except:
            pass
    return None

def scrape_player_page(player_url):
    try:
        r = scraper.get("https://fr.soccerway.com" + player_url, timeout=15)
        if r.status_code != 200:
            return {}
        result = {}
        html = r.text

        # Valeur marchande
        mv_pattern = re.search(r'€\s*[\d,.]+\s*[kKmM]?', html)
        if mv_pattern:
            result["market_value"] = parse_market_value(mv_pattern.group())

        # Date de contrat
        # Stratégie: chercher TOUTES les dates >= 2020 sur la page
        # et prendre celle qui suit "contrat" ou "contract"
        contract_found = None

        # D'abord chercher avec mot-clé contrat (permet balises HTML entre les mots)
        for pat in [
            r"[Cc]ontrat.{0,200}?(\d{2}[./]\d{2}[./]\d{4})",
            r"[Cc]ontract.{0,200}?(\d{2}[./]\d{2}[./]\d{4})",
            r"[Jj]usqu.au.{0,100}?(\d{2}[./]\d{2}[./]\d{4})",
            r"[Ee]xpir.{0,100}?(\d{2}[./]\d{2}[./]\d{4})",
        ]:
            for m in re.finditer(pat, html, re.IGNORECASE | re.DOTALL):
                d = parse_contract_date(m.group(1).strip())
                if d:
                    year = int(d[:4])
                    # Contrat = date >= 2020, pas une date de naissance
                    if year >= 2020:
                        contract_found = d
                        break
            if contract_found:
                break

        # Fallback: chercher toutes les dates >= 2025 sur la page
        # (une date de contrat est forcément dans le futur proche)
        if not contract_found:
            for m in re.finditer(r"(\d{2}[./]\d{2}[./]\d{4})", html):
                d = parse_contract_date(m.group(1).strip())
                if d:
                    year = int(d[:4])
                    if year >= 2025:
                        contract_found = d
                        break

        if contract_found:
            result["contract_until"] = contract_found

        return result
    except Exception as e:
        print(f"    Erreur scrape: {e}")
        return {}

def get_squad_links(club_name, info):
    url = f"https://fr.soccerway.com/equipe/{info['slug']}/{info['sw_id']}/"
    try:
        r = scraper.get(url, timeout=20)
        if r.status_code != 200:
            print(f"  ❌ {club_name}: status {r.status_code}")
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.find_all("a", href=re.compile(r"^/joueur/"))
        seen = set()
        players = []
        for lnk in links:
            href = lnk.get("href", "")
            name = lnk.get_text(strip=True)
            if href and href not in seen and name:
                seen.add(href)
                parts = href.strip("/").split("/")
                if len(parts) >= 3:
                    players.append({
                        "name": name,
                        "sw_url": href,
                        "sw_player_id": parts[2]
                    })
        print(f"  ✅ {club_name}: {len(players)} joueurs")
        return players
    except Exception as e:
        print(f"  ❌ {club_name}: {e}")
        return []

print("=== Sync Valeurs Marchandes (Soccerway) ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# Test Supabase connection
print("\n🔌 Test connexion Supabase...")
test = requests.get(
    SB_URL + "/rest/v1/algeria_market_values?limit=1&select=id,sw_player_id",
    headers=SB_HEADERS
)
print(f"  Status: {test.status_code}, Body: {test.text[:200]}")

total_updated = 0
total_errors = 0

for club_name, info in SW_CLUBS.items():
    print(f"\n📋 {club_name}")
    players = get_squad_links(club_name, info)
    if not players:
        continue

    for p in players:
        try:
            print(f"  👤 {p['name']} ({p['sw_player_id']})", end=" ", flush=True)

            # Scraper la page joueur
            data = scrape_player_page(p["sw_url"])
            time.sleep(0.3)

            record = {
                "tm_id": p["sw_player_id"],
                "sw_player_id": p["sw_player_id"],
                "sw_url": p["sw_url"],
                "name": p["name"],
                "team": club_name,
                "market_value": data.get("market_value"),
                "contract_until": data.get("contract_until"),
                "scraped_at": datetime.now(timezone.utc).isoformat()
            }

            res = requests.post(
                SB_URL + "/rest/v1/algeria_market_values",
                headers=SB_HEADERS,
                json=record
            )

            if res.status_code in [200, 201]:
                mv = data.get("market_value", "?")
                ct = data.get("contract_until", "?")
                print(f"→ ✅ MV={mv} | contrat={ct}")
                total_updated += 1
            else:
                print(f"→ ❌ {res.status_code}: {res.text[:300]}")
                total_errors += 1

        except Exception as e:
            print(f"→ ❌ EXCEPTION: {e}")
            total_errors += 1

print(f"\n=== Terminé: {total_updated} mis à jour, {total_errors} erreurs ===")