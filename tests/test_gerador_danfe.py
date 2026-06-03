"""Testes para helpers de nomenclatura de arquivos DANFE."""
from pathlib import Path

from gerador_danfe import _nome_arquivo_unico, _nome_pdf_danfe, _sanitizar_nome_arquivo


class TestNomenclaturaDanfe:
    def test_nome_pdf_usa_data_e_nome_fantasia(self):
        dados = {
            'dh_emi': '2026-06-03T10:20:30-03:00',
            'emit_fant': 'MERCADO BOM PRECO',
            'emit_nome': 'MERCADO BOM PRECO LTDA',
        }

        resultado = _nome_pdf_danfe(dados)
        assert resultado == '2026.06.03 - DANFE - MERCADO BOM PRECO.pdf'

    def test_nome_pdf_faz_fallback_para_emit_nome(self):
        dados = {
            'dh_emi': '2026-06-03T10:20:30-03:00',
            'emit_fant': '',
            'emit_nome': 'SUPERMERCADO FAMILIA LTDA',
        }

        resultado = _nome_pdf_danfe(dados)
        assert resultado == '2026.06.03 - DANFE - SUPERMERCADO FAMILIA LTDA.pdf'

    def test_nome_pdf_data_invalida_usa_data_padrao(self):
        dados = {
            'dh_emi': 'data-invalida',
            'emit_fant': 'LOJA TESTE',
        }

        resultado = _nome_pdf_danfe(dados)
        assert resultado == '0000.00.00 - DANFE - LOJA TESTE.pdf'


class TestSanitizacaoNomeArquivo:
    def test_remove_caracteres_invalidos(self):
        nome = 'MERCADO: BOM/PRECO* ?"<CENTRO>|'
        resultado = _sanitizar_nome_arquivo(nome)
        assert resultado == 'MERCADO BOMPRECO CENTRO'

    def test_retorna_fallback_quando_nome_vazio(self):
        resultado = _sanitizar_nome_arquivo('   ')
        assert resultado == 'Estabelecimento nao identificado'


class TestNomeArquivoUnico:
    def test_retorna_mesmo_caminho_quando_nao_existe(self, tmp_path):
        caminho = tmp_path / 'saida.pdf'
        assert _nome_arquivo_unico(caminho) == caminho

    def test_adiciona_sufixo_incremental_quando_arquivo_existe(self, tmp_path):
        base = tmp_path / 'saida.pdf'
        conflito_2 = tmp_path / 'saida (2).pdf'

        base.write_bytes(b'%PDF')
        conflito_2.write_bytes(b'%PDF')

        resultado = _nome_arquivo_unico(base)
        assert resultado == tmp_path / 'saida (3).pdf'
