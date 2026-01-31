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

# 2. [핵심] 모바일에서도 2x2를 유지하고 화면을 꽉 채우는 CSS
st.markdown("""
    <style>
    /* 메뉴 및 푸터 숨기기 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}
    
    /* 모바일(화면 폭 640px 이하)에서도 컬럼을 옆으로 2개씩 배치 */
    @media (max-width: 640px) {
        [data-testid="column"] {
            width: 49% !important;
            flex: 1 1 49% !important;
            min-width: 49% !important;
        }
        .stPlotlyChart { height: 250px !important; } /* 모바일에서 차트 높이 조절 */
    }
    
    /* 전체 여백 최소화 */
    .block-container {padding: 0.5rem !important;}
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결 (사장님 시트 주소 고정)
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

@st.cache_data(ttl=60)
def load_data(csv_url):
    try:
        df = pd.read_csv(csv_url)
        return df
    except: return None

df_sheet = load_data(url)

# 4. 사이드바 및 종목 선택
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.markdown("### 🎯 종목 리포트")
    stock_list = df_sheet['종목명'].dropna().unique().tolist()
    selected_name = st.sidebar.selectbox("종목 선택", stock_list)
    stock_info = df_sheet[df_sheet['종목명'] == selected_name].iloc[0]
else:
    st.stop()

# 5. 차트 생성 함수 (확대 기능 포함)
def draw_chart(ticker, period, title):
    interval = "1wk" if period == "max" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    if df.empty: return st.error("데이터 로드 실패")

    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], 
        low=df['Low'], close=df['Close'], name=title
    )])

    fig.update_layout(
        title=dict(text=title, font=dict(size=12)), # 모바일 가독성을 위해 제목 크기 조절
        height=350, template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=5, r=5, b=5, t=40),
        yaxis_type="log" if period == "max" else "linear",
        # 확대/축소 기능은 켜두되 드래그는 방지 (스크롤을 위해)
        xaxis=dict(fixedrange=False), 
        yaxis=dict(fixedrange=False),
        dragmode=False 
    )
    
    # config에서 'displayModeBar': True 로 설정하여 확대 버튼 등을 살립니다.
    return st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': True, 
        'modeBarButtonsToRemove': ['zoom', 'pan', 'select', 'lasso2d'], # 필요한 것만 남김
        'displaylogo': False
    })

# 6. 메인 화면: 2x2 레이아웃
st.subheader(f"🚀 {selected_name} ({stock_info['코드']})")

col1, col2 = st.columns(2)
with col1: draw_chart(stock_info['코드'], "1mo", "📅 1개월")
with col2: draw_chart(stock_info['코드'], "3mo", "📅 3개월")

col3, col4 = st.columns(2)
with col3: draw_chart(stock_info['코드'], "1y", "📅 1년")
with col4: draw_chart(stock_info['코드'], "max", "🏛️ 전체")

st.write("---")

# 7. 하단 리포트
info_a, info_b = st.columns([1, 2])
with info_a: st.metric("목표가", f"{stock_info['적정가']}")
with info_b: st.info(f"**💡 분석 메모**\n\n{stock_info['메모']}")
