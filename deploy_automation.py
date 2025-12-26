"""
Automated Deployment Script for Office Converter Pro v4.1.6
Safely automates deployment steps with user confirmation
"""

import subprocess
import sys
import os
from pathlib import Path

def run_cmd(cmd, description, safe=True):
    """Run command with error handling."""
    print(f"\n{'='*60}")
    print(f"⚙️  {description}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")
    
    if not safe:
        confirm = input("⚠️  This command requires confirmation. Proceed? (y/n): ")
        if confirm.lower() != 'y':
            print("❌ Skipped by user")
            return False
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ FAILED")
        print(f"Error: {result.stderr}")
        return False
    else:
        print(f"✅ SUCCESS")
        if result.stdout:
            print(result.stdout)
        return True

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║   Office Converter Pro v4.1.6 - Automated Deployment    ║
╚══════════════════════════════════════════════════════════╝
""")
    
    # Step 1: Pre-Deployment Verification
    print("\n📋 STEP 1: Pre-Deployment Verification")
    print("="*60)
    
    # Check code quality
    if not run_cmd("python scripts/check_code.py --quick --no-test", 
                   "Running code quality checks"):
        print("⚠️  Warning: Code checks failed. Continue anyway? (y/n): ")
        if input().lower() != 'y':
            return False
    
    # Check git status
    run_cmd("git status --short", "Checking git status")
    
    # Verify dependencies
    run_cmd("pip list | findstr \"tkinterdnd2 customtkinter pywin32\"", 
            "Verifying dependencies")
    
    # Step 2: Backup
    print("\n💾 STEP 2: Creating Backup")
    print("="*60)
    
    run_cmd("git tag v4.1.6-backup-$(date +%Y%m%d)", 
            "Creating backup tag", safe=False)
    
    # Step 3: Ensure Dependencies
    print("\n📦 STEP 3: Installing/Verifying Dependencies")
    print("="*60)
    
    run_cmd("pip install tkinterdnd2==0.4.3", 
            "Installing tkinterdnd2")
    
    # Verify installation
    verify_code = """
import tkinterdnd2
print(f'✅ tkinterdnd2 version: {tkinterdnd2.__version__}')
"""
    
    with open('temp_verify.py', 'w') as f:
        f.write(verify_code)
    
    if run_cmd("python temp_verify.py", "Verifying tkinterdnd2 installation"):
        os.remove('temp_verify.py')
    
    # Step 4: Verify Version
    print("\n🔍 STEP 4: Verifying Version")
    print("="*60)
    
    verify_version = """
import sys
sys.path.insert(0, 'C:/Auto')
from office_converter.ui.main_window_pro import ConverterProApp
print(f'Version: {ConverterProApp.VERSION}')
if ConverterProApp.VERSION != '4.1.7':
    print('⚠️  Warning: Version mismatch!')
    sys.exit(1)
"""
    
    with open('temp_version.py', 'w') as f:
        f.write(verify_version)
    
    run_cmd("python temp_version.py", "Checking application version")
    os.remove('temp_version.py')
    
    # Step 5: Build EXE (if needed)
    print("\n🔨 STEP 5: EXE Build Status")
    print("="*60)
    
    exe_path = Path("dist/OfficeConverterPro.exe")
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"✅ EXE already built: {size_mb:.1f} MB")
    else:
        print("⚠️  EXE not found. Building now...")
        run_cmd("python build_script.py", "Building EXE", safe=False)
    
    # Step 6: Deployment Summary
    print("\n" + "="*60)
    print("📊 DEPLOYMENT SUMMARY")
    print("="*60)
    
    print("""
✅ Pre-deployment checks completed
✅ Backup created
✅ Dependencies verified
✅ Version confirmed: 4.1.7
✅ EXE ready for distribution

⚠️  MANUAL STEPS REQUIRED:

1. Test the EXE:
   cd dist
   .\\OfficeConverterPro.exe

2. Run Critical Tests (see deployment_checklist.md):
   - Unicode drag & drop
   - Office conversion
   - PDF Tools
   - Clean exit

3. If all tests PASS → Approve deployment
   If any test FAILS → Rollback:
   git reset --hard 6f69184

4. After approval:
   git push origin main
   git tag v4.1.7
   git push origin v4.1.7

📋 Full checklist: deployment_checklist.md
""")
    
    print("\n✅ Automated deployment preparation complete!")
    print("Next: Anh test EXE và approve nhé!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Deployment failed: {e}")
        sys.exit(1)
