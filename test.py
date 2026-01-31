import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정 (가장 윗줄에 있어야 함)
st.set_page_config(
    page_title="사장님 전용 가치투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None 
    }
)

# 2. 유료 사이트 느낌을 주는 화면 세척 CSS (최종 강화 버전)
# 모바일에서 왕관과 아이콘을 최대한 가리기 위한 설정입니다.
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    /* 모바일 여백 및 툴바 숨기기 */
    .block-container {padding-top: 1rem; padding-bottom: 0rem; padding-left: 1rem; padding-right: 1rem;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}
    /* 소스 보기 버튼 등 숨기기 */
    button[title="View source code"] {display: none;}
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

# 4. 사이드바 구성 및 데이터 확인
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.markdown("### 🎯 분석 리포트 선택")
    stock_list = df_sheet['종목명'].dropna().unique().tolist()
    selected_name = st.sidebar.selectbox("종목을 선택하세요", stock_list)
    stock_info = df_sheet[df_sheet['종목명'] == selected_name].iloc[0]
else:
    st.error("⚠️ 구글 시트에서 데이터를 가져올 수 없습니다. '공유' 설정을 다시 확인해주세요!")
    st.stop()

# 5. 차트 생성 함수
def draw_chart(ticker, period, title):
    interval = "1wk" if period == "max" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    if df.empty:
        return st.error(f"{title} 데이터를 가져오지 못했습니다.")

    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], 
        low=df['Low'], close=df['Close'], name=title
    )])
    fig.update_layout(
        title=title, height=380, template="plotly_dark",
        xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, b=10, t=50),
        yaxis_type="log" if period == "max" else "linear"
    )
    return st.plotly_chart(fig, use_container_width=True)

# 6. 메인 화면 구성
st.title(f"🚀 {selected_name} ({stock_info['코드']})")

row1_l, row1_r = st.columns(2)
with row1_l: draw_chart(stock_info['코드'], "1mo", "📅 단기 (1개월)")
with row1_r: draw_chart(stock_info['코드'], "3mo", "📅 분기 (3개월)")

row2_l, row2_r = st.columns(2)
with row2_l: draw_chart(stock_info['코드'], "1y", "📅 중기 (1년)")
with row2_r: draw_chart(stock_info['코드'], "max", "🏛️ 전체 역사 (로그)")

st.write("---")

# 7. 하단 가치평가 리포트
st.subheader(f"📑 {selected_name} 투자 인사이트")
col_a, col_b = st.columns([1, 2])
with col_a:
    st.metric("사장님 목표 적정가", f"{stock_info['적정가']}")
with col_b:
    st.success(f"**💡 분석 메모**\n\n{stock_info['메모']}")

st.write("---")
st.caption("※ 구글 시트를 수정하면 약 1분 뒤 사이트에 자동 반영됩니다.")
