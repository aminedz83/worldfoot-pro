#!/usr/bin/env python3
"""
besoccer_coaches.py
===================
Scrape les entraîneurs actuels Ligue 1 Algérie depuis BeSoccer.
URL : https://fr.besoccer.com/competition/entreineurs/algeria-league-one

Structure HTML réelle (vérifiée 19/04/2026) :
  a.item-box[data-cy="coach"]
    img.player-circle-box          → photo (ou nofoto_jugador si absent)
    div.name.bold.ml10             → nom
    div.ml5                        → club
"""

import os, re, json, requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL       = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS   = {
    "apikey":        SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates"
}

URL = "https://fr.besoccer.com/competition/entreineurs/algeria-league-one"

CLUB_NAME_MAP = {
    "Chlef": "ASO Chlef", "ASO Chlef": "ASO Chlef",
    "JS Saoura": "JS Saoura", "Saoura": "JS Saoura",
    "CR Belouizdad": "CR Belouizdad", "Belouizdad": "CR Belouizdad",
    "MC Alger": "MC Alger",
    "JS Kabylie": "JS Kabylie", "Kabylie": "JS Kabylie",
    "ES Setif": "ES Setif", "Sétif": "ES Setif",
    "USM Alger": "USM Alger",
    "CS Constantine": "CS Constantine", "Constantine": "CS Constantine",
    "MC Oran": "MC Oran",
    "ES Mostaganem": "ES Mostaganem", "Mostaganem": "ES Mostaganem",
    "MB Rouissat": "MB Rouissat", "MB Rouisset": "MB Rouissat",
    "ES Ben Aknoun": "ES Ben Aknoun", "Ben Aknoun": "ES Ben Aknoun",
    "USM Khenchela": "USM Khenchela", "Khenchela": "USM Khenchela",
    "Paradou AC": "Paradou AC", "Paradou": "Paradou AC",
    "Olympique Akbou": "Olympique Akbou", "Oued Akbou": "Olympique Akbou",
    "MC El Bayadh": "MC El Bayadh", "El Bayadh": "MC El Bayadh",
}

CLUB_LOGOS = {
    "MC Alger":       "https://media.api-sports.io/football/teams/906.png",
    "CR Belouizdad":  "https://media.api-sports.io/football/teams/904.png",
    "JS Kabylie":     "https://media.api-sports.io/football/teams/918.png",
    "USM Alger":      "https://media.api-sports.io/football/teams/910.png",
    "ES Setif":       "https://media.api-sports.io/football/teams/905.png",
    "CS Constantine": "https://media.api-sports.io/football/teams/911.png",
    "Paradou AC":     "https://media.api-sports.io/football/teams/915.png",
    "ASO Chlef":      "https://media.api-sports.io/football/teams/925.png",
    "MC Oran":        "https://media.api-sports.io/football/teams/907.png",
    "JS Saoura":      "https://media.api-sports.io/football/teams/914.png",
}

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

def extract_coach_id(href):
    m = re.search(r"/entraineur/[^/]+-(\d+)/?$", href)
    if m:
        return m.group(1)
    m = re.search(r"/entraineur/([^/]+)/?$", href)
    return m.group(1) if m else None

def clean_club(raw):
    raw = raw.strip()
    if raw in CLUB_NAME_MAP:
        return CLUB_NAME_MAP[raw]
    for key, val in CLUB_NAME_MAP.items():
        if key.lower() in raw.lower() or raw.lower() in key.lower():
            return val
    return raw

def scrape_coaches():
    print(f"Fetch: {URL}")
    r = scraper.get(URL, timeout=20)
    print(f"Status: {r.status_code} | Size: {len(r.text)} chars")
    if r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    coaches = []
    seen = set()

    for a in soup.select("a.item-box[data-cy='coach']"):
        href      = a.get("href", "")
        coach_id  = extract_coach_id(href)
        if not coach_id or coach_id in seen:
            continue
        seen.add(coach_id)

        # Nom
        name_el = a.select_one("div.name.bold")
        if not name_el:
            name_el = a.select_one("div.bold")
        coach_name = name_el.get_text(strip=True) if name_el else ""
        if not coach_name:
            continue

        # Photo — prendre la src directement, ignorer nofoto
        photo = ""
        img = a.select_one("img.player-circle-box")
        if img:
            src = img.get("src", "")
            if src and "nofoto" not in src:
                photo = src
                # Passer en taille plus grande
                photo = photo.replace("size=60x", "size=120x")

        # Club — div.ml5 contient le texte du club
        club_raw = ""
        ml5 = a.select_one("div.ml5")
        if ml5:
            club_raw = ml5.get_text(strip=True)
        club_name = clean_club(club_raw)

        # Logo club : API-sports en priorité, sinon escudo BeSoccer
        club_logo = CLUB_LOGOS.get(club_name, "")
        if not club_logo:
            shield = a.select_one("img[src*='escudos']")
            if shield:
                src = shield.get("src", "")
                if src.startswith("//"):
                    src = "https:" + src
                club_logo = src.replace("size=60x", "size=120x")

        # ID numérique pour Supabase BIGINT
        try:
            uid = int(coach_id)
        except ValueError:
            import hashlib
            uid = int(hashlib.md5(coach_id.encode()).hexdigest()[:15], 16)

        coaches.append({
            "id":         uid,
            "coach_name": coach_name,
            "coach_id":   coach_id,
            "photo":      photo,
            "club":       club_name,
            "club_logo":  club_logo,
            "url":        href,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"  ✅ {coach_name} → {club_name} | photo: {'oui' if photo else 'non'}")

    print(f"\n→ {len(coaches)} entraîneur(s)")
    return coaches

def upsert_coaches(rows):
    if not rows:
        return
    # Vider d'abord
    requests.delete(
        SB_URL + "/rest/v1/algeria_coaches?id=gte.0",
        headers={**SB_HEADERS, "Prefer": ""},
        timeout=10
    )
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

print("=== BeSoccer Coaches — Ligue 1 Algérie ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

coaches = scrape_coaches()
if coaches:
    upsert_coaches(coaches)

with open("coaches_debug.json", "w", encoding="utf-8") as f:
    json.dump(coaches, f, ensure_ascii=False, indent=2)
print("Debug JSON : coaches_debug.json")