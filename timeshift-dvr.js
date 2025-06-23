/* ===========================================================================
 *  timeshift-dvr  v2.8  —  SBS·KBS 라디오 타임시프트 전용 스크립트
 * ===========================================================================
 *  🎧  기능 요약
 *  -------------------------------------------------------------------------
 *  ▸ 방송 스트림(playlist.m3u8)을 주기적으로 폴링하여 세그먼트(.aac/.ts)를 수집
 *  ▸ Cloudflare Durable Object + Alarm 으로 정확한 주기 제어 및 상태 관리
 *  ▸ 동일 세그먼트 중복 저장 방지, 최대 재시도 3회, 버스트 폴링 지원
 *  ▸ /init  (생성), /stop (완전 종료)  두 가지 관리 API 제공
 *
 *  바인딩
 *  -------------------------------------------------------------------------
 *  ▸ Durable Object :  MY_DURABLE_OBJECT   (class: MyDurableObject)
 *  ▸ R2 Bucket      :  RADIO_STORAGE       (세그먼트 파일 저장)
 *
 *  빠른 사용 예시
 *  -------------------------------------------------------------------------
 *  # SBS 파워FM (폴링 5초)
 *    /init?name=sbs_powerfm&
 *          url=https://apis.sbs.co.kr/play-api/1.0/livestream/powerpc/powerfm?protocol=hls&ssl=Y&
 *          prefix=sbs/powerfm&interval=5
 *
 *  # KBS 채널25 (기본 5초)
 *    /init?name=kbs_25&
 *          url=https://cfpwwwapi.kbs.co.kr/api/v1/landing/live/channel_code/25&
 *          prefix=kbs/25
 * ===========================================================================*/

// 헬퍼: fetch 후 text 변환 & delay
const fetchText = url => fetch(url).then(r => r.text());
const delay     = ms  => new Promise(res => setTimeout(res, ms));

// ────────────────────────────────────────────────────────────────────────────
//  1. Durable Object — MyDurableObject (방송 1개 담당)
// ────────────────────────────────────────────────────────────────────────────
export class MyDurableObject {
  constructor(state, env) {
    this.state = state;
    this.env   = env;

    // 내부 설정값
    this.windowSize   = 500;          // dedup 윈도우 크기
    this.maxRetry     = 3;            // 세그먼트 재시도 횟수
    this.saveInterval = 10 * 60_000;  // dedup 백업 주기 (10분)
    this.fastFactor   = 0.25;         // 버스트 폴링 배수

    // 런타임 상태
    this.seen = new Set();

    // dedup 리스트 복원
    state.storage.get("SEEN").then(arr => Array.isArray(arr) && arr.forEach(u => this.seen.add(u)));
  }

  /** 내부 RPC (Root Worker → DO) */
  async fetch(req) {
    const { pathname } = new URL(req.url);

    // 1) /setup : 설정 + 첫 알람 예약
    if (pathname === "/setup") {
      const { url, prefix, interval } = await req.json();
      await this.state.storage.put("API", url);
      await this.state.storage.put("PREFIX", prefix);
      await this.state.storage.put("INTERVAL", Number(interval) || 5_000);
      await this.state.storage.put("SHUTDOWN", false);
      await this.state.storage.put("_lastSave", Date.now());
      await this.state.storage.setAlarm(Date.now() + 1_000);
      console.log(`[setup] ${prefix} (interval=${interval||5}s)`);
      return new Response("ok");
    }

    // 2) /shutdown : 완전 종료
    if (pathname === "/shutdown") {
      await this.state.storage.put("SHUTDOWN", true);
      await this.state.storage.deleteAlarm();
      console.log("[shutdown] instance stopped");
      return new Response("stopped");
    }

    return new Response("alive");
  }

