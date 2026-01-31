import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정
st.set_page_config(
    page_title="사장님 전용 가치투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={'Get Help': None, 'Report a bug': None, 'About': None}
)

# 2. 화면 세척 CSS
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 1rem; padding-bottom: 0rem; padding-left: 1rem; padding-right: 1rem;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}
    button[title="View source code"] {display: none;}
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

@st.cache_data(ttl=60)
def load_data(csv_url):
    try:
        df = pd.read_csv(csv_url)
        return df
    except: return None

df_sheet = load_data(url)

# 4. 사이드바 종목 선택
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.markdown("### 🎯 분석 리포트 선택")
    stock_list = df_sheet['종목명'].dropna().unique().tolist()
    selected_name = st.sidebar.selectbox("종목을 선택하세요", stock_list)
    stock_info = df_sheet[df_sheet['종목명'] == selected_name].iloc[0]
else:
    st.stop()

# 5. 차트 생성 함수 (확대/축소 금지 버전)
def draw_chart(ticker, period, title):
    interval = "1wk" if period == "max" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    if df.empty: return st.error(f"{title} 데이터 에러")

    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], 
        low=df['Low'], close=df['Close'], name=title
    )])

    fig.update_layout(
        title=title, height=380, template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, b=10, t=50),
        yaxis_type="log" if period == "max" else "linear",
        # --- [여기가 핵심!] 확대/축소 및 이동 금지 설정 ---
        xaxis=dict(fixedrange=True), 
        yaxis=dict(fixedrange=True),
        dragmode=False # 드래그 기능도 끕니다
    )
    
    # 툴바(확대, 축소 버튼 등)를 아예 안 보이게 숨깁니다
    return st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# 6. 메인 화면
st.title(f"🚀 {selected_name} ({stock_info['코드']})")

row1_l, row1_r = st.columns(2)
with row1_l: draw_chart(stock_info['코드'], "1mo", "📅 단기 (1개월)")
with row1_r: draw_chart(stock_info['코드'], "3mo", "📅 분기 (3개월)")

row2_l, row2_r = st.columns(2)
with row2_l: draw_chart(stock_info['코드'], "1y", "📅 중기 (1년)")
with row2_r: draw_chart(stock_info['코드'], "max", "🏛️ 전체 역사 (로그)")

st.write("---")

# 7. 하단 리포트
st.subheader(f"📑 {selected_name} 투자 인사이트")
col_a, col_b = st.columns([1, 2])
with col_a: st.metric("목표 적정가", f"{stock_info['적정가']}")
with col_b: st.success(f"**💡 분석 메모**\n\n{stock_info['메모']}")
