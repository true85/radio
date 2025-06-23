# radio
radio는 두 개의 라디오 방송(SBS 파워FM, KBS Cool FM)을 실시간 스트리밍 및 타임시프트(지정한 시점으로 되감기 재생)로 들을 수 있는 웹 플레이어입니다.

## 주요 기능
- 실시간 방송 청취: SBS 파워FM, KBS Cool FM 두 방송을 실시간으로 스트리밍합니다.
- 타임시프트(시간 이동 재생): 사용자가 원하는 시점(과거의 방송 시간)으로 이동하여 들을 수 있습니다.
- 방송 선택: 방송국과 프로그램을 선택할 수 있습니다.
- 간단한 웹 UI: HTML 기반의 직관적인 사용자 인터페이스 제공.
## 동작 방식
- 백엔드(worker 및 durable object)는 각 방송 스트림의 m3u8(playlist)을 주기적으로 폴링하여 세그먼트(.aac, .ts 파일)를 Cloudflare R2 스토리지에 저장합니다.
- 방송별로 저장된 세그먼트 파일을 기반으로, 사용자가 요청한 시간(예: 30분 전, 1시간 전 등)에 해당하는 플레이리스트(m3u8)를 생성하여 제공합니다.
- 프론트엔드(index.html)는 방송국/프로그램 선택, 실시간/다시듣기 모드 전환, 시간 선택 등 UI를 제공합니다.
- 플레이어는 방송국별 prefix와 시간(ago 파라미터), 모드(live/vod)를 조합해 백엔드에서 실시간 또는 타임시프트 m3u8을 받아옵니다.

## 사용 예시
1. 방송국을 선택합니다.
  - SBS 파워FM
  - KBS Cool FM (2FM)
2. 모드를 선택합니다.

  - 프로그램 다시듣기(특정 시점 재생)
  - 실시간 듣기
3. 프로그램 또는 지연 시간(몇 분 전 등)을 선택하면 해당 구간의 방송이 재생됩니다.

## 기술 스택
- 프론트엔드: HTML, JavaScript
- 백엔드: Cloudflare Workers, Durable Object, R2 Storage
- 스트림 포맷: HLS (m3u8, AAC/TS 세그먼트)
## 빠른 시작
- 방송 파워FM 초기화 예시:
'''Code
/init?name=sbs_powerfm&url=https://apis.sbs.co.kr/play-api/1.0/livestream/powerpc/powerfm?protocol=hls&ssl=Y&prefix=sbs/powerfm&interval=5
'''
- 방송 KBS 25 초기화 예시:
'''Code
/init?name=kbs_25&url=https://cfpwwwapi.kbs.co.kr/api/v1/landing/live/channel_code/25&prefix=kbs/25
'''
## 기타
- 세그먼트 중복 저장 방지, 일정 주기마다 세그먼트 수집 및 저장, 최대 재시도 등 안정성을 고려한 구조입니다.
- Cloudflare 환경에 최적화되어 동작합니다.
