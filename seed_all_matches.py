"""
seed_all_matches.py
===================
Remplit algeria_match_ids pour toute la saison en cours.

Fonctionnement :
1. Récupère les fixtures API football (toute la saison)
2. Pour chaque fixture, cherche le match_id BeSoccer depuis
   la page du club domicile
3. Vérifie la date avant de sauvegarder (anti-doublon saison)
4. Sauvegarde dans algeria_match_ids

100% automatique — fonctionne pour n'importe quelle saison,
y compris avec des clubs promus inconnus.
"""

import os, re, time, requests
import cloudscraper
from datetime import datetime, timedelta

# ── Credentials ──────────────────────────────────────────────────────────────
SUPABASE_URL     = os.environ["SUPABASE_URL"]
SUPABASE_KEY     = os.environ["SUPABASE_KEY"]
API_FOOTBALL_KEY = os.environ["API_FOOTBALL_KEY"]

SB_URL     = SUPABASE_URL
SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type":  "application/json",
}

API_HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}
API_BASE    = "https://v3.football.api-sports.io"
BS_BASE     = "https://www.besoccer.com"

LEAGUE_ID = 186
_now      = datetime.utcnow()
SEASON    = _now.year if _now.month >= 7 else _now.year - 1

# ── Mapping noms API football → slugs BeSoccer ───────────────────────────────
# Chargé dynamiquement depuis algeria_club_slugs
# Ce mapping est auto-découvert pour les nouveaux promus

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

bs_scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# ── Chargement slugs depuis Supabase ─────────────────────────────────────────
def load_slug_cache():
    r = requests.get(
        SB_URL + "/rest/v1/algeria_club_slugs?select=club_name,bs_slug,bs_club_id",
        headers={**SB_HEADERS, "Prefer": ""}
    )
    rows = r.json() if r.status_code == 200 else []
    cache = {}
    for row in rows:
        cache[row["club_name"]] = {
            "slug": row["bs_slug"],
            "id":   row.get("bs_club_id")
        }
    print(f"  {len(cache)} slugs en cache")
    return cache

# ── Récupération de TOUS les fixtures de la saison ───────────────────────────
def get_all_fixtures():
    print(f"  Saison {SEASON} — récupération des fixtures...")
    all_fixtures = []
    page = 1
    while True:
        r = requests.get(
            f"{API_BASE}/fixtures",
            headers=API_HEADERS,
            params={"league": LEAGUE_ID, "season": SEASON, "page": page},
            timeout=15
        )
        if r.status_code != 200:
            print(f"  ⚠️ API erreur {r.status_code}")
            break
        data = r.json()
        fixtures = data.get("response", [])
        if not fixtures:
            break
        all_fixtures.extend(fixtures)
        paging = data.get("paging", {})
        if paging.get("current", 1) >= paging.get("total", 1):
            break
        page += 1
        time.sleep(0.5)
    print(f"  {len(all_fixtures)} fixtures récupérés")
    return all_fixtures

# ── Recherche match_id BeSoccer via page club ─────────────────────────────────
def find_match_id(home_slug, home_bs_id, away_slug, match_date):
    """
    Cherche le match_id BeSoccer depuis la page matchs du club domicile.
    Vérifie que l'ID trouvé correspond bien à match_date.
    """
    if not home_bs_id:
        return None

    url = f"{BS_BASE}/team/matches/{home_slug}/{home_bs_id}/"
    try:
        r = bs_scraper.get(url, timeout=15)
        if r.status_code != 200:
            return None

        # Chercher home/away/ID et away/home/ID
        for h, a in [(home_slug, away_slug), (away_slug, home_slug)]:
            pattern = "/match/" + re.escape(h) + "/" + re.escape(a) + r"/(\d{7,})"
            candidates = re.findall(pattern, r.text)
            for mid in candidates:
                if verify_date(mid, h, a, match_date):
                    return mid

        return None
    except Exception as e:
        print(f"    ⚠️ Erreur: {e}")
        return None

def verify_date(match_id, home_slug, away_slug, expected_date):
    """Vérifie que match_id correspond bien à expected_date."""
    url = f"{BS_BASE}/match/{home_slug}/{away_slug}/{match_id}"
    try:
        r = bs_scraper.get(url, timeout=10, allow_redirects=True)
        if r.status_code != 200:
            return False
        d = datetime.strptime(expected_date, "%Y-%m-%d")
        for fmt in [d.strftime("%d/%m/%Y"), d.strftime("%Y-%m-%d"), d.strftime("%d.%m.%Y")]:
            if fmt in r.text:
                return True
        return False
    except Exception:
        return False

