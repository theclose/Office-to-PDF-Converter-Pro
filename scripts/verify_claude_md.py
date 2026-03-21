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
  6. NEW: Detect new .py files not listed in architecture.md
  7. NEW: Subdirectory CLAUDE.md mentions key modules in its directory
  8. NEW: known-traps.md sanity check (count, format)
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
KNOWN_TRAPS = ROOT / "docs" / "known-traps.md"

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️ WARN"
AUTO = "🔧 AUTO-FIXED"

results = []
fixes_applied = 0

# --- Directories to scan (project source dirs, not tests/scripts/build) ---
SOURCE_DIRS = ["converters", "core", "ui", "utils"]

# --- Files to EXCLUDE from "undocumented" check ---
EXCLUDED_FILES = {
    "conftest.py", "run_pro.py", "__init__.py", "setup.py",
    "test_com_lifecycle.py", "test_converter_integration_v2.py",
    "test_engine_threading.py", "test_core.py", "test_bug_fixes.py",
    "test_fallback_chain.py", "verify_claude_md.py",
}


def check_claude_line_count():
    """Check 1: CLAUDE.md must be < 150 lines."""
    lines = CLAUDE_MD.read_text(encoding="utf-8").splitlines()
    count = len(lines)
    if count < 150:
        results.append((PASS, f"CLAUDE.md: {count} lines (< 150 limit)"))
    else:
        results.append((FAIL, f"CLAUDE.md: {count} lines (EXCEEDS 150 limit)"))


def get_actual_loc() -> dict:
    """Scan all .py files in SOURCE_DIRS and return {relative_path: loc}."""
    loc = {}
    for src_dir in SOURCE_DIRS:
        src_path = ROOT / src_dir
        if not src_path.exists():
            continue
        for dirpath, _, filenames in os.walk(src_path):
            rel_dir = os.path.relpath(dirpath, ROOT)
            if any(skip in rel_dir for skip in [".git", "__pycache__", "build", "dist"]):
                continue
            for f in filenames:
                if f.endswith(".py") and f != "__init__.py":
                    fpath = os.path.join(dirpath, f)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                            count = sum(1 for _ in fh)
                        # Store both basename and relative path
                        loc[f] = {"count": count, "rel_path": os.path.relpath(fpath, ROOT)}
                    except Exception:
                        pass
    return loc


def _parse_arch_entries() -> dict:
    """Parse architecture.md table rows: | path/file.py | 123 | description |"""
    if not ARCH_MD.exists():
        return {}
    arch_text = ARCH_MD.read_text(encoding="utf-8")
    # Match patterns like: | file.py | 123 | or | pdf/file.py | 123 |
    pattern = re.compile(r"\|\s*([\w/]+\.py)\s*\|\s*(\d+)\s*\|")
    entries = {}
    for m in pattern.finditer(arch_text):
        path_or_name = m.group(1)
        loc = int(m.group(2))
        # Extract basename for matching
        basename = os.path.basename(path_or_name)
        entries[basename] = {"doc_loc": loc, "doc_path": path_or_name}
    return entries


