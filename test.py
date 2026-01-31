import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정 (가장 윗줄 고정)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. 지저분한 UI 제거 (메뉴, 푸터 숨기기)
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}
    .block-container {padding-top: 1.5rem; padding-bottom: 0rem;}
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결 (사장님의 시트 주소 자동 적용)
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

# 1분마다 새 데이터를 확인하도록 설정 (ttl=60)
@st.cache_data(ttl=60)
def load_data(csv_url):
    try:
        return pd.read_csv(csv_url)
    except:
        return None

df_sheet = load_data(url)

# 4. 종목 선택 및 데이터 추출
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.title("🎯 종목 리스트")
    # 종목명이 있는 데이터만 깨끗하게 정리
    valid_df = df_sheet.dropna(subset=['종목명'])
    stock_names = valid_df['종목명'].unique().tolist()
    selected = st.sidebar.selectbox("종목 선택", stock_names)
    
    # 선택된 종목의 정보 가져오기
    s_info = valid_df[valid_df['종목명'] == selected].iloc[0]
else:
    st.error("구글 시트 로딩 중입니다... 시트 공유 설정을 확인해주세요!")
    st.stop()

# 5. 차트 그리기 함수
def draw_chart(ticker, period, title):
    # 5년치는 주 단위(1wk), 3개월치는 일 단위(1d)로 설정
    interval = "1wk" if period == "5y" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    if df.empty:
        return st.write(f"{title}: 데이터 로드 실패 (티커 확인)")

    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], 
        low=df['Low'], close=df['Close'], name=title
    )])

    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        height=450, 
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, b=10, t=50),
        yaxis_type="log" if period == "5y" else "linear"
    )
    
    return st.plotly_chart(fig, use_container_width=True)

# 6. 메인 화면 구성
st.title(f"🚀 {selected} ({s_info['코드']})")

# 차트 2개를 양옆(PC) 또는 위아래(모바일)로 배치
col1, col2 = st.columns(2)
with col1:
    draw_chart(s_info['코드'], "3mo", "📅 최근 3개월 흐름")
with col2:
    draw_chart(s_info['코드'], "5y", "🏛️ 5년 장기 성장 (로그)")

st.write("---")

# 7. 하단 리포트 (사장님 인사이트)
c_a, c_b = st.columns([1, 2])
with c_a:
    st.metric("사장님 목표가", f"{s_info['적정가']}")
with c_b:
    st.success(f"**💡 분석 메모:**\n\n{s_info['메모']}")
