# nchart_proxy_line.py
from flask import Flask, Response
import requests

app = Flask(__name__)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HDRS = {
    "User-Agent": UA,
    "Referer": "https://finance.naver.com/",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

# ✅ 실선(area) 전용
AREA = "https://ssl.pstatic.net/imgfinance/chart/item/area/{code}.png"
# 🔁 area가 통신상 막힐 때 대안(모바일 area). 그래도 실선.
AREA_MOBILE = "https://ssl.pstatic.net/imgfinance/chart/mobile/mini/area/{code}.png"

sess = requests.Session()
sess.headers.update(HDRS)

def fetch_img(url):
    r = sess.get(url, timeout=10, allow_redirects=True)
    if r.ok and r.headers.get("Content-Type","").startswith("image/"):
        return r.content
    raise RuntimeError(f"HTTP {r.status_code}")

@app.get("/area/<code>.png")
def area(code):
    # 1순위: area, 2순위: mobile area (둘 다 실선)
    for tmpl in (AREA, AREA_MOBILE):
        try:
            return Response(fetch_img(tmpl.format(code=code)),
                            mimetype="image/png",
                            headers={"Cache-Control":"no-store"})
        except Exception:
            continue
    return Response("FAIL: area blocked", status=502, mimetype="text/plain")

@app.get("/health")
def health():
    try:
        _ = fetch_img(AREA.format(code="005930"))
        return {"ok": True, "src": "area"}
    except Exception:
        try:
            _ = fetch_img(AREA_MOBILE.format(code="005930"))
            return {"ok": True, "src": "area_mobile"}
        except Exception as e:
            return {"ok": False, "error": str(e)}, 502

@app.get("/")
def root():
    return "OK"

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
