import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from io import BytesIO
from datetime import datetime
from openpyxl.styles import Font, Alignment, PatternFill

# Configuração e Estilo
st.set_page_config(page_title="ROI Analyzer Premium", layout="wide")
st.markdown("<style>.stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }</style>", unsafe_allow_html=True)

# Conexão com Google Sheets
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

st.title("📊 Dashboard & Persistência de ROI")

# Sidebar
st.sidebar.header("Configurações")
data_referencia = st.sidebar.date_input("Data de Referência (Dados de Ontem)", datetime.now())
cambio = st.sidebar.number_input("Cotação do Dólar (R$)", value=5.00, step=0.10)

col_u1, col_u2 = st.columns(2)
with col_u1: file_meta = st.file_uploader("📁 Meta Ads", type=["csv"])
with col_u2: file_adx = st.file_uploader("📁 AdX", type=["csv"])

def clean_campaign_name(name):
    name = str(name).lower().strip().replace('"', '')
    if name.startswith(('ad', 'ca')): return name[2:]
    return name

if file_meta and file_adx:
    try:
        # Processamento
        df_m = pd.read_csv(file_meta)
        df_a = pd.read_csv(file_adx, sep=';')
        
        df_m['core'] = df_m['Nome do anúncio'].apply(clean_campaign_name)
        df_a['core'] = df_a['utm_campaign'].apply(clean_campaign_name)
        
        meta_g = df_m.groupby('core')['Valor usado (BRL)'].sum().reset_index()
        df_a['Ganhos_Clean'] = df_a['Ganhos'].str.replace('$', '', regex=False).str.replace(',', '', regex=False).astype(float)
        adx_g = df_a.groupby('core')['Ganhos_Clean'].sum().reset_index()
        
        merged = pd.merge(meta_g, adx_g, on='core', how='inner')
        merged.columns = ['Campanha', 'Investimento', 'USD']
        merged['Receita'] = merged['USD'] * cambio
        merged['Lucro'] = merged['Receita'] - merged['Investimento']
        merged['ROI'] = merged['Lucro'] / merged['Investimento']
        merged = merged.sort_values('ROI', ascending=False)

        # Dashboard em Tela
        t_inv, t_rec = merged['Investimento'].sum(), merged['Receita'].sum()
        t_luc = t_rec - t_inv
        t_roi = t_luc / t_inv if t_inv > 0 else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Investimento Total", f"R$ {t_inv:,.2f}")
        m2.metric("Receita Total", f"R$ {t_rec:,.2f}")
        m3.metric("Lucro Líquido", f"R$ {t_luc:,.2f}")
        m4.metric("ROI Geral", f"{t_roi:.2%}")

        st.dataframe(merged[['Campanha', 'Investimento', 'Receita', 'Lucro', 'ROI']].style.format({'Investimento': 'R$ {:,.2f}', 'Receita': 'R$ {:,.2f}', 'Lucro': 'R$ {:,.2f}', 'ROI': '{:.2%}'}), use_container_width=True, hide_index=True)

        # BOTÃO DE PERSISTÊNCIA
        if st.button("💾 Salvar Fechamento do Dia no Google Sheets"):
            client = get_gspread_client()
            sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
            
            # Preparar dados para o Sheets
            data_to_save = []
            for _, row in merged.iterrows():
                data_to_save.append([
                    str(data_referencia), 
                    row['Campanha'].upper(), 
                    row['Investimento'], 
                    row['Receita'], 
                    row['Lucro'], 
                    row['ROI']
                ])
            
            # Remover dados antigos da mesma data para evitar duplicidade
            all_data = sheet.get_all_values()
            if len(all_data) > 1:
                # Lógica simples: deletar e sobrescrever se a data bater
                # Para simplificar agora, vamos apenas adicionar ao final
                pass
            
            sheet.append_rows(data_to_save)
            st.success(f"Dados salvos com sucesso para {data_referencia}!")

    except Exception as e:
        st.error(f"Erro: {e}")
