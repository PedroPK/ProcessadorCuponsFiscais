import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import pydeck as pdk
import html
import os
import signal
import threading
import subprocess
import sys
import platform
import json
import urllib.parse
import urllib.request
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


@st.cache_data(ttl=60 * 60 * 24)
def geocodificar_endereco(endereco: str):
    """Geocodifica endereço no Nominatim e retorna (lat, lon) ou (None, None)."""
    if not endereco or not str(endereco).strip():
        return (None, None)

    query = urllib.parse.urlencode({'q': endereco, 'format': 'jsonv2', 'limit': 1})
    url = f'https://nominatim.openstreetmap.org/search?{query}'
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'ProcessadorCuponsFiscais/1.0 (dashboard streamlit)'
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        if not payload:
            return (None, None)
        lat = float(payload[0].get('lat'))
        lon = float(payload[0].get('lon'))
        return (lat, lon)
    except Exception:
        return (None, None)


def preparar_mapa_compras(df_compras: pd.DataFrame):
    """Retorna DataFrame com lat/lon por compra filtrada para exibição no mapa."""
    if 'endereco' not in df_compras.columns:
        return pd.DataFrame()

    df_end = df_compras.copy()
    df_end['endereco'] = df_end['endereco'].fillna('').astype(str).str.strip()
    df_end = df_end[df_end['endereco'] != '']
    if df_end.empty:
        return pd.DataFrame()

    unicos = df_end['endereco'].drop_duplicates().tolist()
    coords = []
    for endereco in unicos:
        lat, lon = geocodificar_endereco(f'{endereco}, Brasil')
        coords.append({'endereco': endereco, 'lat': lat, 'lon': lon})

    df_coords = pd.DataFrame(coords)
    if df_coords.empty:
        return pd.DataFrame()

    df_coords = df_coords.dropna(subset=['lat', 'lon'])
    if df_coords.empty:
        return pd.DataFrame()

    return df_end.merge(df_coords, on='endereco', how='inner')


def _formatar_itens_nf_html(grupo_itens: pd.DataFrame, limite: int = 12) -> str:
    """Retorna HTML com os principais itens de uma NF para tooltip do mapa."""
    if grupo_itens.empty:
        return 'Sem itens detalhados.'

    df_itens = (
        grupo_itens.groupby(['produto', 'unidade'], dropna=False)
        .agg(qtd=('qtd', 'sum'), valor=('preco_total', 'sum'))
        .reset_index()
        .sort_values('valor', ascending=False)
    )

    linhas = []
    for _, item in df_itens.head(limite).iterrows():
        produto = html.escape(str(item.get('produto', '') or '-'))
        unidade = html.escape(str(item.get('unidade', '') or '').strip())
        qtd = float(item.get('qtd', 0) or 0)
        valor = float(item.get('valor', 0) or 0)

        if unidade:
            linhas.append(f'• {produto} ({qtd:.2f} {unidade}) - R$ {valor:.2f}')
        else:
            linhas.append(f'• {produto} ({qtd:.2f}) - R$ {valor:.2f}')

    if len(df_itens) > limite:
        linhas.append(f'+ {len(df_itens) - limite} item(ns) ...')

    return '<br/>'.join(linhas)


