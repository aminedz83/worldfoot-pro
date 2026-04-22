"""
sync_match_ids.py
-----------------
Tourne chaque jour a 6h UTC via GitHub Actions.
Pour chaque match de Ligue 1 Algerie dans les 14 prochains jours :
  1. Recupere l'ID API football via /fixtures
  2. Cherche le match_id BeSoccer via la page matchs du club
  3. Sauvegarde dans algeria_match_ids
"""

import os, re, time, unicodedata
import cloudscraper
from datetime import datetime, timedelta
import requests
from supabase import create_client

# Credentials
SUPABASE_URL     = os.environ["SUPABASE_URL"]
SUPABASE_KEY     = os.environ["SUPABASE_KEY"]
API_FOOTBALL_KEY = os.environ["API_FOOTBALL_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

API_BASE   = "https://v3.football.api-sports.io"
BS_BASE    = "https://www.besoccer.com"
LEAGUE_ID  = 186
_now       = datetime.utcnow()
SEASON     = _now.year if _now.month >= 7 else _now.year - 1
DAYS_AHEAD = 14

HEADERS_API = {"x-apisports-key": API_FOOTBALL_KEY}

bs_scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# Mapping noms courts API football vers noms complets BeSoccer
API_NAME_MAP = {
    "Ben Aknoun":  "ES Ben Aknoun",
    "Khenchela":   "USM Khenchela",
    "Rouissat":    "MB Rouissat",
    "Rouisset":    "MB Rouissat",
    "Akbou":       "Olympique Akbou",
    "Mostaganem":  "ES Mostaganem",
    "El Bayadh":   "MC El Bayadh",
    "Chlef":       "ASO Chlef",
    "Saoura":      "JS Saoura",
    "Kabylie":     "JS Kabylie",
    "Constantine": "CS Constantine",
    "Setif":       "ES Setif",
    "Paradou":     "Paradou AC",
    "Oran":        "MC Oran",
    "Belouizdad":  "CR Belouizdad",
}

def resolve_name(name):
    return API_NAME_MAP.get(name, name)

def normalize(name):
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name

def name_to_slug(name):
    return normalize(name).replace(" ", "-")

def load_slug_cache():
    rows = supabase.table("algeria_club_slugs").select("club_name,bs_slug,bs_club_id").execute()
    return {r["club_name"]: {"slug": r["bs_slug"], "id": r.get("bs_club_id")} for r in (rows.data or [])}

def save_slug(club_name, bs_slug, bs_club_id=None):
    supabase.table("algeria_club_slugs").upsert({
        "club_name":  club_name,
        "bs_slug":    bs_slug,
        "bs_club_id": bs_club_id,
        "updated_at": datetime.utcnow().isoformat(),
    }, on_conflict="club_name").execute()
    print(f"  Slug sauvegarde : {club_name} -> {bs_slug}")

def auto_discover_slug(club_name):
    print(f"  Recherche slug pour : {club_name}")
    slug_candidate = name_to_slug(club_name)
    url = f"{BS_BASE}/equipo/{slug_candidate}"
    try:
        r = bs_scraper.get(url, timeout=10, allow_redirects=True)
        if r.status_code == 200 and "equipo/" in r.url:
            found = r.url.split("equipo/")[-1].rstrip("/")
            print(f"  Slug direct : {found}")
            return found
    except Exception:
        pass
    try:
        r = bs_scraper.get(f"{BS_BASE}/buscador", params={"q": club_name}, timeout=10)
        if r.status_code == 200:
            slugs = re.findall(r'/equipo/([a-z0-9\-]+)', r.text)
            norm  = normalize(club_name)
            words = [w for w in norm.split() if len(w) > 3]
            for slug in slugs:
                if all(w in slug for w in words[:2]):
                    print(f"  Slug recherche : {slug}")
                    return slug
    except Exception as e:
        print(f"  Erreur recherche : {e}")
    print(f"  Slug non trouve pour {club_name}")
    return None

def get_upcoming_fixtures():
    today = datetime.utcnow().date()
    end   = today + timedelta(days=DAYS_AHEAD)
    r = requests.get(f"{API_BASE}/fixtures", headers=HEADERS_API, timeout=15, params={
        "league": LEAGUE_ID, "season": SEASON,
        "from": today.isoformat(), "to": end.isoformat(),
    })
    r.raise_for_status()
    fixtures = r.json().get("response", [])
    print(f"Matchs trouves (du {today} au {end}) : {len(fixtures)}")
    return fixtures

def verify_match_date(match_id, home_slug, away_slug, expected_date):
    """Verifie que le match_id correspond bien a la date attendue."""
    url = f"{BS_BASE}/match/{home_slug}/{away_slug}/{match_id}"
    try:
        r = bs_scraper.get(url, timeout=10, allow_redirects=True)
        if r.status_code != 200:
            return False
        d = datetime.strptime(expected_date, "%Y-%m-%d")
        formats = [
            d.strftime("%d/%m/%Y"),
            d.strftime("%Y-%m-%d"),
            d.strftime("%d.%m.%Y"),
        ]
        return any(fmt in r.text for fmt in formats)
    except Exception:
        return False

def find_match_id_via_club(home_slug, home_bs_id, away_slug, match_date):
    """
    Cherche le match_id depuis la page matchs du club.
    Verifie que l'ID trouve correspond bien a match_date.
    """
    if not home_bs_id:
        print(f"    Pas de bs_club_id pour {home_slug}")
        return None

    url = f"{BS_BASE}/team/matches/{home_slug}/{home_bs_id}/"
    try:
        r = bs_scraper.get(url, timeout=15)
        if r.status_code != 200:
            print(f"    Page club {r.status_code} : {url}")
            return None

        # Chercher /match/home/away/ID puis /match/away/home/ID
        for h, a in [(home_slug, away_slug), (away_slug, home_slug)]:
            pattern = "/match/" + re.escape(h) + "/" + re.escape(a) + r"/(\d{7,})"
            found = re.findall(pattern, r.text)
            for mid in found:
                print(f"    Candidat match_id={mid} — verification date...")
                if verify_match_date(mid, h, a, match_date):
                    print(f"    match_id={mid} verifie pour {match_date}")
                    return mid
                else:
                    print(f"    match_id={mid} date incorrecte — ignore")

        print(f"    Aucun match {home_slug} vs {away_slug} verifie pour {match_date}")
        return None

    except Exception as e:
        print(f"    Erreur page club : {e}")
        return None

def upsert_match_id(fixture_id, match_id, home_team, away_team,
                    match_date, bs_home_slug, bs_away_slug):
    supabase.table("algeria_match_ids").upsert({
        "fixture_id":   fixture_id,
        "match_id":     match_id,
        "home_team":    home_team,
        "away_team":    away_team,
        "match_date":   match_date,
        "bs_home_slug": bs_home_slug,
        "bs_away_slug": bs_away_slug,
        "updated_at":   datetime.utcnow().isoformat(),
    }, on_conflict="fixture_id").execute()

def main():
    print("=== sync_match_ids.py ===")
    slug_cache = load_slug_cache()
    print(f"Slugs en cache : {len(slug_cache)} clubs")

    fixtures = get_upcoming_fixtures()
    new_ids  = 0
    skipped  = 0

    for fix in fixtures:
        fid       = fix["fixture"]["id"]
        date_str  = fix["fixture"]["date"][:10]
        home_name = resolve_name(fix["teams"]["home"]["name"])
        away_name = resolve_name(fix["teams"]["away"]["name"])

        print(f"\n{home_name} vs {away_name} ({date_str}) [fixture={fid}]")

        existing = supabase.table("algeria_match_ids") \
            .select("match_id").eq("fixture_id", fid).execute()
        if existing.data:
            print(f"  Deja en base : match_id={existing.data[0]['match_id']}")
            skipped += 1
            continue

        home_info = slug_cache.get(home_name)
        away_info = slug_cache.get(away_name)

        if not home_info:
            slug = auto_discover_slug(home_name)
            if slug:
                save_slug(home_name, slug)
                home_info = {"slug": slug, "id": None}
                slug_cache[home_name] = home_info

        if not away_info:
            slug = auto_discover_slug(away_name)
            if slug:
                save_slug(away_name, slug)
                away_info = {"slug": slug, "id": None}
                slug_cache[away_name] = away_info

        if not home_info or not away_info:
            print(f"  Slug manquant — ignore")
            continue

        home_slug  = home_info["slug"]
        away_slug  = away_info["slug"]
        home_bs_id = home_info.get("id")
        away_bs_id = away_info.get("id")

        match_id = find_match_id_via_club(home_slug, home_bs_id, away_slug, date_str)

        if not match_id:
            print(f"  Essai via page club exterieur...")
            match_id = find_match_id_via_club(away_slug, away_bs_id, home_slug, date_str)

        if match_id:
            upsert_match_id(fid, match_id, home_name, away_name,
                            date_str, home_slug, away_slug)
            print(f"  Sauvegarde : fixture={fid} -> match_id={match_id}")
            new_ids += 1
        else:
            print(f"  match_id non trouve pour {home_name} vs {away_name}")

        time.sleep(1)

    print(f"\n=== Resultat : {new_ids} nouveaux, {skipped} deja en base ===")

if __name__ == "__main__":
    main()