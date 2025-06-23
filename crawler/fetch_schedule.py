#!/usr/bin/env python3
"""📡 Weekly radio schedule scraper (SBS Power‑FM, KBS Cool‑FM)
Robust selectors + fallback to minimise empty list issues.
Generates schedule.json at repo root.
"""
import json, datetime as dt, re, sys, requests
from bs4 import BeautifulSoup as BS

UA = "schedule-bot/1.1 (+github actions)"
HEAD = {"User-Agent": UA}
TODAY = dt.date.today()
MONDAY = TODAY - dt.timedelta(days=TODAY.weekday())
FMT = "%Y%m%d"
TIME_RE = re.compile(r"^\d{2}:\d{2}$")

def clean(txt: str) -> str:
    return re.sub(r"\s+", " ", txt.strip())

# ── SBS ─────────────────────────────────────────────
def fetch_sbs():
    url = f"https://www.sbs.co.kr/m/schedule/index.html?channel=Power&pmDate={MONDAY.strftime(FMT)}&type=ra"
    html = requests.get(url, headers=HEAD, timeout=20).text
    soup = BS(html, "html.parser")

    table = soup.find("table", class_=lambda x: x and "schedule" in x)
    if not table:
        print("[SBS] table not found", file=sys.stderr)
        return {"prefix": "sbs/powerfm", "programs": []}

    programs = []
    for tr in table.select("tbody tr"):
        tcell = tr.find("th") or tr.find("td")
        ncell = tr.find("td", class_=re.compile("(show|tit)")) or tr.find("td")
        if not (tcell and ncell):
            continue
        time = clean(tcell.text)
        name = clean(ncell.text)
        if TIME_RE.match(time) and name:
            programs.append({"name": name, "time": time})
    print(f"[SBS] parsed {len(programs)} rows")
    return {"prefix": "sbs/powerfm", "programs": programs}

# ── KBS ─────────────────────────────────────────────

def fetch_kbs():
    url = f"https://schedule.kbs.co.kr/?sname=schedule&stype=table&ch_code=24&date={MONDAY.strftime(FMT)}"
    html = requests.get(url, headers=HEAD, timeout=20).text
    soup = BS(html, "html.parser")

    table = soup.find("table")
    if not table:
        print("[KBS] table not found", file=sys.stderr)
        return {"prefix": "kbs/25", "programs": []}

    programs = []
    for tr in table.select("tbody tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        time = clean(cells[0].text)
        name = clean(cells[1].text)
        if TIME_RE.match(time) and name:
            programs.append({"name": name, "time": time})
    print(f"[KBS] parsed {len(programs)} rows")
    return {"prefix": "kbs/25", "programs": programs}

# ── Main ────────────────────────────────────────────
if __name__ == "__main__":
    schedule = {"sbs": fetch_sbs(), "kbs": fetch_kbs()}
    with open("schedule.json", "w", encoding="utf-8") as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)
    print("schedule.json written ✔")
