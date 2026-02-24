"""Data models for Sprint Planner Agent."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DeliverableStatus(str, Enum):
    """Status of a vendor deliverable."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    BLOCKED = "blocked"


class VendorType(str, Enum):
    """Vendor types for deliverable tracking."""

    BAYES_CONSULTING = "bayes_consulting"
    INTERNAL = "internal"
    OTHER = "other"


class SprintMetrics(BaseModel):
    """Sprint velocity and health metrics."""

    sprint_id: str
    sprint_name: str
    start_date: datetime
    end_date: datetime
    total_story_points: int = 0
    completed_story_points: int = 0
    remaining_story_points: int = 0
    velocity: float = 0.0  # points per day
    days_remaining: int = 0
    blocked_items: int = 0
    overdue_items: int = 0
    total_issues: int = 0

    @property
    def completion_rate(self) -> float:
        """Calculate completion percentage."""
        if self.total_story_points == 0:
            return 0.0
        return (self.completed_story_points / self.total_story_points) * 100

    @property
    def health_status(self) -> str:
        """Determine sprint health status."""
        if self.completion_rate >= 70 and self.blocked_items == 0:
            return "healthy"
        elif self.completion_rate >= 50 or self.blocked_items <= 2:
            return "at_risk"
        else:
            return "critical"


class Deliverable(BaseModel):
    """A vendor deliverable with tracking information."""

    deliverable_id: str
    title: str
    vendor: VendorType = VendorType.INTERNAL
    status: DeliverableStatus = DeliverableStatus.NOT_STARTED
    due_date: datetime | None = None
    assigned_to: str | None = None
    story_points: int = 0
    labels: list[str] = Field(default_factory=list)
    github_issue_id: int | None = None
    github_pr_id: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Bayes-specific tracking
    sow_reference: str | None = None  # Reference to SOW line item
    budget_allocation: float | None = None  # Budget for this deliverable

    @property
    def is_overdue(self) -> bool:
        """Check if deliverable is overdue."""
        if self.due_date and self.status not in [DeliverableStatus.DONE]:
            return datetime.utcnow() > self.due_date
        return False

    @property
    def is_bayes(self) -> bool:
        """Check if this is a Bayes Consulting deliverable."""
        return self.vendor == VendorType.BAYES_CONSULTING or "bayes" in " ".join(self.labels).lower()


class SprintReport(BaseModel):
    """Generated sprint report."""

    report_id: str
    sprint_id: str
    sprint_name: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    # Summary
    summary: str
    health_status: str  # healthy, at_risk, critical

    # Metrics
    metrics: SprintMetrics

    # Item breakdown
    completed: list[Deliverable] = Field(default_factory=list)
    in_progress: list[Deliverable] = Field(default_factory=list)
    blocked: list[Deliverable] = Field(default_factory=list)
    overdue: list[Deliverable] = Field(default_factory=list)

    # Vendor tracking
    bayes_deliverables: list[Deliverable] = Field(default_factory=list)
    bayes_status_summary: dict[str, Any] = Field(default_factory=dict)

    # Recommendations
    recommendations: list[str] = Field(default_factory=list)

    # Action items
    action_items: list[dict[str, Any]] = Field(default_factory=list)


class BayesSOWSummary(BaseModel):
    """Summary of Bayes Consulting SOW tracking."""

    total_budget: float = 527807.0  # From SOW
    total_deliverables: int = 0
    completed_deliverables: int = 0
    in_progress_deliverables: int = 0
    blocked_deliverables: int = 0
    overdue_deliverables: int = 0

    # Milestone tracking
    summit_ecosystem_status: str = "in_progress"  # Due Oct 2025
    ai_agents_status: str = "pending"  # 16 agents
    data_contributor_status: str = "pending"
    monetization_status: str = "pending"

    @property
    def completion_rate(self) -> float:
        """Calculate completion rate."""
        if self.total_deliverables == 0:
            return 0.0
        return (self.completed_deliverables / self.total_deliverables) * 100


class SprintQueryType(str, Enum):
    """Types of sprint queries."""

    STATUS = "status"  # General sprint status
    REPORT = "report"  # Generate full report
    BAYES_TRACKING = "bayes_tracking"  # Track Bayes deliverables
    VELOCITY = "velocity"  # Velocity analysis
    BLOCKERS = "blockers"  # Blocked items
    OVERDUE = "overdue"  # Overdue items


class SprintPlannerInput(BaseModel):
    """Input for Sprint Planner agent."""

    query_type: SprintQueryType
    repository: str | None = None
    sprint_id: str | None = None
    include_bayes: bool = True
    include_recommendations: bool = True
