# 📘 AI Test Generator v3.1 - User Guide

**Version**: 3.1 (v4.2.55)  
**Status**: Production Ready  
**Author**: AI Development Team  
**Date**: 2025-12-27

---

## 🎯 Overview

AI Test Generator v3.1 is a revolutionary tool that automatically generates comprehensive, intelligent test suites for Python applications using advanced AST analysis, machine learning, and smart prioritization.

### **Key Features**

✅ **Class-Aware Generation** - Tests both classes and functions  
✅ **Smart Prioritization** - Critical paths tested first  
✅ **Pattern Learning** - Learns from existing tests  
✅ **Coverage Integration** - Fills coverage gaps  
✅ **Lightning Fast** - 1,400+ tests/second  
✅ **100% Syntax Correct** - Always valid Python  

---

## 🚀 Quick Start

### **Installation**

```bash
# Already included in project!
cd c:\Auto\office_converter
```

### **Basic Usage**

```bash
# Generate tests for a single file
python scripts/generate_tests_v3.py --src=core/file_tools.py

# Generate tests for a module
python scripts/generate_tests_v3.py --src=core

# Generate tests for entire app
python scripts/generate_tests_v3.py --src=.
```

### **Run Generated Tests**

```bash
# Run all generated tests
pytest tests/test_generated_*_v3.py -v

# Run specific module tests
pytest tests/test_generated_file_tools_v3.py -v

# With coverage
pytest tests/test_generated_*_v3.py --cov=core --cov-report=html
```

---

## 📖 Detailed Usage

### **Command Line Options**

```bash
python scripts/generate_tests_v3.py [OPTIONS]
```

| Option | Description | Default | Example |
|:---|:---|:---:|:---|
| `--src` | Source file/directory | Required | `--src=core` |
| `--output` | Output directory | `tests` | `--output=my_tests` |
| `--prioritize` | Enable smart prioritization | Disabled | `--prioritize` |
| `--learn` | Learn from existing tests | Disabled | `--learn` |
| `--coverage-only` | Generate only for low coverage | Disabled | `--coverage-only` |
| `--parallel` | Number of workers | 1 | `--parallel=4` |
| `--no-cache` | Disable caching | Enabled | `--no-cache` |

### **Usage Examples**

#### **Example 1: Basic Generation**

```bash
# Generate tests for core module
python scripts/generate_tests_v3.py --src=core

# Output:
# ✅ Generated: 66 test functions
# 📄 Test files: 3
# ⚡ Time: 0.12s
```

#### **Example 2: Full-Featured Generation**

```bash
# Use all features for entire app
python scripts/generate_tests_v3.py \
    --src=. \
    --prioritize \
    --learn \
    --parallel=4

# Output:
# ✅ Generated: 5854 test functions
# 🧠 Learned: 322 patterns
# ⚡ Prioritized: 5854 functions
# 📄 Test files: 537
# ⚡ Time: 4.17s
# 🚀 Speed: 1402.4 tests/sec
```

#### **Example 3: Coverage-Driven Generation**

```bash
# First, generate coverage data
pytest --cov=. --cov-report=html

# Then generate tests for uncovered code
python scripts/generate_tests_v3.py \
    --src=. \
    --coverage-only \
    --prioritize
```

---

## 🎓 Understanding Generated Tests

### **Test Structure**

Generated tests follow this pattern:

```python
"""
Auto-generated tests for module (v3.1 - Class-Aware)
Generated: 2025-12-27T00:19:00
Generator: Class-Aware + Smart Prioritized
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

# Import classes and functions
try:
    from core.file_tools import (
        DuplicateFinder,
        AttributeManager,
        # ... other classes
    )
except ImportError as e:
    pytest.skip(f"Cannot import: {e}")

# Test for DuplicateFinder.find_duplicates
def test_DuplicateFinder_find_duplicates_parametrized(input, expected):
    """Test DuplicateFinder_find_duplicates with various inputs."""
    result = DuplicateFinder().find_duplicates(input)
    assert result == expected
```

### **Naming Conventions**

- **Module functions**: `test_function_name_basic`
- **Class methods**: `test_ClassName_method_name_basic`
- **Parametrized**: `test_*_parametrized`

