---
description: Update CLAUDE.md when codebase changes significantly
---
// turbo-all

# Update CLAUDE.md Workflow

Regenerates `CLAUDE.md` to keep it in sync with codebase changes.

## When to Run
- After adding/removing/renaming files or modules
- After changing architecture patterns
- After adding new dependencies or optimizations
- Automatically triggered by `/auto-save` workflow

## Steps

1. Read current CLAUDE.md:
```
View file: CLAUDE.md
```

2. Scan project structure:
```
List directories: converters/, core/, ui/, utils/, tests/
```

3. Check version + dependencies:
```
View file: __init__.py
View file: requirements.txt
```

4. Run test baseline:
```bash
python -m pytest tests/test_com_lifecycle.py tests/test_converter_integration_v2.py tests/test_engine_threading.py tests/test_core.py tests/test_bug_fixes.py --tb=no --no-header -q
```

5. Compare and update CLAUDE.md with any changes:
   - Architecture tree (new/deleted files)
   - Test baseline count
   - Version number
   - Optimizations table
   - Dependencies
   - Critical Rules

6. Verify updated file:
```
View file: CLAUDE.md
```
