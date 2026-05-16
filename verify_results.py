"""
verify_results.py
=================
Vérifie les résultats des prédictions J-1
Met à jour prediction_correct dans predictions et daily_top25
Calcule le taux de réussite réel du moteur

Cron GitHub Actions : 03h00 UTC quotidien
Secrets : API_FOOTBALL_KEY · PREDICTIONS_SUPA_URL · PREDICTIONS_SUPA_KEY
"""

import os
import requests
from datetime import datetime, timedelta
from supabase import create_client

API_KEY  = os.environ["API_FOOTBALL_KEY"]
SUPA_URL = os.environ["PREDICTIONS_SUPA_URL"]
SUPA_KEY = os.environ["PREDICTIONS_SUPA_KEY"]

API_BASE = "https://v3.football.api-sports.io"
HEADERS  = {"x-apisports-key": API_KEY}

supabase = create_client(SUPA_URL, SUPA_KEY)


# ── API ───────────────────────────────────────────────────────────────────────

def api(endpoint, params={}):
    try:
        r = requests.get(
            f"{API_BASE}/{endpoint}",
            headers=HEADERS, params=params, timeout=15
        )
        if r.status_code != 200: return None
        d = r.json()
        return None if d.get("errors") else d.get("response", [])
    except Exception:
        return None


# ── RÉCUPÉRER LES PRÉDICTIONS À VÉRIFIER ─────────────────────────────────────

def get_unverified_predictions():
    """
    Récupère toutes les prédictions dont le match est terminé
    mais dont prediction_correct est encore NULL.
    """
    yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()
    three_days_ago = (datetime.utcnow() - timedelta(days=3)).date().isoformat()

    try:
        result = supabase.table("predictions")\
            .select("id, fixture_id, recommendation, "
                    "rec_confidence, league_name, "
                    "home_team_name, away_team_name, match_date")\
            .is_("prediction_correct", "null")\
            .gte("match_date", three_days_ago)\
            .lte("match_date", yesterday + "T23:59:59")\
            .execute()
        return result.data or []
    except Exception as e:
        print(f"  [ERR] {e}")
        return []


# ── RÉCUPÉRER LE RÉSULTAT RÉEL ────────────────────────────────────────────────

def get_fixture_result(fixture_id):
    """Récupère le score final d'un match via API-Football."""
    data = api("fixtures", {"id": fixture_id})
    if not data:
        return None

    fix    = data[0]
    status = fix.get("fixture", {}).get("status", {}).get("short", "")

    # Match pas encore terminé
    if status not in ("FT", "AET", "PEN"):
        return None

    goals = fix.get("goals", {})
    gh    = goals.get("home")
    ga    = goals.get("away")

    if gh is None or ga is None:
        return None

    return {
        "home_goals":   gh,
        "away_goals":   ga,
        "total_goals":  gh + ga,
        "btts":         gh > 0 and ga > 0,
        "under25":      (gh + ga) < 3,
        "home_win":     gh > ga,
        "away_win":     ga > gh,
        "draw":         gh == ga,
        "status":       status,
    }


# ── VÉRIFIER SI LA PRÉDICTION EST CORRECTE ───────────────────────────────────

def check_prediction(recommendation, result):
    """
    Vérifie si la prédiction était correcte par rapport au résultat réel.
    Retourne True, False, ou None si impossible à déterminer.
    """
    rec = recommendation.upper()

    if "UNDER 2.5" in rec:
        return result["under25"]

    elif "BTTS" in rec:
        return result["btts"]

    elif "VICTOIRE DOMICILE" in rec:
        return result["home_win"]

    elif "VICTOIRE EXTÉRIEUR" in rec or "VICTOIRE EXTERIEUR" in rec:
        return result["away_win"]

    elif "DOUBLE CHANCE 1X" in rec:
        return result["home_win"] or result["draw"]

    elif "DOUBLE CHANCE X2" in rec:
        return result["away_win"] or result["draw"]

    return None


# ── METTRE À JOUR SUPABASE ────────────────────────────────────────────────────

def update_prediction(pred_id, result, is_correct):
    """Met à jour la prédiction avec le résultat réel."""
    try:
        supabase.table("predictions").update({
            "actual_home_goals":  result["home_goals"],
            "actual_away_goals":  result["away_goals"],
            "actual_total_goals": result["total_goals"],
            "prediction_correct": is_correct,
        }).eq("id", pred_id).execute()
        return True
    except Exception as e:
        print(f"    [DB ERR] {e}")
        return False


