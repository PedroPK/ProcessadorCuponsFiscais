"""
Gerador de DANFE simplificado a partir de XML de NF-e / NFC-e.

Gera um PDF legível em formato A4 com o mesmo conteúdo do documento
fiscal, sem depender do portal da SEFAZ.

Uso:
    python3 src/gerador_danfe.py <arquivo.xml>
    python3 src/gerador_danfe.py <arquivo.zip>        # converte todos os XMLs do ZIP
    python3 src/gerador_danfe.py                      # processa todo resources/notas_fiscais/

Os PDFs são salvos em resources/outputData/danfe/
"""

import io
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
)
from reportlab.platypus.flowables import Image as RLImage


# ─── Configurações visuais ────────────────────────────────────────────────────
COR_CABECALHO   = colors.HexColor('#1a3a5c')   # Azul escuro
COR_LINHA_ALT   = colors.HexColor('#f0f4f8')   # Azul muito claro (linhas alternadas)
COR_LINHA_TOTAL = colors.HexColor('#d6e4f0')
COR_CINZA       = colors.HexColor('#666666')

NS = 'http://www.portalfiscal.inf.br/nfe'

TIPOS_PAGAMENTO = {
    '01': 'Dinheiro',        '02': 'Cheque',
    '03': 'Cartão de Crédito', '04': 'Cartão de Débito',
    '05': 'Crédito Loja',    '10': 'Vale Alimentação',
    '11': 'Vale Refeição',   '13': 'Vale Presente',
    '14': 'Vale Combustível','15': 'Boleto Bancário',
    '16': 'Depósito Bancário','17': 'PIX',
    '18': 'Transferência',   '99': 'Outros',
}


# ─── Helpers XML ──────────────────────────────────────────────────────────────
def _t(tag: str) -> str:
    return f'{{{NS}}}{tag}'

def _g(el, tag: str) -> str:
    if el is None:
        return ''
    n = el.find(_t(tag))
    return (n.text or '').strip() if n is not None else ''


def _fmt_cnpj(cnpj: str) -> str:
    c = re.sub(r'\D', '', cnpj)
    if len(c) == 14:
        return f'{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}'
    return cnpj

def _fmt_cep(cep: str) -> str:
    c = re.sub(r'\D', '', cep)
    return f'{c[:5]}-{c[5:]}' if len(c) == 8 else cep

def _fmt_chave(chave: str) -> str:
    """Formata a chave de acesso em grupos de 4 dígitos."""
    c = re.sub(r'\D', '', chave)
    return ' '.join(c[i:i+4] for i in range(0, len(c), 4))

def _fmt_data(dh: str) -> str:
    """ISO 8601 → 'dd/mm/yyyy HH:MM'."""
    try:
        return datetime.fromisoformat(dh).strftime('%d/%m/%Y %H:%M')
    except Exception:
        return dh[:16].replace('T', ' ')

def _fmt_valor(v: str, decimais: int = 2) -> str:
    try:
        return f'R$ {float(v):,.{decimais}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return v or ''

def _fmt_qtd(v: str) -> str:
    try:
        f = float(v)
        return f'{f:,.4f}'.rstrip('0').rstrip(',').replace(',', 'X').replace('.', ',').replace('X', '.') if '.' in f'{f}' else f'{f:,.0f}'
    except Exception:
        return v or ''


