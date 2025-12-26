"""
AI Test Generator - Automated Test Case Generation
===================================================
Reads Python function signatures and docstrings, then automatically
generates test cases using Pytest + Hypothesis patterns.

Features:
- AST parsing to extract function signatures
- Docstring analysis for expected behavior
- Happy path test generation
- Edge case generation (None, empty, boundary values)
- Property-based testing with Hypothesis

Usage:
    python test_generator.py <module_path> [--output=tests/test_generated.py]
    python test_generator.py core/file_tools.py
"""

import ast
import os
import sys
import argparse
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime


@dataclass
class FunctionInfo:
    """Information about a function for test generation."""
    name: str
    args: List[Tuple[str, Optional[str]]]  # (name, type_hint)
    return_type: Optional[str]
    docstring: Optional[str]
    is_method: bool
    class_name: Optional[str]
    decorators: List[str]
    lineno: int
    

@dataclass
class TestCase:
    """Generated test case."""
    test_name: str
    setup: str
    action: str
    assertion: str
    category: str  # happy_path, edge_case, property_based


class FunctionAnalyzer(ast.NodeVisitor):
    """Analyzes Python AST to extract function information."""
    
    def __init__(self):
        self.functions: List[FunctionInfo] = []
        self.current_class: Optional[str] = None
        
    def visit_ClassDef(self, node):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
        
    def visit_FunctionDef(self, node):
        self._process_function(node)
        
    def visit_AsyncFunctionDef(self, node):
        self._process_function(node, is_async=True)
        
    def _process_function(self, node, is_async=False):
        # Skip private/magic methods for test generation
        if node.name.startswith('_') and not node.name == '__init__':
            return
            
        # Extract arguments
        args = []
        for arg in node.args.args:
            if arg.arg == 'self':
                continue
            type_hint = None
            if arg.annotation:
                type_hint = self._get_annotation_str(arg.annotation)
            args.append((arg.arg, type_hint))
            
        # Return type
        return_type = None
        if node.returns:
            return_type = self._get_annotation_str(node.returns)
            
        # Decorators
        decorators = [self._get_decorator_str(d) for d in node.decorator_list]
        
        # Docstring
        docstring = ast.get_docstring(node)
        
        info = FunctionInfo(
            name=node.name,
            args=args,
            return_type=return_type,
            docstring=docstring,
            is_method=self.current_class is not None,
            class_name=self.current_class,
            decorators=decorators,
            lineno=node.lineno
        )
        
        self.functions.append(info)
        
    def _get_annotation_str(self, node) -> str:
        """Convert annotation node to string."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Subscript):
            base = self._get_annotation_str(node.value)
            if isinstance(node.slice, ast.Tuple):
                args = ", ".join(self._get_annotation_str(e) for e in node.slice.elts)
            else:
                args = self._get_annotation_str(node.slice)
            return f"{base}[{args}]"
        elif isinstance(node, ast.Attribute):
            return f"{self._get_annotation_str(node.value)}.{node.attr}"
        return "Any"
        
    def _get_decorator_str(self, node) -> str:
        """Convert decorator node to string."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return node.func.id
            elif isinstance(node.func, ast.Attribute):
                return node.func.attr
        elif isinstance(node, ast.Attribute):
            return node.attr
        return "decorator"


