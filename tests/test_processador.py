"""
Testes para src/processadorCuponsFiscais.py
"""
import io
import zipfile
import pytest
from conftest import XML_VALIDO, NFE_CHAVE
from processadorCuponsFiscais import ProcessadorDeCupons


# ── _converter_valor ───────────────────────────────────────────────────────────

class TestConverterValor:
    def setup_method(self):
        self.p = ProcessadorDeCupons()

    def test_formato_brasileiro_com_milhar(self):
        assert self.p._converter_valor("1.234,56") == pytest.approx(1234.56)

    def test_formato_brasileiro_sem_milhar(self):
        assert self.p._converter_valor("9,99") == pytest.approx(9.99)

    def test_ponto_tratado_como_separador_de_milhar(self):
        # No padrão brasileiro, ponto é separador de milhar — "4.89" → 489.0
        assert self.p._converter_valor("4.89") == pytest.approx(489.0)

    def test_string_vazia_retorna_zero(self):
        assert self.p._converter_valor("") == pytest.approx(0.0)

    def test_none_retorna_zero(self):
        assert self.p._converter_valor(None) == pytest.approx(0.0)

    def test_string_invalida_retorna_zero(self):
        assert self.p._converter_valor("abc") == pytest.approx(0.0)


# ── _extrair_chave_pdf ─────────────────────────────────────────────────────────

class TestExtrairChavePdf:
    def setup_method(self):
        self.p = ProcessadorDeCupons()

    def test_chave_em_texto_continuo(self):
        texto = f"Chave de acesso: {NFE_CHAVE} data: 01/01/2026"
        assert self.p._extrair_chave_pdf(texto) == NFE_CHAVE

    def test_chave_em_blocos_com_espacos(self):
        # Formato típico dos DANFEs: grupos de 4 dígitos separados por espaço
        chave_blocos = " ".join(NFE_CHAVE[i:i+4] for i in range(0, 44, 4))
        assert self.p._extrair_chave_pdf(chave_blocos) == NFE_CHAVE

    def test_sem_chave_retorna_none(self):
        assert self.p._extrair_chave_pdf("texto sem chave") is None

    def test_numero_menor_que_44_nao_e_chave(self):
        assert self.p._extrair_chave_pdf("123456789012345678901234567890") is None


# ── Deduplicação por chave ─────────────────────────────────────────────────────

class TestDeduplicacao:
    def test_mesmo_xml_processado_duas_vezes(self, tmp_path):
        """Processar o mesmo arquivo XML duas vezes não deve duplicar os itens."""
        xml_file = tmp_path / "nota.xml"
        xml_file.write_text(XML_VALIDO, encoding="utf-8")

        p = ProcessadorDeCupons()
        p.processar_arquivo_xml(xml_file)
        p.processar_arquivo_xml(xml_file)

        assert len(p.dados_consolidados) == 2  # 2 itens, não 4

    def test_chave_registrada_apos_primeiro_processamento(self, tmp_path):
        xml_file = tmp_path / "nota.xml"
        xml_file.write_text(XML_VALIDO, encoding="utf-8")

        p = ProcessadorDeCupons()
        p.processar_arquivo_xml(xml_file)

        assert NFE_CHAVE in p._chaves_processadas


# ── processar_arquivo_xml (I/O real com tmp_path) ─────────────────────────────

class TestProcessarArquivoXml:
    def test_campos_extraidos(self, tmp_path):
        xml_file = tmp_path / "nota.xml"
        xml_file.write_text(XML_VALIDO, encoding="utf-8")

        p = ProcessadorDeCupons()
        p.processar_arquivo_xml(xml_file)

        assert len(p.dados_consolidados) == 2
        leite = next(i for i in p.dados_consolidados if i["produto"] == "LEITE INTEGRAL 1L")
        assert leite["loja"] == "SUPER TESTE"
        assert leite["cnpj"] == "06057223049189"
        assert leite["ean"] == "7891234560013"
        assert leite["preco_unit"] == pytest.approx(4.89)

    def test_arquivo_inexistente_nao_lanca_excecao(self, tmp_path):
        p = ProcessadorDeCupons()
        # Não deve propagar exceção — apenas logar o erro
        p.processar_arquivo_xml(tmp_path / "nao_existe.xml")
        assert p.dados_consolidados == []


# ── processar_zip — prioridade XML sobre PDF ───────────────────────────────────

class TestProcessarZip:
    def _criar_zip_com_xml(self, tmp_path, nome_xml="nota.xml"):
        """Cria um ZIP real em disco contendo apenas um XML."""
        zip_path = tmp_path / "notas.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(nome_xml, XML_VALIDO)
        zip_path.write_bytes(buf.getvalue())
        return zip_path

    def _criar_zip_com_xml_e_pdf_dummy(self, tmp_path):
        """Cria um ZIP com um XML válido e um PDF inerte (para testar prioridade)."""
        zip_path = tmp_path / "notas_mistas.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("nota.xml", XML_VALIDO)
            zf.writestr("danfe.pdf", b"%PDF-1.4 dummy")
        zip_path.write_bytes(buf.getvalue())
        return zip_path

    def test_zip_com_xml_extrai_itens(self, tmp_path):
        zip_path = self._criar_zip_com_xml(tmp_path)
        p = ProcessadorDeCupons()
        p.processar_zip(zip_path)
        assert len(p.dados_consolidados) == 2

    def test_zip_xml_e_pdf_usa_apenas_xml(self, tmp_path):
        """Quando o ZIP tem XML e PDF, apenas o XML deve ser processado."""
        zip_path = self._criar_zip_com_xml_e_pdf_dummy(tmp_path)
        p = ProcessadorDeCupons()
        p.processar_zip(zip_path)
        # Itens vêm apenas do XML (2 itens); o PDF dummy não tem dados válidos
        nomes = [i["produto"] for i in p.dados_consolidados]
        assert "LEITE INTEGRAL 1L" in nomes
        assert len(p.dados_consolidados) == 2

    def test_zip_xml_duplicado_nao_dobra_itens(self, tmp_path):
        """Dois XMLs idênticos no mesmo ZIP não devem duplicar os itens."""
        zip_path = tmp_path / "dup.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("nota_a.xml", XML_VALIDO)
            zf.writestr("nota_b.xml", XML_VALIDO)  # mesma chave
        zip_path.write_bytes(buf.getvalue())

        p = ProcessadorDeCupons()
        p.processar_zip(zip_path)
        assert len(p.dados_consolidados) == 2  # ainda 2 itens, não 4