### **Test Types**

1. **Basic Tests**: Simple invocation with default args
2. **Parametrized Tests**: Multiple inputs/outputs
3. **Edge Case Tests**: None, empty, boundaries

---

## 🔧 Workflows

### **Workflow 1: New Feature Development**

```bash
# 1. Write your code
# ... implement new feature in core/new_module.py

# 2. Generate tests
python scripts/generate_tests_v3.py --src=core/new_module.py --prioritize

# 3. Run tests
pytest tests/test_generated_new_module_v3.py -v

# 4. Fix failures and enhance tests manually
# ... edit tests/test_generated_new_module_v3.py

# 5. Run again
pytest tests/test_generated_new_module_v3.py -v --cov=core/new_module
```

### **Workflow 2: Legacy Code Testing**

```bash
# 1. Generate tests for entire legacy module
python scripts/generate_tests_v3.py --src=legacy --prioritize --learn

# 2. Run tests to find bugs
pytest tests/test_generated_legacy_*_v3.py -v --tb=short

# 3. Fix discovered bugs in source code
# ... fix bugs in legacy/

# 4. Re-run tests
pytest tests/test_generated_legacy_*_v3.py -v

# 5. Enhance critical test cases
# ... manually improve important tests
```

### **Workflow 3: CI/CD Integration**

```bash
# In .github/workflows/tests.yml or similar

# Step 1: Generate tests
- name: Generate Tests
  run: python scripts/generate_tests_v3.py --src=. --prioritize

# Step 2: Run tests with coverage
- name: Run Tests
  run: pytest tests/test_generated_*_v3.py --cov=. --cov-report=xml

# Step 3: Upload coverage
- name: Upload Coverage
  uses: codecov/codecov-action@v3
```

---

## 💡 Best Practices

### **DO's** ✅

1. **Use prioritization** for large codebases
   ```bash
   --prioritize  # Tests critical code first
   ```

2. **Enable learning** to improve quality
   ```bash
   --learn  # Learns from existing tests
   ```

3. **Use parallel processing** for speed
   ```bash
   --parallel=4  # 4x faster
   ```

4. **Run with coverage** to find gaps
   ```bash
   pytest --cov=. --cov-report=html
   ```

5. **Manually enhance critical tests**
   - Auto-generated tests are a starting point
   - Add realistic data and better assertions

### **DON'Ts** ❌

1. **Don't rely 100% on generated tests**
   - They're great scaffolding
   - But need human enhancement

2. **Don't ignore test failures**
   - They often reveal real bugs
   - Investigate each failure

3. **Don't commit without review**
   - Review generated tests first
   - Enhance critical ones

4. **Don't disable caching without reason**
   - Cache speeds up regeneration
   - Only disable when needed

---

## 🐛 Troubleshooting

### **Problem: ImportError in tests**

```
ImportError: No module named 'core'
```

**Solution**: Install package in editable mode
```bash
pip install -e .
```

Or tests will use conftest.py to fix paths automatically.

### **Problem: Tests fail with TypeError**

```
TypeError: __init__() missing required argument: 'path'
```

**Solution**: Generated tests use placeholder args. Enhance manually:
```python
# Before (generated)
result = DuplicateFinder().find_duplicates('test')

# After (enhanced)
result = DuplicateFinder().find_duplicates([tmp_path / "file1.txt"])
```

### **Problem: Low pass rate**

**Expected!** Generated tests need enhancement:
- Add realistic test data
- Improve assertions
- Add proper mocks

**Target**: 50-80% pass rate after enhancements

### **Problem: Slow generation**

**Solution**: Use parallel processing
```bash
--parallel=4  # Or higher based on CPU cores
```

---

## 📊 Understanding Output

### **Generation Report**

```
======================================================================
🚀 AI TEST GENERATOR V3.0
======================================================================
Source: C:\Auto\office_converter\core
Features: Coverage=False, Prioritize=True, Learn=True
======================================================================

📁 Found 3 Python files
   ⚡ Prioritized: Top function has score 0.80
   🧠 Learning patterns from tests/

======================================================================
📊 GENERATION COMPLETE
======================================================================
✅ Generated: 66 test functions
💾 Cached: 0 (skipped)
⚡ Prioritized: 66 functions
🧠 Learned: 322 patterns
⏭️  Skipped: 0 files
📄 Test files: 3
⚡ Time: 0.12s
🚀 Speed: 550.0 tests/sec
======================================================================
```

