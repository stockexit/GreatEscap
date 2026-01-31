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

# 3. 데이터 로딩 및 시장 분류
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
        url = sheet_url.split("/edit")[0] + "/export?format=csv"
        df = pd.read_csv(url)
        df = df.dropna(subset=['종목명'])
        
        # 한국/미국 시장 자동 분류 로직
        df['Market'] = df['코드'].apply(
            lambda x: "한국(KRW)" if str(x).upper().endswith(('.KS', '.KQ')) else "미국(USD)"
        )
        return df
    except:
        return None

# 4. 차트 그리기 함수 (목표가 라인 추가 & 기간 버그 수정)
def draw_chart(ticker, period, title, unit, target_p):
    try:
        # [수정] 3개월은 일봉('1d'), 5년은 주봉('1wk')으로 설정해 차트가 겹치지 않게 합니다
        interval = "1d" if period == "3mo" else "1wk"
        df = yf.download(ticker, period=period, interval=interval)
        
        if df.empty:
            return st.write(f"{title} 데이터를 찾을 수 없습니다.")
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name=title
        )])
        
        # [핵심] 차트 위에 목표가 수평선 긋기
        fig.add_hline(
            y=target_p, 
            line_dash="dash", 
            line_color="red", 
            annotation_text=f"사장님 목표가 ({unit}{target_p:,.0f})",
            annotation_position="top right"
        )
        
        fig.update_layout(
            title=dict(text=f"{title} ({unit})", font=dict(size=18)),
            height=450, template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, b=10, t=50),
            yaxis_type="log" if period == "5y" else "linear"
        )
        return st.plotly_chart(fig, use_container_width=True)
    except:
        return st.write("차트 로딩 중...")

# 5. 메인 로직 실행
df_sheet = load_data()

if df_sheet is not None:
    # 사이드바: 한국 시장을 첫 번째로
    st.sidebar.markdown("## 🌍 시장 선택")
    market_choice = st.sidebar.radio("보고 싶은 시장을 골라주세요", ["한국(KRW)", "미국(USD)"])
    
    filtered_df = df_sheet[df_sheet['Market'] == market_choice]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"## 🎯 {market_choice} 종목")
    selected = st.sidebar.selectbox("종목 선택 👇", filtered_df['종목명'].unique())
    s_info = filtered_df[filtered_df['종목명'] == selected].iloc[0]
    
    # 통화 단위 및 숫자 포맷 설정
    ticker_code = s_info['코드'].upper()
    is_korea = market_choice == "한국(KRW)"
    unit = "₩" if is_korea else "$"
    fmt = ",.0f" if is_korea else ",.2f"
    
    try:
        ticker_obj = yf.Ticker(ticker_code)
        current_p = ticker_obj.history(period="1d")['Close'].iloc[-1]
        target_p = float(s_info['적정가'])
        gap_percent = ((target_p - current_p) / current_p) * 100
    except:
        current_p, target_p, gap_percent = 0, 0, 0

    st.title(f"🚀 {selected} ({ticker_code})")
    
    # 상단 요약 지표 (f-string 오타 수술 완료)
    c1, c2, c3 = st.columns(3)
    c1.metric("실시간 현재가", f"{unit}{current_p:{fmt}}")
    c2.metric("사장님 목표가", f"{unit}{target_p:{fmt}}", delta_color="off")
    c3.metric("목표까지 수익률", f"{gap_percent:.1f}%", f"{gap_percent:.1f}%")

    st.write("---")

    # 차트 배치 (목표가 라인 포함)
    col1, col2 = st.columns(2)
    with col1:
        draw_chart(ticker_code, "3mo", "📅 최근 3개월 흐름", unit, target_p)
    with col2:
        draw_chart(ticker_code, "5y", "🏛️ 5년 장기 성장", unit, target_p)

    st.write("---")
    # 하단 분석 메모 ('메메' KeyError 영구 박멸)
    st.subheader("💡 분석 메모")
    st.success(f"{s_info['메모']}") 
else:
    st.error("데이터 로딩 실패! 구글 시트 연결을 확인하세요.")
