"""Shared test fixtures for the Digital CTO test suite."""

from __future__ import annotations

import json
from typing import Any

import pytest


@pytest.fixture
def sample_pr_payload() -> dict[str, Any]:
    """A realistic GitHub pull_request webhook payload."""
    return {
        "action": "opened",
        "number": 42,
        "repository": {
            "full_name": "afcen/platform",
            "name": "platform",
            "owner": {"login": "afcen"},
        },
        "pull_request": {
            "number": 42,
            "title": "feat: add user authentication middleware",
            "body": "Adds JWT-based auth middleware for API routes.\n\nCloses #38",
            "html_url": "https://github.com/afcen/platform/pull/42",
            "diff_url": "https://github.com/afcen/platform/pull/42.diff",
            "state": "open",
            "user": {
                "login": "bayes-dev-1",
                "avatar_url": "https://avatars.githubusercontent.com/u/12345",
            },
            "head": {
                "ref": "feat/auth-middleware",
                "sha": "abc123def456",
            },
            "base": {
                "ref": "main",
                "sha": "789xyz000111",
            },
            "created_at": "2026-02-17T10:00:00Z",
            "updated_at": "2026-02-17T10:00:00Z",
        },
    }


@pytest.fixture
def sample_pr_payload_bytes(sample_pr_payload: dict) -> bytes:
    """Raw bytes version of the PR payload (for webhook signature testing)."""
    return json.dumps(sample_pr_payload).encode("utf-8")


@pytest.fixture
def sample_closed_pr_payload(sample_pr_payload: dict) -> dict:
    """A PR event with action=closed (should be ignored)."""
    payload = sample_pr_payload.copy()
    payload["action"] = "closed"
    return payload


@pytest.fixture
def sample_diff() -> str:
    """A sample PR diff for testing code review."""
    return """\
diff --git a/src/middleware/auth.py b/src/middleware/auth.py
new file mode 100644
--- /dev/null
+++ b/src/middleware/auth.py
@@ -0,0 +1,35 @@
+import jwt
+import os
+
+SECRET_KEY = "hardcoded-secret-key-123"  # TODO: move to env
+
+def verify_token(token: str) -> dict:
+    try:
+        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
+        return payload
+    except:
+        return None
+
+def auth_middleware(request):
+    token = request.headers.get("Authorization")
+    if not token:
+        return {"error": "No token provided"}, 401
+    
+    user = verify_token(token)
+    if user is None:
+        return {"error": "Invalid token"}, 401
+    
+    request.user = user
+    return None
"""


@pytest.fixture
def expected_review_issues() -> list[str]:
    """Issues that a good code review should catch in sample_diff."""
    return [
        "hardcoded secret key",
        "bare except clause",
        "missing MFA / authentication factors",
    ]


# ── Architecture Advisor Fixtures ──


@pytest.fixture
def sample_architecture_query() -> dict[str, Any]:
    """A sample architecture evaluation query."""
    return {
        "query": "Should we use Redis or Memcached for API response caching?",
        "query_type": "technology_evaluation",
        "repository": "afcen/platform",
        "context": {
            "expected_load": "10k requests/minute",
            "budget": "$200/month for caching infrastructure",
        },
    }


# ── JARVIS Directive Fixtures ──


@pytest.fixture
def sample_jarvis_sprint_directive() -> dict[str, Any]:
    """A JARVIS directive requesting a sprint report."""
    return {
        "directive_id": "dir-test-001",
        "type": "sprint_report",
        "payload": {"repository": "afcen/platform"},
        "priority": "normal",
        "sender": "jarvis",
    }


@pytest.fixture
def sample_jarvis_architecture_directive() -> dict[str, Any]:
    """A JARVIS directive for an architecture query."""
    return {
        "directive_id": "dir-test-002",
        "type": "architecture_query",
        "payload": {
            "query": "Best database for time-series climate data?",
            "query_type": "technology_evaluation",
        },
        "priority": "high",
        "sender": "jarvis",
    }


@pytest.fixture
def sample_jarvis_devops_directive() -> dict[str, Any]:
    """A JARVIS directive for DevOps status."""
    return {
        "directive_id": "dir-test-003",
        "type": "devops_status",
        "payload": {"repositories": ["afcen/platform"]},
        "priority": "normal",
        "sender": "jarvis",
    }


# ── Workflow Run Fixtures ──


@pytest.fixture
def sample_workflow_runs() -> list[dict[str, Any]]:
    """Sample GitHub Actions workflow runs."""
    return [
        {
            "id": 100,
            "name": "CI",
            "status": "completed",
            "conclusion": "success",
            "workflow_id": 1,
            "branch": "main",
            "commit_sha": "abc123",
            "event": "push",
            "created_at": "2026-02-20T10:00:00Z",
            "updated_at": "2026-02-20T10:05:00Z",
            "html_url": "https://github.com/afcen/platform/actions/runs/100",
            "run_attempt": 1,
        },
        {
            "id": 101,
            "name": "CI",
            "status": "completed",
            "conclusion": "failure",
            "workflow_id": 1,
            "branch": "feat/broken",
            "commit_sha": "def456",
            "event": "push",
            "created_at": "2026-02-20T11:00:00Z",
            "updated_at": "2026-02-20T11:05:00Z",
            "html_url": "https://github.com/afcen/platform/actions/runs/101",
            "run_attempt": 1,
        },
    ]
