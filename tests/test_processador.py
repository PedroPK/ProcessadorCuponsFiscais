"""
Testes para src/processadorCuponsFiscais.py
"""
import io
import json
import zipfile
from types import SimpleNamespace
import pandas as pd
import pytest
from conftest import XML_VALIDO, NFE_CHAVE
import processadorCuponsFiscais
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


# ── Recibo de compra da Drogasil em PDF ────────────────────────────────────────

class TestReciboDrogasilPdf:
    CHAVE = "26241161585865120130650070003166601390246747"
    TEXTO = """\
Gmail - Seu recibo da Drogasil
Este é o seu cupom da compra que
você realizou do dia 06/11/2024 no
valor de R$ 20.21 .
Resumo do seu pedido
PRODUTO QTD VALOR TOTAL
IBUPROFENO 600 FRM 20
1 R$ 12.57 R$ 12.57
(De) R$ 22.85 (Por) R$ 12.57
NEEDS SAL AMARGO 30G
1 R$ 7.64 R$ 7.64
(De) R$ 8.99 (Por) R$ 7.64
Subtotal R$ 20.21
NFC-e No. Serie Emissão Via do consumidor Chave de Acesso
262411615858651201306500700031
66601390246747
Raia Drogasil S/A
Consumidor Eletrônica PADRE CARAPUCEIRO
CEP: 51020-900
CNPJ: 615.858.651/2013-0
"""

    def _criar_pdf_falso(self):
        palavras = [
            {"text": "Chave", "x0": 369.5, "top": 417.2},
            {"text": "6605860105", "x0": 39.6, "top": 444.4},
            {"text": "7", "x0": 130.0, "top": 444.4},
            {"text": self.CHAVE[:30], "x0": 369.5, "top": 438.4},
            {"text": self.CHAVE[30:], "x0": 369.5, "top": 450.4},
        ]
        pagina = SimpleNamespace(
            extract_text=lambda: self.TEXTO,
            extract_words=lambda: palavras,
        )

        class PdfFalso:
            pages = [pagina]

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        return PdfFalso()

    def test_extrai_itens_e_chave_da_nota_em_colunas(self, tmp_path, monkeypatch):
        pdf = self._criar_pdf_falso()
        monkeypatch.setattr(processadorCuponsFiscais.pdfplumber, "open", lambda *_args, **_kwargs: pdf)
        arquivo = tmp_path / "recibo_drogasil.pdf"

        p = ProcessadorDeCupons()
        p.processar_arquivo_pdf(arquivo)

        assert p._chaves_processadas == {self.CHAVE}
        assert len(p.dados_consolidados) == 2
        ibuprofeno, sal_amargo = p.dados_consolidados
        assert ibuprofeno["data"] == "06/11/2024"
        assert ibuprofeno["loja"] == "Drogasil"
        assert ibuprofeno["cnpj"] == "61585865120130"
        assert ibuprofeno["endereco"] == "PADRE CARAPUCEIRO, CEP 51020-900"
        assert ibuprofeno["produto"] == "IBUPROFENO 600 FRM 20"
        assert ibuprofeno["qtd"] == pytest.approx(1)
        assert ibuprofeno["unidade"] == "UN"
        assert ibuprofeno["preco_unit"] == pytest.approx(12.57)
        assert ibuprofeno["preco_total"] == pytest.approx(12.57)
        assert ibuprofeno["chave_nfe"] == self.CHAVE
        assert sal_amargo["produto"] == "NEEDS SAL AMARGO 30G"
        assert sal_amargo["preco_total"] == pytest.approx(7.64)

        p.processar_arquivo_pdf(arquivo)
        assert len(p.dados_consolidados) == 2

    def test_zip_deduplica_recibo_quando_xml_tem_a_mesma_chave(self, tmp_path, monkeypatch):
        pdf = self._criar_pdf_falso()
        monkeypatch.setattr(processadorCuponsFiscais.pdfplumber, "open", lambda *_args, **_kwargs: pdf)
        zip_path = tmp_path / "notas.zip"
        with zipfile.ZipFile(zip_path, "w") as arquivo_zip:
            arquivo_zip.writestr("nota.xml", XML_VALIDO.replace(NFE_CHAVE, self.CHAVE))
            arquivo_zip.writestr("recibo.pdf", b"pdf de teste")

        p = ProcessadorDeCupons()
        p.processar_zip(zip_path)

        assert len(p.dados_consolidados) == 2
        assert {item["arquivo_origem"] for item in p.dados_consolidados} == {"notas.zip::nota.xml"}


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
        assert leite["endereco"] == "Rua das Flores, 123, Centro, Recife - PE, CEP 50000000"
        assert leite["ean"] == "7891234560013"
        assert leite["preco_unit"] == pytest.approx(4.89)

    def test_arquivo_inexistente_nao_lanca_excecao(self, tmp_path):
        p = ProcessadorDeCupons()
        p.metricas.caminho = tmp_path / "processamento.jsonl"
        # Não deve propagar exceção — apenas logar o erro
        p.processar_arquivo_xml(tmp_path / "nao_existe.xml")
        assert p.dados_consolidados == []
        resumo = p.metricas.finalizar("sucesso")
        assert resumo["status"] == "parcial"
        assert resumo["erros_por_etapa"] == {"xml": 1}

    def test_registra_tempo_e_itens_extraidos(self, tmp_path):
        xml_file = tmp_path / "nota.xml"
        xml_file.write_text(XML_VALIDO, encoding="utf-8")

        p = ProcessadorDeCupons()
        p.metricas.caminho = tmp_path / "processamento.jsonl"
        p.processar_arquivo_xml(xml_file)

        resumo = p.metricas.finalizar("sucesso")

        assert resumo["etapas"]["xml"]["chamadas"] == 1
        assert resumo["itens_extraidos"] == 2
        assert resumo["status"] == "sucesso"

    def test_xml_malformado_registra_erro_parcial(self, tmp_path):
        xml_file = tmp_path / "nota.xml"
        xml_file.write_text("XML inválido", encoding="utf-8")

        p = ProcessadorDeCupons()
        p.metricas.caminho = tmp_path / "processamento.jsonl"
        p.processar_arquivo_xml(xml_file)

        resumo = p.metricas.finalizar("sucesso")

        assert resumo["status"] == "parcial"
        assert resumo["erros_por_etapa"] == {"xml": 1}


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


