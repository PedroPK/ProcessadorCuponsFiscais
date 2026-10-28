import argparse
import json
import pandas as pd
from pathlib import Path
from utils import resolver_caminho_dicionario, chave_nome_produto

COLUNAS_DICIONARIO = ['nome_original', 'nome_padrao', 'categoria']
CATEGORIA_PADRAO = 'Nova'


def dicionario_json_para_dataframe(dados, origem='dicionário'):
    """
    Converte o JSON agrupado por nome padrão em DataFrame (uma linha por nome original).

    Formato esperado:
        {"Nome Padrão": {"categoria": "...", "nomes_originais": ["NOME A", "NOME B"]}}

    Raises:
        ValueError: estrutura inválida ou nome original presente em mais de um grupo.
    """
    if not isinstance(dados, dict):
        raise ValueError(f"{origem}: o JSON deve ser um objeto {{nome_padrao: {{...}}}}.")

    linhas = []
    visto = {}
    for nome_padrao, info in dados.items():
        if not isinstance(info, dict) or not isinstance(info.get('nomes_originais'), list):
            raise ValueError(
                f"{origem}: '{nome_padrao}' deve conter a lista 'nomes_originais'."
            )
        categoria = info.get('categoria') or CATEGORIA_PADRAO
        for nome_original in info['nomes_originais']:
            nome_original = str(nome_original)
            if nome_original in visto and visto[nome_original] != nome_padrao:
                raise ValueError(
                    f"{origem}: '{nome_original}' aparece em '{visto[nome_original]}' "
                    f"e em '{nome_padrao}'."
                )
            visto[nome_original] = nome_padrao
            linhas.append({
                'nome_original': nome_original,
                'nome_padrao': nome_padrao,
                'categoria': categoria,
            })

    return pd.DataFrame(linhas, columns=COLUNAS_DICIONARIO).drop_duplicates('nome_original')


def dataframe_para_dicionario_json(df):
    """Agrupa o DataFrame por nome padrão, com chaves e listas em ordem alfabética."""
    df = df.dropna(subset=['nome_original', 'nome_padrao']).drop_duplicates('nome_original')
    resultado = {}
    for nome_padrao in sorted(df['nome_padrao'].unique(), key=lambda x: (x.lower(), x)):
        grupo = df[df['nome_padrao'] == nome_padrao]
        categorias = [c for c in grupo['categoria'].fillna('') if c.strip()]
        # Prefere uma categoria já classificada à marcação provisória "Nova"
        categoria = next((c for c in categorias if c != CATEGORIA_PADRAO), None) \
            or (categorias[0] if categorias else CATEGORIA_PADRAO)
        resultado[nome_padrao] = {
            'categoria': categoria,
            'nomes_originais': sorted(grupo['nome_original'], key=lambda x: (x.lower(), x)),
        }
    return resultado


def salvar_dicionario(df, caminho_dic):
    """Grava o dicionário em JSON legível (UTF-8, indentado)."""
    caminho_dic.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho_dic, 'w', encoding='utf-8') as arquivo:
        json.dump(dataframe_para_dicionario_json(df), arquivo, ensure_ascii=False, indent=2)
        arquivo.write('\n')


def carregar_dados_existentes(caminho_dic):
    """Carrega o dicionário atual (JSON ou XLSX legado) para não perder nada."""
    if not caminho_dic.exists():
        return pd.DataFrame(columns=COLUNAS_DICIONARIO)

    if caminho_dic.suffix.lower() == '.json':
        try:
            with open(caminho_dic, encoding='utf-8') as arquivo:
                dados = json.load(arquivo)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"JSON inválido em {caminho_dic} (linha {e.lineno}, coluna {e.colno}): {e.msg}"
            ) from e
        return dicionario_json_para_dataframe(dados, str(caminho_dic))

    return pd.read_excel(caminho_dic, dtype=str)

def sugerir_padrao(novo_nome, nomes_conhecidos_padrao):
    """Tenta adivinhar o nome padrão usando Fuzzy Matching."""
    if not nomes_conhecidos_padrao:
        return str(novo_nome).title()
    
    lista_limpa = [str(x) for x in nomes_conhecidos_padrao if pd.notna(x) and str(x).strip() != '']
    
    if not lista_limpa:
         return str(novo_nome).title()

    # Mesmo nome, só com caixa diferente: reaproveita o padrão existente
    por_chave = {chave_nome_produto(x): x for x in lista_limpa}
    existente = por_chave.get(chave_nome_produto(novo_nome))
    if existente:
        return existente

    from thefuzz import process, fuzz

    melhor_match = process.extractOne(str(novo_nome), lista_limpa, scorer=fuzz.token_sort_ratio)
    
    if melhor_match and melhor_match[1] > 80:
        return melhor_match[0]
    
    return str(novo_nome).title()


