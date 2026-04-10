"""
besoccer_lineups.py
===================
Scrape les compositions Ligue 1 Algérie depuis BeSoccer.
Stratégie : cherche les matchs du jour via la page scores avec date exacte.
URL format : /competition/scores/ligue_1_algeria/YYYY/round
Les matchs sont dans le JSON embarqué dans la page (data-params ou script JSON-LD).
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

# Mapping équipes BeSoccer → slugs pour construire les URLs de match
TEAM_SLUGS = {
    "MC Alger":        "mc-alger",
    "CR Belouizdad":   "belouizdad",
    "JS Kabylie":      "kabylie",
    "USM Alger":       "usm-alger",
    "ES Sétif":        "es-setif",
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

# ══════════════════════════════════════════════
# CLOUDSCRAPER
# ══════════════════════════════════════════════

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

def fetch(url):
    try:
        r = scraper.get(url, timeout=20)
        print(f"  Status {r.status_code} : {url}")
        if r.status_code == 200:
            return r
        return None
    except Exception as e:
        print(f"  Erreur: {e}")
        return None

def extract_player_id(href):
    if not href:
        return None
    m = re.search(r"/player/[^/]+-(\d+)/?$", href)
    if m:
        return m.group(1)
    m = re.search(r"/player/([^/]+)/?$", href)
    return m.group(1) if m else None

def extract_match_id(href):
    if not href:
        return None
    m = re.search(r"/match/[^/]+/(\d+)/?", href)
    return m.group(1) if m else None

# ══════════════════════════════════════════════
# MATCHS DU JOUR
# ══════════════════════════════════════════════

def get_today_matches():
    """
    Cherche les matchs du jour en scannant les pages de rounds BeSoccer.
    BeSoccer charge les matchs via JS, mais les URLs des matchs sont dans
    les liens <a href="/match/..."> présents dans le HTML des pages de round.
    On cherche aussi dans les balises JSON-LD et data attributes.
    """
    today     = date.today().strftime("%Y-%m-%d")
    today_fmt = [
        date.today().strftime("%d/%m/%Y"),
        date.today().strftime("%d/%m/%y"),
        date.today().strftime("%-d %b. %Y"),    # "10 Apr. 2026"
        date.today().strftime("%d %b. %Y"),     # "10 Apr. 2026"
        date.today().strftime("%B %-d, %Y"),    # "April 10, 2026"
        date.today().strftime("%Y-%m-%d"),
    ]
    matches = []
    seen    = set()

    print(f"\nRecherche matchs du {today}...")

    # Récupérer le round actuel depuis la page principale
    r = fetch("https://www.besoccer.com/competition/ligue_1_algeria")
    current_round = "26"
    if r:
        soup = BeautifulSoup(r.text, "html.parser")
        data_div = soup.select_one("#data_params")
        if data_div:
            try:
                params = json.loads(data_div.get("data-params", "{}"))
                current_round = str(params.get("req", {}).get("round", "26"))
            except:
                pass
        m = re.search(r"round[\"'\s:]+(\d+)", r.text, re.IGNORECASE)
        if m:
            current_round = m.group(1)
    print(f"  Round actuel: {current_round}")

    # Scanner les rounds autour du round actuel
    try:
        base = int(current_round)
        rounds = [base, base-1, base+1]
    except:
        rounds = [26, 25, 27]

    for round_num in rounds:
        url = f"https://www.besoccer.com/competition/scores/ligue_1_algeria/2026/{round_num}"
        r = fetch(url)
        if not r:
            time.sleep(1)
            continue

        text = r.text

        # Chercher les matchs dans le JSON-LD
        for script in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', text, re.DOTALL):
            try:
                data = json.loads(script)
                events = data if isinstance(data, list) else [data]
                for ev in events:
                    if ev.get("@type") in ["SportsEvent", "Event"]:
                        start = ev.get("startDate", "")
                        if today in str(start):
                            url_ev = ev.get("url", "")
                            match_id = extract_match_id(url_ev)
                            if match_id and match_id not in seen:
                                seen.add(match_id)
                                home = ev.get("homeTeam", {}).get("name", "")
                                away = ev.get("awayTeam", {}).get("name", "")
                                if not home and isinstance(ev.get("competitor"), list):
                                    teams = ev["competitor"]
                                    home = teams[0].get("name", "") if teams else ""
                                    away = teams[1].get("name", "") if len(teams) > 1 else ""
                                matches.append({
                                    "match_id":  match_id,
                                    "url":       "https://www.besoccer.com" + url_ev if url_ev.startswith("/") else url_ev,
                                    "home_team": home,
                                    "away_team": away,
                                    "date":      today
                                })
                                print(f"  ✅ JSON-LD: {home} vs {away} | id={match_id}")
            except:
                pass

        # Chercher les matchs dans les liens /match/ avec vérification de date
        soup = BeautifulSoup(text, "html.parser")
        for a in soup.select("a.match-link, a[href*='/match/']"):
            href = a.get("href", "")
            match_id = extract_match_id(href)
            if not match_id or match_id in seen:
                continue

            # Vérifier la date dans le parent
            parent = a.find_parent(["tr", "li", "div", "article"])
            row_text = parent.get_text(" ") if parent else ""

            # Chercher ".date" dans le parent
            date_el = parent.select_one(".date, time, [class*='date']") if parent else None
            date_text = date_el.get_text(strip=True) if date_el else ""

            is_today = any(d in row_text or d in date_text for d in today_fmt)

            if not is_today:
                continue

            seen.add(match_id)
            match_url = "https://www.besoccer.com" + href if href.startswith("/") else href

            # Noms équipes
            home_el = parent.select_one(".team-name.ta-r, .local .team-name, .team-info.ta-r .team-name") if parent else None
            away_el = parent.select_one(".team-name.ta-l, .visitor .team-name, .team-info:not(.ta-r) .team-name") if parent else None

            matches.append({
                "match_id":  match_id,
                "url":       match_url,
                "home_team": home_el.get_text(strip=True) if home_el else "",
                "away_team": away_el.get_text(strip=True) if away_el else "",
                "date":      today
            })
            print(f"  ✅ HTML: {match_id}")

        time.sleep(1)

    # ── Fallback : construire les URLs depuis Supabase algeria_lineups ──────
    # Si on n'a toujours rien, chercher les matchs du jour dans algeria_lineups
    # et construire les URLs BeSoccer à partir des noms d'équipes
    if not matches:
        print("  Fallback : cherche matchs dans algeria_lineups (Flashscore)...")
        try:
            r2 = requests.get(
                SB_URL + f"/rest/v1/algeria_lineups?match_date=eq.{today}&select=home_team,away_team,soccerway_mid",
                headers={**SB_HEADERS, "Prefer": ""}
            )
            rows = r2.json() if r2.status_code == 200 else []
            for row in rows:
                home = row.get("home_team", "")
                away = row.get("away_team", "")
                home_slug = TEAM_SLUGS.get(home, home.lower().replace(" ", "-"))
                away_slug = TEAM_SLUGS.get(away, away.lower().replace(" ", "-"))
                # URL format BeSoccer : /match/home-away/
                # On ne connaît pas l'ID mais on peut essayer de le chercher
                search_url = f"https://www.besoccer.com/match/{home_slug}/{away_slug}/"
                print(f"  🔍 Essai URL: {search_url}")
                r3 = fetch(search_url)
                if r3 and r3.status_code == 200:
                    match_id = extract_match_id(r3.url)
                    if not match_id:
                        # Chercher l'ID dans l'URL finale (après redirect)
                        m = re.search(r"/match/[^/]+/[^/]+/(\d+)/?", r3.url)
                        if m:
                            match_id = m.group(1)
                    if match_id and match_id not in seen:
                        seen.add(match_id)
                        matches.append({
                            "match_id":  match_id,
                            "url":       r3.url,
                            "home_team": home,
                            "away_team": away,
                            "date":      today
                        })
                        print(f"  ✅ Fallback: {home} vs {away} | id={match_id}")
                time.sleep(1)
        except Exception as e:
            print(f"  Erreur fallback: {e}")

    return matches

# ══════════════════════════════════════════════
# DÉTECTION COMPO OFFICIELLE
# ══════════════════════════════════════════════

def is_official(soup):
    if not soup:
        return False
    text = soup.get_text(" ").lower()
    official_kw = ["alineacion oficial", "official lineup", "confirmed",
                   "confirmé", "alineación oficial"]
    probable_kw = ["probable", "predicted", "prevista", "prévu", "expected"]
    has_official = any(k in text for k in official_kw)
    has_probable = any(k in text for k in probable_kw)

    lineup_section = soup.select_one(
        ".match-lineup, .lineup, [class*='lineup'], .alineacion"
    )
    if lineup_section:
        players = lineup_section.select("a[href*='/player/']")
        if len(players) >= 11 and not has_probable:
            return True

    return has_official and not has_probable

# ══════════════════════════════════════════════
# SCRAPE COMPOSITION
# ══════════════════════════════════════════════

def scrape_lineup(match):
    if not match.get("url"):
        return None
    r = fetch(match["url"])
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    if not is_official(soup):
        print(f"  ⏳ Compos pas encore officielles")
        return None

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
        "scraped_at":     datetime.now(timezone.utc).isoformat()
    }

    # Formation
    formations = [f.get_text(strip=True) for f in soup.select(".formation, [class*='formation']")
                  if re.match(r"\d-\d", f.get_text(strip=True))]
    if len(formations) >= 1: result["home_formation"] = formations[0]
    if len(formations) >= 2: result["away_formation"] = formations[1]

    # Sections équipes
    team_sections = soup.select(".lineup-team, [class*='lineup-team'], .match-lineup .team, .alineacion .equipo")

    for idx, section in enumerate(team_sections[:2]):
        key_pl  = "home_players" if idx == 0 else "away_players"
        key_sub = "home_subs"    if idx == 0 else "away_subs"
        starters, subs = [], []

        for i, link in enumerate(section.select("a[href*='/player/']")):
            player_id = extract_player_id(link.get("href", ""))
            nom       = link.get_text(strip=True)
            if not player_id or not nom:
                continue
            parent = link.find_parent(["li", "tr", "div"])
            pos_el = parent.select_one(".pos, .position, .demarcacion") if parent else None
            num_el = parent.select_one(".num, .number, .dorsal") if parent else None
            player = {
                "name":    nom,
                "id":      player_id,
                "number":  num_el.get_text(strip=True) if num_el else "",
                "pos":     pos_el.get_text(strip=True) if pos_el else "",
                "photo":   f"https://cdn.resfu.com/img_data/players/medium/{player_id}.jpg?size=120x&lossy=1",
                "goals": 0, "yellow": False, "red": False,
                "minutes": 90 if i < 11 else 0,
            }
            (starters if i < 11 else subs).append(player)

        result[key_pl]  = starters
        result[key_sub] = subs

    h, a = len(result["home_players"]), len(result["away_players"])
    print(f"  ✅ Compo : {h} vs {a} | {result['home_formation']} / {result['away_formation']}")
    return result

# ══════════════════════════════════════════════
# SUPABASE
# ══════════════════════════════════════════════

def already_scraped(match_id):
    try:
        r = requests.get(
            SB_URL + f"/rest/v1/besoccer_lineups?match_id=eq.{match_id}&select=id,home_players",
            headers={**SB_HEADERS, "Prefer": ""}
        ).json()
        return bool(r and r[0].get("home_players") and len(r[0]["home_players"]) > 0)
    except:
        return False

def save_lineup(lineup):
    res = requests.post(
        SB_URL + "/rest/v1/besoccer_lineups",
        headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
        params={"on_conflict": "match_id"},
        json=lineup
    )
    code = res.status_code
    print(f"  Supabase: {'✅ OK' if code in [200,201,204] else '❌ '+str(code)+' '+res.text[:100]}")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

print("=== BeSoccer Lineups Scraper ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

matches = get_today_matches()
print(f"\nMatchs aujourd'hui : {len(matches)}")

if not matches:
    print("Aucun match — OK")
    exit(0)

for match in matches:
    print(f"\n--- {match.get('home_team','?')} vs {match.get('away_team','?')} | id={match['match_id']} ---")
    if already_scraped(match["match_id"]):
        print("  Déjà scrapé ✓")
        continue
    lineup = scrape_lineup(match)
    if lineup:
        save_lineup(lineup)
    else:
        print("  Pas encore dispo")
    time.sleep(2)

print("\n=== Terminé ===")