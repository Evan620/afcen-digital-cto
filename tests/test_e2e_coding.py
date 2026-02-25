"""End-to-end tests for Coding Agent workflow.

These tests verify the complete coding workflow from task submission
through execution and PR creation.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.coding_agent.models import (
    CodingTask,
    CodingResult,
    CodingAgentType,
    TaskStatus,
    CodingComplexity,
    RepoAccessMode,
    FileChange,
)
from src.agents.coding_agent.executor import ClaudeCodeExecutor, MockCodeExecutor
from src.agents.coding_agent.quality_gate import QualityGate, QualityGateResult
from src.integrations.github_client import GitHubClient


@pytest.mark.asyncio
class TestMockCodeExecutor:
    """Test the mock executor for unit testing."""

    async def test_mock_execute_simple_task(self):
        """Test mock execution of a simple task."""
        executor = MockCodeExecutor()

        task = CodingTask(
            task_id="test-001",
            description="Add a new endpoint",
            repository="afcen/platform",
            complexity=CodingComplexity.SIMPLE,
        )

        result = await executor.execute_task(task)

        assert result.task_id == "test-001"
        assert result.agent_used == CodingAgentType.CLAUDE_CODE
        assert result.status == TaskStatus.EXECUTING
        assert len(result.files_modified) > 0
        assert result.files_modified[0].path == "src/api/endpoints.py"

    async def test_mock_execute_no_files(self):
        """Test mock execution with no file modifications."""
        executor = MockCodeExecutor()

        task = CodingTask(
            task_id="test-002",
            description="Run tests",
            repository="afcen/platform",
        )

        result = await executor.execute_task(task)

        assert result.task_id == "test-002"
        assert len(result.files_modified) == 0


@pytest.mark.asyncio
class TestQualityGate:
    """Test quality gate validation."""

    async def test_quality_gate_with_no_files(self):
        """Test quality gate passes when no files modified."""
        github_client = MagicMock(spec=GitHubClient)
        gate = QualityGate(github_client=github_client)

        task = CodingTask(
            task_id="test-003",
            description="No-op task",
            repository="afcen/platform",
        )

        result = CodingResult(
            task_id="test-003",
            agent_used=CodingAgentType.CLAUDE_CODE,
            status=TaskStatus.EXECUTING,
            files_modified=[],
        )

        gate_result = await gate.validate(task, result)

        assert gate_result.passed is True
        assert gate_result.verdict == "COMMENT"
        assert "No files were modified" in gate_result.summary

    @patch("src.agents.coding_agent.quality_gate.code_review_graph")
    async def test_quality_gate_with_review(self, mock_review_graph):
        """Test quality gate with code review."""
        # Mock the review graph response
        mock_review_graph.ainvoke = AsyncMock(return_value={
            "review_result": {
                "verdict": "APPROVE",
                "summary": "Code looks good",
                "comments": [],
                "security_issues": [],
            },
            "posted": False,
            "error": None,
        })

        github_client = MagicMock(spec=GitHubClient)
        gate = QualityGate(github_client=github_client)

        task = CodingTask(
            task_id="test-004",
            description="Add feature",
            repository="afcen/platform",
        )

        result = CodingResult(
            task_id="test-004",
            agent_used=CodingAgentType.CLAUDE_CODE,
            status=TaskStatus.EXECUTING,
            files_modified=[
                FileChange(path="src/main.py", status="modified", additions=10, deletions=2)
            ],
        )

        gate_result = await gate.validate(task, result)

        assert gate_result.passed is True
        assert gate_result.verdict == "APPROVE"
        assert "Code looks good" in gate_result.summary

    @patch("src.agents.coding_agent.quality_gate.code_review_graph")
    async def test_quality_gate_request_changes(self, mock_review_graph):
        """Test quality gate requesting changes."""
        mock_review_graph.ainvoke = AsyncMock(return_value={
            "review_result": {
                "verdict": "REQUEST_CHANGES",
                "summary": "Security issues found",
                "comments": [{"body": "Add input validation"}],
                "security_issues": ["SQL injection risk"],
            },
            "posted": False,
            "error": None,
        })

        github_client = MagicMock(spec=GitHubClient)
        gate = QualityGate(github_client=github_client)

        task = CodingTask(
            task_id="test-005",
            description="Add user input",
            repository="afcen/platform",
        )

        result = CodingResult(
            task_id="test-005",
            agent_used=CodingAgentType.CLAUDE_CODE,
            status=TaskStatus.EXECUTING,
            files_modified=[
                FileChange(path="src/api.py", status="modified")
            ],
        )

        gate_result = await gate.validate(task, result)

        assert gate_result.passed is False
        assert gate_result.verdict == "REQUEST_CHANGES"
        assert "Security issues" in gate_result.feedback


@pytest.mark.asyncio
class TestPRCreation:
    """Test GitHub PR creation workflow."""

    async def test_pr_creation_with_approved_code(self):
        """Test PR creation after quality gate approval."""
        github_client = MagicMock(spec=GitHubClient)
        github_client.create_pull_request = MagicMock(return_value={
            "number": 123,
            "html_url": "https://github.com/afcen/platform/pull/123",
            "state": "open",
            "draft": False,
        })

        gate = QualityGate(github_client=github_client)

        task = CodingTask(
            task_id="test-006",
            description="Add feature",
            repository="afcen/platform",
            branch_name="feature/test-006",
        )

        result = CodingResult(
            task_id="test-006",
            agent_used=CodingAgentType.CLAUDE_CODE,
            status=TaskStatus.APPROVED,
            files_modified=[
                FileChange(path="src/feature.py", status="added")
            ],
        )

        gate_result = QualityGateResult(
            passed=True,
            verdict="APPROVE",
            summary="Code approved",
            feedback="No issues",
        )

        pr_result = await gate.create_pr_if_approved(task, result, gate_result)

        assert pr_result["success"] is True
        assert pr_result["pr_number"] == 123
        assert pr_result["pr_url"] == "https://github.com/afcen/platform/pull/123"

        # Verify GitHub client was called
        github_client.create_pull_request.assert_called_once()

    async def test_pr_creation_fails_without_branch(self):
        """Test PR creation fails when no branch specified."""
        github_client = MagicMock(spec=GitHubClient)
        gate = QualityGate(github_client=github_client)

        task = CodingTask(
            task_id="test-007",
            description="Add feature",
            repository="afcen/platform",
            # No branch_name specified
        )

        result = CodingResult(
            task_id="test-007",
            agent_used=CodingAgentType.CLAUDE_CODE,
            status=TaskStatus.APPROVED,
        )

        gate_result = QualityGateResult(
            passed=True,
            verdict="APPROVE",
            summary="Code approved",
        )

        pr_result = await gate.create_pr_if_approved(task, result, gate_result)

        assert pr_result["success"] is False
        assert "No branch name" in pr_result["reason"]

    async def test_pr_creation_skipped_when_gate_fails(self):
        """Test PR creation is skipped when quality gate fails."""
        github_client = MagicMock(spec=GitHubClient)
        gate = QualityGate(github_client=github_client)

        task = CodingTask(
            task_id="test-008",
            description="Add feature",
            repository="afcen/platform",
            branch_name="feature/test-008",
        )

        result = CodingResult(
            task_id="test-008",
            agent_used=CodingAgentType.CLAUDE_CODE,
            status=TaskStatus.REJECTED,
        )

        gate_result = QualityGateResult(
            passed=False,  # Gate failed
            verdict="REQUEST_CHANGES",
            summary="Issues found",
        )

        pr_result = await gate.create_pr_if_approved(task, result, gate_result)

        assert pr_result["success"] is False
        assert "Quality gate did not pass" in pr_result["reason"]

        # GitHub client should NOT have been called
        github_client.create_pull_request.assert_not_called()


@pytest.mark.asyncio
class TestRepositoryStrategies:
    """Test repository access strategy selection."""

    async def test_select_strategy_for_trivial_task(self):
        """Test strategy selection for trivial tasks."""
        executor = ClaudeCodeExecutor()

        task = CodingTask(
            task_id="trivial-1",
            description="Fix typo",
            repository="afcen/platform",
            complexity=CodingComplexity.TRIVIAL,
            estimated_files=1,
        )

        strategy = executor._select_strategy(task)
        assert strategy == RepoAccessMode.GITHUB_CLI

    async def test_select_strategy_for_complex_task(self):
        """Test strategy selection for complex tasks."""
        executor = ClaudeCodeExecutor()

        task = CodingTask(
            task_id="complex-1",
            description="Major refactoring",
            repository="afcen/platform",
            complexity=CodingComplexity.COMPLEX,
        )

        strategy = executor._select_strategy(task)
        assert strategy == RepoAccessMode.PERSISTENT_WORKSPACE

    async def test_select_strategy_default(self):
        """Test default strategy selection."""
        executor = ClaudeCodeExecutor()

        task = CodingTask(
            task_id="moderate-1",
            description="Add endpoint",
            repository="afcen/platform",
            complexity=CodingComplexity.MODERATE,
        )

        strategy = executor._select_strategy(task)
        assert strategy == RepoAccessMode.CLONE_ON_DEMAND

    async def test_strategy_override(self):
        """Test that explicit override is respected."""
        executor = ClaudeCodeExecutor()

        task = CodingTask(
            task_id="override-1",
            description="Simple task",
            repository="afcen/platform",
            complexity=CodingComplexity.TRIVIAL,
            estimated_files=1,
            repo_access_mode=RepoAccessMode.CLONE_ON_DEMAND,  # Override
        )

        # When override is set, it should be used
        strategy = task.repo_access_mode
        assert strategy == RepoAccessMode.CLONE_ON_DEMAND


@pytest.mark.asyncio
class TestCommandBuilding:
    """Test Claude Code CLI command building."""

    async def test_build_command_fully_autonomous(self):
        """Test command building for fully autonomous tasks."""
        executor = ClaudeCodeExecutor()

        task = CodingTask(
            task_id="auto-1",
            description="Add login endpoint",
            repository="afcen/platform",
        )

        command = executor._build_command(task)

        assert "claude" in command
        assert "--yes" in command
        assert "--dangerously-skip-safety" in command
        assert "--suppress-safety" in command
        assert "-p" in command
        assert "Add login endpoint" in command

    async def test_build_command_supervised(self):
        """Test command building for supervised tasks (restricted tools)."""
        from src.agents.coding_agent.models import AutonomyLevel

        executor = ClaudeCodeExecutor()

        task = CodingTask(
            task_id="supervised-1",
            description="Review code",
            repository="afcen/platform",
            autonomy_level=AutonomyLevel.SUPERVISED,
        )

        command = executor._build_command(task)

        assert "claude" in command
        assert "--allowedTools" in command
        assert "read,view" in command
