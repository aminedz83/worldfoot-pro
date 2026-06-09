"""
daily_top25.py
==============
Sélectionne automatiquement les 25 meilleurs matchs du jour
parmi toutes les prédictions Under 2.5 · BTTS · Victoire

Critères de sélection :
  1. Score de confiance le plus élevé
  2. Signal de cotes favorable (Sharp money bonus)
  3. Risque minimum
  4. Diversité — pas plus de 3 matchs par ligue
  5. Équilibre Under / BTTS / Victoire

Cron GitHub Actions : 05h30 UTC (après predictions_master.py à 04h00)
"""

import os
from datetime import datetime, date
from supabase import create_client

SUPA_URL = os.environ["PREDICTIONS_SUPA_URL"].strip()
SUPA_KEY = os.environ["PREDICTIONS_SUPA_KEY"].strip()
supabase = create_client(SUPA_URL, SUPA_KEY)

TOP_N          = 25
MAX_PER_LEAGUE = 2    # Max 2 matchs par ligue dans le top 25
MIN_CONF_TOP   = 70   # Seuil minimum pour entrer dans le top 25

# ── Pays dont les ligues sont disponibles sur Bet365/1xBet ──────────────────
ALLOWED_COUNTRIES = {
    # Europe
    "England", "Germany", "Spain", "Italy", "France", "Netherlands",
    "Portugal", "Belgium", "Turkey", "Scotland", "Greece", "Russia",
    "Ukraine", "Poland", "Czech Republic", "Switzerland", "Austria",
    "Denmark", "Sweden", "Norway", "Croatia", "Serbia", "Romania",
    "Hungary", "Slovakia", "Israel", "Finland", "Bulgaria", "Slovenia",
    # Amériques
    "USA", "Mexico", "Brazil", "Argentina", "Colombia", "Chile",
    "Uruguay", "Peru", "Ecuador", "Venezuela",
    # Asie
    "Japan", "South Korea", "China", "Saudi Arabia", "UAE",
    "Qatar", "Iran", "Australia", "India",
    # Afrique
    "Egypt", "Morocco", "South Africa", "Nigeria", "Tunisia",
    # Compétitions internationales
    "World", "Europe", "Africa", "Asia", "South America", "North America",
}

# Bonus par type de signal cotes
ODDS_SIGNAL_BONUS = {
    "Sharp money Under":   12,
    "Mouvement Under":      6,
    "Consensus bookmakers": 4,
    "Neutre":               0,
    "Mouvement contraire": -15,
}

# Bonus par marché
MARKET_BONUS = {
    "UNDER 2.5": 3,   # Plus fiable statistiquement
    "BTTS":      1,
    "VICTOIRE":  0,   # Seuil plus strict
}

# Poids équilibre — on veut une bonne répartition
TARGET_DISTRIBUTION = {
    "UNDER 2.5": 10,  # ~10 Under sur 25
    "BTTS":       8,  # ~8 BTTS sur 25
    "VICTOIRE":   7,  # ~7 Victoires sur 25
}


def get_today_predictions():
    """Récupère toutes les prédictions publiées pour les 3 prochains jours."""
    from datetime import timedelta
    today     = date.today()
    in3days   = today + timedelta(days=3)
    yesterday = today - timedelta(days=1)

    try:
        # Cherche les prédictions des matchs à venir (aujourd'hui + 3 jours)
        # Récupérer prédictions sur 30 jours à venir
        in30days = today + timedelta(days=30)
        result = supabase.table("predictions")            .select("*")            .gte("match_date", yesterday.isoformat())            .lte("match_date", in30days.isoformat() + "T23:59:59")            .gte("rec_confidence", MIN_CONF_TOP)            .is_("prediction_correct", "null")            .not_.ilike("league_name", "%Friendlies Clubs%")            .not_.ilike("league_name", "%Tercera%")            .not_.ilike("league_name", "%Primera C%")            .not_.ilike("league_name", "%Paulista%")            .not_.ilike("league_name", "%Serie D%")            .not_.ilike("league_name", "%Tournoi%")            .order("rec_confidence", desc=True)            .execute()
        data = result.data or []
        print(f"[TOP25] {len(data)} prédictions trouvées pour sélection")

        # Si aucune prédiction récente → prendre les dernières disponibles
        if not data:
            print("[TOP25] Aucune prédiction récente — chargement des dernières disponibles")
            fallback = supabase.table("predictions")                .select("*")                .gte("rec_confidence", MIN_CONF_TOP)                .is_("prediction_correct", "null")                .order("match_date", desc=False)                .order("rec_confidence", desc=True)                .limit(50)                .execute()
            data = fallback.data or []
            print(f"[TOP25] {len(data)} prédictions fallback trouvées")

        return data
    except Exception as e:
        print(f"[ERREUR] Récupération prédictions : {e}")
        return []


