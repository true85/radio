#!/usr/bin/env python3
"""📡 Weekly radio schedule scraper (SBS Power‑FM, KBS Cool‑FM)
    • SBS  : static.cloud.sbs.co.kr JSON (per‑day)
    • KBS  : static.api.kbs.co.kr weekly endpoint (per‑day range)
Generates schedule.json in repo root.
"""
import json, datetime as dt, re, sys, requests
from pathlib import Path

# ─────────────────────────────────────────────────────────────
UA   = "schedule-bot/1.4 (+github actions)"
HEAD = {"User-Agent": UA}
TODAY   = dt.date.today()
MONDAY  = TODAY - dt.timedelta(days=TODAY.weekday())  # 이번 주 시작 (월)
FMT_DAY = "%Y/%-m/%-d"        # SBS 경로용: 2025/6/24 (0‑패딩 없음)
FMT_API = "%Y%m%d"            # KBS 쿼리용: 20250624
TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")

def clean(text: str) -> str:
    """공백·제어문자 정규화"""
    return re.sub(r"\s+", " ", text.strip())

# ── 1. SBS Power FM ─────────────────────────────────────────

def fetch_sbs():
    ymd = MONDAY.strftime(FMT_DAY)  # e.g. 2025/6/23
    url = f"https://static.cloud.sbs.co.kr/schedule/{ymd}/Power.json"
    try:
        data = requests.get(url, headers=HEAD, timeout=20).json()
    except Exception as e:
        print(f"[SBS] request failed: {e}", file=sys.stderr)
        return {"prefix": "sbs/powerfm", "programs": []}

    items = data if isinstance(data, list) else data.get("schedulerPrograms", [])
    programs = [
        {
            "name": clean(itm.get("title", "")),
            "time": itm.get("start_time", "")[:5]
        }
        for itm in items
        if TIME_RE.match(itm.get("start_time", "")[:5]) and itm.get("title")
    ]
    print(f"[SBS] parsed {len(programs)} rows")
    return {"prefix": "sbs/powerfm", "programs": programs}

# ── 2. KBS Cool FM (channel 25) ─────────────────────────────

def fetch_kbs():
    """KBS Cool‑FM (channel 25)
    API 특성상 30분 간격으로 잘린 슬롯이 많으므로 동일 프로그램명을 병합한다.
    뉴스·캠페인(1분짜리) 등은 제외.
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

    # ── 추출 ───────────────────────────────────────────────
    raw_items = []
    for day in data:
        if day.get("channel_code") != "25":
            continue
        for itm in day.get("schedules", []):
            hhmm = itm.get("program_planned_start_time", "")[:4]  # HHMM
            if len(hhmm) != 4 or not hhmm.isdigit():
                continue
            time = f"{int(hhmm[:2]):02d}:{hhmm[2:]}"
            title = clean(itm.get("program_title", ""))
            if TIME_RE.match(time) and title:
                raw_items.append({"name": title, "time": time})

    # 시간 순 정렬
    raw_items.sort(key=lambda x: x["time"])

    # ── 병합: 같은 프로그램 이름은 첫 등장만 ───────────────
    merged, seen = [], set()
    for row in raw_items:
        norm_name = row["name"]
        if norm_name in seen:
            continue
        if "뉴스" in norm_name or "캠페인" in norm_name:
            continue  # 짧은 슬롯 제외
        merged.append(row)
        seen.add(norm_name)

    print(f"[KBS] parsed {len(merged)} rows (dedup from {len(raw_items)})")
    return {"prefix": "kbs/25", "programs": merged}

# ── MAIN ────────────────────────────────────────────────────
if __name__ == "__main__":
    schedule = {
        "sbs": fetch_sbs(),
        "kbs": fetch_kbs(),
    }
    Path("schedule.json").write_text(
        json.dumps(schedule, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("schedule.json written ✔")
