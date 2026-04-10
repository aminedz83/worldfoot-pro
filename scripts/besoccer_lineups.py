"""
besoccer_lineups.py
===================
Scrape les compositions des matchs de Ligue 1 Algérie depuis BeSoccer.
Tourne toutes les 5 minutes pour détecter les compos officielles.
Sauvegarde dans Supabase table : besoccer_lineups
"""

import os, re, time, requests
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer": "https://www.besoccer.com/",
}

# IDs des 16 clubs pour filtrer les matchs du jour
CLUB_IDS = [
    11505, 11507, 11506, 11504, 11501, 11510,
    59336, 11511, 11509, 20933, 11729, 11530,
    11522, 13715, 100882, 11519
]

CLUB_SLUGS = {
    11505: "mc-alger",       11507: "cr-belouizdad",
    11506: "js-kabylie",     11504: "usm-alger",
    11501: "es-setif",       11510: "cs-constantine",
    59336: "paradou-ac",     11511: "aso-chlef",
    11509: "mc-oran",        20933: "js-saoura",
    11729: "mc-el-bayadh",   11530: "usm-khenchela",
    11522: "olympique-akbou",13715: "es-mostaganem",
    100882:"mb-rouissat",    11519: "es-ben-aknoun",
}

CLUB_NAMES = {
    11505: "MC Alger",       11507: "CR Belouizdad",
    11506: "JS Kabylie",     11504: "USM Alger",
    11501: "ES Sétif",       11510: "CS Constantine",
    59336: "Paradou AC",     11511: "ASO Chlef",
    11509: "MC Oran",        20933: "JS Saoura",
    11729: "MC El Bayadh",   11530: "USM Khenchela",
    11522: "Olympique Akbou",13715: "ES Mostaganem",
    100882:"MB Rouissat",    11519: "ES Ben Aknoun",
}

# ══════════════════════════════════════════════
# FETCH
# ══════════════════════════════════════════════

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
        print(f"  Status {r.status_code} : {url}")
        return None
    except Exception as e:
        print(f"  Erreur : {e}")
        return None

def extract_id(href):
    if not href:
        return None
    m = re.search(r"/player/[^/]+/(\d+)/?", href)
    return m.group(1) if m else None

# ══════════════════════════════════════════════
# MATCHS DU JOUR
# ══════════════════════════════════════════════

def get_today_matches():
    """Récupère les matchs du jour pour les 16 clubs depuis BeSoccer."""
    today = date.today().strftime("%Y-%m-%d")
    matches = []
    seen    = set()

    for club_id in CLUB_IDS:
        slug = CLUB_SLUGS[club_id]
        url  = f"https://www.besoccer.com/team/matches/{slug}/{club_id}/"

        soup = fetch(url)
        if not soup:
            time.sleep(1)
            continue

        # Chercher les matchs du jour
        for row in soup.select("a[href*='/match/']"):
            href     = row.get("href", "")
            match_id = extract_match_id(href)
            if not match_id or match_id in seen:
                continue

            # Vérifier si c'est aujourd'hui
            date_el = row.select_one(".date, .match-date, time")
            if date_el:
                date_text = date_el.get_text(strip=True)
                if today not in date_text and not is_today(date_text):
                    continue

            seen.add(match_id)

            # Extraire équipes depuis l'URL /match/equipe1-equipe2/id/
            m = re.search(r"/match/([^/]+)-([^/]+)/(\d+)/?", href)
            if m:
                matches.append({
                    "match_id":   match_id,
                    "slug1":      m.group(1),
                    "slug2":      m.group(2),
                    "url":        "https://www.besoccer.com" + href,
                    "date":       today
                })
                print(f"  ✅ Match trouvé: {m.group(1)} vs {m.group(2)} | id={match_id}")

        time.sleep(1)

    return matches

def extract_match_id(href):
    """Extrait l'ID du match depuis l'URL BeSoccer."""
    if not href:
        return None
    m = re.search(r"/match/[^/]+/[^/]+/(\d+)/?", href)
    if m:
        return m.group(1)
    # Format alternatif
    m = re.search(r"/match/[^/]+/(\d+)/?", href)
    return m.group(1) if m else None

def is_today(date_text):
    """Vérifie si une date correspond à aujourd'hui."""
    today = date.today()
    patterns = [
        today.strftime("%d/%m/%Y"),
        today.strftime("%d/%m/%y"),
        today.strftime("%d.%m.%Y"),
        today.strftime("%Y-%m-%d"),
    ]
    return any(p in date_text for p in patterns)

# ══════════════════════════════════════════════
# SCRAPE COMPOSITIONS
# ══════════════════════════════════════════════

def is_official(soup):
    """Vérifie si les compositions sont officielles (pas probables)."""
    if not soup:
        return False
    text = soup.get_text(" ").lower()

    # Signaux officiels
    official = ["alineacion oficial", "official lineup", "lineup officiel",
                "titulares", "once inicial", "composition officielle"]
    probable = ["probable", "predicted", "prevista", "prévu", "expected"]

    has_official = any(k in text for k in official)
    has_probable = any(k in text for k in probable)

    # Vérifier aussi la présence d'au moins 11 joueurs dans la section compo
    lineup_section = soup.select_one(
        ".match-lineup, .lineup, [class*='lineup'], .team-lineup"
    )
    if lineup_section:
        players = lineup_section.select("a[href*='/player/']")
        if len(players) >= 11 and not has_probable:
            return True

    return has_official and not has_probable


