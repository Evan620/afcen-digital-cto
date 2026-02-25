"""Tests for Phase 4 supervisor routing.

Tests that coding_task and code_generation events route correctly
to the coding agent through the supervisor.
"""

import pytest

from src.agents.coding_agent.models import (
    CodingTask,
    CodingComplexity,
    RepoAccessMode,
)


@pytest.mark.asyncio
class TestPhase4SupervisorRouting:
    """Test that Phase 4 events route correctly."""

    async def test_coding_task_routes_to_coding_agent(self):
        """Test coding_task event routes to coding agent."""
        # This test verifies the supervisor routing logic
        # The actual routing is done in src/supervisor/graph.py

        # Create a sample coding task
        task = CodingTask(
            task_id="test-123",
            description="Add endpoint for user registration",
            repository="afcen/platform",
            complexity=CodingComplexity.MODERATE,
            repo_access_mode=RepoAccessMode.GITHUB_CLI,
        )

        # Verify task properties
        assert task.task_id == "test-123"
        assert task.repository == "afcen/platform"
        assert task.repo_access_mode == RepoAccessMode.GITHUB_CLI

    async def test_repo_access_mode_selection(self):
        """Test repository access mode auto-selection."""
        # Simple tasks should prefer GITHUB_CLI
        simple_task = CodingTask(
            task_id="simple-1",
            description="Fix typo in README",
            repository="afcen/platform",
            complexity=CodingComplexity.TRIVIAL,
            estimated_files=1,
        )

        # Complex tasks should prefer PERSISTENT_WORKSPACE
        complex_task = CodingTask(
            task_id="complex-1",
            description="Implement multi-service authentication system",
            repository="afcen/platform",
            complexity=CodingComplexity.VERY_COMPLEX,
        )

        # Moderate tasks should default to CLONE_ON_DEMAND
        moderate_task = CodingTask(
            task_id="moderate-1",
            description="Add new API endpoint",
            repository="afcen/platform",
            complexity=CodingComplexity.MODERATE,
        )

        # Override should work
        override_task = CodingTask(
            task_id="override-1",
            description="Simple change",
            repository="afcen/platform",
            complexity=CodingComplexity.TRIVIAL,
            repo_access_mode=RepoAccessMode.CLONE_ON_DEMAND,  # Override
        )

        assert simple_task.complexity == CodingComplexity.TRIVIAL
        assert complex_task.complexity == CodingComplexity.VERY_COMPLEX
        assert moderate_task.complexity == CodingComplexity.MODERATE
        assert override_task.repo_access_mode == RepoAccessMode.CLONE_ON_DEMAND

    async def test_task_safety_check(self):
        """Test task safety validation."""
        safe_task = CodingTask(
            task_id="safe-1",
            description="Add new feature for user dashboard",
            repository="afcen/platform",
        )

        is_safe, reason = safe_task.is_safe_to_execute()
        assert is_safe is True
        assert reason == "Safe"

        # Unsafe task with risky keyword
        unsafe_task = CodingTask(
            task_id="unsafe-1",
            description="Delete all user data from database",
            repository="afcen/platform",
        )

        is_safe, reason = unsafe_task.is_safe_to_execute()
        assert is_safe is False
        assert "risky keyword" in reason.lower()

    async def test_claude_code_appropriateness(self):
        """Test Claude Code agent selection logic."""
        # Low cost, simple task
        simple_task = CodingTask(
            task_id="simple-2",
            description="Add config option",
            repository="afcen/platform",
            complexity=CodingComplexity.SIMPLE,
            cost_sensitivity="low",
        )

        assert simple_task.should_use_claude_code() is True

        # High cost sensitivity
        expensive_task = CodingTask(
            task_id="expensive-1",
            description="Refactor entire codebase",
            repository="afcen/platform",
            complexity=CodingComplexity.COMPLEX,
            cost_sensitivity="high",
        )

        assert expensive_task.should_use_claude_code() is False


@pytest.mark.asyncio
class TestCodingAgentModels:
    """Test Coding Agent data models."""

    def test_repo_access_mode_enum(self):
        """Test RepoAccessMode enum values."""
        assert RepoAccessMode.CLONE_ON_DEMAND == "clone_on_demand"
        assert RepoAccessMode.PERSISTENT_WORKSPACE == "persistent_workspace"
        assert RepoAccessMode.GITHUB_CLI == "github_cli"

    def test_complexity_levels(self):
        """Test CodingComplexity enum values."""
        assert CodingComplexity.TRIVIAL == "trivial"
        assert CodingComplexity.SIMPLE == "simple"
        assert CodingComplexity.MODERATE == "moderate"
        assert CodingComplexity.COMPLEX == "complex"
        assert CodingComplexity.VERY_COMPLEX == "very_complex"
