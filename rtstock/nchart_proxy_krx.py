# nchart_proxy_krx.py
from flask import Flask, jsonify, request
import requests, time

app = Flask(__name__)

HDRS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://api.stock.naver.com/"
}

# 네이버 최신 차트 API (국내 종목)
# duration: 1d, 5d, 1m, 3m, 6m, 1y ...
# interval: 1, 5, 10, 30, 60, day, week ...
NAVER_CHART_API = "https://api.stock.naver.com/chart/domestic/item/{code}?duration={duration}"

def fetch_chart(code, duration="1m"):
    # duration에 따라 interval 자동 선택 (네이버가 duration별 기본 제공)
    url = NAVER_CHART_API.format(code=code, duration=duration)
    r = requests.get(url, headers=HDRS, timeout=10)
    r.raise_for_status()
    return r.json()

@app.get("/series/<code>")
def series(code):
    duration = request.args.get("range", "1m")  # 1m,3m,6m,1y...
    try:
        raw = fetch_chart(code, duration)
        # 네이버 응답: timestamps(ms), closes, etc.
        ts = raw.get("timestamps") or []
        closes = raw.get("close") or raw.get("closes") or []
        data = []
        for i, t in enumerate(ts):
            if i < len(closes) and closes[i] is not None:
                # Lightweight Charts는 초 단위 epoch 필요
                data.append({"time": int(t/1000), "value": float(closes[i])})
        # 현재가/등락률도 전달(헤더에 표시)
        cur = raw.get("meta", {}).get("lastClose")  # 종가(참고)
        return jsonify({"ok": True, "data": data, "price": cur})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/")
def root():
    return "OK"

if __name__ == "__main__":
    # 127.0.0.1:5001 로 구동
    app.run(host="127.0.0.1", port=5001, debug=False)
