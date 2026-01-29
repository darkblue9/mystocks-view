/* naver-proxy-utf8.cjs
 * Simple UTF-8 proxy exposing:
 *  - GET /api/price?code=005930.KS  -> { code, price }
 *  - GET /api/prices?codes=005930.KS,000660.KS -> { data:[{code,price}, ...] }
 *
 * Node >= 18 (global fetch) recommended. No external deps.
 */
const http = require('http');
const express = require('express');

const PORT = process.env.PORT ? Number(process.env.PORT) : 3000;
const app = express();

// --- CORS & UTF-8 ---
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET,OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type');
  res.header('Content-Type', 'application/json; charset=utf-8');
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

// --- Request logging ---
app.use((req, _res, next) => {
  console.log('[REQ]', req.method, req.url);
  next();
});

// --- Helpers ---
function toNaverItemCode(input) {
  // Accept "005930", "005930.KS", "005930.KQ", etc. -> "005930"
  const digits = String(input || '').match(/\d+/g)?.join('') || '';
  if (!digits) return '';
  return digits.padStart(6, '0').slice(-6);
}

async function fetchJson(url) {
  const res = await fetch(url, {
    headers: {
      'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
      'Accept': 'application/json,text/plain,*/*',
      'Referer': 'https://finance.naver.com/',
    },
    cache: 'no-store',
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} for ${url}`);
  }
  return await res.json();
}

// Primary source: Naver public summary API
async function getPriceFromNaverSummary(item6) {
  const url = `https://api.finance.naver.com/service/itemSummary.nhn?itemcode=${item6}`;
  const j = await fetchJson(url);
  // Known fields: now, close, diff, rate, open, high, low ...
  const price = Number(j?.now ?? j?.close ?? 0);
  if (!price) throw new Error('No price field in itemSummary');
  return price;
}

// Fallback: parse simple HTML from finance.naver.com (last close) if API blocked
async function getPriceFromHtml(item6) {
  const url = `https://finance.naver.com/item/sise.naver?code=${item6}`;
  const res = await fetch(url, {
    headers: {
      'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
      'Accept': 'text/html,*/*',
      'Referer': 'https://finance.naver.com/',
    },
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  const html = await res.text();
  // naive parse
  const m = html.match(/<span class="blind">([\d,]+)<\/span>/);
  const price = Number(m?.[1]?.replace(/,/g, '') || 0);
  if (!price) throw new Error('Failed to parse HTML price');
  return price;
}

// Single resolver with fallbacks
async function getPrice(codeInput) {
  const item6 = toNaverItemCode(codeInput);
  if (!item6) throw new Error('invalid code');
  try {
    return await getPriceFromNaverSummary(item6);
  } catch (e1) {
    console.warn('[fallback] itemSummary failed:', e1?.message || e1);
  }
  try {
    return await getPriceFromHtml(item6);
  } catch (e2) {
    console.warn('[fallback] HTML parse failed:', e2?.message || e2);
  }
  return 0;
}

// --- Routes ---
app.get('/health', (_req, res) => res.json({ ok: true }));

app.get('/api/price', async (req, res) => {
  try {
    const code = String(req.query.code || '').trim();
    if (!code) return res.status(400).json({ error: 'code required' });
    const price = await getPrice(code);
    return res.json({ code, price });
  } catch (err) {
    console.error('single error', err);
    return res.status(500).json({ error: String(err?.message || err) });
  }
});

app.get('/api/prices', async (req, res) => {
  try {
    const codes = String(req.query.codes || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if (!codes.length) return res.json({ data: [] });
    const data = await Promise.all(
      codes.map(async (code) => {
        try {
          const price = await getPrice(code);
          return { code, price };
        } catch (e) {
          return { code, price: 0, error: String(e?.message || e) };
        }
      })
    );
    return res.json({ data });
  } catch (err) {
    console.error('multi error', err);
    return res.status(500).json({ error: String(err?.message || err) });
  }
});

http.createServer(app).listen(PORT, () => {
  console.log(`✅ Naver proxy (UTF-8) on http://localhost:${PORT}`);
});
