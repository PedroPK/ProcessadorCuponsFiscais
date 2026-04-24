"""
Testes para src/extratorXml.py
"""
import pytest
from conftest import XML_VALIDO, XML_SEM_CHAVE, XML_MALFORMADO, NFE_CHAVE
from extratorXml import (
    _float,
    _parse_data,
    extrair_chave_do_xml,
    extrair_itens_do_xml,
)


# ── _float ─────────────────────────────────────────────────────────────────────

class TestFloat:
    def test_valor_valido(self):
        assert _float("4.89") == pytest.approx(4.89)

    def test_valor_zero(self):
        assert _float("0.00") == pytest.approx(0.0)

    def test_none_retorna_zero(self):
        assert _float(None) == pytest.approx(0.0)

    def test_string_vazia_retorna_zero(self):
        assert _float("") == pytest.approx(0.0)

    def test_string_invalida_retorna_zero(self):
        assert _float("abc") == pytest.approx(0.0)


# ── _parse_data ────────────────────────────────────────────────────────────────

class TestParseData:
    def test_iso8601_com_timezone(self):
        assert _parse_data("2026-03-01T13:01:36-03:00") == "01/03/2026"

    def test_iso8601_sem_timezone(self):
        assert _parse_data("2026-12-25T00:00:00") == "25/12/2026"

    def test_none_retorna_desconhecida(self):
        assert _parse_data(None) == "Data Desconhecida"

    def test_string_vazia_retorna_desconhecida(self):
        assert _parse_data("") == "Data Desconhecida"

    def test_fallback_para_data_bruta(self):
        # Formato inesperado: retorna os 10 primeiros caracteres como fallback
        resultado = _parse_data("2026-07-04T99:99:99")
        assert resultado == "2026-07-04"


# ── extrair_chave_do_xml ───────────────────────────────────────────────────────

class TestExtrairChaveDoXml:
    def test_xml_valido_retorna_chave(self):
        chave = extrair_chave_do_xml(XML_VALIDO)
        assert chave == NFE_CHAVE
        assert len(chave) == 44

    def test_xml_valido_em_bytes(self):
        chave = extrair_chave_do_xml(XML_VALIDO.encode("utf-8"))
        assert chave == NFE_CHAVE

    def test_xml_sem_chave_retorna_none(self):
        chave = extrair_chave_do_xml(XML_SEM_CHAVE)
        assert chave is None

    def test_xml_malformado_retorna_none(self):
        chave = extrair_chave_do_xml(XML_MALFORMADO)
        assert chave is None


# ── extrair_itens_do_xml ───────────────────────────────────────────────────────

class TestExtrairItensDoXml:
    def setup_method(self):
        self.itens = extrair_itens_do_xml(XML_VALIDO, "nota_teste.xml")

    def test_numero_de_itens(self):
        # Item 3 tem valor zero e deve ser filtrado
        assert len(self.itens) == 2

    def test_campos_presentes(self):
        campos_esperados = {
            "data", "produto", "qtd", "unidade", "preco_unit",
            "preco_total", "codigo", "ean", "ncm", "loja",
            "cnpj", "chave_nfe", "arquivo_origem",
        }
        for item in self.itens:
            assert campos_esperados.issubset(item.keys())

    def test_nome_fantasia_preferido(self):
        assert self.itens[0]["loja"] == "SUPER TESTE"

    def test_cnpj(self):
        assert self.itens[0]["cnpj"] == "06057223049189"

    def test_data_formatada(self):
        assert self.itens[0]["data"] == "01/03/2026"

    def test_chave_nfe(self):
        assert self.itens[0]["chave_nfe"] == NFE_CHAVE

    def test_preco_unitario(self):
        leite = self.itens[0]
        assert leite["preco_unit"] == pytest.approx(4.89)

    def test_preco_total(self):
        leite = self.itens[0]
        assert leite["preco_total"] == pytest.approx(9.78)

    def test_ean_valido(self):
        leite = self.itens[0]
        assert leite["ean"] == "7891234560013"

    def test_ean_sem_gtin_vira_string_vazia(self):
        pao = self.itens[1]
        assert pao["ean"] == ""

    def test_ncm(self):
        leite = self.itens[0]
        assert leite["ncm"] == "04011000"

    def test_arquivo_origem(self):
        assert self.itens[0]["arquivo_origem"] == "nota_teste.xml"

    def test_item_valor_zero_filtrado(self):
        nomes = [i["produto"] for i in self.itens]
        assert "SACOLA CORTESIA" not in nomes

    def test_xml_malformado_retorna_lista_vazia(self):
        itens = extrair_itens_do_xml(XML_MALFORMADO, "ruim.xml")
        assert itens == []

    def test_xml_bytes(self):
        itens = extrair_itens_do_xml(XML_VALIDO.encode("utf-8"), "bytes.xml")
        assert len(itens) == 2
