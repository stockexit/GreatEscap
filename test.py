import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 화면 설정 (사이드바를 처음부터 펼쳐서 고정)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. 불필요한 요소 제거 (깔끔한 순정 스타일)
st.markdown("""
    <style>
    header {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    /* 사이드바 너비 조절 */
    [data-testid="stSidebar"] { min-width: 250px; max-width: 250px; }
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 데이터 로드
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

# 4. [수정] 다시 사이드바로 이동한 종목 선택 메뉴
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.markdown("## 🎯 종목 리서치")
    st.sidebar.write("---")
    
    stock_names = df_sheet['종목명'].unique().tolist()
    # 사이드바에 선택창 배치
    selected = st.sidebar.selectbox("분석할 종목을 고르세요 👇", stock_names)
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
    
    st.sidebar.write("---")
    st.sidebar.success(f"현재 분석 중: **{selected}**")
else:
    st.error("데이터 로딩 실패! 시트 설정을 확인해주세요.")
    st.stop()

# 5. 차트 그리기 함수 (SyntaxError 모든 지점 수술 완료)
def draw_chart(ticker, period, title):
    try:
        # ternary operator 완성
        interval = "1wk" if period == "5y" else "1d"
        df = yf.download(ticker, period=period, interval=interval)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # f-string 따옴표 닫기
        if df.empty:
            return st.write(f"⚠️ {title}: 데이터 없음")

        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name=title
        )])

        # dict 괄호 닫기 및 레이아웃 설정
        fig.update_layout(
            title=dict(text=title, font=dict(size=18)),
            height=500, 
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, b=10, t=50),
            yaxis_type="log" if period == "5y" else "linear",
            xaxis=dict(fixedrange=True),
            yaxis=dict(fixedrange=True)
        )
        return st.plotly_chart(fig, use_container_width=True)
    except:
        return st.write(
