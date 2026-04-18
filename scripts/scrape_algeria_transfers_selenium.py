"""
scrape_algeria_transfers_selenium.py
=====================================
Scrape les transferts Ligue 1 Algérie depuis fr.besoccer.com.
Utilise Selenium + Chrome headless (compatible GitHub Actions).
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

BASE_URL = "https://fr.besoccer.com/competition/transfers/algeria-league-one"

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

def fetch_with_selenium(url, timeout=45):
    driver = create_driver()
    try:
        print(f"  🌐 Ouverture : {url}")
        driver.get(url)

        # Attendre que #transfers-panel soit présent dans le DOM
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#transfers-panel .panel-head"))
            )
            print(f"  ✅ #transfers-panel chargé")
        except Exception:
            print(f"  ⚠️  Timeout sur #transfers-panel — attente supplémentaire")
            time.sleep(8)

        # Scroll pour forcer le lazy-load
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)

        html = driver.page_source
        print(f"  📄 HTML size: {len(html)} chars")
        return html

    except Exception as e:
        print(f"  ❌ Erreur Selenium : {e}")
        return None
    finally:
        driver.quit()

def parse_transfers(html, season):
    soup      = BeautifulSoup(html, "html.parser")
    transfers = []

    club_sections = soup.select("#transfers-panel .panel-head")
    if not club_sections:
        club_sections = soup.select(".signing-season .panel-head")
    if not club_sections:
        club_sections = soup.select(".transfer-new .panel-head")

    print(f"  🏟️  {len(club_sections)} clubs trouvés")

    for section in club_sections:
        club_img  = section.select_one("img")
        club_name = club_img.get("alt", "") if club_img else ""
        club_logo = club_img.get("src", "") if club_img else ""
        body      = section.find_next_sibling("div", class_="panel-body")
        if not body: continue

        halves = body.select("td.w-50p")
        for half_idx, half in enumerate(halves):
            direction = "in" if half_idx == 0 else "out"
            for li in half.select("li.sign-list a.item-box"):
                player_img  = li.select_one(".row-img img")
                player_href = li.get("href", "")
                pid         = re.search(r"-(\d+)/?$", player_href)
                img_alt     = player_img.get("alt", "") if player_img else ""
                # Nettoyage FR + EN
                player_name = re.sub(
                    r"^(Transfert gratuit|Transfert|Prêt|Free transfer|Loan|Transfer)\s+",
                    "", img_alt, flags=re.I
                ).strip()
                photo       = player_img.get("src", "") if player_img else ""
                player_id   = pid.group(1) if pid else ""
                dest_img    = li.select_one(".right-content img, .shield img")
                dest_name   = dest_img.get("alt", "") if dest_img else ""
                dest_logo   = dest_img.get("src", "") if dest_img else ""
                data_box    = li.select_one(".data-transfer, .right-content.data-box")
                fee_type, montant = "", None
                if data_box:
                    texts = [p.get_text(strip=True) for p in data_box.select("p") if p.get_text(strip=True)]
                    if texts: fee_type = texts[0].rstrip(".")
                    if len(texts) > 1 and texts[1]: montant = texts[1]
                if not player_name: continue
                if direction == "in":
                    club_depart, club_arrivee = dest_name, club_name
                else:
                    club_depart, club_arrivee = club_name, dest_name
                transfers.append({
                    "season":          season,
                    "player_name":     player_name,
                    "player_id":       player_id,
                    "photo":           photo,
                    "direction":       direction,
                    "club_source":     club_name,
                    "club_logo":       club_logo,
                    "club_depart":     club_depart,
                    "club_arrivee":    club_arrivee,
                    "club_dest_logo":  dest_logo,
                    "type":            fee_type,
                    "montant":         montant,
                })
    return transfers

def save_to_supabase(records):
    if not records:
        print("  ⚠️  Aucun transfert à sauvegarder")
        return
    now  = datetime.now(timezone.utc).isoformat()
    rows = [{**r, "scraped_at": now} for r in records]
    total_ok = 0
    for i in range(0, len(rows), 100):
        batch = rows[i:i+100]
        res   = requests.post(
            SB_URL + "/rest/v1/algeria_transfers",
            headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
            params={"on_conflict": "season,player_id,club_source,direction"},
            json=batch
        )
        if res.status_code in [200, 201, 204]: total_ok += len(batch)
        else: print(f"  ❌ Supabase {res.status_code}: {res.text[:200]}")
    print(f"  ✅ Supabase: {total_ok}/{len(rows)} transferts sauvegardés")

# ── MAIN ──────────────────────────────────────
print("=== BeSoccer Algeria Transfers Scraper (Selenium) ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

today  = date.today()
season = today.year + 1 if today.month >= 8 else today.year
print(f"\nSaison: {season}")

html = fetch_with_selenium(f"{BASE_URL}/{season}")
if not html:
    print("❌ Impossible de charger la page")
    sys.exit(1)

transfers = parse_transfers(html, season)
print(f"\n📊 {len(transfers)} transferts trouvés")

if transfers:
    filename = f"algeria_transfers_{season}_{today.strftime('%Y-%m-%d')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(transfers, f, ensure_ascii=False, indent=2)
    print(f"💾 JSON : {filename}")
    print("💾 Sauvegarde Supabase...")
    save_to_supabase(transfers)
else:
    print("⚠️  0 transferts — structure de la page peut-être changée")

print("\n=== Terminé ===")