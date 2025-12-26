"""
Performance Benchmarks for Office Converter
============================================
Measures critical path performance to detect regressions.

Usage:
    pytest tests/test_benchmarks.py --benchmark-only
    pytest tests/test_benchmarks.py --benchmark-compare
    pytest tests/test_benchmarks.py --benchmark-autosave
"""

import pytest
import time
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

# Import components to benchmark
from converters.base import get_converter_for_file, get_best_converter
from core.file_tools import FileToolsEngine, CaseRule, ReplaceRule
from utils.config import Config


# ==================== Converter Benchmarks ====================

class TestConverterPerformance:
    """Benchmark converter selection and initialization."""
    
    def test_benchmark_get_converter_for_file(self, benchmark):
        """Benchmark converter lookup speed."""
        result = benchmark(get_converter_for_file, "document.xlsx")
        assert result is not None
        
    def test_benchmark_get_best_converter(self, benchmark):
        """Benchmark best converter selection."""
        result = benchmark(get_best_converter, "document.docx")
        assert result is not None
        
    @pytest.mark.parametrize("extension", [
        ".xlsx", ".docx", ".pptx", ".odt", ".ods", ".odp"
    ])
    def test_benchmark_multiple_extensions(self, benchmark, extension):
        """Benchmark lookup across different file types."""
        result = benchmark(get_converter_for_file, f"file{extension}")
        
    def test_benchmark_converter_factory_pattern(self, benchmark):
        """Benchmark repeated converter instantiation."""
        def create_converters():
            converters = []
            for ext in [".xlsx", ".docx", ".pptx"]:
                conv_class = get_converter_for_file(f"file{ext}")
                if conv_class:
                    converters.append(conv_class())
            return converters
            
        result = benchmark(create_converters)
        assert len(result) > 0


# ==================== File Tools Benchmarks ====================

class TestFileToolsPerformance:
    """Benchmark file renaming operations."""
    
    @pytest.fixture
    def engine(self):
        """Create FileToolsEngine."""
        return FileToolsEngine()
        
    @pytest.fixture
    def temp_files(self, tmp_path):
        """Create temporary test files."""
        files = []
        for i in range(100):
            f = tmp_path / f"test_file_{i}.txt"
            f.write_text(f"content {i}")
            files.append(str(f))
        return files
        
    def test_benchmark_case_conversion(self, benchmark, engine, temp_files):
        """Benchmark case conversion on many files."""
        rule = CaseRule(case_type="upper")
        
        def apply_case():
            return engine.preview_changes(temp_files[:10], [rule])
            
        result = benchmark(apply_case)
        assert len(result) == 10
        
    def test_benchmark_replace_operation(self, benchmark, engine, temp_files):
        """Benchmark text replacement."""
        rule = ReplaceRule(search="test", replace="demo")
        
        def apply_replace():
            return engine.preview_changes(temp_files[:10], [rule])
            
        result = benchmark(apply_replace)
        assert len(result) == 10
        
    def test_benchmark_batch_rename_100_files(self, benchmark, engine, temp_files):
        """Benchmark batch renaming 100 files."""
        rules = [
            CaseRule(case_type="lower"),
            ReplaceRule(search="_", replace="-")
        ]
        
        def batch_rename():
            return engine.preview_changes(temp_files, rules)
            
        result = benchmark(batch_rename)
        assert len(result) == 100
        
    def test_benchmark_rule_chain_complexity(self, benchmark, engine, temp_files):
        """Benchmark complex rule chains."""
        rules = [
            CaseRule(case_type="title"),
            ReplaceRule(search="file", replace="document"),
            ReplaceRule(search="_", replace=" "),
            CaseRule(case_type="lower"),
        ]
        
        def complex_chain():
            return engine.preview_changes(temp_files[:20], rules)
            
        result = benchmark(complex_chain)


# ==================== Config Benchmarks ====================