class TestGenerator:
    """Generates test cases from function information."""
    
    # Type to test value mapping
    TYPE_VALUES = {
        "str": ('""', '"test"', '"hello world"', 'None'),
        "int": ('0', '1', '-1', '999999', 'None'),
        "float": ('0.0', '1.5', '-1.5', 'float("inf")', 'None'),
        "bool": ('True', 'False', 'None'),
        "list": ('[]', '[1, 2, 3]', '["a", "b"]', 'None'),
        "List": ('[]', '[1, 2, 3]', '["a", "b"]', 'None'),
        "dict": ('{}', '{"key": "value"}', 'None'),
        "Dict": ('{}', '{"key": "value"}', 'None'),
        "Optional": ('None',),
        "Path": ('Path(".")', 'Path("/tmp")', 'None'),
    }
    
    # Hypothesis strategies
    HYPOTHESIS_STRATEGIES = {
        "str": "st.text()",
        "int": "st.integers()",
        "float": "st.floats(allow_nan=False)",
        "bool": "st.booleans()",
        "list": "st.lists(st.integers())",
        "List": "st.lists(st.integers())",
    }
    
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.test_cases: List[TestCase] = []
        
    def generate_tests(self, functions: List[FunctionInfo]) -> str:
        """Generate test file content."""
        lines = [
            '"""',
            f'Auto-generated tests for {self.module_name}',
            f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            '',
            'Categories:',
            '- Happy path: Normal expected usage',
            '- Edge cases: Boundary values, empty inputs, None',
            '- Property-based: Hypothesis-driven random testing',
            '"""',
            '',
            'import pytest',
            'from hypothesis import given, strategies as st, settings',
            'from unittest.mock import Mock, patch, MagicMock',
            'import os',
            'import sys',
            '',
            '# Add project to path',
            'sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))',
            '',
            f'# Import module under test',
            f'# TODO: Adjust import path as needed',
            f'# from {self.module_name.replace("/", ".").replace(".py", "")} import *',
            '',
            '',
        ]
        
        # Group by class
        class_functions: Dict[Optional[str], List[FunctionInfo]] = {}
        for func in functions:
            key = func.class_name
            if key not in class_functions:
                class_functions[key] = []
            class_functions[key].append(func)
            
        # Generate tests for each group
        for class_name, funcs in class_functions.items():
            if class_name:
                lines.append(f'class Test{class_name}:')
                lines.append(f'    """Tests for {class_name} class."""')
                lines.append('')
                indent = "    "
            else:
                lines.append('# === Standalone Function Tests ===')
                lines.append('')
                indent = ""
                
            for func in funcs:
                test_lines = self._generate_function_tests(func, indent)
                lines.extend(test_lines)
                
        return '\n'.join(lines)
        
    def _generate_function_tests(self, func: FunctionInfo, indent: str) -> List[str]:
        """Generate tests for a single function."""
        lines = []
        
        # Skip staticmethod/classmethod markers in decorators
        if 'abstractmethod' in func.decorators:
            return lines
            
        func_name = func.name
        
        # 1. Happy Path Test
        lines.append(f'{indent}def test_{func_name}_happy_path(self):' if func.is_method else f'def test_{func_name}_happy_path():')
        lines.append(f'{indent}    """Test {func_name} with valid inputs."""')
        
        # Generate setup based on docstring hints
        setup_lines = self._generate_setup(func, indent + "    ")
        lines.extend(setup_lines)
        
        # Generate action
        args_str = self._generate_args_str(func, "valid")
        if func.is_method:
            lines.append(f'{indent}    # TODO: Create instance')
            lines.append(f'{indent}    # instance = {func.class_name}()')
            lines.append(f'{indent}    # result = instance.{func_name}({args_str})')
        else:
            lines.append(f'{indent}    # result = {func_name}({args_str})')
            
        # Generate assertion based on return type
        assertion = self._generate_assertion(func, indent + "    ")
        lines.extend(assertion)
        lines.append(f'{indent}    pass  # TODO: Implement')
        lines.append('')
        
        # 2. Edge Case Tests (if has parameters)
        if func.args:
            lines.append(f'{indent}@pytest.mark.parametrize("input_val, expected", [')
            edge_cases = self._generate_edge_cases(func)
            for case, expected in edge_cases:
                lines.append(f'{indent}    ({case}, {expected}),')
            lines.append(f'{indent}])')
            
            lines.append(f'{indent}def test_{func_name}_edge_cases(self, input_val, expected):' if func.is_method else f'def test_{func_name}_edge_cases(input_val, expected):')
            lines.append(f'{indent}    """Test {func_name} with edge case inputs."""')
            lines.append(f'{indent}    # TODO: Implement edge case test')
            lines.append(f'{indent}    pass')
            lines.append('')
            
        # 3. Property-based Test (if has typed args)
        typed_args = [(name, typ) for name, typ in func.args if typ and self._get_base_type(typ) in self.HYPOTHESIS_STRATEGIES]
        if typed_args:
            strategies = []
            for name, typ in typed_args:
                base_type = self._get_base_type(typ)
                strat = self.HYPOTHESIS_STRATEGIES.get(base_type, "st.text()")
                strategies.append(f'{name}={strat}')
                
            lines.append(f'{indent}@settings(max_examples=50)')
            lines.append(f'{indent}@given({", ".join(strategies)})')
            
            params = ", ".join(name for name, _ in typed_args)
            lines.append(f'{indent}def test_{func_name}_property_based(self, {params}):' if func.is_method else f'def test_{func_name}_property_based({params}):')
            lines.append(f'{indent}    """Property-based test for {func_name}."""')
            lines.append(f'{indent}    # TODO: Add property assertions')
            lines.append(f'{indent}    # Example: assert result is not None')
            lines.append(f'{indent}    pass')
            lines.append('')
            
        return lines
        
    def _generate_setup(self, func: FunctionInfo, indent: str) -> List[str]:
        """Generate test setup based on docstring."""
        lines = []
        if func.docstring:
            # Extract hints from docstring
            if "Args:" in func.docstring:
                lines.append(f'{indent}# Setup based on docstring:')
                lines.append(f'{indent}# {func.docstring[:100]}...')
        return lines
        
    def _generate_args_str(self, func: FunctionInfo, mode: str) -> str:
        """Generate arguments string for function call."""
        args = []
        for name, typ in func.args:
            if mode == "valid":
                if typ:
                    base = self._get_base_type(typ)
                    values = self.TYPE_VALUES.get(base, ('"test"',))
                    args.append(f'{name}={values[1] if len(values) > 1 else values[0]}')
                else:
                    args.append(f'{name}="test"')
        return ", ".join(args)
        
    def _generate_edge_cases(self, func: FunctionInfo) -> List[Tuple[str, str]]:
        """Generate edge case inputs."""
        cases = []
        
        # None values
        cases.append(('None', 'None  # or raises'))
        
        # Empty values
        cases.append(('""', '"" or None'))
        cases.append(('[]', '[]'))
        cases.append(('{}', '{}'))
        
        # Boundary values
        cases.append(('0', 'expected_for_zero'))
        cases.append(('-1', 'expected_for_negative'))
        
        return cases[:4]  # Limit to 4 cases
        
    def _generate_assertion(self, func: FunctionInfo, indent: str) -> List[str]:
        """Generate assertion based on return type."""
        lines = []
        if func.return_type:
            if 'bool' in func.return_type:
                lines.append(f'{indent}# assert result is True')
            elif 'List' in func.return_type or 'list' in func.return_type:
                lines.append(f'{indent}# assert isinstance(result, list)')
            elif 'Dict' in func.return_type or 'dict' in func.return_type:
                lines.append(f'{indent}# assert isinstance(result, dict)')
            elif 'Optional' in func.return_type:
                lines.append(f'{indent}# assert result is not None')
            else:
                lines.append(f'{indent}# assert result == expected')
        else:
            lines.append(f'{indent}# assert result is not None')
        return lines
        
    def _get_base_type(self, type_str: str) -> str:
        """Extract base type from type hint."""
        if '[' in type_str:
            return type_str.split('[')[0]
        return type_str


