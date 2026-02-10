import pdfplumber
import os
from pathlib import Path
import re

print("--- INICIANDO DIAGNÓSTICO DE CAMINHOS ---")

# 1. Descobre onde o script está rodando
local_do_script = Path(__file__).resolve()
pasta_do_script = local_do_script.parent
raiz_do_projeto = pasta_do_script.parent

print(f"1. O script está em: {local_do_script}")
print(f"2. Assumindo que a raiz do projeto é: {raiz_do_projeto}")

# 3. Define lugares prováveis onde a pasta 'resources' pode estar
lugares_para_tentar = [
    raiz_do_projeto / 'resources' / 'cfs',   # Opção A: resources está fora da src (Raiz)
    pasta_do_script / 'resources' / 'cfs',   # Opção B: resources está dentro da src
    Path('resources/cfs').resolve()          # Opção C: Relativo ao terminal
]

pasta_encontrada = None

for tentativa in lugares_para_tentar:
    if tentativa.exists():
        print(f"-> [SUCESSO] Pasta encontrada em: {tentativa}")
        pasta_encontrada = tentativa
        break
    else:
        print(f"-> [X] Não achei aqui: {tentativa}")

if not pasta_encontrada:
    print("\n[ERRO CRÍTICO] Não encontrei a pasta 'resources/cfs' em lugar nenhum.")
    print("Certifique-se de que a estrutura de pastas está assim:")
    print("PROJETO/")
    print("├── src/")
    print("│   └── seu_script.py")
    print("└── resources/")
    print("    └── cfs/")
    print("        └── seu_arquivo.pdf")
    exit()

# 4. Procura arquivos PDF (Maiúsculo ou Minúsculo)
# Mac/Linux são 'case sensitive', então procuramos .pdf e .PDF
pdfs = list(pasta_encontrada.glob('*.pdf')) + list(pasta_encontrada.glob('*.PDF'))

print(f"\nArquivos PDF encontrados: {len(pdfs)}")

if not pdfs:
    print("A pasta existe, mas está vazia de PDFs. Verifique se o arquivo tem a extensão .pdf")
else:
    arquivo = pdfs[0]
    print(f"--- LENDO O ARQUIVO: {arquivo.name} ---")
    try:
        with pdfplumber.open(arquivo) as pdf:
            # Pega o texto da primeira página
            texto = pdf.pages[0].extract_text()
            print("\n--- INÍCIO DO CONTEÚDO ---")
            print(texto)
            print("--- FIM DO CONTEÚDO ---")
            
            # TESTE RÁPIDO DO REGEX NOVO
            # Remove quebras de linha para simular o código novo
            texto_linear = texto.replace('\n', ' ')
            
            # Procura um padrão simples de Nome + Código para ver se o Regex vai pegar
            match = re.search(r'(?P<nome>.+?)\(Código:\s*(?P<codigo>\d+)\)', texto_linear)
            if match:
                print(f"\n[TESTE DE REGEX] Sucesso! Encontrei um produto: {match.group('nome').strip()} (Cod: {match.group('codigo')})")
            else:
                print("\n[TESTE DE REGEX] O Regex não casou. O layout pode ser diferente do esperado.")
            
    except Exception as e:
        print(f"Erro ao abrir o PDF: {e}")