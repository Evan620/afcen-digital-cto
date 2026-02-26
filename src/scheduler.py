"""APScheduler automation for recurring Digital CTO tasks.

Phase 2 Jobs:
  1. Daily standup — sprint report every weekday morning
  2. Weekly sprint report — full report every Monday
  3. Bayes tracking alert — check for blocked/overdue deliverables MWF

Phase 3 Jobs:
  4. Market scan — collect market intelligence from news, DFIs, registries
  5. Morning brief — generate and deliver daily morning briefing
  6. Meeting intelligence — check for outstanding actions and upcoming meetings
"""

from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import settings

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _parse_cron(expr: str) -> dict:
    """Parse a 5-field cron expression into CronTrigger kwargs."""
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression (need 5 fields): {expr}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


async def daily_standup_job() -> None:
    """Generate and persist a daily sprint status report."""
    logger.info("Running daily standup job...")
    try:
        from src.agents.sprint_planner.agent import get_sprint_report
        from src.memory.postgres_store import PostgresStore

        report = await get_sprint_report()

        store = PostgresStore()
        notified = False

        # Persist report
        await store.save_report("daily_standup", report, notified=notified)

        # Optionally notify JARVIS via OpenClaw
        try:
            from src.integrations.openclaw_client import get_openclaw_client

            client = get_openclaw_client()
            if client.is_connected:
                await client.notify_sprint_update(report)
                notified = True
                logger.info("Daily standup sent to JARVIS")
        except Exception as e:
            logger.debug("JARVIS notification skipped: %s", e)

        logger.info("Daily standup complete (notified=%s)", notified)

    except Exception as e:
        logger.error("Daily standup job failed: %s", e)


async def weekly_sprint_report_job() -> None:
    """Generate and persist a comprehensive weekly sprint report."""
    logger.info("Running weekly sprint report job...")
    try:
        from src.agents.sprint_planner.agent import get_sprint_report
        from src.memory.postgres_store import PostgresStore

        report = await get_sprint_report()

        store = PostgresStore()
        notified = False

        await store.save_report("weekly_report", report, notified=notified)

        try:
            from src.integrations.openclaw_client import get_openclaw_client

            client = get_openclaw_client()
            if client.is_connected:
                await client.notify_sprint_update({
                    "type": "weekly_report",
                    "report": report,
                })
                notified = True
        except Exception as e:
            logger.debug("JARVIS notification skipped: %s", e)

        logger.info("Weekly sprint report complete (notified=%s)", notified)

    except Exception as e:
        logger.error("Weekly sprint report job failed: %s", e)


async def bayes_tracking_alert_job() -> None:
    """Check for blocked or overdue Bayes deliverables and save an alert."""
    logger.info("Running Bayes tracking alert job...")
    try:
        from src.agents.sprint_planner.agent import get_bayes_tracking
        from src.memory.postgres_store import PostgresStore

        bayes = await get_bayes_tracking()

        sow = bayes.get("sow_summary", {})
        blocked = sow.get("blocked_deliverables", 0)
        overdue = sow.get("overdue_deliverables", 0)

        # Only save alert if there are issues
        if blocked > 0 or overdue > 0:
            store = PostgresStore()
            alert_data = {
                "blocked": blocked,
                "overdue": overdue,
                "sow_summary": sow,
                "deliverables": bayes.get("deliverables", []),
                "alert_level": "critical" if blocked > 2 or overdue > 2 else "warning",
            }

            await store.save_report("bayes_alert", alert_data)

            # Notify JARVIS if connected
            try:
                from src.integrations.openclaw_client import get_openclaw_client

                client = get_openclaw_client()
                if client.is_connected:
                    await client.send_agent_message(
                        recipient="jarvis",
                        message=(
                            f"Bayes Alert: {blocked} deliverables blocked, "
                            f"{overdue} overdue. Review required."
                        ),
                        context=alert_data,
                    )
            except Exception as e:
                logger.debug("JARVIS notification skipped: %s", e)

            logger.info("Bayes alert saved: %d blocked, %d overdue", blocked, overdue)
        else:
            logger.info("Bayes tracking: no issues found")

    except Exception as e:
        logger.error("Bayes tracking alert job failed: %s", e)


