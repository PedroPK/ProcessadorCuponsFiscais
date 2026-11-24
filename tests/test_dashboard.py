import shutil
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from conftest import XML_VALIDO
import processadorCuponsFiscais
from processadorCuponsFiscais import ProcessadorDeCupons


def test_dashboard_preserva_identificadores_e_exibe_calendario(tmp_path):
    raiz = Path(__file__).resolve().parent.parent
    script = tmp_path / 'src' / 'dashboard.py'
    script.parent.mkdir()
    shutil.copyfile(raiz / 'src' / 'dashboard.py', script)

    pasta_csv = tmp_path / 'resources' / 'outputData'
    pasta_csv.mkdir(parents=True)
    chave = '0' + '1' * 43
    dados = pd.DataFrame({
        'data': ['01/02/2024'] * 4 + ['01/03/2024', '01/04/2024'],
        'hora': ['13:01:36', '00:00:00', '', '', '', ''],
        'loja': ['Loja Exemplo'] * 6,
        'produto': ['Arroz', 'Feijão', 'Leite', 'Pão', 'Ovos', 'Café'],
        'categoria': ['Mercado'] * 6,
        'qtd': [1] * 6,
        'unidade': ['UN'] * 6,
        'preco_unit': [10.0] * 6,
        'preco_total': [10.0] * 6,
        'codigo': ['0012', 'ABC', '', '', '', ''],
        'ean': ['0123456789012', '', '', '', '', ''],
        'ncm': ['00123456', '', '', '', '', ''],
        'cnpj': ['00123456000199', '', '', '', '', ''],
        'chave_nfe': [chave, chave, chave, chave, '', ''],
        'arquivo_origem': ['nota.xml'] * 6,
    })
    dados.to_csv(pasta_csv / 'minha_inflacao.csv', sep=';', decimal=',', index=False)

    app = AppTest.from_file(str(script), default_timeout=30)
    app.session_state['gastos_ano'] = 2024
    app.session_state['gastos_mes'] = 2
    app.run()
    assert not app.exception
    tabela_bruta = next(tabela.value for tabela in app.dataframe if 'Chave NF-e' in tabela.value.columns)
    assert tabela_bruta['Chave NF-e'].iloc[0] == chave
    assert tabela_bruta['CNPJ'].iloc[0] == '00123456000199'
    assert tabela_bruta['EAN'].iloc[0] == '0123456789012'
    assert tabela_bruta['Código'].iloc[0] == '0012'
    assert tabela_bruta['NCM'].iloc[0] == '00123456'
    assert pd.isna(tabela_bruta['Chave NF-e'].iloc[-1])

    app.button(key='gastos_dia_2024-02-01').click().run()
    assert not app.exception
    assert any(metric.value == 'R$ 40,00' for metric in app.metric)
    detalhes = next(tabela.value for tabela in app.dataframe if 'Hora' in tabela.value.columns and 'Data' in tabela.value.columns and 'Quantidade' in tabela.value.columns)
    assert list(detalhes.columns[:2]) == ['Data', 'Hora']
    assert detalhes['Hora'].tolist() == ['13:01:36', '00:00:00', 'Não informada', 'Não informada']


def test_hora_do_xml_chega_ao_popup(tmp_path, monkeypatch):
    raiz = Path(__file__).resolve().parent.parent
    script = tmp_path / 'src' / 'dashboard.py'
    script.parent.mkdir()
    shutil.copyfile(raiz / 'src' / 'dashboard.py', script)
    monkeypatch.setattr(processadorCuponsFiscais, '__file__', str(tmp_path / 'src' / 'processadorCuponsFiscais.py'))

    processador = ProcessadorDeCupons()
    processador.dados_consolidados = processadorCuponsFiscais.extrair_itens_do_xml(XML_VALIDO, 'nota.xml')
    processador.exportar_csv()

    st.cache_data.clear()
    app = AppTest.from_file(str(script), default_timeout=30)
    app.session_state['gastos_ano'] = 2026
    app.session_state['gastos_mes'] = 3
    app.run()
    app.button(key='gastos_dia_2026-03-01').click().run()
    assert not app.exception
    tabelas = [tabela.value for tabela in app.dataframe]
    assert any('Hora' in tabela.columns and 'Quantidade' in tabela.columns for tabela in tabelas), (
        [list(tabela.columns) for tabela in tabelas], [info.value for info in app.info]
    )
    detalhes = next(tabela for tabela in tabelas if 'Hora' in tabela.columns and 'Quantidade' in tabela.columns)
    assert detalhes['Hora'].tolist() == ['13:01:36', '13:01:36']
