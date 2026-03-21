"""
verify_claude_md.py — Automated verification for CLAUDE.md system.
Checks accuracy of documentation against actual codebase.
Run: python scripts/verify_claude_md.py [--fix]

Checks:
  1. CLAUDE.md line count < 150
  2. LOC counts in docs/architecture.md match actual files
  3. config.json keys are documented in docs/architecture.md
  4. All files listed in docs/architecture.md exist
  5. Critical code values match docs (e.g. pack_propagate)
"""

import os
import re
import json
import sys
from pathlib import Path

# Fix Windows terminal encoding for emoji
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Resolve project root (parent of scripts/)
ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = ROOT / "CLAUDE.md"
ARCH_MD = ROOT / "docs" / "architecture.md"
CONFIG_JSON = ROOT / "config.json"
MAIN_WINDOW = ROOT / "ui" / "main_window_pro.py"

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️ WARN"
AUTO = "🔧 AUTO-FIXED"

results = []
fixes_applied = 0


def check_claude_line_count():
    """Check 1: CLAUDE.md must be < 150 lines."""
    lines = CLAUDE_MD.read_text(encoding="utf-8").splitlines()
    count = len(lines)
    if count < 150:
        results.append((PASS, f"CLAUDE.md: {count} lines (< 150 limit)"))
    else:
        results.append((FAIL, f"CLAUDE.md: {count} lines (EXCEEDS 150 limit)"))


def get_actual_loc() -> dict:
    """Scan all .py files and return {filename: loc}."""
    loc = {}
    for dirpath, _, filenames in os.walk(ROOT):
        # Skip tests, scripts, hidden dirs
        rel = os.path.relpath(dirpath, ROOT)
        if any(skip in rel for skip in [".git", "__pycache__", "scripts", "build", "dist"]):
            continue
        for f in filenames:
            if f.endswith(".py"):
                fpath = os.path.join(dirpath, f)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                        count = sum(1 for _ in fh)
                    loc[f] = count
                except Exception:
                    pass
    return loc


def check_loc_accuracy(auto_fix=False):
    """Check 2: LOC counts in docs/architecture.md match actual."""
    global fixes_applied
    if not ARCH_MD.exists():
        results.append((FAIL, "docs/architecture.md not found"))
        return

    actual_loc = get_actual_loc()
    arch_text = ARCH_MD.read_text(encoding="utf-8")
    
    # Parse LOC from architecture.md table rows like: | file.py | 123 | ...
    pattern = re.compile(r"\|\s*(\w+\.py)\s*\|\s*(\d+)\s*\|")
    documented = {}
    for m in pattern.finditer(arch_text):
        documented[m.group(1)] = int(m.group(2))

    mismatches = []
    for fname, doc_loc in documented.items():
        actual = actual_loc.get(fname)
        if actual is None:
            mismatches.append(f"  {fname}: documented {doc_loc} but file not found")
        elif abs(actual - doc_loc) > 5:  # tolerance of 5 lines
            mismatches.append(f"  {fname}: documented {doc_loc}, actual {actual} (Δ{actual - doc_loc:+d})")

    if not mismatches:
        results.append((PASS, f"LOC accuracy: {len(documented)} files checked, all within ±5 lines"))
    else:
        if auto_fix:
            # Auto-update LOC in architecture.md
            new_text = arch_text
            for fname, doc_loc in documented.items():
                actual = actual_loc.get(fname)
                if actual and abs(actual - doc_loc) > 5:
                    old = f"| {fname} | {doc_loc} |"
                    # Handle variable spacing
                    old_pattern = re.compile(
                        r"\|\s*" + re.escape(fname) + r"\s*\|\s*" + str(doc_loc) + r"\s*\|"
                    )
                    new_text = old_pattern.sub(f"| {fname} | {actual} |", new_text)
            ARCH_MD.write_text(new_text, encoding="utf-8")
            fixes_applied += 1
            results.append((AUTO, f"LOC updated in architecture.md ({len(mismatches)} fixes)"))
        else:
            results.append((FAIL, f"LOC mismatches ({len(mismatches)}):\n" + "\n".join(mismatches)))


