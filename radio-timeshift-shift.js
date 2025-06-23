/* ===========================================================================
 * radio-timeshift-shift  v6.5 (방송국별 세그먼트 길이 적용)
 * ===========================================================================
 * 🎧 변경 사항 요약
 * -------------------------------------------------------------------------
 * ▸ 방송국(KBS/SBS)별 세그먼트 길이 적용 (KBS 5초, SBS 9초)
 * ▸ livePlaylistSize를 약 40초 분량으로 조정해 m3u8 재요청 최소화
 * ▸ video.js VHS 설정 강화: segmentBufferMaxSize, manifestLoadingTimeOut 조정
 * ===========================================================================*/



// ----- worker.js -----
const parseAgo = (agoString) => {
  if (!agoString) return 0;
  const unit = agoString.slice(-1).toLowerCase();
  const value = parseInt(agoString.slice(0, -1), 10);
  if (isNaN(value)) return 0;
  switch (unit) {
    case 's': return value * 1000;
    case 'm': return value * 60 * 1000;
    case 'h': return value * 60 * 60 * 1000;
    case 'd': return value * 24 * 60 * 60 * 1000;
    default: return 0;
  }
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith('/get/')) return this.serveSegment(request, env);
    if (url.pathname.endsWith('.m3u8')) return this.handlePlaylist(request, env);
    return new Response('Radio Timeshift Worker v6.4');
  },

  async handlePlaylist(request, env) {
    const url = new URL(request.url);
    const prefix = url.pathname.slice(1, -5);
    const ago = url.searchParams.get('ago');
    if (!ago) return new Response('`ago` param is required.', { status: 400 });

    let listed = await env.RADIO_STORAGE.list({ prefix: `${prefix}/` });
    const objs = [...listed.objects];
    while (listed.truncated) {
      listed = await env.RADIO_STORAGE.list({ prefix: `${prefix}/`, cursor: listed.cursor });
      objs.push(...listed.objects);
    }
    objs.sort((a, b) => a.uploaded.getTime() - b.uploaded.getTime());
    const segments = objs.map(o => ({ key: o.key, uploaded: o.uploaded.toISOString() }));

    const resp = this.generatePlaylist(url, segments);
    resp.headers.set('Cache-Control', 'public, max-age=0, s-maxage=30');
    return resp;
  },

  generatePlaylist(url, segments) {
    const agoMs = parseAgo(url.searchParams.get('ago'));
    const startTime = Date.now() - agoMs;
    const arr = segments.map(s => ({ key: s.key, time: new Date(s.uploaded).getTime() }));
    const isLive = url.searchParams.get('mode') === 'live';

    // 방송국별 세그먼트 길이 (KBS: 5초, SBS: 9초)
    const prefix = url.pathname.slice(1, -5);
    const dur = prefix.startsWith('kbs') ? 5 : 9;
    // 플레이리스트 재요청 간격을 늘리기 위해 TARGETDURATION을 넉넉히 잡는다
    const tgt = Math.max(60, Math.ceil(dur * 3));

    let selected = [];
    let seq = 0;
    if (isLive) {
      const liveWindowSec = 40;                // 약 40초 분량 노출
      const count = Math.ceil(liveWindowSec / dur);
      const idx = arr.findIndex(x => x.time >= startTime);
      if (idx < 0) {
        selected = arr.slice(-count);
        seq = arr.length - count;
      } else {
        selected = arr.slice(idx, idx + count);
        seq = idx;
      }
    } else {
      selected = arr.filter(x => x.time >= startTime);
    }

    let m3u = `#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:${tgt}
#EXT-X-MEDIA-SEQUENCE:${seq}
`;
    for (const s of selected) {
      m3u += `#EXTINF:${dur.toFixed(3)},
${url.origin}/get/${s.key}
`;
    }
    m3u += isLive ? `#EXT-X-DISCONTINUITY
` : `#EXT-X-ENDLIST
`;

    return new Response(m3u, {
      headers: {
        'Content-Type': 'application/vnd.apple.mpegurl',
        'Access-Control-Allow-Origin': '*'
      }
    });
  },

  async serveSegment(request, env) {
    const url = new URL(request.url);
    const key = url.pathname.slice(5);
    const obj = await env.RADIO_STORAGE.get(key);
    if (!obj) return new Response(null, { status: 404 });

    const etag = obj.httpEtag;
    if (request.headers.get('if-none-match') === etag) {
      return new Response(null, {
        status: 304,
        headers: { 'ETag': etag }
      });
    }

    const headers = new Headers();
    obj.writeHttpMetadata(headers);
    headers.set('Cache-Control', 'public, max-age=0, s-maxage=60');
    headers.set('ETag', etag);
    headers.set('Access-Control-Allow-Origin', '*');
    return new Response(obj.body, { headers });
  }
};
