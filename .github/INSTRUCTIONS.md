---
name: Estratégia de Instruções
version: "1.0.0"
---

# Estratégia de Instruções — ProcessadorCuponsFiscais

Este documento explica como gerenciamos e evoluímos as instruções deste projeto.

## 📋 Visão Geral

Instruções são arquivos de orientação que dizem ao agente de IA como se comportar ao trabalhar com esta base de código. Eles ajudam a garantir consistência, qualidade de código e melhores práticas.

| Escopo | Localização | Propósito | Público |
|---|---|---|---|
| **Pessoal** | `~/Library/Application Support/Code/User/prompts/` | Melhores práticas genéricas para todos os seus projetos | Você apenas |
| **Específico do Projeto** | `.github/instructions/` | Orientação customizada para este projeto | Você + Time |

---

## 🎯 Distinção Chave: Dois Tipos de Arquivos

### **Tipo 1: `*.instructions.md` (Arquivos de Ação)**

**Exemplo:** [`post-implementation-checklist.instructions.md`](./instructions/post-implementation-checklist.instructions.md)

```yaml
---
name: post-implementation-checklist-pcf
version: "1.0.0"
description: "Use quando: após implementação bem-sucedida de feature..."
applyTo: "src/**, tests/**"  # Isto é FUNDAMENTAL
---
```

**O que é:**
- ✅ Arquivo de instrução ativo que **agentes leem e executam**
- ✅ Possui frontmatter (metadados YAML)
- ✅ Acionado automaticamente baseado no padrão `applyTo` ou invocação do usuário
- ✅ Contém **passos executáveis, comandos, exemplos de código**

**Quem usa:**
- O **Agent** (GitHub Copilot) lê automaticamente
- Dispara sugestões e guia o comportamento

**Quando editar:**
- Comando mudou (`pytest tests/` → `pytest tests/ -v --tb=short`)
- Novos casos especiais surgiram (ex: "e se adicionar novas colunas CSV?")
- Estrutura do projeto mudou
- Novos módulos adicionados

**Onde aparece:**
- ✅ Aparece como `/post-implementation-checklist` em comandos de barra
- ✅ Agent sugere automaticamente em contextos relevantes

---

### **Tipo 2: `INSTRUCTIONS.md` (Documentação Meta)**

**Exemplo:** Este arquivo ([`INSTRUCTIONS.md`](.))

```markdown
---
name: Estratégia de Instruções
version: "1.0.0"
---

# Estratégia de Instruções — ProcessadorCuponsFiscais

Este documento explica como gerenciamos e evoluímos as instruções...
```

**O que é:**
- 📚 Documentação **sobre** como gerenciar instruções
- ❌ Sem frontmatter (markdown puro)
- ❌ NÃO lido automaticamente por agentes
- ✅ Contém **estratégia, roadmap, processos, princípios**

**Quem usa:**
- **Você e seu time** (apenas humanos)
- Novos membros do time se onboarding
- Você no futuro tentando lembrar do sistema

**Quando editar:**
- Você quer explicar a estratégia
- Novo arquivo de instrução criado (adicionar ao roadmap)
- Processo de manutenção mudou
- Princípios de design evoluíram

**Onde aparece:**
- ❌ NÃO em comandos de barra
- ✅ Aparece na documentação do projeto
- ✅ Linkado do README ou wiki do time

---

## 📊 Tabela de Referência Rápida

| Aspecto | `*.instructions.md` | `INSTRUCTIONS.md` |
|---|---|---|
| **Propósito** | Guiar comportamento do agent | Documentar estratégia |
| **Frontmatter?** | ✅ Sim (YAML) | ❌ Não |
| **Agent lê?** | ✅ Automaticamente | ❌ Não |
| **Usuário lê?** | ❌ Raramente | ✅ Frequentemente |
| **Comando de barra?** | ✅ `/nome` | ❌ Não |
| **Conteúdo exemplo** | Passos, comandos, exemplos | Roadmap, processos, princípios |
| **Editar quando** | Fluxo de trabalho muda | Mudanças de entendimento/estratégia |
| **Bump de versão** | SemVer (1.0.0 → 1.1.0) | Formato livre (notas de doc) |

---

## 🧠 Ajuda de Memória

**Pense assim:**

