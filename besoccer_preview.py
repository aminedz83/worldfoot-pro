"""
besoccer_preview.py
===================
Scrape les données Avant-Match depuis BeSoccer pour la Ligue 1 Algérie.
Scrape: stats générales, forme récente, H2H, progression buts, apport offensif, joueurs vedettes
Stocke dans: besoccer_preview (Supabase)

PATCH v2 : KNOWN_IDS remplacé par lookup Supabase (algeria_match_ids)
"""

import os, re, time, requests, json
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone, date, timedelta

# ══════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════

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
        print(f"  Erreur: {e}")
        return None

# ══════════════════════════════════════════════
# LOOKUP MATCHS DEPUIS SUPABASE
# ══════════════════════════════════════════════

def get_targets():
    """
    Récupère les matchs des 8 prochains jours depuis algeria_match_ids.
    Remplace l'ancien dict KNOWN_IDS hardcodé.
    """
    targets = []
    today = date.today()
    date_from = today.isoformat()
    date_to   = (today + timedelta(days=7)).isoformat()

    try:
        r = requests.get(
            SB_URL + f"/rest/v1/algeria_match_ids"
                     f"?match_date=gte.{date_from}"
                     f"&match_date=lte.{date_to}"
                     f"&select=*",
            headers={**SB_HEADERS, "Prefer": ""}
        )
        rows = r.json() if r.status_code == 200 else []
        print(f"  {len(rows)} matchs dans algeria_match_ids ({date_from} → {date_to})")
    except Exception as e:
        print(f"  Erreur Supabase algeria_match_ids: {e}")
        rows = []

    for row in rows:
        targets.append({
            "bs_id":     row["match_id"],
            "bs_home":   row.get("bs_home_slug", ""),
            "bs_away":   row.get("bs_away_slug", ""),
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "date":      row["match_date"],
        })

    return targets

# ══════════════════════════════════════════════
# SCRAPING FONCTIONS
# ══════════════════════════════════════════════

def parse_recent_form(soup, selector):
    results = []
    container = soup.select_one(selector)
    if not container:
        return results
    for row in container.select("div.row.align-center.jc-ce.mb5"):
        result_badge = row.select_one("div.bg-match-res")
        if not result_badge:
            continue
        result = "D"
        classes = result_badge.get("class", [])
        if "win" in classes:   result = "G"
        elif "lose" in classes: result = "P"
        marker = row.select_one("div.marker.bold.mh5 a")
        score  = marker.get_text(strip=True) if marker else ""
        link   = marker.get("href", "")      if marker else ""
        shields   = row.select("img.shield")
        home_logo = shields[0].get("src", "") if len(shields) > 0 else ""
        away_logo = shields[1].get("src", "") if len(shields) > 1 else ""
        home_name = shields[0].get("alt", "") if len(shields) > 0 else ""
        away_name = shields[1].get("alt", "") if len(shields) > 1 else ""
        results.append({
            "result": result, "score": score,
            "home": home_name, "away": away_name,
            "home_logo": home_logo, "away_logo": away_logo, "link": link
        })
    return results

def parse_stats_general(soup):
    stats = {"competition": {}, "all": {}}
    for tab_id, key in [("#tab-competition", "competition"), ("#tab-all", "all")]:
        tab = soup.select_one(tab_id)
        if not tab:
            continue
        for row in tab.select("tr"):
            label_el = row.select_one("p.text-label")
            if not label_el:
                continue
            label = label_el.get_text(strip=True)
            nums  = row.select("div.td-num span")
            if len(nums) >= 2:
                stats[key][label] = {
                    "home": nums[0].get_text(strip=True),
                    "away": nums[-1].get_text(strip=True)
                }
        value_row = tab.select_one("div.row.ta-c.pb10.pt5")
        if value_row:
            cols = value_row.select("div")
            if len(cols) >= 3:
                stats[key]["valeur_home"] = cols[0].get_text(strip=True)
                stats[key]["valeur_away"] = cols[2].get_text(strip=True)
    return stats