class TestConfigPerformance:
    """Benchmark configuration operations."""
    
    def test_benchmark_config_load(self, benchmark, tmp_path):
        """Benchmark config file loading."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"quality": 95, "output_dir": "/tmp"}')
        
        def load_config():
            Config._initialized = False
            Config._instance = None
            config = Config(str(config_file))
            config.load()
            return config
            
        result = benchmark(load_config)
        
    def test_benchmark_config_save(self, benchmark, tmp_path):
        """Benchmark config file saving."""
        config_file = tmp_path / "config.json"
        
        def save_config():
            Config._initialized = False
            Config._instance = None
            config = Config(str(config_file))
            config.set("test_key", "test_value")
            config.save()
            return config
            
        result = benchmark(save_config)
        
    def test_benchmark_config_get_set_operations(self, benchmark, tmp_path):
        """Benchmark rapid get/set operations."""
        config_file = tmp_path / "config.json"
        Config._initialized = False
        Config._instance = None
        config = Config(str(config_file))
        
        def rapid_get_set():
            for i in range(100):
                config.set(f"key_{i}", f"value_{i}")
                config.get(f"key_{i}")
                
        benchmark(rapid_get_set)


# ==================== Grid/Queue Benchmarks ====================

class TestQueuePerformance:
    """Benchmark queue operations."""
    
    def test_benchmark_queue_enqueue_dequeue(self, benchmark):
        """Benchmark queue operations."""
        import queue
        
        def queue_ops():
            q = queue.Queue()
            for i in range(1000):
                q.put(i)
            items = []
            while not q.empty():
                items.append(q.get())
            return items
            
        result = benchmark(queue_ops)
        assert len(result) == 1000
        
    def test_benchmark_priority_queue(self, benchmark):
        """Benchmark priority queue sorting."""
        import queue
        
        def priority_ops():
            pq = queue.PriorityQueue()
            for i in range(100):
                pq.put((i % 5, f"task_{i}"))  # 5 priority levels
            items = []
            while not pq.empty():
                items.append(pq.get())
            return items
            
        result = benchmark(priority_ops)
        assert len(result) == 100


# ==================== I/O Benchmarks ====================

class TestIOPerformance:
    """Benchmark file I/O operations."""
    
    def test_benchmark_file_read_small(self, benchmark, tmp_path):
        """Benchmark reading small files."""
        test_file = tmp_path / "small.txt"
        test_file.write_text("x" * 1024)  # 1KB
        
        def read_file():
            return test_file.read_text()
            
        result = benchmark(read_file)
        
    def test_benchmark_file_read_medium(self, benchmark, tmp_path):
        """Benchmark reading medium files."""
        test_file = tmp_path / "medium.txt"
        test_file.write_text("x" * (1024 * 100))  # 100KB
        
        def read_file():
            return test_file.read_text()
            
        result = benchmark(read_file)
        
    def test_benchmark_file_write(self, benchmark, tmp_path):
        """Benchmark file writing."""
        test_file = tmp_path / "output.txt"
        data = "x" * (1024 * 10)  # 10KB
        
        def write_file():
            test_file.write_text(data)
            
        benchmark(write_file)
        
    def test_benchmark_directory_listing(self, benchmark, tmp_path):
        """Benchmark directory scanning."""
        # Create 100 files
        for i in range(100):
            (tmp_path / f"file_{i}.txt").write_text("test")
            
        def list_dir():
            return list(tmp_path.glob("*.txt"))
            
        result = benchmark(list_dir)
        assert len(result) == 100


# ==================== Memory Benchmarks ====================

class TestMemoryPerformance:
    """Benchmark memory-intensive operations."""
    
    def test_benchmark_large_list_operations(self, benchmark):
        """Benchmark list operations on large datasets."""
        def list_ops():
            data = list(range(10000))
            filtered = [x for x in data if x % 2 == 0]
            mapped = [x * 2 for x in filtered]
            return sum(mapped)
            
        result = benchmark(list_ops)
        
    def test_benchmark_dict_operations(self, benchmark):
        """Benchmark dictionary operations."""
        def dict_ops():
            d = {f"key_{i}": i for i in range(1000)}
            lookups = [d.get(f"key_{i}") for i in range(1000)]
            return sum(l for l in lookups if l is not None)
            
        result = benchmark(dict_ops)
        
    def test_benchmark_string_concatenation(self, benchmark):
        """Benchmark string building methods."""
        def string_concat():
            # Compare join vs +=
            parts = [f"part_{i}" for i in range(1000)]
            return "".join(parts)
            
        result = benchmark(string_concat)


# ==================== Regression Detection ====================

class TestPerformanceRegression:
    """Tests to detect performance regressions."""
    
    def test_converter_lookup_under_1ms(self, benchmark):
        """Assert converter lookup is under 1ms."""
        stats = benchmark(get_converter_for_file, "test.xlsx")
        
        # Assert performance requirement
        assert benchmark.stats.stats.mean < 0.001  # 1ms
        
    def test_file_rename_preview_under_100ms(self, benchmark, tmp_path):
        """Assert 100 file preview is under 100ms."""
        engine = FileToolsEngine()
        files = []
        for i in range(100):
            f = tmp_path / f"file_{i}.txt"
            f.write_text("test")
            files.append(str(f))
            
        rule = CaseRule(case_type="upper")
        
        def preview():
            return engine.preview_changes(files, [rule])
            
        benchmark(preview)
        
        # Should be fast for preview (no actual I/O)
        assert benchmark.stats.stats.mean < 0.1  # 100ms


# ==================== Comparison Benchmarks ====================

@pytest.mark.benchmark(group="string-ops")
class TestStringOperationComparison:
    """Compare different string operation approaches."""
    
    def test_string_format_percent(self, benchmark):
        """Benchmark % formatting."""
        def format_percent():
            return "%s-%d-%s" % ("test", 123, "value")
        benchmark(format_percent)
        
    def test_string_format_method(self, benchmark):
        """Benchmark .format() method."""
        def format_method():
            return "{}-{}-{}".format("test", 123, "value")
        benchmark(format_method)
        
    def test_string_format_fstring(self, benchmark):
        """Benchmark f-string."""
        def format_fstring():
            name, num, val = "test", 123, "value"
            return f"{name}-{num}-{val}"
        benchmark(format_fstring)


if __name__ == "__main__":
    # Run benchmarks
    pytest.main([
        __file__,
        "--benchmark-only",
        "--benchmark-autosave",
        "--benchmark-save-data",
        "-v"
    ])
