import streamlit as st
import pandas as pd
import libsql_experimental as libsql

# -------------------------------------------------------------------
# 1. 페이지 설정
# -------------------------------------------------------------------
st.set_page_config(
    page_title="나의 보물창고",
    page_icon="💰",
    layout="wide"
)

# -------------------------------------------------------------------
# 2. DB 연결 함수
# -------------------------------------------------------------------
def get_connection():
    url = st.secrets["db"]["url"]
    auth_token = st.secrets["db"]["auth_token"]
    return libsql.connect("pykrx.db", sync_url=url, auth_token=auth_token)

# -------------------------------------------------------------------
# 3. 데이터 전처리 (방탄 조끼)
# -------------------------------------------------------------------
def process_data(df):
    if df.empty:
        return df

    numeric_cols = ['현재가', '등락률', '거래량', '전일거래량', '시가', '고가', '저가', '외국인순매수', '기관순매수']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    if '전일거래량' in df.columns:
        df['전일거래량'] = df['전일거래량'].replace(0, 1)

    df['거래량비율'] = df['거래량'] / df['전일거래량']
    
    return df

# -------------------------------------------------------------------
# 4. 메인 화면
# -------------------------------------------------------------------
def main():
    st.title("💰 주식 보물창고 (Ver 2.1)")

    # (1) DB 연결 및 날짜 목록 조회
    try:
        conn = get_connection()
        date_rows = conn.execute("SELECT DISTINCT 날짜 FROM Npaystocks ORDER BY 날짜 DESC").fetchall()
        all_dates = [str(row[0]) for row in date_rows]

        if not all_dates:
            st.warning("데이터가 없습니다. 수집기를 먼저 실행해주세요.")
            return

        # (2) 사이드바: 날짜 선택
        with st.sidebar:
            st.header("📅 타임머신")
            selected_date = st.selectbox(
                "언제 데이터를 볼까요?",
                all_dates,
                index=0  # 맨 위(최신)가 기본
            )
            st.markdown("---")
            st.caption("※ 낮에 실행하면 오늘 데이터는 0으로 보일 수 있습니다. 그럴 땐 어제 날짜를 선택하세요!")

        # (3) 선택한 날짜 데이터 가져오기
        query = f"SELECT * FROM Npaystocks WHERE 날짜 = '{selected_date}'"
        rows = conn.execute(query).fetchall()
        columns = [description[0] for description in conn.execute(query).description]
        raw_df = pd.DataFrame(rows, columns=columns)
        
        df = process_data(raw_df)

    except Exception as e:
        st.error(f"데이터 로드 중 오류: {e}")
        return

    # 기준 날짜 표시
    st.markdown(f"###### 📅 조회 기준일: **{selected_date}** (총 {len(df)}개 종목)")
    st.divider()

    if df.empty:
        st.info("선택한 날짜에 데이터가 없습니다.")
        return

    # 탭 구성
    tab1, tab2, tab3, tab4 = st.tabs(["🔥 돈냄새(거래량)", "🐜 개미털기", "🤝 쌍끌이 매수", "📋 전체 목록"])

    # --- TAB 1: 돈냄새 ---
    with tab1:
        st.header("폭발적인 관심을 받는 종목")
        df_money = df[df['거래량비율'] >= 5.0].copy()
        df_money = df_money.sort_values(by='거래량비율', ascending=False)
        
        if df_money.empty:
            st.info("거래량 5배 이상 터진 종목이 없습니다.")
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

    # --- TAB 2: 개미털기 ---
    with tab2:
        st.header("가격은 하락했지만 수급이 들어온 종목")
        condition_ant = (df['등락률'] < 0) & ((df['외국인순매수'] > 0) | (df['기관순매수'] > 0))
        df_ant = df[condition_ant].copy()
        df_ant = df_ant.sort_values(by='외국인순매수', ascending=False)

        if df_ant.empty:
            st.info("조건에 맞는 종목이 없습니다. (장중에는 집계가 안 될 수 있습니다)")
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

    # --- TAB 3: 쌍끌이 ---
    with tab3:
        st.header("외국인과 기관이 같이 사는 종목")
        condition_double = (df['외국인순매수'] > 0) & (df['기관순매수'] > 0)
        df_double = df[condition_double].copy()
        df_double['합산매수'] = df_double['외국인순매수'] + df_double['기관순매수']
        df_double = df_double.sort_values(by='합산매수', ascending=False)

        if df_double.empty:
            st.info("쌍끌이 종목이 없습니다. (장중에는 집계가 안 될 수 있습니다)")
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

    # --- TAB 4: 전체 ---
    with tab4:
        st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()