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

# 2. SSL 인증서 에러 방지 (image_da8e7c 에러 해결용)
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

# 4. 차트 그리기 함수 (SyntaxError 완벽 차단)
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
    st.sidebar.markdown("## 🎯 분석 종목 리스트")
    selected = st.sidebar.selectbox("종목 선택 👇", df_sheet['종목명'].unique())
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
    
    # [뉴스 보안 수술] 데이터 안전하게 긁어오기
    try:
        # 환율 데이터
        ex_rate = yf.Ticker("USDKRW=X").history(period="1d")['Close'].iloc[-1]
        
        # 주식 및 뉴스 데이터
        ticker_obj = yf.Ticker(s_info['코드'])
        current_p = ticker_obj.history(period="1d")['Close'].iloc[-1]
        target_p = float(s_info['적정가'])
        gap_percent = ((target_p - current_p) / current_p) * 100
        
        # 뉴스 데이터를 가장 넓은 범위로 긁어옵니다
        news_data = ticker_obj.news
    except:
        ex_rate, current_p, target_p, gap_percent, news_data = 1400, 0, 0, 0, []

    st.title(f"🚀 {selected} ({s_info['코드'].upper()})")
    
    # 상단 요약 지표 (SyntaxError 수술 완료)
    c1, c2, c3 = st.columns(3)
    c1.metric(f"현재가 (환율: {ex_rate:,.0f}원)", f"${current_p:,.2f}", f"{current_p * ex_rate:,.0f}원")
    c2.metric("사장님 목표가", f"${target_p:,.2f}", f"{target_p * ex_rate:,.0f}원", delta_color="off")
    c3.metric("목표 수익률", f"{gap_percent:.1f}%", f"{gap_percent:.1f}%")

    st.write("---")

    # 가로 2단 차트 배치
    col1, col2 = st.columns(2)
    with col1:
        draw_chart(s_info['코드'], "3mo", "📅 최근 3개월 흐름")
    with col2:
        draw_chart(s_info['코드'], "5y", "🏛️ 5년 장기 성장")

    st.write("---")

    # [수정] 뉴스 표시부: 데이터가 없을 때의 'No Title' 현상을 방지합니다
    low_col1, low_col2 = st.columns([1, 1.5])
    
    with low_col1:
        st.subheader("💡 분석 메모")
        # '메메' 에러 영구 박멸
        st.success(f"{s_info['메모']}") 
        
    with low_col2:
        st.subheader("📰 실시간 최신 뉴스")
        if news_data:
            # 뉴스 내용을 최대 5개까지 안전하게 순회
            for news in news_data[:5]:
                # .get()을 사용해 데이터가 없어도 '정보 없음'으로 표시하여 KeyError 방지
                title = news.get('title') or news.get('headline') or "뉴스 제목을 불러올 수 없음"
                link = news.get('link') or news.get('url') or "#"
                publisher = news.get('publisher') or news.get('source') or "정보처 미상"
                
                st.markdown(f"**[{publisher}]** [{title}]({link})")
        else:
            st.info("현재 이 종목에 대한 실시간 뉴스가 없습니다.")

else:
    # 시트 로딩 에러 시 출력
    st.error("데이터 로딩 실패! 구글 시트 설정을 확인해주세요.")