# ── Auto-discovery slug pour nouveaux clubs ───────────────────────────────────
def discover_slug(club_name):
    """Découvre le slug BeSoccer d'un club inconnu."""
    import unicodedata
    def normalize(s):
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return s.lower().strip().replace(" ", "-")

    slug = normalize(club_name)
    url = f"{BS_BASE}/equipo/{slug}"
    try:
        r = bs_scraper.get(url, timeout=10, allow_redirects=True)
        if r.status_code == 200 and "equipo/" in r.url:
            found = r.url.split("equipo/")[-1].rstrip("/")
            print(f"    🔍 Slug découvert: {club_name} → {found}")
            return found
    except Exception:
        pass

    # Recherche BeSoccer
    try:
        r = bs_scraper.get(f"{BS_BASE}/buscador", params={"q": club_name}, timeout=10)
        if r.status_code == 200:
            slugs = re.findall(r'/equipo/([a-z0-9\-]+)', r.text)
            if slugs:
                print(f"    🔍 Slug recherche: {club_name} → {slugs[0]}")
                return slugs[0]
    except Exception:
        pass

    return None

def save_slug(club_name, slug):
    requests.post(
        SB_URL + "/rest/v1/algeria_club_slugs",
        headers={**SB_HEADERS, "Prefer": "resolution=ignore-duplicates"},
        params={"on_conflict": "club_name"},
        json={"club_name": club_name, "bs_slug": slug}
    )

# ── Upsert dans Supabase ──────────────────────────────────────────────────────
def upsert(fixture_id, match_id, home_team, away_team, match_date, home_slug, away_slug):
    requests.post(
        SB_URL + "/rest/v1/algeria_match_ids",
        headers={**SB_HEADERS, "Prefer": "resolution=merge-duplicates"},
        params={"on_conflict": "fixture_id"},
        json={
            "fixture_id":   fixture_id,
            "match_id":     match_id,
            "home_team":    home_team,
            "away_team":    away_team,
            "match_date":   match_date,
            "bs_home_slug": home_slug,
            "bs_away_slug": away_slug,
            "updated_at":   datetime.utcnow().isoformat(),
        }
    )

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=== Seed All Match IDs ===")
    print(f"Saison : {SEASON} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    slug_cache = load_slug_cache()
    fixtures   = get_all_fixtures()

    ok      = 0
    skipped = 0
    failed  = 0

    for fix in fixtures:
        fid        = fix["fixture"]["id"]
        date_str   = fix["fixture"]["date"][:10]
        home_name  = resolve_name(fix["teams"]["home"]["name"])
        away_name  = resolve_name(fix["teams"]["away"]["name"])

        print(f"\n🏟️  {home_name} vs {away_name} ({date_str}) [fixture={fid}]")

        # Déjà en base ?
        r = requests.get(
            SB_URL + f"/rest/v1/algeria_match_ids?fixture_id=eq.{fid}&select=match_id",
            headers={**SB_HEADERS, "Prefer": ""}
        )
        existing = r.json() if r.status_code == 200 else []
        if existing:
            print(f"  ⏭️  Déjà en base ({existing[0]['match_id']})")
            skipped += 1
            continue

        # Résoudre slugs
        home_info = slug_cache.get(home_name)
        away_info = slug_cache.get(away_name)

        if not home_info:
            slug = discover_slug(home_name)
            if slug:
                save_slug(home_name, slug)
                home_info = {"slug": slug, "id": None}
                slug_cache[home_name] = home_info

        if not away_info:
            slug = discover_slug(away_name)
            if slug:
                save_slug(away_name, slug)
                away_info = {"slug": slug, "id": None}
                slug_cache[away_name] = away_info

        if not home_info or not away_info:
            print(f"  ❌ Slug manquant")
            failed += 1
            continue

        home_slug  = home_info["slug"]
        away_slug  = away_info["slug"]
        home_bs_id = home_info.get("id")
        away_bs_id = away_info.get("id")

        # Chercher match_id
        match_id = find_match_id(home_slug, home_bs_id, away_slug, date_str)
        if not match_id:
            print(f"  🔄 Essai côté extérieur...")
            match_id = find_match_id(away_slug, away_bs_id, home_slug, date_str)

        if match_id:
            upsert(fid, match_id, home_name, away_name, date_str, home_slug, away_slug)
            print(f"  ✅ match_id={match_id}")
            ok += 1
        else:
            print(f"  ⚠️  match_id non trouvé")
            failed += 1

        time.sleep(1)

    print(f"\n=== Résultat : {ok} sauvegardés | {skipped} déjà en base | {failed} échoués ===")

if __name__ == "__main__":
    main()