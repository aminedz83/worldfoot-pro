import cloudscraper, re
from datetime import date, datetime

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

today = date.today().strftime("%Y-%m-%d")
print("Aujourd'hui:", today)

# Récupérer la page Flashscore CA fixtures
r = scraper.get("https://www.flashscore.ca/soccer/algeria/ligue-1/fixtures/", timeout=20)
print(f"Status: {r.status_code} | Taille: {len(r.text)}")

html = r.text

# Parser tous les matchs: AA=mid, AD=timestamp, CX=home, AF=away
entries = []
blocks = html.split("~")
for block in blocks:
    if "AA÷" not in block:
        continue
    fields = {}
    for field in block.split("¬"):
        if "÷" in field:
            key, _, val = field.partition("÷")
            fields[key.strip()] = val.strip()
    if "AA" in fields:
        entries.append(fields)

print(f"\nTotal matchs: {len(entries)}")

# Afficher tous les matchs à venir
print("\n=== Prochains matchs Ligue 1 Algérie ===")
future_matches = []
for e in entries:
    mid = e.get("AA", "")
    ts = int(e.get("AD", 0))
    home = e.get("CX", e.get("WM", "?"))
    away = e.get("AF", e.get("WN", "?"))
    
    if ts:
        match_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        match_time = datetime.fromtimestamp(ts).strftime("%H:%M")
        if match_date >= today:
            future_matches.append({
                "mid": mid,
                "date": match_date,
                "time": match_time,
                "home": home,
                "away": away,
                "ts": ts
            })

future_matches.sort(key=lambda x: x["ts"])
for m in future_matches:
    print(f"  {m['date']} {m['time']} | {m['home']} vs {m['away']} | mid={m['mid']}")

# Matchs d'aujourd'hui spécifiquement
today_matches = [m for m in future_matches if m["date"] == today]
print(f"\nMatchs aujourd'hui ({today}): {len(today_matches)}")
for m in today_matches:
    print(f"  {m['time']} | {m['home']} vs {m['away']} | mid={m['mid']}")