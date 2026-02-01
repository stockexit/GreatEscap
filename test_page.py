import streamlit as st
import sqlite3
import pandas as pd

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="Stockexit Master View")
st.title("📊 Stockexit: 마스터 재무 분석 (Clean Ver.)")

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

# 단위 선택
unit_option = st.sidebar.radio("단위", ["억원", "조원"], index=1 if company=="삼성전자" else 0)
unit_div = 1000000000000 if unit_option == "조원" else 100000000

# 3. 데이터 로드
conn = sqlite3.connect('my_finance.db')
try:
    query = f"SELECT stock_name, bsns_year, quarter, account_nm, thstrm_amount, fs_div FROM finance_all WHERE stock_name = '{company}'"
    df = pd.read_sql(query, conn)
except:
    query = f"SELECT stock_name, bsns_year, quarter, account_nm, thstrm_amount FROM finance_all WHERE stock_name = '{company}'"
    df = pd.read_sql(query, conn)
    df['fs_div'] = 'CFS' 
conn.close()

# 4. 데이터 전처리 (공백 제거 & 쉼표 제거)
# (1) 연결(CFS) 우선 필터링
if df['fs_div'].str.contains('CFS', case=False, na=False).any():
    df = df[df['fs_div'].str.contains('CFS', case=False, na=False)]
    st.sidebar.success("✅ 연결재무제표(CFS) 기준")
else:
    st.sidebar.warning("⚠️ 연결 데이터 없음 (별도 기준)")

# (2) 이름 및 숫자 정리
df['clean_name'] = df['account_nm'].str.replace(" ", "").str.strip()
df['amount'] = (
    df['thstrm_amount']
    .astype(str)
    .str.replace(",", "")
    .pipe(pd.to_numeric, errors='coerce')
) / unit_div

# 5. ⭐️ 매핑 수정 (자본 항목을 재무상태표로 이동) ⭐️
mapping_config = {
    # [손익계산서] - '번 돈' (Flow)
    '매출액': ['매출액', '수익(매출액)', '영업수익', '수익'],
    '매출원가': ['매출원가', '영업원가', '매출의원가'],
    '매출총이익': ['매출총이익'],
    '판관비': ['판매비와관리비', '판관비'],
    '영업이익': ['영업이익', '영업이익(손실)'],
    '당기순이익': ['당기순이익', '당기순이익(손실)', '분기순이익', '분기순이익(손실)', '연결분기순이익', '연결당기순이익'],
    
    # 지배주주 순이익 (이익 항목만 매핑)
    '지배주주순이익': ['지배기업의소유주에게귀속되는당기순이익', '지배주주지분순이익'], 
    # 비지배주주 순이익
    '비지배주주순이익': ['비지배지분에게귀속되는당기순이익'],

    # [재무상태표] - '가진 돈' (Stock)
    '자산총계': ['자산총계', '자산'],
    '부채총계': ['부채총계', '부채'],
    # 🚨 수정됨: 아까 '순이익'으로 오해했던 항목들을 여기(자본)로 옮김
    '자본총계': ['자본총계', '자본', '기말자본', '반기말자본', '분기말자본', '지배기업소유주지분', '지배기업의소유주에게귀속되는지분'], 

    # [현금흐름표]
    '영업활동현금': ['영업활동현금흐름', '영업활동으로인한현금흐름'],
    '투자활동현금': ['투자활동현금흐름', '투자활동으로인한현금흐름'],
    '재무활동현금': ['재무활동현금흐름', '재무활동으로인한현금흐름'],
    '기말현금': ['기말현금및현금성자산', '현금및현금성자산의기말잔액', '기말의현금및현금성자산', '분기말의현금및현금성자산', '현금및현금성자산']
}

# 역매핑
reverse_map = {}
for std, aliases in mapping_config.items():
    for alias in aliases:
        reverse_map[alias] = std

# 6. 출력 함수
def show_table(target_items, tab_name):
    temp = df.copy()
    temp['standard_name'] = temp['clean_name'].map(reverse_map)
    filtered = temp[temp['standard_name'].isin(target_items)]
    
    # 피벗
    pivot = filtered.pivot_table(
        index='standard_name', columns=['bsns_year', 'quarter'], values='amount', aggfunc='first'
    )
    
    # 정렬 및 빈칸 처리
    pivot = pivot.reindex(target_items)
    # pivot = pivot.fillna(0) # 0으로 채우기보다는 없는 건 비워두는 게 오해를 줄임
    pivot = pivot.sort_index(axis=1, ascending=False)
    
    # 높이 자동 조절
    h = (len(pivot.dropna(how='all')) + 1) * 35 + 3
    
    if pivot.empty:
        st.info(f"데이터가 없습니다. ({tab_name})")
    else:
        st.dataframe(pivot.style.format(f"{{:,.1f}} {unit_option}"), use_container_width=True, height=h)

# 7. 탭 구성
tab1, tab2, tab3 = st.tabs(["손익계산서", "재무상태표", "현금흐름표"])

with tab1:
    st.markdown("#### 📋 손익계산서")
    # 지배/비지배 순이익 데이터가 없으면 표시되지 않도록 처리
    items = ['매출액', '매출원가', '매출총이익', '판관비', '영업이익', '당기순이익', '지배주주순이익']
    show_table(items, "손익계산서")

with tab2:
    st.markdown("#### 🏛️ 재무상태표")
    # 여기서 이제 자본총계가 제대로 나올 겁니다.
    items = ['자산총계', '부채총계', '자본총계']
    show_table(items, "재무상태표")

with tab3:
    st.markdown("#### 💸 현금흐름표")
    items = ['영업활동현금', '투자활동현금', '재무활동현금', '기말현금']
    show_table(items, "현금흐름표")
