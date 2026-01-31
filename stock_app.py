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
# [스타일] 탭 글씨 크기 키우기 + 표 헤더 디자인
# ---------------------------------------------------------
st.markdown("""
<style>
    button[data-baseweb="tab"] div p {
        font-size: 20px !important;
        font-weight: bold !important;
    }
    thead tr th {
        background-color: #262730 !important;
        color: white !important;
        font-size: 16px !important;
    }
</style>
""", unsafe_allow_html=True)
# ---------------------------------------------------------

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
        df['Market'] = df['코드'].apply(lambda x: "한국(KRW)" if str(x).upper().endswith(('.KS', '.KQ')) or str(x).isdigit() else "미국(USD)")
        return df
    except:
        return None

# 4. [업그레이드] 상세 재무제표 수집 함수 (연도 역순 + 모든 항목)
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
    start_year = now_year - 5 # 최근 5~6년 집중 (데이터 양이 많아져서)
    
    financial_list = []
    
    # -----------------------------------------------------------
    # [핵심] 재무제표 항목 정의 (검색어 확장)
    # -----------------------------------------------------------
    # (표시 이름, 검색할 키워드)
    # 순서를 보장하기 위해 앞에 번호를 붙이고 나중에 뗍니다.
    target_items = [
        ('01.매출액', '매출액|영업수익|수익'),
        ('02.매출원가', '매출원가|영업비용'), # 영업비용은 서비스업 등에서 원가 대신 쓰임
        ('03.매출총이익', '매출총이익'),
        ('04.판매비와관리비', '판매비와관리비|판매비및관리비|판관비'),
        ('05.영업이익', '영업이익'),
        ('06.금융수익', '금융수익'),
        ('07.금융원가', '금융원가|금융비용'),
        ('08.기타수익', '기타수익|기타영업외수익'),
        ('09.기타비용', '기타비용|기타영업외비용'),
        ('10.법인세차감전이익', '법인세비용차감전|법인세차감전'),
        ('11.법인세비용', '법인세비용|법인세'),
        ('12.당기순이익', '당기순이익'),
        ('13.총포괄손익', '총포괄손익')
    ]
    
    try:
        for year in range(start_year, end_year + 1):
            try:
                # 11011: 사업보고서 (확정)
                df = dart.finstate(ticker_code, year, reprt_code='11011')
            except:
                df = None

            if df is not None:
                if 'account_nm' not in df.columns: continue 

                # 연결/별도 필터링
                if 'fs_div' in df.columns:
                    if 'CFS' in df['fs_div'].values:
                        df = df[df['fs_div'] == 'CFS']
                    elif 'OFS' in df['fs_div'].values:
                        df = df[df['fs_div'] == 'OFS']
                
                # --- 항목 매핑 로직 (개선됨) ---
                for label, pattern in target_items:
                    # 1. 일단 패턴이 포함된 행을 찾음
                    mask = df['account_nm'].str.contains(pattern, na=False)
                    
                    # 2. 예외 처리 (원하지 않는 것 제외)
                    if '매출액' in label:
                        # 매출원가가 매출액에 잡히지 않도록 제외
                        mask = mask & ~df['account_nm'].str.contains('원가|총이익', na=False)
                    elif '당기순이익' in label:
                        # 지배/비지배/포괄 제외하고 순수 당기순이익만
                        mask = mask & ~df['account_nm'].str.contains('포괄|지배|비지배', na=False)
                    elif '영업이익' in label:
                         # 영업이익(손실)만 잡고, 기타영업이익 제외
                         mask = mask & ~df['account_nm'].str.contains('기타', na=False)

                    found_row = df[mask]
                    
                    if not found_row.empty:
                        # 여러 개가 잡히면 첫 번째 것 사용 (보통 가장 상위 항목)
                        amount_str = str(found_row.iloc[0]['thstrm_amount'])
                        try:
                            amount = float(amount_str.replace(',', ''))
                        except:
                            amount = 0
                        
                        financial_list.append({
                            'Year': str(year),
                            'Item': label,
                            'Amount': amount
                        })
            
            time.sleep(0.1)

        if financial_list:
            df_final = pd.DataFrame(financial_list)
            
            # 피벗 (행: Item, 열: Year)
            df_pivot = df_final.pivot_table(index='Item', columns='Year', values='Amount', aggfunc='sum')
            
            # 단위 변환 (억원)
            df_pivot = df_pivot / 100000000
            df_pivot = df_pivot.round(0)
            
            # 정렬 1: 항목 순서대로 (01.매출액 ~ 13.총포괄손익)
            df_pivot = df_pivot.sort_index()
            
            # 정렬 2: 연도 최신순 (오른쪽 -> 왼쪽 역순 정렬)
            # columns를 역순으로 정렬해서 적용
            cols = sorted(df_pivot.columns, reverse=True)
            df_pivot = df_pivot[cols]

            # 인덱스 이름 깔끔하게 (앞에 숫자 '01.' 제거)
            df_pivot.index = [idx.split('.')[1] for idx in df_pivot.index]
            
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
        
        # --- 재무 데이터 로딩 ---
        dart_df = None
        if is_korea:
            DART_API_KEY = "f7626661c1cd11987d285bd50b6d94ffdc08ca62" 
            with st.spinner(f"📊 {selected} 상세 재무제표 분석 중..."):
                dart_df, msg = fetch_dart_data(DART_API_KEY, dart_code, selected)

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

        tab1, tab2 = st.tabs(["🚀 종목 대시보드", "📊 상세 재무제표"])

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

        with tab2:
            st.markdown(f"### 📊 {selected} 손익계산서 (단위: 억원)")
            
            if is_korea:
                if dart_df is not None:
                    st.dataframe(dart_df, use_container_width=True, height=600)
                    
                    csv = dart_df.to_csv().encode('utf-8-sig')
                    st.download_button(
                        label="💾 엑셀(CSV)로 다운로드",
                        data=csv,
                        file_name=f"{selected}_상세재무제표.csv",
                        mime='text/csv',
                    )
                else:
                    st.warning(f"데이터가 없거나 금융업(은행/보험) 종목일 수 있습니다.")
            else:
                st.info("🇺🇸 미국 주식은 DART 재무제표 조회를 지원하지 않습니다.")

    else:
        st.warning("종목 없음")
else:
    st.error("데이터 로딩 실패")
