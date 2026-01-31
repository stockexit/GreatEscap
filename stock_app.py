import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl

# 1. 화면 설정 (메뉴 상시 오픈)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. SSL 에러 방지 (로컬 실행 필수)
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

# 4. 차트 그리기 함수 (통화별 기호 자동 설정)
def draw_chart(ticker, period, title, unit):
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
            title=dict(text=f"{title} ({unit})", font=dict(size=18)),
            height=450, template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, b=10, t=50),
            yaxis_type="log" if period == "5y" else "linear"
        )
        return st.plotly_chart(fig, use_container_width=True)
    except:
        return st.write("차트 생성 중...")

# 5. 메인 로직 실행
df_sheet = load_data()

if df_sheet is not None:
    # 사이드바: 종목 선택
    st.sidebar.markdown("## 🎯 분석 종목 리스트")
    selected = st.sidebar.selectbox("종목 선택 👇", df_sheet['종목명'].unique())
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
    
    # [핵심] 통화 구분 로직
    ticker_code = s_info['코드'].upper()
    is_korea = ticker_code.endswith('.KS') or ticker_code.endswith('.KQ')
    unit = "₩" if is_korea else "$"
    
    # 데이터 가져오기
    try:
        ticker_obj = yf.Ticker(ticker_code)
        current_p = ticker_obj.history(period="1d")['Close'].iloc[-1]
        target_p = float(s_info['적정가'])
        gap_percent = ((target_p - current_p) / current_p) * 100
    except:
        current_p, target_p, gap_percent = 0, 0, 0

    st.title(f"🚀 {selected} ({ticker_code})")
    
    # 상단 요약 지표 (통화 기호 자동 적용)
    c1, c2, c3 = st.columns(3)
    
    # 원화일 때는 소수점 없이(,:0f), 달러일 때는 소수점 2자리(,:2f)로 표시
    format_str = ":,.0f" if is_korea else ":,.2f"
    
    c1.metric("실시간 현재가", f"{unit}{current_p{format_str}}")
    c2.metric("사장님 목표가", f"{unit}{target_p{format_str}}", delta_color="off")
    c3.metric("목표까지 수익률", f"{gap_percent:.1f}%", f"{gap_percent:.1f}%")

    st.write("---")

    # 차트 배치
    col1, col2 = st.columns(2)
    with col1:
        draw_chart(ticker_code, "3mo", "📅 최근 3개월 흐름", unit)
    with col2:
        draw_chart(ticker_code, "5y", "🏛️ 5년 장기 성장", unit)

    st.write("---")

    # 하단 분석 메모
    st.subheader("💡 분석 메모")
    st.success(f"{s_info['메모']}") 

else:
    st.error("데이터 로딩 실패! 구글 시트 연결을 확인하세요.")
