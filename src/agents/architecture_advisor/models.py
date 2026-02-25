"""Data models for Architecture Advisor Agent."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ArchitectureQueryType(str, Enum):
    """Types of architecture advisory queries."""

    TECHNOLOGY_EVALUATION = "technology_evaluation"
    DESIGN_REVIEW = "design_review"
    TECH_DEBT_ASSESSMENT = "tech_debt_assessment"
    INFRASTRUCTURE_PROPOSAL = "infrastructure_proposal"
    COST_ANALYSIS = "cost_analysis"


class OptionConsidered(BaseModel):
    """A technology or design option evaluated by the advisor."""

    name: str
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    estimated_cost: str | None = None


class ArchitectureRecommendation(BaseModel):
    """A structured architecture decision recommendation."""

    decision_id: str
    title: str
    context: str = ""
    query_type: ArchitectureQueryType = ArchitectureQueryType.TECHNOLOGY_EVALUATION
    options_considered: list[OptionConsidered] = Field(default_factory=list)
    recommendation: str = ""
    rationale: str = ""
    cost_implications: str = ""
    timeline: str = ""
    risks: list[str] = Field(default_factory=list)
    migration_plan: str = ""
    approval_status: str = "pending"  # pending, approved, rejected
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ArchitectureAdvisorInput(BaseModel):
    """Input for Architecture Advisor agent."""

    query_type: ArchitectureQueryType
    query: str
    repository: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
