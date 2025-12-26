"""
Comprehensive Test Suite for AI Test Generator
===============================================
Unit tests and integration tests for generate_tests_v3.py

This tests the test generator itself!
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from generate_tests_v3 import (
    FunctionSignature,
    CoverageIntegrator,
    SmartPrioritizer,
    TestPatternLearner,
    EnhancedTestGeneratorV3
)


# ==================== Unit Tests ====================

class TestFunctionSignature:
    """Test FunctionSignature dataclass."""
    
    def test_create_basic_signature(self):
        """Test creating a basic function signature."""
        sig = FunctionSignature(
            name="test_func",
            file="test.py",
            line=10,
            args=[("x", "int"), ("y", "str")],
            return_type="bool",
            docstring="Test function",
            complexity=3,
            is_async=False,
            decorators=[],
            hash="abc123"
        )
        
        assert sig.name == "test_func"
        assert sig.complexity == 3
        assert sig.coverage == 0.0  # Default
        assert sig.priority_score == 0.0  # Default
        
    def test_signature_with_coverage(self):
        """Test signature with coverage data."""
        sig = FunctionSignature(
            name="func",
            file="test.py",
            line=1,
            args=[],
            return_type=None,
            docstring=None,
            complexity=1,
            is_async=False,
            decorators=[],
            hash="",
            coverage=85.5
        )
        
        assert sig.coverage == 85.5


class TestCoverageIntegrator:
    """Test CoverageIntegrator class."""
    
    @pytest.fixture
    def temp_coverage_file(self, tmp_path):
        """Create temporary .coverage file."""
        cov_file = tmp_path / ".coverage"
        cov_file.touch()
        return cov_file
        
    def test_init_without_coverage_file(self):
        """Test initialization when .coverage doesn't exist."""
        integrator = CoverageIntegrator(cov_file="nonexistent.coverage")
        
        assert integrator.has_coverage == False
        
    def test_load_coverage_missing_file(self, tmp_path):
        """Test loading coverage when file is missing."""
        integrator = CoverageIntegrator(cov_file=str(tmp_path / "missing.coverage"))
        result = integrator.load_coverage()
        
        assert result == False
        assert integrator.has_coverage == False
        
    def test_filter_untested_functions(self):
        """Test filtering functions by coverage threshold."""
        integrator = CoverageIntegrator()
        integrator.has_coverage = False  # Simulate no coverage
        
        functions = [
            FunctionSignature("f1", "test.py", 1, [], None, None, 1, False, [], "", coverage=90),
            FunctionSignature("f2", "test.py", 10, [], None, None, 2, False, [], "", coverage=50),
            FunctionSignature("f3", "test.py", 20, [], None, None, 3, False, [], "", coverage=20),
        ]
        
        # Without coverage data, should return all
        result = integrator.filter_untested_functions(functions, threshold=80)
        assert len(result) == 3
        
    def test_generate_coverage_report(self):
        """Test generating coverage report."""
        integrator = CoverageIntegrator()
        
        functions = [
            FunctionSignature("f1", "test.py", 1, [], None, None, 1, False, [], "", coverage=90),
            FunctionSignature("f2", "test.py", 10, [], None, None, 2, False, [], "", coverage=50),
            FunctionSignature("f3", "test.py", 20, [], None, None, 3, False, [], "", coverage=20),
        ]
        
        report = integrator.generate_coverage_report(functions)
        
        assert report['total_functions'] == 3
        assert report['covered'] == 1  # >= 80%
        assert report['partial'] == 1  # 50-80%
        assert report['untested'] == 1  # < 50%
        assert report['avg_coverage'] == pytest.approx(53.33, 0.1)


