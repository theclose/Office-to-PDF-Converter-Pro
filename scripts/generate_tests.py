"""
AI Test Generator - Coverage-Aware Test Generation
===================================================
1. Scans src folder and reads functions without test coverage
2. Uses AI to generate pytest test cases covering edge cases
3. Saves to generated_tests/ folder

Usage:
    python generate_tests.py --src=core/ --output=generated_tests/
    python generate_tests.py --file=core/file_tools.py
    
Environment Variables:
    OPENAI_API_KEY or GEMINI_API_KEY
"""

import os
import sys
import json
import ast
import argparse
import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from pathlib import Path
import urllib.request


@dataclass
class FunctionInfo:
    """Information about a function."""
    name: str
    file: str
    lineno: int
    signature: str
    docstring: Optional[str]
    body_preview: str
    is_covered: bool = False


class CoverageAnalyzer:
    """Analyzes test coverage to find untested functions."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.tested_functions: Set[str] = set()
        
    def load_coverage_data(self, coverage_file: str = ".coverage"):
        """Load coverage data if available."""
        # Try to load existing coverage data
        cov_path = self.project_root / coverage_file
        if cov_path.exists():
            try:
                import coverage
                cov = coverage.Coverage()
                cov.load()
                # Get covered lines... (simplified)
            except ImportError:
                pass
                
    def scan_test_files(self) -> Set[str]:
        """Scan test files to find which functions are tested."""
        tests_dir = self.project_root / "tests"
        tested = set()
        
        if not tests_dir.exists():
            return tested
            
        for test_file in tests_dir.glob("test_*.py"):
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Extract function names being tested
                # Pattern: test_<function_name>, or calls to function_name
                matches = re.findall(r'def test_(\w+)', content)
                tested.update(matches)
                
                # Also look for direct function calls in tests
                calls = re.findall(r'(\w+)\s*\(', content)
                tested.update(calls)
                
            except Exception:
                continue
                
        self.tested_functions = tested
        return tested
        
    def scan_source_file(self, file_path: str) -> List[FunctionInfo]:
        """Scan a source file and extract function info."""
        functions = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content)
            lines = content.splitlines()
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip private/magic methods
                    if node.name.startswith('_') and not node.name == '__init__':
                        continue
                        
                    # Get signature
                    args = []
                    for arg in node.args.args:
                        if arg.arg != 'self':
                            arg_str = arg.arg
                            if arg.annotation:
                                arg_str += f": {ast.unparse(arg.annotation)}"
                            args.append(arg_str)
                    signature = f"{node.name}({', '.join(args)})"
                    
                    # Get body preview (first 3 lines)
                    start = node.lineno - 1
                    end = min(start + 5, len(lines))
                    body_preview = "\n".join(lines[start:end])
                    
                    # Check if covered
                    is_covered = node.name in self.tested_functions
                    
                    functions.append(FunctionInfo(
                        name=node.name,
                        file=file_path,
                        lineno=node.lineno,
                        signature=signature,
                        docstring=ast.get_docstring(node),
                        body_preview=body_preview,
                        is_covered=is_covered
                    ))
                    
        except Exception as e:
            print(f"Error scanning {file_path}: {e}")
            
        return functions


class AITestGenerator:
    """Generates tests using AI."""
    
    SYSTEM_PROMPT = """You are an expert Python test engineer. Generate pytest test cases.

For each function, generate:
1. Happy path test (normal expected input)
2. Edge case tests (empty, None, boundary values)
3. Error handling tests (invalid input)

Use pytest conventions:
- Use descriptive test names: test_<function>_<scenario>
- Use parametrize for multiple test cases
- Include docstrings explaining what each test verifies
- Use appropriate assertions

