import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 화면 설정 (메뉴창을 처음부터 펼쳐서 고정)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. [순정 스타일] 로고 가리기 기능을 빼서 모바일 메뉴 버튼을 살렸습니다.
st.markdown("""
    <style>
    /* 하단 푸터와 우측 상단 메뉴만 깔끔하게 제거 */
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
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

# 4. 차트 그리기 함수 (SyntaxError 완벽 박멸 수술 완료)
def draw_chart(ticker, period, title):
    try:
        # 3개월은 일봉, 5년은 주봉/로그차트
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
        return st.error(f"⚠️ {title}: 데이터를 가져올 수 없습니다.")

# 5. 메인 실행 로직 (NameError 방지를 위해 모든 변수를 이 안에 넣음)
if df_sheet is not None and not df_sheet.empty:
    # 사이드바: 종목 선택 메뉴
    st.sidebar.markdown("## 🎯 분석 종목 리스트")
    st.sidebar.write("---")
    
    stock_names = df_sheet['종목명'].unique().tolist()
    selected = st.sidebar.selectbox("종목을 고르세요 👇", stock_names)
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
    
    st.sidebar.write("---")
    st.sidebar.success(f"현재 분석: **{selected}**")

    # 메인 화면 구성
    st.title(f"🚀 {selected} ({s_info['코드'].upper()})")

    # 차트 배치 (PC는 가로, 모바일은 세로 자동 정렬)
    col1, col2 = st.columns(2)
    with col1:
        draw_chart(s_info['코드'], "3mo", "📅 최근 3개월 흐름")
    with col2:
        draw_chart(s_info['코드'], "5y", "🏛️ 5년 장기 성장")

    st.write("---")

    # 하단 정보 리포트
