"""
AI Code Reviewer - GitHub PR Integration
=========================================
1. Uses git diff to get changed code
2. Calls AI API (OpenAI/Gemini) with "Senior Architect" role
3. Comments directly on Pull Request via GitHub API

Usage:
    python ai_reviewer.py --pr=123 --repo=owner/repo
    python ai_reviewer.py --diff-only  # Just show diff, no API call
    
Environment Variables:
    OPENAI_API_KEY or GEMINI_API_KEY
    GITHUB_TOKEN
"""

import os
import sys
import json
import subprocess
import argparse
import re
from typing import Optional, Dict, List
from dataclasses import dataclass
import urllib.request
import urllib.error


@dataclass
class ReviewComment:
    """A review comment for a specific file/line."""
    file: str
    line: int
    message: str
    severity: str  # info, warning, error


class AIReviewer:
    """AI-powered code reviewer with GitHub integration."""
    
    SYSTEM_PROMPT = """
You are the "Omniscient Code Auditor" — an advanced AI engine tailored for high-stakes Python environments. 
Your capability encompasses the combined expertise of a Principal Software Architect, a Lead Security Researcher (OWASP/CWE), and a Senior SRE.

YOUR MISSION: Perform a forensic-level analysis of the provided Git Diff within the context of the full file. 
You act as the final "Quality Gate" before deployment. Your standards are absolute.

### 🔬 THE 5-LAYER DEEP SCAN PROTOCOL
You must evaluate the code through these 5 strict lenses:

1.  **LAYER 1: SECURITY & VULNERABILITY (Zero Tolerance)**
    -   Perform "Taint Analysis" mentally: Trace user inputs to SQL queries, shell commands, or HTML rendering.
    -   Detect OWASP Top 10 risks: Insecure Deserialization (pickle), SQLi, SSRF, XSS, and Broken Access Control.
    -   Identify Hardcoded Secrets (API Keys, JWT tokens, passwords) using entropy heuristics.

2.  **LAYER 2: ALGORITHMIC & PERFORMANCE (Big-O Focus)**
    -   Detect Time Complexity regressions: Look for O(n^2) loops nested in critical paths or DB transactions.
    -   Analyze Memory Complexity: Identify uncontrolled generator usage, massive list comprehensions, or potential memory leaks.
    -   Async/Await Pitfalls: Flag blocking I/O calls (e.g., `requests.get`, `time.sleep`) inside `async def` functions.

3.  **LAYER 3: ROBUSTNESS & RELIABILITY**
    -   Error Handling: Reject generic `except Exception:` or `pass`. Demand specific exception handling.
    -   Concurrency Safety: Check for Race Conditions in shared variables (global state, class attributes).
    -   Type Safety: Enforce Python Type Hinting (PEP 484). Flag missing types in public function signatures.

4.  **LAYER 4: ARCHITECTURE & MAINTAINABILITY (SOLID)**
    -   Cyclomatic Complexity: Flag functions with too many branches (if/else) > 10.
    -   Coupling: Identify violation of Dependency Inversion or Single Responsibility Principle.
    -   DRY (Don't Repeat Yourself): Detect copy-pasted logic that should be refactored into utility functions.

5.  **LAYER 5: MODERN PYTHONIC STANDARDS**
    -   Enforce usage of modern features (e.g., `f-strings` over `.format()`, `pathlib` over `os.path`, dataclasses/pydantic over raw dicts).

### 🛡️ ANTI-HALLUCINATION RULES
-   **Context verification:** Do NOT flag an issue if the definition exists in the `Full File Content` but is not visible in the `Diff`.
-   **False Positive Reduction:** Only report issues with HIGH or MEDIUM confidence. If you are unsure, do not report it.

### 📊 SCORING ALGORITHM
-   **100:** Perfection. Meets all 5 layers. (Rare).
-   **90-99:** Excellent. Minor styling/nitpicks only.
-   **75-89:** Good. Some actionable feedback but safe to merge.
-   **<75:** REJECT. Contains Security risks, Logical bugs, or blocking I/O.

### 📝 OUTPUT FORMAT (STRICT JSON ONLY)
Return raw JSON. No Markdown. No intro/outro text.
{
    "score": <integer 0-100>,
    "summary": "<Technical Executive Summary of the impact (max 2 sentences)>",
    "security_risk": <boolean>,
    "issues": [
        {
            "category": "SECURITY" | "PERFORMANCE" | "LOGIC" | "MAINTAINABILITY",
            "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
            "line": <line_number_in_diff_or_closest_context>,
            "message": "<Concise, technical description of the flaw>",
            "rationale": "<Why is this an issue? Cite specific principles (e.g., 'Violates OWASP A03', 'O(n^2) complexity')>",
            "suggestion": "<Production-ready Python code fix. Use comments to explain changes.>"
        }
    ]
}
"""
    
    def __init__(self, api_key: Optional[str] = None, api_type: str = "openai"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        self.api_type = api_type
        self.github_token = os.environ.get("GITHUB_TOKEN")
        
    def get_git_diff(self, base: str = "HEAD~1", target: str = "HEAD") -> str:
        """Get git diff between two refs."""
        try:
            result = subprocess.run(
                ["git", "diff", base, target, "--", "*.py"],
                capture_output=True, text=True
            )
            return result.stdout
        except Exception as e:
            print(f"Error getting git diff: {e}")
            return ""
            
    def get_pr_diff(self, repo: str, pr_number: int) -> str:
        """Get diff from a GitHub Pull Request."""
        if not self.github_token:
            print("⚠️ GITHUB_TOKEN not set")
            return ""
            
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3.diff"
        }
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            print(f"Error fetching PR diff: {e}")
            return ""
            
    def call_openai(self, diff: str) -> dict:
        """Call OpenAI API for review."""
        if not self.api_key:
            return self._mock_review(diff)
            
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"Review these code changes:\n\n```diff\n{diff[:8000]}\n```"}
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
            print(f"API Error: {e}")
            return self._mock_review(diff)
            
    def call_gemini(self, diff: str) -> dict:
        """Call Gemini API for review."""
        if not self.api_key:
            return self._mock_review(diff)
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        
        data = {
            "contents": [{
                "parts": [{
                    "text": f"{self.SYSTEM_PROMPT}\n\nReview these changes:\n```diff\n{diff[:8000]}\n```"
                }]
            }]
        }
        
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode())
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return self._mock_review(diff)
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return self._mock_review(diff)
            
    def _mock_review(self, diff: str) -> dict:
        """Generate mock review when API is unavailable."""
        lines_changed = diff.count('\n+') + diff.count('\n-')
        files = set(re.findall(r'diff --git a/(.*?) b/', diff))
        
        return {
            "overall_score": 7,
            "summary": f"Reviewed {len(files)} files with {lines_changed} line changes",
            "issues": [
                {"file": list(files)[0] if files else "unknown", "line": 1, 
                 "severity": "info", "message": "Mock review - API key not configured"}
            ],
            "suggestions": [
                "Configure OPENAI_API_KEY or GEMINI_API_KEY for real AI review",
                "Ensure code follows project conventions"
            ]
        }
        
    def post_pr_comment(self, repo: str, pr_number: int, review: dict) -> bool:
        """Post review comment to GitHub PR with enhanced formatting."""
        if not self.github_token:
            print("⚠️ GITHUB_TOKEN not set - cannot post comment")
            return False
            
        url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Content-Type": "application/json"
        }
        
        score = review.get('score', review.get('overall_score', 0))
        security_risk = review.get('security_risk', False)
        
        # Build issues table
        issues_table = ""
        if review.get("issues"):
            issues_table = "| Type | Sev | Line | Issue | Rationale | Fix |\n"
            issues_table += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
            
            for issue in review.get("issues", []):
                # Icon mapping
                sev_icon = "🔴" if issue.get('severity') in ['CRITICAL', 'HIGH'] else "🟡" if issue.get('severity') == 'MEDIUM' else "🟢"
                cat_icons = {
                    "SECURITY": "🔒",
                    "PERFORMANCE": "🚀",
                    "LOGIC": "🧠",
                    "MAINTAINABILITY": "🧹"
                }
                cat_icon = cat_icons.get(issue.get('category', ''), "❓")
                
                suggestion = issue.get('suggestion', '').replace('\n', '<br>')
                
                issues_table += (
                    f"| {cat_icon} {issue.get('category', 'UNKNOWN')} "
                    f"| {sev_icon} {issue.get('severity', 'MEDIUM')} "
                    f"| {issue.get('line', '-')} "
                    f"| {issue.get('message', '')} "
                    f"| *{issue.get('rationale', '')}* "
                    f"| ```python\n{suggestion}\n``` |\n"
                )
        
        # Security warning
        security_warning = ""
        if security_risk:
            security_warning = "\n> [!CAUTION]\n> **SECURITY RISK DETECTED** - This PR introduces potential security vulnerabilities and should NOT be merged without fixes.\n\n"
        
        body = f"""## 🔬 Omniscient Code Auditor - Review Complete

**Overall Score**: {score}/100 {'❌ FAIL' if score < 75 or security_risk else '⚠️ REVIEW' if score < 90 else '✅ PASS'}

{security_warning}

### 📝 Executive Summary
{review.get('summary', 'No summary available')}

### ⚠️ Issues Found
{issues_table if issues_table else '✅ No issues detected!'}

---
*Generated by Omniscient Code Auditor - 5-Layer Deep Scan Protocol*
"""
        
        data = {"body": body}
        
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
            with urllib.request.urlopen(req) as response:
                print(f"✅ Posted review comment to PR #{pr_number}")
                return True
        except Exception as e:
            print(f"Error posting comment: {e}")
            return False
            
    def review(self, diff: str) -> dict:
        """Perform AI review on diff."""
        if self.api_type == "gemini":
            return self.call_gemini(diff)
        return self.call_openai(diff)
        
    def print_review(self, review: dict):
        """Print review to console with enhanced formatting."""
        print("\n" + "=" * 70)
        print("🔬 OMNISCIENT CODE AUDITOR - FORENSIC ANALYSIS")
        print("=" * 70)
        
        score = review.get('score', review.get('overall_score', 0))
        security_risk = review.get('security_risk', False)
        
        # Score with color coding
        if score >= 90:
            score_icon = "✅"
        elif score >= 75:
            score_icon = "⚠️"
        else:
            score_icon = "❌"
            
        print(f"\n📊 Overall Score: {score_icon} {score}/100")
        if security_risk:
            print(f"🚨 SECURITY RISK DETECTED - FAIL BUILD")
        print(f"\n📝 Summary: {review.get('summary', 'N/A')}")
        
        issues = review.get("issues", [])
        if issues:
            print(f"\n⚠️ Issues Found: {len(issues)}\n")
            
            # Category icons
            cat_icons = {
                "SECURITY": "🔒",
                "PERFORMANCE": "🚀",
                "LOGIC": "🧠",
                "MAINTAINABILITY": "🧹"
            }
            
            # Severity icons
            sev_icons = {
                "CRITICAL": "🔴",
                "HIGH": "🔴",
                "MEDIUM": "🟡",
                "LOW": "🟢"
            }
            
            # Print table header
            print("┌─────────────────┬──────────┬──────┬─────────────────────────────────┐")
            print("│ Type            │ Severity │ Line │ Issue                           │")
            print("├─────────────────┼──────────┼──────┼─────────────────────────────────┤")
            
            for issue in issues:
                cat = issue.get('category', 'UNKNOWN')
                sev = issue.get('severity', 'MEDIUM')
                line = str(issue.get('line', '-')).ljust(4)
                msg = issue.get('message', '')[:30].ljust(30)
                
                cat_icon = cat_icons.get(cat, "❓")
                sev_icon = sev_icons.get(sev, "⚪")
                
                print(f"│ {cat_icon} {cat:<13} │ {sev_icon} {sev:<6} │ {line} │ {msg} │")
                
                # Print rationale and suggestion
                rationale = issue.get('rationale', '')
                if rationale:
                    print(f"│   Rationale: {rationale[:60]:<60} │")
                    
                suggestion = issue.get('suggestion', '')
                if suggestion:
                    print(f"│   Fix: {suggestion[:64]:<64} │")
                print("├─────────────────┼──────────┼──────┼─────────────────────────────────┤")
                
            print("└─────────────────┴──────────┴──────┴─────────────────────────────────┘")
        else:
            print("\n✅ No issues found!")
            
        print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="AI Code Reviewer")
    parser.add_argument("--pr", type=int, help="Pull Request number")
    parser.add_argument("--repo", help="GitHub repo (owner/repo)")
    parser.add_argument("--base", default="HEAD~1", help="Base ref for diff")
    parser.add_argument("--target", default="HEAD", help="Target ref for diff")
    parser.add_argument("--diff-only", action="store_true", help="Just show diff")
    parser.add_argument("--api", choices=["openai", "gemini"], default="openai")
    parser.add_argument("--post-comment", action="store_true", help="Post comment to PR")
    
    args = parser.parse_args()
    
    reviewer = AIReviewer(api_type=args.api)
    
    # Get diff
    if args.pr and args.repo:
        diff = reviewer.get_pr_diff(args.repo, args.pr)
    else:
        diff = reviewer.get_git_diff(args.base, args.target)
        
    if not diff:
        print("No changes to review")
        sys.exit(0)
        
    if args.diff_only:
        print(diff)
        sys.exit(0)
        
    # Perform review
    print("🔍 Analyzing code changes...")
    review = reviewer.review(diff)
    reviewer.print_review(review)
    
    # Post to PR if requested
    if args.post_comment and args.pr and args.repo:
        reviewer.post_pr_comment(args.repo, args.pr, review)


if __name__ == "__main__":
    main()
