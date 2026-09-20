"""Small helpers that keep tool output readable and bounded."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .config import settings


def dollars(n: float | int | None) -> str | None:
    """``1234567`` → ``"$1.2M"``; ``None`` stays ``None``."""
    if n is None:
        return None
    n = float(n)
    if abs(n) >= 1e9:
        return f"${n / 1e9:.1f}B"
    if abs(n) >= 1e6:
        return f"${n / 1e6:.1f}M"
    if abs(n) >= 1e3:
        return f"${n / 1e3:.0f}K"
    return f"${n:.0f}"


def clip_text(text: str | None) -> str | None:
    """Truncate free text to the configured limit with a visible marker."""
    if text is None or len(text) <= settings.max_text_chars:
        return text
    return text[: settings.max_text_chars].rstrip() + " …[truncated]"


def cap_rows(rows: list[Any], limit: int | None = None) -> list[Any]:
    """Never return more rows than the tool's limit or the server-wide cap."""
    cap = min(limit or settings.max_rows, settings.max_rows)
    return rows[:cap]


def envelope(data: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
    """Wrap a tool result with ``as_of`` and the disclaimer."""
    from .client import DISCLAIMER

    return {
        "as_of": as_of or datetime.now(UTC).isoformat(timespec="seconds"),
        **data,
        "disclaimer": DISCLAIMER,
    }
