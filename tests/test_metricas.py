import json

import pytest

from metricas import MetricasProcessamento, carregar_ultima_execucao


class TestMetricasProcessamento:
    def test_agrega_duracao_e_chamadas_por_etapa(self, tmp_path):
        metricas = MetricasProcessamento(tmp_path / 'processamento.jsonl')

        with metricas.medir('xml'):
            pass
        with metricas.medir('xml'):
            pass

        resumo = metricas.finalizar('sucesso')

        assert resumo['etapas']['xml']['chamadas'] == 2
        assert resumo['etapas']['xml']['duracao_total_segundos'] >= 0
        assert resumo['etapas']['xml']['duracao_media_segundos'] >= 0

    def test_persiste_resumo_e_le_execucao_mais_recente(self, tmp_path):
        caminho = tmp_path / 'processamento.jsonl'
        primeira = MetricasProcessamento(caminho).finalizar('sucesso')
        segunda = MetricasProcessamento(caminho).finalizar('sucesso')

        linhas = caminho.read_text(encoding='utf-8').splitlines()
        assert len(linhas) == 2
        assert json.loads(linhas[0])['execucao_id'] == primeira['execucao_id']
        assert carregar_ultima_execucao(caminho)['execucao_id'] == segunda['execucao_id']

    def test_execucao_com_erro_fica_parcial(self, tmp_path):
        metricas = MetricasProcessamento(tmp_path / 'processamento.jsonl')
        metricas.registrar_erro('xml')

        resumo = metricas.finalizar('sucesso')

        assert resumo['status'] == 'parcial'
        assert resumo['total_erros'] == 1
        assert resumo['erros_por_etapa'] == {'xml': 1}

    def test_carregar_sem_arquivo_retorna_none(self, tmp_path):
        assert carregar_ultima_execucao(tmp_path / 'inexistente.jsonl') is None

    def test_arquivo_malformado_gera_erro_explicito(self, tmp_path):
        caminho = tmp_path / 'processamento.jsonl'
        caminho.write_text('{invalido}\n', encoding='utf-8')

        with pytest.raises(json.JSONDecodeError):
            carregar_ultima_execucao(caminho)
