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
    """Convertit '€309k' ou '€1.2m' en entier"""
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
    """Convertit '20.08.2028' ou '20/08/2028' en YYYY-MM-DD"""
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
    """
    Scrape la page joueur Soccerway et retourne
    {market_value, contract_until, position, nationality}
    """
    try:
        r = scraper.get("https://fr.soccerway.com" + player_url, timeout=15)
        if r.status_code != 200:
            return {}

        soup = BeautifulSoup(r.text, "html.parser")
        result = {}

        # Chercher la valeur marchande — span avec €
        mv_pattern = re.search(r'€\s*[\d,.]+\s*[kKmMmM]?', r.text)
        if mv_pattern:
            result["market_value"] = parse_market_value(mv_pattern.group())

        # Chercher le contrat — pattern date après "Contrat"
        contract_pattern = re.search(
            r'[Cc]ontrat[^:]*?:?\s*(?:jusqu[^\d]*)?(\d{2}[./]\d{2}[./]\d{4})',
            r.text
        )
        if contract_pattern:
            result["contract_until"] = parse_contract_date(contract_pattern.group(1))

        # Chercher aussi dans les spans wcl-scores
        for span in soup.find_all("span", {"data-testid": "wcl-scores-simple-text-01"}):
            txt = span.get_text(strip=True)
            if "€" in txt and "market_value" not in result:
                result["market_value"] = parse_market_value(txt)

        # Position
        pos_m = re.search(r'"type":"player_page"[^}]*"country":"([A-Z]+)"', r.text)
        if pos_m:
            result["nationality_code"] = pos_m.group(1)

        return result

    except Exception as e:
        print(f"    Erreur scrape_player_page: {e}")
        return {}

def get_squad_links(club_name, info):
    """Récupère tous les liens joueurs depuis la page effectif du club"""
    url = f"https://fr.soccerway.com/equipe/{info['slug']}/{info['sw_id']}/"
    try:
        r = scraper.get(url, timeout=20)
        if r.status_code != 200:
            print(f"  ❌ {club_name}: status {r.status_code}")
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.find_all("a", href=re.compile(r"^/joueur/"))

        # Dédupliquer
        seen = set()
        players = []
        for lnk in links:
            href = lnk.get("href", "")
            name = lnk.get_text(strip=True)
            if href and href not in seen and name:
                seen.add(href)
                # Extraire sw_player_id depuis l'URL /joueur/slug/ID/
                parts = href.strip("/").split("/")
                if len(parts) >= 3:
                    players.append({
                        "name": name,
                        "sw_url": href,
                        "sw_player_id": parts[2]  # ex: As8Cxr8H
                    })

        print(f"  ✅ {club_name}: {len(players)} joueurs trouvés")
        return players

    except Exception as e:
        print(f"  ❌ {club_name}: {e}")
        return []

print("=== Sync Valeurs Marchandes (Soccerway) ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

total_updated = 0
total_errors = 0

for club_name, info in SW_CLUBS.items():
    print(f"\n📋 {club_name}")
    players = get_squad_links(club_name, info)

    if not players:
        continue

    for p in players:
        try:
            print(f"  👤 {p['name']} ({p['sw_player_id']})", end=" ")

            # Vérifier si déjà à jour (scraped < 7 jours)
            check = requests.get(
                SB_URL + "/rest/v1/algeria_market_values"
                + "?sw_player_id=eq." + p["sw_player_id"]
                + "&select=id,scraped_at,market_value",
                headers=SB_HEADERS
            ).json()

            if check:
                scraped_at = check[0].get("scraped_at", "")
                if scraped_at:
                    age_days = (datetime.now(timezone.utc) -
                                datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
                               ).days
                    if age_days < 7:
                        mv = check[0].get("market_value")
                        print(f"→ skip (scraped il y a {age_days}j, MV={mv})")
                        continue

            # Scraper la page joueur
            data = scrape_player_page(p["sw_url"])
            time.sleep(0.5)  # pause pour ne pas surcharger

            record = {
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
                print(f"→ ❌ Supabase {res.status_code}: {res.text[:80]}")
                total_errors += 1

        except Exception as e:
            print(f"→ ❌ {e}")
            total_errors += 1

print(f"\n=== Terminé: {total_updated} mis à jour, {total_errors} erreurs ===")