class TestSmartPrioritizer:
    """Test SmartPrioritizer class."""
    
    def test_calculate_priority_high_complexity(self):
        """Test priority calculation for high complexity function."""
        prioritizer = SmartPrioritizer()
        
        func = FunctionSignature(
            name="complex_func",
            file="test.py",
            line=1,
            args=[],
            return_type="int",
            docstring="Complex function",
            complexity=15,  # High complexity
            is_async=False,
            decorators=[],
            hash="",
            coverage=0.0  # No coverage
        )
        
        score = prioritizer._calculate_priority(func)
        
        # Should have high priority due to complexity and no coverage
        assert score > 0.5
        
    def test_calculate_priority_public_api(self):
        """Test priority boost for public API."""
        prioritizer = SmartPrioritizer()
        
        public_func = FunctionSignature(
            name="public_method",  # No underscore
            file="test.py",
            line=1,
            args=[],
            return_type=None,
            docstring=None,
            complexity=5,
            is_async=False,
            decorators=[],
            hash="",
            coverage=50.0
        )
        
        private_func = FunctionSignature(
            name="_private_method",  # Underscore
            file="test.py",
            line=10,
            args=[],
            return_type=None,
            docstring=None,
            complexity=5,
            is_async=False,
            decorators=[],
            hash="",
            coverage=50.0
        )
        
        public_score = prioritizer._calculate_priority(public_func)
        private_score = prioritizer._calculate_priority(private_func)
        
        # Public API should have higher priority
        assert public_score > private_score
        
    def test_prioritize_sorting(self):
        """Test that prioritize sorts functions correctly."""
        prioritizer = SmartPrioritizer()
        
        functions = [
            FunctionSignature("low", "test.py", 1, [], None, None, 1, False, [], "", coverage=90),
            FunctionSignature("high", "test.py", 10, [], None, None, 20, False, [], "", coverage=0),
            FunctionSignature("medium", "test.py", 20, [], None, None, 10, False, [], "", coverage=50),
        ]
        
        sorted_funcs = prioritizer.prioritize(functions)
        
        # Should be sorted by priority score (high to low)
        assert sorted_funcs[0].name == "high"
        assert sorted_funcs[-1].name == "low"


class TestPatternLearner:
    """Test TestPatternLearner class."""
    
    @pytest.fixture
    def temp_test_dir(self, tmp_path):
        """Create temporary test directory with sample tests."""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        
        # Create sample test file
        test_file = test_dir / "test_sample.py"
        test_file.write_text("""
import pytest

@pytest.fixture
def my_fixture():
    return 42

def test_something():
    assert True
    assert result is not None
    
def test_other():
    assert len(items) > 0
""")
        
        return test_dir
        
    def test_learn_from_empty_dir(self, tmp_path):
        """Test learning when test dir doesn't exist."""
        learner = TestPatternLearner(test_dir=str(tmp_path / "nonexistent"))
        patterns = learner.learn_from_tests()
        
        assert patterns is not None
        assert len(patterns['assertions']) == 0
        
    def test_learn_assertions(self, temp_test_dir):
        """Test learning assertion patterns."""
        learner = TestPatternLearner(test_dir=str(temp_test_dir))
        patterns = learner.learn_from_tests()
        
        # Should have learned some assertions
        assert len(patterns['assertions']) > 0
        
    def test_learn_fixtures(self, temp_test_dir):
        """Test learning fixture patterns."""
        learner = TestPatternLearner(test_dir=str(temp_test_dir))
        patterns = learner.learn_from_tests()
        
        # Should have found the fixture
        assert 'my_fixture' in patterns['fixtures']
        
    def test_suggest_assertion_bool_return(self):
        """Test assertion suggestion for bool return type."""
        learner = TestPatternLearner(test_dir="tests")
        
        func = FunctionSignature(
            name="is_valid",
            file="test.py",
            line=1,
            args=[],
            return_type="bool",
            docstring=None,
            complexity=1,
            is_async=False,
            decorators=[],
            hash=""
        )
        
        suggestion = learner.suggest_assertion(func)
        
        assert "True" in suggestion or "bool" in suggestion.lower()


# ==================== Integration Tests ====================