  /** Alarm(): 주기적으로 세그먼트 다운로드 */
  async alarm() {
    // 종료 플래그 확인
    if (await this.state.storage.get("SHUTDOWN")) return;

    const t0 = Date.now();

    // 1) 설정값 로드
    const [API, PREFIX, INTERVAL] = await Promise.all([
      this.state.storage.get("API"),
      this.state.storage.get("PREFIX"),
      this.state.storage.get("INTERVAL")
    ]);
    if (!API || !PREFIX) return this.next(INTERVAL);

    // 2) API → playlist URL
    let playlist = API;
    try {
      const apiBody = await fetchText(API);
      if (apiBody.trim().startsWith("{")) {
        const j = JSON.parse(apiBody);
        playlist = API.includes("sbs") ? j.stream?.[0]?.source
                                       : j.channel_item?.[0]?.service_url;
      } else {
        playlist = apiBody.trim();
      }
    } catch (e) {
      console.warn("[API]", e.message);
      return this.next(INTERVAL);
    }

    // 3) chunklist → media playlist (.m3u8)
    let m3u8;
    try { m3u8 = await fetchText(playlist); }
    catch(e){ console.warn("[playlist]", e.message); return this.next(INTERVAL); }

    // 마스터 → variant 변환
    if (m3u8.includes("#EXT-X-STREAM-INF") && !m3u8.includes("#EXTINF")) {
      const rel = m3u8.split("\n").find(l => l && !l.startsWith("#")).trim();
      const variant = rel.startsWith("http") ? rel : new URL(rel, playlist).href;
      try { m3u8 = await fetchText(variant); }
      catch(e){ console.warn("[variant]", e.message); return this.next(INTERVAL); }
    }

    // 4) 세그먼트 URI 추출
    const segList = m3u8.split("\n").filter(l => l && !l.startsWith("#") && /\.(aac|ts)(\?|$)/i.test(l));
    if (!segList.length) return this.next(INTERVAL);

    // 5) 새 세그먼트 다운로드 & 저장
    const jobs = [];
    for (const raw of segList) {
      const dedupKey = raw.split("?")[0];
      if (this.seen.has(dedupKey)) continue;

      const abs = raw.startsWith("http") ? raw : new URL(raw, playlist).href;
      const file = abs.split("/").pop().split("?")[0];
      const r2Key = `${PREFIX}/${file}`;

      jobs.push(
        this.downloadAndPut(abs, r2Key)
          .then(() => {
            this.seen.add(dedupKey);
            if (this.seen.size > this.windowSize)
              this.seen.delete(this.seen.values().next().value);
          })
      );
    }
    await Promise.all(jobs);

    // 6) dedup 리스트 주기적 백업
    const lastSave = await this.state.storage.get("_lastSave") || 0;
    if (Date.now() - lastSave > this.saveInterval) {
      await this.state.storage.put("SEEN", [...this.seen]);
      await this.state.storage.put("_lastSave", Date.now());
    }

    // 7) 다음 알람 예약 (버스트/보정)
    const spent = Date.now() - t0;
    const nextGap = jobs.length ? Math.max(200, INTERVAL * this.fastFactor)
                                : Math.max(0, INTERVAL - spent);
    await this.next(nextGap);
  }

  /** 세그먼트 다운로드 & R2 PUT (재시도 포함) */
  async downloadAndPut(url, key, attempt = 1) {
    try {
      const res = await fetch(url, { cf: { cacheTtl: 0 } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await this.env.RADIO_STORAGE.put(key, await res.arrayBuffer(), {
        httpMetadata: { contentType: key.endsWith(".ts") ? "video/mp2t" : "audio/aac" }
      });
      console.log(`✔ ${key}`);
    } catch (e) {
      if (attempt < this.maxRetry) {
        console.warn(`⟳ retry ${key} (${attempt})`);
        await delay(1_000);
        return this.downloadAndPut(url, key, attempt + 1);
      }
      console.error(`✗ ${key}  ${e.message}`);
    }
  }

  async next(ms) {
    await this.state.storage.setAlarm(Date.now() + (ms || 5_000));
  }
}

// ────────────────────────────────────────────────────────────────────────────
//  2. Root Worker — 인스턴스 관리 라우터
// ────────────────────────────────────────────────────────────────────────────
export default {
  async fetch(req, env) {
    const { pathname, searchParams, origin } = new URL(req.url);

    // /init : 인스턴스 생성
    if (pathname === "/init") {
      const name   = searchParams.get("name");
      const url    = searchParams.get("url");
      const prefix = searchParams.get("prefix");
      const interval = Number(searchParams.get("interval")) * 1_000 || undefined;

      if (!name || !url || !prefix)
        return new Response("usage: /init?name=&url=&prefix=&interval=", { status: 400 });

      const id   = env.MY_DURABLE_OBJECT.idFromName(name);
      const stub = env.MY_DURABLE_OBJECT.get(id);
      await stub.fetch(`${origin}/setup`, {
        method: "POST",
        body:   JSON.stringify({ url, prefix, interval })
      });
      return new Response(`instance \"${name}\" started`);
    }

    // /stop : 인스턴스 종료
    if (pathname === "/stop") {
      const name = searchParams.get("name");
      if (!name) return new Response("usage: /stop?name=", { status: 400 });

      const id   = env.MY_DURABLE_OBJECT.idFromName(name);
      const stub = env.MY_DURABLE_OBJECT.get(id);
      await stub.fetch(`${origin}/shutdown`);
      return new Response(`instance \"${name}\" stopped`);
    }

    return new Response("root ok");
  }
}

/* =========================================================================
 *  Quick links (복사·붙여넣기)
 * -------------------------------------------------------------------------
 *  /init?name=sbs_powerfm&url=https://apis.sbs.co.kr/play-api/1.0/livestream/powerpc/powerfm?protocol=hls&ssl=Y&prefix=sbs/powerfm&interval=5
 *  /init?name=kbs_25&url=https://cfpwwwapi.kbs.co.kr/api/v1/landing/live/channel_code/25&prefix=kbs/25
────────────────────────────────────────────────────────────────────────*/

