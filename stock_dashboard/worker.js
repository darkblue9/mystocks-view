export default {
  async fetch(req, env, ctx) {
    try {
      // 1) 프리플라이트 허용
      if (req.method === 'OPTIONS') {
        return cors(new Response(null, { status: 204 }), req);
      }

      const url = new URL(req.url);

      if (url.pathname === '/api/health') {
        return cors(json({ ok: true, ts: Date.now() }), req);
      }

      if (url.pathname === '/api/price') {
        const codeParam = url.searchParams.get('codeParam') || 'code';
        const code = url.searchParams.get(codeParam) || url.searchParams.get('code') || '';
        const data = await fetchNaverMany([code]);
        return cors(json({ data }), req);
      }

      if (url.pathname === '/api/prices') {
        const codesStr = url.searchParams.get('codes') || '';
        const raw = decodeURIComponent(codesStr);
        const codes = raw.split(',').map(s => s.trim()).filter(Boolean);
        const out = [];

        // 너무 한꺼번에 때리면 503나므로 20개씩 순차
        const CHUNK = 20;
        for (let i = 0; i < codes.length; i += CHUNK) {
          const part = codes.slice(i, i + CHUNK);
          const got = await fetchNaverMany(part);
          out.push(...got);
          // 살짝 텀을 줘도 좋음 (네이버/CF 429 방지)
          await sleep(50);
        }
        return cors(json({ data: out }), req);
      }

      // 기타 경로
      return cors(json({ error: 'Not Found' }, 404), req);
    } catch (e) {
      // 어떤 예외라도 CORS가 붙은 JSON으로 내보내기
      return cors(json({ error: String(e?.message || e) }, 502), req);
    }
  }
};

// ---------- 헬퍼들 ----------
function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8' }
  });
}

function cors(res, req) {
  // 모든 오리진 허용(필요하면 req.headers.get('Origin') 반영로 좁힐 수도 있음)
  const h = new Headers(res.headers);
  h.set('Access-Control-Allow-Origin', '*');
  h.set('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  h.set('Access-Control-Allow-Headers', 'Content-Type, Authorization, *');
  h.set('Access-Control-Max-Age', '86400');
  return new Response(res.body, { status: res.status, headers: h });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// function normKey(c) { return String(c || '').toUpperCase().replace(/\.KS$/, ''); }
function normKey(c){
  return String(c || '').toUpperCase().replace(/\.(KS|KQ)$/, '');
}

// ---------- 업스트림 호출 ----------
async function fetchNaverMany(codes) {
  if (!codes?.length) return [];
  const list = codes.map(c => normKey(c)).join(',');                 // '005930,000660,035420'
  const q = `SERVICE_ITEM:${list}`;                                  // ✅ SERVICE_ITEM: 한 번만
  const url = `https://polling.finance.naver.com/api/realtime?query=${encodeURIComponent(q)}`;

  const r = await fetch(url, {
    headers: {
      'referer': 'https://finance.naver.com/',
      'user-agent': 'Mozilla/5.0 (Linux; Android 13; SAMSUNG) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Mobile Safari/537.36',
      'accept': 'application/json, text/plain, */*',
      'accept-language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
    },
    cf: { cacheTtl: 5, cacheEverything: true }
  });

  if (!r.ok) {
    // 네이버가 5xx/4xx를 줘도 워커는 JSON+CORS 로 응답
    // 호출자는 0원 처리할지 재시도할지 판단 가능
    return codes.map(c => ({ code: normKey(c), price: 0, err: r.status }));
  }

  const j = await r.json();
  const areas = (j && j.result && j.result.areas) || [];
  const datas = areas.flatMap(a => a.datas || []);


// [Worker.js] 수정할 부분 (fetchNaverMany 함수 맨 끝)

  return datas.map(d => {
    const code = normKey(d.cd);
    const current = Number(d.nv || 0); // 현재가
    const prev = Number(d.sv || 0);    // 전일 종가 (Standard Value)
    
    // [핵심] 등락률 직접 계산 (부호 문제 해결)
    let rate = 0;
    if (prev > 0) {
      rate = ((current - prev) / prev) * 100;
    } else {
      // 전일 종가 데이터가 없는 예외적인 경우, 그냥 cr 사용 (fallback)
      rate = Number(d.cr || 0);
    }

    return { 
      code: code, 
      price: current,
      day_rate: parseFloat(rate.toFixed(2)) // 소수점 2자리로 깔끔하게
    };
  });

}
