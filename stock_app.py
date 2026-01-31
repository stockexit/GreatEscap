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
    button[data-baseweb="tab"] div p { font-size: 18px !important; font-weight: bold !important; }
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
# [핵심] 10년치 당기순이익만 뽑아오는 함수 (에러 방지 강화)
# ---------------------------------------------------------
@st.cache_data(show_spinner=False) 
def fetch_net_income_history(api_key, ticker_code):
    try:
        dart = OpenDartReader(api_key)
    except Exception as e:
         return None, f"API 키 오류: {e}"

    if len(str(ticker_code)) != 6:
        return None, "DART 조회 불가"

    now_year = datetime.datetime.now().year 
    years = range(now_year - 10, now_year + 1) 
    
    income_data = []
    status_text = st.empty()
    
    try:
        for year in years:
            status_text.text(f"🔍 {year}년 실적 조회 중...")
            try:
                # 11011: 사업보고서 (1년 확정치)
                df = dart.finstate(ticker_code, year, reprt_code='11011')
            except:
                df = None

            # [수정] df가 None이 아니고, 'account_nm' 컬럼이 진짜 있을 때만 실행
            if df is not None and 'account_nm' in df.columns:
                # 1. '당기순이익' 찾기
                mask = df['account_nm'].str.contains('당기순이익', na=False) & \
                       ~df['account_nm'].str.contains('포괄', na=False) & \
                       ~df['account_nm'].str.contains('지배', na=False) & \
                       ~df['account_nm'].str.contains('비지배', na=False)
                
                target_row = df[mask]
                
                if not target_row.empty:
                    # 2. 연결(CFS) 우선
                    val_row = target_row[target_row['fs_div'] == 'CFS']
                    if val_row.empty:
                        val_row = target_row[target_row['fs_div'] == 'OFS']
                    
                    if not val_row.empty:
                        amount_str = str(val_row.iloc[0]['thstrm_amount'])
                        try:
                            income_val = float(amount_str.replace(',', ''))
                        except:
                            income_val = 0
                        
                        income_data.append({
                            '연도': str(year),
                            '당기순이익': income_val
                        })
            
            time.sleep(0.1) 

        status_text.empty()

        if income_data:
            df_final = pd.DataFrame(income_data)
            
            # 단위 변환
            df_final['당기순이익(억)'] = df_final['당기순이익'] / 100000000
            df_final['당기순이익(억)'] = df_final['당기순이익(억)'].round(0)
            
            # 피벗
            df_pivot = df_final[['연도', '당기순이익(억)']].set_index('연도').T
            cols = sorted(df_pivot.columns, reverse=True)
            df_pivot = df_pivot[cols]
            
            return df_pivot, "OK"
        else:
            return None, "데이터 없음 (사업보고서 누락 등)"

    except Exception as e:
        status_text.empty()
        return None, f"에러: {e}"

