"""Onboarding wizard orchestration.

Manages the onboarding flow and persists configuration.
"""

from __future__ import annotations

import logging

from src.tui.onboard.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    TUIConfig,
    is_onboarded,
    load_config,
    mark_onboarded,
    save_config,
)
from src.tui.onboard.steps import run_onboarding

logger = logging.getLogger(__name__)


def should_run_onboarding() -> bool:
    """Check if onboarding should be run.

    Returns:
        True if onboarding is needed
    """
    return not is_onboarded()


def run_wizard(force: bool = False) -> TUIConfig | None:
    """Run the onboarding wizard.

    Args:
        force: Force re-running onboarding even if already done

    Returns:
        Config object if successful, None if cancelled
    """
    # Check if already onboarded
    if not force and is_onboarded():
        existing_config = load_config()
        logger.info("Already onboarded on %s", existing_config.onboarded_at)

        response = input(
            "You've already completed onboarding. Run again? [y/N]: "
        ).strip().lower()

        if response not in ("y", "yes"):
            return existing_config

    print("Starting Digital CTO onboarding...")

    try:
        # Run the wizard
        config = run_onboarding()

        # Save the configuration
        if save_config(config):
            # Mark as onboarded
            mark_onboarded()
            logger.info("Onboarding complete, config saved to %s", CONFIG_FILE)
            return config
        else:
            logger.error("Failed to save configuration")
            return None

    except KeyboardInterrupt:
        print()
        print("\nOnboarding cancelled.")
        return None
    except Exception as e:
        logger.error("Onboarding failed: %s", e)
        print(f"\nError during onboarding: {e}")
        return None


def reset_onboarding() -> bool:
    """Reset onboarding status.

    Useful for testing or starting fresh.

    Returns:
        True if successful
    """
    try:
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
            logger.info("Removed configuration file: %s", CONFIG_FILE)
        return True
    except Exception as e:
        logger.error("Failed to reset onboarding: %s", e)
        return False
