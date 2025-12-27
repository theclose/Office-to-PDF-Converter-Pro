"""
AI AutoFix - Automated Test Failure Fixer
==========================================
1. Reads pytest XML/JSON test results for failures
2. Extracts failing code + error messages
3. Uses AI to suggest fixes and generate patches

Usage:
    python ai_autofix.py --results=test_results.xml
    python ai_autofix.py --results=test_results.json --apply
    
Environment Variables:
    OPENAI_API_KEY or GEMINI_API_KEY
"""

import os
import sys
import json
import argparse
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import urllib.request


@dataclass
class TestFailure:
    """Information about a test failure."""
    test_name: str
    test_file: str
    source_file: str
    source_line: int
    error_type: str
    error_message: str
    traceback: str
    source_code: str = ""


@dataclass
class FixSuggestion:
    """AI-generated fix suggestion."""
    file: str
    description: str
    original_code: str
    fixed_code: str
    patch: str


class TestResultParser:
    """Parses pytest test results from XML or JSON."""
    
    def parse_junit_xml(self, xml_path: str) -> List[TestFailure]:
        """Parse JUnit XML format (pytest --junitxml)."""
        failures = []
        
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            for testcase in root.iter('testcase'):
                failure = testcase.find('failure')
                error = testcase.find('error')
                
                fail_elem = failure if failure is not None else error
                if fail_elem is None:
                    continue
                    
                classname = testcase.get('classname', '')
                name = testcase.get('name', '')
                message = fail_elem.get('message', '')
                traceback = fail_elem.text or ''
                
                # Extract source file and line from traceback
                source_file, source_line = self._extract_source_location(traceback)
                
                failures.append(TestFailure(
                    test_name=f"{classname}::{name}",
                    test_file=classname.replace('.', '/') + '.py' if classname else '',
                    source_file=source_file,
                    source_line=source_line,
                    error_type=fail_elem.get('type', 'Error'),
                    error_message=message,
                    traceback=traceback
                ))
                
        except Exception as e:
            print(f"Error parsing XML: {e}")
            
        return failures
        
    def parse_json(self, json_path: str) -> List[TestFailure]:
        """Parse pytest JSON report."""
        failures = []
        
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                
            for test in data.get('tests', []):
                if test.get('outcome') != 'failed':
                    continue
                    
                longrepr = test.get('call', {}).get('longrepr', '')
                source_file, source_line = self._extract_source_location(longrepr)
                
                failures.append(TestFailure(
                    test_name=test.get('nodeid', ''),
                    test_file=test.get('nodeid', '').split('::')[0],
                    source_file=source_file,
                    source_line=source_line,
                    error_type=test.get('call', {}).get('crash', {}).get('message', 'Error'),
                    error_message=test.get('call', {}).get('crash', {}).get('message', ''),
                    traceback=longrepr
                ))
                
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            
        return failures
        
    def parse_console_output(self, output: str) -> List[TestFailure]:
        """Parse pytest console output."""
        failures = []
        
        # Pattern for failed tests
        pattern = r'FAILED\s+([\w/]+\.py::[\w:]+)'
        matches = re.findall(pattern, output)
        
        for match in matches:
            parts = match.split('::')
            test_file = parts[0] if parts else ''
            test_name = match
            
            # Extract error from output
            error_pattern = rf'{re.escape(test_name)}.*?(?=FAILED|PASSED|$)'
            error_match = re.search(error_pattern, output, re.DOTALL)
            
            traceback = error_match.group() if error_match else ''
            source_file, source_line = self._extract_source_location(traceback)
            
            failures.append(TestFailure(
                test_name=test_name,
                test_file=test_file,
                source_file=source_file,
                source_line=source_line,
                error_type="AssertionError",
                error_message="Test failed",
                traceback=traceback[:1000]
            ))
            
        return failures
        
    def _extract_source_location(self, traceback: str) -> Tuple[str, int]:
        """Extract source file and line from traceback."""
        # Pattern: file.py:123
        pattern = r'([\w/\\]+\.py):(\d+)'
        matches = re.findall(pattern, traceback)
        
        # Get last non-test file match
        for file, line in reversed(matches):
            if 'test_' not in file and 'conftest' not in file:
                return file, int(line)
                
        return '', 0


