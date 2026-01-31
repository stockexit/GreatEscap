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

# 2. [강력 CSS] 모바일에서도 무조건 2x2 격자를 만드는 마법의 명령어
st.markdown("""
    <style>
    /* 기본 UI 제거 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}

    /* 모바일에서도 한 줄에 2개씩 강제 배치 */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        width: 100% !important;
    }
    
    [data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        width: 48% !important; 
        flex: 1 1 48% !important;
        min-width: 48% !important;
        margin-bottom: 5px !important;
    }

    /* 차트 높이 최적화 */
    .stPlotlyChart { height: 260px !important; }

    /* 여백 최소화 */
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
    st.sidebar.markdown("### 🎯 종목 리서치")
    stock_list = df_sheet['종목명'].dropna().unique().tolist()
    selected_name = st.sidebar.selectbox("종목 선택", stock_list)
    stock_info = df_sheet[df_sheet['종목명'] == selected_name].iloc[0]
else:
    st.error("데이터 로딩 실패")
    st.stop()

# 5. 차트 생성 함수 (괄호 오타 수정 완료!)
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

    # 괄호 닫기 확실히 확인!
    fig.update_layout(
        title=dict(text=title, font=dict(size=12)),
        height=300, 
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=5, r=5, b=5, t=35),
        yaxis_type="log" if period == "max" else "linear",
        xaxis=dict(fixedrange=False), 
        yaxis=dict(fixedrange=False)
    )
    
    # 돋보기(전체화면) 버튼 활성화
    return st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['zoom', 'pan', 'select', 'lasso2d', 'zoomIn', 'zoomOut', 'autoScale', 'resetScale2d'],
        'displaylogo': False
    })

# 6. 메인 화면: 2x2 고정 레이아웃
st.markdown(f"#### 🚀 {selected_name} ({stock_info['코드']})")

# 가로로 2개씩 강제 배치
row1_col1, row1_col2 = st.columns(2)
with row1_col1: draw_chart(stock_info['코드'], "1mo", "📅 1개월")
with row1_col2: draw_chart(stock_info['코드'], "3mo", "📅 3개월")

row2_col1, row2_col2
