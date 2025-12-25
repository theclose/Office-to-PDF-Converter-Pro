import os
import sys
import re
import subprocess
import argparse

def bump_version(file_path):
    print(f"Bumping version in {file_path}...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        match = re.search(r'VERSION = "(\d+)\.(\d+)\.(\d+)"', content)
        if not match:
            print(f"Error: VERSION not found in {file_path}")
            return None
        
        major, minor, patch = match.groups()
        new_version = f"{major}.{minor}.{int(patch) + 1}"
        
        new_content = re.sub(
            r'VERSION = "\d+\.\d+\.\d+"',
            f'VERSION = "{new_version}"',
            content
        )
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        print(f"Version bumped to {new_version}")
        return new_version
    except Exception as e:
        print(f"Error bumping version: {e}")
        return None

def git_commit(version, message):
    try:
        # Check status
        # subprocess.run(["git", "status"], check=True)
        
        # Add all changes
        print("Git adding changes...")
        subprocess.run(["git", "add", "-A"], check=True)
        
        # Commit
        commit_msg = f"auto: v{version} - {message}"
        print(f"Committing with message: {commit_msg}")
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        
        print("✅ Auto-save complete!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto save and version bump")
    parser.add_argument("message", help="Commit message")
    args = parser.parse_args()
    
    # Determine path to main_window_pro.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    file_path = os.path.join(root_dir, "ui", "main_window_pro.py")
    
    if not os.path.exists(file_path):
        print(f"Error: Could not find {file_path}")
        sys.exit(1)

    version = bump_version(file_path)
    if version:
        git_commit(version, args.message)
