import streamlit as st
import streamlit.components.v1 as components 
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl
import OpenDartReader
import time
import datetime

# 1. 화면 설정
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# 스타일 설정
st.markdown("""
<style>
    thead tr th { background-color: #f5f6f7 !important; color: #333 !important; font-weight: bold !important; }
</style>
""", unsafe_allow_html=True)

# 2. SSL 에러 방지
ssl._create_default_https_context = ssl._create_unverified_context

# 3. 기본 데이터 로딩
@st.cache_data(ttl=60)
def load_data():
    try:
        sheet_url = "https://docs.google.com/spreadsheets/d/1FHEblKL20VNpqdhnGu2FK7UY4ueMS3JSEwiZUEqDtaw/edit?usp=sharing"
        url = sheet_url.split("/edit")[0] + "/export?format=csv"
        df = pd.read_csv(url)
        df = df.dropna(subset=['종목명'])
        df['Market'] = df['코드'].apply(lambda x: "한국(KRW)" if str(x).upper().endswith(('.KS', '.KQ')) or str(x).isdigit() else "미국(USD)")
        return df
    except:
        return None

# ---------------------------------------------------------
# [핵심] EPS만 10년치 뽑아오는 함수 (초간단 버전)
# ---------------------------------------------------------
@st.cache_data(show_spinner=False) 
def fetch_eps_history(api_key, ticker_code):
    try:
        dart = OpenDartReader(api_key)
    except Exception as e:
         return None, f"API 키 오류: {e}"

    if len(str(ticker_code)) != 6:
        return None, "DART 조회 불가"

    now_year = datetime.datetime.now().year 
    # 10년치 (현재-10년 ~ 현재)
    years = range(now_year - 10, now_year + 1) 
    
    eps_data = []
    status_text = st.empty()
    
    try:
        for year in years:
            status_text.text(f"🔍 {year}년 EPS 찾는 중...")
            try:
                # 11011: 사업보고서 (1년 확정치)
                df = dart.finstate(ticker_code, year, reprt_code='11011')
            except:
                df = None

            if df is not None:
                # 1. '기본주당이익' 글자가 들어간 행 찾기
                # (보통 '기본주당이익' 또는 '기본주당순이익' 이라고 적혀있음)
                mask = df['account_nm'].str.contains('기본주당', na=False) & df['account_nm'].str.contains('이익', na=False)
                target_row = df[mask]
                
                if not target_row.empty:
                    # 2. 연결(CFS) 우선, 없으면 별도(OFS)
                    val_row = target_row[target_row['fs_div'] == 'CFS']
                    if val_row.empty:
                        val_row = target_row[target_row['fs_div'] == 'OFS']
                    
                    if not val_row.empty:
                        amount_str = str(val_row.iloc[0]['thstrm_amount'])
                        try:
                            # 콤마 제거하고 숫자로 변환
                            eps_val = float(amount_str.replace(',', ''))
                        except:
                            eps_val = 0
                        
                        eps_data.append({
                            'Year': str(year),
                            'EPS': eps_val
                        })
            
            time.sleep(0.1) # 서버 예의 지키기

        status_text.empty()

        if eps_data:
            df_final = pd.DataFrame(eps_data)
            # 표 모양 만들기 (가로로 연도 나열)
            df_pivot = df_final.set_index('Year').T 
            
            # 최신 연도가 왼쪽으로 오게 정렬
            cols = sorted(df_pivot.columns, reverse=True)
            df_pivot = df_pivot[cols]
            
            return df_pivot, "OK"
        else:
            return None, "EPS 데이터를 찾지 못했습니다."

    except Exception as e:
        status_text.empty()
        return None, f"에러: {e}"

# 4. 차트 함수
def draw_chart(ticker, period, title, unit, target_min=None, target_max=None, target_buy=None, current_price=None):
    try:
        interval = "1d" if period == "3mo" else "1wk"
        df = yf.download(ticker, period=period, interval=interval)
        if df.empty: return st.write(f"{title} 데이터 없음")
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name=title)])
        
        if current_price and current_price > 0:
            fig.add_hline(y=current_price, line_dash="dot", line_color="#FF4081", line_width=1)
            fig.add_annotation(xref="paper", x=0.5, y=current_price, text=f"<b>현재가 {unit}{current_price:,.0f}</b>", showarrow=False, xanchor="center", yshift=10, font=dict(color="white", size=16), bgcolor="#FF4081", bordercolor="white", borderwidth=1, opacity=0.9)
        
        fig.update_layout(title=dict(text=f"{title} ({unit})", font=dict(size=20)), height=450, template="plotly_dark", margin=dict(l=10, r=10, b=10, t=50), xaxis_rangeslider_visible=False, xaxis=dict(fixedrange=True), yaxis=dict(fixedrange=True))
        return st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})
    except Exception as e: return st.write(f"차트 에러: {e}")

# 5. 메인 로직
df_sheet = load_data()

