"""LangChain tool wrappers for the Code Review agent."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool

from src.integrations.github_client import GitHubClient

logger = logging.getLogger(__name__)

# Shared client instance — initialized by the agent
_github_client: GitHubClient | None = None


def set_github_client(client: GitHubClient) -> None:
    """Set the GitHub client instance for tool use."""
    global _github_client
    _github_client = client


def _get_client() -> GitHubClient:
    if _github_client is None:
        raise RuntimeError("GitHub client not initialized. Call set_github_client() first.")
    return _github_client


@tool
def fetch_pr_diff(repo_full_name: str, pr_number: int) -> str:
    """Fetch the raw diff of a pull request.

    Args:
        repo_full_name: Repository in 'owner/repo' format
        pr_number: Pull request number
    """
    client = _get_client()
    diff = client.get_pr_diff(repo_full_name, pr_number)
    logger.info("Fetched diff for %s PR #%d (%d chars)", repo_full_name, pr_number, len(diff))
    return diff


@tool
def fetch_pr_files(repo_full_name: str, pr_number: int) -> str:
    """Fetch the list of changed files in a pull request with patch details.

    Args:
        repo_full_name: Repository in 'owner/repo' format
        pr_number: Pull request number
    """
    client = _get_client()
    files = client.get_pr_files(repo_full_name, pr_number)
    logger.info("Fetched %d changed files for %s PR #%d", len(files), repo_full_name, pr_number)
    return json.dumps(files, indent=2)


@tool
def fetch_file_content(repo_full_name: str, file_path: str, ref: str = "main") -> str:
    """Fetch the full content of a file from the repository at a specific commit/branch.

    Use this to understand the broader codebase context around changed files.

    Args:
        repo_full_name: Repository in 'owner/repo' format
        file_path: Path to the file within the repository
        ref: Git ref (branch name, tag, or commit SHA)
    """
    client = _get_client()
    content = client.get_file_content(repo_full_name, file_path, ref)
    if not content:
        return f"[File not found or empty: {file_path} at {ref}]"
    return content


@tool
def post_pr_review(
    repo_full_name: str,
    pr_number: int,
    summary: str,
    verdict: str,
    comments_json: str = "[]",
) -> str:
    """Submit a code review on a pull request.

    Args:
        repo_full_name: Repository in 'owner/repo' format
        pr_number: Pull request number
        summary: Overall review summary in markdown
        verdict: One of 'APPROVE', 'REQUEST_CHANGES', 'COMMENT'
        comments_json: JSON array of inline comments, each with 'path', 'line', 'body'
    """
    client = _get_client()
    comments = json.loads(comments_json) if comments_json else []

    client.post_review(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        body=summary,
        event=verdict,
        comments=comments,
    )

    return f"Review posted: {verdict} on {repo_full_name} PR #{pr_number} with {len(comments)} inline comments"


# All tools available to the Code Review agent
CODE_REVIEW_TOOLS = [
    fetch_pr_diff,
    fetch_pr_files,
    fetch_file_content,
    post_pr_review,
]
