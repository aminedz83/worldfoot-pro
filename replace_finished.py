"""
replace_finished.py
===================
Remplace automatiquement les matchs terminés dans le Top 25
par de nouveaux matchs à haute confiance (≥ 78% · Risque Faible)

Cron GitHub Actions : toutes les heures de 08h à 23h UTC
Secrets : API_FOOTBALL_KEY · PREDICTIONS_SUPA_URL · PREDICTIONS_SUPA_KEY
"""

import os
import requests
from datetime import datetime, timedelta
from supabase import create_client

API_KEY  = os.environ["API_FOOTBALL_KEY"].strip()
SUPA_URL = os.environ["PREDICTIONS_SUPA_URL"].strip()
SUPA_KEY = os.environ["PREDICTIONS_SUPA_KEY"].strip()

API_BASE = "https://v3.football.api-sports.io"
HEADERS  = {"x-apisports-key": API_KEY}

supabase = create_client(SUPA_URL, SUPA_KEY)

# Seuil strict pour les remplaçants
MIN_CONF_REPLACE = 78
MAX_HOURS_AHEAD  = 8   # Match dans les 8 prochaines heures


def api(endpoint, params={}):
    try:
        r = requests.get(
            f"{API_BASE}/{endpoint}",
            headers=HEADERS, params=params, timeout=15
        )
        if r.status_code != 200:
            return None
        d = r.json()
        return None if d.get("errors") else d.get("response", [])
    except Exception:
        return None


def get_finished_slots():
    """
    Récupère les matchs du Top 25 qui sont terminés
    ou dont l'heure est passée depuis plus d'1h30.
    Retourne le nombre de slots libres.
    """
    today = datetime.utcnow().date().isoformat()
    try:
        result = supabase.table("daily_top25")\
            .select("id, fixture_id, rank, match_date, prediction_correct")\
            .eq("selection_date", today)\
            .execute()
        top25 = result.data or []
    except Exception as e:
        print(f"[ERR] Lecture Top 25 : {e}")
        return 0, [], []

    now_utc     = datetime.utcnow()
    finished    = []
    active_fids = []

    for item in top25:
        if item.get("prediction_correct") is not None:
            # Match déjà vérifié = terminé
            finished.append(item["id"])
            continue

        # Vérifier si l'heure du match est passée depuis plus d'1h30
        match_date_str = item.get("match_date", "")
        if match_date_str:
            try:
                md = datetime.fromisoformat(match_date_str.replace("Z", ""))
                if md < now_utc - timedelta(hours=1, minutes=30):
                    # Match probablement terminé
                    finished.append(item["id"])
                    continue
            except Exception:
                pass

        active_fids.append(item.get("fixture_id"))

    slots_free = len(finished)
    print(f"[REPLACE] {slots_free} slots libres · {len(active_fids)} matchs actifs")

    return slots_free, finished, active_fids


def get_candidates(active_fids):
    """
    Cherche les meilleures prédictions disponibles
    qui ne sont pas encore dans le Top 25.
    """
    now_utc  = datetime.utcnow()
    cutoff   = (now_utc + timedelta(hours=MAX_HOURS_AHEAD)).isoformat()
    now_str  = now_utc.isoformat()
    today    = now_utc.date().isoformat()

    try:
        result = supabase.table("predictions")\
            .select("*")\
            .gte("match_date", now_str)\
            .lte("match_date", cutoff)\
            .gte("rec_confidence", MIN_CONF_REPLACE)\
            .eq("risk_level", "Faible")\
            .is_("prediction_correct", "null")\
            .neq("odds_signal", "Mouvement contraire")\
            .order("rec_confidence", desc=True)\
            .limit(50)\
            .execute()

        all_preds = result.data or []
    except Exception as e:
        print(f"[ERR] Lecture candidats : {e}")
        return []

    # Exclure les matchs déjà dans le Top 25
    candidates = [
        p for p in all_preds
        if p.get("fixture_id") not in active_fids
    ]

    print(f"[REPLACE] {len(candidates)} candidats qualifiés (conf ≥ {MIN_CONF_REPLACE}% · Risque Faible)")
    return candidates


def remove_finished(finished_ids):
    """Supprime les slots terminés du Top 25."""
    for fid in finished_ids:
        try:
            supabase.table("daily_top25")\
                .delete()\
                .eq("id", fid)\
                .execute()
        except Exception as e:
            print(f"  [ERR] Suppression {fid} : {e}")