# ─── Extração do NF-e ─────────────────────────────────────────────────────────
def _extrair_dados(conteudo_xml: bytes) -> dict:
    root = ET.fromstring(conteudo_xml.decode('utf-8', errors='replace'))

    nfe  = root.find('.//' + _t('infNFe'))
    ide  = nfe.find(_t('ide'))   if nfe is not None else None
    emit = nfe.find(_t('emit'))  if nfe is not None else None
    end  = emit.find(_t('enderEmit')) if emit is not None else None
    dest = nfe.find(_t('dest'))  if nfe is not None else None
    total= nfe.find(_t('total')) if nfe is not None else None
    pag  = nfe.find(_t('pag'))   if nfe is not None else None
    inf_adic = nfe.find(_t('infAdic')) if nfe is not None else None
    icms = total.find(_t('ICMSTot')) if total is not None else None

    # Chave de acesso
    id_attr = nfe.get('Id', '') if nfe is not None else ''
    chave   = id_attr[len('NFe'):] if id_attr.startswith('NFe') else id_attr

    # Itens
    itens = []
    if nfe is not None:
        for det in nfe.findall(_t('det')):
            prod = det.find(_t('prod'))
            if prod is None:
                continue
            v_item = _g(det, 'vItem') or _g(prod, 'vProd')
            v_desc = _g(prod, 'vDesc')
            itens.append({
                'n':         det.get('nItem', ''),
                'codigo':    _g(prod, 'cProd'),
                'ean':       _g(prod, 'cEAN'),
                'nome':      _g(prod, 'xProd'),
                'ncm':       _g(prod, 'NCM'),
                'cfop':      _g(prod, 'CFOP'),
                'unidade':   _g(prod, 'uCom'),
                'qtd':       _g(prod, 'qCom'),
                'vunit':     _g(prod, 'vUnCom'),
                'vdesc':     v_desc,
                'vtotal':    v_item,
            })

    # Formas de pagamento
    pagamentos = []
    if pag is not None:
        for dp in pag.findall(_t('detPag')):
            tp  = _g(dp, 'tPag')
            vp  = _g(dp, 'vPag')
            pagamentos.append({'tipo': TIPOS_PAGAMENTO.get(tp, tp), 'valor': vp})
        troco = _g(pag, 'vTroco')
    else:
        troco = ''

    return {
        'chave':      chave,
        'n_nf':       _g(ide, 'nNF'),
        'serie':      _g(ide, 'serie'),
        'dh_emi':     _g(ide, 'dhEmi'),
        'nat_op':     _g(ide, 'natOp'),
        'emit_cnpj':  _g(emit, 'CNPJ'),
        'emit_nome':  _g(emit, 'xNome'),
        'emit_fant':  _g(emit, 'xFant'),
        'emit_ie':    _g(emit, 'IE'),
        'end_lgr':    _g(end, 'xLgr'),
        'end_nro':    _g(end, 'nro'),
        'end_bairro': _g(end, 'xBairro'),
        'end_mun':    _g(end, 'xMun'),
        'end_uf':     _g(end, 'UF'),
        'end_cep':    _g(end, 'CEP'),
        'dest_cpf':   _g(dest, 'CPF') if dest is not None else '',
        'dest_cnpj':  _g(dest, 'CNPJ') if dest is not None else '',
        'dest_nome':  _g(dest, 'xNome') if dest is not None else '',
        'v_prod':     _g(icms, 'vProd'),
        'v_desc':     _g(icms, 'vDesc'),
        'v_frete':    _g(icms, 'vFrete'),
        'v_icms':     _g(icms, 'vICMS'),
        'v_tot_trib': _g(icms, 'vTotTrib'),
        'v_nf':       _g(icms, 'vNF'),
        'itens':      itens,
        'pagamentos': pagamentos,
        'troco':      troco,
        'inf_compl':  _g(inf_adic, 'infCpl') if inf_adic is not None else '',
    }


# ─── Geração do QR Code ───────────────────────────────────────────────────────
def _qrcode_image(chave: str, size_mm: float = 30) -> RLImage:
    """Gera um QR Code com a URL de consulta da NF-e."""
    # URL padrão de consulta NFC-e (SEFAZ — genérica)
    url = f'https://www.nfce.fazenda.gov.br/consulta?chNFe={chave}'
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    size_pt = size_mm * mm
    return RLImage(buf, width=size_pt, height=size_pt)


