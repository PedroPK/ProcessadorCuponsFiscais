# 🛒 Monitor de Inflação Pessoal

Uma ferramenta em Python para extrair dados de Notas Fiscais (NFC-e) — em formato **XML ou PDF** —, criar um banco de dados histórico de compras e visualizar a evolução dos preços através de um Dashboard interativo.

## 📋 Sobre o Projeto

Este software resolve o problema de rastrear a "inflação real" do consumidor. Diferente dos índices oficiais (IPCA), que usam uma cesta de produtos genérica, este projeto calcula a inflação baseada **exatamente no que você compra**.

**Funcionalidades:**
* **Extração via XML (preferencial):** Lê diretamente o XML da NF-e (obtido pelo app de consulta de notas fiscais). Dados estruturados, precisos e sem necessidade de regex — inclui EAN, NCM, CNPJ e nome da loja.
* **Extração via PDF (legado):** Continua suportando arquivos DANFE em PDF para notas mais antigas.
* **Deduplicação automática:** Usa a **chave de acesso NF-e (44 dígitos)** para garantir que a mesma nota não seja contada duas vezes, mesmo que exista nos dois formatos ou duplicada dentro de um ZIP.
* **Normalização de Nomes:** Usa algoritmos de similaridade (*Fuzzy Matching*) para identificar variações de nomes de produtos.
* **Dashboard Interativo:** Painel visual para analisar variação de preços e Curva ABC (Pareto).

### Comparativo XML vs PDF

| | XML (NF-e) | PDF (DANFE) |
|---|---|---|
| Parsing | Zero regex, 100% confiável | Regex frágil, depende do layout |
| Nome do produto | Exato (dado do sistema da loja) | Abreviado/truncado |
| Código EAN (barcode) | ✅ | ❌ |
| Código NCM (fiscal) | ✅ | ❌ |
| Nome e CNPJ da loja | ✅ | ❌ |
| Data/hora exata | ✅ ISO 8601 com timezone | Somente data, via regex |

> **Recomendação:** sempre prefira baixar o XML da nota (disponível no app "NFC-e" ou pelo QR Code do cupom). O PDF só é necessário para notas antigas que você não tenha o XML.

---

## 📂 Estrutura de Pastas Esperada

```text
MEU_PROJETO/
├── src/
│   ├── processadorCuponsFiscais.py  # Script principal de extração
│   ├── extratorXml.py               # Parser de NF-e XML (chamado pelo processador)
│   ├── gerador_danfe.py             # Converte XML → PDF legível (DANFE simplificado)
│   ├── dicionario.py                # Script de normalização de nomes
│   └── dashboard.py                 # Interface visual (Streamlit)
├── resources/
│   ├── notas_fiscais/  # COLOQUE SEUS ARQUIVOS AQUI (.xml, .pdf ou .zip)
│   └── outputData/     # AQUI SERÃO GERADOS OS RESULTADOS
│       ├── minha_inflacao.csv      # CSV de dados extraídos
│       ├── dicionario_produtos.xlsx # Dicionário de normalização
│       └── danfe/                  # DANFEs em PDF gerados a partir de XMLs
├── .venv/            # Ambiente virtual Python (recomendado)
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
pip install pdfplumber pandas openpyxl streamlit plotly thefuzz python-Levenshtein reportlab qrcode
```

> **Nota:** o suporte a XML utiliza a biblioteca `xml.etree.ElementTree`, que já vem incluída no Python — nenhum pacote extra é necessário para isso.


## ▶️ Como Executar (Fluxo de Trabalho)
Sempre que você tiver novas notas fiscais, siga esta ordem:

### 1️⃣ Colocar os Arquivos
Pegue seus arquivos e coloque na pasta `resources/notas_fiscais/`. Os formatos aceitos são:

