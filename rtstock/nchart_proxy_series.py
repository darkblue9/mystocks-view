# nchart_proxy_series.py
from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://m.stock.naver.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

# 네이버 차트 API (국내)
# duration 예시: 1d, 5d, 1m, 3m, 6m, 1y
NAVER_API = "https://api.stock.naver.com/chart/domestic/item/{code}?duration={duration}"

sess = requests.Session()
sess.headers.update(HDRS)

def fetch_series(code: str, duration: str):
    url = NAVER_API.format(code=code, duration=duration)
    r = sess.get(url, timeout=10)
    r.raise_for_status()
    j = r.json()
    # 기대 구조: {"timestamps":[...ms...], "close":[...], "meta":{...}}
    ts = j.get("timestamps") or []
    closes = j.get("close") or j.get("closes") or []
    data = []
    for i, t in enumerate(ts):
        if i < len(closes) and closes[i] is not None:
            # Lightweight-Charts는 초 단위 epoch 사용
            data.append({"time": int(t/1000), "value": float(closes[i])})
    price = None
    meta = j.get("meta") or {}
    for k in ("lastClose","lastPrice","closePrice"):
        if meta.get(k) is not None:
            price = float(meta[k])
            break
    return {"ok": True, "data": data, "price": price}

@app.get("/series/<code>")
def series(code):
    duration = request.args.get("range", "1m")
    try:
        return jsonify(fetch_series(code, duration))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

@app.get("/health")
def health():
    try:
        _ = fetch_series("005930", "1m")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 502

@app.get("/")
def root():
    return "OK"

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
