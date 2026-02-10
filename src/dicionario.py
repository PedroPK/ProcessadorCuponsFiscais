import pandas as pd
from pathlib import Path

def criar_planilha_depara():
    # 1. Define caminhos
    raiz = Path(__file__).resolve().parent.parent
    arquivo_dados = raiz / 'resources' / 'outputData' / 'minha_inflacao.csv'
    arquivo_dicionario = raiz / 'resources' / 'dicionario_produtos.xlsx'

    # 2. Carrega os dados atuais
    if not arquivo_dados.exists():
        print("Erro: O arquivo de dados não existe. Rode o main.py primeiro.")
        return

    df = pd.read_csv(arquivo_dados, sep=';', decimal=',', encoding='utf-8-sig')
    
    # 3. Pega todos os nomes únicos encontrados até hoje
    produtos_unicos = df['produto'].unique()
    print(f"Encontrados {len(produtos_unicos)} nomes de produtos diferentes.")

    # 4. Verifica se o dicionário já existe para não apagar seu trabalho
    if arquivo_dicionario.exists():
        print("Carregando dicionário existente...")
        df_existente = pd.read_excel(arquivo_dicionario)
        # Pega apenas os nomes novos que ainda não estão no Excel
        novos_produtos = [p for p in produtos_unicos if p not in df_existente['nome_original'].values]
        
        if novos_produtos:
            print(f"Adicionando {len(novos_produtos)} novos produtos ao dicionário.")
            df_novos = pd.DataFrame({'nome_original': novos_produtos, 'nome_padrao': '', 'categoria': ''})
            df_final = pd.concat([df_existente, df_novos], ignore_index=True)
            df_final.to_excel(arquivo_dicionario, index=False)
        else:
            print("Nenhum produto novo encontrado.")
    else:
        # Cria o arquivo do zero
        print("Criando novo arquivo de dicionário...")
        df_novo = pd.DataFrame({
            'nome_original': produtos_unicos,
            'nome_padrao': produtos_unicos, # Sugere o próprio nome inicialmente
            'categoria': 'Geral' # Coluna extra para você agrupar (Laticínios, Limpeza, etc)
        })
        df_novo.to_excel(arquivo_dicionario, index=False)
    
    print(f"\n[SUCESSO] Abra o arquivo em:\n{arquivo_dicionario}")
    print("Preencha a coluna 'nome_padrao' com os nomes corrigidos e salve.")

if __name__ == "__main__":
    criar_planilha_depara()