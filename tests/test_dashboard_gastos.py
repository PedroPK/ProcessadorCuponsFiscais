from html.parser import HTMLParser

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard_gastos import agrupar_periodos, cor_gasto_dia, filtrar_periodo, preparar_gastos, tabela_dia_mesclada


@pytest.fixture
def gastos():
    return pd.DataFrame({
        'data': pd.to_datetime(['2023-12-31', '2024-02-01', '2024-02-29', None]),
        'categoria': ['Mercado', None, '  ', 'Mercado'],
        'produto': ['Arroz', 'Leite', 'Pão', 'Ovos'],
        'preco_total': [20.0, 10.0, 5.0, 100.0],
    })


def test_periodos_e_categorias_sem_data(gastos):
    preparados = preparar_gastos(gastos)
    assert preparados['preco_total'].sum() == 35
    assert preparados['categoria'].tolist() == ['Mercado', 'Sem categoria', 'Sem categoria']
    assert filtrar_periodo(preparados, 2024, None)['preco_total'].sum() == 15
    fevereiro = filtrar_periodo(preparados, 2024, 2)
    assert fevereiro['preco_total'].sum() == 15
    assert fevereiro.groupby('categoria')['preco_total'].sum().to_dict() == {'Sem categoria': 15}
    assert filtrar_periodo(preparados, 2024, 3).empty
    meses = agrupar_periodos(filtrar_periodo(preparados, 2024, None), 'mes')
    assert len(meses) == 12
    assert meses.loc[meses['mes'] == 2, 'preco_total'].iloc[0] == 15
    assert meses.loc[meses['mes'] == 3, 'preco_total'].iloc[0] == 0


def test_csv_sem_coluna_categoria(gastos):
    preparados = preparar_gastos(gastos.drop(columns='categoria'))
    assert preparados['categoria'].tolist() == ['Sem categoria'] * 3


def test_cor_dos_dias_reflete_gasto_relativo():
    assert cor_gasto_dia(0, 0) == cor_gasto_dia(0, 100)
    assert cor_gasto_dia(-10, 100) == cor_gasto_dia(0, 100)
    claro = cor_gasto_dia(10, 100)
    escuro = cor_gasto_dia(100, 100)
    assert claro != escuro
    assert int(claro[1:], 16) > int(escuro[1:], 16)
    assert cor_gasto_dia(10, 10) == escuro


def test_tabela_mescla_apenas_valores_consecutivos_da_mesma_data():
    detalhes = pd.DataFrame({
        'Data': ['01/02/2024'] * 4 + ['02/02/2024'],
        'Hora': ['10:00:00', '10:00:00', '11:00:00', '10:00:00', '10:00:00'],
        'Produto': ['<script>x</script>', 'Leite', 'Pão', 'Ovos', 'Café'],
        'Total': [1.0, 2.0, 3.0, 4.0, 5.0],
    })
    html = tabela_dia_mesclada(detalhes)

    class LeitorTabela(HTMLParser):
        def __init__(self):
            super().__init__()
            self.linhas = []
            self.no_corpo = False

        def handle_starttag(self, tag, attrs):
            if tag == 'tbody':
                self.no_corpo = True
            elif self.no_corpo and tag == 'tr':
                self.linhas.append([])
            elif self.no_corpo and tag == 'td':
                self.linhas[-1].append([dict(attrs).get('rowspan', '1'), ''])

        def handle_data(self, data):
            if self.no_corpo and self.linhas and self.linhas[-1]:
                self.linhas[-1][-1][1] += data

        def handle_endtag(self, tag):
            if tag == 'tbody':
                self.no_corpo = False

    leitor = LeitorTabela()
    leitor.feed(html)
    assert leitor.linhas == [
        [['4', '01/02/2024'], ['2', '10:00:00'], ['1', '<script>x</script>'], ['1', 'R$ 1,00']],
        [['1', 'Leite'], ['1', 'R$ 2,00']],
        [['1', '11:00:00'], ['1', 'Pão'], ['1', 'R$ 3,00']],
        [['1', '10:00:00'], ['1', 'Ovos'], ['1', 'R$ 4,00']],
        [['1', '02/02/2024'], ['1', '10:00:00'], ['1', 'Café'], ['1', 'R$ 5,00']],
    ]
    assert '<script>' not in html