def add_replacement(pred, rank, today_str):
    """Ajoute un match remplaçant dans le Top 25."""
    try:
        supabase.table("daily_top25").insert({
            "rank":             rank,
            "selection_date":   today_str,
            "fixture_id":       pred["fixture_id"],
            "prediction_id":    pred["id"],
            "league_name":      pred["league_name"],
            "league_tier":      pred.get("league_tier", 1),
            "match_date":       pred["match_date"],
            "home_team_name":   pred["home_team_name"],
            "away_team_name":   pred["away_team_name"],
            "recommendation":   pred["recommendation"],
            "rec_confidence":   pred["rec_confidence"],
            "selection_score":  pred["rec_confidence"] + 5,  # bonus remplaçant urgent
            "risk_level":       pred["risk_level"],
            "odds_signal":      pred.get("odds_signal", "Neutre"),
            "pinnacle_under25": pred.get("pinnacle_under25"),
            "pinnacle_home":    pred.get("pinnacle_home"),
            "pinnacle_away":    pred.get("pinnacle_away"),
            "pinnacle_draw":    pred.get("pinnacle_draw"),
            "xg_total":         pred.get("xg_total"),
            "context_text":     pred.get("context_text", ""),
            "prediction_correct": None,
            "created_at":       datetime.utcnow().isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"  [ERR] Insertion remplaçant : {e}")
        return False


def verify_finished_results(active_fids):
    """
    Vérifie en temps réel les scores des matchs actifs
    pour détecter les matchs terminés non encore marqués.
    """
    if not active_fids:
        return

    print(f"\n[VERIFY] Vérification de {len(active_fids)} matchs actifs...")

    for fixture_id in active_fids[:10]:  # max 10 pour économiser le quota
        if not fixture_id:
            continue

        data = api("fixtures", {"id": fixture_id})
        if not data:
            continue

        fix    = data[0]
        status = fix.get("fixture", {}).get("status", {}).get("short", "")
        goals  = fix.get("goals", {})
        gh     = goals.get("home")
        ga     = goals.get("away")

        if status not in ("FT", "AET", "PEN") or gh is None or ga is None:
            continue

        # Match terminé — chercher la prédiction correspondante
        try:
            preds = supabase.table("predictions")\
                .select("id, recommendation, rec_confidence")\
                .eq("fixture_id", fixture_id)\
                .is_("prediction_correct", "null")\
                .execute()

            for pred in (preds.data or []):
                rec = pred["recommendation"].upper()
                total = gh + ga

                if "UNDER 2.5" in rec:
                    correct = total < 3
                elif "BTTS" in rec:
                    correct = gh > 0 and ga > 0
                elif "VICTOIRE DOMICILE" in rec:
                    correct = gh > ga
                elif "VICTOIRE EXT" in rec:
                    correct = ga > gh
                elif "1X" in rec:
                    correct = gh >= ga
                elif "X2" in rec:
                    correct = ga >= gh
                else:
                    correct = None

                if correct is not None:
                    icon = "✅" if correct else "❌"
                    print(
                        f"  {icon} {fix['teams']['home']['name']} "
                        f"{gh}-{ga} {fix['teams']['away']['name']} · "
                        f"{rec} → {'CORRECT' if correct else 'INCORRECT'}"
                    )
                    supabase.table("predictions").update({
                        "actual_home_goals":  gh,
                        "actual_away_goals":  ga,
                        "actual_total_goals": total,
                        "prediction_correct": correct,
                    }).eq("id", pred["id"]).execute()

                    supabase.table("daily_top25").update({
                        "prediction_correct": correct,
                    }).eq("fixture_id", fixture_id).execute()

        except Exception as e:
            print(f"  [ERR] Vérification fixture {fixture_id} : {e}")


def rerank_top25(today_str):
    """Rerange les entrées du Top 25 par score décroissant."""
    try:
        result = supabase.table("daily_top25")\
            .select("id, rec_confidence, selection_score")\
            .eq("selection_date", today_str)\
            .is_("prediction_correct", "null")\
            .order("rec_confidence", desc=True)\
            .execute()

        for i, item in enumerate(result.data or [], 1):
            supabase.table("daily_top25")\
                .update({"rank": i})\
                .eq("id", item["id"])\
                .execute()
    except Exception:
        pass


def main():
    print(
        f"\n=== Replace Finished — "
        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC ===\n"
    )

    today_str = datetime.utcnow().date().isoformat()

    # 1. Vérifier les résultats des matchs actifs
    slots_free, finished_ids, active_fids = get_finished_slots()
    verify_finished_results(active_fids)

    # Re-vérifier après update
    slots_free, finished_ids, active_fids = get_finished_slots()

    if slots_free == 0:
        print("Aucun slot libre — Top 25 complet.")
        return

    # 2. Trouver les meilleurs remplaçants
    candidates = get_candidates(active_fids)

    if not candidates:
        print(f"Aucun remplaçant qualifié disponible (conf ≥ {MIN_CONF_REPLACE}%).")
        remove_finished(finished_ids)
        rerank_top25(today_str)
        return

    # 3. Supprimer les slots terminés
    remove_finished(finished_ids)

    # 4. Calculer le prochain rang disponible
    try:
        existing = supabase.table("daily_top25")\
            .select("rank")\
            .eq("selection_date", today_str)\
            .order("rank", desc=True)\
            .limit(1)\
            .execute()
        max_rank = existing.data[0]["rank"] if existing.data else 0
    except Exception:
        max_rank = 25

    # 5. Ajouter les remplaçants
    added = 0
    seen_leagues = {}
    MAX_PER_LEAGUE_REPLACE = 2  # Plus strict pour les remplaçants

    for pred in candidates:
        if added >= slots_free:
            break

        # Règle diversité
        league_id = pred.get("league_id")
        if seen_leagues.get(league_id, 0) >= MAX_PER_LEAGUE_REPLACE:
            continue

        rank = max_rank + added + 1
        ok   = add_replacement(pred, rank, today_str)

        if ok:
            added += 1
            seen_leagues[league_id] = seen_leagues.get(league_id, 0) + 1
            print(
                f"  ➕ #{rank} {pred['home_team_name']} vs {pred['away_team_name']} "
                f"· {pred['recommendation']} {pred['rec_confidence']}%"
            )

    # 6. Reranker
    rerank_top25(today_str)

    print(
        f"\n=== Terminé : {added}/{slots_free} slots remplacés "
        f"· {len(candidates)} candidats disponibles ===\n"
    )


if __name__ == "__main__":
    main()