"""
Configurações compartilhadas dos testes.
Adiciona src/ ao sys.path para que os módulos possam ser importados diretamente.
"""
import sys
from pathlib import Path

# Garante que `import extratorXml`, `import processadorCuponsFiscais` etc. funcionem
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))


# ── Fixtures compartilhadas ────────────────────────────────────────────────────

NFE_CHAVE = '26260306057223049189650130001286971130305212'

XML_VALIDO = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe Id="NFe{NFE_CHAVE}">
      <ide>
        <dhEmi>2026-03-01T13:01:36-03:00</dhEmi>
      </ide>
      <emit>
        <CNPJ>06057223049189</CNPJ>
        <xNome>SUPERMERCADO TESTE LTDA</xNome>
        <xFant>SUPER TESTE</xFant>
      </emit>
      <det nItem="1">
        <prod>
          <cProd>001</cProd>
          <cEAN>7891234560013</cEAN>
          <xProd>LEITE INTEGRAL 1L</xProd>
          <NCM>04011000</NCM>
          <qCom>2.0000</qCom>
          <uCom>UN</uCom>
          <vUnCom>4.89</vUnCom>
          <vProd>9.78</vProd>
        </prod>
      </det>
      <det nItem="2">
        <prod>
          <cProd>002</cProd>
          <cEAN>SEM GTIN</cEAN>
          <xProd>PAO FRANCES</xProd>
          <NCM>19059090</NCM>
          <qCom>6.0000</qCom>
          <uCom>UN</uCom>
          <vUnCom>0.75</vUnCom>
          <vProd>4.50</vProd>
        </prod>
      </det>
      <det nItem="3">
        <prod>
          <cProd>003</cProd>
          <cEAN>SEM GTIN</cEAN>
          <xProd>SACOLA CORTESIA</xProd>
          <NCM>39232100</NCM>
          <qCom>1.0000</qCom>
          <uCom>UN</uCom>
          <vUnCom>0.00</vUnCom>
          <vProd>0.00</vProd>
        </prod>
      </det>
    </infNFe>
  </NFe>
</nfeProc>
"""

XML_SEM_CHAVE = """\
<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe>
      <ide><dhEmi>2026-01-01T10:00:00-03:00</dhEmi></ide>
      <emit><CNPJ>00000000000000</CNPJ><xNome>SEM CHAVE</xNome></emit>
    </infNFe>
  </NFe>
</nfeProc>
"""

XML_MALFORMADO = "isto nao e xml valido <<<"
