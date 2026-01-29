import streamlit as st
import pandas as pd
import requests
import json

# 1. 화면 세팅
st.set_page_config(page_title="동일의 주식 보물지도", page_icon="📈", layout="wide")

st.title("📈 동일의 주식 보물지도 (Pro Ver.)")
st.markdown("Run by **Turso DB** & **Streamlit** | Data: **OHLC + 수급(외인/기관)**")

# 2. Turso HTTP API 통신 함수
def query_turso(sql_query):
    try:
        db_url = st.secrets["TURSO_DB_URL"]
        auth_token = st.secrets["TURSO_AUTH_TOKEN"]
        
        if db_url.startswith("libsql://"):
            db_url = db_url.replace("libsql://", "https://")
        
        url = f"{db_url}/v2/pipeline"
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        payload = {
            "requests": [
                {"type": "execute", "stmt": {"sql": sql_query}}
            ],
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            try:
                if not result['results'][0]['response']['result']: 
                     return pd.DataFrame()
                res_data = result['results'][0]['response']['result']
                cols = [c['name'] for c in res_data['cols']]
                rows = []
                for r in res_data['rows']:
                    row_vals = []
                    for val in r:
                        if isinstance(val, dict): 
                            row_vals.append(val.get('value'))
                        else:
                            row_vals.append(val)
                    rows.append(row_vals)
                return pd.DataFrame(rows, columns=cols)
            except (KeyError, IndexError):
                return pd.DataFrame()
        else:
            st.error(f"통신 에러: {response.text}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"함수 에러: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# [핵심] 쿼리 저장소 (수급 데이터 반영)
# ---------------------------------------------------------

# 공통 CTE: 오늘 날짜 기준 데이터만 필터링 (최신 데이터)
base_cte = """
WITH latest_data AS (
    SELECT * FROM Npaystocks 
    WHERE 날짜 = (SELECT MAX(날짜) FROM Npaystocks)
)
"""

tab1, tab2, tab3, tab4 = st.tabs(["🐋 쌍끌이 매집 (수급)", "🔥 돈 냄새 (급등)", "🤫 개미 털기 (스윙)", "🔍 데이터 확인"])

# ---------------------------------------------------------
# 탭 1: 쌍끌이 매집 (Foreigner + Institution Buy)
# ---------------------------------------------------------
with tab1:
    st.header("🐋 세력 형님들이 같이 사는 종목 (양매수)")
    st.caption("조건: 외국인과 기관이 동시에 순매수 + 주가 상승")
    
    sql_whale = base_cte + """
    SELECT 
        종목명, 현재가, 
        ROUND(등락률, 2) || '%' AS 등락률,
        거래량,
        외국인순매수, 기관순매수, 개인순매수,
        업종명,
        indate AS 수집시간
    FROM latest_data
    WHERE 외국인순매수 > 0 
      AND 기관순매수 > 0
      AND 등락률 > 0
    ORDER BY (외국인순매수 + 기관순매수) DESC
    LIMIT 30
    """
    
    if st.button("쌍끌이 포착", key="btn_whale"):
        df = query_turso(sql_whale)
        if not df.empty:
            # 보기 좋게 포맷팅 (천 단위 콤마)
            # 주의: 데이터가 문자열로 올 수 있어서 처리
            st.dataframe(df, use_container_width=True)
        else:
            st.info("오늘 쌍끌이 매수 종목이 없거나 데이터가 아직 수집되지 않았어.")

# ---------------------------------------------------------
# 탭 2: 돈 냄새 (Volume Spike)
# ---------------------------------------------------------
with tab2:
    st.header("🔥 돈 냄새가 진동하는 놈들")
    st.caption("조건: 거래량 폭발 + 외국인 매수 개입")
    
    sql_money = base_cte + """
    SELECT 
        종목명, 현재가, 
        ROUND(등락률, 2) || '%' AS 등락률,
        거래량, 전일거래량,
        ROUND((거래량 - 전일거래량)*100.0/전일거래량, 1) || '%' AS 거래량급증,
        외국인순매수, 
        (현재가 * 거래량) / 100000000 AS 거래대금_억,
        업종명
    FROM latest_data
    WHERE 거래량 >= 전일거래량 * 3
      AND 전일거래량 > 0
      AND 등락률 >= 3
      AND 외국인순매수 > 0  -- 외국인이 냄새 맡고 온 것만
    ORDER BY 등락률 DESC
    LIMIT 30
    """
    
    if st.button("급등주 포착", key="btn_money"):
        df = query_turso(sql_money)
        st.dataframe(df, use_container_width=True)

# ---------------------------------------------------------
# 탭 3: 개미 털기 (Swing) - 캔들 분석 추가
# ---------------------------------------------------------
with tab3:
    st.header("🤫 개미 털고 조용히 가는 놈들")
    st.caption("조건: 아래꼬리 달림(저가 대비 반등) + 기관 매집")
    
    # 저가보다 현재가가 2% 이상 높게 끝난 것 (장중 털고 올라옴)
    sql_quiet = base_cte + """
    SELECT 
        종목명, 현재가, 저가, 시가,
        ROUND((현재가 - 저가)*100.0/저가, 2) || '%' AS 아래꼬리반등,
        기관순매수, 외국인순매수,
        거래량
    FROM latest_data
    WHERE 저가 < 시가        -- 장중 음봉 갔다가
      AND 현재가 > 저가 * 1.02 -- 저점에서 2% 이상 말아올림
      AND 기관순매수 > 0     -- 기관이 받쳐줌
    ORDER BY 기관순매수 DESC
    LIMIT 30
    """
    
    if st.button("눌림목 포착", key="btn_quiet"):
        df = query_turso(sql_quiet)
        st.dataframe(df, use_container_width=True)

# ---------------------------------------------------------
# 탭 4: 데이터 확인 (Raw Data)
# ---------------------------------------------------------
with tab4:
    st.header("🔍 DB 데이터 까보기")
    st.write("실제로 데이터가 잘 들어갔는지 최신 5건만 조회해볼게.")
    
    sql_check = """
    SELECT 날짜, 종목명, 외국인순매수, 기관순매수, 시가, 고가, 저가, indate 
    FROM Npaystocks 
    ORDER BY rowid DESC 
    LIMIT 5
    """
    if st.button("최신 데이터 5건 조회"):
        df = query_turso(sql_check)
        st.dataframe(df)