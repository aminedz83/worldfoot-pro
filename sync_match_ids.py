"""
sync_match_ids.py
-----------------
Tourne chaque jour à 6h UTC via GitHub Actions.
Pour chaque match de Ligue 1 Algérie dans les 14 prochains jours :
  1. Récupère l'ID API football via /fixtures
  2. Cherche le match_id BeSoccer via auto_discover_slug() + recherche par date
  3. Sauvegarde dans algeria_match_ids

Si un club n'est pas dans algeria_club_slugs → auto_discover_slug() le cherche
automatiquement sur BeSoccer et mémorise le slug pour toujours.
"""

import os, re, time, json, unicodedata
from datetime import datetime, timedelta
import requests
from supabase import create_client

# ── Credentials ────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
API_FOOTBALL_KEY = os.environ["API_FOOTBALL_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

API_BASE    = "https://v3.football.api-sports.io"
BS_BASE     = "https://www.besoccer.com"
LEAGUE_ID   = 186   # Ligue 1 Algérie
SEASON      = 2024
DAYS_AHEAD  = 14

HEADERS_API = {"x-apisports-key": API_FOOTBALL_KEY}
HEADERS_BS  = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# ── Normalisation des noms ──────────────────────────────────────────────────
def normalize(name: str) -> str:
    """Normalise un nom de club : minuscules, sans accents, sans ponctuation."""
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name

def name_to_slug(name: str) -> str:
    """Convertit un nom normalisé en slug BeSoccer."""
    return normalize(name).replace(" ", "-")

# ── Chargement du cache depuis Supabase ────────────────────────────────────
def load_slug_cache() -> dict:
    """Charge tous les slugs depuis algeria_club_slugs."""
    rows = supabase.table("algeria_club_slugs").select("club_name,bs_slug").execute()
    return {r["club_name"]: r["bs_slug"] for r in (rows.data or [])}

def save_slug(club_name: str, bs_slug: str, bs_club_id: str = None):
    """Sauvegarde un nouveau slug découvert."""
    supabase.table("algeria_club_slugs").upsert({
        "club_name":  club_name,
        "bs_slug":    bs_slug,
        "bs_club_id": bs_club_id,
        "updated_at": datetime.utcnow().isoformat(),
    }, on_conflict="club_name").execute()
    print(f"  💾 Slug sauvegardé : {club_name} → {bs_slug}")

# ── Auto-discovery du slug BeSoccer ───────────────────────────────────────
def auto_discover_slug(club_name: str) -> str | None:
    """
    Cherche automatiquement le slug BeSoccer d'un club inconnu.
    Stratégie :
      1. Essai direct avec le slug généré depuis le nom
      2. Recherche via /buscador?q=<nom> sur BeSoccer
      3. Matching flou sur les résultats
    """
    print(f"  🔍 Auto-discovery slug pour : {club_name}")
    slug_candidate = name_to_slug(club_name)

    # Stratégie 1 — slug direct
    url = f"{BS_BASE}/equipo/{slug_candidate}"
    try:
        r = requests.get(url, headers=HEADERS_BS, timeout=10, allow_redirects=True)
        if r.status_code == 200 and "equipo/" in r.url:
            found_slug = r.url.split("equipo/")[-1].rstrip("/")
            print(f"  ✅ Slug direct trouvé : {found_slug}")
            return found_slug
    except Exception:
        pass

    # Stratégie 2 — recherche BeSoccer
    try:
        search_url = f"{BS_BASE}/buscador"
        r = requests.get(search_url, params={"q": club_name}, headers=HEADERS_BS, timeout=10)
        if r.status_code == 200:
            # Chercher des liens /equipo/ dans le HTML
            matches = re.findall(r'/equipo/([a-z0-9\-]+)', r.text)
            norm_name = normalize(club_name)
            for slug in matches:
                # Matching flou : le slug doit contenir le mot-clé principal
                words = [w for w in norm_name.split() if len(w) > 3]
                if all(w in slug for w in words[:2]):
                    print(f"  ✅ Slug trouvé par recherche : {slug}")
                    return slug
            # Fallback : premier résultat /equipo/
            if matches:
                print(f"  ⚠️  Premier résultat : {matches[0]}")
                return matches[0]
    except Exception as e:
        print(f"  ❌ Erreur recherche BeSoccer : {e}")

    print(f"  ❌ Slug non trouvé pour {club_name}")
    return None

# ── Récupération des fixtures API football ─────────────────────────────────
def get_upcoming_fixtures() -> list:
    """Récupère les matchs de Ligue 1 dans les DAYS_AHEAD prochains jours."""
    today = datetime.utcnow().date()
    end   = today + timedelta(days=DAYS_AHEAD)
    url   = f"{API_BASE}/fixtures"
    params = {
        "league": LEAGUE_ID,
        "season": SEASON,
        "from":   today.isoformat(),
        "to":     end.isoformat(),
    }
    r = requests.get(url, headers=HEADERS_API, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    fixtures = data.get("response", [])
    print(f"📅 {len(fixtures)} matchs trouvés (du {today} au {end})")
    return fixtures

# ── Recherche du match_id BeSoccer pour un match donné ───────────────────
def find_besoccer_match_id(
    home_slug: str,
    away_slug: str,
    match_date: str,   # format YYYY-MM-DD
) -> str | None:
    """
    Cherche le match_id BeSoccer pour une rencontre home vs away à une date donnée.
    URL : /partido/{home_slug}/{away_slug}/({date})/
    """
    # Essayer date exacte + veille + lendemain (décalages de fuseau)
    base_date = datetime.strptime(match_date, "%Y-%m-%d").date()
    for delta in [0, -1, 1]:
        d = (base_date + timedelta(days=delta)).strftime("%Y-%m-%d")
        url = f"{BS_BASE}/partido/{home_slug}/{away_slug}/({d})/"
        try:
            r = requests.get(url, headers=HEADERS_BS, timeout=10, allow_redirects=True)
            if r.status_code == 200:
                # Extraire le match_id depuis l'URL finale ou le HTML
                # Pattern : /partido/xxx/yyy/(date)/MATCH_ID/
                m = re.search(r'/partido/[^/]+/[^/]+/\([^)]+\)/(\d{7,})', r.url)
                if m:
                    mid = m.group(1)
                    print(f"    ✅ match_id={mid} (URL redirect)")
                    return mid
                # Chercher dans le HTML
                m2 = re.search(r'"match_id"\s*:\s*"?(\d{7,})"?', r.text)
                if m2:
                    mid = m2.group(1)
                    print(f"    ✅ match_id={mid} (HTML)")
                    return mid
                # Chercher data-match-id
                m3 = re.search(r'data-match-id="(\d{7,})"', r.text)
                if m3:
                    mid = m3.group(1)
                    print(f"    ✅ match_id={mid} (data attr)")
                    return mid
        except Exception as e:
            print(f"    ⚠️  Erreur {url}: {e}")
        time.sleep(0.5)
    return None

# ── Upsert dans Supabase ────────────────────────────────────────────────────
def upsert_match_id(
    fixture_id: int,
    match_id: str,
    home_team: str,
    away_team: str,
    match_date: str,
    bs_home_slug: str,
    bs_away_slug: str,
):
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

# ── Main ───────────────────────────────────────────────────────────────────
def main():
    print("=== sync_match_ids.py ===")
    slug_cache = load_slug_cache()
    print(f"📚 {len(slug_cache)} slugs en cache : {list(slug_cache.keys())}")

    fixtures = get_upcoming_fixtures()
    new_ids = 0
    skipped = 0

    for fix in fixtures:
        fid        = fix["fixture"]["id"]
        date_str   = fix["fixture"]["date"][:10]
        home_name  = fix["teams"]["home"]["name"]
        away_name  = fix["teams"]["away"]["name"]

        print(f"\n🏟️  {home_name} vs {away_name} ({date_str}) [fixture={fid}]")

        # Vérifier si déjà en base
        existing = supabase.table("algeria_match_ids") \
            .select("match_id").eq("fixture_id", fid).execute()
        if existing.data:
            print(f"  ⏭️  Déjà en base (match_id={existing.data[0]['match_id']})")
            skipped += 1
            continue

        # Résoudre les slugs BeSoccer
        home_slug = slug_cache.get(home_name)
        away_slug = slug_cache.get(away_name)

        if not home_slug:
            home_slug = auto_discover_slug(home_name)
            if home_slug:
                save_slug(home_name, home_slug)
                slug_cache[home_name] = home_slug

        if not away_slug:
            away_slug = auto_discover_slug(away_name)
            if away_slug:
                save_slug(away_name, away_slug)
                slug_cache[away_name] = away_slug

        if not home_slug or not away_slug:
            print(f"  ❌ Slug manquant — ignoré (home={home_slug}, away={away_slug})")
            continue

        # Chercher le match_id BeSoccer
        match_id = find_besoccer_match_id(home_slug, away_slug, date_str)

        if not match_id:
            # Essai inversé (BeSoccer met parfois l'extérieur en premier)
            print(f"  🔄 Essai inversé...")
            match_id = find_besoccer_match_id(away_slug, home_slug, date_str)

        if match_id:
            upsert_match_id(fid, match_id, home_name, away_name,
                            date_str, home_slug, away_slug)
            print(f"  ✅ Sauvegardé : fixture={fid} → match_id={match_id}")
            new_ids += 1
        else:
            print(f"  ⚠️  match_id non trouvé pour {home_name} vs {away_name}")

        time.sleep(1)  # Respecter rate limit BeSoccer

    print(f"\n=== Résultat : {new_ids} nouveaux, {skipped} déjà en base ===")

if __name__ == "__main__":
    main()