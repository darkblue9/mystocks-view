import streamlit as st
import pandas as pd
import libsql_experimental as libsql

# -------------------------------------------------------------------
# 1. 페이지 설정 (반드시 맨 처음에 와야 함)
# -------------------------------------------------------------------
st.set_page_config(
    page_title="나의 보물창고",
    page_icon="💰",
    layout="wide"
)

# -------------------------------------------------------------------
# 2. DB 연결 함수 (Turso)
# -------------------------------------------------------------------
def get_connection():
    url = st.secrets["db"]["url"]
    auth_token = st.secrets["db"]["auth_token"]
    return libsql.connect("pykrx.db", sync_url=url, auth_token=auth_token)

# -------------------------------------------------------------------
# 3. 데이터 가져오기 (캐싱 적용)
# -------------------------------------------------------------------
@st.cache_data(ttl=600)  # 10분마다 갱신
def load_data():
    conn = get_connection()
    # 가장 최근 날짜의 데이터만 가져오기
    query = """
    SELECT * FROM Npaystocks 
    WHERE 날짜 = (SELECT MAX(날짜) FROM Npaystocks)
    """
    rows = conn.execute(query).fetchall()
    
    # 컬럼명 가져오기
    columns = [description[0] for description in conn.execute(query).description]
    df = pd.DataFrame(rows, columns=columns)
    
    return df

# -------------------------------------------------------------------
# 4. 데이터 전처리 (방탄 조끼 입히기)
# -------------------------------------------------------------------
def process_data(df):
    if df.empty:
        return df

    # (1) 숫자로 변환 (문자가 섞여 있으면 에러 나므로 강제 변환)
    numeric_cols = ['현재가', '등락률', '거래량', '전일거래량', '시가', '고가', '저가', '외국인순매수', '기관순매수']
    for col in numeric_cols:
        if col in df.columns:
            # 에러(문자)가 있으면 NaN으로 바꾸고 -> 0으로 채움
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # (2) 0 나누기 방지 (전일거래량이 0이면 1로 변경)
    if '전일거래량' in df.columns:
        df['전일거래량'] = df['전일거래량'].replace(0, 1)

    # (3) 파생 지표 계산
    # 거래량 급증 비율 (오늘 / 어제)
    df['거래량비율'] = df['거래량'] / df['전일거래량']
    
    return df

# -------------------------------------------------------------------
# 5. 메인 화면 구성
# -------------------------------------------------------------------
def main():
    st.title("💰 주식 보물창고 (Ver 2.0)")

    # 데이터 로드
    try:
        raw_df = load_data()
        df = process_data(raw_df)
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return

    if df.empty:
        st.warning("데이터가 없습니다. 수집기를 확인해주세요.")
        return

    # 기준 날짜 표시
    base_date = df['날짜'].iloc[0]
    st.markdown(f"###### 📅 기준일: **{base_date}** (총 {len(df)}개 종목)")
    st.divider()

    # 탭 구성
    tab1, tab2, tab3, tab4 = st.tabs(["🔥 돈냄새(거래량)", "🐜 개미털기", "🤝 쌍끌이 매수", "📋 전체 목록"])

    # ----------------------------------------------------------------
    # TAB 1: 돈냄새 (거래량 5배 폭발)
    # ----------------------------------------------------------------
    with tab1:
        st.header("폭발적인 관심을 받는 종목")
        # 조건: 거래량비율 5배(5.0) 이상
        df_money = df[df['거래량비율'] >= 5.0].copy()
        
        # 보기 좋게 정렬
        df_money = df_money.sort_values(by='거래량비율', ascending=False)
        
        if df_money.empty:
            st.info("오늘 거래량이 5배 이상 터진 종목이 없습니다.")
        else:
            st.dataframe(
                df_money[['종목명', '현재가', '등락률', '거래량', '전일거래량', '거래량비율']],
                column_config={
                    "현재가": st.column_config.NumberColumn(format="%d원"),
                    "등락률": st.column_config.NumberColumn(format="%.2f%%"),
                    "거래량비율": st.column_config.NumberColumn(format="%.1f배"),
                },
                use_container_width=True,
                hide_index=True
            )

    # ----------------------------------------------------------------
    # TAB 2: 개미털기 (가격은 떨어졌는데 형님들은 샀다)
    # ----------------------------------------------------------------
    with tab2:
        st.header("가격은 하락했지만 수급이 들어온 종목")
        # 조건: 등락률 < 0 (음봉) AND (외국인 > 0 OR 기관 > 0)
        condition_ant = (df['등락률'] < 0) & ((df['외국인순매수'] > 0) | (df['기관순매수'] > 0))
        df_ant = df[condition_ant].copy()
        
        # 정렬: 외국인 많이 산 순서
        df_ant = df_ant.sort_values(by='외국인순매수', ascending=False)

        if df_ant.empty:
            st.info("조건에 맞는 개미털기 의심 종목이 없습니다.")
        else:
            st.dataframe(
                df_ant[['종목명', '현재가', '등락률', '외국인순매수', '기관순매수']],
                column_config={
                    "현재가": st.column_config.NumberColumn(format="%d원"),
                    "등락률": st.column_config.NumberColumn(format="%.2f%%"),
                    "외국인순매수": st.column_config.NumberColumn(format="%d주"),
                    "기관순매수": st.column_config.NumberColumn(format="%d주"),
                },
                use_container_width=True,
                hide_index=True
            )

    # ----------------------------------------------------------------
    # TAB 3: 쌍끌이 (외국인 + 기관 동시 매수)
    # ----------------------------------------------------------------
    with tab3:
        st.header("외국인과 기관이 같이 사는 종목")
        # 조건: 외국인 > 0 AND 기관 > 0
        condition_double = (df['외국인순매수'] > 0) & (df['기관순매수'] > 0)
        df_double = df[condition_double].copy()
        
        # 합산 매수량으로 정렬
        df_double['합산매수'] = df_double['외국인순매수'] + df_double['기관순매수']
        df_double = df_double.sort_values(by='합산매수', ascending=False)

        if df_double.empty:
            st.info("쌍끌이 매수 종목이 없습니다.")
        else:
            st.dataframe(
                df_double[['종목명', '현재가', '등락률', '외국인순매수', '기관순매수']],
                column_config={
                    "현재가": st.column_config.NumberColumn(format="%d원"),
                    "등락률": st.column_config.NumberColumn(format="%.2f%%"),
                },
                use_container_width=True,
                hide_index=True
            )

    # ----------------------------------------------------------------
    # TAB 4: 전체 데이터 ddddd
    # ----------------------------------------------------------------
    with tab4:
        st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()