if df_sheet is not None:
    st.sidebar.markdown("## 🌍 시장 선택")
    market_choice = st.sidebar.radio("보고 싶은 시장", ["한국(KRW)", "미국(USD)"])
    
    if market_choice == "한국(KRW)":
        filtered_df = df_sheet[df_sheet['Market'] == "한국(KRW)"]
    else:
        filtered_df = df_sheet[df_sheet['Market'] == "미국(USD)"]
        
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"## 🎯 {market_choice} 종목")
    
    if not filtered_df.empty:
        selected = st.sidebar.selectbox("종목 선택 👇", filtered_df['종목명'].unique())
        s_info = filtered_df[filtered_df['종목명'] == selected].iloc[0]
        
        raw_code = str(s_info['코드']).strip().upper()
        if market_choice == "한국(KRW)":
            import re
            dart_code = "".join(re.findall(r'\d+', raw_code))
            if len(dart_code) < 6: dart_code = dart_code.zfill(6)
            yf_code = dart_code + ".KQ" if raw_code.endswith(".KQ") else dart_code + ".KS"
        else:
            dart_code = raw_code
            yf_code = raw_code

        is_korea = market_choice == "한국(KRW)"
        unit = "₩" if is_korea else "$"
        p_format = "{:,.0f}" if is_korea else "{:,.2f}"
        
        try:
            ticker_obj = yf.Ticker(yf_code)
            history = ticker_obj.history(period="1d")
            current_p = history['Close'].iloc[-1] if not history.empty else 0
            
            t_min = float(s_info.get('보수적적정가', 0))
            t_max = float(s_info.get('최대미래가치', 0))
            t_buy = float(s_info.get('매수가치', 0))
            
            gap_min = ((t_min - current_p)/current_p)*100 if current_p else 0
            gap_max = ((t_max - current_p)/current_p)*100 if current_p else 0
            gap_buy = ((t_buy - current_p)/current_p)*100 if current_p else 0
            
            grade = s_info.get('투자등급', '미분류') 
            badge_color = {"코어": "#2962FF", "위성": "#FFAB00", "시가존": "#2E7D32"}.get(grade, "#616161")
            badge_icon = {"코어": "💎", "위성": "🛰️", "시가존": "🚬"}.get(grade, "❔")
            badge_text = {"코어": "CORE", "위성": "SATELLITE", "시가존": "시가존"}.get(grade, "미지정")
            
        except:
            current_p = 0; gap_min=gap_max=gap_buy=0

        st.title(f"🚀 {selected} ({dart_code if is_korea else yf_code}) 기업 가치")

        # 탭 없이 심플하게 구성
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("실시간 현재가", f"{unit}{p_format.format(current_p)}")
            st.markdown(f"""<div style="background-color: {badge_color}; padding: 5px 10px; border-radius: 5px; color: white; font-weight: bold;">{badge_icon} {badge_text}</div>""", unsafe_allow_html=True)
        with c2: st.metric("⚡ 매수 가치", f"{unit}{p_format.format(t_buy)}", f"{gap_buy:.1f}%")
        with c3: st.metric("🛡️ 보수적 적정가", f"{unit}{p_format.format(t_min)}", f"{gap_min:.1f}%")
        with c4: st.metric("🚀 최대 미래가치", f"{unit}{p_format.format(t_max)}", f"{gap_max:.1f}%")

        st.write("---")
        
        # ----------------------------------------------------
        # [NEW] EPS 10년치 섹션
        # ----------------------------------------------------
        st.subheader("📊 지난 10년 EPS(주당순이익) 추이")
        
        if not is_korea:
            st.info("미국 주식은 지원하지 않습니다.")
        else:
            DART_API_KEY = "f7626661c1cd11987d285bd50b6d94ffdc08ca62" 
            
            # 버튼 없이 자동 로딩 (스피너만 표시)
            with st.spinner(f"{selected} 10년치 EPS 찾는 중..."):
                eps_df, msg = fetch_eps_history(DART_API_KEY, dart_code)
            
            if eps_df is not None:
                # 1. 표 보여주기
                st.dataframe(eps_df.style.format("{:,.0f}"), use_container_width=True)
                
                # 2. 바 차트 보여주기 (시각화)
                # 데이터 전처리 for Chart
                chart_df = eps_df.T.reset_index() # 연도를 행으로
                chart_df.columns = ['Year', 'EPS']
                chart_df = chart_df.sort_values('Year') # 차트는 과거->최신 순이 이쁨

                fig = go.Figure([go.Bar(x=chart_df['Year'], y=chart_df['EPS'], marker_color='#2962FF')])
                fig.update_layout(title="연도별 EPS 성장 흐름", template="plotly_dark", height=300)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"EPS 데이터를 가져오지 못했습니다. ({msg})")

        st.write("---")
        
        # 차트 및 리포트 섹션
        col1, col2 = st.columns(2)
        with col1: draw_chart(yf_code, "3mo", "📅 최근 3개월", unit, current_price=current_p)
        with col2: draw_chart(yf_code, "5y", "🏛️ 5년 장기", unit, t_min, t_max, t_buy)
        
        st.subheader("📌 핵심 요약 (메모)")
        st.info(s_info.get('메모', '메모 없음'))
        
        st.subheader("💡 심층 리포트")
        note = s_info.get('노트링크', '')
        if note and "docs.google.com" in str(note):
            components.iframe(note.replace("/edit", "/preview"), height=800, scrolling=True)
        elif s_info.get('이미지URL'):
            st.image(s_info.get('이미지URL'), use_container_width=True)
            if str(note).startswith('http'): st.link_button("🔗 링크 열기", note)

    else:
        st.warning("종목 없음")
else:
    st.error("데이터 로딩 실패")
