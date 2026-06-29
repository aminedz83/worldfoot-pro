"""
predictions_master.py — VERSION FINALE
=======================================
Auto-découverte complète · Zéro liste codée en dur
Gestion intelligente du quota API · Priorité aux meilleurs signaux
Marchés : Under 2.5 · BTTS · Victoire
Ligues   : TOUTES les compétitions actives du monde détectées automatiquement

Quota API estimé par match : ~7 appels
Plan PRO  (7 500/j)  → ~1 000 matchs analysables par nuit
Plan Mega (150 000/j) → ~20 000 matchs analysables par nuit

GitHub Actions : cron 04h00 UTC quotidien
Secrets : API_FOOTBALL_KEY · PREDICTIONS_SUPA_URL · PREDICTIONS_SUPA_KEY
pip install requests supabase
"""

import os, hashlib, requests, time
from datetime import datetime, timedelta
from supabase import create_client

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

API_KEY  = os.environ["API_FOOTBALL_KEY"].strip()
SUPA_URL = os.environ["PREDICTIONS_SUPA_URL"].strip()
SUPA_KEY = os.environ["PREDICTIONS_SUPA_KEY"].strip()

API_BASE   = "https://v3.football.api-sports.io"
HEADERS    = {"x-apisports-key": API_KEY}
DAYS_AHEAD = 7
MIN_CONF   = 72

# Quota safety — on s'arrête à 90% du quota pour ne jamais le dépasser
QUOTA_SAFETY_PCT = 0.98  # Utiliser 98% du quota disponible

# Requêtes utilisées aujourd'hui (mis à jour en temps réel depuis les headers)
quota_used      = 0
quota_limit_day = 7500  # sera mis à jour depuis les headers API

supabase = create_client(SUPA_URL, SUPA_KEY)

# ── Mots-clés exclusion ───────────────────────────────────────────────────────
EXCLUDE_KW = [
    "u17","u18","u19","u20","u21","u23","youth","reserve",
    "women","feminin","femenino","ladies","féminin","mujer","dames"," w ","wsl","nwsl","frauen","beach","futsal","indoor",
    "friendly","amical","pre-season","preseason","test","exhibition",
    "friendlies clubs","friendlies",  # Pas de valeur prédictive
]

# ── LISTE BLANCHE DES LIGUES (integree) ───────────────────────────────────────
WHITELIST = {
    # ─────────────── EUROPE ───────────────
    39: "Premier League (England)", 40: "Championship (England)", 41: "League One (England)",
    179: "Premiership (Scotland)", 180: "Championship (Scotland)", 183: "League One (Scotland)",
    110: "Premier League (Wales)", 111: "FAW Championship (Wales)",
    357: "Premier Division (Ireland)", 358: "First Division (Ireland)",
    408: "Premiership (N. Ireland)", 407: "Championship (N. Ireland)",
    61: "Ligue 1 (France)", 62: "Ligue 2 (France)", 63: "National 1 (France)",
    78: "Bundesliga (Germany)", 79: "2. Bundesliga (Germany)", 80: "3. Liga (Germany)",
    135: "Serie A (Italy)", 136: "Serie B (Italy)",
    138: "Serie C/A (Italy)", 942: "Serie C/B (Italy)", 943: "Serie C/C (Italy)",
    140: "La Liga (Spain)", 141: "Segunda (Spain)",
    94: "Primeira Liga (Portugal)", 95: "Segunda Liga (Portugal)", 865: "Liga 3 (Portugal)",
    88: "Eredivisie (Netherlands)", 89: "Eerste Divisie (Netherlands)",
    144: "Jupiler Pro League (Belgium)", 145: "Challenger Pro League (Belgium)",
    207: "Super League (Switzerland)", 208: "Challenge League (Switzerland)",
    218: "Bundesliga (Austria)", 219: "2. Liga (Austria)",
    119: "Superliga (Denmark)", 120: "1. Division (Denmark)",
    103: "Eliteserien (Norway)", 104: "1. Division (Norway)",
    113: "Allsvenskan (Sweden)", 114: "Superettan (Sweden)",
    244: "Veikkausliiga (Finland)", 1087: "Ykkosliiga (Finland)", 245: "Ykkonen (Finland)",
    164: "Urvalsdeild (Iceland)", 165: "1. Deild (Iceland)",
    106: "Ekstraklasa (Poland)", 107: "I Liga (Poland)", 109: "II Liga (Poland)",
    345: "Czech Liga (Czechia)", 346: "FNL (Czechia)",
    332: "Super Liga (Slovakia)", 506: "2. liga (Slovakia)",
    271: "NB I (Hungary)", 272: "NB II (Hungary)",
    283: "Liga I (Romania)", 284: "Liga II (Romania)",
    172: "First League (Bulgaria)", 173: "Second League (Bulgaria)",
    286: "Super Liga (Serbia)", 287: "Prva Liga (Serbia)",
    210: "HNL (Croatia)", 211: "First NL (Croatia)",
    373: "1. SNL (Slovenia)", 374: "2. SNL (Slovenia)",
    315: "Premijer Liga (Bosnia)", 316: "1st League FBiH (Bosnia)", 317: "1st League RS (Bosnia)",
    197: "Super League 1 (Greece)", 494: "Super League 2 (Greece)",
    203: "Super Lig (Turkey)", 204: "1. Lig (Turkey)", 205: "2. Lig (Turkey)",
    235: "Premier League (Russia)", 236: "First League (Russia)",
    333: "Premier League (Ukraine)", 334: "Persha Liga (Ukraine)",
    116: "Premier League (Belarus)", 117: "1. Division (Belarus)",
    318: "1. Division (Cyprus)", 319: "2. Division (Cyprus)",
    383: "Ligat Ha'al (Israel)", 382: "Liga Leumit (Israel)",
    393: "Premier League (Malta)", 392: "Challenge League (Malta)",
    261: "National Division (Luxembourg)",
    367: "Meistaradeildin (Faroe)", 366: "1. Deild (Faroe)",
    329: "Meistriliiga (Estonia)", 328: "Esiliiga A (Estonia)",
    365: "Virsliga (Latvia)", 364: "1. Liga (Latvia)",
    362: "A Lyga (Lithuania)", 361: "1 Lyga (Lithuania)",
    327: "Erovnuli Liga (Georgia)", 326: "Erovnuli Liga 2 (Georgia)",
    342: "Premier League (Armenia)", 343: "First League (Armenia)",
    419: "Premyer Liqa (Azerbaijan)", 418: "Birinci Dasta (Azerbaijan)",
    389: "Premier League (Kazakhstan)", 388: "1. Division (Kazakhstan)",
    394: "Super Liga (Moldova)", 395: "Liga 1 (Moldova)",
    310: "Superliga (Albania)", 311: "1st Division (Albania)",
    371: "First League (Macedonia)", 372: "Second League (Macedonia)",
    355: "First League (Montenegro)", 356: "Second League (Montenegro)",

    # ─────────────── AMERIQUES ───────────────
    71: "Serie A (Brazil)", 72: "Serie B (Brazil)", 75: "Serie C (Brazil)",
    128: "Liga Profesional (Argentina)", 129: "Primera Nacional (Argentina)",
    265: "Primera Division (Chile)", 266: "Primera B (Chile)",
    239: "Primera A (Colombia)", 240: "Primera B (Colombia)",
    268: "Primera Apertura (Uruguay)", 270: "Primera Clausura (Uruguay)", 269: "Segunda (Uruguay)",
    250: "Profesional Apertura (Paraguay)", 252: "Profesional Clausura (Paraguay)", 251: "Intermedia (Paraguay)",
    281: "Primera Division (Peru)", 282: "Segunda Division (Peru)",
    242: "Liga Pro (Ecuador)", 243: "Liga Pro Serie B (Ecuador)",
    344: "Primera Division (Bolivia)", 710: "Nacional B (Bolivia)",
    299: "Primera Division (Venezuela)", 300: "Segunda Division (Venezuela)",
    262: "Liga MX (Mexico)", 263: "Liga de Expansion (Mexico)",
    253: "MLS (USA)", 255: "USL Championship (USA)", 489: "USL League One (USA)",
    479: "Canadian Premier League (Canada)",
    162: "Primera Division (Costa Rica)", 163: "Liga de Ascenso (Costa Rica)",
    339: "Liga Nacional (Guatemala)", 338: "Primera Division (Guatemala)",
    234: "Liga Nacional (Honduras)",
    304: "Liga Panamena (Panama)",
    370: "Primera Division (El Salvador)",

    # ─────────────── ASIE ───────────────
    98: "J1 League (Japan)", 99: "J2 League (Japan)", 100: "J3 League (Japan)",
    292: "K League 1 (South Korea)", 293: "K League 2 (South Korea)",
    169: "Super League (China)", 170: "League One (China)",
    307: "Pro League (Saudi Arabia)", 308: "Division 1 (Saudi Arabia)",
    301: "Pro League (UAE)", 303: "Division 1 (UAE)",
    305: "Stars League (Qatar)", 306: "Second Division (Qatar)",
    290: "Persian Gulf Pro League (Iran)", 291: "Azadegan League (Iran)",
    542: "Iraqi League (Iraq)",
    323: "Indian Super League (India)", 324: "I-League (India)",
    274: "Liga 1 (Indonesia)", 275: "Liga 2 (Indonesia)",
    296: "Thai League 1 (Thailand)", 297: "Thai League 2 (Thailand)",
    340: "V.League 1 (Vietnam)", 637: "V.League 2 (Vietnam)",
    278: "Super League (Malaysia)", 279: "Premier League (Malaysia)",
    369: "Super League (Uzbekistan)", 1075: "Pro League A (Uzbekistan)",

    # ─────────────── AFRIQUE ───────────────
    # NB : pour la plupart de ces pays l'API ne fournit qu'UNE division (D1).
    200: "Botola Pro (Morocco)", 201: "Botola 2 (Morocco)",
    202: "Ligue 1 (Tunisia)", 828: "Ligue 2 (Tunisia)",
    186: "Ligue 1 (Algeria)", 187: "Ligue 2 (Algeria)",
    233: "Premier League (Egypt)", 887: "Second League (Egypt)",
    288: "Premier Soccer League (South Africa)", 289: "1st Division (South Africa)",
    399: "NPFL (Nigeria)",
    598: "Premiere Division (Mali)",           # D1 seule
    423: "Ligue 1 (Burkina Faso)",             # D1 seule
    403: "Ligue 1 (Senegal)",                  # D1 seule
    386: "Ligue 1 (Ivory Coast)",              # D1 seule
    570: "Premier League (Ghana)", 1196: "Division One League (Ghana)",
    411: "Elite One (Cameroon)", 813: "Elite Two (Cameroon)",
    424: "Ligue 1 (DR Congo)",                 # D1 seule
    397: "Girabola (Angola)",                  # D1 seule
    567: "Ligi kuu Bara (Tanzania)",           # D1 seule
    400: "Super League (Zambia)",              # D1 seule

    # ─────────────── OCEANIE ───────────────
    188: "A-League (Australia)",
    955: "National League (New Zealand)",

    # ─────── COUPES INTERNATIONALES DE CLUBS (IDs verifies) ───────
    # Elimination directe mais clubs = stats fiables. Risque modere.
    2:   "UEFA Champions League",
    3:   "UEFA Europa League",
    848: "UEFA Europa Conference League",
    531: "UEFA Super Cup",
    13:  "CONMEBOL Libertadores",
    11:  "CONMEBOL Sudamericana",
    541: "CONMEBOL Recopa",
    12:  "CAF Champions League",
    20:  "CAF Confederation Cup",
    533: "CAF Super Cup",
    16:  "CONCACAF Champions League",
    772: "Leagues Cup",
    1028: "CONCACAF Central American Cup",
    17:  "AFC Champions League Elite",
    18:  "AFC Champions League Two",
    1132: "AFC Challenge League",
    27:  "OFC Champions League",
    15:  "FIFA Club World Cup",
    1168: "FIFA Intercontinental Cup",

    # ─────── SELECTIONS NATIONALES (HAUTE VARIANCE — voir note) ───────
    # ATTENTION : ce sont les matchs les plus imprevisibles. A surveiller :
    # si le taux chute, commente simplement ce bloc.
    4:   "Euro Championship",
    960: "Euro - Qualification",
    5:   "UEFA Nations League",
    32:  "World Cup - Qual Europe",
    6:   "Africa Cup of Nations (CAN)",
    36:  "CAN - Qualification",
    19:  "African Nations Championship (CHAN)",
    29:  "World Cup - Qual Africa",
    22:  "CONCACAF Gold Cup",
    536: "CONCACAF Nations League",
    804: "Caribbean Cup",
    31:  "World Cup - Qual CONCACAF",
    9:   "Copa America",
    34:  "World Cup - Qual South America",
    7:   "Asian Cup",
    30:  "World Cup - Qual Asia",
    860: "Arab Cup",
    806: "OFC Nations Cup",
    33:  "World Cup - Qual Oceania",
    37:  "World Cup - Qual Intercontinental Play-offs",
    480: "Olympics Men",
    913: "Finalissima (CONMEBOL-UEFA)",
    916: "Kirin Cup",
    1038: "King's Cup",
    766: "China Cup",
    914: "Tournoi Maurice Revello",
    # NB : la Coupe du Monde (id 1) est deja geree separement par le moteur,
    #      on ne la remet pas ici pour eviter un double traitement.
}

