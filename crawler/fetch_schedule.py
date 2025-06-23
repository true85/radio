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

# ── SBS JSON Scraper ───────────────────────────────────────────
def fetch_sbs():
    y, m, d = MONDAY.year, MONDAY.month, MONDAY.day           # 주간 기준 날짜
    url = f"https://static.cloud.sbs.co.kr/schedule/{y}/{m}/{d}/Power.json"
    data = requests.get(url, headers=HEAD, timeout=20).json()
    programs = [
        {"name": item["programName"], "time": item["stdHours"]}
        for item in data.get("schedulerPrograms", [])
        if TIME_RE.match(item.get("stdHours", ""))            # HH:MM 필터
    ]
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
