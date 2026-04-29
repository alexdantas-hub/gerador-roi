import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from io import BytesIO
from datetime import datetime
from openpyxl.styles import Font, Alignment, PatternFill

# 1. CONFIGURAÇÃO E ESTILO
st.set_page_config(page_title="ROI Analyzer Premium", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { background-color: #2c3e50; color: white; border-radius: 8px; width: 100%; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

st.title("📊 Dashboard & Persistência de ROI")
st.markdown("---")

# 2. SIDEBAR E INPUTS
st.sidebar.header("Configurações")
data_referencia = st.sidebar.date_input("Data de Referência", datetime.now())
cambio = st.sidebar.number_input("Cotação do Dólar (R$)", value=5.00, step=0.01)

col_u1, col_u2 = st.columns(2)
with col_u1:
    file_meta = st.file_uploader("📁 Arquivo Meta Ads (Gastos)", type=["csv"])
with col_u2:
    file_adx = st.file_uploader("📁 Arquivo AdX (Receita)", type=["csv"])

def clean_campaign_name(name):
    name = str(name).lower().strip().replace('"', '')
    if name.startswith(('ad', 'ca')): return name[2:]
    return name

if file_meta and file_adx:
    try:
        # 3. PROCESSAMENTO
        df_m = pd.read_csv(file_meta, sep=',', encoding='utf-8')
        df_a = pd.read_csv(file_adx, sep=';', encoding='utf-8')
        
        df_m['core'] = df_m['Nome do anúncio'].apply(clean_campaign_name)
        df_a['core'] = df_a['utm_campaign'].apply(clean_campaign_name)
        
        meta_g = df_m.groupby('core')['Valor usado (BRL)'].sum().reset_index()
        df_a['G_USD'] = df_a['Ganhos'].str.replace('$', '', regex=False).str.replace(',', '', regex=False).astype(float)
        adx_g = df_a.groupby('core')['G_USD'].sum().reset_index()
        
        # Cruzamento (Left Join para não perder dados do Meta)
        merged = pd.merge(meta_g, adx_g, on='core', how='left').fillna(0)
        merged.columns = ['Campanha', 'Investimento', 'Receita (USD)']
        
        merged['Receita (BRL)'] = merged['Receita (USD)'] * cambio
        merged['Lucro'] = merged['Receita (BRL)'] - merged['Investimento']
        merged['ROI'] = merged['Lucro'] / merged['Investimento']
        merged = merged.sort_values('ROI', ascending=False)

        # 4. DASHBOARD VISUAL
        tot_inv, tot_rec_brl = merged['Investimento'].sum(), merged['Receita (BRL)'].sum()
        tot_luc = tot_rec_brl - tot_inv
        tot_roi = tot_luc / tot_inv if tot_inv > 0 else 0

        st.subheader("📌 Resumo Consolidado")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Investimento Total", f"R$ {tot_inv:,.2f}")
        m2.metric("Receita Total", f"R$ {tot_rec_brl:,.2f}")
        m3.metric("Lucro Líquido", f"R$ {tot_luc:,.2f}", delta=f"{tot_luc:,.2f}")
        m4.metric("ROI Geral", f"{tot_roi:.2%}")

        st.markdown("---")

        # 5. TABELA COM COLUNA USD INCLUÍDA
        st.subheader("📋 Detalhamento por Campanha")
        
        df_display = merged[['Campanha', 'Investimento', 'Receita (USD)', 'Receita (BRL)', 'Lucro', 'ROI']].copy()
        df_display['Campanha'] = df_display['Campanha'].str.upper()

        st.dataframe(
            df_display.style.format({
                'Investimento': 'R$ {:,.2f}',
                'Receita (USD)': '$ {:,.2f}',
                'Receita (BRL)': 'R$ {:,.2f}',
                'Lucro': 'R$ {:,.2f}',
                'ROI': '{:.2%}'
            }).map(lambda x: f"color: {'#c0392b' if x < 0 else '#27ae60'}; font-weight: bold", subset=['Lucro', 'ROI']),
            use_container_width=True,
            height=450,
            hide_index=True
        )

        # 6. BOTÃO SALVAR (GOOGLE SHEETS)
        if st.button("💾 Salvar Fechamento no Google Sheets"):
            with st.spinner("Enviando dados..."):
                client = get_gspread_client()
                sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
                
                # Prepara as linhas para salvar (incluindo o USD agora)
                rows = []
                for _, r in merged.iterrows():
                    rows.append([
                        str(data_referencia), 
                        r['Campanha'].upper(), 
                        r['Investimento'], 
                        r['Receita (USD)'], # Adicionado ao histórico
                        r['Receita (BRL)'], 
                        r['Lucro'], 
                        r['ROI']
                    ])
                
                sheet.append_rows(rows)
                st.success(f"✅ Dados de {data_referencia} salvos com sucesso!")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
