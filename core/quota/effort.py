"""Effort levels per Claude model tier, and the weekly pace check.

Effort is a per-dispatch setting on subagents. Never write an effort from memory or copy
it from another model: models differ in what they accept. This table is the project's
default; override it in ``swarmtier.toml`` under ``[effort]`` if your models differ.

``pace()`` answers: "at this rate, will the weekly quota last the week?" by comparing
the percent spent with the percent of the week that has elapsed.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from core.config import load_config

LEVELS = ("low", "medium", "high", "xhigh", "max")

# tier -> (supported efforts, recommended ceiling). Ceilings are advice, not limits.
SUPPORTED = {
    "haiku": LEVELS,
    "sonnet": LEVELS,
    "opus": LEVELS,
}
CEILING = {"haiku": "max", "sonnet": "high", "opus": "high"}  # Sonnet at max costs far more than it adds


def tier_of(model: str) -> str:
    m = (model or "").lower()
    for tier in SUPPORTED:
        if tier in m:
            return tier
    return ""


def supported_efforts(model: str) -> tuple:
    """Efforts accepted for ``model`` (empty tuple if the tier is unknown: omit the flag)."""
    over = load_config().get("effort", {}).get(tier_of(model))
    return tuple(over) if over else SUPPORTED.get(tier_of(model), ())


def check_effort(model: str, effort: str) -> tuple:
    """``(ok, message)``. Unknown model -> not ok: do not guess a flag value."""
    allowed = supported_efforts(model)
    if not allowed:
        return False, "unknown model %r: omit the effort flag or add it under [effort] in swarmtier.toml" % model
    if effort not in allowed:
        return False, "effort %r not supported for %s (supported: %s)" % (effort, model, ", ".join(allowed))
    ceiling = CEILING.get(tier_of(model))
    if ceiling and LEVELS.index(effort) > LEVELS.index(ceiling):
        return True, "allowed, but above the recommended ceiling (%s) for %s" % (ceiling, tier_of(model))
    return True, "ok"


def _epoch(reset):
    if reset in (None, ""):
        return None
    if isinstance(reset, (int, float)):
        return reset / 1000.0 if reset > 1e11 else float(reset)
    try:
        dt = datetime.fromisoformat(str(reset).replace("Z", "+00:00"))
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()
    except ValueError:
        return None


def pace(pct_spent, resets_at, now=None) -> dict:
    """Weekly pace: ``{spent_pct, elapsed_pct, ratio, verdict}``.

    verdict is ``above`` (ratio > pace_high: hold back), ``on`` or ``below`` (room to
    spend), or ``unknown`` when either input is missing - unknown is never treated as ok.
    """
    cfg = load_config()["quota"]
    end = _epoch(resets_at)
    if pct_spent is None or end is None:
        return {"spent_pct": pct_spent, "elapsed_pct": None, "ratio": None, "verdict": "unknown"}
    now = time.time() if now is None else now
    week_s = cfg["week_days"] * 86400.0
    elapsed = min(max(1 - (end - now) / week_s, 0.01), 1.0) * 100
    ratio = pct_spent / elapsed
    verdict = "above" if ratio > cfg["pace_high"] else ("on" if ratio >= cfg["pace_low"] else "below")
    return {"spent_pct": pct_spent, "elapsed_pct": round(elapsed, 1), "ratio": round(ratio, 2), "verdict": verdict}
