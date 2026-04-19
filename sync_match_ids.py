"""
sync_match_ids.py
-----------------
Tourne chaque jour à 6h UTC via GitHub Actions.
Pour chaque match de Ligue 1 Algérie dans les 14 prochains jours :
  1. Récupère l'ID API football via /fixtures
  2. Cherche le match_id BeSoccer via la page matchs du club
  3. Sauvegarde dans algeria_match_ids
"""

import os, re, time, unicodedata
from datetime import datetime, timedelta
import requests
from supabase import create_client

# ── Credentials ─────────────────────────────────────────────────────────────
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
HEADERS_BS  = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# ── Mapping noms courts API football → noms complets BeSoccer ───────────────
# L'API retourne parfois "Ben Aknoun" au lieu de "ES Ben Aknoun"
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

def resolve_name(name: str) -> str:
    return API_NAME_MAP.get(name, name)

# ── Normalisation ────────────────────────────────────────────────────────────
def normalize(name: str) -> str:
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name

def name_to_slug(name: str) -> str:
    return normalize(name).replace(" ", "-")

# ── Cache slugs depuis Supabase ──────────────────────────────────────────────
def load_slug_cache() -> dict:
    rows = supabase.table("algeria_club_slugs").select("club_name,bs_slug,bs_club_id").execute()
    return {r["club_name"]: {"slug": r["bs_slug"], "id": r.get("bs_club_id")} for r in (rows.data or [])}

def save_slug(club_name: str, bs_slug: str, bs_club_id: str = None):
    supabase.table("algeria_club_slugs").upsert({
        "club_name":  club_name,
        "bs_slug":    bs_slug,
        "bs_club_id": bs_club_id,
        "updated_at": datetime.utcnow().isoformat(),
    }, on_conflict="club_name").execute()
    print(f"  💾 Slug sauvegardé : {club_name} → {bs_slug}")

# ── Auto-discovery du slug BeSoccer ─────────────────────────────────────────
def auto_discover_slug(club_name: str) -> str | None:
    print(f"  🔍 Auto-discovery slug pour : {club_name}")
    slug_candidate = name_to_slug(club_name)

    # Essai direct
    url = f"{BS_BASE}/equipo/{slug_candidate}"
    try:
        r = requests.get(url, headers=HEADERS_BS, timeout=10, allow_redirects=True)
        if r.status_code == 200 and "equipo/" in r.url:
            found = r.url.split("equipo/")[-1].rstrip("/")
            print(f"  ✅ Slug direct : {found}")
            return found
    except Exception:
        pass

    # Recherche BeSoccer
    try:
        r = requests.get(f"{BS_BASE}/buscador", params={"q": club_name},
                         headers=HEADERS_BS, timeout=10)
        if r.status_code == 200:
            slugs = re.findall(r'/equipo/([a-z0-9\-]+)', r.text)
            norm  = normalize(club_name)
            words = [w for w in norm.split() if len(w) > 3]
            for slug in slugs:
                if all(w in slug for w in words[:2]):
                    print(f"  ✅ Slug recherche : {slug}")
                    return slug
            if slugs:
                print(f"  ⚠️  Premier résultat : {slugs[0]}")
                return slugs[0]
    except Exception as e:
        print(f"  ❌ Erreur recherche BeSoccer : {e}")

    print(f"  ❌ Slug non trouvé pour {club_name}")
    return None

# ── Récupération fixtures API football ──────────────────────────────────────
def get_upcoming_fixtures() -> list:
    today = datetime.utcnow().date()
    end   = today + timedelta(days=DAYS_AHEAD)
    r = requests.get(f"{API_BASE}/fixtures", headers=HEADERS_API, timeout=15, params={
        "league": LEAGUE_ID, "season": SEASON,
        "from": today.isoformat(), "to": end.isoformat(),
    })
    r.raise_for_status()
    fixtures = r.json().get("response", [])
    print(f"📅 {len(fixtures)} matchs trouvés (du {today} au {end})")
    return fixtures

# ── Recherche match_id via page du club domicile ─────────────────────────────
def find_match_id_via_club(home_slug: str, home_bs_id: str,
                            away_slug: str, match_date: str) -> str | None:
    """
    Cherche le match_id BeSoccer depuis la page des matchs du club domicile.
    Plus fiable que l'URL /partido/ qui nécessite déjà l'ID.
    """
    if not home_bs_id:
        return None

    url = f"{BS_BASE}/team/matches/{home_slug}/{home_bs_id}/"
    try:
        r = requests.get(url, headers=HEADERS_BS, timeout=15)
        if r.status_code != 200:
            print(f"    ⚠️  Page club {r.status_code}")
            return None

        # Chercher /match/home_slug/away_slug/ID ou /match/away_slug/home_slug/ID
        for h, a in [(home_slug, away_slug), (away_slug, home_slug)]:
            pattern = r'/match/' + re.escape(h) + r'/' + re.escape(a) + r'/(\d{7,})'
            found = re.findall(pattern, r.text)
            if found:
                mid = found[0]
                print(f"    ✅ match_id={mid} (via page club)")
                return mid

        # Fallback : tous les IDs 7+ chiffres dans la page
        all_ids = re.findall(r'/match/[^"\'>\s]+/(\d{7,})', r.text)
        if all_ids:
            mid = all_ids[0]
            print(f"    ⚠️  match_id={mid} (fallback premier ID)")
            return mid

    except Exception as e:
        print(f"    ⚠️  Erreur page club : {e}")

    return None

# ── Upsert Supabase ──────────────────────────────────────────────────────────
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

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=== sync_match_ids.py ===")
    slug_cache = load_slug_cache()
    print(f"📚 {len(slug_cache)} slugs en cache : {list(slug_cache.keys())}")

    fixtures = get_upcoming_fixtures()
    new_ids  = 0
    skipped  = 0

    for fix in fixtures:
        fid       = fix["fixture"]["id"]
        date_str  = fix["fixture"]["date"][:10]
        # Résoudre noms courts API → noms complets
        home_name = resolve_name(fix["teams"]["home"]["name"])
        away_name = resolve_name(fix["teams"]["away"]["name"])

        print(f"\n🏟️  {home_name} vs {away_name} ({date_str}) [fixture={fid}]")

        # Déjà en base ?
        existing = supabase.table("algeria_match_ids") \
            .select("match_id").eq("fixture_id", fid).execute()
        if existing.data:
            print(f"  ⏭️  Déjà en base (match_id={existing.data[0]['match_id']})")
            skipped += 1
            continue

        # Résoudre slugs
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
            print(f"  ❌ Slug manquant — ignoré (home={home_info}, away={away_info})")
            continue

        home_slug  = home_info["slug"]
        away_slug  = away_info["slug"]
        home_bs_id = home_info.get("id")

        # Chercher match_id via page club domicile
        match_id = find_match_id_via_club(home_slug, home_bs_id, away_slug, date_str)

        # Essai inversé via page club extérieur
        if not match_id:
            print(f"  🔄 Essai via page club extérieur...")
            away_bs_id = away_info.get("id")
            match_id = find_match_id_via_club(away_slug, away_bs_id, home_slug, date_str)

        if match_id:
            upsert_match_id(fid, match_id, home_name, away_name,
                            date_str, home_slug, away_slug)
            print(f"  ✅ Sauvegardé : fixture={fid} → match_id={match_id}")
            new_ids += 1
        else:
            print(f"  ⚠️  match_id non trouvé pour {home_name} vs {away_name}")

        time.sleep(1)

    print(f"\n=== Résultat : {new_ids} nouveaux, {skipped} déjà en base ===")

if __name__ == "__main__":
    main()