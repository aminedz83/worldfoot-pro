#!/usr/bin/env python3
"""
Analyse rétrospective des tickets figés.
Pour chaque ticket terminé, simule : si on avait joué seulement les N meilleurs
matchs (3, 4, 5, 6, 7), aurait-on gagné le combiné ?

Un combiné de N matchs gagne SEULEMENT si les N matchs sont tous corrects.
On classe les matchs du ticket par confiance (les "meilleurs" = confiance la plus haute).

Stocke le résultat dans ticket_format_stats pour affichage dans l'app.

Secrets : PREDICTIONS_SUPA_URL · PREDICTIONS_SUPA_KEY
"""

import os
from datetime import datetime
from supabase import create_client

SUPA_URL = os.environ["PREDICTIONS_SUPA_URL"].strip()
SUPA_KEY = os.environ["PREDICTIONS_SUPA_KEY"].strip()
supabase = create_client(SUPA_URL, SUPA_KEY)

FORMATS = [2, 3, 4]


def get_finished_tickets():
    """Récupère les tickets dont tous les matchs sont joués (won ou lost)."""
    try:
        r = supabase.table("daily_tickets") \
            .select("*") \
            .in_("status", ["won", "lost"]) \
            .execute()
        return r.data or []
    except Exception as e:
        print(f"  [ERR] lecture tickets : {e}")
        return []


def simulate(tickets):
    """
    Pour chaque format N, compte combien de tickets auraient gagné
    si on avait joué seulement les N meilleurs matchs.
    """
    results = {n: {"total": 0, "won": 0, "sum_odds_won": 0.0} for n in FORMATS}

    for t in tickets:
        matches = t.get("matches") or []
        # Garder seulement les matchs avec un résultat connu
        played = [m for m in matches if m.get("prediction_correct") is not None]
        if len(played) < 2:
            continue

        # Trier par confiance décroissante (les meilleurs d'abord)
        played.sort(key=lambda m: (m.get("rec_confidence") or 0), reverse=True)

        for n in FORMATS:
            if len(played) < n:
                continue
            top_n = played[:n]
            # Le combiné gagne si TOUS les n matchs sont corrects
            all_correct = all(m.get("prediction_correct") is True for m in top_n)
            results[n]["total"] += 1
            if all_correct:
                results[n]["won"] += 1
                # cote du combiné = produit des cotes
                cote = 1.0
                for m in top_n:
                    cote *= float(m.get("cote") or 1.0)
                results[n]["sum_odds_won"] += cote

    return results


def save_stats(results):
    """Sauvegarde l'analyse dans ticket_format_stats."""
    now = datetime.utcnow().isoformat()
    for n in FORMATS:
        d = results[n]
        total = d["total"]
        won = d["won"]
        rate = round(won / total * 100, 1) if total else 0.0
        # Gain moyen quand ça gagne (cote moyenne des combinés gagnants)
        avg_odds = round(d["sum_odds_won"] / won, 2) if won else 0.0
        # Rendement attendu : (taux de réussite × cote moyenne)
        # > 1 = rentable sur le long terme
        expected = round((rate / 100) * avg_odds, 2) if avg_odds else 0.0
        try:
            supabase.table("ticket_format_stats").upsert({
                "num_matches":   n,
                "total_tickets": total,
                "won_tickets":   won,
                "win_rate":      rate,
                "avg_odds_won":  avg_odds,
                "expected_value": expected,
                "updated_at":    now,
            }, on_conflict="num_matches").execute()
        except Exception as e:
            print(f"  [DB ERR] format {n}: {e}")


def print_report(results):
    print(f"\n{'='*60}")
    print("  ANALYSE FORMAT DE TICKET — Quel nombre de matchs ?")
    print(f"{'='*60}\n")
    print(f"  {'Format':<10}{'Tickets':<10}{'Gagnés':<10}{'Taux':<10}{'Cote moy':<10}{'Rendement'}")
    print(f"  {'-'*58}")

    best_n = None
    best_ev = -1
    for n in FORMATS:
        d = results[n]
        total = d["total"]
        won = d["won"]
        rate = round(won / total * 100, 1) if total else 0.0
        avg_odds = round(d["sum_odds_won"] / won, 2) if won else 0.0
        ev = round((rate / 100) * avg_odds, 2) if avg_odds else 0.0
        flag = ""
        if total >= 10 and ev > best_ev:
            best_ev = ev
            best_n = n
        print(f"  {str(n)+' matchs':<10}{total:<10}{won:<10}{str(rate)+'%':<10}{str(avg_odds):<10}{ev}")

    print()
    if best_n:
        print(f"  💡 RECOMMANDATION : {best_n} matchs offre le meilleur rendement ({best_ev})")
        print(f"     (Rendement > 1 = rentable · < 1 = perdant sur le long terme)")
    else:
        print("  ⚠️ Pas assez de tickets terminés (min 10 par format) pour conclure.")
        print("     Continue d'accumuler — reviens dans quelques semaines.")
    print(f"\n{'='*60}\n")


def main():
    print(f"\n=== Analyze Tickets — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC ===")
    tickets = get_finished_tickets()
    print(f"{len(tickets)} ticket(s) terminé(s) à analyser")

    if not tickets:
        print("Aucun ticket terminé — analyse impossible pour l'instant.")
        return

    results = simulate(tickets)
    print_report(results)
    save_stats(results)
    print("Analyse sauvegardée dans Supabase · table ticket_format_stats")


if __name__ == "__main__":
    main()