| Formato | Descrição |
|---|---|
| `.xml` | XML da NF-e — **formato preferencial**, máxima qualidade de dados |
| `.pdf` | DANFE em PDF — suporte legado para notas antigas |
| `.zip` | ZIP com XMLs e/ou PDFs. Se o ZIP contiver ambos, apenas os XMLs são usados |

> **Como obter o XML:** leia o QR Code do cupom físico com o app de NFC-e do seu estado (ex.: app da SEFAZ), acesse a nota e baixe o XML. Você pode salvar vários XMLs num único ZIP.

### 2️⃣ Extrair os Dados (Bruto)
Rode este comando para ler as notas e gerar o CSV inicial:

```Bash
python3 src/processadorCuponsFiscais.py
````

**O que faz:**
- Processa primeiro todos os ZIPs e XMLs avulsos, registrando a chave de acesso de cada nota
- Em seguida processa os PDFs avulsos, **pulando automaticamente** qualquer nota cuja chave já foi lida via XML
- Dentro de um ZIP com XMLs e PDFs, usa apenas os XMLs
- Gera o arquivo `resources/outputData/minha_inflacao.csv`

**Colunas geradas no CSV:**

| Coluna | Preenchida por | Descrição |
|---|---|---|
| `data` | XML e PDF | Data da compra (dd/mm/yyyy) |
| `loja` | XML | Nome fantasia ou razão social do emissor |
| `cnpj` | XML | CNPJ do emissor |
| `produto` | XML e PDF | Nome do produto |
| `qtd` | XML e PDF | Quantidade |
| `unidade` | XML e PDF | Unidade (PC, Kg, Un…) |
| `preco_unit` | XML e PDF | Preço unitário |
| `preco_total` | XML e PDF | Valor total do item |
| `codigo` | XML e PDF | Código interno do produto na loja |
| `ean` | XML | Código de barras EAN/GTIN |
| `ncm` | XML | Código NCM (classificação fiscal) |
| `chave_nfe` | XML | Chave de acesso NF-e de 44 dígitos |
| `arquivo_origem` | XML e PDF | Nome do arquivo processado |
| `categoria` | Dicionário | Categoria (após rodar o Passo 3) |

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
- **📈 Evolução de Preços** — histórico de preço unitário por produto
- **💰 Análise Pareto (ABC)** — quais produtos pesam mais no seu orçamento
- **📊 Índice de Inflação Pessoal** — índice de Laspeyres calculado com os seus produtos:
  - Escolha o mínimo de meses em que um produto deve aparecer para entrar na cesta
  - Passe o mouse sobre qualquer mês no gráfico para ver os 10 produtos que mais puxaram o índice para cima ou para baixo naquele mês
  - Veja a inflação acumulada, a variação mês a mês e a composição e pesos da cesta
- **📋 Dados Brutos** — tabela completa do CSV com campo de busca para filtrar por nome de produto

**Para parar o dashboard:** Pressione `Ctrl + C` no terminal

---

### 5️⃣ Gerar PDF a partir de XML (Opcional)

Precisa consultar uma nota de forma legível sem depender do portal da SEFAZ?

```Bash
# Converte todos os XMLs da pasta notas_fiscais de uma vez
python3 src/gerador_danfe.py

# Ou converte apenas um ZIP ou XML específico
python3 src/gerador_danfe.py resources/notas_fiscais/minhas_notas.zip
python3 src/gerador_danfe.py resources/notas_fiscais/consulta.xml
```

**O que faz:**
- Lê cada XML e gera um DANFE simplificado em PDF (formato A4)
- Inclui: cabeçalho com dados do emissor, tabela completa de itens (código, EAN, NCM, qtd, preços), totais, forma de pagamento, QR Code e chave de acesso
- Salva os PDFs em `resources/outputData/danfe/`

✅ Resultado: PDFs legíveis em `resources/outputData/danfe/`

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

Erro: "Pasta resources/notas_fiscais não encontrada"
- Causa: Você esqueceu de criar a pasta.
- Solução: Crie a pasta resources na raiz e dentro dela a pasta notas_fiscais.

---