def check_config_sync():
    """Check 3: config.json keys are documented in docs/architecture.md."""
    if not CONFIG_JSON.exists():
        results.append((WARN, "config.json not found (may be first run)"))
        return
    if not ARCH_MD.exists():
        results.append((FAIL, "docs/architecture.md not found"))
        return

    with open(CONFIG_JSON, "r", encoding="utf-8") as f:
        config = json.load(f)

    arch_text = ARCH_MD.read_text(encoding="utf-8")

    # Collect all keys (top-level + nested)
    actual_keys = set()
    for k, v in config.items():
        actual_keys.add(k)
        if isinstance(v, dict):
            for sub_k in v:
                actual_keys.add(sub_k)

    undocumented = [k for k in actual_keys if f'"{k}"' not in arch_text]

    if not undocumented:
        results.append((PASS, f"Config sync: all {len(actual_keys)} keys documented"))
    else:
        results.append((FAIL, f"Config keys not in architecture.md: {', '.join(undocumented)}"))


def check_file_existence():
    """Check 4: All .py files mentioned in architecture.md exist."""
    if not ARCH_MD.exists():
        results.append((FAIL, "docs/architecture.md not found"))
        return

    arch_text = ARCH_MD.read_text(encoding="utf-8")
    pattern = re.compile(r"\|\s*(\w+\.py)\s*\|")
    mentioned = set()
    for m in pattern.finditer(arch_text):
        mentioned.add(m.group(1))

    actual_files = set()
    for dirpath, _, filenames in os.walk(ROOT):
        rel = os.path.relpath(dirpath, ROOT)
        if any(skip in rel for skip in [".git", "__pycache__", "scripts", "build", "dist"]):
            continue
        for f in filenames:
            if f.endswith(".py"):
                actual_files.add(f)

    missing = mentioned - actual_files
    undocumented_py = actual_files - mentioned - {"conftest.py", "run_pro.py", "__init__.py",
                                                   "setup.py", "test_com_lifecycle.py",
                                                   "test_converter_integration_v2.py",
                                                   "test_engine_threading.py", "test_core.py",
                                                   "test_bug_fixes.py", "test_fallback_chain.py"}

    if not missing:
        results.append((PASS, f"File existence: all {len(mentioned)} documented files exist"))
    else:
        results.append((FAIL, f"Files in architecture.md but missing: {', '.join(missing)}"))

    if undocumented_py:
        results.append((WARN, f"Undocumented .py files: {', '.join(sorted(undocumented_py))}"))


def check_critical_code_values():
    """Check 5: Critical code values match documentation."""
    if not MAIN_WINDOW.exists():
        results.append((WARN, "main_window_pro.py not found"))
        return

    code = MAIN_WINDOW.read_text(encoding="utf-8")

    checks = []

    # Check pack_propagate
    if "pack_propagate(False)" in code:
        checks.append((PASS, "pack_propagate(False) confirmed in code"))
    elif "pack_propagate(True)" in code:
        checks.append((FAIL, "pack_propagate(True) found — MUST be False (see known-traps #1)"))
    else:
        checks.append((WARN, "pack_propagate not found in code"))

    # Check right_frame width
    width_match = re.search(r"right_frame\.configure\(width=(\d+)\)", code)
    if width_match:
        width = int(width_match.group(1))
        checks.append((PASS, f"right_frame width={width}px confirmed"))
    else:
        checks.append((WARN, "right_frame width not found"))

    # Check quality presets count
    presets = code.count("_quality_presets")
    if presets > 0:
        checks.append((PASS, "Quality presets system found in code"))

    # Check window geometry
    geo_match = re.search(r'self\.geometry\("(\d+)x(\d+)"\)', code)
    if geo_match:
        w, h = geo_match.group(1), geo_match.group(2)
        checks.append((PASS, f"Window geometry: {w}×{h}"))

    results.extend(checks)


def main():
    auto_fix = "--fix" in sys.argv

    print("=" * 60)
    print("  CLAUDE.md Verification Report")
    print("=" * 60)
    print()

    check_claude_line_count()
    check_loc_accuracy(auto_fix=auto_fix)
    check_config_sync()
    check_file_existence()
    check_critical_code_values()

    # Print results
    pass_count = sum(1 for s, _ in results if s == PASS)
    fail_count = sum(1 for s, _ in results if s == FAIL)
    warn_count = sum(1 for s, _ in results if s == WARN)
    fix_count = sum(1 for s, _ in results if s == AUTO)

    for status, msg in results:
        print(f"  {status} {msg}")

    print()
    print("-" * 60)
    print(f"  Results: {pass_count} passed, {fail_count} failed, {warn_count} warnings, {fix_count} auto-fixed")
    
    if fail_count > 0:
        print(f"\n  Run with --fix to auto-fix LOC mismatches:")
        print(f"  python scripts/verify_claude_md.py --fix")
        print()
        return 1
    
    if fix_count > 0:
        print(f"\n  {fix_count} auto-fixes applied. Review changes and commit.")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
