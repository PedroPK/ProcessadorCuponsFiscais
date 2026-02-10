import pdfplumber
import pandas as pd
import re
import zipfile
from pathlib import Path

class ProcessadorDeCupons:
    def __init__(self):
        self.dados_consolidados = []

    def _converter_valor(self, valor_str):
        """Converte strings como '1.234,50' ou '14,9' para float."""
        if not valor_str: return 0.0
        # Remove pontos de milhar e troca vírgula decimal por ponto
        limpo = valor_str.replace('.', '').replace(',', '.')
        try:
            return float(limpo)
        except ValueError:
            return 0.0

    def _extrair_dados_do_pdf(self, pdf, nome_arquivo_origem):
        texto_completo = ""
        for page in pdf.pages:
            texto_completo += page.extract_text() or ""

        # 1. Busca Data (Aceita ano com 2 ou 4 digitos: 26 ou 2026)
        match_data = re.search(r'(\d{2}/\d{2}/\d{2,4})', texto_completo)
        data_compra = match_data.group(1) if match_data else "Data Desconhecida"

        # 2. Lineariza o texto (transforma multilinhas em uma linha só)
        texto_linear = texto_completo.replace('\n', ' ').replace('\r', '')

        # 3. O NOVO REGEX (Cirúrgico para o seu layout)
        # Padrão: NOME (Cod) Vl.Total Qtde UN Vl.Unit PRECO_FINAL
        regex_item = (
            r'(?P<nome>.+?)'                # Nome do produto
            r'\(Código:\s*(?P<codigo>\d+)\)' # O Código entre parênteses
            r'\s*Vl\. Total'                # Ignora o texto "Vl. Total" solto
            r'\s*Qtde\.:\s*(?P<qtd>[\d,.]+)' # Pega a Quantidade
            r'\s*UN:\s*(?P<un>\w+)'         # Pega a Unidade (Kg, Un, etc)
            r'\s*Vl\. Unit\.:\s*(?P<vunit>[\d,.]+)' # Pega o Preço Unitário
            r'\s*(?P<vtotal>[\d,.]+)'       # Pega o número solto no final (O Total Real)
        )

        itens_encontrados = 0
        
        # O finditer percorre o texto extraindo cada bloco que casa com o regex
        for match in re.finditer(regex_item, texto_linear):
            nome = match.group('nome').strip()
            
            # LIMPEZA: O primeiro item geralmente vem com o cabeçalho (CNPJ, Endereço) grudado.
            # Vamos limpar isso cortando tudo antes de ", PE " se houver.
            if "CNPJ" in nome or "Recife" in nome:
                if "PE" in nome:
                    nome = nome.split(" PE ")[-1].strip()
            
            # Extrai os grupos do regex
            codigo = match.group('codigo')
            qtd = self._converter_valor(match.group('qtd'))
            unidade = match.group('un')
            preco_unit = self._converter_valor(match.group('vunit'))
            preco_total = self._converter_valor(match.group('vtotal'))

            if preco_total > 0:
                self.dados_consolidados.append({
                    'data': data_compra,
                    'produto': nome,
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
                qtd = self._extrair_dados_do_pdf(pdf, caminho_arquivo.name)
                print(f"[PDF] {caminho_arquivo.name}: {qtd} itens extraídos.")
        except Exception as e:
            print(f"[ERRO] Falha em {caminho_arquivo.name}: {e}")

    def processar_zip(self, caminho_zip):
        print(f"--- Abrindo ZIP: {caminho_zip.name} ---")
        try:
            with zipfile.ZipFile(caminho_zip, 'r') as z:
                # Ignora arquivos de sistema do Mac (__MACOSX)
                pdfs_no_zip = [n for n in z.namelist() if n.lower().endswith('.pdf') and not n.startswith('__MACOSX')]
                
                for nome_pdf in pdfs_no_zip:
                    with z.open(nome_pdf) as f:
                        with pdfplumber.open(f) as pdf:
                            qtd = self._extrair_dados_do_pdf(pdf, f"{caminho_zip.name}::{nome_pdf}")
                            print(f"  └── {nome_pdf}: {qtd} itens.")
        except Exception as e:
            print(f"[ERRO ZIP] {caminho_zip.name}: {e}")

    def varrer_diretorio(self, pasta_alvo):
        pasta = Path(pasta_alvo)
        if not pasta.exists():
            print(f"ERRO CRÍTICO: A pasta '{pasta}' não existe.")
            return

        arquivos = list(pasta.glob('*'))
        print(f"Lendo pasta: {pasta}")
        print(f"Arquivos encontrados: {len(arquivos)}")

        for arquivo in arquivos:
            if arquivo.suffix.lower() == '.pdf':
                self.processar_arquivo_pdf(arquivo)
            elif arquivo.suffix.lower() == '.zip':
                self.processar_zip(arquivo)

    def exportar_csv(self, nome_arquivo="minha_inflacao.csv"):
        df = pd.DataFrame(self.dados_consolidados)
        
        if not df.empty:
            # Reordena colunas
            cols = ['data', 'produto', 'qtd', 'unidade', 'preco_unit', 'preco_total', 'codigo', 'arquivo_origem']
            df = df[[c for c in cols if c in df.columns]]
            
            # Define o caminho: Raiz -> resources -> outputData
            raiz_projeto = Path(__file__).resolve().parent.parent
            pasta_saida = raiz_projeto / 'resources' / 'outputData'
            
            # Cria a pasta se não existir
            pasta_saida.mkdir(parents=True, exist_ok=True)
            
            caminho_completo = pasta_saida / nome_arquivo
            
            # --- MUDANÇA AQUI ---
            # sep=';'       -> Usa ponto e vírgula para separar as colunas (Padrão BR)
            # decimal=','   -> Usa vírgula para os números (Ex: 12,50)
            # encoding='utf-8-sig' -> Garante que acentos (ç, ã, é) funcionem no Excel/Numbers
            df.to_csv(caminho_completo, index=False, sep=';', decimal=',', encoding='utf-8-sig')
            
            print(f"\n[SUCESSO] Relatório salvo em: {caminho_completo}")
            print(f"Total de registros: {len(df)}")
            print(df.head())
        else:
            print("\n[AVISO] Nenhum dado extraído.")

# ==========================================
# CONFIGURAÇÃO DE CAMINHOS AUTOMÁTICA
# ==========================================
if __name__ == "__main__":
    # Lógica baseada no seu diagnóstico
    # Se o script está em /src, voltamos um nível (.parent) para a raiz
    raiz_projeto = Path(__file__).resolve().parent.parent
    pasta_cupons = raiz_projeto / 'resources' / 'cfs'

    print(f"Procurando na pasta: {pasta_cupons}")

    app = ProcessadorDeCupons()
    app.varrer_diretorio(pasta_cupons)
    app.exportar_csv()