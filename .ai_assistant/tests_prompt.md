# 🧪 Test Generation Request

**Vai trò**: Senior Test Engineer

**Module**: 
**Functions**: 10

## Functions cần test


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


### run_cmd(cmd, description, safe)
**File**: `deploy_automation.py:11`
**Docstring**: Run command with error handling.
```python
def run_cmd(cmd, description, safe=True):
    """Run command with error handling."""
    print(f"\n{'='*60}")
    print(f"⚙️  {description}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")
    
    if not safe:
```


### main()
**File**: `deploy_automation.py:36`
**Docstring**: No docstring
```python
def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║   Office Converter Pro v4.1.6 - Automated Deployment    ║
╚══════════════════════════════════════════════════════════╝
""")
    
    # Step 1: Pre-Deployment Verification
```


### test_modules()
**File**: `main.py:21`
**Docstring**: Test that all modules load correctly.
```python
def test_modules():
    """Test that all modules load correctly."""
    logger = get_logger("test")
    
    print("=" * 50)
    print("Office Converter - Module Test")
    print("=" * 50)
    
```


### main()
**File**: `run_grid.py:57`
**Docstring**: Main entry point for Autonomous Conversion Grid.
```python
def main():
    """Main entry point for Autonomous Conversion Grid."""
    logger.info("="*60)
    logger.info("Autonomous Conversion Grid - Starting")
    logger.info("="*60)
    
    try:
        # Create grid
```


### run_tests()
**File**: `test_all.py:13`
**Docstring**: No docstring
```python
def run_tests():
    print('=== COMPREHENSIVE TEST ===')
    print()
    errors = []
    
    # Test 1: Config
    print('[1] Config...')
    try:
```


### test_basic_functionality()
**File**: `validate_core.py:19`
**Docstring**: Quick smoke test for core components.
```python
def test_basic_functionality():
    """Quick smoke test for core components."""
    print("=" * 60)
    print("VALIDATION: Core Data Structures")
    print("=" * 60)
    
    # Create test file
    import tempfile
```


### validate()
**File**: `validate_shim.py:19`
**Docstring**: Run comprehensive shim layer validation.
```python
def validate():
    """Run comprehensive shim layer validation."""
    print("=" * 60)
    print("SHIM LAYER VALIDATION")
    print("=" * 60)
    print()
    
    # Step 1: Verify legacy files exist on disk
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