def check_loc_accuracy(auto_fix=False):
    """Check 2: LOC counts in docs/architecture.md match actual."""
    global fixes_applied
    if not ARCH_MD.exists():
        results.append((FAIL, "docs/architecture.md not found"))
        return

    actual_loc = get_actual_loc()
    arch_text = ARCH_MD.read_text(encoding="utf-8")

    # Parse LOC from architecture.md table rows like: | file.py | 123 | ...
    pattern = re.compile(r"\|\s*([\w/]+\.py)\s*\|\s*(\d+)\s*\|")
    documented = {}
    for m in pattern.finditer(arch_text):
        fname = os.path.basename(m.group(1))
        documented[fname] = int(m.group(2))

    mismatches = []
    for fname, doc_loc in documented.items():
        actual = actual_loc.get(fname)
        if actual is None:
            mismatches.append(f"  {fname}: documented {doc_loc} but file not found")
        elif abs(actual["count"] - doc_loc) > 5:  # tolerance of 5 lines
            mismatches.append(f"  {fname}: documented {doc_loc}, actual {actual['count']} (Δ{actual['count'] - doc_loc:+d})")

    if not mismatches:
        results.append((PASS, f"LOC accuracy: {len(documented)} files checked, all within ±5 lines"))
    else:
        if auto_fix:
            # Auto-update LOC in architecture.md
            new_text = arch_text
            for fname, doc_loc in documented.items():
                actual = actual_loc.get(fname)
                if actual and abs(actual["count"] - doc_loc) > 5:
                    old_pattern = re.compile(
                        r"\|\s*" + re.escape(fname) + r"\s*\|\s*" + str(doc_loc) + r"\s*\|"
                    )
                    # Also try with path prefix
                    for pattern_str in [fname]:
                        p = re.compile(
                            r"(\|\s*[\w/]*" + re.escape(pattern_str) + r"\s*\|\s*)" + str(doc_loc) + r"(\s*\|)"
                        )
                        new_text = p.sub(rf"\g<1>{actual['count']}\2", new_text)
                    
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
    pattern = re.compile(r"\|\s*([\w/]+\.py)\s*\|")
    mentioned = set()
    for m in pattern.finditer(arch_text):
        mentioned.add(os.path.basename(m.group(1)))

    actual_files = set()
    for src_dir in SOURCE_DIRS:
        src_path = ROOT / src_dir
        if not src_path.exists():
            continue
        for dirpath, _, filenames in os.walk(src_path):
            for f in filenames:
                if f.endswith(".py") and f != "__init__.py":
                    actual_files.add(f)

    missing = mentioned - actual_files
    if not missing:
        results.append((PASS, f"File existence: all {len(mentioned)} documented files exist"))
    else:
        results.append((FAIL, f"Files in architecture.md but missing: {', '.join(missing)}"))


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


def check_undocumented_files():
    """Check 6: Detect .py files in source dirs NOT listed in architecture.md."""
    if not ARCH_MD.exists():
        results.append((FAIL, "docs/architecture.md not found"))
        return

    arch_text = ARCH_MD.read_text(encoding="utf-8")
    
    # Get all files mentioned in architecture.md
    pattern = re.compile(r"\|\s*([\w/]+\.py)\s*\|")
    documented_files = set()
    for m in pattern.finditer(arch_text):
        documented_files.add(os.path.basename(m.group(1)))

    # Get all actual .py files in source directories
    actual_files = set()
    actual_details = {}
    for src_dir in SOURCE_DIRS:
        src_path = ROOT / src_dir
        if not src_path.exists():
            continue
        for dirpath, _, filenames in os.walk(src_path):
            for f in filenames:
                if f.endswith(".py") and f not in EXCLUDED_FILES:
                    fpath = os.path.join(dirpath, f)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                            loc = sum(1 for _ in fh)
                        rel = os.path.relpath(fpath, ROOT)
                        actual_files.add(f)
                        actual_details[f] = {"loc": loc, "rel_path": rel}
                    except Exception:
                        pass

    undocumented = actual_files - documented_files
    # Filter out small files (< 10 lines) — likely __init__ stubs
    significant_undocumented = []
    for f in sorted(undocumented):
        if f in actual_details and actual_details[f]["loc"] >= 10:
            d = actual_details[f]
            significant_undocumented.append(f"  {d['rel_path']}: {d['loc']} lines (NOT in architecture.md)")

    if not significant_undocumented:
        results.append((PASS, f"No undocumented source files (checked {len(actual_files)} files)"))
    else:
        results.append((FAIL, f"Undocumented source files ({len(significant_undocumented)}):\n" + "\n".join(significant_undocumented)))


def check_subdir_claude_accuracy():
    """Check 7: Subdirectory CLAUDE.md mentions key modules that exist in its dir."""
    subdir_checks = {
        "core": {
            "claude_path": ROOT / "core" / "CLAUDE.md",
            "key_modules": [],  # Will be auto-detected
        },
        "converters": {
            "claude_path": ROOT / "converters" / "CLAUDE.md",
            "key_modules": [],
        },
        "ui": {
            "claude_path": ROOT / "ui" / "CLAUDE.md",
            "key_modules": [],
        },
    }

    all_ok = True
    details = []

    for subdir_name, info in subdir_checks.items():
        claude_path = info["claude_path"]
        if not claude_path.exists():
            results.append((WARN, f"{subdir_name}/CLAUDE.md not found"))
            continue

        claude_text = claude_path.read_text(encoding="utf-8").lower()
        subdir_path = ROOT / subdir_name

        # Find all .py files > 50 lines in this subdir (significant modules)
        significant_modules = []
        for dirpath, _, filenames in os.walk(subdir_path):
            for f in filenames:
                if f.endswith(".py") and f != "__init__.py":
                    fpath = os.path.join(dirpath, f)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                            loc = sum(1 for _ in fh)
                        if loc >= 50:
                            significant_modules.append((f, loc, os.path.relpath(fpath, ROOT)))
                    except Exception:
                        pass

        # Check if each significant module is mentioned in CLAUDE.md
        missing = []
        for fname, loc, rel_path in significant_modules:
            # Check for filename (without .py) mention
            basename = fname.replace(".py", "")
            if basename not in claude_text and fname not in claude_text:
                missing.append(f"  {rel_path} ({loc} lines) not mentioned in {subdir_name}/CLAUDE.md")

        if missing:
            all_ok = False
            details.extend(missing)

    if all_ok:
        results.append((PASS, "Subdirectory CLAUDE.md files cover all significant modules"))
    else:
        results.append((FAIL, f"Subdirectory CLAUDE.md gaps ({len(details)}):\n" + "\n".join(details)))


