import json, datetime as dt, re, sys, requests
from bs4 import BeautifulSoup as BS   # KBS에서 그대로 사용

UA = "schedule-bot/1.2 (+github actions)"
HEAD = {"User-Agent": UA}
TODAY = dt.date.today()
MONDAY = TODAY - dt.timedelta(days=TODAY.weekday())
FMT = "%Y/%-m/%-d"   # 0-패딩 없는 년/월/일

TIME_RE = re.compile(r"^\\d{2}:\\d{2}$")
def clean(t): return re.sub(r"\\s+", " ", t.strip())

# ── robust SBS JSON ───────────────────────────────────────────
def fetch_sbs():
    ymd = MONDAY.strftime(FMT)               # e.g. 2025/6/23
    url = f"https://static.cloud.sbs.co.kr/schedule/{ymd}/Power.json"
    try:
        resp = requests.get(url, headers=HEAD, timeout=20)
        resp.raise_for_status()              # 4xx/5xx → exception
        data = resp.json()
    except Exception as e:
        print(f"[SBS] request failed: {e}", file=sys.stderr)
        return {"prefix": "sbs/powerfm", "programs": []}

    progs = [
        {"name": item["programName"], "time": item["stdHours"]}
        for item in data.get("schedulerPrograms", [])
        if TIME_RE.match(item.get("stdHours", ""))
    ]
    print(f"[SBS] parsed {len(progs)} rows")
    return {"prefix": "sbs/powerfm", "programs": progs}



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
