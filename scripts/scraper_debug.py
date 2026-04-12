"""
scraper_debug.py - Fix score regex + subs format alternatif
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
        c = s.strip().replace("'","")
        if not c or c in ("Half-time","Kick-off","FT"): return None
        if "+" in c:
            p = c.split("+")
            return int(p[0]) + (int(p[1]) if len(p)>1 and p[1].strip() else 0)
        return int(c)
    except: return None

def extract_player_id(href):
    if not href: return None
    m = re.search(r"/player/[^/]+-(\d+)/?$", href)
    if m: return m.group(1)
    m = re.search(r"/player/([^/]+)/?$", href)
    return m.group(1) if m else None

def parse_player(link):
    href = link.get("href","")
    pid  = extract_player_id(href)
    nom_el = link.select_one("p.name")
    nom    = nom_el.get_text(strip=True) if nom_el else link.get_text(strip=True)
    if not pid or not nom: return None

    img   = link.select_one("div.bench-player img")
    photo = img["src"] if img and img.get("src") else ""
    if photo and photo.startswith("//"): photo = "https:"+photo
    if not photo or "nofoto" in photo:
        photo = f"https://cdn.resfu.com/img_data/players/medium/{pid}.jpg?size=120x&lossy=1"

    number=""; pos=""
    role_box = link.select_one("div.role-box span.t-up")
    if role_box:
        num_el = role_box.select_one("span.number")
        if num_el: number = num_el.get_text(strip=True)
        rt = role_box.get_text(strip=True)
        if num_el: rt = rt.replace(number,"").strip()
        pos = rt

    goals=0; goal_minutes=[]; yellow=False; yellow_minute=None
    red=False; red_minute=None; sub_out_minute=None

    info = link.select_one("div.info-wrapper")
    if info:
        for img_ev in info.select("img.ic-bench"):
            parent = img_ev.parent
            min_el = parent.select_one("p.min") if parent else None
            mv     = parse_minute(min_el.get_text(strip=True) if min_el else "")
            alt = img_ev.get("alt","").lower()
            src = img_ev.get("src","").lower()
            if "goal" in alt or "accion1" in src:
                if mv is not None: goals+=1; goal_minutes.append(mv)
            elif "yellow" in alt or "accion5" in src:
                yellow=True; yellow_minute=mv
            elif "red" in alt or "tarjeta_r" in src:
                red=True; red_minute=mv
            elif "sub" in alt or "cambio" in src:
                sub_out_minute=mv

    note_el = link.select_one("div.match-points")
    note=None
    if note_el:
        try: note=float(note_el.get_text(strip=True))
        except: pass

    return {"name":nom,"id":pid,"number":number,"pos":pos,"photo":photo,
            "goals":goals,"goal_minutes":goal_minutes,
            "yellow":yellow,"yellow_minute":yellow_minute,
            "red":red,"red_minute":red_minute,
            "sub_out":sub_out_minute is not None,"sub_out_minute":sub_out_minute,
            "minutes":90,"rating":note}

def scrape_events_page(base_url, home_team, away_team):
    url = base_url.rstrip("/") + "/events"
    r   = fetch(url)
    if not r: return {}, [], {"home":0,"away":0}

    soup   = BeautifulSoup(r.text, "html.parser")
    events = []
    sub_in_minutes = {}
    seen = set()

    # ── Score : prendre le DERNIER mini-result (= score final) ──
    score = {"home":0,"away":0}
    all_mini = soup.select("div.mini-result")
    if all_mini:
        # Le premier mini-result = dernier event chronologique = score final
        txt = all_mini[0].get_text(strip=True)
        m = re.search(r"(\d+)\s*-\s*(\d+)", txt)
        if m:
            score["home"]=int(m.group(1)); score["away"]=int(m.group(2))
    if score["home"]==0 and score["away"]==0:
        # Fallback: div.result
        result_el = soup.select_one("div.result")
        if result_el:
            txt = result_el.get_text(strip=True)
            nums = re.findall(r"\b(\d{1,2})\s*-\s*(\d{1,2})\b", txt)
            if nums:
                score["home"]=int(nums[-1][0]); score["away"]=int(nums[-1][1])
    print(f"  Score: {score['home']}-{score['away']}")

    # ── Events : format 1 (all-events) ──────────────────────
    for row in soup.select("div.table-played-match.all-events"):
        min_el = row.select_one("div.col-mid-rows div.min")
        if not min_el: continue
        minute = parse_minute(min_el.get_text(strip=True))
        if minute is None: continue

        img_ev = row.select_one("img[src*='events/']")
        if not img_ev: continue
        src = img_ev.get("src","").lower()
        alt = img_ev.get("alt","").lower()

        event_type = None
        if "accion1" in src or "goal" in alt: event_type = "goal"
        elif "accion5" in src or "yellow card" in alt: event_type = "yellow"
        elif "tarjeta_r" in src or ("red card" in alt): event_type = "red"
        elif "cambio" in src or "substitution" in alt: event_type = "sub"
        if not event_type: continue

        # Côté domicile/extérieur
        left  = row.select_one("div.col-side.left")
        right = row.select_one("div.col-side.right")
        left_has  = left  and (left.select_one("a[data-cy='eventOrd']") or left.select_one("div.name-wrapper"))
        right_has = right and (right.select_one("a[data-cy='eventOrd']") or right.select_one("div.name-wrapper"))
        is_home = bool(left_has) and not bool(right_has)

        if event_type == "sub":
            # Méthode 1: popup avec player_id dans l'ID
            popup = row.select_one("div[id^='popup_event_order']")
            if popup:
                pid_m = re.search(r"_(\d+)_(\d+)$", popup.get("id",""))
                if pid_m:
                    sub_min = int(pid_m.group(1))
                    sub_pid = pid_m.group(2)
                    key = f"sub_{sub_min}_{sub_pid}"
                    if key not in seen:
                        seen.add(key)
                        sub_in_minutes[sub_pid] = sub_min
                        print(f"    🔄 {sub_min}' pid={sub_pid} ({'dom' if is_home else 'ext'})")
            else:
                # Méthode 2: extraire player_id depuis href du lien joueur
                side = left if is_home else right
                if side:
                    for lnk in side.select("a[href*='/player/']"):
                        pid2 = extract_player_id(lnk.get("href",""))
                        if pid2:
                            key = f"sub_{minute}_{pid2}"
                            if key not in seen:
                                seen.add(key)
                                sub_in_minutes[pid2] = minute
                                nm = lnk.get_text(strip=True)
                                print(f"    🔄 {minute}' pid={pid2} nom={nm} ({'dom' if is_home else 'ext'})")
            continue

        # Buts / cartons
        side = left if is_home else right
        player_link = side.select_one("a[data-cy='eventOrd']") if side else None
        player_name = player_link.get_text(strip=True) if player_link else ""

        key = f"{event_type}_{minute}_{player_name}"
        if key in seen: continue
        seen.add(key)

        mini = row.select_one("div.mini-result")
        events.append({
            "type":event_type,"minute":minute,
            "team":home_team if is_home else away_team,
            "is_home":is_home,"player":player_name,"assist":"",
            "score":mini.get_text(strip=True) if mini else ""
        })
        icon = {"goal":"⚽","yellow":"🟨","red":"🟥"}.get(event_type,"?")
        print(f"    {icon} {minute}' {player_name} ({'dom' if is_home else 'ext'})")

    print(f"  📊 {len(events)} events | {len(sub_in_minutes)} subs")
    return sub_in_minutes, events, score

def scrape_match(t):
    base = f"https://www.besoccer.com/match/{t['bs_home']}/{t['bs_away']}/{t['match_id']}"
    r    = fetch(base+"/lineups")
    if not r: return None

    soup = BeautifulSoup(r.text, "html.parser")
    starters = soup.select('a.col-bench[data-cy="starterPlayer"]')
    print(f"  Titulaires: {len(starters)}")
    if len(starters) < 11: return None

    sub_in_minutes, live_events, score = scrape_events_page(base, t["home_team"], t["away_team"])

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
        p=parse_player(link); 
        if p: result["home_players"].append(p)
    for link in soup.select('a.col-bench.visitor[data-cy="starterPlayer"]'):
        p=parse_player(link)
        if p: result["away_players"].append(p)
    for link in soup.select('a.col-bench.local[data-cy="benchPlayer"]'):
        p=parse_player(link)
        if p:
            sm=sub_in_minutes.get(p["id"])
            p["minutes"]=sm if sm else 0; p["sub_in_minute"]=sm
            result["home_subs"].append(p)
    for link in soup.select('a.col-bench.visitor[data-cy="benchPlayer"]'):
        p=parse_player(link)
        if p:
            sm=sub_in_minutes.get(p["id"])
            p["minutes"]=sm if sm else 0; p["sub_in_minute"]=sm
            result["away_subs"].append(p)

    hs=sum(1 for p in result["home_subs"] if p.get("sub_in_minute"))
    as_=sum(1 for p in result["away_subs"] if p.get("sub_in_minute"))
    yc=sum(1 for p in result["home_players"]+result["away_players"] if p.get("yellow"))
    gc=sum(p.get("goals",0) for p in result["home_players"]+result["away_players"]+result["home_subs"]+result["away_subs"])
    print(f"  ✅ {hs}+{as_} subs | {gc} buts | {yc} cartons | {score['home']}-{score['away']}")
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
    {"match_id":"2026264214","bs_home":"kabylie","bs_away":"cs-constantine",
     "home_team":"JS Kabylie","away_team":"CS Constantine","match_date":"2026-04-10"},
]

print("=== DEBUG: Re-scrape fix score + subs ===")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
for t in TARGETS:
    print(f"\n--- {t['home_team']} vs {t['away_team']} ---")
    lineup = scrape_match(t)
    if lineup: force_save(lineup)
    else: print("  ❌ Scrape échoué")
    time.sleep(3)
print("\n=== Terminé ===")