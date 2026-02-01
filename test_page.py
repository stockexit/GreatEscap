import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(layout="wide")
st.title("📑 월덱스 손익계산서 전체 항목 테스트")

# 1. DB 연결 (worldex_full 테이블 사용)
try:
    conn = sqlite3.connect('my_finance.db')
    query = "SELECT bsns_year, quarter, account_nm, thstrm_amount FROM worldex_full"
    df = pd.read_sql(query, conn)
    conn.close()

    # 2. 데이터 처리
    df['thstrm_amount'] = pd.to_numeric(df['thstrm_amount'], errors='coerce') / 10**8 # 억원 단위

    # 3. 피벗 테이블 생성 (세로: 항목명, 가로: 연도/분기)
    # DART에서 가져온 모든 account_nm이 행(Index)으로 들어갑니다.
    pivot = df.pivot_table(
        index='account_nm', 
        columns=['bsns_year', 'quarter'], 
        values='thstrm_amount', 
        aggfunc='first'
    )

    # 4. 정렬: 최신 분기가 가장 왼쪽으로 오도록 뒤집기
    pivot = pivot[pivot.columns[::-1]]

    # 5. 결과 출력
    st.success(f"✅ DB에서 {len(pivot)}개의 항목을 성공적으로 불러왔습니다!")
    st.dataframe(pivot.style.format("{:,.1f} 억"))

except Exception as e:
    st.error(f"데이터를 불러오는 중 에러가 발생했습니다: {e}")
