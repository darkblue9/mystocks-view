// yf-proxy.js (v1.2)
// - User-Agent/Referer/Accept-Language 헤더 추가
// - query1 -> query2 폴백
// - /api/ping 헬스체크, 에러 로깅 강화
const express = require('express');
const fetch = require('node-fetch');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

const H = {
  headers: {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
    'Accept': 'application/json,text/plain,*/*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://finance.yahoo.com/'
  }
};

async function getJson(url){
  const res = await fetch(url, H);
  if(!res.ok){
    const txt = await res.text().catch(()=> '');
    throw new Error(`HTTP ${res.status} @ ${url} :: ${txt.slice(0,160)}`);
  }
  return res.json();
}

// 작은 캐시
const cache = new Map();
function cached(key, ttlSec, fn) {
  const now = Date.now();
  const hit = cache.get(key);
  if (hit && (now - hit.t) < ttlSec*1000) return Promise.resolve(hit.v);
  return fn().then(v=>{ cache.set(key, {v, t:Date.now()}); return v; });
}

app.get('/api/ping', (req,res)=> res.json({ ok:true, time: Date.now() }));

// 배치 quote
app.get('/api/quote', async (req, res)=>{
  try{
    const symbols = (req.query.symbols||'').split(',').map(s=>s.trim()).filter(Boolean);
    if (symbols.length===0) return res.json({});
    const s = encodeURIComponent(symbols.join(','));
    const url1 = `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${s}`;
    const url2 = `https://query2.finance.yahoo.com/v7/finance/quote?symbols=${s}`;

    let data, result = [];
    try {
      data = await cached('q1:'+s, 2, ()=>getJson(url1));
      result = (data.quoteResponse && data.quoteResponse.result) || [];
    } catch(e1){
      console.error('[query1]', e1.message);
    }
    if (!Array.isArray(result) || result.length===0){
      try {
        data = await cached('q2:'+s, 2, ()=>getJson(url2));
        result = (data.quoteResponse && data.quoteResponse.result) || [];
      } catch(e2){
        console.error('[query2]', e2.message);
      }
    }
    if (!Array.isArray(result) || result.length===0){
      return res.status(502).json({ error: 'No data from Yahoo (both endpoints empty)' });
    }

    const out = {};
    for (const it of result){
      out[it.symbol] = {
        c: Number(it.regularMarketPrice||0),
        name: it.longName || it.shortName || it.symbol
      };
    }
    res.json(out);
  }catch(e){
    console.error('[quote]', e);
    res.status(500).json({ error: e.message });
  }
});

// 검색
app.get('/api/search', async (req,res)=>{
  try{
    const q = req.query.q || '';
    const url = `https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}`;
    const data = await cached('s:'+q, 5, ()=>getJson(url));
    const result = (data.quotes||[])
      .filter(it=>/\.K[QS]$/.test(it.symbol||''))
      .map(it=>({ symbol: it.symbol, description: it.shortname || it.longname || it.symbol }));
    res.json({ result });
  }catch(e){ console.error('[search]', e); res.status(500).json({error:e.message}); }
});

// 이름만 간단 반환
app.get('/api/profile', async (req,res)=>{
  try{
    const symbol = req.query.symbol || '';
    const url = `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${encodeURIComponent(symbol)}`;
    const data = await cached('p:'+symbol, 10, ()=>getJson(url));
    const it = (data.quoteResponse?.result||[])[0] || {};
    res.json({ name: it.longName || it.shortName || symbol });
  }catch(e){ console.error('[profile]', e); res.status(500).json({error:e.message}); }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, ()=>console.log('✅ YF proxy listening on http://localhost:'+PORT));
