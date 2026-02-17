"""Tests for the GitHub webhook endpoint."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient


def _sign_payload(payload_bytes: bytes, secret: str = "test-secret") -> str:
    """Generate HMAC-SHA256 signature matching GitHub's format."""
    sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


class TestWebhookSignatureVerification:
    """Test that webhook signature verification works correctly."""

    def test_valid_signature_is_accepted(self, sample_pr_payload_bytes):
        """A correctly signed payload should pass verification."""
        from src.integrations.github_client import GitHubClient

        client = GitHubClient(token="fake", webhook_secret="test-secret")
        sig = _sign_payload(sample_pr_payload_bytes, "test-secret")

        assert client.verify_webhook_signature(sample_pr_payload_bytes, sig) is True

    def test_invalid_signature_is_rejected(self, sample_pr_payload_bytes):
        """A payload signed with the wrong secret should be rejected."""
        from src.integrations.github_client import GitHubClient

        client = GitHubClient(token="fake", webhook_secret="test-secret")
        bad_sig = _sign_payload(sample_pr_payload_bytes, "wrong-secret")

        assert client.verify_webhook_signature(sample_pr_payload_bytes, bad_sig) is False

    def test_missing_signature_is_rejected(self, sample_pr_payload_bytes):
        """A payload with no signature header should be rejected."""
        from src.integrations.github_client import GitHubClient

        client = GitHubClient(token="fake", webhook_secret="test-secret")

        assert client.verify_webhook_signature(sample_pr_payload_bytes, "") is False

    def test_no_secret_configured_passes(self, sample_pr_payload_bytes):
        """If no webhook secret is set, verification is skipped (dev mode)."""
        from src.integrations.github_client import GitHubClient

        client = GitHubClient(token="fake", webhook_secret="")

        assert client.verify_webhook_signature(sample_pr_payload_bytes, "anything") is True


class TestPREventParsing:
    """Test that GitHub PR webhook payloads are parsed correctly."""

    def test_parse_opened_pr(self, sample_pr_payload):
        """A valid PR opened event should parse into our model."""
        from src.integrations.github_client import GitHubClient

        event = GitHubClient.parse_pr_event(sample_pr_payload)

        assert event.action == "opened"
        assert event.repository_full_name == "afcen/platform"
        assert event.pull_request.number == 42
        assert event.pull_request.title == "feat: add user authentication middleware"
        assert event.pull_request.user.login == "bayes-dev-1"
        assert event.pull_request.head.ref == "feat/auth-middleware"
        assert event.pull_request.base.ref == "main"
        assert event.is_reviewable is True

    def test_closed_pr_not_reviewable(self, sample_closed_pr_payload):
        """A closed PR should not be flagged as reviewable."""
        from src.integrations.github_client import GitHubClient

        event = GitHubClient.parse_pr_event(sample_closed_pr_payload)

        assert event.action == "closed"
        assert event.is_reviewable is False
