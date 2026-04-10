---
name: bug-fix-workflow
description: |
  Systematic workflow for debugging and fixing bugs in the Office to PDF Converter.
  Covers COM automation issues, GUI rendering problems, converter failures,
  PDF processing errors, and refactor-induced breaks. Ensures bug fixes are
  documented in known-traps.md and CLAUDE.md is updated.
  Use this skill when fixing any bug in the application.
---

# Bug Fix Workflow

## When to Use
- When debugging a reported bug or unexpected behavior
- When a test fails unexpectedly
- When fixing regression issues
- When a refactored method breaks callers

## Step-by-Step Process

### 1. Research Before Fixing
```
READ docs/known-traps.md FIRST (23 entries)
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
- [ ] If method signature changed → grep ALL callers (see Refactor Safety below)

### 4. Refactor Safety Checklist (Traps #21-23)
When changing ANY method signature, constructor, or API:
```bash
# Find all callers of the changed method
grep -rn "method_name" converters/ core/ ui/ utils/ tests/

# Verify constructor kwargs match actual params
grep -rn "ClassName(" ui/ core/ tests/
```
Common mistakes:
- Renaming `undo()` → `undo_last_transaction()` but UI still calls `undo()` (trap #22)
- Adding required param `rules` to `preview()` but not updating UI caller (trap #21)
- Using wrong kwarg name: `SequenceRule(position=)` vs `at_start=` (trap #23)

### 5. Resource Leak Checklist (Traps #15-18)
- [ ] PDF files opened with `fitz` are closed in `finally` block
- [ ] Temp files created in `tempfile` are cleaned up
- [ ] subprocess calls don't leave zombie processes
- [ ] `self.after()` callbacks cancelled on widget destroy
- [ ] COM objects released on same thread they were created

### 6. Verify Fix
```bash
# Always run tests
python -m pytest tests/ -v --tb=short

# If UI change → MUST run app and verify visually
python run_pro.py

# Run verify script
python scripts/verify_claude_md.py
```

### 7. Document (MANDATORY)
Add entry to `docs/known-traps.md`:
```markdown
## N. [Short description]
- **Bug:** [What happened]
- **Cause:** [Root cause — WHY it happened]
- **Fix:** [What was changed]
- **Rule:** [How to avoid in future]
```

### 8. Update CLAUDE.md System
- If new Critical Rule discovered → add to root CLAUDE.md
- If affects specific layer → update subdirectory CLAUDE.md
- Run: `python scripts/verify_claude_md.py --fix`

## Common Bug Categories

### COM Automation Bugs
- Check COM STA threading (converters/CLAUDE.md)
- Verify COM object lifecycle (create → use → cleanup on SAME thread)
- Check fallback chain ordering
- Never call CoUninitialize when using COM pool (trap #20)

### GUI Rendering Bugs
- Check pack_propagate value (trap #1)
- Verify widget operations are on main thread
- Run app to verify — pytest CANNOT catch GUI rendering bugs (trap #4)

### PDF Processing Bugs
- Use `get_fitz()` not `HAS_PYMUPDF` boolean (trap #2)
- NEVER use `doc.update_stream()` for image replacement (trap #11)
- Image replacement: always `delete_image()` + `insert_image()`
- Ghostscript pipeline: falls back gracefully when GS not installed

### Refactor-Induced Bugs (Traps #21-23)
- Method renamed but not all callers updated
- Constructor kwarg name doesn't match actual parameter
- Required parameter added but callers not updated

## Anti-Patterns (DON'T DO)
1. ❌ Fix symptom without finding root cause
2. ❌ Skip visual verification for UI changes
3. ❌ Trust pytest alone for GUI correctness
4. ❌ Forget to add known-traps.md entry
5. ❌ Change method signature without grepping ALL callers
6. ❌ Change pack_propagate or COM threading without reading docs