def preparar_mapa_notas(df_compras: pd.DataFrame):
    """Retorna DataFrame de notas com coordenadas e resumo para mapa por NF."""
    if 'endereco' not in df_compras.columns:
        return pd.DataFrame()

    df_end = df_compras.copy()
    df_end['endereco'] = df_end['endereco'].fillna('').astype(str).str.strip()
    df_end = df_end[df_end['endereco'] != '']
    if df_end.empty:
        return pd.DataFrame()

    chave = (
        df_end['chave_nfe'].fillna('').astype(str).str.strip()
        if 'chave_nfe' in df_end.columns
        else pd.Series('', index=df_end.index)
    )
    fallback = (
        df_end['arquivo_origem'].fillna('').astype(str).str.strip() + '|'
        + df_end['data'].dt.strftime('%Y-%m-%d') + '|'
        + df_end['loja'].fillna('').astype(str).str.strip() + '|'
        + df_end['endereco']
    )
    df_end['id_nota'] = chave.where(chave != '', fallback)

    grupos_nf = []
    for (id_nota, endereco), grupo in df_end.groupby(['id_nota', 'endereco'], dropna=False):
        grupos_nf.append(
            {
                'id_nota': id_nota,
                'endereco': endereco,
                'loja': grupo['loja'].dropna().astype(str).iloc[0] if 'loja' in grupo.columns and not grupo['loja'].dropna().empty else 'Loja não informada',
                'data_nota': grupo['data'].max(),
                'arquivo_origem': grupo['arquivo_origem'].dropna().astype(str).iloc[0] if 'arquivo_origem' in grupo.columns and not grupo['arquivo_origem'].dropna().empty else '',
                'valor_total_nf': float(grupo['preco_total'].sum()),
                'qtd_itens': int(len(grupo)),
                'itens_html': _formatar_itens_nf_html(grupo),
            }
        )

    df_notas = pd.DataFrame(grupos_nf)
    if df_notas.empty:
        return pd.DataFrame()

    unicos = df_notas['endereco'].drop_duplicates().tolist()
    coords = []
    for endereco in unicos:
        lat, lon = geocodificar_endereco(f'{endereco}, Brasil')
        coords.append({'endereco': endereco, 'lat': lat, 'lon': lon})

    df_coords = pd.DataFrame(coords).dropna(subset=['lat', 'lon'])
    if df_coords.empty:
        return pd.DataFrame()

    df_notas = df_notas.merge(df_coords, on='endereco', how='inner')
    df_notas['data_nota'] = pd.to_datetime(df_notas['data_nota'], errors='coerce').dt.strftime('%d/%m/%Y')
    df_notas['valor_total_nf'] = df_notas['valor_total_nf'].map(lambda x: f'{x:.2f}')
    return df_notas

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
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📈 Evolução de Preços", "💰 Análise Pareto (ABC)", "📋 Dados Brutos", "📊 Índice de Inflação Pessoal", "🏆 Produtos Mais Comprados", "🗺️ Onde Comprar Melhor", "📍 Mapa de Compras (NF)"])

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
        'endereco': 'Endereço',
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

