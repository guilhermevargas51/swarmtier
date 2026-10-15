import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import learning, lesson_inject  # noqa: E402


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SWARMTIER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "proj"))
    (tmp_path / "proj").mkdir()
    return tmp_path


def test_record_and_search_failure_only():
    learning.record("python-inline", "claude", ok=False,
                    note="python -c inline breaks with nested quotes; write a file instead")
    learning.record("edit-big-json", "claude", ok=True, hits=5, total=5, note="json written and validated")
    found = learning.search("running python inline here")
    assert [r["task"] for r in found] == ["python-inline"]
    assert learning.search("edit big json file") == []  # success is never injected
    assert learning.search("schedule a dentist appointment") == []  # control: new situation


def test_failure_requires_note():
    with pytest.raises(ValueError):
        learning.record("t", "who", ok=False)


def test_top_for_prompt_and_archive():
    rec = learning.record("deploy-script", "sonnet", ok=False,
                          note="deploy script needs the env var exported first")
    assert "deploy-script" in learning.top_for_prompt("fix the deploy script")
    learning.archive(learning.lesson_id(rec))
    assert learning.top_for_prompt("fix the deploy script") == ""
    learning.unarchive(learning.lesson_id(rec))
    assert learning.top_for_prompt("fix the deploy script") != ""


def test_cli_register_alias_and_flags(capsys):
    assert learning._cli(["register", "--task", "build-thing", "--skill", "dispatch-by-cost", "--failed",
                          "--note", "build fails without cache"]) == 0
    assert learning._cli(["record", "--task", "x", "--who", "m"]) == 0
    assert learning._cli(["record", "--task", "x", "--failed"]) == 2  # failure without note
    rows = learning.load()
    assert rows[0]["skill"] == "dispatch-by-cost" and rows[0]["ok"] is False
    capsys.readouterr()
    assert learning._cli(["search", "build", "fails"]) == 0
    assert "build-thing" in capsys.readouterr().out


def test_ranking_prefers_rate_then_cost():
    learning.record("classify", "a", hits=9, total=10, cost=5)
    learning.record("classify", "b", hits=9, total=10, cost=1)
    assert [r["who"] for r in learning.ranking("classify")] == ["b", "a"]


def test_lookup_logs_even_when_empty_and_guard():
    text, rec = lesson_inject.lookup("a brand new situation")
    assert text == "" and rec["status"] == "executed"
    with pytest.raises(lesson_inject.LookupInvalid):
        lesson_inject.validate_lookup({"status": "injected", "lessons": []})
    with pytest.raises(lesson_inject.LookupInvalid):
        lesson_inject.validate_lookup({"status": "skipped", "lessons": []})


def test_lookup_injects_and_brakes_third_identical_attempt():
    learning.record("fix-parser", "claude", ok=False, note="parser.py fails on empty input; guard first")
    s = "fix parser.py for empty input"
    t1, r1 = lesson_inject.lookup(s)
    t2, r2 = lesson_inject.lookup("again: fix parser.py for empty input")
    t3, r3 = lesson_inject.lookup("rephrased: repair parser.py empty input handling")
    assert r1["status"] == r2["status"] == "injected" and "fix-parser" in t1
    assert r3["status"] == "blocked" and t3 == "" and r3["attempt"] == 3
    assert lesson_inject.unlooked_dispatches([s])


def test_work_anchor_ambiguous_without_artifact():
    assert lesson_inject.work_anchor("do something nice")["state"] == "ambiguous"
    assert lesson_inject.work_anchor("see src/a.py")["state"] == "resolved"


def test_register_defaults_to_lesson(tmp_path, monkeypatch):
    """'register' is what the skills use to record a lesson: it must come back in search."""
    import subprocess, sys, os
    env = dict(os.environ, SWARMTIER_HOME=str(tmp_path))
    run = lambda *args: subprocess.run([sys.executable, "-m", "core.learning", *args],
                                      env=env, capture_output=True, text=True)
    assert run("register", "--task", "flaky quoting", "--note", "use a temp file").returncode == 0
    assert "use a temp file" in run("search", "flaky", "quoting").stdout
    assert run("register", "--ok", "--task", "fine run", "--note", "worked").returncode == 0
    assert "worked" not in run("search", "fine", "run").stdout
