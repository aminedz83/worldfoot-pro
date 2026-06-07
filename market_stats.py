"""
market_stats.py
===============
Calcule les taux de réussite réels par marché
basé sur les vrais résultats vérifiés dans Supabase.
Tourne après verify_results.py — cron 03h30 UTC

Secrets : PREDICTIONS_SUPA_URL · PREDICTIONS_SUPA_KEY
"""

import os
from datetime import datetime, timedelta
from supabase import create_client

SUPA_URL = os.environ["PREDICTIONS_SUPA_URL"].strip()
SUPA_KEY = os.environ["PREDICTIONS_SUPA_KEY"].strip()
supabase = create_client(SUPA_URL, SUPA_KEY)


def compute_market_stats():
    """
    Calcule les stats de performance pour chaque marché
    sur 7j · 30j · 90j · tout le temps
    """

    periods = [
        {"label": "7j",   "days": 7},
        {"label": "30j",  "days": 30},
        {"label": "90j",  "days": 90},
        {"label": "tout", "days": 9999},
    ]

    markets = ["UNDER 2.5", "BTTS", "VICTOIRE"]

    results = {}

    for period in periods:
        period_label = period["label"]
        results[period_label] = {}

        if period["days"] < 9999:
            from_date = (datetime.utcnow() - timedelta(days=period["days"])).isoformat()
        else:
            from_date = "2024-01-01T00:00:00"

        for market in markets:
            try:
                # Récupérer toutes les prédictions vérifiées pour ce marché
                if market == "VICTOIRE":
                    # Inclure VICTOIRE DOMICILE, EXTÉRIEUR, DOUBLE CHANCE
                    r = supabase.table("predictions")\
                        .select("prediction_correct, rec_confidence, league_name, league_tier")\
                        .not_.is_("prediction_correct", "null")\
                        .gte("match_date", from_date)\
                        .ilike("recommendation", "%VICTOIRE%")\
                        .execute()
                    r2 = supabase.table("predictions")\
                        .select("prediction_correct, rec_confidence, league_name, league_tier")\
                        .not_.is_("prediction_correct", "null")\
                        .gte("match_date", from_date)\
                        .ilike("recommendation", "%DOUBLE%")\
                        .execute()
                    data = (r.data or []) + (r2.data or [])
                else:
                    r = supabase.table("predictions")\
                        .select("prediction_correct, rec_confidence, league_name, league_tier")\
                        .not_.is_("prediction_correct", "null")\
                        .gte("match_date", from_date)\
                        .ilike("recommendation", f"%{market}%")\
                        .execute()
                    data = r.data or []

                total   = len(data)
                correct = sum(1 for p in data if p["prediction_correct"] is True)
                rate    = round(correct / total * 100, 1) if total > 0 else None
                avg_conf = round(
                    sum(p["rec_confidence"] or 0 for p in data) / total, 1
                ) if total > 0 else None

                results[period_label][market] = {
                    "total":    total,
                    "correct":  correct,
                    "rate":     rate,
                    "avg_conf": avg_conf,
                }

            except Exception as e:
                print(f"  [ERR] {market} {period_label} : {e}")
                results[period_label][market] = {
                    "total": 0, "correct": 0, "rate": None, "avg_conf": None
                }

    return results


def find_best_market(stats_30j):
    """
    Détermine le meilleur marché sur les 30 derniers jours.
    Prend en compte le taux ET le nombre de matchs (fiabilité).
    """
    best_market = None
    best_score  = -1

    for market, stats in stats_30j.items():
        if stats["total"] < 5:
            continue  # Pas assez de données

        rate  = stats["rate"] or 0
        total = stats["total"]

        # Score = taux * (1 - 1/sqrt(total)) — favorise les marchés avec plus de données
        import math
        score = rate * (1 - 1 / max(math.sqrt(total), 1))

        if score > best_score:
            best_score  = score
            best_market = market

    return best_market


