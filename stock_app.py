import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl

# 1. 화면 설정 (와이드 모드)
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. SSL 에러 방지
ssl._create_default_https_context = ssl._create_unverified_context

# --------------------------------------------------------------------
# 📌 [수정됨] CSS 스타일: 제목과 숫자를 아주 크게 확대
# --------------------------------------------------------------------
st.markdown("""
    <style>
    /* 1. 메트릭 라벨 (제목: 실시간 현재가 등) */
    [data-testid="stMetricLabel"] {
        font-size: 30px !important;      /* 글씨 크기 대폭 확대 */
        font-weight: 900 !important;     /* 아주 굵게 */
        color: #ffffff !important;       /* 완전 흰색으로 잘 보이게 */
        margin-bottom: 10px !important;  /* 숫자와의 간격 벌리기 */
    }
    
    /* 2. 메트릭 값 (숫자: 가격) */
    [data-testid="stMetricValue"] {
        font-size: 55px !important;      /* 숫자도 비율에 맞춰 초대형으로 */
        font-weight: 700 !important;
        padding-top: 5px !important;
    }
    
    /* 3. 메트릭 델타 (퍼센트) */
    [data-testid="stMetricDelta"] {
        font-size: 22px !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)
# --------------------------------------------------------------------

# 3. 데이터 로딩
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
        url = sheet_url.split("/edit")[0] + "/export?format=csv"
        df = pd.read_csv(url)
        df = df.dropna(subset=['종목명'])
        
        df['Market'] = df['코드'].apply(
            lambda x: "한국(KRW)" if str(x).upper().endswith(('.KS', '.KQ')) else "미국(USD)"
        )
        return df
    except:
        return None

# 4. 차트 그리기 함수 (고정형 + 2줄 표시)
def draw_chart(ticker, period, title, unit, target_min=None, target_max=None):
    try:
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
        
        # [1] 보수적 적정가
        if target_min and target_min > 0:
            fig.add_hline(y=target_min, line_dash="dot", line_color="#00C853", opacity=0.8)
            fig.add_annotation(
                x=df.index[-1], y=target_min,
                text=f"<b>🛡️ 보수 {unit}{target_min:,.0f}</b>", 
                showarrow=False, yshift=-20,
                font=dict(color="white", size=13),
                bgcolor="#00C853", bordercolor="white", borderwidth=1, opacity=0.9
            )

        # [2] 최대 미래가치
        if target_max and target_max > 0:
            fig.add_hline(y=target_max, line_dash="dash", line_color="#FF3D00", opacity=0.8)
            fig.add_annotation(
                x=df.index[-1], y=target_max,
                text=f"<b>🚀 최대 {unit}{target_max:,.0f}</b>", 
                showarrow=False, yshift=20,
                font=dict(color="white", size=13),
                bgcolor="#FF3D00", bordercolor="white", borderwidth=1, opacity=0.9
            )
        
        # 차트 고정
        fig.update_layout(
            title=dict(text=f"{title} ({unit})", font=dict(size=18)),
            height=450, template="plotly_dark",
            margin=dict(l=10, r=10, b=10, t=50),
            xaxis_rangeslider_visible=False,
            xaxis=dict(fixedrange=True),
            yaxis=dict(fixedrange=True)
        )
        
        config = {'displayModeBar': False, 'scrollZoom': False}
        return st.plotly_chart(fig, use_container_width=True, config=config)

    except Exception as e:
        return st.write(f"차트 로딩 중 에러: {e}")

# 5. 메인 로직
df_sheet = load_data()

if df_sheet is not None:
    st.sidebar.markdown("## 🌍 시장 선택")
    market_choice = st.sidebar.radio("보고 싶은 시장", ["한국(KRW)", "미국(USD)"])
    filtered_df = df_sheet[df_sheet['Market'] == market_choice]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"## 🎯 {market_choice} 종목")
    
    if not filtered_df.empty:
        selected = st.sidebar.selectbox("종목 선택 👇", filtered_df['종목명'].unique())
        s_info = filtered_df[filtered_df['종목명'] == selected].iloc[0]
        
        ticker_code = s_info['코드'].upper()
        is_korea = market_choice == "한국(KRW)"
        unit = "₩" if is_korea else "$"
        p_format = "{:,.0f}" if is_korea else "{:,.2f}"
        
        try:
            ticker_obj = yf.Ticker(ticker_code)
            history = ticker_obj.history(period="1d")
            current_p = history['Close'].iloc[-1] if not history.empty else 0
            
            t_min = float(s_info.get('보수적적정가', 0))
            t_max = float(s_info.get('최대미래가치', 0)) 
            
            if current_p > 0:
                gap_min = ((t_min - current_p) / current_p) * 100
                gap_max = ((t_max - current_p) / current_p) * 100
            else:
                gap_min, gap_max = 0, 0

        except Exception as e:
            current_p, t_min, t_max = 0, 0, 0
            gap_min, gap_max = 0, 0

        st.title(f"🚀 {selected} ({ticker_code}) Analysis")
        
        # 상단 지표
        c1, c2, c3 = st.columns(3)
        c1.metric("실시간 현재가", f"{unit}{p_format.format(current_p)}")
        c2.metric("🛡️ 보수적 적정가", f"{unit}{p_format.format(t_min)}", f"{gap_min:.1f}%")
        c3.metric("🚀 최대 미래가치", f"{unit}{p_format.format(t_max)}", f"{gap_max:.1f}%")

        st.write("---")

        col1, col2 = st.columns(2)
        with col1:
            draw_chart(ticker_code, "3mo", "📅 최근 3개월 흐름", unit)
        with col2:
            draw_chart(ticker_code, "5y", "🏛️ 5년 장기 + 가치 평가", unit, t_min, t_max)

        st.write("---")
        
        st.subheader("💡 투자 포인트 및 메모")
        memo_content = s_info.get('메모', '작성된 메모가 없습니다.')
        if pd.isna(memo_content):
            memo_content = "작성된 메모가 없습니다."
        st.info(memo_content)
        
    else:
        st.warning("선택한 시장에 해당하는 종목이 구글 시트에 없습니다.")
else:
    st.error("데이터 로딩 실패! 구글 시트 연결을 확인하세요.")
