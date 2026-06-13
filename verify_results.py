"""
verify_results.py
=================
Vérifie les résultats des prédictions J-1 ET du jour même
Met à jour prediction_correct dans predictions et daily_top25
Calcule le taux de réussite réel du moteur

Cron GitHub Actions : toutes les heures 8h-23h UTC
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


def get_unverified_predictions():
    """
    Fenêtre : 3 jours en arrière jusqu'à maintenant (inclus aujourd'hui).
    """
    now_iso        = datetime.utcnow().isoformat()
    three_days_ago = (datetime.utcnow() - timedelta(days=3)).date().isoformat()
    try:
        result = supabase.table("predictions")\
            .select("id, fixture_id, recommendation, "
                    "rec_confidence, league_name, "
                    "home_team_name, away_team_name, match_date")\
            .is_("prediction_correct", "null")\
            .gte("match_date", three_days_ago)\
            .lte("match_date", now_iso)\
            .execute()
        return result.data or []
    except Exception as e:
        print(f"  [ERR] {e}")
        return []


def get_fixture_result(fixture_id):
    data = api("fixtures", {"id": fixture_id})
    if not data:
        return None
    fix    = data[0]
    status = fix.get("fixture", {}).get("status", {}).get("short", "")
    if status not in ("FT", "AET", "PEN"):
        return None
    goals = fix.get("goals", {})
    gh    = goals.get("home")
    ga    = goals.get("away")
    if gh is None or ga is None:
        return None
    return {
        "home_goals":  gh,
        "away_goals":  ga,
        "total_goals": gh + ga,
        "btts":        gh > 0 and ga > 0,
        "under25":     (gh + ga) < 3,
        "home_win":    gh > ga,
        "away_win":    ga > gh,
        "draw":        gh == ga,
        "status":      status,
    }


def check_prediction(recommendation, result):
    rec = recommendation.upper()
    if "UNDER 2.5"                                    in rec: return result["under25"]
    if "BTTS"                                         in rec: return result["btts"]
    if "VICTOIRE DOMICILE"                            in rec: return result["home_win"]
    if "VICTOIRE EXTÉRIEUR" in rec or "VICTOIRE EXTERIEUR" in rec: return result["away_win"]
    if "DOUBLE CHANCE 1X"                             in rec: return result["home_win"] or result["draw"]
    if "DOUBLE CHANCE X2"                             in rec: return result["away_win"] or result["draw"]
    return None


def update_prediction(pred_id, result, is_correct):
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
    try:
        supabase.table("daily_top25").update({
            "prediction_correct": is_correct,
        }).eq("fixture_id", fixture_id).execute()
    except Exception:
        pass


def update_daily_tickets():
    """
    Met à jour le statut des tickets figés (daily_tickets) selon les résultats.
    Ne change JAMAIS les matchs du ticket — met juste à jour won/lost/pending et le statut.
    """
    try:
        # Récupérer les tickets pas encore finalisés
        r = supabase.table("daily_tickets") \
            .select("*") \
            .neq("status", "won") \
            .neq("status", "lost") \
            .execute()
        tickets = r.data or []
    except Exception as e:
        print(f"  [TICKET] Lecture échouée : {e}")
        return

    for ticket in tickets:
        matches = ticket.get("matches") or []
        if not matches:
            continue

        # Récupérer les résultats actuels de chaque match du ticket
        changed = False
        won = lost = pending = 0
        for m in matches:
            fid = m.get("fixture_id")
            try:
                pr = supabase.table("predictions") \
                    .select("prediction_correct") \
                    .eq("fixture_id", fid) \
                    .limit(1) \
                    .execute()
                pc = (pr.data[0]["prediction_correct"] if pr.data else None)
            except Exception:
                pc = m.get("prediction_correct")

            if m.get("prediction_correct") != pc:
                m["prediction_correct"] = pc
                changed = True

            if pc is True:    won += 1
            elif pc is False: lost += 1
            else:             pending += 1

        # Déterminer le statut global
        if lost > 0:
            status = "lost"          # un seul perdu = ticket perdu
        elif pending == 0:
            status = "won"           # tous joués et aucun perdu = gagné
        else:
            status = "pending"       # encore des matchs à jouer

        try:
            supabase.table("daily_tickets").update({
                "matches":       matches,
                "won_count":     won,
                "lost_count":    lost,
                "pending_count": pending,
                "status":        status,
            }).eq("id", ticket["id"]).execute()
            if changed or status != ticket.get("status"):
                print(f"  [TICKET {ticket['ticket_date']}] {won}✅ {lost}❌ {pending}⏳ → {status}")
        except Exception as e:
            print(f"  [TICKET update err] {e}")


def compute_daily_stats(verified):
    if not verified:
        return
    total   = len(verified)
    correct = sum(1 for v in verified if v["correct"] is True)
    wrong   = sum(1 for v in verified if v["correct"] is False)
    rate    = round(correct / total * 100, 1) if total else 0
    by_market = {}
    for v in verified:
        rec = v["recommendation"].upper()
        if   "UNDER"    in rec: market = "UNDER 2.5"
        elif "BTTS"     in rec: market = "BTTS"
        elif "VICTOIRE" in rec: market = "VICTOIRE"
        else:                   market = "AUTRE"
        if market not in by_market:
            by_market[market] = {"total": 0, "correct": 0}
        by_market[market]["total"] += 1
        if v["correct"]:
            by_market[market]["correct"] += 1

    print(f"\n{'═'*55}")
    print(f"  BILAN — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
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
        r = round(c / t * 100, 1) if t else 0
        print(f"    {market:<15} {c}/{t} = {r}%")
    print(f"{'═'*55}\n")
    print("  Détail :")
    for v in sorted(verified, key=lambda x: x["correct"] is False):
        icon = "✅" if v["correct"] else "❌"
        print(
            f"  {icon} {v['home']} vs {v['away']}\n"
            f"     {v['recommendation']} · "
            f"Résultat : {v['home_goals']}-{v['away_goals']} · "
            f"Conf {v['rec_confidence']}%\n"
        )


def main():
    print(f"\n=== Verify Results — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC ===\n")
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
        print(f"  → {pred['home_team_name']} vs {pred['away_team_name']} ({pred['league_name']})")
        result = get_fixture_result(fixture_id)
        if not result:
            print(f"    [SKIP] Match pas encore terminé ou données indisponibles")
            skipped += 1
            continue
        is_correct = check_prediction(rec, result)
        if is_correct is None:
            print(f"    [SKIP] Type de recommandation non reconnu : {rec}")
            skipped += 1
            continue
        update_prediction(pred["id"], result, is_correct)
        update_top25(fixture_id, is_correct)
        icon = "✅" if is_correct else "❌"
        print(f"    {icon} {rec} · Score réel : {result['home_goals']}-{result['away_goals']} · {'CORRECT' if is_correct else 'INCORRECT'}")
        verified.append({
            "home":           pred["home_team_name"],
            "away":           pred["away_team_name"],
            "recommendation": rec,
            "rec_confidence": pred["rec_confidence"],
            "correct":        is_correct,
            "home_goals":     result["home_goals"],
            "away_goals":     result["away_goals"],
        })

    compute_daily_stats(verified)

    # Mettre à jour le statut des tickets figés
    print("\n=== Mise à jour tickets figés ===")
    update_daily_tickets()

    print(f"=== Terminé : {len(verified)} vérifiés · {skipped} ignorés ===\n")


if __name__ == "__main__":
    main()