"""
AI Assistant Integration - Use Antigravity/Claude Directly
==========================================================
Generates prompts for the AI assistant instead of calling external APIs.
User copies the output and sends to their AI assistant (Antigravity/Claude).

Scripts:
    collect_for_review.py - Collects diff and generates review prompt
    collect_for_tests.py - Collects functions and generates test prompt
    collect_for_fix.py - Collects test failures and generates fix prompt
    
Usage:
    python ai_assistant.py review [--base=HEAD~1]
    python ai_assistant.py tests --src=core/
    python ai_assistant.py fix --results=pytest_output.txt
    python ai_assistant.py apply --response=ai_response.json
"""

import os
import sys
import json
import subprocess
import argparse
import ast
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class AIAssistant:
    """Prepares prompts for AI assistant and applies responses."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).absolute()
        self.output_dir = self.project_root / ".ai_assistant"
        self.output_dir.mkdir(exist_ok=True)
        
    # ==================== REVIEW ====================
    
    def collect_for_review(self, base: str = "HEAD~1", target: str = "HEAD") -> str:
        """Collect git diff and generate review prompt."""
        print("📝 Collecting changes for review...")
        
        # Get git diff
        result = subprocess.run(
            ["git", "diff", base, target, "--", "*.py"],
            capture_output=True, text=True, cwd=self.project_root
        )
        diff = result.stdout
        
        if not diff:
            print("No Python changes found")
            return ""
            
        # Count changes
        files_changed = len(set(re.findall(r'diff --git a/(.*?) b/', diff)))
        lines_added = diff.count('\n+') - diff.count('\n+++')
        lines_removed = diff.count('\n-') - diff.count('\n---')
        
        prompt = f"""# 🔍 Code Review Request

**Vai trò**: Senior Software Architect + Security Engineer

**Thay đổi**: {files_changed} files, +{lines_added}/-{lines_removed} lines

## Git Diff

```diff
{diff[:12000]}
```

## Yêu cầu Review

1. **Security**: Tìm lỗ hổng bảo mật (injection, path traversal, etc.)
2. **Bugs**: Logic errors, race conditions, memory leaks
3. **Quality**: Code style, best practices, maintainability
4. **Performance**: Bottlenecks, inefficiencies

## Output Format

Trả về theo format này:
```json
{{
    "overall_score": 8,
    "summary": "Tóm tắt thay đổi",
    "issues": [
        {{"file": "path/file.py", "line": 10, "severity": "high|medium|low", "message": "Mô tả issue"}}
    ],
    "suggestions": ["Gợi ý 1", "Gợi ý 2"]
}}
```
"""
        # Save prompt
        prompt_file = self.output_dir / "review_prompt.md"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(prompt)
            
        print(f"✅ Prompt saved: {prompt_file}")
        print(f"\n{'='*60}")
        print("📋 COPY PROMPT BELOW AND SEND TO AI ASSISTANT:")
        print('='*60)
        print(prompt[:3000])
        if len(prompt) > 3000:
            print(f"\n... (xem file đầy đủ: {prompt_file})")
        print('='*60)
        
        return str(prompt_file)
        
    # ==================== TESTS ====================
    
    def collect_for_tests(self, src_folder: str = "core") -> str:
        """Collect uncovered functions and generate test prompt."""
        print(f"🧪 Scanning {src_folder} for functions...")
        
        src_path = self.project_root / src_folder
        functions = []
        
        for py_file in src_path.glob("**/*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                tree = ast.parse(content)
                lines = content.splitlines()
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        if node.name.startswith('_') and node.name != '__init__':
                            continue
                            
                        # Get signature
                        args = [a.arg for a in node.args.args if a.arg != 'self']
                        sig = f"{node.name}({', '.join(args)})"
                        
                        # Get docstring and preview
                        docstring = ast.get_docstring(node) or "No docstring"
                        start = node.lineno - 1
                        end = min(start + 8, len(lines))
                        preview = '\n'.join(lines[start:end])
                        
                        functions.append({
                            'name': node.name,
                            'file': str(py_file.relative_to(self.project_root)),
                            'line': node.lineno,
                            'signature': sig,
                            'docstring': docstring[:100],
                            'preview': preview
                        })
            except Exception:
                continue
                
        print(f"   Found {len(functions)} functions")
        
        # Limit to 10 functions
        functions = functions[:10]
        
        funcs_text = ""
        for f in functions:
            funcs_text += f"""
### {f['signature']}
**File**: `{f['file']}:{f['line']}`
**Docstring**: {f['docstring']}
```python
{f['preview']}
```

"""
        
        prompt = f"""# 🧪 Test Generation Request

**Vai trò**: Senior Test Engineer

**Module**: {src_folder}
**Functions**: {len(functions)}

## Functions cần test

