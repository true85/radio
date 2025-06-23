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

# ── SBS Scraper (div 구조 대응) ──────────────────────────────
def fetch_sbs():
    url = (
        f"https://www.sbs.co.kr/schedule/index.html"
        f"?type=ra&channel=Power&pmDate={MONDAY.strftime(FMT)}"
    )
    html = requests.get(url, headers=HEAD, timeout=20).text
    soup = BS(html, "html.parser")

    root = soup.select_one("#sbs-scheduler-schedulerList-self")
    if not root:
        print("[SBS] root div not found", file=sys.stderr)
        return {"prefix": "sbs/powerfm", "programs": []}

    programs = []
    for box in root.select("div.scheduler_program_w"):
        time_el  = box.select_one(".spt_hours")
        title_el = box.select_one(".spi_title_w .spi_title, .spi_title_w strong")
        time  = clean(time_el.text)  if time_el  else ""
        title = clean(title_el.text) if title_el else ""
        # 일자별 'AM/PM' 표기가 붙을 때가 있어 시간만 남깁니다 (HH:MM 형태)
        time = re.sub(r"[^0-9:]", "", time)
        if TIME_RE.match(time) and title:
            programs.append({"name": title, "time": time})

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
