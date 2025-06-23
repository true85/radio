#!/usr/bin/env python3
"""SBS Power FM & KBS Cool FM 주간 편성표 스크래퍼 → schedule.json 저장

• SBS  : https://www.sbs.co.kr/schedule/index.html?channel=Power&pmDate=YYYYMMDD&type=ra
• KBS  : https://schedule.kbs.co.kr/?sname=schedule&stype=table&ch_code=24&date=YYYYMMDD

결과 구조
{
  "sbs": {
    "prefix": "sbs/powerfm",
    "programs": [
       {"name": "김영철의 파워FM", "time": "07:00"},
       …
    ]
  },
  "kbs": {
    "prefix": "kbs/25",
    "programs": [ … ]
  }
}
"""
import json, datetime as dt, requests
from bs4 import BeautifulSoup as BS

# ── Helper
TODAY   = dt.date.today()
MONDAY  = TODAY - dt.timedelta(days=TODAY.weekday())  # 이번 주 월요일
FMT     = "%Y%m%d"
HEADERS = {"User-Agent": "schedule-bot/1.0 (+github actions)"}

# ── SBS Scraper ────────────────────────────────────────────────────────────
def fetch_sbs():
    url = f"https://www.sbs.co.kr/schedule/index.html?channel=Power&pmDate={MONDAY.strftime(FMT)}&type=ra"
    html = requests.get(url, headers=HEADERS, timeout=15).text
    soup = BS(html, "html.parser")
    rows = soup.select("table.schedule_tbl tbody tr")
    programs = []
    for tr in rows:
        time = tr.select_one("th.time").get_text(strip=True)
        name = tr.select_one("td.show a, td.show span").get_text(strip=True)
        if time and name:
            programs.append({"name": name, "time": time})
    return {"prefix": "sbs/powerfm", "programs": programs}

# ── KBS Scraper ────────────────────────────────────────────────────────────
def fetch_kbs():
    url = f"https://schedule.kbs.co.kr/?sname=schedule&stype=table&ch_code=24&date={MONDAY.strftime(FMT)}"
    html = requests.get(url, headers=HEADERS, timeout=15).text
    soup = BS(html, "html.parser")
    rows = soup.select("table tbody tr")
    programs = []
    for tr in rows:
        tcell = tr.select_one("th")
        ncell = tr.select_one("td.prog a, td.prog")
        time = tcell.get_text(strip=True) if tcell else ""
        name = ncell.get_text(strip=True) if ncell else ""
        if time and name:
            programs.append({"name": name, "time": time})
    return {"prefix": "kbs/25", "programs": programs}

# ── Main ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    schedule = {
        "sbs": fetch_sbs(),
        "kbs": fetch_kbs(),
    }
    with open("schedule.json", "w", encoding="utf-8") as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)
    print("schedule.json updated ✔")