def identificar_duplicatas_por_ean(df_raw):
    """Identifica descrições distintas de produtos associadas ao mesmo EAN."""
    col_nome = 'produto_raw' if 'produto_raw' in df_raw.columns else 'produto'
    colunas = ['ean', 'nomes_originais', 'ocorrencias']

    if 'ean' not in df_raw.columns or col_nome not in df_raw.columns:
        return pd.DataFrame(columns=colunas)

    df_validos = df_raw[['ean', col_nome]].dropna(subset=['ean', col_nome]).copy()
    df_validos['ean'] = df_validos['ean'].astype(str).str.strip()
    df_validos[col_nome] = df_validos[col_nome].astype(str).str.strip()
    df_validos = df_validos[(df_validos['ean'] != '') & (df_validos[col_nome] != '')]

    duplicatas = []
    for ean, grupo in df_validos.groupby('ean', sort=True):
        nomes = list(dict.fromkeys(grupo[col_nome]))
        if len(nomes) > 1:
            duplicatas.append({
                'ean': ean,
                'nomes_originais': nomes,
                'ocorrencias': len(grupo)
            })

    return pd.DataFrame(duplicatas, columns=colunas)


def atualizar_dicionario(apenas_auditar_duplicatas=False):
    raiz = Path(__file__).resolve().parent.parent
    
    pasta_saida = raiz / 'resources' / 'outputData'
    arquivo_dados = pasta_saida / 'minha_inflacao.csv'
    arquivo_dicionario = raiz / 'resources' / 'data' / 'dicionario_produtos.json'
    caminho_dicionario_existente = resolver_caminho_dicionario(raiz)

    print("--- INICIANDO ATUALIZAÇÃO DO DICIONÁRIO ---")

    if not arquivo_dados.exists():
        print("Erro: CSV de dados não encontrado em outputData.")
        return

    df_raw = pd.read_csv(
        arquivo_dados,
        sep=';',
        decimal=',',
        encoding='utf-8-sig',
        dtype={'ean': str}
    )
    col_nome = 'produto_raw' if 'produto_raw' in df_raw.columns else 'produto'
    produtos_novos_detectados = df_raw[col_nome].dropna().unique()

    duplicatas_ean = identificar_duplicatas_por_ean(df_raw)
    if not duplicatas_ean.empty:
        print(f"Possíveis duplicatas encontradas por EAN: {len(duplicatas_ean)}")
        for _, item in duplicatas_ean.iterrows():
            nomes = ' | '.join(item['nomes_originais'])
            print(f"  EAN {item['ean']}: {nomes} ({item['ocorrencias']} ocorrências)")

    if apenas_auditar_duplicatas:
        return

    df_dic = carregar_dados_existentes(caminho_dicionario_existente)
    # XLSX legado encontrado: converte para JSON mesmo sem produtos novos
    migrar_formato = caminho_dicionario_existente != arquivo_dicionario and not df_dic.empty
    
    ja_cadastrados = set(df_dic['nome_original'].values) if not df_dic.empty else set()
    nomes_padrao_existentes = list(df_dic['nome_padrao'].dropna().unique()) if not df_dic.empty else []

    novos_itens = []
    
    print(f"Lendo dicionário em: {arquivo_dicionario}")
    print(f"Total de produtos no CSV: {len(produtos_novos_detectados)}")
    print(f"Produtos já no dicionário: {len(ja_cadastrados)}")

    # Variações só de caixa de um nome já cadastrado herdam padrão e categoria dele
    por_chave = {}
    if not df_dic.empty:
        for _, linha in df_dic.iterrows():
            por_chave.setdefault(chave_nome_produto(linha['nome_original']), linha)

    contagem_novos = 0
    for produto in produtos_novos_detectados:
        if produto not in ja_cadastrados:
            equivalente = por_chave.get(chave_nome_produto(produto))
            if equivalente is not None:
                sugestao = equivalente['nome_padrao']
                categoria = equivalente['categoria']
            else:
                sugestao = sugerir_padrao(produto, nomes_padrao_existentes)
                categoria = 'Nova'
            novos_itens.append({
                'nome_original': produto,
                'nome_padrao': sugestao,
                'categoria': categoria
            })
            contagem_novos += 1

    if novos_itens or migrar_formato:
        if novos_itens:
            print(f"Encontrados {contagem_novos} novos produtos. Adicionando e ordenando...")
            df_dic = pd.concat([df_dic, pd.DataFrame(novos_itens)], ignore_index=True)

        salvar_dicionario(df_dic, arquivo_dicionario)
        print(f"✅ Dicionário atualizado e salvo em {arquivo_dicionario}!")
    else:
        print("✅ Nenhuma novidade encontrada.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Atualiza ou audita o dicionário de produtos.")
    parser.add_argument(
        '--auditar-duplicatas',
        action='store_true',
        help='Lista produtos com descrições distintas e o mesmo EAN, sem alterar arquivos.'
    )
    args = parser.parse_args()
    atualizar_dicionario(apenas_auditar_duplicatas=args.auditar_duplicatas)