"""
Static Analysis & Semantic Review Pipeline
==========================================
Combines Ruff (fast linter) with Cyclomatic Complexity analysis
and generates AI review prompts for complex/risky code sections.

Features:
1. Ruff lint for syntax/style errors
2. AST-based Cyclomatic Complexity calculation  
3. Detection of security-sensitive patterns
4. AI prompt generation for complex code review

Usage:
    python code_analyzer.py <path> [--threshold=10] [--ai-review]
    python code_analyzer.py core/file_tools.py --ai-review
"""

import ast
import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime


@dataclass
class ComplexityResult:
    """Result of complexity analysis."""
    file: str
    function: str
    class_name: Optional[str]
    complexity: int
    lineno: int
    code_snippet: str


@dataclass
class SecurityPattern:
    """Detected security-sensitive pattern."""
    file: str
    pattern_type: str
    description: str
    lineno: int
    code_snippet: str
    severity: str  # low, medium, high


@dataclass  
class AnalysisReport:
    """Complete analysis report."""
    files_analyzed: int
    total_lines: int
    lint_errors: List[dict]
    complexity_issues: List[ComplexityResult]
    security_patterns: List[SecurityPattern]
    ai_review_prompts: List[str]


class CyclomaticComplexityVisitor(ast.NodeVisitor):
    """Calculates Cyclomatic Complexity for functions."""
    
    DECISION_NODES = (
        ast.If, ast.While, ast.For, ast.ExceptHandler,
        ast.With, ast.Assert, ast.comprehension
    )
    
    def __init__(self, source_lines: List[str]):
        self.functions: List[ComplexityResult] = []
        self.current_class: Optional[str] = None
        self.source_lines = source_lines
        self.file_path = ""
        
    def calculate_complexity(self, node) -> int:
        """Calculate complexity for a node."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            # Decision points
            if isinstance(child, self.DECISION_NODES):
                complexity += 1
            # Boolean operators
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            # Ternary expressions
            elif isinstance(child, ast.IfExp):
                complexity += 1
            # Try-except
            elif isinstance(child, ast.Try):
                complexity += len(child.handlers)
                
        return complexity
        
    def visit_ClassDef(self, node):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
        
    def visit_FunctionDef(self, node):
        complexity = self.calculate_complexity(node)
        
        # Get code snippet (first 5 lines)
        start = node.lineno - 1
        end = min(start + 5, len(self.source_lines))
        snippet = "\n".join(self.source_lines[start:end])
        
        result = ComplexityResult(
            file=self.file_path,
            function=node.name,
            class_name=self.current_class,
            complexity=complexity,
            lineno=node.lineno,
            code_snippet=snippet
        )
        self.functions.append(result)
        self.generic_visit(node)
        
    visit_AsyncFunctionDef = visit_FunctionDef


class SecurityPatternDetector(ast.NodeVisitor):
    """Detects security-sensitive patterns in code."""
    
    DANGEROUS_FUNCTIONS = {
        'eval': ('high', 'Code injection risk'),
        'exec': ('high', 'Code injection risk'),
        'compile': ('medium', 'Dynamic code execution'),
        '__import__': ('medium', 'Dynamic import'),
        'open': ('low', 'File access - check path validation'),
        'subprocess.run': ('medium', 'Command execution'),
        'subprocess.call': ('medium', 'Command execution'),
        'subprocess.Popen': ('high', 'Shell command execution'),
        'os.system': ('high', 'Shell command execution'),
        'os.popen': ('high', 'Shell command execution'),
        'pickle.load': ('high', 'Deserialization risk'),
        'pickle.loads': ('high', 'Deserialization risk'),
    }
    
    SQL_PATTERNS = ['execute', 'executemany', 'executescript']
    
    def __init__(self, source_lines: List[str]):
        self.patterns: List[SecurityPattern] = []
        self.source_lines = source_lines
        self.file_path = ""
        
    def visit_Call(self, node):
        func_name = self._get_func_name(node.func)
        
        # Check dangerous functions
        for dangerous, (severity, desc) in self.DANGEROUS_FUNCTIONS.items():
            if dangerous in func_name:
                snippet = self.source_lines[node.lineno - 1] if node.lineno <= len(self.source_lines) else ""
                self.patterns.append(SecurityPattern(
                    file=self.file_path,
                    pattern_type="dangerous_function",
                    description=f"{dangerous}: {desc}",
                    lineno=node.lineno,
                    code_snippet=snippet.strip(),
                    severity=severity
                ))
                break
                
        # Check for SQL injection patterns
        if any(sql in func_name for sql in self.SQL_PATTERNS):
            # Check if using string formatting in args
            for arg in node.args:
                if isinstance(arg, (ast.JoinedStr, ast.BinOp)):
                    self.patterns.append(SecurityPattern(
                        file=self.file_path,
                        pattern_type="sql_injection_risk",
                        description="Possible SQL injection - string formatting in query",
                        lineno=node.lineno,
                        code_snippet=self.source_lines[node.lineno - 1].strip() if node.lineno <= len(self.source_lines) else "",
                        severity="high"
                    ))
                    break
                    
        self.generic_visit(node)
        
    def _get_func_name(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_func_name(node.value)}.{node.attr}"
        return ""


def run_ruff(path: str) -> List[dict]:
    """Run Ruff linter on path."""
    try:
        result = subprocess.run(
            ["ruff", "check", path, "--output-format=json", "--ignore=E501"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.stdout:
            return json.loads(result.stdout)
        return []
    except FileNotFoundError:
        print("⚠️ Ruff not installed. Run: pip install ruff")
        return []
    except Exception as e:
        print(f"⚠️ Ruff error: {e}")
        return []


def analyze_file(file_path: str, threshold: int = 10) -> Tuple[List[ComplexityResult], List[SecurityPattern]]:
    """Analyze a single Python file."""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        
    source_lines = content.splitlines()
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return [], []
        
    # Complexity analysis
    complexity_visitor = CyclomaticComplexityVisitor(source_lines)
    complexity_visitor.file_path = file_path
    complexity_visitor.visit(tree)
    
    # Filter by threshold
    complex_funcs = [f for f in complexity_visitor.functions if f.complexity >= threshold]
    
    # Security analysis
    security_visitor = SecurityPatternDetector(source_lines)
    security_visitor.file_path = file_path
    security_visitor.visit(tree)
    
    return complex_funcs, security_visitor.patterns


def generate_ai_prompt(result: ComplexityResult) -> str:
    """Generate AI review prompt for complex function."""
    prompt = f"""
