"""
scraper_debug.py - Force re-scrape besoccer_preview pour matchs passés
"""
import os, re, time, requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL       = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS   = {
    "apikey":        SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type":  "application/json"
}

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

def fetch(url):
    try:
        r = scraper.get(url, timeout=25)
        print(f"  GET {r.status_code} : {url}")
        return r if r.status_code == 200 else None
    except Exception as e:
        print(f"  Erreur: {e}"); return None

def parse_featured_players(soup):
    featured = {"competition": {}, "all": {}}
    for tab_id, key in [("#tab-featured-competition", "competition"), ("#tab-featured-all", "all")]:
        tab = soup.select_one(tab_id)
        if not tab: continue
        for section in tab.select("div.mb15"):
            title_el = section.select_one("p.title.bold.ta-c.mb10")
            if not title_el: continue
            title = title_el.get_text(strip=True)
            cols = section.select("div.col-6")
            if len(cols) < 2: continue

            home_mark_el  = cols[0].select_one("div.mark")
            home_photo_el = cols[0].select_one("img.player-circle-box")
            home_name = ""
            for a in cols[0].select("a.item-box"):
                d = a.select_one("div")
                if d: home_name = d.get_text(strip=True); break

            away_mark_el  = cols[1].select_one("div.mark")
            away_photo_el = cols[1].select_one("img.player-circle-box")
            away_name = ""
            for a in cols[1].select("a.item-box"):
                d = a.select_one("div")
                if d: away_name = d.get_text(strip=True); break

            home_val   = home_mark_el.get_text(strip=True)  if home_mark_el  else ""
            away_val   = away_mark_el.get_text(strip=True)  if away_mark_el  else ""
            home_photo = home_photo_el.get("src", "")        if home_photo_el else ""
            away_photo = away_photo_el.get("src", "")        if away_photo_el else ""

            featured[key][title] = {
                "home": {"name": home_name, "value": home_val, "photo": home_photo},
                "away": {"name": away_name, "value": away_val, "photo": away_photo}
            }
            print(f"    {title}: home={home_name} | away={away_name}")
    return featured

def update_featured(bs_id, bs_home, bs_away):
    url  = f"https://www.besoccer.com/match/{bs_home}/{bs_away}/{bs_id}/preview"
    r    = fetch(url)
    if not r: return
    soup = BeautifulSoup(r.text, "html.parser")
    featured = parse_featured_players(soup)

    # PATCH uniquement featured_players dans la ligne existante
    res = requests.patch(
        SB_URL + f"/rest/v1/besoccer_preview?match_id=eq.{bs_id}",
        headers={**SB_HEADERS, "Prefer": ""},
        json={"featured_players": featured}
    )
    print(f"  Supabase: {'✅ OK' if res.status_code in [200,201,204] else '❌ '+str(res.status_code)+' '+res.text[:100]}")

TARGETS = [
    {"bs_id": "2026264207", "bs_home": "oued-akbou", "bs_away": "es-setif",       "label": "Akbou vs Setif"},
    {"bs_id": "2026264211", "bs_home": "paradou",     "bs_away": "js-saoura",      "label": "Paradou vs Saoura"},
    {"bs_id": "2026264210", "bs_home": "es-mostaganem","bs_away": "usm-khenchela", "label": "Mostaganem vs Khenchela"},
    {"bs_id": "2026264214", "bs_home": "kabylie",     "bs_away": "cs-constantine", "label": "JSK vs CSC"},
]

print("=== Fix featured_players noms ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
for t in TARGETS:
    print(f"\n--- {t['label']} ---")
    update_featured(t["bs_id"], t["bs_home"], t["bs_away"])
    time.sleep(2)
print("\n=== Terminé ===")