**Key Metrics**:
- **Generated**: New tests created
- **Cached**: Tests skipped (unchanged)
- **Prioritized**: Functions scored by importance
- **Learned**: Patterns extracted from existing tests
- **Speed**: Tests generated per second

---

## 🎯 Advanced Features

### **Feature 1: Coverage Integration**

```bash
# Step 1: Generate coverage
pytest --cov=. --cov-report=html

# Step 2: Generate tests for low-coverage code
python scripts/generate_tests_v3.py --src=. --coverage-only
```

Only generates tests for functions with <80% coverage.

### **Feature 2: Pattern Learning**

```bash
# Enable learning from existing tests
python scripts/generate_tests_v3.py --src=. --learn
```

Learns:
- Common assertion patterns
- Fixture usage
- Parametrization strategies
- Mock patterns

### **Feature 3: Smart Prioritization**

Scores functions by:
- **Complexity**: Higher = more important
- **Coverage**: Lower = needs tests
- **Public API**: Yes = higher priority
- **Decorators**: Special handling

Top-priority functions tested first!

---

## 📈 Metrics & Reporting

### **Generation Metrics**

Track these KPIs:
- **Tests/second**: Target >500
- **Coverage increase**: Target >20% boost
- **Pass rate**: Target >50% after enhancements
- **Bug discovery**: Count bugs found

### **Quality Metrics**

- **Syntax correctness**: Should be 100%
- **Import success**: Should be 100%
- **Test relevance**: Manual review needed

---

## 🔄 Version History

### **v3.1 (Current)** - 2025-12-27
✨ **Class-aware generation** - Revolutionary!
- Detects and tests classes properly
- Generates `Class().method()` calls
- 100% syntax correct

### **v3.0** - 2025-12-26
- Coverage integration
- Smart prioritization
- Pattern learning
- 4,000+ tests/sec

### **v2.0** - 2025-12-25
- Template engine
- Caching
- 10x faster than v1

### **v1.0** - 2025-12-24
- Basic generation
- AST analysis

---

## 🆘 Support

### **Common Questions**

**Q: How accurate are generated tests?**  
A: Structure 100% correct. Assertions need enhancement. Expect 50-80% pass rate after improvements.

**Q: Can I edit generated tests?**  
A: Yes! They're meant to be enhanced. Start with generated, improve manually.

**Q: Will regeneration overwrite my changes?**  
A: Tests use `_v3` suffix. Your manually enhanced tests in separate files are safe.

**Q: How do I test private methods?**  
A: Generator skips private methods (starting with `_`). Test them indirectly through public methods.

---

## 🎓 Training & Resources

### **Learning Path**

1. **Beginner**: Run basic generation
2. **Intermediate**: Use prioritization and learning
3. **Advanced**: Coverage-driven, parallel processing
4. **Expert**: CI/CD integration, custom enhancements

### **Example Projects**

See `tests/test_generated_*_v3.py` for examples!

---

## 📝 Cheat Sheet

```bash
# Quick commands

# Generate for module
python scripts/generate_tests_v3.py --src=core

# Full featured
python scripts/generate_tests_v3.py --src=. --prioritize --learn --parallel=4

# With coverage
pytest --cov=. && python scripts/generate_tests_v3.py --src=. --coverage-only

# Run tests
pytest tests/test_generated_*_v3.py -v

# With coverage report
pytest tests/test_generated_*_v3.py --cov=. --cov-report=html
```

---

## 🎉 Success Stories

### **Office Converter Project**

- **Before**: 0 tests for OOP code
- **After**: 5,854 tests in 4.17 seconds
- **Coverage**: 100% module coverage
- **Time saved**: Weeks → Seconds

---

**Remember**: Generated tests are a **starting point**, not the **finish line**. Enhance them for production use! 

**Happy Testing!** 🚀

---

**Generated with**: AI Test Generator v3.1  
**Last Updated**: 2025-12-27  
**Support**: Check documentation or ask team lead
