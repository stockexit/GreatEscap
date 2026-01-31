if display_df is not None:
                    # -----------------------------------------------------
                    # [업그레이드] 10년 평균 vs 5년 평균 성장률(모멘텀) 분석
                    # -----------------------------------------------------
                    raw_data = raw_data.sort_values('연도') # 과거 -> 최신
                    eps_series = raw_data['EPS(원)']
                    
                    # 1. 평균 계산
                    eps_mean_10 = eps_series.mean()        # 10년 전체 평균
                    eps_mean_5 = eps_series.tail(5).mean() # 최근 5년 평균
                    
                    # 2. [핵심] 성장 모멘텀 계산 ((5년평균 - 10년평균) / 10년평균)
                    # 10년 평균이 0이거나 음수일 경우 예외처리
                    if eps_mean_10 > 0:
                        momentum = ((eps_mean_5 - eps_mean_10) / eps_mean_10) * 100
                    else:
                        momentum = 0 # 적자 기업이거나 데이터 문제 시 0 처리
                    
                    # 3. 화면 표시 (화살표 색상 자동 적용됨)
                    c_m1, c_m2, c_m3 = st.columns(3)
                    
                    with c_m1: 
                        st.metric("10년 평균 EPS (기초체력)", f"{eps_mean_10:,.0f}원")
                    
                    with c_m2: 
                        st.metric("5년 평균 EPS (최근추세)", f"{eps_mean_5:,.0f}원")
                    
                    with c_m3:
                        # delta 옵션을 쓰면 자동으로 초록(상승)/빨강(하락) 화살표가 생깁니다.
                        st.metric(
                            "성장 가속도 (Momentum)", 
                            f"{momentum:+.1f}%", 
                            f"{momentum:+.1f}% (장기평균 대비)",
                            delta_color="normal" # 양수면 초록, 음수면 빨강
                        )
                    
                    # -----------------------------------------------------
                    # 아래는 기존 표/차트 로직 그대로 유지
                    # -----------------------------------------------------
                    st.dataframe(display_df.style.format("{:,.0f}"), use_container_width=True)
                    
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    
                    fig.add_trace(go.Bar(
                        x=raw_data['연도'], y=raw_data['매출액(억)'], 
                        name='매출액(좌측)', marker_color='#90CAF9', opacity=0.6
                    ), secondary_y=False)
                    
                    fig.add_trace(go.Bar(
                        x=raw_data['연도'], y=raw_data['영업이익(억)'], 
                        name='영업이익(좌측)', marker_color='#2962FF'
                    ), secondary_y=False)

                    fig.add_trace(go.Scatter(
                        x=raw_data['연도'], y=raw_data['EPS(원)'], 
                        name='EPS(보정됨)', mode='lines+markers+text',
                        line=dict(color='#00E676', width=3),
                        marker=dict(size=8, color='#00E676', symbol='diamond'),
                        text=raw_data['EPS(원)'].apply(lambda x: f"{x:,.0f}"),
                        textposition="top center",
                        textfont=dict(color="white", size=11)
                    ), secondary_y=True)
                    
                    # 평균선 표시
                    fig.add_hline(y=eps_mean_10, line_dash="dash", line_color="#FFAB00", line_width=2, secondary_y=True,
                                  annotation_text=f"10년평균: {eps_mean_10:,.0f}", annotation_position="top left", annotation_font_color="#FFAB00")
                    fig.add_hline(y=eps_mean_5, line_dash="dot", line_color="#D500F9", line_width=2, secondary_y=True,
                                  annotation_text=f"5년평균: {eps_mean_5:,.0f}", annotation_position="bottom left", annotation_font_color="#D500F9")
                    
                    fig.update_layout(title=f"{selected} 실적 성장 추이", template="plotly_dark", barmode='group', height=550, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                    fig.update_yaxes(title_text="금액 (억 원)", secondary_y=False, showgrid=True, gridcolor='rgba(255,255,255,0.1)')
                    fig.update_yaxes(title_text="EPS (원)", secondary_y=True, showgrid=False)
                    
                    st.plotly_chart(fig, use_container_width=True)
