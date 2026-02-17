"""Tests for memory stores (Redis, PostgreSQL, Qdrant).

These tests validate the store interfaces using mocks. Integration tests
(with real services via Docker) are run separately.
"""

from __future__ import annotations

import pytest

from src.models.schemas import PRWebhookEvent, PullRequestData, PRUser, PRHead, PRBase


class TestPRWebhookModel:
    """Test the PR webhook event model and its helper properties."""

    def _make_event(self, action: str = "opened") -> PRWebhookEvent:
        return PRWebhookEvent(
            action=action,
            repository_full_name="afcen/platform",
            pull_request=PullRequestData(
                number=1,
                title="Test PR",
                html_url="https://github.com/afcen/platform/pull/1",
                diff_url="https://github.com/afcen/platform/pull/1.diff",
                user=PRUser(login="dev-1"),
                head=PRHead(ref="feat/test", sha="abc123"),
                base=PRBase(ref="main", sha="def456"),
            ),
        )

    def test_opened_is_reviewable(self):
        event = self._make_event("opened")
        assert event.is_reviewable is True

    def test_synchronize_is_reviewable(self):
        event = self._make_event("synchronize")
        assert event.is_reviewable is True

    def test_reopened_is_reviewable(self):
        event = self._make_event("reopened")
        assert event.is_reviewable is True

    def test_closed_is_not_reviewable(self):
        event = self._make_event("closed")
        assert event.is_reviewable is False

    def test_labeled_is_not_reviewable(self):
        event = self._make_event("labeled")
        assert event.is_reviewable is False


class TestConfigParsing:
    """Test configuration helpers."""

    def test_monitored_repos_parsing(self):
        """Comma-separated repo list should parse correctly."""
        from src.config import Settings

        s = Settings(github_repos="afcen/platform, afcen/agents , afcen/dashboard")
        assert s.monitored_repos == ["afcen/platform", "afcen/agents", "afcen/dashboard"]

    def test_empty_repos(self):
        from src.config import Settings

        s = Settings(github_repos="")
        assert s.monitored_repos == []

    def test_llm_availability_flags(self):
        from src.config import Settings

        s = Settings(anthropic_api_key="sk-test", azure_openai_api_key="", azure_openai_endpoint="")
        assert s.has_anthropic is True
        assert s.has_azure_openai is False
