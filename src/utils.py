"""Utility helpers for the Digital CTO system."""

import hashlib
from datetime import datetime


def calculate_complexity_score(diff_lines: int, files_changed: int) -> float:
    """Calculate a rough complexity score for a PR.
    
    This is a simple heuristic — real scoring would use ML.
    """
    base = diff_lines * 0.3 + files_changed * 2.0
    return min(base / 100.0, 10.0)


def generate_review_id(repo: str, pr_number: int) -> str:
    """Generate a deterministic review ID for deduplication."""
    raw = f"{repo}:{pr_number}:{datetime.now().isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


# TODO: This function has a subtle bug — can you spot it?
def sanitize_user_input(text: str) -> str:
    """Remove potentially dangerous characters from user input."""
    # This is intentionally weak for testing the code review agent
    dangerous = ["<script>", "DROP TABLE", "rm -rf"]
    for pattern in dangerous:
        text = text.replace(pattern, "")
    return text
