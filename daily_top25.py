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
from datetime import datetime, date, timedelta
from supabase import create_client

SUPA_URL = os.environ["PREDICTIONS_SUPA_URL"].strip()
SUPA_KEY = os.environ["PREDICTIONS_SUPA_KEY"].strip()
supabase = create_client(SUPA_URL, SUPA_KEY)

TOP_N          = 25
MAX_PER_LEAGUE = 2    # Max 2 matchs par ligue dans le top 25
MIN_CONF_TOP   = 80   # Seuil minimum pour entrer dans le top 25

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
    "Mali", "Kenya", "Burkina Faso",
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

# Bonus par marché — recalibré sur les résultats réels (calibration mesurée)
MARKET_BONUS = {
    "UNDER 2.5": -6,   # surévalué : ~55% réel pour ~78% affiché (à réviser avec les données)
    "BTTS":       0,   # échantillon encore trop faible pour trancher
    "VICTOIRE":   4,   # marché le mieux calibré (~76% réel = affiché)
}

# Poids équilibre — priorité au marché le plus fiable (Victoire)
TARGET_DISTRIBUTION = {
    "UNDER 2.5":  6,  # réduit : marché le moins fiable
    "BTTS":       7,
    "VICTOIRE":  12,  # majorité : marché le mieux calibré
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
        result = supabase.table("predictions") \
            .select("*") \
            .gte("match_date", yesterday.isoformat()) \
            .lte("match_date", in30days.isoformat() + "T23:59:59") \
            .gte("rec_confidence", MIN_CONF_TOP) \
            .is_("prediction_correct", "null") \
            .not_.ilike("league_name", "%Friendlies%") \
            .not_.ilike("league_name", "%Tercera%") \
            .not_.ilike("league_name", "%Primera C%") \
            .not_.ilike("league_name", "%Paulista%") \
            .not_.ilike("league_name", "%Serie D%") \
            .not_.ilike("league_name", "%Tournoi%") \
            .not_.ilike("league_name", "%Tasmania%") \
            .not_.ilike("league_name", "%Baiano%") \
            .not_.ilike("league_name", "%Mineiro%") \
            .not_.ilike("league_name", "%Catarinense%") \
            .not_.ilike("league_name", "%Landesliga%") \
            .not_.ilike("league_name", "%Oberliga%") \
            .not_.ilike("league_name", "%Second League%") \
            .not_.ilike("league_name", "%USL League Two%") \
            .not_.ilike("league_name", "%NPL%") \
            .not_.ilike("league_name", "%Queensland%") \
            .not_.ilike("league_name", "%Capital Territory%") \
            .not_.ilike("league_name", "%4. liga%") \
            .not_.ilike("league_name", "%Ligi kuu%") \
            .not_.ilike("league_name", "%MLS Next Pro%") \
            .not_.ilike("league_name", "%Maurice Revello%") \
            .not_.ilike("league_name", "%Toulon%") \
            .not_.ilike("league_name", "%U20%") \
            .not_.ilike("league_name", "%U21%") \
            .not_.ilike("league_name", "%U23%") \
            .order("rec_confidence", desc=True) \
            .execute()
        data = result.data or []
        print(f"[TOP25] {len(data)} prédictions trouvées pour sélection")

        # Si aucune prédiction récente → prendre les dernières disponibles
        if not data:
            print("[TOP25] Aucune prédiction récente — chargement des dernières disponibles")
            fallback = supabase.table("predictions") \
                .select("*") \
                .gte("rec_confidence", MIN_CONF_TOP) \
                .is_("prediction_correct", "null") \
                .order("match_date", desc=False) \
                .order("rec_confidence", desc=True) \
                .limit(50) \
                .execute()
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

    # Bonus xG bas pour Under — signal réel mais secondaire (réduit)
    if "UNDER" in rec and xgt <= 1.8:
        score += 2
    elif "UNDER" in rec and xgt <= 2.0:
        score += 1

    # (retiré : le bonus L2/L3 Under reposait sur une hypothèse non vérifiée —
    #  les divisions mineures sont au contraire les moins fiables/vérifiables)

    # Malus si peu de données
    home_matches = pred.get("home_off_index") is not None
    if not home_matches:
        score -= 5

    return round(score, 1)


# Mots-clés de ligues NON disponibles sur Bet365/1xBet
EXCLUDED_LEAGUE_KW = [
    # Australie régionale
    "tasmania", "queensland", "capital territory", "nnsw", "northern territory",
    "south australia state", "western australia", "victoria state",
    "npl", "premier league nsw", "premier league victoria",
    # Brésil régional/inférieur
    "baiano", "mineiro", "catarinense", "cearense", "matogrossense", "maranhense",
    "carioca a2", "carioca b", "carioca c", "copa gaucha", "paulista serie",
    "serie d", "copa sul", "gaucho", "paranaense", "pernambucano",
    # Allemagne régionale
    "landesliga", "oberliga", "regionalliga",
    # Scandinavie inférieure
    "division 2 - norrland", "division 2 -", "ettan", "2. division",
    "3. division", "4. division",
    # Europe de l'Est inférieure
    "second league", "srpska liga", "4. liga", "ii liga - east", "ii liga - west",
    "divizie", "liga 3", "liga 4",
    # Amérique du Nord inférieure
    "usl league two", "usl super league",
    "mls next pro", "liga de expansion",
    # Amérique du Sud inférieure
    "torneo federal", "torneo promocional", "primera b metro", "primera c",
    "primera d", "ligi kuu", "tanzania",
    # Afrique/Asie ligues mineures
    "ligi kuu", "tanzania", "ethiopia",
    # Jeunes, amicaux, tournois (alignement avec le filtre du fetch Top 25)
    "friendlies", "tercera", "tournoi", "maurice revello", "toulon",
    "u20", "u21", "u23",
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


def is_women_match(pred):
    """Détecte un match féminin via les noms d'équipes.
    Beaucoup de ligues féminines ont un nom de ligue neutre (Toppserien,
    Damallsvenskan...), donc on regarde les équipes (suffixe ' W', 'Kvinner'...)."""
    def femme(name):
        n = (name or "").strip()
        nl = n.lower()
        if n.endswith(" W") or n.endswith(" (W)"):
            return True
        marks = ["women", "kvinner", "femenin", "féminin", "feminin",
                 "frauen", "ladies", "(w)", " w "]
        return any(mk in nl for mk in marks)
    return femme(pred.get("home_team_name")) or femme(pred.get("away_team_name"))


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

    # Filtrer les prédictions où la cote recommandée > 3.00
    # (bookmakers plus fiables que le moteur sur les équipes nationales)
    def get_rec_cote(pred):
        rec = (pred.get("recommendation") or "").upper()
        if "EXTÉRIEUR" in rec or "EXTERIEUR" in rec:
            return pred.get("pinnacle_away") or pred.get("bet365_away")
        elif "DOMICILE" in rec:
            return pred.get("pinnacle_home") or pred.get("bet365_home")
        elif "1X" in rec:
            return pred.get("pinnacle_home") or pred.get("bet365_home")
        elif "X2" in rec:
            return pred.get("pinnacle_away") or pred.get("bet365_away")
        return None

    filtered_by_cote = []
    for pred in predictions:
        cote = get_rec_cote(pred)
        if cote is not None and float(cote) > 3.00:
            print(f"  [COTE FILTER] {pred.get('home_team_name')} vs {pred.get('away_team_name')} — cote {cote} > 3.00 → exclu")
            continue
        filtered_by_cote.append(pred)
    predictions = filtered_by_cote
    print(f"{len(predictions)} prédictions après filtre cote > 3.00")

    # Filtre féminin (par noms d'équipes : ' W', 'Kvinner', 'Women'...)
    before_w = len(predictions)
    predictions = [p for p in predictions if not is_women_match(p)]
    if before_w - len(predictions) > 0:
        print(f"{before_w - len(predictions)} matchs féminins exclus")
    print(f"{len(predictions)} prédictions après filtre féminin")

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
        # Supprimer hier + aujourd'hui pour éviter les doublons
        from datetime import timedelta
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        supabase.table("daily_top25") \
            .delete() \
            .gte("selection_date", yesterday_str) \
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


# --- Paramètres du ticket combiné ---
TICKET_MIN_COTE  = 1.20  # cote minimale par match (exclut les cotes sans valeur réelle)
TICKET_NB_MATCHS = 3     # 1 VICTOIRE + 1 UNDER 2.5 + 1 BTTS, pris dans la Sélection du jour
TICKET_MIN_CONF  = 72    # plancher de confiance (inclut les Under, qui vivent sous le Top 25)
TICKET_MAX_CONF  = 92    # plafond (exclut les favoris écrasants à cote sans valeur)


def _cote_pari(p):
    """Cote du pari recommandé (victoire sèche, double chance, Under 2.5, BTTS)."""
    rec = (p.get("recommendation") or "").upper()
    ph = p.get("pinnacle_home"); pa = p.get("pinnacle_away"); pdr = p.get("pinnacle_draw")
    if "UNDER" in rec:
        c = p.get("pinnacle_under25")
        try:
            return float(c) if c else None
        except (TypeError, ValueError):
            return None
    if "BTTS" in rec:
        c = p.get("pinnacle_btts")
        try:
            return float(c) if c else None
        except (TypeError, ValueError):
            return None
    if "DOUBLE" in rec:
        c_team, c_draw = (pa, pdr) if "X2" in rec else (ph, pdr)
        try:
            return 1.0 / (1.0/float(c_team) + 1.0/float(c_draw))
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    elif "EXTÉRIEUR" in rec or "EXTERIEUR" in rec:
        c = pa or ph
    else:
        c = ph or pa
    try:
        return float(c) if c else None
    except (TypeError, ValueError):
        return None


def save_daily_ticket(selected=None):
    """
    Fige un ticket combiné des paris RENTABLES (Victoire domicile + Under 2.5).
    Source dédiée : prédictions du jour à confiance 72-92% (indépendant du Top 25).
    Le ticket ne change plus une fois créé — il est analysable.
    """
    today_str = date.today().isoformat()
    _today = date.today()
    # Fenêtre : aujourd'hui -> +3 jours
    allowed_dates = {(_today + timedelta(days=i)).isoformat() for i in range(4)}

    # 1) Candidats du ticket : confiance 72-92%, non joués, dans la fenêtre
    try:
        last_day = (_today + timedelta(days=3)).isoformat() + "T23:59:59"
        res = supabase.table("predictions").select("*") \
            .gte("match_date", _today.isoformat()) \
            .lte("match_date", last_day) \
            .gte("rec_confidence", TICKET_MIN_CONF) \
            .lte("rec_confidence", TICKET_MAX_CONF) \
            .is_("prediction_correct", "null") \
            .order("rec_confidence", desc=True) \
            .execute()
        candidats = res.data or []
        # Trier par score de sélection réel (favorise les marchés calibrés)
        # plutôt que par la confiance brute, qui surévalue les Under.
        candidats.sort(key=compute_selection_score, reverse=True)
        print(f"[TICKET] {len(candidats)} candidats (confiance {TICKET_MIN_CONF}-{TICKET_MAX_CONF}%)")
    except Exception as e:
        print(f"[TICKET] Erreur fetch candidats : {e}")
        return

    # 2) Fixtures déjà figés dans les tickets des 3 derniers jours -> à exclure
    used_fixtures = set()
    try:
        since = (_today - timedelta(days=3)).isoformat()
        rec_tickets = supabase.table("daily_tickets") \
            .select("matches").gte("ticket_date", since).execute()
        for t in (rec_tickets.data or []):
            for m in (t.get("matches") or []):
                fid = m.get("fixture_id")
                if fid is not None:
                    used_fixtures.add(fid)
        print(f"[TICKET] {len(used_fixtures)} matchs déjà utilisés récemment -> exclus")
    except Exception as e:
        print(f"[TICKET] Lecture tickets récents impossible : {e}")

    # 3) UN match par marché — pris dans la SÉLECTION DU JOUR (Top 25).
    #    Format : 1 VICTOIRE + 1 UNDER 2.5 + 1 BTTS, le meilleur de chaque
    #    marché dans l'ordre de la sélection (déjà triée par score).
    #    Fallback sur les candidats DB uniquement si la sélection est vide.
    pool = selected if selected else candidats
    picks = {"VICTOIRE": None, "UNDER": None, "BTTS": None}
    teams_used = []
    for p in pool:
        rec = (p.get("recommendation") or "").upper()
        if   "UNDER" in rec:    key = "UNDER"
        elif "BTTS"  in rec:    key = "BTTS"
        elif "VICTOIRE" in rec: key = "VICTOIRE"
        else: continue
        if picks[key] is not None:
            continue
        # Ligue autorisée (utile surtout pour le fallback DB)
        if not is_allowed_league(p.get("league_name", ""), p.get("is_national", False),
                                 p.get("league_tier", 3), p.get("league_country", "")):
            continue
        # Match déjà figé récemment -> on saute (pas de répétition)
        if p.get("fixture_id") in used_fixtures:
            continue
        # Hors fenêtre (aujourd'hui -> +3j) -> on saute
        if (p.get("match_date") or "")[:10] not in allowed_dates:
            continue
        # Cote du pari -> on écarte les cotes absentes ou sans valeur
        cote = _cote_pari(p)
        if cote is None or cote < TICKET_MIN_COTE:
            continue
        # Une seule fois chaque équipe (répartir le risque)
        team_reco = p.get("home_team_name")
        if team_reco in teams_used:
            continue
        teams_used.append(team_reco)
        picks[key] = (p, cote)
        if picks["VICTOIRE"] and picks["UNDER"] and picks["BTTS"]:
            break
    victoires = [v for v in (picks["VICTOIRE"], picks["UNDER"], picks["BTTS"]) if v]
    manquants = [k for k in ("VICTOIRE", "UNDER", "BTTS") if picks[k] is None]
    if manquants:
        print(f"[TICKET] Marché(s) sans match qualifiant dans la sélection : {', '.join(manquants)}")

    if len(victoires) < 2:
        print(f"[TICKET] Pas assez de matchs ({len(victoires)}) — ticket non créé")
        return

    # Construire la cote totale + le snapshot figé des matchs
    total_odds = 1.0
    matches = []
    for p, cote in victoires:
        total_odds *= cote
        matches.append({
            "fixture_id":     p["fixture_id"],
            "prediction_id":  p["id"],
            "home_team_name": p["home_team_name"],
            "away_team_name": p["away_team_name"],
            "league_name":    p["league_name"],
            "match_date":     p["match_date"],
            "recommendation": p["recommendation"],
            "rec_confidence": p["rec_confidence"],
            "cote":           round(cote, 2),
            "xg_total":       p.get("xg_total"),
            "prediction_correct": None,
        })

    try:
        # Ticket VRAIMENT figé : généré une seule fois par jour, jamais réécrit ensuite.
        # Les tentatives engine suivantes le conservent tel quel.
        existing = supabase.table("daily_tickets").select("ticket_date").eq("ticket_date", today_str).execute()
        if existing.data:
            print(f"[TICKET] Déjà figé pour {today_str} — conservé tel quel (pas de régénération)")
        elif not matches:
            print(f"[TICKET] Aucun match qualifiant pour {today_str} — ticket non créé (réessai au prochain run)")
        else:
            supabase.table("daily_tickets").insert({
                "ticket_date":   today_str,
                "matches":       matches,
                "total_odds":    round(total_odds, 2),
                "num_matches":   len(matches),
                "status":        "pending",
                "won_count":     0,
                "lost_count":    0,
                "pending_count": len(matches),
                "created_at":    datetime.utcnow().isoformat(),
            }).execute()
            print(f"[TICKET] Ticket figé du {today_str} : {len(matches)} matchs · cote {round(total_odds,2)}")
    except Exception as e:
        print(f"  [TICKET ERR] {e}")


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

    # Figer le ticket du jour (7 matchs VICTOIRE)
    save_daily_ticket(selected)


if __name__ == "__main__":
    main()