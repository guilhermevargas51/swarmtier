"""Claude quota provider: reads the quota file YOU maintain. No network, no login data.

Source of truth is ``quota.json`` in ``data_dir()`` (or the path in ``SWARMTIER_QUOTA_FILE``):

    {"window_5h_pct": 42, "weekly_pct": 64,
     "resets_at": {"window_5h": "<iso or null>", "weekly": "<iso or null>"},
     "ts": 1760000000.0}

Write it with ``python -m core.quota set --5h 42 --week 64`` (copy the numbers from
Claude Code's /usage screen). ``ts`` is when you wrote it, so the reading carries its own
age; old readings are flagged stale, never hidden. A missing file gives ``None``
percentages with an ``error`` - never zero.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from core.config import data_dir
from core.quota import QuotaProvider, empty_reading

SOURCE = "file"


def quota_file() -> Path:
    env = os.environ.get("SWARMTIER_QUOTA_FILE")
    return Path(env).expanduser() if env else data_dir() / "quota.json"


def write_reading(five_h, weekly, resets_5h=None, resets_week=None, path=None, now=None) -> dict:
    """Store a reading with a timestamp. Percentages must be within 0-100 (None = unknown)."""
    for name, v in (("5h", five_h), ("week", weekly)):
        if v is not None and not 0 <= v <= 100:
            raise ValueError("%s percent must be between 0 and 100, got %r" % (name, v))
    rec = {"window_5h_pct": five_h, "weekly_pct": weekly,
           "resets_at": {"window_5h": resets_5h, "weekly": resets_week},
           "ts": time.time() if now is None else now}
    p = Path(path) if path else quota_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec), encoding="utf-8")
    return rec


class ClaudeProvider(QuotaProvider):
    name = "claude"

    def __init__(self, path=None, now=None):
        self._path = Path(path) if path else None
        self._now = now

    def read(self) -> dict:
        p = self._path or quota_file()
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                raise ValueError("not an object")
        except (OSError, ValueError) as e:
            return empty_reading(SOURCE, "no usable quota file at %s (%s); run: python -m core.quota set --5h N --week N"
                                 % (p, str(e)[:40]))
        now = time.time() if self._now is None else self._now
        ts = d.get("ts")
        resets = d.get("resets_at") or {}
        return {"window_5h_pct": d.get("window_5h_pct"),
                "weekly_pct": d.get("weekly_pct"),
                "resets_at": {"window_5h": resets.get("window_5h"), "weekly": resets.get("weekly")},
                "source": SOURCE,
                "age_s": None if ts is None else max(0, int(now - ts))}
