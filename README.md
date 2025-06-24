# radio (타임시프트 라디오, VOD 전용)

SBS 파워FM, KBS Cool FM 라디오 방송의 "다시듣기(VOD)" 기능을 제공하는 웹 플레이어입니다. 실시간 스트리밍 기능은 제공하지 않으며, 원하는 프로그램/시간을 선택해 과거 방송을 재생할 수 있습니다.

## 주요 기능
- SBS 파워FM, KBS Cool FM 방송의 과거 프로그램 다시듣기(VOD)
- 방송국/프로그램/시점(시작 시간) 선택 UI
- 방송별 최신 편성표(schedule.json) 자동 반영
- Cloudflare Durable Object + R2 기반 세그먼트 수집 및 저장
- video.js 기반 HLS 플레이어 제공

## 동작 구조
- **timeshift-dvr.js**: 방송 스트림(m3u8)을 주기적으로 폴링하여 세그먼트(.aac/.ts)를 Cloudflare R2에 저장 (중복 방지, 재시도, 관리 API)
- **radio-timeshift-shift.js**: 저장된 세그먼트로부터 사용자가 지정한 시점(ago 파라미터)에 맞는 m3u8 플레이리스트를 동적으로 생성 (VOD 전용)
- **index.html**: 방송국/프로그램/시점 선택 UI 및 video.js 플레이어
- **schedule.json**: SBS/KBS 공식 API에서 자동 크롤링된 최신 편성표 (crawler/fetch_schedule.py + GitHub Actions)

## 사용법
1. 웹 UI(index.html)에서 방송국과 프로그램을 선택합니다.
2. 원하는 프로그램(시작 시간)을 선택 후 "재생" 버튼을 누르면 해당 시점부터 방송이 재생됩니다.
3. 방송별로 최신 편성표가 자동 반영됩니다.

## 빠른 시작 (세그먼트 수집 인스턴스 생성)
- SBS 파워FM:
  
  `/init?name=sbs_powerfm&url=https://apis.sbs.co.kr/play-api/1.0/livestream/powerpc/powerfm?protocol=hls&ssl=Y&prefix=sbs/powerfm&interval=5`

- KBS 25:
  
  `/init?name=kbs_25&url=https://cfpwwwapi.kbs.co.kr/api/v1/landing/live/channel_code/25&prefix=kbs/25`

## 파일 구조 및 역할
- `index.html` : 사용자 웹 UI (방송/프로그램 선택, video.js 플레이어)
- `radio-timeshift-shift.js` : VOD 전용 Cloudflare Worker (m3u8 동적 생성, 세그먼트 전달)
- `timeshift-dvr.js` : Durable Object 기반 세그먼트 수집기 (R2 저장)
- `schedule.json` : 방송별 프로그램 편성표 (자동 크롤링)
- `crawler/fetch_schedule.py` : 편성표 크롤러 (SBS/KBS 공식 API)
- `.github/workflows/fetch-schedule.yml` : GitHub Actions로 편성표 자동 갱신

## 기타
- 세그먼트 중복 저장 방지, 재시도, 주기적 백업 등 안정성 고려
- Cloudflare 환경에 최적화된 구조
- 실시간 스트리밍은 지원하지 않음 (VOD 전용)
