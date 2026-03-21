---
description: Update CLAUDE.md and docs/ when codebase changes significantly
---
# /update-claude-md — Verify & Update CLAUDE.md

// turbo-all

## Steps

1. Run automated verification script (MUST pass before proceeding)
```powershell
python scripts/verify_claude_md.py
```

2. If LOC mismatches found, auto-fix:
```powershell
python scripts/verify_claude_md.py --fix
```

3. Re-run to confirm all checks pass:
```powershell
python scripts/verify_claude_md.py
```

4. For any code changes:
   - If modified converters/ → verify converters/CLAUDE.md is accurate
   - If modified ui/ → verify ui/CLAUDE.md is accurate  
   - If modified core/ → verify core/CLAUDE.md is accurate
   - If fixed a bug → add entry to docs/known-traps.md (WHY + HOW TO AVOID)

5. If CLAUDE.md exceeds 150 lines → move details to appropriate docs/ file

6. Update "Last updated" date in CLAUDE.md header

7. IMPORTANT: For UI changes, verify the rules in ui/CLAUDE.md and docs/gui-rules.md are still correct by checking the actual code values (the verify script checks pack_propagate and width automatically)
