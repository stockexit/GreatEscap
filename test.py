import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정 (가장 윗줄 고정)
st.set_page_config(
    page_title="사장님 전용 금융 터미널", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. [초정밀 CSS] 옆으로 밀림 방지 + 모바일 2x2 강제 고정
st.markdown("""
    <style>
    /* 메뉴 및 헤더 숨기기 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}

    /* 전체 페이지 가로 스크롤(옆으로 밀림) 원천 봉쇄 */
    .main .block-container {
        max-width: 100% !important;
        padding-left: 0.2rem !important;
        padding-right: 0.2rem !important;
        padding-top: 1rem !important;
        overflow-x: hidden !important; 
    }

    /* 모바일 2x2 강제 배치 (정밀 너비 계산으로 옆으로 안 밀리게 함) */
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            width: 100% !important;
            gap: 2px !important;
        }
        [data-testid="column"] {
            /* 50%에서 아주 미세한 여백을 뺀 값으로 옆으로 밀림 방지 */
            width: calc(50% - 4px) !important;
            flex: 1 1 calc(50% - 4px) !important;
            min-width: calc(50% - 4px) !important;
        }
        /* 차트 높이 최적화 */
        .stPlotlyChart { height: 240px !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결 (사장님 시트 주소)
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

@st.cache_data(ttl=60)
def load_data(csv_url):
    try:
        df = pd.read_csv(csv_url)
        return df
    except:
        return None

df_sheet = load_data(url)

# 4. 종목 선택 로직
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.markdown("### 🎯 분석 종목")
    # 종목명이 있는 데이터만 추출
    valid_df = df_sheet.dropna(subset=['종목명'])
    stock_list = valid_df['종목명'].unique().tolist()
    selected_name = st.sidebar.selectbox("종목 선택", stock_list)
    stock_info = valid_df[valid_df['종목명'] == selected_name].iloc[0]
else:
    st.warning("구글 시트에서 데이터를 불러오는 중입니다...")
    st.stop()

# 5. 차트 생성 함수 (오타 완벽 박멸)
def draw_chart(ticker, period, title):
    try:
        interval = "1wk" if period == "max" else "1d"
        df = yf.download(ticker, period=period, interval=interval)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        if df.empty:
            return st.write(f"{title}:
