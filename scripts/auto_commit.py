"""
Auto-commit script with version bump
Usage: python scripts/auto_commit.py "commit message"
"""

import sys
import os
import re
import subprocess
from datetime import datetime

def get_current_version(file_path="ui/main_window_pro.py"):
    """Extract current version from code."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        match = re.search(r'VERSION\s*=\s*"(\d+\.\d+\.\d+)"', content)
        if match:
            return match.group(1)
    return None

def bump_version(version, bump_type='patch'):
    """Bump version number."""
    major, minor, patch = map(int, version.split('.'))
    
    if bump_type == 'major':
        return f"{major + 1}.0.0"
    elif bump_type == 'minor':
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"

def update_version_in_file(new_version, file_path="ui/main_window_pro.py"):
    """Update VERSION in code."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = re.sub(
        r'VERSION\s*=\s*"\d+\.\d+\.\d+"',
        f'VERSION = "{new_version}"',
        content
    )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✓ Updated version to {new_version}")

def git_commit(message, new_version):
    """Stage all changes and commit."""
    # Stage all changes
    subprocess.run(['git', 'add', '-A'], check=True)
    
    # Commit with auto prefix
    full_message = f"auto: v{new_version} - {message}"
    subprocess.run(['git', 'commit', '-m', full_message], check=True)
    
    print(f"✓ Committed: {full_message}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/auto_commit.py \"commit message\"")
        print("Example: python scripts/auto_commit.py \"feat: Add new feature\"")
        sys.exit(1)
    
    commit_msg = sys.argv[1]
    bump_type = sys.argv[2] if len(sys.argv) > 2 else 'patch'
    
    # Get current version
    current_version = get_current_version()
    if not current_version:
        print("❌ Could not find VERSION in code")
        sys.exit(1)
    
    print(f"Current version: {current_version}")
    
    # Bump version
    new_version = bump_version(current_version, bump_type)
    print(f"New version: {new_version}")
    
    # Update version in code
    update_version_in_file(new_version)
    
    # Commit
    git_commit(commit_msg, new_version)
    
    print(f"\n🎉 Success! Version bumped to v{new_version} and committed.")

if __name__ == "__main__":
    main()
