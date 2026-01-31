import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 화면 설정 (사장님이 좋아하신 '왼쪽 메뉴 고정' 버전)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. 지저분한 요소 제거 (에러 방지를 위해 헤더는 살려둡니다)
st.markdown("""
    <style>
    footer {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}
    /* 사이드바 가독성 향상 */
    [data-testid="stSidebar"] { min-width: 260px; }
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

@st.cache_data(ttl=60)
def load_data(csv_url):
    try:
        df = pd.read_csv(csv_url)
        return df.dropna(subset=['종목명'])
    except:
        return None

df_sheet = load_data(url)

# 4. 차트 그리기 함수 (SyntaxError 완벽 박멸)
def draw_chart(ticker, period, title):
    try:
        # 3개월은 일간 데이터, 5년은 주간 데이터
        interval = "1wk" if period == "5y" else "1d"
        df = yf.download(ticker, period=period, interval=interval)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty:
            return st.write(f"⚠️ {title}: 데이터를 찾을 수 없습니다.")

        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name=title
        )])

        fig.update_layout(
            title=dict(text=title, font=dict(size=18)),
            height=500, 
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, b=10, t=50),
            yaxis_type="log" if period == "5y" else "linear"
        )
        return st.plotly_chart(fig, use_container_width=True)
    except:
        return st.error(f"⚠️ {title}: 로딩 에러")

# 5. 메인 실행 로직 (NameError 방지를 위해 순서 조정)
if df_sheet is not None and not df_sheet.empty:
    # 사이드바: 종목 선택
    st.sidebar.markdown("## 🎯 분석 종목 리스트")
    st.sidebar.write("---")
    
    stock_names = df_sheet['종목