# ==========================================
# ABA 6: ONDE COMPRAR MELHOR
# ==========================================
with tab6:
    st.markdown("### 🗺️ Melhor Local para Comprar por Produto")
    st.markdown(
        "Busque um produto e um período para ver onde ele saiu mais barato. "
        "O ranking é ordenado do menor para o maior preço e o mapa exibe cada compra encontrada."
    )

    data_min = df['data'].min().date()
    data_max = df['data'].max().date()

    c1, c2 = st.columns([2, 1])
    busca_produto_melhor = c1.text_input(
        "Produto",
        placeholder="Ex.: leite, ovos, arroz...",
        key='busca_produto_melhor_preco',
    )
    periodo = c2.date_input(
        "Período",
        value=(data_min, data_max),
        min_value=data_min,
        max_value=data_max,
        key='periodo_melhor_preco',
    )

    if isinstance(periodo, tuple) and len(periodo) == 2:
        data_ini, data_fim = periodo
    else:
        data_ini, data_fim = data_min, data_max

    df_periodo = df[(df['data'].dt.date >= data_ini) & (df['data'].dt.date <= data_fim)].copy()
    df_busca = filtrar_produtos(df_periodo, busca_produto_melhor)

    if busca_produto_melhor and df_busca.empty:
        st.warning("Nenhuma compra encontrada para esse produto no período selecionado.")
    elif not busca_produto_melhor:
        st.info("Digite um produto para iniciar a busca de melhores locais de compra.")
    else:
        df_busca = df_busca.sort_values(['preco_unit', 'data'], ascending=[True, True])

        st.markdown("#### Ranking por estabelecimento")
        agrup_cols = ['loja']
        if 'endereco' in df_busca.columns:
            agrup_cols.append('endereco')

        df_rank = (
            df_busca.groupby(agrup_cols, dropna=False)
            .agg(
                menor_preco=('preco_unit', 'min'),
                preco_medio=('preco_unit', 'mean'),
                qtd_compras=('preco_unit', 'size'),
                ultima_compra=('data', 'max')
            )
            .reset_index()
            .sort_values(['menor_preco', 'preco_medio', 'qtd_compras'], ascending=[True, True, False])
        )

        top1, top2, top3 = st.columns(3)
        top1.metric("Menor preço encontrado", f"R$ {df_rank['menor_preco'].min():.2f}")
        top2.metric("Preço médio no período", f"R$ {df_busca['preco_unit'].mean():.2f}")
        top3.metric("Total de compras encontradas", f"{len(df_busca)}")

        st.dataframe(
            df_rank.style.format({
                'menor_preco': 'R$ {:.2f}',
                'preco_medio': 'R$ {:.2f}',
                'ultima_compra': lambda d: d.strftime('%d/%m/%Y') if pd.notna(d) else ''
            }),
            use_container_width=True
        )

        st.markdown("#### Compras encontradas (menor para maior preço)")
        cols_show = [c for c in ['data', 'produto', 'loja', 'endereco', 'qtd', 'unidade', 'preco_unit', 'preco_total', 'arquivo_origem'] if c in df_busca.columns]
        df_show = df_busca[cols_show].copy()
        df_show['data'] = df_show['data'].dt.strftime('%d/%m/%Y')
        st.dataframe(
            df_show,
            use_container_width=True,
            height=350
        )

        st.markdown("#### Mapa dos locais de compra")
        df_mapa = preparar_mapa_compras(df_busca)

        if df_mapa.empty:
            st.info(
                "Não foi possível montar o mapa para este filtro. "
                "Verifique se os cupons possuem endereço do estabelecimento."
            )
        else:
            df_mapa = df_mapa.copy()
            df_mapa['data'] = df_mapa['data'].dt.strftime('%d/%m/%Y')
            df_mapa['preco_unit'] = df_mapa['preco_unit'].map(lambda x: f'{x:.2f}')

            camada = pdk.Layer(
                'ScatterplotLayer',
                data=df_mapa,
                get_position='[lon, lat]',
                get_radius=80,
                get_fill_color='[0, 130, 90, 180]',
                pickable=True,
            )

            view_state = pdk.ViewState(
                latitude=float(df_mapa['lat'].mean()),
                longitude=float(df_mapa['lon'].mean()),
                zoom=11,
                pitch=0,
            )

            tooltip = {
                'html': (
                    '<b>Loja:</b> {loja}<br/>'
                    '<b>Endereço:</b> {endereco}<br/>'
                    '<b>Produto:</b> {produto}<br/>'
                    '<b>Preço Unitário:</b> R$ {preco_unit}<br/>'
                    '<b>Data:</b> {data}'
                ),
                'style': {
                    'backgroundColor': '#0f172a',
                    'color': 'white'
                }
            }

            st.pydeck_chart(
                pdk.Deck(
                    layers=[camada],
                    initial_view_state=view_state,
                    tooltip=tooltip,
                    map_style='https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
                ),
                use_container_width=True
            )

