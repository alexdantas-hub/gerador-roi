import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
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
st.write("Processador de Meta Ads vs Google Ad Exchange")

col1, col2 = st.columns(2)
with col1:
    file_meta = st.file_uploader("Arquivo Meta (Gastos)", type=["csv"])
with col2:
    file_adx = st.file_uploader("Arquivo AdX (Receita)", type=["csv"])

cambio = st.sidebar.number_input("Cotação do Dólar (R$)", value=5.00, step=0.10)

if file_meta and file_adx:
    if st.button("🚀 Processar e Gerar Planilha"):
        try:
            # 1. Leitura com detecção automática de delimitador para evitar o erro de indexação
            df_m = pd.read_csv(file_meta, sep=None, engine='python')
            df_a = pd.read_csv(file_adx, sep=None, engine='python')
            
            # Função para limpar prefixos ad/ca
            def clean_n(n):
                n = str(n).lower().strip()
                if n.startswith('ad'): return n[2:]
                if n.startswith('ca'): return n[2:]
                return n

            # Identificando colunas por nome para maior segurança
            col_nome_meta = "Nome do anúncio"
            col_gasto_meta = "Valor usado (BRL)"
            col_nome_adx = "utm_campaign"
            col_ganho_adx = "Ganhos"

            df_m['core'] = df_m[col_nome_meta].apply(clean_n)
            df_a['core'] = df_a[col_nome_adx].apply(clean_n)
            
            # Agrupamento
            meta_g = df_m.groupby('core')[col_gasto_meta].sum().reset_index()
            
            # Limpeza financeira do AdX
            df_a['Ganhos_USD'] = df_a[col_ganho_adx].replace('[\$,]', '', regex=True).astype(float)
            adx_g = df_a.groupby('core')['Ganhos_USD'].sum().reset_index()
            
            # Cruzamento
            merged = pd.merge(meta_g, adx_g, on='core', how='inner')
            merged.columns = ['Campanha', 'Investimento', 'USD']
            
            # Cálculos
            merged['Receita'] = merged['USD'] * cambio
            merged['Lucro'] = merged['Receita'] - merged['Investimento']
            merged['ROI'] = merged['Lucro'] / merged['Investimento']
            merged = merged.sort_values('ROI', ascending=False)
            
            # 2. Geração do Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_ex = merged[['Campanha', 'Investimento', 'Receita', 'Lucro', 'ROI']].copy()
                df_ex['Campanha'] = df_ex['Campanha'].str.upper()
                
                # Totais
                t_inv = df_ex['Investimento'].sum()
                t_rec = df_ex['Receita'].sum()
                t_luc = t_rec - t_inv
                t_roi = t_luc / t_inv if t_inv > 0 else 0
                
                df_ex = pd.concat([df_ex, pd.DataFrame([['TOTAL', t_inv, t_rec, t_luc, t_roi]], columns=df_ex.columns)], ignore_index=True)
                df_ex.to_excel(writer, index=False, sheet_name='ROI', startrow=4)
                
                ws = writer.sheets['ROI']
                azul, vermelho, verde = "2C3E50", "C0392B", "27AE60"
                
                # Estilo do Título Superior
                ws.merge_cells('A1:E1')
                ws['A1'] = "Relatório de ROI por Campanha"
                ws['A1'].font = Font(name='Arial', bold=True, size=20, color=azul)
                ws['A1'].alignment = Alignment(horizontal='center')
                
                # Títulos da Tabela
                for cell in ws[5]:
                    cell.font = Font(name='Arial', bold=True, color="FFFFFF")
                    cell.fill = PatternFill(start_color=azul, end_color=azul, fill_type="solid")
                    cell.alignment = Alignment(horizontal='center')
                
                # Formatação Numérica e Cores
                for r in range(6, ws.max_row + 1):
                    ws[f'B{r}'].number_format = '"R$" #,##0.00'
                    ws[f'C{r}'].number_format = '"R$" #,##0.00'
                    ws[f'D{r}'].number_format = '"R$" #,##0.00'
                    ws[f'E{r}'].number_format = '0.00%'
                    
                    val_lucro = ws[f'D{r}'].value
                    val_roi = ws[f'E{r}'].value
                    
                    if isinstance(val_lucro, (int, float)) and val_lucro < 0:
                        ws[f'D{r}'].font = Font(color=vermelho, bold=True)
                    if isinstance(val_roi, (int, float)):
                        if val_roi < 0: ws[f'E{r}'].font = Font(color=vermelho, bold=True)
                        elif val_roi > 0: ws[f'E{r}'].font = Font(color=verde, bold=True)
                
                ws.column_dimensions['A'].width = 35
                for c in ['B', 'C', 'D', 'E']: ws.column_dimensions[c].width = 18

            st.success("✅ Relatório gerado!")
            st.download_button("⬇️ Baixar Planilha Premium", output.getvalue(), "Relatorio_ROI.xlsx")
            
        except Exception as e:
            st.error(f"Erro no processamento: {e}")
            st.info("Dica: Verifique se os arquivos CSV contêm as colunas 'Nome do anúncio' e 'utm_campaign'.")
