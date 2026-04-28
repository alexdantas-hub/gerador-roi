import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from openpyxl.styles import Font, Alignment, PatternFill

# Configuração da página para ocupar melhor o espaço
st.set_page_config(page_title="ROI Analyzer Premium", layout="wide")

# CSS para tornar a interface web moderna e limpa
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { background-color: #2c3e50; color: white; border-radius: 8px; width: 100%; font-weight: bold; }
    .stDownloadButton>button { background-color: #27ae60; color: white; border-radius: 8px; width: 100%; font-weight: bold; }
    .css-12w0qpk { padding: 2rem 1rem; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Dashboard de Performance ROI")
st.markdown("---")

# Barra lateral para configurações
st.sidebar.header("Configurações")
cambio = st.sidebar.number_input("Cotação do Dólar (R$)", value=5.00, step=0.10)

# Área de Upload
col_u1, col_u2 = st.columns(2)
with col_u1:
    file_meta = st.file_uploader("📁 Arquivo Meta Ads (Gastos)", type=["csv"])
with col_u2:
    file_adx = st.file_uploader("📁 Arquivo AdX (Receita)", type=["csv"])

def clean_campaign_name(name):
    name = str(name).lower().strip().replace('"', '')
    if name.startswith('ad'): return name[2:]
    if name.startswith('ca'): return name[2:]
    return name

if file_meta and file_adx:
    try:
        # Processamento idêntico ao anterior
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
        merged['ROI'] = (merged['Lucro'] / merged['Investimento'])
        merged = merged.sort_values('ROI', ascending=False)

        # --- EXIBIÇÃO DO DASHBOARD EM TELA ---
        
        # 1. Métricas de Resumo (Cards)
        tot_inv = merged['Investimento'].sum()
        tot_rec = merged['Receita'].sum()
        tot_luc = tot_rec - tot_inv
        tot_roi = (tot_luc / tot_inv) if tot_inv > 0 else 0

        st.subheader("📌 Resumo Consolidado")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Investimento Total", f"R$ {tot_inv:,.2f}")
        m2.metric("Receita Total", f"R$ {tot_rec:,.2f}")
        m3.metric("Lucro Líquido", f"R$ {tot_luc:,.2f}", delta=f"{tot_luc:,.2f}")
        m4.metric("ROI Geral", f"{tot_roi:.2%}")

        st.markdown("---")

        # 2. Tabela de Dados Estilizada para Web
        st.subheader("📋 Detalhamento por Campanha")
        
        # Formatando o DataFrame apenas para exibição visual
        df_display = merged[['Campanha', 'Investimento', 'Receita', 'Lucro', 'ROI']].copy()
        df_display['Campanha'] = df_display['Campanha'].str.upper()
        
        # Aplicando cores condicionais na visualização web
        def color_roi(val):
            color = '#27ae60' if val > 0 else '#c0392b'
            return f'color: {color}; font-weight: bold'

        st.dataframe(
            df_display.style.format({
                'Investimento': 'R$ {:,.2f}',
                'Receita': 'R$ {:,.2f}',
                'Lucro': 'R$ {:,.2f}',
                'ROI': '{:.2%}'
            }).applymap(color_roi, subset=['Lucro', 'ROI']),
            use_container_width=True,
            height=400
        )

        # 3. Botão de Download (Mantendo a formatação Excel idêntica ao PDF)
        st.markdown("### 📥 Exportar")
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_ex = df_display.copy()
            df_ex = pd.concat([df_ex, pd.DataFrame([['TOTAL', tot_inv, tot_rec, tot_luc, tot_roi]], columns=df_ex.columns)], ignore_index=True)
            df_ex.to_excel(writer, index=False, sheet_name='ROI', startrow=4)
            
            ws = writer.sheets['ROI']
            azul, vermelho, verde, cinza = "2C3E50", "C0392B", "27AE60", "7F8C8D"
            
            # Cabeçalho da Planilha (as 3 linhas que você pediu)
            ws.merge_cells('A1:E1')
            ws['A1'] = "Relatório de ROI por Campanha"
            ws['A1'].font = Font(name='Arial', bold=True, size=18, color=azul)
            ws['A1'].alignment = Alignment(horizontal='center')
            
            ws.merge_cells('A2:E2')
            ws['A2'] = "Análise de Performance - Meta Ads vs Google Ad Exchange"
            ws['A2'].font = Font(name='Arial', size=12, color=cinza)
            ws['A2'].alignment = Alignment(horizontal='center')
            
            ws.merge_cells('A3:E3')
            ws['A3'] = f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Câmbio: R$ {cambio:,.2f}"
            ws['A3'].font = Font(name='Arial', italic=True, size=10, color=cinza)
            ws['A3'].alignment = Alignment(horizontal='center')

            for cell in ws[5]:
                cell.font = Font(name='Arial', bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color=azul, end_color=azul, fill_type="solid")
                cell.alignment = Alignment(horizontal='center')

            for r in range(6, ws.max_row + 1):
                ws[f'B{r}'].number_format = '"R$" #,##0.00'
                ws[f'C{r}'].number_format = '"R$" #,##0.00'
                ws[f'D{r}'].number_format = '"R$" #,##0.00'
                ws[f'E{r}'].number_format = '0.00%'
            
            ws.column_dimensions['A'].width = 35
            for c in ['B', 'C', 'D', 'E']: ws.column_dimensions[c].width = 18

        st.download_button(
            label="Baixar Planilha Excel Formatada",
            data=output.getvalue(),
            file_name=f"ROI_Dashboard_{datetime.now().strftime('%d%m%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"Erro ao processar arquivos: {e}")
else:
    st.info("Aguardando upload dos arquivos Meta e AdX para gerar o dashboard.")
