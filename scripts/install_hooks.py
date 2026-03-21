"""
install_hooks.py — Install git hooks for CLAUDE.md verification.
Run: python scripts/install_hooks.py

This copies scripts/pre-commit to .git/hooks/pre-commit.
Since .git/hooks/ is NOT tracked by git, this script must be run
once after cloning or by any new developer.
"""

import os
import sys
import shutil
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT / ".git" / "hooks"
SOURCE_HOOK = ROOT / "scripts" / "pre-commit"
TARGET_HOOK = HOOKS_DIR / "pre-commit"


def main():
    print("=" * 50)
    print("  Git Hooks Installer")
    print("=" * 50)
    print()

    # Check .git exists
    if not (ROOT / ".git").exists():
        print("❌ Not a git repository. Run from project root.")
        return 1

    # Check source hook exists
    if not SOURCE_HOOK.exists():
        print(f"❌ Source hook not found: {SOURCE_HOOK}")
        return 1

    # Create hooks dir if needed
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)

    # Check if hook already exists
    if TARGET_HOOK.exists():
        # Read both to compare
        source_content = SOURCE_HOOK.read_text(encoding="utf-8")
        target_content = TARGET_HOOK.read_text(encoding="utf-8")
        if source_content == target_content:
            print("✅ pre-commit hook is already installed and up-to-date")
            return 0
        else:
            print("⚠️ pre-commit hook exists but differs from source")
            print("   Overwriting with latest version...")

    # Copy hook
    shutil.copy2(SOURCE_HOOK, TARGET_HOOK)
    
    # Make executable (important for git on Windows with Git Bash)
    os.chmod(TARGET_HOOK, 0o755)

    print(f"✅ Installed: {TARGET_HOOK}")
    print()
    print("  Hook will run 'python scripts/verify_claude_md.py' before each commit.")
    print("  To bypass: git commit --no-verify")
    print()

    # Verify it works
    print("  Testing hook...")
    result = os.system(f'python "{ROOT / "scripts" / "verify_claude_md.py"}"')
    if result == 0:
        print("\n✅ Hook test passed — ready to use!")
    else:
        print("\n⚠️ Hook test found issues — fix before committing")

    return 0


if __name__ == "__main__":
    sys.exit(main())
