"""
Enhanced AI Test Generator v3.0 - Coverage Integration
=======================================================
New in v3.0:
- ✅ Coverage Integration - Direct pytest-cov integration
- ✅ Smart Prioritization - Test complex functions first
- ✅ AI Learning - Learn from existing test patterns

Usage:
    python generate_tests_v3.py --coverage-only
    python generate_tests_v3.py --prioritize
    python generate_tests_v3.py --learn
"""

import os
import sys
import ast
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import argparse
import subprocess


@dataclass
class FunctionSignature:
    """Enhanced function signature with coverage and priority info."""
    name: str
    file: str
    line: int
    args: List[Tuple[str, Optional[str]]]
    return_type: Optional[str]
    docstring: Optional[str]
    complexity: int
    is_async: bool
    decorators: List[str]
    hash: str
    coverage: float = 0.0  # NEW: Coverage percentage
    priority_score: float = 0.0  # NEW: Priority score


class CoverageIntegrator:
    """Direct pytest-cov integration for coverage-aware test generation."""
    
    def __init__(self, cov_file: str = ".coverage"):
        self.cov_file = Path(cov_file)
        self.coverage_data = None
        self.has_coverage = False
        
    def load_coverage(self) -> bool:
        """Load pytest-cov coverage data."""
        try:
            import coverage
            if not self.cov_file.exists():
                print("⚠️ No .coverage file found. Run: pytest --cov=. first")
                return False
                
            cov = coverage.Coverage(data_file=str(self.cov_file))
            cov.load()
            self.coverage_data = cov.get_data()
            self.has_coverage = True
            print(f"✅ Loaded coverage data from {self.cov_file}")
            return True
            
        except ImportError:
            print("⚠️ coverage not installed. Run: pip install coverage")
            return False
        except Exception as e:
            print(f"⚠️ Error loading coverage: {e}")
            return False
            
    def get_function_coverage(self, file_path: str, line_start: int, line_end: int) -> float:
        """Get coverage % for a specific function."""
        if not self.has_coverage:
            return 0.0
            
        # Get executed lines for this file
        executed = set(self.coverage_data.lines(file_path) or [])
        
        # Get lines in function range
        function_lines = set(range(line_start, line_end + 1))
        
        # Calculate coverage
        covered = len(function_lines & executed)
        total = len(function_lines)
        
        return (covered / total * 100) if total > 0 else 0.0
        
    def get_file_coverage(self, file_path: str) -> float:
        """Get overall coverage % for a file."""
        if not self.has_coverage:
            return 0.0
            
        executed = len(self.coverage_data.lines(file_path) or [])
        
        # Count total lines (exclude empty/comments)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f.readlines()]
            total = len([l for l in lines if l and not l.startswith('#')])
        except:
            total = 0
            
        return (executed / total * 100) if total > 0 else 0.0
        
    def filter_untested_functions(self, functions: List[FunctionSignature], threshold: float = 80.0) -> List[FunctionSignature]:
        """Filter functions that need more test coverage."""
        if not self.has_coverage:
            return functions
            
        untested = []
        for func in functions:
            # Calculate function coverage
            func.coverage = self.get_function_coverage(func.file, func.line, func.line + 20)  # Estimate 20 lines
            
            if func.coverage < threshold:
                untested.append(func)
                
        return untested
        
    def generate_coverage_report(self, functions: List[FunctionSignature]) -> Dict[str, Any]:
        """Generate coverage report."""
        report = {
            'total_functions': len(functions),
            'untested': len([f for f in functions if f.coverage < 50]),
            'partial': len([f for f in functions if 50 <= f.coverage < 80]),
            'covered': len([f for f in functions if f.coverage >= 80]),
            'avg_coverage': sum(f.coverage for f in functions) / len(functions) if functions else 0
        }
        return report


