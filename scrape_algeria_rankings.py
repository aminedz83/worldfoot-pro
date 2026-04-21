"""
scrape_algeria_transfers_selenium.py
=====================================
Scrape les transferts Ligue 1 Algérie depuis fr.besoccer.com.
Utilise Selenium + Chrome headless (compatible GitHub Actions).

CORRECTIONS :
- URL : fr.besoccer.com (pas besoccer.com)
- Nom : p.pl-name (pas img alt qui donne toujours le même joueur)
- Contrainte unique : season,player_id,club_source,direction,date
"""

import os, re, sys, time, json, requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, date
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL       = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS   = {
    "apikey":        SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates"
}

BASE_URL = "https://fr.besoccer.com/competition/transferts/algeria-league-one"

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=fr-FR")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    try:
        driver = webdriver.Chrome(service=Service(), options=options)
    except Exception:
        from webdriver_manager.chrome import ChromeDriverManager
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def fetch_with_selenium(url, timeout=60):
    driver = create_driver()
    try:
        print(f"  Ouverture : {url}")
        driver.get(url)
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#transfers-panel .panel-head"))
            )
            print(f"  Contenu charge")
        except Exception:
            print(f"  Timeout — attente supplementaire")
            time.sleep(15)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        html = driver.page_source
        print(f"  HTML size: {len(html)} chars")
        return html
    except Exception as e:
        print(f"  Erreur Selenium : {e}")
        return None
    finally:
        driver.quit()

def parse_transfers(html, season):
    soup = BeautifulSoup(html, "html.parser")
    transfers = []
    club_sections = (
        soup.select("#transfers-panel .panel-head") or
        soup.select(".signing-season .panel-head") or
        soup.select(".transfer-new .panel-head")
    )
    print(f"  {len(club_sections)} clubs trouves")

    for section in club_sections:
        club_img  = section.select_one("img")
        club_name = club_img.get("alt", "").strip() if club_img else ""
        club_logo = club_img.get("src", "") if club_img else ""
        body      = section.find_next_sibling("div", class_="panel-body")
        if not body: continue

        halves = body.select("td.w-50p")
        for half_idx, half in enumerate(halves):
            direction = "in" if half_idx == 0 else "out"
            for li in half.select("li.sign-list a.item-box"):
                # NOM depuis p.pl-name UNIQUEMENT
                name_el     = li.select_one("p.pl-name")
                player_name = name_el.get_text(strip=True) if name_el else ""
                if not player_name: continue

                date_el    = li.select_one("p.date")
                date_str   = date_el.get_text(strip=True) if date_el else ""
                player_img = li.select_one(".row-img.player img")
                photo      = player_img.get("src", "") if player_img else ""
                player_href = li.get("href", "")
                pid        = re.search(r"-(\d+)/?$", player_href)
                player_id  = pid.group(1) if pid else ""
                shield_img = li.select_one(".right-content .shield img")
                dest_name  = shield_img.get("alt", "").strip() if shield_img else ""
                dest_logo  = shield_img.get("src", "") if shield_img else ""
                data_box   = li.select_one(".data-transfer")
                fee_type, montant = "", None
                if data_box:
                    paras = [p.get_text(strip=True) for p in data_box.select("p") if p.get_text(strip=True)]
                    if paras: fee_type = paras[0].rstrip(".")
                    if len(paras) > 1 and paras[1]: montant = paras[1]

                if direction == "in":
                    club_depart, club_arrivee = dest_name, club_name
                else:
                    club_depart, club_arrivee = club_name, dest_name

                transfers.append({
                    "season": season, "date": date_str,
                    "player_name": player_name, "player_id": player_id,
                    "photo": photo, "direction": direction,
                    "club_source": club_name, "club_logo": club_logo,
                    "club_depart": club_depart, "club_arrivee": club_arrivee,
                    "club_dest_logo": dest_logo, "type": fee_type, "montant": montant,
                })
    return transfers

def save_to_supabase(records):
    if not records:
        print("  Aucun transfert a sauvegarder")
        return
    now  = datetime.now(timezone.utc).isoformat()
    rows = [{**r, "scraped_at": now} for r in records]
    total_ok = 0
    for i in range(0, len(rows), 100):
        batch = rows[i:i+100]
        res   = requests.post(
            SB_URL + "/rest/v1/algeria_transfers",
            headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
            params={"on_conflict": "season,player_id,club_source,direction,date"},
            json=batch
        )
        if res.status_code in [200, 201, 204]: total_ok += len(batch)
        else: print(f"  Supabase {res.status_code}: {res.text[:200]}")
    print(f"  Supabase: {total_ok}/{len(rows)} transferts sauvegardes")

print("=== BeSoccer Algeria Transfers Scraper (Selenium) ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

today  = date.today()
season = today.year + 1 if today.month >= 8 else today.year
print(f"\nSaison: {season}")

html = fetch_with_selenium(f"{BASE_URL}/{season}")
if not html or len(html) < 100000:
    print("Page incomplete ou inaccessible")
    sys.exit(1)

transfers = parse_transfers(html, season)
print(f"\n{len(transfers)} transferts trouves")

if transfers:
    filename = f"algeria_transfers_{season}_{today.strftime('%Y-%m-%d')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(transfers, f, ensure_ascii=False, indent=2)
    print(f"JSON : {filename}")
    save_to_supabase(transfers)
else:
    print("0 transferts — BeSoccer bloque la requete")

print("\n=== Termine ===")