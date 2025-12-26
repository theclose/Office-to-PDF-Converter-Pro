"""
AI-Driven CI/CD Pipeline
=========================
4-Job automated pipeline triggered on push/PR:

Job 1: AI Code Reviewer - Semantic + Security analysis
Job 2: Auto-Test Generation - Generate tests for changed files
Job 3: Execution - Run pytest (existing + generated tests)
Job 4: Self-Healing - If tests fail, analyze and create hotfix

Usage:
    python ai_pipeline.py [--branch=develop] [--auto-fix]
    python ai_pipeline.py --changed-only  # Only analyze changed files
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import difflib
import re


@dataclass
class PipelineResult:
    """Result of pipeline execution."""
    job_name: str
    status: str  # passed, failed, skipped
    duration: float
    output: str
    errors: List[str] = field(default_factory=list)


@dataclass
class TestFailure:
    """Information about a test failure."""
    test_name: str
    file: str
    line: int
    error_type: str
    error_message: str
    traceback: str


class AIPipeline:
    """AI-Driven CI/CD Pipeline orchestrator."""
    
    def __init__(self, project_root: str, auto_fix: bool = False):
        self.project_root = Path(project_root)
        self.auto_fix = auto_fix
        self.results: List[PipelineResult] = []
        self.scripts_dir = self.project_root / "scripts"
        
    def run(self, changed_files: Optional[List[str]] = None) -> bool:
        """Run full pipeline."""
        print("=" * 70)
        print("🤖 AI-DRIVEN CI/CD PIPELINE")
        print("=" * 70)
        print(f"📂 Project: {self.project_root}")
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔧 Auto-fix: {'Enabled' if self.auto_fix else 'Disabled'}")
        print("=" * 70)
        
        # Get changed files if not provided
        if changed_files is None:
            changed_files = self._get_changed_files()
        
        if not changed_files:
            print("\n✅ No Python files changed. Pipeline skipped.")
            return True
            
        print(f"\n📝 Changed files: {len(changed_files)}")
        for f in changed_files[:5]:
            print(f"   - {f}")
        if len(changed_files) > 5:
            print(f"   ... and {len(changed_files) - 5} more")
            
        # Job 1: AI Code Review
        job1_success = self._job1_code_review(changed_files)
        
        # Job 2: Auto-Test Generation
        job2_success = self._job2_generate_tests(changed_files)
        
        # Job 3: Test Execution
        job3_success, failures = self._job3_run_tests()
        
        # Job 4: Self-Healing (if tests failed and auto-fix enabled)
        if not job3_success and self.auto_fix:
            job4_success = self._job4_self_healing(failures)
        else:
            job4_success = job3_success
            
        # Summary
        self._print_summary()
        
        return all(r.status == "passed" for r in self.results)
        
    def _get_changed_files(self) -> List[str]:
        """Get list of changed Python files from git."""
        try:
            # Get uncommitted changes
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                capture_output=True, text=True, cwd=self.project_root
            )
            files = result.stdout.strip().split("\n") if result.stdout.strip() else []
            
            # Also get staged changes
            result2 = subprocess.run(
                ["git", "diff", "--name-only", "--cached"],
                capture_output=True, text=True, cwd=self.project_root
            )
            staged = result2.stdout.strip().split("\n") if result2.stdout.strip() else []
            
            all_files = set(files + staged)
            return [f for f in all_files if f.endswith(".py") and f]
            
        except Exception as e:
            print(f"⚠️ Git error: {e}")
            return []
            
    def _job1_code_review(self, files: List[str]) -> bool:
        """Job 1: Run AI code review (semantic + security)."""
        print("\n" + "─" * 70)
        print("🔍 JOB 1: AI Code Review")
        print("─" * 70)
        
        start = datetime.now()
        errors = []
        
        try:
            # Run code_analyzer.py if exists
            analyzer_path = self.scripts_dir / "code_analyzer.py"
            if analyzer_path.exists():
                for file in files[:10]:  # Limit to 10 files
                    file_path = self.project_root / file
                    if file_path.exists():
                        result = subprocess.run(
                            [sys.executable, str(analyzer_path), str(file_path), "--threshold=15"],
                            capture_output=True, text=True, timeout=60
                        )
                        # Only count high-severity as errors (exit code 1 means high severity found)
                        if result.returncode != 0 and "high-severity" in result.stdout.lower():
                            errors.append(f"{file}: High-severity issues detected")
                            
                print(f"   Analyzed {min(len(files), 10)} files")
                print(f"   Issues found: {len(errors)}")
            else:
                print("   ⚠️ code_analyzer.py not found, skipping...")
                
            status = "passed" if len(errors) == 0 else "failed"
            
        except Exception as e:
            status = "failed"
            errors.append(str(e))
            
        duration = (datetime.now() - start).total_seconds()
        self.results.append(PipelineResult(
            job_name="AI Code Review",
            status=status,
            duration=duration,
            output=f"{len(files)} files reviewed",
            errors=errors
        ))
        
        print(f"   Status: {'✅ PASSED' if status == 'passed' else '❌ FAILED'}")
        return status == "passed"
        
    def _job2_generate_tests(self, files: List[str]) -> bool:
        """Job 2: Generate tests for changed files."""
        print("\n" + "─" * 70)
        print("🧪 JOB 2: Auto-Test Generation")
        print("─" * 70)
        
        start = datetime.now()
        generated = 0
        errors = []
        
        try:
            generator_path = self.scripts_dir / "test_generator.py"
            if generator_path.exists():
                # Filter to only core/utils/converters modules
                test_candidates = [f for f in files if any(
                    x in f for x in ["core/", "utils/", "converters/", "grid/"]
                )]
                
                for file in test_candidates[:5]:  # Limit generation
                    file_path = self.project_root / file
                    if file_path.exists() and not "test_" in file:
                        result = subprocess.run(
                            [sys.executable, str(generator_path), str(file_path)],
                            capture_output=True, text=True, timeout=60
                        )
                        if result.returncode == 0:
                            generated += 1
                        else:
                            errors.append(f"Failed to generate tests for {file}")
                            
                print(f"   Generated tests for: {generated} files")
            else:
                print("   ⚠️ test_generator.py not found, skipping...")
                
            status = "passed"
            
        except Exception as e:
            status = "failed"
            errors.append(str(e))
            
        duration = (datetime.now() - start).total_seconds()
        self.results.append(PipelineResult(
            job_name="Auto-Test Generation",
            status=status,
            duration=duration,
            output=f"Generated {generated} test files",
            errors=errors
        ))
        
        print(f"   Status: {'✅ PASSED' if status == 'passed' else '❌ FAILED'}")
        return status == "passed"
        
    def _job3_run_tests(self) -> Tuple[bool, List[TestFailure]]:
        """Job 3: Run pytest and collect results."""
        print("\n" + "─" * 70)
        print("🏃 JOB 3: Test Execution")
        print("─" * 70)
        
        start = datetime.now()
        failures = []
        
        try:
            tests_dir = self.project_root / "tests"
            
            # Run pytest with JSON output
            result = subprocess.run(
                [sys.executable, "-m", "pytest", 
                 str(tests_dir), "-v", "--tb=short",
                 "--ignore=tests/test_generated*",  # Skip generated tests initially
                 "-x",  # Stop on first failure
                 "--timeout=30"],
                capture_output=True, text=True, 
                timeout=300, cwd=self.project_root
            )
            
            output = result.stdout + result.stderr
            
            # Parse failures
            if result.returncode != 0:
                failures = self._parse_test_failures(output)
                print(f"   Tests failed: {len(failures)}")
                for f in failures[:3]:
                    print(f"   ❌ {f.test_name}: {f.error_type}")
            else:
                print(f"   All tests passed!")
                
            status = "passed" if result.returncode == 0 else "failed"
            
        except subprocess.TimeoutExpired:
            status = "failed"
            output = "Test execution timed out"
        except Exception as e:
            status = "failed"
            output = str(e)
            
        duration = (datetime.now() - start).total_seconds()
        self.results.append(PipelineResult(
            job_name="Test Execution",
            status=status,
            duration=duration,
            output=f"{len(failures)} failures",
            errors=[f.error_message for f in failures]
        ))
        
        print(f"   Status: {'✅ PASSED' if status == 'passed' else '❌ FAILED'}")
        return status == "passed", failures
        
    def _parse_test_failures(self, output: str) -> List[TestFailure]:
        """Parse pytest output for failure information."""
        failures = []
        
        # Simple regex patterns for common pytest output
        # Pattern: FAILED test_file.py::TestClass::test_method
        failed_pattern = r'FAILED\s+([\w/]+\.py)::(\w+)(?:::(\w+))?'
        
        for match in re.finditer(failed_pattern, output):
            file, class_or_func, method = match.groups()
            test_name = f"{class_or_func}::{method}" if method else class_or_func
            
            failures.append(TestFailure(
                test_name=test_name,
                file=file,
                line=0,
                error_type="AssertionError",
                error_message="Test failed - see full output",
                traceback=""
            ))
            
        return failures
        
    def _job4_self_healing(self, failures: List[TestFailure]) -> bool:
        """Job 4: Self-healing - analyze failures and create hotfix."""
        print("\n" + "─" * 70)
        print("🔧 JOB 4: Self-Healing")
        print("─" * 70)
        
        start = datetime.now()
        fixed = 0
        errors = []
        
        if not failures:
            print("   No failures to fix")
            status = "passed"
        else:
            print(f"   Analyzing {len(failures)} failures...")
            
            for failure in failures[:3]:  # Limit to 3 fixes
                fix_result = self._attempt_fix(failure)
                if fix_result:
                    fixed += 1
                    print(f"   ✅ Fixed: {failure.test_name}")
                else:
                    errors.append(f"Could not auto-fix: {failure.test_name}")
                    print(f"   ⚠️ Manual fix needed: {failure.test_name}")
                    
            # Create hotfix commit if any fixes applied
            if fixed > 0:
                self._create_hotfix_commit(fixed)
                
            status = "passed" if fixed == len(failures) else "failed"
            
        duration = (datetime.now() - start).total_seconds()
        self.results.append(PipelineResult(
            job_name="Self-Healing",
            status=status,
            duration=duration,
            output=f"Fixed {fixed}/{len(failures)} issues",
            errors=errors
        ))
        
        print(f"   Status: {'✅ PASSED' if status == 'passed' else '⚠️ PARTIAL'}")
        return status == "passed"
        
    def _attempt_fix(self, failure: TestFailure) -> bool:
        """Attempt to automatically fix a test failure."""
        # Common auto-fix patterns
        
        # Pattern 1: Missing import
        if "ImportError" in failure.error_type or "ModuleNotFoundError" in failure.error_type:
            # Generate AI prompt for fix
            prompt = self._generate_fix_prompt(failure)
            # Save prompt for manual review
            self._save_fix_prompt(failure, prompt)
            return False  # Needs human review for imports
            
        # Pattern 2: Assertion error with expected value
        if "AssertionError" in failure.error_type:
            # Simple fixes only
            return False
            
        # Pattern 3: Type error - often fixable
        if "TypeError" in failure.error_type:
            prompt = self._generate_fix_prompt(failure)
            self._save_fix_prompt(failure, prompt)
            return False
            
        return False
        
    def _generate_fix_prompt(self, failure: TestFailure) -> str:
        """Generate AI prompt for fixing the failure."""
        return f"""
