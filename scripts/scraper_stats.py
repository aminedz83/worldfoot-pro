"""
scraper_stats.py
Enrichit les matchs dans algeria_lineups avec les minutes jouées
depuis l'API Flashscore ninja (feed df_sui).
Complète le travail de scraper.py qui sauvegarde déjà buts/cartons.
"""
import requests, os, re, time
import cloudscraper
from datetime import datetime, timezone

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

PROJECT = "2043"
FS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://www.flashscore.ca/",
    "x-fsign": "SW9D1eZo",
}

def get_matches_without_minutes():
    """Récupère les matchs qui n'ont pas encore les minutes jouées."""
    try:
        r = requests.get(
            SB_URL + "/rest/v1/algeria_lineups?select=id,soccerway_mid,home_players,away_players,home_subs,away_subs,match_date,home_team,away_team&order=match_date.desc&limit=50",
            headers={**SB_HEADERS, "Prefer": ""},
            timeout=15
        )
        rows = r.json()
        to_update = []
        for row in rows:
            hp = row.get("home_players") or []
            if hp and isinstance(hp, list) and len(hp) > 0:
                # Si pas de 'minutes' ou minutes=None → à enrichir
                if "minutes" not in hp[0] or hp[0].get("minutes") is None:
                    to_update.append(row)
        return to_update
    except Exception as e:
        print("Erreur fetch matches:", e)
        return []

def get_minutes_from_feed(mid):
    """
    Récupère les minutes jouées depuis le feed df_sui (événements).
    Remplacements: IE=subst → sortant sort à X', entrant entre à X'
    Titulaires sans remplacement → 90 minutes
    
    Format remplacement dans df_sui:
    IE÷30 (substitution) → IB=minute, IF=joueur sortant, IV=joueur entrant
    """
    url = f"https://{PROJECT}.flashscore.ninja/46/x/feed/df_sui_1_{mid}_1_fr_1"
    minutes_map = {}  # player_id → minutes jouées
    
    try:
        r = scraper.get(url, headers=FS_HEADERS, timeout=10)
        if r.status_code != 200 or len(r.text) < 5:
            return minutes_map

        for block in r.text.split("~"):
            fields = {}
            for field in block.split("¬"):
                if "÷" in field:
                    k, _, v = field.partition("÷")
                    fields[k.strip()] = v.strip()

            event_type = fields.get("IE", "")
            minute_str = fields.get("IB", "")
            
            # Nettoyer la minute (ex: "90+2'" → 92)
            minute = None
            if minute_str:
                m = re.search(r'(\d+)(?:\+(\d+))?', minute_str)
                if m:
                    base = int(m.group(1))
                    extra = int(m.group(2)) if m.group(2) else 0
                    minute = base + extra

            # IE=30 → remplacement
            if event_type == "30" and minute:
                # Joueur sortant → a joué jusqu'à cette minute
                out_id = fields.get("IM", "")
                # Joueur entrant → entre à cette minute
                in_id = fields.get("IV", fields.get("IN_", ""))
                
                if out_id:
                    minutes_map[out_id] = minute
                if in_id:
                    minutes_map[in_id] = 90 - minute  # minutes restantes

    except Exception as e:
        print(f"  Erreur minutes feed: {e}")
    
    return minutes_map

def enrich_with_minutes(players, minutes_map, is_sub=False, default_minutes=90):
    """Ajoute les minutes jouées à chaque joueur."""
    enriched = []
    for p in players:
        new_p = dict(p)
        pid = p.get("sw_player_id", "")
        
        if pid and pid in minutes_map:
            new_p["minutes"] = minutes_map[pid]
        elif not is_sub:
            # Titulaire sans remplacement → 90 minutes
            new_p["minutes"] = new_p.get("minutes") or default_minutes
        else:
            # Remplaçant non entré → 0 minutes
            new_p["minutes"] = new_p.get("minutes") or 0
            
        enriched.append(new_p)
    return enriched

def update_match(row_id, home_players, away_players, home_subs, away_subs):
    """Met à jour les minutes dans Supabase."""
    try:
        r = requests.patch(
            SB_URL + "/rest/v1/algeria_lineups?id=eq." + str(row_id),
            headers={**SB_HEADERS, "Prefer": "return=minimal"},
            json={
                "home_players": home_players,
                "away_players": away_players,
                "home_subs": home_subs,
                "away_subs": away_subs,
                "scraped_at": datetime.now(timezone.utc).isoformat()
            },
            timeout=15
        )
        return r.status_code in [200, 204]
    except Exception as e:
        print(f"  Erreur update: {e}")
        return False

# ══════════════════════════════════════════
print("=== Sync Minutes Joueurs (Flashscore) ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

matches = get_matches_without_minutes()
print(f"\n{len(matches)} matchs sans minutes à traiter\n")

updated = 0
errors = 0

for match in matches:
    mid = match.get("soccerway_mid")
    if not mid:
        continue

    home = match.get("home_team", "?")
    away = match.get("away_team", "?")
    date = match.get("match_date", "?")
    print(f"📋 {home} vs {away} ({date}) - mid={mid}")

    # Récupérer les minutes depuis Flashscore
    minutes_map = get_minutes_from_feed(mid)
    print(f"  Minutes trouvées: {len(minutes_map)} joueurs")

    # Enrichir les joueurs
    hp = enrich_with_minutes(match.get("home_players") or [], minutes_map, is_sub=False)
    ap = enrich_with_minutes(match.get("away_players") or [], minutes_map, is_sub=False)
    hs = enrich_with_minutes(match.get("home_subs") or [], minutes_map, is_sub=True)
    as_ = enrich_with_minutes(match.get("away_subs") or [], minutes_map, is_sub=True)

    # Afficher résumé
    mins = [p.get("minutes") for p in hp if p.get("minutes")]
    print(f"  Dom minutes: {mins[:4]}...")

    ok = update_match(match["id"], hp, ap, hs, as_)
    if ok:
        print(f"  ✅ Sauvegardé")
        updated += 1
    else:
        print(f"  ❌ Erreur")
        errors += 1

    time.sleep(1)

print(f"\n=== Terminé: {updated} mis à jour, {errors} erreurs ===")