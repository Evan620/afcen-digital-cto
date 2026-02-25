"""Architecture Advisor Agent — LangGraph subgraph for architecture decisions.

Flow:
  1. Gather context (repo structure, prior decisions)
  2. Analyze with LLM
  3. Build recommendation
  4. Persist decision
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

from src.agents.architecture_advisor.models import (
    ArchitectureQueryType,
    ArchitectureRecommendation,
    OptionConsidered,
)
from src.agents.architecture_advisor.prompts import (
    ARCHITECTURE_ADVISOR_SYSTEM_PROMPT,
    ARCHITECTURE_QUERY_PROMPT,
)
from src.config import settings

logger = logging.getLogger(__name__)


# ── Agent State ──


class ArchitectureAdvisorState(TypedDict):
    """State flowing through the Architecture Advisor graph."""

    # Input
    query_type: str
    query: str
    repository: str | None
    context: dict[str, Any]

    # Intermediate
    repo_context: str
    prior_decisions: list[dict[str, Any]]
    llm_output: str

    # Output
    recommendation: dict[str, Any] | None
    error: str | None


# ── Node Functions ──


async def gather_context(state: ArchitectureAdvisorState) -> dict:
    """Gather repository context and prior decisions."""
    repo_context = "No repository specified."
    prior_decisions: list[dict[str, Any]] = []

    try:
        # Fetch repo structure if specified
        if state.get("repository"):
            from src.integrations.github_client import GitHubClient

            github = GitHubClient()
            try:
                repo = github.github.get_repo(state["repository"])
                # Get top-level structure
                contents = repo.get_contents("")
                if isinstance(contents, list):
                    tree = "\n".join(f"- {c.path}/" if c.type == "dir" else f"- {c.path}" for c in contents[:30])
                    repo_context = f"**Repository:** {state['repository']}\n\n**Structure:**\n{tree}"
            except Exception as e:
                logger.warning("Failed to fetch repo structure: %s", e)
                repo_context = f"Repository: {state['repository']} (structure unavailable)"

        # Fetch prior architecture decisions from PostgreSQL
        try:
            from src.memory.postgres_store import PostgresStore

            store = PostgresStore()
            async with store.session() as session:
                from sqlalchemy import select
                from src.memory.postgres_store import AgentDecision

                stmt = (
                    select(AgentDecision)
                    .where(AgentDecision.agent_name == "architecture_advisor")
                    .order_by(AgentDecision.created_at.desc())
                    .limit(5)
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()
                prior_decisions = [
                    {
                        "decision_type": r.decision_type,
                        "reasoning": r.reasoning,
                        "outcome": r.outcome,
                        "created_at": r.created_at.isoformat() if r.created_at else "",
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.warning("Failed to fetch prior decisions: %s", e)

        return {"repo_context": repo_context, "prior_decisions": prior_decisions}

    except Exception as e:
        logger.error("Failed to gather context: %s", e)
        return {"repo_context": repo_context, "prior_decisions": [], "error": str(e)}


async def analyze_with_llm(state: ArchitectureAdvisorState) -> dict:
    """Send the architecture query to the LLM for analysis."""
    if state.get("error"):
        return {}

    # Format prior decisions
    prior_text = "No prior decisions found."
    if state.get("prior_decisions"):
        parts = []
        for d in state["prior_decisions"]:
            parts.append(f"- **{d['decision_type']}** ({d['created_at']}): {d['outcome']}")
        prior_text = "\n".join(parts)

    # Format additional context
    additional = ""
    if state.get("context"):
        additional = "\n".join(f"- **{k}**: {v}" for k, v in state["context"].items())

    user_prompt = ARCHITECTURE_QUERY_PROMPT.format(
        query_type=state["query_type"],
        query=state["query"],
        repo_context=state.get("repo_context", "N/A"),
        prior_decisions=prior_text,
        additional_context=additional or "None provided.",
    )

    # LLM cascade: Claude > GLM-5 > Azure OpenAI
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
        return {"error": "No LLM configured. Set ANTHROPIC_API_KEY, ZAI_API_KEY, or AZURE_OPENAI_API_KEY."}

    messages = [
        SystemMessage(content=ARCHITECTURE_ADVISOR_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = await llm.ainvoke(messages)
        content = response.content
        logger.info("Architecture LLM response: %d chars", len(content))
        return {"llm_output": content}

    except Exception as e:
        logger.error("Architecture LLM analysis failed: %s", e)
        return {"error": f"LLM analysis failed: {e}"}


async def build_recommendation(state: ArchitectureAdvisorState) -> dict:
    """Parse LLM output into a structured ArchitectureRecommendation."""
    if state.get("error") or not state.get("llm_output"):
        return {}

    try:
        content = state["llm_output"]

        # Extract JSON from response
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
            json_str = content[start:end]
        else:
            json_str = content.strip()

        parsed = json.loads(json_str)

        recommendation = ArchitectureRecommendation(
            decision_id=f"arch-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            title=parsed.get("title", "Architecture Recommendation"),
            context=parsed.get("context", ""),
            query_type=ArchitectureQueryType(state["query_type"]),
            options_considered=[
                OptionConsidered(**opt) for opt in parsed.get("options_considered", [])
            ],
            recommendation=parsed.get("recommendation", ""),
            rationale=parsed.get("rationale", ""),
            cost_implications=parsed.get("cost_implications", ""),
            timeline=parsed.get("timeline", ""),
            risks=parsed.get("risks", []),
            migration_plan=parsed.get("migration_plan", ""),
        )

        logger.info("Built architecture recommendation: %s", recommendation.decision_id)
        return {"recommendation": recommendation.model_dump()}

    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Failed to parse architecture recommendation: %s", e)
        return {"error": f"Failed to parse recommendation: {e}"}


async def persist_decision(state: ArchitectureAdvisorState) -> dict:
    """Store the architecture decision to PostgreSQL."""
    if not state.get("recommendation"):
        return {}

    try:
        from src.memory.postgres_store import PostgresStore

        store = PostgresStore()
        rec = state["recommendation"]

        await store.log_decision(
            agent_name="architecture_advisor",
            decision_type=rec.get("query_type", "architecture"),
            reasoning=rec.get("rationale", ""),
            outcome=rec.get("recommendation", ""),
            context={
                "decision_id": rec.get("decision_id"),
                "title": rec.get("title"),
                "options": rec.get("options_considered", []),
                "costs": rec.get("cost_implications"),
                "risks": rec.get("risks", []),
            },
        )

        logger.info("Architecture decision persisted: %s", rec.get("decision_id"))
    except Exception as e:
        logger.error("Failed to persist architecture decision: %s", e)

    return {}


# ── Build the Graph ──


def build_architecture_advisor_graph() -> StateGraph:
    """Construct the Architecture Advisor as a LangGraph StateGraph.

    Flow: gather_context → analyze_with_llm → build_recommendation → persist_decision → END
    """
    graph = StateGraph(ArchitectureAdvisorState)

    graph.add_node("gather_context", gather_context)
    graph.add_node("analyze_with_llm", analyze_with_llm)
    graph.add_node("build_recommendation", build_recommendation)
    graph.add_node("persist_decision", persist_decision)

    graph.set_entry_point("gather_context")
    graph.add_edge("gather_context", "analyze_with_llm")
    graph.add_edge("analyze_with_llm", "build_recommendation")
    graph.add_edge("build_recommendation", "persist_decision")
    graph.add_edge("persist_decision", END)

    return graph


# Compiled graph ready to invoke
architecture_advisor_graph = build_architecture_advisor_graph().compile()


# ── Convenience Function ──


async def query_architecture(
    query: str,
    query_type: str = "technology_evaluation",
    repository: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Submit an architecture query and get a recommendation."""
    input_state: ArchitectureAdvisorState = {
        "query_type": query_type,
        "query": query,
        "repository": repository,
        "context": context or {},
        "repo_context": "",
        "prior_decisions": [],
        "llm_output": "",
        "recommendation": None,
        "error": None,
    }
    result = await architecture_advisor_graph.ainvoke(input_state)
    return result.get("recommendation") or {"error": result.get("error", "Unknown error")}
