---
name: code-audit
description: |
  Systematic code audit workflow for Office to PDF Converter Pro.
  Covers full-app audit, per-module audit, test coverage analysis,
  and scoring methodology. Use this skill when performing quality audits,
  security reviews, or pre-release verification of the application.
---

# Code Audit Skill

## When to Use
- Full-app quality audit before EXE release
- Per-module audit after significant changes
- Security review for PDF password/permissions features
- Pre-release verification checklist

## Audit Methodology (Top-Down)

### Phase 1: System Overview (5 min)
```bash
# 1. Read CLAUDE.md for architecture overview
# 2. Run verify script
python scripts/verify_claude_md.py
# 3. Run full test suite
python -m pytest tests/ -v --tb=short
# 4. Check for lint issues
ruff check .
```

### Phase 2: Per-Module Deep Dive
Audit each layer in dependency order:

#### Layer 4 → utils/ (lowest risk, audit first)
- [ ] Config singleton thread-safety
- [ ] COMPool lifecycle (health-check, recycle)
- [ ] Logging setup (no print(), proper levels)
- [ ] Error handling (no bare excepts)

#### Layer 1 → converters/ (highest risk)
- [ ] COM STA compliance (CoInitialize per thread)
- [ ] Quality parameter actually used (not ignored)
- [ ] Fallback chains complete and ordered
- [ ] Pre-flight validation (file exists, size, lock)
- [ ] Resource cleanup in finally blocks
- [ ] PDF output validation after conversion

#### Layer 2 → core/ (medium risk)
- [ ] Engine stop/force-stop contract
- [ ] Post-processing order correct
- [ ] Auto-compress integration
- [ ] get_fitz() used (not stale boolean)

#### Layer 3 → ui/ (visual verification required)
- [ ] pack_propagate(False) enforced
- [ ] Thread-safety (self.after for cross-thread)
- [ ] All callbacks wrapped in try/except
- [ ] after() callbacks cleaned up on destroy/language change
- [ ] Visual verification (run app, check rendering)
- [ ] MUST run app and test: open → change language → close

### Phase 3: Cross-Cutting Concerns
- [ ] Exception handling: no bare excepts, proper logging
- [ ] Resource cleanup: try/finally for COM, files, DB
- [ ] Thread safety: no cross-thread COM or widget access
- [ ] File I/O: encoding specified (utf-8), error handling
- [ ] Security: password handling, no hardcoded secrets

## Scoring Methodology

### Per-Module Score (0-10)
| Score | Meaning |
|-------|---------|
| 0-3 | Critical bugs, crashes, data loss risk |
| 4-5 | Functional but fragile, missing validation |
| 6-7 | Solid with minor issues |
| 8-9 | Production-ready, well-tested |
| 10 | Exceptional, comprehensive edge-case handling |

### Criteria Weights
| Criteria | Weight | What to check |
|----------|--------|---------------|
| Correctness | ×3 | Does it produce correct output? |
| Error handling | ×2 | Fails gracefully? Proper logging? |
| Resource management | ×2 | COM cleanup? File handles closed? |
| Code quality | ×1 | Readability, naming, structure |
| Test coverage | ×1.5 | Mock quality, edge cases |
| Documentation | ×0.5 | CLAUDE.md, known-traps updated? |

## Output Format
```markdown
# Audit Report — [Date]
## Summary: [Score]/10
## Findings
### Critical (must fix before release)
### Warning (should fix)
### Info (nice to have)
## Recommendations
```

## Pre-Release Checklist
- [ ] All 107+ tests pass
- [ ] verify_claude_md.py passes (0 fails)
- [ ] Visual verification of main window
- [ ] Quality presets all work (test each)
- [ ] Force-stop works during conversion
- [ ] .spec file up to date
- [ ] Version number updated
