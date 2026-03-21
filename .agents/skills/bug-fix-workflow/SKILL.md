---
name: bug-fix-workflow
description: |
  Systematic workflow for debugging and fixing bugs in the Office to PDF Converter.
  Covers COM automation issues, GUI rendering problems, converter failures,
  and PDF processing errors. Ensures bug fixes are documented in known-traps.md
  and CLAUDE.md is updated. Use this skill when fixing any bug in the application.
---

# Bug Fix Workflow

## When to Use
- When debugging a reported bug or unexpected behavior
- When a test fails unexpectedly
- When fixing regression issues

## Step-by-Step Process

### 1. Research Before Fixing
```
READ docs/known-traps.md FIRST
→ Check if this bug (or similar) has been seen before
→ If yes: follow the documented fix, don't reinvent
→ If no: proceed to diagnosis
```

### 2. Diagnose Root Cause
```
DON'T jump to fixing symptoms. Ask:
1. WHAT is the actual error? (error message, behavior)
2. WHERE in the stack? (converter? engine? UI? utils?)
3. WHEN does it happen? (always? specific files? specific quality?)
4. WHY does the existing code not handle this?
```

### 3. Fix with Constraints
Before writing code, verify:
- [ ] Read the subdirectory CLAUDE.md (ui/, converters/, core/) for rules
- [ ] Check if fix violates any Critical Rule (COM STA, Tkinter thread-safety, etc.)
- [ ] If UI change → plan visual verification

### 4. Verify Fix
```
# Always run tests
python -m pytest tests/ -v --tb=short

# If UI change → MUST run app and verify visually
python run_pro.py

# Run verify script
python scripts/verify_claude_md.py
```

### 5. Document (MANDATORY)
Add entry to `docs/known-traps.md`:
```markdown
## N. [Short description]
- **Bug:** [What happened]
- **Cause:** [Root cause — WHY it happened]
- **Fix:** [What was changed]
- **Rule:** [How to avoid in future]
```

### 6. Update CLAUDE.md System
- If new Critical Rule discovered → add to root CLAUDE.md
- If affects specific layer → update subdirectory CLAUDE.md
- Run: `python scripts/verify_claude_md.py --fix`

## Common Bug Categories

### COM Automation Bugs
- Check COM STA threading (converters/CLAUDE.md)
- Verify COM object lifecycle (create → use → cleanup on SAME thread)
- Check fallback chain ordering

### GUI Rendering Bugs  
- Check pack_propagate value
- Verify widget operations are on main thread
- Run app to verify — pytest CANNOT catch GUI rendering bugs

### PDF Processing Bugs
- Use `get_fitz()` not `HAS_PYMUPDF` boolean
- Check post-processing order in engine.py
- Verify compression levels map correctly

## Anti-Patterns (DON'T DO)
1. ❌ Fix symptom without finding root cause
2. ❌ Skip visual verification for UI changes
3. ❌ Trust pytest alone for GUI correctness
4. ❌ Forget to add known-traps.md entry
5. ❌ Change pack_propagate or COM threading without reading docs
