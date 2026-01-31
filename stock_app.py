import streamlit as st
import streamlit.components.v1 as components 
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl

# 1. 화면 설정
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 2. SSL 에러 방지
ssl._create_default_https_context = ssl._create_unverified_context

# 3. 데이터 로딩
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
        url = sheet_url.split("/edit")[0] + "/export?format=csv"
        df = pd.read_csv(url)
        df = df.dropna(subset=['종목명'])
        df['Market'] = df['코드'].apply(lambda x: "한국(KRW)" if str(x).upper().endswith(('.KS', '.KQ')) else "미국(USD)")
        return df
    except:
        return None

# 4. 차트 그리기 함수
def draw_chart(ticker, period, title, unit, target_min=None, target_max=None, target_buy=None, current_price=None):
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
        
        # --- [수정됨] 현재가 라인 (3개월 차트용) ---
        # 중앙 정렬 + 글씨 키움 + 한글로 변경
        if current_price and current_price > 0:
            fig.add_hline(y=current_price, line_dash="dot", line_color="#FF4081", line_width=1)
            fig.add_annotation(
                xref="paper", 
                x=0.5,               # [변경] 화면 중앙
                y=current_price, 
                text=f"<b>현재가 {unit}{current_price:,.0f}</b>", # [변경] 텍스트 수정
                showarrow=False, 
                xanchor="center",    # [변경] 가운데 정렬
                yshift=10,           # 선 바로 위에 배치
                font=dict(color="#FF4081", size=16), # [변경] 글씨 크기 확대 (16px)
                bgcolor="rgba(0,0,0,0.7)" # 배경을 조금 더 진하게 해서 글씨 잘 보이게
            )

        # --- 가치 평가 라인들 (5년 차트용) ---
        if target_buy and target_buy > 0:
            fig.add_hline(y=target_buy, line_width=2, line_color="#FFFFFF", opacity=1.0)
            fig.add_annotation(xref="paper", x=0.5, y=target_buy, text=f"<b>⚡ 매수 {unit}{target_buy:,.0f}</b>", showarrow=False, yshift=0, xanchor="center", font=dict(color="black", size=16), bgcolor="#FFFFFF", bordercolor="gray", borderwidth=1, opacity=0.9)

        if target_min and target_min > 0:
            fig.add_hline(y=target_min, line_dash="dot", line_color="#00C853", opacity=0.8)
            fig.add_annotation(xref="paper", x=0.5, y=target_min, text=f"<b>🛡️ 보수 {unit}{target_min:,.0f}</b>", showarrow=False, yshift=-25, xanchor="center", font=dict(color="white", size=16), bgcolor="#00C853", bordercolor="white", borderwidth=1, opacity=0.9)

        if target_max and target_max > 0:
            fig.add_hline(y=target_max, line_dash="dash", line_color="#FF3D00", opacity=0.8)
            fig.add_annotation(xref="paper", x=0.5, y=target_max, text=f"<b>🚀 최대 {unit}{target_max:,.0f}</b>", showarrow=False, yshift=25, xanchor="center", font=dict(color="white", size=16), bgcolor="#FF3D00", bordercolor="white", borderwidth=1, opacity=0.9)
        
        fig.update_layout(
            title=dict(text=f"{title} ({unit})", font=dict(size=20)), 
            height=450, template="plotly_dark", margin=dict(l=10, r=10, b=10, t=50),
            xaxis_rangeslider_visible=False,
            xaxis=dict(fixedrange=True, tickfont=dict(size=12)), 
            yaxis=dict(fixedrange=True, tickfont=dict(size=14))
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
        
        # 등급 설정
        grade = s_info.get('투자등급', '미분류') 
        if grade == "코어":
            badge_color = "#2962FF"; badge_icon = "💎"; badge_text = "CORE"
        elif grade == "위성":
            badge_color = "#FFAB00"; badge_icon = "🛰️"; badge_text = "SATELLITE"
        elif grade == "시가존":
            badge_color = "#2E7D32"; badge_icon = "🚬"; badge_text = "시가존"
        else:
            badge_color = "#616161"; badge_icon = "❔"; badge_text = "미지정"

        # 가격 데이터 처리
        try:
            ticker_obj = yf.Ticker(ticker_code)
            history = ticker_obj.history(period="1d")
            current_p = history['Close'].iloc[-1] if not history.empty else 0
            t_min = float(s_info.get('보수적적정가', 0))
            t_max = float(s_info.get('최대미래가치', 0))
            t_buy = float(s_info.get('매수가치', 0))
            
            if current_p > 0:
                gap_min = ((t_min - current_p) / current_p) * 100
                gap_max = ((t_max - current_p) / current_p) * 100
                gap_buy = ((t_buy - current_p) / current_p) * 100
            else:
                gap_min, gap_max, gap_buy = 0, 0, 0
        except:
            current_p, t_min, t_max, t_buy = 0, 0, 0, 0
            gap_min, gap_max, gap_buy = 0, 0, 0

        # 상단 지표 출력
        st.title(f"🚀 {selected} ({ticker_code}) 기업 가치")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("실시간 현재가", f"{unit}{p_format.format(current_p)}")
            st.markdown(f"""<div style="background-color: {badge_color}; padding: 5px 10px; border-radius: 5px; color: white; font-weight: bold; text-align: center; display: inline-block; margin-top: -15px; font-size: 0.9em;">{badge_icon} {badge_text}</div>""", unsafe_allow_html=True)
        with c2: st.metric("⚡ 매수 가치 (안전마진)", f"{unit}{p_format.format(t_buy)}", f"{gap_buy:.1f}%")
        with c3: st.metric("🛡️ 보수적 적정가 (안전)", f"{unit}{p_format.format(t_min)}", f"{gap_min:.1f}%")
        with c4: st.metric("🚀 최대 미래가치 (목표)", f"{unit}{p_format.format(t_max)}", f"{gap_max:.1f}%")

        st.write("---")

        # 차트 출력
        col1, col2 = st.columns(2)
        with col1: 
            draw_chart(ticker_code, "3mo", "📅 최근 3개월 흐름", unit, current_price=current_p)
        with col2: 
            draw_chart(ticker_code, "5y", "🏛️ 5년 장기 + 가치 평가", unit, t_min, t_max, t_buy)

        st.write("---")
        
        # 1. 간단 메모
        st.subheader("📌 핵심 요약 (메모)")
        memo_content = s_info.get('메모', '작성된 메모가 없습니다.')
        if pd.isna(memo_content): memo_content = "작성된 메모가 없습니다."
        st.info(memo_content)
        
        # 2. 심층 리포트
        st.subheader("💡 심층 분석 리포트")
        note_link = s_info.get('노트링크', None)
        img_url = s_info.get('이미지URL', None)

        if note_link and "docs.google.com" in str(note_link):
            if "/edit" in note_link:
                preview_link = note_link.split("/edit")[0] + "/preview"
            else:
                preview_link = note_link
            st.success(f"📄 **{selected}** 리포트 원본")
            components.iframe(preview_link, height=800, scrolling=True)

        elif img_url and str(img_url).startswith('http'):
            st.image(img_url, caption=f"{selected} 분석 이미지", use_container_width=True)
            if note_link and str(note_link).startswith('http'):
                 st.link_button("🔗 외부 링크 열기", note_link)
        else:
            st.markdown("등록된 심층 리포트(구글 문서)나 이미지가 없습니다.")
        
    else:
        st.warning("선택한 시장에 해당하는 종목이 없습니다.")
else:
    st.error("데이터 로딩 실패! 구글 시트 연결을 확인하세요.")
