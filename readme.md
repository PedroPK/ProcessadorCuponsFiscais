# 🛒 Monitor de Inflação Pessoal

Uma ferramenta em Python para extrair dados de Cupons Fiscais (NFC-e) em PDF, criar um banco de dados histórico de compras e visualizar a evolução dos preços através de um Dashboard interativo.

## 📋 Sobre o Projeto

Este software resolve o problema de rastrear a "inflação real" do consumidor. Diferente dos índices oficiais (IPCA), que usam uma cesta de produtos genérica, este projeto calcula a inflação baseada **exatamente no que você compra**.

**Funcionalidades:**
* **Extração Inteligente:** Lê PDFs (soltos ou em ZIP) de Notas Fiscais Eletrônicas.
* **Normalização de Nomes:** Usa algoritmos de similaridade (*Fuzzy Matching*) para identificar variações de nomes de produtos.
* **Dashboard Interativo:** Painel visual para analisar variação de preços e Curva ABC (Pareto).

---

## 📂 Estrutura de Pastas Esperada

```text
MEU_PROJETO/
├── src/
│   ├── main.py              # Script principal de extração
│   ├── criar_dicionario.py  # Script de normalização de nomes
│   └── dashboard.py         # Interface visual (Streamlit)
├── resources/
│   ├── cfs/                 # COLOQUE SEUS PDFs AQUI (ou arquivos .zip)
│   └── outputData/          # AQUI SERÃO GERADOS OS RESULTADOS (CSV e Excel)
├── .venv/                   # Ambiente virtual Python (recomendado)
└── README.md
```

## 💾 Instalação (Faça apenas na 1ª vez)
Siga estes passos no seu terminal (Prompt de Comando ou Terminal do VS Code) para preparar o terreno.

Passo A: Criar o Ambiente Virtual
Isso isola o projeto para não bagunçar seu computador.

### No Windows:

```Bash
python3 -m venv .venv
.\.venv\Scripts\activate
````


### No Mac / Linux:

```Bash
python3 -m venv .venv
source .venv/bin/activate
````

(Você saberá que funcionou se aparecer um (.venv) verde ou branco no início da linha do terminal).


#### Passo B: Instalar as Bibliotecas
Copie e cole este comando inteiro para baixar tudo o que o projeto precisa:

```Bash
pip install pdfplumber pandas openpyxl streamlit plotly thefuzz python-Levenshtein
```


## ▶️ Como Executar (Fluxo de Trabalho)
Sempre que você tiver novas notas fiscais, siga esta ordem:

### 1️⃣ Colocar os Arquivos
Pegue seus arquivos .pdf (ou arquivos .zip com vários PDFs dentro) e coloque na pasta:

```
resources/cfs/
````

### 2️⃣ Extrair os Dados (Bruto)
Rode este comando para ler os PDFs e gerar o CSV inicial:

```Bash
python3 src/processadorCuponsFiscais.py
````

**O que faz:**
- Lê arquivos PDF ou ZIP dentro de `resources/cfs/`
- Extrai dados de produtos, preços e datas
- Gera o arquivo `resources/outputData/minha_inflacao.csv`

---

✅ Resultado: Vai criar/atualizar o arquivo resources/outputData/minha_inflacao.csv.

### 3️⃣ Normalizar Nomes (Limpeza)
Rode este comando para padronizar nomes (ex: transformar "LEITE PARMALAT CX" em "Leite Integral"):

```Bash
python3 src/criar_dicionario.py
```

**O que faz:**
- Lê o arquivo CSV gerado pelo processador
- Sugere nomes padrão usando Fuzzy Matching
- Cria/atualiza `resources/outputData/dicionario_produtos.numbers` (ou Excel)
- Facilita a análise em "produtos iguais com nomes diferentes"

✅ Resultado: Vai criar/atualizar resources/outputData/dicionario_produtos.xlsx.

**Dica Importante**: Após rodar esse comando, abra o arquivo Excel gerado, corrija a coluna "nome_padrao" manualmente se necessário, salve, e depois rode o comando do Passo 2 novamente para atualizar seu CSV final com os nomes corrigidos.

### 4️⃣ Abrir o Painel (Dashboard)
Para ver os gráficos e a análise de inflação, rode:

```Bash
streamlit run src/dashboard.py
```

**O que abre:**
- O navegador abrirá automaticamente com seu Dashboard.
- Serão exibidos gráficos de evolução de preços
- Permite uma análise de inflação pessoal
- Curva ABC (Pareto) dos gastos

**Para parar o dashboard:** Pressione `Ctrl + C` no terminal

---

### 🆘 Problemas Comuns
Erro: "ModuleNotFoundError"
- Causa: Você esqueceu de ativar o ambiente virtual.
- Solução: Rode o comando do Passo A da instalação novamente.
---

Erro: "No such file or directory"
- Causa: Você não está na pasta raiz do projeto no terminal.
- Solução: Use o comando cd para entrar na pasta do projeto antes de rodar os scripts.
---

Erro: "Pasta resources/cfs não encontrada"
- Causa: Você esqueceu de criar a pasta.
- Solução: Crie a pasta resources na raiz e dentro dela a pasta cfs.

---