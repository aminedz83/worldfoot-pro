"""
odds_monitor.py
===============
Surveille les cotes des prédictions actives toutes les heures.
- Récupère les cotes actuelles via API-Football (Pinnacle, Bet365, 1xBet)
- Compare avec les cotes précédentes dans odds_history
- Si une cote Under 2.5 baisse de ≥5% → signal sharp → notification push

Cron GitHub Actions : toutes les heures 10h-23h UTC
Secrets : API_FOOTBALL_KEY · PREDICTIONS_SUPA_URL · PREDICTIONS_SUPA_KEY
"""

import os, requests
from datetime import datetime, timedelta
from supabase import create_client

API_KEY  = os.environ["API_FOOTBALL_KEY"].strip()
SUPA_URL = os.environ["PREDICTIONS_SUPA_URL"].strip()
SUPA_KEY = os.environ["PREDICTIONS_SUPA_KEY"].strip()

API_BASE = "https://v3.football.api-sports.io"
HEADERS  = {"x-apisports-key": API_KEY}

supabase = create_client(SUPA_URL, SUPA_KEY)

# Seuil de mouvement pour déclencher une alerte
SHARP_THRESHOLD   = -5.0   # -5% = cote baisse de 5% → signal sharp
MOVE_THRESHOLD    = -3.0   # -3% = mouvement notable (pas sharp mais intéressant)

# IDs bookmakers API-Football
BK_PINNACLE = 8
BK_BET365   = 4
BK_1XBET    = 36

# ── Appel API ────────────────────────────────────────────────────────────────

def api(endpoint, params={}):
    try:
        r = requests.get(
            f"{API_BASE}/{endpoint}",
            headers=HEADERS, params=params, timeout=15
        )
        if r.status_code != 200: return None
        d = r.json()
        return None if d.get("errors") else d.get("response", [])
    except Exception as e:
        print(f"  [ERR] {endpoint}: {e}")
        return None

# ── Récupérer les cotes d'un fixture ────────────────────────────────────────

def get_odds_for_fixture(fixture_id):
    """
    Récupère les cotes Under 2.5 et 1X2 pour un fixture.
    Bookmakers : Pinnacle (8), Bet365 (4), 1xBet (36)
    """
    result = {
        "pinnacle_under25": None,
        "bet365_under25":   None,
        "xbet_under25":     None,
        "pinnacle_home":    None,
        "pinnacle_away":    None,
        "pinnacle_draw":    None,
        "bet365_home":      None,
        "bet365_away":      None,
        "bet365_draw":      None,
        "xbet_home":        None,
        "xbet_away":        None,
        "xbet_draw":        None,
    }

    # Under 2.5 (bet_id=5) — tous bookmakers
    odds = api("odds", {"fixture": fixture_id, "bet": 5}) or []
    for item in odds:
        for bk in item.get("bookmakers", []):
            bk_id = bk.get("id")
            for bet in bk.get("bets", []):
                if bet.get("id") == 5:
                    for v in bet.get("values", []):
                        if v.get("value") == "Under 2.5":
                            o = float(v.get("odd") or 0)
                            if   bk_id == BK_PINNACLE: result["pinnacle_under25"] = o
                            elif bk_id == BK_BET365:   result["bet365_under25"]   = o
                            elif bk_id == BK_1XBET:    result["xbet_under25"]     = o

    # 1X2 (bet_id=1) — tous bookmakers
    odds_1x2 = api("odds", {"fixture": fixture_id, "bet": 1}) or []
    for item in odds_1x2:
        for bk in item.get("bookmakers", []):
            bk_id = bk.get("id")
            if bk_id not in (BK_PINNACLE, BK_BET365, BK_1XBET):
                continue
            for bet in bk.get("bets", []):
                if bet.get("id") == 1:
                    for v in bet.get("values", []):
                        vl = v.get("value")
                        o  = float(v.get("odd") or 0)
                        if bk_id == BK_PINNACLE:
                            if   vl == "Home": result["pinnacle_home"] = o
                            elif vl == "Away": result["pinnacle_away"] = o
                            elif vl == "Draw": result["pinnacle_draw"] = o
                        elif bk_id == BK_BET365:
                            if   vl == "Home": result["bet365_home"] = o
                            elif vl == "Away": result["bet365_away"] = o
                            elif vl == "Draw": result["bet365_draw"] = o
                        elif bk_id == BK_1XBET:
                            if   vl == "Home": result["xbet_home"] = o
                            elif vl == "Away": result["xbet_away"] = o
                            elif vl == "Draw": result["xbet_draw"] = o

    return result

# ── Calculer le mouvement de cote ────────────────────────────────────────────

