import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 화면 설정 (접속하자마자 메뉴를 열어두는 핵심 설정)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" # 메뉴를 처음부터 열어줍니다!
)

# 2. [수정] 메뉴 버튼은 살리고 지저분한 요소만 가리는 CSS
st.markdown("""
    <style>
    /* 하단 푸터만 숨기고 헤더(메뉴버튼 영역)는 살려둡니다 */
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
        # 종목명이 있는 데이터만 가져오기
        return df.dropna(subset=['종목명'])
    except:
        return None

df_sheet = load_data(url)

# 4. 차트 그리기 함수 (SyntaxError 완벽 수술)
def draw_chart(ticker, period, title):
    try:
        # 3개월(일봉), 5년(주봉) 설정
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
            title=dict(text=title, font=dict(size=18)),
            height=500, 
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, b=10, t=50),
            yaxis_type="log" if period == "5y" else "linear"
        )
        return st.plotly_chart(fig, use_container_width=True)
    except:
        return st.error(f"⚠️ {title}: 로드 실패")

# 5. 메인 로직 실행 (NameError 방지를 위해 순서 조정)
if df_sheet is not None and not df_sheet.empty:
    # 사이드바: 종목 선택
    st.sidebar.markdown("## 🎯 분석 종목 리스트")
    st.sidebar.write("---")
    
    stock_names = df_sheet['종목명'].unique().tolist()
    selected = st.sidebar.selectbox("종목을 고르세요 👇", stock_names)
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
    
    st.sidebar.write("---")
    st.sidebar.success(f"현재 분석 중: **{selected}**")

    # 메인 화면 구성
    st.title(f"🚀 {selected} ({s_info['코드'].upper()})")

    # 차트 2개 배치 (PC 가로, 모바일 세로)
    col1, col2 = st.columns(2)
    with col1:
        draw_chart(s_info['코드'], "3mo", "📅 최근 3개월 흐름")
    with col2:
        draw_chart(s_info['코드'], "5y", "🏛️ 5년 장기 성장")

    st.write("---")

    # 하단 정보 리포트
    c_a, c_b = st.columns([1, 2])
    with c_a:
        st.metric("사장님 목표가", f"{s_info['적정가']}")
    with c_b:
        st.success(f"**💡 분석 메모:**\n\n{s_info['메모']}")
else:
    st.error("데이터 로딩 실패! 시트 주소를 확인해주세요.")