class SmartPrioritizer:
    """Prioritize functions based on complexity, coverage, and other metrics."""
    
    WEIGHTS = {
        'complexity': 0.35,
        'coverage_gap': 0.30,  # How much coverage is missing
        'public_api': 0.15,
        'loc': 0.10,
        'decorators': 0.10,
    }
    
    def prioritize(self, functions: List[FunctionSignature]) -> List[FunctionSignature]:
        """Sort functions by priority score (high to low)."""
        # Calculate scores
        for func in functions:
            func.priority_score = self._calculate_priority(func)
            
        # Sort by score
        functions.sort(key=lambda f: f.priority_score, reverse=True)
        return functions
        
    def _calculate_priority(self, func: FunctionSignature) -> float:
        """Calculate priority score (0-1)."""
        score = 0.0
        
        # Complexity (normalize to 0-1, cap at 20)
        complexity_score = min(func.complexity / 20.0, 1.0)
        score += complexity_score * self.WEIGHTS['complexity']
        
        # Coverage gap (0% = highest priority)
        coverage_gap = (100 - func.coverage) / 100.0
        score += coverage_gap * self.WEIGHTS['coverage_gap']
        
        # Public API bonus
        if not func.name.startswith('_'):
            score += self.WEIGHTS['public_api']
            
        # Decorators (property, staticmethod, etc. are important)
        if func.decorators:
            score += self.WEIGHTS['decorators']
            
        return min(score, 1.0)


class TestPatternLearner:
    """Learn test patterns from existing test suite."""
    
    def __init__(self, test_dir: str = "tests"):
        self.test_dir = Path(test_dir)
        self.patterns = {
            'assertions': {},
            'fixtures': set(),
            'decorators': {},
            'imports': set(),
        }
        
    def learn_from_tests(self) -> Dict[str, Any]:
        """Analyze existing tests to extract patterns."""
        if not self.test_dir.exists():
            print(f"⚠️ Test directory {self.test_dir} not found")
            return self.patterns
            
        test_files = list(self.test_dir.glob("test_*.py"))
        
        for test_file in test_files:
            try:
                self._analyze_test_file(test_file)
            except Exception as e:
                print(f"Error analyzing {test_file}: {e}")
                
        return self.patterns
        
    def _analyze_test_file(self, file_path: Path):
        """Extract patterns from a test file."""
        content = file_path.read_text(encoding='utf-8')
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            # Learn assertion patterns
            if isinstance(node, ast.Assert):
                try:
                    pattern = ast.unparse(node.test)
                    self.patterns['assertions'][pattern] = \
                        self.patterns['assertions'].get(pattern, 0) + 1
                except:
                    pass
                    
            # Learn fixtures
            if isinstance(node, ast.FunctionDef):
                for dec in node.decorator_list:
                    try:
                        dec_str = ast.unparse(dec)
                        if 'fixture' in dec_str:
                            self.patterns['fixtures'].add(node.name)
                        if 'parametrize' in dec_str:
                            self.patterns['decorators'][node.name] = dec_str
                    except:
                        pass
                        
            # Learn imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                try:
                    self.patterns['imports'].add(ast.unparse(node))
                except:
                    pass
                    
    def suggest_assertion(self, func: FunctionSignature) -> str:
        """Suggest best assertion based on learned patterns."""
        # Use most common assertion
        if self.patterns['assertions']:
            most_common = max(self.patterns['assertions'].items(), key=lambda x: x[1])
            return f"assert {most_common[0]}"
        
        # Fallback based on return type
        if func.return_type:
            if 'bool' in func.return_type.lower():
                return "assert result is True"
            elif 'list' in func.return_type.lower():
                return "assert len(result) >= 0"
            elif 'dict' in func.return_type.lower():
                return "assert isinstance(result, dict)"
                
        return "assert result is not None"


# Import only utilities from v2.0, NOT dataclasses
import sys
from pathlib import Path as PathLib
sys.path.insert(0, str(PathLib(__file__).parent))

from generate_tests_v2 import SmartTestCache, TestTemplateEngine