# Set d'IDs pret a l'emploi pour le moteur
WHITELIST_IDS = set(WHITELIST.keys())


# ── Mots-clés → équipes nationales ────────────────────────────────────────────
NATIONAL_KW = [
    "world cup","coupe du monde","copa mundial","euro","european championship",
    "copa america","africa cup","afcon","can","asian cup","gold cup",
    "nations league","olympic","qualifying","qualification","world cup 2026",
]

WORLD_COUNTRIES = {
    "World","Europe","Africa","Asia","South America","North America","Oceania",
}

# ── Classement FIFA — chargé depuis l'API au démarrage ───────────────────────
FIFA = {}  # Sera rempli par load_fifa_rankings()

def load_fifa_rankings():
    """
    Charge les vrais classements FIFA depuis API-Football.
    Endpoint : /teams/rankings?type=world
    Fallback sur valeurs statiques si l'API échoue.
    """
    global FIFA
    data = api("teams/ranking", {"type": "world"}) or []
    if data and len(data) > 5:
        for item in data:
            name = item.get("team", {}).get("name", "")
            rank = item.get("rank", 99)
            if name:
                FIFA[name] = rank
        print(f"  [FIFA] {len(FIFA)} classements chargés depuis l'API")
        return True
    else:
        # Fallback statique
        print("  [FIFA] Fallback sur classements statiques")
        FIFA = {
            "Argentina":1,"France":2,"England":3,"Spain":4,"Brazil":5,
            "Portugal":6,"Belgium":7,"Netherlands":8,"Germany":9,"Italy":10,
            "Croatia":11,"Colombia":12,"Morocco":13,"Uruguay":15,
            "USA":16,"Mexico":17,"Senegal":18,"Japan":19,"Switzerland":19,
            "Denmark":21,"Austria":22,"Turkey":25,"South Korea":23,
            "Ecuador":30,"Algeria":35,"Australia":24,"Poland":26,
            "Ukraine":28,"Sweden":27,"Hungary":29,"Czech Republic":32,
            "Romania":34,"Serbia":31,"Norway":36,"Slovakia":38,
            "Qatar":37,"Canada":40,"South Africa":64,"Bosnia & Herzegovina":60,
            "Paraguay":53,"New Zealand":98,"Tunisia":48,"Cape Verde Islands":70,
            "Egypt":43,"Saudi Arabia":56,"Iran":21,"Jordan":85,
            "Ivory Coast":42,"Ghana":66,"Curaçao":85,"Scotland":39,
            "Haiti":90,"Türkiye":25,"Tunisia":48,
        }
        return False