async def market_scan_job() -> None:
    """Collect market intelligence from all enabled sources.

    Runs at 3 AM daily to collect overnight developments.
    """
    logger.info("Running market scan job...")
    try:
        from src.agents.market_scanner.agent import collect_market_data
        from src.memory.postgres_store import PostgresStore

        # Collect data from all sources
        result = await collect_market_data(hours_back=24)

        # Store collection summary
        store = PostgresStore()
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "sources_succeeded": result.get("sources_succeeded", []),
            "sources_failed": result.get("sources_failed", {}),
            "news_items_collected": len(result.get("news_items", [])),
            "dfi_opportunities_collected": len(result.get("dfi_opportunities", [])),
            "carbon_updates_collected": len(result.get("carbon_updates", [])),
        }

        await store.save_report("market_scan", summary, notified=False)

        logger.info(
            "Market scan complete: %d news, %d DFI opportunities, %d carbon updates",
            summary["news_items_collected"],
            summary["dfi_opportunities_collected"],
            summary["carbon_updates_collected"],
        )

    except Exception as e:
        logger.error("Market scan job failed: %s", e)


async def morning_brief_job() -> None:
    """Generate and deliver the morning brief.

    Runs at 6 AM daily to deliver briefing to CEO via JARVIS.
    """
    logger.info("Running morning brief job...")
    try:
        from src.agents.market_scanner.agent import generate_morning_brief
        from src.memory.postgres_store import PostgresStore

        # Generate brief
        brief = await generate_morning_brief()

        if not brief:
            logger.warning("Morning brief generation returned None")
            return

        # Store brief (already saved by agent, just log)
        logger.info(
            "Morning brief generated: %s - %d moves, %d opportunities",
            brief.brief_id,
            len(brief.market_moves),
            len(brief.funding_opportunities),
        )

        # If JARVIS notification failed in agent, try again
        if not brief.delivered:
            try:
                from src.integrations.openclaw_client import get_openclaw_client

                client = get_openclaw_client()
                if client.is_connected:
                    # Format brief message
                    message = f"""Morning Brief for {brief.brief_date.strftime('%B %d, %Y')}

## Market Moves ({len(brief.market_moves)})
"""
                    for move in brief.market_moves[:5]:
                        message += f"- {move.title}: {move.description}\n"

                    if brief.funding_opportunities:
                        message += f"\n## Funding Opportunities ({len(brief.funding_opportunities)})\n"
                        for opp in brief.funding_opportunities[:5]:
                            message += f"- [{opp.source}] {opp.title}: {opp.description[:100]}...\n"

                    if brief.recommended_actions:
                        message += "\n## Recommended Actions\n"
                        for action in brief.recommended_actions[:5]:
                            message += f"- [{action.priority.upper()}] {action.title}: {action.description}\n"

                    await client.send_agent_message(
                        recipient="jarvis",
                        message=message,
                        context={
                            "type": "morning_brief",
                            "brief_id": brief.brief_id,
                            "brief_date": brief.brief_date.isoformat(),
                        },
                    )
                    logger.info("Morning brief delivered to JARVIS")
            except Exception as e:
                logger.debug("JARVIS notification for morning brief failed: %s", e)

    except Exception as e:
        logger.error("Morning brief job failed: %s", e)


