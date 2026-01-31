import streamlit as st
import streamlit.components.v1 as components 
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots # 이중축 차트를 위해 필수
import ssl
import OpenDartReader
import time
import datetime
import re

# =========================================================
# 1. 화면 설정 & 스타일
# =========================================================
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

st.markdown("""
<style>
    button[data-baseweb="tab"] div p { font-size: 18px !important; font-weight: bold !important; }
    thead tr th { background-color: #f5f6f7 !important; color: #333 !important; font-weight: bold !important; }
    div[data-testid="stMetricValue"] { font-size: 24px !important; }
</style>
""", unsafe_allow_html=True)

# SSL 인증서 문제 해결 (Mac/Windows 호환)
ssl._create_default_https_context = ssl._create_unverified_context

# =========================================================
# 2. 데이터 로딩 (구글 시트)
# =========================================================
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

# =========================================================
# 3. [핵심] DART 재무제표 크롤링 (EPS 로직 강화됨)
# =========================================================
@st.cache_data(show_spinner=False) 
def fetch_core_financials(api_key, ticker_code):
    try:
        dart = OpenDartReader(api_key)
    except Exception as e:
         return None, None, f"API 키 오류: {e}"

    if len(str(ticker_code)) != 6:
        return None, None, "DART 조회 불가"

    now_year = datetime.datetime.now().year 
    years = range(now_year, now_year - 12, -1) # 최근 12년치 스캔
    
    result_data = []
    status_text = st.empty()
    
    try:
        for year in years:
            # 10개 데이터 모이면 중단
            if len(result_data) >= 10:
                break
                
            status_text.text(f"🔍 {year}년 핵심 실적(매출/영업/EPS) 정밀 스캔 중...")
            
            df = None
            try: 
                # 11011: 사업보고서 (가장 정확)
                df = dart.finstate(ticker_code, year, reprt_code='11011')
            except: 
                pass 

            if df is not None and not df.empty and 'account_nm' in df.columns:
                
                # 전처리: 공백 제거
                df['account_clean'] = df['account_nm'].astype(str).str.replace(' ', '').str.strip()

                # --- A. 매출액 찾기 ---
                mask_sales = df['account_clean'].str.contains('매출액|영업수익') & \
                             ~df['account_clean'].str.contains('원가|총이익|미실현')
                
                # --- B. 영업이익 찾기 ---
                mask_op = df['account_clean'].str.contains('영업이익') & \
                          ~df['account_clean'].str.contains('기타|금융|관계|지분')

                # --- C. [수정됨] EPS(기본주당이익) 찾기 ---
                # '기본주당' 키워드 사용, 희석/중단/우선주 제외
                mask_eps = df['account_clean'].str.contains('기본주당') & \
                           ~df['account_clean'].str.contains('희석') & \
                           ~df['account_clean'].str.contains('중단') & \
                           ~df['account_clean'].str.contains('우선주')

                # --- D. 값 추출 헬퍼 함수 ---
                def extract_value(dataframe, mask):
                    if dataframe.empty: return 0
                    rows = dataframe[mask]
                    if rows.empty: return 0
                    
                    # '보통주'가 명시된 행 우선 선택
                    if len(rows) > 1:
                        priority_row = rows[rows['account_clean'].str.contains('보통주')]
                        if not priority_row.empty:
                            rows = priority_row
                    
                    # 값 정제 (콤마 제거)
                    val_str = str(rows.iloc[0]['thstrm_amount']).replace(',', '').strip()
                    try: return float(val_str)
                    except: return 0

                # --- E. 연결(CFS)우선, 없으면 별도(OFS) ---
                df_cfs = df[df['fs_div'] == 'CFS'] # 연결
                df_ofs = df[df['fs_div'] == 'OFS'] # 별도

                sales = extract_value(df_cfs, mask_sales)
                op_income = extract_value(df_cfs, mask_op)
                eps = extract_value(df_cfs, mask_eps)

                # 연결 데이터가 0이면 별도 데이터로 백업(Backup)
                if sales == 0: sales = extract_value(df_ofs, mask_sales)
                if op_income == 0: op_income = extract_value(df_ofs, mask_op)
                if eps == 0: eps = extract_value(df_ofs, mask_eps)

                # 유효 데이터 있으면 저장
                if sales != 0 or op_income != 0 or eps != 0:
                    result_data.append({
                        '연도': str(year),
                        '매출액': sales,
                        '영업이익': op_income,
                        'EPS': eps
                    })
            
            time.sleep(0.05) # API 호출 제한 방지

        status_text.empty()

        if result_data:
            # 연도 내림차순 정렬
            result_data.sort(key=lambda x: x['연도'], reverse=True)
            df_final = pd.DataFrame(result_data)
            
            # 단위 변환 (매출/영업: 억, EPS: 원)
            df_final['매출액(억)'] = (df_final['매출액'] / 100000000).round(0)
            df_final['영업이익(억)'] = (df_final['영업이익'] / 100000000).round(0)
            df_final['EPS(원)'] = df_final['EPS'].round(0)

            # 화면 표시용 Transpose
            view_cols = ['연도', '매출액(억)', '영업이익(억)', 'EPS(원)']
            df_view = df_final[view_cols].set_index('연도').T
            cols = df_view.columns[:10]
            
            return df_view[cols], df_final.head(10), "OK"
        else:
            return None, None, "데이터 없음"

    except Exception as e:
        status_text.empty()
        return None, None, f"오류: {e}"

