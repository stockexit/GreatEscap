import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 1. 화면 설정
st.set_page_config(
    page_title="사장님 전용 금융 터미널", 
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={'Get Help': None, 'Report a bug': None, 'About': None}
)

# 2. [초강력 CSS] 모바일에서도 강제로 2x2 격자를 만드는 마법의 명령어
# 스트림릿의 기본 '줄 세우기' 기능을 원천 차단합니다.
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stToolbar"] {visibility: hidden !important;}

    /* 모바일 화면(폭 768px 이하)에서도 가로로 2개씩 강제 배치 */
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important; /* 아래로 떨어지지 않게 막음 */
            gap: 5px !important;
        }
        [data-testid="column"] {
            width: 50% !important;
            flex: 1 1 50% !important;
            min-width: 50% !important;
        }
        .stPlotlyChart { height: 250px !important; } /* 모바일 차트 높이 최적화 */
    }
    
    .block-container {padding: 0.5rem !important;}
    </style>
    """, unsafe_allow_html=True)

# 3. 구글 시트 연결 (사장님 시트 주소 자동 적용)
sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
url = sheet_url.split("/edit")[0] + "/export?format=csv"

@st.cache_data(ttl=60)
def load_data(csv_url):
    try:
        df = pd.read_csv(csv_url)
        return df
    except:
        return None

df_sheet = load_data(url)

# 4. 종목 선택 로직
if df_sheet is not None and not df_sheet.empty:
    st.sidebar.markdown("### 🎯 분석 종목")
    stock_list = df_sheet['종목명'].dropna().unique().tolist()
    selected_name = st.sidebar.selectbox("종목 선택", stock_list)
    # 선택된 종목의 데이터 한 줄 가져오기
    stock_info = df_sheet[df_sheet['종목명'] == selected_name].iloc[0]
else:
    st.error("구글 시트 로딩 실패! 공유 설정을 확인해주세요.")
    st.stop()

# 5. 차트 생성 함수 (괄호 및 오타 꼼꼼히 체크 완료)
def draw_chart(ticker, period, title):
    interval = "1wk" if period == "max" else "1d"
    df = yf.download(ticker, period=period, interval=interval)
    
    if isinstance(df.columns, pd.
