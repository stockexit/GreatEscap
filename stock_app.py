import streamlit as st
import streamlit.components.v1 as components 
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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

# 스타일
st.markdown("""
<style>
    button[data-baseweb="tab"] div p { font-size: 18px !important; font-weight: bold !important; }
    thead tr th { background-color: #f5f6f7 !important; color: #333 !important; font-weight: bold !important; }
</style>
""", unsafe_allow_html=True)

# 2. SSL 설정
ssl._create_default_https_context = ssl._create_unverified_context

# 3. 데이터 로딩
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
# [핵심 로직] 이익 & EPS 추출 (초강력 버전)
# ---------------------------------------------------------
@st.cache_data(show_spinner=False) 
def fetch_value_metrics(api_key, ticker_code):
    try:
        dart = OpenDartReader(api_key)
    except Exception as e:
         return None, None, f"API 키 오류: {e}"

    if len(str(ticker_code)) != 6:
        return None, None, "DART 조회 불가"

    now_year = datetime.datetime.now().year 
    years = range(now_year - 10, now_year + 1) 
    
    result_data = []
    status_text = st.empty()
    
    try:
        for year in years:
            status_text.text(f"🔍 {year}년 실적 데이터 정밀 분석 중...")
            df = None
            try:
                # 11011: 사업보고서 (연간)
                df = dart.finstate(ticker_code, year, reprt_code='11011')
            except:
                pass # 없으면 패스

            # [수정] 데이터가 있고, 컬럼도 온전한지 체크
            if df is not None and not df.empty and 'account_nm' in df.columns:
                
                # [수정] 공백 제거 후 검색 (띄어쓰기 때문에 못 찾는 경우 방지)
                # 예: "기본 주당 이익" -> "기본주당이익"
                df['account_clean'] = df['account_nm'].astype(str).str.replace(' ', '')

                # 1. 당기순이익 찾기 (지배주주 우선)
                # '당기순이익' 글자가 있고, '포괄'은 없고
                mask_net = df['account_clean'].str.contains('당기순이익') & ~df['account_clean'].str.contains('포괄')
                
                # 2. EPS 찾기 (기본 + 주당)
                mask_eps = df['account_clean'].str.contains('기본') & df['account_clean'].str.contains('주당')

                # 연결(CFS) 우선
                target_df = df[df['fs_div'] == 'CFS']
                if target_df.empty:
                    target_df = df[df['fs_div'] == 'OFS']
                
                if not target_df.empty:
                    # (1) 순이익 추출
                    rows_net = target_df[mask_net]
                    net_income = 0
                    
                    # 지배기업소유주지분 순이익이 있으면 그걸 씀 (가장 정확)
                    row_controlling = rows_net[rows_net['account_clean'].str.contains('지배')]
                    if not row_controlling.empty:
                        target_row = row_controlling.iloc[0]
                    elif not rows_net.empty:
                        target_row = rows_net.iloc[0]
                    else:
                        target_row = None

                    if target_row is not None:
                        try: net_income = float(str(target_row['thstrm_amount']).replace(',', ''))
                        except: pass

                    # (2) EPS 추출
                    rows_eps = target_df[mask_eps]
                    eps = 0
                    if not rows_eps.empty:
                        # 보통주 우선
                        row_common = rows_eps[~rows_eps['account_clean'].str.contains('우선')]
                        if not row_common.empty:
                            eps_row = row_common.iloc[0]
                        else:
                            eps_row = rows_eps.iloc[0]
                            
                        try: eps = float(str(eps_row['thstrm_amount']).replace(',', ''))
                        except: pass
                    
                    # (3) 주식수 역산
                    shares = 0
                    if eps != 0:
                        shares = net_income / eps

                    if net_income != 0 or eps != 0:
                        result_data.append({
                            '연도': str(year),
                            '당기순이익(원)': net_income,
                            'EPS(원)': eps,
                            '유통주식수(주)': shares
                        })
            
            time.sleep(0.1)

        status_text.empty()

        if result_data:
            df_final = pd.DataFrame(result_data)
            
            # 단위 가공
            df_final['당기순이익(억)'] = (df_final['당기순이익(원)'] / 100000000).round(0)
            df_final['유통주식수(만주)'] = (df_final['유통주식수(주)'] / 10000).round(0)
            df_final['EPS(원)'] = df_final['EPS(원)'].round(0)

            # 표 포맷팅
            view_cols = ['연도', '당기순이익(억)', 'EPS(원)', '유통주식수(만주)']
            df_view = df_final[view_cols].set_index('연도').T
            cols = sorted(df_view.columns, reverse=True) 
            df_view = df_view[cols]
            
            return df_view, df_final, "OK"
        else:
            return None, None, "DART 데이터 없음"

    except Exception as e:
        status_text.empty()
        return None, None, f"오류: {e}"