# ── Coordonnées par pays ──────────────────────────────────────────────────────
COUNTRY_COORDS = {
    "England":(51.509,-0.118),"Germany":(52.520,13.405),
    "France":(48.856,2.352),"Spain":(40.417,-3.704),
    "Italy":(41.903,12.496),"Netherlands":(52.368,4.904),
    "Portugal":(38.722,-9.139),"Belgium":(50.850,4.352),
    "Turkey":(39.933,32.860),"Brazil":(-15.78,-47.929),
    "Argentina":(-34.604,-58.382),"USA":(38.907,-77.037),
    "Mexico":(19.433,-99.133),"Algeria":(36.752,3.042),
    "Morocco":(33.990,-6.850),"Japan":(35.689,139.692),
    "South Korea":(37.566,126.978),"Australia":(-33.868,151.209),
    "Saudi Arabia":(24.688,46.722),"Egypt":(30.033,31.233),
    "World":(48.856,2.352),"Europe":(48.856,2.352),
}

CITY_COORDS = {
    "New York":(40.713,-74.006),"Los Angeles":(34.052,-118.244),
    "Dallas":(32.777,-96.797),"Miami":(25.762,-80.192),
    "Toronto":(43.653,-79.383),"Vancouver":(49.283,-123.121),
    "Mexico City":(19.433,-99.133),"Guadalajara":(20.660,-103.350),
    "Paris":(48.856,2.352),"London":(51.509,-0.118),
    "Madrid":(40.417,-3.704),"Berlin":(52.520,13.405),
    "Rome":(41.903,12.496),"Amsterdam":(52.368,4.904),
    "Lisbon":(38.722,-9.139),"Brussels":(50.850,4.352),
}

# ── Score de priorité par pays — pour trier les ligues ────────────────────────
# Plus le score est élevé, plus la ligue est analysée en priorité
COUNTRY_PRIORITY = {
    "England":100,"Germany":98,"Spain":97,"Italy":96,"France":95,
    "Netherlands":90,"Portugal":88,"Belgium":87,"Turkey":85,
    "Brazil":83,"Argentina":82,"USA":80,"Mexico":78,
    "Scotland":75,"Greece":73,"Russia":72,"Ukraine":71,
    "Poland":70,"Czech Republic":69,"Switzerland":68,
    "Croatia":67,"Serbia":66,"Romania":65,"Norway":64,
    "Sweden":63,"Denmark":62,"Austria":61,
    "Morocco":58,"Algeria":57,"Egypt":56,"South Africa":55,
    "Saudi Arabia":54,"Japan":53,"South Korea":52,"Australia":50,
    "World":99,"Europe":97,"Africa":60,"Asia":55,
    "South America":82,"North America":75,
}

# ══════════════════════════════════════════════════════════════════════════════
# GESTION DU QUOTA API EN TEMPS RÉEL
# ══════════════════════════════════════════════════════════════════════════════

def api(endpoint, params={}):
    """
    Appel API-Football avec :
    - Gestion du quota en temps réel depuis les headers
    - Arrêt automatique avant dépassement
    - Retry intelligent si rate limit minute atteint
    """
    global quota_used, quota_limit_day

    # Vérifier le quota avant d'appeler
    quota_max = int(quota_limit_day * QUOTA_SAFETY_PCT)
    if quota_used >= quota_max:
        return None  # Quota atteint — arrêt silencieux

    try:
        r = requests.get(
            f"{API_BASE}/{endpoint}",
            headers=HEADERS, params=params, timeout=15
        )

        # Petite pause régulière pour lisser le débit (plan PRO ~450 req/min)
        time.sleep(0.12)

        # Mettre à jour le quota depuis les headers
        limit  = r.headers.get("x-ratelimit-requests-limit")
        remain = r.headers.get("x-ratelimit-requests-remaining")
        if limit:  quota_limit_day = int(limit)
        if remain: quota_used = quota_limit_day - int(remain)

        # Rate limit par minute atteint → attendre (réduit à 8s, suffisant)
        if r.status_code == 429:
            print("  [RATELIMIT] Pause 8 secondes...")
            time.sleep(8)
            return api(endpoint, params)

        if r.status_code != 200: return None
        d = r.json()
        return None if d.get("errors") else d.get("response", [])

    except Exception as e:
        print(f"  [ERR] {endpoint}: {e}")
        return None


def quota_remaining():
    return quota_limit_day - quota_used

def quota_pct_used():
    return quota_used / quota_limit_day * 100 if quota_limit_day else 0

# ══════════════════════════════════════════════════════════════════════════════
# AUTO-DÉCOUVERTE DES COMPÉTITIONS — TOTALEMENT AUTOMATIQUE
# ══════════════════════════════════════════════════════════════════════════════

def detect_national(name, country):
    nl = name.lower()
    if country in WORLD_COUNTRIES: return True
    for kw in NATIONAL_KW:
        if kw in nl: return True
    return False

def detect_tier(name):
    nl = name.lower()
    l3 = ["3","third","tercera","serie c","3. liga","league one","national",
          "division 3","primera rfef","regionalliga","troisieme","troisième"]
    l2 = ["2","second","segunda","serie b","championship","ligue 2",
          "eerste","challenger","division 2","2. bundesliga","b league",
          "segunda divisao","segunda division"]
    for kw in l3:
        if kw in nl: return 3
    for kw in l2:
        if kw in nl: return 2
    return 1

def league_priority_score(name, country, tier, is_national, fixtures_count):
    """
    Score de priorité pour trier les ligues.
    Ligues avec les meilleurs signaux historiques analysées en premier.
    """
    score = COUNTRY_PRIORITY.get(country, 40)

    # Pénalité par tier (L1 > L2 > L3 en termes de données disponibles)
    score -= (tier - 1) * 5

    # Bonus compétitions internationales
    if is_national: score += 10

    # Bonus si beaucoup de matchs à venir (plus de chances de trouver des signaux)
    if fixtures_count >= 8: score += 5
    elif fixtures_count >= 4: score += 2

    return score

def discover_leagues():
    """
    Découverte 100% automatique de toutes les ligues actives dans le monde.
    Triées par priorité — les meilleures ligues analysées en premier.
    Cache Supabase 20h pour économiser les requêtes.
    """
    print(f"  [AUTO-DISCOVER] Scan des ligues actives...")
    print(f"  [QUOTA] {quota_used}/{quota_limit_day} requêtes utilisées")

    # Cache Supabase
    try:
        c = supabase.table("active_leagues").select("*")\
            .gte("updated_at",
                 (datetime.utcnow() - timedelta(hours=1)).isoformat())\
            .execute()
        if c.data:
            print(f"  [AUTO-DISCOVER] {len(c.data)} ligues depuis cache")
            return sorted(c.data,
                          key=lambda x: x.get("priority_score", 0),
                          reverse=True)
    except Exception:
        pass

    raw = api("leagues", {"current": "true"}) or []
    print(f"  [AUTO-DISCOVER] {len(raw)} ligues brutes reçues de l'API")

    # Fallback si l'API renvoie vide : relire la DERNIÈRE découverte réussie
    # depuis Supabase (active_leagues), SANS contrainte de fraîcheur. Ce sont
    # des IDs réels déjà validés par l'API lors d'un run précédent — jamais
    # devinés. Élimine le risque d'ID périmé ou de collision (ex. l'ancien
    # bug 292 Liga MX / K League). Aucune liste codée en dur.
    if not raw:
        print("  [FALLBACK] API vide — relecture de la dernière découverte Supabase")
        try:
            c2 = supabase.table("active_leagues").select("*")\
                .order("updated_at", desc=True).execute()
            if c2.data:
                print(f"  [FALLBACK] {len(c2.data)} ligues récupérées depuis active_leagues (IDs réels)")
                return sorted(c2.data, key=lambda x: x.get("priority_score", 0), reverse=True)
        except Exception as e:
            print(f"  [FALLBACK] Lecture active_leagues échouée : {e}")
        print("  [FALLBACK] Aucune découverte en cache — run ignoré (aucun ID deviné)")
        return []

    today = datetime.utcnow().date()
    end   = today + timedelta(days=DAYS_AHEAD)
    active = []

    for item in raw:
        lg      = item.get("league", {})
        ct      = item.get("country", {})
        name    = lg.get("name", "")
        lid     = lg.get("id")
        country = ct.get("name", "")

        # ── FILTRE LISTE BLANCHE : seule source de verite ──
        # On ne traite QUE les ligues ciblees -> supprime le scan
        # de ~1000 ligues bruit et evite le timeout.
        if lid not in WHITELIST_IDS:
            continue

        # Exclusion automatique
        nl = name.lower()
        # Exclure par mots-clés ET ligues féminines (nom finissant par " w")
        if any(kw in nl for kw in EXCLUDE_KW) or nl.endswith(" w") or " w " in nl:
            continue

        # Exclure CdM (traitée séparément) et Friendlies par league_id
        if lid in (1, 10, 667, 666):
            continue

        # Saison courante
        season = None
        for s in item.get("seasons", []):
            if s.get("current"):
                season = s.get("year"); break
        if not season:
            continue

        # Matchs à venir dans les 7 jours ?
        upcoming = api("fixtures", {
            "league": lid, "season": season,
            "from": str(today), "to": str(end), "status": "NS",
        }) or []
        if not upcoming:
            continue

        # Données suffisantes ? (au moins 3 matchs joués récemment)
        # Exception : CdM 2026 pas encore commencée → skip ce filtre
        if lid != 1:
            played = api("fixtures", {
                "league": lid, "season": season,
                "status": "FT", "last": 5,
            }) or []
            if len(played) < 3:
                continue

        is_nat = detect_national(name, country)
        tier   = detect_tier(name)

        # (Ancien filtre tier>=3 retire : la liste blanche choisit deja
        #  les divisions, y compris les D3 club voulues.)

        prio   = league_priority_score(
            name, country, tier, is_nat, len(upcoming)
        )

        info = {
            "id":             lid,
            "league_id":      lid,
            "name":           name,
            "country":        country,
            "season":         season,
            "tier":           tier,
            "is_national":    is_nat,
            "priority_score": prio,
            "fixtures_ahead": len(upcoming),
            "updated_at":     datetime.utcnow().isoformat(),
        }
        active.append(info)

        try:
            supabase.table("active_leagues")\
                .upsert(info, on_conflict="id").execute()
        except Exception:
            pass

    # Trier par priorité décroissante — limiter à 80 ligues max
    active.sort(key=lambda x: x["priority_score"], reverse=True)
    active = active[:80]

    print(f"  [AUTO-DISCOVER] {len(active)} ligues retenues · triées par priorité")
    for lg in active[:10]:
        print(f"    #{lg['priority_score']} {lg['name']} ({lg['country']}) "
              f"T{lg['tier']} {'NAT' if lg['is_national'] else 'CLUB'} "
              f"{lg['fixtures_ahead']}matchs")
    if len(active) > 10:
        print(f"    ... et {len(active)-10} autres ligues")

    return active

