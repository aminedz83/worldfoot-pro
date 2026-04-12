"""
scraper_debug.py
================
Fix score + re-scrape complet avec cartons/changements depuis lineups page.
"""

import os, re, time, requests
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timezone

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL       = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS   = {
    "apikey":        SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type":  "application/json",
}

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

def fetch(url):
    try:
        r = scraper.get(url, timeout=20)
        print(f"  GET {r.status_code} : {url}")
        return r if r.status_code == 200 else None
    except Exception as e:
        print(f"  Erreur: {e}"); return None

def parse_minute(s):
    try:
        c = s.replace("'","").strip()
        if not c or c in ("Half-time","Kick-off","FT"): return None
        if "+" in c:
            p = c.split("+")
            return int(p[0]) + (int(p[1]) if len(p)>1 and p[1] else 0)
        return int(c)
    except: return None

def extract_player_id(href):
    if not href: return None
    m = re.search(r"/player/[^/]+-(\d+)/?$", href)
    if m: return m.group(1)
    m = re.search(r"/player/([^/]+)/?$", href)
    return m.group(1) if m else None

def parse_player(link):
    href      = link.get("href","")
    player_id = extract_player_id(href)
    nom_el    = link.select_one("p.name")
    nom       = nom_el.get_text(strip=True) if nom_el else link.get_text(strip=True)
    if not player_id or not nom: return None

    img   = link.select_one("div.bench-player img")
    photo = img["src"] if img and img.get("src") else ""
    if photo and photo.startswith("//"): photo = "https:"+photo
    if not photo or "nofoto" in photo:
        photo = f"https://cdn.resfu.com/img_data/players/medium/{player_id}.jpg?size=120x&lossy=1"

    number=""; pos=""
    role_box = link.select_one("div.role-box span.t-up")
    if role_box:
        num_el = role_box.select_one("span.number")
        if num_el: number = num_el.get_text(strip=True)
        role_text = role_box.get_text(strip=True)
        if num_el: role_text = role_text.replace(number,"").strip()
        pos = role_text

    goals=0; goal_minutes=[]; yellow=False; yellow_minute=None
    red=False; red_minute=None; sub_out_minute=None

    info = link.select_one("div.info-wrapper")
    if info:
        for img_ev in info.select("img.ic-bench"):
            parent  = img_ev.parent
            min_el  = parent.select_one("p.min") if parent else None
            mv      = parse_minute(min_el.get_text(strip=True) if min_el else "")
            alt = img_ev.get("alt","").lower()
            src = img_ev.get("src","").lower()
            if "goal" in alt or "gol" in alt or "accion1" in src:
                if mv is not None: goals+=1; goal_minutes.append(mv)
            elif "yellow" in alt or "amarilla" in alt or "tarjeta_a" in src or "event-5" in src:
                yellow=True; yellow_minute=mv
            elif "red" in alt or "roja" in alt or "tarjeta_r" in src or "event-3" in src:
                red=True; red_minute=mv
            elif "sub" in alt or "cambio" in src or "event-6" in src:
                sub_out_minute=mv

    note_el = link.select_one("div.match-points")
    note=None
    if note_el:
        try: note=float(note_el.get_text(strip=True))
        except: pass

    return {"name":nom,"id":player_id,"number":number,"pos":pos,"photo":photo,
            "goals":goals,"goal_minutes":goal_minutes,
            "yellow":yellow,"yellow_minute":yellow_minute,
            "red":red,"red_minute":red_minute,
            "sub_out":sub_out_minute is not None,"sub_out_minute":sub_out_minute,
            "minutes":90,"rating":note}

