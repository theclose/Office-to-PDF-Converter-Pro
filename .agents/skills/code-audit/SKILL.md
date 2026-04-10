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
- [ ] COMPool lifecycle (health-check, recycle, zombie kill)
- [ ] Logging setup (no print(), proper levels)
- [ ] Error handling (no bare excepts)
- [ ] Parallel converter process management

#### Layer 1 → converters/ (highest risk)
- [ ] COM STA compliance (CoInitialize per thread)
- [ ] Quality parameter actually used (not ignored — trap #3)
- [ ] Fallback chains complete and ordered
- [ ] Pre-flight validation (file exists, size, lock)
- [ ] Resource cleanup in finally blocks
- [ ] PDF output validation after conversion
- [ ] COM pool integration (no CoUninitialize when pooled — trap #20)

#### Layer 2 → core/ (medium risk)
- [ ] Engine stop/force-stop contract
- [ ] Post-processing order correct
- [ ] Auto-compress integration
- [ ] get_fitz() used (not stale boolean — trap #2)
- [ ] Excel Tools: split/merge/csv/protect all work
- [ ] File Tools: preview/execute/undo API consistent
- [ ] File Tools: all UI callers match core API signatures (traps #21-23)

#### Layer 3 → ui/ (visual verification required)
- [ ] pack_propagate(False) enforced (trap #1)
- [ ] Thread-safety (self.after for cross-thread)
- [ ] All callbacks wrapped in try/except
- [ ] after() callbacks cleaned up on destroy
- [ ] Visual verification (run app, check rendering)
- [ ] MUST test: Excel Tools dialog open → all 7 operations
- [ ] MUST test: File Tools dialog → preview → rename → undo
- [ ] MUST run app and test: open → change language → close

### Phase 3: Cross-Cutting Concerns
- [ ] Exception handling: no bare excepts, proper logging
- [ ] Resource cleanup: try/finally for COM, files, DB
- [ ] Thread safety: no cross-thread COM or widget access
- [ ] File I/O: encoding specified (utf-8), error handling
- [ ] Security: password handling, no hardcoded secrets
- [ ] API consistency: UI callers match core method signatures

### Phase 4: Cross-Caller Verification
```bash
# Verify all core API methods are called correctly from UI
grep -rn "\.preview(" ui/ --include="*.py"
grep -rn "\.execute(" ui/ --include="*.py"
grep -rn "\.undo" ui/ --include="*.py"
grep -rn "SequenceRule(" ui/ --include="*.py"
grep -rn "split_excel(" ui/ --include="*.py"
grep -rn "merge_excel(" ui/ --include="*.py"
```

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
- [ ] All 188+ tests pass (4 COM-dependent may skip)
- [ ] verify_claude_md.py passes (18/18, 0 fails)
- [ ] Visual verification of main window
- [ ] Excel Tools: test split + merge
- [ ] File Tools: test preview + rename + undo
- [ ] Quality presets all work (test each)
- [ ] Force-stop works during conversion
- [ ] .spec file up to date (dynamic SITE_PACKAGES)
- [ ] Version number updated
