---
name: Instructions Strategy
version: "1.0.0"
---

# Instructions Strategy — ProcessadorCuponsFiscais

This document explains how we manage and evolve instructions for this project.

## 📋 Overview

Instructions are guidance files that tell the AI agent how to behave when working on this codebase. They help ensure consistency, code quality, and best practices.

| Scope | Location | Purpose | Audience |
|---|---|---|---|
| **Personal** | `~/Library/Application Support/Code/User/prompts/` | Generic best practices for all your projects | You only |
| **Project-Specific** | `.github/instructions/` | Customized guidance for this project | You + Team |

## 📁 Current Instructions

### 1. **post-implementation-checklist** ✅

**Scopes:**
- Personal: `~/Library/.../post-implementation-checklist.instructions.md`
- Project: `.github/instructions/post-implementation-checklist.instructions.md`

**When triggered:** After implementing a feature, fixing a bug, or completing code changes

**What it does:** Suggests a 4-step checklist
1. Run tests
2. Update test suite
3. Update CHANGELOG
4. Update documentation

**Project-specific details:**
- Exact test commands (`pytest tests/`)
- Module-to-test mappings (which module → which test file)
- CSV column documentation
- Dashboard tab updates
- Special cases (new parser, CSV changes, etc.)

**Version:** 1.0.0

---

## 🔄 How to Maintain Instructions

### When to Update

- ✅ New testing framework or commands
- ✅ Changed project structure (moved files, renamed folders)
- ✅ New types of documentation needed
- ✅ New modules added to project
- ✅ Conventions changed

### Update Process

1. **Identify the need**
   - During implementation, notice what's outdated
   - Ask: "Would future me know how to handle this?"

2. **Edit the instruction file**
   - Keep examples up-to-date
   - Add special cases if they're not covered

3. **Commit with clear message**
   ```bash
   git add .github/instructions/*.md
   git commit -m "docs: update post-implementation checklist for XLS support"
   ```

4. **Bump version (SemVer)**
   - Patch (`1.0.1`): Typos, clarifications, minor wording
   - Minor (`1.1.0`): New section, new special case
   - Major (`2.0.0`): Complete restructure

### Example Commit History

```
commit abc123 — docs: update post-implementation checklist for XLS support (v1.1.0)
commit def456 — docs: add special case for dashboard changes (v1.0.1)
commit ghi789 — docs: create initial instructions (v1.0.0)
```

---

## 🔗 Linking Instructions to Code

Instructions use the `applyTo` pattern to determine when they should be active.

**Example:**
```yaml
applyTo: "src/**, tests/**"  # Applies to all src/ and tests/ files
```

**Common patterns:**
- `**` — all files (use sparingly, burns context)
- `src/**` — only source files
- `src/*.py` — only Python files in src root
- `src/dashboard.py` — specific file

---

## 🛠️ Extending Instructions

To add a new instruction file:

1. **Create the file:** `.github/instructions/your-name.instructions.md`

2. **Add frontmatter:**
   ```yaml
   ---
   name: my-instruction
   version: "1.0.0"
   description: "Use when: [specific scenario]. [What it guides]."
   applyTo: "src/**"
   ---
   ```

3. **Write body:** Clear, actionable guidance

4. **Commit and document** (add entry to this file)

---

## 📚 Related Files

- [post-implementation-checklist.instructions.md](./post-implementation-checklist.instructions.md) — Main checklist
- [CHANGELOG.md](../../CHANGELOG.md) — Project version history
- [tests/TESTES.md](../../tests/TESTES.md) — Testing guidelines
- [readme.md](../../readme.md) — Project overview

---

## 🧠 Design Principles

1. **DRY (Don't Repeat Yourself)**
   - Link to existing docs instead of duplicating
   - Reference files, don't rewrite them

2. **Progressive Disclosure**
   - Basic info up front
   - Advanced sections lower in the file
   - Special cases at the end

3. **Actionable**
   - Command-line examples (copy-paste ready)
   - Checklists users can follow
   - Links to reference material

4. **Versioned**
   - Easy to track when things changed
   - Easier to debug "why did the instruction change?"

---

## 🚀 Future Enhancements

- [ ] Add instruction for "Adding a new data source" (when Citizen XLS support is added)
- [ ] Add instruction for "Dashboard modifications"
- [ ] Create `.github/hooks/` for enforced checks (e.g., no commits without tests passing)
- [ ] Add GitHub Actions to validate instructions are followed (automated test runs on PR)

---

**Last updated:** 2026-06-01
**Maintained by:** @you
