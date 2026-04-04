"""
scraper_stats.py
Récupère les stats joueurs (minutes, buts, cartons, remplacements)
depuis Soccerway pour tous les matchs dans algeria_lineups.
Ne touche PAS au scraper de lineups — script indépendant.
"""
import requests, os, re, time, json
from bs4 import BeautifulSoup
from datetime import datetime, timezone

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": "https://ca.soccerway.com/"
}

def get_matches_without_stats():
    """Récupère les matchs qui n'ont pas encore de stats (minutes manquantes)"""
    try:
        r = requests.get(
            SB_URL + "/rest/v1/algeria_lineups?select=id,soccerway_mid,home_players,away_players,home_subs,away_subs,match_date,home_team,away_team&order=match_date.desc&limit=100",
            headers={**SB_HEADERS, "Prefer": ""},
            timeout=15
        )
        rows = r.json()
        # Filtrer ceux qui n'ont pas de stats (pas de 'minutes' dans les joueurs)
        to_update = []
        for row in rows:
            hp = row.get("home_players") or []
            # Si premier joueur n'a pas de champ 'minutes' → pas encore de stats
            if hp and isinstance(hp, list) and len(hp) > 0:
                if "minutes" not in hp[0]:
                    to_update.append(row)
            elif hp:
                to_update.append(row)
        return to_update
    except Exception as e:
        print("Erreur fetch matches:", e)
        return []

def scrape_match_stats(mid):
    """
    Scrape les stats d'un match Soccerway depuis la page summary.
    Retourne un dict: { "NomJoueur": { minutes, goals, yellow, red, subbed_in, subbed_out } }
    """
    url = "https://ca.soccerway.com/game/x/x/summary/lineups/?mid=" + mid
    try:
        time.sleep(1.5)  # Pause pour éviter le blocage
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  Status {r.status_code} pour mid={mid}")
            return {}

        soup = BeautifulSoup(r.text, "html.parser")
        stats = {}

        # ── Parser les événements du match ──
        # Soccerway affiche les events dans des divs avec classes spécifiques
        # Structure: <td class="event"> <span class="minute">45'</span> <span class="player">Nom</span> </td>

        # Méthode 1: chercher les icônes d'events dans le tableau de lineup
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            for cell in cells:
                cell_text = cell.get_text(separator=" ", strip=True)

                # Chercher minutes jouées (ex: "90'" ou "67'")
                min_match = re.search(r'\b(\d{1,3})\'', cell_text)

                # Chercher nom du joueur
                player_link = cell.find("a", href=re.compile(r"/joueur/|/players/"))
                if not player_link:
                    continue

                player_name = player_link.get_text(strip=True)
                if not player_name or len(player_name) < 2:
                    continue

                if player_name not in stats:
                    stats[player_name] = {
                        "minutes": None,
                        "goals": 0,
                        "yellow": False,
                        "red": False,
                        "subbed_in": None,
                        "subbed_out": None
                    }

                # Minutes jouées
                if min_match:
                    stats[player_name]["minutes"] = int(min_match.group(1))

                # But ⚽
                if cell.find(class_=re.compile(r"goal|scorer")) or "⚽" in cell_text:
                    stats[player_name]["goals"] += 1

                # Carton jaune
                if cell.find(class_=re.compile(r"yellow|booking")) or "🟨" in cell_text:
                    stats[player_name]["yellow"] = True

                # Carton rouge
                if cell.find(class_=re.compile(r"red.card|sent.off")) or "🟥" in cell_text:
                    stats[player_name]["red"] = True

        # Méthode 2: chercher dans la section events/timeline
        events_section = soup.find(class_=re.compile(r"events|timeline|match.events"))
        if events_section:
            for event in events_section.find_all(class_=re.compile(r"event")):
                event_text = event.get_text(separator=" ", strip=True)
                min_m = re.search(r"(\d{1,3})'", event_text)
                minute = int(min_m.group(1)) if min_m else None

                player_link = event.find("a", href=re.compile(r"/joueur/|/players/"))
                if not player_link:
                    continue
                pname = player_link.get_text(strip=True)
                if not pname:
                    continue

                if pname not in stats:
                    stats[pname] = {"minutes": None, "goals": 0, "yellow": False, "red": False, "subbed_in": None, "subbed_out": None}

                cls = event.get("class", [])
                cls_str = " ".join(cls) if isinstance(cls, list) else str(cls)

                if "goal" in cls_str or "scorer" in cls_str:
                    stats[pname]["goals"] += 1
                if "yellow" in cls_str or "booking" in cls_str:
                    stats[pname]["yellow"] = True
                if "red" in cls_str or "sent" in cls_str:
                    stats[pname]["red"] = True
                if "sub" in cls_str or "substitut" in cls_str:
                    if minute:
                        stats[pname]["subbed_out"] = minute

        # Méthode 3: titulaires = 90 minutes par défaut si pas trouvé
        # (on enrichit après avec les remplacements)

        print(f"  Stats trouvées pour {len(stats)} joueurs")
        return stats

    except Exception as e:
        print(f"  Erreur scrape_match_stats mid={mid}: {e}")
        return {}

