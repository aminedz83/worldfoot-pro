import requests, os, re
from datetime import datetime, timezone, date
from bs4 import BeautifulSoup

SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SB_URL = "https://iqeqlsxjiklygywjirqs.supabase.co"
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-FR,fr;q=0.9"
}

def get_today_fixtures():
    url = "https://ca.soccerway.com/algeria/ligue-1/fixtures/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print("Soccerway status:", r.status_code)
        soup = BeautifulSoup(r.text, "html.parser")
        matches = []
        today_str = date.today().strftime("%Y-%m-%d")
        for row in soup.find_all("tr", class_=re.compile(r"match")):
            try:
                mid = None
                for link in row.find_all("a", href=re.compile(r"/game/|/matches/")):
                    href = link.get("href", "")
                    s = re.search(r"mid=([A-Za-z0-9]+)", href)
                    if s:
                        mid = s.group(1)
                        break
                if not mid:
                    continue
                team_links = row.find_all("a", href=re.compile(r"/teams/"))
                home, away = "", ""
                if len(team_links) >= 2:
                    home = team_links[0].get_text(strip=True)
                    away = team_links[1].get_text(strip=True)
                match_date = today_str
                dc = row.find("td", class_=re.compile(r"date"))
                if dc:
                    try:
                        match_date = datetime.strptime(dc.get_text(strip=True), "%d/%m/%Y").strftime("%Y-%m-%d")
                    except:
                        pass
                if match_date == today_str and mid and home:
                    matches.append({"mid": mid, "home": home, "away": away, "date": match_date})
                    print("Match:", home, "vs", away, "mid=" + mid)
            except:
                continue
        return matches
    except Exception as e:
        print("Erreur fixtures:", e)
        return []

def scrape_lineups(mid):
    url = "https://ca.soccerway.com/game/x/x/summary/lineups/?mid=" + mid
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        if not soup.find(string=re.compile(r"STARTING LINEUP", re.I)):
            print("Pas encore de lineups pour mid=" + mid)
            return None
        home_players, away_players = [], []
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                lt = cells[0].get_text(strip=True)
                rt = cells[-1].get_text(strip=True)
                if lt and len(lt) > 2:
                    m = re.match(r"^(\d{1,2})\s+(.+)$", lt)
                    if m:
                        home_players.append({"number": m.group(1), "name": m.group(2).strip(), "is_gk": "(G)" in lt})
                if rt and len(rt) > 2 and rt != lt:
                    m = re.match(r"^(.+?)\s+(\d{1,2})$", rt)
                    if m:
                        away_players.append({"number": m.group(2), "name": m.group(1).strip(), "is_gk": "(G)" in rt})
        if home_players or away_players:
            print("Lineups:", len(home_players), "dom,", len(away_players), "ext")
            return {"home_players": home_players[:11], "away_players": away_players[:11]}
        return None
    except Exception as e:
        print("Erreur lineups:", e)
        return None

print("=== Algeria Lineups", datetime.now().strftime("%H:%M:%S"), "===")
matches = get_today_fixtures()
print("Matchs aujourd'hui:", len(matches))
if not matches:
    print("Aucun match aujourd'hui - OK")
    exit(0)
for match in matches:
    mid, home, away, match_date = match["mid"], match["home"], match["away"], match["date"]
    print("\n---", home, "vs", away, "---")
    try:
        check = requests.get(
            SB_URL + "/rest/v1/algeria_lineups?soccerway_mid=eq." + mid + "&select=id,home_players",
            headers=SB_HEADERS
        ).json()
        if check and len(check) > 0 and check[0].get("home_players") and len(check[0]["home_players"]) > 0:
            print("Deja scraped")
            continue
    except:
        pass
    lineups = scrape_lineups(mid)
    if lineups:
        res = requests.post(SB_URL + "/rest/v1/algeria_lineups", headers=SB_HEADERS, json={
            "fixture_id": 0,
            "soccerway_mid": mid,
            "home_team": home,
            "away_team": away,
            "match_date": match_date,
            "home_players": lineups["home_players"],
            "away_players": lineups["away_players"],
            "scraped_at": datetime.now(timezone.utc).isoformat()
        })
        print("Sauvegarde:", res.status_code, "-", home, "vs", away)
    else:
        print("Pas encore disponible")
print("=== Termine ===")