class SmartASTAnalyzerV3:
    """v3.0-native AST analyzer using v3.0 FunctionSignature."""
    
    def analyze_file(self, file_path: str) -> List[FunctionSignature]:
        """Analyze file and extract function signatures."""
        functions = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content)
            
            for node in list(ast.walk(tree)):  # Use list() to avoid dict iteration errors
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_sig = self._extract_signature(node, file_path, content)
                    if func_sig:
                        functions.append(func_sig)
                        
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            
        return functions
        
    def _extract_signature(self, node: ast.FunctionDef, file_path: str, content: str) -> Optional[FunctionSignature]:
        """Extract detailed function signature using v3.0 FunctionSignature."""
        # Skip private methods (except __init__)
        if node.name.startswith('_') and node.name != '__init__':
            return None
            
        # Extract args with type hints
        args = []
        for arg in node.args.args:
            if arg.arg == 'self' or arg.arg == 'cls':
                continue
            type_hint = None
            if arg.annotation:
                try:
                    type_hint = ast.unparse(arg.annotation)
                except:
                    pass
            args.append((arg.arg, type_hint))
            
        # Extract return type
        return_type = None
        if node.returns:
            try:
                return_type = ast.unparse(node.returns)
            except:
                pass
                
        # Extract decorators
        decorators = []
        for dec in node.decorator_list:
            try:
                decorators.append(ast.unparse(dec))
            except:
                pass
                
        # Estimate complexity
        complexity = self._estimate_complexity(node)
        
        # Get docstring
        docstring = ast.get_docstring(node)
        
        # Compute hash
        content = f"{node.name}:{args}:{return_type}"
        hash_value = hashlib.md5(content.encode()).hexdigest()
        
        # Create v3.0 FunctionSignature with ALL fields
        func_sig = FunctionSignature(
            name=node.name,
            file=file_path,
            line=node.lineno,
            args=args,
            return_type=return_type,
            docstring=docstring,
            complexity=complexity,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            decorators=decorators,
            hash=hash_value,
            coverage=0.0,  # v3.0 field
            priority_score=0.0  # v3.0 field
        )
        
        return func_sig
        
    def _estimate_complexity(self, node: ast.FunctionDef) -> int:
        """Estimate cyclomatic complexity."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity


class EnhancedTestGeneratorV3:
    """v3.0 Generator with coverage, prioritization, and learning."""
    
    def __init__(self, 
                 use_cache: bool = True,
                 parallel: int = 1,
                 coverage_aware: bool = False,
                 prioritize: bool = False,
                 learn_patterns: bool = False):
        self.cache = SmartTestCache() if use_cache else None
        self.parallel = parallel
        self.template_engine = TestTemplateEngine()
        self.analyzer = SmartASTAnalyzerV3()  # Use v3.0-native analyzer
        
        # v3.0 features
        self.coverage = CoverageIntegrator() if coverage_aware else None
        self.prioritizer = SmartPrioritizer() if prioritize else None
        self.learner = TestPatternLearner() if learn_patterns else None
        
        self.stats = {
            'cached': 0,
            'generated': 0,
            'skipped': 0,
            'prioritized': 0,
            'learned_patterns': 0,
        }
        
    def initialize(self):
        """Initialize v3.0 features."""
        if self.coverage:
            self.coverage.load_coverage()
            
        if self.learner:
            patterns = self.learner.learn_from_tests()
            self.stats['learned_patterns'] = len(patterns.get('assertions', {}))
            if self.stats['learned_patterns'] > 0:
                print(f"🧠 Learned {self.stats['learned_patterns']} test patterns")
                
    def generate_tests_parallel(self, files: List[str], output_dir: str) -> Dict[str, str]:
        """Generate tests with v3.0 enhancements."""
        # Same as v2.0 but with coverage filtering and prioritization
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        results = {}
        
        if self.parallel > 1:
            with ThreadPoolExecutor(max_workers=self.parallel) as executor:
                futures = {
                    executor.submit(self._generate_for_file, f, output_dir): f 
                    for f in files
                }
                
                for future in as_completed(futures):
                    file_path = futures[future]
                    try:
                        test_file = future.result()
                        if test_file:
                            results[file_path] = test_file
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")
        else:
            for file_path in files:
                test_file = self._generate_for_file(file_path, output_dir)
                if test_file:
                    results[file_path] = test_file
                    
        return results
        
    def _generate_for_file(self, file_path: str, output_dir: str) -> Optional[str]:
        """Generate tests with coverage and priority awareness."""
        # Analyze file
        functions = self.analyzer.analyze_file(file_path)
        
        if not functions:
            self.stats['skipped'] += 1
            return None
            
        # v3.0: Filter by coverage
        if self.coverage and self.coverage.has_coverage:
            original_count = len(functions)
            functions = self.coverage.filter_untested_functions(functions, threshold=80.0)
            print(f"   📊 Coverage: {len(functions)}/{original_count} need tests")
            
        # Filter cached
        if self.cache:
            untested = [f for f in functions if not self.cache.is_tested(f)]
            self.stats['cached'] += len(functions) - len(untested)
            functions = untested
            
        if not functions:
            return None
            
        # v3.0: Prioritize
        if self.prioritizer:
            functions = self.prioritizer.prioritize(functions)
            self.stats['prioritized'] += len(functions)
            print(f"   ⚡ Prioritized: Top function has score {functions[0].priority_score:.2f}")
            
        # Generate tests
        test_code = self._generate_test_code(functions, file_path)
        
        # Write
        module_name = Path(file_path).stem
        test_file = Path(output_dir) / f"test_generated_{module_name}_v3.py"
        
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_code)
            
        # Update cache
        if self.cache:
            for func in functions:
                self.cache.mark_tested(func, str(test_file))
            self.cache.save()
            
        self.stats['generated'] += len(functions)
        return str(test_file)
        
    def _generate_test_code(self, functions: List[FunctionSignature], source_file: str) -> str:
        """Generate test code (same as v2.0 for now)."""
        lines = [
            '"""',
            f'Auto-generated tests for {Path(source_file).stem} (v3.0 - AI Enhanced)',
            f'Generated: {datetime.now().isoformat()}',
            'Generator: Coverage-Aware + Smart Prioritized + Pattern Learned',
            '"""',
            '',
            'import pytest',
            'from unittest.mock import Mock, patch, MagicMock',
            '',
            f'# Import from {source_file}',
            f'# TODO: Adjust import path',
            '',
        ]
        
        for func in functions:
            template_type = self.template_engine.infer_template_type(func)
            test_code = self.template_engine.generate_from_template(func, template_type)
            
            # Add metadata
            docstring_safe = ""
            if func.docstring:
                docstring_safe = func.docstring.replace('\n', ' ').replace('\r', '')[:60]
                
            lines.append(f'# Test for {func.name} (complexity: {func.complexity}, coverage: {func.coverage:.0f}%, priority: {func.priority_score:.2f})')
            if docstring_safe:
                lines.append(f'# Doc: {docstring_safe}...')
            lines.append(test_code)
            lines.append('')
            
        return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description="AI Test Generator v3.0")
    parser.add_argument("--src", default="core", help="Source directory")
    parser.add_argument("--output", default="tests", help="Output directory")
    parser.add_argument("--parallel", type=int, default=4, help="Parallel workers")
    parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    
    # v3.0 flags
    parser.add_argument("--coverage-only", action="store_true", help="Only generate for untested code")
    parser.add_argument("--prioritize", action="store_true", help="Prioritize complex functions")
    parser.add_argument("--learn", action="store_true", help="Learn from existing tests")
    
    args = parser.parse_args()
    
    project_root = Path(".").absolute()
    src_dir = project_root / args.src
    
    print("=" * 70)
    print("🚀 AI TEST GENERATOR V3.0")
    print("=" * 70)
    print(f"Source: {src_dir}")
    print(f"Features: Coverage={args.coverage_only}, Prioritize={args.prioritize}, Learn={args.learn}")
    print("=" * 70)
    
    # Find files
    files = list(src_dir.glob("**/*.py"))
    files = [str(f) for f in files if "__pycache__" not in str(f)]
    
    print(f"\n📁 Found {len(files)} Python files")
    
    # Initialize generator
    generator = EnhancedTestGeneratorV3(
        use_cache=not args.no_cache,
        parallel=args.parallel,
        coverage_aware=args.coverage_only,
        prioritize=args.prioritize,
        learn_patterns=args.learn
    )
    
    generator.initialize()
    
    # Generate
    import time
    start = time.time()
    
    results = generator.generate_tests_parallel(files, args.output)
    
    elapsed = time.time() - start
    
    print(f"\n{'='*70}")
    print("📊 GENERATION COMPLETE")
    print(f"{'='*70}")
    print(f"✅ Generated: {generator.stats['generated']} test functions")
    print(f"💾 Cached: {generator.stats['cached']} (skipped)")
    if args.prioritize:
        print(f"⚡ Prioritized: {generator.stats['prioritized']} functions")
    if args.learn:
        print(f"🧠 Learned: {generator.stats['learned_patterns']} patterns")
    print(f"⏭️  Skipped: {generator.stats['skipped']} files")
    print(f"📄 Test files: {len(results)}")
    print(f"⚡ Time: {elapsed:.2f}s")
    if generator.stats['generated'] > 0:
        print(f"🚀 Speed: {generator.stats['generated']/elapsed:.1f} tests/sec")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
