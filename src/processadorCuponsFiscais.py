import pdfplumber
import pandas as pd
import re
import zipfile
from pathlib import Path
from extratorXml import extrair_itens_do_xml, extrair_chave_do_xml

class ProcessadorDeCupons:
    def __init__(self):
        self.dados_consolidados = []
        # Conjunto de chaves de acesso NF-e já processadas (44 dígitos).
        # Evita duplicidade quando o mesmo documento existe como XML e como PDF.
        self._chaves_processadas: set[str] = set()

    def _converter_valor(self, valor_str):
        if not valor_str: return 0.0
        limpo = valor_str.replace('.', '').replace(',', '.')
        try:
            return float(limpo)
        except ValueError:
            return 0.0

    def _extrair_chave_pdf(self, texto: str) -> str | None:
        """
        Tenta localizar a chave de acesso NF-e (44 dígitos) dentro do texto
        extraído de um DANFE PDF. A chave pode estar formatada em blocos
        separados por espaços (ex.: '2625 0506 ...').
        Retorna a chave sem espaços (44 dígitos) ou None se não encontrar.
        """
        # Remove espaços e quebras para facilitar a busca
        texto_sem_espacos = re.sub(r'\s+', '', texto)
        match = re.search(r'(?<![\d])(\d{44})(?![\d])', texto_sem_espacos)
        return match.group(1) if match else None

    def _extrair_dados_do_pdf(self, pdf, nome_arquivo_origem):
        texto_completo = ""
        for page in pdf.pages:
            texto_completo += page.extract_text() or ""

        match_data = re.search(r'(\d{2}/\d{2}/\d{2,4})', texto_completo)
        data_compra = match_data.group(1) if match_data else "Data Desconhecida"

        texto_linear = texto_completo.replace('\n', ' ').replace('\r', '')

        regex_item = (
            r'(?P<nome>.+?)'                
            r'\(Código:\s*(?P<codigo>[A-Za-z]?\d+)\)' 
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
                # Extrai o texto da primeira página apenas para verificar a chave
                texto_p1 = pdf.pages[0].extract_text() or '' if pdf.pages else ''
                chave = self._extrair_chave_pdf(texto_p1)
                if chave:
                    if chave in self._chaves_processadas:
                        print(f"  [SKIP PDF] {caminho_arquivo.name}: chave já processada via XML")
                        return
                    self._chaves_processadas.add(chave)
                self._extrair_dados_do_pdf(pdf, caminho_arquivo.name)
        except Exception as e:
            print(f"[ERRO] {caminho_arquivo.name}: {e}")

    def processar_arquivo_xml(self, caminho_arquivo):
        """Processa um único arquivo XML (NF-e / NFC-e) diretamente do disco."""
        try:
            conteudo = Path(caminho_arquivo).read_bytes()
            chave = extrair_chave_do_xml(conteudo)
            if chave:
                if chave in self._chaves_processadas:
                    print(f"  [SKIP XML] {caminho_arquivo.name}: chave duplicada, ignorado")
                    return
                self._chaves_processadas.add(chave)
            itens = extrair_itens_do_xml(conteudo, caminho_arquivo.name)
            self.dados_consolidados.extend(itens)
            print(f"  [XML] {caminho_arquivo.name}: {len(itens)} item(s)")
        except Exception as e:
            print(f"[ERRO XML] {caminho_arquivo.name}: {e}")

    def _processar_xlsx_citizen(self, conteudo_bytes: bytes, nome_origem: str) -> int:
        """Processa exportação de Notas Fiscais do app Citizen (XLSX).

        Espera uma aba 'Notas Fiscais' com cabeçalho contendo a coluna 'Chave'.
        Usa a chave NF-e (44 dígitos) para deduplicação global.
        Retorna a quantidade de itens adicionados.
        """
        try:
            import io as _io
            df_sheets = pd.read_excel(_io.BytesIO(conteudo_bytes), sheet_name=None)
            sheet = df_sheets.get('Notas Fiscais')
            if sheet is None:
                return 0

            # Localiza a linha que contém o cabeçalho ('Chave' deve estar presente)
            header_row = None
            for i, row in sheet.iterrows():
                if 'Chave' in row.values:
                    header_row = i
                    break
            if header_row is None:
                return 0

            sheet.columns = sheet.iloc[header_row].tolist()
            sheet = sheet.iloc[header_row + 1:].reset_index(drop=True)
            sheet = sheet.dropna(subset=['Chave', 'Descricao'])
            # Mantém apenas linhas de DocumentoFiscal (ignora despesas manuais)
            if 'TipoDespesa' in sheet.columns:
                sheet = sheet[sheet['TipoDespesa'] == 'DocumentoFiscal']

            count = 0
            for chave_val, grupo in sheet.groupby('Chave', sort=False):
                chave_str = str(chave_val).strip()
                if len(chave_str) == 44 and chave_str in self._chaves_processadas:
                    print(f"  [SKIP XLSX] chave {chave_str[:8]}...: já processada")
                    continue
                if len(chave_str) == 44:
                    self._chaves_processadas.add(chave_str)

                for _, row in grupo.iterrows():
                    loja = str(row.get('NomeFantasia', '') or '').strip()
                    if not loja or loja == 'nan':
                        loja = str(row.get('RazaoSocial', '') or '').strip()

                    try:
                        qtd = float(str(row.get('Quantidade', 0)).replace(',', '.'))
                    except (ValueError, TypeError):
                        qtd = 0.0

                    try:
                        preco_unit = float(row.get('ValorUnitarioProduto', 0) or 0)
                    except (ValueError, TypeError):
                        preco_unit = 0.0

                    try:
                        preco_total = float(row.get('ValorTotalProduto', 0) or 0)
                    except (ValueError, TypeError):
                        preco_total = 0.0

                    if preco_total <= 0:
                        continue

                    data = str(row.get('DataEmissao', '')).strip()
                    # Normaliza para dd/mm/yyyy se vier em yyyy-mm-dd
                    if re.match(r'\d{4}-\d{2}-\d{2}', data):
                        data = f"{data[8:10]}/{data[5:7]}/{data[:4]}"

                    self.dados_consolidados.append({
                        'data': data,
                        'loja': loja,
                        'cnpj': str(row.get('CNPJ', '') or '').strip(),
                        'produto': str(row.get('Descricao', '')).strip(),
                        'qtd': qtd,
                        'unidade': str(row.get('Unidade', '') or '').strip(),
                        'preco_unit': preco_unit,
                        'preco_total': preco_total,
                        'codigo': '',
                        'ean': '',
                        'ncm': str(row.get('NCM', '') or '').strip(),
                        'chave_nfe': chave_str,
                        'arquivo_origem': nome_origem,
                    })
                    count += 1

            return count
        except Exception as e:
            print(f"[ERRO XLSX] {nome_origem}: {e}")
            return 0

    def _processar_membros_zip(self, z: zipfile.ZipFile, nome_zip_raiz: str) -> None:
        """Processa todos os membros de um ZipFile aberto.

        Estratégia:
        1. XMLs primeiro — registram as chaves NF-e.
        2. XLSXs (formato Citizen) — deduplicam por chave.
        3. PDFs — cada um verificado individualmente pela chave extraída;
           só são pulados se a chave já foi registrada (ex.: DANFE de um XML).
        4. ZIPs aninhados — processados recursivamente.
        """
        import io as _io

        entradas = [
            n for n in z.namelist()
            if not n.startswith('__MACOSX') and not n.endswith('/')
        ]
        xmls  = [n for n in entradas if n.lower().endswith('.xml')]
        pdfs  = [n for n in entradas if n.lower().endswith('.pdf')]
        xlsxs = [n for n in entradas if n.lower().endswith('.xlsx')]
        zips  = [n for n in entradas if n.lower().endswith('.zip')]

        # --- XMLs ---
        for nome_xml in xmls:
            with z.open(nome_xml) as f:
                conteudo = f.read()
            chave = extrair_chave_do_xml(conteudo)
            origem = f"{nome_zip_raiz}::{nome_xml}"
            if chave:
                if chave in self._chaves_processadas:
                    print(f"  [SKIP XML] {origem}: chave duplicada")
                    continue
                self._chaves_processadas.add(chave)
            itens = extrair_itens_do_xml(conteudo, origem)
            self.dados_consolidados.extend(itens)
            print(f"  [XML] {origem}: {len(itens)} item(s)")

        # --- XLSXs (Citizen) ---
        for nome_xlsx in xlsxs:
            with z.open(nome_xlsx) as f:
                conteudo = f.read()
            origem = f"{nome_zip_raiz}::{nome_xlsx}"
            n = self._processar_xlsx_citizen(conteudo, origem)
            print(f"  [XLSX] {origem}: {n} item(s)")

        # --- PDFs (deduplicação por chave, sem pular em bloco) ---
        for nome_pdf in pdfs:
            with z.open(nome_pdf) as f:
                pdf_bytes = f.read()
            origem = f"{nome_zip_raiz}::{nome_pdf}"
            try:
                with pdfplumber.open(_io.BytesIO(pdf_bytes)) as pdf:
                    texto_p1 = pdf.pages[0].extract_text() or '' if pdf.pages else ''
                    chave = self._extrair_chave_pdf(texto_p1)
                    if chave:
                        if chave in self._chaves_processadas:
                            print(f"  [SKIP PDF] {origem}: chave já processada")
                            continue
                        self._chaves_processadas.add(chave)
                    n = self._extrair_dados_do_pdf(pdf, origem)
                    if n > 0:
                        print(f"  [PDF] {origem}: {n} item(s)")
            except Exception as e:
                print(f"[ERRO PDF] {origem}: {e}")

        # --- ZIPs aninhados (recursão) ---
        for nome_zip in zips:
            with z.open(nome_zip) as f:
                try:
                    inner_bytes = _io.BytesIO(f.read())
                    with zipfile.ZipFile(inner_bytes) as inner_z:
                        print(f"  [ZIP aninhado] abrindo {nome_zip_raiz}::{nome_zip}")
                        self._processar_membros_zip(inner_z, f"{nome_zip_raiz}::{nome_zip}")
                except Exception as e:
                    print(f"[ERRO ZIP aninhado] {nome_zip}: {e}")

    def processar_zip(self, caminho_zip):
        """Processa um ZIP podendo conter PDFs, XMLs, XLSXs e ZIPs aninhados."""
        try:
            with zipfile.ZipFile(caminho_zip, 'r') as z:
                self._processar_membros_zip(z, caminho_zip.name)
        except Exception as e:
            print(f"[ERRO ZIP] {caminho_zip.name}: {e}")

    def varrer_diretorio(self, pasta_alvo):
        pasta = Path(pasta_alvo)
        arquivos = list(pasta.glob('*'))
        print(f"Lendo {len(arquivos)} arquivos em: {pasta}")

        # Passo 1: ZIPs e XMLs avulsos primeiro (registram as chaves)
        for arquivo in arquivos:
            if arquivo.suffix.lower() == '.xml':
                self.processar_arquivo_xml(arquivo)
            elif arquivo.suffix.lower() == '.zip':
                self.processar_zip(arquivo)

        # Passo 2: XLSXs avulsos (formato Citizen)
        for arquivo in arquivos:
            if arquivo.suffix.lower() == '.xlsx':
                conteudo = arquivo.read_bytes()
                n = self._processar_xlsx_citizen(conteudo, arquivo.name)
                print(f"  [XLSX] {arquivo.name}: {n} item(s)")

        # Passo 3: processa PDFs avulsos — pula os que já foram cobertos por XML
        for arquivo in arquivos:
            if arquivo.suffix.lower() == '.pdf':
                self.processar_arquivo_pdf(arquivo)

    # --- NOVIDADE: Método para aplicar o dicionário ---
    def _aplicar_normalizacao(self, df):
        raiz = Path(__file__).resolve().parent.parent
        caminho_dic = raiz / 'resources' / 'outputData' / 'dicionario_produtos.xlsx'
        df['produto_raw'] = df['produto']
        
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
            cols = ['data', 'loja', 'cnpj', 'categoria', 'produto', 'produto_raw', 'qtd', 'unidade',
                    'preco_unit', 'preco_total', 'codigo', 'ean', 'ncm', 'chave_nfe', 'arquivo_origem']
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
    pasta_cupons = raiz_projeto / 'resources' / 'notas_fiscais'
    
    app = ProcessadorDeCupons()
    app.varrer_diretorio(pasta_cupons)
    app.exportar_csv()