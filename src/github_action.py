"""GitHub Action Runner v2.8.1 - Run CrackedCode AI review in CI/CD.

Usage as GitHub Action:
    - uses: actions/checkout@v4
    - run: python src/github_action.py
      env:
        CRACKEDCODE_API_URL: http://localhost:8080
        CRACKEDCODE_API_KEY: secret
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        GITHUB_REPOSITORY: ${{ github.repository }}
        PR_NUMBER: ${{ github.event.pull_request.number }}

Usage locally:
    python src/github_action.py --repo user/repo --pr 42 --api-url http://localhost:8080
"""

import argparse
import json
import os
import sys
from typing import Optional

from src.logger_config import get_logger

logger = get_logger("GitHubAction")


def run_review(api_url: str, api_key: Optional[str], repo: str, pr_number: int,
               github_token: Optional[str], post_comment: bool = True) -> dict:
    """Run AI review on a PR via CrackedCode API.
    
    Returns:
        dict with review results
    """
    import requests
    
    review_url = f"{api_url}/github/review-pr"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    
    payload = {
        "repo": repo,
        "pr_number": pr_number,
        "post_comment": False
    }
    
    try:
        response = requests.post(review_url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        review = response.json()
        logger.info(f"Review received: {review.get('verdict', 'UNKNOWN')} for PR #{pr_number}")
        return review
    except Exception as e:
        logger.error(f"Review request failed: {e}")
        raise


def post_pr_comment(repo: str, pr_number: int, token: str, body: str) -> bool:
    """Post a comment to a GitHub PR."""
    import requests
    
    comment_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.post(comment_url, json={"body": body}, headers=headers, timeout=30)
        response.raise_for_status()
        logger.info(f"Posted comment to PR #{pr_number}")
        return True
    except Exception as e:
        logger.error(f"Failed to post comment: {e}")
        return False


def format_review_comment(review: dict) -> str:
    """Format review as GitHub markdown comment."""
    verdict = review.get("verdict", "COMMENT")
    confidence = review.get("confidence", 0)
    summary = review.get("summary", "No summary available")
    security_count = review.get("security_issues_count", 0)
    code_count = review.get("code_issues_count", 0)
    
    verdict_emoji = {
        "APPROVE": "✅",
        "COMMENT": "💬",
        "REQUEST_CHANGES": "🛑"
    }.get(verdict, "💬")
    
    return f"""## {verdict_emoji} CrackedCode AI Review

**Verdict:** {verdict} (confidence: {confidence:.0%})

### Summary
{summary}

### Findings
- 🔒 Security issues: {security_count}
- 📝 Code quality issues: {code_count}

---
*Reviewed by CrackedCode v2.8.1*
"""


def set_output(name: str, value: str):
    """Set GitHub Actions output."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{name}={value}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="CrackedCode GitHub Action")
    parser.add_argument("--api-url", default=os.environ.get("CRACKEDCODE_API_URL", ""),
                        help="CrackedCode API URL")
    parser.add_argument("--api-key", default=os.environ.get("CRACKEDCODE_API_KEY", ""),
                        help="CrackedCode API key")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""),
                        help="Repository in owner/name format")
    parser.add_argument("--pr", type=int, default=int(os.environ.get("PR_NUMBER", "0")),
                        help="Pull request number")
    parser.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN", ""),
                        help="GitHub token for posting comments")
    parser.add_argument("--no-comment", action="store_true",
                        help="Don't post comment to PR")
    parser.add_argument("--fail-on-security", action="store_true",
                        help="Exit with error if security issues found")
    
    args = parser.parse_args()
    
    if not args.api_url:
        logger.error("CRACKEDCODE_API_URL not set")
        sys.exit(1)
    
    if not args.repo:
        logger.error("Repository not specified")
        sys.exit(1)
    
    if not args.pr:
        logger.error("PR number not specified")
        sys.exit(1)
    
    try:
        # Run review
        review = run_review(
            api_url=args.api_url,
            api_key=args.api_key or None,
            repo=args.repo,
            pr_number=args.pr,
            github_token=args.github_token or None,
        )
        
        # Format and post comment
        comment_body = format_review_comment(review)
        
        if not args.no_comment and args.github_token:
            post_pr_comment(args.repo, args.pr, args.github_token, comment_body)
        else:
            print(comment_body)
        
        # Set outputs
        set_output("verdict", review.get("verdict", "COMMENT"))
        set_output("security_issues", str(review.get("security_issues_count", 0)))
        set_output("code_issues", str(review.get("code_issues_count", 0)))
        set_output("confidence", str(review.get("confidence", 0)))
        
        # Fail on security if requested
        if args.fail_on_security and review.get("security_issues_count", 0) > 0:
            logger.error(f"Found {review['security_issues_count']} security issues")
            sys.exit(1)
        
        logger.info("AI review completed successfully")
        
    except Exception as e:
        logger.error(f"AI review failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
