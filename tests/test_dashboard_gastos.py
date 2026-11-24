import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard_gastos import agrupar_periodos, filtrar_periodo, preparar_gastos


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
    app.button(key='gastos_dia_2024-02-29').click().run()
    assert not app.exception
    assert app.metric[1].value == 'R$ 5,00'
    assert app.dataframe[0].value['Produto'].tolist() == ['Pão']
    app.button(key='gastos_dia_2024-02-02').click().run()
    assert app.metric[1].value == 'R$ 0,00'
    assert any('Nenhum gasto neste dia' in element.value for element in app.info)
    app.button[1].click().run()
    assert app.session_state['gastos_mes'] is None
    assert app.metric[0].value == 'R$ 15,00'


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
