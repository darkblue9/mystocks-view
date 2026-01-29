// finnhub-proxy.js
// 간단한 Finnhub 프록시 (Node.js + Express)
// 실행 예시 (PowerShell):
//   $env:FINNHUB_API_KEY="YOUR_KEY"; node finnhub-proxy.js
const express = require('express');
const fetch = require('node-fetch');
const cors = require('cors');

const API_KEY = process.env.FINNHUB_API_KEY || '';
if (!API_KEY) {
  console.error('환경변수 FINNHUB_API_KEY 가 없습니다. 예: $env:FINNHUB_API_KEY="xxxxx"');
  process.exit(1);
}

const app = express();
app.use(cors());
app.use(express.json());

// --- 아주 단순한 메모리 캐시 ---
const cache = new Map();
function cached(key, ttlSec, fn) {
  const now = Date.now();
  const hit = cache.get(key);
  if (hit && (now - hit.t) < ttlSec*1000) return Promise.resolve(hit.v);
  return fn().then(v=>{ cache.set(key, {v, t:Date.now()}); return v; });
}

// 검색
app.get('/api/search', async (req,res)=>{
  try{
    const q = req.query.q || '';
    const url = `https://finnhub.io/api/v1/search?q=${encodeURIComponent(q)}&token=${encodeURIComponent(API_KEY)}`;
    const data = await cached('search:'+q, 5, ()=>fetch(url).then(r=>r.json()));
    res.json(data);
  }catch(e){ console.error(e); res.status(500).json({error:e.message}); }
});

// 프로필
app.get('/api/profile', async (req,res)=>{
  try{
    const symbol = req.query.symbol || '';
    const key = 'profile:'+symbol;
    const url = `https://finnhub.io/api/v1/stock/profile2?symbol=${encodeURIComponent(symbol)}&token=${encodeURIComponent(API_KEY)}`;
    const data = await cached(key, 30, ()=>fetch(url).then(r=>r.json()));
    res.json(data);
  }catch(e){ console.error(e); res.status(500).json({error:e.message}); }
});

// 멀티 Quote (Finnhub은 단건만 지원 → 병렬 + rate limit 완화)
app.get('/api/quote', async (req,res)=>{
  try{
    const symbols = (req.query.symbols||'').split(',').map(s=>s.trim()).filter(Boolean);
    const out = {};
    for (const sym of symbols){
      const key = 'quote:'+sym;
      const data = await cached(key, 3, ()=>fetch(`https://finnhub.io/api/v1/quote?symbol=${encodeURIComponent(sym)}&token=${encodeURIComponent(API_KEY)}`).then(r=>r.json()));
      out[sym] = data;
      await new Promise(r=>setTimeout(r, 120)); // rate limit 완화
    }
    res.json(out);
  }catch(e){ console.error(e); res.status(500).json({error:e.message}); }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, ()=>console.log('✅ Finnhub proxy listening on http://localhost:'+PORT));