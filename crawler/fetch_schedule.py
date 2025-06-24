import json, datetime as dt, re, sys, requests
from bs4 import BeautifulSoup as BS   # KBS에서 그대로 사용

UA = "schedule-bot/1.2 (+github actions)"
HEAD = {"User-Agent": UA}
TODAY = dt.date.today()
MONDAY = TODAY - dt.timedelta(days=TODAY.weekday())
FMT = "%Y/%-m/%-d"   # 0-패딩 없는 년/월/일

TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")   # ← 01:00 / 9:00 모두 OK
def clean(t): return re.sub(r"\\s+", " ", t.strip())

def fetch_sbs():
    ymd = f"{MONDAY.year}/{MONDAY.month}/{MONDAY.day}"      # 2025/6/23
    url = f"https://static.cloud.sbs.co.kr/schedule/{ymd}/Power.json"

    try:
        resp = requests.get(url, headers=HEAD, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[SBS] request failed: {e}", file=sys.stderr)
        return {"prefix": "sbs/powerfm", "programs": []}

    items = data if isinstance(data, list) else data.get("schedulerPrograms", [])

    programs = [
        {"name": itm.get("title", "").strip(),
         "time": itm.get("start_time", "").strip()}
        for itm in items
        if TIME_RE.match(itm.get("start_time", "")) and itm.get("title")
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
