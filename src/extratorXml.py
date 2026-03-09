"""
Extrator de dados de Nota Fiscal Eletrônica (NF-e / NFC-e) em formato XML.

O XML segue o schema oficial do Portal da Fazenda (portalfiscal.inf.br/nfe)
e contém dados muito mais ricos e confiáveis do que os PDFs DANFE:
  - Código EAN (barcode internacional do produto)
  - Código NCM (classificação fiscal)
  - Razão social e CNPJ do emissor
  - Data/hora exata da emissão
  - Valores precisos sem necessidade de regex
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# Namespace padrão dos documentos NF-e brasileiros
_NS = 'http://www.portalfiscal.inf.br/nfe'


def _t(tag: str) -> str:
    """Retorna a tag com o namespace NF-e."""
    return f'{{{_NS}}}{tag}'


def _get(element, tag: str) -> str | None:
    """Busca um filho direto e retorna seu texto, ou None se não existir."""
    child = element.find(_t(tag))
    return child.text if child is not None else None


def _float(valor_str: str | None) -> float:
    """Converte string decimal (ponto) para float com segurança."""
    if not valor_str:
        return 0.0
    try:
        return float(valor_str)
    except ValueError:
        return 0.0


def _parse_data(dh_emi: str | None) -> str:
    """
    Converte o campo dhEmi do NF-e (ISO 8601) para dd/mm/yyyy.
    Ex.: '2026-03-01T13:01:36-03:00' → '01/03/2026'
    """
    if not dh_emi:
        return 'Data Desconhecida'
    try:
        # Remove o offset de fuso e parseia
        dt = datetime.fromisoformat(dh_emi)
        return dt.strftime('%d/%m/%Y')
    except ValueError:
        return dh_emi[:10]  # Fallback: apenas a parte da data


def extrair_chave_do_xml(conteudo_xml: bytes | str) -> str | None:
    """
    Extrai apenas a chave de acesso NF-e (44 dígitos) do XML.
    Retorna None se não encontrar.
    """
    if isinstance(conteudo_xml, bytes):
        conteudo_xml = conteudo_xml.decode('utf-8', errors='replace')
    try:
        root = ET.fromstring(conteudo_xml)
    except ET.ParseError:
        return None
    inf = root.find('.//' + _t('infNFe'))
    if inf is None:
        return None
    id_attr = inf.get('Id', '')  # ex.: 'NFe26260306057223049189650130001286971130305212'
    return id_attr.lstrip('NFe') if id_attr else None


def extrair_itens_do_xml(conteudo_xml: bytes | str, nome_origem: str) -> list[dict]:
    """
    Extrai todos os itens de uma NF-e / NFC-e a partir do conteúdo XML.

    Parâmetros
    ----------
    conteudo_xml : bytes | str
        Conteúdo bruto do arquivo XML (bytes ou string UTF-8).
    nome_origem : str
        Nome do arquivo de origem (para rastreabilidade no CSV).

    Retorna
    -------
    list[dict]
        Lista de dicts, um por item da nota, com as chaves:
          data, produto, qtd, unidade, preco_unit, preco_total,
          codigo, ean, ncm, loja, cnpj, chave_nfe, arquivo_origem
    """
    if isinstance(conteudo_xml, bytes):
        conteudo_xml = conteudo_xml.decode('utf-8', errors='replace')

    try:
        root = ET.fromstring(conteudo_xml)
    except ET.ParseError as e:
        print(f'[ERRO XML] {nome_origem}: XML inválido — {e}')
        return []

    # A NFe pode estar em diferentes níveis dependendo se é "nfeProc" ou "NFe" direta
    nfe = root.find('.//' + _t('infNFe'))
    if nfe is None:
        print(f'[AVISO XML] {nome_origem}: tag <infNFe> não encontrada.')
        return []

    # Chave de acesso: atributo Id sem o prefixo 'NFe' (44 dígitos)
    id_attr = nfe.get('Id', '')
    chave_nfe = id_attr[len('NFe'):] if id_attr.startswith('NFe') else id_attr

    # ── Cabeçalho da nota ────────────────────────────────────────────────────
    ide  = nfe.find(_t('ide'))
    emit = nfe.find(_t('emit'))

    data_compra = _parse_data(_get(ide, 'dhEmi') if ide is not None else None)

    cnpj = _get(emit, 'CNPJ') if emit is not None else None
    # Prefere o nome fantasia; cai para razão social se não existir
    loja = (_get(emit, 'xFant') or _get(emit, 'xNome')) if emit is not None else None

    # ── Itens ────────────────────────────────────────────────────────────────
    itens = []
    for det in nfe.findall(_t('det')):
        prod = det.find(_t('prod'))
        if prod is None:
            continue

        nome_produto = _get(prod, 'xProd') or 'Desconhecido'
        codigo       = _get(prod, 'cProd') or ''
        ean          = _get(prod, 'cEAN') or ''
        ncm          = _get(prod, 'NCM') or ''
        unidade      = _get(prod, 'uCom') or ''
        qtd          = _float(_get(prod, 'qCom'))
        preco_unit   = _float(_get(prod, 'vUnCom'))

        # vItem reflete o valor real pago (já com eventuais descontos por item)
        # vProd é o valor antes de desconto ao nível do item
        v_item = _get(det, 'vItem')
        v_prod = _get(prod, 'vProd')
        preco_total  = _float(v_item if v_item is not None else v_prod)

        # Ignora itens zerados (ex.: sacolas de cortesia sem valor fiscal)
        if preco_total <= 0 and preco_unit <= 0:
            continue

        itens.append({
            'data':           data_compra,
            'produto':        nome_produto,
            'qtd':            qtd,
            'unidade':        unidade,
            'preco_unit':     preco_unit,
            'preco_total':    preco_total,
            'codigo':         codigo,
            'ean':            ean if ean != 'SEM GTIN' else '',
            'ncm':            ncm,
            'loja':           loja or '',
            'cnpj':           cnpj or '',
            'chave_nfe':      chave_nfe,
            'arquivo_origem': nome_origem,
        })

    return itens
