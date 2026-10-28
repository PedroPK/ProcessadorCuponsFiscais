"""Coleta e persistência local de métricas agregadas do processamento."""

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from uuid import uuid4


CAMINHO_METRICAS = (
    Path(__file__).resolve().parent.parent
    / 'resources'
    / 'outputData'
    / 'metrics'
    / 'processamento.jsonl'
)


class MetricasProcessamento:
    """Agrega durações, chamadas e erros de uma execução do processador."""

    def __init__(self, caminho: Path | None = None):
        self.caminho = Path(caminho) if caminho else CAMINHO_METRICAS
        self._inicio = time.perf_counter()
        self._iniciado_em = datetime.now(timezone.utc).isoformat()
        self._etapas: dict[str, dict[str, float | int]] = {}
        self._erros_por_etapa: dict[str, int] = {}
        self._itens_extraidos = 0

    @contextmanager
    def medir(self, etapa: str):
        """Registra duração e quantidade de chamadas de uma etapa."""
        inicio = time.perf_counter()
        try:
            yield
        finally:
            duracao = time.perf_counter() - inicio
            dados = self._etapas.setdefault(
                etapa,
                {'chamadas': 0, 'duracao_total_segundos': 0.0, 'duracao_max_segundos': 0.0},
            )
            dados['chamadas'] += 1
            dados['duracao_total_segundos'] += duracao
            dados['duracao_max_segundos'] = max(dados['duracao_max_segundos'], duracao)

    def registrar_erro(self, etapa: str) -> None:
        """Conta uma falha capturada durante a etapa."""
        self._erros_por_etapa[etapa] = self._erros_por_etapa.get(etapa, 0) + 1

    def registrar_itens(self, quantidade: int) -> None:
        """Acumula o número de itens fiscais extraídos."""
        self._itens_extraidos += quantidade

    def finalizar(self, status: str) -> dict:
        """Persiste e retorna o resumo agregado desta execução."""
        if status == 'sucesso' and self._erros_por_etapa:
            status = 'parcial'

        etapas = {}
        for nome, dados in self._etapas.items():
            chamadas = int(dados['chamadas'])
            duracao_total = float(dados['duracao_total_segundos'])
            etapas[nome] = {
                **dados,
                'duracao_media_segundos': duracao_total / chamadas if chamadas else 0.0,
            }

        finalizado_em = datetime.now(timezone.utc).isoformat()
        resumo = {
            'execucao_id': str(uuid4()),
            'iniciada_em': self._iniciado_em,
            'finalizada_em': finalizado_em,
            'status': status,
            'duracao_total_segundos': time.perf_counter() - self._inicio,
            'itens_extraidos': self._itens_extraidos,
            'total_erros': sum(self._erros_por_etapa.values()),
            'erros_por_etapa': self._erros_por_etapa,
            'etapas': etapas,
        }

        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self.caminho.open('a', encoding='utf-8') as arquivo:
            arquivo.write(json.dumps(resumo, ensure_ascii=False) + '\n')
        return resumo


def medir_etapa(nome: str):
    """Decora um método do processador para registrar sua duração."""
    def decorar(funcao):
        @wraps(funcao)
        def envolvida(self, *args, **kwargs):
            try:
                with self.metricas.medir(nome):
                    return funcao(self, *args, **kwargs)
            except Exception:
                self.metricas.registrar_erro(nome)
                raise
        return envolvida
    return decorar


def carregar_ultima_execucao(caminho: Path = CAMINHO_METRICAS) -> dict | None:
    """Lê o registro mais recente do histórico JSONL, se existir."""
    caminho = Path(caminho)
    if not caminho.exists():
        return None

    linhas = caminho.read_text(encoding='utf-8').splitlines()
    for linha in reversed(linhas):
        if linha.strip():
            return json.loads(linha)
    return None
