import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# 1. CONFIGURAÇÕES DE PÁGINA E ESTILO VISUAL PREMIUM
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

st.title("📊 ROI Intelligence System")

if 'confirmar_salvamento' not in st.session_state:
    st.session_state.confirmar_salvamento = False

tab1, tab2 = st.tabs(["🚀 Processamento Diário", "📈 Consulta Histórica"])

with tab1:
    # --- BARRA LATERAL ---
    st.sidebar.header("Configurações")
    data_referencia = st.sidebar.date_input("Data de Referência", datetime.now())
    cambio = st.sidebar.number_input("Cotação do Dólar (R$)", value=5.00, step=0.01)
    data_str = data_referencia.strftime('%Y-%m-%d')

    col_u1, col_u2 = st.columns(2)
    with col_u1: file_meta = st.file_uploader("📁 Meta Ads", type=["csv"])
    with col_u2: file_adx = st.file_uploader("📁 AdX", type=["csv"])

    if file_meta and file_adx:
        try:
            # 2. PROCESSAMENTO DE DADOS
            df_m = pd.read_csv(file_meta, sep=',', encoding='utf-8')
            df_a = pd.read_csv(file_adx, sep=';', encoding='utf-8')
            
            def clean_name(n):
                n = str(n).lower().strip().replace('"', '')
                return n[2:] if n.startswith(('ad', 'ca')) else n

            df_m['core'] = df_m['Nome do anúncio'].apply(clean_name)
            df_a['core'] = df_a['utm_campaign'].apply(clean_name)
            
            meta_g = df_m.groupby('core')['Valor usado (BRL)'].sum().reset_index()
            # Limpeza robusta da moeda AdX
            df_a['G_USD'] = df_a['Ganhos'].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False).astype(float)
            adx_g = df_a.groupby('core')['G_USD'].sum().reset_index()
            
            merged = pd.merge(meta_g, adx_g, on='core', how='left').fillna(0)
            merged.columns = ['Campanha', 'Investimento', 'Receita (USD)']
            merged['Receita (BRL)'] = merged['Receita (USD)'] * cambio
            merged['Lucro'] = merged['Receita (BRL)'] - merged['Investimento']
            merged['ROI'] = merged['Lucro'] / merged['Investimento']
            
            # --- DASHBOARD DE MÉTRICAS ---
            inv_t, rec_t = merged['Investimento'].sum(), merged['Receita (BRL)'].sum()
            luc_t = rec_t - inv_t
            roi_t = luc_t / inv_t if inv_t > 0 else 0

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Investimento Total", f"R$ {inv_t:,.2f}")
            m2.metric("Receita Total", f"R$ {rec_t:,.2f}")
            m3.metric("Lucro Líquido", f"R$ {luc_t:,.2f}", delta=f"R$ {luc_t:,.2f}")
            m4.metric("ROI Geral", f"{roi_t:.2%}", delta=f"{roi_t:.2%}")

            st.markdown("---")
            st.subheader("📋 Detalhamento por Campanha")
            
            df_styled = merged.style.format({
                'Investimento': 'R$ {:,.2f}', 'Receita (USD)': '$ {:,.2f}',
                'Receita (BRL)': 'R$ {:,.2f}', 'Lucro': 'R$ {:,.2f}', 'ROI': '{:.2%}'
            }).map(color_negative_red, subset=['Lucro', 'ROI'])
            
            st.dataframe(df_styled, use_container_width=True, height=450)

            # --- SALVAMENTO CORRIGIDO (Evita multiplicação por 100) ---
            if st.button("💾 Salvar no Google Sheets"):
                client = get_gspread_client()
                sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
                
                # Prepara linhas forçando strings com vírgula se a sua planilha for pt-BR
                # Ou usa USER_ENTERED para que o Sheets interprete o float nativo corretamente
                new_rows = []
                for _, r in merged.iterrows():
                    new_rows.append([
                        data_str, 
                        r['Campanha'].upper(), 
                        float(r['Investimento']), 
                        float(r['Receita (USD)']), 
                        float(r['Receita (BRL)']), 
                        float(r['Lucro']), 
                        float(r['ROI'])
                    ])
                
                # O segredo está aqui: value_input_option='USER_ENTERED'
                sheet.append_rows(new_rows, value_input_option='USER_ENTERED')
                st.success("✅ Dados salvos com sucesso!")

        except Exception as e:
            st.error(f"Erro no processamento: {e}")

with tab2:
    st.subheader("🔍 Análise de Desempenho Histórico")
    
    if st.button("Consultar Histórico"):
        client = get_gspread_client()
        sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
        
        # Lê os dados e força conversão numérica correta
        raw_data = sheet.get_all_records()
        if raw_data:
            df_h = pd.DataFrame(raw_data)
            
            # Converte colunas para numérico, tratando possíveis erros de formatação do Sheets
            cols_to_fix = ['Investimento', 'Receita (USD)', 'Receita (BRL)', 'Lucro', 'ROI']
            for col in cols_to_fix:
                df_h[col] = pd.to_numeric(df_h[col], errors='coerce').fillna(0)

            # Dashboard do Histórico
            inv_h, rec_h = df_h['Investimento'].sum(), df_h['Receita (BRL)'].sum()
            luc_h = rec_h - inv_h
            roi_h = luc_h / inv_h if inv_h > 0 else 0
            
            h1, h2, h3, h4 = st.columns(4)
            h1.metric("Investimento Acumulado", f"R$ {inv_h:,.2f}")
            h2.metric("Receita Acumulada", f"R$ {rec_h:,.2f}")
            h3.metric("Lucro Líquido", f"R$ {luc_h:,.2f}")
            h4.metric("ROI Médio", f"{roi_h:.2%}")
            
            st.dataframe(
                df_h.style.format({
                    'Investimento': 'R$ {:,.2f}', 'Receita (BRL)': 'R$ {:,.2f}',
                    'Lucro': 'R$ {:,.2f}', 'ROI': '{:.2%}'
                }).map(color_negative_red, subset=['Lucro', 'ROI']),
                use_container_width=True
            )