def calc_movement(old_val, new_val):
    """Retourne le % de changement. Négatif = cote baisse = signal bullish."""
    if not old_val or not new_val: return None
    return round((new_val - old_val) / old_val * 100, 2)

# ── Sauvegarder les cotes et détecter les mouvements ─────────────────────────

def process_fixture(pred):
    fixture_id = pred["fixture_id"]
    home       = pred["home_team_name"]
    away       = pred["away_team_name"]
    league     = pred["league_name"]
    rec        = pred.get("recommendation", "")
    match_date = pred.get("match_date", "")

    print(f"  → {home} vs {away} ({league})")

    # Récupérer les nouvelles cotes
    new_odds = get_odds_for_fixture(fixture_id)

    # Récupérer les anciennes cotes depuis odds_history
    try:
        prev = supabase.table("odds_history")\
            .select("*")\
            .eq("fixture_id", fixture_id)\
            .order("recorded_at", desc=True)\
            .limit(1)\
            .execute()
        old_odds = prev.data[0] if prev.data else {}
    except Exception:
        old_odds = {}

    now = datetime.utcnow().isoformat()

    # Mettre à jour odds_history avec toutes les cotes
    try:
        supabase.table("odds_history").upsert({
            "fixture_id":       fixture_id,
            "pinnacle_under25": new_odds["pinnacle_under25"],
            "bet365_under25":   new_odds["bet365_under25"],
            "xbet_under25":     new_odds["xbet_under25"],
            "pinnacle_home":    new_odds["pinnacle_home"],
            "pinnacle_away":    new_odds["pinnacle_away"],
            "pinnacle_draw":    new_odds["pinnacle_draw"],
            "bet365_home":      new_odds.get("bet365_home"),
            "bet365_away":      new_odds.get("bet365_away"),
            "bet365_draw":      new_odds.get("bet365_draw"),
            "xbet_home":        new_odds.get("xbet_home"),
            "xbet_away":        new_odds.get("xbet_away"),
            "xbet_draw":        new_odds.get("xbet_draw"),
            "recorded_at":      now,
        }, on_conflict="fixture_id").execute()
    except Exception as e:
        print(f"    [DB odds_history] {e}")

    # Mettre à jour les cotes dans predictions
    try:
        update_data = {}
        if new_odds["pinnacle_under25"]: update_data["pinnacle_under25"] = new_odds["pinnacle_under25"]
        if new_odds["bet365_under25"]:   update_data["bet365_under25"]   = new_odds["bet365_under25"]
        if new_odds["xbet_under25"]:     update_data["xbet_under25"]     = new_odds["xbet_under25"]
        if new_odds["pinnacle_home"]:    update_data["pinnacle_home"]    = new_odds["pinnacle_home"]
        if new_odds["pinnacle_away"]:    update_data["pinnacle_away"]    = new_odds["pinnacle_away"]
        if new_odds["pinnacle_draw"]:    update_data["pinnacle_draw"]    = new_odds["pinnacle_draw"]
        if update_data:
            supabase.table("predictions").update(update_data)\
                .eq("fixture_id", fixture_id).execute()
            supabase.table("daily_top25").update(update_data)\
                .eq("fixture_id", fixture_id).execute()
    except Exception as e:
        print(f"    [DB predictions] {e}")

    # ── Détecter les mouvements sharps ──────────────────────────────────────
    alerts = []

    # Choisir la meilleure cote Under 2.5 disponible (priorité Pinnacle > Bet365 > 1xBet)
    best_new  = new_odds["pinnacle_under25"] or new_odds["bet365_under25"] or new_odds["xbet_under25"]
    best_old  = old_odds.get("pinnacle_under25") or old_odds.get("bet365_under25") or old_odds.get("xbet_under25")
    best_bk   = "Pinnacle" if new_odds["pinnacle_under25"] else "Bet365" if new_odds["bet365_under25"] else "1xBet"

    move_u25 = calc_movement(best_old, best_new)

    if move_u25 is not None:
        if move_u25 <= SHARP_THRESHOLD:
            signal = "SHARP ⚡"
            alerts.append({
                "type":    "sharp_under",
                "market":  "Under 2.5",
                "bk":      best_bk,
                "old":     best_old,
                "new":     best_new,
                "move":    move_u25,
                "signal":  signal,
            })
            print(f"    ⚡ SHARP Under 2.5 : {best_bk} {best_old} → {best_new} ({move_u25:+.1f}%)")
        elif move_u25 <= MOVE_THRESHOLD:
            print(f"    📉 Mouvement Under 2.5 : {best_bk} {best_old} → {best_new} ({move_u25:+.1f}%)")

    # Mouvement sur 1X2 Pinnacle
    for market, old_key, new_key, label in [
        ("Victoire Dom.", "pinnacle_home", "pinnacle_home", "Dom."),
        ("Victoire Ext.", "pinnacle_away", "pinnacle_away", "Ext."),
    ]:
        move = calc_movement(old_odds.get(old_key), new_odds.get(new_key))
        if move is not None and move <= SHARP_THRESHOLD:
            alerts.append({
                "type":   "sharp_victory",
                "market": market,
                "bk":     "Pinnacle",
                "old":    old_odds.get(old_key),
                "new":    new_odds.get(new_key),
                "move":   move,
                "signal": "SHARP ⚡",
            })
            print(f"    ⚡ SHARP {market} : Pinnacle {old_odds.get(old_key)} → {new_odds.get(new_key)} ({move:+.1f}%)")

    # Envoyer notifications pour les alertes sharps
    for alert in alerts:
        send_notification(pred, alert)
        update_odds_signal(fixture_id, alert)

    return len(alerts)

