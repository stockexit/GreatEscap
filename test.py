import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 화면 설정 (접속하자마자 메뉴를 열어두는 핵심 설정)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" # 이 명령어가 메뉴를 처음부터 열어줍니다!
)

# 2. [완전 순정] 아이콘 실종 방지를 위해 최소한의 스타일만 적용
st.markdown("""
    <style>
    /* 하단 푸터만 숨기고 헤더(메뉴버튼 영역)는 살려둡니다 */
    footer {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}
    
    /* 사이드바 너비를 적당히 고정해 가독성 확보 */
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

# 4. 차트 그리기 함수 (오타 완벽 박멸 수술 완료)
def draw_chart(ticker, period, title):
    try:
        # 3개월은 일봉, 5년은 주봉
        interval = "1wk" if period == "5y" else "1d"
        df = yf.download(ticker, period=period, interval=interval)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty:
            return st.write(f"⚠️ {title}: 데이터 로딩 중...")

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
        return st.error(f"⚠️ {title}: 차트를 불러올 수 없습니다.")

# 5. 메인 로직 실행 (NameError 방지를 위해 모든 출력을 이 안에 묶음)
if df_sheet is not None and not df_sheet.empty:
    # 사이드바: 종목 선택
    st.sidebar.markdown("## 🎯 분석 종목 리스트")
    st.sidebar.write("---")
    
    stock_names = df_sheet['종목명'].unique().tolist()
    selected = st.sidebar.selectbox("종목을 고르세요 👇", stock_names)
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
    
    st.sidebar.write
