import streamlit as st
import streamlit.components.v1 as components 
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import ssl
import OpenDartReader # [필수] 이제 앱 안에서 직접 씁니다!
import time

# 1. 화면 설정
st.set_page_config(
    page_title="사장님 투자 터미널", 
    layout="wide",
    initial_sidebar_state="expanded" 
)

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
        df['Market'] = df['코드'].apply(lambda x: "한국(KRW)" if str(x).upper().endswith(('.KS', '.KQ')) else "미국(USD)")
        return df
    except:
        return None

# 4. [NEW] DART 재무제표 가져오기 함수 (버튼 누르면 실행)
def fetch_dart_data(api_key, ticker_code, stock_name):
    dart = OpenDartReader(api_key)
    # 종목코드가 6자리가 아니면(예: 미국주식) 실행 안 함
    if len(str(ticker_code)) != 6:
        return None, "미국 주식이나 코드가 잘못된 종목은 DART에서 조회할 수 없습니다."

    start_year = 2015
    end_year = 2023
    financial_list = []
    
    # 진행 상황 표시바
    progress_text = "DART 서버 접속 중..."
    my_bar = st.progress(0, text=progress_text)
    total_years = end_year - start_year + 1

    try:
        for idx, year in enumerate(range(start_year, end_year + 1)):
            # 진행률 업데이트
            percent = int((idx / total_years) * 100)
            my_bar.progress(percent, text=f"{year}년도 데이터 수집 중... ({percent}%)")
            
            # 데이터 요청 (11011: 사업보고서)
            df = dart.finstate(ticker_code, year, reprt_code='11011')
            
            if df is not None:
                # 연결(CFS)만 필터링
                df = df[df['fs_div'] == 'CFS']
                df['Year'] = year
                
                # 핵심 지표 필터링
                cond_sales = df['account_nm'].str.contains('매출액|영업수익') & ~df['account_nm'].str.contains('원가')
                cond_op = df['account_nm'].str.contains('영업이익')
                cond_net = df['account_nm'].str.contains('당기순이익') & ~df['account_nm'].str.contains('포괄|지배|비지배')
                
                target_df = df[cond_sales | cond_op | cond_net].copy()
                financial_list.append(target_df)
            
            time.sleep(0.3) # 서버 부하 방지

        my_bar.progress(100, text="정리 중...")
        time.sleep(0.5)
        my_bar.empty() # 바 지우기

        if financial_list:
            df_final = pd.concat(financial_list)
            df_final['thstrm_amount'] = df_final['thstrm_amount'].str.replace(',', '').astype(float)
            df_clean = df_final[['Year', 'account_nm', 'thstrm_amount']]
            
            # 피벗 (보기 좋게)
            df_pivot = df_clean.pivot_table(index='Year', columns='account_nm', values='thstrm_amount', aggfunc='sum')
            
            # 억 단위 변환
            df_pivot = df_pivot / 100000000
            df_pivot = df_pivot.round(0)
            
            # 파일 저장
            file_name = f"{stock_name}({ticker_code})_재무제표.csv"
            df_pivot.to_csv(file_name, encoding="utf-8-sig")
            
            return df_pivot, f"성공! '{file_name}' 저장 완료"
        else:
            return None, "데이터를 찾지 못했습니다."

    except Exception as e:
        return None, f"에러 발생: {e}"

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
    # --- 사이드바 ---
    st.sidebar.markdown("## 🌍 시장 선택")
    market_choice = st.sidebar.radio("보고 싶은 시장", ["한국(KRW)", "미국(USD)"])
    filtered_df = df_sheet[df_sheet['Market'] == market_choice]
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"## 🎯 {market_choice} 종목")
    
    if not filtered_df.empty:
        selected = st.sidebar.selectbox("종목 선택 👇", filtered_df['종목명'].unique())
        s_info = filtered_df[filtered_df['종목명'] == selected].iloc[0]
        
        ticker_code = str(s_info['코드']).strip()
        # 한국 코드는 6자리 맞춰주기 (005930)
        if market_choice == "한국(KRW)" and len(ticker_code) < 6:
            ticker_code = ticker_code.zfill(6)
            
        is_korea = market_choice == "한국(KRW)"
        # yfinance용 코드 (한국은 .KS 붙이기)
        yf_code = ticker_code + ".KS" if is_korea and not ticker_code.endswith(".KS") and not ticker_code.endswith(".KQ") else ticker_code
        if market_choice == "미국(USD)": yf_code = ticker_code 
        
        unit = "₩" if is_korea else "$"
        p_format = "{:,.0f}" if is_korea else "{:,.2f}"
        
        # --- [NEW] DART 데이터 가져오기 버튼 (한국장일 때만 표시) ---
        if is_korea:
            st.sidebar.markdown("---")
            st.sidebar.subheader("📊 재무 데이터 수집")
            
            # ⚠️ 여기에 API 키를 입력하세요!
            DART_API_KEY = "f7626661c1cd11987d285bd50b6d94ffdc08ca62" 
            
            if st.sidebar.button("10년치 재무제표 가져오기 (클릭)"):
                with st.spinner('DART에서 데이터를 긁어오는 중입니다... (약 10초 소요)'):
                    dart_df, msg = fetch_dart_data(DART_API_KEY, ticker_code, selected)
                    
                    if dart_df is not None:
                        st.sidebar.success(msg)
                        # 화면에 바로 보여주기 (임시)
                        st.session_state['dart_data'] = dart_df # 상태 저장
                    else:
                        st.sidebar.error(msg)
        
        # --- 등급 및 가격 계산 ---
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

        # --- 메인 화면 ---
        st.title(f"🚀 {selected} ({ticker_code}) 기업 가치")
        
        # 재무제표 버튼 눌렀으면 표 보여주기
        if 'dart_data' in st.session_state and is_korea:
            st.markdown("### 📊 최근 10년 핵심 재무지표 (단위: 억원)")
            st.dataframe(st.session_state['dart_data'], use_container_width=True)
            if st.button("표 닫기"):
                del st.session_state['dart_data']
                st.rerun()
            st.write("---")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("실시간 현재가", f"{unit}{p_format.format(current_p)}")
            st.markdown(f"""<div style="background-color: {badge_color}; padding: 5px 10px; border-radius: 5px; color: white; font-weight: bold;">{badge_icon} {badge_text}</div>""", unsafe_allow_html=True)
        with c2: st.metric("⚡ 매수 가치", f"{unit}{p_format.format(t_buy)}", f"{gap_buy:.1f}%")
        with c3: 
            st.metric("🛡️ 보수적 적정가", f"{unit}{p_format.format
