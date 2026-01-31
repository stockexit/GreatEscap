import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 화면 설정 (사이드바를 처음부터 펼쳐두도록 설정)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. [완전 순정] 메뉴 버튼을 가리는 모든 코드를 삭제했습니다.
st.markdown("""
    <style>
    footer {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}
    /* 모바일에서 사이드바가 열려있다는 걸 알 수 있도록 강조 */
    [data-testid="stSidebar"] { border-right: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결 (사장님의 시트 데이터 주소)
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

# 4. 차트 그리기 함수 (문법 오류 완벽 수정)
def draw_chart(ticker, period, title):
    try:
        # 3개월은 일봉, 5년은 주봉으로 설정
        interval = "1wk" if period == "5y" else "1d"
        df = yf.download(ticker, period=period, interval=interval)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty:
            return st.warning(f"{title}: 데이터를 가져올 수 없습니다.")

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
    except Exception as e:
        return st.error(f"차트 로드 실패: {e}")

# 5. 메인 로직 (변수가 섞이지 않도록 한 블록 안에 묶음)
if df_sheet is not None and not df_sheet.empty:
    # 왼쪽 사이드바: 종목 리스트 출력
    st.sidebar.markdown("## 🎯 분석 종목 리스트")
    st.sidebar.write("---")
    
    stock_names = df_sheet['종목명'].unique().tolist()
    # 여기서 종목을 선택하면 아래 차트가 바뀝니다.
    selected = st.sidebar.selectbox("종목을 고르세요 👇", stock_names)
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
    
    st.sidebar.write("---")
    st.sidebar.info("💡 모바일은 왼쪽 상단의 '>' 버튼을 누르면 이 리스트가 나옵니다!")

    # 메인 화면: 제목 및 차트 배치
    st.title(f"🚀 {selected} ({s_info['코드'].upper()})")

    col1, col2 = st.columns(2)
    with col1:
        draw_chart(s_info['코드'], "3mo", "📅 최근 3개월 흐름")
    with col2:
        draw_chart(s_info['코드'], "5y", "🏛️ 5년 장기 성장")

    st.write("---")

    # 하단: 사장님 투자 메모
    c_a, c_b = st.columns([1, 2])
    with c_a:
        st.metric("사장님 목표가", f"{s_info['적정가']}")
    with c_b:
        st.success(f"**💡 분석 메모:**\n\n{s_info['메모']}")
else:
    st.error("데이터 로딩 실패! 구글 시트 주소나 공유 설정을 확인해주세요.")
