import streamlit as st
import streamlit.components.v1 as components 
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl
import OpenDartReader
import time
import re 
import datetime

# 1. 화면 설정
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

# ---------------------------------------------------------
# [NEW] 탭 글씨 크기 키우기 (CSS 스타일 주입)
# ---------------------------------------------------------
st.markdown("""
<style>
    /* 탭(Tab) 텍스트 크기 키우기 */
    button[data-baseweb="tab"] div p {
        font-size: 22px !important;
        font-weight: bold !important;
        padding-top: 5px !important;
        padding-bottom: 5px !important;
    }
</style>
""", unsafe_allow_html=True)
# ---------------------------------------------------------

# 2. SSL 에러 방지
ssl._create_default_https_context = ssl._create_unverified_context

# 3. 데이터 로딩 (구글 시트)
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

# 4. [자동 로딩용] DART 데이터 수집 함수 (캐싱 적용 @st.cache_data)
@st.cache_data(show_spinner=False) 
def fetch_dart_data(api_key, ticker_code, stock_name):
    try:
        dart = OpenDartReader(api_key)
    except Exception as e:
         return None, f"API 키 오류: {e}"

    if len(str(ticker_code)) != 6:
        return None, "DART는 6자리 숫자 코드만 가능"

    now_year = datetime.datetime.now().year 
    end_year = now_year
    start_year = now_year - 10
    
    financial_list = []
    
    try:
        for year in range(start_year, end_year + 1):
            try:
                df = dart.finstate(ticker_code, year, reprt_code='11011')
            except:
                df = None

            if df is not None:
                if 'account_nm' not in df.columns: continue 

                if 'fs_div' in df.columns:
                    if 'CFS' in df['fs_div'].values:
                        df = df[df['fs_div'] == 'CFS']
                    elif 'OFS' in df['fs_div'].values:
                        df = df[df['fs_div'] == 'OFS']
                
                df['Year'] = year
                cond_sales = df['account_nm'].str.contains('매출액|영업수익') & ~df['account_nm'].str.contains('원가')
                cond_op = df['account_nm'].str.contains('영업이익')
                cond_net = df['account_nm'].str.contains('당기순이익') & ~df['account_nm'].str.contains('포괄|지배|비지배')
                
                target_df = df[cond_sales | cond_op | cond_net].copy()
                financial_list.append(target_df)
            
            time.sleep(0.1)

        if financial_list:
            df_final = pd.concat(financial_list)
            
            def clean_number(x):
                try:
                    return float(str(x).replace(',', ''))
                except:
                    return 0
            
            df_final['thstrm_amount'] = df_final['thstrm_amount'].apply(clean_number)
            df_clean = df_final[['Year', 'account_nm', 'thstrm_amount']]
            
            df_pivot = df_clean.pivot_table(index='Year', columns='account_nm', values='thstrm_amount', aggfunc='sum')
            df_pivot = df_pivot / 100000000 # 억 단위
            df_pivot = df_pivot.round(0)
            df_pivot = df_pivot.sort_index(ascending=True)
            
            return df_pivot, "OK"
        else:
            return None, "데이터 없음"

    except Exception as e:
        return None, f"에러: {e}"

# 5. 차트 함수
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

        if target_buy and target_buy > 0:
            fig.add_hline(y=target_buy, line_width=2, line_color="#FFFFFF", opacity=1.0)
            fig.add_annotation(xref="paper", x=0.5, y=target_buy, text=f"<b>⚡ 매수 {unit}{target_buy:,.0f}</b>", showarrow=False, yshift=0, xanchor="center", font=dict(color="black", size=16), bgcolor="#FFFFFF", bordercolor="gray", borderwidth=1, opacity=0.9)

        if target_min and target_min > 0:
            fig.add_hline(y=target_min, line_dash="dot", line_color="#00C853", opacity=0.8)
            fig.add_annotation(xref="paper", x=0.5, y=target_min, text=f"<b>🛡️ 보수 {unit}{target_min:,.0f}</b>", showarrow=False, yshift=-25, xanchor="center", font=dict(color="white", size=16), bgcolor="#00C853", bordercolor="white", borderwidth=1, opacity=0.9)

        if target_max and target_max > 0:
            fig.add_hline(y=target_max, line_dash="dash", line_color="#FF3D00", opacity=0.8)
            fig.add_annotation(xref="paper", x=0.5, y=target_max, text=f"<b>🚀 최대 {unit}{target_max:,.0f}</b>", showarrow=False, yshift=25, xanchor="center", font=dict(color="white", size=16), bgcolor="#FF3D00", bordercolor="white", borderwidth=1, opacity=0.9)
        
        fig.update_layout(title=dict(text=f"{title} ({unit})", font=dict(size=20)), height=450, template="plotly_dark", margin=dict(l=10, r=10, b=10, t=50), xaxis_rangeslider_visible=False, xaxis=dict(fixedrange=True), yaxis=dict(fixedrange=True))
        return st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})
    except Exception as e: return st.write(f"차트 에러: {e}")