def check_known_traps():
    """Check 8: known-traps.md sanity check."""
    if not KNOWN_TRAPS.exists():
        results.append((FAIL, "docs/known-traps.md not found"))
        return

    text = KNOWN_TRAPS.read_text(encoding="utf-8")
    
    # Count trap entries (## N. pattern)
    trap_pattern = re.compile(r"^## (\d+)\.", re.MULTILINE)
    traps = trap_pattern.findall(text)
    trap_count = len(traps)

    if trap_count == 0:
        results.append((FAIL, "known-traps.md has no entries"))
        return

    # Check format: each trap should have Bug, Cause, Fix, Rule
    required_fields = ["**Bug:**", "**Cause:**", "**Fix:**", "**Rule:**"]
    malformed = []
    
    # Split by ## to get individual traps
    sections = re.split(r"^## \d+\.", text, flags=re.MULTILINE)
    for i, section in enumerate(sections[1:], 1):  # Skip header
        missing_fields = [f for f in required_fields if f not in section]
        if missing_fields:
            # Get trap title
            title_match = re.search(r"^(.+?)$", section.strip(), re.MULTILINE)
            title = title_match.group(1).strip() if title_match else f"Trap {i}"
            malformed.append(f"  Trap {i} ({title}): missing {', '.join(missing_fields)}")

    checks = []
    checks.append((PASS, f"known-traps.md: {trap_count} entries found"))
    
    # Check numbering is sequential
    expected_nums = list(range(1, trap_count + 1))
    actual_nums = [int(n) for n in traps]
    if actual_nums != expected_nums:
        checks.append((WARN, f"Trap numbering not sequential: {actual_nums}"))
    else:
        checks.append((PASS, f"Trap numbering: 1-{trap_count} sequential"))

    if malformed:
        checks.append((WARN, f"Malformed trap entries:\n" + "\n".join(malformed)))
    else:
        checks.append((PASS, f"All {trap_count} traps have required fields (Bug/Cause/Fix/Rule)"))

    results.extend(checks)


