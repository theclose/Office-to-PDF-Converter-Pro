---
name: pre-release-build
description: |
  Pre-release build and verification workflow for Office to PDF Converter Pro.
  Consolidates all build knowledge: PyInstaller .spec validation, dependency
  checks, test gates, documentation verification, and EXE smoke testing.
  Use this skill before building a production EXE or publishing to GitHub.
---

# Pre-Release Build Skill

## When to Use
- Before building a production EXE (`pyinstaller OfficeToPDF_Pro.spec`)
- Before pushing a release to GitHub
- After significant code changes that affect the build

## Pre-Build Gate Checklist

### Gate 1: Tests Must Pass
```bash
python -m pytest tests/ -v --tb=short
# Expected: 188+ passed, ≤4 skipped (COM-dependent)
# ZERO failures allowed
```

### Gate 2: Documentation Verified
```bash
python scripts/verify_claude_md.py
# Expected: 18/18 passed, 0 failed
```

### Gate 3: No Dead Code
```bash
# Check for files that shouldn't be tracked
git status --short
# Working tree should be clean or only contain intended changes
```

### Gate 4: Dependencies Verified
```bash
pip list | Select-String "pywin32|PyMuPDF|Pillow|customtkinter|openpyxl|pyinstaller"
```
Required packages:
| Package | Min Version | Purpose |
|---------|-------------|---------|
| pywin32 | ≥306 | COM automation |
| PyMuPDF | ≥1.23 | PDF manipulation |
| Pillow | ≥10.0 | Image processing |
| customtkinter | ≥5.2 | GUI framework |
| openpyxl | ≥3.1 | Excel operations |
| pyinstaller | ≥6.0 | Build to EXE |

### Gate 5: .spec File Valid
```bash
# Verify OfficeToPDF_Pro.spec uses dynamic SITE_PACKAGES
Select-String "importlib" OfficeToPDF_Pro.spec
# Should find: importlib.util.find_spec("...")
# Should NOT find hardcoded paths like: C:\python\Lib\site-packages
```

## Build Process

### Step 1: Clean Build
```bash
# Remove old build artifacts
Remove-Item -Recurse -Force build/, dist/ -ErrorAction SilentlyContinue

# Build
pyinstaller OfficeToPDF_Pro.spec --clean
```

### Step 2: Verify EXE
```bash
# Check output exists and is reasonable size
Get-Item dist/OfficeToPDF_Pro.exe | Select-Object Name, Length
# Expected: ~40-50 MB
```

### Step 3: Smoke Test EXE
1. Run `dist/OfficeToPDF_Pro.exe`
2. Verify:
   - [ ] App launches without error
   - [ ] Main window renders correctly
   - [ ] Theme toggle works
   - [ ] Language switch works
   - [ ] PDF Tools opens
   - [ ] Excel Tools opens (requires openpyxl bundled)
   - [ ] File Tools opens
   - [ ] Add a file → convert (if Office installed)

## GitHub Release Checklist
- [ ] All gates pass (tests, verify, deps, spec)
- [ ] README.md up to date
- [ ] Version number in CLAUDE.md matches
- [ ] .gitignore correct (spec tracked, db/dist/build ignored)
- [ ] No sensitive data in tracked files
- [ ] `git push origin main` succeeds

## .gitignore Critical Rules
```gitignore
# MUST be ignored
*.db
*.db-wal
*.db-shm
dist/
build/
__pycache__/

# MUST be tracked
OfficeToPDF_Pro.spec    # Build config
requirements.txt        # Dependencies
```

## Known Build Issues
- PyInstaller warning about `fitz.fitz` hidden import — expected, handled gracefully
- `windnd` import warning — app falls back to tkdnd/no-dnd gracefully
- Some antivirus may flag the EXE — false positive, known PyInstaller issue