# ── Mettre à jour le signal dans predictions ─────────────────────────────────

def update_odds_signal(fixture_id, alert):
    signal = "Sharp money Under" if "under" in alert["type"] else "Sharp money Victoire"
    try:
        supabase.table("predictions").update({"odds_signal": signal})\
            .eq("fixture_id", fixture_id).execute()
        supabase.table("daily_top25").update({"odds_signal": signal})\
            .eq("fixture_id", fixture_id).execute()
    except Exception:
        pass

# ── Notification push via Supabase ───────────────────────────────────────────

def send_notification(pred, alert):
    """
    Stocke la notification dans Supabase table odds_alerts.
    Le front-end (index.html) poll cette table et affiche les notifications.
    """
    home  = pred["home_team_name"]
    away  = pred["away_team_name"]
    move  = alert["move"]
    bk    = alert["bk"]
    new_v = alert["new"]
    mkt   = alert["market"]

    title = f"⚡ Sharp Money — {mkt}"
    body  = (f"{home} vs {away}\n"
             f"{bk}: {alert['old']} → {new_v} ({move:+.1f}%)\n"
             f"Argent professionnel détecté !")

    print(f"    📲 Notification : {title} — {body[:60]}")

    try:
        supabase.table("odds_alerts").insert({
            "fixture_id":    pred["fixture_id"],
            "home_team":     home,
            "away_team":     away,
            "league_name":   pred["league_name"],
            "match_date":    pred["match_date"],
            "market":        mkt,
            "bookmaker":     bk,
            "old_odds":      alert["old"],
            "new_odds":      new_v,
            "movement_pct":  move,
            "signal":        alert["signal"],
            "title":         title,
            "body":          body,
            "sent_at":       datetime.utcnow().isoformat(),
            "read":          False,
        }).execute()
    except Exception as e:
        print(f"    [DB odds_alerts] {e}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(
        f"\n=== Odds Monitor — "
        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC ===\n"
    )

    now_utc  = datetime.utcnow()
    # Analyser les matchs des prochaines 24 heures
    in_24h   = (now_utc + timedelta(hours=24)).isoformat()
    now_str  = now_utc.isoformat()

    # Récupérer les prédictions actives dans le Top 25 avec matchs à venir
    try:
        result = supabase.table("daily_top25")\
            .select("fixture_id, home_team_name, away_team_name, league_name, match_date, recommendation")\
            .gte("match_date", now_str)\
            .lte("match_date", in_24h)\
            .is_("prediction_correct", "null")\
            .execute()
        top25 = result.data or []
    except Exception as e:
        print(f"[ERR] Lecture Top 25 : {e}")
        return

    # Compléter avec les prédictions des 7 prochains jours (pas dans le top 25 nécessairement)
    try:
        in_7d = (now_utc + timedelta(days=7)).isoformat()
        result2 = supabase.table("predictions")\
            .select("fixture_id, home_team_name, away_team_name, league_name, match_date, recommendation")\
            .gte("match_date", now_str)\
            .lte("match_date", in_7d)\
            .is_("prediction_correct", "null")\
            .gte("rec_confidence", 75)\
            .execute()
        all_preds = result2.data or []
    except Exception as e:
        all_preds = []

    # Fusionner sans doublons — dédupliquer aussi daily_top25
    seen = {}
    for p in top25 + all_preds:
        fid = p["fixture_id"]
        if fid not in seen:
            seen[fid] = p
    top25 = list(seen.values())

    print(f"{len(top25)} matchs à surveiller\n")

    if not top25:
        print("Aucun match actif dans les prochaines 24h.")
        return

    total_alerts = 0
    for pred in top25:
        alerts = process_fixture(pred)
        total_alerts += alerts

    print(f"\n=== Terminé · {total_alerts} alerte(s) sharp détectée(s) ===\n")


if __name__ == "__main__":
    main()