"""Tests for the APScheduler automation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from unittest.mock import patch

from src.scheduler import (
    _parse_cron,
    configure_scheduler,
    daily_standup_job,
    weekly_sprint_report_job,
    bayes_tracking_alert_job,
)


class TestCronParsing:
    """Test cron expression parsing."""

    def test_parse_standard_cron(self):
        result = _parse_cron("0 8 * * 1-5")
        assert result["minute"] == "0"
        assert result["hour"] == "8"
        assert result["day"] == "*"
        assert result["month"] == "*"
        assert result["day_of_week"] == "1-5"

    def test_parse_weekly_cron(self):
        result = _parse_cron("0 9 * * 1")
        assert result["hour"] == "9"
        assert result["day_of_week"] == "1"

    def test_parse_mwf_cron(self):
        result = _parse_cron("0 10 * * 1,3,5")
        assert result["hour"] == "10"
        assert result["day_of_week"] == "1,3,5"

    def test_invalid_cron_raises(self):
        with pytest.raises(ValueError, match="Invalid cron"):
            _parse_cron("bad cron")


class TestSchedulerConfiguration:
    """Test scheduler job registration."""

    def test_configure_scheduler_creates_three_jobs(self):
        """configure_scheduler should register 5 cron jobs (3 Phase 2 + 2 Phase 3)."""
        scheduler = configure_scheduler()
        jobs = scheduler.get_jobs()

        job_ids = {j.id for j in jobs}
        # Phase 2 jobs
        assert "daily_standup" in job_ids
        assert "weekly_report" in job_ids
        assert "bayes_alert" in job_ids
        # Phase 3 jobs
        assert "market_scan" in job_ids
        assert "morning_brief" in job_ids
        assert len(jobs) == 5


class TestSchedulerJobs:
    """Test individual scheduled job functions."""

    @pytest.mark.asyncio
    async def test_daily_standup_job(self):
        """daily_standup_job should generate and save a report."""
        with patch(
            "src.agents.sprint_planner.agent.get_sprint_report", new_callable=AsyncMock
        ) as mock_report, patch(
            "src.memory.postgres_store.PostgresStore.save_report", new_callable=AsyncMock
        ) as mock_save:
            mock_report.return_value = {"summary": "Sprint on track"}
            mock_save.return_value = 1

            await daily_standup_job()

            mock_report.assert_called_once()
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_weekly_sprint_report_job(self):
        """weekly_sprint_report_job should generate and save a report."""
        with patch(
            "src.agents.sprint_planner.agent.get_sprint_report", new_callable=AsyncMock
        ) as mock_report, patch(
            "src.memory.postgres_store.PostgresStore.save_report", new_callable=AsyncMock
        ) as mock_save:
            mock_report.return_value = {"summary": "Weekly sprint report"}
            mock_save.return_value = 1

            await weekly_sprint_report_job()

            mock_report.assert_called_once()
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_bayes_tracking_alert_with_issues(self):
        """bayes_tracking_alert_job should save alert when issues exist."""
        with patch(
            "src.agents.sprint_planner.agent.get_bayes_tracking", new_callable=AsyncMock
        ) as mock_bayes, patch(
            "src.memory.postgres_store.PostgresStore.save_report", new_callable=AsyncMock
        ) as mock_save:
            mock_bayes.return_value = {
                "sow_summary": {
                    "blocked_deliverables": 2,
                    "overdue_deliverables": 1,
                },
                "deliverables": [],
            }
            mock_save.return_value = 1

            await bayes_tracking_alert_job()

            mock_save.assert_called_once()
            call_args = mock_save.call_args
            assert call_args[0][0] == "bayes_alert"
            assert call_args[0][1]["blocked"] == 2

    @pytest.mark.asyncio
    async def test_bayes_tracking_alert_no_issues(self):
        """bayes_tracking_alert_job should skip saving when no issues."""
        with patch(
            "src.agents.sprint_planner.agent.get_bayes_tracking", new_callable=AsyncMock
        ) as mock_bayes, patch(
            "src.memory.postgres_store.PostgresStore.save_report", new_callable=AsyncMock
        ) as mock_save:
            mock_bayes.return_value = {
                "sow_summary": {
                    "blocked_deliverables": 0,
                    "overdue_deliverables": 0,
                },
            }

            await bayes_tracking_alert_job()

            mock_save.assert_not_called()