def scrape_lineup(match):
    """Scrape les compositions d'un match."""
    url = match["url"]
    print(f"  Scraping : {url}")

    soup = fetch(url)
    if not soup:
        return None

    if not is_official(soup):
        print(f"  ⏳ Compos pas encore officielles")
        return None

    result = {
        "match_id":      match["match_id"],
        "home_team":     "",
        "away_team":     "",
        "match_date":    match["date"],
        "home_players":  [],
        "away_players":  [],
        "home_subs":     [],
        "away_subs":     [],
        "home_formation":"",
        "away_formation":"",
        "scraped_at":    datetime.now(timezone.utc).isoformat()
    }

    # Noms des équipes
    team_els = soup.select(".team-name, .match-team h2, h2.team")
    if len(team_els) >= 2:
        result["home_team"] = team_els[0].get_text(strip=True)
        result["away_team"] = team_els[1].get_text(strip=True)

    # Formations
    formations = soup.select(".formation, [class*='formation'], .tactic")
    if len(formations) >= 1:
        result["home_formation"] = formations[0].get_text(strip=True)
    if len(formations) >= 2:
        result["away_formation"] = formations[1].get_text(strip=True)

    # Sections des deux équipes
    team_sections = soup.select(
        ".lineup-team, .team-lineup, [class*='lineup-team'], .match-team-players"
    )

    for idx, section in enumerate(team_sections[:2]):
        team_key_pl  = "home_players"  if idx == 0 else "away_players"
        team_key_sub = "home_subs"     if idx == 0 else "away_subs"

        starters = []
        subs     = []

        player_links = section.select("a[href*='/player/']")

        for i, link in enumerate(player_links):
            href      = link.get("href", "")
            player_id = extract_id(href)
            nom       = link.get_text(strip=True)
            if not player_id or not nom:
                continue

            parent  = link.find_parent(["li", "tr", "div"])
            pos_el  = parent.select_one(".pos, .position") if parent else None
            num_el  = parent.select_one(".num, .number, .shirt") if parent else None

            photo = f"https://cdn.resfu.com/img_data/players/medium/{player_id}.jpg"

            player = {
                "name":       nom,
                "id":         player_id,
                "number":     num_el.get_text(strip=True) if num_el else "",
                "pos":        pos_el.get_text(strip=True) if pos_el else "",
                "photo":      photo,
                "goals":      0,
                "yellow":     False,
                "red":        False,
                "minutes":    90 if i < 11 else 0,
            }

            if i < 11:
                starters.append(player)
            else:
                subs.append(player)

        result[team_key_pl]  = starters
        result[team_key_sub] = subs

    home_count = len(result["home_players"])
    away_count = len(result["away_players"])
    print(f"  ✅ Compo officielle : {home_count} vs {away_count} titulaires")

    return result

# ══════════════════════════════════════════════
# ÉVÉNEMENTS (buts, cartons)
# ══════════════════════════════════════════════

def scrape_events(soup, match_id):
    """Met à jour buts et cartons depuis les événements du match."""
    events = {"goals": [], "yellow": [], "red": [], "subs": []}
    if not soup:
        return events

    event_rows = soup.select(
        ".match-event, .event-row, [class*='match-event'], .timeline li"
    )

    for row in event_rows:
        row_low = row.get_text(" ").lower()
        link    = row.select_one("a[href*='/player/']")
        pid     = extract_id(link.get("href", "")) if link else None
        name    = link.get_text(strip=True) if link else ""

        min_m   = re.search(r"(\d{1,3})'", row.get_text())
        minute  = int(min_m.group(1)) if min_m else None

        if any(k in row_low for k in ["goal", "but", "gol"]):
            events["goals"].append({"player_id": pid, "name": name, "minute": minute})
        elif any(k in row_low for k in ["yellow", "jaune", "amarill"]):
            events["yellow"].append({"player_id": pid, "name": name, "minute": minute})
        elif any(k in row_low for k in ["red", "rouge", "roja"]):
            events["red"].append({"player_id": pid, "name": name, "minute": minute})

    return events

# ══════════════════════════════════════════════
# SAUVEGARDE SUPABASE
# ══════════════════════════════════════════════

def already_scraped(match_id):
    """Vérifie si le match est déjà dans Supabase avec des compositions."""
    try:
        r = requests.get(
            SB_URL + f"/rest/v1/besoccer_lineups?match_id=eq.{match_id}&select=id,home_players",
            headers={**SB_HEADERS, "Prefer": ""}
        ).json()
        if r and r[0].get("home_players") and len(r[0]["home_players"]) > 0:
            return True
    except:
        pass
    return False

def save_lineup(lineup):
    """Upsert dans besoccer_lineups."""
    res = requests.post(
        SB_URL + "/rest/v1/besoccer_lineups",
        headers=SB_HEADERS,
        json=lineup
    )
    code = res.status_code
    print(f"  Supabase: {code} ({'OK' if code in [200,201,204] else res.text[:200]})")

    if code == 409:
        patch = requests.patch(
            SB_URL + f"/rest/v1/besoccer_lineups?match_id=eq.{lineup['match_id']}",
            headers=SB_HEADERS,
            json=lineup
        )
        print(f"  PATCH: {patch.status_code}")

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
    mid = match["match_id"]
    print(f"\n--- Match {mid} : {match['slug1']} vs {match['slug2']} ---")

    if already_scraped(mid):
        print("  Déjà scrapé ✓")
        continue

    lineup = scrape_lineup(match)
    if lineup:
        save_lineup(lineup)
    else:
        print("  Pas encore dispo")

    time.sleep(2)

print("\n=== Terminé ===")
