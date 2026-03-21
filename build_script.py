"""
Build script for Office to PDF Converter Pro EXE
Automates the entire build process with optimization
"""

import subprocess
import os
import shutil
import sys
from pathlib import Path

def print_step(msg):
    """Print step with formatting."""
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")

def run_command(cmd, description):
    """Run command and handle errors."""
    print(f"⚙️  {description}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Error: {description} failed")
        print(result.stderr)
        return False
    else:
        print(f"✅ {description} completed")
        return True

def main():
    print_step("Office to PDF Converter Pro - EXE Build Script v4.1.6")
    
    # Step 1: Check PyInstaller
    print_step("Step 1: Checking Dependencies")
    
    if not run_command("pyinstaller --version", "Check PyInstaller"):
        print("Installing PyInstaller...")
        run_command("pip install pyinstaller", "Install PyInstaller")
    
    # Step 2: Clean old builds
    print_step("Step 2: Cleaning Old Builds")
    
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            print(f"🗑️  Removing {folder}/")
            shutil.rmtree(folder)
    
    # Step 3: Build EXE
    print_step("Step 3: Building EXE (This may take 5-10 minutes)")
    
    if not run_command(
        "pyinstaller --clean build_exe.spec",
        "Build EXE with PyInstaller"
    ):
        print("❌ Build failed!")
        return False
    
    # Step 4: Check output
    print_step("Step 4: Verifying Build")
    
    exe_path = Path("dist/OfficeConverterPro.exe")
    
    if not exe_path.exists():
        print(f"❌ EXE not found at {exe_path}")
        return False
    
    # Get file size
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"✅ EXE created successfully!")
    print(f"📦 Location: {exe_path.absolute()}")
    print(f"💾 Size: {size_mb:.1f} MB")
    
    # Step 5: Optional - Create portable package
    print_step("Step 5: Creating Portable Package")
    
    portable_dir = Path("dist/OfficeConverterPro_Portable")
    portable_dir.mkdir(exist_ok=True)
    
    # Copy EXE
    shutil.copy(exe_path, portable_dir / "OfficeConverterPro.exe")
    
    # Create README
    readme = portable_dir / "README.txt"
    readme.write_text("""Office to PDF Converter Pro v4.1.6 - Portable Edition

How to Use:
1. Double-click OfficeConverterPro.exe to launch
2. Drag and drop Office files to convert
3. Choose output settings
4. Click Convert

Features:
- Vietnamese/Unicode filename support
- Batch conversion
- PDF Tools (merge, split, compress, etc.)
- No installation required

System Requirements:
- Windows 10/11
- Microsoft Office installed (for conversions)

Support: TungDo
""", encoding='utf-8')
    
    print(f"✅ Portable package created at: {portable_dir.absolute()}")
    
    print_step("Build Complete!")
    print(f"""
🎉 Success! Your EXE is ready.

📂 Output:
   - Single EXE: dist/OfficeConverterPro.exe
   - Portable:   dist/OfficeConverterPro_Portable/

📊 Next Steps:
   1. Test the EXE: Run dist/OfficeConverterPro.exe
   2. Test drag-drop with Vietnamese filenames
   3. Test PDF Tools dialog
   4. Check clean exit (no background processes)

🚀 If all tests pass, you're ready to distribute!
""")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
