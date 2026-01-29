import streamlit as st
import pandas as pd
import requests
import json

# 1. 화면 세팅
st.set_page_config(page_title="주식 분석 지도", page_icon="📈", layout="wide")

st.title("📈 주식 분석 지도")
st.markdown("Run by **Turso DB** & **Streamlit**")

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
                # 결과가 비어있을 때 처리
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
# [수정됨] 쿼리 저장소: indate 컬럼 추가
# ---------------------------------------------------------

# 공통: indate(입력시간) 추가
view_sql = """
WITH v_stocks_plus AS (
    SELECT 
        indate,  -- [추가] 입력 시간
        날짜, 구분, 종목명, 현재가, 전일비, 
        ROUND(등락률/100.0, 4) as 등락률, 
        거래량, 전일거래량, 시가총액, 상장주식수 
    FROM Npaystocks 
    WHERE 등락률 > 0
)
"""

tab1, tab2, tab3 = st.tabs(["🔥 돈 냄새 (급등주)", "🤫 개미 털기 (스윙)", "🔍 테이블 확인"])

with tab1:
    st.header("🔥 돈 냄새가 진동하는 놈들")
    st.caption("조건: 거래량 3배 폭발 + 3~15% 상승 + 중형주")
    
    # [수정] SELECT 맨 앞에 indate 추가
    sql_money = view_sql + """
    SELECT 
        indate AS 수집시간,  -- [추가]
        날짜, 종목명, 현재가, 
        ROUND(등락률 * 100, 2) || '%' AS 등락률,
        ROUND(거래량 * 1.0 / 전일거래량 * 100, 1) || '%' AS 거래량급증률,
        ROUND(거래량 * 1.0 / 상장주식수 * 100, 1) || '%' AS 거래회전율, 
        ROUND((현재가 * 거래량) / 100000000.0, 1) || '억' AS 거래대금,
        ROUND(시가총액 / 10000.0, 1) || '조' AS 시가총액_조단위
    FROM v_stocks_plus
    WHERE 날짜 = (SELECT MAX(날짜) FROM Npaystocks)
      AND 전일거래량 > 0
      AND 거래량 >= 전일거래량 * 3          
      AND 등락률 BETWEEN 0.03 AND 0.15      
      AND 시가총액 BETWEEN 1000 AND 50000   
      AND (현재가 * 거래량) >= 5000000000   
      
      -- 필터링
      AND 종목명 NOT LIKE '%KODEX%' 
      AND 종목명 NOT LIKE '%TIGER%' 
      AND 종목명 NOT LIKE '%ETN%' 
      AND 종목명 NOT LIKE '%스팩%' 
      AND 종목명 NOT LIKE '%우'
      AND 종목명 NOT LIKE 'RISE%'
      AND 종목명 NOT LIKE 'KoAct%'
      AND 종목명 NOT LIKE 'TIMEFOLIO%'
      AND 종목명 NOT LIKE 'SOL%'
      AND 종목명 NOT LIKE 'ACE%'
      AND 종목명 NOT LIKE 'HANARO%'
    ORDER BY 거래회전율 DESC, 거래량급증률 DESC;
    """
    
    if st.button("돈 냄새 맡기", key="btn_money"):
        with st.spinner('데이터 분석 중...'):
            df = query_turso(sql_money)
            if not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("조건에 맞는 종목이 없습니다.")

with tab2:
    st.header("🤫 개미 털고 조용히 가는 놈들")
    st.caption("조건: 3일 연속 상승 + 거래량은 오히려 감소 (매집 의심)")
    
    # [수정] SELECT 및 내부 쿼리에 indate 전달
    sql_quiet = """
    WITH v_stocks_plus AS (
        SELECT 
            indate, -- [추가]
            날짜, 구분, 종목명, 현재가, 전일비, 
            ROUND(등락률/100.0, 4) as 등락률, 
            거래량, 전일거래량, 시가총액, 상장주식수 
        FROM Npaystocks 
        WHERE 등락률 > 0
    ),
    trading_days AS (
        SELECT DISTINCT 날짜 FROM v_stocks_plus ORDER BY 날짜
    ),
    numbered_days AS (
        SELECT 날짜, ROW_NUMBER() OVER (ORDER BY 날짜) AS day_seq
        FROM trading_days
    ),
    stock_days AS (
        SELECT n.종목명, n.날짜, d.day_seq,
            ROW_NUMBER() OVER (PARTITION BY n.종목명 ORDER BY n.날짜) AS rn
        FROM v_stocks_plus n JOIN numbered_days d USING (날짜)
    ),
    groups AS (
        SELECT 종목명, 날짜, day_seq, rn, day_seq - rn AS grp
        FROM stock_days
    ),
    latest_date AS (
        SELECT MAX(날짜) AS max_date FROM v_stocks_plus
    ),
    current_streak_group AS (
        SELECT g.종목명, g.grp
        FROM groups g JOIN latest_date l ON g.날짜 = l.max_date
    ),
    streaks AS (
        SELECT g.종목명, COUNT(*) AS 연속일수 
        FROM groups g
        JOIN current_streak_group c ON g.종목명 = c.종목명 AND g.grp = c.grp
        GROUP BY g.종목명
    )
    SELECT 
        d.indate AS 수집시간, -- [추가] 최종 출력,
          d.날짜,
        s.종목명, 
        s.연속일수, 
        d.현재가, 
        ROUND(d.등락률 * 100, 2) || '%' AS 등락률,
        d.거래량, 
        d.전일거래량,
        ROUND(d.거래량증가율 * 100, 1) || '%' AS 거래량증가율,
        CASE 
            WHEN d.거래량 < d.전일거래량 THEN '매집의심(감소)'
            ELSE '보통'
        END AS 신호
    FROM streaks s 
    JOIN latest_date l
    JOIN (
        SELECT 
            indate, -- [추가] 내부 전달
            날짜, 종목명, 현재가, 전일비, 등락률, 거래량, 전일거래량, 시가총액,
            CASE WHEN 전일거래량 IS NULL OR 전일거래량 = 0 THEN 0 ELSE (거래량 - 전일거래량) * 1.0 / 전일거래량 END AS 거래량증가율
        FROM v_stocks_plus
    ) d ON d.날짜 = l.max_date AND d.종목명 = s.종목명
    WHERE s.연속일수 >= 3
      AND d.거래량 < d.전일거래량
      AND d.시가총액 BETWEEN 300 AND 3000
      AND d.등락률 BETWEEN 0.01 AND 0.12
      AND d.거래량증가율 BETWEEN -0.8 AND -0.2
    ORDER BY s.연속일수 DESC, d.등락률 DESC;
    """
    
    if st.button("조용한 놈들 찾기", key="btn_quiet"):
        with st.spinner('세력 발자국 추적 중...'):
            df = query_turso(sql_quiet)
            if not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("조건에 맞는 종목이 없습니다.")

with tab3:
    st.header("내 DB 테이블 목록")
    if st.button("테이블 스캔"):
        df = query_turso("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        st.dataframe(df)