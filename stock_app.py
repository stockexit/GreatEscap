import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl

# 1. 화면 설정 (순정 상태 유지, 메뉴 상시 오픈)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. SSL 에러 방지 (로컬 실행 필수 설정)
ssl._create_default_https_context = ssl._create_unverified_context

# 3. 데이터 로딩 (구글 시트 연동)
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
        url = sheet_url.split("/edit")[0] + "/export?format=csv"
        df = pd.read_csv(url)
        return df.dropna(subset=['종목명'])
    except:
        return None

# 4. 차트 그리기 함수
def draw_chart(ticker, period, title):
    try:
        interval = "1wk" if period == "5y" else "1d"
        df = yf.download(ticker, period=period, interval=interval)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name=title
        )])
        fig.update_layout(
            title=dict(text=title, font=dict(size=18)),
            height=450, template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, b=10, t=50),
            yaxis_type="log" if period == "5y" else "linear"
        )
        return st.plotly_chart(fig, use_container_width=True)
    except:
        return st.write("차트 데이터를 불러오는 중...")

# 5. 메인 로직 실행
df_sheet = load_data()

if df_sheet is not None:
    # 사이드바: 종목 선택
    st.sidebar.markdown("## 🎯 분석 종목 리스트")
    selected = st.sidebar.selectbox("종목을 골라주세요 👇", df_sheet['종목명'].unique())
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
    
    # 실시간 데이터 가져오기 (주가 및 뉴스)
    try:
        ticker_obj = yf.Ticker(s_info['코드'])
        current_p = ticker_obj.history(period="1d")['Close'].iloc[-1]
        target_p = float(s_info['적정가'])
        gap_percent = ((target_p - current_p) / current_p) * 100
        news_list = ticker_obj.news[:5] # 최신 뉴스 5개 추출
    except:
        current_p, target_p, gap_percent, news_list = 0, 0, 0, []

    # 메인 화면 구성
    st.title(f"🚀 {selected} ({s_info['코드'].upper()})")
    
    # 지표 요약
    c1, c2, c3 = st.columns(3)
    c1.metric("실시간 현재가", f"${current_p:.2f}")
    c2.metric("사장님 목표가", f"${target_p:.2f}")
    c3.metric("목표 수익률", f"{gap_percent:.1f}%", delta=f"{gap_percent:.1f}%")

    st.write("---")

    # 차트 배치
    col1, col2 = st.columns(2)
    with col1:
        draw_chart(s_info['코드'], "3mo", "📅 최근 3개월 흐름")
    with col2:
        draw_chart(s_info['코드'], "5y", "🏛️ 5년 장기 성장")

    st.write("---")

    # 하단 레이아웃 (메모 + 실시간 뉴스)
    low_col1, low_col2 = st.columns([1, 1])
    
    with low_col1:
        st.subheader("💡 분석 메모")
        st.success(f"{s_info['메모']}")
        
    with low_col2:
        st.subheader("📰 실시간 최신 뉴스")
        if news_list:
            for news in news_list:
                st.markdown(f"**[{news['publisher']}]** [{news['title']}]({news['link']})")
        else:
            st.write("현재 관련 뉴스가 없습니다.")

else:
    st.error("데이터 로딩 실패! 구글 시트 연결을 확인하세요.")
