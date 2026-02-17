"""Code Review Agent — LangGraph subgraph that reviews pull requests.

Flow:
  1. Receive PR event
  2. Fetch diff + changed files
  3. Optionally fetch full file context for architectural understanding
  4. Send to LLM for deep review against the checklist
  5. Parse review result
  6. Post review on GitHub
  7. Log to PostgreSQL
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import END, StateGraph

from src.agents.code_review.prompts import CODE_REVIEW_SYSTEM_PROMPT, PR_ANALYSIS_PROMPT
from src.config import settings
from src.integrations.github_client import GitHubClient
from src.memory.postgres_store import PostgresStore
from src.models.schemas import CodeReviewResult, ReviewComment, ReviewSeverity, ReviewVerdict

logger = logging.getLogger(__name__)


# ── Agent State ──


class CodeReviewState(TypedDict):
    """State flowing through the code review graph."""

    # Input
    repository: str
    pr_number: int
    pr_title: str
    pr_body: str
    pr_author: str
    base_branch: str
    head_branch: str

    # Intermediate
    diff: str
    changed_files: List[Dict[str, Any]]
    file_contexts: Dict[str, str]  # path → full file content

    # Output
    review_result: Optional[Dict[str, Any]]
    posted: bool
    error: Optional[str]


# ── Node Functions ──


async def fetch_pr_data(state: CodeReviewState) -> dict:
    """Fetch the PR diff and changed file list from GitHub."""
    github = GitHubClient()

    try:
        diff = github.get_pr_diff(state["repository"], state["pr_number"])
        files = github.get_pr_files(state["repository"], state["pr_number"])

        logger.info(
            "Fetched PR #%d: %d files changed, %d char diff",
            state["pr_number"], len(files), len(diff),
        )

        return {
            "diff": diff,
            "changed_files": files,
        }
    except Exception as e:
        logger.error("Failed to fetch PR data: %s", e)
        return {"error": f"Failed to fetch PR data: {e}"}


async def fetch_file_contexts(state: CodeReviewState) -> dict:
    """Fetch full file content for key changed files to understand broader context."""
    if state.get("error"):
        return {}

    github = GitHubClient()
    contexts = {}

    # Only fetch context for Python/JS/TS files (the ones we can meaningfully review)
    reviewable_extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".yaml", ".yml", ".toml"}

    for f in state["changed_files"][:10]:  # Cap at 10 files to control cost
        filename = f["filename"]
        ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""

        if ext in reviewable_extensions and f["status"] != "removed":
            content = github.get_file_content(
                state["repository"],
                filename,
                ref=state["head_branch"],
            )
            if content:
                contexts[filename] = content

    logger.info("Fetched full context for %d files", len(contexts))
    return {"file_contexts": contexts}


async def run_llm_review(state: CodeReviewState) -> dict:
    """Send the PR data to the LLM for deep code review."""
    if state.get("error"):
        return {}

    # Build the changed files summary
    files_summary = "\n".join(
        f"- `{f['filename']}` ({f['status']}: +{f['additions']}/-{f['deletions']})"
        for f in state["changed_files"]
    )

    # Build additional context section
    additional_context = ""
    if state.get("file_contexts"):
        context_parts = []
        for path, content in state["file_contexts"].items():
            # Truncate very long files
            if len(content) > 5000:
                content = content[:5000] + "\n... [truncated]"
            context_parts.append(f"### Full file: `{path}`\n```\n{content}\n```")
        additional_context = "## Full File Context\n\n" + "\n\n".join(context_parts)

    # Format the prompt
    user_prompt = PR_ANALYSIS_PROMPT.format(
        repository=state["repository"],
        pr_number=state["pr_number"],
        pr_title=state["pr_title"],
        pr_body=state.get("pr_body", "No description provided."),
        pr_author=state["pr_author"],
        base_branch=state["base_branch"],
        head_branch=state["head_branch"],
        changed_files_summary=files_summary,
        diff=state["diff"][:15000],  # Cap diff size for token limits
        additional_context=additional_context,
    )

    # Choose LLM — prefer Claude for code review, fall back to Azure OpenAI
    if settings.has_anthropic:
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=settings.anthropic_api_key,
            temperature=0,
            max_tokens=4096,
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
        return {"error": "No LLM configured. Set ANTHROPIC_API_KEY or AZURE_OPENAI_API_KEY."}

    messages = [
        SystemMessage(content=CODE_REVIEW_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = await llm.ainvoke(messages)
        content = response.content

        # Parse JSON from the response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        review_result = json.loads(content.strip())
        logger.info(
            "LLM review complete for PR #%d: verdict=%s, %d comments",
            state["pr_number"],
            review_result.get("verdict", "?"),
            len(review_result.get("comments", [])),
        )

        return {"review_result": review_result}

    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM review output: %s", e)
        return {"error": f"Failed to parse LLM review response: {e}"}
    except Exception as e:
        logger.error("LLM review failed: %s", e)
        return {"error": f"LLM review failed: {e}"}


async def post_review_to_github(state: CodeReviewState) -> dict:
    """Post the review result as a GitHub PR review."""
    if state.get("error") or not state.get("review_result"):
        return {"posted": False}

    github = GitHubClient()
    result = state["review_result"]

    try:
        # Format inline comments for GitHub API
        inline_comments = []
        for comment in result.get("comments", []):
            inline_comments.append({
                "path": comment["file_path"],
                "line": comment.get("line", 1),
                "body": comment["body"],
            })

        # Post the review
        github.post_review(
            repo_full_name=state["repository"],
            pr_number=state["pr_number"],
            body=result.get("summary", "Review complete."),
            event=result.get("verdict", "COMMENT"),
            comments=inline_comments,
        )

        return {"posted": True}

    except Exception as e:
        logger.error("Failed to post review to GitHub: %s", e)
        return {"posted": False, "error": f"Failed to post review: {e}"}


async def log_review(state: CodeReviewState) -> dict:
    """Persist the review result to PostgreSQL for audit trail."""
    if not state.get("review_result"):
        return {}

    try:
        store = PostgresStore()
        result = state["review_result"]

        await store.log_review(
            repository=state["repository"],
            pr_number=state["pr_number"],
            pr_title=state["pr_title"],
            pr_author=state["pr_author"],
            verdict=result.get("verdict", "COMMENT"),
            summary=result.get("summary", ""),
            comments=result.get("comments", []),
            security_issues=result.get("security_issues", []),
            deprecated_deps=result.get("deprecated_deps", []),
        )

        logger.info("Review for PR #%d logged to PostgreSQL", state["pr_number"])
    except Exception as e:
        logger.error("Failed to log review: %s", e)

    return {}


# ── Build the Graph ──


def build_code_review_graph() -> StateGraph:
    """Construct the Code Review agent as a LangGraph StateGraph.

    Flow: fetch_pr_data → fetch_file_contexts → run_llm_review → post_review → log_review
    """
    graph = StateGraph(CodeReviewState)

    # Add nodes
    graph.add_node("fetch_pr_data", fetch_pr_data)
    graph.add_node("fetch_file_contexts", fetch_file_contexts)
    graph.add_node("run_llm_review", run_llm_review)
    graph.add_node("post_review_to_github", post_review_to_github)
    graph.add_node("log_review", log_review)

    # Define edges (linear pipeline for Phase 1)
    graph.set_entry_point("fetch_pr_data")
    graph.add_edge("fetch_pr_data", "fetch_file_contexts")
    graph.add_edge("fetch_file_contexts", "run_llm_review")
    graph.add_edge("run_llm_review", "post_review_to_github")
    graph.add_edge("post_review_to_github", "log_review")
    graph.add_edge("log_review", END)

    return graph


# Compiled graph ready to invoke
code_review_graph = build_code_review_graph().compile()