def test_calendario_e_detalhes_do_dia():
    app = AppTest.from_string("""
import pandas as pd
from dashboard_gastos import exibir_dashboard_gastos
df = pd.DataFrame({
    'data': pd.to_datetime(['2024-02-01', '2024-02-29', '2023-02-01']),
    'produto': ['Leite', 'Pão', 'Arroz'],
    'categoria': ['Mercado', 'Padaria', 'Mercado'],
    'preco_total': [10.0, 5.0, 50.0],
})
exibir_dashboard_gastos(df)
""")
    app.session_state['gastos_ano'] = 2024
    app.session_state['gastos_mes'] = 2
    app.run()
    assert not app.exception
    assert app.metric[0].value == 'R$ 15,00'
    assert len([b for b in app.button if b.key and b.key.startswith('gastos_dia_')]) == 29
    estilo = next(element.value for element in app.markdown if '.st-key-gastos_dia_' in element.value)
    assert f'.st-key-gastos_dia_2024-02-29 button {{ background-color: {cor_gasto_dia(5, 10)}; }}' in estilo
    assert app.button(key='gastos_dia_2024-02-29').label == '29  \n**R$ 5,00**'
    app.button(key='gastos_dia_2024-02-29').click().run()
    assert not app.exception
    assert app.metric[1].value == 'R$ 5,00'
    assert app.dataframe[0].value['Produto'].tolist() == ['Pão']
    assert app.dataframe[0].value['Hora'].tolist() == ['Não informada']
    app.button(key='gastos_dia_2024-02-02').click().run()
    assert app.metric[1].value == 'R$ 0,00'
    assert any('Nenhum gasto neste dia' in element.value for element in app.info)
    app.button[1].click().run()
    assert app.session_state['gastos_mes'] is None
    assert app.metric[0].value == 'R$ 15,00'


def test_detalhes_do_dia_exibem_horarios_reais_e_ausentes():
    app = AppTest.from_string("""
import pandas as pd
from dashboard_gastos import exibir_dashboard_gastos
df = pd.DataFrame({
    'data': pd.to_datetime(['2024-02-01'] * 4),
    'hora': ['13:01:36', '13:01:36', '00:00:00', None],
    'produto': ['Leite', 'Arroz', 'Pão', 'Ovos'],
    'categoria': ['Mercado'] * 4,
    'preco_total': [10.0, 2.0, 5.0, 3.0],
})
exibir_dashboard_gastos(df)
""")
    app.session_state['gastos_ano'] = 2024
    app.session_state['gastos_mes'] = 2
    app.run()
    app.button(key='gastos_dia_2024-02-01').click().run()
    assert not app.exception
    detalhes = app.dataframe[0].value
    assert list(detalhes.columns[:2]) == ['Data', 'Hora']
    assert detalhes['Hora'].tolist() == ['13:01:36', '13:01:36', '00:00:00', 'Não informada']
    html = app.get('html')[0].proto.body
    assert '<td rowspan="4">01/02/2024</td>' in html
    assert '<td rowspan="2">13:01:36</td>' in html
    assert 'Não informada' in html
    assert any(expander.label == 'Abrir tabela interativa' for expander in app.expander)


def test_categoria_negativa_usa_tabela_sem_ocultar_valores():
    app = AppTest.from_string("""
import pandas as pd
from dashboard_gastos import exibir_dashboard_gastos
df = pd.DataFrame({
    'data': pd.to_datetime(['2024-01-01', '2024-01-02']),
    'categoria': ['Mercado', 'Devolução'],
    'produto': ['Leite', 'Arroz'],
    'preco_total': [10.0, -3.0],
})
exibir_dashboard_gastos(df)
""").run()
    assert not app.exception
    assert app.metric[0].value == 'R$ 7,00'
    assert any('total negativo' in warning.value for warning in app.warning)
    assert app.dataframe[0].value.set_index('categoria')['preco_total'].to_dict() == {
        'Mercado': 10.0, 'Devolução': -3.0,
    }
