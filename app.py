import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURAÇÕES INICIAIS ---
st.set_page_config(page_title="ROI Analyzer Premium", layout="wide")

def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

st.title("📊 Dashboard & Persistência de ROI")

# --- SIDEBAR ---
st.sidebar.header("Configurações")
data_referencia = st.sidebar.date_input("Data de Referência", datetime.now())
cambio = st.sidebar.number_input("Cotação do Dólar (R$)", value=5.00, step=0.01)

# Uploads
col_u1, col_u2 = st.columns(2)
with col_u1: file_meta = st.file_uploader("📁 Meta Ads", type=["csv"])
with col_u2: file_adx = st.file_uploader("📁 AdX", type=["csv"])

def clean_campaign_name(name):
    name = str(name).lower().strip().replace('"', '')
    if name.startswith(('ad', 'ca')): return name[2:]
    return name

# --- LÓGICA DE PROCESSAMENTO ---
if file_meta and file_adx:
    try:
        df_m = pd.read_csv(file_meta, sep=',', encoding='utf-8')
        df_a = pd.read_csv(file_adx, sep=';', encoding='utf-8')
        
        df_m['core'] = df_m['Nome do anúncio'].apply(clean_campaign_name)
        df_a['core'] = df_a['utm_campaign'].apply(clean_campaign_name)
        
        meta_g = df_m.groupby('core')['Valor usado (BRL)'].sum().reset_index()
        df_a['G_USD'] = df_a['Ganhos'].str.replace('$', '', regex=False).str.replace(',', '', regex=False).astype(float)
        adx_g = df_a.groupby('core')['G_USD'].sum().reset_index()
        
        merged = pd.merge(meta_g, adx_g, on='core', how='left').fillna(0)
        merged.columns = ['Campanha', 'Investimento', 'Receita (USD)']
        merged['Receita (BRL)'] = merged['Receita (USD)'] * cambio
        merged['Lucro'] = merged['Receita (BRL)'] - merged['Investimento']
        merged['ROI'] = merged['Lucro'] / merged['Investimento']
        merged = merged.sort_values('ROI', ascending=False)

        # Exibição básica
        st.dataframe(merged.style.format({'ROI': '{:.2%}'}), use_container_width=True, hide_index=True)

        # --- NOVA FUNCIONALIDADE: PERSISTÊNCIA COM VERIFICAÇÃO ---
        
        if st.button("💾 Salvar Fechamento no Google Sheets"):
            client = get_gspread_client()
            sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
            
            # 1. Verificar se a data já existe na Coluna A
            data_str = str(data_referencia)
            coluna_datas = sheet.col_values(1) # Pega toda a Coluna A
            
            if data_str in coluna_datas:
                # Avisar o usuário e pedir confirmação
                st.warning(f"⚠️ Atenção: Já existem dados salvos para a data {data_str}.")
                col_conf1, col_conf2 = st.columns(2)
                
                # Usamos botões de confirmação específicos
                if st.button("Sim, Desejo Atualizar (Sobrescrever)"):
                    with st.spinner("Removendo dados antigos e atualizando..."):
                        # Encontrar todas as linhas que contêm essa data e deletar
                        # Dica: Deletamos de baixo para cima para não errar o índice
                        records = sheet.get_all_values()
                        rows_to_delete = [i+1 for i, row in enumerate(records) if row[0] == data_str]
                        
                        for row_idx in reversed(rows_to_delete):
                            sheet.delete_rows(row_idx)
                        
                        # Salvar novos dados
                        new_rows = [[data_str, r['Campanha'].upper(), r['Investimento'], r['Receita (USD)'], 
                                     r['Receita (BRL)'], r['Lucro'], r['ROI']] for _, r in merged.iterrows()]
                        sheet.append_rows(new_rows)
                        st.success(f"✅ Dados de {data_str} atualizados com sucesso!")
                
                if st.button("Não, Cancelar Operação"):
                    st.info("Operação cancelada pelo usuário.")
            else:
                # Se não existe, salva direto
                with st.spinner("Salvando novos dados..."):
                    new_rows = [[data_str, r['Campanha'].upper(), r['Investimento'], r['Receita (USD)'], 
                                 r['Receita (BRL)'], r['Lucro'], r['ROI']] for _, r in merged.iterrows()]
                    sheet.append_rows(new_rows)
                    st.success(f"✅ Dados de {data_str} salvos com sucesso!")

    except Exception as e:
        st.error(f"Erro: {e}")
