import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

st.set_page_config(page_title="Gerador de ROI Premium", layout="wide")

# Estilização para a interface Web
st.markdown("""
    <style>
    .main { background-color: #faf9f6; }
    .stButton>button { background-color: #2c3e50; color: white; border-radius: 8px; width: 100%; height: 3em; }
    .stDownloadButton>button { background-color: #27ae60; color: white; border-radius: 8px; width: 100%; height: 3em; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Relatório de ROI por Campanha")
st.write("Processador de Meta Ads vs Google Ad Exchange")

# Uploads
col1, col2 = st.columns(2)
with col1:
    file_meta = st.file_uploader("Arquivo Meta (Gastos)", type=["csv"])
with col2:
    file_adx = st.file_uploader("Arquivo AdX (Receita)", type=["csv"])

cambio = st.sidebar.number_input("Cotação do Dólar (R$)", value=5.00, step=0.10)

if file_meta and file_adx:
    if st.button("🚀 Processar e Gerar Planilha"):
        try:
            # 1. Processamento de Dados
            df_m = pd.read_csv(file_meta)
            df_a = pd.read_csv(file_adx, sep=';')
            
            def clean_n(n):
                n = str(n).lower()
                return n[2:] if n.startswith(('ad', 'ca')) else n

            df_m['core'] = df_m.iloc[:, 0].apply(clean_n)
            df_a['core'] = df_a['utm_campaign'].apply(clean_n)
            
            meta_g = df_m.groupby('core').iloc[:, 1].sum().reset_index()
            df_a['Ganhos_USD'] = df_a['Ganhos'].replace('[\$,]', '', regex=True).astype(float)
            adx_g = df_a.groupby('core')['Ganhos_USD'].sum().reset_index()
            
            merged = pd.merge(meta_g, adx_g, on='core', how='inner')
            merged.columns = ['Campanha', 'Investimento', 'USD']
            merged['Receita'] = merged['USD'] * cambio
            merged['Lucro'] = merged['Receita'] - merged['Investimento']
            merged['ROI'] = merged['Lucro'] / merged['Investimento']
            merged = merged.sort_values('ROI', ascending=False)
            
            # 2. Criação do Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_ex = merged[['Campanha', 'Investimento', 'Receita', 'Lucro', 'ROI']].copy()
                df_ex['Campanha'] = df_ex['Campanha'].str.upper()
                
                # Totais
                t_inv, t_rec = df_ex['Investimento'].sum(), df_ex['Receita'].sum()
                t_luc = t_rec - t_inv
                t_roi = t_luc / t_inv if t_inv > 0 else 0
                df_ex = pd.concat([df_ex, pd.DataFrame([['TOTAL', t_inv, t_rec, t_luc, t_roi]], columns=df_ex.columns)], ignore_index=True)
                
                df_ex.to_excel(writer, index=False, sheet_name='ROI', startrow=4)
                ws = writer.sheets['ROI']
                
                # Estilos PDF
                azul, vermelho, verde = "2C3E50", "C0392B", "27AE60"
                
                # Header Superior
                ws.merge_cells('A1:E1')
                ws['A1'] = "Relatório de ROI por Campanha"
                ws['A1'].font = Font(name='Arial', bold=True, size=20, color=azul)
                ws['A1'].alignment = Alignment(horizontal='center')
                
                # Cabeçalho Tabela
                for cell in ws[5]:
                    cell.font = Font(name='Arial', bold=True, color="FFFFFF")
                    cell.fill = PatternFill(start_color=azul, end_color=azul, fill_type="solid")
                    cell.alignment = Alignment(horizontal='center')
                
                # Formatação
                for r in range(6, ws.max_row + 1):
                    ws[f'B{r}'].number_format = '"R$" #,##0.00'
                    ws[f'C{r}'].number_format = '"R$" #,##0.00'
                    ws[f'D{r}'].number_format = '"R$" #,##0.00'
                    ws[f'E{r}'].number_format = '0.00%'
                    
                    if ws[f'D{r}'].value and ws[f'D{r}'].value < 0: ws[f'D{r}'].font = Font(color=vermelho, bold=True)
                    if ws[f'E{r}'].value and ws[f'E{r}'].value < 0: ws[f'E{r}'].font = Font(color=vermelho, bold=True)
                    elif ws[f'E{r}'].value and ws[f'E{r}'].value > 0: ws[f'E{r}'].font = Font(color=verde, bold=True)
                
                ws.column_dimensions['A'].width = 35
                for c in ['B', 'C', 'D', 'E']: ws.column_dimensions[c].width = 18

            st.success("✅ Tudo pronto! Clique abaixo para baixar.")
            st.download_button("📥 Baixar Planilha Premium", output.getvalue(), "Relatorio_ROI.xlsx")
        except Exception as e:
            st.error(f"Erro: Certifique-se de que o arquivo AdX usa ';' como separador. Detalhe: {e}")
