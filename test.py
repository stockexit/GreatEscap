import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정 (가장 윗줄 고정)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" # 사이드바가 처음부터 보이게 설정
)

# 2. [수정] 메뉴는 살리고 지저분한 요소만 제거하는 안전한 CSS
st.markdown("""
    <style>
    /* 상단 헤더와 하단 푸터만 제거 */
    header[data-testid="stHeader"] { visibility: hidden; }
    footer { visibility: hidden; }
    
    /* 사이드바가 모바일에서도 잘 보이도록 배경색 강조 */
    [data-testid="stSidebar"] {
        background-color: #111111 !important;
        border-right: 1px solid #333;
    }
    
    /* 전체 여백 조정 */
    .block-container { padding-top: 1rem !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUE?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

@st.cache_data(ttl=30) # 30초마다 데이터 갱신
def load_data(csv_url):
    try:
        df = pd.read_csv(csv_url)
        return df.dropna(subset=['종목명']) # 종목명이 있는 것만 가져옴
    except:
        return None

df_sheet = load_data(url)

# 4. 종목 선택 (사이드바 메뉴)
if df_sheet is not None and not df_sheet.empty:
    # 시트의 모든 종목명을 가져옵니다
    stock_list = df_sheet['종목명'].unique().tolist()
    
    st.sidebar.markdown("### 🎯 분석 종목")
    # [중요] 여기서 종목을 선택하면 화면이 바뀝니다!
    selected = st.sidebar.selectbox("리스트에서 고르세요 👇", stock_list)
    
    # 선택된 종목의 데이터 한 줄 추출
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
else:
    st.error("구글 시트 로딩 실패! 공유 설정을 확인해주세요.")
    st.stop()

# 5. 차트 그리기 함수 (괄호 및 오타 완벽 수정)
def draw_chart(ticker, period, title):
    try:
        # 5년치는 주 단위(1wk), 3개월치는 일 단위(1d)
        interval = "1wk" if period == "5y" else "1d"
        df = yf.download(ticker, period=period, interval=interval)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty:
            return st.write(f"⚠️ {title}: 데이터 없음")

        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name=title
        )])

        fig.update_layout(
            title=dict(text=title, font=dict(size=14)),
            height=450, 
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=
