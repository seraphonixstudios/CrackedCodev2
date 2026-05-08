"""GitHub Integration v2.9.6 - Automated PR review and issue analysis.

Features:
  - Review pull requests for security/code quality
  - Analyze issues and suggest fixes
  - List repos, commits, branches
  - Post review comments back to GitHub

Usage:
    from src.github_integration import GitHubClient, create_github_client
    gh = create_github_client(token="ghp_...")
    review = gh.review_pr("user/repo", 42, engine=engine)
"""

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

logger = get_logger("GitHub")


# â”€â”€ Data Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@dataclass
class PRReview:
    """A pull request review result."""
    repo: str
    pr_number: int
    title: str
    author: str
    additions: int
    deletions: int
    files_changed: int
    security_issues: List[Dict[str, Any]]
    code_issues: List[Dict[str, Any]]
    summary: str
    overall_verdict: str = ""
    confidence: float = 0.0


@dataclass
class IssueAnalysis:
    """An issue analysis result."""
    repo: str
    issue_number: int
    title: str
    summary: str
    suggested_fix: str
    related_files: List[str]
    confidence: float = 0.0


# â”€â”€ GitHub API Client â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class GitHubClient:
    """GitHub API client for repository operations."""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self._session = None
    
    def _get_session(self):
        """Get or create HTTP session."""
        if self._session is None:
            import requests
            self._session = requests.Session()
            if self.token:
                self._session.headers["Authorization"] = f"token {self.token}"
            self._session.headers["Accept"] = "application/vnd.github.v3+json"
        return self._session
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a GitHub API request."""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            session = self._get_session()
            response = session.request(method, url, timeout=30, **kwargs)
            
            if response.status_code == 404:
                raise ValueError(f"Resource not found: {endpoint}")
            elif response.status_code == 401:
                raise ValueError("Invalid GitHub token")
            elif response.status_code == 403:
                raise ValueError("GitHub API rate limit exceeded")
            elif response.status_code >= 400:
                raise ValueError(f"GitHub API error {response.status_code}: {response.text[:200]}")
            
            if response.status_code == 204:
                return {}
            
            return response.json()
        except Exception as e:
            logger.error(f"GitHub API request failed: {e}")
            raise
    
    def get_repo(self, repo: str) -> Dict[str, Any]:
        """Get repository information."""
        return self._request("GET", f"/repos/{repo}")
    
    def list_repos(self, username: str, per_page: int = 30) -> List[Dict[str, Any]]:
        """List repositories for a user."""
        return self._request("GET", f"/users/{username}/repos", params={"per_page": per_page})
    
    def get_pr(self, repo: str, pr_number: int) -> Dict[str, Any]:
        """Get pull request details."""
        return self._request("GET", f"/repos/{repo}/pulls/{pr_number}")
    
    def get_pr_diff(self, repo: str, pr_number: int) -> str:
        """Get pull request diff."""
        url = f"{self.BASE_URL}/repos/{repo}/pulls/{pr_number}"
        try:
            session = self._get_session()
            response = session.get(url, headers={"Accept": "application/vnd.github.v3.diff"}, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to get PR diff: {e}")
            return ""
    
    def get_pr_files(self, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Get files changed in a pull request."""
        return self._request("GET", f"/repos/{repo}/pulls/{pr_number}/files")
    
    def post_pr_comment(self, repo: str, pr_number: int, body: str) -> Dict[str, Any]:
        """Post a comment on a pull request."""
        return self._request("POST", f"/repos/{repo}/issues/{pr_number}/comments", json={"body": body})
    
    def get_issue(self, repo: str, issue_number: int) -> Dict[str, Any]:
        """Get issue details."""
        return self._request("GET", f"/repos/{repo}/issues/{issue_number}")
    
    def list_issues(self, repo: str, state: str = "open", per_page: int = 30) -> List[Dict[str, Any]]:
        """List issues for a repository."""
        return self._request("GET", f"/repos/{repo}/issues", params={"state": state, "per_page": per_page})
    
    def list_commits(self, repo: str, branch: str = "main", per_page: int = 30) -> List[Dict[str, Any]]:
        """List commits for a branch."""
        return self._request("GET", f"/repos/{repo}/commits", params={"sha": branch, "per_page": per_page})
    
    def get_rate_limit(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        return self._request("GET", "/rate_limit")
    
    # â”€â”€ AI-Powered Analysis â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    
    def review_pr(self, repo: str, pr_number: int, engine=None,
                  post_comment: bool = False) -> PRReview:
        """Review a pull request using AI analysis.
        
        Args:
            repo: Repository in "owner/name" format
            pr_number: Pull request number
            engine: CrackedCodeEngine instance for analysis
            post_comment: Whether to post review back to GitHub
        
        Returns:
            PRReview with security and code quality findings
        """
        logger.info(f"Reviewing PR #{pr_number} in {repo}")
        
        # Fetch PR data
        pr_data = self.get_pr(repo, pr_number)
        pr_files = self.get_pr_files(repo, pr_number)
        pr_diff = self.get_pr_diff(repo, pr_number)
        
        # Build analysis prompt
        files_summary = "\n".join([
            f"- {f['filename']} (+{f.get('additions', 0)} -{f.get('deletions', 0)})"
            for f in pr_files[:20]
        ])
        
        diff_excerpt = pr_diff[:8000] if pr_diff else "No diff available"
        
        analysis_prompt = f"""Review this pull request for security vulnerabilities and code quality issues.

PR: #{pr_number} - {pr_data.get('title', 'Untitled')}
Author: {pr_data.get('user', {}).get('login', 'unknown')}
Files changed: {len(pr_files)}

Files:
{files_summary}

Diff (excerpt):
```diff
{diff_excerpt}
```

Provide:
1. Security analysis: Any vulnerabilities, injection risks, unsafe defaults, credential leaks?
2. Code quality: Bugs, anti-patterns, missing error handling, performance issues?
3. Overall verdict: APPROVE, COMMENT, or REQUEST_CHANGES with confidence (0-1)

Format as JSON:
{{
  "security_issues": [{{"severity": "high|medium|low", "file": "...", "line": 0, "description": "...", "fix": "..."}}],
  "code_issues": [{{"severity": "high|medium|low", "file": "...", "line": 0, "description": "...", "fix": "..."}}],
  "summary": "Brief summary",
  "verdict": "APPROVE|COMMENT|REQUEST_CHANGES",
  "confidence": 0.85
}}
"""
        
        # Run AI analysis
        security_issues = []
        code_issues = []
        summary = "No AI analysis available"
        verdict = "COMMENT"
        confidence = 0.0
        
        if engine:
            try:
                import asyncio
                response = asyncio.run(engine.process(
                    prompt=analysis_prompt,
                    intent="review",
                ))
                
                if response.success:
                    # Try to parse JSON from response
                    import re
                    json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                    if json_match:
                        try:
                            result = json.loads(json_match.group())
                            security_issues = result.get("security_issues", [])
                            code_issues = result.get("code_issues", [])
                            summary = result.get("summary", summary)
                            verdict = result.get("verdict", verdict)
                            confidence = result.get("confidence", 0.0)
                        except json.JSONDecodeError:
                            summary = response.text[:500]
                    else:
                        summary = response.text[:500]
                else:
                    summary = f"Analysis failed: {response.error}"
            except Exception as e:
                logger.error(f"AI analysis failed: {e}")
                summary = f"Analysis error: {e}"
        
        review = PRReview(
            repo=repo,
            pr_number=pr_number,
            title=pr_data.get("title", ""),
            author=pr_data.get("user", {}).get("login", ""),
            additions=pr_data.get("additions", 0),
            deletions=pr_data.get("deletions", 0),
            files_changed=len(pr_files),
            security_issues=security_issues,
            code_issues=code_issues,
            summary=summary,
            overall_verdict=verdict,
            confidence=confidence,
        )
        
        # Post comment if requested
        if post_comment and self.token:
            try:
                comment_body = self._format_pr_review(review)
                self.post_pr_comment(repo, pr_number, comment_body)
                logger.info(f"Posted review comment to PR #{pr_number}")
            except Exception as e:
                logger.error(f"Failed to post review comment: {e}")
        
        return review
    
    def analyze_issue(self, repo: str, issue_number: int, engine=None) -> IssueAnalysis:
        """Analyze a GitHub issue and suggest fixes.
        
        Args:
            repo: Repository in "owner/name" format
            issue_number: Issue number
            engine: CrackedCodeEngine instance for analysis
        
        Returns:
            IssueAnalysis with summary and suggested fix
        """
        logger.info(f"Analyzing issue #{issue_number} in {repo}")
        
        issue = self.get_issue(repo, issue_number)
        
        title = issue.get("title", "")
        body = issue.get("body", "") or ""
        labels = [l["name"] for l in issue.get("labels", [])]
        
        analysis_prompt = f"""Analyze this GitHub issue and suggest a fix.

Issue #{issue_number}: {title}
Labels: {', '.join(labels)}

Description:
{body[:4000]}

Provide:
1. Brief summary of the issue
2. Root cause analysis
3. Suggested fix with code example
4. Related files that might need changes

Format as JSON:
{{
  "summary": "...",
  "suggested_fix": "...",
  "related_files": ["file1.py", "file2.py"],
  "confidence": 0.8
}}
"""
        
        summary = f"Issue: {title}"
        suggested_fix = "No AI analysis available"
        related_files = []
        confidence = 0.0
        
        if engine:
            try:
                import asyncio
                response = asyncio.run(engine.process(
                    prompt=analysis_prompt,
                    intent="debug",
                ))
                
                if response.success:
                    import re
                    json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                    if json_match:
                        try:
                            result = json.loads(json_match.group())
                            summary = result.get("summary", summary)
                            suggested_fix = result.get("suggested_fix", suggested_fix)
                            related_files = result.get("related_files", [])
                            confidence = result.get("confidence", 0.0)
                        except json.JSONDecodeError:
                            summary = response.text[:500]
                    else:
                        summary = response.text[:500]
                else:
                    summary = f"Analysis failed: {response.error}"
            except Exception as e:
                logger.error(f"AI analysis failed: {e}")
                summary = f"Analysis error: {e}"
        
        return IssueAnalysis(
            repo=repo,
            issue_number=issue_number,
            title=title,
            summary=summary,
            suggested_fix=suggested_fix,
            related_files=related_files,
            confidence=confidence,
        )
    
    def _format_pr_review(self, review: PRReview) -> str:
        """Format PR review as GitHub markdown comment."""
        lines = [
            f"## ðŸ¤– CrackedCode AI Review",
            f"",
            f"**Verdict:** {review.overall_verdict} (confidence: {review.confidence:.0%})",
            f"",
            f"### Summary",
            f"{review.summary}",
            f"",
        ]
        
        if review.security_issues:
            lines.extend([
                f"### ðŸ”’ Security Issues ({len(review.security_issues)})",
                f"",
            ])
            for issue in review.security_issues:
                severity = issue.get("severity", "medium").upper()
                emoji = "ðŸš¨" if severity == "HIGH" else "âš ï¸" if severity == "MEDIUM" else "â„¹ï¸"
                lines.extend([
                    f"{emoji} **{severity}** - `{issue.get('file', 'unknown')}` line {issue.get('line', 'N/A')}",
                    f"> {issue.get('description', 'No description')}",
                    f"> Fix: {issue.get('fix', 'No fix suggested')}",
                    f"",
                ])
        
        if review.code_issues:
            lines.extend([
                f"### ðŸ“ Code Quality ({len(review.code_issues)})",
                f"",
            ])
            for issue in review.code_issues:
                severity = issue.get("severity", "medium").upper()
                emoji = "ðŸš¨" if severity == "HIGH" else "âš ï¸" if severity == "MEDIUM" else "â„¹ï¸"
                lines.extend([
                    f"{emoji} **{severity}** - `{issue.get('file', 'unknown')}` line {issue.get('line', 'N/A')}",
                    f"> {issue.get('description', 'No description')}",
                    f"> Fix: {issue.get('fix', 'No fix suggested')}",
                    f"",
                ])
        
        if not review.security_issues and not review.code_issues:
            lines.extend([
                f"### âœ… No issues found",
                f"",
            ])
        
        lines.extend([
            f"---",
            f"*Reviewed by CrackedCode v2.9.6*",
        ])
        
        return "\n".join(lines)


def create_github_client(token: Optional[str] = None) -> GitHubClient:
    """Create a GitHub client instance."""
    return GitHubClient(token=token)

