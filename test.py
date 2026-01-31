import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정 (가장 윗줄에 위치해야 합니다)
st.set_page_config(
    page_title="사장님 전용 금융 터미널", 
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={'Get Help': None, 'Report a bug': None, 'About': None}
)

# 2. [초강력 CSS] 모바일에서도 강제로 2x2 격자를 만드는 마법의 명령어
# 스트림릿의 기본 '줄 세우기' 기능을 원천 차단하고 폰 화면을 꽉 채웁니다.
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}

    /* 모바일 화면에서도 가로로 2개씩 강제 배치 */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        width: 100% !important;
    }
    
    /* 각 컬럼의 너비를 강제로 50%로 고정 */
    [data-testid="column"] {
        width: 48% !important; 
        flex: 1 1 48% !important;
        min-width: 48% !important;
        padding: 2px !important;
    }

    /* 차트 높이 최적화 */
    .stPlotlyChart { height: 260px !important; }

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
    except:
        return None

df_sheet = load_data(url)

# 4. 사이드바 구성 및 종목 선택
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.markdown("### 🎯 분석 리포트 선택")
    stock_list = df_sheet['종목명'].dropna().unique().tolist()
    selected_name = st.sidebar.selectbox("종목을 고르세요", stock_list)
    stock_info = df_sheet[df_sheet['종목명'] == selected_name].iloc[0]
else:
    st.error("⚠️ 구글 시트 데이터를 가져올 수 없습니다. 공유 설정을 확인해주세요!")
    st.stop()

# 5. 차트 생성 함수 (오타 및 괄호 꼼꼼히 체크 완료!)
def draw_chart(ticker, period, title):
    interval = "1wk" if period == "max" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    if df.empty:
        return st.error(f"{title} 데이터 없음")

    fig = go.Figure(data=[go.Candlestick(
        x=df.index, 
        open=df['Open'], 
        high=df['High'], 
        low=df['Low'], 
        close=df['Close'], 
        name=title
    )])

    fig.update_layout(
        title=dict(text=title, font=dict(size=12)),
        height=320, 
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=5, r=5, b=5, t=35),
        yaxis_type="log" if period == "max" else "linear",
        xaxis=dict(fixedrange=True), 
        yaxis=dict(fixedrange=True)
    )
    
    # 전체화면 아이콘을 살려서 확대 가능하게 설정
    return st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': True,
        'modeBarButtons
