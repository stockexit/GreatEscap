import streamlit as st
import sqlite3
import pandas as pd

# 1. 페이지 설정
st.set_page_config(layout="wide")
st.title("📊 Stockexit: 마스터 재무 분석")

# 2. 사이드바 - 종목 선택
st.sidebar.header("🔍 분석 대상")
company = st.sidebar.selectbox("종목을 선택하세요", ["삼성전자", "월덱스"])

# 3. 데이터 불러오기 (통합 테이블 finance_all 사용)
conn = sqlite3.connect('my_finance.db')
# 선택한 종목의 데이터만 가져옵니다.
query = f"SELECT stock_name, bsns_year, quarter, account_nm, thstrm_amount, sj_div FROM finance_all WHERE stock_name = '{company}'"
df = pd.read_sql(query, conn)
conn.close()

# 4. 단위 설정 (삼성은 조 단위, 나머지는 억 단위)
if company == "삼성전자":
    unit = 1000000000000 # 1조
    unit_nm = "조원"
else:
    unit = 100000000 # 1억
    unit_nm = "억원"

df['amount'] = pd.to_numeric(df['thstrm_amount'], errors='coerce') / unit

# 5. ⭐️ 표준 템플릿 정의 (사용자님이 주신 리스트) ⭐️
# DART의 다양한 표현을 우리가 원하는 표준 이름으로 연결하는 지도입니다.

# [손익계산서 매핑]
is_map = {
    '매출액': '01. 매출액', '수익(매출액)': '01. 매출액', '영업수익': '01. 매출액',
    '매출원가': '02. 매출원가', '영업원가': '02. 매출원가',
    '매출총이익': '03. 매출총이익',
    '판매비와관리비': '04. 판매비와 관리비',
    '영업이익': '05. 영업이익', '영업이익(손실)': '05. 영업이익',
    '금융수익': '06. 금융수익',
    '금융원가': '07. 금융원가', '금융비용': '07. 금융원가',
    '기타수익': '08. 기타수익',
    '기타비용': '09. 기타비용', '기타손실': '09. 기타비용',
    '법인세비용차감전순이익': '10. 세전계속사업이익', '법인세비용차감전계속사업이익': '10. 세전계속사업이익',
    '법인세비용': '11. 법인세비용',
    '당기순이익': '12. 당기순이익', '당기순이익(손실)': '12. 당기순이익', '분기순이익': '12. 당기순이익', '분기순이익(손실)': '12. 당기순이익',
    '지배기업의 소유주에게 귀속되는 당기순이익': '13. 지배주주순이익', '지배기업소유주지분': '13. 지배주주순이익',
    '비지배지분': '14. 비지배주주순이익', '비지배지분에게 귀속되는 당기순이익': '14. 비지배주주순이익'
}

# [재무상태표 매핑]
bs_map = {
    '자산총계': '01. 자산총계',
    '유동자산': '02. 유동자산',
    '비유동자산': '03. 비유동자산',
    '부채총계': '04. 부채총계',
    '유동부채': '05. 유동부채',
    '비유동부채': '06. 비유동부채',
    '자본총계': '07. 자본총계'
}

# [현금흐름표 매핑]
cf_map = {
    '영업활동현금흐름': '01. 영업활동 현금흐름', '영업활동으로 인한 현금흐름': '01. 영업활동 현금흐름',
    '투자활동현금흐름': '02. 투자활동 현금흐름', '투자활동으로 인한 현금흐름': '02. 투자활동 현금흐름',
    '재무활동현금흐름': '03. 재무활동 현금흐름', '재무활동으로 인한 현금흐름': '03. 재무활동 현금흐름',
    '기말현금및현금성자산': '04. 기말 현금', '현금및현금성자산의 기말잔액': '04. 기말 현금'
}

# 6. 화면 출력 (탭 구성)
st.subheader(f"📈 {company} 재무제표 (단위: {unit_nm})")
tab1, tab2, tab3 = st.tabs(["손익계산서", "재무상태표", "현금흐름표"])

def show_table(mapping_dict):
    # 선택된 맵핑에 맞는 데이터만 필터링 및 이름 변경
    temp_df = df.copy()
    temp_df['standard_name'] = temp_df['account_nm'].map(mapping_dict)
    temp_df = temp_df.dropna(subset=['standard_name'])
    
    # 피벗 테이블 생성
    pivot = temp_df.pivot_table(
        index='standard_name', 
        columns=['bsns_year', 'quarter'], 
        values='amount', 
        aggfunc='first'
    )
    
    # 최신순 정렬
    pivot = pivot[pivot.columns[::-1]]
    
    # 스타일링 후 출력
    st.dataframe(pivot.style.format(f"{{:,.1f}} {unit_nm}"))

with tab1:
    st.markdown("#### 📋 손익계산서 (Income Statement)")
    show_table(is_map)

with tab2:
    st.markdown("#### 🏛️ 재무상태표 (Balance Sheet)")
    show_table(bs_map)

with tab3:
    st.markdown("#### 💸 현금흐름표 (Cash Flow)")
    show_table(cf_map)
