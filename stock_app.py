import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl

# 1. 화면 설정 (사이드바 메뉴 상시 오픈)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. SSL 인증서 에러 방지 (로컬 실행 시 필수)
ssl._create_default_https_context = ssl._create_unverified_context

# 3. 메뉴 아이콘(>) 보호 및 불필요 요소 제거
st.markdown("""
    <style>
    footer {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}
    header[data-testid="stHeader"] { background-color: rgba(0,0,0,0); }
    [data-testid="stSidebar"] { min-width: 260px; }
    </style>
    """, unsafe_allow_html=True)

# 4. 데이터 로드 (에러 방지용 정밀 필터링)
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
        url = sheet_url.split("/edit")[0] + "/export?format=csv"
        df = pd.read_csv(url)
        return df.dropna(subset=['종목명'])
    except Exception as e:
        st.error(f"데이터를 가져오지 못했습니다: {e}")
        return None

df_sheet = load_data()

# 5. 차트 그리기 함수 (SyntaxError 완벽 수술)
def draw_chart(ticker, period, title):
    try:
        interval = "1wk" if period == "5y" else "1d"
        df = yf.download(ticker, period=period, interval=interval)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty:
            return st.warning(f"⚠️ {title}: 데이터 없음")

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

# 6. 메인 로직 (NameError 방지를 위해 모든 변수를 안전하게 정의)
if df_sheet is not None and not df_sheet.empty:
    # 사이드바 메뉴
    st.sidebar.markdown("## 🎯 분석 종목 리스트")
    stock_names = df_sheet['종목명'].unique().tolist()
    selected = st.sidebar.selectbox("종목을 고르세요 👇", stock_names)
    
    # 선택된 종목 정보
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
    
    # 메인 화면 구성
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
    st.error("구글 시트 데이터를 읽을 수 없습니다. 주소를 확인해주세요.")
