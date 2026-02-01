import streamlit as st
import sqlite3
import pandas as pd

# 1. 페이지 설정 (스크롤 최대한 확보)
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

# 3. 데이터 로드
conn = sqlite3.connect('my_finance.db')
# sj_div(재무제표 구분) 컬럼을 반드시 가져와야 합니다.
try:
    query = f"SELECT stock_name, bsns_year, quarter, sj_div, account_nm, thstrm_amount, fs_div FROM finance_all WHERE stock_name = '{company}'"
    df = pd.read_sql(query, conn)
except:
    # 구버전 DB 호환용
    query = f"SELECT stock_name, bsns_year, quarter, sj_div, account_nm, thstrm_amount FROM finance_all WHERE stock_name = '{company}'"
    df = pd.read_sql(query, conn)
    df['fs_div'] = 'CFS' 
conn.close()

# 4. 데이터 전처리 (핵심: 연결/별도 필터링 & 공백 제거)
# (1) 연결재무제표(CFS)만 남기기
if 'fs_div' in df.columns and df['fs_div'].str.contains('CFS', case=False, na=False).any():
    df = df[df['fs_div'].str.contains('CFS', case=False, na=False)]

# (2) 이름 청소 및 숫자 변환
df['clean_name'] = df['account_nm'].str.replace(" ", "").str.strip()
df['amount'] = (
    df['thstrm_amount']
    .astype(str)
    .str.replace(",", "")
    .pipe(pd.to_numeric, errors='coerce')
) / unit_div

# 5. ⭐️ 데이터 3단 분리 (여기가 핵심!) ⭐️
# 이름이 같아도 소속(sj_div)이 다르면 다른 데이터입니다. 미리 쪼개놓습니다.
# BS: 재무상태표, IS/CIS: 손익계산서, CF: 현금흐름표
df_bs = df[df['sj_div'].str.contains('BS', case=False, na=False)].copy()
df_is = df[df['sj_div'].str.contains('IS|CIS', case=False, na=False)].copy()
df_cf = df[df['sj_div'].str.contains('CF', case=False, na=False)].copy()

# 6. ⭐️ 구역별 전용 매핑 리스트 ⭐️
# 이제 '지배기업소유주지분'이 손익계산서 구역에 있으면 이익으로, 재무상태표 구역에 있으면 자본으로 처리됩니다.

# [1] 손익계산서 매핑
map_is = {
    '매출액': ['매출액', '수익(매출액)', '영업수익', '수익'],
    '매출원가': ['매출원가', '영업원가', '매출의원가'],
    '매출총이익': ['매출총이익'],
    '판매비와 관리비': ['판매비와관리비', '판관비'],
    '영업이익': ['영업이익', '영업이익(손실)'],
    '금융수익': ['금융수익', '금융이익'],
    '금융원가': ['금융원가', '금융비용'],
    '기타수익': ['기타수익', '기타이익', '기타영업외수익'],
    '기타비용': ['기타비용', '기타손실', '기타영업외비용'],
    '세전계속사업이익': ['법인세비용차감전순이익', '법인세비용차감전계속사업이익', '법인세차감전순이익', '법인세차감전전순이익'],
    '법인세비용': ['법인세비용', '법인세'],
    '당기순이익': ['당기순이익', '당기순이익(손실)', '분기순이익', '분기순이익(손실)', '연결분기순이익', '연결당기순이익'],
    
    # 🚨 여기가 0원 문제 해결 포인트 🚨
    # 손익계산서(IS) 데이터 안에서 '지배기업소유주지분'을 찾으면 그건 순이익 배분액입니다.
    '지배주주순이익': ['지배기업의소유주에게귀속되는당기순이익', '지배주주지분순이익', '지배기업소유주지분', '지배주주지분'],
    '비지배주주순이익': ['비지배지분에게귀속되는당기순이익', '비지배주주지분순이익', '비지배지분', '비지배주주지분']
}

# [2] 재무상태표 매핑
map_bs = {
    '자산총계': ['자산총계', '자산'],
    '유동자산': ['유동자산'],
    '비유동자산': ['비유동자산'],
    '부채총계': ['부채총계', '부채'],
    '유동부채': ['유동부채'],
    '비유동부채': ['비유동부채', '비유동부체'], 
    '자본총계': ['자본총계', '자본', '기말자본', '반기말자본', '분기말자본']
}

# [3] 현금흐름표 매핑
map_cf = {
    '영업활동 현금흐름': ['영업활동현금흐름', '영업활동으로인한현금흐름'],
    '투자활동 현금흐름': ['투자활동현금흐름', '투자활동으로인한현금흐름'],
    '재무활동 현금흐름': ['재무활동현금흐름', '재무활동으로인한현금흐름'],
    '기말 현금': ['기말현금및현금성자산', '현금및현금성자산의기말잔액', '기말의현금및현금성자산', '분기말의현금및현금성자산', '현금및현금성자산', '기말현금']
}

# 7. 출력 함수 (높이 조절 + 정밀 매핑)
def show_table(subset_df, mapping_dict, target_order):
    # 역매핑 생성
    reverse_map = {}
    for std, aliases in mapping_dict.items():
        for alias in aliases:
            reverse_map[alias] = std
            
    temp = subset_df.copy()
    temp['standard_name'] = temp['clean_name'].map(reverse_map)
    
    # 해당 구역의 데이터만 필터링
    filtered = temp[temp['standard_name'].isin(target_order)]
    
    # 피벗 테이블
    pivot = filtered.pivot_table(
        index='standard_name', columns=['bsns_year', 'quarter'], values='amount', aggfunc='first'
    )
    
    # ⭐️ 순서 강제 및 0 처리 (None 방지)
    pivot = pivot.reindex(target_order)
    pivot = pivot.fillna(0)
    
    # 최신순 정렬
    pivot = pivot.sort_index(axis=1, ascending=False)
    
    # 높이 자동 계산 (스크롤 제거)
    h = (len(target_order) + 1) * 35 + 3
    
    st.dataframe(
        pivot.style.format(f"{{:,.1f}} {unit_option}"), 
        use_container_width=True, 
        height=h
    )

# 8. 화면 탭 구성
tab1, tab2, tab3 = st.tabs(["손익계산서", "재무상태표", "현금흐름표"])

with tab1:
    st.markdown("#### 📋 손익계산서")
    order = [
        '매출액', '매출원가', '매출총이익', '판매비와 관리비',
        '영업이익', '금융수익', '금융원가', '기타수익', '기타비용',
        '세전계속사업이익', '법인세비용',
        '당기순이익', '지배주주순이익', '비지배주주순이익'
    ]
    # df_is (손익계산서 데이터)만 사용
    show_table(df_is, map_is, order)

with tab2:
    st.markdown("#### 🏛️ 재무상태표")
    order = [
        '자산총계', '유동자산', '비유동자산',
        '부채총계', '유동부채', '비유동부채',
        '자본총계'
    ]
    # df_bs (재무상태표 데이터)만 사용
    show_table(df_bs, map_bs, order)

with tab3:
    st.markdown("#### 💸 현금흐름표")
    order = [
        '영업활동 현금흐름', '투자활동 현금흐름', '재무활동 현금흐름', '기말 현금'
    ]
    # df_cf (현금흐름표 데이터)만 사용
    show_table(df_cf, map_cf, order)