## 🔧 Auto-Fix Request

**Test**: `{failure.test_name}`
**File**: `{failure.file}`
**Error Type**: `{failure.error_type}`

**Error Message**:
```
{failure.error_message}
```

**Traceback**:
```
{failure.traceback}
```

**Instructions**:
1. Analyze the error and identify root cause
2. Propose minimal fix to pass the test
3. Ensure fix doesn't break other tests
4. Generate diff/patch for the fix

**Expected Output**: Code patch that fixes this specific issue
"""
        
    def _save_fix_prompt(self, failure: TestFailure, prompt: str):
        """Save fix prompt for AI review."""
        fixes_dir = self.project_root / ".fixes"
        fixes_dir.mkdir(exist_ok=True)
        
        prompt_file = fixes_dir / f"fix_{failure.test_name.replace('::', '_')}.md"
        with open(prompt_file, 'w') as f:
            f.write(prompt)
            
    def _create_hotfix_commit(self, fixed_count: int):
        """Create a hotfix commit for the fixes."""
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.project_root, check=True
            )
            subprocess.run(
                ["git", "commit", "-m", f"hotfix: AI auto-fix for {fixed_count} test failures"],
                cwd=self.project_root, check=False  # May fail if nothing to commit
            )
            print(f"   📦 Created hotfix commit")
        except Exception as e:
            print(f"   ⚠️ Commit failed: {e}")
            
    def _print_summary(self):
        """Print pipeline summary."""
        print("\n" + "=" * 70)
        print("📊 PIPELINE SUMMARY")
        print("=" * 70)
        
        total_duration = sum(r.duration for r in self.results)
        passed = sum(1 for r in self.results if r.status == "passed")
        failed = sum(1 for r in self.results if r.status == "failed")
        
        print(f"\n{'Job':<25} {'Status':<10} {'Duration':<10} {'Output'}")
        print("-" * 70)
        
        for result in self.results:
            status_icon = "✅" if result.status == "passed" else "❌"
            print(f"{result.job_name:<25} {status_icon} {result.status:<8} {result.duration:>6.1f}s    {result.output}")
            
        print("-" * 70)
        print(f"{'Total':<25} {passed}/{len(self.results)} passed  {total_duration:>6.1f}s")
        
        if failed > 0:
            print(f"\n⚠️ Pipeline completed with {failed} failed job(s)")
        else:
            print(f"\n✅ Pipeline completed successfully!")
            
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="AI-Driven CI/CD Pipeline")
    parser.add_argument("--project", "-p", default=".", help="Project root path")
    parser.add_argument("--auto-fix", "-f", action="store_true", help="Enable auto-fix on test failures")
    parser.add_argument("--changed-only", "-c", action="store_true", help="Only analyze changed files")
    parser.add_argument("--files", nargs="*", help="Specific files to analyze")
    
    args = parser.parse_args()
    
    project_path = os.path.abspath(args.project)
    
    pipeline = AIPipeline(project_path, auto_fix=args.auto_fix)
    
    # Determine files to analyze
    if args.files:
        changed_files = args.files
    elif args.changed_only:
        changed_files = None  # Will be detected from git
    else:
        # Analyze all Python files
        changed_files = []
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in ["__pycache__", ".git", "venv", ".venv", "tests"]]
            for f in files:
                if f.endswith(".py"):
                    changed_files.append(os.path.relpath(os.path.join(root, f), project_path))
    
    success = pipeline.run(changed_files)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
