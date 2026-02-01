import streamlit as st
import sqlite3
import pandas as pd

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="Stockexit Master View")
st.title("📊 Stockexit: 마스터 재무 분석 (정밀교정판)")

# 2. 사이드바 설정
st.sidebar.header("🔍 분석 설정")

# 종목 선택
try:
    conn = sqlite3.connect('my_finance.db')
    stock_list = pd.read_sql("SELECT DISTINCT stock_name FROM finance_all", conn)['stock_name'].tolist()
    conn.close()
    if not stock_list: stock_list = ["삼성전자", "월덱스"]
except:
    stock_list = ["삼성전자", "월덱스"]

company = st.sidebar.selectbox("종목 선택", stock_list)

# 단위 선택 (사용자가 직접 선택 가능하게 변경)
unit_option = st.sidebar.radio("화폐 단위", ["억원", "조원"], index=1 if company=="삼성전자" else 0)
unit_div = 1000000000000 if unit_option == "조원" else 100000000

# 3. 데이터 불러오기
conn = sqlite3.connect('my_finance.db')
# fs_div 컬럼도 가져와서 연결/별도를 구분합니다.
try:
    query = f"SELECT stock_name, bsns_year, quarter, account_nm, thstrm_amount, fs_div FROM finance_all WHERE stock_name = '{company}'"
    df = pd.read_sql(query, conn)
except:
    # 혹시 fs_div 컬럼이 없는 구버전 DB일 경우 대비
    query = f"SELECT stock_name, bsns_year, quarter, account_nm, thstrm_amount FROM finance_all WHERE stock_name = '{company}'"
    df = pd.read_sql(query, conn)
    df['fs_div'] = 'CFS' # 강제 할당

conn.close()

# 4. 🚨 핵심 수정 1: 연결재무제표(CFS) 우선 필터링 🚨
# 데이터에 연결(CFS)과 별도(OFS)가 섞여 있으면 연결만 남깁니다.
if 'fs_div' in df.columns and len(df['fs_div'].unique()) > 1:
    df = df[df['fs_div'].str.contains('CFS', case=False, na=False)]

# 5. 🚨 핵심 수정 2: 공백 제거로 이름 통일 (자 본 총 계 -> 자본총계) 🚨
# 모든 공백을 없애서 매핑 확률을 비약적으로 높입니다.
df['clean_name'] = df['account_nm'].str.replace(" ", "").str.strip()

# 숫자 변환
df['amount'] = pd.to_numeric(df['thstrm_amount'], errors='coerce') / unit_div

# 6. 강력해진 매핑 리스트 (공백 없는 버전)
# 이제 '자 본 총 계'가 들어와도 '자본총계'로 인식되어 매핑됩니다.
mapping_config = {
    # [손익계산서]
    '매출액': ['매출액', '수익(매출액)', '영업수익', '수익'],
    '매출원가': ['매출원가', '영업원가', '매출의원가'],
    '매출총이익': ['매출총이익'],
    '판매비와관리비': ['판매비와관리비', '판관비'],
    '영업이익': ['영업이익', '영업이익(손실)'],
    '금융수익': ['금융수익', '금융이익'],
    '금융원가': ['금융원가', '금융비용'],
    '기타수익': ['기타수익', '기타이익', '기타영업외수익'],
    '기타비용': ['기타비용', '기타손실', '기타영업외비용'],
    '법인세차감전이익': ['법인세비용차감전순이익', '법인세비용차감전계속사업이익', '법인세차감전순이익'],
    '법인세비용': ['법인세비용', '법인세'],
    '당기순이익': ['당기순이익', '당기순이익(손실)', '분기순이익', '분기순이익(손실)', '연결분기순이익', '연결당기순이익'],
    '지배주주순이익': ['지배기업의소유주에게귀속되는당기순이익', '지배기업소유주지분', '지배주주지분순이익', '지배기업소유주지분순이익'], 
    '비지배주주순이익': ['비지배지분', '비지배지분에게귀속되는당기순이익'],

    # [재무상태표]
    '자산총계': ['자산총계', '자산'],
    '유동자산': ['유동자산'],
    '비유동자산': ['비유동자산'],
    '부채총계': ['부채총계', '부채'],
    '유동부채': ['유동부채'],
    '비유동부채': ['비유동부채'],
    '자본총계': ['자본총계', '자본'], # 이제 '자 본 총 계'도 여기 걸립니다.

    # [현금흐름표]
    '영업활동현금흐름': ['영업활동현금흐름', '영업활동으로인한현금흐름'],
    '투자활동현금흐름': ['투자활동현금흐름', '투자활동으로인한현금흐름'],
    '재무활동현금흐름': ['재무활동현금흐름', '재무활동으로인한현금흐름'],
    '기말현금': ['기말현금및현금성자산', '현금및현금성자산의기말잔액', '기말의현금및현금성자산']
}

# 역매핑 생성 (매핑 리스트를 뒤집어서 검색하기 쉽게 만듦)
reverse_map = {}
for std, aliases in mapping_config.items():
    for alias in aliases:
        reverse_map[alias] = std

# 7. 화면 출력 로직
st.subheader(f"📈 {company} 재무제표 (단위: {unit_option})")
tab1, tab2, tab3 = st.tabs(["손익계산서", "재무상태표", "현금흐름표"])

def show_table(target_items):
    temp_df = df.copy()
    # clean_name 기준으로 매핑
    temp_df['standard_name'] = temp_df['clean_name'].map(reverse_map)
    
    # 보고 싶은 항목만 필터링
    target_set = set(target_items)
    temp_df = temp_df[temp_df['standard_name'].isin(target_set)]
    
    # 피벗
    pivot = temp_df.pivot_table(
        index='standard_name', 
        columns=['bsns_year', 'quarter'], 
        values='amount', 
        aggfunc='first' # 중복되면 첫 번째 값 (연결 필터링 했으니 안전)
    )
    
    # 정렬 (사용자가 원하는 순서대로)
    pivot = pivot.reindex(target_items)
    pivot = pivot.fillna(0)
    pivot = pivot.sort_index(axis=1, ascending=False) # 최신순
    
    # 높이 자동 조절
    dynamic_height = (len(pivot) + 1) * 35 + 3
    
    st.dataframe(
        pivot.style.format(f"{{:,.1f}} {unit_option}"), 
        use_container_width=True,
        height=dynamic_height
    )

with tab1:
    st.markdown("#### 📋 손익계산서")
    items = ['매출액', '매출원가', '매출총이익', '판매비와관리비', '영업이익', 
             '금융수익', '금융원가', '기타수익', '기타비용', 
             '법인세차감전이익', '법인세비용', '당기순이익', '지배주주순이익']
    show_table(items)

with tab2:
    st.markdown("#### 🏛️ 재무상태표")
    items = ['자산총계', '유동자산', '비유동자산', '부채총계', '유동부채', '비유동부채', '자본총계']
    show_table(items)

with tab3:
    st.markdown("#### 💸 현금흐름표")
    items = ['영업활동현금흐름', '투자활동현금흐름', '재무활동현금흐름', '기말현금']
    show_table(items)
