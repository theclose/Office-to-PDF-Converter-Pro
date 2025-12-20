"""
Post-Code Check Script for Office Converter
============================================
Run: python scripts/check_code.py [--quick] [--fix]
"""

import subprocess
import sys
import os
import time
from pathlib import Path

# ==============================================================================
# Configuration for Office Converter
# ==============================================================================
CHECK_DIRS = ["converters", "ui", "utils", "core", "tests"]
CRITICAL_FILES = ["main.py", "run_pro.py", "build_exe.py"]
QUICK_TESTS = ["tests/"]

# ==============================================================================
# Colors
# ==============================================================================
try:
    import colorama
    colorama.init()
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
except ImportError:
    GREEN = YELLOW = RED = CYAN = BOLD = RESET = ""


def print_header(title: str) -> None:
    print(f"\n{CYAN}{BOLD}{'='*60}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{BOLD}{'='*60}{RESET}\n")


def print_result(name: str, success: bool, duration: float) -> None:
    status = f"{GREEN}✓ PASS{RESET}" if success else f"{RED}✗ FAIL{RESET}"
    print(f"  {name:<30} {status}  ({duration:.2f}s)")


def run_command(cmd: list, capture: bool = True) -> tuple:
    start = time.time()
    try:
        result = subprocess.run(cmd, capture_output=capture, text=True, timeout=300)
        return result.returncode == 0, result.stdout + result.stderr if capture else "", time.time() - start
    except Exception as e:
        return False, str(e), time.time() - start


# ==============================================================================
# Check Functions
# ==============================================================================

def check_syntax() -> tuple:
    files = []
    for d in CHECK_DIRS:
        if os.path.isdir(d):
            for f in Path(d).rglob("*.py"):
                files.append(str(f))
    files.extend([f for f in CRITICAL_FILES if os.path.exists(f)])
    
    if not files:
        return True, "No files", 0
    
    cmd = ["python", "-m", "py_compile"] + files[:50]
    return run_command(cmd)


def check_ruff(fix: bool = False) -> tuple:
    dirs = [d for d in CHECK_DIRS if os.path.isdir(d)]
    cmd = ["ruff", "check"] + dirs
    if fix:
        cmd.append("--fix")
    cmd.extend(["--select", "E,F,W"])
    return run_command(cmd)


def check_imports() -> tuple:
    start = time.time()
    try:
        import importlib
        modules = ["converters.word", "converters.excel", "utils.file_utils"]
        for mod in modules:
            importlib.import_module(mod)
        return True, "OK", time.time() - start
    except Exception as e:
        return False, str(e), time.time() - start


def check_tests() -> tuple:
    cmd = ["pytest", "tests/", "-q", "--tb=line", "-x"]
    return run_command(cmd)


# ==============================================================================
# Main
# ==============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Office Converter code checks")
    parser.add_argument("--quick", action="store_true", help="Quick mode")
    parser.add_argument("--fix", action="store_true", help="Auto-fix ruff issues")
    parser.add_argument("--no-test", action="store_true", help="Skip pytest")
    args = parser.parse_args()
    
    print_header("OFFICE CONVERTER CHECK" + (" (Quick)" if args.quick else ""))
    
    results = []
    total_start = time.time()
    
    # 1. Syntax
    print(f"{BOLD}1. Syntax Check{RESET}")
    success, output, duration = check_syntax()
    results.append(("Syntax", success, duration))
    print_result("py_compile", success, duration)
    
    # 2. Imports
    print(f"\n{BOLD}2. Import Check{RESET}")
    success, output, duration = check_imports()
    results.append(("Imports", success, duration))
    print_result("Converters", success, duration)
    
    # 3. Ruff
    print(f"\n{BOLD}3. Ruff Linting{RESET}")
    success, output, duration = check_ruff(fix=args.fix)
    results.append(("Ruff", success, duration))
    print_result("Ruff", success, duration)
    if not success:
        for line in output.strip().split("\n")[:5]:
            print(f"    {line}")
    
    # 4. Tests
    if not args.no_test:
        print(f"\n{BOLD}4. Pytest{RESET}")
        success, output, duration = check_tests()
        results.append(("Tests", success, duration))
        print_result("Pytest", success, duration)
    
    # Summary
    total_duration = time.time() - total_start
    passed = sum(1 for _, s, _ in results if s)
    failed = len(results) - passed
    
    print_header("SUMMARY")
    print(f"  Total:   {len(results)} checks")
    print(f"  Passed:  {GREEN}{passed}{RESET}")
    print(f"  Failed:  {RED if failed else ''}{failed}{RESET}")
    print(f"  Time:    {total_duration:.2f}s")
    
    if failed == 0:
        print(f"\n{GREEN}{BOLD}✓ All checks passed!{RESET}")
        return 0
    else:
        print(f"\n{RED}{BOLD}✗ {failed} check(s) failed{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
