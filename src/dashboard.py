import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import os
import signal
import threading
import subprocess
import sys
import platform
from pathlib import Path
from utils import filtrar_produtos, resolver_danfe

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


# -------------------------------------------------------
# Detecta arquivos na pasta que ainda não estão no CSV
# -------------------------------------------------------
def detectar_novos_arquivos(df_base):
    pasta_nf = Path(__file__).resolve().parent.parent / 'resources' / 'notas_fiscais'
    if not pasta_nf.exists():
        return []
    extensoes = {'.xml', '.pdf', '.zip', '.xlsx'}
    arquivos_na_pasta = {f.name for f in pasta_nf.iterdir() if f.suffix.lower() in extensoes}
    if df_base is None or 'arquivo_origem' not in df_base.columns:
        return sorted(arquivos_na_pasta)
    # Extrai o nome-raiz da origem (antes de '::' nos ZIPs)
    origens_processadas = {
        str(origem).split('::')[0]
        for origem in df_base['arquivo_origem'].dropna()
    }
    return sorted(arquivos_na_pasta - origens_processadas)


def fechar_aba_navegador():
    components.html(
        """
        <script>
        (function () {
            try {
                const hostWin = window.parent || window.top || window;
                hostWin.close();
            } catch (e) {
                // Ignora erro de política do navegador.
            }
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def encerrar_streamlit(delay_segundos: float = 0.8):
    def _encerrar():
        try:
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            os._exit(0)

    threading.Timer(delay_segundos, _encerrar).start()


def iniciar_watchdog_fechamento_aba_macos(
    porta: int,
    intervalo_segundos: float = 2.0,
    max_falhas_consecutivas: int = 3,
):
    if platform.system() != 'Darwin':
        return

    if st.session_state.get('_watchdog_fechamento_macos_iniciado'):
        return

    target_url = f'localhost:{porta}'

    script_watchdog = f"""
import time
import urllib.request
import urllib.error
import subprocess
import sys

health_url = 'http://localhost:{porta}/_stcore/health'
intervalo = {intervalo_segundos}
max_falhas = {max_falhas_consecutivas}
falhas = 0

def backend_ativo():
    try:
        with urllib.request.urlopen(health_url, timeout=1.2) as resp:
            return 200 <= getattr(resp, 'status', 0) < 500
    except Exception:
        return False

for _ in range(1800):
    if backend_ativo():
        falhas = 0
    else:
        falhas += 1

    if falhas >= max_falhas:
        break
    time.sleep(intervalo)

if falhas < max_falhas:
    sys.exit(0)

apple_script = r'''
set targetText to "{target_url}"

set chromiumApps to {{"Google Chrome", "Microsoft Edge", "Brave Browser", "Vivaldi"}}
repeat with appName in chromiumApps
    if application appName is running then
        tell application appName
            repeat with w in windows
                set tabsToClose to {{}}
                repeat with t in tabs of w
                    try
                        if URL of t contains targetText then
                            set end of tabsToClose to t
                        end if
                    end try
                end repeat
                repeat with t in tabsToClose
                    close t
                end repeat
            end repeat
        end tell
    end if
end repeat

if application "Safari" is running then
    tell application "Safari"
        repeat with w in windows
            set tabsToClose to {{}}
            repeat with t in tabs of w
                try
                    if URL of t contains targetText then
                        set end of tabsToClose to t
                    end if
                end try
            end repeat
            repeat with t in tabsToClose
                close t
            end repeat
        end repeat
    end tell
end if
'''

subprocess.run(['osascript', '-e', apple_script], check=False)
"""

    subprocess.Popen(
        [sys.executable, '-c', script_watchdog],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    st.session_state['_watchdog_fechamento_macos_iniciado'] = True


def auto_fechar_aba_quando_desconectar(
    intervalo_ms: int = 2000,
    max_falhas_consecutivas: int = 3,
):
    components.html(
        f"""
        <script>
        (function () {{
            const hostWin = window.parent || window;
            const WATCHDOG_KEY = '__pcf_disconnect_watchdog_installed__';

            if (hostWin[WATCHDOG_KEY]) return;
            hostWin[WATCHDOG_KEY] = true;

            const CHECK_INTERVAL_MS = {intervalo_ms};
            const MAX_FAILS = {max_falhas_consecutivas};
            const HEALTH_ENDPOINTS = ['/_stcore/health', '/healthz'];
            let failedChecks = 0;

            function fetchWithTimeout(url, timeoutMs) {{
                const controller = new AbortController();
                const timer = setTimeout(() => controller.abort(), timeoutMs);

                return fetch(url, {{
                    method: 'GET',
                    cache: 'no-store',
                    signal: controller.signal,
                }}).finally(() => clearTimeout(timer));
            }}

            async function isBackendAlive() {{
                for (const endpoint of HEALTH_ENDPOINTS) {{
                    try {{
                        const response = await fetchWithTimeout(endpoint, 1200);
                        if (response.ok) return true;
                    }} catch (err) {{
                        // Tenta o próximo endpoint
                    }}
                }}
                return false;
            }}

            function forceCloseOrBlank() {{
                try {{
                    hostWin.open('', '_self');
                    hostWin.close();
                }} catch (e) {{}}

                // Fallback quando o navegador bloqueia fechamento de aba.
                try {{
                    hostWin.location.replace('about:blank');
                }} catch (e) {{
                    hostWin.location.href = 'about:blank';
                }}
            }}

            async function checkConnection() {{
                const alive = await isBackendAlive();
                failedChecks = alive ? 0 : failedChecks + 1;

                if (failedChecks >= MAX_FAILS) {{
                    forceCloseOrBlank();
                }}
            }}

            hostWin.setInterval(checkConnection, CHECK_INTERVAL_MS);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


# --- BARRA LATERAL (REPROCESSAMENTO) ---
st.sidebar.header("🔄 Atualizar Dados")

novos = detectar_novos_arquivos(df)

if novos:
    st.sidebar.warning(f"**{len(novos)} arquivo(s) novo(s)** encontrado(s):")
    for nome in novos:
        st.sidebar.caption(f"• {nome}")
else:
    st.sidebar.success("Nenhum arquivo novo detectado.")

if st.sidebar.button(
    "Processar e Atualizar" if novos else "Reprocessar tudo",
    type="primary" if novos else "secondary",
    use_container_width=True,
):
    import subprocess, sys
    script = Path(__file__).resolve().parent / 'processadorCuponsFiscais.py'
    with st.sidebar.status("Processando notas fiscais...", expanded=True) as status:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
        )
    if result.returncode == 0:
        st.sidebar.success("✅ Dados atualizados!")
        carregar_dados.clear()
        st.rerun()
    else:
        st.sidebar.error("❌ Erro ao processar:")
        st.sidebar.code(result.stderr[-800:] or result.stdout[-800:])

st.sidebar.divider()

# Monitora perda de conexão com backend e fecha a aba automaticamente.
auto_fechar_aba_quando_desconectar()
iniciar_watchdog_fechamento_aba_macos(st.get_option('server.port'))

# --- BARRA LATERAL (ENCERRAR DASHBOARD) ---
st.sidebar.header("⏹ Encerrar Dashboard")

if st.sidebar.button(
    "Encerrar serviço e fechar aba",
    type="secondary",
    use_container_width=True,
):
    st.sidebar.info("Encerrando dashboard...")
    fechar_aba_navegador()
    encerrar_streamlit()

st.sidebar.divider()

# --- BARRA LATERAL (FILTROS GERAIS) ---
st.sidebar.header("Filtros")

if df is None:
    st.error("Arquivo CSV não encontrado. Use o botão **Processar e Atualizar** na barra lateral.")
    st.stop()

if df.empty:
    st.warning("O arquivo CSV existe, mas está vazio.")
    st.stop()

mercados = st.sidebar.multiselect("Filtrar por Mercado (Origem)", df['arquivo_origem'].unique())

if mercados:
    df = df[df['arquivo_origem'].isin(mercados)]

# --- CRIAÇÃO DAS ABAS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Evolução de Preços", "💰 Análise Pareto (ABC)", "📋 Dados Brutos", "📊 Índice de Inflação Pessoal", "🏆 Produtos Mais Comprados"])

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
    busca = st.text_input("🔍 Filtrar produtos", placeholder="Digite parte do nome do produto...")
    df_brutos = filtrar_produtos(df, busca)

    # Exibe a data sem o componente de hora (apenas para visualização)
    df_exibir = df_brutos.copy()
    df_exibir['data'] = df_exibir['data'].dt.date
    
    # Renomeia colunas para exibição: remove underscores e capitaliza
    mapa_colunas = {
        'data': 'Data',
        'loja': 'Loja',
        'cnpj': 'CNPJ',
        'categoria': 'Categoria',
        'produto': 'Produto',
        'qtd': 'Qtd',
        'unidade': 'Unidade',
        'preco_unit': 'Preço Unit',
        'preco_total': 'Preço Total',
        'codigo': 'Código',
        'ean': 'EAN',
        'ncm': 'NCM',
        'chave_nfe': 'Chave NF-e',
        'arquivo_origem': 'Arquivo Origem'
    }
    df_exibir = df_exibir.rename(columns=mapa_colunas)
    
    # Configura coluna "Arquivo Origem" com largura expandida para melhor visualização
    st.dataframe(
        df_exibir,
        column_config={
            "Arquivo Origem": st.column_config.TextColumn(width=600)
        },
        use_container_width=True,
        height=400
    )

    # --- Visualizar Nota Fiscal Original ---
    st.markdown("---")
    st.markdown("#### 📄 Visualizar Nota Fiscal Original")

    raiz_projeto = Path(__file__).resolve().parent.parent
    origens_visiveis = sorted(df_brutos['arquivo_origem'].dropna().unique())

    if origens_visiveis:
        origem_selecionada = st.selectbox(
            "Selecione o arquivo de origem:",
            options=origens_visiveis,
        )
        caminho_pdf = resolver_danfe(origem_selecionada, raiz_projeto)

        if caminho_pdf:
            with open(caminho_pdf, 'rb') as f:
                st.download_button(
                    label="⬇️ Baixar / Abrir DANFE (PDF)",
                    data=f,
                    file_name=caminho_pdf.name,
                    mime="application/pdf",
                )
        else:
            st.info(
                "DANFE não encontrado para este arquivo. "
                "Rode `python3 src/gerador_danfe.py` para gerar os PDFs a partir dos XMLs."
            )
    else:
        st.info("Nenhum registro visível para selecionar.")

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
            value=max(2, len(meses_disponiveis) // 2),
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

            # Pivotear, forward-fill e backward-fill para meses sem compra
            # (bfill garante que produtos com primeira compra após o mês base
            # recebam um preço base válido, evitando NaN e deflação espúria)
            df_pivot = df_mensal.pivot(index='ano_mes', columns='produto', values='preco_medio')
            df_pivot = df_pivot.reindex(meses_disponiveis).ffill().bfill()

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

            # Calcular índice mensal (Laspeyres) e contribuições por produto
            registros_indice = []
            for i, mes in enumerate(meses_disponiveis):
                precos_mes = df_pivot.loc[mes]
                indice = sum(
                    pesos.get(prod, 0) * (precos_mes[prod] / precos_base[prod])
                    for prod in produtos_cesta
                    if precos_base[prod] > 0
                )
                if i == 0:
                    contribs = {prod: 0.0 for prod in produtos_cesta if precos_base[prod] > 0}
                else:
                    precos_ant = df_pivot.loc[meses_disponiveis[i - 1]]
                    contribs = {
                        prod: pesos.get(prod, 0) * ((precos_mes[prod] - precos_ant[prod]) / precos_base[prod]) * 100
                        for prod in produtos_cesta
                        if precos_base[prod] > 0
                    }
                registros_indice.append({'ano_mes': mes, 'indice': indice * 100, 'contribuicoes': contribs})

            df_indice = pd.DataFrame(registros_indice)
            df_indice['ano_mes_str'] = df_indice['ano_mes'].astype(str)
            df_indice['var_mensal'] = df_indice['indice'].pct_change() * 100
            df_indice['var_acumulada'] = df_indice['indice'] - 100

            def _hover_top10(contribs):
                top10 = sorted(contribs.items(), key=lambda x: abs(x[1]), reverse=True)[:10]
                linhas = ['<b>Top 10 contribuições (pp):</b>']
                for prod, contrib in top10:
                    sinal = '▲' if contrib > 0 else ('▼' if contrib < 0 else '●')
                    linhas.append(f'{sinal} {prod[:35]}: {contrib:+.3f}')
                return '<br>'.join(linhas)

            df_indice['hover_top10'] = df_indice['contribuicoes'].apply(_hover_top10)

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
                labels={'ano_mes_str': 'Mês', 'indice': 'Índice'},
                custom_data=['hover_top10']
            )
            fig_indice.update_traces(
                hovertemplate=(
                    '<b>%{x}</b><br>'
                    'Índice: %{y:.2f}<br><br>'
                    '%{customdata[0]}'
                    '<extra></extra>'
                )
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
                mes_ultimo = meses_disponiveis[-1]
                precos_atual = df_pivot.loc[mes_ultimo]
                df_pesos = pd.DataFrame([
                    {
                        'produto': prod,
                        'peso_%': pesos[prod] * 100,
                        'preco_base': precos_base[prod],
                        'preco_atual': precos_atual[prod],
                        'variacao_%': ((precos_atual[prod] / precos_base[prod]) - 1) * 100
                        if precos_base[prod] > 0 else float('nan')
                    }
                    for prod in produtos_cesta
                ]).sort_values('peso_%', ascending=False)
                st.dataframe(
                    df_pesos.style.format({
                        'peso_%': '{:.2f}%',
                        'preco_base': 'R$ {:.2f}',
                        'preco_atual': 'R$ {:.2f}',
                        'variacao_%': '{:+.2f}%'
                    }),
                    use_container_width=True
                )

            with st.expander("Ver preços médios mensais por produto"):
                df_pivot_display = df_pivot.copy()
                df_pivot_display.index = df_pivot_display.index.astype(str)
                st.dataframe(
                    df_pivot_display.style.format('R$ {:.2f}'),
                    use_container_width=True
                )

# ==========================================
# ABA 5: PRODUTOS MAIS COMPRADOS
# ==========================================
with tab5:
    st.markdown("### 🏆 Produtos Mais Comprados")
    st.markdown("Ranking dos produtos pela **quantidade de vezes** que aparecem nas notas fiscais, do mais frequente ao menos frequente.")

    df_freq = (
        df.groupby('produto')
        .size()
        .reset_index(name='vezes_comprado')
        .sort_values('vezes_comprado', ascending=False)
        .reset_index(drop=True)
    )
    df_freq.index += 1  # Ranking começa em 1
    df_freq.index.name = 'Posição'
    df_freq = df_freq.rename(columns={'produto': 'Produto', 'vezes_comprado': 'Vezes Comprado'})

    top_n = st.slider("Exibir top N produtos no gráfico:", min_value=5, max_value=min(50, len(df_freq)), value=min(20, len(df_freq)))

    fig_freq = px.bar(
        df_freq.head(top_n),
        x='Produto',
        y='Vezes Comprado',
        title=f"Top {top_n} Produtos Mais Comprados",
        text_auto=True,
        color='Vezes Comprado',
        color_continuous_scale='Blues',
    )
    fig_freq.update_layout(xaxis_tickangle=-45, coloraxis_showscale=False)
    st.plotly_chart(fig_freq, use_container_width=True)

    st.divider()
    st.markdown("#### Tabela Completa")
    
    # Filtro por nome
    busca_produto = st.text_input("🔍 Filtrar produtos por Nome", placeholder="Digite parte do nome do produto...")
    
    df_freq_filtrado = df_freq
    if busca_produto:
        df_freq_filtrado = df_freq[df_freq['Produto'].str.contains(busca_produto, case=False, na=False)]
    
    st.dataframe(df_freq_filtrado, use_container_width=True)