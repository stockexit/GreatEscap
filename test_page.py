import streamlit as st
import sqlite3
import pandas as pd

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="Stockexit Master View")
st.title("📊 Stockexit: 마스터 재무 분석 (최종 교정)")

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
# fs_div가 없을 수도 있으니 예외처리
try:
    query = f"SELECT stock_name, bsns_year, quarter, account_nm, thstrm_amount, fs_div FROM finance_all WHERE stock_name = '{company}'"
    df = pd.read_sql(query, conn)
except:
    query = f"SELECT stock_name, bsns_year, quarter, account_nm, thstrm_amount FROM finance_all WHERE stock_name = '{company}'"
    df = pd.read_sql(query, conn)
    df['fs_div'] = 'CFS' # 정보 없으면 일단 연결로 가정

conn.close()

# 4. 🚨 데이터 전처리 (이 부분이 핵심!) 🚨

# (1) 연결/별도 필터링: 'CFS'(연결)가 하나라도 있으면 연결만 남깁니다.
if df['fs_div'].str.contains('CFS', case=False, na=False).any():
    df = df[df['fs_div'].str.contains('CFS', case=False, na=False)]
    st.sidebar.success("✅ 연결재무제표(CFS) 기준")
else:
    st.sidebar.warning("⚠️ 연결 데이터 없음 (별도 기준)")

# (2) 이름 청소: 모든 공백 제거 (띄어쓰기 문제 해결)
df['clean_name'] = df['account_nm'].str.replace(" ", "").str.strip()

# (3) 쉼표 제거 및 숫자 변환 (413,501,494 같은 문자열 처리)
# 숫자에 쉼표가 들어있으면 문자로 인식돼서 None이 뜰 수 있습니다.
df['amount'] = (
    df['thstrm_amount']
    .astype(str)                 # 문자로 변환
    .str.replace(",", "")        # 쉼표 제거
    .pipe(pd.to_numeric, errors='coerce') # 숫자로 변환
) / unit_div

# 5. ⭐️ 사용자님이 찾아낸 이름 완벽 반영 ⭐️
mapping_config = {
    # [손익계산서]
    '매출액': ['매출액', '수익(매출액)', '영업수익', '수익'],
    '매출원가': ['매출원가', '영업원가', '매출의원가'],
    '매출총이익': ['매출총이익'],
    '판관비': ['판매비와관리비', '판관비'],
    '영업이익': ['영업이익', '영업이익(손실)'],
    '당기순이익': ['당기순이익', '당기순이익(손실)', '분기순이익', '분기순이익(손실)', '연결분기순이익', '연결당기순이익'],
    
    # ✅ 사용자 제보 반영: 지배/비지배
    '지배주주순이익': [
        '지배기업의소유주에게귀속되는당기순이익', 
        '지배기업소유주지분',  # ⭐ 추가됨
        '지배주주지분순이익', 
        '지배기업소유주지분순이익'
    ],
    '비지배주주순이익': [
        '비지배지분',         # ⭐ 추가됨
        '비지배지분에게귀속되는당기순이익'
    ],

    # [재무상태표]
    # ✅ 자본총계가 안 나왔던 건 숫자 포맷(쉼표) 문제였을 가능성이 큽니다.
    '자산총계': ['자산총계', '자산'],
    '부채총계': ['부채총계', '부채'],
    '자본총계': ['자본총계', '자본', '기말자본', '반기말자본', '분기말자본'], 

    # [현금흐름표]
    '영업활동현금': ['영업활동현금흐름', '영업활동으로인한현금흐름'],
    '투자활동현금': ['투자활동현금흐름', '투자활동으로인한현금흐름'],
    '재무활동현금': ['재무활동현금흐름', '재무활동으로인한현금흐름'],
    # ✅ 사용자 제보 반영: 분기말의...
    '기말현금': [
        '기말현금및현금성자산', 
        '현금및현금성자산의기말잔액', 
        '기말의현금및현금성자산', 
        '분기말의현금및현금성자산', # ⭐ 추가됨
        '현금및현금성자산'
    ]
}

# 역매핑 생성
reverse_map = {}
for std, aliases in mapping_config.items():
    for alias in aliases:
        reverse_map[alias] = std

# 6. 출력 함수 (높이 자동 조절 포함)
def show_table(target_items, tab_name):
    temp = df.copy()
    temp['standard_name'] = temp['clean_name'].map(reverse_map)
    
    # 해당 탭의 항목만 필터링
    filtered = temp[temp['standard_name'].isin(target_items)]
    
    # 피벗 (중복 시 첫 번째 값 사용)
    pivot = filtered.pivot_table(
        index='standard_name', columns=['bsns_year', 'quarter'], values='amount', aggfunc='first'
    )
    
    # 순서 강제 정렬
    pivot = pivot.reindex(target_items)
    
    # 빈칸 채우기 (0.0)
    pivot = pivot.fillna(0)
    
    # 최신순 정렬
    pivot = pivot.sort_index(axis=1, ascending=False)
    
    # 높이 계산
    h = (len(pivot.dropna(how='all')) + 1) * 35 + 3
    
    if pivot.empty:
        st.info(f"데이터가 없습니다. ({tab_name})")
    else:
        st.dataframe(pivot.style.format(f"{{:,.1f}} {unit_option}"), use_container_width=True, height=h)

# 7. 탭 구성
tab1, tab2, tab3 = st.tabs(["손익계산서", "재무상태표", "현금흐름표"])

with tab1:
    st.markdown("#### 📋 손익계산서")
    items = ['매출액', '매출원가', '매출총이익', '판관비', '영업이익', '당기순이익', '지배주주순이익', '비지배주주순이익']
    show_table(items, "손익계산서")

with tab2:
    st.markdown("#### 🏛️ 재무상태표")
    items = ['자산총계', '부채총계', '자본총계']
    show_table(items, "재무상태표")

with tab3:
    st.markdown("#### 💸 현금흐름표")
    items = ['영업활동현금', '투자활동현금', '재무활동현금', '기말현금']
    show_table(items, "현금흐름표")

# 8. (유지) 범인 찾기 기능
st.markdown("---")
with st.expander("🕵️‍♀️ 데이터 확인용 (문제 해결됨)", expanded=False):
    st.write("매핑에 사용된 실제 이름들:")
    st.dataframe(sorted(df['clean_name'].unique()))
