import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 순정 화면 설정 (initial_sidebar_state="expanded"로 메뉴 강제 고정)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded"  # 바로 이 부분입니다!
)

# 2. 구글 시트 데이터 로드
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

# 3. 종목 선택 (왼쪽 사이드바 메뉴)
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.title("🎯 분석 종목 리스트")
    # 구글 시트에 있는 테슬라, 삼성전자, 애플이 여기 뜹니다
    stock_names = df_sheet['종목명'].unique().tolist()
    
    # 선택창
    selected = st.sidebar.selectbox("종목을 고르세요 👇", stock_names)
    s_info = df_sheet[df_sheet['종목명'] == selected].iloc[0]
    
    st.sidebar.write("---")
    st.sidebar.success(f"현재 분석 중: **{selected}**")
else:
    st.error("데이터 로딩 실패")
    st.stop()

# 4. 차트 그리기 함수 (SyntaxError 방지 완벽 검수)
def draw_chart(ticker, period, title):
    try:
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
            title=dict(text=title, font=dict(size=16)),
            height=500, 
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, b=10, t=50),
            yaxis_type="log" if period == "5y" else "linear"
        )
        return st.plotly_chart(fig, use_container_width=True)
    except:
        return st.write(f"⚠️ {title}: 로딩 에러")

#