class TestAplicarNormalizacao:
    def test_le_dicionario_do_diretorio_data(self, tmp_path, monkeypatch):
        raiz = tmp_path
        (raiz / "src").mkdir()
        pasta_dados = raiz / "resources" / "data"
        pasta_dados.mkdir(parents=True)
        (pasta_dados / "dicionario_produtos.json").write_text(json.dumps({
            "Leite Ninho Integral": {
                "categoria": "Laticínios",
                "nomes_originais": ["LEITE NINHO", "L PO NINHO"],
            },
        }, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(
            processadorCuponsFiscais,
            "__file__",
            str(raiz / "src" / "processadorCuponsFiscais.py"),
        )

        resultado = ProcessadorDeCupons()._aplicar_normalizacao(
            pd.DataFrame([{"produto": "LEITE NINHO"}])
        )

        assert resultado.loc[0, "produto"] == "Leite Ninho Integral"
        assert resultado.loc[0, "categoria"] == "Laticínios"

    def test_ignora_diferenca_de_caixa_no_nome_bruto(self, tmp_path, monkeypatch):
        raiz = tmp_path
        (raiz / "src").mkdir()
        pasta_dados = raiz / "resources" / "data"
        pasta_dados.mkdir(parents=True)
        (pasta_dados / "dicionario_produtos.json").write_text(json.dumps({
            "Banana Maca Kg": {"categoria": "Hortifruti", "nomes_originais": ["BANANA MACA kg"]},
        }, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(
            processadorCuponsFiscais,
            "__file__",
            str(raiz / "src" / "processadorCuponsFiscais.py"),
        )

        resultado = ProcessadorDeCupons()._aplicar_normalizacao(
            pd.DataFrame([{"produto": "BANANA MACA KG"}, {"produto": "OUTRO"}])
        )

        assert resultado.loc[0, "produto"] == "Banana Maca Kg"
        assert resultado.loc[0, "categoria"] == "Hortifruti"
        assert resultado.loc[1, "produto"] == "OUTRO"
        assert resultado.loc[1, "categoria"] == "Outros"

class TestExportarCsv:
    def test_exporta_hora_xml_e_mantem_vazia_para_outros_itens(self, tmp_path, monkeypatch):
        (tmp_path / "src").mkdir()
        monkeypatch.setattr(processadorCuponsFiscais, "__file__", str(tmp_path / "src" / "processadorCuponsFiscais.py"))
        p = ProcessadorDeCupons()
        p.dados_consolidados = processadorCuponsFiscais.extrair_itens_do_xml(XML_VALIDO, "nota.xml")
        p.dados_consolidados.append({
            "data": "01/03/2026", "produto": "ITEM PDF", "qtd": 1,
            "unidade": "UN", "preco_unit": 1.0, "preco_total": 1.0,
            "arquivo_origem": "nota.pdf",
        })
        p.exportar_csv("teste.csv")
        df = pd.read_csv(tmp_path / "resources" / "outputData" / "teste.csv", sep=";", dtype={"hora": str})
        assert df["hora"].tolist()[:2] == ["13:01:36", "13:01:36"]
        assert pd.isna(df["hora"].iloc[2])

    def test_exporta_produto_raw_mesmo_sem_dicionario(self, tmp_path, monkeypatch):
        raiz = tmp_path
        (raiz / "src").mkdir()
        monkeypatch.setattr(processadorCuponsFiscais, "__file__", str(raiz / "src" / "processadorCuponsFiscais.py"))

        p = ProcessadorDeCupons()
        p.dados_consolidados = [{
            "data": "01/03/2026",
            "produto": "LEITE INTEGRAL UHT 1L",
            "qtd": 1.0,
            "unidade": "UN",
            "preco_unit": 4.89,
            "preco_total": 4.89,
            "codigo": "001",
            "arquivo_origem": "citizen.xlsx",
        }]

        p.exportar_csv("teste.csv")

        df = pd.read_csv(raiz / "resources" / "outputData" / "teste.csv", sep=";", encoding="utf-8-sig")
        assert "produto_raw" in df.columns
        assert df.loc[0, "produto_raw"] == "LEITE INTEGRAL UHT 1L"
