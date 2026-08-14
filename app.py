# ═══════════════════════════════════════════════════════════════════
# PATCH — substitua o bloco que hoje começa em:
#     df_m['core'] = (df_m['Nome do anúncio'].str.lower()...
# e termina em:
#     merged = pd.merge(meta_g, adx_g, on='core', how='left').fillna(0)
# ═══════════════════════════════════════════════════════════════════
import re

def gerar_chave(nome):
    """
    Chave robusta de pareamento Meta ↔ AdX.

    Padrão dos nomes: <PREFIXO><NUMERO>.<NICHO>.<PAIS>.<DATA>
        AD162.BIENESTAR.MEX.13/08/2026
        ca162.BIENESTARQUIZ.MEX.13/08/2026

    O token do NICHO é ignorado de propósito: é o campo que na prática
    diverge entre as duas plataformas (bienestar vs bienestarquiz).
    A chave final vira '162.mex.13/08/2026', que é única.
    """
    s = str(nome).lower().strip().replace('"', '')
    s = re.sub(r'^[a-z]+', '', s)          # remove prefixo alfabético (ad, ca, cad...)
    p = s.split('.')
    if len(p) >= 4:                        # numero . nicho . pais . data
        return f"{p[0]}.{p[2]}.{'.'.join(p[3:])}"
    return s                               # formato desconhecido: mantém como está

# ── Chaves ────────────────────────────────────────────────────────────
df_m['core'] = df_m['Nome do anúncio'].map(gerar_chave)
df_a['core'] = df_a['utm_campaign'].map(gerar_chave)

# Nome original do Meta, para exibir na planilha em vez da chave crua
nome_exibicao = (df_m.groupby('core')['Nome do anúncio']
                     .first().to_dict())

# ── Receita do AdX para float ─────────────────────────────────────────
df_a['G_USD'] = (df_a['Ganhos'].astype(str)
                 .str.replace('$', '', regex=False)
                 .str.replace(',', '', regex=False)
                 .astype(float))

# ── Linhas numéricas (ID da campanha) → chave via mapa de IDs ─────────
df_m['ID_str'] = df_m['Identificação da campanha'].astype(str).str.strip()
id_para_core = df_m.set_index('ID_str')['core'].to_dict()

mask_numerica = df_a['utm_campaign'].astype(str).str.match(r'^\d+$', na=False)
df_a.loc[mask_numerica, 'core'] = (df_a.loc[mask_numerica, 'utm_campaign']
                                   .astype(str).str.strip().map(id_para_core))

# ── Auditoria: o que o AdX trouxe e não casou com nenhuma campanha ────
chaves_meta = set(df_m['core'])
orfas = df_a[~df_a['core'].isin(chaves_meta)].copy()
orfas = orfas[orfas['G_USD'] > 0]
if not orfas.empty:
    st.warning(
        f"⚠️ {len(orfas)} linha(s) do AdX somando "
        f"$ {orfas['G_USD'].sum():,.2f} não casaram com nenhuma campanha do Meta."
    )
    st.dataframe(orfas[['utm_campaign', 'Visitantes', 'G_USD']],
                 use_container_width=True, hide_index=True)

# ── Agregação e junção (outer: nada some) ─────────────────────────────
adx_g  = df_a.dropna(subset=['core']).groupby('core')['G_USD'].sum().reset_index()
meta_g = df_m.groupby('core')['Valor usado (BRL)'].sum().reset_index()

merged = pd.merge(meta_g, adx_g, on='core', how='outer').fillna(0)
merged['core'] = merged['core'].map(lambda k: nome_exibicao.get(k, k))
merged.columns = ['Campanha', 'Investimento', 'Receita (USD)']
