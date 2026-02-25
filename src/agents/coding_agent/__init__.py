"""Coding Agent — Autonomous code generation via Claude Code.

Phase 4: This agent can execute coding tasks in isolated Docker containers
using Claude Code, with mandatory quality gate via Code Review Agent.

Flow:
  1. Receive coding task
  2. Assess complexity and routing
  3. Execute in Docker sandbox via Claude Code
  4. Run quality gate (Code Review Agent)
  5. If approved: commit/PR
  6. If rejected: retry with feedback
"""

from src.agents.coding_agent.agent import (
    coding_graph,
    execute_coding_task,
    get_task_status,
    _default_state,
)

from src.agents.coding_agent.models import (
    CodingTask,
    CodingResult,
    CodingComplexity,
    CodingAgentType,
    TaskStatus,
)

__all__ = [
    "coding_graph",
    "execute_coding_task",
    "get_task_status",
    "_default_state",
    "CodingTask",
    "CodingResult",
    "CodingComplexity",
    "CodingAgentType",
    "TaskStatus",
]