def analyze_module(file_path: str) -> List[FunctionInfo]:
    """Analyze a Python module and extract function info."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    tree = ast.parse(content)
    analyzer = FunctionAnalyzer()
    analyzer.visit(tree)
    
    return analyzer.functions


def main():
    parser = argparse.ArgumentParser(description="Generate tests from Python module")
    parser.add_argument("module_path", help="Path to Python module to analyze")
    parser.add_argument("--output", "-o", help="Output test file path")
    parser.add_argument("--run", "-r", action="store_true", help="Run generated tests")
    
    args = parser.parse_args()
    
    module_path = args.module_path
    if not os.path.exists(module_path):
        print(f"❌ File not found: {module_path}")
        sys.exit(1)
        
    print("=" * 60)
    print("🧪 AI TEST GENERATOR")
    print("=" * 60)
    print(f"📄 Analyzing: {module_path}")
    
    # Analyze module
    functions = analyze_module(module_path)
    print(f"   Found {len(functions)} public functions/methods")
    
    # Generate tests
    module_name = os.path.basename(module_path).replace(".py", "")
    generator = TestGenerator(module_path)
    test_content = generator.generate_tests(functions)
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        # Default: tests/test_generated_<module>.py
        tests_dir = os.path.join(os.path.dirname(module_path), "..", "tests")
        os.makedirs(tests_dir, exist_ok=True)
        output_path = os.path.join(tests_dir, f"test_generated_{module_name}.py")
        
    output_path = os.path.abspath(output_path)
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(test_content)
        
    print(f"✅ Generated: {output_path}")
    print(f"   Test cases: Happy path + Edge cases + Property-based")
    
    # Run tests if requested
    if args.run:
        print("\n🏃 Running tests...")
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", output_path, "-v", "--tb=short"],
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            
    print("=" * 60)
    print("Done!")
    

if __name__ == "__main__":
    main()
