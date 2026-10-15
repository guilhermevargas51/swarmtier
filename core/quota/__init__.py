"""Quota readers behind a small pluggable interface.

A provider returns a dict with these keys:

    window_5h_pct  float | None   percent used in the rolling 5-hour window
    weekly_pct     float | None   percent used in the weekly window
    resets_at      dict           {"window_5h": iso-or-None, "weekly": iso-or-None}
    source         str            where the numbers came from ("api", "cache", "file", ...)
    age_s          int | None     how old the reading is, in seconds (None if unknown)

Honesty rule: a missing reading is ``None``, NEVER 0. "Could not measure" must not read
as "bucket is empty". Stale readings are flagged by :func:`is_stale`, not hidden.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class QuotaProvider(ABC):
    """Implement ``read()`` to plug in another quota source."""

    name = "base"

    @abstractmethod
    def read(self) -> dict:
        """Return the dict described in the module docstring. Must not raise on I/O trouble."""


def empty_reading(source: str, error: str = "") -> dict:
    out = {"window_5h_pct": None, "weekly_pct": None,
           "resets_at": {"window_5h": None, "weekly": None},
           "source": source, "age_s": None}
    if error:
        out["error"] = error
    return out


def is_stale(reading: dict, stale_after_s=None) -> bool:
    """True if the reading is older than the threshold, or its age is unknown/errored."""
    if stale_after_s is None:
        from core.config import load_config
        stale_after_s = load_config()["quota"]["stale_after_s"]
    age = reading.get("age_s")
    return bool(reading.get("error")) or age is None or age > stale_after_s