def enrich_players(players, stats, is_sub=False):
    """
    Ajoute les stats à chaque joueur dans la liste.
    Pour les titulaires sans remplacement → 90 minutes par défaut.
    Pour les remplaçants → minutes depuis leur entrée.
    """
    enriched = []
    for p in players:
        name = p.get("name", "")
        # Chercher dans les stats par correspondance de nom
        matched_stats = None
        for stat_name, stat_data in stats.items():
            # Matching: comparer les noms (Soccerway peut avoir format différent)
            n1 = name.lower().replace(" ", "")
            n2 = stat_name.lower().replace(" ", "")
            if n1 == n2 or n1 in n2 or n2 in n1:
                matched_stats = stat_data
                break
            # Matching par nom de famille
            parts1 = name.lower().split()
            parts2 = stat_name.lower().split()
            if parts1 and parts2 and (parts1[-1] in n2 or parts2[-1] in n1):
                matched_stats = stat_data
                break

        new_p = dict(p)
        if matched_stats:
            new_p["minutes"] = matched_stats.get("minutes") or (None if is_sub else 90)
            new_p["goals"] = matched_stats.get("goals", 0)
            new_p["yellow"] = matched_stats.get("yellow", False)
            new_p["red"] = matched_stats.get("red", False)
            new_p["subbed_out"] = matched_stats.get("subbed_out")
            new_p["subbed_in"] = matched_stats.get("subbed_in")
        else:
            # Titulaire sans stats trouvées → 90' par défaut
            if not is_sub:
                new_p["minutes"] = new_p.get("minutes", 90)
            else:
                new_p["minutes"] = new_p.get("minutes", None)
            new_p["goals"] = new_p.get("goals", 0)
            new_p["yellow"] = new_p.get("yellow", False)
            new_p["red"] = new_p.get("red", False)

        enriched.append(new_p)
    return enriched

def update_match_stats(row_id, home_players, away_players, home_subs, away_subs):
    """Met à jour les stats dans Supabase"""
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
print("=== Sync Stats Joueurs (Soccerway) ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

matches = get_matches_without_stats()
print(f"\n{len(matches)} matchs sans stats à traiter\n")

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

    stats = scrape_match_stats(mid)

    # Enrichir les joueurs avec les stats
    hp = enrich_players(match.get("home_players") or [], stats, is_sub=False)
    ap = enrich_players(match.get("away_players") or [], stats, is_sub=False)
    hs = enrich_players(match.get("home_subs") or [], stats, is_sub=True)
    as_ = enrich_players(match.get("away_subs") or [], stats, is_sub=True)

    # Afficher un résumé
    hp_min = [p.get("minutes") for p in hp if p.get("minutes")]
    print(f"  → {len(hp)} dom: {hp_min[:3]}... | {len(ap)} ext")

    # Sauvegarder
    ok = update_match_stats(match["id"], hp, ap, hs, as_)
    if ok:
        print(f"  ✅ Sauvegardé")
        updated += 1
    else:
        print(f"  ❌ Erreur sauvegarde")
        errors += 1

    time.sleep(2)  # Pause entre chaque match

print(f"\n=== Terminé: {updated} mis à jour, {errors} erreurs ===")