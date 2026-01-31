import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정
st.set_page_config(
    page_title="사장님 전용 가치투자 터미널", 
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={'Get Help': None, 'Report a bug': None, 'About': None}
)

# 2. [강력 수정] 모바일에서도 강제로 2x2 격자를 만드는 마법의 CSS
st.markdown("""
    <style>
    /* 기본 메뉴 및 푸터 숨기기 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}

    /* [핵심] 모바일에서도 컬럼이 밑으로 떨어지지 않게 강제 고정 */
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
    }
    div[data-testid="column"] {
        width: 48% !important; /* 2개씩 배치하기 위해 약 50% 설정 */
        flex: 1 1 48% !important;
        min-width: 48% !important;
        padding: 2px !important;
    }
    
    /* 차트 높이를 모바일에 맞게 최적화 */
    .stPlotlyChart { height: 220px !important; }

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

# 5. 차트 생성 함수 (확대 버튼 활성화)
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
        title=dict(text=title, font=dict(size=10)), # 제목 작게
        height=300, template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=2, r=2, b=2, t=30),
        yaxis_type="log" if period == "max" else "linear",
        xaxis=dict(fixedrange=True), # 드래그 금지 (스크롤 원활하게)
        yaxis=dict(fixedrange=True)
    )
    
    # modeBar(툴바)를 살려서 확대 버튼을 쓸 수 있게 합니다.
    return st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['zoom', 'pan', 'select', 'lasso2d', 'zoomIn', 'zoomOut', 'autoScale', 'resetScale2d'],
        'displaylogo': False
    })

# 6. 메인 화면: 2x2 레이아웃
st.markdown(f"### 🚀 {selected_name} ({stock_info['코드']})")

col1, col2 = st.columns(2)
with col1: draw_chart(stock_info['코드'], "1mo", "1개월")
with col2: draw_chart(stock_info['코드'], "3mo", "3개월")

col3, col4 = st.columns(2)
with col3: draw_chart(stock_info['코드'], "1y", "1년")
with col4: draw_chart(stock_info['코드'], "max", "전체")

st.write("---")

# 7. 하단 리포트
c_a, c_b = st.columns([1, 2])
with c_a: st.metric("목표가", f"{stock_info['적정가']}")
with c_b: st.info(f"**分析:** {stock_info['메모']}")
