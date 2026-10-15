import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import ledger  # noqa: E402


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SWARMTIER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "proj"))
    (tmp_path / "proj").mkdir()
    return tmp_path


@pytest.mark.parametrize("events,expected", [
    (["created", "assigned", "started", "completed"], None),
    (["created", "assigned", "started", "blocked", "started", "completed"], None),
    (["created", "cancelled"], None),
    (["started", "completed"], "no_creation"),
    (["created", "completed"], "invalid_transition"),
    (["created", "assigned", "started", "completed", "started"], "event_after_terminal"),
])
def test_audit_trajectories(events, expected):
    for e in events:
        ledger.record("T1", e)
    types = {p["type"] for p in ledger.audit()}
    assert (not types) if expected is None else (expected in types)


def test_stuck_and_unrecorded_and_extras():
    for e in ("created", "assigned", "started"):
        ledger.record("T2", e, model="haiku", effort="low", bogus="dropped")
    assert any(p["type"] == "stuck" for p in ledger.audit(now=datetime.now() + timedelta(hours=10)))
    first = ledger.read()[0]
    assert first["effort"] == "low" and "bogus" not in first
    with pytest.raises(ledger.LedgerIncomplete):
        ledger.unrecorded_work(["T2", "T-missing"])
    assert ledger.unrecorded_work(["T2"])
    with pytest.raises(ValueError):
        ledger.record("T3", "exploded")
