# Documentação dos Testes Automatizados

Suíte de testes com **pytest** para os módulos principais do projeto.  
Execute a qualquer momento com:

```bash
python -m pytest tests/ -v
```

> **55 testes · 0 falhas** *(atualizado em 2026-04-23)*

---

## Estrutura

| Arquivo | Módulo testado | Testes |
|---|---|---|
| `test_extrator_xml.py` | `src/extratorXml.py` | 29 |
| `test_processador.py` | `src/processadorCuponsFiscais.py` | 17 |
| `test_dicionario.py` | `src/dicionario.py` | 9 |

**`conftest.py`** — compartilhado entre todos os arquivos. Configura o `sys.path` e define as fixtures de XML:

| Fixture | Descrição |
|---|---|
| `XML_VALIDO` | NF-e sintética com 3 itens (2 com valor, 1 zerado — sacola de cortesia) |
| `XML_SEM_CHAVE` | XML válido mas sem o atributo `Id` em `<infNFe>` |
| `XML_MALFORMADO` | String que não é XML |
| `NFE_CHAVE` | Chave de 44 dígitos correspondente ao `XML_VALIDO` |

---

## `test_extrator_xml.py`

### `TestFloat` — conversão de string para float

| Cenário | Entrada | Resultado esperado |
|---|---|---|
| Valor decimal válido | `"4.89"` | `4.89` |
| Valor zero | `"0.00"` | `0.0` |
| `None` | `None` | `0.0` |
| String vazia | `""` | `0.0` |
| String não numérica | `"abc"` | `0.0` |

---

### `TestParseData` — conversão de timestamp ISO 8601 para dd/mm/yyyy

| Cenário | Entrada | Resultado esperado |
|---|---|---|
| Com fuso horário | `"2026-03-01T13:01:36-03:00"` | `"01/03/2026"` |
| Sem fuso horário | `"2026-12-25T00:00:00"` | `"25/12/2026"` |
| `None` | `None` | `"Data Desconhecida"` |
| String vazia | `""` | `"Data Desconhecida"` |
| Hora inválida (fallback) | `"2026-07-04T99:99:99"` | `"2026-07-04"` *(primeiros 10 chars)* |

---

### `TestExtrairChaveDoXml` — extração da chave NF-e de 44 dígitos

| Cenário | Entrada | Resultado esperado |
|---|---|---|
| XML válido (string) | `XML_VALIDO` | Chave de 44 dígitos |
| XML válido (bytes) | `XML_VALIDO.encode("utf-8")` | Mesma chave de 44 dígitos |
| XML sem atributo `Id` | `XML_SEM_CHAVE` | `None` |
| XML malformado | `XML_MALFORMADO` | `None` |

---

### `TestExtrairItensDoXml` — extração completa dos itens de uma NF-e

> Usa `XML_VALIDO` (3 itens declarados: Leite, Pão Francês, Sacola de Cortesia)

| Cenário | O que verifica |
|---|---|
| Quantidade de itens retornados | 2 itens (sacola com valor zero é filtrada) |
| Campos presentes em cada item | `data`, `produto`, `qtd`, `unidade`, `preco_unit`, `preco_total`, `codigo`, `ean`, `ncm`, `loja`, `cnpj`, `chave_nfe`, `arquivo_origem` |
| Nome da loja | Prefere `xFant` (nome fantasia) sobre `xNome` (razão social) |
| CNPJ do emissor | Valor correto extraído do `<emit>` |
| Data formatada | ISO 8601 convertido para `dd/mm/yyyy` |
| Chave NF-e no item | Igual a `NFE_CHAVE` |
| Preço unitário | `4.89` (Leite Integral) |
| Preço total | `9.78` (Leite Integral × 2 unidades) |
| EAN válido | `"7891234560013"` (Leite) |
| EAN "SEM GTIN" vira string vazia | `""` (Pão Francês) |
| Código NCM | `"04011000"` (Leite) |
| `arquivo_origem` | Nome do arquivo passado como parâmetro |
| Item com valor zero filtrado | "SACOLA CORTESIA" não aparece no resultado |
| XML malformado | Retorna lista vazia sem lançar exceção |
| Entrada em bytes | Produz os mesmos 2 itens que a versão string |