## 🔍 Security & Logic Review Request

**Role**: Senior Security Engineer + Code Architect

**Target**: `{result.function}` in `{result.file}` (line {result.lineno})

**Metrics**:
- Cyclomatic Complexity: {result.complexity} (threshold: 10)
- Class: {result.class_name or 'standalone'}

**Code Snippet**:
```python
{result.code_snippet}
```

**Review Checklist**:
1. 🔒 **Security Vulnerabilities**
   - Path traversal risks
   - Injection attacks (SQL, Command, Code)
   - Sensitive data exposure
   
2. 🏃 **Race Conditions**
   - Shared state access
   - File locking issues  
   - Thread safety
   
3. 💾 **Memory Leaks**
   - Unclosed resources (files, connections)
   - Growing collections
   - Circular references
   
4. 🧠 **Logic Errors**
   - Edge cases not handled
   - Off-by-one errors
   - Null/None checks

**Expected Output**: List findings with severity (Critical/High/Medium/Low) and fix suggestions.
"""
    return prompt


def generate_report(report: AnalysisReport, output_dir: str):
    """Generate analysis report files."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Summary report
    summary_path = os.path.join(output_dir, "analysis_report.md")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("# 🔬 Static Analysis Report\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        
        f.write("## 📊 Summary\n\n")
        f.write(f"| Metric | Count |\n")
        f.write(f"|:---|---:|\n")
        f.write(f"| Files Analyzed | {report.files_analyzed} |\n")
        f.write(f"| Total Lines | {report.total_lines} |\n")
        f.write(f"| Lint Errors | {len(report.lint_errors)} |\n")
        f.write(f"| High Complexity Functions | {len(report.complexity_issues)} |\n")
        f.write(f"| Security Patterns | {len(report.security_patterns)} |\n\n")
        
        # Lint errors
        if report.lint_errors:
            f.write("## 🧹 Lint Errors (Ruff)\n\n")
            for err in report.lint_errors[:20]:  # Limit display
                f.write(f"- **{err.get('code', 'ERR')}** `{err.get('filename', '')}:{err.get('location', {}).get('row', 0)}`: {err.get('message', '')}\n")
            if len(report.lint_errors) > 20:
                f.write(f"\n... and {len(report.lint_errors) - 20} more\n")
            f.write("\n")
            
        # Complexity issues
        if report.complexity_issues:
            f.write("## ⚠️ High Complexity Functions\n\n")
            f.write("| Function | File | Complexity | Line |\n")
            f.write("|:---|:---|:---:|:---:|\n")
            for issue in sorted(report.complexity_issues, key=lambda x: -x.complexity):
                name = f"{issue.class_name}.{issue.function}" if issue.class_name else issue.function
                f.write(f"| `{name}` | `{os.path.basename(issue.file)}` | {issue.complexity} | {issue.lineno} |\n")
            f.write("\n")
            
        # Security patterns
        if report.security_patterns:
            f.write("## 🔒 Security Patterns Detected\n\n")
            for pattern in report.security_patterns:
                icon = "🔴" if pattern.severity == "high" else "🟡" if pattern.severity == "medium" else "🟢"
                f.write(f"### {icon} {pattern.pattern_type} ({pattern.severity})\n")
                f.write(f"- **File**: `{pattern.file}:{pattern.lineno}`\n")
                f.write(f"- **Description**: {pattern.description}\n")
                f.write(f"- **Code**: `{pattern.code_snippet[:80]}...`\n\n")
                
    print(f"   📄 Report: {summary_path}")
    
    # AI review prompts
    if report.ai_review_prompts:
        prompts_path = os.path.join(output_dir, "ai_review_prompts.md")
        with open(prompts_path, 'w', encoding='utf-8') as f:
            f.write("# 🤖 AI Review Prompts\n\n")
            f.write("Copy each section below to an AI assistant for security review.\n\n")
            f.write("---\n\n")
            for i, prompt in enumerate(report.ai_review_prompts, 1):
                f.write(f"# Review {i}\n\n")
                f.write(prompt)
                f.write("\n---\n\n")
        print(f"   🤖 AI Prompts: {prompts_path}")


def main():
    parser = argparse.ArgumentParser(description="Static Analysis & Semantic Review Pipeline")
    parser.add_argument("path", help="File or directory to analyze")
    parser.add_argument("--threshold", "-t", type=int, default=10, help="Complexity threshold")
    parser.add_argument("--ai-review", "-a", action="store_true", help="Generate AI review prompts")
    parser.add_argument("--output", "-o", default=".analysis", help="Output directory")
    
    args = parser.parse_args()
    
    target_path = os.path.abspath(args.path)
    output_dir = os.path.join(os.path.dirname(target_path), args.output)
    
    print("=" * 60)
    print("🔬 STATIC ANALYSIS PIPELINE")
    print("=" * 60)
    
    # Collect Python files
    py_files = []
    if os.path.isfile(target_path):
        py_files = [target_path]
    else:
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in ["__pycache__", ".git", "venv", ".venv"]]
            for f in files:
                if f.endswith(".py"):
                    py_files.append(os.path.join(root, f))
                    
    print(f"📂 Target: {target_path}")
    print(f"   Found {len(py_files)} Python files")
    
    # Phase 1: Ruff lint
    print("\n🧹 Phase 1: Running Ruff linter...")
    lint_errors = run_ruff(target_path)
    print(f"   Found {len(lint_errors)} lint issues")
    
    # Phase 2: Complexity + Security analysis
    print(f"\n🔍 Phase 2: Complexity & Security Analysis (threshold={args.threshold})...")
    all_complexity = []
    all_security = []
    total_lines = 0
    
    for file_path in py_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                total_lines += len(f.readlines())
        except:
            pass
            
        complex_funcs, security_patterns = analyze_file(file_path, args.threshold)
        all_complexity.extend(complex_funcs)
        all_security.extend(security_patterns)
        
    print(f"   High complexity functions: {len(all_complexity)}")
    print(f"   Security patterns: {len(all_security)}")
    
    # Phase 3: Generate AI prompts
    ai_prompts = []
    if args.ai_review:
        print("\n🤖 Phase 3: Generating AI review prompts...")
        for result in sorted(all_complexity, key=lambda x: -x.complexity)[:5]:  # Top 5
            ai_prompts.append(generate_ai_prompt(result))
        print(f"   Generated {len(ai_prompts)} review prompts")
    
    # Generate report
    report = AnalysisReport(
        files_analyzed=len(py_files),
        total_lines=total_lines,
        lint_errors=lint_errors,
        complexity_issues=all_complexity,
        security_patterns=all_security,
        ai_review_prompts=ai_prompts
    )
    
    print(f"\n📝 Generating reports...")
    generate_report(report, output_dir)
    
    print("\n" + "=" * 60)
    print("✅ Analysis complete!")
    print(f"   Output: {output_dir}")
    print("=" * 60)
    
    # Exit with error code if high-severity issues
    high_severity = sum(1 for p in all_security if p.severity == "high")
    if high_severity > 0:
        print(f"\n⚠️ WARNING: {high_severity} high-severity security patterns detected!")
        sys.exit(1)


if __name__ == "__main__":
    main()