def compute_selection_score(pred):
    """
    Calcule un score de sélection composite pour chaque prédiction.
    Ce score détermine le classement final dans le Top 25.
    """
    base_conf  = pred.get("rec_confidence", 0)
    odds_sig   = pred.get("odds_signal", "Neutre")
    rec        = pred.get("recommendation", "")
    risk       = pred.get("risk_level", "Moyen")
    tier       = pred.get("league_tier", 1)
    xgt        = pred.get("xg_total", 2.5) or 2.5
    h2h_count  = pred.get("h2h_count", 0) or 0

    score = base_conf

    # Bonus signal cotes
    score += ODDS_SIGNAL_BONUS.get(odds_sig, 0)

    # Bonus marché
    for market, bonus in MARKET_BONUS.items():
        if market in rec:
            score += bonus
            break

    # Bonus risque faible
    if risk == "Faible":
        score += 4

    # Bonus H2H solide
    if h2h_count >= 6:
        score += 3
    elif h2h_count >= 4:
        score += 1

    # Bonus xG très clair pour Under
    if "UNDER" in rec and xgt <= 1.8:
        score += 5
    elif "UNDER" in rec and xgt <= 2.0:
        score += 3

    # Bonus L2/L3 pour Under (signaux plus nets)
    if "UNDER" in rec and tier >= 2:
        score += 2

    # Malus si peu de données
    home_matches = pred.get("home_off_index") is not None
    if not home_matches:
        score -= 5

    return round(score, 1)


# Mots-clés de ligues NON disponibles sur Bet365/1xBet
EXCLUDED_LEAGUE_KW = [
    "tasmania", "queensland", "capital territory", "nnsw", "northern territory",
    "baiano", "mineiro", "catarinense", "cearense", "matogrossense", "maranhense",
    "carioca a2", "copa gaucha", "paulista serie",
    "landesliga", "oberliga", "regionalliga",
    "division 2 - norrland", "division 2 -", "ettan",
    "second league", "srpska liga",
    "canadian premier", "usl league two", "usl super league",
    "npl", "premier league nsw", "premier league victoria",
    "torneo federal", "torneo promocional", "primera b metro", "primera c",
    "serie d", "copa sul",
]

def is_allowed_league(league_name, is_national, tier, country=""):
    """
    Filtre basé sur liste noire — exclut les ligues non disponibles sur Bet365/1xBet.
    Fonctionne même sans active_leagues.
    """
    # Compétitions nationales toujours autorisées (CdM, Euro, Copa America...)
    if is_national:
        return True
    # Vérifier liste noire par nom
    ln = (league_name or "").lower()
    for kw in EXCLUDED_LEAGUE_KW:
        if kw in ln:
            return False
    # Tier 1 et 2 uniquement
    if (tier or 3) >= 3:
        return False
    return True


def select_top25(predictions):
    """
    Algorithme de sélection des 25 meilleurs matchs.

    Étapes :
    1. Calculer le score composite de chaque prédiction
    2. Trier par score décroissant
    3. Appliquer la règle max 3 par ligue
    4. Équilibrer la distribution Under / BTTS / Victoire
    5. Retourner les 25 meilleurs
    """

    if not predictions:
        return []

    # Récupérer les pays depuis active_leagues
    try:
        al = supabase.table("active_leagues").select("league_id,country").execute()
        country_map = {row["league_id"]: row.get("country","") for row in (al.data or [])}
    except Exception:
        country_map = {}

    # Filtrer uniquement les ligues disponibles sur Bet365/1xBet
    predictions = [
        p for p in predictions
        if is_allowed_league(
            p.get("league_name", ""),
            p.get("is_national", False),
            p.get("league_tier", 3),
            country_map.get(p.get("league_id"), "")
        )
    ]
    print(f"{len(predictions)} prédictions après filtre ligues disponibles")

    if not predictions:
        print("⚠️ Aucune prédiction dans les ligues autorisées")
        return []

    # Étape 1 : Calculer les scores
    for pred in predictions:
        pred["_selection_score"] = compute_selection_score(pred)

    # Étape 2 : Trier par score décroissant
    predictions.sort(key=lambda x: x["_selection_score"], reverse=True)

    # Étape 3 & 4 : Sélection avec contraintes
    selected         = []
    league_count     = {}  # {league_id: count}
    market_count     = {"UNDER 2.5": 0, "BTTS": 0, "VICTOIRE": 0}

    # Passe 1 : sélectionner les meilleurs en respectant max/ligue
    for pred in predictions:
        if len(selected) >= TOP_N:
            break

        league_id = pred.get("league_id")
        rec       = pred.get("recommendation", "")

        # Règle max 3 par ligue
        if league_count.get(league_id, 0) >= MAX_PER_LEAGUE:
            continue

        # Identifier le marché
        market = None
        for m in ["UNDER 2.5", "BTTS", "VICTOIRE"]:
            if m in rec:
                market = m
                break
        if not market:
            market = "VICTOIRE"

        # Éviter de surcharger un marché
        target = TARGET_DISTRIBUTION.get(market, 7)
        if market_count.get(market, 0) >= target + 2:
            continue

        selected.append(pred)
        league_count[league_id] = league_count.get(league_id, 0) + 1
        market_count[market]    = market_count.get(market, 0) + 1

    # Passe 2 : compléter si moins de 25 (assouplir les contraintes)
    if len(selected) < TOP_N:
        selected_ids = {p["id"] for p in selected}
        for pred in predictions:
            if len(selected) >= TOP_N:
                break
            if pred["id"] not in selected_ids:
                selected.append(pred)
                selected_ids.add(pred["id"])

    # Trier le résultat final par score
    selected.sort(key=lambda x: x["_selection_score"], reverse=True)

    return selected[:TOP_N]