# ══════════════════════════════════════════════════════════════════════════════
# DONNÉES DES ÉQUIPES
# ══════════════════════════════════════════════════════════════════════════════

def last_matches(team_id, n):
    return api("fixtures", {
        "team": team_id, "last": n, "status": "FT",
    }) or []

def team_stats(team_id, league_id, season):
    d = api("teams/statistics", {
        "team": team_id, "league": league_id, "season": season,
    })
    if not d:
        return None
    if isinstance(d, list):
        return d[0] if d else None
    if isinstance(d, dict):
        return d
    return None

def get_h2h(t1, t2, n=8):
    return api("fixtures/headtohead", {
        "h2h": f"{t1}-{t2}", "last": n,
    }) or []

def get_injuries(team_id, fixture_id):
    return api("injuries", {
        "team": team_id, "fixture": fixture_id,
    }) or []

def get_standings(league_id, season):
    d = api("standings", {"league": league_id, "season": season})
    if not d: return {}
    out = {}
    try:
        for e in d[0]["league"]["standings"][0]:
            out[e["team"]["id"]] = {
                "rank": e["rank"], "points": e["points"],
            }
    except Exception:
        pass
    return out

def get_fixture_stats(fid):
    return api("fixtures/statistics", {"fixture": fid}) or []


def get_odds(fid, bet):
    return api("odds", {"fixture": fid, "bet": bet}) or []

# ══════════════════════════════════════════════════════════════════════════════
# INDEX ATTAQUE / DÉFENSE
# ══════════════════════════════════════════════════════════════════════════════

def compute_index(team_id, name, league_id, season, is_nat):
    cnt   = 12 if is_nat else 10
    # Pour les équipes nationales : matchs officiels prioritaires (pas amicaux)
    if is_nat:
        all_lasts = api("fixtures", {"team": team_id, "last": cnt*2, "status": "FT"}) or []
        # Filtrer amicaux (league_id=10) — bruitent la vraie forme
        officiels = [f for f in all_lasts if f.get("league",{}).get("id") not in (10,667,666)]
        lasts = officiels[:cnt] if len(officiels) >= 4 else all_lasts[:cnt]
    else:
        lasts = last_matches(team_id, cnt)
    stats = None if is_nat else team_stats(team_id, league_id, season)

    gf_s = ga_s = 0.0
    if stats:
        p    = stats.get("fixtures",{}).get("played",{}).get("total",1) or 1
        gf_s = (stats.get("goals",{}).get("for",{})
                .get("total",{}).get("total",0) or 0) / p
        ga_s = (stats.get("goals",{}).get("against",{})
                .get("total",{}).get("total",0) or 0) / p

    rgf=[]; rga=[]; btts=cs=win=0
    csm=csc=0

    for f in lasts:
        teams = f.get("teams",{})
        goals = f.get("goals",{})
        ih    = teams.get("home",{}).get("id") == team_id
        gf    = goals.get("home") if ih else goals.get("away")
        ga    = goals.get("away") if ih else goals.get("home")
        if gf is None or ga is None: continue
        rgf.append(gf); rga.append(ga)
        if gf>0 and ga>0: btts+=1
        if ga==0:         cs+=1
        if gf>ga:         win+=1
        # Corners via les stats embarquées dans la fixture (0 req supplémentaire)
        if not is_nat:
            for st in f.get("statistics", []):
                if (st.get("team",{}).get("id") == team_id and
                        st.get("type") == "Corner Kicks"):
                    try: csm += int(st.get("value") or 0); csc += 1
                    except: pass

    n   = len(rgf) or 1
    ref = 2.5 if is_nat else 3.0

    if len(rgf) >= 5 and not is_nat:
        gfw = (sum(rgf)/n)*0.6 + gf_s*0.4
        gaw = (sum(rga)/n)*0.6 + ga_s*0.4
    else:
        gfw = sum(rgf)/n if rgf else gf_s
        gaw = sum(rga)/n if rga else ga_s

    oi = round(min((gfw/ref)*10, 10.0), 1)
    di = round(max(10-(gaw/ref)*10, 0.0), 1)

    fr = None
    if is_nat:
        fr = FIFA.get(name, 50)
        fb = 1.5 if fr<=5 else 0.8 if fr<=15 else 0.0 if fr<=30 else -0.8
        oi = round(min(oi+fb*0.4, 10.0), 1)
        di = round(min(di+fb*0.4, 10.0), 1)

    return {
        "off_index":         oi,
        "def_index":         di,
        "goals_for_avg":     round(gfw, 2),
        "goals_against_avg": round(gaw, 2),
        "btts_rate":         round(btts/n*100, 1),
        "clean_sheet_pct":   round(cs/n*100, 1),
        "win_rate":          round(win/n*100, 1),
        "avg_corners":       round(csm/csc, 1) if csc else 5.0,
        "matches_analyzed":  len(rgf),
        "fifa_rank":         fr,
    }

# ══════════════════════════════════════════════════════════════════════════════
# xG · H2H · FACTEURS EXTERNES
# ══════════════════════════════════════════════════════════════════════════════

def xg(home, away):
    h = home["goals_for_avg"] * (1 - away["def_index"]/10)
    a = away["goals_for_avg"] * (1 - home["def_index"]/10)
    return round(h,2), round(a,2), round(h+a,2)

def analyze_h2h(fxs):
    if not fxs:
        return {"under25":50.0,"btts":50.0,"count":0}
    tots=[]; b=0
    for f in fxs:
        gh=f.get("goals",{}).get("home")
        ga=f.get("goals",{}).get("away")
        if gh is None or ga is None: continue
        tots.append(gh+ga)
        if gh>0 and ga>0: b+=1
    n = len(tots) or 1
    return {
        "under25": round(sum(1 for t in tots if t<3)/n*100,1),
        "btts":    round(b/n*100,1),
        "count":   n,
    }

