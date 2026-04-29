import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# 1. CONFIGURAÇÕES DE PÁGINA E ESTILO VISUAL
st.set_page_config(page_title="ROI Intelligence System", layout="wide")

# Estilo para cores condicionais (Verde para Positivo, Vermelho para Negativo)
def color_negative_red(val):
    if isinstance(val, (int, float)):
        color = 'red' if val < 0 else 'green'
        return f'color: {color}; font-weight: bold'
    return ''

# Função para conectar ao Google Sheets
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

st.title("📊 ROI Intelligence System")

# Gerenciamento de estado para confirmação de salvamento
if 'confirmar_salvamento' not in st.session_state:
    st.session_state.confirmar_salvamento = False

# Criação das Abas
tab1, tab2 = st.tabs(["🚀 Processamento Diário", "📈 Consulta Histórica"])

with tab1:
    # --- BARRA LATERAL ---
    st.sidebar.header("Configurações")
    data_referencia = st.sidebar.date_input("Data de Referência", datetime.now())
    cambio = st.sidebar.number_input("Cotação do Dólar (R$)", value=5.00, step=0.01)
    data_str = data_referencia.strftime('%Y-%m-%d')

    # --- UPLOAD DE ARQUIVOS ---
    col_u1, col_u2 = st.columns(2)
    with col_u1: file_meta = st.file_uploader("📁 Meta Ads", type=["csv"])
    with col_u2: file_adx = st.file_uploader("📁 AdX", type=["csv"])

    if file_meta and file_adx:
        try:
            # 1. Lógica de Limpeza e Processamento
            df_m = pd.read_csv(file_meta, sep=',', encoding='utf-8')
            df_a = pd.read_csv(file_adx, sep=';', encoding='utf-8')
            
            def clean_name(n):
                n = str(n).lower().strip().replace('"', '')
                return n[2:] if n.startswith(('ad', 'ca')) else n

            df_m['core'] = df_m['Nome do anúncio'].apply(clean_name)
            df_a['core'] = df_a['utm_campaign'].apply(clean_name)
            
            meta_g = df_m.groupby('core')['Valor usado (BRL)'].sum().reset_index()
            df_a['G_USD'] = df_a['Ganhos'].str.replace('$', '', regex=False).str.replace(',', '', regex=False).astype(float)
            adx_g = df_a.groupby('core')['G_USD'].sum().reset_index()
            
            merged = pd.merge(meta_g, adx_g, on='core', how='left').fillna(0)
            merged.columns = ['Campanha', 'Investimento', 'Receita (USD)']
            merged['Receita (BRL)'] = merged['Receita (USD)'] * cambio
            merged['Lucro'] = merged['Receita (BRL)'] - merged['Investimento']
            merged['ROI'] = merged['Lucro'] / merged['Investimento']
            
            # --- DASHBOARD VISUAL (Métricas de Topo) ---
            inv_t = merged['Investimento'].sum()
            rec_t = merged['Receita (BRL)'].sum()
            luc_t = rec_t - inv_t
            roi_t = luc_t / inv_t if inv_t > 0 else 0

            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Investimento Total", f"R$ {inv_t:,.2f}")
            col_m2.metric("Receita Total", f"R$ {rec_t:,.2f}")
            col_m3.metric("Lucro Líquido", f"R$ {luc_t:,.2f}", delta=f"R$ {luc_t:,.2f}")
            col_m4.metric("ROI Geral", f"{roi_t:.2%}", delta=f"{roi_t:.2%}")

            st.markdown("---")
            st.subheader("📋 Detalhamento por Campanha")
            
            # --- TABELA ESTILIZADA (Visual Premium) ---
            df_styled = merged.style.format({
                'Investimento': 'R$ {:,.2f}',
                'Receita (USD)': '$ {:,.2f}',
                'Receita (BRL)': 'R$ {:,.2f}',
                'Lucro': 'R$ {:,.2f}',
                'ROI': '{:.2%}'
            }).map(color_negative_red, subset=['Lucro', 'ROI']) # Correção do erro applymap -> map
            
            st.dataframe(df_styled, use_container_width=True, height=450)

            # --- LÓGICA DE PERSISTÊNCIA (Google Sheets) ---
            if st.button("💾 Salvar no Google Sheets"):
                client = get_gspread_client()
                sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
                
                # Previne duplicatas normalizando as datas da planilha
                coluna_datas = sheet.col_values(1)
                datas_norm = [pd.to_datetime(d).strftime('%Y-%m-%d') if d != 'Data_Ref' else d for d in coluna_datas]
                
                if data_str in datas_norm:
                    st.session_state.confirmar_salvamento = True
                else:
                    new_rows = [[data_str, r['Campanha'].upper(), r['Investimento'], r['Receita (USD)'], 
                                 r['Receita (BRL)'], r['Lucro'], r['ROI']] for _, r in merged.iterrows()]
                    sheet.append_rows(new_rows)
                    st.success("✅ Dados salvos com sucesso!")

            if st.session_state.confirmar_salvamento:
                st.warning(f"⚠️ Já existem dados para {data_str}. Deseja substituir os dados antigos?")
                c1, c2 = st.columns(2)
                if c1.button("Sim, Substituir"):
                    client = get_gspread_client()
                    sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
                    records = sheet.get_all_values()
                    
                    # Deleta registros daquela data (de baixo para cima)
                    for i, row in enumerate(reversed(records)):
                        idx = len(records) - i
                        try:
                            if pd.to_datetime(row[0]).strftime('%Y-%m-%d') == data_str:
                                sheet.delete_rows(idx)
                        except: continue
                    
                    new_rows = [[data_str, r['Campanha'].upper(), r['Investimento'], r['Receita (USD)'], 
                                 r['Receita (BRL)'], r['Lucro'], r['ROI']] for _, r in merged.iterrows()]
                    sheet.append_rows(new_rows)
                    st.session_state.confirmar_salvamento = False
                    st.success("🔄 Dados atualizados com sucesso!")
                    st.rerun()
                
                if c2.button("Cancelar"):
                    st.session_state.confirmar_salvamento = False
                    st.rerun()

        except Exception as e:
            st.error(f"Erro no processamento: {e}")