async def meeting_intel_job() -> None:
    """Check for outstanding meeting action items and generate status report.

    Runs at 7 AM weekdays to surface overdue items and recent meeting insights.
    """
    logger.info("Running meeting intelligence job...")
    try:
        from src.agents.meeting_intelligence.agent import get_meeting_status
        from src.memory.postgres_store import PostgresStore

        status = await get_meeting_status()

        if not status:
            logger.warning("Meeting intelligence status returned None")
            return

        # Store report
        store = PostgresStore()
        await store.save_report("meeting_intel", status, notified=False)

        outstanding = status.get("outstanding_action_items", 0)

        # Notify JARVIS if there are overdue items
        if outstanding > 0:
            try:
                from src.integrations.openclaw_client import get_openclaw_client

                client = get_openclaw_client()
                if client.is_connected:
                    await client.send_agent_message(
                        recipient="jarvis",
                        message=(
                            f"Meeting Intelligence: {outstanding} outstanding action items. "
                            f"Recent meetings: {status.get('recent_meetings_count', 0)} in last 30 days."
                        ),
                        context={"type": "meeting_intel", **status},
                    )
                    logger.info("Meeting intel status sent to JARVIS")
            except Exception as e:
                logger.debug("JARVIS notification skipped: %s", e)

        logger.info(
            "Meeting intel job complete: %d outstanding actions, %d recent meetings",
            outstanding,
            status.get("recent_meetings_count", 0),
        )

    except Exception as e:
        logger.error("Meeting intelligence job failed: %s", e)


def configure_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler with cron jobs from config.

    Returns the scheduler (not yet started — call scheduler.start() in lifespan).
    """
    global _scheduler

    scheduler = AsyncIOScheduler()

    # Daily standup
    try:
        cron_kwargs = _parse_cron(settings.daily_standup_cron)
        scheduler.add_job(
            daily_standup_job,
            CronTrigger(**cron_kwargs),
            id="daily_standup",
            name="Daily Standup Report",
            replace_existing=True,
        )
        logger.info("Scheduled daily standup: %s", settings.daily_standup_cron)
    except Exception as e:
        logger.error("Failed to schedule daily standup: %s", e)

    # Weekly report
    try:
        cron_kwargs = _parse_cron(settings.weekly_report_cron)
        scheduler.add_job(
            weekly_sprint_report_job,
            CronTrigger(**cron_kwargs),
            id="weekly_report",
            name="Weekly Sprint Report",
            replace_existing=True,
        )
        logger.info("Scheduled weekly report: %s", settings.weekly_report_cron)
    except Exception as e:
        logger.error("Failed to schedule weekly report: %s", e)

    # Bayes tracking alert
    try:
        cron_kwargs = _parse_cron(settings.bayes_alert_cron)
        scheduler.add_job(
            bayes_tracking_alert_job,
            CronTrigger(**cron_kwargs),
            id="bayes_alert",
            name="Bayes Tracking Alert",
            replace_existing=True,
        )
        logger.info("Scheduled Bayes alert: %s", settings.bayes_alert_cron)
    except Exception as e:
        logger.error("Failed to schedule Bayes alert: %s", e)

    # Phase 3: Market scan
    if settings.market_scan_enabled:
        try:
            cron_kwargs = _parse_cron(settings.market_scan_cron)
            scheduler.add_job(
                market_scan_job,
                CronTrigger(**cron_kwargs),
                id="market_scan",
                name="Market Intelligence Scan",
                replace_existing=True,
            )
            logger.info("Scheduled market scan: %s", settings.market_scan_cron)
        except Exception as e:
            logger.error("Failed to schedule market scan: %s", e)

    # Phase 3: Morning brief
    if settings.morning_brief_enabled:
        try:
            cron_kwargs = _parse_cron(settings.morning_brief_cron)
            scheduler.add_job(
                morning_brief_job,
                CronTrigger(**cron_kwargs),
                id="morning_brief",
                name="Morning Brief Generation",
                replace_existing=True,
            )
            logger.info("Scheduled morning brief: %s", settings.morning_brief_cron)
        except Exception as e:
            logger.error("Failed to schedule morning brief: %s", e)

    # Phase 3: Meeting intelligence
    if settings.meeting_intel_enabled:
        try:
            cron_kwargs = _parse_cron(settings.meeting_intel_cron)
            scheduler.add_job(
                meeting_intel_job,
                CronTrigger(**cron_kwargs),
                id="meeting_intel",
                name="Meeting Intelligence Status",
                replace_existing=True,
            )
            logger.info("Scheduled meeting intel: %s", settings.meeting_intel_cron)
        except Exception as e:
            logger.error("Failed to schedule meeting intel: %s", e)

    _scheduler = scheduler
    return scheduler


def get_scheduler() -> AsyncIOScheduler | None:
    """Get the global scheduler instance."""
    return _scheduler