- **`*.instructions.md`** = Script que executa automaticamente (como `run_tests.sh`)
  - Agent executa
  - Contém comandos exatos
  - Quando fluxo muda, atualize

- **`INSTRUCTIONS.md`** = Manual que explica os scripts (como `SCRIPTS_README.md`)
  - Humanos leem
  - Contém filosofia e processo
  - Quando quer lembrar "por que estamos fazendo isso?", leia

---

## 🛠️ Prático: Qual Arquivo Editar?

### Cenário 1: "O comando de teste mudou"
```bash
# VELHO: python -m pytest tests/ -v
# NOVO: pytest tests/ -v --tb=short (mais rápido, melhor saída)
```
→ Edite: **`post-implementation-checklist.instructions.md`** (seção "Executar Testes Atuais")  
Por quê: Agent precisa saber exatamente o novo comando

---

### Cenário 2: "Queremos adicionar um 5º passo ao checklist"
```
1. Executar testes
2. Atualizar testes
3. Atualizar CHANGELOG
4. Atualizar docs
5. [NOVO] Deploy para staging ← Adicionar isto
```
→ Edite: **`post-implementation-checklist.instructions.md`** (adicione nova seção)  
Por quê: Agent vai sugerir 5 passos em vez de 4

---

### Cenário 3: "Quero lembrar POR QUE temos essas instruções"
```
"Por que temos tanto .instructions.md E INSTRUCTIONS.md?
 Qual é a filosofia aqui?"
```
→ Leia: **`INSTRUCTIONS.md`** (este arquivo)  
Por quê: Explica a estratégia e decisões de design

---

### Cenário 4: "Política de versionamento mudou"
```
VELHO: Versionamento semântico (1.0.0 → 1.1.0)
NOVO: Baseado em data (v2026-06-01)
```
→ Edite: **`INSTRUCTIONS.md`** (seção "Processo de Atualização" → "Bump de versão")  
Por quê: Documenta a nova política para você no futuro e para o time

---

### Cenário 5: "Estamos adicionando uma nova instrução para mudanças no dashboard"
```
Novo arquivo: .github/instructions/dashboard-modifications.instructions.md
```
→ Edite: **Ambos os arquivos**
- Crie novo `dashboard-modifications.instructions.md` (arquivo de ação)
- Adicione entrada em `INSTRUCTIONS.md` → "📁 Instruções Atuais" (documente)  
Por quê: Nova instrução é acionável (agents usam) + time precisa saber (documentado)

---

## 📁 Instruções Atuais

### 1. **post-implementation-checklist** ✅

**Escopos:**
- Pessoal: `~/Library/.../post-implementation-checklist.instructions.md`
- Projeto: `.github/instructions/post-implementation-checklist.instructions.md`

**Quando acionada:** Após implementar uma feature, corrigir um bug, ou completar mudanças de código

**O que faz:** Sugere um checklist de 4 passos
1. Executar testes
2. Atualizar suite de testes
3. Atualizar CHANGELOG
4. Atualizar documentação

**Detalhes específicos do projeto:**
- Comandos exatos de teste (`pytest tests/`)
- Mapeamentos módulo-para-teste (qual módulo → qual arquivo de teste)
- Documentação de colunas CSV
- Atualizações de abas do dashboard
- Casos especiais (novo parser, mudanças CSV, etc.)

**Versão:** 1.0.0

---

## 🔄 Como Manter as Instruções

### Quando Atualizar

- ✅ Novo framework de testes ou comandos
- ✅ Estrutura do projeto alterada (arquivos movidos, pastas renomeadas)
- ✅ Novos tipos de documentação necessários
- ✅ Novos módulos adicionados ao projeto
- ✅ Convenções mudaram

### Processo de Atualização

1. **Identifique a necessidade**
   - Durante implementação, note o que está desatualizado
   - Pergunte: "Meu futuro eu saberia como lidar com isto?"

2. **Edite o arquivo de instrução**
   - Mantenha exemplos atualizados
   - Adicione casos especiais se não estiverem cobertos

3. **Faça commit com mensagem clara**
   ```bash
   git add .github/instructions/*.md
   git commit -m "docs: atualizar checklist pós-implementação para suporte XLS"
   ```