class TestEnhancedTestGeneratorV3Integration:
    """Integration tests for full test generator."""
    
    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project structure."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        
        # Create sample source file
        sample_file = src_dir / "sample.py"
        sample_file.write_text("""
def simple_function(x: int) -> int:
    '''Simple function for testing.'''
    return x * 2
    
def complex_function(a, b, c):
    '''Complex function with loops.'''
    result = 0
    for i in range(a):
        if i % 2 == 0:
            for j in range(b):
                result += c
    return result
    
async def async_function():
    '''Async function.'''
    return await some_task()
""")
        
        return {
            'root': tmp_path,
            'src': src_dir,
            'tests': test_dir,
            'sample_file': sample_file
        }
        
    def test_basic_generation(self, temp_project):
        """Test basic test generation workflow."""
        generator = EnhancedTestGeneratorV3(
            use_cache=False,
            parallel=1,
            coverage_aware=False,
            prioritize=False,
            learn_patterns=False
        )
        
        files = [str(temp_project['sample_file'])]
        output_dir = str(temp_project['tests'])
        
        results = generator.generate_tests_parallel(files, output_dir)
        
        # Should have generated a test file
        assert len(results) > 0
        
        # Check test file exists
        test_file = temp_project['tests'] / "test_generated_sample_v3.py"
        assert test_file.exists()
        
        # Check test file has content
        content = test_file.read_text()
        assert "def test_" in content
        assert "pytest" in content
        
    def test_prioritized_generation(self, temp_project):
        """Test generation with prioritization."""
        generator = EnhancedTestGeneratorV3(
            use_cache=False,
            parallel=1,
            prioritize=True
        )
        
        generator.initialize()
        
        files = [str(temp_project['sample_file'])]
        output_dir = str(temp_project['tests'])
        
        results = generator.generate_tests_parallel(files, output_dir)
        
        # Should have prioritized
        assert generator.stats['prioritized'] > 0
        
    def test_pattern_learning(self, temp_project):
        """Test generation with pattern learning."""
        # Create existing test first
        existing_test = temp_project['tests'] / "test_existing.py"
        existing_test.write_text("""
import pytest

def test_example():
    assert result == expected
    assert len(items) > 0
""")
        
        generator = EnhancedTestGeneratorV3(
            use_cache=False,
            parallel=1,
            learn_patterns=True
        )
        
        generator.initialize()
        
        # Should have learned patterns
        assert generator.stats['learned_patterns'] > 0
        
    def test_caching_mechanism(self, temp_project):
        """Test that caching prevents regeneration."""
        generator = EnhancedTestGeneratorV3(
            use_cache=True,
            parallel=1
        )
        
        files = [str(temp_project['sample_file'])]
        output_dir = str(temp_project['tests'])
        
        # First run
        results1 = generator.generate_tests_parallel(files, output_dir)
        generated1 = generator.stats['generated']
        
        # Reset stats
        generator.stats = {'cached': 0, 'generated': 0, 'skipped': 0, 'prioritized': 0, 'learned_patterns': 0}
        
        # Second run (should use cache)
        results2 = generator.generate_tests_parallel(files, output_dir)
        cached2 = generator.stats['cached']
        
        # Should have cached the functions
        assert cached2 > 0


# ==================== Bug Detection Tests ====================

class TestBugDetection:
    """Tests specifically designed to find bugs."""
    
    def test_handles_empty_file(self, tmp_path):
        """Test handling of empty Python file."""
        empty_file = tmp_path / "empty.py"
        empty_file.write_text("")
        
        generator = EnhancedTestGeneratorV3()
        results = generator.generate_tests_parallel([str(empty_file)], str(tmp_path))
        
        # Should not crash
        assert results is not None
        
    def test_handles_syntax_error_file(self, tmp_path):
        """Test handling of file with syntax errors."""
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(:\n    pass")
        
        generator = EnhancedTestGeneratorV3()
        results = generator.generate_tests_parallel([str(bad_file)], str(tmp_path))
        
        # Should not crash, should skip the file
        assert generator.stats['skipped'] > 0
        
    def test_handles_unicode_in_docstring(self, tmp_path):
        """Test handling of Unicode characters in docstrings."""
        unicode_file = tmp_path / "unicode.py"
        unicode_file.write_text("""
def func():
    '''Tính năng đặc biệt với tiếng Việt và emoji 🚀'''
    return True
""", encoding='utf-8')
        
        generator = EnhancedTestGeneratorV3()
        results = generator.generate_tests_parallel([str(unicode_file)], str(tmp_path))
        
        # Should handle Unicode gracefully
        test_file = tmp_path / "test_generated_unicode_v3.py"
        assert test_file.exists()
        
    def test_handles_very_long_function_names(self, tmp_path):
        """Test handling of extremely long function names."""
        long_name = "x" * 200
        long_file = tmp_path / "long.py"
        long_file.write_text(f"def {long_name}():\n    pass\n")
        
        generator = EnhancedTestGeneratorV3()
        results = generator.generate_tests_parallel([str(long_file)], str(tmp_path))
        
        # Should not crash
        assert results is not None
        
    def test_handles_circular_imports(self, tmp_path):
        """Test handling when source has circular imports."""
        file_a = tmp_path / "module_a.py"
        file_b = tmp_path / "module_b.py"
        
        file_a.write_text("from module_b import func_b\ndef func_a(): pass")
        file_b.write_text("from module_a import func_a\ndef func_b(): pass")
        
        generator = EnhancedTestGeneratorV3()
        results = generator.generate_tests_parallel([str(file_a), str(file_b)], str(tmp_path))
        
        # Should handle without infinite loop
        assert results is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