def scrape_events_page(base_url, home_team, away_team):
    """Scrape /events pour buts + score uniquement (cartons/subs viennent de lineups)"""
    url = base_url.rstrip("/") + "/events"
    r   = fetch(url)
    if not r: return [], {"home":0,"away":0}

    soup   = BeautifulSoup(r.text, "html.parser")
    events = []

    # ── Score : div.result → ex: "82'1 - 0" → extraire "1 - 0"
    score = {"home":0,"away":0}
    result_el = soup.select_one("div.result")
    if result_el:
        txt = result_el.get_text(strip=True)
        # Extraire le dernier "X - Y" dans le texte
        m = re.search(r"(\d+)\s*-\s*(\d+)(?!.*\d\s*-\s*\d)", txt)
        if m:
            score["home"] = int(m.group(1))
            score["away"] = int(m.group(2))
    print(f"  Score: {score['home']}-{score['away']}")

    # ── Events : parcourir chaque div.table-played-match ──
    for row in soup.select("div.table-played-match"):
        min_el = row.select_one("div.col-mid-rows div.min")
        minute = parse_minute(min_el.get_text(strip=True) if min_el else "")
        if minute is None: continue

        # Score partiel dans cet event
        mini = row.select_one("div.mini-result")
        mini_txt = mini.get_text(strip=True) if mini else ""

        # Type d'event via image
        img_ev = row.select_one("img[src*='events/']")
        if not img_ev: continue
        src = img_ev.get("src","").lower()
        alt = img_ev.get("alt","").lower()

        event_type = None
        if "accion1" in src or "goal" in alt: event_type = "goal"
        elif "tarjeta_a" in src or "event-5" in src or "yellow" in alt: event_type = "yellow"
        elif "tarjeta_r" in src or "event-3" in src or "red" in alt: event_type = "red"
        elif "cambio" in src or "event-8" in src or "sub" in alt: event_type = "sub"
        if not event_type: continue

        # Joueur — côté gauche = domicile, droit = extérieur
        left  = row.select_one("div.col-side.left")
        right = row.select_one("div.col-side.right")
        is_home = left and left.select_one("a[data-cy='eventOrd']") is not None

        side = left if is_home else right
        player_links = side.select("a[data-cy='eventOrd']") if side else []
        player_name  = player_links[0].get_text(strip=True) if player_links else ""
        assist_name  = player_links[1].get_text(strip=True) if len(player_links)>1 else ""

        events.append({
            "type": event_type, "minute": minute,
            "team": home_team if is_home else away_team,
            "is_home": is_home,
            "player": player_name, "assist": assist_name,
            "score": mini_txt
        })
        icon = {"goal":"⚽","yellow":"🟨","red":"🟥","sub":"🔄"}.get(event_type,"?")
        print(f"    {icon} {minute}' {player_name} ({'dom' if is_home else 'ext'}) {mini_txt}")

    return events, score

def match_sub_minute(name, sub_dict):
    if not name: return None
    if name in sub_dict: return sub_dict[name]
    nl = name.lower()
    for k,v in sub_dict.items():
        kl = k.lower() if k else ""
        lp=nl.split(".")[-1].strip(); lk=kl.split(".")[-1].strip()
        if (lp and lp in kl) or (lk and lk in nl): return v
    return None

