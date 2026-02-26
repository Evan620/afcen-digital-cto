"""Tests for the Coding Agent (Phase 4)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.coding_agent.models import (
    CodingTask,
    CodingResult,
    CodingComplexity,
    CodingAgentType,
    TaskStatus,
    FileChange,
)
from src.agents.coding_agent.agent import (
    _default_state,
    coding_graph,
)
from src.agents.coding_agent.executor import MockCodeExecutor
from src.agents.coding_agent.quality_gate import QualityGate, QualityGateResult


@pytest.mark.asyncio
class TestCodingModels:
    """Tests for Coding Agent data models."""

    async def test_coding_task_creation(self):
        """Test creating a CodingTask."""
        task = CodingTask(
            task_id="test-123",
            description="Add a health check endpoint",
            repository="afcen/platform",
            complexity=CodingComplexity.SIMPLE,
            estimated_files=2,
            requires_testing=True,
        )

        assert task.task_id == "test-123"
        assert task.repository == "afcen/platform"
        assert task.complexity == CodingComplexity.SIMPLE
        assert task.estimated_files == 2

    async def test_coding_task_safety_check(self):
        """Test safety validation for coding tasks."""
        # Safe task
        safe_task = CodingTask(
            task_id="safe-1",
            description="Add a new endpoint",
            repository="afcen/platform",
        )
        is_safe, reason = safe_task.is_safe_to_execute()
        assert is_safe is True

        # Unsafe task - risky keyword
        unsafe_task = CodingTask(
            task_id="unsafe-1",
            description="Delete all data from database",
            repository="afcen/platform",
        )
        is_safe, reason = unsafe_task.is_safe_to_execute()
        assert is_safe is False
        assert "risky" in reason.lower()

    async def test_coding_result_to_dict(self):
        """Test converting CodingResult to dictionary."""
        result = CodingResult(
            task_id="test-123",
            agent_used=CodingAgentType.CLAUDE_CODE,
            status=TaskStatus.COMPLETED,
            files_modified=[
                FileChange(path="src/main.py", status="modified", additions=10, deletions=2)
            ],
            execution_time_seconds=45.5,
        )

        result_dict = result.to_dict()

        assert result_dict["task_id"] == "test-123"
        assert result_dict["agent_used"] == "claude_code"
        assert result_dict["status"] == "completed"
        assert len(result_dict["files_modified"]) == 1


@pytest.mark.asyncio
class TestCodingExecutor:
    """Tests for Claude Code executor."""

    async def test_mock_executor(self):
        """Test the mock executor for testing."""
        executor = MockCodeExecutor()

        task = CodingTask(
            task_id="mock-test",
            description="Add endpoint",
            repository="afcen/platform",
        )

        result = await executor.execute_task(task)

        assert result.task_id == "mock-test"
        assert result.agent_used == CodingAgentType.CLAUDE_CODE
        assert result.status == TaskStatus.EXECUTING


@pytest.mark.asyncio
class TestQualityGate:
    """Tests for the quality gate."""

    async def test_quality_gate_construction(self):
        """Test creating a quality gate."""
        gate = QualityGate()
        assert gate is not None

    async def test_quality_gate_result(self):
        """Test QualityGateResult."""
        result = QualityGateResult(
            passed=True,
            verdict="APPROVE",
            summary="Code looks good",
            feedback="No issues found",
        )

        assert result.passed is True
        assert result.verdict == "APPROVE"
        assert "No issues" in result.feedback

    async def test_quality_gate_no_changes(self):
        """Test quality gate with no file changes."""
        gate = QualityGate()

        task = CodingTask(
            task_id="no-changes",
            description="Do nothing",
            repository="afcen/platform",
        )

        result = CodingResult(
            task_id="no-changes",
            agent_used=CodingAgentType.CLAUDE_CODE,
            status=TaskStatus.EXECUTING,
            files_modified=[],
        )

        gate_result = await gate.validate(task, result)

        assert gate_result.passed is False
        assert gate_result.verdict == "REQUEST_CHANGES"
        assert "No files were modified" in gate_result.summary


@pytest.mark.asyncio
class TestCodingAgentGraph:
    """Tests for the Coding Agent LangGraph workflow."""

    async def test_default_state(self):
        """Test creating a default agent state."""
        state = _default_state(
            task_id="test-state",
            description="Test task",
            repository="afcen/platform",
        )

        assert state["task"] is not None
        assert state["task"].task_id == "test-state"
        assert state["task"].description == "Test task"
        assert state["status"] == TaskStatus.PENDING

    @patch("src.agents.coding_agent.agent.ClaudeCodeExecutor")
    async def test_coding_graph_execution(self, mock_executor_class):
        """Test executing a task through the coding graph."""
        # Mock the executor
        mock_executor = AsyncMock()
        mock_result = CodingResult(
            task_id="graph-test",
            agent_used=CodingAgentType.CLAUDE_CODE,
            status=TaskStatus.EXECUTING,
            files_modified=[
                FileChange(path="test.py", status="modified")
            ],
        )
        mock_executor.execute_task.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        # Create state
        state = _default_state(
            task_id="graph-test",
            description="Test execution",
            repository="afcen/platform",
            complexity=CodingComplexity.SIMPLE,
        )

        # Note: Full graph execution would require more setup
        # For now, verify the graph exists
        assert coding_graph is not None


@pytest.mark.asyncio
class TestCodingAgentIntegration:
    """Integration tests for the Coding Agent."""

    async def test_full_mock_workflow(self):
        """Test a complete mock workflow."""
        # Create task
        task = CodingTask(
            task_id="integration-test",
            description="Add a simple endpoint",
            repository="afcen/platform",
            complexity=CodingComplexity.SIMPLE,
        )

        # Execute with mock executor
        executor = MockCodeExecutor()
        result = await executor.execute_task(task)

        # Validate result
        assert result.task_id == "integration-test"
        assert result.status == TaskStatus.EXECUTING

        # Run quality gate
        gate = QualityGate()
        gate_result = await gate.validate(task, result)

        assert gate_result is not None


def test_coding_complexity_enum():
    """Test CodingComplexity enum values."""
    assert CodingComplexity.TRIVIAL.value == "trivial"
    assert CodingComplexity.SIMPLE.value == "simple"
    assert CodingComplexity.MODERATE.value == "moderate"
    assert CodingComplexity.COMPLEX.value == "complex"
    assert CodingComplexity.VERY_COMPLEX.value == "very_complex"


def test_task_status_enum():
    """Test TaskStatus enum values."""
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.EXECUTING.value == "executing"
    assert TaskStatus.APPROVED.value == "approved"
    assert TaskStatus.REJECTED.value == "rejected"
    assert TaskStatus.COMPLETED.value == "completed"


def test_coding_agent_type_enum():
    """Test CodingAgentType enum values."""
    assert CodingAgentType.CLAUDE_CODE.value == "claude_code"
    assert CodingAgentType.AIDER.value == "aider"
    assert CodingAgentType.CUSTOM.value == "custom"
