"""Coding Agent — LangGraph workflow for autonomous code generation.

This agent orchestrates the coding task execution flow:
1. Receive and assess task
2. Select appropriate coding agent (Claude Code)
3. Execute in Docker sandbox
4. Run quality gate (Code Review Agent)
5. Retry if needed or approve
6. Create PR/commit

Phase 4: Uses Claude Code CLI (Tier 2) in Docker containers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from src.agents.coding_agent.executor import (
    AiderExecutor,
    ClaudeCodeExecutor,
    MockCodeExecutor,
)
from src.agents.coding_agent.models import (
    CodingAgentState,
    CodingAgentType,
    CodingComplexity,
    CodingResult,
    CodingTask,
    TaskStatus,
)
from src.agents.coding_agent.prompts import TASK_ASSESSMENT_PROMPT
from src.agents.coding_agent.quality_gate import QualityGate
from src.config import settings
from src.memory.postgres_store import PostgresStore

logger = logging.getLogger(__name__)


# ── Task Storage (in-memory for now) ──

_task_store: dict[str, CodingResult] = {}


# ── Helper Functions ──


def _default_state(
    task_id: str | None = None,
    description: str = "",
    repository: str = "",
    base_branch: str = "main",
    complexity: CodingComplexity = CodingComplexity.MODERATE,
    estimated_files: int = 1,
    requires_testing: bool = True,
    cost_sensitivity: str = "medium",
    autonomy_level: str = "semi_autonomous",
    context: dict | None = None,
    related_issue: int | None = None,
    related_pr: int | None = None,
) -> CodingAgentState:
    """Create a default state for the coding agent graph."""
    task = CodingTask(
        task_id=task_id or str(uuid.uuid4()),
        description=description,
        repository=repository,
        base_branch=base_branch,
        complexity=complexity,
        estimated_files=estimated_files,
        requires_testing=requires_testing,
        cost_sensitivity=cost_sensitivity,
        autonomy_level=autonomy_level,
        context=context or {},
        related_issue=related_issue,
        related_pr=related_pr,
    )

    return {
        "task": task,
        "status": TaskStatus.PENDING,
        "started_at": datetime.utcnow(),
        "needs_retry": False,
        "error": None,
        "result": None,
    }


async def execute_coding_task(task: CodingTask) -> CodingResult:
    """Execute a coding task through the coding agent graph.

    This is the main entry point for programmatic access.

    Args:
        task: The coding task to execute

    Returns:
        CodingResult with execution outcome
    """
    state = _default_state(
        task_id=task.task_id,
        description=task.description,
        repository=task.repository,
        base_branch=task.base_branch,
        complexity=task.complexity,
        estimated_files=task.estimated_files,
        requires_testing=task.requires_testing,
        cost_sensitivity=task.cost_sensitivity,
        autonomy_level=task.autonomy_level.value,
        context=task.context,
        related_issue=task.related_issue,
        related_pr=task.related_pr,
    )

    result_state = await coding_graph.ainvoke(state)
    result = result_state.get("result") if isinstance(result_state, dict) else None

    if result:
        _task_store[task.task_id] = result

    return result


async def get_task_status(task_id: str) -> CodingResult | None:
    """Get the status of a coding task.

    Args:
        task_id: The task identifier

    Returns:
        CodingResult if found, None otherwise
    """
    return _task_store.get(task_id)


# ── Node Functions ──


async def receive_task(state: CodingAgentState) -> dict:
    """Receive and validate the incoming task."""
    task = state.get("task")

    if not task:
        return {"error": "No task provided", "status": TaskStatus.FAILED}

    # Validate safety
    is_safe, reason = task.is_safe_to_execute()
    if not is_safe:
        logger.warning("Task %s blocked: %s", task.task_id, reason)
        return {
            "error": reason,
            "status": TaskStatus.FAILED,
        }

    logger.info(
        "Received coding task %s: %s (complexity=%s, autonomy=%s)",
        task.task_id,
        task.description[:50],
        task.complexity.value,
        task.autonomy_level.value,
    )

    return {"status": TaskStatus.ASSESSING}


async def assess_complexity(state: CodingAgentState) -> dict:
    """Assess task complexity and create execution plan."""
    task = state.get("task")
    if not task:
        return {"error": "No task to assess"}

    # For simple tasks, use pre-computed assessment
    if task.complexity in (CodingComplexity.TRIVIAL, CodingComplexity.SIMPLE):
        agent_selection = CodingAgentType.CLAUDE_CODE
        execution_plan = f"Execute simple task: {task.description}"
    else:
        # Use LLM to assess complex tasks
        agent_selection, execution_plan = await _llm_assess(task)

    logger.info(
        "Task %s assessed: complexity=%s, agent=%s",
        task.task_id,
        task.complexity.value,
        agent_selection.value,
    )

    return {
        "agent_selection": agent_selection,
        "execution_plan": execution_plan,
        "status": TaskStatus.EXECUTING,
    }


async def _llm_assess(task: CodingTask) -> tuple[CodingAgentType, str]:
    """Use LLM to assess task complexity and plan execution."""
    prompt = TASK_ASSESSMENT_PROMPT.format(
        description=task.description,
        repository=task.repository,
        base_branch=task.base_branch,
        context=json.dumps(task.context),
    )

    # Choose LLM
    if settings.has_anthropic:
        llm = ChatAnthropic(
            model="claude-haiku-4-20250514",  # Use faster model for assessment
            api_key=settings.anthropic_api_key,
            temperature=0,
            max_tokens=1024,
        )
    elif settings.has_zai:
        llm = ChatOpenAI(
            model=settings.zai_model,
            api_key=settings.zai_api_key,
            base_url=settings.zai_base_url,
            temperature=0,
            max_tokens=1024,
        )
    else:
        # Default to Claude Code without assessment
        return CodingAgentType.CLAUDE_CODE, "Execute with Claude Code"

    try:
        messages = [
            SystemMessage(content="You are a code assessment assistant."),
            HumanMessage(content=prompt),
        ]

        response = await llm.ainvoke(messages)
        content = response.content

        # Extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            assessment = json.loads(json_match.group())
            return (
                CodingAgentType.CLAUDE_CODE,
                "\n".join(assessment.get("implementation_steps", [])),
            )

    except Exception as e:
        logger.warning("LLM assessment failed: %s", e)

    return CodingAgentType.CLAUDE_CODE, "Execute with Claude Code"


async def execute_in_sandbox(state: CodingAgentState) -> dict:
    """Execute the coding task in the Docker sandbox."""
    task = state.get("task")
    agent_selection = state.get("agent_selection")

    if not task:
        return {"error": "No task to execute"}

    # Select executor based on agent type
    if agent_selection == CodingAgentType.AIDER:
        if settings.coding_enabled:
            executor = AiderExecutor(
                timeout=task.timeout_seconds,
                anthropic_api_key=settings.anthropic_api_key,
            )
        else:
            executor = MockCodeExecutor()
    elif agent_selection == CodingAgentType.CLAUDE_CODE:
        # Use mock executor if Docker not available
        if settings.coding_enabled:
            executor = ClaudeCodeExecutor(
                timeout=task.timeout_seconds,
                anthropic_api_key=settings.anthropic_api_key,
            )
        else:
            executor = MockCodeExecutor()
    else:
        executor = MockCodeExecutor()

    try:
        # Execute the task
        result = await executor.execute_task(task)

        # Carry over retry_count from previous attempt so the counter
        # isn't reset to 0 on each retry (which would loop forever).
        prev_result = state.get("result")
        if prev_result:
            result.retry_count = prev_result.retry_count

        # If the executor already marked the task as FAILED, propagate that
        # instead of blindly advancing to quality gate.
        if result.status == TaskStatus.FAILED:
            logger.error(
                "Task %s execution failed: %s",
                task.task_id,
                "; ".join(result.errors) or "unknown error",
            )
            return {
                "result": result,
                "error": "; ".join(result.errors) or "Executor returned FAILED",
                "status": TaskStatus.FAILED,
            }

        result.status = TaskStatus.QUALITY_GATE

        logger.info(
            "Task %s executed: %d files modified in %.1fs",
            task.task_id,
            len(result.files_modified),
            result.execution_time_seconds,
        )

        return {
            "result": result,
            "status": TaskStatus.QUALITY_GATE,
        }

    except Exception as e:
        logger.error("Task execution failed for %s: %s", task.task_id, e)
        return {
            "error": f"Execution failed: {str(e)}",
            "status": TaskStatus.FAILED,
        }


async def run_quality_gate(state: CodingAgentState) -> dict:
    """Run the quality gate on generated code."""
    task = state.get("task")
    result = state.get("result")

    if not task or not result:
        return {"error": "No task or result to validate"}

    logger.info("Running quality gate for task %s", task.task_id)

    quality_gate = QualityGate()

    try:
        gate_result = await quality_gate.validate(task, result)

        # Update result with quality gate info
        result.quality_gate_passed = gate_result.passed
        result.quality_gate_feedback = gate_result.feedback

        if gate_result.passed:
            result.status = TaskStatus.APPROVED
            logger.info("Quality gate passed for task %s", task.task_id)
            return {
                "result": result,
                "status": TaskStatus.APPROVED,
                "quality_gate_result": gate_result.to_dict(),
            }
        else:
            # Check if we should retry
            if result.retry_count < task.max_retries:
                result.status = TaskStatus.EXECUTING
                result.retry_count += 1
                logger.info(
                    "Quality gate failed, scheduling retry %d/%d for task %s",
                    result.retry_count,
                    task.max_retries,
                    task.task_id,
                )
                return {
                    "result": result,
                    "status": TaskStatus.EXECUTING,
                    "needs_retry": True,
                    "retry_feedback": gate_result.feedback,
                    "quality_gate_result": gate_result.to_dict(),
                }
            else:
                result.status = TaskStatus.REJECTED
                result.errors.append(
                    f"Quality gate failed after {task.max_retries} retries"
                )
                logger.warning(
                    "Quality gate rejected for task %s after %d retries",
                    task.task_id,
                    task.max_retries,
                )
                return {
                    "result": result,
                    "status": TaskStatus.REJECTED,
                    "quality_gate_result": gate_result.to_dict(),
                }

    except Exception as e:
        logger.error("Quality gate error for task %s: %s", task.task_id, e)
        result.status = TaskStatus.FAILED
        result.errors.append(f"Quality gate error: {str(e)}")
        return {
            "error": f"Quality gate error: {str(e)}",
            "result": result,
            "status": TaskStatus.FAILED,
        }


async def finalize_result(state: CodingAgentState) -> dict:
    """Finalize the result and update status."""
    result = state.get("result")
    status = state.get("status")
    task = state.get("task")

    if not result:
        # Early failures (e.g. assess_complexity error) may have no result.
        # Build a minimal FAILED result so we don't crash.
        error = state.get("error", "Unknown error")
        result = CodingResult(
            task_id=task.task_id if task else "unknown",
            agent_used=CodingAgentType.CLAUDE_CODE,
            status=TaskStatus.FAILED,
            errors=[error],
        )

    result.status = status or TaskStatus.COMPLETED
    result.completed_at = datetime.utcnow()

    # Create PR if approved and quality gate passed
    if status == TaskStatus.APPROVED and task:
        gate_result_dict = state.get("quality_gate_result")
        if gate_result_dict:
            from src.agents.coding_agent.quality_gate import QualityGate, QualityGateResult

            # Auto-generate branch name if not set
            if not task.branch_name:
                task.branch_name = f"digital-cto/{task.task_id[:12]}"

            gate_result = QualityGateResult(
                passed=gate_result_dict.get("passed", False),
                verdict=gate_result_dict.get("verdict", "COMMENT"),
                summary=gate_result_dict.get("summary", ""),
                feedback=gate_result_dict.get("feedback"),
                issues=gate_result_dict.get("issues"),
            )

            try:
                quality_gate = QualityGate()
                pr_result = await quality_gate.create_pr_if_approved(
                    task, result, gate_result,
                )
                if pr_result.get("success"):
                    result.pr_number = pr_result.get("pr_number")
                    logger.info(
                        "Created PR #%s for task %s",
                        result.pr_number,
                        result.task_id,
                    )
                else:
                    logger.warning(
                        "PR creation skipped for task %s: %s",
                        result.task_id,
                        pr_result.get("reason"),
                    )
            except Exception as e:
                logger.warning("Failed to create PR for task %s: %s", result.task_id, e)

    # Log to database
    try:
        store = PostgresStore()
        await store.log_decision(
            agent_name="coding_agent",
            decision_type="code_generation",
            reasoning=f"Generated code for task: {result.task_id}",
            outcome=f"Status: {result.status.value}, Files: {len(result.files_modified)}",
            context={
                "task_id": result.task_id,
                "agent_used": result.agent_used.value,
                "files_modified": [f.path for f in result.files_modified],
            },
        )
    except Exception as e:
        logger.warning("Failed to log decision: %s", e)

    logger.info(
        "Task %s finalized: status=%s, files=%d, time=%.1fs, pr=%s",
        result.task_id,
        result.status.value,
        len(result.files_modified),
        result.execution_time_seconds,
        result.pr_number,
    )

    return {"status": TaskStatus.COMPLETED}


async def handle_error(state: CodingAgentState) -> dict:
    """Handle errors during execution."""
    error = state.get("error") or "Unknown error"
    task = state.get("task")

    logger.error("Error in coding agent: %s", error)

    return {
        "status": TaskStatus.FAILED,
        "result": CodingResult(
            task_id=task.task_id if task else "unknown",
            agent_used=CodingAgentType.CLAUDE_CODE,
            status=TaskStatus.FAILED,
            errors=[error],
        ),
    }


# ── Routing Functions ──


def should_retry(state: CodingAgentState) -> str:
    """Determine if we should retry after quality gate failure."""
    if state.get("needs_retry"):
        return "execute_in_sandbox"
    return "finalize_result"


def route_after_assessment(state: CodingAgentState) -> str:
    """Route after task assessment."""
    if state.get("error"):
        return "handle_error"
    return "execute_in_sandbox"


def route_after_execution(state: CodingAgentState) -> str:
    """Route after sandbox execution."""
    if state.get("error"):
        return "handle_error"
    return "run_quality_gate"


def route_after_quality_gate(state: CodingAgentState) -> str:
    """Route after quality gate."""
    status = state.get("status")

    if status == TaskStatus.EXECUTING:
        return "execute_in_sandbox"  # Retry
    elif status in (TaskStatus.APPROVED, TaskStatus.REJECTED, TaskStatus.FAILED):
        return "finalize_result"
    else:
        return "finalize_result"


# ── Build the Graph ──


def build_coding_graph() -> StateGraph:
    """Construct the Coding Agent as a LangGraph StateGraph.

    Flow:
        receive_task → assess_complexity → execute_in_sandbox →
        run_quality_gate → (retry | finalize_result) → END
    """
    graph = StateGraph(CodingAgentState)

    # Add nodes
    graph.add_node("receive_task", receive_task)
    graph.add_node("assess_complexity", assess_complexity)
    graph.add_node("execute_in_sandbox", execute_in_sandbox)
    graph.add_node("run_quality_gate", run_quality_gate)
    graph.add_node("finalize_result", finalize_result)
    graph.add_node("handle_error", handle_error)

    # Set entry point
    graph.set_entry_point("receive_task")

    # Add edges
    graph.add_edge("receive_task", "assess_complexity")
    graph.add_conditional_edges(
        "assess_complexity",
        route_after_assessment,
        {
            "execute_in_sandbox": "execute_in_sandbox",
            "handle_error": "handle_error",
        },
    )
    graph.add_conditional_edges(
        "execute_in_sandbox",
        route_after_execution,
        {
            "run_quality_gate": "run_quality_gate",
            "handle_error": "handle_error",
        },
    )
    graph.add_conditional_edges(
        "run_quality_gate",
        route_after_quality_gate,
        {
            "execute_in_sandbox": "execute_in_sandbox",
            "finalize_result": "finalize_result",
        },
    )
    graph.add_edge("finalize_result", END)
    graph.add_edge("handle_error", END)

    return graph


# Compiled graph ready to invoke
coding_graph = build_coding_graph().compile()
