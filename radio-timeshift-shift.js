/* ===========================================================================
 * radio-timeshift-shift v12 — VOD-only Worker
 * ---------------------------------------------------------------------------
 * 라이브(실시간) 모드를 완전히 제거하고, 프로그램 다시듣기(VOD) 기능만 제공합니다.
 * 세그먼트 길이(KBS 5 s / SBS 9 s)를 기반으로 targetDuration 을 segDur+1 로 설정.
 * ---------------------------------------------------------------------------
 * KV(Storage) 구조
 *   └── <prefix>/<timestamp>.ts
 *       예) sbs/powerfm/media-u5axffi7h_239570.ts
 *
 * 플레이리스트 요청 (예)
 *   /sbs/powerfm.m3u8?ago=3600s     ← 1시간 전부터 재생
 * ---------------------------------------------------------------------------*/

/** ago 문자열(예: "90s", "10m", "2h", "1d") → ms 로 변환 */
const parseAgo = (ago = '') => {
  const m = /^([0-9]+)([smhd])$/.exec(ago.toLowerCase());
  if (!m) return 0;
  const n = +m[1];
  const unit = { s: 1, m: 60, h: 3600, d: 86400 }[m[2]];
  return n * unit * 1000;
};

export default {
  /** Cloudflare Worker entry */
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname.startsWith('/get/')) {
      // 세그먼트 전달
      return this.serveSegment(url.pathname.slice(5), request, env);
    }

    if (url.pathname.endsWith('.m3u8')) {
      // VOD 플레이리스트 생성
      return this.handlePlaylist(url, env);
    }

    return new Response('Radio Timeshift Worker v12 (VOD only)');
  },

  /* ---------------------------------------------------------------------- */
  /* 1) VOD 플레이리스트 핸들러                                            */
  /* ---------------------------------------------------------------------- */
  async handlePlaylist(url, env) {
    const prefix = url.pathname.slice(1, -5);           // "sbs/powerfm" 등
    const segDur = prefix.includes('kbs') ? 5 : 9;      // 방송사별 세그먼트 길이
    const targetDur = segDur + 1;                       // 권장: +1 초

    // KV 리스트 가져오기 (최신순 정렬)
    let listed = await env.RADIO_STORAGE.list({ prefix: `${prefix}/` });
    const objs = [...listed.objects];
    while (listed.truncated) {
      listed = await env.RADIO_STORAGE.list({ prefix: `${prefix}/`, cursor: listed.cursor });
      objs.push(...listed.objects);
    }
    objs.sort((a, b) => a.uploaded - b.uploaded);

    const agoMs = parseAgo(url.searchParams.get('ago'));
    const startTime = Date.now() - agoMs;

    const selected = objs.filter(o => o.uploaded.getTime() >= startTime);
    const mediaSeq = objs.findIndex(o => o.uploaded.getTime() >= startTime);

    let m3u = `#EXTM3U\n`;
    m3u += `#EXT-X-VERSION:3\n`;
    m3u += `#EXT-X-TARGETDURATION:${targetDur}\n`;
    m3u += `#EXT-X-MEDIA-SEQUENCE:${mediaSeq}\n`;

    selected.forEach(o => {
      m3u += `#EXTINF:${segDur.toFixed(3)},\n${url.origin}/get/${o.key}\n`;
    });

    m3u += `#EXT-X-ENDLIST\n`;

    return new Response(m3u, {
      headers: {
        'Content-Type': 'application/vnd.apple.mpegurl',
        'Access-Control-Allow-Origin': '*'
      }
    });
  },

  /* ---------------------------------------------------------------------- */
  /* 2) 세그먼트 전달                                                       */
  /* ---------------------------------------------------------------------- */
  async serveSegment(key, request, env) {
    const obj = await env.RADIO_STORAGE.get(key);
    if (!obj) return new Response(null, { status: 404 });

    const etag = obj.httpEtag;
    if (request.headers.get('if-none-match') === etag) {
      return new Response(null, { status: 304, headers: { ETag: etag } });
    }

    const headers = new Headers();
    obj.writeHttpMetadata(headers);
    headers.set('Cache-Control', 'public, max-age=0, s-maxage=86400');  // 세그먼트는 하루 동안 캐시
    headers.set('ETag', etag);
    headers.set('Access-Control-Allow-Origin', '*');

    return new Response(obj.body, { headers });
  }
};
