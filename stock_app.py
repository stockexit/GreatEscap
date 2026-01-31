import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl

# 1. 화면 설정 (PC 접속 시 메뉴를 기본으로 펼쳐둡니다)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. SSL 인증서 에러 방지 (로컬 VS Code 실행 시 필수)
ssl._create_default_https_context = ssl._create_unverified_context

# 3. [핵심 수술] 메뉴 버튼(>)을 살리고 지저분한 요소만 제거하는 CSS
st.markdown("""
    <style>
    /* 하단 푸터와 툴바 제거 */
    footer {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}
    
    /* 헤더 영역을 투명하게 해서 모바일 메뉴 버튼 아이콘(>)이 보이게 함 */
    header[data-testid="stHeader"] {
        background-color: rgba(0,0,0,0) !important;
        visibility: visible !important;
    }
    
    /* 사이드바 너비 고정 및 가독성 향상 */
    [data-testid="stSidebar"] { min-width: 260px; max-width: 260px; }
    </style>
    """, unsafe_allow_html=True)

# 4. 데이터 로드 함수
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
        url = sheet_url.split("/edit")[0] + "/export?format=csv"
        df = pd.read_csv(url)
        return df.dropna(subset=['종목명'])
    except Exception as e:
        st.error(f"데이터 로딩 에러: {e}")
        return None

df_sheet = load_data()

# 5. 차트 그리기 함수 (SyntaxError 모든 지점 완벽 수술)
def draw_chart(ticker, period, title):
    try:
        interval = "1wk" if period == "5y" else "1d"
        df = yf.download(ticker, period=period, interval=interval)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty:
            return st.warning(f"⚠️ {title}: 데이터를 찾을 수 없습니다.")

        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name=title
        )])

        fig.update_layout(
            title=dict(text=title, font=dict(size=18)),
            height=500, template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, b=10, t=50),
            yaxis_type="log" if period == "5y" else "linear"
        )
        return st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        return st.error(f"차트 로드 실패: {e}")

# 6. 메인 화면 로직 (NameError 방지를 위해 변수 사용 순서 엄수)
if df_sheet is not None and not df_sheet.empty:
    # 사이드바: 종목 선택 메뉴
    st.sidebar.markdown("## 🎯 분석 종목 리스트")
    st.sidebar.write("---")
    
    stock_names = df_sheet['종목명'].unique().tolist()
    selected = st.sidebar.selectbox("종목을 고르세요 👇", stock_names)
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
    
    st.sidebar.write("---")
    st.sidebar.success(f"현재 분석: **{selected}**")

    # 메인 화면: 제목 및 차트
    st.title(f"🚀 {selected} ({s_info['코드'].upper()})")

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
    st.error("구글 시트 데이터를 읽을 수 없습니다.")
