"""Sprint Planner Agent — LangGraph subgraph for sprint management.

Flow:
  1. Receive sprint query
  2. Fetch GitHub Projects V2 data
  3. Calculate metrics
  4. Track Bayes deliverables
  5. Generate report
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from src.agents.sprint_planner.models import (
    BayesSOWSummary,
    Deliverable,
    DeliverableStatus,
    SprintMetrics,
    SprintPlannerInput,
    SprintQueryType,
    SprintReport,
    VendorType,
)
from src.integrations.github_client import GitHubClient

logger = logging.getLogger(__name__)


# ── Agent State ──


class SprintPlannerState(TypedDict):
    """State flowing through the Sprint Planner graph."""

    # Input
    query_type: str
    repository: str | None
    sprint_id: str | None
    include_bayes: bool
    include_recommendations: bool

    # Intermediate
    issues: list[dict[str, Any]]
    project_items: list[dict[str, Any]]

    # Output
    metrics: dict[str, Any] | None
    report: dict[str, Any] | None
    bayes_summary: dict[str, Any] | None
    recommendations: list[str]

    # Error handling
    error: str | None


# ── Node Functions ──


async def fetch_sprint_data(state: SprintPlannerState) -> dict:
    """Fetch sprint data from GitHub Issues and Projects."""
    github = GitHubClient()

    try:
        issues = []
        repositories = []

        # Get repositories to scan
        if state.get("repository"):
            repositories = [state["repository"]]
        else:
            # Default to configured repos
            from src.config import settings

            repositories = settings.monitored_repos or []

        # Fetch issues from each repository
        for repo in repositories:
            try:
                repo_issues = github.get_repository_issues(repo, state="open")
                issues.extend(repo_issues)
                logger.info("Fetched %d issues from %s", len(repo_issues), repo)
            except Exception as e:
                logger.warning("Failed to fetch issues from %s: %s", repo, e)

        # Also fetch closed issues from last 30 days for velocity calculation
        for repo in repositories:
            try:
                since = datetime.utcnow() - timedelta(days=30)
                closed_issues = github.get_repository_issues(
                    repo, state="closed", since=since.isoformat()
                )
                issues.extend(closed_issues)
            except Exception as e:
                logger.warning("Failed to fetch closed issues: %s", e)

        return {"issues": issues}

    except Exception as e:
        logger.error("Failed to fetch sprint data: %s", e)
        return {"error": f"Failed to fetch sprint data: {e}"}


async def calculate_metrics(state: SprintPlannerState) -> dict:
    """Calculate sprint velocity and health metrics."""
    if state.get("error"):
        return {}

    issues = state.get("issues", [])

    try:
        # Extract story points from labels (looking for "points:X" or "sp:X" labels)
        total_points = 0
        completed_points = 0
        blocked_count = 0
        overdue_count = 0
        total_issues = len(issues)

        now = datetime.utcnow()
        sprint_start = now - timedelta(days=14)  # Assume 2-week sprint
        sprint_end = now

        for issue in issues:
            labels = [l.get("name", "").lower() for l in issue.get("labels", [])]
            state_label = issue.get("state", "open").lower()

            # Extract story points
            points = 0
            for label in labels:
                if label.startswith("points:") or label.startswith("sp:"):
                    try:
                        points = int(label.split(":")[1])
                    except (IndexError, ValueError):
                        points = 1
                    break

            total_points += points

            # Check status
            if state_label == "closed":
                completed_points += points
            elif "blocked" in labels:
                blocked_count += 1
            elif "bayes-blocked" in labels:
                blocked_count += 1

            # Check overdue
            milestone = issue.get("milestone")
            if milestone and milestone.get("due_on"):
                due_date = datetime.fromisoformat(milestone["due_on"].replace("Z", "+00:00"))
                if due_date < now and state_label != "closed":
                    overdue_count += 1

        # Calculate velocity (points per day)
        days_elapsed = (now - sprint_start).days or 1
        velocity = completed_points / days_elapsed if days_elapsed > 0 else 0

        # Determine sprint dates
        sprint_name = "Current Sprint"
        if state.get("sprint_id"):
            sprint_name = state["sprint_id"]

        metrics = SprintMetrics(
            sprint_id=state.get("sprint_id") or "current",
            sprint_name=sprint_name,
            start_date=sprint_start,
            end_date=sprint_end,
            total_story_points=total_points,
            completed_story_points=completed_points,
            remaining_story_points=total_points - completed_points,
            velocity=round(velocity, 2),
            days_remaining=max(0, (sprint_end - now).days),
            blocked_items=blocked_count,
            overdue_items=overdue_count,
            total_issues=total_issues,
        )

        logger.info(
            "Sprint metrics: %d/%d points, %d blocked, %d overdue",
            completed_points, total_points, blocked_count, overdue_count
        )

        return {"metrics": metrics.model_dump()}

    except Exception as e:
        logger.error("Failed to calculate metrics: %s", e)
        return {"error": f"Failed to calculate metrics: {e}"}


async def track_bayes_deliverables(state: SprintPlannerState) -> dict:
    """Track Bayes Consulting deliverables against SOW."""
    if state.get("error"):
        return {}

    if not state.get("include_bayes", True):
        return {"bayes_summary": {}}

    issues = state.get("issues", [])

    try:
        bayes_issues = []
        bayes_labels = {"bayes", "bayes-assigned", "bayes-in-progress", "bayes-review", "bayes-blocked"}

        for issue in issues:
            labels = [l.get("name", "").lower() for l in issue.get("labels", [])]
            if any(bayes_label in labels for bayes_label in bayes_labels):
                bayes_issues.append(issue)

        # Categorize Bayes deliverables
        deliverables = []
        status_counts = {
            "not_started": 0,
            "in_progress": 0,
            "review": 0,
            "done": 0,
            "blocked": 0,
        }

        for issue in bayes_issues:
            labels = [l.get("name", "").lower() for l in issue.get("labels", [])]
            state_label = issue.get("state", "open").lower()

            # Determine status
            if state_label == "closed":
                status = DeliverableStatus.DONE
            elif "bayes-blocked" in labels:
                status = DeliverableStatus.BLOCKED
            elif "bayes-review" in labels:
                status = DeliverableStatus.REVIEW
            elif "bayes-in-progress" in labels:
                status = DeliverableStatus.IN_PROGRESS
            else:
                status = DeliverableStatus.NOT_STARTED

            status_counts[status.value] += 1

            # Extract story points
            points = 0
            for label in labels:
                if label.startswith("points:") or label.startswith("sp:"):
                    try:
                        points = int(label.split(":")[1])
                    except (IndexError, ValueError):
                        points = 1
                    break

            deliverable = Deliverable(
                deliverable_id=str(issue.get("number", 0)),
                title=issue.get("title", ""),
                vendor=VendorType.BAYES_CONSULTING,
                status=status,
                story_points=points,
                labels=labels,
                github_issue_id=issue.get("number"),
            )
            deliverables.append(deliverable)

        # Create Bayes summary
        sow_summary = BayesSOWSummary(
            total_deliverables=len(bayes_issues),
            completed_deliverables=status_counts["done"],
            in_progress_deliverables=status_counts["in_progress"],
            blocked_deliverables=status_counts["blocked"],
            overdue_deliverables=sum(1 for d in deliverables if d.is_overdue),
        )

        logger.info(
            "Bayes tracking: %d deliverables, %d done, %d blocked",
            sow_summary.total_deliverables,
            sow_summary.completed_deliverables,
            sow_summary.blocked_deliverables,
        )

        return {
            "bayes_summary": {
                "deliverables": [d.model_dump() for d in deliverables],
                "status_counts": status_counts,
                "sow_summary": sow_summary.model_dump(),
            }
        }

    except Exception as e:
        logger.error("Failed to track Bayes deliverables: %s", e)
        return {"error": f"Failed to track Bayes deliverables: {e}"}


async def generate_recommendations(state: SprintPlannerState) -> dict:
    """Generate recommendations based on sprint status."""
    if state.get("error"):
        return {"recommendations": []}

    if not state.get("include_recommendations", True):
        return {"recommendations": []}

    recommendations = []
    metrics_data = state.get("metrics", {})
    bayes_summary = state.get("bayes_summary", {})

    try:
        # Check overall sprint health
        if metrics_data:
            health = metrics_data.get("health_status", "unknown")
            completion_rate = metrics_data.get("completion_rate", 0)
            blocked = metrics_data.get("blocked_items", 0)
            overdue = metrics_data.get("overdue_items", 0)

            if health == "critical":
                recommendations.append(
                    f"⚠️ **Critical**: Sprint is at risk. Only {completion_rate:.0f}% complete with {blocked} blocked items."
                )
                recommendations.append(
                    "Consider: Re-prioritizing blocked items or escalating dependencies."
                )
            elif health == "at_risk":
                recommendations.append(
                    f"⚡ **At Risk**: Sprint needs attention. {completion_rate:.0f}% complete."
                )

            if overdue > 0:
                recommendations.append(
                    f"🔴 **Overdue Alert**: {overdue} items are past their due date."
                )

            if blocked > 2:
                recommendations.append(
                    f"🚧 **Blocked Items**: {blocked} items are blocked. Consider a blocker review meeting."
                )

        # Check Bayes deliverables
        if bayes_summary:
            sow = bayes_summary.get("sow_summary", {})
            bayes_blocked = sow.get("blocked_deliverables", 0)
            bayes_overdue = sow.get("overdue_deliverables", 0)

            if bayes_blocked > 0:
                recommendations.append(
                    f"🏭 **Bayes Consulting**: {bayes_blocked} deliverables blocked. "
                    "May need escalation to Bayes team lead."
                )

            if bayes_overdue > 0:
                recommendations.append(
                    f"📅 **Bayes Overdue**: {bayes_overdue} Bayes deliverables are overdue. "
                    "Review SOW timeline implications."
                )

        # Default positive message if no issues
        if not recommendations:
            recommendations.append("✅ Sprint is on track. No immediate actions required.")

        logger.info("Generated %d recommendations", len(recommendations))
        return {"recommendations": recommendations}

    except Exception as e:
        logger.error("Failed to generate recommendations: %s", e)
        return {"recommendations": ["Unable to generate recommendations due to an error."]}


async def generate_report(state: SprintPlannerState) -> dict:
    """Generate comprehensive sprint report."""
    if state.get("error"):
        return {"report": {"error": state["error"]}}

    try:
        metrics_data = state.get("metrics", {})
        bayes_summary = state.get("bayes_summary", {})
        recommendations = state.get("recommendations", [])
        issues = state.get("issues", [])

        # Categorize issues
        completed = []
        in_progress = []
        blocked = []
        overdue = []

        now = datetime.utcnow()

        for issue in issues:
            labels = [l.get("name", "").lower() for l in issue.get("labels", [])]
            state_label = issue.get("state", "open").lower()

            if state_label == "closed":
                completed.append(issue)
            elif "blocked" in labels or "bayes-blocked" in labels:
                blocked.append(issue)
            else:
                in_progress.append(issue)

            # Check overdue
            milestone = issue.get("milestone")
            if milestone and milestone.get("due_on"):
                due_date = datetime.fromisoformat(milestone["due_on"].replace("Z", "+00:00"))
                if due_date < now and state_label != "closed":
                    overdue.append(issue)

        # Build summary text
        health = metrics_data.get("health_status", "unknown")
        completion = metrics_data.get("completion_rate", 0)
        velocity = metrics_data.get("velocity", 0)

        summary = f"""## Sprint Status: {health.upper()}