# ==========================================
# ABA 7: MAPA DE COMPRAS POR NOTA FISCAL
# ==========================================
with tab7:
    st.markdown("### 📍 Mapa de Compras por Nota Fiscal")
    st.markdown(
        "Mostra **1 pin por NF** com endereço. Passe o mouse no pin para ver "
        "resumo da nota e os itens comprados."
    )

    data_min_nf = df['data'].min().date()
    data_max_nf = df['data'].max().date()

    c1, c2 = st.columns([2, 1])
    filtro_loja_nf = c1.text_input(
        "Filtrar por loja (opcional)",
        placeholder="Ex.: supermercado, atacadão, farmácia...",
        key='filtro_loja_mapa_nf',
    )
    periodo_nf = c2.date_input(
        "Período das NFs",
        value=(data_min_nf, data_max_nf),
        min_value=data_min_nf,
        max_value=data_max_nf,
        key='periodo_mapa_nf',
    )

    if isinstance(periodo_nf, tuple) and len(periodo_nf) == 2:
        data_ini_nf, data_fim_nf = periodo_nf
    else:
        data_ini_nf, data_fim_nf = data_min_nf, data_max_nf

    df_nf = df[(df['data'].dt.date >= data_ini_nf) & (df['data'].dt.date <= data_fim_nf)].copy()

    if filtro_loja_nf and 'loja' in df_nf.columns:
        df_nf = df_nf[df_nf['loja'].fillna('').str.contains(filtro_loja_nf, case=False, na=False)]

    if df_nf.empty:
        st.warning("Nenhuma NF encontrada com os filtros selecionados.")
    else:
        df_mapa_nf = preparar_mapa_notas(df_nf)

        if df_mapa_nf.empty:
            st.info(
                "Não foi possível montar o mapa por NF para este filtro. "
                "Verifique se as notas possuem endereço e se foi possível geocodificá-las."
            )
        else:
            k1, k2, k3 = st.columns(3)
            k1.metric("Notas com pin no mapa", f"{len(df_mapa_nf)}")
            k2.metric("Total de itens nas NFs", f"{df_mapa_nf['qtd_itens'].sum()}")
            k3.metric(
                "Valor total das NFs mapeadas",
                f"R$ {pd.to_numeric(df_mapa_nf['valor_total_nf'], errors='coerce').sum():.2f}",
            )

            icon_data = {
                'url': 'https://img.icons8.com/fluency/48/marker-storm.png',
                'width': 128,
                'height': 128,
                'anchorY': 128,
            }
            df_mapa_nf['icon_data'] = [icon_data] * len(df_mapa_nf)

            camada_nf = pdk.Layer(
                'IconLayer',
                data=df_mapa_nf,
                get_icon='icon_data',
                get_size=4,
                size_scale=10,
                get_position='[lon, lat]',
                pickable=True,
            )

            view_state_nf = pdk.ViewState(
                latitude=float(df_mapa_nf['lat'].mean()),
                longitude=float(df_mapa_nf['lon'].mean()),
                zoom=10,
                pitch=0,
            )

            tooltip_nf = {
                'html': (
                    '<b>Loja:</b> {loja}<br/>'
                    '<b>Data:</b> {data_nota}<br/>'
                    '<b>Endereço:</b> {endereco}<br/>'
                    '<b>Total da NF:</b> R$ {valor_total_nf}<br/>'
                    '<b>Itens na NF:</b> {qtd_itens}<br/>'
                    '<hr style="margin:6px 0"/>'
                    '{itens_html}'
                ),
                'style': {
                    'backgroundColor': '#0f172a',
                    'color': 'white',
                    'maxWidth': '520px',
                    'fontSize': '12px',
                }
            }

            st.pydeck_chart(
                pdk.Deck(
                    layers=[camada_nf],
                    initial_view_state=view_state_nf,
                    tooltip=tooltip_nf,
                    map_style='https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
                ),
                use_container_width=True,
            )

            st.markdown("#### Resumo das notas plotadas")
            st.dataframe(
                df_mapa_nf[['data_nota', 'loja', 'endereco', 'qtd_itens', 'valor_total_nf', 'arquivo_origem']]
                .rename(columns={
                    'data_nota': 'Data',
                    'loja': 'Loja',
                    'endereco': 'Endereço',
                    'qtd_itens': 'Qtd Itens',
                    'valor_total_nf': 'Valor Total NF',
                    'arquivo_origem': 'Arquivo Origem',
                }),
                use_container_width=True,
                height=320,
            )