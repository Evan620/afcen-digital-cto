"""Tests for the Code Review agent logic."""

from __future__ import annotations

import json

import pytest

from src.models.schemas import (
    CodeReviewResult,
    ReviewComment,
    ReviewSeverity,
    ReviewVerdict,
)


class TestCodeReviewModels:
    """Test that code review data models validate correctly."""

    def test_review_result_creation(self):
        """A CodeReviewResult should serialize and deserialize cleanly."""
        result = CodeReviewResult(
            pr_number=42,
            repository="afcen/platform",
            verdict=ReviewVerdict.REQUEST_CHANGES,
            summary="Found critical security issues.",
            comments=[
                ReviewComment(
                    file_path="src/middleware/auth.py",
                    line=4,
                    body="**[CRITICAL]** Hardcoded secret key — move to env var.",
                    severity=ReviewSeverity.CRITICAL,
                ),
            ],
            security_issues=["Hardcoded JWT secret key"],
            deprecated_deps=[],
        )

        assert result.verdict == ReviewVerdict.REQUEST_CHANGES
        assert len(result.comments) == 1
        assert result.comments[0].severity == ReviewSeverity.CRITICAL

        # Round-trip through JSON
        data = result.model_dump()
        restored = CodeReviewResult(**data)
        assert restored.pr_number == 42
        assert restored.comments[0].body == result.comments[0].body

    def test_review_with_no_issues_approves(self):
        """A clean review should have APPROVE verdict and no comments."""
        result = CodeReviewResult(
            pr_number=10,
            repository="afcen/platform",
            verdict=ReviewVerdict.APPROVE,
            summary="Clean code, no issues found.",
        )

        assert result.verdict == ReviewVerdict.APPROVE
        assert len(result.comments) == 0
        assert len(result.security_issues) == 0


class TestReviewPromptFormatting:
    """Test that review prompts are formatted correctly."""

    def test_pr_analysis_prompt_fills_all_fields(self):
        """The PR analysis prompt template should accept all expected fields."""
        from src.agents.code_review.prompts import PR_ANALYSIS_PROMPT

        formatted = PR_ANALYSIS_PROMPT.format(
            repository="afcen/platform",
            pr_number=42,
            pr_title="feat: add auth",
            pr_author="bayes-dev-1",
            base_branch="main",
            head_branch="feat/auth",
            pr_body="Adds authentication.",
            changed_files_summary="- `auth.py` (added: +35/-0)",
            diff="+ some code",
            additional_context="No additional context.",
        )

        assert "afcen/platform" in formatted
        assert "PR #42" in formatted
        assert "bayes-dev-1" in formatted
        assert "feat: add auth" in formatted
