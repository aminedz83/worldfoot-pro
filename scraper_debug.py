"""
scraper_debug.py - Force scrape complet besoccer_preview pour matchs passés
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

def parse_recent_form(soup, selector):
    results = []
    container = soup.select_one(selector)
    if not container: return results
    for row in container.select("div.row.align-center.jc-ce.mb5"):
        result_badge = row.select_one("div.bg-match-res")
        if not result_badge: continue
        result = "D"
        classes = result_badge.get("class", [])
        if "win" in classes: result = "G"
        elif "lose" in classes: result = "P"
        marker = row.select_one("div.marker.bold.mh5 a")
        score  = marker.get_text(strip=True) if marker else ""
        link   = marker.get("href", "") if marker else ""
        shields   = row.select("img.shield")
        results.append({
            "result": result, "score": score,
            "home": shields[0].get("alt","") if len(shields)>0 else "",
            "away": shields[1].get("alt","") if len(shields)>1 else "",
            "home_logo": shields[0].get("src","") if len(shields)>0 else "",
            "away_logo": shields[1].get("src","") if len(shields)>1 else "",
            "link": link
        })
    return results

def parse_stats_general(soup):
    stats = {"competition": {}, "all": {}}
    for tab_id, key in [("#tab-competition","competition"),("#tab-all","all")]:
        tab = soup.select_one(tab_id)
        if not tab: continue
        for row in tab.select("tr"):
            label_el = row.select_one("p.text-label")
            if not label_el: continue
            label = label_el.get_text(strip=True)
            nums  = row.select("div.td-num span")
            if len(nums) >= 2:
                stats[key][label] = {
                    "home": nums[0].get_text(strip=True),
                    "away": nums[-1].get_text(strip=True)
                }
    return stats

def parse_h2h(soup):
    h2h = {"matches":[],"home_wins":0,"draws":0,"away_wins":0}
    container = soup.select_one("div.panel.match-h2h")
    if not container: return h2h
    for row in container.select("div.row.align-center.table-row-round"):
        shields = row.select("img.shield")
        badges  = row.select("div.bg-match-res")
        marker  = row.select_one("div.marker.mh5 a")
        if not marker or len(shields) < 2: continue
        result_home = "D"
        if badges:
            classes = badges[0].get("class",[])
            if "win" in classes: result_home = "G"
            elif "lose" in classes: result_home = "P"
        h2h["matches"].append({
            "home": shields[0].get("alt",""), "away": shields[1].get("alt",""),
            "home_logo": shields[0].get("src",""), "away_logo": shields[1].get("src",""),
            "score": marker.get_text(strip=True).replace(" ",""),
            "result": result_home, "link": marker.get("href","")
        })
    totals = container.select("div.row.jc-sa.pv20 div.box")
    if len(totals) >= 3:
        h2h["home_wins"] = totals[0].select_one("span.num").get_text(strip=True) if totals[0].select_one("span.num") else "0"
        h2h["draws"]     = totals[1].select_one("span.num").get_text(strip=True) if totals[1].select_one("span.num") else "0"
        h2h["away_wins"] = totals[2].select_one("span.num").get_text(strip=True) if totals[2].select_one("span.num") else "0"
    return h2h

def parse_goals_progression(soup):
    progression = {"home":[],"away":[],"intervals":["1-15","16-30","31-45","46-60","61-75","75+"]}
    container = soup.select_one("div.panel.goals-progression")
    if not container: return progression
    for row in container.select("div.row.align-center"):
        bars = row.select("div.bar")
        if not bars: continue
        is_visitor = "visitor" in row.get("class",[])
        key = "away" if is_visitor else "home"
        if progression[key]: continue
        for bar in bars:
            num_el = bar.select_one("span.num")
            style  = bar.get("style","")
            w = re.search(r"width:([\d.]+)%", style)
            progression[key].append({
                "count": int(num_el.get_text(strip=True)) if num_el else 0,
                "width": float(w.group(1)) if w else 0
            })
    return progression

def parse_offensive_contribution(soup):
    offensive = {"competition":{"home":[],"away":[]},"all":{"home":[],"away":[]}}
    for tab_id, key in [("#tab-offensive-competition","competition"),("#tab-offensive-all","all")]:
        tab = soup.select_one(tab_id)
        if not tab: continue
        home_col = tab.select_one("div.col-6.item-list.mr5")
        if home_col:
            for item in home_col.select("a.item-box"):
                name_el = item.select_one("div.mb5.ta-r")
                if not name_el: continue
                goals_el = item.select_one("div.goal span.va-m")
                assists_el = item.select_one("div.assist span.va-m")
                offensive[key]["home"].append({
                    "name": name_el.get_text(strip=True),
                    "goals": int(goals_el.get_text(strip=True).strip("()")) if goals_el else 0,
                    "assists": int(assists_el.get_text(strip=True).strip("()")) if assists_el else 0,
                    "photo": (item.select_one("img.player") or {}).get("src",""),
                    "link": item.get("href","")
                })
        away_col = tab.select_one("div.col-6.item-list:not(.mr5)")
        if away_col:
            for item in away_col.select("a.item-box"):
                name_el = item.select_one("div.mb5:not(.ta-r)")
                if not name_el: continue
                goals_el = item.select_one("div.goal span.va-m")
                assists_el = item.select_one("div.assist span.va-m")
                offensive[key]["away"].append({
                    "name": name_el.get_text(strip=True),
                    "goals": int(goals_el.get_text(strip=True).strip("()")) if goals_el else 0,
                    "assists": int(assists_el.get_text(strip=True).strip("()")) if assists_el else 0,
                    "photo": (item.select_one("img.player") or {}).get("src",""),
                    "link": item.get("href","")
                })
    return offensive

def parse_featured_players(soup):
    featured = {"competition":{},"all":{}}
    for tab_id, key in [("#tab-featured-competition","competition"),("#tab-featured-all","all")]:
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
            featured[key][title] = {
                "home": {"name": home_name, "value": home_mark_el.get_text(strip=True) if home_mark_el else "", "photo": home_photo_el.get("src","") if home_photo_el else ""},
                "away": {"name": away_name, "value": away_mark_el.get_text(strip=True) if away_mark_el else "", "photo": away_photo_el.get("src","") if away_photo_el else ""}
            }
            print(f"    {title}: {home_name} | {away_name}")
    return featured

def scrape_and_upsert(t):
    url  = f"https://www.besoccer.com/match/{t['bs_home']}/{t['bs_away']}/{t['bs_id']}/preview"
    r    = fetch(url)
    if not r: return

    soup = BeautifulSoup(r.text, "html.parser")

    stats        = parse_stats_general(soup)
    h2h          = parse_h2h(soup)
    goals_prog   = parse_goals_progression(soup)
    offensive    = parse_offensive_contribution(soup)
    featured     = parse_featured_players(soup)

    home_form_comp = parse_recent_form(soup, "#tab-recentForm-competition div.team-coach-stats.ta-c.col-6.pv10:first-child")
    away_form_comp = parse_recent_form(soup, "#tab-recentForm-competition div.team-coach-stats.ta-c.col-6.pv10:last-child")
    home_form_all  = parse_recent_form(soup, "#tab-recentForm-all div.team-coach-stats.ta-c.col-6.pv10:first-child")
    away_form_all  = parse_recent_form(soup, "#tab-recentForm-all div.team-coach-stats.ta-c.col-6.pv10:last-child")

    data = {
        "match_id":               t["bs_id"],
        "home_team":              t["home_team"],
        "away_team":              t["away_team"],
        "match_date":             t["match_date"],
        "stats_general":          stats,
        "recent_form":            {"competition":{"home":home_form_comp,"away":away_form_comp},"all":{"home":home_form_all,"away":away_form_all}},
        "streaks":                {"competition":[],"all":[]},
        "h2h":                    h2h,
        "goals_progression":      goals_prog,
        "offensive_contribution": offensive,
        "featured_players":       featured,
        "scraped_at":             datetime.now(timezone.utc).isoformat()
    }

    # Upsert = INSERT si absent, UPDATE si présent
    res = requests.post(
        SB_URL + "/rest/v1/besoccer_preview",
        headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
        params={"on_conflict": "match_id"},
        json=data
    )
    print(f"  Supabase: {'✅ OK' if res.status_code in [200,201,204] else '❌ '+str(res.status_code)+' '+res.text[:100]}")

TARGETS = [
    {"bs_id":"2026264207","bs_home":"oued-akbou","bs_away":"es-setif",       "home_team":"Olympique Akbou","away_team":"ES Setif",       "match_date":"2026-04-11"},
    {"bs_id":"2026264211","bs_home":"paradou",    "bs_away":"js-saoura",     "home_team":"Paradou AC",     "away_team":"JS Saoura",      "match_date":"2026-04-11"},
    {"bs_id":"2026264210","bs_home":"es-mostaganem","bs_away":"usm-khenchela","home_team":"ES Mostaganem", "away_team":"USM Khenchela",  "match_date":"2026-04-10"},
    {"bs_id":"2026264214","bs_home":"kabylie",    "bs_away":"cs-constantine","home_team":"JS Kabylie",     "away_team":"CS Constantine", "match_date":"2026-04-10"},
]

print("=== Force scrape besoccer_preview ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
for t in TARGETS:
    print(f"\n--- {t['home_team']} vs {t['away_team']} ---")
    scrape_and_upsert(t)
    time.sleep(3)
print("\n=== Terminé ===")