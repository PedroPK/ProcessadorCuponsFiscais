"""
Testes para src/utils.py — filtrar_produtos()
"""
import pandas as pd
import pytest
from utils import filtrar_produtos


# ── Fixture ────────────────────────────────────────────────────────────────────

@pytest.fixture
def df_produtos():
    return pd.DataFrame({
        'produto': [
            'LEITE NINHO 750G INT',
            'LEITE NINHO 400G',
            'LEITE INTEGRAL CX 1L',
            'CAFE PILAO 500G',
            'ACHOCOLATADO NESCAU 400G',
        ]
    })


# ── Busca vazia — retorna tudo ─────────────────────────────────────────────────

class TestBuscaVazia:
    def test_string_vazia_retorna_df_completo(self, df_produtos):
        resultado = filtrar_produtos(df_produtos, "")
        assert len(resultado) == len(df_produtos)

    def test_apenas_espacos_retorna_df_completo(self, df_produtos):
        resultado = filtrar_produtos(df_produtos, "   ")
        assert len(resultado) == len(df_produtos)

    def test_none_equivalente_a_vazio(self, df_produtos):
        resultado = filtrar_produtos(df_produtos, None)
        assert len(resultado) == len(df_produtos)


# ── Busca por token único ──────────────────────────────────────────────────────

class TestTokenUnico:
    def test_token_encontra_registros(self, df_produtos):
        resultado = filtrar_produtos(df_produtos, "ninho")
        assert len(resultado) == 2

    def test_busca_case_insensitive(self, df_produtos):
        upper = filtrar_produtos(df_produtos, "NINHO")
        lower = filtrar_produtos(df_produtos, "ninho")
        assert list(upper['produto']) == list(lower['produto'])

    def test_token_sem_match_retorna_vazio(self, df_produtos):
        resultado = filtrar_produtos(df_produtos, "cerveja")
        assert resultado.empty

    def test_token_numerico(self, df_produtos):
        resultado = filtrar_produtos(df_produtos, "750")
        assert len(resultado) == 1
        assert resultado.iloc[0]['produto'] == 'LEITE NINHO 750G INT'


# ── Busca por múltiplos tokens (AND) — o cenário do bug ───────────────────────

class TestMultiplosTokens:
    def test_dois_tokens_filtra_corretamente(self, df_produtos):
        # "leite ninho" deve retornar os 2 produtos LEITE NINHO
        resultado = filtrar_produtos(df_produtos, "leite ninho")
        assert len(resultado) == 2

    def test_tres_tokens_com_caracter_intermediario(self, df_produtos):
        # CASO DO BUG: "leite ninho 750 int" não é substring contígua de
        # "LEITE NINHO 750G INT" (existe o "G" entre "750" e "INT"),
        # mas a busca por tokens deve encontrar o produto.
        resultado = filtrar_produtos(df_produtos, "leite ninho 750 int")
        assert len(resultado) == 1
        assert resultado.iloc[0]['produto'] == 'LEITE NINHO 750G INT'

    def test_tokens_em_ordem_diferente(self, df_produtos):
        # A ordem dos tokens não deve importar
        resultado = filtrar_produtos(df_produtos, "int ninho 750")
        assert len(resultado) == 1
        assert resultado.iloc[0]['produto'] == 'LEITE NINHO 750G INT'

    def test_tokens_que_nao_coexistem_retorna_vazio(self, df_produtos):
        # "ninho" existe, "pilao" existe, mas nunca no mesmo produto
        resultado = filtrar_produtos(df_produtos, "ninho pilao")
        assert resultado.empty

    def test_refinamento_progressivo(self, df_produtos):
        # Digitar mais palavras deve restringir (nunca ampliar) o resultado
        resultado_1 = filtrar_produtos(df_produtos, "leite")
        resultado_2 = filtrar_produtos(df_produtos, "leite ninho")
        resultado_3 = filtrar_produtos(df_produtos, "leite ninho 750")
        assert len(resultado_1) >= len(resultado_2) >= len(resultado_3)
