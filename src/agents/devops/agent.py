"""DevOps & CI/CD Agent — LangGraph subgraph for pipeline monitoring.

Flow:
  1. Fetch pipeline data from GitHub Actions
  2. Analyze failures and categorize alerts
  3. Generate DevOps report with LLM
  4. Persist report
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langgraph.graph import END, StateGraph

from src.agents.devops.models import (
    AlertCategory,
    AlertSeverity,
    DevOpsAlert,
    DevOpsQueryType,
    DevOpsReport,
)
from src.agents.devops.prompts import DEVOPS_ANALYSIS_PROMPT, DEVOPS_REPORT_SYSTEM_PROMPT
from src.config import settings

logger = logging.getLogger(__name__)


# ── Agent State ──


class DevOpsState(TypedDict):
    """State flowing through the DevOps agent graph."""

    # Input
    query_type: str
    repositories: list[str]

    # Intermediate
    workflow_runs: list[dict[str, Any]]
    failed_runs: list[dict[str, Any]]
    failure_details: list[dict[str, Any]]
    llm_output: str

    # Output
    report: dict[str, Any] | None
    error: str | None


# ── Node Functions ──


async def fetch_pipeline_data(state: DevOpsState) -> dict:
    """Fetch recent workflow runs from GitHub Actions."""
    from src.integrations.github_graphql import GitHubGraphQLClient

    graphql = GitHubGraphQLClient()
    repositories = state.get("repositories", [])

    if not repositories:
        from src.config import settings as _settings
        repositories = _settings.monitored_repos or []

    all_runs: list[dict[str, Any]] = []
    failed_runs: list[dict[str, Any]] = []

    for repo in repositories:
        try:
            runs = await graphql.get_workflow_runs(repo, limit=20)
            for run in runs:
                run["repository"] = repo
            all_runs.extend(runs)

            # Collect failed runs
            for run in runs:
                if run.get("conclusion") == "failure":
                    failed_runs.append(run)
        except Exception as e:
            logger.warning("Failed to fetch workflow runs from %s: %s", repo, e)

    logger.info("Fetched %d total runs, %d failed across %d repos", len(all_runs), len(failed_runs), len(repositories))
    return {"workflow_runs": all_runs, "failed_runs": failed_runs, "repositories": repositories}


async def analyze_failures(state: DevOpsState) -> dict:
    """Analyze failed runs and get job-level details."""
    if state.get("error"):
        return {}

    from src.integrations.github_graphql import GitHubGraphQLClient

    graphql = GitHubGraphQLClient()
    failed_runs = state.get("failed_runs", [])
    failure_details: list[dict[str, Any]] = []

    # Get job details for up to 5 most recent failures
    for run in failed_runs[:5]:
        repo = run.get("repository", "")
        run_id = run.get("id")
        if not run_id or not repo:
            continue

        try:
            jobs = await graphql.get_workflow_run_jobs(repo, run_id)
            failed_jobs = [j for j in jobs if j.get("conclusion") == "failure"]

            failure_details.append({
                "run_id": run_id,
                "repository": repo,
                "workflow_name": run.get("name", ""),
                "branch": run.get("branch", ""),
                "commit_sha": run.get("commit_sha", ""),
                "html_url": run.get("html_url", ""),
                "failed_jobs": failed_jobs,
            })
        except Exception as e:
            logger.warning("Failed to get job details for run %s: %s", run_id, e)

    return {"failure_details": failure_details}


async def generate_devops_report(state: DevOpsState) -> dict:
    """Generate a DevOps report using LLM analysis."""
    if state.get("error"):
        return {}

    workflow_runs = state.get("workflow_runs", [])
    failure_details = state.get("failure_details", [])
    repositories = state.get("repositories", [])

    # Calculate basic stats
    total_runs = len(workflow_runs)
    successful = sum(1 for r in workflow_runs if r.get("conclusion") == "success")
    failed = sum(1 for r in workflow_runs if r.get("conclusion") == "failure")

    # Build workflow runs summary
    runs_summary = f"Total: {total_runs}, Success: {successful}, Failed: {failed}\n\n"
    for run in workflow_runs[:10]:
        runs_summary += (
            f"- [{run.get('conclusion', 'unknown')}] {run.get('name', 'unnamed')} "
            f"on {run.get('branch', '?')} ({run.get('repository', '')})\n"
        )

    # Build failure details text
    failure_text = "No failures to analyze." if not failure_details else ""
    for fd in failure_details:
        failure_text += f"\n### {fd['workflow_name']} ({fd['repository']})\n"
        failure_text += f"Branch: {fd['branch']}, Commit: {fd['commit_sha'][:8]}\n"
        for job in fd.get("failed_jobs", []):
            failure_text += f"  - Job: {job['name']} — FAILED\n"
            failed_steps = [s for s in job.get("steps", []) if s.get("conclusion") == "failure"]
            for step in failed_steps:
                failure_text += f"    - Step {step['number']}: {step['name']} — FAILED\n"

    # If no failures and no need for deep analysis, return simple report
    if not failure_details:
        health = "healthy" if failed == 0 else ("degraded" if failed <= 2 else "critical")
        report = DevOpsReport(
            report_id=f"devops-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            summary=f"Pipeline health: {health}. {successful}/{total_runs} runs successful.",
            total_runs=total_runs,
            successful_runs=successful,
            failed_runs=failed,
            alerts=[],
            pipeline_health=health,
            recommendations=["All pipelines running smoothly."] if health == "healthy" else [],
            repositories=repositories,
        )
        return {"report": report.model_dump()}

    # Use LLM for failure analysis
    user_prompt = DEVOPS_ANALYSIS_PROMPT.format(
        repositories=", ".join(repositories),
        workflow_runs_summary=runs_summary,
        failure_details=failure_text,
    )

    # LLM cascade
    if settings.has_anthropic:
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=settings.anthropic_api_key,
            temperature=0,
            max_tokens=4096,
        )
    elif settings.has_zai:
        llm = ChatOpenAI(
            model=settings.zai_model,
            api_key=settings.zai_api_key,
            base_url=settings.zai_base_url,
            temperature=0,
            max_tokens=8192,
        )
    elif settings.has_azure_openai:
        llm = AzureChatOpenAI(
            azure_deployment=settings.azure_openai_deployment,
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            temperature=0,
            max_tokens=4096,
        )
    else:
        # Fall back to rule-based report if no LLM
        alerts = []
        for fd in failure_details:
            alerts.append(
                DevOpsAlert(
                    alert_id=f"alert-{fd['run_id']}",
                    category=AlertCategory.BUILD_FAILURE,
                    severity=AlertSeverity.WARNING,
                    title=f"Failed: {fd['workflow_name']}",
                    description=f"Workflow failed on branch {fd['branch']}",
                    repository=fd["repository"],
                    workflow_name=fd["workflow_name"],
                    workflow_run_id=fd["run_id"],
                    branch=fd["branch"],
                    commit_sha=fd["commit_sha"],
                    html_url=fd.get("html_url", ""),
                )
            )
        health = "degraded" if len(alerts) <= 2 else "critical"
        report = DevOpsReport(
            report_id=f"devops-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            summary=f"{len(alerts)} pipeline failures detected. No LLM available for deep analysis.",
            total_runs=total_runs,
            successful_runs=successful,
            failed_runs=failed,
            alerts=alerts,
            pipeline_health=health,
            recommendations=["Configure an LLM for detailed failure analysis."],
            repositories=repositories,
        )
        return {"report": report.model_dump()}

    try:
        messages = [
            SystemMessage(content=DEVOPS_REPORT_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
        response = await llm.ainvoke(messages)
        content = response.content

        # Parse JSON
        json_match = re.search(r"\{", content)
        if json_match:
            start = json_match.start()
            depth = 0
            in_string = False
            escape = False
            end = start
            for i in range(start, len(content)):
                c = content[i]
                if escape:
                    escape = False
                    continue
                if c == "\\":
                    escape = True
                    continue
                if c == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            parsed = json.loads(content[start:end])
        else:
            parsed = json.loads(content.strip())

        # Build alerts from LLM output
        alerts = []
        for alert_data in parsed.get("alerts", []):
            try:
                alerts.append(
                    DevOpsAlert(
                        alert_id=f"alert-{datetime.utcnow().strftime('%H%M%S')}-{len(alerts)}",
                        category=AlertCategory(alert_data.get("category", "build_failure")),
                        severity=AlertSeverity(alert_data.get("severity", "warning")),
                        title=alert_data.get("title", ""),
                        description=alert_data.get("description", ""),
                    )
                )
            except (ValueError, KeyError) as e:
                logger.warning("Skipping malformed alert: %s", e)

        report = DevOpsReport(
            report_id=f"devops-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            summary=parsed.get("summary", ""),
            total_runs=total_runs,
            successful_runs=successful,
            failed_runs=failed,
            alerts=alerts,
            pipeline_health=parsed.get("pipeline_health", "unknown"),
            recommendations=parsed.get("recommendations", []),
            repositories=repositories,
        )
        return {"report": report.model_dump()}

    except Exception as e:
        logger.error("DevOps LLM analysis failed: %s", e)
        return {"error": f"DevOps analysis failed: {e}"}


async def persist_report(state: DevOpsState) -> dict:
    """Persist the DevOps report to PostgreSQL."""
    if not state.get("report"):
        return {}

    try:
        from src.memory.postgres_store import PostgresStore

        store = PostgresStore()
        await store.log_decision(
            agent_name="devops",
            decision_type="devops_report",
            reasoning=state["report"].get("summary", ""),
            outcome=f"{state['report'].get('pipeline_health', 'unknown')} — "
                    f"{state['report'].get('failed_runs', 0)} failures, "
                    f"{len(state['report'].get('alerts', []))} alerts",
            context={"report_id": state["report"].get("report_id")},
        )
        logger.info("DevOps report persisted: %s", state["report"].get("report_id"))
    except Exception as e:
        logger.error("Failed to persist DevOps report: %s", e)

    return {}


# ── Build the Graph ──


def build_devops_graph() -> StateGraph:
    """Construct the DevOps agent as a LangGraph StateGraph.

    Flow: fetch_pipeline_data → analyze_failures → generate_devops_report → persist_report → END
    """
    graph = StateGraph(DevOpsState)

    graph.add_node("fetch_pipeline_data", fetch_pipeline_data)
    graph.add_node("analyze_failures", analyze_failures)
    graph.add_node("generate_devops_report", generate_devops_report)
    graph.add_node("persist_report", persist_report)

    graph.set_entry_point("fetch_pipeline_data")
    graph.add_edge("fetch_pipeline_data", "analyze_failures")
    graph.add_edge("analyze_failures", "generate_devops_report")
    graph.add_edge("generate_devops_report", "persist_report")
    graph.add_edge("persist_report", END)

    return graph


# Compiled graph ready to invoke
devops_graph = build_devops_graph().compile()


# ── Convenience Functions ──


async def get_pipeline_status(repositories: list[str] | None = None) -> dict[str, Any]:
    """Get current pipeline status across repositories."""
    input_state: DevOpsState = {
        "query_type": DevOpsQueryType.PIPELINE_STATUS.value,
        "repositories": repositories or [],
        "workflow_runs": [],
        "failed_runs": [],
        "failure_details": [],
        "llm_output": "",
        "report": None,
        "error": None,
    }
    result = await devops_graph.ainvoke(input_state)
    return result.get("report") or {"error": result.get("error", "Unknown error")}


async def get_devops_report(repositories: list[str] | None = None) -> dict[str, Any]:
    """Get full DevOps health report with failure analysis."""
    input_state: DevOpsState = {
        "query_type": DevOpsQueryType.DEVOPS_REPORT.value,
        "repositories": repositories or [],
        "workflow_runs": [],
        "failed_runs": [],
        "failure_details": [],
        "llm_output": "",
        "report": None,
        "error": None,
    }
    result = await devops_graph.ainvoke(input_state)
    return result.get("report") or {"error": result.get("error", "Unknown error")}