4. **Bump de versão (SemVer)**
   - Patch (`1.0.1`): Erros de digitação, clarificações, mudanças menores de redação
   - Minor (`1.1.0`): Nova seção, novo caso especial
   - Major (`2.0.0`): Reestruturação completa

### Exemplo de Histórico de Commits

```
commit abc123 — docs: atualizar checklist pós-implementação para suporte XLS (v1.1.0)
commit def456 — docs: adicionar caso especial para mudanças dashboard (v1.0.1)
commit ghi789 — docs: criar instruções iniciais (v1.0.0)
```

---

## 🔗 Ligando Instruções ao Código

Instruções usam o padrão `applyTo` para determinar quando devem estar ativas.

**Exemplo:**
```yaml
applyTo: "src/**, tests/**"  # Aplica a todos os arquivos em src/ e tests/
```

**Padrões comuns:**
- `**` — todos os arquivos (use com cuidado, consome contexto)
- `src/**` — apenas arquivos de origem
- `src/*.py` — apenas arquivos Python na raiz de src
- `src/dashboard.py` — arquivo específico

---

## 🛠️ Estendendo Instruções

Para adicionar um novo arquivo de instrução:

1. **Crie o arquivo:** `.github/instructions/seu-nome.instructions.md`

2. **Adicione frontmatter:**
   ```yaml
   ---
   name: minha-instrucao
   version: "1.0.0"
   description: "Use quando: [cenário específico]. [O que orienta]."
   applyTo: "src/**"
   ---
   ```

3. **Escreva o corpo:** Orientação clara e acionável

4. **Faça commit e documente** (adicione entrada a este arquivo)

---

## 📋 Cola de Memória: Lembre-se Disto

**Perdido? Não sabe qual arquivo editar? Use isto:**

| Quero... | Edite isto | Por quê |
|---|---|---|
| Mudar comando de teste | `post-implementation-checklist.instructions.md` | Agent precisa saber exatamente do novo comando |
| Adicionar novo passo | `post-implementation-checklist.instructions.md` | Agent vai sugerir novo passo |
| Lembrar da estratégia | Leia `INSTRUCTIONS.md` | É o manual/docs |
| Documentar nova política | `INSTRUCTIONS.md` | É para explicar decisões |
| Criar nova instrução | Crie `.instructions.md` + atualize `INSTRUCTIONS.md` | Ambos ação + docs |
| Referência rápida | **Esta seção** | Busca rápida |

**Ainda confuso?**
- 🚀 **Ação necessária?** Edite `*.instructions.md` (frontmatter + YAML)
- 📚 **Entendimento necessário?** Leia/edite `INSTRUCTIONS.md` (sem frontmatter, markdown puro)

---

## 📚 Arquivos Relacionados

- [post-implementation-checklist.instructions.md](./instructions/post-implementation-checklist.instructions.md) — Checklist principal
- [CHANGELOG.md](../../CHANGELOG.md) — Histórico de versões do projeto
- [tests/TESTES.md](../../tests/TESTES.md) — Diretrizes de testes
- [readme.md](../../readme.md) — Visão geral do projeto

---

## 🧠 Princípios de Design

1. **DRY (Não Repita a Si Mesmo)**
   - Ligue para docs existentes em vez de duplicar
   - Referencie arquivos, não reescreva

2. **Divulgação Progressiva**
   - Informação básica em primeiro
   - Seções avançadas mais abaixo no arquivo
   - Casos especiais no final

3. **Acionável**
   - Exemplos de linha de comando (prontos para copiar-colar)
   - Checklists que usuários podem seguir
   - Links para material de referência

4. **Versionado**
   - Fácil rastrear quando as coisas mudaram
   - Mais fácil depurar "por que a instrução mudou?"

---

## 🚀 Melhorias Futuras

- [ ] Adicionar instrução para "Adicionar nova fonte de dados" (quando suporte Citizen XLS for adicionado)
- [ ] Adicionar instrução para "Modificações no dashboard"
- [ ] Criar `.github/hooks/` para verificações forçadas (ex: sem commits sem testes passando)
- [ ] Adicionar GitHub Actions para validar que as instruções são seguidas (testes automatizados em PR)

---

**Última atualização:** 2026-06-01  
**Mantido por:** @você