# ─── Estilos de texto ─────────────────────────────────────────────────────────
def _estilos():
    base = getSampleStyleSheet()
    estilos = {
        'titulo_loja': ParagraphStyle(
            'titulo_loja', parent=base['Normal'],
            fontSize=14, fontName='Helvetica-Bold',
            textColor=COR_CABECALHO, spaceAfter=1*mm, leading=16,
        ),
        'subtitulo_loja': ParagraphStyle(
            'subtitulo_loja', parent=base['Normal'],
            fontSize=8, fontName='Helvetica',
            textColor=COR_CINZA, leading=10,
        ),
        'danfe_titulo': ParagraphStyle(
            'danfe_titulo', parent=base['Normal'],
            fontSize=10, fontName='Helvetica-Bold',
            textColor=COR_CABECALHO, alignment=1, leading=12,
        ),
        'danfe_subtit': ParagraphStyle(
            'danfe_subtit', parent=base['Normal'],
            fontSize=8, fontName='Helvetica',
            textColor=COR_CINZA, alignment=1, leading=10,
        ),
        'label': ParagraphStyle(
            'label', parent=base['Normal'],
            fontSize=6.5, fontName='Helvetica-Bold',
            textColor=COR_CINZA, leading=8,
        ),
        'valor': ParagraphStyle(
            'valor', parent=base['Normal'],
            fontSize=8.5, fontName='Helvetica',
            textColor=colors.black, leading=10,
        ),
        'chave': ParagraphStyle(
            'chave', parent=base['Normal'],
            fontSize=7, fontName='Courier',
            textColor=colors.black, leading=9, alignment=1,
        ),
        'secao': ParagraphStyle(
            'secao', parent=base['Normal'],
            fontSize=7.5, fontName='Helvetica-Bold',
            textColor=colors.white, leading=9,
        ),
        'th': ParagraphStyle(
            'th', parent=base['Normal'],
            fontSize=6.5, fontName='Helvetica-Bold',
            textColor=colors.white, leading=8,
        ),
        'td': ParagraphStyle(
            'td', parent=base['Normal'],
            fontSize=7.5, fontName='Helvetica',
            textColor=colors.black, leading=9,
        ),
        'td_r': ParagraphStyle(
            'td_r', parent=base['Normal'],
            fontSize=7.5, fontName='Helvetica',
            textColor=colors.black, leading=9, alignment=2,
        ),
    }
    return estilos


# ─── Blocos do documento ──────────────────────────────────────────────────────
def _bloco_cabecalho(d: dict, s: dict, larg: float) -> Table:
    """Linha superior: logo/nome da loja | DANFE | número da NF."""
    nome_fant = d['emit_fant'] or d['emit_nome']
    razao     = d['emit_nome'] if d['emit_fant'] else ''
    endereco  = (f"{d['end_lgr']}, {d['end_nro']} — {d['end_bairro']}"
                 f"\n{d['end_mun']}/{d['end_uf']}  CEP {_fmt_cep(d['end_cep'])}")
    cnpj_ie   = (f"CNPJ: {_fmt_cnpj(d['emit_cnpj'])}"
                 + (f"  |  IE: {d['emit_ie']}" if d['emit_ie'] else ''))

    col_loja = [
        Paragraph(nome_fant, s['titulo_loja']),
        *(([Paragraph(razao, s['subtitulo_loja'])]) if razao else []),
        Paragraph(endereco, s['subtitulo_loja']),
        Paragraph(cnpj_ie,  s['subtitulo_loja']),
    ]

    col_danfe = [
        Paragraph('DANFE NFC-e', s['danfe_titulo']),
        Spacer(1, 1*mm),
        Paragraph('Documento Auxiliar da<br/>Nota Fiscal Eletrônica<br/>ao Consumidor', s['danfe_subtit']),
    ]

    nf_str    = f"NF-e {d['n_nf']} — Série {d['serie']}"
    data_str  = _fmt_data(d['dh_emi'])
    natop_str = f"Nat. Operação: {d['nat_op']}"
    col_nf = [
        Paragraph(nf_str,    s['danfe_titulo']),
        Spacer(1, 1*mm),
        Paragraph(data_str,  s['danfe_subtit']),
        Paragraph(natop_str, s['danfe_subtit']),
    ]

    t = Table([[col_loja, col_danfe, col_nf]],
              colWidths=[larg * 0.45, larg * 0.25, larg * 0.30])
    t.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('BOX',          (0, 0), (-1, -1), 0.5, COR_CABECALHO),
        ('LINEAFTER',    (0, 0), (1, 0),   0.3, colors.lightgrey),
        ('BACKGROUND',   (0, 0), (-1, -1), colors.white),
        ('TOPPADDING',   (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t


def _bloco_secao(titulo: str, s: dict, larg: float) -> Table:
    """Faixa colorida de título de seção."""
    t = Table([[Paragraph(titulo, s['secao'])]], colWidths=[larg])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), COR_CABECALHO),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
    ]))
    return t


