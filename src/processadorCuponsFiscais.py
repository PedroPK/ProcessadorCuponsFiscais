import pdfplumber
import pandas as pd
import re
import zipfile
from pathlib import Path
from extratorXml import extrair_itens_do_xml

class ProcessadorDeCupons:
    def __init__(self):
        self.dados_consolidados = []

    def _converter_valor(self, valor_str):
        if not valor_str: return 0.0
        limpo = valor_str.replace('.', '').replace(',', '.')
        try:
            return float(limpo)
        except ValueError:
            return 0.0

    def _extrair_dados_do_pdf(self, pdf, nome_arquivo_origem):
        texto_completo = ""
        for page in pdf.pages:
            texto_completo += page.extract_text() or ""

        match_data = re.search(r'(\d{2}/\d{2}/\d{2,4})', texto_completo)
        data_compra = match_data.group(1) if match_data else "Data Desconhecida"

        texto_linear = texto_completo.replace('\n', ' ').replace('\r', '')

        regex_item = (
            r'(?P<nome>.+?)'                
            r'\(Código:\s*(?P<codigo>\d+)\)' 
            r'\s*Vl\. Total'                
            r'\s*Qtde\.:\s*(?P<qtd>[\d,.]+)' 
            r'\s*UN:\s*(?P<un>\w+)'         
            r'\s*Vl\. Unit\.:\s*(?P<vunit>[\d,.]+)' 
            r'\s*(?P<vtotal>[\d,.]+)'       
        )

        itens_encontrados = 0
        for match in re.finditer(regex_item, texto_linear):
            nome = match.group('nome').strip()
            if "CNPJ" in nome or "Recife" in nome:
                if "PE" in nome:
                    nome = nome.split(" PE ")[-1].strip()
            
            codigo = match.group('codigo')
            qtd = self._converter_valor(match.group('qtd'))
            unidade = match.group('un')
            preco_unit = self._converter_valor(match.group('vunit'))
            preco_total = self._converter_valor(match.group('vtotal'))

            if preco_total > 0:
                self.dados_consolidados.append({
                    'data': data_compra,
                    'produto': nome, # Nome original (sujo)
                    'qtd': qtd,
                    'unidade': unidade,
                    'preco_unit': preco_unit,
                    'preco_total': preco_total,
                    'codigo': codigo,
                    'arquivo_origem': nome_arquivo_origem
                })
                itens_encontrados += 1
        return itens_encontrados

    def processar_arquivo_pdf(self, caminho_arquivo):
        try:
            with pdfplumber.open(caminho_arquivo) as pdf:
                self._extrair_dados_do_pdf(pdf, caminho_arquivo.name)
        except Exception as e:
            print(f"[ERRO] {caminho_arquivo.name}: {e}")

    def processar_arquivo_xml(self, caminho_arquivo):
        """Processa um único arquivo XML (NF-e / NFC-e) diretamente do disco."""
        try:
            conteudo = Path(caminho_arquivo).read_bytes()
            itens = extrair_itens_do_xml(conteudo, caminho_arquivo.name)
            self.dados_consolidados.extend(itens)
            print(f"  [XML] {caminho_arquivo.name}: {len(itens)} item(s)")
        except Exception as e:
            print(f"[ERRO XML] {caminho_arquivo.name}: {e}")

    def processar_zip(self, caminho_zip):
        """Processa um ZIP podendo conter PDFs e/ou XMLs de NF-e."""
        try:
            with zipfile.ZipFile(caminho_zip, 'r') as z:
                entradas = [
                    n for n in z.namelist()
                    if not n.startswith('__MACOSX') and not n.endswith('/')
                ]

                pdfs = [n for n in entradas if n.lower().endswith('.pdf')]
                xmls = [n for n in entradas if n.lower().endswith('.xml')]

                for nome_pdf in pdfs:
                    with z.open(nome_pdf) as f:
                        with pdfplumber.open(f) as pdf:
                            self._extrair_dados_do_pdf(pdf, f"{caminho_zip.name}::{nome_pdf}")

                for nome_xml in xmls:
                    with z.open(nome_xml) as f:
                        conteudo = f.read()
                    itens = extrair_itens_do_xml(conteudo, f"{caminho_zip.name}::{nome_xml}")
                    self.dados_consolidados.extend(itens)
                    print(f"  [XML] {caminho_zip.name}::{nome_xml}: {len(itens)} item(s)")

        except Exception as e:
            print(f"[ERRO ZIP] {caminho_zip.name}: {e}")

    def varrer_diretorio(self, pasta_alvo):
        pasta = Path(pasta_alvo)
        arquivos = list(pasta.glob('*'))
        print(f"Lendo {len(arquivos)} arquivos em: {pasta}")
        for arquivo in arquivos:
            if arquivo.suffix.lower() == '.pdf':
                self.processar_arquivo_pdf(arquivo)
            elif arquivo.suffix.lower() == '.xml':
                self.processar_arquivo_xml(arquivo)
            elif arquivo.suffix.lower() == '.zip':
                self.processar_zip(arquivo)

    # --- NOVIDADE: Método para aplicar o dicionário ---
    def _aplicar_normalizacao(self, df):
        raiz = Path(__file__).resolve().parent.parent
        caminho_dic = raiz / 'resources' / 'dicionario_produtos.xlsx'
        
        if caminho_dic.exists():
            print("Aplicando dicionário de produtos...")
            try:
                # Lê o Excel
                df_dic = pd.read_excel(caminho_dic)
                
                # Cria um dicionário Python { 'Nome Sujo': 'Nome Limpo' }
                mapa_nomes = dict(zip(df_dic['nome_original'], df_dic['nome_padrao']))
                mapa_categorias = dict(zip(df_dic['nome_original'], df_dic['categoria']))
                
                # Aplica a troca
                # Se não achar no dicionário, mantém o nome original
                df['produto_raw'] = df['produto'] # Guarda o original por segurança
                df['produto'] = df['produto_raw'].map(mapa_nomes).fillna(df['produto_raw'])
                df['categoria'] = df['produto_raw'].map(mapa_categorias).fillna('Outros')
                
                return df
            except Exception as e:
                print(f"Erro ao ler dicionário: {e}")
                return df
        else:
            print("Dicionário não encontrado. Usando nomes originais.")
            return df

    def exportar_csv(self, nome_arquivo="minha_inflacao.csv"):
        df = pd.DataFrame(self.dados_consolidados)
        
        if not df.empty:
            # --- Aplica a Normalização antes de salvar ---
            df = self._aplicar_normalizacao(df)
            
            # Reordena — inclui campos extras vindos de XMLs (ean, ncm, loja, cnpj)
            cols = ['data', 'loja', 'cnpj', 'categoria', 'produto', 'qtd', 'unidade',
                    'preco_unit', 'preco_total', 'codigo', 'ean', 'ncm', 'arquivo_origem']
            # Garante que as colunas existem (caso o dicionário tenha falhado)
            cols_finais = [c for c in cols if c in df.columns]
            df = df[cols_finais]

            # Mantém identificadores como texto (evita notação científica no CSV)
            for col in ['codigo', 'ean', 'ncm', 'cnpj']:
                if col in df.columns:
                    df[col] = df[col].fillna('').astype(str).str.replace(r'\.0$', '', regex=True)
            
            raiz_projeto = Path(__file__).resolve().parent.parent
            pasta_saida = raiz_projeto / 'resources' / 'outputData'
            pasta_saida.mkdir(parents=True, exist_ok=True)
            
            caminho_completo = pasta_saida / nome_arquivo
            df.to_csv(caminho_completo, index=False, sep=';', decimal=',', encoding='utf-8-sig')
            
            print(f"\n[SUCESSO] Relatório salvo em: {caminho_completo}")
            cols_preview = [c for c in ['loja', 'produto', 'preco_unit', 'categoria'] if c in df.columns]
            print(df[cols_preview].head())
        else:
            print("\n[AVISO] Nenhum dado extraído.")

if __name__ == "__main__":
    raiz_projeto = Path(__file__).resolve().parent.parent
    pasta_cupons = raiz_projeto / 'resources' / 'cfs'
    
    app = ProcessadorDeCupons()
    app.varrer_diretorio(pasta_cupons)
    app.exportar_csv()