with tab2:
    st.subheader("🔍 Análise de Desempenho Histórico")
    
    # Filtro de Período
    opcao_data = st.selectbox("Selecione o Período", ["Hoje", "Ontem", "Últimos 7 dias", "Mês Atual", "Personalizado"])
    hoje = datetime.now().date()
    
    if opcao_data == "Hoje": start, end = hoje, hoje
    elif opcao_data == "Ontem": start = end = hoje - timedelta(days=1)
    elif opcao_data == "Últimos 7 dias": start, end = hoje - timedelta(days=7), hoje
    elif opcao_data == "Mês Atual": start, end = hoje.replace(day=1), hoje
    else:
        start = st.date_input("Início", hoje - timedelta(days=30))
        end = st.date_input("Fim", hoje)

    if st.button("Consultar Histórico"):
        client = get_gspread_client()
        sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
        data = pd.DataFrame(sheet.get_all_records())
        
        # Filtro Robusto: Trata datas e remove linhas manuais de "TOTAL" da planilha
        data['Data_Ref'] = pd.to_datetime(data['Data_Ref'], errors='coerce').dt.date
        df_f = data.dropna(subset=['Data_Ref'])
        df_f = df_f[df_f['Campanha'] != 'TOTAL'] # Evita somar o total da planilha
        
        mask = (df_f['Data_Ref'] >= start) & (df_f['Data_Ref'] <= end)
        df_final = df_f.loc[mask]

        if df_final.empty:
            st.warning("Nenhum dado encontrado para o período selecionado.")
        else:
            # Métricas Consolidadas do Período
            inv_h = df_final['Investimento'].sum()
            rec_h = df_final['Receita (BRL)'].sum()
            luc_h = rec_h - inv_h
            roi_h = luc_h / inv_h if inv_h > 0 else 0
            
            h1, h2, h3, h4 = st.columns(4)
            h1.metric("Investimento no Período", f"R$ {inv_h:,.2f}")
            h2.metric("Receita no Período", f"R$ {rec_h:,.2f}")
            h3.metric("Lucro no Período", f"R$ {luc_h:,.2f}", delta=f"R$ {luc_h:,.2f}")
            h4.metric("ROI Médio", f"{roi_h:.2%}", delta=f"{roi_h:.2%}")
            
            # Tabela Estilizada igual ao tab1
            st.dataframe(
                df_final.style.format({
                    'Investimento': 'R$ {:,.2f}', 'Receita (BRL)': 'R$ {:,.2f}',
                    'Lucro': 'R$ {:,.2f}', 'ROI': '{:.2%}'
                }).map(color_negative_red, subset=['Lucro', 'ROI']),
                use_container_width=True
            )
