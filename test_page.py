import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(layout="wide") # 화면을 넓게 씁니다
st.title("🧪 Stockexit: 월덱스 분석 테스트")

# 1. DB 연결 및 데이터 가져오기
conn = sqlite3.connect('my_finance.db')
query = "SELECT bsns_year, reprt_code, account_nm, thstrm_amount FROM worldex_data"
df = pd.read_sql(query, conn)
conn.close()

# 2. 데이터 정제 (우리가 연습했던 로직)
df['thstrm_amount'] = pd.to_numeric(df['thstrm_amount'], errors='coerce')
name_map = {
    '매출액': '매출액', '수익(매출액)': '매출액', '영업수익': '매출액',
    '영업이익': '영업이익', '영업이익(손실)': '영업이익',
    '당기순이익': '당기순이익', '당기순이익(손실)': '당기순이익', '분기순이익': '당기순이익'
}
df['standard_name'] = df['account_nm'].map(name_map)
df = df.dropna(subset=['standard_name'])

# 3. 분기 계산 및 피벗
code_map = {'11013': '1Q', '11012': '2Q', '11014': '3Q', '11011': 'Year'}
df['quarter'] = df['reprt_code'].map(code_map)
pivot = df.pivot_table(index='bsns_year', columns=['standard_name', 'quarter'], values='thstrm_amount', aggfunc='first')

# 4Q 계산
for acc in ['매출액', '영업이익', '당기순이익']:
    if (acc, 'Year') in pivot.columns:
        q1, q2, q3 = pivot.get((acc, '1Q'), 0), pivot.get((acc, '2Q'), 0), pivot.get((acc, '3Q'), 0)
        pivot[(acc, '4Q')] = pivot[(acc, 'Year')] - (q1.fillna(0) + q2.fillna(0) + q3.fillna(0))

# 4. 정렬 및 단위 변환 (억 원)
final_df = pivot.reindex(columns=['1Q', '2Q', '3Q', '4Q'], level=1) / 10**8
final_table = final_df.stack(level=1).T
final_table.columns = [f"{year} {q}" for year, q in final_table.columns]
final_table = final_table.reindex(['매출액', '영업이익', '당기순이익']) # 항목 순서
final_table = final_table[final_table.columns[::-1]] # 최신순

# 5. 웹 화면에 출력
st.success("✅ 버틀러 스타일로 정렬 완료!")
st.dataframe(final_table.style.format("{:,.1f} 억")) # 소수점 첫째자리와 '억' 표시