Output ONLY valid Python code, no explanations.
"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        
    def generate_tests(self, functions: List[FunctionInfo], module_name: str) -> str:
        """Generate test code for functions."""
        if not functions:
            return ""
            
        # Build prompt
        func_descriptions = []
        for f in functions[:10]:  # Limit to 10 functions
            desc = f"""
Function: {f.signature}
Docstring: {f.docstring or 'No docstring'}
Code:
```python
{f.body_preview}
```
"""
            func_descriptions.append(desc)
            
        prompt = f"""Generate pytest tests for these functions from module '{module_name}':

{''.join(func_descriptions)}

Requirements:
- Import the module at the top
- Use @pytest.mark.parametrize for edge cases
- Include at least 2 test cases per function
- Handle expected exceptions with pytest.raises
"""
        
        if self.api_key:
            return self._call_api(prompt)
        else:
            return self._generate_mock_tests(functions, module_name)
            
    def _call_api(self, prompt: str) -> str:
        """Call OpenAI API."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode())
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"API Error: {e}")
            return self._generate_mock_tests([], "unknown")
            
    def _generate_mock_tests(self, functions: List[FunctionInfo], module_name: str) -> str:
        """Generate mock tests when API unavailable."""
        lines = [
            '"""',
            f'Auto-generated tests for {module_name}',
            'Generated by AI Test Generator (mock mode - configure API key for real generation)',
            '"""',
            '',
            'import pytest',
            'from unittest.mock import Mock, patch',
            '',
            f'# TODO: Import from {module_name}',
            '',
        ]
        
        for func in functions:
            lines.extend([
                f'class Test{func.name.title().replace("_", "")}:',
                f'    """Tests for {func.name}."""',
                '',
                f'    def test_{func.name}_basic(self):',
                f'        """Test {func.name} with valid input."""',
                f'        # TODO: Implement - function from line {func.lineno}',
                '        pass',
                '',
                f'    def test_{func.name}_edge_cases(self):',
                f'        """Test {func.name} with edge cases."""',
                '        # TODO: Test with None, empty values, boundaries',
                '        pass',
                '',
            ])
            
        return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description="AI Test Generator")
    parser.add_argument("--src", default="core", help="Source folder to scan")
    parser.add_argument("--file", help="Specific file to generate tests for")
    parser.add_argument("--output", default="generated_tests", help="Output folder")
    parser.add_argument("--uncovered-only", action="store_true", help="Only generate for uncovered functions")
    parser.add_argument("--project", default=".", help="Project root")
    
    args = parser.parse_args()
    
    project_root = Path(args.project).absolute()
    output_dir = project_root / args.output
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("🧪 AI TEST GENERATOR")
    print("=" * 60)
    
    # Initialize
    analyzer = CoverageAnalyzer(str(project_root))
    generator = AITestGenerator()
    
    # Scan for existing test coverage
    print("📊 Scanning existing tests...")
    tested = analyzer.scan_test_files()
    print(f"   Found {len(tested)} tested functions")
    
    # Get files to process
    if args.file:
        files = [project_root / args.file]
    else:
        src_dir = project_root / args.src
        files = list(src_dir.glob("**/*.py"))
        
    print(f"\n📁 Scanning {len(files)} source files...")
    
    # Process each file
    total_generated = 0
    for file_path in files:
        if "__pycache__" in str(file_path) or "test_" in file_path.name:
            continue
            
        functions = analyzer.scan_source_file(str(file_path))
        
        if args.uncovered_only:
            functions = [f for f in functions if not f.is_covered]
            
        if not functions:
            continue
            
        print(f"\n   📄 {file_path.name}: {len(functions)} functions")
        
        # Generate tests
        module_name = file_path.stem
        test_code = generator.generate_tests(functions, module_name)
        
        # Save to file
        output_file = output_dir / f"test_generated_{module_name}.py"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(test_code)
            
        print(f"      ✅ Generated: {output_file.name}")
        total_generated += 1
        
    print("\n" + "=" * 60)
    print(f"✅ Generated tests for {total_generated} modules")
    print(f"   Output: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
