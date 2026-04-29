import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from io import BytesIO
from datetime import datetime
from openpyxl.styles import Font, Alignment, PatternFill

# 1. CONFIGURAÇÃO E ESTILO PREMIUM
st.set_page_config(page_title="ROI Analyzer Premium", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { background-color: #2c3e50; color: white; border-radius: 8px; width: 100%; font-weight: bold; }
    .stDownloadButton>button { background-color: #27ae60; color: white; border-radius: 8px; width: 100%; font-weight: bold; }
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

# 3. LÓGICA DE PROCESSAMENTO
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

        # 4. DASHBOARD VISUAL (MÉTRICAS)
        t_inv, t_rec_brl = merged['Investimento'].sum(), merged['Receita (BRL)'].sum()
        t_luc = t_rec_brl - t_inv
        t_roi = t_luc / t_inv if t_inv > 0 else 0

        st.subheader("📌 Resumo Consolidado")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Investimento Total", f"R$ {t_inv:,.2f}")
        m2.metric("Receita Total", f"R$ {t_rec_brl:,.2f}")
        m3.metric("Lucro Líquido", f"R$ {t_luc:,.2f}", delta=f"{t_luc:,.2f}")
        m4.metric("ROI Geral", f"{t_roi:.2%}")

        st.markdown("---")

        # 5. TABELA PREMIUM ESTILIZADA
        st.subheader("📋 Detalhamento por Campanha")
        
        def color_negative_red(val):
            color = '#c0392b' if val < 0 else '#27ae60'
            return f'color: {color}; font-weight: bold'

        df_display = merged[['Campanha', 'Investimento', 'Receita (USD)', 'Receita (BRL)', 'Lucro', 'ROI']].copy()
        df_display['Campanha'] = df_display['Campanha'].str.upper()

        st.dataframe(
            df_display.style.format({
                'Investimento': 'R$ {:,.2f}',
                'Receita (USD)': '$ {:,.2f}',
                'Receita (BRL)': 'R$ {:,.2f}',
                'Lucro': 'R$ {:,.2f}',
                'ROI': '{:.2%}'
            }).map(color_negative_red, subset=['Lucro', 'ROI']),
            use_container_width=True,
            height=450,
            hide_index=True
        )

        st.markdown("---")

        # 6. AÇÕES: SALVAR (COM VERIFICAÇÃO) E EXPORTAR EXCEL
        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            if st.button("💾 Salvar Fechamento no Google Sheets"):
                client = get_gspread_client()
                sheet = client.open_by_key(st.secrets["spreadsheet"]["id"]).worksheet("Historico")
                
                data_str = str(data_referencia)
                coluna_datas = sheet.col_values(1)
                
                if data_str in coluna_datas:
                    st.warning(f"⚠️ Já existem dados para {data_str}. Deseja sobrescrever?")
                    c1, c2 = st.columns(2)
                    if c1.button("Confirmar Sobrescrita"):
                        with st.spinner("Atualizando histórico..."):
                            records = sheet.get_all_values()
                            rows_to_delete = [i+1 for i, row in enumerate(records) if row[0] == data_str]
                            for row_idx in reversed(rows_to_delete):
                                sheet.delete_rows(row_idx)
                            
                            new_rows = [[data_str, r['Campanha'].upper(), r['Investimento'], r['Receita (USD)'], 
                                         r['Receita (BRL)'], r['Lucro'], r['ROI']] for _, r in merged.iterrows()]
                            sheet.append_rows(new_rows)
                            st.success(f"✅ Dados de {data_str} atualizados!")
                    if c2.button("Cancelar"):
                        st.info("Ação cancelada.")
                else:
                    with st.spinner("Salvando novos dados..."):
                        new_rows = [[data_str, r['Campanha'].upper(), r['Investimento'], r['Receita (USD)'], 
                                     r['Receita (BRL)'], r['Lucro'], r['ROI']] for _, r in merged.iterrows()]
                        sheet.append_rows(new_rows)
                        st.success(f"✅ Dados de {data_str} salvos!")

        with col_btn2:
            # Exportação Excel Formatada (Recuperada)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_ex = df_display.copy()
                df_ex.to_excel(writer, index=False, sheet_name='ROI', startrow=4)
                ws = writer.sheets['ROI']
                azul, cinza = "2C3E50", "7F8C8D"
                ws.merge_cells('A1:F1')
                ws['A1'] = "Relatório de Performance ROI"
                ws['A1'].font = Font(bold=True, size=16, color=azul)
                ws['A1'].alignment = Alignment(horizontal='center')
                ws.merge_cells('A2:F2')
                ws['A2'] = f"Referência: {data_str} | Câmbio: R$ {cambio:,.2f}"
                ws['A2'].alignment = Alignment(horizontal='center')
                
                for cell in ws[5]:
                    cell.font = Font(bold=True, color="FFFFFF")
                    cell.fill = PatternFill(start_color=azul, end_color=azul, fill_type="solid")

            st.download_button("📥 Baixar Excel Formatado", output.getvalue(), f"ROI_{data_str}.xlsx")

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
