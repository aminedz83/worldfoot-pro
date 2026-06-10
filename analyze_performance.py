"""
analyze_performance.py
======================
Rapport de performance sur 30 jours — lit directement Supabase.
Lance manuellement : python analyze_performance.py

Secrets : PREDICTIONS_SUPA_URL · PREDICTIONS_SUPA_KEY
"""

import os
from datetime import datetime, timedelta
from supabase import create_client

SUPA_URL = os.environ["PREDICTIONS_SUPA_URL"].strip()
SUPA_KEY = os.environ["PREDICTIONS_SUPA_KEY"].strip()
supabase = create_client(SUPA_URL, SUPA_KEY)

DAYS = 30


def fetch_verified():
    since = (datetime.utcnow() - timedelta(days=DAYS)).isoformat()
    try:
        r = supabase.table("predictions") \
            .select("id,recommendation,rec_confidence,league_name,league_tier,"
                    "home_team_name,away_team_name,match_date,"
                    "actual_home_goals,actual_away_goals,xg_total,prediction_correct") \
            .not_.is_("prediction_correct", "null") \
            .gte("match_date", since) \
            .order("match_date", desc=True) \
            .execute()
        return r.data or []
    except Exception as e:
        print(f"[ERR] {e}")
        return []


def market(rec):
    rec = rec.upper()
    if "UNDER"    in rec: return "UNDER 2.5"
    if "BTTS"     in rec: return "BTTS"
    if "DOUBLE"   in rec: return "DOUBLE CHANCE"
    if "VICTOIRE" in rec: return "VICTOIRE"
    return "AUTRE"


def tranche_conf(conf):
    if conf is None: return "N/A"
    if conf >= 90:   return "90%+"
    if conf >= 85:   return "85-90%"
    if conf >= 80:   return "80-85%"
    if conf >= 75:   return "75-80%"
    return "< 75%"


def tranche_xg(xg):
    if xg is None:   return "N/A"
    if xg < 1.0:     return "xG < 1.0"
    if xg < 1.5:     return "xG 1.0-1.5"
    if xg < 2.0:     return "xG 1.5-2.0"
    if xg < 2.5:     return "xG 2.0-2.5"
    return "xG > 2.5"


def stats(items):
    total   = len(items)
    correct = sum(1 for x in items if x["prediction_correct"] is True)
    rate    = round(correct / total * 100, 1) if total else None
    return total, correct, rate


def print_table(title, data, min_total=3):
    """data = dict {label: [pred, ...]}"""
    print(f"\n{'─'*65}")
    print(f"  {title}")
    print(f"{'─'*65}")
    print(f"  {'Label':<35} {'Total':>6} {'✅':>6} {'Taux':>8}")
    print(f"  {'─'*60}")

    rows = []
    for label, preds in data.items():
        total, correct, rate = stats(preds)
        if total >= min_total:
            rows.append((label, total, correct, rate))

    rows.sort(key=lambda x: (x[3] or 0), reverse=True)

    for label, total, correct, rate in rows:
        flag = " ⚠️" if (rate is not None and rate < 70) else ""
        flag += " 🔥" if (rate is not None and rate >= 85 and total >= 10) else ""
        rate_str = f"{rate}%" if rate is not None else "N/A"
        print(f"  {label:<35} {total:>6} {correct:>6} {rate_str:>8}{flag}")


def main():
    print(f"\n{'═'*65}")
    print(f"  ANALYSE PERFORMANCE — {DAYS} DERNIERS JOURS")
    print(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"{'═'*65}")

    data = fetch_verified()
    if not data:
        print("  Aucune donnée trouvée.")
        return

    total, correct, rate = stats(data)
    print(f"\n  Total vérifié : {total}")
    print(f"  Correct       : {correct} ✅")
    print(f"  Taux global   : {rate}%")

    # ── Par marché ────────────────────────────────────────────────────────────
    by_market = {}
    for p in data:
        m = market(p["recommendation"] or "")
        by_market.setdefault(m, []).append(p)
    print_table("PAR MARCHÉ", by_market, min_total=3)

    # ── Par tranche de confiance ──────────────────────────────────────────────
    by_conf = {}
    for p in data:
        t = tranche_conf(p["rec_confidence"])
        by_conf.setdefault(t, []).append(p)
    print_table("PAR TRANCHE DE CONFIANCE", by_conf, min_total=3)

    # ── Par tranche xG ───────────────────────────────────────────────────────
    by_xg = {}
    for p in data:
        t = tranche_xg(p["xg_total"])
        by_xg.setdefault(t, []).append(p)
    print_table("PAR TRANCHE xG", by_xg, min_total=3)

    # ── Par ligue (top 25) ────────────────────────────────────────────────────
    by_league = {}
    for p in data:
        l = p["league_name"] or "Inconnue"
        by_league.setdefault(l, []).append(p)
    print_table("PAR LIGUE (min 3 matchs)", by_league, min_total=3)

    # ── Par marché × tranche confiance ───────────────────────────────────────
    print(f"\n{'─'*65}")
    print(f"  VICTOIRE — DÉTAIL PAR TRANCHE DE CONFIANCE")
    print(f"{'─'*65}")
    vic = [p for p in data if "VICTOIRE" in (p["recommendation"] or "").upper()]
    by_conf_vic = {}
    for p in vic:
        t = tranche_conf(p["rec_confidence"])
        by_conf_vic.setdefault(t, []).append(p)
    print_table("VICTOIRE × CONFIANCE", by_conf_vic, min_total=2)

    # ── Matchs échoués — détail ───────────────────────────────────────────────
    failed = [p for p in data if p["prediction_correct"] is False]
    print(f"\n{'─'*65}")
    print(f"  MATCHS ÉCHOUÉS ({len(failed)}) — DÉTAIL")
    print(f"{'─'*65}")

    # Regrouper par marché
    failed_by_market = {}
    for p in failed:
        m = market(p["recommendation"] or "")
        failed_by_market.setdefault(m, []).append(p)

    for m, preds in sorted(failed_by_market.items()):
        print(f"\n  [{m}] — {len(preds)} échec(s)")
        preds_sorted = sorted(preds, key=lambda x: x["rec_confidence"] or 0, reverse=True)
        for p in preds_sorted:
            date = (p["match_date"] or "")[:10]
            conf = p["rec_confidence"]
            xg   = p["xg_total"]
            gh   = p["actual_home_goals"]
            ga   = p["actual_away_goals"]
            score = f"{gh}-{ga}" if gh is not None else "N/A"
            print(f"    ❌ {date} · {p['home_team_name']} vs {p['away_team_name']}")
            print(f"       {p['recommendation']} · Conf {conf}% · xG {xg} · Score {score}")
            print(f"       Ligue : {p['league_name']}")

    # ── Recommandations finales ───────────────────────────────────────────────
    print(f"\n{'═'*65}")
    print(f"  RECOMMANDATIONS MOTEUR")
    print(f"{'═'*65}")

    for m, preds in by_market.items():
        t, c, r = stats(preds)
        if t >= 5:
            if r is not None and r < 70:
                print(f"  ⚠️  {m} ({r}% sur {t} matchs) → envisager désactivation ou seuil plus élevé")
            elif r is not None and r >= 80:
                print(f"  ✅ {m} ({r}% sur {t} matchs) → marché fiable, garder")

    for t_label, preds in by_conf.items():
        tot, cor, r = stats(preds)
        if tot >= 5 and r is not None and r < 65:
            print(f"  ⚠️  Tranche {t_label} ({r}% sur {tot} matchs) → relever le seuil minimum")

    print(f"\n{'═'*65}\n")


if __name__ == "__main__":
    main()