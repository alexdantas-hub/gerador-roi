import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

st.set_page_config(page_title="ROI Intelligence System", layout="wide")

def color_negative_red(val):
    if isinstance(val, (int, float)):
        color = 'red' if val < 0 else 'green'
        return f'color: {color}; font-weight: bold'
    return ''

def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

def clean_numeric(val):
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace('R$', '').replace(' ', '').replace('%', '')
    if not s or s.lower() == 'nan':
        return 0.0
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except:
        return 0.0

st.title("📊 ROI Intelligence System")

tab1, tab2 = st.tabs(["🚀 Processamento Diário", "📈 Consulta Histórica"])

with tab1:
    st.sidebar.header("Configurações")
    data_referencia = st.sidebar.date_input("Data de Referência", datetime.now())
    cambio = st.sidebar.number_input("Cotação do Dólar (R$)", value=5.00, step=0.01)

    col_u1, col_u2 = st.columns(2)
    with col_u1: file_meta = st.file_uploader("📁 Meta Ads", type=["csv"])
    with col_u2: file_adx = st.file_uploader("📁 AdX", type=["csv"])

    if file_meta and file_adx:
        try:
            df_m = pd.read_csv(file_meta, sep=',', encoding='utf-8-sig')
            df_a = pd.read_csv(file_adx, sep=';', encoding='utf-8-sig')

            df_m['core'] = (df_m['Nome do anúncio'].str.lower().str.strip()
                            .str.replace('"', '').str.replace(r'^[a-z]{2}', '', regex=True))
            df_a['core'] = (df_a['utm_campaign'].str.lower().str.strip()
                            .str.replace('"', '').str.replace(r'^[a-z]{2}', '', regex=True))

            meta_g = df_m.groupby('core')['Valor usado (BRL)'].sum().reset_index()
            df_a['G_USD'] = (df_a['Ganhos'].astype(str)
                             .str.replace('$', '', regex=False)
                             .str.replace(',', '', regex=False)
                             .astype(float))
            adx_g = df_a.groupby('core')['G_USD'].sum().reset_index()

            merged = pd.merge(meta_g, adx_g, on='core', how='left').fillna(0)
            merged.columns = ['Campanha', 'Investimento', 'Receita (USD)']
            merged['Receita (BRL)'] = merged['Receita (USD)'] * cambio
            merged['Lucro'] = merged['Receita (BRL)'] - merged['Investimento']
            merged['ROI'] = merged.apply(
                lambda r: r['Lucro'] / r['Investimento'] if r['Investimento'] > 0 else 0, axis=1
            )

            inv_t = merged['Investimento'].sum()
            rec_t = merged['Receita (BRL)'].sum()
            luc_t = rec_t - inv_t
            roi_t = luc_t / inv_t if inv_t > 0 else 0

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Investimento Total", f"R$ {inv_t:,.2f}")
            m2.metric("Receita Total", f"R$ {rec_t:,.2f}")
            m3.metric("Lucro Líquido", f"R$ {luc_t:,.2f}")
            m4.metric("ROI Geral", f"{roi_t:.2%}")

            st.dataframe(merged.style.format({
                'Investimento': 'R$ {:,.2f}',
                'Receita (USD)': '$ {:,.2f}',
                'Receita (BRL)': 'R$ {:,.2f}',
                'Lucro': 'R$ {:,.2f}',
                'ROI': '{:.2%}'
            }).map(color_negative_red, subset=['Lucro', 'ROI']), use_container_width=True)

            # Prepara as novas linhas para salvar (usadas tanto no save normal quanto na atualização)
            def build_new_rows(df, data_str):
                return [
                    [
                        data_str,
                        r['Campanha'].upper(),
                        round(float(r['Investimento']), 2),
                        round(float(r['Receita (USD)']), 2),
                        round(float(r['Receita (BRL)']), 2),
                        round(float(r['Lucro']), 2)
                    ]
                    for _, r in df.iterrows()
                ]

            if st.button("💾 Salvar no Google Sheets"):
                data_str = data_referencia.strftime('%Y-%m-%d')
                client = get_gspread_client()
                sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
                raw_existing = sheet.get_all_values()

                datas_existentes = set()
                if len(raw_existing) > 1:
                    for row in raw_existing[1:]:
                        if row:
                            datas_existentes.add(str(row[0]).strip()[:10])

                if data_str in datas_existentes:
                    # Armazena contexto para o diálogo de confirmação
                    st.session_state['aguardando_confirmacao'] = True
                    st.session_state['data_str_pendente'] = data_str
                    st.session_state['merged_pendente'] = merged.copy()
                else:
                    # Não há duplicata: salva diretamente
                    new_rows = build_new_rows(merged, data_str)
                    sheet.append_rows(new_rows, value_input_option='RAW')
                    st.session_state['aguardando_confirmacao'] = False
                    st.success(f"✅ {len(new_rows)} campanhas salvas para {data_str}!")

            # Diálogo de confirmação (persiste entre re-execuções via session_state)
            if st.session_state.get('aguardando_confirmacao'):
                data_str = st.session_state['data_str_pendente']
                st.warning(
                    f"⚠️ Já existem dados salvos para **{data_str}**. "
                    f"Deseja substituí-los pelos novos dados carregados?"
                )
                col_sim, col_nao, _ = st.columns([1, 1, 6])
                with col_sim:
                    if st.button("✅ Sim, atualizar", type="primary"):
                        try:
                            client2 = get_gspread_client()
                            sheet2 = client2.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
                            all_rows = sheet2.get_all_values()
                            headers = all_rows[0]

                            # Identifica os índices das linhas da data a substituir (1-based no Sheets)
                            linhas_para_deletar = [
                                i + 2  # +1 pelo header, +1 porque Sheets é 1-based
                                for i, row in enumerate(all_rows[1:])
                                if row and str(row[0]).strip()[:10] == data_str
                            ]

                            # Deleta de baixo para cima para não deslocar índices
                            for idx in sorted(linhas_para_deletar, reverse=True):
                                sheet2.delete_rows(idx)

                            # Insere as novas linhas no final
                            merged_p = st.session_state['merged_pendente']
                            new_rows = build_new_rows(merged_p, data_str)
                            sheet2.append_rows(new_rows, value_input_option='RAW')

                            st.session_state['aguardando_confirmacao'] = False
                            st.success(f"✅ Dados de {data_str} atualizados com sucesso! ({len(new_rows)} campanhas)")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao atualizar: {e}")
                with col_nao:
                    if st.button("❌ Não, cancelar"):
                        st.session_state['aguardando_confirmacao'] = False
                        st.info("Operação cancelada. Os dados existentes foram mantidos.")
                        st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")