def compute_xg_stats():
    """
    Analyse le taux de réussite par tranche de xG.
    Permet de décider si un ajustement xG est nécessaire.
    """
    try:
        r = supabase.table("predictions")            .select("prediction_correct, xg_total, recommendation, rec_confidence")            .not_.is_("prediction_correct", "null")            .not_.is_("xg_total", "null")            .gte("match_date", "2024-01-01T00:00:00")            .execute()
        data = r.data or []
    except Exception as e:
        print(f"  [ERR] xG stats : {e}")
        return

    # Tranches xG
    tranches = [
        {"label": "xG < 1.0",      "min": 0,   "max": 1.0},
        {"label": "xG 1.0 - 1.5",  "min": 1.0, "max": 1.5},
        {"label": "xG 1.5 - 2.0",  "min": 1.5, "max": 2.0},
        {"label": "xG 2.0 - 2.5",  "min": 2.0, "max": 2.5},
        {"label": "xG > 2.5",      "min": 2.5, "max": 99},
    ]

    print("\n  📊 ANALYSE PAR TRANCHE xG (Victoire uniquement)")
    print(f"  {'Tranche':<18} {'Total':>6} {'Correct':>8} {'Taux':>8}")
    print(f"  {'-'*45}")

    for t in tranches:
        subset = [
            p for p in data
            if t["min"] <= (p["xg_total"] or 0) < t["max"]
            and ("VICTOIRE" in (p["recommendation"] or "") or "DOUBLE" in (p["recommendation"] or ""))
        ]
        total   = len(subset)
        correct = sum(1 for p in subset if p["prediction_correct"] is True)
        rate    = round(correct / total * 100, 1) if total > 0 else None
        rate_str = f"{rate}%" if rate is not None else "N/A"
        flag = " ⚠️" if (rate is not None and rate < 70 and total >= 5) else ""
        print(f"  {t['label']:<18} {total:>6} {correct:>8} {rate_str:>8}{flag}")

    print()


def save_stats(stats):
    """Sauvegarde les stats dans Supabase table market_performance."""
    now = datetime.utcnow().isoformat()

    for period_label, period_data in stats.items():
        for market, s in period_data.items():
            try:
                supabase.table("market_performance").upsert({
                    "market":      market,
                    "period":      period_label,
                    "total":       s["total"],
                    "correct":     s["correct"],
                    "rate":        s["rate"],
                    "avg_conf":    s["avg_conf"],
                    "updated_at":  now,
                }, on_conflict="market,period").execute()
            except Exception as e:
                print(f"  [DB] {market} {period_label} : {e}")


def print_report(stats):
    """Affiche le rapport de performance dans les logs."""
    print("\n" + "═" * 60)
    print("  PERFORMANCE PAR MARCHÉ — RÉSULTATS RÉELS")
    print("═" * 60)

    for period_label in ["7j", "30j", "90j"]:
        period_data = stats.get(period_label, {})
        print(f"\n  📅 Période : {period_label}")
        print(f"  {'Marché':<15} {'Total':>6} {'Correct':>8} {'Taux':>8} {'Conf.moy':>10}")
        print(f"  {'-'*50}")

        period_results = []
        for market in ["UNDER 2.5", "BTTS", "VICTOIRE"]:
            s = period_data.get(market, {})
            total   = s.get("total", 0)
            correct = s.get("correct", 0)
            rate    = s.get("rate")
            avg_c   = s.get("avg_conf")
            rate_str = f"{rate}%" if rate is not None else "N/A"
            avg_str  = f"{avg_c}%" if avg_c is not None else "N/A"
            period_results.append((market, total, rate or 0))
            print(f"  {market:<15} {total:>6} {correct:>8} {rate_str:>8} {avg_str:>10}")

        # Meilleur marché de cette période
        valid = [(m, t, r) for m, t, r in period_results if t >= 5]
        if valid:
            best = max(valid, key=lambda x: x[2])
            print(f"\n  🏆 Meilleur marché ({period_label}) : {best[0]} → {best[2]}%")

    # Recommandation globale sur 30j
    best_30j = find_best_market(stats.get("30j", {}))
    if best_30j:
        rate_30j = stats["30j"][best_30j].get("rate", 0)
        total_30j = stats["30j"][best_30j].get("total", 0)
        print(f"\n{'═'*60}")
        print(f"  💡 RECOMMANDATION GLOBALE (30j)")
        print(f"  → Miser en priorité sur : {best_30j}")
        print(f"  → Taux de réussite : {rate_30j}% sur {total_30j} matchs vérifiés")
        print(f"{'═'*60}\n")
    else:
        print("\n  ⚠️ Pas encore assez de données — continuez à utiliser le moteur")


def main():
    print(
        f"\n=== Market Stats — "
        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC ===\n"
    )

    stats = compute_market_stats()
    print_report(stats)
    save_stats(stats)
    print("Stats sauvegardées dans Supabase · table market_performance")

    # Analyse xG — pour décider d'ajustements futurs
    print("\n=== Analyse xG ===")
    compute_xg_stats()


if __name__ == "__main__":
    main()