class AIAutoFixer:
    """Uses AI to generate fixes for test failures."""
    
    SYSTEM_PROMPT = """You are an expert Python debugger. Analyze test failures and suggest fixes.

For each failure:
1. Understand the error type and message
2. Identify the root cause in the source code
3. Suggest a minimal fix that resolves the issue
4. Provide the fix as a code diff

Output JSON format:
{
    "analysis": "What went wrong and why",
    "root_cause": "The specific bug in the code",
    "fix_description": "What the fix does",
    "original_code": "the buggy code snippet",
    "fixed_code": "the corrected code snippet",
    "patch": "unified diff format patch"
}
"""
    
    def __init__(self, api_key: Optional[str] = None):
        # Support both OpenAI and Gemini
        self.openai_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.gemini_key = os.environ.get("GEMINI_API_KEY")
        
        if self.openai_key:
            self.api_type = "openai"
            self.api_key = self.openai_key
        elif self.gemini_key:
            self.api_type = "gemini"
            self.api_key = self.gemini_key
        else:
            self.api_type = None
            self.api_key = None or os.environ.get("GEMINI_API_KEY")
        
    def load_source_code(self, file_path: str, line: int, context: int = 5) -> str:
        """Load source code around the error line."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            start = max(0, line - context - 1)
            end = min(len(lines), line + context)
            
            code_lines = []
            for i, l in enumerate(lines[start:end], start=start+1):
                marker = ">>> " if i == line else "    "
                code_lines.append(f"{marker}{i}: {l.rstrip()}")
                
            return '\n'.join(code_lines)
            
        except Exception:
            return ""
            
    def generate_fix(self, failure: TestFailure) -> Optional[FixSuggestion]:
        """Generate fix suggestion for a failure."""
        # Load source code if available
        if failure.source_file and failure.source_line:
            failure.source_code = self.load_source_code(failure.source_file, failure.source_line)
            
        prompt = f"""Analyze and fix this test failure:

Test: {failure.test_name}
Error Type: {failure.error_type}
Error Message: {failure.error_message}

Traceback:
```
{failure.traceback[:2000]}
```

Source Code (error at >>> line):
```python
{failure.source_code}
```