def _bloco_itens(itens: list, s: dict, larg: float) -> Table:
    """Tabela de itens da nota."""
    # Cabeçalho
    headers = ['#', 'Código', 'Descrição', 'EAN', 'NCM', 'Qtd', 'Un', 'Vl. Unit.', 'Vl. Total']
    header_row = [Paragraph(h, s['th']) for h in headers]

    # Proporções das colunas
    w = larg
    #         #      Cód    Descrição  EAN    NCM    Qtd    Un     Vl.Un  Vl.Tot
    col_w = [w*0.04, w*0.07, w*0.30, w*0.13, w*0.09,
             w*0.08, w*0.05, w*0.12, w*0.12]

    rows = [header_row]
    for i, it in enumerate(itens):
        bg = COR_LINHA_ALT if i % 2 == 0 else colors.white
        ean_display = it['ean'] if it['ean'] and it['ean'] != 'SEM GTIN' else '—'
        row = [
            Paragraph(it['n'],                s['td']),
            Paragraph(it['codigo'],           s['td']),
            Paragraph(it['nome'],             s['td']),
            Paragraph(ean_display,            s['td']),
            Paragraph(it['ncm'],              s['td']),
            Paragraph(_fmt_qtd(it['qtd']),    s['td_r']),
            Paragraph(it['unidade'],          s['td']),
            Paragraph(_fmt_valor(it['vunit']), s['td_r']),
            Paragraph(_fmt_valor(it['vtotal']), s['td_r']),
        ]
        rows.append((row, bg))

    # Monta a tabela separando dados e cores
    data   = [r[0] if isinstance(r, tuple) else r for r in rows]
    bgs    = [r[1] if isinstance(r, tuple) else COR_CABECALHO for r in rows]

    t = Table(data, colWidths=col_w, repeatRows=1)

    style = [
        # Cabeçalho
        ('BACKGROUND',    (0, 0), (-1, 0),  COR_CABECALHO),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0),  6.5),
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 2),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 2),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX',           (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ('INNERGRID',     (0, 0), (-1, -1), 0.2, colors.lightgrey),
        # Alinha valores à direita
        ('ALIGN',         (5, 1), (-1, -1), 'RIGHT'),
    ]
    # Aplica linhas alternadas (rows[0] é o cabeçalho, já tratado acima)
    for i, (_, bg) in enumerate(rows[1:], 1):
        style.append(('BACKGROUND', (0, i), (-1, i), bg))

    t.setStyle(TableStyle(style))
    return t