def analyze_inj(hid, aid, fid):
    adj_u=adj_b=0; dets=[]
    for tid,lbl in [(hid,"dom"),(aid,"ext")]:
        ko=0
        for inj in get_injuries(tid, fid):
            p = inj.get("player",{})
            if (p.get("reason") in ("Missing Fixture","Injured") and
                    p.get("position") in ("Attacker","Midfielder")):
                ko+=1; dets.append(f"{p.get('name','?')} ({lbl})")
        if   ko>=2: adj_u+=3; adj_b-=5
        elif ko==1: adj_u+=2; adj_b-=3
    return {"adj_under":adj_u,"adj_btts":adj_b,"details":dets}

def get_weather(coords, date_str):
    lat,lon = coords
    try:
        ds = date_str[:10]
        r  = requests.get(
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&daily=precipitation_sum,windspeed_10m_max,"
            f"temperature_2m_min,temperature_2m_max"
            f"&start_date={ds}&end_date={ds}&timezone=UTC",
            timeout=10)
        if r.status_code != 200:
            return {"adj_under":0,"adj_btts":0,"description":""}
        d    = r.json().get("daily",{})
        pr   = (d.get("precipitation_sum") or [0])[0]  or 0
        wd   = (d.get("windspeed_10m_max")  or [10])[0] or 10
        tm   = (d.get("temperature_2m_min") or [15])[0] or 15
        tx   = (d.get("temperature_2m_max") or [25])[0] or 25
        adj=0; pts=[]
        if pr>=10:  adj+=4; pts.append(f"Pluie forte {pr:.0f}mm")
        elif pr>=5: adj+=2; pts.append(f"Pluie {pr:.0f}mm")
        if wd>=40:  adj+=3; pts.append(f"Vent {wd:.0f}km/h")
        if tm<=2:   adj+=2; pts.append(f"Froid {tm:.0f}°C")
        if tx>=35:  adj+=3; pts.append(f"Chaleur {tx:.0f}°C")
        return {
            "adj_under":adj,"adj_btts":-(adj//2),
            "description":" · ".join(pts) if pts else "Normale",
            "precip":pr,"wind":wd,"temp_min":tm,"temp_max":tx,
        }
    except Exception:
        return {"adj_under":0,"adj_btts":0,"description":""}

def stake_adj(hid, aid, stds, wc_round=""):
    adj=0
    if wc_round:
        if "Semi"     in wc_round: adj+=5
        elif "Quarter" in wc_round: adj+=4
        elif "Round"   in wc_round: adj+=3
        elif "Final"   in wc_round: adj+=4
        return adj
    if not stds: return adj
    tot=len(stds); rz=tot-2
    hr=stds.get(hid,{}).get("rank",10)
    ar=stds.get(aid,{}).get("rank",10)
    if hr<=3 and stds.get(hid,{}).get("points",0)>70: adj+=4
    if ar<=3 and stds.get(aid,{}).get("points",0)>70: adj+=4
    if hr>=rz and ar>=rz: adj-=3
    if abs(hr-ar)<=2: adj-=2
    return adj

def corner_adj(hi, ai):
    avg = (hi["avg_corners"]+ai["avg_corners"])/2
    return -4 if avg>=11 else 3 if avg<=7 else 0

def odds_data(fid):
    res = {
        "pinnacle_under25":None,"bet365_under25":None,"xbet_under25":None,
        "pinnacle_btts":None,"bet365_btts":None,"xbet_btts":None,
        "pinnacle_home":None,"pinnacle_away":None,"pinnacle_draw":None,

        "adj":0,"signal":"Neutre","movement":{},
    }
    for item in get_odds(fid, 5):
        for bk in item.get("bookmakers",[]):
            for bet in bk.get("bets",[]):
                if bet.get("id")==5:
                    for v in bet.get("values",[]):
                        if v.get("value")=="Under 2.5":
                            o = float(v.get("odd") or 0)
                            if   bk.get("id")==8:  res["pinnacle_under25"]=o
                            elif bk.get("id")==4:  res["bet365_under25"]=o
                            elif bk.get("id")==36: res["xbet_under25"]=o
    for item in get_odds(fid, 1):
        for bk in item.get("bookmakers",[]):
            if bk.get("id") == 8:
                for bet in bk.get("bets",[]):
                    if bet.get("id")==1:
                        for v in bet.get("values",[]):
                            vl=v.get("value"); o=float(v.get("odd") or 0)
                            if   vl=="Home": res["pinnacle_home"]=o
                            elif vl=="Away": res["pinnacle_away"]=o
                            elif vl=="Draw": res["pinnacle_draw"]=o
    for item in get_odds(fid, 8):
        for bk in item.get("bookmakers",[]):
            for bet in bk.get("bets",[]):
                if bet.get("id")==8:
                    for v in bet.get("values",[]):
                        if v.get("value")=="Yes":
                            o = float(v.get("odd") or 0)
                            if   bk.get("id")==8:  res["pinnacle_btts"]=o
                            elif bk.get("id")==4:  res["bet365_btts"]=o
                            elif bk.get("id")==36: res["xbet_btts"]=o
    try:
        prev = supabase.table("odds_history")\
            .select("pinnacle_under25")\
            .eq("fixture_id",fid)\
            .order("recorded_at").limit(1).execute()
        po = prev.data[0]["pinnacle_under25"] if prev.data else None
    except Exception:
        po = None

    if po and res["pinnacle_under25"]:
        ch = (res["pinnacle_under25"]-po)/po*100
        res["movement"]["pinnacle"] = {
            "open":po,"current":res["pinnacle_under25"],"change":round(ch,1)
        }
        if   ch<=-8: res["adj"]=9;  res["signal"]="Sharp money Under"
        elif ch<=-4: res["adj"]=5;  res["signal"]="Mouvement Under"
        elif ch>= 8: res["adj"]=-8; res["signal"]="Mouvement contraire"

    try:
        supabase.table("odds_history").upsert({
            "fixture_id":fid,
            "pinnacle_under25":res["pinnacle_under25"],
            "bet365_under25":res["bet365_under25"],
            "xbet_under25":res["xbet_under25"],
            "recorded_at":datetime.utcnow().isoformat(),
        },on_conflict="fixture_id").execute()
    except Exception:
        pass
    return res

# ══════════════════════════════════════════════════════════════════════════════
# SCORE DE CONFIANCE
# ══════════════════════════════════════════════════════════════════════════════

def compute_scores(hi,ai,h2h_d,xgt,inj_d,sk,wth,ca,odd,
                   stds,hid,aid,tier,is_nat,wr=""):

    # Under 2.5
    if   xgt>=3.0: bu=15
    elif xgt>=2.5: bu=32
    elif xgt>=2.0: bu=55
    elif xgt>=1.5: bu=72
    else:          bu=85

    ds  = (hi["def_index"]+ai["def_index"])/2
    hw  = 0.28 if h2h_d["count"]>=5 else 0.15
    us  = (bu*0.37 + h2h_d["under25"]*hw +
           hi["clean_sheet_pct"]*0.18 + 50*(0.45-hw))
    us += (ds-5)*2.8 + inj_d["adj_under"] + sk
    us += wth.get("adj_under",0) + ca + odd["adj"]
    if tier==3:  us+=2
    if is_nat:   us+=1
    us = round(min(max(us,0),96),1)

    # ── GARDE-FOU RÉALITÉ (Under 2.5) ───────────────────────────────────
    # Les BUTS RÉELLEMENT marqués priment sur l'estimation xG, qui peut
    # s'effondrer à tort (def_index surévalué sur des équipes mal notées en
    # défense) et gonfler l'Under sur des équipes qui marquent beaucoup.
    # On plafonne la confiance SOUS le seuil de sélection quand l'historique
    # direct OU les moyennes de buts réelles contredisent l'Under.
    # N'augmente jamais le score — ne fait que le réduire. Ex. Vikingur-Runavik :
    # H2H ~40% Under -> plafonné à 68 < MIN_CONF -> Under non retenu.
    real_total = hi.get("goals_for_avg", 0) + ai.get("goals_for_avg", 0)
    under_cap = 96.0
    # 1) Confrontations directes : ces équipes passent souvent l'Over
    if h2h_d["count"] >= 4:
        if   h2h_d["under25"] < 30: under_cap = min(under_cap, MIN_CONF - 14)
        elif h2h_d["under25"] < 45: under_cap = min(under_cap, MIN_CONF - 4)
    # 2) Moyennes de buts réelles élevées (hors influence trompeuse du def_index)
    if   real_total >= 3.2: under_cap = min(under_cap, MIN_CONF - 14)
    elif real_total >= 2.8: under_cap = min(under_cap, MIN_CONF - 4)
    us = round(min(us, under_cap), 1)

    # BTTS
    oc=(hi["off_index"]+ai["off_index"])/2
    dc=(hi["def_index"]+ai["def_index"])/2
    br=(hi["btts_rate"]+ai["btts_rate"])/2
    bs=(br*0.40+(oc/10*100)*0.30+((10-dc)/10*100)*0.15+h2h_d["btts"]*0.15)
    bs+=inj_d["adj_btts"]+wth.get("adj_btts",0)
    if hi["off_index"]<5.5 or ai["off_index"]<5.5: bs-=4
    bs=round(min(max(bs,0),96),1)

    # Éviter contradiction Under ↔ BTTS
    if abs(us-bs)<8:
        mx=max(us,bs)
        us=mx-8 if us<bs else us
        bs=mx-8 if bs<us else bs

    # Victoire
    og=abs(hi["off_index"]-ai["off_index"])
    dg=abs(hi["def_index"]-ai["def_index"])
    ihs=hi["off_index"]>=ai["off_index"]
    swr=hi["win_rate"] if ihs else ai["win_rate"]
    vs=None; sl=None

    # Seuils adaptés pour équipes nationales CdM
    if is_nat:
        hr = hi.get("fifa_rank", 50) or 50
        ar = ai.get("fifa_rank", 50) or 50
        fifa_gap = abs(hr - ar)

        # ── FILTRE ANTI-PIÈGE ──────────────────────────────────────────────
        # Exiger un écart FIFA MINIMUM pour éviter les matchs équilibrés
        # Deux nations dans les 20 premiers = match trop incertain
        top_nations = min(hr, ar)
        both_strong = top_nations <= 20 and fifa_gap < 10

        # Forme récente insuffisante = signal peu fiable
        fav_win_rate = hi["win_rate"] if ihs else ai["win_rate"]
        opp_win_rate = ai["win_rate"] if ihs else hi["win_rate"]
        weak_form = fav_win_rate < 50

        # Écart trop faible = match piège
        weak_signal = og < 1.5 or dg < 0.8

        # ── COHÉRENCE FIFA ─────────────────────────────────────────────────
        # Le favori désigné par le calcul doit être cohérent avec FIFA.
        # Si le calcul désigne une équipe bien moins classée → contradiction.
        fav_fifa = hr if ihs else ar
        opp_fifa = ar if ihs else hr
        fifa_contradiction = fav_fifa > opp_fifa + 15

        # Abandonner si match piège détecté
        if both_strong or weak_form or weak_signal or fifa_contradiction:
            pass  # vs et sl restent None → pas de prédiction
        else:
            # Signal validé — calculer le score
            bv = 50 + og*5 + dg*4

            # Bonus classement FIFA — seulement si le favori est mieux classé
            fav_better = fav_fifa < opp_fifa
            if fav_better:
                if   fifa_gap >= 30: bv += 15
                elif fifa_gap >= 20: bv += 10
                elif fifa_gap >= 15: bv += 6
                elif fifa_gap >= 10: bv += 3
            # Malus si les deux équipes sont fortes (match serré probable)
            if top_nations <= 15: bv -= 5

            # Bonus forme récente de la favorite
            if fav_win_rate >= 70: bv += 5
            elif fav_win_rate >= 60: bv += 2

            # Malus forme de l'OUTSIDER : une équipe en forme peut tenir tête
            # au favori, même si son rang FIFA reste modéré (ex : sélection
            # sortant d'une bonne CAN). On ne juge plus seulement la favorite,
            # mais aussi la dynamique récente de l'adversaire.
            if   opp_win_rate >= 65: bv -= 12
            elif opp_win_rate >= 55: bv -= 7
            elif opp_win_rate >= 45: bv -= 3

            # Bonus round CdM
            bv += stake_adj(hid, aid, {}, wr)

            sl = "DOMICILE" if ihs else "EXTÉRIEUR"
            mv = 78 if sl == "EXTÉRIEUR" else 75
            if   bv >= mv: vs = round(min(bv, 91), 1)
            elif bv >= 70:
                sl = f"DOUBLE CHANCE {'1X' if ihs else 'X2'}"
                vs = round(min(bv+7, 88), 1)
    else:
        if og>=2.5 and dg>=1.5 and swr>=55:
            bv=50+og*4+dg*3
            if ihs: bv+={3:6,2:4,1:2,0:3}.get(tier,2)
            if stds and not is_nat:
                sp=stds.get(hid if ihs else aid,{}).get("points",0)
                wp=stds.get(aid if ihs else hid,{}).get("points",0)
                mg=6 if tier>=2 else 8
                if sp-wp<mg: bv-=5
            sl="DOMICILE" if ihs else "EXTÉRIEUR"
            mv=78 if sl=="EXTÉRIEUR" else 75
            if   bv>=mv: vs=round(min(bv,91),1)
            elif bv>=70:
                sl=f"DOUBLE CHANCE {'1X' if ihs else 'X2'}"
                vs=round(min(bv+7,88),1)

    cands=[]
    # Under 2.5 exclu pour CdM et compétitions nationales (BTTS et Victoire plus pertinents)
    if us>=MIN_CONF and not is_nat: cands.append(("UNDER 2.5", us))
    if bs>=MIN_CONF:               cands.append(("BTTS",        bs))
    if vs and vs>=MIN_CONF and sl: cands.append((f"VICTOIRE {sl}", vs))
    if not cands: return None

    cands.sort(key=lambda x:x[1],reverse=True)
    br2,bc=cands[0]

    # Si victoire gagne mais < 5 pts d'écart → préférer Under/BTTS
    if "VICTOIRE" in br2 and len(cands)>1:
        if bc-cands[1][1]<5: br2,bc=cands[1]

    return {
        "recommendation":br2,"rec_confidence":bc,
        "under25_score":us,"btts_score":bs,"victory_score":vs,
        "risk_level":"Faible" if bc>=80 else "Moyen",
    }

# ══════════════════════════════════════════════════════════════════════════════
# CONTEXTE NATUREL
# ══════════════════════════════════════════════════════════════════════════════

def gen_context(hn,an,hi,ai,h2h_d,xgt,rec,odd,wth,inj_d,is_nat):
    ps=[]
    if is_nat:
        hr=hi.get("fifa_rank",50); ar=ai.get("fifa_rank",50)
        if abs(hr-ar)>=10:
            sn=hn if hr<ar else an
            ps.append(f"{sn} favori mondial (FIFA #{min(hr,ar)} vs #{max(hr,ar)})")
    if "UNDER" in rec:
        for nm,ix in [(hn,hi),(an,ai)]:
            di=ix["def_index"]; ga=ix["goals_against_avg"]
            if   di>=8.0: ps.append(f"{nm} — défense élite ({ga:.2f} but/match)")
            elif di>=6.5: ps.append(f"{nm} — défense solide ({ga:.2f} but/match)")
            else:         ps.append(f"{nm} — défense moyenne ({ga:.2f} but/match)")
        ps.append(f"{xgt} buts attendus — "
                  f"{'signal très fort' if xgt<=1.8 else 'sous le seuil'}")
    elif "BTTS" in rec:
        for nm,ix in [(hn,hi),(an,ai)]:
            oi=ix["off_index"]; gf=ix["goals_for_avg"]
            if   oi>=7.5: ps.append(f"{nm} — attaque forte ({gf:.2f} buts/match)")
            elif oi>=5.5: ps.append(f"{nm} — marque régulièrement ({gf:.2f}/match)")
            else:         ps.append(f"{nm} — attaque limitée ({gf:.2f}/match)")
        ba=(hi["btts_rate"]+ai["btts_rate"])/2
        ps.append(f"Les deux marquent dans {ba:.0f}% des matchs")
    elif "VICTOIRE" in rec or "DOUBLE" in rec:
        ihs=hi["off_index"]>=ai["off_index"]
        sn=hn if ihs else an; si=hi if ihs else ai
        ps.append(f"{sn} — off {si['off_index']:.1f}/10 · "
                  f"def {si['def_index']:.1f}/10")
        if si["win_rate"]>=65:
            ps.append(f"En forme : {si['win_rate']:.0f}% de victoires récentes")
    if h2h_d["count"]>=3:
        if "UNDER" in rec and h2h_d["under25"]>=60:
            w=round(h2h_d["under25"]/100*h2h_d["count"])
            ps.append(f"H2H fermé : {w}/{h2h_d['count']} matchs sous 3 buts")
        elif "BTTS" in rec and h2h_d["btts"]>=50:
            w=round(h2h_d["btts"]/100*h2h_d["count"])
            ps.append(f"H2H : les deux marquent dans {w}/{h2h_d['count']} matchs")
    if   odd["signal"]=="Sharp money Under":
        c=odd["pinnacle_under25"]
        m=odd.get("movement",{}).get("pinnacle",{}).get("change",0)
        ps.append(f"Sharp money — Pinnacle Under {c} ({m:+.1f}%)")
    elif odd["signal"]=="Mouvement contraire":
        ps.append("Attention — mouvement contraire Pinnacle")
    if wth.get("description") and wth["description"] not in ("Normale",""):
        ps.append(f"Météo : {wth['description']}")
    if inj_d.get("details"):
        ps.append(f"Absent(s) : {', '.join(inj_d['details'][:2])}")
    n=min(hi["matches_analyzed"],ai["matches_analyzed"])
    ps.append(f"Basé sur {n}+ matchs · {h2h_d['count']} H2H")
    return " · ".join(ps)

# ══════════════════════════════════════════════════════════════════════════════
# SAUVEGARDE SUPABASE
# ══════════════════════════════════════════════════════════════════════════════

def make_id(fid, lid):
    return int(hashlib.md5(f"{fid}_{lid}".encode()).hexdigest()[:12], 16)

def save(row):
    try:
        supabase.table("predictions")\
            .upsert(row, on_conflict="id").execute()
        return True
    except Exception as e:
        print(f"    [DB] {e}"); return False

def save_idx(team_id, name, lid, season, ix):
    try:
        uid = int(hashlib.md5(
            f"{team_id}_{lid}_{season}".encode()
        ).hexdigest()[:12], 16)
        supabase.table("team_indexes").upsert({
            "id":uid,"team_id":team_id,"team_name":name,
            "league_id":lid,"season":season,
            **{k:ix[k] for k in [
                "off_index","def_index","goals_for_avg","goals_against_avg",
                "btts_rate","clean_sheet_pct","win_rate",
                "avg_corners","matches_analyzed",
            ]},
            "updated_at":datetime.utcnow().isoformat(),
        },on_conflict="id").execute()
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
# TRAITEMENT D'UN MATCH
# ══════════════════════════════════════════════════════════════════════════════

def process(fix, li):
    lid     = li["league_id"]
    season  = li["season"]
    is_nat  = li["is_national"]
    tier    = li["tier"]
    country = li["country"]

    fid    = fix["fixture"]["id"]
    md     = fix["fixture"]["date"]
    home   = fix["teams"]["home"]
    away   = fix["teams"]["away"]
    vc     = fix.get("fixture",{}).get("venue",{}).get("city","") if is_nat else None
    wr     = fix.get("league",{}).get("round","") if is_nat else ""

    print(f"    [{quota_pct_used():.0f}% quota] "
          f"{home['name']} vs {away['name']}")

    # Exclure équipes jeunes (U20, U21, U23...) même si la ligue passe le filtre
    YOUTH_KW = ["u16","u17","u18","u19","u20","u21","u22","u23","youth","u-20","u-21","u-23"]
    hn_low = home["name"].lower()
    an_low = away["name"].lower()
    if any(kw in hn_low for kw in YOUTH_KW) or any(kw in an_low for kw in YOUTH_KW):
        print(f"      [SKIP] Équipe jeune (U20/U21/U23)")
        return False

    mn = 3 if is_nat else 5
    hi = compute_index(home["id"],home["name"],lid,season,is_nat)
    ai = compute_index(away["id"],away["name"],lid,season,is_nat)

    if hi["matches_analyzed"]<mn or ai["matches_analyzed"]<mn:
        print(f"      [SKIP] Données insuffisantes")
        return False

    save_idx(home["id"],home["name"],lid,season,hi)
    save_idx(away["id"],away["name"],lid,season,ai)

    h2h_raw      = get_h2h(home["id"],away["id"],10 if is_nat else 8)
    h2h_d        = analyze_h2h(h2h_raw)
    xgh,xga,xgt  = xg(hi,ai)
    inj_d        = analyze_inj(home["id"],away["id"],fid)
    stds         = get_standings(lid,season) if not is_nat else {}
    sk           = stake_adj(home["id"],away["id"],stds,wr)

    # Coordonnées GPS automatiques
    if vc and vc in CITY_COORDS: coords=CITY_COORDS[vc]
    else: coords=COUNTRY_COORDS.get(country,(48.856,2.352))

    wth  = get_weather(coords, md)
    ca   = corner_adj(hi,ai) if not is_nat else 0
    odd  = odds_data(fid)

    hi_adj = hi
    ai_adj = ai

    res  = compute_scores(hi_adj,ai_adj,h2h_d,xgt,inj_d,sk,wth,ca,odd,
                          stds,home["id"],away["id"],tier,is_nat,wr)
    if not res:
        print(f"      [SKIP] Signal insuffisant")
        return False

    # ── Prudence Coupe du Monde selon la phase (round) ──────────────────
    # 3e match de groupe : enjeux faussés (équipes qualifiées gèrent, calculs)
    # Élimination directe : peut aller en prolongation/penalties → "Victoire"
    #   au temps réglementaire devient incertaine.
    if is_nat and wr:
        wr_low = wr.lower()
        rec_up = (res.get("recommendation") or "").upper()
        is_victoire = "VICTOIRE" in rec_up
        malus = 0
        raison = ""
        # Élimination directe (penalties possibles)
        if any(k in wr_low for k in ["round of", "8th finals", "16", "quarter", "semi", "final"]):
            malus = 12
            raison = "élimination directe (prolongation/penalties possibles)"
        # 3e match de groupe (enjeux faussés)
        elif "group" in wr_low and ("3" in wr_low or "- 3" in wr_low):
            malus = 8
            raison = "3e match de groupe (enjeux faussés)"

        if malus > 0 and is_victoire:
            res["rec_confidence"] = round(res["rec_confidence"] - malus, 1)
            print(f"      [CdM PRUDENCE] -{malus} conf · {raison} → {res['rec_confidence']}%")
            # Si la confiance retombe sous le seuil, on annule la prédiction
            if res["rec_confidence"] < MIN_CONF:
                print(f"      [SKIP] Confiance sous le seuil après prudence CdM")
                return False

    ctx = gen_context(
        home["name"],away["name"],hi_adj,ai_adj,h2h_d,xgt,
        res["recommendation"],odd,wth,inj_d,is_nat
    )



    now = datetime.utcnow().isoformat()
    row = {
        "id":make_id(fid,lid),"fixture_id":fid,
        "league_id":lid,"league_name":li["name"],"league_country":country,
        "league_tier":tier,"is_national":is_nat,"wc_round":wr,
        "season":season,"match_date":md,"venue_city":vc,
        "home_team_id":home["id"],"home_team_name":home["name"],
        "away_team_id":away["id"],"away_team_name":away["name"],
        "xg_home":xgh,"xg_away":xga,"xg_total":xgt,
        "recommendation":res["recommendation"],
        "rec_confidence":res["rec_confidence"],
        "under25_score":res["under25_score"],
        "btts_score":res["btts_score"],
        "victory_score":res["victory_score"],
        "risk_level":res["risk_level"],"context_text":ctx,
        "home_off_index":hi["off_index"],"home_def_index":hi["def_index"],
        "away_off_index":ai["off_index"],"away_def_index":ai["def_index"],
        "home_fifa_rank":hi.get("fifa_rank"),"away_fifa_rank":ai.get("fifa_rank"),
        "h2h_under25_rate":h2h_d["under25"],"h2h_btts_rate":h2h_d["btts"],
        "h2h_count":h2h_d["count"],"injuries_detail":str(inj_d["details"]),
        "weather_desc":wth.get("description",""),
        "weather_precip":wth.get("precip",0),
        "weather_wind":wth.get("wind",0),
        "weather_temp":wth.get("temp_max",0),
        "odds_signal":odd["signal"],
        "pinnacle_under25":odd["pinnacle_under25"],
        "bet365_under25":odd["bet365_under25"],
        "xbet_under25":odd["xbet_under25"],
        "pinnacle_btts":odd["pinnacle_btts"],
        "bet365_btts":odd["bet365_btts"],
        "xbet_btts":odd["xbet_btts"],
        "pinnacle_home":odd["pinnacle_home"],
        "pinnacle_away":odd["pinnacle_away"],
        "pinnacle_draw":odd["pinnacle_draw"],
        "adj_injuries":inj_d["adj_under"],
        "adj_stake":sk,
        "adj_weather":wth.get("adj_under",0),
        "adj_corners":ca,
        "adj_odds":odd["adj"],
        "manually_validated":None,
        "actual_total_goals":None,
        "actual_home_goals":None,
        "actual_away_goals":None,
        "prediction_correct":None,
        "scraped_at":now,
    }
    ok = save(row)
    if ok:
        print(
            f"      [OK] {res['recommendation']} "
            f"{res['rec_confidence']}% · xG={xgt} · "
            f"{odd['signal']} · {res['risk_level']}"
        )
    return ok

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(
        f"\n=== Predictions Master — Auto-Discovery — "
        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC ===\n"
    )

    # ── PROTECTION ANTI-DOUBLON ──────────────────────────────────────────
    # Si le moteur a déjà publié des prédictions aujourd'hui, on s'arrête.
    # Permet plusieurs tentatives cron (00h30/01h00/01h30) sans gaspiller le quota.
    try:
        today_iso = datetime.utcnow().date().isoformat()
        chk = supabase.table("predictions") \
            .select("id", count="exact") \
            .gte("scraped_at", today_iso + "T00:00:00") \
            .limit(1) \
            .execute()
        already = getattr(chk, "count", None) or 0
        if already and already > 0:
            print(f"  [SKIP] {already} prédictions déjà publiées aujourd'hui — moteur déjà exécuté")
            print("=== Arrêt anti-doublon ===")
            return
    except Exception as e:
        print(f"  [WARN] Vérification anti-doublon échouée ({e}) — on continue")

    # Vérifier le quota actuel via un appel test
    global quota_used, quota_limit_day
    print(f"Heure UTC : {datetime.utcnow().strftime('%H:%M')}")
    try:
        import requests as _req
        r = _req.get(
            "https://v3.football.api-sports.io/status",
            headers=HEADERS, timeout=10
        )
        if r.status_code == 200:
            d = r.json().get("response", {})
            if isinstance(d, dict):
                reqs = d.get("requests", {})
                # Body JSON est la source fiable — pas les headers
                current = reqs.get("current", None)
                limit   = reqs.get("limit_day", None)
                if current is not None: quota_used      = current
                if limit   is not None: quota_limit_day = limit
            # Headers en fallback uniquement si body vide
            if quota_used == 0:
                h_remain = r.headers.get("x-ratelimit-requests-remaining")
                h_limit  = r.headers.get("x-ratelimit-requests-limit")
                if h_limit:  quota_limit_day = int(h_limit)
                if h_remain: quota_used = quota_limit_day - int(h_remain)
    except Exception:
        pass

    avail = quota_limit_day - quota_used
    print(f"Quota : {quota_used}/{quota_limit_day} ({avail} disponibles)")
    if avail < 200:
        print(f"[QUOTA] ⚠️  Seulement {avail} req disponibles — run annulé.")
        print(f"[QUOTA] Recharge à 00h00 UTC. Cron automatique à 04h00 UTC.")
        return
    print()

    today = datetime.utcnow().date()
    end   = today + timedelta(days=DAYS_AHEAD)
    tp=ts=0

    # Charger les vrais classements FIFA depuis l'API
    load_fifa_rankings()

    # ══ PRIORITÉ ABSOLUE : World Cup 2026 traitée AVANT discover_leagues ══
    # La CdM a 0 matchs joués → rejetée par discover_leagues (filtre played>=3)
    # On la traite ici avant de brûler du quota sur les autres ligues
    wc_league = {
        "league_id": 1, "name": "FIFA World Cup 2026",
        "country": "World", "season": 2026,
        "tier": 1, "is_national": True,
        "priority_score": 999, "fixtures_ahead": 64,
    }
    print("\n[FIFA World Cup 2026] World S2026 NAT Priorité #999")
    wc_end = today + timedelta(days=7)

    # Essai 1 : status NS
    wc_fxs = api("fixtures", {
        "league": 1, "season": 2026,
        "from": str(today), "to": str(wc_end), "status": "NS",
    }) or []

    # Essai 2 : sans filtre statut (matchs TBD ou autre)
    if not wc_fxs:
        wc_fxs = api("fixtures", {
            "league": 1, "season": 2026,
            "from": str(today), "to": str(wc_end),
        }) or []
        if wc_fxs:
            print(f"  [CdM] {len(wc_fxs)} fixtures (sans filtre statut)")

    # Essai 3 : next=10
    if not wc_fxs:
        wc_fxs = api("fixtures", {"league": 1, "season": 2026, "next": 10}) or []
        if wc_fxs:
            print(f"  [CdM] {len(wc_fxs)} fixtures (next=10)")

    if wc_fxs:
        print(f"  [CdM] ✅ {len(wc_fxs)} matchs trouvés — analyse en cours")
        for fx in wc_fxs[:5]:
            h = fx.get("teams",{}).get("home",{}).get("name","?")
            a = fx.get("teams",{}).get("away",{}).get("name","?")
            d = fx.get("fixture",{}).get("date","?")[:10]
            s = fx.get("fixture",{}).get("status",{}).get("short","?")
            print(f"    {h} vs {a} ({d}) [{s}]")
        for fx in wc_fxs[:64]:
            tp += 1
            if process(fx, wc_league): ts += 1
    else:
        print("  [CdM] ❌ Aucun fixture — league_id=1 inaccessible sur ce plan API")
        print("  [CdM] → Vérifier sur rapidapi.com/dashboard que la CdM est incluse")

    # Découvrir toutes les autres ligues actives automatiquement
    leagues = discover_leagues()
    if not leagues:
        print("Aucune ligue active trouvée.")
        # Sauvegarde quand même les stats CdM
        print(f"\n=== Terminé · {ts}/{tp} prédictions publiées · {quota_pct_used():.1f}% du quota utilisé ===\n")
        return

    # Exclure la CdM de la liste (déjà traitée)
    leagues = [li for li in leagues if li["league_id"] != 1]

    # Analyser par ordre de priorité
    for li in leagues:

        # Vérifier le quota avant chaque ligue
        if quota_pct_used() >= QUOTA_SAFETY_PCT * 100:
            break

        tier_str = "NAT" if li["is_national"] else "T" + str(li["tier"])
        print("\n[" + li["name"] + "] " + li["country"] +
              " S" + str(li["season"]) + " " + tier_str +
              " Priorité #" + str(li["priority_score"]))

        days_window = DAYS_AHEAD
        end_li = today + timedelta(days=days_window)
        fxs = api("fixtures", {
            "league": li["league_id"], "season": li["season"],
            "from": str(today), "to": str(end_li), "status": "NS",
        }) or []

        if not fxs:
            print("  Aucun match.")
            continue

        # Limiter à 10 matchs par ligue pour éviter timeout (les + proches)
        fxs = fxs[:10]
        print(f"  {len(fxs)} match(s) · "
              f"{quota_remaining()} requêtes restantes")

        for fx in fxs:
            # Vérifier quota avant chaque match
            if quota_pct_used() >= QUOTA_SAFETY_PCT * 100:
                print(f"  [QUOTA] Arrêt avant ce match")
                break
            tp+=1
            if process(fx, li): ts+=1

    print(
        f"\n=== Terminé · {ts}/{tp} prédictions publiées · "
        f"{quota_pct_used():.1f}% du quota utilisé ===\n"
    )

if __name__=="__main__":
    main()