def parse_h2h(soup):
    h2h = {"matches": [], "home_wins": 0, "draws": 0, "away_wins": 0}
    container = soup.select_one("div.panel.match-h2h")
    if not container:
        return h2h
    for row in container.select("div.row.align-center.table-row-round"):
        shields = row.select("img.shield")
        badges  = row.select("div.bg-match-res")
        marker  = row.select_one("div.marker.mh5 a")
        if not marker or len(shields) < 2:
            continue
        score     = marker.get_text(strip=True).replace(" ", "")
        link      = marker.get("href", "")
        home_name = shields[0].get("alt", "")
        away_name = shields[1].get("alt", "")
        result_home = "D"
        if badges:
            classes = badges[0].get("class", [])
            if "win" in classes:   result_home = "G"
            elif "lose" in classes: result_home = "P"
        h2h["matches"].append({
            "home": home_name, "away": away_name,
            "home_logo": shields[0].get("src", ""),
            "away_logo": shields[1].get("src", ""),
            "score": score, "result": result_home, "link": link
        })
    totals = container.select("div.row.jc-sa.pv20 div.box")
    if len(totals) >= 3:
        h2h["home_wins"] = totals[0].select_one("span.num").get_text(strip=True) if totals[0].select_one("span.num") else "0"
        h2h["draws"]     = totals[1].select_one("span.num").get_text(strip=True) if totals[1].select_one("span.num") else "0"
        h2h["away_wins"] = totals[2].select_one("span.num").get_text(strip=True) if totals[2].select_one("span.num") else "0"
    return h2h

def parse_goals_progression(soup):
    progression = {
        "home": [], "away": [],
        "intervals": ["1-15", "16-30", "31-45", "46-60", "61-75", "75+"]
    }
    container = soup.select_one("div.panel.goals-progression")
    if not container:
        return progression
    for row in container.select("div.row.align-center"):
        bars = row.select("div.bar")
        if not bars:
            continue
        is_visitor = "visitor" in row.get("class", [])
        key = "away" if is_visitor else "home"
        if progression[key]:
            continue
        for bar in bars:
            num_el      = bar.select_one("span.num")
            style       = bar.get("style", "")
            width_match = re.search(r"width:([\d.]+)%", style)
            width       = float(width_match.group(1)) if width_match else 0
            progression[key].append({
                "count": int(num_el.get_text(strip=True)) if num_el else 0,
                "width": width
            })
    return progression

def parse_offensive_contribution(soup):
    offensive = {"competition": {"home": [], "away": []}, "all": {"home": [], "away": []}}
    for tab_id, key in [("#tab-offensive-competition", "competition"), ("#tab-offensive-all", "all")]:
        tab = soup.select_one(tab_id)
        if not tab:
            continue
        home_col = tab.select_one("div.col-6.item-list.mr5")
        if home_col:
            for item in home_col.select("a.item-box"):
                name_el    = item.select_one("div.mb5.ta-r")
                if not name_el: continue
                name       = name_el.get_text(strip=True)
                photo_el   = item.select_one("img.player")
                photo      = photo_el.get("src", "") if photo_el else ""
                link       = item.get("href", "")
                goals_el   = item.select_one("div.goal span.va-m")
                assists_el = item.select_one("div.assist span.va-m")
                goals      = int(goals_el.get_text(strip=True).strip("()"))   if goals_el   else 0
                assists    = int(assists_el.get_text(strip=True).strip("()")) if assists_el else 0
                offensive[key]["home"].append({
                    "name": name, "goals": goals, "assists": assists,
                    "photo": photo, "link": link
                })
        away_col = tab.select_one("div.col-6.item-list:not(.mr5)")
        if away_col:
            for item in away_col.select("a.item-box"):
                name_el    = item.select_one("div.mb5:not(.ta-r)")
                if not name_el: continue
                name       = name_el.get_text(strip=True)
                photo_el   = item.select_one("img.player")
                photo      = photo_el.get("src", "") if photo_el else ""
                link       = item.get("href", "")
                goals_el   = item.select_one("div.goal span.va-m")
                assists_el = item.select_one("div.assist span.va-m")
                goals      = int(goals_el.get_text(strip=True).strip("()"))   if goals_el   else 0
                assists    = int(assists_el.get_text(strip=True).strip("()")) if assists_el else 0
                offensive[key]["away"].append({
                    "name": name, "goals": goals, "assists": assists,
                    "photo": photo, "link": link
                })
    return offensive

