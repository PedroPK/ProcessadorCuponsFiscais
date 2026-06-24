# ⚡ Quick Start — Monitor de Inflação Pessoal

## 1. Pré-requisitos

- Python 3.9+
- Terminal na pasta raiz do projeto

---

## 2. Instalação (apenas na 1ª vez)

```bash
# Criar e ativar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate          # Mac/Linux
# .\.venv\Scripts\activate         # Windows

# Instalar dependências
pip install pdfplumber pandas openpyxl streamlit plotly thefuzz python-Levenshtein reportlab qrcode
```

---

## 3. Uso diário

### a) Coloque as notas fiscais
Copie seus arquivos `.xml`, `.pdf` ou `.zip` para:
```
resources/notas_fiscais/
```
> Prefira XML — dados mais completos (EAN, NCM, CNPJ, data exata).

### b) Abra o dashboard
```bash
streamlit run src/dashboard.py
```
O navegador abre automaticamente. Use o botão **"Processar e Atualizar"** na barra lateral para extrair as notas e recarregar os dados.
Para encerrar depois, use o botão **"Encerrar serviço e fechar aba"** na própria barra lateral.

---

## 4. Comandos opcionais

| Comando | Para que serve |
|---|---|
| `python3 src/processadorCuponsFiscais.py` | Extrai notas e gera o CSV manualmente |
| `python3 src/dicionario.py` | Atualiza o dicionário de normalização de nomes |
| `python3 src/gerador_danfe.py` | Gera PDFs legíveis (DANFE) a partir dos XMLs |
| `python -m pytest tests/ -v` | Roda a suíte de testes (95 testes) |

---

## 5. Estrutura de saída

```
resources/outputData/
├── minha_inflacao.csv          # Dados extraídos de todas as notas
├── dicionario_produtos.numbers # Dicionário de normalização de nomes
└── danfe/                      # PDFs gerados a partir de XMLs
```

---

> Para detalhes completos, consulte o [readme.md](readme.md).
