"""
scrape_algeria_transfers_selenium.py
=====================================
Scrape les transferts Ligue 1 Algérie depuis fr.besoccer.com.
Utilise Selenium + Chrome headless (compatible GitHub Actions).
Cron : chaque lundi à 4h UTC
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

# URL française — contient tous les clubs de la ligue
BASE_URL = "https://fr.besoccer.com/competition/transferts/algeria-league-one"

# ══════════════════════════════════════════════
# SELENIUM
# ══════════════════════════════════════════════

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
    # Masquer Selenium au JS de BeSoccer
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def fetch_page(url, timeout=60):
    """Charge la page avec Selenium et attend que les transferts soient présents."""
    driver = create_driver()
    try:
        print(f"  🌐 Chargement : {url}")
        driver.get(url)

        # Attendre que le contenu JS soit chargé (#transfers-panel avec au moins un club)
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#transfers-panel .panel-head"))
            )
            print(f"  ✅ Contenu chargé")
        except Exception:
            print(f"  ⚠️  Timeout — attente supplémentaire de 15s")
            time.sleep(15)

        # Scroll bas → haut pour déclencher le lazy-load
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)

        html = driver.page_source
        print(f"  📄 Taille HTML : {len(html)} chars")
        return html

    except Exception as e:
        print(f"  ❌ Erreur Selenium : {e}")
        return None
    finally:
        driver.quit()

# ══════════════════════════════════════════════
# PARSER
# ══════════════════════════════════════════════

def parse_transfers(html, season):
    """
    Parse le HTML BeSoccer et retourne la liste des transferts.
    Structure : #transfers-panel > .panel-head (club) + .panel-body (table arrivées/départs)
    """
    soup      = BeautifulSoup(html, "html.parser")
    transfers = []

    # Chercher les sections par club
    club_sections = (
        soup.select("#transfers-panel .panel-head") or
        soup.select(".signing-season .panel-head") or
        soup.select(".transfer-new .panel-head")
    )
    print(f"  🏟️  {len(club_sections)} clubs trouvés")

    for section in club_sections:
        # Nom et logo du club Ligue 1
        club_img  = section.select_one("img")
        club_name = club_img.get("alt", "").strip() if club_img else ""
        club_logo = club_img.get("src", "") if club_img else ""

        # Le panel-body suit immédiatement le panel-head
        body = section.find_next_sibling("div", class_="panel-body")
        if not body:
            continue

        # Deux colonnes : arrivées (index 0) et départs (index 1)
        halves = body.select("td.w-50p")
        for half_idx, half in enumerate(halves):
            direction = "ARRIVÉE" if half_idx == 0 else "DÉPART"

            for li in half.select("li.sign-list a.item-box"):

                # ── Nom du joueur ──────────────────────────────────
                name_el     = li.select_one("p.pl-name")
                player_name = name_el.get_text(strip=True) if name_el else ""

                # Fallback : extraire depuis alt de l'image
                if not player_name:
                    img_alt     = li.select_one(".row-img img").get("alt", "") if li.select_one(".row-img img") else ""
                    player_name = re.sub(
                        r"^(Transfert gratuit|Transfert|Prêt|Free transfer|Loan|Transfer|Agent libre)\s+",
                        "", img_alt, flags=re.I
                    ).strip()

                if not player_name:
                    continue

                # ── Date ───────────────────────────────────────────
                date_el   = li.select_one("p.date")
                date_str  = date_el.get_text(strip=True) if date_el else ""

                # ── Photo joueur ───────────────────────────────────
                player_img = li.select_one(".row-img.player img, .row-img img")
                photo      = player_img.get("src", "") if player_img else ""

                # ── ID joueur depuis href ──────────────────────────
                player_href = li.get("href", "")
                pid         = re.search(r"-(\d+)/?$", player_href)
                player_id   = pid.group(1) if pid else ""

                # ── Club précédent/suivant ─────────────────────────
                shield_img = li.select_one(".right-content .shield img, .right-content img")
                dest_name  = shield_img.get("alt", "").strip() if shield_img else ""
                dest_logo  = shield_img.get("src", "") if shield_img else ""

                # ── Type et montant ────────────────────────────────
                data_box = li.select_one(".data-transfer")
                fee_type = ""
                montant  = None
                if data_box:
                    paras = [p.get_text(strip=True) for p in data_box.select("p") if p.get_text(strip=True)]
                    if paras:
                        fee_type = paras[0].rstrip(".")
                    if len(paras) > 1 and paras[1]:
                        montant = paras[1]

                # ── Club départ / arrivée ──────────────────────────
                if direction == "ARRIVÉE":
                    club_depart  = dest_name
                    club_arrivee = club_name
                else:
                    club_depart  = club_name
                    club_arrivee = dest_name

                transfers.append({
                    "season":          season,
                    "date":            date_str,
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

# ══════════════════════════════════════════════
# SUPABASE
# ══════════════════════════════════════════════

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
        if res.status_code in [200, 201, 204]:
            total_ok += len(batch)
        else:
            print(f"  ❌ Supabase {res.status_code}: {res.text[:200]}")
    print(f"  ✅ Supabase: {total_ok}/{len(rows)} transferts sauvegardés")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

print("=== BeSoccer Algeria Transfers Scraper ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

today  = date.today()
season = today.year + 1 if today.month >= 8 else today.year
print(f"\nSaison : {season}")

# Essayer les deux URLs possibles
urls = [
    f"{BASE_URL}/{season}",
    f"https://fr.besoccer.com/competition/transfers/algeria-league-one/{season}",
]

html = None
for url in urls:
    html = fetch_page(url)
    if html and len(html) > 100000:  # Page complète = > 100k chars
        print(f"  ✅ Page complète récupérée")
        break
    else:
        print(f"  ⚠️  Page incomplète ({len(html) if html else 0} chars), essai suivant...")

if not html or len(html) < 50000:
    print("❌ Impossible de charger la page complète")
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
    print("⚠️  0 transferts — BeSoccer bloque peut-être la requête")
    # Afficher un extrait du HTML pour diagnostic
    print(f"  Début HTML : {html[:500] if html else 'vide'}")

print("\n=== Terminé ===")