def update_top25(fixture_id, is_correct):
    """Met à jour la table daily_top25 avec le résultat."""
    try:
        supabase.table("daily_top25").update({
            "prediction_correct": is_correct,
        }).eq("fixture_id", fixture_id).execute()
    except Exception:
        pass


# ── CALCULER ET AFFICHER LE BILAN ─────────────────────────────────────────────

def compute_daily_stats(verified):
    """Calcule et affiche le bilan de la journée."""
    if not verified:
        return

    total   = len(verified)
    correct = sum(1 for v in verified if v["correct"] is True)
    wrong   = sum(1 for v in verified if v["correct"] is False)
    rate    = round(correct / total * 100, 1) if total else 0

    # Par marché
    by_market = {}
    for v in verified:
        rec = v["recommendation"].upper()
        if   "UNDER"   in rec: market = "UNDER 2.5"
        elif "BTTS"    in rec: market = "BTTS"
        elif "VICTOIRE" in rec: market = "VICTOIRE"
        else:                  market = "AUTRE"

        if market not in by_market:
            by_market[market] = {"total":0,"correct":0}
        by_market[market]["total"] += 1
        if v["correct"]:
            by_market[market]["correct"] += 1

    print(f"\n{'═'*55}")
    print(f"  BILAN J-1 — {(datetime.utcnow()-timedelta(days=1)).date()}")
    print(f"{'═'*55}")
    print(f"  Total vérifié : {total}")
    print(f"  Correct       : {correct} ✅")
    print(f"  Incorrect     : {wrong} ❌")
    print(f"  Taux réussite : {rate}%")
    print(f"{'─'*55}")
    print(f"  Par marché :")
    for market, stats in sorted(by_market.items()):
        t = stats["total"]
        c = stats["correct"]
        r = round(c/t*100,1) if t else 0
        print(f"    {market:<15} {c}/{t} = {r}%")
    print(f"{'═'*55}\n")

    # Détail des prédictions
    print("  Détail :")
    for v in sorted(verified, key=lambda x: x["correct"] is False):
        icon = "✅" if v["correct"] else "❌"
        print(
            f"  {icon} {v['home']} vs {v['away']}\n"
            f"     {v['recommendation']} · "
            f"Résultat : {v['home_goals']}-{v['away_goals']} · "
            f"Conf {v['rec_confidence']}%\n"
        )


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print(
        f"\n=== Verify Results — "
        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC ===\n"
    )

    predictions = get_unverified_predictions()
    print(f"{len(predictions)} prédiction(s) à vérifier\n")

    if not predictions:
        print("Aucune prédiction à vérifier.")
        return

    verified = []
    skipped  = 0

    for pred in predictions:
        fixture_id = pred["fixture_id"]
        rec        = pred["recommendation"]

        print(f"  → {pred['home_team_name']} vs {pred['away_team_name']} "
              f"({pred['league_name']})")

        # Récupérer le résultat réel
        result = get_fixture_result(fixture_id)

        if not result:
            print(f"    [SKIP] Match pas encore terminé ou données indisponibles")
            skipped += 1
            continue

        # Vérifier la prédiction
        is_correct = check_prediction(rec, result)

        if is_correct is None:
            print(f"    [SKIP] Type de recommandation non reconnu : {rec}")
            skipped += 1
            continue

        # Mettre à jour Supabase
        update_prediction(pred["id"], result, is_correct)
        update_top25(fixture_id, is_correct)

        icon = "✅" if is_correct else "❌"
        print(
            f"    {icon} {rec} · "
            f"Score réel : {result['home_goals']}-{result['away_goals']} · "
            f"{'CORRECT' if is_correct else 'INCORRECT'}"
        )

        verified.append({
            "home":           pred["home_team_name"],
            "away":           pred["away_team_name"],
            "recommendation": rec,
            "rec_confidence": pred["rec_confidence"],
            "correct":        is_correct,
            "home_goals":     result["home_goals"],
            "away_goals":     result["away_goals"],
        })

    # Bilan
    compute_daily_stats(verified)
    print(
        f"=== Terminé : {len(verified)} vérifiés · "
        f"{skipped} ignorés ===\n"
    )


if __name__ == "__main__":
    main()