import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정
st.set_page_config(page_title="사장님 투자 터미널", layout="wide")

# 2. 지저분한 UI 제거 및 사이드바 강조
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    /* 모바일에서 사이드바가 보인다는 걸 알려주는 화살표 강조 */
    [data-testid="stSidebarNav"] {background-color: #111;}
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

# 1분마다 새 데이터를 확인 (ttl=60)
@st.cache_data(ttl=60)
def load_data(csv_url):
    try:
        return pd.read_csv(csv_url)
    except:
        return None

df_sheet = load_data(url)

# 4. 왼쪽 사이드바: 종목 선택 메뉴
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.title("🎯 분석 종목 리스트")
    
    # 시트의 '종목명' 열에서 모든 이름을 가져와 리스트로 만듭니다.
    all_stocks = df_sheet['종목명'].dropna().unique().tolist()
    
    # [핵심] 여기서 종목을 선택하면 아래 화면이 해당 종목으로 바뀝니다.
    selected_name = st.sidebar.selectbox("종목을 고르세요 👇", all_stocks)
    
    # 선택된 종목의 데이터만 추출
    stock_info = df_sheet[df_sheet['종목명'] == selected_name].iloc[0]
    
    st.sidebar.write("---")
    st.sidebar.info("💡 모바일은 왼쪽 상단 '>' 버튼을 누르면 이 메뉴가 나옵니다!")
else:
    st.error("시트 데이터를 읽을 수 없습니다.")
    st.stop()

# 5. 차트 그리기 함수
def draw_chart(ticker, period, title):
    interval = "1wk" if period == "5y" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    if df.empty:
        return st.write(f"⚠️ {title}: '{ticker}' 코드를 확인해주세요.")

    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], 
        low=df['Low'], close=df['Close'], name=title
    )])

    fig.update_layout(
        title=title, height=450, template="plotly_dark",
        xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, b=10, t=50),
        yaxis_type="log" if period == "5y" else "linear"
    )
    return st.plotly_chart(fig, use_container_width=True)

# 6. 메인 화면 출력
st.title(f"🚀 {selected_name} ({stock_info['코드'].upper()})")

col1, col2 = st.columns(2)
with col1:
    draw_chart(stock_info['코드'], "3mo", "📅 최근 3개월 흐름")
with col2:
    draw_chart(stock_info['코드'], "5y", "🏛️ 5년 장기 성장")

st.write("---")

# 7. 하단 사장님 리포트
c1, c2 = st.columns([1, 2])
with c1:
    st.metric("사장님 목표가", f"{stock_info['적정가']}")
with c2:
    st.success(f"**💡 분석 메모:**\n\n{stock_info['메모']}")
