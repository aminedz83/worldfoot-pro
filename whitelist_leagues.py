# -*- coding: utf-8 -*-
"""
whitelist_leagues.py
====================
LISTE BLANCHE des ligues a cibler (IDs API-Football).

Regles appliquees :
  - GARDE : 1re, 2e et 3e division NATIONALE pleinement pro.
  - VIRE  : regional / etat (ex. championnats d'etat bresiliens, Oberliga,
            National 2/3 francais, Tercera espagnole...), amateur, feminin,
            jeunes, reserves, phases de play-offs listees a part,
            et les D1 de micro-pays (donnees peu fiables).
  - Semi-pro regionalise du 3e niveau (Primera RFEF, Tweede Divisie,
    K3, Serie D...) : VIRE (pas pleinement pro).

NB : liste de DEPART, volontairement ajustable. Pour ajouter/retirer une
ligue, il suffit d'editer ce dict. Le moteur ne traitera QUE ces IDs.
"""

# id -> "Nom (Pays)"  (le commentaire sert juste a la relecture humaine)
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