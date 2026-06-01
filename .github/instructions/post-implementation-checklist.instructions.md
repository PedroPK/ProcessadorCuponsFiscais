---
name: post-implementation-checklist-pcf
version: "1.0.0"
description: "Use when: after successful feature implementation, bug fixes, or code changes in ProcessadorCuponsFiscais. Guides running tests, updating test suite, updating changelog, and documentation."
applyTo: "src/**, tests/**"
---

# Post-Implementation Checklist — ProcessadorCuponsFiscais

When implementation of a feature or bug fix is complete, execute this checklist to ensure code quality and project documentation is maintained.

## 🎯 The Checklist

After successful implementation, recommend executing these activities **in order**:

### 1️⃣ Run Current Tests
Ensure all existing tests pass and no regressions were introduced.

**Command:**
```bash
python -m pytest tests/ -v
```

**What to validate:**
- All 80+ tests pass
- No new warnings
- If tests fail, fix issues before proceeding to next steps

**Skip if:** Only updating documentation or non-code assets

---

### 2️⃣ Update Test Suite
Add or update tests to cover the new functionality or bug fix.

**When needed:**
- ✅ New feature added (new parser, new dashboard tab, new utility)
- ✅ Bug fixed (add test that would have caught the bug)
- ✅ Logic changed in core modules (extratorXml, processadorCuponsFiscais, dicionario)

**Where to add tests:**
| Module | Test File |
|---|---|
| `extratorXml.py` | `tests/test_extrator_xml.py` |
| `processadorCuponsFiscais.py` | `tests/test_processador.py` |
| `dicionario.py` | `tests/test_dicionario.py` |
| `utils.py` | `tests/test_utils.py` |

**Tips:**
- Use fixtures from `tests/conftest.py`
- Mock external dependencies (file I/O, API calls)
- Aim for >80% code coverage
- Run tests again: `python -m pytest tests/ -v`

**Skip if:** Only documentation or dashboard UI tweaks

---

### 3️⃣ Update Changelog
Document the change in `CHANGELOG.md` using semantic versioning convention.

**Format:**
```markdown
## [X.Y.Z] - YYYY-MM-DD
### Added
- Feature description

### Fixed
- Bug description

### Changed
- Behavior change description
```

**Example:**
```markdown
## [1.2.0] - 2026-06-01
### Added
- Support for extracting product data from Citizen app XLS files
- Fuzzy matching normalization for Citizen products

### Fixed
- Deduplication now handles products from multiple sources correctly
```

**Sections to use:**
- `Added` — new features
- `Fixed` — bug fixes
- `Changed` — behavior changes
- `Deprecated` — features to be removed
- `Removed` — features removed
- `Security` — security fixes

**Reference:** [Keep a Changelog](https://keepachangelog.com/)

---

### 4️⃣ Update Documentation

Update relevant documentation files to reflect the changes.

**What to update:**

| File | When |
|---|---|
| `readme.md` | New features, workflow changes, new columns in CSV |
| `tests/TESTES.md` | New test patterns, testing guidelines |
| Docstrings in code | All new/modified functions and classes |
| `requirements.txt` | New dependencies added |

**Documentation checklist:**
- [ ] Docstrings follow format: description, params, returns, raises
- [ ] README reflects new features or changed workflows
- [ ] CSV column changes documented in "Colunas geradas no CSV" table
- [ ] New modules or classes have usage examples
- [ ] Known issues updated in "⚠️ Problemas Conhecidos" section

**Example docstring:**
```python
def normalize_product_name(name: str, threshold: float = 0.6) -> str:
    """
    Normalize product name using Fuzzy Matching against dictionary.
    
    Args:
        name: Original product name from receipt
        threshold: Similarity threshold (0-1) for fuzzy matching
        
    Returns:
        Normalized product name or original if no match found
        
    Raises:
        ValueError: If name is empty
    """
```

---

## 🔄 Special Cases

### Adding a New Parser (e.g., new file format)
1. Run tests ✅
2. Add tests for new parser (e.g., `test_extrator_xls.py`)
3. Update CHANGELOG under "Added"
4. Update README:
   - Add to "Funcionalidades"
   - Add row to "Estrutura de Pastas Esperada" if new folder needed
   - Add row to "Como Executar" step 1 (accepted formats)

### Modifying CSV Output Structure
1. Run tests ✅
2. Add tests validating new columns
3. Update CHANGELOG
4. Update README table "Colunas geradas no CSV"
5. Update docstring in `processadorCuponsFiscais.py`

### Dashboard Changes
1. Run tests (if logic affected) ✅
2. Update test for dashboard if UI logic changed
3. Update CHANGELOG
4. Update README tab in "📸 Prévia do Dashboard" with new screenshots

### Bug Fix for Production Issue
1. Run tests ✅
2. Add regression test (so bug doesn't happen again)
3. Update CHANGELOG under "Fixed" with issue reference
4. Update documentation if behavior changed

---

## 💡 Tips & Best Practices

- **Never skip tests** — they catch regressions
- **Keep changelog human-readable** — avoid technical jargon
- **Docstrings are documentation** — keep them updated
- **Test first thinking** — consider edge cases before implementation
- **One concern per commit** — makes history easier to follow
- **Validate end-to-end** — if processing XML → CSV → Dashboard, test all 3 steps

---

## ❓ Need Help?

Refer to:
- `tests/TESTES.md` — detailed testing guidelines
- `tests/conftest.py` — available test fixtures
- `CHANGELOG.md` — previous entries for formatting reference
- `readme.md` — project overview and architecture
