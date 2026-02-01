import streamlit as st
import sqlite3
import pandas as pd

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="Stockexit Master View")
st.title("📊 Stockexit: 마스터 재무 분석")

# 2. 사이드바 - 종목/단위 선택
st.sidebar.header("🔍 설정")
try:
    conn = sqlite3.connect('my_finance.db')
    stock_list = pd.read_sql("SELECT DISTINCT stock_name FROM finance_all", conn)['stock_name'].tolist()
    conn.close()
    if not stock_list: stock_list = ["삼성전자", "월덱스"]
except:
    stock_list = ["삼성전자", "월덱스"]

company = st.sidebar.selectbox("종목 선택", stock_list)

# 단위: 삼성전자는 조원, 나머지는 억원
unit_option = st.sidebar.radio("단위", ["억원", "조원"], index=1 if company=="삼성전자" else 0)
unit_div = 1000000000000 if unit_option == "조원" else 100000000

# 3. 데이터 로드 및 전처리
conn = sqlite3.connect('my_finance.db')
try:
    # 연결/별도 구분을 위해 fs_div 가져옴
    query = f"SELECT stock_name, bsns_year, quarter, account_nm, thstrm_amount, fs_div FROM finance_all WHERE stock_name = '{company}'"
    df = pd.read_sql(query, conn)
except:
    # 구버전 DB 대비
    query = f"SELECT stock_name, bsns_year, quarter, account_nm, thstrm_amount FROM finance_all WHERE stock_name = '{company}'"
    df = pd.read_sql(query, conn)
    df['fs_div'] = 'CFS' 
conn.close()

# (1) 연결재무제표(CFS)만 남기기 (중복 제거)
if df['fs_div'].str.contains('CFS', case=False, na=False).any():
    df = df[df['fs_div'].str.contains('CFS', case=False, na=False)]

# (2) 이름 공백/특수문자 제거 (매핑 정확도 향상)
df['clean_name'] = df['account_nm'].str.replace(" ", "").str.strip()

# (3) 숫자 변환 (쉼표 제거)
df['amount'] = (
    df['thstrm_amount']
    .astype(str)
    .str.replace(",", "")
    .pipe(pd.to_numeric, errors='coerce')
) / unit_div

# 4. ⭐️ 사용자 지정 고정 템플릿 매핑 ⭐️
# 말씀하신 리스트 그대로 매핑합니다.
mapping_config = {
    # [손익계산서]
    '매출액': ['매출액', '수익(매출액)', '영업수익', '수익'],
    '매출원가': ['매출원가', '영업원가', '매출의원가'],
    '매출총이익': ['매출총이익'],
    '판매비와 관리비': ['판매비와관리비', '판관비'],
    '영업이익': ['영업이익', '영업이익(손실)'],
    '금융수익': ['금융수익', '금융이익'],
    '금융원가': ['금융원가', '금융비용'],
    '기타수익': ['기타수익', '기타이익', '기타영업외수익'],
    '기타비용': ['기타비용', '기타손실', '기타영업외비용'],
    '세전계속사업이익': ['법인세비용차감전순이익', '법인세비용차감전계속사업이익', '법인세차감전순이익'],
    '법인세비용': ['법인세비용', '법인세'],
    '당기순이익': ['당기순이익', '당기순이익(손실)', '분기순이익', '분기순이익(손실)', '연결분기순이익', '연결당기순이익'],
    
    # 순이익 배분 (이익잉여금/자본이 아님!)
    '지배주주순이익': ['지배기업의소유주에게귀속되는당기순이익', '지배주주지분순이익', '지배기업소유주지분순이익'],
    '비지배주주순이익': ['비지배지분에게귀속되는당기순이익', '비지배지분순이익'],

    # [재무상태표]
    '자산총계': ['자산총계', '자산'],
    '유동자산': ['유동자산'],
    '비유동자산': ['비유동자산'],
    '부채총계': ['부채총계', '부채'],
    '유동부채': ['유동부채'],
    '비유동부채': ['비유동부채'], # 오타 수정: 비유동부체 -> 비유동부채
    '자본총계': ['자본총계', '자본', '기말자본', '반기말자본', '분기말자본'],

    # [현금흐름표]
    '영업활동 현금흐름': ['영업활동현금흐름', '영업활동으로인한현금흐름'],
    '투자활동 현금흐름': ['투자활동현금흐름', '투자활동으로인한현금흐름'],
    '재무활동 현금흐름': ['재무활동현금흐름', '재무활동으로인한현금흐름'],
    '기말 현금': ['기말현금및현금성자산', '현금및현금성자산의기말잔액', '기말의현금및현금성자산', '분기말의현금및현금성자산', '현금및현금성자산']
}

# 역매핑 생성
reverse_map = {}
for std, aliases in mapping_config.items():
    for alias in aliases:
        reverse_map[alias] = std

# 5. 출력 함수 (스크롤 없이 쫙 펴기)
def show_table(target_items_list):
    temp = df.copy()
    temp['standard_name'] = temp['clean_name'].map(reverse_map)
    
    # 템플릿에 있는 항목만 가져오기
    filtered = temp[temp['standard_name'].isin(target_items_list)]
    
    # 피벗 테이블 생성
    pivot = filtered.pivot_table(
        index='standard_name', columns=['bsns_year', 'quarter'], values='amount', aggfunc='first'
    )
    
    # ⭐️ 핵심: 사용자님이 정한 순서대로 강제 정렬 (없으면 0 처리)
    pivot = pivot.reindex(target_items_list)
    pivot = pivot.fillna(0)
    
    # 최신순 정렬 (2025 -> 2024...)
    pivot = pivot.sort_index(axis=1, ascending=False)
    
    # 높이 자동 조절 (스크롤 제거)
    h = (len(target_items_list) + 1) * 35 + 3
    
    st.dataframe(
        pivot.style.format(f"{{:,.1f}} {unit_option}"), 
        use_container_width=True, 
        height=h
    )

# 6. 화면 출력 (탭 대신 한눈에 보기 좋게, 혹은 탭 유지)
tab1, tab2, tab3 = st.tabs(["손익계산서", "재무상태표", "현금흐름표"])

with tab1:
    st.markdown("#### 📋 손익계산서")
    # 사용자님 리스트 그대로 적용
    is_items = [
        '매출액', '매출원가', '매출총이익', '판매비와 관리비',
        '영업이익', '금융수익', '금융원가', '기타수익', '기타비용',
        '세전계속사업이익', '법인세비용',
        '당기순이익', '지배주주순이익', '비지배주주순이익'
    ]
    show_table(is_items)

with tab2:
    st.markdown("#### 🏛️ 재무상태표")
    bs_items = [
        '자산총계', '유동자산', '비유동자산',
        '부채총계', '유동부채', '비유동부채',
        '자본총계'
    ]
    show_table(bs_items)

with tab3:
    st.markdown("#### 💸 현금흐름표")
    cf_items = [
        '영업활동 현금흐름', '투자활동 현금흐름', '재무활동 현금흐름', '기말 현금'
    ]
    show_table(cf_items)