# 4. 차트 함수 (선 긋기 로직 수정됨)
def draw_chart(ticker, period, title, unit, current_price=None, target_min=None, target_max=None, target_buy=None):
    try:
        interval = "1d" if period == "3mo" else "1wk"
        df = yf.download(ticker, period=period, interval=interval)
        if df.empty: return st.write(f"{title} 데이터 없음")
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name=title)])
        
        # 현재가 (항상 표시)
        if current_price and current_price > 0:
            fig.add_hline(y=current_price, line_dash="dot", line_color="#FF4081", line_width=1)
            fig.add_annotation(xref="paper", x=0.5, y=current_price, text=f"<b>현재가 {unit}{current_price:,.0f}</b>", showarrow=False, xanchor="center", yshift=10, font=dict(color="white", size=14), bgcolor="#FF4081", bordercolor="white", borderwidth=1, opacity=0.9)

        # [수정] 아래 타겟 가격들은 값이 넘어올 때만 그립니다 (5년 차트용)
        if target_buy and target_buy > 0:
            fig.add_hline(y=target_buy, line_width=2, line_color="#FFFFFF", opacity=1.0)
            fig.add_annotation(xref="paper", x=0.5, y=target_buy, text=f"<b>⚡ 매수 {unit}{target_buy:,.0f}</b>", showarrow=False, yshift=0, xanchor="center", font=dict(color="black", size=14), bgcolor="#FFFFFF", bordercolor="gray", borderwidth=1, opacity=0.9)

        if target_min and target_min > 0:
            fig.add_hline(y=target_min, line_dash="dot", line_color="#00C853", opacity=0.8)
            fig.add_annotation(xref="paper", x=0.5, y=target_min, text=f"<b>🛡️ 보수 {unit}{target_min:,.0f}</b>", showarrow=False, yshift=-20, xanchor="center", font=dict(color="white", size=14), bgcolor="#00C853", bordercolor="white", borderwidth=1, opacity=0.9)

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
        
        # 구글 시트 값 (콤마 제거 안전 로딩)
        try:
            def clean_val(v):
                try: return float(str(v).replace(',', ''))
                except: return 0
            
            t_min = clean_val(s_info.get('보수적적정가', 0))
            t_max = clean_val(s_info.get('최대미래가치', 0))
            t_buy = clean_val(s_info.get('매수가치', 0))
            
            ticker_obj = yf.Ticker(yf_code)
            history = ticker_obj.history(period="1d")
            current_p = history['Close'].iloc[-1] if not history.empty else 0
            
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

        tab1, tab2 = st.tabs(["🚀 종목 대시보드", "💎 가치분석 (이익/EPS/주식수)"])

        # --- 탭 1 ---
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
            # [수정] 3개월 차트에는 targets를 안 넣거나 None으로 전달
            with col1: draw_chart(yf_code, "3mo", "📅 최근 3개월", unit, current_price=current_p)
            
            # [수정] 5년 차트에만 targets 전달
            with col2: draw_chart(yf_code, "5y", "🏛️ 5년 장기", unit, current_price=current_p, target_min=t_min, target_max=t_max, target_buy=t_buy)
            
            st.subheader("📌 핵심 요약 (메모)")
            st.info(s_info.get('메모', '메모 없음'))
            
            st.subheader("💡 심층 리포트")
            note = s_info.get('노트링크', '')
            if note and "docs.google.com" in str(note):
                components.iframe(note.replace("/edit", "/preview"), height=800, scrolling=True)
            elif s_info.get('이미지URL'):
                st.image(s_info.get('이미지URL'), use_container_width=True)
                if str(note).startswith('http'): st.link_button("🔗 링크 열기", note)

        # --- 탭 2 ---
        with tab2:
            st.subheader(f"📊 {selected} 10년 가치 지표 (순이익 / EPS / 주식수)")
            
            if not is_korea:
                st.info("미국 주식은 지원하지 않습니다.")
            else:
                DART_API_KEY = "f7626661c1cd11987d285bd50b6d94ffdc08ca62" 
                
                with st.spinner(f"DART에서 {selected}의 이익과 주식수를 정밀 분석 중..."):
                    display_df, raw_data, msg = fetch_value_metrics(DART_API_KEY, dart_code)
                
                if display_df is not None:
                    st.dataframe(display_df.style.format("{:,.0f}"), use_container_width=True)
                    st.caption("※ 유통주식수(추정) = 당기순이익 ÷ EPS (기업이 발표한 확정 EPS 기준 역산)")

                    # 차트
                    raw_data = raw_data.sort_values('연도')
                    fig = make_subplots(specs=[[{"secondary_y": True}]])

                    fig.add_trace(go.Bar(x=raw_data['연도'], y=raw_data['당기순이익(억)'], name="당기순이익(억)", marker_color='#2962FF', opacity=0.5), secondary_y=False)
                    fig.add_trace(go.Scatter(x=raw_data['연도'], y=raw_data['EPS(원)'], name="EPS(원)", mode='lines+markers+text', text=raw_data['EPS(원)'], textposition="top center", line=dict(color='#FFD600', width=3)), secondary_y=True)

                    fig.update_layout(title="당기순이익(좌) vs EPS(우) 성장 추이", template="plotly_dark", height=500, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                    fig.update_yaxes(title_text="당기순이익 (억원)", secondary_y=False, showgrid=False)
                    fig.update_yaxes(title_text="EPS (원)", secondary_y=True, showgrid=False)

                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning(f"데이터를 가져오지 못했습니다. ({msg})")

    else:
        st.warning("종목 없음")
else:
    st.error("데이터 로딩 실패")