def scrape_match(t):
    base = f"https://www.besoccer.com/match/{t['bs_home']}/{t['bs_away']}/{t['match_id']}"
    r    = fetch(base+"/lineups")
    if not r: return None

    soup = BeautifulSoup(r.text, "html.parser")
    starters = soup.select('a.col-bench[data-cy="starterPlayer"]')
    print(f"  Titulaires: {len(starters)}")
    if len(starters) < 11: return None

    live_events, score = scrape_events_page(base, t["home_team"], t["away_team"])

    # Extraire sub_in_minutes depuis les events
    sub_in_minutes = {}
    for e in live_events:
        if e["type"]=="sub" and e.get("assist"):
            sub_in_minutes[e["assist"]] = e["minute"]
            sub_in_minutes[e["player"]] = e["minute"]

    # Si pas de subs dans events → extraire depuis la page events directement
    if not sub_in_minutes:
        ev_url = base+"/events"
        rev = fetch(ev_url)
        if rev:
            esoup = BeautifulSoup(rev.text,"html.parser")
            for row in esoup.select("div.table-played-match"):
                img_ev = row.select_one("img[src*='events/']")
                if not img_ev: continue
                src = img_ev.get("src","").lower()
                if "cambio" not in src and "event-8" not in src: continue
                min_el = row.select_one("div.col-mid-rows div.min")
                minute = parse_minute(min_el.get_text(strip=True) if min_el else "")
                if not minute: continue
                all_links = row.select("a[data-cy='eventOrd']")
                for lnk in all_links:
                    nm = lnk.get_text(strip=True)
                    if nm: sub_in_minutes[nm] = minute

    result = {
        "match_id":t["match_id"],"home_team":t["home_team"],"away_team":t["away_team"],
        "match_date":t["match_date"],
        "home_players":[],"away_players":[],"home_subs":[],"away_subs":[],
        "home_formation":"","away_formation":"",
        "home_score":score["home"],"away_score":score["away"],
        "events":live_events,
        "scraped_at":datetime.now(timezone.utc).isoformat()
    }

    for link in soup.select('a.col-bench.local[data-cy="starterPlayer"]'):
        p=parse_player(link)
        if p: result["home_players"].append(p)
    for link in soup.select('a.col-bench.visitor[data-cy="starterPlayer"]'):
        p=parse_player(link)
        if p: result["away_players"].append(p)
    for link in soup.select('a.col-bench.local[data-cy="benchPlayer"]'):
        p=parse_player(link)
        if p:
            sm=match_sub_minute(p["name"],sub_in_minutes)
            p["minutes"]=sm if sm else 0; p["sub_in_minute"]=sm
            result["home_subs"].append(p)
    for link in soup.select('a.col-bench.visitor[data-cy="benchPlayer"]'):
        p=parse_player(link)
        if p:
            sm=match_sub_minute(p["name"],sub_in_minutes)
            p["minutes"]=sm if sm else 0; p["sub_in_minute"]=sm
            result["away_subs"].append(p)

    hp=len(result["home_players"]); ap=len(result["away_players"])
    hs=len(result["home_subs"]); as_=len(result["away_subs"])
    yc=sum(1 for p in result["home_players"]+result["away_players"] if p.get("yellow"))
    gc=sum(p.get("goals",0) for p in result["home_players"]+result["away_players"]+result["home_subs"]+result["away_subs"])
    print(f"  ✅ {hp}vs{ap} titulaires | {hs}+{as_} subs | {gc} buts | {yc} cartons | score {score['home']}-{score['away']}")
    return result

def force_save(lineup):
    res = requests.patch(
        SB_URL+f"/rest/v1/besoccer_lineups?match_id=eq.{lineup['match_id']}",
        headers={**SB_HEADERS,"Prefer":""},
        json=lineup
    )
    if res.status_code not in [200,201,204]:
        res = requests.post(
            SB_URL+"/rest/v1/besoccer_lineups",
            headers={**SB_HEADERS,"Prefer":"resolution=merge-duplicates"},
            params={"on_conflict":"match_id"},
            json=lineup
        )
    print(f"  Supabase: {'✅ OK' if res.status_code in [200,201,204] else '❌ '+str(res.status_code)+' '+res.text[:100]}")

TARGETS = [
    {"match_id":"2026264207","bs_home":"oued-akbou","bs_away":"es-setif",
     "home_team":"Olympique Akbou","away_team":"ES Setif","match_date":"2026-04-11"},
    {"match_id":"2026264211","bs_home":"paradou","bs_away":"js-saoura",
     "home_team":"Paradou AC","away_team":"JS Saoura","match_date":"2026-04-11"},
]

print("=== DEBUG: Re-scrape avec fix score + subs ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

for t in TARGETS:
    print(f"\n--- {t['home_team']} vs {t['away_team']} ---")
    lineup = scrape_match(t)
    if lineup: force_save(lineup)
    else: print("  ❌ Scrape échoué")
    time.sleep(3)

print("\n=== Terminé ===")