import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 화면 설정 (순정 와이드 모드)
st.set_page_config(page_title="사장님 투자 터미널", layout="wide")

# 2. 불필요한 요소 제거 (깔끔한 순정 스타일)
st.markdown("""
    <style>
    header {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    /* 모바일 여백 최적화 */
    .main .block-container { padding-top: 1rem !important; }
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

# 4. 메인 화면 상단: 종목 선택창 (이제 메뉴가 안 숨습니다!)
if df_sheet is not None and not df_sheet.empty:
    stock_names = df_sheet['종목명'].unique().tolist()
    
    # [핵심] 사이드바가 아닌 '메인 화면' 맨 위에 선택창 배치
    selected = st.selectbox("🎯 분석할 종목을 선택하세요", stock_names)
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
else:
    st.error("데이터 로딩 실패! 시트 설정을 확인해주세요.")
    st.stop()

# 5. 차트 그리기 함수 (SyntaxError 완벽 방지 검수 완료)
def draw_chart(ticker, period, title):
    try:
        # 3개월(일봉), 5년(주봉/로그차트)
        interval = "1wk" if period == "5y" else "1d" #
        df = yf.download(ticker, period=period, interval=interval)
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty:
            return st.write(f"{title}: 데이터 없음") #

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
            yaxis_type="log" if period == "5y" else "linear",
            xaxis=dict(fixedrange=True), #
            yaxis=dict(fixedrange=True)
        )
        return st.plotly_chart(fig, use_container_width=True)
    except:
        return st.write(f"⚠️ {title}: 데이터 로딩 중...")

# 6. 메인 화면 구성
st.title(f"🚀 {selected} ({s_info['코드'].upper()})")

# 차트 2개 배치 (PC는 가로, 모바일은 세로 자동 정렬)
col1, col2 = st.columns(2)
with col1:
    draw_chart(s_info['코드'], "3mo", "📅 최근 3개월 흐름") #
with col2:
    draw_chart(s_info['코드'], "5y", "🏛️ 5년 장기 성장") #

st.write("---")

# 7. 하단 리포트
c_a, c_b = st.columns([1, 2])
with c_a:
    st.metric("사장님 목표가", f"{s_info['적정가']}")
with c_b:
    st.success(f"**💡 분석 메모:**\n\n{s_info['메모']}") #
