import streamlit as st
import sqlite3
import pandas as pd

st.title("🧪 테스트 페이지 (연습용)")

# DB 연결 확인
try:
    conn = sqlite3.connect('my_finance.db')
    # 월덱스 데이터가 있는지 확인해봅니다
    df = pd.read_sql("SELECT * FROM worldex_data LIMIT 10", conn)
    st.success("DB 연결 성공!")
    st.dataframe(df)
    conn.close()
except Exception as e:
    st.error(f"아직 DB 파일이 없거나 에러가 났어요: {e}")
