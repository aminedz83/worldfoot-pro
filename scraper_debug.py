"""
scraper_debug.py
================
Force re-scrape BeSoccer pour matchs déjà en base.
Cible: Akbou vs Setif + Paradou vs Saoura (11/04/2026)
"""

import os, re, time, requests, json
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL       = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS   = {
    "apikey":        SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates"
}

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

def fetch(url):
    try:
        r = scraper.get(url, timeout=20)
        print(f"  GET {r.status_code} : {url}")
        return r if r.status_code == 200 else None
    except Exception as e:
        print(f"  Erreur: {e}")
        return None

def parse_minute(minute_str):
    try:
        clean = minute_str.replace("'", "").strip()
        if not clean or clean in ("Half-time", "Kick-off", "FT"):
            return None
        if "+" in clean:
            parts = clean.split("+")
            return int(parts[0]) + (int(parts[1]) if len(parts) > 1 and parts[1] else 0)
        return int(clean)
    except:
        return None

def extract_player_id(href):
    if not href: return None
    m = re.search(r"/player/[^/]+-(\d+)/?$", href)
    if m: return m.group(1)
    m = re.search(r"/player/([^/]+)/?$", href)
    return m.group(1) if m else None

def parse_player(link):
    href      = link.get("href", "")
    player_id = extract_player_id(href)
    nom_el    = link.select_one("p.name")
    nom       = nom_el.get_text(strip=True) if nom_el else link.get_text(strip=True)
    if not player_id or not nom:
        return None

    img   = link.select_one("div.bench-player img")
    photo = img["src"] if img and img.get("src") else ""
    if photo and photo.startswith("//"): photo = "https:" + photo
    if not photo or "nofoto" in photo:
        photo = f"https://cdn.resfu.com/img_data/players/medium/{player_id}.jpg?size=120x&lossy=1"

    number = ""
    pos    = ""
    role_box = link.select_one("div.role-box span.t-up")
    if role_box:
        num_el = role_box.select_one("span.number")
        if num_el: number = num_el.get_text(strip=True)
        role_text = role_box.get_text(strip=True)
        if num_el: role_text = role_text.replace(number, "").strip()
        pos = role_text

    goals = 0; goal_minutes = []; yellow = False; yellow_minute = None
    red = False; red_minute = None; sub_out_minute = None

    info_wrapper = link.select_one("div.info-wrapper")
    if info_wrapper:
        for img_ev in info_wrapper.select("img.ic-bench"):
            parent    = img_ev.parent
            min_el    = parent.select_one("p.min") if parent else None
            minute_val = parse_minute(min_el.get_text(strip=True) if min_el else "")
            alt = img_ev.get("alt", "").lower()
            src = img_ev.get("src", "").lower()
            if "goal" in alt or "gol" in alt or "accion1" in src:
                if minute_val is not None: goals += 1; goal_minutes.append(minute_val)
            elif "yellow" in alt or "amarilla" in alt or "tarjeta_a" in src or "event-5" in src:
                yellow = True; yellow_minute = minute_val
            elif "red" in alt or "roja" in alt or "tarjeta_r" in src or "event-3" in src:
                red = True; red_minute = minute_val
            elif "sub" in alt or "cambio" in src or "event-6" in src:
                sub_out_minute = minute_val

    note_el = link.select_one("div.match-points")
    note    = None
    if note_el:
        try: note = float(note_el.get_text(strip=True))
        except: pass

    return {
        "name": nom, "id": player_id, "number": number, "pos": pos, "photo": photo,
        "goals": goals, "goal_minutes": goal_minutes,
        "yellow": yellow, "yellow_minute": yellow_minute,
        "red": red, "red_minute": red_minute,
        "sub_out": sub_out_minute is not None, "sub_out_minute": sub_out_minute,
        "minutes": 90, "rating": note,
    }

def scrape_events_live(base_url, home_team, away_team):
    url = base_url.rstrip("/").replace("/lineups", "") + "/events"
    r   = fetch(url)
    if not r: return {}, [], {"home": 0, "away": 0}

    soup = BeautifulSoup(r.text, "html.parser")
    sub_in_minutes = {}
    events = []
    score  = {"home": 0, "away": 0}

    # Score
    score_el = soup.select_one("div.match-score, span.match-score, div.score-cont")
    if score_el:
        nums = re.findall(r"\d+", score_el.get_text())
        if len(nums) >= 2:
            score["home"] = int(nums[0]); score["away"] = int(nums[1])

    for row in soup.select("div.table-played-match.all-events, li.event-row, div.event-item"):
        min_el     = row.select_one("div.col-mid-rows div.min, span.min, div.minute")
        minute     = parse_minute(min_el.get_text(strip=True) if min_el else "")
        imgs       = row.select("img")
        event_type = None
        for img in imgs:
            src = img.get("src", "").lower(); alt = img.get("alt", "").lower()
            if "accion1" in src or "goal" in alt or "gol" in alt: event_type = "goal"
            elif "cambio" in src or "substitution" in alt or "event-8" in src: event_type = "sub"
            elif "tarjeta_a" in src or "event-5" in src or "yellow" in alt: event_type = "yellow"
            elif "tarjeta_r" in src or "event-3" in src or ("red" in alt and "yellow" not in alt): event_type = "red"
            if event_type: break

        if not event_type or minute is None: continue

        player_links = row.select("a[data-cy='eventOrd'], a.player-link, a[href*='/player/']")
        player_name  = player_links[0].get_text(strip=True) if len(player_links) > 0 else ""
        assist_name  = player_links[1].get_text(strip=True) if len(player_links) > 1 else ""
        is_home      = "local" in row.get("class", []) or "home" in row.get("class", [])

        events.append({
            "type": event_type, "minute": minute,
            "team": home_team if is_home else away_team,
            "is_home": is_home, "player": player_name, "assist": assist_name,
        })
        print(f"    {'⚽' if event_type=='goal' else '🔄' if event_type=='sub' else '🟨' if event_type=='yellow' else '🟥'} {minute}' {player_name}")

        if event_type == "sub" and assist_name:
            sub_in_minutes[assist_name] = minute
            sub_in_minutes[player_name] = minute

    print(f"  📊 Events: {len(events)} | Score: {score['home']}-{score['away']}")
    return sub_in_minutes, events, score

