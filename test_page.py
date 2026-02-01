import streamlit as st
import sqlite3
import pandas as pd

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="Stockexit Master View")
st.title("📊 Stockexit: 마스터 재무 분석 (복구 및 안정화)")

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

# 4. 데이터 전처리
# (1) 연결(CFS) 우선 필터링
if df['fs_div'].str.contains('CFS', case=False, na=False).any():
    df = df[df['fs_div'].str.contains('CFS', case=False, na=False)]
    st.sidebar.success("✅ 연결재무제표(CFS) 기준")
else:
    st.sidebar.warning("⚠️ 연결 데이터 없음 (별도 기준)")

# (2) 이름 및 숫자 정리 (공백/쉼표 제거)
df['clean_name'] = df['account_nm'].str.replace(" ", "").str.strip()
df['amount'] = (
    df['thstrm_amount']
    .astype(str)
    .str.replace(",", "")
    .pipe(pd.to_numeric, errors='coerce')
) / unit_div

# 5. ⭐️ 매핑 리스트 (누락된 항목들 모두 포함) ⭐️
mapping_config = {
    # [손익계산서] - Flow (번 돈)
    '매출액': ['매출액', '수익(매출액)', '영업수익', '수익'],
    '매출원가': ['매출원가', '영업원가', '매출의원가'],
    '매출총이익': ['매출총이익'],
    '판관비': ['판매비와관리비', '판관비'],
    '영업이익': ['영업이익', '영업이익(손실)'],
    '당기순이익': ['당기순이익', '당기순이익(손실)', '분기순이익', '분기순이익(손실)', '연결분기순이익', '연결당기순이익'],
    
    # [재무상태표] - Stock (쌓인 돈)
    '자산총계': ['자산총계', '자산'],
    '부채총계': ['부채총계', '부채'],
    '자본총계': ['자본총계', '자본', '기말자본', '반기말자본', '분기말자본'], 
    
    # 🚨 아까 사라졌던 항목들 여기(재무상태표)에 확실히 매핑합니다 🚨
    '지배주주지분': ['지배기업소유주지분', '지배기업의소유주에게귀속되는지분', '지배주주지분'], 
    '비지배지분': ['비지배지분', '비지배주주지분'],

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

# 6. 출력 함수 (None -> 0 처리 강화)
def show_table(target_items, tab_name):
    temp = df.copy()
    temp['standard_name'] = temp['clean_name'].map(reverse_map)
    filtered = temp[temp['standard_name'].isin(target_items)]
    
    # 피벗
    pivot = filtered.pivot_table(
        index='standard_name', columns=['bsns_year', 'quarter'], values='amount', aggfunc='first'
    )
    
    # ⭐️ 1. 강제 순서 맞추기 (없어도 행을 만듦)
    pivot = pivot.reindex(target_items)
    
    # ⭐️ 2. None 값을 0으로 채우기 (개판 방지)
    pivot = pivot.fillna(0)
    
    # 3. 최신순 정렬
    pivot = pivot.sort_index(axis=1, ascending=False)
    
    # 4. 높이 자동 조절 (스크롤 방지)
    h = (len(target_items) + 1) * 35 + 3
    
    if pivot.empty: # 데이터가 아예 없어도 틀은 보여줌
         st.dataframe(pd.DataFrame(index=target_items), use_container_width=True)
    else:
        st.dataframe(pivot.style.format(f"{{:,.1f}} {unit_option}"), use_container_width=True, height=h)

# 7. 탭 구성
tab1, tab2, tab3 = st.tabs(["손익계산서", "재무상태표", "현금흐름표"])

with tab1:
    st.markdown("#### 📋 손익계산서")
    items = ['매출액', '매출원가', '매출총이익', '판관비', '영업이익', '당기순이익']
    show_table(items, "손익계산서")

with tab2:
    st.markdown("#### 🏛️ 재무상태표")
    # 🚨 여기에 '지배주주지분', '비지배지분'을 추가했습니다. 이제 보일 겁니다.
    items = ['자산총계', '부채총계', '자본총계', '지배주주지분', '비지배지분']
    show_table(items, "재무상태표")

with tab3:
    st.markdown("#### 💸 현금흐름표")
    items = ['영업활동현금', '투자활동현금', '재무활동현금', '기말현금']
    show_table(items, "현금흐름표")
