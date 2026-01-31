import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정
st.set_page_config(
    page_title="사장님 전용 금융 터미널", 
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={'Get Help': None, 'Report a bug': None, 'About': None}
)

# 2. [강력 권고] 시스템 설정을 무시하고 강제로 옆으로 붙이는 마법의 CSS
st.markdown("""
    <style>
    /* 기본 UI 제거 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}

    /* [핵심] 모바일에서도 컬럼이 밑으로 떨어지는 것을 원천 봉쇄 */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        width: 100% !important;
    }
    
    /* 각 컬럼의 너비를 강제로 50%로 고정 (폰에서도 무조건 옆으로 붙음) */
    [data-testid="column"] {
        width: calc(50% - 10px) !important;
        flex: 1 1 calc(50% - 10px) !important;
        min-width: calc(50% - 10px) !important;
        margin: 5px !important;
    }

    /* 차트 높이 최적화 (폰 화면에 꽉 차게) */
    .stPlotlyChart { height: 280px !important; }

    /* 여백 최소화 */
    .block-container {padding: 0.5rem !important;}
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
    except: return None

df_sheet = load_data(url)

# 4. 사이드바 구성
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.markdown("### 🎯 종목 선택")
    stock_list = df_sheet['종목명'].dropna().unique().tolist()
    selected_name = st.sidebar.selectbox("리포트", stock_list)
    stock_info = df_sheet[df_sheet['종목명'] == selected_name].iloc[0]
else:
    st.stop()

# 5. 차트 생성 함수 (확대 기능 활성화)
def draw_chart(ticker, period, title):
    interval = "1wk" if period == "max" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    if df.empty: return st.error("Error")

    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], 
        low=df['Low'], close=df['Close'], name=title
    )])

    fig.update_layout(
        title=dict(text=title, font=dict(size=12)),
        height=320, template="plotly_dark",
        xaxis
