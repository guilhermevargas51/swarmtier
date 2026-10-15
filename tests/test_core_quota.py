import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.quota import is_stale  # noqa: E402
from core.quota.claude import ClaudeProvider, write_reading  # noqa: E402
from core.quota.effort import check_effort, pace  # noqa: E402


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SWARMTIER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "proj"))
    monkeypatch.delenv("SWARMTIER_QUOTA_FILE", raising=False)
    (tmp_path / "proj").mkdir()
    return tmp_path


def test_set_then_read_reports_age(home):
    from core.quota.__main__ import main
    assert main(["set", "--5h", "42", "--week", "64"]) == 0
    r = ClaudeProvider().read()
    assert r["window_5h_pct"] == 42 and r["weekly_pct"] == 64 and r["source"] == "file"
    assert r["age_s"] is not None and r["age_s"] < 5 and not is_stale(r)
    assert main(["set", "--5h", "150"]) == 2 and main(["set"]) == 2


def test_old_reading_is_stale_and_missing_is_none(home):
    write_reading(10, 20, now=1000.0)
    r = ClaudeProvider(now=1000.0 + 3600).read()
    assert r["age_s"] == 3600 and is_stale(r)
    f = home / "nope.json"
    miss = ClaudeProvider(path=f).read()
    assert miss["window_5h_pct"] is None and miss["weekly_pct"] is None and "error" in miss and is_stale(miss)


def test_env_file_override(home, monkeypatch):
    f = home / "custom.json"
    monkeypatch.setenv("SWARMTIER_QUOTA_FILE", str(f))
    write_reading(5, 6)
    assert f.exists() and ClaudeProvider().read()["weekly_pct"] == 6


def test_pace_and_effort():
    now = 1_000_000.0
    p = pace(80, now + 3.5 * 86400, now=now)  # 3.5 of 7 days left -> 50% elapsed
    assert p["verdict"] == "above" and p["ratio"] == 1.6
    assert pace(50, now + 3.5 * 86400, now=now)["verdict"] == "on"
    assert pace(10, now + 3.5 * 86400, now=now)["verdict"] == "below"
    assert pace(None, now, now=now)["verdict"] == "unknown"
    assert check_effort("claude-haiku-5-5", "xhigh")[0]
    assert not check_effort("claude-sonnet-5-5", "turbo")[0]
    assert not check_effort("mystery-model", "low")[0]
