"""Pydantic models for data flowing through the Digital CTO system."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ── GitHub Event Models ──


class PRAction(str, Enum):
    """GitHub pull_request webhook action types we handle."""

    OPENED = "opened"
    SYNCHRONIZE = "synchronize"
    REOPENED = "reopened"


class PRUser(BaseModel):
    """GitHub user who opened the PR."""

    login: str
    avatar_url: str = ""


class PRHead(BaseModel):
    """Head branch info from a PR event."""

    ref: str
    sha: str


class PRBase(BaseModel):
    """Base branch info from a PR event."""

    ref: str
    sha: str


class PullRequestData(BaseModel):
    """Core PR data extracted from a GitHub webhook payload."""

    number: int
    title: str
    body: str = ""
    html_url: str
    diff_url: str
    user: PRUser
    head: PRHead
    base: PRBase
    created_at: str = ""
    updated_at: str = ""


class PRWebhookEvent(BaseModel):
    """Parsed GitHub pull_request webhook event."""

    action: str
    repository_full_name: str = Field(description="e.g. 'afcen/platform'")
    pull_request: PullRequestData

    @property
    def is_reviewable(self) -> bool:
        """Only review on open/sync/reopen — not on close, label, etc."""
        return self.action in {a.value for a in PRAction}


# ── Code Review Models ──


class ReviewSeverity(str, Enum):
    """Severity levels for review findings."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    SUGGESTION = "suggestion"


class ReviewComment(BaseModel):
    """A single inline review comment to post on a PR."""

    file_path: str = Field(description="Path to the file in the repo")
    line: int = Field(description="Line number in the diff")
    body: str = Field(description="Review comment text (markdown)")
    severity: ReviewSeverity = ReviewSeverity.INFO


class ReviewVerdict(str, Enum):
    """Final verdict for a PR review."""

    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    COMMENT = "COMMENT"


class CodeReviewResult(BaseModel):
    """Complete output from the Code Review agent for a single PR."""

    pr_number: int
    repository: str
    verdict: ReviewVerdict
    summary: str = Field(description="High-level review summary (markdown)")
    comments: list[ReviewComment] = Field(default_factory=list)
    security_issues: list[str] = Field(default_factory=list, description="Security scan findings")
    deprecated_deps: list[str] = Field(default_factory=list, description="Deprecated dependencies found")
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)


# ── Supervisor State ──


class AgentEvent(BaseModel):
    """An event that the supervisor routes to the appropriate sub-agent."""

    event_type: str = Field(description="e.g. 'pull_request', 'sprint_update', 'meeting'")
    source: str = Field(description="e.g. 'github_webhook', 'slack', 'scheduler'")
    payload: dict = Field(default_factory=dict, description="Raw event payload")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── JARVIS Directive Models ──


class JarvisDirectiveType(str, Enum):
    """Types of directives JARVIS can send to the Digital CTO."""

    SPRINT_REPORT = "sprint_report"
    REVIEW_PR = "review_pr"
    TRACK_BAYES = "track_bayes"
    ARCHITECTURE_QUERY = "architecture_query"
    DEVOPS_STATUS = "devops_status"
    APPROVAL_RESPONSE = "approval_response"
    GENERAL_QUERY = "general_query"


class JarvisDirective(BaseModel):
    """A directive from JARVIS (CEO agent) to the Digital CTO."""

    directive_id: str = Field(default_factory=lambda: "")
    type: JarvisDirectiveType
    payload: dict = Field(default_factory=dict)
    priority: str = Field(default="normal", description="low, normal, high, urgent")
    requires_response: bool = True
    sender: str = "jarvis"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CTOResponseStatus(str, Enum):
    """Status of a CTO response to a JARVIS directive."""

    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"
    NEEDS_APPROVAL = "needs_approval"


class CTOResponse(BaseModel):
    """Response from Digital CTO to a JARVIS directive."""

    response_to: str = Field(description="directive_id this responds to")
    status: CTOResponseStatus
    result: dict = Field(default_factory=dict)
    approval_request: dict | None = None
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
