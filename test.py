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

# 2. [초강력 CSS] 시스템의 고집을 완전히 꺾는 모바일 2x2 강제 설정
st.markdown("""
    <style>
    /* 1. 기본 메뉴 및 불필요한 UI 제거 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}

    /* 2. [핵심] 모바일 화면(768px 이하)에서 컬럼이 아래로 떨어지는 것을 원천 봉쇄 */
    @media (max-width: 768px) {
        /* 가로 배치 컨테이너 강제 고정 */
        [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important; /* 아래로 절대 안 내려가게 막음 */
            align-items: stretch !important;
            gap: 5px !important;
        }
        
        /* 각 컬럼의 너비를 무조건 50%로 고정 */
        [data-testid="column"] {
            width: 50% !important;
            flex: 1 1 50% !important;
            min-width: 50% !important;
        }

        /* 차트 높이를 폰 화면에 적절하게 조정 */
        .stPlotlyChart { height: 240px !important; }
    }
    
    /* 3. 전체 여백 최소화 */
    .block-container {padding: 0.5rem !important;}
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결 (사장님의 시트 주소)
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

# 4. 사이드바 종목 선택
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.markdown("### 🎯 종목 리서치")
    stock_list = df_sheet['종목명'].dropna().unique().tolist()
    selected_name = st.sidebar.selectbox("종목 선택", stock_list)
    stock_info = df_sheet[df_sheet['종목명'] == selected_name].iloc[0]
else:
    st.error("데이터 로딩 실패! 시트 설정을 확인해주세요.")
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
        title=dict(text=title, font=dict(size=11)),
        height=300, 
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=2, r=2, b=2, t=35),
        yaxis_type="log" if period == "max" else "linear",
        xaxis=dict(fixedrange=True), # 스크롤을 방해하지 않도록 드래그 방지
        yaxis=dict(fixedrange=True)
    )
    
    # 돋보기(전체화면) 아이콘을 살려서 폰에서 크게 볼 수 있게 함
    return st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['zoom', 'pan', 'select', 'lasso2d', 'zoomIn', 'zoomOut', 'autoScale', 'resetScale2d'],
        'displaylogo': False
    })

# 6. 메인 화면: 2x2 강제 격자
st.markdown(f"#### 🚀 {selected_name} ({stock_info['코드']})")

# 첫 번째 줄 (2개 강제 결합)
col1, col2 = st.columns(2)
with col1: draw_chart(stock_info['코드'], "1mo", "📅 1개월")
with col2: draw_chart(stock_info['코드'], "3mo", "📅 3개월")

# 두 번째 줄 (2개 강제 결합)
col3, col4 = st.columns(2)
with col3: draw_chart(stock_info['코드'], "1y", "📅 1년")
with col4: draw_chart(stock_info['코드'], "max", "🏛️ 전체")

st.write("---")

# 7. 하단 가치평가 리포트
c_a, c_b = st.columns([1, 2])
with c_a: st.metric("목표가", f"{stock_info['적정가']}")
with c_b: st.success(f"**分析:** {stock_info['메모']}")
