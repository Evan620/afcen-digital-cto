"""GitHub integration: webhook verification, PR reading, and review posting."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import httpx
from github import Auth, Github, GithubException
from github.PullRequest import PullRequest

from src.config import settings
from src.models.schemas import PRWebhookEvent, PullRequestData, PRUser, PRHead, PRBase

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for GitHub API operations: read PRs, post reviews, manage labels."""

    def __init__(self, token: str | None = None, webhook_secret: str | None = None) -> None:
        self._token = token or settings.github_token
        self._webhook_secret = webhook_secret or settings.github_webhook_secret
        self._github: Github | None = None

    @property
    def github(self) -> Github:
        """Lazy-init PyGithub client."""
        if self._github is None:
            auth = Auth.Token(self._token)
            self._github = Github(auth=auth)
        return self._github

    # ── Webhook Verification ──

    def verify_webhook_signature(self, payload_body: bytes, signature_header: str) -> bool:
        """Verify that a webhook payload was actually sent by GitHub.

        Args:
            payload_body: Raw request body bytes
            signature_header: Value of X-Hub-Signature-256 header

        Returns:
            True if signature is valid
        """
        if not self._webhook_secret:
            logger.warning("No webhook secret configured — skipping signature verification")
            return True

        if not signature_header:
            return False

        expected_sig = "sha256=" + hmac.new(
            self._webhook_secret.encode("utf-8"),
            payload_body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_sig, signature_header)

    # ── Parse Webhook Events ──

    @staticmethod
    def parse_pr_event(payload: dict[str, Any]) -> PRWebhookEvent:
        """Parse a raw GitHub pull_request webhook payload into our model."""
        pr = payload["pull_request"]
        repo = payload["repository"]

        return PRWebhookEvent(
            action=payload["action"],
            repository_full_name=repo["full_name"],
            pull_request=PullRequestData(
                number=pr["number"],
                title=pr["title"],
                body=pr.get("body") or "",
                html_url=pr["html_url"],
                diff_url=pr["diff_url"],
                user=PRUser(
                    login=pr["user"]["login"],
                    avatar_url=pr["user"].get("avatar_url", ""),
                ),
                head=PRHead(ref=pr["head"]["ref"], sha=pr["head"]["sha"]),
                base=PRBase(ref=pr["base"]["ref"], sha=pr["base"]["sha"]),
                created_at=pr.get("created_at", ""),
                updated_at=pr.get("updated_at", ""),
            ),
        )

    # ── PR Operations ──

    def get_pr(self, repo_full_name: str, pr_number: int) -> PullRequest:
        """Fetch a PullRequest object from GitHub."""
        repo = self.github.get_repo(repo_full_name)
        return repo.get_pull(pr_number)

    def get_pr_diff(self, repo_full_name: str, pr_number: int) -> str:
        """Fetch the diff of a PR as a string."""
        pr = self.get_pr(repo_full_name, pr_number)
        # PyGithub doesn't directly provide diff, use httpx
        diff_url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github.diff",
        }
        resp = httpx.get(diff_url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.text

    def get_pr_files(self, repo_full_name: str, pr_number: int) -> list[dict[str, Any]]:
        """Get list of changed files in a PR with patch data."""
        pr = self.get_pr(repo_full_name, pr_number)
        files = []
        for f in pr.get_files():
            files.append({
                "filename": f.filename,
                "status": f.status,  # added, removed, modified, renamed
                "additions": f.additions,
                "deletions": f.deletions,
                "changes": f.changes,
                "patch": f.patch or "",
                "contents_url": f.contents_url,
            })
        return files

    def get_file_content(self, repo_full_name: str, path: str, ref: str = "main") -> str:
        """Fetch the full content of a file at a specific ref/sha."""
        repo = self.github.get_repo(repo_full_name)
        try:
            content = repo.get_contents(path, ref=ref)
            if isinstance(content, list):
                # It's a directory — shouldn't happen for a file path
                return ""
            return content.decoded_content.decode("utf-8")
        except GithubException as e:
            logger.warning("Could not fetch %s:%s — %s", repo_full_name, path, e)
            return ""

    # ── Review Posting ──

    def post_review(
        self,
        repo_full_name: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
        comments: list[dict] | None = None,
    ) -> None:
        """Submit a review on a PR.

        Args:
            repo_full_name: 'owner/repo'
            pr_number: PR number
            body: Overall review summary
            event: 'APPROVE', 'REQUEST_CHANGES', or 'COMMENT'
            comments: List of inline comments with 'path', 'position'/'line', 'body'
        """
        pr = self.get_pr(repo_full_name, pr_number)

        if comments:
            # Post review with inline comments
            pr.create_review(
                body=body,
                event=event,
                comments=[
                    {
                        "path": c["path"],
                        "line": c.get("line", 1),
                        "body": c["body"],
                    }
                    for c in comments
                ],
            )
        else:
            # Post review without inline comments
            pr.create_review(body=body, event=event)

        logger.info(
            "Posted %s review on %s PR #%d (%d inline comments)",
            event, repo_full_name, pr_number, len(comments or []),
        )

    # ── Labels ──

    def add_labels(self, repo_full_name: str, pr_number: int, labels: list[str]) -> None:
        """Add labels to a PR/issue."""
        repo = self.github.get_repo(repo_full_name)
        issue = repo.get_issue(pr_number)
        for label in labels:
            issue.add_to_labels(label)

    # ── Authenticated User ──

    def get_authenticated_user(self) -> str:
        """Get the login of the authenticated user."""
        user = self.github.get_user()
        return user.login

    # ── Health ──

    def health_check(self) -> bool:
        """Return True if GitHub API is reachable with valid token."""
        try:
            user = self.github.get_user()
            logger.debug("GitHub authenticated as %s", user.login)
            return True
        except Exception:
            return False