def match_sub_minute(name, sub_dict):
    if not name: return None
    if name in sub_dict: return sub_dict[name]
    nl = name.lower()
    for k, v in sub_dict.items():
        kl = k.lower() if k else ""
        lp = nl.split(".")[-1].strip(); lk = kl.split(".")[-1].strip()
        if (lp and lp in kl) or (lk and lk in nl): return v
    return None

def scrape_match(match_id, bs_home, bs_away, home_team, away_team, match_date):
    url_lineup = f"https://www.besoccer.com/match/{bs_home}/{bs_away}/{match_id}/lineups"
    r = fetch(url_lineup)
    if not r: return None

    soup = BeautifulSoup(r.text, "html.parser")
    starters = soup.select('a.col-bench[data-cy="starterPlayer"]')
    print(f"  Titulaires: {len(starters)}")
    if len(starters) < 11:
        print("  ⏳ Compos incomplètes")
        return None

    sub_in_minutes, live_events, score = scrape_events_live(
        f"https://www.besoccer.com/match/{bs_home}/{bs_away}/{match_id}",
        home_team, away_team
    )

    result = {
        "match_id": match_id, "home_team": home_team, "away_team": away_team,
        "match_date": match_date,
        "home_players": [], "away_players": [], "home_subs": [], "away_subs": [],
        "home_formation": "", "away_formation": "",
        "home_score": score["home"], "away_score": score["away"],
        "events": live_events,
        "scraped_at": datetime.now(timezone.utc).isoformat()
    }

    for link in soup.select('a.col-bench.local[data-cy="starterPlayer"]'):
        p = parse_player(link)
        if p: result["home_players"].append(p)
    for link in soup.select('a.col-bench.visitor[data-cy="starterPlayer"]'):
        p = parse_player(link)
        if p: result["away_players"].append(p)
    for link in soup.select('a.col-bench.local[data-cy="benchPlayer"]'):
        p = parse_player(link)
        if p:
            sm = match_sub_minute(p["name"], sub_in_minutes)
            p["minutes"] = sm if sm else 0; p["sub_in_minute"] = sm
            result["home_subs"].append(p)
    for link in soup.select('a.col-bench.visitor[data-cy="benchPlayer"]'):
        p = parse_player(link)
        if p:
            sm = match_sub_minute(p["name"], sub_in_minutes)
            p["minutes"] = sm if sm else 0; p["sub_in_minute"] = sm
            result["away_subs"].append(p)

    print(f"  ✅ {len(result['home_players'])} vs {len(result['away_players'])} titulaires | {len(live_events)} events | {score['home']}-{score['away']}")
    return result

def force_save(lineup):
    res = requests.patch(
        SB_URL + f"/rest/v1/besoccer_lineups?match_id=eq.{lineup['match_id']}",
        headers={**SB_HEADERS, "Prefer": ""},
        json=lineup
    )
    code = res.status_code
    if code not in [200, 201, 204]:
        # Si patch échoue → insert
        res = requests.post(
            SB_URL + "/rest/v1/besoccer_lineups",
            headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
            params={"on_conflict": "match_id"},
            json=lineup
        )
        code = res.status_code
    print(f"  Supabase: {'✅ OK' if code in [200,201,204] else '❌ '+str(code)+' '+res.text[:120]}")

# ══════════════════════════════════════════════
# MATCHS À RE-SCRAPER
# ══════════════════════════════════════════════

TARGETS = [
    {
        "match_id":  "2026264207",
        "bs_home":   "oued-akbou",
        "bs_away":   "es-setif",
        "home_team": "Olympique Akbou",
        "away_team": "ES Setif",
        "match_date": "2026-04-11"
    },
    {
        "match_id":  "2026264211",
        "bs_home":   "paradou",
        "bs_away":   "js-saoura",
        "home_team": "Paradou AC",
        "away_team": "JS Saoura",
        "match_date": "2026-04-11"
    },
]

print("=== DEBUG: Force re-scrape BeSoccer ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

for t in TARGETS:
    print(f"\n--- {t['home_team']} vs {t['away_team']} ---")
    lineup = scrape_match(
        t["match_id"], t["bs_home"], t["bs_away"],
        t["home_team"], t["away_team"], t["match_date"]
    )
    if lineup:
        force_save(lineup)
    else:
        print("  ❌ Scrape échoué")
    time.sleep(3)

print("\n=== Terminé ===")