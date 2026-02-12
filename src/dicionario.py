import pandas as pd
from pathlib import Path
from thefuzz import process, fuzz

def carregar_dados_existentes(caminho_dic):
    """Carrega o dicionário atual para não perder nada."""
    if caminho_dic.exists():
        return pd.read_excel(caminho_dic, dtype=str)
    else:
        return pd.DataFrame(columns=['nome_original', 'nome_padrao', 'categoria'])

def sugerir_padrao(novo_nome, nomes_conhecidos_padrao):
    """Tenta adivinhar o nome padrão usando Fuzzy Matching."""
    if not nomes_conhecidos_padrao:
        return str(novo_nome).title()
    
    lista_limpa = [str(x) for x in nomes_conhecidos_padrao if pd.notna(x) and str(x).strip() != '']
    
    if not lista_limpa:
         return str(novo_nome).title()

    melhor_match = process.extractOne(str(novo_nome), lista_limpa, scorer=fuzz.token_sort_ratio)
    
    if melhor_match and melhor_match[1] > 80:
        return melhor_match[0]
    
    return str(novo_nome).title()

def atualizar_dicionario():
    raiz = Path(__file__).resolve().parent.parent
    
    # --- MUDANÇA DE CAMINHO AQUI ---
    # Agora ambos ficam dentro de outputData
    pasta_saida = raiz / 'resources' / 'outputData'
    arquivo_dados = pasta_saida / 'minha_inflacao.csv'
    arquivo_dicionario = pasta_saida / 'dicionario_produtos.xlsx'

    print("--- INICIANDO ATUALIZAÇÃO DO DICIONÁRIO ---")

    if not arquivo_dados.exists():
        print("Erro: CSV de dados não encontrado em outputData.")
        return
    
    df_raw = pd.read_csv(arquivo_dados, sep=';', decimal=',', encoding='utf-8-sig')
    produtos_novos_detectados = df_raw['produto'].dropna().unique()

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
    atualizar_dicionario()