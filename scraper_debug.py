import requests
from datetime import date, datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Accept": "application/json",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer": "https://www.sofascore.com/",
}

today_str = date.today().strftime("%Y-%m-%d")
print("=== Test SofaScore Ligue 1 Algérie ===")
print("Date:", today_str)

# Test 1: Matchs par date
print("\n--- Endpoint par date ---")
url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today_str}"
r = requests.get(url, headers=HEADERS, timeout=10)
print("Status:", r.status_code)
if r.status_code == 200:
    events = r.json().get("events", [])
    algeria = [e for e in events if e.get("tournament", {}).get("uniqueTournament", {}).get("id") == 841]
    print("Matchs Ligue 1 Algérie:", len(algeria))
    for e in algeria:
        print(" ", e["homeTeam"]["name"], "vs", e["awayTeam"]["name"], "| ID:", e["id"])

# Test 2: Par round (journée 25-27)
print("\n--- Endpoint par journée ---")
for rnd in range(24, 28):
    url = f"https://api.sofascore.com/api/v1/tournament/841/season/79568/events/round/{rnd}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code == 200:
        events = r.json().get("events", [])
        print(f"Round {rnd}: {len(events)} matchs")
        for e in events:
            ts = e.get("startTimestamp", 0)
            d = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
            status = e.get("status", {}).get("type", "?")
            print(f"  [{status}] {d} | {e['homeTeam']['name']} vs {e['awayTeam']['name']} | ID={e['id']}")

# Test 3: Lineups d'un match SofaScore
print("\n--- Test lineups SofaScore ---")
# Prendre le premier match trouvé
url = "https://api.sofascore.com/api/v1/tournament/841/season/79568/events/round/25"
r = requests.get(url, headers=HEADERS, timeout=10)
if r.status_code == 200:
    events = r.json().get("events", [])
    if events:
        event_id = events[0]["id"]
        home = events[0]["homeTeam"]["name"]
        away = events[0]["awayTeam"]["name"]
        print(f"Match: {home} vs {away} (ID={event_id})")
        lineup_url = f"https://api.sofascore.com/api/v1/event/{event_id}/lineups"
        r2 = requests.get(lineup_url, headers=HEADERS, timeout=10)
        print("Lineups status:", r2.status_code)
        if r2.status_code == 200:
            data = r2.json()
            home_players = data.get("home", {}).get("players", [])
            away_players = data.get("away", {}).get("players", [])
            print(f"Joueurs dom: {len(home_players)} | ext: {len(away_players)}")
            for p in home_players[:3]:
                name = p.get("player", {}).get("name", "?")
                pos = p.get("position", "?")
                print(f"  {name} ({pos})")