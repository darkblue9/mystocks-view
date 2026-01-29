from flask import Flask, Response
import requests

app = Flask(__name__)
HDRS = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com"}
BASE = "https://ssl.pstatic.net/imgfinance/chart/item/area/{code}.png"

@app.route("/chart/<code>.png")
def chart(code):
    r = requests.get(BASE.format(code=code), headers=HDRS)
    return Response(r.content, mimetype="image/png")

app.run(port=5000)