# 4. 차트 함수 (선 긋기 기능 복구 완료!)
def draw_chart(ticker, period, title, unit, target_min=None, target_max=None, target_buy=None, current_price=None):
    try:
        interval = "1d" if period == "3mo" else "1wk"
        df = yf.download(ticker, period=period, interval=interval)
        if df.empty: return st.write(f"{title} 데이터 없음")
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name=title)])
        
        # 현재가 점선
        if current_price and current_price > 0:
            fig.add_hline(y=current_price, line_dash="dot", line_color="#FF4081", line_width=1)
            fig.add_annotation(xref="paper", x=0.5, y=current_price, text=f"<b>현재가 {unit}{current_price:,.0f}</b>", showarrow=False, xanchor="center", yshift=10, font=dict(color="white", size=14), bgcolor="#FF4081", bordercolor="white", borderwidth=1, opacity=0.9)

        # [복구] 매수가 (흰색 실선)
        if target_buy and target_buy > 0:
            fig.add_hline(y=target_buy, line_width=2, line_color="#FFFFFF", opacity=1.0)
            fig.add_annotation(xref="paper", x=0.5, y=target_buy, text=f"<b>⚡ 매수 {unit}{target_buy:,.0f}</b>", showarrow=False, yshift=0, xanchor="center", font=dict(color="black", size=14), bgcolor="#FFFFFF", bordercolor="gray", borderwidth=1, opacity=0.9)

        # [복구] 보수적 적정가 (초록 점선)
        if target_min and target_min > 0:
            fig.add_hline(y=target_min, line_dash="dot", line_color="#00C853", opacity=0.8)
            fig.add_annotation(xref="paper", x=0.5, y=target_min, text=f"<b>🛡️ 보수 {unit}{target_min:,.0f}</b>", showarrow=False, yshift=-20, xanchor="center", font=dict(color="white", size=14), bgcolor="#00C853", bordercolor="white", borderwidth=1, opacity=0.9)

        # [복구] 최대 미래가치 (주황 파선)
        if target_max and target_max > 0:
            fig.add_hline(y=target_max, line_dash="dash", line_color="#FF3D00", opacity=0.8)
            fig.add_annotation(xref="paper", x=0.5, y=target_max, text=f"<b>🚀 최대 {unit}{target_max:,.0f}</b>", showarrow=False, yshift=20, xanchor="center", font=dict(color="white", size=14), bgcolor="#FF3D00", bordercolor="white", borderwidth=1, opacity=0.9)
        
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
        
        # [복구] 구글 시트에서 적정가 데이터 가져오기 (이게 있어야 선을 그음)
        try:
            t_min = float(str(s_info.get('보수적적정가', 0)).replace(',', ''))
            t_max = float(str(s_info.get('최대미래가치', 0)).replace(',', ''))
            t_buy = float(str(s_info.get('매수가치', 0)).replace(',', ''))
        except:
            t_min = t_max = t_buy = 0

        # 실시간 가격 가져오기
        try:
            ticker_obj = yf.Ticker(yf_code)
            history = ticker_obj.history(period="1d")
            current_p = history['Close'].iloc[-1] if not history.empty else 0
            
            # 괴리율 계산
            gap_min = ((t_min - current_p)/current_p)*100 if current_p else 0
            gap_max = ((t_max - current_p)/current_p)*100 if current_p else 0
            gap_buy = ((t_buy - current_p)/current_p)*100 if current_p else 0
            cagr_min = ((t_min/current_p)**(1/7)-1)*100 if current_p and t_min else 0
            cagr_max = ((t_max/current_p)**(1/7)-1)*100 if current_p and t_max else 0
            
            grade = s_info.get('투자등급', '미분류') 
            badge_color = {"코어": "#2962FF", "위성": "#FFAB00", "시가존": "#2E7D32"}.get(grade, "#616161")
            badge_icon = {"코어": "💎", "위성": "🛰️", "시가존": "🚬"}.get(grade, "❔")
            badge_text = {"코어": "CORE", "위성": "SATELLITE", "시가존": "시가존"}.get(grade, "미지정")
            
        except:
            current_p = 0; gap_min=gap_max=gap_buy=cagr_min=cagr_max=0

        st.title(f"🚀 {selected} ({dart_code if is_korea else yf_code}) 기업 가치")

        # 탭 구성
        tab1, tab2 = st.tabs(["🚀 종목 대시보드", "💎 가치분석 (10년 이익)"])

        # ----------------------------------------------------
        # [탭 1] 대시보드 (차트 선 복구 완료)
        # ----------------------------------------------------
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
            # [수정] draw_chart에 t_min, t_max, t_buy 값을 제대로 전달
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

        # ----------------------------------------------------
        # [탭 2] 가치분석 (10년치 당기순이익 - 에러 방지 적용)
        # ----------------------------------------------------
        with tab2:
            st.subheader(f"📊 {selected} 최근 10년 당기순이익 추이")
            
            if not is_korea:
                st.info("미국 주식은 지원하지 않습니다.")
            else:
                DART_API_KEY = "f7626661c1cd11987d285bd50b6d94ffdc08ca62" 
                
                with st.spinner(f"{selected} 10년치 당기순이익 가져오는 중..."):
                    inc_df, msg = fetch_net_income_history(DART_API_KEY, dart_code)
                
                if inc_df is not None:
                    st.markdown("**단위: 억원**")
                    st.dataframe(inc_df.style.format("{:,.0f}"), use_container_width=True)
                    
                    chart_df = inc_df.T.reset_index()
                    chart_df.columns = ['Year', 'NetIncome']
                    chart_df['NetIncome'] = chart_df['NetIncome'].astype(float)
                    chart_df = chart_df.sort_values('Year')

                    colors = ['#2962FF' if v >= 0 else '#FF5252' for v in chart_df['NetIncome']]

                    fig = go.Figure([go.Bar(
                        x=chart_df['Year'], 
                        y=chart_df['NetIncome'], 
                        marker_color=colors,
                        text=chart_df['NetIncome'],
                        textposition='auto'
                    )])
                    fig.update_layout(title="연도별 당기순이익 변화", template="plotly_dark", height=400)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    # 에러 메시지를 좀 더 친절하게 출력
                    st.warning(f"데이터를 가져오지 못했습니다. ({msg})")

    else:
        st.warning("종목 없음")
else:
    st.error("데이터 로딩 실패")
