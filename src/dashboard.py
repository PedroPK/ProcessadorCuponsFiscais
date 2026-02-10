import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Minha Inflação Pessoal", layout="wide")
st.title("🛒 Monitor de Preços & Inflação Pessoal")

# --- CARREGAMENTO DOS DADOS ---
@st.cache_data
def carregar_dados():
    # Caminho automático: src -> raiz -> resources -> outputData
    caminho_csv = Path(__file__).resolve().parent.parent / 'resources' / 'outputData' / 'minha_inflacao.csv'
    
    if not caminho_csv.exists():
        return None
    
    # Lê com padrão brasileiro
    df = pd.read_csv(caminho_csv, sep=';', decimal=',', encoding='utf-8-sig')
    df['data'] = pd.to_datetime(df['data'], dayfirst=True)
    return df.sort_values('data')

df = carregar_dados()

if df is None:
    st.error("Arquivo CSV não encontrado. Rode o 'main.py' primeiro!")
    st.stop()

if df.empty:
    st.warning("O arquivo CSV existe, mas está vazio.")
    st.stop()

# --- BARRA LATERAL (FILTROS GERAIS) ---
st.sidebar.header("Filtros")
mercados = st.sidebar.multiselect("Filtrar por Mercado (Origem)", df['arquivo_origem'].unique())

if mercados:
    df = df[df['arquivo_origem'].isin(mercados)]

# --- CRIAÇÃO DAS ABAS ---
tab1, tab2, tab3 = st.tabs(["📈 Evolução de Preços", "💰 Análise Pareto (ABC)", "📋 Dados Brutos"])

# ==========================================
# ABA 1: EVOLUÇÃO (O que você já tinha)
# ==========================================
with tab1:
    st.markdown("### Como os preços variaram no tempo?")
    
    lista_produtos = sorted(df['produto'].unique())
    produtos_selecionados = st.multiselect(
        "Selecione os produtos para comparar:",
        options=lista_produtos,
        default=lista_produtos[0] if len(lista_produtos) > 0 else None
    )

    if produtos_selecionados:
        df_filtrado = df[df['produto'].isin(produtos_selecionados)]
        
        # Gráfico de Linha
        fig_evolucao = px.line(
            df_filtrado, 
            x='data', 
            y='preco_unit', 
            color='produto', 
            markers=True,
            title="Histórico de Preço Unitário (R$)"
        )
        st.plotly_chart(fig_evolucao, use_container_width=True)
        
        # Métricas rápidas
        col1, col2, col3 = st.columns(3)
        ultimos_precos = df_filtrado.sort_values('data').groupby('produto').tail(1)
        media_preco = df_filtrado['preco_unit'].mean()
        
        col1.metric("Média de Preço (Sel.)", f"R$ {media_preco:.2f}")
    else:
        st.info("Selecione produtos acima para gerar o gráfico.")

# ==========================================
# ABA 2: PARETO / CURVA ABC (O Novo Código!)
# ==========================================
with tab2:
    st.markdown("### Quem são os vilões do seu orçamento?")
    st.markdown("A **Lei de Pareto (80/20)** diz que geralmente 20% dos produtos são responsáveis por 80% do gasto total.")

    # 1. Agrupar por produto e somar o total gasto
    df_pareto = df.groupby('produto')['preco_total'].sum().reset_index()
    
    # 2. Ordenar do maior gasto para o menor
    df_pareto = df_pareto.sort_values('preco_total', ascending=False)
    
    # 3. Calcular percentuais acumulados
    total_geral = df_pareto['preco_total'].sum()
    df_pareto['% do Total'] = (df_pareto['preco_total'] / total_geral) * 100
    df_pareto['% Acumulado'] = df_pareto['% do Total'].cumsum()

    # 4. Classificar em A, B e C
    def classificar_abc(row):
        if row['% Acumulado'] <= 80: return 'A (Alta Importância)'
        elif row['% Acumulado'] <= 95: return 'B (Média Importância)'
        else: return 'C (Baixa Importância)'
    
    df_pareto['Classe'] = df_pareto.apply(classificar_abc, axis=1)

    # --- Visualização ---
    
    # KPIs
    qtd_produtos = len(df_pareto)
    qtd_classe_a = len(df_pareto[df_pareto['Classe'] == 'A (Alta Importância)'])
    gasto_classe_a = df_pareto[df_pareto['Classe'] == 'A (Alta Importância)']['preco_total'].sum()

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Gasto", f"R$ {total_geral:.2f}")
    kpi2.metric("Itens 'Classe A'", f"{qtd_classe_a} de {qtd_produtos}")
    kpi3.metric("Impacto da Classe A", f"{(gasto_classe_a/total_geral)*100:.1f}% do dinheiro")

    st.divider()

    # Gráfico de Barras dos Top 20 itens
    fig_pareto = px.bar(
        df_pareto.head(20), 
        x='produto', 
        y='preco_total',
        color='Classe',
        title="Top 20 Produtos onde você mais gasta dinheiro",
        text_auto='.2s',
        color_discrete_map={'A (Alta Importância)': '#ff4b4b', 'B (Média Importância)': '#ffa421', 'C (Baixa Importância)': '#21c354'}
    )
    st.plotly_chart(fig_pareto, use_container_width=True)

    with st.expander("Ver Tabela Completa ABC"):
        st.dataframe(df_pareto.style.format({'preco_total': 'R$ {:.2f}', '% do Total': '{:.2f}%', '% Acumulado': '{:.2f}%'}))

# ==========================================
# ABA 3: DADOS BRUTOS
# ==========================================
with tab3:
    st.dataframe(df)