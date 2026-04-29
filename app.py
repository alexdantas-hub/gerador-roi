import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from io import BytesIO
from datetime import datetime, timedelta
import altair as alt # Biblioteca para gráficos mais bonitos

# 1. CONFIGURAÇÃO E ESTILO PREMIUM
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

# --- INÍCIO DO APP ---
st.title("📊 ROI Intelligence System")

# Criando as Abas
tab1, tab2 = st.tabs(["🚀 Processamento Diário", "📈 Consulta Histórica"])

with tab1:
    # --- TODO O CÓDIGO QUE JÁ TEMOS VAI AQUI (Simplificado para brevidade) ---
    st.subheader("Subir novos dados")
    # (Mantenha aqui a sua lógica de upload e o botão de salvar que já funciona)
    st.info("Utilize esta aba para processar os arquivos CSV do Meta e AdX e salvar no Google Sheets.")

with tab2:
    st.subheader("🔍 Análise de Desempenho por Período")
    
    # Filtros de Data
    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        opcao_data = st.selectbox("Selecione o Período", [
            "Hoje", "Ontem", "Últimos 7 dias", "Últimos 15 dias", 
            "Mês Atual", "Mês Passado", "Personalizado"
        ])
        
        hoje = datetime.now().date()
        if opcao_data == "Hoje": start, end = hoje, hoje
        elif opcao_data == "Ontem": start = end = hoje - timedelta(days=1)
        elif opcao_data == "Últimos 7 dias": start, end = hoje - timedelta(days=7), hoje
        elif opcao_data == "Últimos 15 dias": start, end = hoje - timedelta(days=15), hoje
        elif opcao_data == "Mês Atual": start, end = hoje.replace(day=1), hoje
        elif opcao_data == "Mês Passado":
            last_month = hoje.replace(day=1) - timedelta(days=1)
            start, end = last_month.replace(day=1), last_month
        else:
            start = st.date_input("Início", hoje - timedelta(days=30))
            end = st.date_input("Fim", hoje)

    # Botão para Carregar Dados
    if st.button("Consultar Histórico"):
        with st.spinner("Buscando dados no Google Sheets..."):
            client = get_gspread_client()
            sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
            data = pd.DataFrame(sheet.get_all_records())
            
            # Converter coluna de data para o formato datetime do Pandas
            data['Data_Ref'] = pd.to_datetime(data['Data_Ref']).dt.date
            
            # Filtrar pelo período selecionado
            mask = (data['Data_Ref'] >= start) & (data['Data_Ref'] <= end)
            df_filtered = data.loc[mask]

            if df_filtered.empty:
                st.warning("Nenhum dado encontrado para este período.")
            else:
                # Métricas Agregadas
                t_inv = df_filtered['Investimento'].sum()
                t_rec = df_filtered['Receita (BRL)'].sum()
                t_luc = t_rec - t_inv
                t_roi = t_luc / t_inv if t_inv > 0 else 0

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Investimento no Período", f"R$ {t_inv:,.2f}")
                m2.metric("Receita no Período", f"R$ {t_rec:,.2f}")
                m3.metric("Lucro no Período", f"R$ {t_luc:,.2f}")
                m4.metric("ROI Médio", f"{t_roi:.2%}")

                # --- GRÁFICOS ---
                st.markdown("### 📊 Visualização de Dados")
                g1, g2 = st.columns(2)
                
                with g1:
                    st.write("**Evolução da Receita vs Investimento**")
                    evolucao = df_filtered.groupby('Data_Ref').agg({'Investimento': 'sum', 'Receita (BRL)': 'sum'}).reset_index()
                    st.line_chart(evolucao.set_index('Data_Ref'))

                with g2:
                    st.write("**ROI por Campanha (Média do Período)**")
                    # Agrupar por campanha para ver quem performou melhor no total
                    per_camp = df_filtered.groupby('Campanha').agg({
                        'Investimento': 'sum', 
                        'Receita (BRL)': 'sum',
                        'Lucro': 'sum'
                    }).reset_index()
                    per_camp['ROI'] = per_camp['Lucro'] / per_camp['Investimento']
                    
                    # Gráfico de Barras com Altair para cores condicionais
                    chart = alt.Chart(per_camp).mark_bar().encode(
                        x='Campanha:N',
                        y='ROI:Q',
                        color=alt.condition(
                            alt.datum.ROI > 0,
                            alt.value('#27ae60'), # Verde
                            alt.value('#c0392b')  # Vermelho
                        )
                    ).properties(height=300)
                    st.altair_chart(chart, use_container_width=True)

                # --- TABELA DETALHADA ---
                st.markdown("### 📋 Resumo Consolidado do Período")
                per_camp_display = per_camp.sort_values('ROI', ascending=False)
                st.dataframe(
                    per_camp_display.style.format({
                        'Investimento': 'R$ {:,.2f}',
                        'Receita (BRL)': 'R$ {:,.2f}',
                        'Lucro': 'R$ {:,.2f}',
                        'ROI': '{:.2%}'
                    }),
                    use_container_width=True, hide_index=True
                )
