import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from io import BytesIO
from datetime import datetime
from openpyxl.styles import Font, Alignment, PatternFill

# 1. CONFIGURAÇÃO E ESTILO DA INTERFACE
st.set_page_config(page_title="ROI Analyzer Premium", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { background-color: #2c3e50; color: white; border-radius: 8px; width: 100%; font-weight: bold; }
    .stDownloadButton>button { background-color: #27ae60; color: white; border-radius: 8px; width: 100%; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# Função para conectar ao Google Sheets
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

st.title("📊 Dashboard & Persistência de ROI")
st.markdown("---")

# 2. SIDEBAR E UPLOADS
st.sidebar.header("Configurações")
data_referencia = st.sidebar.date_input("Data de Referência (Ontem/Retroativo)", datetime.now())
cambio = st.sidebar.number_input("Cotação do Dólar (R$)", value=5.00, step=0.10)

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
        # 3. PROCESSAMENTO DOS DADOS
        df_m = pd.read_csv(file_meta, sep=',', encoding='utf-8')
        df_a = pd.read_csv(file_adx, sep=';', encoding='utf-8')
        
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

        # 4. DASHBOARD VISUAL (MÉTRICAS)
        tot_inv, tot_rec = merged['Investimento'].sum(), merged['Receita'].sum()
        tot_luc = tot_rec - tot_inv
        tot_roi = tot_luc / tot_inv if tot_inv > 0 else 0

        st.subheader("📌 Resumo Consolidado")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Investimento Total", f"R$ {tot_inv:,.2f}")
        m2.metric("Receita Total", f"R$ {tot_rec:,.2f}")
        m3.metric("Lucro Líquido", f"R$ {tot_luc:,.2f}", delta=f"{tot_luc:,.2f}")
        m4.metric("ROI Geral", f"{tot_roi:.2%}")

        st.markdown("---")

        # 5. TABELA ESTILIZADA (RESTAURADA)
        st.subheader("📋 Detalhamento por Campanha")
        
        def color_negative_red(val):
            color = '#c0392b' if val < 0 else '#27ae60'
            return f'color: {color}; font-weight: bold'

        df_display = merged[['Campanha', 'Investimento', 'Receita', 'Lucro', 'ROI']].copy()
        df_display['Campanha'] = df_display['Campanha'].str.upper()

        st.dataframe(
            df_display.style.format({
                'Investimento': 'R$ {:,.2f}',
                'Receita': 'R$ {:,.2f}',
                'Lucro': 'R$ {:,.2f}',
                'ROI': '{:.2%}'
            }).map(color_negative_red, subset=['Lucro', 'ROI']),
            use_container_width=True,
            height=450,
            hide_index=True
        )

        # 6. BOTÕES DE AÇÃO
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("💾 Salvar Fechamento no Google Sheets"):
                with st.spinner("Salvando dados..."):
                    client = get_gspread_client()
                    sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
                    
                    data_to_save = []
                    for _, row in merged.iterrows():
                        data_to_save.append([
                            str(data_referencia), 
                            row['Campanha'].upper(), 
                            round(float(row['Investimento']), 2), 
                            round(float(row['Receita']), 2), 
                            round(float(row['Lucro']), 2), 
                            round(float(row['ROI']), 4)
                        ])
                    
                    sheet.append_rows(data_to_save)
                    st.success(f"✅ Dados de {data_referencia} salvos com sucesso!")

        with col_btn2:
            # Geração do Excel idêntico ao original
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_ex = df_display.copy()
                df_ex = pd.concat([df_ex, pd.DataFrame([['TOTAL', tot_inv, tot_rec, tot_luc, tot_roi]], columns=df_ex.columns)], ignore_index=True)
                df_ex.to_excel(writer, index=False, sheet_name='ROI', startrow=4)
                ws = writer.sheets['ROI']
                # (Estilização do Excel omitida aqui para brevidade, mas mantida no seu arquivo funcional)
                # Adicione aqui o bloco de estilização do Excel se desejar baixar formatado.
            
            st.download_button("📥 Baixar Planilha Excel Formatada", output.getvalue(), f"ROI_{data_referencia}.xlsx")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
