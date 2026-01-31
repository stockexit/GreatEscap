import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정
st.set_page_config(page_title="사장님 실시간 리서치 센터", layout="wide")

# 2. 구글 시트 연결 (사장님 시트 주소를 여기에 넣으세요!)
# 주소 뒤에 /export?format=csv 를 붙여야 파이썬이 읽을 수 있습니다.
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing" # <--- 이 부분 수정!
url = sheet_url.split("/edit")[0] + "/export?format=csv"

# 데이터 불러오기 함수
@st.cache_data(ttl=60) # 1분마다 새로운 데이터를 확인합니다
def load_data(url):
    try:
        df = pd.read_csv(url)
        return df
    except:
        return None

df_sheet = load_data(url)

# 3. 사이드바 구성
st.sidebar.header("🎯 분석 종목 리스트")

if df_sheet is not None and not df_sheet.empty:
    # 시트의 '종목명' 열을 리스트로 가져옴
    selected_name = st.sidebar.selectbox("종목을 고르세요", df_sheet['종목명'].tolist())
    # 선택된 종목의 정보 추출
    stock_info = df_sheet[df_sheet['종목명'] == selected_name].iloc[0]
else:
    st.error("구글 시트 데이터를 가져올 수 없습니다. 공유 설정을 확인해주세요!")
    st.stop()

# 4. 차트 생성 함수
def draw_chart(ticker, period, title):
    interval = "1wk" if period == "max" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    fig.update_layout(title=title, height=350, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# 5. 메인 화면 출력
st.title(f"🚀 {selected_name} ({stock_info['코드']}) 실시간 분석")

col1, col2 = st.columns(2)
with col1: draw_chart(stock_info['코드'], "1mo", "📅 단기 흐름")
with col2: draw_chart(stock_info['코드'], "3mo", "📅 분기 흐름")

col3, col4 = st.columns(2)
with col3: draw_chart(stock_info['코드'], "1y", "📅 중기 흐름")
with col4: draw_chart(stock_info['코드'], "max", "🏛️ 전체 역사")

st.write("---")
# 6. 하단 리포트 (시트에 적은 내용이 실시간으로 뜹니다)
st.subheader(f"📑 {selected_name} 가치평가 리포트")
info_c1, info_c2 = st.columns([1, 3])
info_c1.metric("목표 적정가", stock_info['적정가'])
info_c2.success(f"**💡 사장님 분석 의견:**\n\n{stock_info['메모']}")
