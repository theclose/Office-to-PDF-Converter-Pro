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
    
    SYSTEM_PROMPT = """You are a Senior Software Architect reviewing code changes.
    
Your task is to:
1. Identify potential bugs, security issues, and performance problems
2. Suggest improvements for code quality and maintainability
3. Check for best practices and design patterns
4. Rate the overall quality (1-10)

Format your response as JSON:
{
    "overall_score": 8,
    "summary": "Brief summary of the changes",
    "issues": [
        {"file": "path/file.py", "line": 10, "severity": "warning", "message": "Description"},
        ...
    ],
    "suggestions": ["Suggestion 1", "Suggestion 2"]
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
        """Post review comment to GitHub PR."""
        if not self.github_token:
            print("⚠️ GITHUB_TOKEN not set - cannot post comment")
            return False
            
        url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Content-Type": "application/json"
        }
        
        # Format comment
        issues_text = ""
        for issue in review.get("issues", []):
            icon = "🔴" if issue["severity"] == "error" else "🟡" if issue["severity"] == "warning" else "ℹ️"
            issues_text += f"- {icon} **{issue['file']}:{issue.get('line', '?')}** - {issue['message']}\n"
            
        suggestions_text = "\n".join(f"- {s}" for s in review.get("suggestions", []))
        
        body = f"""## 🤖 AI Code Review

**Overall Score**: {review.get('overall_score', '?')}/10

### Summary
{review.get('summary', 'No summary available')}

### Issues Found
{issues_text or 'No issues found! ✅'}

### Suggestions
{suggestions_text or 'No additional suggestions'}

---
*Generated by AI Reviewer*
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
        """Print review to console."""
        print("\n" + "=" * 60)
        print("🤖 AI CODE REVIEW")
        print("=" * 60)
        print(f"\n📊 Overall Score: {review.get('overall_score', '?')}/10")
        print(f"\n📝 Summary: {review.get('summary', 'N/A')}")
        
        print("\n⚠️ Issues:")
        for issue in review.get("issues", []):
            icon = "🔴" if issue["severity"] == "error" else "🟡" if issue["severity"] == "warning" else "ℹ️"
            print(f"  {icon} {issue['file']}:{issue.get('line', '?')} - {issue['message']}")
            
        print("\n💡 Suggestions:")
        for s in review.get("suggestions", []):
            print(f"  - {s}")
            
        print("=" * 60)


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