# 6. 메인 로직
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
            dart_code = "".join(re.findall(r'\d+', raw_code))
            if len(dart_code) < 6: dart_code = dart_code.zfill(6)
            yf_code = dart_code + ".KQ" if raw_code.endswith(".KQ") else dart_code + ".KS"
        else:
            dart_code = raw_code
            yf_code = raw_code

        is_korea = market_choice == "한국(KRW)"
        unit = "₩" if is_korea else "$"
        p_format = "{:,.0f}" if is_korea else "{:,.2f}"
        
        # ---------------------------------------------------------
        # [NEW] 재무 데이터 자동 로딩 로직 (버튼 삭제됨)
        # ---------------------------------------------------------
        dart_df = None
        if is_korea:
            DART_API_KEY = "f7626661c1cd11987d285bd50b6d94ffdc08ca62" # ⚠️ API 키 확인
            
            with st.spinner(f"📊 {selected} 10년치 재무제표 가져오는 중... (최초 1회만 로딩)"):
                dart_df, msg = fetch_dart_data(DART_API_KEY, dart_code, selected)

        # ---------------------------------------------------------

        # 지표 계산
        grade = s_info.get('투자등급', '미분류') 
        badge_color = {"코어": "#2962FF", "위성": "#FFAB00", "시가존": "#2E7D32"}.get(grade, "#616161")
        badge_icon = {"코어": "💎", "위성": "🛰️", "시가존": "🚬"}.get(grade, "❔")
        badge_text = {"코어": "CORE", "위성": "SATELLITE", "시가존": "시가존"}.get(grade, "미지정")

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
            cagr_min = ((t_min/current_p)**(1/7)-1)*100 if current_p and t_min else 0
            cagr_max = ((t_max/current_p)**(1/7)-1)*100 if current_p and t_max else 0
        except:
            current_p = 0; gap_min=gap_max=gap_buy=cagr_min=cagr_max=0

        st.title(f"🚀 {selected} ({dart_code if is_korea else yf_code}) 기업 가치")

        # 탭 구성
        tab1, tab2 = st.tabs(["🚀 종목 대시보드", "📊 10년 재무제표"])

        # --- 탭 1: 대시보드 ---
        with tab1:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("실시간 현재가", f"{unit}{p_format.format(current_p)}")
                st.markdown(f"""<div style="background-color: {badge_color}; padding: 5px 10px; border-radius: 5px; color: white; font-weight: bold;">{badge_icon} {badge_text}</div>""", unsafe_allow_html=True)
            with c2: st.metric("⚡ 매수 가치", f"{unit}{p_format.format(t_buy)}", f"{gap_buy:.1f}%")
            with c3: 
                st.metric("🛡️ 보수적 적정가", f"{unit}{p_format.format(t_min)}", f"{gap_min:.1f}%")
                if cagr_min: st.markdown(f"<div style='background-color:#7B1FA2;color:white;padding:3px;border-radius:3px;font-size:0.8em'>📈 7~10년 CAGR {cagr_min:+.1f}%</div>", unsafe_allow_html=True)
            with c4: 
                st.metric("🚀 최대 미래가치", f"{unit}{p_format.format(t_max)}", f"{gap_max:.1f}%")
                if cagr_max: st.markdown(f"<div style='background-color:#7B1FA2;color:white;padding:3px;border-radius:3px;font-size:0.8em'>📈 7~10년 CAGR {cagr_max:+.1f}%</div>", unsafe_allow_html=True)

            st.write("---")
            col1, col2 = st.columns(2)
            with col1: draw_chart(yf_code, "3mo", "📅 최근 3개월", unit, current_price=current_p)
            with col2: draw_chart(yf_code, "5y", "🏛️ 5년 장기", unit, t_min, t_max, t_buy)

            st.write("---")
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
                st.text("등록된 리포트 없음")

        # --- 탭 2: 재무제표 (자동 로딩됨) ---
        with tab2:
            st.markdown("### 📊 최근 10년 핵심 재무지표 (매출/영업이익/순이익)")
            
            if is_korea:
                if dart_df is not None:
                    st.markdown(f"**단위: 억원** (종목: {selected})")
                    st.dataframe(dart_df, use_container_width=True, height=500)
                    
                    csv = dart_df.to_csv().encode('utf-8-sig')
                    st.download_button(
                        label="💾 엑셀(CSV)로 다운로드",
                        data=csv,
                        file_name=f"{selected}_10년재무제표.csv",
                        mime='text/csv',
                    )
                else:
                    st.warning(f"데이터를 가져오지 못했습니다. (메시지: {msg if 'msg' in locals() else '데이터 없음'})")
            else:
                st.info("🇺🇸 미국 주식은 DART 재무제표 조회를 지원하지 않습니다.")

    else:
        st.warning("종목 없음")
else:
    st.error("데이터 로딩 실패")