# =========================================================
# 4. 주가 차트 함수 (캔들스틱)
# =========================================================
def draw_chart(ticker, period, title, unit, current_price=None, target_min=None, target_max=None, target_buy=None):
    try:
        interval = "1d" if period == "3mo" else "1wk"
        df = yf.download(ticker, period=period, interval=interval)
        if df.empty: return st.write(f"{title} 데이터 없음")
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name=title)])
        
        # 현재가 라인
        if current_price and current_price > 0:
            fig.add_hline(y=current_price, line_dash="dot", line_color="#FF4081", line_width=1)
            fig.add_annotation(xref="paper", x=0.5, y=current_price, text=f"<b>현재가 {unit}{current_price:,.0f}</b>", showarrow=False, xanchor="center", yshift=10, font=dict(color="white", size=14), bgcolor="#FF4081", bordercolor="white", borderwidth=1, opacity=0.9)

        # 타겟 가격 라인들
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

# =========================================================
# 5. 메인 앱 로직
# =========================================================
df_sheet = load_data()

if df_sheet is not None:
    # --- 사이드바 ---
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
        
        # 코드 변환 로직
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
        
        # 데이터 계산
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

        # 헤더
        st.title(f"🚀 {selected} ({dart_code if is_korea else yf_code}) 기업 가치")

        # 탭 구성
        tab1, tab2 = st.tabs(["🚀 종목 대시보드", "💎 가치분석 (매출/영업/EPS)"])

        # ==========================
        # 탭 1: 대시보드
        # ==========================
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
            with col2: draw_chart(yf_code, "5y", "🏛️ 5년 장기", unit, current_price=None, target_min=t_min, target_max=t_max, target_buy=t_buy)
            
            st.subheader("📌 핵심 요약 (메모)")
            st.info(s_info.get('메모', '메모 없음'))
            
            st.subheader("💡 심층 리포트")
            note = s_info.get('노트링크', '')
            if note and "docs.google.com" in str(note):
                components.iframe(note.replace("/edit", "/preview"), height=800, scrolling=True)
            elif s_info.get('이미지URL'):
                st.image(s_info.get('이미지URL'), use_container_width=True)
                if str(note).startswith('http'): st.link_button("🔗 링크 열기", note)

        # ==========================
        # 탭 2: 가치분석 (매출/영업/EPS)
        # ==========================
        with tab2:
            st.subheader(f"📊 {selected} 최근 10년 핵심 실적 (매출/영업/EPS)")
            
            if not is_korea:
                st.info("미국 주식은 지원하지 않습니다.")
            else:
                # [중요] API KEY 설정
                DART_API_KEY = "f7626661c1cd11987d285bd50b6d94ffdc08ca62" 
                
                with st.spinner(f"DART에서 {selected} 10년치 데이터를 수집 중입니다..."):
                    display_df, raw_data, msg = fetch_core_financials(DART_API_KEY, dart_code)
                
                if display_df is not None:
                    # 표 출력
                    st.dataframe(display_df.style.format("{:,.0f}"), use_container_width=True)
                    
                    # ----------------------------------------------------------------
                    # [핵심] 이중축 (Dual Axis) 차트: 막대(좌) + 꺾은선(우)
                    # ----------------------------------------------------------------
                    raw_data = raw_data.sort_values('연도')
                    
                    # 1. 이중축 생성 (secondary_y=True)
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    
                    # 2. 막대 그래프 (매출, 영업이익) -> 왼쪽 Y축
                    fig.add_trace(go.Bar(
                        x=raw_data['연도'], y=raw_data['매출액(억)'], 
                        name='매출액(좌측)', marker_color='#90CAF9', opacity=0.6
                    ), secondary_y=False)
                    
                    fig.add_trace(go.Bar(
                        x=raw_data['연도'], y=raw_data['영업이익(억)'], 
                        name='영업이익(좌측)', marker_color='#2962FF'
                    ), secondary_y=False)

                    # 3. 꺾은선 그래프 (EPS) -> 오른쪽 Y축
                    fig.add_trace(go.Scatter(
                        x=raw_data['연도'], y=raw_data['EPS(원)'], 
                        name='EPS(우측)', mode='lines+markers+text',
                        line=dict(color='#00E676', width=3),
                        marker=dict(size=8, color='#00E676', symbol='diamond'),
                        text=raw_data['EPS(원)'].apply(lambda x: f"{x:,.0f}"),
                        textposition="top center",
                        textfont=dict(color="white", size=11)
                    ), secondary_y=True)
                    
                    # 4. 차트 꾸미기
                    fig.update_layout(
                        title=f"{selected} 실적 성장 추이 (Bar: 억원 / Line: 원)", 
                        template="plotly_dark", 
                        barmode='group', 
                        height=550,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    
                    # Y축 라벨 설정
                    fig.update_yaxes(title_text="금액 (억 원)", secondary_y=False, showgrid=True, gridcolor='rgba(255,255,255,0.1)')
                    fig.update_yaxes(title_text="EPS (원)", secondary_y=True, showgrid=False) # 오른쪽 그리드는 제거하여 깔끔하게
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning(f"데이터를 가져오지 못했습니다. ({msg})")

    else:
        st.warning("종목 없음")
else:
    st.error("데이터 로딩 실패")
