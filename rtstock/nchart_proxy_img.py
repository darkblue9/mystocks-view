# nchart_proxy_img.py
from flask import Flask, Response
import requests

app = Flask(__name__)
HDRS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.naver.com/"
}
BASE = "https://ssl.pstatic.net/imgfinance/chart/item/area/{code}.png"

@app.get("/chart/<code>.png")
def chart(code):
    url = BASE.format(code=code)
    r = requests.get(url, headers=HDRS, timeout=10)
    return Response(r.content, status=r.status_code,
                    headers={"Content-Type":"image/png","Cache-Control":"no-store"})

@app.get("/")
def ok():
    return "OK"

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
