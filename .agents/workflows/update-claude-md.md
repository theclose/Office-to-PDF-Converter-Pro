---
description: Update CLAUDE.md and docs/ when codebase changes significantly
---
# /update-claude-md — Verify & Update CLAUDE.md

// turbo-all

## MANDATORY TRIGGER CONDITIONS
⚠️ This workflow MUST be executed when ANY of these occur:
- A **new .py file** is created in converters/, core/, ui/, utils/
- An existing file's LOC changes by **>50 lines**
- A **bug is fixed** (MUST add known-traps.md entry)
- A **new function/class** is added to a core module
- A **new dependency** is introduced (e.g. Ghostscript, new pip package)
- A **SKILL.md** file's domain is affected by the code change

## Steps

1. Run automated verification script (MUST pass before proceeding)
```powershell
python scripts/verify_claude_md.py
```

2. If failures found, review each:
   - **LOC mismatches** → auto-fix with `--fix`
   - **Undocumented files** → add to docs/architecture.md  
   - **CLAUDE.md gaps** → update subdirectory CLAUDE.md
   - **Known-traps missing fields** → fix format

3. Auto-fix LOC mismatches:
```powershell
python scripts/verify_claude_md.py --fix
```

4. Re-run to confirm all checks pass:
```powershell
python scripts/verify_claude_md.py
```

5. For any code changes, manually verify:
   - If modified converters/ → verify converters/CLAUDE.md is accurate
   - If modified ui/ → verify ui/CLAUDE.md is accurate  
   - If modified core/ → verify core/CLAUDE.md is accurate
   - If fixed a bug → add entry to docs/known-traps.md (WHY + HOW TO AVOID)
   - If added new module → verify SKILL.md files that reference that layer

6. If CLAUDE.md exceeds 150 lines → move details to appropriate docs/ file

7. Update "Last updated" date in CLAUDE.md header

8. IMPORTANT: For UI changes, verify the rules in ui/CLAUDE.md and docs/gui-rules.md are still correct by checking the actual code values (the verify script checks pack_propagate and width automatically)

## What the Script Checks (v2)
| # | Check | Auto-fixable? |
|---|-------|---------------|
| 1 | CLAUDE.md < 150 lines | ❌ Manual |
| 2 | LOC accuracy (±5 tolerance) | ✅ `--fix` |
| 3 | config.json keys documented | ❌ Manual |
| 4 | Documented files exist | ❌ Manual |
| 5 | Critical code values (pack_propagate, width) | ❌ Manual |
| 6 | **NEW:** Undocumented .py files (>10 LOC) | ❌ Manual |
| 7 | **NEW:** Subdirectory CLAUDE.md covers all modules (>50 LOC) | ❌ Manual |
| 8 | **NEW:** known-traps.md format (Bug/Cause/Fix/Rule fields) | ❌ Manual |
| 9 | **NEW:** SKILL.md cross-refs (trap #s, files exist, domain coverage) | ❌ Manual |
