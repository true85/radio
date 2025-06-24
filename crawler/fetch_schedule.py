#!/usr/bin/env python3
"""📡 Weekly radio schedule scraper (SBS Power-FM, KBS Cool-FM)
    • SBS  : static.cloud.sbs.co.kr JSON (per‑day)
    • KBS  : static.api.kbs.co.kr weekly endpoint (per‑day range)
Generates schedule.json in repo root.
"""
import json, datetime as dt, re, sys, requests
from pathlib import Path

# ─────────────────────────────────────────────────────────────
UA   = "schedule-bot/1.3 (+github actions)"
HEAD = {"User-Agent": UA}
TODAY   = dt.date.today()
MONDAY  = TODAY - dt.timedelta(days=TODAY.weekday())  # 이번 주 시작일 (월)
FMT_DAY = "%Y/%-m/%-d"        # SBS 경로용: 2025/6/24
FMT_API = "%Y%m%d"            # KBS query용: 20250624
TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")

def clean(t:str):
    return re.sub(r"\s+", " ", t.strip())

# ── 1. SBS Power FM ─────────────────────────────────────────

def fetch_sbs():
    ymd = MONDAY.strftime(FMT_DAY)                 # 2025/6/23
    url = f"https://static.cloud.sbs.co.kr/schedule/{ymd}/Power.json"
    try:
        data = requests.get(url, headers=HEAD, timeout=20).json()
    except Exception as e:
        print(f"[SBS] request failed: {e}", file=sys.stderr)
        return {"prefix": "sbs/powerfm", "programs": []}

    items = data if isinstance(data, list) else data.get("schedulerPrograms", [])
    progs = [
        {"name": itm.get("title", "").strip(),
         "time": itm.get("start_time", "").strip()[:5]}
        for itm in items
        if TIME_RE.match(itm.get("start_time", "")[:5]) and itm.get("title")
    ]
    print(f"[SBS] parsed {len(progs)} rows")
    return {"prefix": "sbs/powerfm", "programs": progs}

# ── 2. KBS Cool FM (channel 25) ─────────────────────────────

def fetch_kbs():
    date_str = MONDAY.strftime(FMT_API)            # 20250624
    url = (
        "https://static.api.kbs.co.kr/mediafactory/v1/schedule/weekly"
        f"?local_station_code=00&channel_code=24,25,26"
        f"&program_planned_date_from={date_str}&program_planned_date_to={date_str}"
    )
    try:
        data = requests.get(url, headers=HEAD, timeout=20).json()
    except Exception as e:
        print(f"[KBS] request failed: {e}", file=sys.stderr)
        return {"prefix": "kbs/25", "programs": []}

    # 응답은 배열 → 각 객체에 schedules 배열
    programs = []
    for day in data:
        if day.get("channel_code") != "25":
            continue  # Cool FM 만
        for item in day.get("schedules", []):
            raw = item.get("program_planned_start_time", "")[:4]  # HHMM
            if len(raw)==4:
                time = f"{int(raw[:2]):02d}:{raw[2:]}"
            else:
                time = ""
            title = item.get("program_title", "").strip()
            if TIME_RE.match(time) and title:
                programs.append({"name": title, "time": time})
    print(f"[KBS] parsed {len(programs)} rows")
    return {"prefix": "kbs/25", "programs": programs}

# ── MAIN ────────────────────────────────────────────────────
if __name__ == "__main__":
    schedule = {
        "sbs": fetch_sbs(),
        "kbs": fetch_kbs(),
    }
    Path("schedule.json").write_text(json.dumps(schedule, ensure_ascii=False, indent=2), encoding="utf-8")
    print("schedule.json written ✔")