def parse_featured_players(soup):
    featured = {"competition": {}, "all": {}}
    for tab_id, key in [("#tab-featured-competition", "competition"), ("#tab-featured-all", "all")]:
        tab = soup.select_one(tab_id)
        if not tab:
            continue
        for section in tab.select("div.mb15"):
            title_el = section.select_one("p.title.bold.ta-c.mb10")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            cols = section.select("div.col-6")
            if len(cols) < 2:
                continue
            home_mark_el  = cols[0].select_one("div.mark")
            home_photo_el = cols[0].select_one("img.player-circle-box")
            home_name = ""
            for a in cols[0].select("a.item-box"):
                d = a.select_one("div")
                if d:
                    home_name = d.get_text(strip=True)
                    break
            away_mark_el  = cols[1].select_one("div.mark")
            away_photo_el = cols[1].select_one("img.player-circle-box")
            away_name = ""
            for a in cols[1].select("a.item-box"):
                d = a.select_one("div")
                if d:
                    away_name = d.get_text(strip=True)
                    break
            home_val   = home_mark_el.get_text(strip=True)  if home_mark_el  else ""
            away_val   = away_mark_el.get_text(strip=True)  if away_mark_el  else ""
            home_photo = home_photo_el.get("src", "")        if home_photo_el else ""
            away_photo = away_photo_el.get("src", "")        if away_photo_el else ""
            if home_photo and home_photo.startswith("//"): home_photo = "https:" + home_photo
            if away_photo and away_photo.startswith("//"): away_photo = "https:" + away_photo
            featured[key][title] = {
                "home": {"name": home_name, "value": home_val, "photo": home_photo},
                "away": {"name": away_name, "value": away_val, "photo": away_photo}
            }
    return featured

def parse_recent_streaks(soup, tab_id):
    streaks = []
    tab = soup.select_one(tab_id)
    if not tab:
        return streaks
    for row in tab.select("table.table tbody tr"):
        label_el = row.select_one("p.text-label")
        if not label_el:
            continue
        label        = label_el.get_text(strip=True)
        left_el      = row.select_one("div.td-num.left div.color-grey")
        right_el     = row.select_one("div.td-num.right div")
        record_left  = row.select_one("div.td-num.left div.color-grey2.record")
        record_right = row.select_one("div.td-num.right div.color-grey2.record")
        streaks.append({
            "label":        label,
            "home":         left_el.get_text(strip=True)      if left_el      else "",
            "away":         right_el.get_text(strip=True)     if right_el     else "",
            "home_record":  record_left.get_text(strip=True)  if record_left  else "",
            "away_record":  record_right.get_text(strip=True) if record_right else ""
        })
    return streaks

# ══════════════════════════════════════════════
# SCRAPE PREVIEW
# ══════════════════════════════════════════════

