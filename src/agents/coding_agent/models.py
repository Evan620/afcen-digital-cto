"""Data models for the Coding Agent.

Defines the input task specifications, output results, and internal state
for coding operations.
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Enums ──


class CodingComplexity(str, Enum):
    """Complexity levels for routing coding tasks."""

    TRIVIAL = "trivial"  # Simple one-liner, config change
    SIMPLE = "simple"  # Small function, obvious implementation
    MODERATE = "moderate"  # Multiple files, some design decisions
    COMPLEX = "complex"  # Significant feature, architectural impact
    VERY_COMPLEX = "very_complex"  # Multi-component, requires human oversight


class CodingAgentType(str, Enum):
    """Available coding agent implementations."""

    CLAUDE_CODE = "claude_code"  # Claude Code CLI (Tier 2 - preferred)
    AIDER = "aider"  # Aider (Tier 3 - not implemented in Phase 4)
    CUSTOM = "custom"  # Custom implementation


class TaskStatus(str, Enum):
    """Status of a coding task execution."""

    PENDING = "pending"
    ASSESSING = "assessing"
    EXECUTING = "executing"
    QUALITY_GATE = "quality_gate"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    COMPLETED = "completed"


class AutonomyLevel(str, Enum):
    """Level of human supervision required."""

    SUPERVISED = "supervised"  # Every step requires approval
    SEMI_AUTONOMOUS = "semi_autonomous"  # Quality gate only
    FULLY_AUTONOMOUS = "fully_autonomous"  # No human intervention


class RepoAccessMode(str, Enum):
    """Repository access strategy for coding tasks."""

    CLONE_ON_DEMAND = "clone_on_demand"  # Clone fresh for each task
    PERSISTENT_WORKSPACE = "persistent_workspace"  # Use pre-cloned workspace
    GITHUB_CLI = "github_cli"  # Use gh CLI API operations (no local clone)


# ── Input Models ──


class CodingTask(BaseModel):
    """Input specification for a coding task."""

    task_id: str = Field(description="Unique identifier for this task")
    description: str = Field(description="Natural language description of what to implement")
    repository: str = Field(description="GitHub repository (owner/repo)")
    base_branch: str = Field(default="main", description="Base branch to work on")

    # Routing criteria
    complexity: CodingComplexity = Field(
        default=CodingComplexity.MODERATE,
        description="Estimated complexity for agent selection",
    )
    estimated_files: int = Field(default=1, description="Estimated number of files to modify")
    requires_testing: bool = Field(default=True, description="Whether tests are required")
    cost_sensitivity: str = Field(
        default="medium",
        description="Cost sensitivity: low, medium, high",
    )
    autonomy_level: AutonomyLevel = Field(
        default=AutonomyLevel.SEMI_AUTONOMOUS,
        description="Level of human supervision",
    )

    # Context
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    related_issue: int | None = Field(default=None, description="Related GitHub issue number")
    related_pr: int | None = Field(default=None, description="Related PR number")
    branch_name: str | None = Field(default=None, description="Branch to create/use")

    # Scope restrictions (security)
    allowed_paths: list[str] = Field(
        default_factory=list,
        description="Whitelist of paths allowed to modify (empty = all)",
    )
    forbidden_patterns: list[str] = Field(
        default_factory=lambda: [
            "*.env",
            "*.key",
            "*.pem",
            "secrets/*",
            ".aws/*",
            ".ssh/*",
        ],
        description="Patterns that must never be modified",
    )

    # Execution parameters
    timeout_seconds: int = Field(default=300, description="Maximum execution time")
    max_retries: int = Field(default=2, description="Maximum retry attempts on quality gate failure")

    # Repository access (Phase 4)
    repo_access_mode: RepoAccessMode | None = Field(
        default=None,
        description="Override repository access strategy (auto-selected if None)",
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)

    def should_use_claude_code(self) -> bool:
        """Determine if Claude Code is appropriate for this task."""
        return (
            self.complexity in (CodingComplexity.TRIVIAL, CodingComplexity.SIMPLE, CodingComplexity.MODERATE)
            and self.cost_sensitivity in ("low", "medium")
        )

    def is_safe_to_execute(self) -> tuple[bool, str]:
        """Check if task is safe to execute autonomously."""
        # Check if description contains risky patterns
        risky_keywords = [
            "delete all",
            "drop table",
            "remove all data",
            "format disk",
            "wipe",
            "destroy",
            "credentials",
            "passwords",
            "api keys",
        ]
        desc_lower = self.description.lower()
        for keyword in risky_keywords:
            if keyword in desc_lower:
                return False, f"Task contains risky keyword: {keyword}"

        # Check autonomy level
        if self.autonomy_level == AutonomyLevel.SUPERVISED:
            return False, "Task requires supervised execution"

        return True, "Safe"


# ── Output Models ──


class FileChange(BaseModel):
    """A single file modification made by the coding agent."""

    path: str = Field(description="File path in repository")
    status: str = Field(description="modified, added, deleted")
    additions: int = Field(default=0)
    deletions: int = Field(default=0)
    patch: str = Field(default="", description="Git diff patch")


class TestResult(BaseModel):
    """Test execution results."""

    framework: str = Field(description="pytest, unittest, jest, etc.")
    passed: int = Field(default=0)
    failed: int = Field(default=0)
    skipped: int = Field(default=0)
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = Field(default=0.0)


class CodingResult(BaseModel):
    """Result from a coding agent execution."""

    task_id: str
    agent_used: CodingAgentType
    status: TaskStatus

    # Output
    files_modified: list[FileChange] = Field(default_factory=list)
    commit_hash: str | None = Field(default=None)
    pr_number: int | None = Field(default=None)

    # Testing
    test_results: TestResult | None = Field(default=None)

    # Quality gate
    quality_gate_passed: bool = Field(default=False)
    quality_gate_feedback: str | None = Field(default=None)

    # Error handling
    errors: list[str] = Field(default_factory=list)
    retry_count: int = Field(default=0)

    # Execution metadata
    execution_time_seconds: float = Field(default=0.0)
    llm_tokens_used: int = Field(default=0)
    docker_container_id: str | None = Field(default=None)

    # Timestamps
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "task_id": self.task_id,
            "agent_used": self.agent_used.value,
            "status": self.status.value,
            "files_modified": [f.model_dump() for f in self.files_modified],
            "commit_hash": self.commit_hash,
            "pr_number": self.pr_number,
            "test_results": self.test_results.model_dump() if self.test_results else None,
            "quality_gate_passed": self.quality_gate_passed,
            "quality_gate_feedback": self.quality_gate_feedback,
            "errors": self.errors,
            "retry_count": self.retry_count,
            "execution_time_seconds": self.execution_time_seconds,
            "llm_tokens_used": self.llm_tokens_used,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# ── Internal State ──


class CodingAgentState(BaseModel):
    """Internal state for the Coding Agent LangGraph."""

    # Input
    task: CodingTask | None = None

    # State tracking
    status: TaskStatus = TaskStatus.PENDING
    current_retry: int = 0

    # Assessment
    agent_selection: CodingAgentType | None = None
    execution_plan: str | None = None

    # Execution results
    result: CodingResult | None = None

    # Quality gate
    quality_gate_result: dict | None = None
    needs_retry: bool = False
    retry_feedback: str | None = None

    # Error handling
    error: str | None = None

    # Timestamps
    started_at: datetime | None = None
    completed_at: datetime | None = None
