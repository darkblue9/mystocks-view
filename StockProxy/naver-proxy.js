// naver-proxy.js
// 한국주식 전용 프록시 (API 키 불필요)
// - 6자리코드(+.KS/.KQ 허용) -> 네이버에서 현재가 가져와서 {symbol:{c,name}}로 응답
// - 1차: 네이버 모바일 JSON, 2차: 네이버 HTML 파싱 폴백
const express = require('express');
const fetch = require('node-fetch');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

const UA = {
  headers: {
    'User-Agent':
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
    'Accept': 'text/html,application/json;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8'
  }
};

// 작은 메모리 캐시 (초단위)
const cache = new Map();
function cached(key, ttlSec, fn) {
  const now = Date.now();
  const hit = cache.get(key);
  if (hit && now - hit.t < ttlSec * 1000) return Promise.resolve(hit.v);
  return fn().then((v) => {
    cache.set(key, { v, t: Date.now() });
    return v;
  });
}

function toCode(sym) {
  // '005930.KS' -> '005930'
  const m = String(sym).match(/(\d{6})/);
  return m ? m[1] : '';
}
function toSymbol(sym) {
  // 코드만 들어오면 .KS 기본
  if (/^\d{6}$/.test(sym)) return `${sym}.KS`;
  return sym.toUpperCase();
}

async function fetchFromNaverJson(code) {
  // 네이버 모바일 JSON (비공식)
  // 흔히 쓰는 엔드포인트들: 아래 둘 중 하나는 보통 열림(환경 따라 다름)
  const urls = [
    `https://m.stock.naver.com/api/stock/${code}/price`,
    `https://m.stock.naver.com/api/stock/${code}/basic`
  ];
  for (const url of urls) {
    try {
      const res = await fetch(url, UA);
      if (!res.ok) continue;
      const j = await res.json();
      // 다양한 포맷을 허용적으로 처리
      const price =
        Number(j?.now?.price) ||
        Number(j?.closePrice) ||
        Number(j?.price) ||
        Number(j?.tradePrice) ||
        0;
      const name =
        j?.stockName ||
        j?.name ||
        j?.stock?.name ||
        j?.basic?.name ||
        '';
      if (price > 0) return { c: price, name: name || '' };
    } catch (e) {
      // 다음 후보로 폴백
    }
  }
  return null;
}

async function fetchFromNaverHtml(code) {
  const url = `https://finance.naver.com/item/main.naver?code=${code}`;
  const res = await fetch(url, UA);
  if (!res.ok) throw new Error('naver html http ' + res.status);
  const html = await res.text();

  // 현재가
  const rxList = [
    /id=["']_nowVal["'][^>]*>([\d,]+)</i,
    /class=["']no_today["'][\s\S]*?<span[^>]*>([\d,]+)</i,
    /class=["']price["'][^>]*>\s*<strong[^>]*>([\d,]+)</i,
  ];
  let price = 0;
  for (const rx of rxList) {
    const m = html.match(rx);
    if (m) {
      price = Number(String(m[1]).replace(/[^\d]/g, ''));
      if (price > 0) break;
    }
  }

  // 종목명 (여기 수정!)
  let name = '';
  const rxName = /<meta property="og:title" content="([^"]+) : 네이버 금융"/i;
  const m = html.match(rxName);
  if (m) {
    name = m[1].trim();
  } else {
    const alt = html.match(/<title>\s*([^<]+)\s*:\s*네이버 금융/i);
    if (alt) name = alt[1].trim();
  }

  if (price > 0) return { c: price, name };
  return null;
}


// 헬스체크
app.get('/api/ping', (req, res) => res.json({ ok: true, time: Date.now() }));

// 배치 현재가
// /api/quote?symbols=005930.KS,066970.KQ
app.get('/api/quote', async (req, res) => {
  try {
    const symbols = (req.query.symbols || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if (symbols.length === 0) return res.json({});

    const out = {};
    await Promise.all(
  symbols.map(async (sym) => {
    const symbol = toSymbol(sym);
    const code = toCode(sym);
    if (!code) return;

    const key = 'q:' + code;

    const got = await cached(key, 2, async () => {
      const a = await fetchFromNaverJson(code);   // 1차: JSON (가격 빠름)
      if (a && a.c > 0) {
        // 이름이 비어 있으면 HTML로 보충
        if (!a.name) {
          const b = await fetchFromNaverHtml(code);
          if (b && b.name) a.name = b.name;
        }
        return a;
      }
      // JSON 실패 시 HTML 폴백
      const b = await fetchFromNaverHtml(code);
      return b || { c: 0, name: '' };
    });

    out[symbol] = got;
  })
);
    res.json(out);
  } catch (e) {
    console.error('[quote]', e);
    res.status(500).json({ error: e.message });
  }
});

// 간단 검색(코드만 입력해도 동작하도록 네이버 HTML로 보완)
app.get('/api/search', async (req, res) => {
  try {
    const q = String(req.query.q || '').trim();
    if (!q) return res.json({ result: [] });

    // 6자리면 바로 반환
    if (/^\d{6}$/.test(q)) {
      return res.json({ result: [{ symbol: `${q}.KS`, description: q }] });
    }

    // 네이버 검색 HTML (간단 파싱)
    const url = `https://finance.naver.com/search/searchList.naver?query=${encodeURIComponent(q)}`;
    const html = await fetch(url, UA).then((r) => r.text());
    const items = [];
    const rx = /href="\/item\/main\.nhn\?code=(\d{6})"[^>]*>\s*<span[^>]*>([^<]+)<\/span>/gi;
    let m;
    while ((m = rx.exec(html))) {
      items.push({ symbol: `${m[1]}.KS`, description: m[2] });
      if (items.length > 10) break;
    }
    res.json({ result: items });
  } catch (e) {
    console.error('[search]', e);
    res.status(500).json({ error: e.message });
  }
});

// 이름 조회 (HTML 폴백)
app.get('/api/profile', async (req, res) => {
  try {
    const sym = String(req.query.symbol || '');
    const code = toCode(sym);
    if (!code) return res.json({ name: '' });
    const html = await fetch(`https://finance.naver.com/item/main.naver?code=${code}`, UA).then((r) => r.text());
    const m = html.match(/<title>\s*([^<]+)\s*:\s*네이버 금융/i);
    res.json({ name: (m && m[1]) || '' });
  } catch (e) {
    console.error('[profile]', e);
    res.status(500).json({ error: e.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log('? Naver proxy listening on http://localhost:' + PORT));
