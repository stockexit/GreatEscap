import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 순정 화면 설정 (CSS 가리기 코드 완전 삭제)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide"
)

# 2. 구글 시트 데이터 로드
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

@st.cache_data(ttl=60)
def load_data(csv_url):
    try:
        df = pd.read_csv(csv_url)
        # 종목명이 있는 데이터만 깨끗하게 필터링
        return df.dropna(subset=['종목명'])
    except:
        return None

df_sheet = load_data(url)

# 3. 종목 선택 (사이드바 메뉴 부활)
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.title("🎯 분석 종목")
    stock_names = df_sheet['종목명'].unique().tolist()
    # 사이드바에서 종목을 선택하면 아래 화면이 즉시 바뀝니다
    selected = st.sidebar.selectbox("종목을 고르세요", stock_names)
    # 선택된 종목의 행 정보를 가져옵니다
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
else:
    st.error("구글 시트를 읽지 못했습니다. 공유 설정을 확인해주세요!")
    st.stop()

# 4. 차트 그리기 함수 (SyntaxError 방지 완벽 검수)
def draw_chart(ticker, period, title):
    try:
        # 3개월은 일간(1d), 5년은 주간(1wk) 데이터
        interval = "1wk" if period == "5y" else "1d"
        df = yf.download(ticker, period=period, interval=interval)
        
        # 멀티인덱스 컬럼 처리
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty:
            return st.warning(f"⚠️ {title}: 데이터 없음")

        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name=title
        )])

        fig.update_layout(
            title=title,
            height=500, # 순정 모드에서는 차트를 큼직하게 띄웁니다
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, b=10, t=50),
            yaxis_type="log" if period == "5y" else "linear"
        )
        return st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        return st.error(f"차트 에러: {e}")

# 5. 메인 화면 구성
st.title(f"🚀 {selected} ({s_info['코드'].upper()})")

# 차트 2개 배치 (PC는 2열, 모바일은 자동 1열로 변환되어 안 밀립니다)
col1, col2 = st.columns(2)
with col1:
    draw_chart(s_info['코드'], "3mo", "📅 최근 3개월 흐름")
with col2:
    draw_chart(s_info['코드'], "5y", "🏛️ 5년 장기 성장
