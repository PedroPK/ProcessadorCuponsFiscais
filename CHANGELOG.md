# Changelog

Todas as mudanças relevantes do projeto são documentadas aqui.  
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [Não lançado]

---

## [0.6.0] — 2026-04-23

### Adicionado
- `tests/` — suíte de testes automatizados com **pytest** (55 testes, 100% passando)
  - `tests/conftest.py` — configuração do `sys.path` e fixtures de XML sintético reutilizáveis
  - `tests/test_extrator_xml.py` — 29 testes para `extratorXml.py`: `_float`, `_parse_data`, `extrair_chave_do_xml` (str, bytes, malformado, sem tag) e `extrair_itens_do_xml` (campos, filtro de valor zero, EAN "SEM GTIN", entrada bytes)
  - `tests/test_processador.py` — 17 testes para `processadorCuponsFiscais.py`: `_converter_valor`, `_extrair_chave_pdf`, deduplicação XML duplo, prioridade XML sobre PDF em ZIP, XMLs duplicados dentro do ZIP
  - `tests/test_dicionario.py` — 9 testes para `dicionario.py`: `carregar_dados_existentes` (arquivo inexistente retorna DataFrame com colunas corretas) e `sugerir_padrao` (match alto, sem match, lista vazia, entradas None, ordem de palavras invertida)
- `src/dashboard.py` — campo de busca com filtragem em tempo real na aba **📋 Dados Brutos**
  - Campo de texto acima da tabela filtra as linhas exibidas pelo nome do produto (sem distinção de maiúsculas/minúsculas)
  - Com o campo vazio, a tabela exibe todos os registros normalmente
- `src/dashboard.py` — nova aba **📊 Índice de Inflação Pessoal**
  - Monta a cesta de produtos automaticamente: slider para definir o mínimo de meses em que o produto deve ter sido comprado
  - Calcula o preço médio ponderado por quantidade ($\bar{p} = \sum p_i q_i / \sum q_i$) de cada produto por mês
  - Gera índice de Laspeyres (base 100 = primeiro mês dos dados), ponderado pela participação no gasto do mês base
  - KPIs: índice atual, inflação acumulada e variação no último mês
  - Gráfico de linha do índice acumulado com **tooltip interativo**: ao passar o mouse sobre um mês, exibe os 10 produtos que mais influenciaram a variação daquele mês (em pontos percentuais, com ▲/▼)
  - Gráfico de barras da variação mensal (verde/vermelho)
  - Tabelas expansíveis: composição e pesos da cesta; preços médios mensais por produto

### Alterado
- Coluna EAN ampliada de 10% para 13% da largura da tabela do DANFE (elimina quebra de linha nos 13 dígitos)
- Coluna NCM ampliada de 7% para 9% (elimina quebra de linha nos 8 dígitos)
- Tabela de itens agora ocupa 100% da largura útil (antes 88%)

---

## [0.5.0] — 2026-03-09

### Adicionado
- `src/gerador_danfe.py` — converte XML de NF-e em PDF legível (DANFE simplificado)
  - Cabeçalho com nome fantasia, endereço, CNPJ/IE, número, série e data da nota
  - Tabela de itens com código, EAN, NCM, quantidade, unidade, valor unitário e total; linhas alternadas para legibilidade
  - Bloco de totais (valor dos produtos, descontos, ICMS, tributos aprox., **valor total em destaque**)
  - Bloco de forma de pagamento com troco
  - Rodapé com QR Code, chave de acesso formatada em grupos de 4 dígitos e dados do consumidor
  - Suporta arquivo `.xml` avulso, `.zip` com múltiplos XMLs ou varredura automática de `resources/notas_fiscais/`
  - PDFs salvos em `resources/outputData/danfe/`
- Dependências `reportlab` e `qrcode` adicionadas ao projeto

### Corrigido
- Bug na tabela de itens do DANFE: primeira linha de dados era pintada com a cor do cabeçalho

### Alterado
- `readme.md` atualizado com novo passo 5 (geração de DANFE), estrutura de pastas revisada e dependências atualizadas

---

## [0.4.0] — 2026-03-09

### Adicionado
- Deduplicação automática de notas fiscais usando a **chave de acesso NF-e (44 dígitos)**
  - Notas já processadas via XML são ignoradas quando o mesmo DANFE PDF é encontrado
  - XMLs duplicados dentro de um mesmo ZIP são detectados e pulados (`[SKIP XML]`)
  - Dentro de um ZIP com XMLs e PDFs, os PDFs são ignorados automaticamente (são o DANFE dos mesmos XMLs)
- `extrair_chave_do_xml()` em `src/extratorXml.py` — extrai apenas a chave sem processar os itens
- `_extrair_chave_pdf()` em `src/processadorCuponsFiscais.py` — localiza a chave de 44 dígitos no texto do DANFE PDF
- Campo `chave_nfe` adicionado ao CSV de saída e à lista de colunas exportadas
- `varrer_diretorio()` agora processa ZIPs e XMLs antes dos PDFs (garante prioridade do XML)

---

## [0.3.0] — 2026-03-09

### Adicionado
- `src/extratorXml.py` — parser de NF-e XML usando `xml.etree.ElementTree` (sem regex)
  - Extrai: data/hora ISO 8601, nome e CNPJ do emissor, EAN, NCM, quantidade, unidade, preços
  - Retorna campo `chave_nfe` (44 dígitos) em cada item
- Suporte a arquivos `.xml` avulsos e XMLs dentro de ZIPs em `ProcessadorDeCupons`
  - `processar_arquivo_xml()` para arquivos soltos
  - `processar_zip()` atualizado para detectar e processar XMLs além de PDFs
- Novos campos no CSV de saída: `loja`, `cnpj`, `ean`, `ncm`, `chave_nfe`
- Campos identificadores (`codigo`, `ean`, `ncm`, `cnpj`) exportados como texto, sem notação científica

### Alterado
- `varrer_diretorio()` estendido para reconhecer extensão `.xml`
- `exportar_csv()` atualizado com nova lista de colunas e conversão de tipos

---

## [0.2.0] — 2026-03-09

### Alterado
- Pasta `resources/cfs/` renomeada para `resources/notas_fiscais/` (evita confusão com "configurações")
- Todas as referências atualizadas: `processadorCuponsFiscais.py`, `extratorTexto.py` e `readme.md`

---

## [0.1.1] — anterior

### Adicionado
- `readme.md` com instruções completas de instalação, fluxo de trabalho e troubleshooting

---

## [0.1.0] — anterior

### Adicionado
- `src/processadorCuponsFiscais.py` — extração de dados de DANFE PDFs via `pdfplumber` com regex
  - Suporte a PDFs avulsos e ZIPs de PDFs
  - Aplicação de dicionário de normalização antes da exportação
  - Exportação para CSV com separador `;` e decimal `,`
- `src/dicionario.py` — geração e atualização de dicionário de produtos com *Fuzzy Matching* (`thefuzz`)
- `src/dashboard.py` — painel interativo em Streamlit com evolução de preços e Curva ABC (Pareto)
- `src/extratorTexto.py` — script diagnóstico para exploração inicial da estrutura dos PDFs
