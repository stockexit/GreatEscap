import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정 (가장 윗줄에 위치)
st.set_page_config(
    page_title="사장님 전용 금융 터미널", 
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={'Get Help': None, 'Report a bug': None, 'About': None}
)

# 2. [초강력 CSS] 모바일에서도 2x2 격자를 강제하는 마법의 코드
st.markdown("""
    <style>
    /* 기본 UI 제거 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}

    /* 모바일에서도 한 줄에 2개씩 강제 배치 (flex-direction 고정) */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        width: 100% !important;
        gap: 0px !important;
    }
    
    /* 각 컬럼의 너비를 강제로 50%로 고정 */
    [data-testid="column"] {
        width: 50% !important;
        flex: 1 1 50% !important;
        min-width: 50% !important;
    }

    /* 차트 높이 최적화 및 여백 제거 */
    .stPlotlyChart { height: 260px !important; }
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
    st.error("데이터 로딩 실패! 구글 시트 공유 설정을 확인하세요.")
    st.stop()

# 5. 차트 생성 함수 (오타 및 괄호 꼼꼼히 체크 완료)
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
        title=dict(text=title, font=dict(size=11)),
        height=300, 
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=2, r=2, b=2, t=35),
        yaxis_type="log" if period == "max" else "linear",
        xaxis=dict(fixedrange=True), # 스크롤을 위해 드래그 방지
        yaxis=dict(fixedrange=True)
    )
    
    # 돋보기(전체화면) 아이콘을 활성화하여 폰에서도 크게 볼 수 있게 함
    return st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['zoom', 'pan', 'select', 'lasso2d', 'zoomIn', 'zoomOut', 'autoScale', 'resetScale2d'],
        'displaylogo': False
    })

# 6. 메인 화면 구성
st.markdown(f"#### 🚀 {selected_name} ({stock_info['코드']})")

# 2x2 격자 배치
row1_left, row1_right = st.columns(2)
with row1_left:
    draw_chart(stock_info['코드'], "1mo", "📅 1개월")
with row1_right:
    draw_chart(stock_info['코드'], "3mo", "📅 3개월")

row2_left, row2_right = st.columns(2)
with row2_left:
    draw_chart(stock_info['코드'], "1y", "📅 1년")
with row2_right:
    draw_chart(stock_info['코드'], "max", "🏛️ 전체")

st.write("---")

# 7. 하단 리포트
c_a, c_b = st.columns([1, 2])
with c_a:
    st.metric("목표 적정가", f"{stock_info['적정가']}")
with c_b:
    st.info(f"**💡 분석 메모:**\n{stock_info['메모']}")
