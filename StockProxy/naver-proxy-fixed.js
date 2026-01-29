/**
 * Naver Stock Proxy Server (Full version, name+price)
 * Works without API key. Use: node naver-proxy.js
 */

import express from 'express';
import fetch from 'node-fetch';
import cors from 'cors';

const app = express();
app.use(cors());

const UA = {
  headers: {
    'User-Agent':
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
  },
};

const cache = new Map();

function toSymbol(sym) {
  sym = sym.toUpperCase().trim();
  if (!sym.includes('.')) sym += sym.endsWith('KQ') ? '.KQ' : '.KS';
  return sym;
}

function toCode(sym) {
  return sym.replace(/[^0-9]/g, '');
}

async function fetchFromNaverJson(code) {
  const url = `https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:${code}`;
  const res = await fetch(url, UA);
  if (!res.ok) throw new Error('naver json http ' + res.status);
  const j = await res.json();
  const item = j?.result?.areas?.[0]?.datas?.[0];
  if (!item) return null;
  return { c: item.nv || 0, name: item.nm || '' };
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

  // 이름
  let name = '';
  const mOg = html.match(/<meta\s+property=["']og:title["']\s+content=["']([^"']+)["']/i);
  if (mOg && mOg[1]) {
    name = String(mOg[1]).replace(/\s*:\s*네이버\s*금융\s*$/i, '').trim();
  }
  if (!name) {
    const mTitle = html.match(/<title>\s*([^<]+?)\s*:\s*네이버\s*금융\s*<\/title>/i);
    if (mTitle && mTitle[1]) name = mTitle[1].trim();
  }
  if (!name) {
    const mWrap = html.match(/<div[^>]+class=["']wrap_company["'][\s\S]*?<\/div>/i);
    if (mWrap) {
      const mH2 = mWrap[0].match(/<h2[^>]*>([\s\S]*?)<\/h2>/i);
      if (mH2) {
        const raw = mH2[1].replace(/<[^>]+>/g, '').trim();
        if (raw) name = raw;
      }
    }
  }
  name = name.replace(/\u00a0/g, ' ').trim();

  if (price > 0) return { c: price, name };
  return null;
}

async function cached(key, ttlMin, fn) {
  const now = Date.now();
  const hit = cache.get(key);
  if (hit && now - hit.time < ttlMin * 60 * 1000) return hit.val;
  const val = await fn();
  cache.set(key, { val, time: now });
  return val;
}

app.get('/api/ping', (req, res) => {
  res.json({ ok: true, time: Date.now() });
});

app.get('/api/quote', async (req, res) => {
  const syms = (req.query.symbols || '').split(',').map((s) => s.trim()).filter(Boolean);
  const out = {};
  await Promise.all(
    syms.map(async (sym) => {
      const symbol = toSymbol(sym);
      const code = toCode(sym);
      if (!code) return;

      const key = 'q:' + code;
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
    })
  );
  res.json(out);
});

app.listen(3000, () => console.log('✅ Naver proxy running on http://localhost:3000'));