with tab2:

    st.subheader("🔍 Análise de Desempenho Histórico")

    hoje = datetime.now().date()
    primeiro_dia_mes = hoje.replace(day=1)
    ultimo_mes_fim = primeiro_dia_mes - timedelta(days=1)
    ultimo_mes_inicio = ultimo_mes_fim.replace(day=1)

    opcao_data = st.selectbox("Selecione o Período", [
        "Hoje", "Ontem", "Últimos 7 dias", "Últimos 15 dias",
        "Mês Atual", "Mês Passado", "Personalizado"
    ])

    if opcao_data == "Hoje":
        start, end = hoje, hoje
    elif opcao_data == "Ontem":
        start = end = hoje - timedelta(days=1)
    elif opcao_data == "Últimos 7 dias":
        start, end = hoje - timedelta(days=6), hoje
    elif opcao_data == "Últimos 15 dias":
        start, end = hoje - timedelta(days=14), hoje
    elif opcao_data == "Mês Atual":
        start, end = primeiro_dia_mes, hoje
    elif opcao_data == "Mês Passado":
        start, end = ultimo_mes_inicio, ultimo_mes_fim
    else:
        c1, c2 = st.columns(2)
        start = c1.date_input("Início", hoje - timedelta(days=30))
        end = c2.date_input("Fim", hoje)

    if st.button("Consultar Histórico"):
        try:
            client = get_gspread_client()
            sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")

            raw = sheet.get_all_values()
            if len(raw) < 2:
                st.warning("Sem dados na planilha.")
            else:
                headers = raw[0]
                df_h = pd.DataFrame(raw[1:], columns=headers)

                for col in ['Investimento', 'Receita (USD)', 'Receita (BRL)', 'Lucro']:
                    if col in df_h.columns:
                        df_h[col] = df_h[col].apply(clean_numeric)

                df_h['ROI'] = df_h.apply(
                    lambda r: r['Lucro'] / r['Investimento'] if r['Investimento'] > 0 else 0, axis=1
                )
                df_h['Data_Ref'] = pd.to_datetime(df_h['Data_Ref'], errors='coerce').dt.date
                df_final = df_h[(df_h['Data_Ref'] >= start) & (df_h['Data_Ref'] <= end)].copy()

                if df_final.empty:
                    st.warning("Sem dados para este período.")
                else:
                    # ── CARDS ──────────────────────────────────────────────────
                    inv_h = df_final['Investimento'].sum()
                    rec_h = df_final['Receita (BRL)'].sum()
                    luc_h = rec_h - inv_h
                    roi_h = luc_h / inv_h if inv_h > 0 else 0

                    h1, h2, h3, h4 = st.columns(4)
                    h1.metric("💰 Investimento", f"R$ {inv_h:,.2f}")
                    h2.metric("📥 Receita", f"R$ {rec_h:,.2f}")
                    h3.metric("💵 Lucro", f"R$ {luc_h:,.2f}")
                    h4.metric("📊 ROI Médio", f"{roi_h:.2%}")

                    st.divider()

                    # ── TABELAS ────────────────────────────────────────────────
                    st.markdown("### 📋 Tabelas")
                    tb_resumo, tb_detalhado, tb_diario = st.tabs([
                        "Resumo por Campanha", "Detalhado por Dia", "📅 Consolidado por Dia"
                    ])

                    fmt = {
                        'Investimento': 'R$ {:,.2f}',
                        'Receita (USD)': '$ {:,.2f}',
                        'Receita (BRL)': 'R$ {:,.2f}',
                        'Lucro': 'R$ {:,.2f}',
                        'ROI': '{:.2%}'
                    }

                    with tb_resumo:
                        resumo = df_final.groupby('Campanha').agg(
                            Investimento=('Investimento', 'sum'),
                            Receita_USD=('Receita (USD)', 'sum'),
                            Receita_BRL=('Receita (BRL)', 'sum'),
                            Lucro=('Lucro', 'sum'),
                            Dias=('Data_Ref', 'nunique')
                        ).reset_index()
                        resumo['ROI'] = resumo.apply(
                            lambda r: r['Lucro'] / r['Investimento'] if r['Investimento'] > 0 else 0, axis=1
                        )
                        resumo = resumo.rename(columns={
                            'Receita_USD': 'Receita (USD)',
                            'Receita_BRL': 'Receita (BRL)'
                        })
                        resumo = resumo.sort_values('ROI', ascending=False)

                        st.dataframe(
                            resumo[['Campanha', 'Dias', 'Investimento', 'Receita (USD)', 'Receita (BRL)', 'Lucro', 'ROI']]
                            .style.format({**fmt, 'Dias': '{:.0f}'})
                            .map(color_negative_red, subset=['Lucro', 'ROI']),
                            use_container_width=True, hide_index=True
                        )

                    with tb_detalhado:
                        det = df_final[['Data_Ref', 'Campanha', 'Investimento', 'Receita (USD)', 'Receita (BRL)', 'Lucro', 'ROI']].copy()
                        det = det.sort_values(['Data_Ref', 'Campanha'])
                        st.dataframe(
                            det.style.format(fmt)
                            .map(color_negative_red, subset=['Lucro', 'ROI']),
                            use_container_width=True, hide_index=True
                        )

                    with tb_diario:
                        # Agrupa tudo por data — uma linha por dia
                        cons = df_final.groupby('Data_Ref').agg(
                            Investimento=('Investimento', 'sum'),
                            Receita_USD=('Receita (USD)', 'sum'),
                            Receita_BRL=('Receita (BRL)', 'sum'),
                            Lucro=('Lucro', 'sum')
                        ).reset_index()
                        cons['ROI'] = cons.apply(
                            lambda r: r['Lucro'] / r['Investimento'] if r['Investimento'] > 0 else 0, axis=1
                        )
                        cons = cons.rename(columns={
                            'Receita_USD': 'Receita (USD)',
                            'Receita_BRL': 'Receita (BRL)'
                        })
                        cons = cons.sort_values('Data_Ref')

                        # Linha de totais do período
                        total_inv  = cons['Investimento'].sum()
                        total_usd  = cons['Receita (USD)'].sum()
                        total_brl  = cons['Receita (BRL)'].sum()
                        total_luc  = cons['Lucro'].sum()
                        total_roi  = total_luc / total_inv if total_inv > 0 else 0

                        totais = pd.DataFrame([{
                            'Data_Ref': 'TOTAL',
                            'Investimento': total_inv,
                            'Receita (USD)': total_usd,
                            'Receita (BRL)': total_brl,
                            'Lucro': total_luc,
                            'ROI': total_roi
                        }])
                        cons_display = pd.concat([cons, totais], ignore_index=True)
                        cons_display['Data_Ref'] = cons_display['Data_Ref'].astype(str)

                        def highlight_total(row):
                            if row['Data_Ref'] == 'TOTAL':
                                return ['font-weight: bold; background-color: #1e1e2e; color: white'] * len(row)
                            return [''] * len(row)

                        st.dataframe(
                            cons_display[['Data_Ref', 'Investimento', 'Receita (USD)', 'Receita (BRL)', 'Lucro', 'ROI']]
                            .style
                            .format({**fmt, 'Data_Ref': '{}'})
                            .map(color_negative_red, subset=['Lucro', 'ROI'])
                            .apply(highlight_total, axis=1),
                            use_container_width=True, hide_index=True
                        )

                        # Botão de download CSV
                        csv_data = cons[['Data_Ref', 'Investimento', 'Receita (USD)', 'Receita (BRL)', 'Lucro', 'ROI']].copy()
                        csv_data['Data_Ref'] = csv_data['Data_Ref'].astype(str)
                        csv_data['ROI'] = (csv_data['ROI'] * 100).round(2).astype(str) + '%'
                        st.download_button(
                            label="⬇️ Baixar CSV",
                            data=csv_data.to_csv(index=False, sep=';', decimal=',').encode('utf-8'),
                            file_name=f"consolidado_{start}_{end}.csv",
                            mime='text/csv'
                        )

                    st.divider()

                    # ── GRÁFICOS ───────────────────────────────────────────────
                    st.markdown("### 📈 Gráficos")

                    # 1. Evolução diária — ROI e Lucro
                    st.markdown("#### Evolução Diária — ROI e Lucro")
                    diario = df_final.groupby('Data_Ref').agg(
                        Investimento=('Investimento', 'sum'),
                        Receita_BRL=('Receita (BRL)', 'sum'),
                        Lucro=('Lucro', 'sum')
                    ).reset_index()
                    diario['ROI (%)'] = diario.apply(
                        lambda r: (r['Lucro'] / r['Investimento'] * 100) if r['Investimento'] > 0 else 0, axis=1
                    )
                    diario['Data_Ref'] = diario['Data_Ref'].astype(str)

                    fig1 = go.Figure()
                    fig1.add_trace(go.Bar(
                        x=diario['Data_Ref'], y=diario['Lucro'],
                        name='Lucro (R$)',
                        marker_color=['#2ecc71' if v >= 0 else '#e74c3c' for v in diario['Lucro']],
                        yaxis='y1'
                    ))
                    fig1.add_trace(go.Scatter(
                        x=diario['Data_Ref'], y=diario['ROI (%)'],
                        name='ROI (%)', mode='lines+markers',
                        line=dict(color='#3498db', width=2),
                        marker=dict(size=7), yaxis='y2'
                    ))
                    fig1.update_layout(
                        yaxis=dict(title='Lucro (R$)', side='left'),
                        yaxis2=dict(title='ROI (%)', side='right', overlaying='y', ticksuffix='%'),
                        legend=dict(orientation='h', y=1.1),
                        hovermode='x unified', height=380
                    )
                    st.plotly_chart(fig1, use_container_width=True)

                    # 2. Investimento vs Receita por dia
                    st.markdown("#### Investimento vs Receita por Dia")
                    fig2 = go.Figure()
                    fig2.add_trace(go.Bar(
                        x=diario['Data_Ref'], y=diario['Investimento'],
                        name='Investimento', marker_color='#e67e22'
                    ))
                    fig2.add_trace(go.Bar(
                        x=diario['Data_Ref'], y=diario['Receita_BRL'],
                        name='Receita (BRL)', marker_color='#2ecc71'
                    ))
                    fig2.update_layout(
                        barmode='group', yaxis_title='R$',
                        legend=dict(orientation='h', y=1.1),
                        hovermode='x unified', height=350
                    )
                    st.plotly_chart(fig2, use_container_width=True)

                    # 3. Ranking de campanhas por ROI
                    st.markdown("#### Ranking de Campanhas por ROI no Período")
                    ranking = resumo.sort_values('ROI')
                    ranking = ranking.copy()
                    ranking['ROI (%)'] = ranking['ROI'] * 100
                    ranking['cor'] = ranking['ROI (%)'].apply(lambda v: '#2ecc71' if v >= 0 else '#e74c3c')

                    fig3 = go.Figure(go.Bar(
                        x=ranking['ROI (%)'],
                        y=ranking['Campanha'],
                        orientation='h',
                        marker_color=ranking['cor'].tolist(),
                        text=ranking['ROI (%)'].apply(lambda v: f'{v:.1f}%'),
                        textposition='outside'
                    ))
                    fig3.update_layout(
                        xaxis=dict(title='ROI (%)', ticksuffix='%'),
                        height=max(350, len(ranking) * 38),
                        margin=dict(l=20, r=80)
                    )
                    st.plotly_chart(fig3, use_container_width=True)

                    # 4. ROI por campanha ao longo do tempo
                    st.markdown("#### ROI por Campanha ao Longo do Tempo")
                    camp_diario = df_final.copy()
                    camp_diario['Data_Ref'] = camp_diario['Data_Ref'].astype(str)
                    camp_diario['ROI (%)'] = camp_diario['ROI'] * 100

                    fig4 = px.line(
                        camp_diario.sort_values('Data_Ref'),
                        x='Data_Ref', y='ROI (%)',
                        color='Campanha', markers=True,
                        labels={'Data_Ref': 'Data', 'ROI (%)': 'ROI (%)'}
                    )
                    fig4.add_hline(y=0, line_dash='dash', line_color='gray', opacity=0.5)
                    fig4.update_layout(
                        yaxis_ticksuffix='%',
                        hovermode='x unified',
                        legend=dict(orientation='h', y=-0.3),
                        height=450
                    )
                    st.plotly_chart(fig4, use_container_width=True)

        except Exception as e:
            st.error(f"Erro ao consultar: {e}")
