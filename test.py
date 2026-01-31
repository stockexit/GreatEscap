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

# 2. 화면 세척 (메뉴, 푸터 등 지저분한 것만 제거)
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}
    .block-container {padding-top: 2rem; padding-bottom: 0rem;}
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결 (사장님의 시트 주소)
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

@st.cache_data(ttl=10)
def load_data(csv_url):
    try:
        df = pd.read_csv(csv_url)
        return df
    except:
        return None

df_sheet = load_data(url)

# 4. 종목 선택
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.markdown("### 🎯 분석 리포트")
    valid_df = df_sheet.dropna(subset=['종목명'])
    stock_list = valid_df['종목명'].unique().tolist()
    selected_name = st.sidebar.selectbox("종목 선택", stock_list)
    stock_info = valid_df[valid_df['종목명'] == selected_name].iloc[0]
else:
    st.warning("시트 데이터를 불러오는 중...")
    st.stop()

# 5. 차트 생성 함수
def draw_chart(ticker, period, title):
    # 5년치는 주 단위(1wk), 3개월치는 일 단위(1d)로 설정
    interval = "1wk" if period == "5y" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    if df.empty:
        return st.write(f"{title}: 로드 실패")

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
    
    # 돋보기(전체화면) 아이콘은 기본으로 유지됩니다.
    return st.plotly_chart(fig, use_container_width=True)

# 6. 메인 화면 구성 (차트 2개 집중 배치)
st.title(f"🚀 {selected_name} ({stock_info['코드']})")

col1, col2 = st.columns(2)
with col1:
    draw_chart(stock_info['코드'], "3mo", "📅 단기 흐름 (3개월)")
with col2:
    draw_chart(stock_info['코드'], "5y", "🏛️ 장기 성장 (5년)")

st.write("---")

# 7. 하단 리포트 (사장님 인사이트)
c_a, c_b = st.columns([1, 2])
with c_a:
    st.metric("사장님 목표가", f"{stock_info['적정가']}")
with c_b:
    st.success(f"**💡 분석 의견:** {stock_info['메모']}")
