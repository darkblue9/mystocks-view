/**
 * Naver Stock Proxy Server (CommonJS)
 * No API key required. Run: node naver-proxy-fixed.cjs
 */
const express = require('express');
const fetch = require('node-fetch');
const cors = require('cors');
const iconv = require('iconv-lite');

const app = express();
app.use(cors());
app.use(express.json());

const UA = {
  headers: {
    'User-Agent':
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
    'Accept': 'text/html,application/json;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8'
  },
};

// simple in-memory cache
const cache = new Map();
function cached(key, ttlSec, fn) {
  const now = Date.now();
  const hit = cache.get(key);
  if (hit && now - hit.t < ttlSec * 1000) return Promise.resolve(hit.v);
  return Promise.resolve(fn()).then((v)=>{ cache.set(key,{v,t:Date.now()}); return v; });
}

function toSymbol(sym) {
  sym = String(sym || '').toUpperCase().trim();
  if (!sym) return '';
  if (!sym.includes('.')) {
    // default to .KS if not specified
    sym = sym + '.KS';
  }
  return sym;
}
function toCode(sym) {
  const m = String(sym).match(/(\d{6})/);
  return m ? m[1] : '';
}

// ---- Data sources ----
async function fetchFromNaverJson(code) {
  // polling API used widely, returns now value + name
  const url = `https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:${code}`;
  const res = await fetch(url, UA);
  if (!res.ok) return null;
  const j = await res.json().catch(()=>null);
  const item = j && j.result && j.result.areas && j.result.areas[0] && j.result.areas[0].datas && j.result.areas[0].datas[0];
  if (!item) return null;
  return { c: Number(item.nv||0), name: String(item.nm||'') };
}

async function fetchFromNaverHtml(code) {
  const url = `https://finance.naver.com/item/main.naver?code=${code}`;
  // ★ text() 말고 buffer()로 받고 EUC-KR 디코딩
  const res = await fetch(url, { ...UA });
  if (!res.ok) return null;
  const buf = await res.buffer();
  const html = iconv.decode(buf, 'EUC-KR'); // 또는 'CP949'

  // 가격
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

  // 이름 (여러 패턴 시도)
  let name = '';
  const mOg = html.match(/<meta\s+property=["']og:title["']\s+content=["']([^"']+)["']/i);
  if (mOg && mOg[1]) name = String(mOg[1]).replace(/\s*:\s*네이버\s*금융\s*$/i, '').trim();

  if (!name) {
    const mTitle = html.match(/<title>\s*([^<]+?)\s*:\s*네이버\s*금융\s*<\/title>/i);
    if (mTitle && mTitle[1]) name = mTitle[1].trim();
  }
  if (!name) {
    const mWrap = html.match(/<div[^>]+class=["']wrap_company["'][\s\S]*?<\/div>/i);
    if (mWrap) {
      const mH2 = mWrap[0].match(/<h2[^>]*>([\s\S]*?)<\/h2>/i);
      if (mH2) name = mH2[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
    }
  }

  if (price > 0) return { c: price, name };
  return null;
}

// ---- Routes ----
app.get('/api/ping', (req, res)=> res.json({ ok:true, time: Date.now() }));

app.get('/api/quote', async (req, res) => {
  try{
    const symbols = String(req.query.symbols||'').split(',').map(s=>s.trim()).filter(Boolean);
    if (symbols.length===0) return res.json({});
    const out = {};
    await Promise.all(symbols.map(async (sym)=>{
      const symbol = toSymbol(sym);
      const code = toCode(sym);
      if (!code) return;

      const key = 'q:'+code;
      const got = await cached(key, 2, async () => {
        const a = await fetchFromNaverJson(code);
        if (a && a.c > 0) {
          if (!a.name) {
            const b = await fetchFromNaverHtml(code);
            if (b && b.name) a.name = b.name;
          }
          return a;
        }
        const b = await fetchFromNaverHtml(code);
        return b || { c: 0, name: '' };
      });

      out[symbol] = got;
    }));
    res.json(out);
  }catch(e){
    console.error('[quote]', e);
    res.status(500).json({ error: e.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, ()=> console.log(`✅ Naver proxy (CJS) listening on http://localhost:${PORT}`));
