import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정
st.set_page_config(
    page_title="사장님 전용 금융 터미널", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. [정밀 수술] 화면을 꽉 채우되 밖으로 나가지 않게 하는 CSS
st.markdown("""
    <style>
    /* 불필요한 요소 제거 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}

    /* 전체 페이지 가로 스크롤 방지 */
    .main .block-container {
        max-width: 100% !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        overflow-x: hidden !important;
    }

    /* 모바일 2x2 강제 배치 (너비 정밀 조정) */
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important;
            width: 100% !important;
            gap: 4px !important;
        }
        [data-testid="column"] {
            /* 50%에서 여백을 뺀 정밀한 값으로 옆으로 밀리는 현상 방지 */
            width: calc(50% - 6px) !important;
            flex: 1 1 calc(50% - 6px) !important;
            min-width: calc(50% - 6px) !important;
        }
        /* 차트 높이를 모바일 비율에 맞춰 살짝 줄임 */
        .stPlotlyChart { height: 220px !important; }
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
    except: return None

df_sheet = load_data(url)

# 4. 종목 선택
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.markdown("### 🎯 종목 리서치")
    stock_list = df_sheet['종목명'].dropna().unique().tolist()
    selected_name = st.sidebar.selectbox("종목 선택", stock_list)
    stock_info = df_sheet[df_sheet['종목명'] == selected_name].iloc[0]
else:
    st.stop()

# 5. 차트 생성 함수 (확대 기능 유지)
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
        title=dict(text=title, font=dict(size=11)),
        height=300, 
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=2, r=2, b=2, t=35),
        yaxis_type="log" if period == "max" else "linear",
        xaxis=dict(fixedrange=True),
        yaxis=dict(fixedrange=True)
    )
    
    return st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['zoom', 'pan', 'select', 'lasso2d', 'zoomIn', 'zoomOut', 'autoScale', 'resetScale2d'],
        'displaylogo': False
    })

# 6. 메인 화면 구성
st.markdown(f"#### 🚀 {selected_name} ({stock_info['코드']})")

# 강제 2열 배치
col1, col2 = st.columns(2)
with col1: draw_chart(stock_info['코드'], "1mo", "1개월")
with col2: draw_chart(stock_info['코드'], "3mo", "3개월")

col3, col4 = st.
