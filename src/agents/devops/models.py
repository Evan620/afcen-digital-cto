"""Data models for DevOps & CI/CD Agent."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AlertCategory(str, Enum):
    """Categories of DevOps alerts."""

    BUILD_FAILURE = "build_failure"
    TEST_FAILURE = "test_failure"
    SECURITY_VULNERABILITY = "security_vulnerability"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    DEPLOYMENT_FAILURE = "deployment_failure"


class AlertSeverity(str, Enum):
    """Severity levels for DevOps alerts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DevOpsAlert(BaseModel):
    """A DevOps alert generated from pipeline analysis."""

    alert_id: str
    category: AlertCategory
    severity: AlertSeverity
    title: str
    description: str = ""
    repository: str = ""
    workflow_name: str = ""
    workflow_run_id: int | None = None
    branch: str = ""
    commit_sha: str = ""
    html_url: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DevOpsQueryType(str, Enum):
    """Types of DevOps queries."""

    PIPELINE_STATUS = "pipeline_status"
    FAILURE_ANALYSIS = "failure_analysis"
    SECURITY_SCAN = "security_scan"
    DEVOPS_REPORT = "devops_report"


class DevOpsReport(BaseModel):
    """Comprehensive DevOps health report."""

    report_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    summary: str = ""
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    alerts: list[DevOpsAlert] = Field(default_factory=list)
    pipeline_health: str = "unknown"  # healthy, degraded, critical
    recommendations: list[str] = Field(default_factory=list)
    repositories: list[str] = Field(default_factory=list)
