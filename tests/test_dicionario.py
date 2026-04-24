"""
Testes para src/dicionario.py
"""
import pandas as pd
import pytest
from pathlib import Path
from dicionario import carregar_dados_existentes, sugerir_padrao


# ── carregar_dados_existentes ──────────────────────────────────────────────────

class TestCarregarDadosExistentes:
    def test_arquivo_inexistente_retorna_dataframe_vazio(self, tmp_path):
        df = carregar_dados_existentes(tmp_path / "nao_existe.xlsx")
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_colunas_corretas_quando_arquivo_inexistente(self, tmp_path):
        df = carregar_dados_existentes(tmp_path / "nao_existe.xlsx")
        assert list(df.columns) == ["nome_original", "nome_padrao", "categoria"]

    def test_carrega_arquivo_existente(self, tmp_path):
        xlsx = tmp_path / "dic.xlsx"
        pd.DataFrame([
            {"nome_original": "LEITE CX", "nome_padrao": "Leite Integral", "categoria": "Laticínios"},
        ]).to_excel(xlsx, index=False)

        df = carregar_dados_existentes(xlsx)
        assert len(df) == 1
        assert df.iloc[0]["nome_padrao"] == "Leite Integral"


# ── sugerir_padrao ─────────────────────────────────────────────────────────────

class TestSugerirPadrao:
    def test_match_alto_retorna_nome_conhecido(self):
        nomes_conhecidos = ["Leite Integral", "Pão Francês", "Arroz Branco"]
        resultado = sugerir_padrao("LEITE INTEGRAL 1L", nomes_conhecidos)
        assert resultado == "Leite Integral"

    def test_sem_match_suficiente_retorna_titulo(self):
        nomes_conhecidos = ["Leite Integral", "Arroz Branco"]
        resultado = sugerir_padrao("DETERGENTE NEUTRO 500ML", nomes_conhecidos)
        # Sem match > 80%, deve retornar o nome em Title Case
        assert resultado == "Detergente Neutro 500Ml"

    def test_lista_vazia_retorna_titulo(self):
        resultado = sugerir_padrao("FEIJAO CARIOCA", [])
        assert resultado == "Feijao Carioca"

    def test_lista_none_entries_ignoradas(self):
        nomes_conhecidos = [None, "Leite Integral", None]
        resultado = sugerir_padrao("LEITE INTEGRAL 1L", nomes_conhecidos)
        assert resultado == "Leite Integral"

    def test_match_exato(self):
        nomes_conhecidos = ["Arroz Branco"]
        resultado = sugerir_padrao("Arroz Branco", nomes_conhecidos)
        assert resultado == "Arroz Branco"

    def test_match_ordem_palavras_invertida(self):
        """token_sort_ratio deve ser robusto à ordem das palavras."""
        nomes_conhecidos = ["Integral Leite"]
        resultado = sugerir_padrao("LEITE INTEGRAL", nomes_conhecidos)
        assert resultado == "Integral Leite"