def _bloco_totais_pagto(d: dict, s: dict, larg: float) -> Table:
    """Dois blocos lado a lado: Totais | Formas de Pagamento."""

    def campo(label, valor):
        return [Paragraph(label, s['label']), Paragraph(valor, s['valor'])]

    # Coluna esquerda: totais financeiros
    col_tot = []
    if d['v_prod']:   col_tot += campo('Valor dos Produtos',  _fmt_valor(d['v_prod']))
    if d['v_frete'] and d['v_frete'] != '0.00':
                      col_tot += campo('Frete',               _fmt_valor(d['v_frete']))
    if d['v_desc'] and d['v_desc'] != '0.00':
                      col_tot += campo('Descontos',           _fmt_valor(d['v_desc']))
    col_tot += campo('Base de Cálculo ICMS', _fmt_valor(d.get('v_bc', '')))
    col_tot += campo('Valor ICMS',           _fmt_valor(d['v_icms']))
    if d['v_tot_trib'] and d['v_tot_trib'] != '0.00':
        col_tot += campo('Trib. Aprox. (Lei 12.741)', _fmt_valor(d['v_tot_trib']))

    # Total em destaque
    col_tot.append(HRFlowable(width='100%', thickness=1, color=COR_CABECALHO,
                               spaceAfter=2, spaceBefore=4))
    col_tot.append(Paragraph('VALOR TOTAL DA NOTA', s['label']))
    col_tot.append(Paragraph(_fmt_valor(d['v_nf']),
                              ParagraphStyle('vt', parent=s['valor'],
                                             fontSize=13, fontName='Helvetica-Bold',
                                             textColor=COR_CABECALHO)))

    # Coluna direita: pagamento
    col_pag = [Paragraph('FORMA DE PAGAMENTO', s['label']), Spacer(1, 1*mm)]
    for pg in d['pagamentos']:
        col_pag.append(Paragraph(pg['tipo'], s['label']))
        col_pag.append(Paragraph(_fmt_valor(pg['valor']), s['valor']))
    if d['troco'] and d['troco'] != '0.00':
        col_pag.append(Spacer(1, 1*mm))
        col_pag.append(Paragraph('Troco', s['label']))
        col_pag.append(Paragraph(_fmt_valor(d['troco']), s['valor']))

    t = Table([[col_tot, col_pag]], colWidths=[larg * 0.55, larg * 0.45])
    t.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LINEAFTER',    (0, 0), (0, 0),   0.3, colors.lightgrey),
        ('TOPPADDING',   (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
        ('LEFTPADDING',  (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('BOX',          (0, 0), (-1, -1), 0.5, COR_CABECALHO),
    ]))
    return t


def _bloco_rodape(d: dict, s: dict, larg: float) -> Table:
    """QR Code à esquerda + chave de acesso e info ao consumidor."""
    chave_fmt = _fmt_chave(d['chave'])

    qr = _qrcode_image(d['chave'], size_mm=28)

    # Info do consumidor (se houver)
    cons_lines = []
    if d['dest_cpf']:
        cons_lines.append(Paragraph(f"CPF do Consumidor: {d['dest_cpf']}", s['danfe_subtit']))
    elif d['dest_cnpj']:
        cons_lines.append(Paragraph(f"CNPJ do Consumidor: {_fmt_cnpj(d['dest_cnpj'])}", s['danfe_subtit']))
    if d['dest_nome']:
        cons_lines.append(Paragraph(f"Nome: {d['dest_nome']}", s['danfe_subtit']))
    if not cons_lines:
        cons_lines.append(Paragraph('Consumidor não identificado', s['danfe_subtit']))

    col_qr = [qr]
    col_text = (
        [Paragraph('CHAVE DE ACESSO', s['label']),
         Paragraph(chave_fmt, s['chave']),
         Spacer(1, 2*mm),
         Paragraph('Consulte em: nfce.sefaz.pe.gov.br/nfce-web/consultarNFCe', s['danfe_subtit']),
         Spacer(1, 2*mm),
         Paragraph('CONSUMIDOR', s['label']),
         ] + cons_lines
    )

    if d['inf_compl']:
        col_text += [
            Spacer(1, 2*mm),
            Paragraph('INFORMAÇÕES ADICIONAIS', s['label']),
            Paragraph(d['inf_compl'][:300], s['danfe_subtit']),
        ]

    t = Table([[col_qr, col_text]], colWidths=[32*mm, larg - 32*mm])
    t.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LINEAFTER',    (0, 0), (0, 0),   0.3, colors.lightgrey),
        ('TOPPADDING',   (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('BOX',          (0, 0), (-1, -1), 0.5, COR_CABECALHO),
        ('ALIGN',        (0, 0), (0, 0),   'CENTER'),
    ]))
    return t


# ─── Bloco de carga tributária ───────────────────────────────────────────────
def _bloco_carga_tributaria(d: dict, s: dict, larg: float) -> Table:
    """Calcula e exibe a carga tributária da nota.

    Lógica:
      valor_liquido  = v_nf − v_icms − v_tot_trib
      total_impostos = v_icms + v_tot_trib
      carga (%)      = total_impostos / valor_liquido × 100
    """
    try:
        v_nf      = float(d['v_nf']       or 0)
        v_icms    = float(d['v_icms']     or 0)
        v_trib    = float(d['v_tot_trib'] or 0)
        total_imp = v_icms + v_trib
        v_liquido = v_nf - total_imp
        carga_pct = (total_imp / v_liquido * 100) if v_liquido > 0 else 0.0
    except (ValueError, ZeroDivisionError):
        v_nf = v_icms = v_trib = total_imp = v_liquido = carga_pct = 0.0

    def campo(label, valor):
        return [Paragraph(label, s['label']), Paragraph(valor, s['valor'])]

    col = []
    col += campo('Valor Total da Nota',             _fmt_valor(f'{v_nf:.2f}'))
    col += campo('(−) ICMS',                        _fmt_valor(f'{v_icms:.2f}'))
    if v_trib:
        col += campo('(−) Trib. Aprox. (Lei 12.741)', _fmt_valor(f'{v_trib:.2f}'))
    col.append(HRFlowable(width='100%', thickness=0.5, color=COR_CABECALHO,
                          spaceAfter=2, spaceBefore=4))
    col += campo('Valor Líquido (sem impostos)',     _fmt_valor(f'{v_liquido:.2f}'))
    col.append(Spacer(1, 2*mm))
    col += campo('Total de Impostos',               _fmt_valor(f'{total_imp:.2f}'))
    col.append(HRFlowable(width='100%', thickness=1, color=COR_CABECALHO,
                          spaceAfter=2, spaceBefore=4))

    pct_str = f'{carga_pct:.2f}%'.replace('.', ',')
    col.append(Paragraph('CARGA TRIBUTÁRIA  (impostos ÷ valor líquido)', s['label']))
    col.append(Paragraph(
        pct_str,
        ParagraphStyle('carga', parent=s['valor'],
                       fontSize=13, fontName='Helvetica-Bold',
                       textColor=COR_CABECALHO),
    ))

    t = Table([[col]], colWidths=[larg])
    t.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('BOX',           (0, 0), (-1, -1), 0.5, COR_CABECALHO),
    ]))
    return t


