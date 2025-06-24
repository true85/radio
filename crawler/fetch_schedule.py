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
    """KBS Cool‑FM (channel 25)
    • API는 같은 프로그램을 30분 간격으로 쪼개어 돌려준다.
    • 아래 로직은 [프로그램명]이 동일하고 연속된 항목을 하나로 병합해
      시작 시각만 보존한다 (시간 순 정렬 전제).
    """
    date_str = MONDAY.strftime(FMT_API)  # 20250624
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

    # 추출 + 병합
    raw_items = []
    for day in data:
        if day.get("channel_code") != "25":
            continue
        for itm in day.get("schedules", []):
            start_raw = itm.get("program_planned_start_time", "")[:4]  # HHMM
            if len(start_raw) != 4:
                continue
            hh = int(start_raw[:2]); mm = start_raw[2:]
            time = f"{hh:02d}:{mm}"
            title = itm.get("program_title", "").strip()
            if TIME_RE.match(time) and title:
                raw_items.append({"name": title, "time": time})

    # 시간 순 정렬
    raw_items.sort(key=lambda x: x["time"])

        # 병합: 같은 프로그램이 하루에 여러 슬롯(30분 간격)으로 나뉘어 있을 때
    #       → 첫 등장 시각만 남기고 이후 중복은 모두 제거
    merged, seen = [], set()
    for row in raw_items:
        if row["name"] in seen:
            continue                    # 이미 추가된 프로그램은 스킵
        if "뉴스" in row["name"]:       # 30분 뉴스 등 짧은 코너 제외 (원하면 삭제)
            continue
        merged.append(row)
        seen.add(row["name"])

    print(f"[KBS] parsed {len(merged)} rows (dedup from {len(raw_items)})")
    return {"prefix": "kbs/25", "programs": merged}
 {"prefix": "kbs/25", "programs": merged}

# ── MAIN ────────────────────────────────────────────────────
if __name__ == "__main__":
    schedule = {
        "sbs": fetch_sbs(),
        "kbs": fetch_kbs(),
    }
    Path("schedule.json").write_text(json.dumps(schedule, ensure_ascii=False, indent=2), encoding="utf-8")
    print("schedule.json written ✔")
