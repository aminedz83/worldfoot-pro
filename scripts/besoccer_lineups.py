"""
besoccer_lineups.py
===================
Scrape les compositions des matchs de Ligue 1 Algérie depuis BeSoccer.
Utilise l'API interne BeSoccer pour trouver les matchs du jour.
Sauvegarde dans Supabase : besoccer_lineups
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

# API BeSoccer interne — Ligue 1 Algérie
# league=311, year=2026
BS_API_URL = "https://www.besoccer.com/competition/json/competition_matches_v2"
BS_LEAGUE  = "311"
BS_YEAR    = "2026"

# ══════════════════════════════════════════════
# CLOUDSCRAPER
# ══════════════════════════════════════════════

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

def fetch_html(url):
    try:
        r = scraper.get(url, timeout=20)
        print(f"  Status {r.status_code} : {url}")
        if r.status_code == 200:
            return BeautifulSoup(r.text, "html.parser")
        return None
    except Exception as e:
        print(f"  Erreur: {e}")
        return None

def fetch_json(url, params=None):
    try:
        r = scraper.get(url, params=params, timeout=20)
        print(f"  API Status {r.status_code} : {url}")
        if r.status_code == 200:
            return r.json()
        return None
    except Exception as e:
        print(f"  Erreur API: {e}")
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
# MATCHS DU JOUR — via API interne BeSoccer
# ══════════════════════════════════════════════

def get_current_round():
    """Récupère le round actuel depuis la page compétition."""
    soup = fetch_html("https://www.besoccer.com/competition/ligue_1_algeria")
    if not soup:
        return "26"
    # Chercher dans data_params
    data_div = soup.select_one("#data_params")
    if data_div:
        params_str = data_div.get("data-params", "")
        try:
            params = json.loads(params_str)
            round_num = params.get("req", {}).get("round", "26")
            print(f"  Round actuel: {round_num}")
            return str(round_num)
        except:
            pass
    # Fallback : chercher dans le texte
    m = re.search(r"Matchday\s+(\d+)", soup.get_text())
    if m:
        return m.group(1)
    return "26"

def get_today_matches():
    """
    Récupère les matchs du jour via l'API interne BeSoccer.
    Format: /competition/json/competition_matches_v2?league=311&year=2026&round=26
    """
    today  = date.today().strftime("%Y-%m-%d")
    matches = []
    seen    = set()

    print(f"\nRecherche matchs du {today}...")

    # Récupérer le round actuel
    current_round = get_current_round()

    # Essayer les rounds autour du round actuel (au cas où des matchs sont en retard)
    rounds_to_try = [current_round]
    try:
        r = int(current_round)
        if r > 1:
            rounds_to_try.append(str(r - 1))
        rounds_to_try.append(str(r + 1))
    except:
        pass

    for round_num in rounds_to_try:
        print(f"  Vérification round {round_num}...")

        # Appel API interne
        data = fetch_json(
            BS_API_URL,
            params={
                "req":    "competition_matches_v2",
                "vr":     "3",
                "isocode":"ca",
                "group":  "1",
                "league": BS_LEAGUE,
                "year":   BS_YEAR,
                "round":  round_num,
                "lang":   "en"
            }
        )

        if not data:
            # Fallback: essayer l'URL directe avec le round
            scores_url = f"https://www.besoccer.com/competition/scores/ligue_1_algeria/{BS_YEAR}/{round_num}"
            soup = fetch_html(scores_url)
            if soup:
                data = parse_matches_from_html(soup, today, seen, matches)
            continue

        # Parser la réponse JSON
        if isinstance(data, dict):
            match_list = data.get("matches", data.get("data", data.get("games", [])))
        elif isinstance(data, list):
            match_list = data
        else:
            match_list = []

        print(f"  {len(match_list)} matchs dans le round {round_num}")

        for m in match_list:
            # Extraire la date du match
            match_date = (
                m.get("date", "") or
                m.get("match_date", "") or
                m.get("fecha", "") or ""
            )

            # Normaliser la date
            if match_date and today not in match_date:
                # Essayer de parser différents formats
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
                    try:
                        d = datetime.strptime(match_date[:10], fmt)
                        match_date = d.strftime("%Y-%m-%d")
                        break
                    except:
                        pass

            if today not in str(match_date):
                continue

            # Extraire l'ID et l'URL du match
            match_id = (
                str(m.get("id", "")) or
                str(m.get("match_id", "")) or
                extract_match_id(m.get("url", "") or m.get("link", ""))
            )
            if not match_id or match_id in seen:
                continue

            seen.add(match_id)

            match_url = m.get("url", "") or m.get("link", "") or ""
            if match_url and not match_url.startswith("http"):
                match_url = "https://www.besoccer.com" + match_url

            home = m.get("local", m.get("home", m.get("home_team", "")))
            away = m.get("visitor", m.get("away", m.get("away_team", "")))

            # Si home/away sont des dicts
            if isinstance(home, dict):
                home = home.get("name", home.get("nombre", ""))
            if isinstance(away, dict):
                away = away.get("name", away.get("nombre", ""))

            matches.append({
                "match_id":  match_id,
                "url":       match_url,
                "home_team": str(home),
                "away_team": str(away),
                "date":      today
            })
            print(f"  ✅ Match: {home} vs {away} | id={match_id}")

        time.sleep(1)

    # Si toujours rien → essayer la page scores directement
    if not matches:
        print("  Essai page scores directe...")
        scores_url = f"https://www.besoccer.com/competition/scores/ligue_1_algeria/{BS_YEAR}/{current_round}"
        soup = fetch_html(scores_url)
        if soup:
            parse_matches_from_html(soup, today, seen, matches)

    return matches


def parse_matches_from_html(soup, today, seen, matches):
    """Parse les matchs depuis le HTML statique si disponible."""
    today_dmy  = date.today().strftime("%d/%m/%Y")
    today_dmy2 = date.today().strftime("%d/%m/%y")
    today_apr  = date.today().strftime("%-d %b. %Y")  # ex: "10 Apr. 2026"

    for a in soup.select("a[href*='/match/']"):
        href     = a.get("href", "")
        match_id = extract_match_id(href)
        if not match_id or match_id in seen:
            continue

        parent   = a.find_parent(["tr", "li", "div", "article"])
        row_text = parent.get_text(" ") if parent else ""

        is_today = any(d in row_text for d in [today, today_dmy, today_dmy2, today_apr])
        if not is_today:
            continue

        seen.add(match_id)
        match_url = "https://www.besoccer.com" + href if href.startswith("/") else href

        # Noms équipes depuis les divs .team-name
        home_el = parent.select_one(".team-name.ta-r, .local .team-name") if parent else None
        away_el = parent.select_one(".team-name.ta-l, .visitor .team-name") if parent else None

        matches.append({
            "match_id":  match_id,
            "url":       match_url,
            "home_team": home_el.get_text(strip=True) if home_el else "",
            "away_team": away_el.get_text(strip=True) if away_el else "",
            "date":      today
        })
        print(f"  ✅ Match HTML: {match_id}")

    return matches

# ══════════════════════════════════════════════
# DÉTECTION COMPO OFFICIELLE
# ══════════════════════════════════════════════

def is_official(soup):
    if not soup:
        return False
    text = soup.get_text(" ").lower()
    official_kw = ["alineacion oficial", "official lineup", "confirmed",
                   "confirmé", "lineup confirmed", "alineación oficial"]
    probable_kw = ["probable", "predicted", "prevista", "prévu", "expected"]
    has_official = any(k in text for k in official_kw)
    has_probable = any(k in text for k in probable_kw)

    lineup_section = soup.select_one(
        ".match-lineup, .lineup, [class*='lineup'], .team-lineup, .alineacion"
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
        print("  ⚠️  Pas d'URL pour ce match")
        return None

    soup = fetch_html(match["url"])
    if not soup:
        return None

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

    # Noms équipes
    team_names = soup.select(".team-name, .match-team-name, h2.team, .local .name, .visitante .name")
    if len(team_names) >= 2:
        result["home_team"] = result["home_team"] or team_names[0].get_text(strip=True)
        result["away_team"] = result["away_team"] or team_names[1].get_text(strip=True)

    # Formation
    formation_els = soup.select(".formation, [class*='formation'], .tactic")
    formations = [f.get_text(strip=True) for f in formation_els if re.match(r"\d-\d", f.get_text(strip=True))]
    if len(formations) >= 1:
        result["home_formation"] = formations[0]
    if len(formations) >= 2:
        result["away_formation"] = formations[1]

    # Sections équipes
    team_sections = soup.select(
        ".lineup-team, .team-lineup, [class*='lineup-team'], "
        ".match-lineup .team, .alineacion .equipo"
    )

    for idx, section in enumerate(team_sections[:2]):
        key_pl  = "home_players" if idx == 0 else "away_players"
        key_sub = "home_subs"    if idx == 0 else "away_subs"
        starters = []
        subs     = []

        for i, link in enumerate(section.select("a[href*='/player/']")):
            href      = link.get("href", "")
            player_id = extract_player_id(href)
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
                "goals":   0,
                "yellow":  False,
                "red":     False,
                "minutes": 90 if i < 11 else 0,
            }

            if i < 11:
                starters.append(player)
            else:
                subs.append(player)

        result[key_pl]  = starters
        result[key_sub] = subs

    h = len(result["home_players"])
    a = len(result["away_players"])
    print(f"  ✅ Compo : {h} vs {a} titulaires | {result['home_formation']} / {result['away_formation']}")
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