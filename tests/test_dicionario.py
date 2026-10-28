"""
Testes para src/dicionario.py
"""
import json
import pandas as pd
import pytest
from pathlib import Path
import dicionario
from dicionario import (
    atualizar_dicionario,
    carregar_dados_existentes,
    dicionario_json_para_dataframe,
    identificar_duplicatas_por_ean,
    salvar_dicionario,
    sugerir_padrao,
)


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


class TestDicionarioJson:
    def test_salvar_agrupa_por_nome_padrao_e_ordena(self, tmp_path):
        df = pd.DataFrame([
            {"nome_original": "L PO NINHO", "nome_padrao": "Leite Ninho", "categoria": "Nova"},
            {"nome_original": "ARROZ T1", "nome_padrao": "Arroz", "categoria": "Grãos"},
            {"nome_original": "LEITE NINHO", "nome_padrao": "Leite Ninho", "categoria": "Laticínios"},
            {"nome_original": "LEITE NINHO", "nome_padrao": "Leite Ninho", "categoria": "Laticínios"},
        ])
        caminho = tmp_path / "dic.json"

        salvar_dicionario(df, caminho)

        assert json.loads(caminho.read_text(encoding="utf-8")) == {
            "Arroz": {"categoria": "Grãos", "nomes_originais": ["ARROZ T1"]},
            "Leite Ninho": {
                "categoria": "Laticínios",
                "nomes_originais": ["L PO NINHO", "LEITE NINHO"],
            },
        }
        assert list(json.loads(caminho.read_text(encoding="utf-8"))) == ["Arroz", "Leite Ninho"]

    def test_salvar_preserva_acentos(self, tmp_path):
        df = pd.DataFrame([
            {"nome_original": "CAFE", "nome_padrao": "Café", "categoria": "Bebidas"},
        ])
        caminho = tmp_path / "dic.json"
        salvar_dicionario(df, caminho)
        assert "Café" in caminho.read_text(encoding="utf-8")

    def test_ida_e_volta_preserva_mapeamentos(self, tmp_path):
        df = pd.DataFrame([
            {"nome_original": "A", "nome_padrao": "Produto 1", "categoria": "X"},
            {"nome_original": "B", "nome_padrao": "Produto 1", "categoria": "X"},
            {"nome_original": "C", "nome_padrao": "Produto 2", "categoria": "Y"},
        ])
        caminho = tmp_path / "dic.json"
        salvar_dicionario(df, caminho)

        carregado = carregar_dados_existentes(caminho).set_index("nome_original")
        assert carregado.loc["B", "nome_padrao"] == "Produto 1"
        assert carregado.loc["C", "categoria"] == "Y"

    def test_categoria_ausente_usa_nova(self):
        df = dicionario_json_para_dataframe({"Leite": {"nomes_originais": ["LEITE"]}})
        assert df.iloc[0]["categoria"] == "Nova"

    def test_nome_original_em_dois_grupos_gera_erro(self):
        dados = {
            "Leite A": {"categoria": "Nova", "nomes_originais": ["LEITE"]},
            "Leite B": {"categoria": "Nova", "nomes_originais": ["LEITE"]},
        }
        with pytest.raises(ValueError, match="LEITE"):
            dicionario_json_para_dataframe(dados)

    def test_estrutura_invalida_gera_erro(self):
        with pytest.raises(ValueError, match="nomes_originais"):
            dicionario_json_para_dataframe({"Leite": {"categoria": "Nova"}})
        with pytest.raises(ValueError):
            dicionario_json_para_dataframe(["não é objeto"])

    def test_json_malformado_informa_arquivo_e_linha(self, tmp_path):
        caminho = tmp_path / "dic.json"
        caminho.write_text('{\n  "Leite": {\n    "nomes_originais": ["A",]\n  }\n}', encoding="utf-8")
        with pytest.raises(ValueError, match=r"dic\.json.*linha 3"):
            carregar_dados_existentes(caminho)


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

    def test_diferenca_apenas_de_caixa_reaproveita_padrao(self):
        resultado = sugerir_padrao("BANANA MACA KG", ["Banana Maca Kg", "Banana Prata Kg"])
        assert resultado == "Banana Maca Kg"

    def test_match_ordem_palavras_invertida(self):
        """token_sort_ratio deve ser robusto à ordem das palavras."""
        nomes_conhecidos = ["Integral Leite"]
        resultado = sugerir_padrao("LEITE INTEGRAL", nomes_conhecidos)
        assert resultado == "Integral Leite"


