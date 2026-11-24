"""Aba de gastos por período e categoria."""

import calendar
from datetime import date
from html import escape
from itertools import groupby

import altair as alt
import pandas as pd
import streamlit as st

from utils import format_currency


MESES = (
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
)


def preparar_gastos(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara os registros com data e identifica categorias não informadas."""
    gastos = df.loc[df['data'].notna()].copy()
    if 'categoria' not in gastos.columns:
        gastos['categoria'] = 'Sem categoria'
    else:
        categorias = gastos['categoria'].fillna('').astype(str).str.strip()
        gastos['categoria'] = categorias.mask(categorias == '', 'Sem categoria')
    return gastos


def filtrar_periodo(df: pd.DataFrame, ano: int | None, mes: int | None) -> pd.DataFrame:
    """Filtra os itens pelo ano e, quando informado, pelo mês."""
    if ano is not None:
        df = df.loc[df['data'].dt.year == ano]
        if mes is not None:
            df = df.loc[df['data'].dt.month == mes]
    return df


def agrupar_periodos(df: pd.DataFrame, campo: str) -> pd.DataFrame:
    """Soma gastos por ano ou mês, incluindo meses sem gastos."""
    datas = df['data'].dt.year if campo == 'ano' else df['data'].dt.month
    totais = df.assign(**{campo: datas}).groupby(campo, as_index=False)['preco_total'].sum()
    if campo == 'mes':
        totais = pd.DataFrame({'mes': range(1, 13)}).merge(totais, on='mes', how='left')
        totais['preco_total'] = totais['preco_total'].fillna(0)
        totais['nome_mes'] = [MESES[mes - 1] for mes in totais['mes']]
    return totais


def cor_gasto_dia(valor: float, maior_gasto: float) -> str:
    """Calcula a cor do card em relação ao maior gasto positivo do mês."""
    if valor <= 0 or maior_gasto <= 0:
        return '#f0f2f6'
    intensidade = min(valor / maior_gasto, 1)
    claro = (255, 241, 238)
    escuro = (219, 87, 75)
    componentes = [round(inicio + (fim - inicio) * intensidade)
                   for inicio, fim in zip(claro, escuro)]
    return '#{:02x}{:02x}{:02x}'.format(*componentes)


def tabela_dia_mesclada(detalhes: pd.DataFrame) -> str:
    """Gera uma tabela HTML com data e hora consecutivas mescladas."""
    registros = detalhes.to_dict('records')
    spans = {}
    for coluna, chave in (
        ('Data', lambda registro: registro['Data']),
        ('Hora', lambda registro: (registro['Data'], registro['Hora'])),
    ):
        for _, grupo in groupby(enumerate(registros), key=lambda item: chave(item[1])):
            indices = [indice for indice, _ in grupo]
            spans[(indices[0], coluna)] = len(indices)

    cabecalho = ''.join(f'<th scope="col">{escape(str(coluna))}</th>' for coluna in detalhes.columns)
    linhas = []
    for indice, registro in enumerate(registros):
        celulas = []
        for coluna, valor in registro.items():
            if coluna in ('Data', 'Hora'):
                if (indice, coluna) not in spans:
                    continue
                atributo = f' rowspan="{spans[(indice, coluna)]}"'
            else:
                atributo = ''
            if coluna in ('Quantidade', 'Preço unitário', 'Total'):
                atributo += ' class="valor"'
            if pd.isna(valor):
                texto = ''
            elif coluna in ('Preço unitário', 'Total'):
                texto = format_currency(valor)
            else:
                texto = str(valor)
            celulas.append(f'<td{atributo}>{escape(texto)}</td>')
        linhas.append('<tr>' + ''.join(celulas) + '</tr>')

    return (
        '<style>'
        '.gastos-dia-tabela { overflow: auto; max-height: 400px; }'
        '.gastos-dia-tabela table { border-collapse: collapse; width: 100%; font-size: 0.875rem; }'
        '.gastos-dia-tabela th, .gastos-dia-tabela td { '
        'border: 1px solid rgba(128, 128, 128, 0.35); padding: 0.5rem; '
        'text-align: left; vertical-align: middle; white-space: nowrap; }'
        '.gastos-dia-tabela td.valor { text-align: right; }'
        '</style>'
        '<div class="gastos-dia-tabela"><table aria-label="Detalhes dos gastos do dia">'
        f'<thead><tr>{cabecalho}</tr></thead><tbody>{"".join(linhas)}</tbody>'
        '</table></div>'
    )


@st.dialog("Detalhes dos gastos", width="large")
def exibir_detalhes(titulo: str, itens: pd.DataFrame, mostrar_hora: bool = False) -> None:
    """Exibe os itens e o total do dia ou categoria selecionados."""
    st.subheader(titulo)
    st.metric("Total", format_currency(itens['preco_total'].sum()))
    if itens.empty:
        st.info("Nenhum gasto neste dia.")
        return
    colunas = {
        'data': 'Data', 'loja': 'Loja', 'categoria': 'Categoria',
        'produto': 'Produto', 'qtd': 'Quantidade', 'unidade': 'Unidade',
        'preco_unit': 'Preço unitário', 'preco_total': 'Total',
        'arquivo_origem': 'Arquivo de origem',
    }
    detalhes = itens[[c for c in colunas if c in itens.columns]].copy()
    detalhes['data'] = detalhes['data'].dt.strftime('%d/%m/%Y')
    if mostrar_hora:
        if 'hora' in itens.columns:
            horas = itens['hora'].fillna('').astype(str).str.strip()
            horas = horas.mask(horas == '', 'Não informada')
        else:
            horas = 'Não informada'
        detalhes.insert(1, 'Hora', horas)
    detalhes = detalhes.rename(columns=colunas)
    if mostrar_hora:
        st.html(tabela_dia_mesclada(detalhes))
        with st.expander("Abrir tabela interativa"):
            _exibir_tabela_interativa(detalhes)
    else:
        _exibir_tabela_interativa(detalhes)


def _exibir_tabela_interativa(detalhes: pd.DataFrame) -> None:
    """Exibe a tabela original com busca, ordenação e download."""
    st.dataframe(
        detalhes, hide_index=True, use_container_width=True,
        column_config={
            'Preço unitário': st.column_config.NumberColumn(format="R$ %.2f"),
            'Total': st.column_config.NumberColumn(format="R$ %.2f"),
        },
    )


def _selecionar_periodo(chave: str, campo: str) -> None:
    selecao = st.session_state[chave]['selection']['periodo']
    if selecao:
        st.session_state[f'gastos_{campo}'] = int(selecao[0][campo])
        st.session_state['gastos_versao'] += 1


def _selecionar_categoria(chave: str) -> None:
    selecao = st.session_state[chave]['selection']['categoria']
    if selecao:
        st.session_state['gastos_categoria_popup'] = selecao[0]['categoria']
        st.session_state['gastos_versao'] += 1


def _voltar(nivel: str) -> None:
    if nivel == 'anos':
        st.session_state['gastos_ano'] = None
    st.session_state['gastos_mes'] = None
    st.session_state['gastos_versao'] += 1


def exibir_dashboard_gastos(df: pd.DataFrame) -> None:
    """Renderiza a navegação de gastos por ano, mês, dia e categoria."""
    st.subheader("Dashboard de Gastos")
    st.session_state.setdefault('gastos_ano', None)
    st.session_state.setdefault('gastos_mes', None)
    st.session_state.setdefault('gastos_versao', 0)

    gastos = preparar_gastos(df)
    sem_data = len(df) - len(gastos)
    if sem_data:
        st.warning(f"{sem_data} item(ns) sem data foram excluídos deste dashboard.")
    if gastos.empty:
        st.info("Não há gastos com data para exibir.")
        return

    ano = st.session_state['gastos_ano']
    mes = st.session_state['gastos_mes']
    periodo = filtrar_periodo(gastos, ano, mes)
    versao = st.session_state['gastos_versao']

    if ano is None:
        titulo = 'Todos os anos'
    elif mes is None:
        st.button("← Todos os anos", on_click=_voltar, args=('anos',))
        titulo = str(ano)
    else:
        col_anos, col_ano = st.columns(2)
        col_anos.button("← Todos os anos", on_click=_voltar, args=('anos',))
        col_ano.button(f"← {ano}", on_click=_voltar, args=('ano',))
        titulo = f'{MESES[mes - 1]} de {ano}'

    st.markdown(f"#### {titulo}")
    st.metric("Total dos gastos no período", format_currency(periodo['preco_total'].sum()))

    if mes is None:
        campo = 'ano' if ano is None else 'mes'
        dados_barras = agrupar_periodos(periodo, campo)
        if not dados_barras.empty:
            selecao = alt.selection_point(name='periodo', fields=[campo], toggle=False)
            eixo_x = (alt.X('ano:O', title='Ano') if ano is None
                      else alt.X('nome_mes:N', title='Mês', sort=list(MESES)))
            base = alt.Chart(dados_barras).encode(
                x=eixo_x,
                y=alt.Y('preco_total:Q', title='Gastos (R$)'),
                tooltip=[alt.Tooltip('ano:O', title='Ano') if ano is None
                         else alt.Tooltip('nome_mes:N', title='Mês'),
                         alt.Tooltip('preco_total:Q', title='Gastos (R$)', format='.2f')],
            )
            barras = base.mark_bar()
            if (dados_barras['preco_total'] == 0).any():
                barras += base.transform_filter(
                    alt.datum.preco_total == 0
                ).mark_point(filled=True, size=100)
            barras = barras.add_params(selecao)
            st.caption("Clique em uma barra ou no ponto de valor zero para detalhar o período.")
            chave = f'gastos_barras_{campo}_{ano}_{versao}'
            st.altair_chart(barras, use_container_width=True, key=chave,
                            on_select=lambda chave=chave, campo=campo: _selecionar_periodo(chave, campo))
        else:
            st.info("Não há gastos neste período para o filtro selecionado.")
    else:
        st.caption("Quanto mais escuro o card, maior o gasto em relação aos demais dias do mês. "
                   "Clique em um dia para ver os itens, inclusive nos dias sem gastos.")
        dias = periodo.groupby(periodo['data'].dt.date)['preco_total'].sum()
        maior_gasto = max(0, dias.max()) if not dias.empty else 0
        estilos_dias = []
        for dia_data, valor in dias.items():
            cor = cor_gasto_dia(valor, maior_gasto)
            estilos_dias.append(f'.st-key-gastos_dia_{dia_data} button {{ background-color: {cor}; }}')
        st.markdown(
            """
            <style>
            [class*="st-key-gastos_dia_"] button {
                min-height: 84px;
                justify-content: flex-start;
                text-align: left;
                background-color: #f0f2f6;
                color: #171717;
                border: 1px solid #dedfe3;
                position: relative;
            }
            [class*="st-key-gastos_dia_"] button > div { 
                width: 100%; 
                display: flex;
                flex-direction: column;
            }
            [class*="st-key-gastos_dia_"] button p {
                color: #171717;
                text-align: left;
                font-size: 1.1rem;
                line-height: 1.4;
                margin: 0;
                font-weight: 600;
                order: 1;
            }
            [class*="st-key-gastos_dia_"] button strong { 
                color: #171717; 
                font-size: 1.5rem; 
                order: 2;
                margin-top: auto;
            }
            [class*="st-key-gastos_dia_"] button:hover { border-color: #a52e28; color: #171717; }
            """ + '\n'.join(estilos_dias) + """
            </style>
            """,
            unsafe_allow_html=True,
        )
        cabecalho = st.columns(7)
        for coluna, nome in zip(cabecalho, ('Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom')):
            coluna.markdown(f"**{nome}**")
        for semana in calendar.Calendar(firstweekday=0).monthdayscalendar(ano, mes):
            colunas = st.columns(7)
            for coluna, dia in zip(colunas, semana):
                if dia:
                    data = date(ano, mes, dia)
                    if coluna.button(f"{dia}  \n**{format_currency(dias.get(data, 0))}**",
                                     key=f'gastos_dia_{data}', use_container_width=True):
                        itens = periodo.loc[periodo['data'].dt.date == data]
                        exibir_detalhes(data.strftime('%d/%m/%Y'), itens, mostrar_hora=True)

    st.markdown("#### Gastos por categoria")
    categorias = periodo.groupby('categoria', as_index=False)['preco_total'].sum()
    if (categorias['preco_total'] < 0).any():
        st.warning("O gráfico de pizza não representa categorias com total negativo. Veja os valores abaixo.")
        st.dataframe(categorias, hide_index=True, use_container_width=True)
    elif categorias.empty or not (categorias['preco_total'] > 0).any():
        st.info("Não há valores positivos para exibir no gráfico de categorias.")
    else:
        categorias = categorias.loc[categorias['preco_total'] > 0]
        selecao = alt.selection_point(name='categoria', fields=['categoria'], toggle=False)
        pizza = (
            alt.Chart(categorias).mark_arc().encode(
                theta=alt.Theta('preco_total:Q', title='Gastos (R$)'),
                color=alt.Color('categoria:N', title='Categoria'),
                tooltip=[alt.Tooltip('categoria:N', title='Categoria'),
                         alt.Tooltip('preco_total:Q', title='Gastos (R$)', format='.2f')],
            ).add_params(selecao)
        )
        st.caption("Clique em uma fatia para ver os itens da categoria neste período.")
        chave = f'gastos_pizza_{ano}_{mes}_{versao}'
        st.altair_chart(pizza, use_container_width=True, key=chave,
                        on_select=lambda chave=chave: _selecionar_categoria(chave))
        categoria = st.session_state.pop('gastos_categoria_popup', None)
        if categoria is not None:
            exibir_detalhes(categoria, periodo.loc[periodo['categoria'] == categoria])
