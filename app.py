import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from io import BytesIO
from datetime import datetime, timedelta
import altair as alt

# 1. CONFIGURAÇÃO E ESTILO
st.set_page_config(page_title="ROI Analyzer Premium", layout="wide")

def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

st.title("📊 ROI Intelligence System")

# Inicializar estados de confirmação
if 'confirmar_salvamento' not in st.session_state:
    st.session_state.confirmar_salvamento = False

# Criando as Abas
tab1, tab2 = st.tabs(["🚀 Processamento Diário", "📈 Consulta Histórica"])

with tab1:
    st.sidebar.header("Configurações")
    data_referencia = st.sidebar.date_input("Data de Referência", datetime.now())
    cambio = st.sidebar.number_input("Cotação do Dólar (R$)", value=5.00, step=0.01)
    data_str = data_referencia.strftime('%Y-%m-%d')

    col_u1, col_u2 = st.columns(2)
    with col_u1: file_meta = st.file_uploader("📁 Meta Ads", type=["csv"])
    with col_u2: file_adx = st.file_uploader("📁 AdX", type=["csv"])

    if file_meta and file_adx:
        try:
            # ... (Lógica de processamento igual à anterior) ...
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
            
            st.dataframe(merged.style.format({'ROI': '{:.2%}'}), use_container_width=True)

            # LÓGICA DE SALVAMENTO CORRIGIDA (SEM BOTÕES ANINHADOS)
            if st.button("💾 Salvar no Google Sheets"):
                client = get_gspread_client()
                sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
                
                # Normalizar datas para comparação (evita erro de formato BR vs ISO)
                coluna_datas = sheet.col_values(1)
                datas_normalizadas = [pd.to_datetime(d).strftime('%Y-%m-%d') if d != 'Data_Ref' else d for d in coluna_datas]
                
                if data_str in datas_normalizadas:
                    st.session_state.confirmar_salvamento = True
                else:
                    new_rows = [[data_str, r['Campanha'].upper(), r['Investimento'], r['Receita (USD)'], 
                                 r['Receita (BRL)'], r['Lucro'], r['ROI']] for _, r in merged.iterrows()]
                    sheet.append_rows(new_rows)
                    st.success("✅ Dados salvos com sucesso!")

            if st.session_state.confirmar_salvamento:
                st.warning(f"⚠️ Já existem dados para {data_str}. Deseja sobrescrever?")
                col_c1, col_c2 = st.columns(2)
                if col_c1.button("Sim, Substituir"):
                    client = get_gspread_client()
                    sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
                    records = sheet.get_all_values()
                    # Deletar linhas antigas de trás para frente
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
                    st.success("🔄 Dados atualizados!")
                    st.rerun()
                
                if col_c2.button("Cancelar"):
                    st.session_state.confirmar_salvamento = False
                    st.rerun()

        except Exception as e:
            st.error(f"Erro: {e}")

with tab2:
    st.subheader("🔍 Análise de Desempenho por Período")
    
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
        
        # Filtro Robusto: Converte datas e remove linhas "TOTAL"
        data['Data_Ref'] = pd.to_datetime(data['Data_Ref'], errors='coerce').dt.date
        df_filtered = data.dropna(subset=['Data_Ref'])
        
        # REMOVE LINHAS QUE POSSAM SER TOTAIS (Para não dobrar o valor)
        df_filtered = df_filtered[df_filtered['Campanha'] != 'TOTAL']
        
        mask = (df_filtered['Data_Ref'] >= start) & (df_filtered['Data_Ref'] <= end)
        df_final = df_filtered.loc[mask]

        if df_final.empty:
            st.warning("Sem dados para este período.")
        else:
            # Métricas
            inv = df_final['Investimento'].sum()
            rec = df_final['Receita (BRL)'].sum()
            st.columns(3)[0].metric("Investimento Total", f"R$ {inv:,.2f}")
            st.columns(3)[1].metric("Receita Total", f"R$ {rec:,.2f}")
            st.columns(3)[2].metric("ROI", f"{(rec-inv)/inv:.2%}")
            
            # Gráfico de Evolução (Linhas)
            evol = df_final.groupby('Data_Ref').agg({'Investimento':'sum', 'Receita (BRL)':'sum'}).reset_index()
            st.line_chart(evol.set_index('Data_Ref'))
