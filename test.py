import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 순정 화면 설정 (메뉴창을 처음부터 펼쳐서 고정)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. 불필요한 요소 제거 (헤더와 푸터만 살짝 숨김)
st.markdown("""
    <style>
    header {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
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

# 4. 왼쪽 메뉴 구성 (사이드바)
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.markdown("## 🎯 분석 종목 리스트")
    st.sidebar.write("---")
    
    stock_names = df_sheet['종목명'].unique().tolist()
    # 종목 선택창
    selected = st.sidebar.selectbox("종목을 고르세요 👇", stock_names)
    # 선택된 종목의 정보 추출
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
    
    st.sidebar.write("---")
    st.sidebar.success(f"현재 선택: **{selected}**")
    st.sidebar.info("💡 종목을 바꾸면 차트가 새로 고침됩니다.")
else:
    st.error("데이터 로딩 실패! 시트 주소나 공유 설정을 확인해주세요.")
    st.stop()

# 5. 차트 그리기 함수 (SyntaxError 완벽 방지 검수)
def draw_chart(ticker, period, title):
    # 로딩 중 메시지 표시
    with st.spinner(f'{title} 데이터를 가져오는 중...'):
        try:
            # 5년치는 주 단위, 3개월치는 일 단위
            interval = "1wk" if period == "5y" else "1d"
            df = yf.download(ticker, period=period, interval=interval)
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            if df.empty:
                return st.warning(f"⚠️ {title}: '{ticker}' 데이터를 찾을 수 없습니다.")

            fig = go.Figure(data=[go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], 
                low=df['Low'], close=df['Close'], name=title
            )])

            fig.update_layout(
                title=dict(text=title, font=dict(size=16)),
                height=500, 
                template="plotly_dark",
                xaxis_rangeslider_visible=False,
                margin=dict(l=10, r=10, b=10, t=50),
                yaxis_type="log" if period == "5y" else "linear"
            )
            return st.plotly_chart(fig, use_container_width=True)
        except:
            return st.error(f"⚠️ {title}: 금융 서버 연결 실패")

# 6. 메인 화면 구성
st.title(f"🚀 {selected} ({s_info['코드'].upper()})")

# 차트 2개 집중 배치
col1, col2 = st.columns(2)
with col1:
    draw_chart(s_info['코드'], "3mo", "📅 최근 3개월 흐름")
with col2:
    draw_chart(s_info
