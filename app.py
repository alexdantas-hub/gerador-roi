import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill

st.set_page_config(page_title="Gerador de ROI Premium", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #faf9f6; }
    .stButton>button { background-color: #2c3e50; color: white; border-radius: 8px; width: 100%; height: 3em; }
    .stDownloadButton>button { background-color: #27ae60; color: white; border-radius: 8px; width: 100%; height: 3em; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Relatório de ROI por Campanha")

col1, col2 = st.columns(2)
with col1:
    file_meta = st.file_uploader("Arquivo Meta (Gastos)", type=["csv"])
with col2:
    file_adx = st.file_uploader("Arquivo AdX (Receita)", type=["csv"])

cambio = st.sidebar.number_input("Cotação do Dólar (R$)", value=5.00, step=0.10)

def clean_campaign_name(name):
    name = str(name).lower().strip().replace('"', '')
    if name.startswith('ad'): return name[2:]
    if name.startswith('ca'): return name[2:]
    return name

if file_meta and file_adx:
    if st.button("🚀 Processar e Gerar Planilha"):
        try:
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
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_ex = merged[['Campanha', 'Investimento', 'Receita', 'Lucro', 'ROI']].copy()
                df_ex['Campanha'] = df_ex['Campanha'].str.upper()
                
                t_inv, t_rec = df_ex['Investimento'].sum(), df_ex['Receita'].sum()
                t_luc = t_rec - t_inv
                t_roi = t_luc / t_inv if t_inv > 0 else 0
                
                df_ex = pd.concat([df_ex, pd.DataFrame([['TOTAL', t_inv, t_rec, t_luc, t_roi]], columns=df_ex.columns)], ignore_index=True)
                
                # Começamos a tabela na linha 5 para dar espaço ao cabeçalho triplo
                df_ex.to_excel(writer, index=False, sheet_name='ROI', startrow=4)
                
                ws = writer.sheets['ROI']
                azul, vermelho, verde, cinza = "2C3E50", "C0392B", "27AE60", "7F8C8D"
                
                # 1. TÍTULO PRINCIPAL
                ws.merge_cells('A1:E1')
                ws['A1'] = "Relatório de ROI por Campanha"
                ws['A1'].font = Font(name='Arial', bold=True, size=18, color=azul)
                ws['A1'].alignment = Alignment(horizontal='center')
                
                # 2. SUBTÍTULO
                ws.merge_cells('A2:E2')
                ws['A2'] = "Análise de Performance - Meta Ads vs Google Ad Exchange"
                ws['A2'].font = Font(name='Arial', size=12, color=cinza)
                ws['A2'].alignment = Alignment(horizontal='center')
                
                # 3. LINHA DE INFORMAÇÕES (DATA E CÂMBIO)
                ws.merge_cells('A3:E3')
                timestamp = datetime.now().strftime('%d/%m/%Y %H:%M')
                ws['A3'] = f"Gerado em: {timestamp} | Câmbio Utilizado: R$ {cambio:,.2f}"
                ws['A3'].font = Font(name='Arial', italic=True, size=10, color=cinza)
                ws['A3'].alignment = Alignment(horizontal='center')
                
                # Títulos das Colunas (Linha 5)
                for cell in ws[5]:
                    cell.font = Font(name='Arial', bold=True, color="FFFFFF")
                    cell.fill = PatternFill(start_color=azul, end_color=azul, fill_type="solid")
                    cell.alignment = Alignment(horizontal='center')
                
                # Formatação das Células e Cores
                for r in range(6, ws.max_row + 1):
                    ws[f'B{r}'].number_format = '"R$" #,##0.00'
                    ws[f'C{r}'].number_format = '"R$" #,##0.00'
                    ws[f'D{r}'].number_format = '"R$" #,##0.00'
                    ws[f'E{r}'].number_format = '0.00%'
                    
                    l_val, r_val = ws[f'D{r}'].value, ws[f'E{r}'].value
                    if isinstance(l_val, (int, float)) and l_val < 0: ws[f'D{r}'].font = Font(color=vermelho, bold=True)
                    if isinstance(r_val, (int, float)):
                        if r_val < 0: ws[f'E{r}'].font = Font(color=vermelho, bold=True)
                        elif r_val > 0: ws[f'E{r}'].font = Font(color=verde, bold=True)
                
                ws.column_dimensions['A'].width = 35
                for c in ['B', 'C', 'D', 'E']: ws.column_dimensions[c].width = 18

            st.success("✅ Relatório formatado com sucesso!")
            st.download_button("📥 Baixar Planilha Premium", output.getvalue(), f"Relatorio_ROI_{datetime.now().strftime('%d%m%Y')}.xlsx")
            
        except Exception as e:
            st.error(f"Erro ao processar: {e}")