class TestIdentificarDuplicatasPorEan:
    def test_retorna_descricoes_distintas_com_mesmo_ean(self):
        df = pd.DataFrame([
            {"produto_raw": "LEITE NINHO 750G", "ean": "7891000325896"},
            {"produto_raw": "LEITE PO NINHO", "ean": "7891000325896"},
            {"produto_raw": "ARROZ", "ean": "7890000000000"},
            {"produto_raw": "LEITE NINHO 750G", "ean": "7891000325896"},
        ])

        resultado = identificar_duplicatas_por_ean(df)

        assert resultado.to_dict("records") == [{
            "ean": "7891000325896",
            "nomes_originais": ["LEITE NINHO 750G", "LEITE PO NINHO"],
            "ocorrencias": 3,
        }]

    def test_ignora_eans_vazios_e_aceita_coluna_produto(self):
        df = pd.DataFrame([
            {"produto": "PRODUTO A", "ean": ""},
            {"produto": "PRODUTO B", "ean": None},
        ])

        resultado = identificar_duplicatas_por_ean(df)

        assert resultado.empty
        assert list(resultado.columns) == ["ean", "nomes_originais", "ocorrencias"]


class TestAtualizarDicionario:
    def test_usa_produto_raw_quando_coluna_existe(self, tmp_path, monkeypatch):
        raiz = tmp_path
        pasta_saida = raiz / "resources" / "outputData"
        pasta_saida.mkdir(parents=True)
        (raiz / "src").mkdir()

        pd.DataFrame([
            {"produto": "Leite Integral", "produto_raw": "LEITE INTEGRAL UHT 1L"},
        ]).to_csv(pasta_saida / "minha_inflacao.csv", index=False, sep=";", encoding="utf-8-sig")
        (raiz / "resources" / "data").mkdir(parents=True)

        monkeypatch.setattr(dicionario, "__file__", str(raiz / "src" / "dicionario.py"))

        atualizar_dicionario()

        df = carregar_dados_existentes(raiz / "resources" / "data" / "dicionario_produtos.json")
        assert list(df["nome_original"]) == ["LEITE INTEGRAL UHT 1L"]
        assert list(df["categoria"]) == ["Nova"]

    def test_faz_fallback_para_produto_por_compatibilidade(self, tmp_path, monkeypatch):
        raiz = tmp_path
        pasta_saida = raiz / "resources" / "outputData"
        pasta_saida.mkdir(parents=True)
        (raiz / "src").mkdir()

        pd.DataFrame([
            {"produto": "LEITE INTEGRAL UHT 1L"},
        ]).to_csv(pasta_saida / "minha_inflacao.csv", index=False, sep=";", encoding="utf-8-sig")
        (raiz / "resources" / "data").mkdir(parents=True)

        monkeypatch.setattr(dicionario, "__file__", str(raiz / "src" / "dicionario.py"))

        atualizar_dicionario()

        df = carregar_dados_existentes(raiz / "resources" / "data" / "dicionario_produtos.json")
        assert list(df["nome_original"]) == ["LEITE INTEGRAL UHT 1L"]

    def test_migra_dicionario_xlsx_legado_para_json(self, tmp_path, monkeypatch):
        raiz = tmp_path
        pasta_saida = raiz / "resources" / "outputData"
        pasta_saida.mkdir(parents=True)
        (raiz / "src").mkdir()

        pd.DataFrame([
            {"produto": "LEITE INTEGRAL UHT 1L"},
        ]).to_csv(pasta_saida / "minha_inflacao.csv", index=False, sep=";", encoding="utf-8-sig")
        legado = pasta_saida / "dicionario_produtos.xlsx"
        pd.DataFrame([
            {
                "nome_original": "LEITE INTEGRAL UHT 1L",
                "nome_padrao": "Leite Integral",
                "categoria": "Laticínios",
            },
        ]).to_excel(legado, index=False)
        monkeypatch.setattr(dicionario, "__file__", str(raiz / "src" / "dicionario.py"))

        atualizar_dicionario()

        novo = raiz / "resources" / "data" / "dicionario_produtos.json"
        assert novo.exists()
        assert legado.exists()
        assert json.loads(novo.read_text(encoding="utf-8")) == {
            "Leite Integral": {
                "categoria": "Laticínios",
                "nomes_originais": ["LEITE INTEGRAL UHT 1L"],
            }
        }

    def test_preserva_edicoes_manuais_do_json(self, tmp_path, monkeypatch):
        raiz = tmp_path
        pasta_saida = raiz / "resources" / "outputData"
        pasta_saida.mkdir(parents=True)
        (raiz / "resources" / "data").mkdir(parents=True)
        (raiz / "src").mkdir()

        pd.DataFrame([
            {"produto": "LEITE INTEGRAL UHT 1L"},
            {"produto": "ARROZ BRANCO 5KG"},
        ]).to_csv(pasta_saida / "minha_inflacao.csv", index=False, sep=";", encoding="utf-8-sig")
        caminho = raiz / "resources" / "data" / "dicionario_produtos.json"
        caminho.write_text(json.dumps({
            "Leite Integral": {"categoria": "Laticínios", "nomes_originais": ["LEITE INTEGRAL UHT 1L"]},
        }, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(dicionario, "__file__", str(raiz / "src" / "dicionario.py"))

        atualizar_dicionario()

        dados = json.loads(caminho.read_text(encoding="utf-8"))
        assert dados["Leite Integral"]["categoria"] == "Laticínios"
        assert "ARROZ BRANCO 5KG" in sum((v["nomes_originais"] for v in dados.values()), [])
