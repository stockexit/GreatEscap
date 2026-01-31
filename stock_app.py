import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl

# 1. 화면 설정 (순정 상태에서 메뉴를 처음부터 열어둡니다)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. SSL 인증서 에러 방지 (로컬 실행 시 필수)
ssl._create_default_https_context = ssl._create_unverified_context

# 3. [완전 순정] 가리기 CSS를 모두 삭제했습니다. 
# 이제 로고는 보이겠지만, 메뉴 버튼이 절대 사라지지 않습니다!

# 4. 데이터 로드 함수 (SyntaxError 박멸 수술 완료)
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
        url = sheet_url.split("/edit")[0] + "/export?format=csv"
        df = pd.read_csv(url)
        # 종목명이 있는 행만 깨끗하게 가져오기
        return df.dropna(subset=['종목명'])
    except Exception as e:
        st.error(f"데이터 로딩 에러: {e}")
        return None

df_sheet = load_data()

# 5. 차트 그리기 함수 (괄호 및 명칭 에러 수술 완료)
def draw_chart(ticker, period, title):
    try:
        # 3개월은 일봉, 5년은 주봉 설정
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
            height=500, 
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, b=10, t=50),
            yaxis_type="log" if period == "5y" else "linear"
        )
        return st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        return st.error(f"차트 로드 실패: {e}")

# 6. 메인 로직 실행 (NameError 방지를 위해 출력 순서 엄수)
if df_sheet is not None and not df_sheet.empty:
    # 사이드바: 종목 선택 메뉴
    st.sidebar.markdown("## 🎯 분석 종목 리스트")
    st.sidebar.write("---")
    
    stock_names = df_sheet['종목명'].unique().tolist()
    selected = st.sidebar.selectbox("종목을 고르세요 👇", stock_names)
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
    
    st.sidebar.write("---")
    st.sidebar.success(f"현재 분석: **{selected}**")

    # 메인 화면 구성
    st.title(f"🚀 {selected} ({s_info['코드'].upper()})")

    # 가로 2단 차트 배치 (PC 가로, 모바일 세로 자동 전환)
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
    st.error("데이터 로딩 실패! 시트 설정을 확인해주세요.")
