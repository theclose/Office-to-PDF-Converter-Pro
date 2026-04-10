---
name: safe-refactor
description: |
  Safety checklist for refactoring code in Office to PDF Converter.
  Prevents the class of bugs where method signatures change but callers
  are not updated (traps #21-23). Covers method renames, parameter changes,
  constructor modifications, and cross-layer API contracts.
  Use this skill when renaming methods, changing function signatures,
  or restructuring modules.
---

# Safe Refactor Skill

## When to Use
- Renaming any method or function
- Adding/removing/reordering parameters
- Changing constructor signatures
- Moving functions between modules
- Extracting methods into mixins or base classes

## The Problem This Solves
Traps #21-23 show a recurring pattern:
1. Core method signature changes (e.g., `preview()` gains required `rules` param)
2. Tests are updated (they pass ✅)
3. UI callers are NOT updated (they crash at runtime ❌)
4. pytest can't catch this because UI is not tested end-to-end

## Pre-Refactor Checklist

### 1. Find ALL Callers Before Changing
```bash
# Method rename: find every call site
grep -rn "old_method_name(" converters/ core/ ui/ utils/ tests/ --include="*.py"

# Constructor change: find every instantiation  
grep -rn "ClassName(" converters/ core/ ui/ utils/ tests/ --include="*.py"

# Import change: find every import
grep -rn "from.*import.*FunctionName" converters/ core/ ui/ utils/ tests/ --include="*.py"
```

### 2. Document the Change Matrix
Before making changes, list:
```
Method: preview(files) → preview(files, rules)
Callers:
  - core/file_tools.py:642  → execute() calls self.preview()
  - ui/file_tools_ui_v2.py:375 → _preview() calls engine.preview()
  - tests/test_file_tools.py:XX → test calls engine.preview()
Status: [ ] core [ ] ui [ ] tests
```

### 3. Make Changes in Order
1. **Core module** — change the signature
2. **Tests** — update to match new signature, verify they pass
3. **UI callers** — update ALL UI files that call this method
4. **Run full suite** — `python -m pytest tests/ -v --tb=short`

## Common Refactor Patterns

### Pattern A: Method Rename
```python
# OLD: engine.undo()
# NEW: engine.undo_last_transaction()

# MUST grep: grep -rn "\.undo(" ui/ tests/
# MUST update ALL callers, not just tests
```

### Pattern B: New Required Parameter
```python
# OLD: def preview(self, files)
# NEW: def preview(self, files, rules)

# MUST grep: grep -rn "\.preview(" ui/ tests/
# UI callers will crash with TypeError if not updated
```

### Pattern C: Constructor Kwargs Changed
```python
# OLD: SequenceRule(position="prefix")
# NEW: SequenceRule(at_start=True)

# MUST grep: grep -rn "SequenceRule(" ui/ tests/
# Wrong kwarg = TypeError at runtime
```

### Pattern D: Module Moved
```python
# OLD: from converters.parallel_converter import ...
# NEW: from utils.parallel_converter import ...

# MUST grep: grep -rn "parallel_converter" . --include="*.py"
```

## Post-Refactor Verification

### Automated
```bash
# 1. All tests pass
python -m pytest tests/ -v --tb=short

# 2. Verify docs
python scripts/verify_claude_md.py

# 3. Grep for OLD names (should find 0 results)
grep -rn "old_method_name" converters/ core/ ui/ utils/ --include="*.py"
```

### Manual (if UI affected)
```bash
# Run app and test the refactored feature
python run_pro.py
```
- [ ] Feature works end-to-end in UI
- [ ] No AttributeError or TypeError in console

## Anti-Patterns
1. ❌ Rename method in core, update tests, forget UI
2. ❌ Add required param, rely on default value that doesn't exist
3. ❌ Change kwarg name without checking all callers
4. ❌ Move file without updating all imports
5. ❌ Trust "tests pass" as proof that refactor is complete
6. ❌ Skip grepping because "I know all the callers"

## Reference
- `docs/known-traps.md` — Traps #21, #22, #23 document real crashes from this pattern
