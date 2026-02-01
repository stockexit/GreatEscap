import streamlit as st
import sqlite3
import pandas as pd

# 1. 페이지 기본 설정
st.set_page_config(layout="wide", page_title="Stockexit Master View")
st.title("📊 Stockexit: 마스터 재무 분석")

# 2. 사이드바 - 종목 선택
st.sidebar.header("🔍 분석 대상")
# DB에 있는 종목만 자동으로 가져오기
try:
    conn = sqlite3.connect('my_finance.db')
    # finance_all 테이블에서 종목명 목록을 가져옴 (중복 제거)
    stock_list = pd.read_sql("SELECT DISTINCT stock_name FROM finance_all", conn)['stock_name'].tolist()
    conn.close()
    
    # 리스트가 비어있을 경우 대비
    if not stock_list:
        stock_list = ["삼성전자", "월덱스"]
except:
    stock_list = ["삼성전자", "월덱스"] # DB 에러 시 기본값

company = st.sidebar.selectbox("종목을 선택하세요", stock_list)

# 3. 데이터 불러오기
conn = sqlite3.connect('my_finance.db')
query = f"SELECT stock_name, bsns_year, quarter, account_nm, thstrm_amount FROM finance_all WHERE stock_name = '{company}'"
df = pd.read_sql(query, conn)
conn.close()

# 4. 데이터 현황 표시
if not df.empty:
    max_year = df['bsns_year'].max()
    min_year = df['bsns_year'].min()
    st.info(f"✅ **{company}** 데이터 로드 완료: **{min_year}년 ~ {max_year}년** 데이터를 분석합니다.")
else:
    st.error("데이터가 없습니다. DB를 확인해주세요.")

# 5. 단위 변환 (삼성전자는 조 단위, 나머지는 억 단위)
if company == "삼성전자":
    unit = 1000000000000
    unit_nm = "조원"
else:
    unit = 100000000
    unit_nm = "억원"

df['amount'] = pd.to_numeric(df['thstrm_amount'], errors='coerce') / unit

# 6. ⭐️ 마스터 매핑 리스트 (전종목 공통) ⭐️
is_map = {
    '매출액': '01. 매출액', '수익(매출액)': '01. 매출액', '영업수익': '01. 매출액',
    '매출원가': '02. 매출원가', '영업원가': '02. 매출원가',
    '매출총이익': '03. 매출총이익',
    '판매비와관리비': '04. 판매비와 관리비',
    '영업이익': '05. 영업이익', '영업이익(손실)': '05. 영업이익',
    '금융수익': '06. 금융수익', '금융원가': '07. 금융원가', '금융비용': '07. 금융원가',
    '기타수익': '08. 기타수익', '기타비용': '09. 기타비용', '기타손실': '09. 기타비용',
    '법인세비용차감전순이익': '10. 세전계속사업이익', '법인세비용차감전계속사업이익': '10. 세전계속사업이익', '법인세비용차감전순이익(손실)': '10. 세전계속사업이익',
    '법인세비용': '11. 법인세비용', '법인세비용(수익)': '11. 법인세비용',
    '당기순이익': '12. 당기순이익', '당기순이익(손실)': '12. 당기순이익', '분기순이익': '12. 당기순이익', '분기순이익(손실)': '12. 당기순이익', '연결분기순이익': '12. 당기순이익', '연결당기순이익': '12. 당기순이익',
    '지배기업의 소유주에게 귀속되는 당기순이익': '13. 지배주주순이익', '지배기업소유주지분': '13. 지배주주순이익', '지배주주지분 순이익': '13. 지배주주순이익',
    '비지배지분': '14. 비지배주주순이익', '비지배지분에게 귀속되는 당기순이익': '14. 비지배주주순이익'
}

bs_map = {
    '자산총계': '01. 자산총계', '유동자산': '02. 유동자산', '비유동자산': '03. 비유동자산',
    '부채총계': '04. 부채총계', '유동부채': '05. 유동부채', '비유동부채': '06. 비유동부채',
    '자본총계': '07. 자본총계'
}

cf_map = {
    '영업활동현금흐름': '01. 영업활동 현금흐름', '영업활동으로 인한 현금흐름': '01. 영업활동 현금흐름',
    '투자활동현금흐름': '02. 투자활동 현금흐름', '투자활동으로 인한 현금흐름': '02. 투자활동 현금흐름',
    '재무활동현금흐름': '03. 재무활동 현금흐름', '재무활동으로 인한 현금흐름': '03. 재무활동 현금흐름',
    '기말현금및현금성자산': '04. 기말 현금', '현금및현금성자산의 기말잔액': '04. 기말 현금'
}

# 7. 탭 구성 및 출력 함수
st.subheader(f"📈 {company} 재무제표 (단위: {unit_nm})")
tab1, tab2, tab3 = st.tabs(["손익계산서", "재무상태표", "현금흐름표"])

def show_table(mapping_dict):
    temp_df = df.copy()
    temp_df['standard_name'] = temp_df['account_nm'].map(mapping_dict)
    temp_df = temp_df.dropna(subset=['standard_name'])
    
    # 피벗 테이블
    pivot = temp_df.pivot_table(
        index='standard_name', 
        columns=['bsns_year', 'quarter'], 
        values='amount', 
        aggfunc='first'
    )
    
    # 빈칸 0으로 채우기
    pivot = pivot.fillna(0)
    
    # 정렬: 최신 연도가 왼쪽으로 오게 정렬
    pivot = pivot.sort_index(axis=1, ascending=False)
    
    # ⭐️ 핵심: 높이 자동 조절 로직 ⭐️
    # (행 개수 + 헤더 1줄) * 35픽셀 + 여유분 3px
    dynamic_height = (len(pivot) + 1) * 35 + 3
    
    st.dataframe(
        pivot.style.format(f"{{:,.1f}} {unit_nm}"), 
        use_container_width=True, # 가로 꽉 차게
        height=dynamic_height     # 세로 꽉 차게
    )

with tab1:
    st.markdown("#### 📋 손익계산서 (Income Statement)")
    show_table(is_map)

with tab2:
    st.markdown("#### 🏛️ 재무상태표 (Balance Sheet)")
    show_table(bs_map)

with tab3:
    st.markdown("#### 💸 현금흐름표 (Cash Flow)")
    show_table(cf_map)