def scrape_preview(match):
    bs_id   = match["bs_id"]
    bs_home = match["bs_home"]
    bs_away = match["bs_away"]

    url = f"https://www.besoccer.com/match/{bs_home}/{bs_away}/{bs_id}/preview"
    r   = fetch(url)
    if not r:
        print(f"  ❌ Impossible de récupérer {url}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    print(f"  HTML size: {len(r.text)} chars")

    stats          = parse_stats_general(soup)
    print(f"  ✅ Stats générales: {len(stats['competition'])} métriques")

    home_form_comp = parse_recent_form(soup, "#tab-recentForm-competition div.team-coach-stats.ta-c.col-6.pv10:first-child")
    away_form_comp = parse_recent_form(soup, "#tab-recentForm-competition div.team-coach-stats.ta-c.col-6.pv10:last-child")
    home_form_all  = parse_recent_form(soup, "#tab-recentForm-all div.team-coach-stats.ta-c.col-6.pv10:first-child")
    away_form_all  = parse_recent_form(soup, "#tab-recentForm-all div.team-coach-stats.ta-c.col-6.pv10:last-child")
    print(f"  ✅ Forme: {len(home_form_comp)} home / {len(away_form_comp)} away")

    streaks_comp   = parse_recent_streaks(soup, "#tab-recentForm-competition")
    streaks_all    = parse_recent_streaks(soup, "#tab-recentForm-all")
    h2h            = parse_h2h(soup)
    print(f"  ✅ H2H: {len(h2h['matches'])} matchs")

    goals_prog     = parse_goals_progression(soup)
    print(f"  ✅ Progression buts: {len(goals_prog['home'])} intervalles")

    offensive      = parse_offensive_contribution(soup)
    print(f"  ✅ Offensif: {len(offensive['competition']['home'])} joueurs home")

    featured       = parse_featured_players(soup)
    print(f"  ✅ Vedettes: {len(featured['competition'])} catégories")

    return {
        "match_id":               bs_id,
        "home_team":              match["home_team"],
        "away_team":              match["away_team"],
        "match_date":             match["date"],
        "stats_general":          stats,
        "recent_form":            {
            "competition": {"home": home_form_comp, "away": away_form_comp},
            "all":         {"home": home_form_all,  "away": away_form_all}
        },
        "streaks":                {"competition": streaks_comp, "all": streaks_all},
        "h2h":                    h2h,
        "goals_progression":      goals_prog,
        "offensive_contribution": offensive,
        "featured_players":       featured,
        "scraped_at":             datetime.now(timezone.utc).isoformat()
    }

# ══════════════════════════════════════════════
# SUPABASE
# ══════════════════════════════════════════════

def delete_preview(match_id):
    requests.delete(
        SB_URL + f"/rest/v1/besoccer_preview?match_id=eq.{match_id}",
        headers=SB_HEADERS
    )

def already_scraped(match_id):
    try:
        r = requests.get(
            SB_URL + f"/rest/v1/besoccer_preview?match_id=eq.{match_id}&select=id,goals_progression",
            headers={**SB_HEADERS, "Prefer": ""}
        ).json()
        if not r or len(r) == 0:
            return False
        gp = r[0].get("goals_progression", {})
        if not gp or not gp.get("home"):
            print("  ⚠️ Progression buts vide → re-scrape")
            delete_preview(match_id)
            return False
        return True
    except:
        return False

def save_preview(data):
    res = requests.post(
        SB_URL + "/rest/v1/besoccer_preview",
        headers={**SB_HEADERS, "Prefer": "resolution=ignore-duplicates"},
        params={"on_conflict": "match_id"},
        json=data
    )
    code = res.status_code
    print(f"  Supabase: {'✅ OK' if code in [200,201,204] else '❌ '+str(code)+' '+res.text[:200]}")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

print("=== BeSoccer Preview Scraper ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

targets = get_targets()
print(f"\n{len(targets)} matchs à scraper")

if not targets:
    print("Aucun match — OK")
    exit(0)

for match in targets:
    print(f"\n--- {match['home_team']} vs {match['away_team']} | {match['date']} ---")
    if already_scraped(match["bs_id"]):
        print("  Déjà scrapé ✓")
        continue
    preview = scrape_preview(match)
    if preview:
        save_preview(preview)
    else:
        print("  ❌ Échec")
    time.sleep(3)

print("\n=== Terminé ===")