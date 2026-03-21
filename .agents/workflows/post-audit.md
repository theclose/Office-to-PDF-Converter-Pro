---
description: Post-audit workflow — run integration + stress tests after static audit
---

# Post-Audit Integration + Stress Test Workflow

Run this workflow AFTER completing a static code audit to catch
library-internal, framework-lifecycle, and OS-specific bugs.

// turbo-all

## Steps

1. Run existing unit tests to ensure baseline stability:
```bash
python -m pytest tests/test_split_features.py tests/test_compression_features.py -q --tb=short
```

2. Run library integration tests (PyMuPDF edge cases, Trap #16):
```bash
python -m pytest tests/test_integration_library.py -v --tb=short
```

3. Run UI lifecycle tests (dialog destroy, CTkEntry traces, Trap #17):
```bash
python -m pytest tests/test_integration_ui_lifecycle.py -v --tb=short
```

4. Run converter integration tests (real Office COM conversion):
```bash
python -m pytest tests/test_integration_converter.py -v --tb=short
```

5. Run stress tests (file lock, concurrency, temp cleanup, Trap #18):
```bash
python -m pytest tests/test_stress_file_handling.py -v --tb=short
```

6. Run CLAUDE.md verification:
```bash
python scripts/verify_claude_md.py --fix
```

7. Visual verification — launch app and do these manual checks:
   - Open PDF Tools → switch operations 3-4 times → close dialog
   - Add 3+ files → try converting
   - Toggle theme dark↔light 2-3 times
   - Check log for any errors

8. Document any new findings in `docs/known-traps.md`
