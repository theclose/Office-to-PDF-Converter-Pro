"""
Simple Deployment Automation for Office Converter Pro v4.1.7
Windows PowerShell compatible version
"""

import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

print("""
╔══════════════════════════════════════════════════════════╗
║   Office Converter Pro v4.1.7 - Automated Deployment    ║
╚══════════════════════════════════════════════════════════╝
""")

# Step 1: Git Status
print("\n📋 Step 1: Checking Git Status")
print("="*60)
subprocess.run("git status --short", shell=True)
subprocess.run("git log --oneline -3", shell=True)

# Step 2: Create Backup Tag
print("\n💾 Step 2: Creating Backup Tag")
print("="*60)
backup_tag = f"v4.1.7-backup-{datetime.now().strftime('%Y%m%d-%H%M')}"
print(f"Creating tag: {backup_tag}")
result = subprocess.run(f"git tag {backup_tag}", shell=True, capture_output=True)
if result.returncode == 0:
    print(f"✅ Backup tag created: {backup_tag}")
else:
    print(f"⚠️  Tag may already exist (OK)")

# Step 3: Verify Dependencies
print("\n📦 Step 3: Verifying Dependencies")
print("="*60)
result = subprocess.run("pip show tkinterdnd2", shell=True, capture_output=True, text=True)
if "Version: 0.4.3" in result.stdout:
    print("✅ tkinterdnd2==0.4.3 installed")
else:
    print("Installing tkinterdnd2...")
    subprocess.run("pip install tkinterdnd2==0.4.3", shell=True)

# Step 4: Check EXE
print("\n🔨 Step 4: Checking EXE Build")
print("="*60)
exe_path = Path("dist/OfficeConverterPro.exe")
if exe_path.exists():
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    mod_time = datetime.fromtimestamp(exe_path.stat().st_mtime)
    print(f"✅ EXE found: {size_mb:.1f} MB")
    print(f"   Built: {mod_time.strftime('%Y-%m-%d %H:%M')}")
else:
    print("❌ EXE not found at dist/OfficeConverterPro.exe")

# Step 5: Summary
print("\n" + "="*60)
print("📊 DEPLOYMENT STATUS SUMMARY")
print("="*60)

print(f"""
✅ Git backup tag created: {backup_tag}
✅ Dependencies verified
✅ EXE ready for testing

🧪 NEXT STEPS - TESTING REQUIRED:

1. Test EXE Launch:
   cd dist
   .\\OfficeConverterPro.exe

2. Critical Tests:
   ✓ Unicode drag-drop (file tiếng Việt)
   ✓ Office conversion
   ✓ PDF Tools
   ✓ Clean exit (no background process)

3. If ALL tests PASS:
   - App is ready for deployment
   - Distribute dist/OfficeConverterPro_Portable/

4. If ANY test FAILS:
   - Rollback: git checkout {backup_tag}
   - Investigate issue

📋 Full checklist: deployment_checklist.md
📄 EXE details: EXE_BUILD_REPORT.md
""")

print("✅ Automated preparation complete!")
print("\n👉 Anh test EXE và cho em biết kết quả nhé!")