---

## `test_processador.py`

### `TestConverterValor` — parse de valores monetários no padrão brasileiro

| Cenário | Entrada | Resultado esperado |
|---|---|---|
| Formato BR com separador de milhar | `"1.234,56"` | `1234.56` |
| Formato BR sem milhar | `"9,99"` | `9.99` |
| Ponto como separador de milhar | `"4.89"` | `489.0` *(ponto = milhar no padrão BR)* |
| String vazia | `""` | `0.0` |
| `None` | `None` | `0.0` |
| String não numérica | `"abc"` | `0.0` |

---

### `TestExtrairChavePdf` — localização da chave NF-e no texto de um DANFE PDF

| Cenário | Entrada | Resultado esperado |
|---|---|---|
| Chave em texto contínuo | `"Chave de acesso: <44 dígitos> ..."` | Chave de 44 dígitos |
| Chave em blocos de 4 (formato DANFE) | `"2626 0306 0572 ..."` | Chave sem espaços |
| Texto sem chave | `"texto sem chave"` | `None` |
| Sequência com menos de 44 dígitos | `"123456789012345678901234567890"` | `None` |

---

### `TestDeduplicacao` — garantia de que a mesma nota nunca é contabilizada duas vezes

| Cenário | O que verifica |
|---|---|
| Mesmo XML processado duas vezes | Resultado final tem 2 itens, não 4 |
| Chave registrada após 1º processamento | `NFE_CHAVE` está no conjunto `_chaves_processadas` |

---

### `TestProcessarArquivoXml` — leitura de arquivo XML do disco

| Cenário | O que verifica |
|---|---|
| Campos extraídos corretamente | `loja`, `cnpj`, `ean`, `preco_unit` do Leite Integral |
| Arquivo inexistente | Não lança exceção; `dados_consolidados` permanece vazio |

---

### `TestProcessarZip` — processamento de arquivos ZIP

| Cenário | O que verifica |
|---|---|
| ZIP contendo apenas XMLs | Itens extraídos corretamente |
| ZIP com XML **e** PDF | Apenas o XML é processado (PDF é ignorado por ser o DANFE do mesmo XML) |
| ZIP com dois XMLs de mesma chave | Segundo XML é pulado; resultado final tem 2 itens, não 4 |

---

## `test_dicionario.py`

### `TestCarregarDadosExistentes` — carregamento do dicionário de produtos

| Cenário | O que verifica |
|---|---|
| Arquivo `.xlsx` inexistente | Retorna `DataFrame` vazio (não lança exceção) |
| Colunas do DataFrame vazio | Sempre `["nome_original", "nome_padrao", "categoria"]` |
| Arquivo `.xlsx` existente | Carrega corretamente e preserva os dados |

---

### `TestSugerirPadrao` — sugestão de nome padronizado via Fuzzy Matching

| Cenário | Entrada | Resultado esperado |
|---|---|---|
| Similaridade > 80% | `"LEITE INTEGRAL 1L"` vs lista com `"Leite Integral"` | `"Leite Integral"` |
| Sem match suficiente (< 80%) | `"DETERGENTE NEUTRO 500ML"` vs lista sem similar | `"Detergente Neutro 500Ml"` *(Title Case)* |
| Lista de nomes conhecidos vazia | qualquer entrada | Nome em Title Case |
| Lista com entradas `None` | `[None, "Leite Integral", None]` | Ignora `None`s, retorna match correto |
| Match exato | `"Arroz Branco"` vs `["Arroz Branco"]` | `"Arroz Branco"` |
| Palavras em ordem invertida | `"LEITE INTEGRAL"` vs `["Integral Leite"]` | `"Integral Leite"` *(token_sort_ratio é insensível à ordem)* |