- **Completion**: {completion:.1f}%
- **Velocity**: {velocity:.2f} points/day
- **Total Issues**: {len(issues)}
- **Completed**: {len(completed)}
- **In Progress**: {len(in_progress)}
- **Blocked**: {len(blocked)}
- **Overdue**: {len(overdue)}
"""

        # Add Bayes section if available
        if bayes_summary:
            sow = bayes_summary.get("sow_summary", {})
            summary += f"""
### Bayes Consulting Status
- **Total Deliverables**: {sow.get('total_deliverables', 0)}
- **Completed**: {sow.get('completed_deliverables', 0)}
- **In Progress**: {sow.get('in_progress_deliverables', 0)}
- **Blocked**: {sow.get('blocked_deliverables', 0)}
- **Budget**: $527,807 SOW
"""

        report = {
            "report_id": f"sprint-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            "sprint_id": metrics_data.get("sprint_id", "current"),
            "sprint_name": metrics_data.get("sprint_name", "Current Sprint"),
            "generated_at": datetime.utcnow().isoformat(),
            "summary": summary,
            "health_status": health,
            "metrics": metrics_data,
            "counts": {
                "completed": len(completed),
                "in_progress": len(in_progress),
                "blocked": len(blocked),
                "overdue": len(overdue),
                "total": len(issues),
            },
            "bayes_summary": bayes_summary,
            "recommendations": recommendations,
        }

        logger.info("Generated sprint report: %s", report["report_id"])
        return {"report": report}

    except Exception as e:
        logger.error("Failed to generate report: %s", e)
        return {"report": {"error": f"Failed to generate report: {e}"}}


# ── Build the Graph ──


def build_sprint_planner_graph() -> StateGraph:
    """Construct the Sprint Planner agent as a LangGraph StateGraph.

    Flow: fetch_sprint_data → calculate_metrics → track_bayes → generate_recommendations → generate_report
    """
    graph = StateGraph(SprintPlannerState)

    # Add nodes
    graph.add_node("fetch_sprint_data", fetch_sprint_data)
    graph.add_node("calculate_metrics", calculate_metrics)
    graph.add_node("track_bayes", track_bayes_deliverables)
    graph.add_node("generate_recommendations", generate_recommendations)
    graph.add_node("generate_report", generate_report)

    # Define edges (linear pipeline)
    graph.set_entry_point("fetch_sprint_data")
    graph.add_edge("fetch_sprint_data", "calculate_metrics")
    graph.add_edge("calculate_metrics", "track_bayes")
    graph.add_edge("track_bayes", "generate_recommendations")
    graph.add_edge("generate_recommendations", "generate_report")
    graph.add_edge("generate_report", END)

    return graph


# Compiled graph ready to invoke
sprint_planner_graph = build_sprint_planner_graph().compile()


# ── Convenience Functions ──


async def get_sprint_status(repository: str | None = None) -> dict:
    """Get quick sprint status."""
    input_state: SprintPlannerState = {
        "query_type": SprintQueryType.STATUS.value,
        "repository": repository,
        "sprint_id": None,
        "include_bayes": True,
        "include_recommendations": False,
        "issues": [],
        "project_items": [],
        "metrics": None,
        "report": None,
        "bayes_summary": None,
        "recommendations": [],
        "error": None,
    }
    result = await sprint_planner_graph.ainvoke(input_state)
    return result.get("metrics", {})


async def get_sprint_report(repository: str | None = None, sprint_id: str | None = None) -> dict:
    """Get full sprint report."""
    input_state: SprintPlannerState = {
        "query_type": SprintQueryType.REPORT.value,
        "repository": repository,
        "sprint_id": sprint_id,
        "include_bayes": True,
        "include_recommendations": True,
        "issues": [],
        "project_items": [],
        "metrics": None,
        "report": None,
        "bayes_summary": None,
        "recommendations": [],
        "error": None,
    }
    result = await sprint_planner_graph.ainvoke(input_state)
    return result.get("report", {})


async def get_bayes_tracking(repository: str | None = None) -> dict:
    """Get Bayes Consulting deliverable tracking."""
    input_state: SprintPlannerState = {
        "query_type": SprintQueryType.BAYES_TRACKING.value,
        "repository": repository,
        "sprint_id": None,
        "include_bayes": True,
        "include_recommendations": False,
        "issues": [],
        "project_items": [],
        "metrics": None,
        "report": None,
        "bayes_summary": None,
        "recommendations": [],
        "error": None,
    }
    result = await sprint_planner_graph.ainvoke(input_state)
    return result.get("bayes_summary", {})