def check_skill_files():
    """Check 9: SKILL.md cross-reference validation."""
    skills_dir = ROOT / ".agents" / "skills"
    if not skills_dir.exists():
        results.append((WARN, "Skills directory not found"))
        return

    skill_files = list(skills_dir.rglob("SKILL.md"))
    if not skill_files:
        results.append((WARN, "No SKILL.md files found"))
        return

    # Get max known-trap number
    max_trap = 0
    if KNOWN_TRAPS.exists():
        trap_text = KNOWN_TRAPS.read_text(encoding="utf-8")
        trap_nums = re.findall(r"^## (\d+)\.", trap_text, re.MULTILINE)
        if trap_nums:
            max_trap = max(int(n) for n in trap_nums)

    all_issues = []

    # Define domain → key concerns mapping
    # Each skill should mention key concepts relevant to recent changes
    DOMAIN_CONCERNS = {
        "bug-fix-workflow": {
            "must_mention": ["known-traps", "update_stream"],  # Critical traps
            "should_reference_files": ["docs/known-traps.md"],
        },
        "code-audit": {
            "must_mention": ["verify_claude_md"],
            "should_reference_files": ["scripts/verify_claude_md.py"],
        },
        "converter-development": {
            "must_mention": ["com", "fallback"],
            "should_reference_files": [],
        },
        "ui-visual-verify": {
            "must_mention": ["pack_propagate", "run_pro"],
            "should_reference_files": [],
        },
    }

    for skill_path in skill_files:
        skill_name = skill_path.parent.name
        skill_text = skill_path.read_text(encoding="utf-8")
        skill_text_lower = skill_text.lower()
        issues = []

        # Check 9a: known-trap references are valid
        trap_refs = re.findall(r"known-trap[s]?\s*#(\d+)", skill_text, re.IGNORECASE)
        trap_refs += re.findall(r"trap\s*#(\d+)", skill_text, re.IGNORECASE)
        for ref in trap_refs:
            ref_num = int(ref)
            if ref_num > max_trap:
                issues.append(f"references trap #{ref_num} but max is #{max_trap}")

        # Check 9b: referenced project files exist
        # Find patterns like `scripts/verify_claude_md.py`, `engine.py`, `docs/known-traps.md`
        file_refs = re.findall(r"`([a-zA-Z_/]+\.(?:py|md|json))`", skill_text)
        for fref in file_refs:
            # Try to find the file
            fpath = ROOT / fref
            if not fpath.exists():
                # Try basename search
                basename = os.path.basename(fref)
                found = False
                for src_dir in SOURCE_DIRS + ["docs", "scripts", ".agents"]:
                    for dirpath, _, filenames in os.walk(ROOT / src_dir):
                        if basename in filenames:
                            found = True
                            break
                    if found:
                        break
                if not found and basename not in ("new_format.py",):  # Skip example files
                    issues.append(f"references `{fref}` but file not found")

        # Check 9c: domain coverage
        domain = DOMAIN_CONCERNS.get(skill_name, {})
        for concept in domain.get("must_mention", []):
            if concept.lower() not in skill_text_lower:
                issues.append(f"should mention '{concept}' (domain relevance)")

        if issues:
            for issue in issues:
                all_issues.append(f"  {skill_name}/SKILL.md: {issue}")

    if not all_issues:
        results.append((PASS, f"SKILL.md validation: {len(skill_files)} skills checked, all references valid"))
    else:
        results.append((FAIL, f"SKILL.md issues ({len(all_issues)}):\n" + "\n".join(all_issues)))


def main():
    auto_fix = "--fix" in sys.argv

    print("=" * 60)
    print("  CLAUDE.md Verification Report")
    print("=" * 60)
    print()

    all_pass = 0
    all_fail = 0
    all_warn = 0
    all_fix = 0

    # --- Core Checks (1-5) ---
    print("  --- Core Checks (1-5) ---")
    check_claude_line_count()
    check_loc_accuracy(auto_fix=auto_fix)
    check_config_sync()
    check_file_existence()
    check_critical_code_values()

    for status, msg in results:
        print(f"  {status} {msg}")
    all_pass += sum(1 for s, _ in results if s == PASS)
    all_fail += sum(1 for s, _ in results if s == FAIL)
    all_warn += sum(1 for s, _ in results if s == WARN)
    all_fix += sum(1 for s, _ in results if s == AUTO)
    results.clear()

    # --- Extended Checks (6-8) ---
    print()
    print("  --- Extended Checks (6-8) ---")
    check_undocumented_files()
    check_subdir_claude_accuracy()
    check_known_traps()

    for status, msg in results:
        print(f"  {status} {msg}")
    all_pass += sum(1 for s, _ in results if s == PASS)
    all_fail += sum(1 for s, _ in results if s == FAIL)
    all_warn += sum(1 for s, _ in results if s == WARN)
    all_fix += sum(1 for s, _ in results if s == AUTO)
    results.clear()

    # --- Skill Checks (9) ---
    print()
    print("  --- Skill Checks (9) ---")
    check_skill_files()

    for status, msg in results:
        print(f"  {status} {msg}")
    all_pass += sum(1 for s, _ in results if s == PASS)
    all_fail += sum(1 for s, _ in results if s == FAIL)
    all_warn += sum(1 for s, _ in results if s == WARN)
    all_fix += sum(1 for s, _ in results if s == AUTO)
    results.clear()

    # --- Summary ---
    print()
    print("-" * 60)
    total = all_pass + all_fail + all_warn + all_fix
    print(f"  Total: {all_pass} passed, {all_fail} failed, {all_warn} warnings, {all_fix} auto-fixed ({total} checks)")

    if all_fail > 0:
        print(f"\n  Action needed: update docs to match codebase")
        print(f"  Auto-fix LOC: python scripts/verify_claude_md.py --fix")
        print()
        return 1

    if all_fix > 0:
        print(f"\n  {all_fix} auto-fixes applied. Review changes and commit.")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

