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
    df['data'] = pd.to_datetime(df['data'], format='mixed', dayfirst=True)
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
tab1, tab2, tab3, tab4 = st.tabs(["📈 Evolução de Preços", "💰 Análise Pareto (ABC)", "📋 Dados Brutos", "📊 Índice de Inflação"])

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

# ==========================================
# ABA 4: ÍNDICE DE INFLAÇÃO PESSOAL
# ==========================================
with tab4:
    st.markdown("### 📊 Índice de Inflação Pessoal")
    st.markdown(
        "Mede como os preços dos **seus produtos** variaram ao longo do tempo, "
        "usando média ponderada pela quantidade comprada (método de Laspeyres)."
    )

    df_inf = df.copy()
    df_inf['ano_mes'] = df_inf['data'].dt.to_period('M')
    meses_disponiveis = sorted(df_inf['ano_mes'].unique())

    if len(meses_disponiveis) < 2:
        st.warning("São necessários dados de pelo menos 2 meses para calcular a inflação.")
    else:
        min_meses_req = st.slider(
            "Mínimo de meses em que o produto deve aparecer na cesta:",
            min_value=2,
            max_value=len(meses_disponiveis),
            value=len(meses_disponiveis),
            help="Reduzir este número amplia a cesta, mas inclui produtos comprados esporadicamente."
        )

        contagem_meses_prod = df_inf.groupby('produto')['ano_mes'].nunique()
        produtos_cesta = contagem_meses_prod[contagem_meses_prod >= min_meses_req].index.tolist()

        if not produtos_cesta:
            st.warning("Nenhum produto encontrado com o critério selecionado. Reduza o número mínimo de meses.")
        else:
            st.info(f"**{len(produtos_cesta)} produto(s)** compõem a cesta de inflação.")

            df_cesta = df_inf[df_inf['produto'].isin(produtos_cesta)].copy()

            # Preço médio ponderado por mês e produto
            df_cesta['preco_x_qtd'] = df_cesta['preco_unit'] * df_cesta['qtd']
            df_mensal = df_cesta.groupby(['ano_mes', 'produto']).agg(
                preco_x_qtd_sum=('preco_x_qtd', 'sum'),
                qtd_total=('qtd', 'sum'),
                gasto_total=('preco_total', 'sum')
            ).reset_index()
            df_mensal['preco_medio'] = df_mensal['preco_x_qtd_sum'] / df_mensal['qtd_total']

            # Pivotear e forward-fill para meses sem compra
            df_pivot = df_mensal.pivot(index='ano_mes', columns='produto', values='preco_medio')
            df_pivot = df_pivot.reindex(meses_disponiveis).ffill()

            # Mês base: primeiro mês disponível
            mes_base = meses_disponiveis[0]
            precos_base = df_pivot.loc[mes_base]

            # Pesos: participação no gasto do mês base
            df_base_gastos = (
                df_mensal[df_mensal['ano_mes'] == mes_base]
                .set_index('produto')['gasto_total']
            )
            # Produtos sem compra no mês base recebem a média de gastos do período
            for prod in produtos_cesta:
                if prod not in df_base_gastos.index:
                    df_base_gastos[prod] = df_mensal[df_mensal['produto'] == prod]['gasto_total'].mean()

            total_base = df_base_gastos.sum()
            pesos = (df_base_gastos / total_base).to_dict()

            # Calcular índice mensal (Laspeyres)
            registros_indice = []
            for mes in meses_disponiveis:
                precos_mes = df_pivot.loc[mes]
                indice = sum(
                    pesos.get(prod, 0) * (precos_mes[prod] / precos_base[prod])
                    for prod in produtos_cesta
                    if precos_base[prod] > 0
                )
                registros_indice.append({'ano_mes': mes, 'indice': indice * 100})

            df_indice = pd.DataFrame(registros_indice)
            df_indice['ano_mes_str'] = df_indice['ano_mes'].astype(str)
            df_indice['var_mensal'] = df_indice['indice'].pct_change() * 100
            df_indice['var_acumulada'] = df_indice['indice'] - 100

            # KPIs
            indice_atual = df_indice['indice'].iloc[-1]
            var_acum = df_indice['var_acumulada'].iloc[-1]
            var_ultimo_mes = df_indice['var_mensal'].iloc[-1]

            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Índice Atual (base 100)", f"{indice_atual:.1f}")
            kpi2.metric("Inflação Acumulada", f"{var_acum:+.2f}%")
            kpi3.metric(
                "Variação no Último Mês",
                f"{var_ultimo_mes:+.2f}%" if pd.notna(var_ultimo_mes) else "—"
            )

            st.divider()

            # Gráfico do índice acumulado
            fig_indice = px.line(
                df_indice,
                x='ano_mes_str',
                y='indice',
                markers=True,
                title=f"Índice de Inflação Pessoal (base {str(mes_base)} = 100)",
                labels={'ano_mes_str': 'Mês', 'indice': 'Índice'}
            )
            fig_indice.add_hline(y=100, line_dash="dash", line_color="gray", annotation_text="Base 100")
            st.plotly_chart(fig_indice, use_container_width=True)

            # Gráfico de variação mensal
            fig_var = px.bar(
                df_indice.iloc[1:],
                x='ano_mes_str',
                y='var_mensal',
                title="Variação Mensal (%)",
                labels={'ano_mes_str': 'Mês', 'var_mensal': 'Variação (%)'},
                color='var_mensal',
                color_continuous_scale=['#21c354', '#ffffff', '#ff4b4b'],
                color_continuous_midpoint=0
            )
            st.plotly_chart(fig_var, use_container_width=True)

            # Detalhamento da cesta
            with st.expander(f"Ver os {len(produtos_cesta)} produtos na cesta e seus pesos"):
                df_pesos = pd.DataFrame([
                    {'produto': prod, 'peso_%': pesos[prod] * 100, 'preco_base': precos_base[prod]}
                    for prod in produtos_cesta
                ]).sort_values('peso_%', ascending=False)
                st.dataframe(
                    df_pesos.style.format({'peso_%': '{:.2f}%', 'preco_base': 'R$ {:.2f}'}),
                    use_container_width=True
                )

            with st.expander("Ver preços médios mensais por produto"):
                df_pivot_display = df_pivot.copy()
                df_pivot_display.index = df_pivot_display.index.astype(str)
                st.dataframe(
                    df_pivot_display.style.format('R$ {:.2f}'),
                    use_container_width=True
                )