{funcs_text}

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
"""
        # Save prompt
        prompt_file = self.output_dir / "tests_prompt.md"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(prompt)
            
        print(f"✅ Prompt saved: {prompt_file}")
        print(f"\n{'='*60}")
        print("📋 COPY PROMPT BELOW AND SEND TO AI ASSISTANT:")
        print('='*60)
        print(prompt[:2000])
        print('='*60)
        
        return str(prompt_file)
        
    # ==================== FIX ====================
    
    def collect_for_fix(self, results_file: str = None) -> str:
        """Collect test failures and generate fix prompt."""
        print("🔧 Collecting test failures...")
        
        failures = []
        
        # Try to find test results
        if results_file and os.path.exists(results_file):
            with open(results_file, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            # Run pytest to get current failures
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "-x", "--timeout=30"],
                capture_output=True, text=True, cwd=self.project_root
            )
            content = result.stdout + result.stderr
            
        # Parse failures
        failed_pattern = r'FAILED\s+([\w/]+\.py::\w+)'
        for match in re.finditer(failed_pattern, content):
            test_id = match.group(1)
            
            # Extract traceback for this test
            tb_pattern = rf'{re.escape(test_id)}.*?(?=FAILED|PASSED|={5,}|$)'
            tb_match = re.search(tb_pattern, content, re.DOTALL)
            traceback = tb_match.group()[:500] if tb_match else ""
            
            failures.append({
                'test': test_id,
                'traceback': traceback
            })
            
        if not failures:
            print("No test failures found")
            return ""
            
        print(f"   Found {len(failures)} failures")
        
        failures_text = ""
        for i, f in enumerate(failures[:5], 1):
            failures_text += f"""
### Failure {i}: `{f['test']}`
```
{f['traceback']}
```

"""
        
        prompt = f"""# 🔧 Test Failure Fix Request

**Vai trò**: Senior Debugger

**Failures**: {len(failures)}

## Test Failures

{failures_text}

## Yêu cầu

Phân tích mỗi failure và:
1. Xác định **nguyên nhân gốc** (root cause)
2. Đề xuất **cách fix** cụ thể
3. Cung cấp **code patch** nếu có thể

## Output Format

```json
{{
    "fixes": [
        {{
            "test": "test_name",
            "root_cause": "Nguyên nhân",
            "solution": "Cách fix",
            "file_to_edit": "path/to/file.py",
            "original_code": "code cần sửa",
            "fixed_code": "code đã sửa"
        }}
    ]
}}
```
"""
        # Save prompt
        prompt_file = self.output_dir / "fix_prompt.md"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(prompt)
            
        print(f"✅ Prompt saved: {prompt_file}")
        print(f"\n{'='*60}")
        print("📋 COPY PROMPT BELOW AND SEND TO AI ASSISTANT:")
        print('='*60)
        print(prompt[:2000])
        print('='*60)
        
        return str(prompt_file)
        
    # ==================== APPLY ====================
    
    def apply_response(self, response_file: str = None, response_text: str = None) -> bool:
        """Apply AI response (tests or fixes)."""
        print("📥 Applying AI response...")
        
        if response_file:
            with open(response_file, 'r', encoding='utf-8') as f:
                content = f.read()
        elif response_text:
            content = response_text
        else:
            print("No response provided")
            return False
            
        # Try to extract JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                
                # Handle fixes
                if 'fixes' in data:
                    for fix in data['fixes']:
                        file_path = self.project_root / fix.get('file_to_edit', '')
                        if file_path.exists() and fix.get('original_code') and fix.get('fixed_code'):
                            with open(file_path, 'r') as f:
                                content = f.read()
                            if fix['original_code'] in content:
                                content = content.replace(fix['original_code'], fix['fixed_code'], 1)
                                with open(file_path, 'w') as f:
                                    f.write(content)
                                print(f"   ✅ Applied fix to {file_path.name}")
                    return True
                    
            except json.JSONDecodeError:
                pass
                
        # Try to extract Python code
        code_match = re.search(r'```python\n(.*?)\n```', content, re.DOTALL)
        if code_match:
            code = code_match.group(1)
            
            # Save as test file
            test_file = self.project_root / "tests" / "test_ai_generated.py"
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(code)
            print(f"   ✅ Saved tests to {test_file}")
            return True
            
        print("   ⚠️ Could not parse response")
        return False


def main():
    parser = argparse.ArgumentParser(description="AI Assistant Integration")
    parser.add_argument("action", choices=["review", "tests", "fix", "apply"],
                        help="Action to perform")
    parser.add_argument("--base", default="HEAD~1", help="Base ref for review")
    parser.add_argument("--src", default="core", help="Source folder for tests")
    parser.add_argument("--results", help="Test results file for fix")
    parser.add_argument("--response", help="AI response file to apply")
    parser.add_argument("--project", default=".", help="Project root")
    
    args = parser.parse_args()
    
    assistant = AIAssistant(args.project)
    
    if args.action == "review":
        assistant.collect_for_review(args.base)
    elif args.action == "tests":
        assistant.collect_for_tests(args.src)
    elif args.action == "fix":
        assistant.collect_for_fix(args.results)
    elif args.action == "apply":
        assistant.apply_response(args.response)


if __name__ == "__main__":
    main()
