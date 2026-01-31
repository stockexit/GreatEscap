import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl

# 1. 화면 설정 (한국 시장 우선, 메뉴 상시 오픈)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. SSL 에러 방지 (로컬 실행 시 필수)
ssl._create_default_https_context = ssl._create_unverified_context

# 3. 데이터 로딩 및 시장 자동 분류
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
        # 구글 시트 URL을 CSV 다운로드 링크로 변환
        url = sheet_url.split("/edit")[0] + "/export?format=csv"
        df = pd.read_csv(url)
        df = df.dropna(subset=['종목명'])
        
        # 코드 끝자리를 보고 한국/미국 시장 자동 분류
        df['Market'] = df['코드'].apply(
            lambda x: "한국(KRW)" if str(x).upper().endswith(('.KS', '.KQ')) else "미국(USD)"
        )
        return df
    except:
        return None

# 4. 차트 그리기 함수 (보수적 적정가 & 최대 미래가치 2줄 표시)
def draw_chart(ticker, period, title, unit, target_min=None, target_max=None):
    try:
        # 3개월은 일봉(1d), 5년은 주봉(1wk)으로 설정
        interval = "1d" if period == "3mo" else "1wk"
        df = yf.download(ticker, period=period, interval=interval)
        
        if df.empty:
            return st.write(f"{title} 데이터를 불러올 수 없습니다.")
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name=title
        )])
        
        # --- [1] 보수적 적정가 (초록색 방어선) ---
        if target_min and target_min > 0:
            fig.add_hline(y=target_min, line_dash="dot", line_color="#00C853", opacity=0.8)
            fig.add_annotation(
                x=df.index[-1], y=target_min,
                text=f"<b>🛡️ 보수 {unit}{target_min:,.0f}</b>", 
                showarrow=False, 
                yshift=-20, # 텍스트를 선 아래로 배치
                font=dict(color="white", size=13),
                bgcolor="#00C853", # 초록 배경
                bordercolor="white", borderwidth=1, opacity=0.9
            )

        # --- [2] 최대 미래가치 (빨간색 목표선) ---
        if target_max and target_max > 0:
            fig.add_hline(y=target_max, line_dash="dash", line_color="#FF3D00", opacity=0.8)
            fig.add_annotation(
                x=df.index[-1], y=target_max,
                text=f"<b>🚀 최대 {unit}{target_max:,.0f}</b>", 
                showarrow=False, 
                yshift=20, # 텍스트를 선 위로 배치
                font=dict(color="white", size=13),
                bgcolor="#FF3D00", # 빨강 배경
                bordercolor="white", borderwidth=1, opacity=0.9
            )
        
        fig.update_layout(
            title=dict(text=f"{title} ({unit})", font=dict(size=18)),
            height=450, template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, b=10, t=50)
        )
        return st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        return st.write(f"차트 로딩 중 에러: {e}")

# 5. 메인 로직 실행
df_sheet = load_data()

if df_sheet is not None:
    # 사이드바: 시장 및 종목 선택
    st.sidebar.markdown("## 🌍 시장 선택")
    market_choice = st.sidebar.radio("보고 싶은 시장", ["한국(KRW)", "미국(USD)"])
    
    filtered_df = df_sheet[df_sheet['Market'] == market_choice]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"## 🎯 {market_choice} 종목")
    
    # 종목 리스트가 비어있을 경우 대비
    if not filtered_df.empty:
        selected = st.sidebar.selectbox("종목 선택 👇", filtered_df['종목명'].unique())
        s_info = filtered_df[filtered_df['종목명'] == selected].iloc[0]
        
        # 기본 정보 설정
        ticker_code = s_info['코드'].upper()
        is_korea = market_choice == "한국(KRW)"
        unit = "₩" if is_korea else "$"
        p_format = "{:,.0f}" if is_korea else "{:,.2f}"
        
        # 현재가 및 목표가 데이터 처리
        try:
            ticker_obj = yf.Ticker(ticker_code)
            history = ticker_obj.history(period="1d")
            
            if not history.empty:
                current_p = history['Close'].iloc[-1]
            else:
                current_p = 0

            # 구글 시트 컬럼 읽기 (에러 방지용 .get 사용)
            t_min = float(s_info.get('보수적적정가', 0)) # 컬럼명 확인 필수
            t_max = float(s_info.get('최대미래가치', 0)) # 컬럼명 확인 필수
            
            # 수익률 계산 (현재가가 0이면 0 처리)
            if current_p > 0:
                gap_min = ((t_min - current_p) / current_p) * 100
                gap_max = ((t_max - current_p) / current_p) * 100
            else:
                gap_min, gap_max = 0, 0

        except Exception as e:
            current_p, t_min, t_max = 0, 0, 0
            gap_min, gap_max = 0, 0
            st.error(f"데이터 불러오기 오류: {e}")

        # --- 메인 화면 구성 ---
        st.title(f"🚀 {selected} ({ticker_code}) Analysis")
        
        # 3단 지표 (현재가 / 보수적 / 최대)
        c1, c2, c3 = st.columns(3)
        c1.metric("실시간 현재가", f"{unit}{p_format.format(current_p)}")
        c2.metric("🛡️ 보수적 적정가 (안전)", f"{unit}{p_format.format(t_min)}", f"{gap_min:.1f}%")
        c3.metric("🚀 최대 미래가치 (목표)", f"{unit}{p_format.format(t_max)}", f"{gap_max:.1f}%")

        st.write("---")

        # 차트 배치
        col1, col2 = st.columns(2)
        with col1:
            draw_chart(ticker_code, "3mo", "📅 최근 3개월 흐름", unit)
        with col2:
            # 5년 차트에만 min, max 선을 모두 전달
            draw_chart(ticker_code, "5y", "🏛️ 5년 장기 + 가치 평가", unit, t_min, t_max)

        st.write("---")
        
        # 메모 섹션
        st.subheader("💡 투자 포인트 및 메모")
        memo_content = s_info.get('메모', '작성된 메모가 없습니다.')
        if pd.isna(memo_content):
            memo_content = "작성된 메모가 없습니다."
        st.info(memo_content)
        
    else:
        st.warning("선택한 시장에 해당하는 종목이 구글 시트에 없습니다.")
else:
    st.error("데이터 로딩 실패! 구글 시트 연결을 확인하세요.")
