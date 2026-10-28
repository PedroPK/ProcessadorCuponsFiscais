import argparse
import shutil
import pandas as pd
from pathlib import Path
from utils import resolver_caminho_dicionario

def carregar_dados_existentes(caminho_dic):
    """Carrega o dicionário atual para não perder nada."""
    if caminho_dic.exists():
        return pd.read_excel(caminho_dic, dtype=str)
    else:
        return pd.DataFrame(columns=['nome_original', 'nome_padrao', 'categoria'])

def sugerir_padrao(novo_nome, nomes_conhecidos_padrao):
    """Tenta adivinhar o nome padrão usando Fuzzy Matching."""
    from thefuzz import process, fuzz

    if not nomes_conhecidos_padrao:
        return str(novo_nome).title()
    
    lista_limpa = [str(x) for x in nomes_conhecidos_padrao if pd.notna(x) and str(x).strip() != '']
    
    if not lista_limpa:
         return str(novo_nome).title()

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
    arquivo_dicionario = raiz / 'resources' / 'data' / 'dicionario_produtos.xlsx'
    caminho_dicionario_existente = resolver_caminho_dicionario(raiz)

    print("--- INICIANDO ATUALIZAÇÃO DO DICIONÁRIO ---")

    if not arquivo_dados.exists():
        print("Erro: CSV de dados não encontrado em outputData.")
        return

    arquivo_dicionario.parent.mkdir(parents=True, exist_ok=True)
    if caminho_dicionario_existente != arquivo_dicionario:
        shutil.copy2(caminho_dicionario_existente, arquivo_dicionario)
        print(f"Dicionário legado copiado para: {arquivo_dicionario}")
    
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

    df_dic = carregar_dados_existentes(arquivo_dicionario)
    
    ja_cadastrados = set(df_dic['nome_original'].values) if not df_dic.empty else set()
    nomes_padrao_existentes = list(df_dic['nome_padrao'].dropna().unique()) if not df_dic.empty else []

    novos_itens = []
    
    print(f"Lendo dicionário em: {arquivo_dicionario}")
    print(f"Total de produtos no CSV: {len(produtos_novos_detectados)}")
    print(f"Produtos já no dicionário: {len(ja_cadastrados)}")

    contagem_novos = 0
    for produto in produtos_novos_detectados:
        if produto not in ja_cadastrados:
            sugestao = sugerir_padrao(produto, nomes_padrao_existentes)
            novos_itens.append({
                'nome_original': produto,
                'nome_padrao': sugestao,
                'categoria': 'Nova'
            })
            contagem_novos += 1

    if novos_itens:
        print(f"Encontrados {contagem_novos} novos produtos. Adicionando e ordenando...")
        
        df_novos = pd.DataFrame(novos_itens)
        df_final = pd.concat([df_dic, df_novos], ignore_index=True)
        
        # Ordena alfabeticamente ignorando maiúsculas/minúsculas
        df_final = df_final.sort_values(by='nome_original', key=lambda col: col.str.lower())
        
        df_final.to_excel(arquivo_dicionario, index=False)
        print("✅ Dicionário atualizado e salvo em outputData!")
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