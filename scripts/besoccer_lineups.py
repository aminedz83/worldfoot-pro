"""
besoccer_lineups.py
===================
Scrape les compositions + événements live Ligue 1 Algérie depuis BeSoccer.
- Sauvegarde les compos dès qu'elles sont disponibles (sans attendre les notes)
- Met à jour les events (buts, cartons, changements) toutes les 5 min pendant le match
"""

import os, re, time, requests, json
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone, date

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

TEAM_SLUG = {
    "MC Alger":        "mc-alger",
    "CR Belouizdad":   "belouizdad",
    "JS Kabylie":      "kabylie",
    "USM Alger":       "usm-alger",
    "ES Setif":        "es-setif",
    "CS Constantine":  "cs-constantine",
    "Paradou AC":      "paradou",
    "ASO Chlef":       "chlef",
    "MC Oran":         "mc-oran",
    "JS Saoura":       "js-saoura",
    "MC El Bayadh":    "el-bayadh",
    "USM Khenchela":   "usm-khenchela",
    "Olympique Akbou": "oued-akbou",
    "ES Mostaganem":   "es-mostaganem",
    "MB Rouissat":     "mb-rouisset",
    "ES Ben Aknoun":   "ben-aknoun",
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

def extract_player_id(href):
    if not href: return None
    m = re.search(r"/player/[^/]+-(\d+)/?$", href)
    if m: return m.group(1)
    m = re.search(r"/player/([^/]+)/?$", href)
    return m.group(1) if m else None

def parse_minute(minute_str):
    """Parse une minute style '45+2'' → int"""
    try:
        clean = minute_str.replace("'", "").strip()
        if not clean or clean in ("Half-time", "Kick-off", "FT"):
            return None
        if clean.startswith("+"):
            return int(clean[1:]) if clean[1:] else None
        if "+" in clean:
            parts = clean.split("+")
            base  = int(parts[0]) if parts[0] else 0
            extra = int(parts[1]) if len(parts) > 1 and parts[1] else 0
            return base + extra
        return int(clean)
    except:
        return None

# ══════════════════════════════════════════════
# TROUVER L'ID BESOCCER D'UN MATCH
# ══════════════════════════════════════════════

def find_besoccer_match_id(home_team, away_team, year):
    home_slug = TEAM_SLUG.get(home_team, "")
    away_slug = TEAM_SLUG.get(away_team, "")
    if not home_slug or not away_slug:
        print(f"  ⚠️  Slug manquant: {home_team} / {away_team}")
        return None, None

    club_ids = {
        "MC Alger": 11505, "CR Belouizdad": 11507, "JS Kabylie": 11506,
        "USM Alger": 11504, "ES Setif": 11501, "CS Constantine": 11510,
        "Paradou AC": 59336, "ASO Chlef": 11511, "MC Oran": 11509,
        "JS Saoura": 20933, "MC El Bayadh": 11729, "USM Khenchela": 11530,
        "Olympique Akbou": 11522, "ES Mostaganem": 13715,
        "MB Rouissat": 100882, "ES Ben Aknoun": 11519,
    }
    club_id = club_ids.get(home_team)
    if not club_id:
        return None, None

    url = f"https://www.besoccer.com/team/matches/{home_slug}/{club_id}/"
    r = fetch(url)
    if not r:
        return None, None

    soup = BeautifulSoup(r.text, "html.parser")
    best_id  = None
    best_url = None
    for a in soup.select(f"a[href*='/match/'][href*='{away_slug}']"):
        href = a.get("href", "")
        m = re.search(r"/match/[^/]+/[^/]+/(\d+)/?", href)
        if m:
            mid = m.group(1)
            try:
                if best_id is None or int(mid) > int(best_id):
                    best_id  = mid
                    best_url = "https://www.besoccer.com" + href if href.startswith("/") else href
            except:
                pass
    if best_id:
        print(f"  ✅ Trouvé: {best_url}")
        return best_id, best_url
    return None, None

# ══════════════════════════════════════════════
# MATCHS DU JOUR
# ══════════════════════════════════════════════

KNOWN_IDS = {
    "2026-04-10": [
        {"home_team": "ES Ben Aknoun",   "away_team": "ASO Chlef",      "bs_id": "2026264208", "bs_home": "ben-aknoun",    "bs_away": "chlef"},
        {"home_team": "ES Mostaganem",   "away_team": "USM Khenchela",  "bs_id": "2026264210", "bs_home": "es-mostaganem", "bs_away": "usm-khenchela"},
        {"home_team": "JS Kabylie",      "away_team": "CS Constantine", "bs_id": "2026264214", "bs_home": "kabylie",       "bs_away": "cs-constantine"},
    ],
    "2026-04-11": [
        {"home_team": "Olympique Akbou", "away_team": "ES Setif",       "bs_id": "2026264207", "bs_home": "oued-akbou",    "bs_away": "es-setif"},
        {"home_team": "Paradou AC",      "away_team": "JS Saoura",      "bs_id": "2026264211", "bs_home": "paradou",       "bs_away": "js-saoura"},
    ],
    "2026-04-16": [
        {"home_team": "CS Constantine",  "away_team": "MC Alger",       "bs_id": "2026264221", "bs_home": "cs-constantine","bs_away": "mc-alger"},
    ],
    "2026-04-17": [
        {"home_team": "MB Rouissat",     "away_team": "JS Kabylie",     "bs_id": "2026264220", "bs_home": "mb-rouisset",   "bs_away": "kabylie"},
        {"home_team": "ASO Chlef",       "away_team": "Olympique Akbou","bs_id": "2026264215", "bs_home": "chlef",         "bs_away": "oued-akbou"},
        {"home_team": "MC El Bayadh",    "away_team": "Paradou AC",     "bs_id": "2026264216", "bs_home": "el-bayadh",     "bs_away": "paradou"},
        {"home_team": "JS Saoura",       "away_team": "USM Khenchela",  "bs_id": "2026264219", "bs_home": "js-saoura",     "bs_away": "usm-khenchela"},
        {"home_team": "ES Setif",        "away_team": "MC Oran",        "bs_id": "2026264222", "bs_home": "es-setif",      "bs_away": "mc-oran"},
    ],
    "2026-05-09": [
        {"home_team": "JS Kabylie",      "away_team": "ES Setif",       "bs_id": "2026264223", "bs_home": "kabylie",       "bs_away": "es-setif"},
        {"home_team": "ES Mostaganem",   "away_team": "JS Saoura",      "bs_id": "2026264224", "bs_home": "es-mostaganem", "bs_away": "js-saoura"},
        {"home_team": "MC Alger",        "away_team": "MB Rouissat",    "bs_id": "2026264225", "bs_home": "mc-alger",      "bs_away": "mb-rouisset"},
        {"home_team": "Paradou AC",      "away_team": "CS Constantine", "bs_id": "2026264226", "bs_home": "paradou",       "bs_away": "cs-constantine"},
        {"home_team": "USM Khenchela",   "away_team": "MC El Bayadh",   "bs_id": "2026264227", "bs_home": "usm-khenchela", "bs_away": "el-bayadh"},
        {"home_team": "ES Ben Aknoun",   "away_team": "USM Alger",      "bs_id": "2026264228", "bs_home": "ben-aknoun",    "bs_away": "usm-alger"},
        {"home_team": "MC Oran",         "away_team": "ASO Chlef",      "bs_id": "2026264229", "bs_home": "mc-oran",       "bs_away": "chlef"},
        {"home_team": "Olympique Akbou", "away_team": "CR Belouizdad",  "bs_id": "2026264230", "bs_home": "oued-akbou",    "bs_away": "belouizdad"},
    ],
    "2026-05-15": [
        {"home_team": "MC El Bayadh",    "away_team": "JS Saoura",      "bs_id": "2026264231", "bs_home": "el-bayadh",     "bs_away": "js-saoura"},
        {"home_team": "CS Constantine",  "away_team": "USM Khenchela",  "bs_id": "2026264232", "bs_home": "cs-constantine","bs_away": "usm-khenchela"},
        {"home_team": "ES Setif",        "away_team": "MC Alger",       "bs_id": "2026264233", "bs_home": "es-setif",      "bs_away": "mc-alger"},
        {"home_team": "CR Belouizdad",   "away_team": "MC Oran",        "bs_id": "2026264234", "bs_home": "belouizdad",    "bs_away": "mc-oran"},
        {"home_team": "USM Alger",       "away_team": "Olympique Akbou","bs_id": "2026264235", "bs_home": "usm-alger",     "bs_away": "oued-akbou"},
        {"home_team": "ASO Chlef",       "away_team": "JS Kabylie",     "bs_id": "2026264236", "bs_home": "chlef",         "bs_away": "kabylie"},
        {"home_team": "ES Ben Aknoun",   "away_team": "ES Mostaganem",  "bs_id": "2026264237", "bs_home": "ben-aknoun",    "bs_away": "es-mostaganem"},
        {"home_team": "MB Rouissat",     "away_team": "Paradou AC",     "bs_id": "2026264238", "bs_home": "mb-rouisset",   "bs_away": "paradou"},
    ],
    "2026-05-22": [
        {"home_team": "ES Mostaganem",   "away_team": "MC El Bayadh",   "bs_id": "2026264432", "bs_home": "es-mostaganem", "bs_away": "el-bayadh"},
        {"home_team": "JS Saoura",       "away_team": "CS Constantine", "bs_id": "2026264433", "bs_home": "js-saoura",     "bs_away": "cs-constantine"},
        {"home_team": "USM Khenchela",   "away_team": "MB Rouissat",    "bs_id": "2026264434", "bs_home": "usm-khenchela", "bs_away": "mb-rouisset"},
        {"home_team": "Paradou AC",      "away_team": "ES Setif",       "bs_id": "2026264435", "bs_home": "paradou",       "bs_away": "es-setif"},
        {"home_team": "MC Alger",        "away_team": "ASO Chlef",      "bs_id": "2026264436", "bs_home": "mc-alger",      "bs_away": "chlef"},
        {"home_team": "JS Kabylie",      "away_team": "CR Belouizdad",  "bs_id": "2026264437", "bs_home": "kabylie",       "bs_away": "belouizdad"},
        {"home_team": "MC Oran",         "away_team": "USM Alger",      "bs_id": "2026264438", "bs_home": "mc-oran",       "bs_away": "usm-alger"},
        {"home_team": "Olympique Akbou", "away_team": "ES Ben Aknoun",  "bs_id": "2026264439", "bs_home": "oued-akbou",    "bs_away": "ben-aknoun"},
    ],
}

def get_today_matches():
    today   = date.today().strftime("%Y-%m-%d")
    matches = []
    seen    = set()

    print(f"\nRecherche matchs du {today}...")

    try:
        r = requests.get(
            SB_URL + f"/rest/v1/algeria_lineups?match_date=eq.{today}&select=home_team,away_team,fixture_id",
            headers={**SB_HEADERS, "Prefer": ""}
        )
        rows = r.json() if r.status_code == 200 else []
        print(f"  {len(rows)} matchs dans algeria_lineups")
    except Exception as e:
        print(f"  Erreur Supabase: {e}")
        rows = []

    today_known = KNOWN_IDS.get(today, [])
    if today_known:
        existing = {f"{r.get('home_team')}_{r.get('away_team')}" for r in rows}
        for m in today_known:
            key = f"{m['home_team']}_{m['away_team']}"
            if key not in existing:
                rows.append({
                    "home_team": m["home_team"], "away_team": m["away_team"],
                    "bs_id": m.get("bs_id"), "bs_home": m.get("bs_home"), "bs_away": m.get("bs_away")
                })
        print(f"  {len(rows)} matchs total après enrichissement")
    elif not rows:
        print("  ⚠️  Aucun match connu pour aujourd'hui")

    known_today = {f"{m['home_team']}_{m['away_team']}": m for m in KNOWN_IDS.get(today, [])}

    for row in rows:
        home = row.get("home_team", "")
        away = row.get("away_team", "")
        if not home or not away:
            continue
        key = f"{home}_{away}"
        if key in seen:
            continue
        seen.add(key)
        print(f"\n  🔍 {home} vs {away}")

        known = known_today.get(key)
        if known and known.get("bs_id"):
            bs_id   = known["bs_id"]
            bs_home = known["bs_home"]
            bs_away = known["bs_away"]
            match_url = f"https://www.besoccer.com/match/{bs_home}/{bs_away}/{bs_id}"
            print(f"  ✅ ID connu: {match_url}")
            match_id  = bs_id
        elif row.get("bs_id"):
            bs_id   = row["bs_id"]
            bs_home = row.get("bs_home", TEAM_SLUG.get(home, ""))
            bs_away = row.get("bs_away", TEAM_SLUG.get(away, ""))
            match_url = f"https://www.besoccer.com/match/{bs_home}/{bs_away}/{bs_id}"
            print(f"  ✅ ID direct: {match_url}")
            match_id  = bs_id
        else:
            match_id, match_url = find_besoccer_match_id(home, away, today[:4])

        if match_id:
            matches.append({
                "match_id":  match_id,
                "url":       match_url,
                "home_team": home,
                "away_team": away,
                "date":      today
            })
        else:
            print(f"  ⚠️  Match BeSoccer non trouvé pour {home} vs {away}")
        time.sleep(1)

    return matches

# ══════════════════════════════════════════════
# PARSE PLAYER
# ══════════════════════════════════════════════

def parse_player(link):
    href      = link.get("href", "")
    player_id = extract_player_id(href)

    nom_el = link.select_one("p.name")
    nom    = nom_el.get_text(strip=True) if nom_el else link.get_text(strip=True)
    if not player_id or not nom:
        return None

    img   = link.select_one("div.bench-player img")
    photo = img["src"] if img and img.get("src") else ""
    if photo and photo.startswith("//"):
        photo = "https:" + photo
    if not photo or "nofoto" in photo:
        photo = f"https://cdn.resfu.com/img_data/players/medium/{player_id}.jpg?size=120x&lossy=1"

    number = ""
    pos    = ""
    role_box = link.select_one("div.role-box span.t-up")
    if role_box:
        num_el = role_box.select_one("span.number")
        if num_el:
            number = num_el.get_text(strip=True)
        role_text = role_box.get_text(strip=True)
        if num_el:
            role_text = role_text.replace(number, "").strip()
        pos = role_text

    info_wrapper   = link.select_one("div.info-wrapper")
    goals          = 0
    goal_minutes   = []
    yellow         = False
    yellow_minute  = None
    red            = False
    red_minute     = None
    sub_out_minute = None

    if info_wrapper:
        for img_ev in info_wrapper.select("img.ic-bench"):
            parent  = img_ev.parent
            min_el  = parent.select_one("p.min") if parent else None
            minute_val = parse_minute(min_el.get_text(strip=True) if min_el else "")

            alt = img_ev.get("alt", "").lower()
            src = img_ev.get("src", "").lower()
            if ("goal" in alt or "gol" in alt or "accion1" in src) and "cambio" not in src and "sub" not in alt:
                if minute_val is not None:
                    goals += 1
                    goal_minutes.append(minute_val)
            elif "yellow" in alt or "amarilla" in alt or "tarjeta_a" in src or "event-5" in src:
                yellow        = True
                yellow_minute = minute_val
            elif "red" in alt or "roja" in alt or "tarjeta_r" in src or "event-3" in src:
                red        = True
                red_minute = minute_val
            elif "sub" in alt or "cambio" in src or "event-6" in src:
                sub_out_minute = minute_val

    note_el = link.select_one("div.match-points")
    note    = None
    if note_el:
        try:
            note = float(note_el.get_text(strip=True))
        except:
            pass

    return {
        "name":           nom,
        "id":             player_id,
        "number":         number,
        "pos":            pos,
        "photo":          photo,
        "goals":          goals,
        "goal_minutes":   goal_minutes,
        "yellow":         yellow,
        "yellow_minute":  yellow_minute,
        "red":            red,
        "red_minute":     red_minute,
        "sub_out":        sub_out_minute is not None,
        "sub_out_minute": sub_out_minute,
        "minutes":        90,
        "rating":         note,
    }

# ══════════════════════════════════════════════
# SCRAPE EVENTS LIVE — nouvelle version complète
# ══════════════════════════════════════════════

def scrape_events_live(base_url, home_team, away_team):
    """
    Scrape la page /events de BeSoccer et retourne:
    - sub_in_minutes: dict player_id → minute d'entrée
    - events: liste d'événements (buts/cartons)
    - score: {home, away}
    """
    url = base_url.rstrip("/").replace("/lineups", "") + "/events"
    r   = fetch(url)
    if not r:
        return {}, [], {"home": 0, "away": 0}

    soup           = BeautifulSoup(r.text, "html.parser")
    sub_in_minutes = {}
    events         = []
    seen           = set()

    # ── Score : premier mini-result = score final ─────────────
    score = {"home": 0, "away": 0}
    all_mini = soup.select("div.mini-result")
    if all_mini:
        m = re.search(r"(\d+)\s*-\s*(\d+)", all_mini[0].get_text(strip=True))
        if m:
            score["home"] = int(m.group(1))
            score["away"] = int(m.group(2))
    if score["home"] == 0 and score["away"] == 0:
        result_el = soup.select_one("div.result")
        if result_el:
            nums = re.findall(r"\b(\d{1,2})\s*-\s*(\d{1,2})\b", result_el.get_text(strip=True))
            if nums:
                score["home"] = int(nums[-1][0])
                score["away"] = int(nums[-1][1])

    # ── Events : format 1 uniquement (all-events) ────────────
    for row in soup.select("div.table-played-match.all-events"):
        min_el = row.select_one("div.col-mid-rows div.min")
        if not min_el: continue
        minute = parse_minute(min_el.get_text(strip=True))
        if minute is None: continue

        img_ev = row.select_one("img[src*='events/']")
        if not img_ev: continue
        src = img_ev.get("src", "").lower()
        alt = img_ev.get("alt", "").lower()

        event_type = None
        if "accion1" in src or "goal" in alt:           event_type = "goal"
        elif "accion5" in src or "yellow card" in alt:  event_type = "yellow"
        elif "tarjeta_r" in src or "red card" in alt:   event_type = "red"
        elif "cambio" in src or "substitution" in alt:  event_type = "sub"
        if not event_type: continue

        # Côté domicile/extérieur
        left  = row.select_one("div.col-side.left")
        right = row.select_one("div.col-side.right")
        left_has  = left  and (left.select_one("a[data-cy='eventOrd']") or left.select_one("div.name-wrapper"))
        right_has = right and (right.select_one("a[data-cy='eventOrd']") or right.select_one("div.name-wrapper"))
        is_home = bool(left_has) and not bool(right_has)

        if event_type == "sub":
            # Méthode 1 : popup avec player_id dans l'ID
            popup = row.select_one("div[id^='popup_event_order']")
            if popup:
                pid_m = re.search(r"_(\d+)_(\d+)$", popup.get("id", ""))
                if pid_m:
                    sub_min = int(pid_m.group(1))
                    sub_pid = pid_m.group(2)
                    key = f"sub_{sub_min}_{sub_pid}"
                    if key not in seen:
                        seen.add(key)
                        sub_in_minutes[sub_pid] = sub_min
                        print(f"    🔄 {sub_min}' pid={sub_pid} ({'dom' if is_home else 'ext'})")
            else:
                # Méthode 2 : player_id depuis href
                side = left if is_home else right
                if side:
                    for lnk in side.select("a[href*='/player/']"):
                        pid2 = extract_player_id(lnk.get("href", ""))
                        if pid2:
                            key = f"sub_{minute}_{pid2}"
                            if key not in seen:
                                seen.add(key)
                                sub_in_minutes[pid2] = minute
                                print(f"    🔄 {minute}' pid={pid2} ({'dom' if is_home else 'ext'})")
            continue

        # Buts / cartons
        side = left if is_home else right
        player_link = side.select_one("a[data-cy='eventOrd']") if side else None
        player_name = player_link.get_text(strip=True) if player_link else ""

        key = f"{event_type}_{minute}_{player_name}"
        if key in seen: continue
        seen.add(key)

        mini = row.select_one("div.mini-result")
        events.append({
            "type":    event_type,
            "minute":  minute,
            "team":    home_team if is_home else away_team,
            "is_home": is_home,
            "player":  player_name,
            "assist":  "",
            "score":   mini.get_text(strip=True) if mini else ""
        })
        icon = {"goal": "⚽", "yellow": "🟨", "red": "🟥"}.get(event_type, "?")
        print(f"    {icon} {minute}' {player_name} ({'dom' if is_home else 'ext'})") 

    print(f"  📊 Events: {len(events)} | Score: {score['home']}-{score['away']}")
    return sub_in_minutes, events, score

# ══════════════════════════════════════════════
# SCRAPE LINEUP
# ══════════════════════════════════════════════


def enrich_players_from_events(players, events):
    """Croise les events (buts/cartons) avec les players par nom."""
    for evt in events:
        pname  = evt.get("player", "")
        etype  = evt.get("type", "")
        minute = evt.get("minute")
        if not pname or not minute:
            continue
        for p in players:
            pn     = p.get("name", "").lower()
            en     = pname.lower()
            last_p = pn.split(".")[-1].strip()
            last_e = en.split(".")[-1].strip()
            match  = (pn == en) or                      (last_p and last_p in en) or                      (last_e and last_e in pn)
            if not match:
                continue
            if etype == "goal":
                if minute not in p.get("goal_minutes", []):
                    p["goals"] = p.get("goals", 0) + 1
                    gm = p.get("goal_minutes", [])
                    gm.append(minute)
                    p["goal_minutes"] = gm
            elif etype == "yellow" and not p.get("yellow"):
                p["yellow"]        = True
                p["yellow_minute"] = minute
            elif etype == "red" and not p.get("red"):
                p["red"]        = True
                p["red_minute"] = minute
            break
    return players

def scrape_lineup(match):
    url = match["url"]
    if not url.endswith("/lineups") and not url.endswith("/lineups/"):
        url = url.rstrip("/") + "/lineups"

    r = fetch(url)
    if not r:
        r = fetch(match["url"])
    if not r:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    print(f"  HTML size: {len(r.text)} chars")

    starters_all = soup.select('a.col-bench[data-cy="starterPlayer"]')
    print(f"  Titulaires trouvés: {len(starters_all)}")

    if len(starters_all) < 11:
        print(f"  ⏳ Compos pas encore officielles ({len(starters_all)} joueurs)")
        return None

    # ── Events live (buts, cartons, changements) ────────────
    sub_in_minutes, live_events, score = scrape_events_live(
        match["url"], match.get("home_team", ""), match.get("away_team", "")
    )
    print(f"  Changements: {sub_in_minutes}")

    result = {
        "match_id":       match["match_id"],
        "home_team":      match.get("home_team", ""),
        "away_team":      match.get("away_team", ""),
        "match_date":     match["date"],
        "home_players":   [],
        "away_players":   [],
        "home_subs":      [],
        "away_subs":      [],
        "home_formation": "",
        "away_formation": "",
        "home_score":     score["home"],
        "away_score":     score["away"],
        "events":         live_events,   # ← NOUVEAU : buts/cartons/changements
        "scraped_at":     datetime.now(timezone.utc).isoformat()
    }

    home_starters = soup.select('a.col-bench.local[data-cy="starterPlayer"]')
    away_starters = soup.select('a.col-bench.visitor[data-cy="starterPlayer"]')
    home_subs     = soup.select('a.col-bench.local[data-cy="benchPlayer"]')
    away_subs     = soup.select('a.col-bench.visitor[data-cy="benchPlayer"]')

    for link in home_starters:
        p = parse_player(link)
        if p: result["home_players"].append(p)

    for link in away_starters:
        p = parse_player(link)
        if p: result["away_players"].append(p)

    def match_sub_minute(player_id, sub_dict):
        """Cherche la minute d'entrée d'un remplaçant par player_id"""
        if not player_id:
            return None
        return sub_dict.get(player_id)

    for link in home_subs:
        p = parse_player(link)
        if p:
            sub_min = match_sub_minute(p["id"], sub_in_minutes)
            p["minutes"]        = sub_min if sub_min else 0
            p["sub_in_minute"]  = sub_min
            result["home_subs"].append(p)

    for link in away_subs:
        p = parse_player(link)
        if p:
            sub_min = match_sub_minute(p["id"], sub_in_minutes)
            p["minutes"]        = sub_min if sub_min else 0
            p["sub_in_minute"]  = sub_min
            result["away_subs"].append(p)

    # ── Enrichir players avec events (buts/cartons depuis /events) ──
    home_evts = [e for e in live_events if e.get("is_home")]
    away_evts = [e for e in live_events if not e.get("is_home")]
    result["home_players"] = enrich_players_from_events(result["home_players"], home_evts)
    result["away_players"] = enrich_players_from_events(result["away_players"], away_evts)
    result["home_subs"]    = enrich_players_from_events(result["home_subs"],    home_evts)
    result["away_subs"]    = enrich_players_from_events(result["away_subs"],    away_evts)

    h  = len(result["home_players"])
    a  = len(result["away_players"])
    hs = len(result["home_subs"])
    as_= len(result["away_subs"])
    gc = sum(p.get("goals",0) for p in result["home_players"]+result["away_players"]+result["home_subs"]+result["away_subs"])
    print(f"  ✅ Compo : {h} vs {a} titulaires | {hs} vs {as_} remplaçants | {gc} buts | {len(live_events)} events")

    # ── PLUS DE BLOCAGE has_notes — on sauvegarde toujours ──
    return result

# ══════════════════════════════════════════════
# SUPABASE
# ══════════════════════════════════════════════

def lineup_status(match_id):
    """
    Retourne:
    - "none"     : pas encore en base
    - "lineups"  : compos en base, pas d'events
    - "complete" : compos + notes (match terminé) → ne plus toucher
    """
    try:
        r = requests.get(
            SB_URL + f"/rest/v1/besoccer_lineups?match_id=eq.{match_id}&select=home_players,events",
            headers={**SB_HEADERS, "Prefer": ""}
        ).json()
        if not r or not r[0].get("home_players"):
            return "none"
        # Si tous les joueurs ont une note → match terminé
        players = r[0].get("home_players", [])
        has_notes = any(p.get("rating") for p in players if isinstance(p, dict))
        return "complete" if has_notes else "lineups"
    except:
        return "none"

def save_lineup(lineup):
    res = requests.post(
        SB_URL + "/rest/v1/besoccer_lineups",
        headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
        params={"on_conflict": "match_id"},
        json=lineup
    )
    code = res.status_code
    print(f"  Supabase: {'✅ OK' if code in [200,201,204] else '❌ '+str(code)+' '+res.text[:120]}")

def update_events(match_id, events, home_score, away_score, home_players, away_players, home_subs, away_subs):
    """Met à jour uniquement les events + score (sans réécrire tout le lineup)"""
    payload = {
        "events":       events,
        "home_score":   home_score,
        "away_score":   away_score,
        "home_players": home_players,
        "away_players": away_players,
        "home_subs":    home_subs,
        "away_subs":    away_subs,
        "scraped_at":   datetime.now(timezone.utc).isoformat()
    }
    res = requests.patch(
        SB_URL + f"/rest/v1/besoccer_lineups?match_id=eq.{match_id}",
        headers={**SB_HEADERS, "Prefer": ""},
        json=payload
    )
    code = res.status_code
    print(f"  Events update: {'✅ OK' if code in [200,201,204] else '❌ '+str(code)+' '+res.text[:120]}")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

print("=== BeSoccer Lineups + Events Scraper ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

matches = get_today_matches()
print(f"\nMatchs trouvés : {len(matches)}")

if not matches:
    print("Aucun match — OK")
    exit(0)

for match in matches:
    home = match.get("home_team")
    away = match.get("away_team")
    mid  = match["match_id"]
    print(f"\n--- {home} vs {away} | id={mid} ---")

    status = lineup_status(mid)
    print(f"  Status: {status}")

    if status == "complete":
        # Match terminé avec notes → on skip pour ne pas écraser
        print("  ✓ Match terminé, données complètes — skip")
        continue

    lineup = scrape_lineup(match)
    if not lineup:
        print("  Compos pas encore dispo")
        time.sleep(2)
        continue

    if status == "none":
        # Première fois → sauvegarder tout
        save_lineup(lineup)
    else:
        # Compos déjà en base → mettre à jour uniquement events + score + joueurs (cartons/buts)
        update_events(
            mid,
            lineup["events"],
            lineup["home_score"],
            lineup["away_score"],
            lineup["home_players"],
            lineup["away_players"],
            lineup["home_subs"],
            lineup["away_subs"]
        )

    time.sleep(2)

print("\n=== Terminé ===")