# ─── Função principal ─────────────────────────────────────────────────────────
def gerar_pdf_de_xml(conteudo_xml: bytes, caminho_saida: Path) -> None:
    """Gera o DANFE PDF a partir do conteúdo XML bruto."""
    d = _extrair_dados(conteudo_xml)
    s = _estilos()

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(caminho_saida),
        pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=12*mm,
        title=f"DANFE NFC-e {d['n_nf']}",
        author=d['emit_nome'],
    )

    larg = A4[0] - 30*mm   # largura útil

    story = [
        _bloco_cabecalho(d, s, larg),
        Spacer(1, 3*mm),
        _bloco_secao(f"ITENS DA NOTA  ({len(d['itens'])} produto(s))", s, larg),
        Spacer(1, 1*mm),
        _bloco_itens(d['itens'], s, larg),
        PageBreak(),
        _bloco_secao('TOTAIS E FORMA DE PAGAMENTO', s, larg),
        Spacer(1, 1*mm),
        _bloco_totais_pagto(d, s, larg),
        Spacer(1, 3*mm),
        _bloco_secao('CARGA TRIBUTÁRIA', s, larg),
        Spacer(1, 1*mm),
        _bloco_carga_tributaria(d, s, larg),
        Spacer(1, 3*mm),
        _bloco_secao('CHAVE DE ACESSO / CONSULTA', s, larg),
        Spacer(1, 1*mm),
        _bloco_rodape(d, s, larg),
    ]

    doc.build(story)
    print(f'  [PDF] {caminho_saida.name}  ({len(d["itens"])} itens)')


def _processar_fonte(origem: Path, pasta_saida: Path) -> int:
    """Processa uma única fonte (XML ou ZIP) e retorna nº de PDFs gerados."""
    gerados = 0

    if origem.suffix.lower() == '.xml':
        conteudo = origem.read_bytes()
        nome_pdf = pasta_saida / (origem.stem + '.pdf')
        gerar_pdf_de_xml(conteudo, nome_pdf)
        gerados += 1

    elif origem.suffix.lower() == '.zip':
        with zipfile.ZipFile(origem, 'r') as z:
            xmls = [n for n in z.namelist()
                    if n.lower().endswith('.xml') and not n.startswith('__MACOSX')]
            if not xmls:
                print(f'  [AVISO] {origem.name}: nenhum XML encontrado no ZIP')
            for nome_xml in xmls:
                with z.open(nome_xml) as f:
                    conteudo = f.read()
                stem = Path(nome_xml).stem
                nome_pdf = pasta_saida / f'{origem.stem}__{stem}.pdf'
                gerar_pdf_de_xml(conteudo, nome_pdf)
                gerados += 1

    return gerados


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    raiz   = Path(__file__).resolve().parent.parent
    saida  = raiz / 'resources' / 'outputData' / 'danfe'

    if len(sys.argv) > 1:
        # Arquivo(s) passados como argumento
        fontes = [Path(a) for a in sys.argv[1:]]
    else:
        # Varre resources/notas_fiscais/ inteiro
        pasta  = raiz / 'resources' / 'notas_fiscais'
        fontes = [f for f in pasta.iterdir()
                  if f.suffix.lower() in ('.xml', '.zip')]
        print(f'Processando {len(fontes)} arquivo(s) em: {pasta}')

    total = 0
    for fonte in fontes:
        if not fonte.exists():
            print(f'[ERRO] Arquivo não encontrado: {fonte}')
            continue
        total += _processar_fonte(fonte, saida)

    print(f'\n[CONCLUÍDO] {total} PDF(s) gerado(s) em: {saida}')