Provide a fix in JSON format.
"""
        
        if self.api_key:
            result = self._call_api(prompt)
        else:
            result = self._generate_mock_fix(failure)
            
        if result:
            return FixSuggestion(
                file=failure.source_file,
                description=result.get('fix_description', ''),
                original_code=result.get('original_code', ''),
                fixed_code=result.get('fixed_code', ''),
                patch=result.get('patch', '')
            )
        return None
        
    def _call_api(self, prompt: str) -> dict:
        """Call AI API (OpenAI or Gemini)."""
        if self.api_type == "gemini":
            return self._call_gemini_api(prompt)
        else:
            return self._call_openai_api(prompt)
    
    def _call_openai_api(self, prompt: str) -> dict:
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
            ],
            "response_format": {"type": "json_object"}
        }
        
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode())
                content = result["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            return {}
    
    def _call_gemini_api(self, prompt: str) -> dict:
        """Call Gemini API."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        
        full_prompt = self.SYSTEM_PROMPT + "\n\nAnalyze and respond in JSON format:\n\n" + prompt
        
        data = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }]
        }
        
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode())
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                # Clean JSON response
                text = text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                return json.loads(text.strip())
        except json.JSONDecodeError as e:
            print(f"Gemini JSON Parse Error: {e}")
            print(f"Raw response: {text[:200] if 'text' in dir() else 'N/A'}")
            return {}
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return {}
            
    def _generate_mock_fix(self, failure: TestFailure) -> dict:
        """Generate mock fix when API unavailable."""
        return {
            "analysis": f"Test {failure.test_name} failed with {failure.error_type}",
            "root_cause": "Unable to determine without API - configure OPENAI_API_KEY",
            "fix_description": "Manual review required",
            "original_code": failure.source_code.split('\n')[0] if failure.source_code else "",
            "fixed_code": "# TODO: Apply fix",
            "patch": f"# Patch for {failure.source_file}:{failure.source_line}\n# Requires manual review"
        }
        
    def apply_patch(self, suggestion: FixSuggestion) -> bool:
        """Apply the fix patch to the source file."""
        if not suggestion.original_code or not suggestion.fixed_code:
            return False
            
        try:
            with open(suggestion.file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Simple replacement
            if suggestion.original_code in content:
                new_content = content.replace(suggestion.original_code, suggestion.fixed_code, 1)
                
                with open(suggestion.file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                    
                return True
        except Exception as e:
            print(f"Error applying patch: {e}")
            
        return False


def main():
    parser = argparse.ArgumentParser(description="AI AutoFix - Test Failure Fixer")
    parser.add_argument("--results", help="Test results file (XML or JSON)")
    parser.add_argument("--console", help="Console output file to parse")
    parser.add_argument("--apply", action="store_true", help="Apply fixes automatically")
    parser.add_argument("--output", default=".fixes", help="Output folder for patches")
    parser.add_argument("--project", default=".", help="Project root")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔧 AI AUTOFIX - Test Failure Fixer")
    print("=" * 60)
    
    # Parse test results
    result_parser = TestResultParser()  # Fixed: was shadowing argparse parser
    failures = []
    
    if args.results:
        if args.results.endswith('.xml'):
            failures = result_parser.parse_junit_xml(args.results)
        else:
            failures = result_parser.parse_json(args.results)
    elif args.console:
        with open(args.console, 'r') as f:
            failures = result_parser.parse_console_output(f.read())
    else:
        # Try to find test results
        for pattern in ['test_results.xml', 'pytest_output.txt', '.pytest_cache']:
            if os.path.exists(pattern):
                print(f"Found: {pattern}")
                
    if not failures:
        print("No test failures found")
        sys.exit(0)
        
    print(f"\n❌ Found {len(failures)} test failures")
    
    # Generate fixes
    fixer = AIAutoFixer()
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)
    
    fixes_applied = 0
    
    for failure in failures[:5]:  # Limit to 5 failures
        print(f"\n{'─' * 60}")
        print(f"🔍 Analyzing: {failure.test_name}")
        print(f"   Error: {failure.error_type}: {failure.error_message[:80]}")
        
        suggestion = fixer.generate_fix(failure)
        
        if suggestion:
            print(f"\n💡 Suggested Fix:")
            print(f"   {suggestion.description}")
            
            # Save patch file
            patch_file = output_dir / f"fix_{failure.test_name.replace('::', '_').replace('/', '_')}.patch"
            with open(patch_file, 'w') as f:
                f.write(f"# Fix for {failure.test_name}\n")
                f.write(f"# File: {suggestion.file}\n")
                f.write(f"# Description: {suggestion.description}\n\n")
                f.write(suggestion.patch)
                
            print(f"   📄 Patch saved: {patch_file}")
            
            if args.apply:
                if fixer.apply_patch(suggestion):
                    print(f"   ✅ Fix applied!")
                    fixes_applied += 1
                else:
                    print(f"   ⚠️ Could not apply automatically")
        else:
            print(f"   ⚠️ Could not generate fix")
            
    print("\n" + "=" * 60)
    print(f"📊 Summary: {fixes_applied}/{len(failures)} fixes applied")
    print(f"   Patches saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
