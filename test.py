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

# 2. [정밀 수술] 메뉴 버튼은 살리고 지저분한 로고만 제거하는 CSS
st.markdown("""
    <style>
    /* 하단 푸터와 우측 상단 메뉴만 제거 */
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
    /* 헤더는 숨기지 않고 배경만 투명하게 해서 '모바일 메뉴 버튼'만 남김 */
    header[data-testid="stHeader"] {
        background-color: rgba(0,0,0,0);
    }
    
    /* 사이드바 너비 고정 및 가독성 향상 */
    [data-testid="stSidebar"] { min-width: 260px; max-width: 260px; }
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

# 4. 차트 그리기 함수 (SyntaxError 모든 지점 완벽 수술)
def draw_chart(ticker, period, title):
    try:
        # try-except 구조 완성
        interval = "1wk" if period == "5y" else "1d"
        df = yf.download(ticker, period=period, interval=interval)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # 괄호 닫기 확인
        if df.empty:
            return st.write(f"⚠️ {title}: 데이터를 찾을 수 없습니다.")

        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name=title
        )])

        # 문자열 마감 완벽 체크
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
        return st.error(f"⚠️ {title}: 데이터 로드 실패")

# 5. 메인 로직 실행
if df_sheet is not None and not df_sheet.empty:
    # 사이드바 종목 선택
    st.sidebar.markdown("## 🎯 분석 종목 리스트")
    st.sidebar.write("---")
    
    stock_names = df_sheet['종목명'].unique().tolist()
    selected = st.sidebar.selectbox("종목을 고르세요 👇", stock_names)
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
    
    st.sidebar.write("---")
    st.sidebar.success(f"현재 분석 중: **{selected}**")

    # 메인 화면 구성
    st.title(f"🚀 {selected} ({s_info['코드'].upper()})")

    # 함수 호출 괄호 완벽 마감
    col1, col2 = st.columns(2)
    with col1:
        draw_chart(s_info['코드'], "3mo", "📅 최근 3개월 흐름")
    with col2:
        draw_chart(s_info['코드'], "5y", "🏛️ 5년 장기 성장")

    st.write("---")

    # 변수 정의를 로직 안으로 이동
    c_a, c_b = st.columns([1, 2])
    with c_a:
        st.metric("사장님 목표가", f"{s_info['적정가']}")
    with c_b:
        # 중괄호 마감 확인
        st.success(f"**💡 분석 메모:**\n\n{s_info['메모']}")
else:
    st.error("데이터 로딩 실패! 구글 시트 설정을 확인해주세요.")
