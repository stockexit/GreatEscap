import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정 (반드시 가장 윗줄!)
st.set_page_config(
    page_title="사장님 전용 금융 터미널", 
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={'Get Help': None, 'Report a bug': None, 'About': None}
)

# 2. [정밀 수술] 화면 밖으로 절대 나가지 않는 2x2 격자 CSS
st.markdown("""
    <style>
    /* 1. 기본 메뉴 및 불필요한 UI 제거 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}

    /* 2. 전체 페이지 가로 스크롤(옆으로 밀림) 원천 봉쇄 */
    .main .block-container {
        max-width: 100% !important;
        padding-left: 0.2rem !important;
        padding-right: 0.2rem !important;
        padding-top: 1rem !important;
        overflow-x: hidden !important; /* 옆으로 밀리는 현상 방지 핵심 */
    }

    /* 3. 모바일에서 2x2 강제 배치 (정밀 너비 계산) */
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important; /* 아래로 떨어지지 않게 고정 */
            width: 100% !important;
            gap: 4px !important; /* 컬럼 사이 간격 */
        }
        [data-testid="column"] {
            /* 50%에서 여백을 뺀 정밀한 값으로 옆으로 밀리는 현상 방지 */
            width: calc(50% - 3px) !important;
            flex: 1 1 calc(50% - 3px) !important;
            min-width: calc(50% - 3px) !important;
        }
        /* 차트 높이를 모바일 비율에 맞춰 최적화 */
        .stPlotlyChart { height: 250px !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결 (사장님의 시트 주소 자동 적용)
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
    st.sidebar.markdown("### 🎯 분석 리포트 선택")
    stock_list = df_sheet['종목명'].dropna().unique().tolist()
    selected_name = st.sidebar.selectbox("종목 선택", stock_list)
    stock_info = df_sheet[df_sheet['종목명'] == selected_name].iloc[0]
else:
    st.error("⚠️ 시트 데이터를 가져오지 못했습니다. '공유' 설정을 확인해주세요!")
    st.stop()

# 5. 차트 생성 함수 (확대 기능 포함)
def draw_chart(ticker, period, title):
    interval = "1wk" if period == "max" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    if df.empty: return st.error(f"{title} 데이터 없음")

    fig
