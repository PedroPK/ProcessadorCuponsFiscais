# 🛒 Monitor de Inflação Pessoal

Uma ferramenta em Python para extrair dados de Cupons Fiscais (NFC-e) em PDF, criar um banco de dados histórico de compras e visualizar a evolução dos preços através de um Dashboard interativo.

## 📋 Sobre o Projeto

Este software resolve o problema de rastrear a "inflação real" do consumidor. Diferente dos índices oficiais (IPCA), que usam uma cesta de produtos genérica, este projeto calcula a inflação baseada **exatamente no que você compra**.

**Funcionalidades:**
* **Extração Inteligente:** Lê PDFs (soltos ou em ZIP) de Notas Fiscais Eletrônicas (focado no layout NFC-e/SAT).
* **Normalização de Nomes:** Usa algoritmos de similaridade (*Fuzzy Matching*) para identificar que "LEITE PARMALAT" e "LEITE PARMALAT CX" são o mesmo produto.
* **Banco de Dados:** Consolida tudo em um arquivo CSV padronizado (compatível com Excel/Numbers).
* **Dashboard Interativo:** Painel visual para analisar variação de preços, Curva ABC (Pareto) e gastos totais.

---

## 📂 Estrutura de Pastas

O projeto deve seguir esta organização para funcionar corretamente:

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