def save_top25(selected):
    """Sauvegarde le top 25 dans la table daily_top25 avec rang."""
    today_str = date.today().isoformat()
    print(f"[TOP25] Sauvegarde sélection du {today_str}")

    try:
        # Supprimer l'ancienne sélection du jour
        supabase.table("daily_top25")\
            .delete()\
            .eq("selection_date", today_str)\
            .execute()
    except Exception:
        pass

    now = datetime.utcnow().isoformat()

    for rank, pred in enumerate(selected, 1):
        try:
            supabase.table("daily_top25").insert({
                "rank":             rank,
                "selection_date":   today_str,
                "fixture_id":       pred["fixture_id"],
                "prediction_id":    pred["id"],
                "league_name":      pred["league_name"],
                "league_tier":      pred["league_tier"],
                "match_date":       pred["match_date"],
                "home_team_name":   pred["home_team_name"],
                "away_team_name":   pred["away_team_name"],
                "recommendation":   pred["recommendation"],
                "rec_confidence":   pred["rec_confidence"],
                "selection_score":  pred["_selection_score"],
                "risk_level":       pred["risk_level"],
                "odds_signal":      pred["odds_signal"],
                "pinnacle_under25": pred.get("pinnacle_under25"),
                "pinnacle_home":    pred.get("pinnacle_home"),
                "pinnacle_away":    pred.get("pinnacle_away"),
                "pinnacle_draw":    pred.get("pinnacle_draw"),
                "xg_total":         pred.get("xg_total"),
                "context_text":     pred.get("context_text",""),
                "created_at":       now,
                "prediction_correct": None,
            }).execute()
        except Exception as e:
            print(f"  [DB ERR] Rang {rank}: {e}")


def print_top25(selected):
    """Affiche le top 25 dans les logs GitHub Actions."""
    print(f"\n{'═'*65}")
    print(f"  TOP 25 SÉLECTION DU JOUR — {date.today().isoformat()}")
    print(f"{'═'*65}\n")

    market_icons = {
        "UNDER 2.5": "⬇️ ",
        "BTTS":      "⚽",
        "VICTOIRE":  "🏆",
        "DOUBLE":    "🔄",
    }

    for pred in selected:
        rec  = pred["recommendation"]
        icon = "🎯"
        for k, v in market_icons.items():
            if k in rec: icon = v; break

        conf  = pred["rec_confidence"]
        score = pred["_selection_score"]
        risk  = "🟢" if pred["risk_level"] == "Faible" else "🟡"
        odds  = "📈" if pred.get("odds_signal") in (
            "Sharp money Under","Mouvement Under") else ""

        rank = selected.index(pred) + 1
        print(
            f"  #{rank:02d} {icon} {risk} {odds} "
            f"{pred['home_team_name']} vs {pred['away_team_name']}\n"
            f"      {pred['league_name']} · {rec} · "
            f"Conf {conf}% · Score {score}\n"
        )

    # Résumé distribution
    dist = {}
    for p in selected:
        rec = p["recommendation"]
        for m in ["UNDER 2.5","BTTS","VICTOIRE","DOUBLE"]:
            if m in rec:
                dist[m] = dist.get(m,0)+1
                break

    print(f"{'─'*65}")
    print(f"  Distribution : ", end="")
    for m,n in sorted(dist.items(), key=lambda x:-x[1]):
        print(f"{m}: {n}  ", end="")
    print(f"\n  Total sélectionné : {len(selected)}/25")
    print(f"{'═'*65}\n")


def main():
    print(f"\n=== Daily Top 25 — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC ===\n")

    # Récupérer les prédictions du jour
    predictions = get_today_predictions()
    print(f"{len(predictions)} prédictions disponibles pour sélection")

    if not predictions:
        print("Aucune prédiction disponible — Top 25 vide aujourd'hui.")
        return

    # Sélectionner les 25 meilleurs
    selected = select_top25(predictions)
    print(f"{len(selected)} matchs sélectionnés dans le Top 25")

    # Afficher dans les logs
    print_top25(selected)

    # Sauvegarder dans Supabase
    save_top25(selected)
    print(f"Top 25 sauvegardé dans Supabase · table daily_top25")


if __name__ == "__main__":
    main()