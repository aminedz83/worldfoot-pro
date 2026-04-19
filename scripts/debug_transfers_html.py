#!/usr/bin/env python3
import cloudscraper
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

url = "https://www.besoccer.com/team/transfers/belouizdad/11507/2026"
print(f"Fetch: {url}")
r = scraper.get(url, timeout=20)
print(f"Status: {r.status_code} | Size: {len(r.text)} chars")

soup = BeautifulSoup(r.text, "html.parser")

print("\n--- TOUS LES li.elem-title ---")
for li in soup.select("li.elem-title"):
    print(f"  repr: {repr(li.get_text(strip=True))}")

print("\n--- TOUS LES li.elem-title.mt10 ---")
for li in soup.select("li.elem-title.mt10"):
    print(f"  repr: {repr(li.get_text(strip=True))}")

print("\n--- PREMIERS 5 li.sign-list ---")
for li in soup.select("li.sign-list")[:5]:
    print(f"  TEXT: {li.get_text(' ', strip=True)[:120]}")
    player = li.select_one("a[href*='/player/']")
    print(f"  PLAYER LINK: {player.get('href','') if player else 'None'}")
    print(f"  PLAYER TEXT: {player.get_text('|', strip=True)[:80] if player else 'None'}")
    p_tag = li.select_one("p.name")
    print(f"  p.name: {p_tag.get_text(strip=True) if p_tag else 'None'}")
    dt = li.select_one("div.data-transfer")
    print(f"  data-transfer: {dt.get_text(strip=True) if dt else 'None'}")
    teams = li.select("a[href*='/team/']")
    for t in teams:
        print(f"  TEAM: {t.get('href','')} → '{t.get_text(strip=True)[:40]}'")
    print()

# Sauver HTML brut
with open("besoccer_transfers_raw.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("HTML sauvé")