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
