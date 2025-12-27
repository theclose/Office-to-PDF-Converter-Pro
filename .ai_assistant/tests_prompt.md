# 🧪 Test Generation Request

**Vai trò**: Senior Test Engineer

**Module**: 
**Functions**: 10

## Functions cần test


### clean()
**File**: `build_exe.py:27`
**Docstring**: Clean build artifacts.
```python
def clean():
    """Clean build artifacts."""
    print("🧹 Cleaning build artifacts...")
    
    for folder in [DIST_DIR, BUILD_DIR]:
        if folder.exists():
            shutil.rmtree(folder)
            print(f"  Removed: {folder}")
```


### create_version_info()
**File**: `build_exe.py:45`
**Docstring**: Create version info file for Windows.
```python
def create_version_info():
    """Create version info file for Windows."""
    version_parts = VERSION.split(".")
    major = version_parts[0] if len(version_parts) > 0 else "1"
    minor = version_parts[1] if len(version_parts) > 1 else "0"
    patch = version_parts[2] if len(version_parts) > 2 else "0"
    
    version_info = f'''
```


### get_hidden_imports()
**File**: `build_exe.py:92`
**Docstring**: Get list of hidden imports - comprehensive for all features.
```python
def get_hidden_imports():
    """Get list of hidden imports - comprehensive for all features."""
    return [
        # Core modules
        "office_converter",
        "office_converter.converters",
        "office_converter.converters.excel",
        "office_converter.converters.word",
```


### get_excludes()
**File**: `build_exe.py:193`
**Docstring**: Get modules to exclude for smaller size.
```python
def get_excludes():
    """Get modules to exclude for smaller size."""
    return [
        # Large packages we don't need
        "torch", "scipy", "numpy", "pandas", "matplotlib",
        "sklearn", "scikit-learn", "tensorflow", "keras",
        "cv2", "opencv", "opencv-python",
        "IPython", "ipython", "notebook", "jupyter", "jupyterlab",
```


### get_data_files()
**File**: `build_exe.py:213`
**Docstring**: Get data files to include.
```python
def get_data_files():
    """Get data files to include."""
    data_files = []
    
    # CustomTkinter
    try:
        import customtkinter
        ctk_path = Path(customtkinter.__file__).parent
```


### build()
**File**: `build_exe.py:238`
**Docstring**: Build the executable.
```python
def build():
    """Build the executable."""
    print(f"🔨 Building {APP_NAME} v{VERSION}...")
    print()
    
    # Ensure main script exists
    main_script_path = PROJECT_ROOT / MAIN_SCRIPT
    if not main_script_path.exists():
```


### main()
**File**: `build_exe.py:341`
**Docstring**: Main entry point.
```python
def main():
    """Main entry point."""
    if "--clean" in sys.argv:
        clean()
    elif "--help" in sys.argv:
        print(__doc__)
    else:
        sys.exit(build())
```


### print_step(msg)
**File**: `build_script.py:12`
**Docstring**: Print step with formatting.
```python
def print_step(msg):
    """Print step with formatting."""
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")

def run_command(cmd, description):
    """Run command and handle errors."""
```


### run_command(cmd, description)
**File**: `build_script.py:18`
**Docstring**: Run command and handle errors.
```python
def run_command(cmd, description):
    """Run command and handle errors."""
    print(f"⚙️  {description}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Error: {description} failed")
        print(result.stderr)
```


### main()
**File**: `build_script.py:31`
**Docstring**: No docstring
```python
def main():
    print_step("Office to PDF Converter Pro - EXE Build Script v4.1.6")
    
    # Step 1: Check PyInstaller
    print_step("Step 1: Checking Dependencies")
    
    if not run_command("pyinstaller --version", "Check PyInstaller"):
        print("Installing PyInstaller...")
```



## Yêu cầu

Viết pytest test cases cho mỗi function với:
1. **Happy path**: Input hợp lệ
2. **Edge cases**: None, empty, boundary values
3. **Error handling**: Invalid input

## Output Format

Trả về Python code có thể chạy được:
```python
import pytest
# ... test code
```
