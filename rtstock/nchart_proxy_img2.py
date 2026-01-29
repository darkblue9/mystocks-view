# nchart_proxy_img2.py
from flask import Flask, Response, jsonify
import requests, sys

app = Flask(__name__)

# 네이버 이미지 경로 후보들 (일부망에서 경로별 허용/차단 다름)
CANDIDATES = [
    "https://ssl.pstatic.net/imgfinance/chart/item/area/{code}.png",
    "https://ssl.pstatic.net/imgfinance/chart/item/candle/day/{code}.png",    # candlestick(백업)
    "https://ssl.pstatic.net/imgfinance/chart/mobile/mini/area/{code}.png",   # 모바일 미니(있으면 사용)
]

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com/",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

sess = requests.Session()
sess.headers.update(COMMON_HEADERS)

def fetch_img(code):
    last_err = None
    for tmpl in CANDIDATES:
        url = tmpl.format(code=code)
        try:
            r = sess.get(url, timeout=10, allow_redirects=True)
            print(f"[NAVER] {url} -> {r.status_code} {r.headers.get('Content-Type')}", file=sys.stderr)
            if r.ok and r.headers.get("Content-Type","").startswith("image/"):
                return r.content
            last_err = f"HTTP {r.status_code} {r.text[:120]}"
        except Exception as e:
            last_err = str(e)
            print(f"[ERR] {url} -> {e}", file=sys.stderr)
    raise RuntimeError(last_err or "unknown error")

@app.get("/chart/<code>.png")
def chart(code):
    try:
        png = fetch_img(code)
        return Response(png, mimetype="image/png",
                        headers={"Cache-Control":"no-store"})
    except Exception as e:
        return Response(f"FAIL: {e}", status=502, mimetype="text/plain")

@app.get("/health")
def health():
    # 간이 헬스체크 (삼성전자 시도)
    try:
        _ = fetch_img("005930")
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 502

@app.get("/")
def root():
    return "OK"

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
