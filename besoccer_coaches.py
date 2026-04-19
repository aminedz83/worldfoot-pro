#!/usr/bin/env python3
"""
besoccer_coaches.py
===================
Scrape les entraîneurs actuels Ligue 1 Algérie depuis BeSoccer.
URL : https://fr.besoccer.com/competition/entreineurs/algeria-league-one
Stocke dans Supabase `algeria_coaches`.
"""

import os, re, json, requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# ══════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL       = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS   = {
    "apikey":        SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates"
}

URL = "https://fr.besoccer.com/competition/entreineurs/algeria-league-one"

# Mapping nom BeSoccer → nom interne app (club_source)
CLUB_NAME_MAP = {
    "Chlef":          "ASO Chlef",
    "ASO Chlef":      "ASO Chlef",
    "JS Saoura":      "JS Saoura",
    "CR Belouizdad":  "CR Belouizdad",
    "Belouizdad":     "CR Belouizdad",
    "MC Alger":       "MC Alger",
    "JS Kabylie":     "JS Kabylie",
    "Kabylie":        "JS Kabylie",
    "ES Setif":       "ES Setif",
    "USM Alger":      "USM Alger",
    "CS Constantine": "CS Constantine",
    "MC Oran":        "MC Oran",
    "ES Mostaganem":  "ES Mostaganem",
    "MB Rouissat":    "MB Rouissat",
    "MB Rouisset":    "MB Rouissat",
    "ES Ben Aknoun":  "ES Ben Aknoun",
    "Ben Aknoun":     "ES Ben Aknoun",
    "USM Khenchela":  "USM Khenchela",
    "Paradou AC":     "Paradou AC",
    "Paradou":        "Paradou AC",
    "Olympique Akbou":"Olympique Akbou",
    "Oued Akbou":     "Olympique Akbou",
    "MC El Bayadh":   "MC El Bayadh",
    "El Bayadh":      "MC El Bayadh",
}

CLUB_LOGOS = {
    "MC Alger":        "https://media.api-sports.io/football/teams/906.png",
    "CR Belouizdad":   "https://media.api-sports.io/football/teams/904.png",
    "JS Kabylie":      "https://media.api-sports.io/football/teams/918.png",
    "USM Alger":       "https://media.api-sports.io/football/teams/910.png",
    "ES Setif":        "https://media.api-sports.io/football/teams/905.png",
    "CS Constantine":  "https://media.api-sports.io/football/teams/911.png",
    "Paradou AC":      "https://media.api-sports.io/football/teams/915.png",
    "ASO Chlef":       "https://media.api-sports.io/football/teams/925.png",
    "MC Oran":         "https://media.api-sports.io/football/teams/907.png",
    "JS Saoura":       "https://media.api-sports.io/football/teams/914.png",
}

# ══════════════════════════════════════════════
# CLOUDSCRAPER
# ══════════════════════════════════════════════

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# ══════════════════════════════════════════════
# PARSE
# ══════════════════════════════════════════════

def extract_coach_id(href):
    """Extrait l'ID depuis /entraineur/nom-prenom-12345"""
    m = re.search(r"/entraineur/[^/]+-(\d+)/?$", href)
    if m:
        return m.group(1)
    m = re.search(r"/entraineur/([^/]+)/?$", href)
    return m.group(1) if m else None

def get_photo(coach_id, coach_name):
    """Photo depuis cdn.resfu.com — même pattern que joueurs"""
    if coach_id and coach_id.isdigit():
        return f"https://cdn.resfu.com/img_data/coaches/medium/{coach_id}.jpg?size=120x&lossy=1"
    return ""

def clean_club_name(raw):
    """Essaie de mapper le nom BeSoccer vers le nom interne."""
    raw = raw.strip()
    # Match direct
    if raw in CLUB_NAME_MAP:
        return CLUB_NAME_MAP[raw]
    # Match partiel
    for key, val in CLUB_NAME_MAP.items():
        if key.lower() in raw.lower() or raw.lower() in key.lower():
            return val
    return raw

def scrape_coaches():
    print(f"Fetch: {URL}")
    r = scraper.get(URL, timeout=20)
    print(f"Status: {r.status_code} | Size: {len(r.text)} chars")
    if r.status_code != 200:
        print("❌ Erreur fetch")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    coaches = []
    seen = set()

    for a in soup.select("a[href*='/entraineur/']"):
        href = a.get("href", "")
        coach_id = extract_coach_id(href)
        if not coach_id:
            continue

        # Texte du lien : "Nom CoachClub" (concaténé)
        # On cherche p ou span avec le nom et le club séparément
        name_el = a.select_one("p.pl-name, p.name, span.name, p:first-child")
        club_el = a.select_one("p.team-name, span.team, p:last-child")

        if name_el and club_el and name_el != club_el:
            coach_name = name_el.get_text(strip=True)
            club_raw   = club_el.get_text(strip=True)
        else:
            # Fallback : split texte brut
            full_text = a.get_text("|", strip=True)
            parts     = [p.strip() for p in full_text.split("|") if p.strip()]
            if len(parts) >= 2:
                coach_name = parts[0]
                club_raw   = parts[-1]
            elif len(parts) == 1:
                coach_name = parts[0]
                club_raw   = ""
            else:
                continue

        if not coach_name or len(coach_name) < 2:
            continue
        if coach_id in seen:
            continue
        seen.add(coach_id)

        club_name = clean_club_name(club_raw)
        photo     = get_photo(coach_id, coach_name)
        club_logo = CLUB_LOGOS.get(club_name, "")

        coaches.append({
            "id":          int(coach_id) if coach_id.isdigit() else coach_id,
            "coach_name":  coach_name,
            "coach_id":    coach_id,
            "photo":       photo,
            "club":        club_name,
            "club_logo":   club_logo,
            "url":         href,
            "scraped_at":  datetime.now(timezone.utc).isoformat(),
        })
        print(f"  ✅ {coach_name} → {club_name}")

    print(f"\n→ {len(coaches)} entraîneur(s) trouvé(s)")
    return coaches

# ══════════════════════════════════════════════
# SUPABASE
# ══════════════════════════════════════════════

def upsert_coaches(rows):
    if not rows:
        return
    res = requests.post(
        SB_URL + "/rest/v1/algeria_coaches",
        headers=SB_HEADERS,
        json=rows,
        timeout=20
    )
    code = res.status_code
    if code in (200, 201, 204):
        print(f"✅ Supabase OK ({len(rows)} coaches)")
    else:
        print(f"❌ Supabase {code}: {res.text[:300]}")

# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

print("=== BeSoccer Coaches — Ligue 1 Algérie ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

coaches = scrape_coaches()

if coaches:
    # D'abord vider la table (on veut toujours l'état actuel)
    requests.delete(
        SB_URL + "/rest/v1/algeria_coaches?id=gte.0",
        headers={**SB_HEADERS, "Prefer": ""},
        timeout=10
    )
    upsert_coaches(coaches)

with open("coaches_debug.json", "w", encoding="utf-8") as f:
    json.dump(coaches, f, ensure_ascii=False, indent=2)
print("Debug JSON : coaches_debug.json")