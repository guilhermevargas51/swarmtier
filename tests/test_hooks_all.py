# -*- coding: utf-8 -*-
"""Hook tests: feed each hook a JSON event on stdin (subprocess) and check output / exit code / state.

Every run uses an isolated SWARMTIER_HOME so tests never touch real state.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks"


@pytest.fixture
def home(tmp_path):
    return tmp_path


def run(hook, event, home, args=(), env_extra=None, raw=None):
    env = dict(os.environ)
    env["SWARMTIER_HOME"] = str(home)
    env["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(env_extra or {})
    data = raw if raw is not None else json.dumps(event, ensure_ascii=False)
    return subprocess.run([sys.executable, str(HOOKS / hook), *args], input=data.encode("utf-8"),
                          capture_output=True, env=env, timeout=60)


def out(r):
    return r.stdout.decode("utf-8", "replace")


def err(r):
    return r.stderr.decode("utf-8", "replace")


def read_jsonl(path):
    if not Path(path).exists():
        return []
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


# ---------------------------------------------------------------- require-effort

def agent_event(**tool_input):
    return {"session_id": "s1", "tool_name": "Agent", "tool_input": tool_input}


def test_require_effort_blocks_without_effort(home):
    r = run("require-effort.py", agent_event(prompt="x", model="haiku"), home)
    assert r.returncode == 2
    assert "DISPATCH WITHOUT EFFORT" in err(r)


def test_require_effort_allows_with_effort(home):
    r = run("require-effort.py", agent_event(prompt="x", model="haiku", effort="low"), home)
    assert r.returncode == 0


def test_require_effort_refuses_max_on_sonnet_only(home):
    assert run("require-effort.py", agent_event(model="sonnet", effort="max"), home).returncode == 2
    assert run("require-effort.py", agent_event(model="haiku", effort="max"), home).returncode == 0


def test_require_effort_ignores_other_tools_and_bad_json(home):
    assert run("require-effort.py", {"tool_name": "Bash", "tool_input": {}}, home).returncode == 0
    assert run("require-effort.py", None, home, raw="not json").returncode == 0


def test_require_effort_exempt_agents(home):
    (home / "swarmtier.toml").write_text('exempt_agents = ["vision-reader"]\n', encoding="utf-8")
    ev = agent_event(subagent_type="vision-reader", prompt="x")
    assert run("require-effort.py", ev, home).returncode == 0
    ev = agent_event(subagent_type="other", prompt="x")
    assert run("require-effort.py", ev, home).returncode == 2


# ---------------------------------------------------------------- cold-cache

def test_cold_cache_warns_after_ttl(home):
    state = home / "cold-cache.json"
    old = time.time() - 90 * 60
    state.write_text(json.dumps({"sessions": {"s1": old}}), encoding="utf-8")
    r = run("cold-cache.py", {"session_id": "s1", "prompt": "hello again"}, home)
    assert r.returncode == 0
    payload = json.loads(out(r))
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert "COLD CACHE" in ctx and "compact" in ctx.lower()


def test_cold_cache_silent_when_recent_and_updates_state(home):
    r1 = run("cold-cache.py", {"session_id": "s1", "prompt": "first prompt"}, home)
    r2 = run("cold-cache.py", {"session_id": "s1", "prompt": "second prompt"}, home)
    assert out(r1) == "" and out(r2) == ""
    assert "s1" in json.loads((home / "cold-cache.json").read_text(encoding="utf-8"))["sessions"]


def test_cold_cache_ttl_is_configurable(home):
    (home / "swarmtier.toml").write_text("cache_ttl_minutes = 5\n", encoding="utf-8")
    (home / "cold-cache.json").write_text(
        json.dumps({"sessions": {"s1": time.time() - 10 * 60}}), encoding="utf-8")
    r = run("cold-cache.py", {"session_id": "s1", "prompt": "hello again"}, home)
    assert "COLD CACHE" in out(r)


def test_cold_cache_no_session_id_writes_nothing(home):
    r = run("cold-cache.py", {"prompt": "hello"}, home)
    assert r.returncode == 0
    assert not (home / "cold-cache.json").exists()


def test_cold_cache_watch_reminds_on_big_context_once(home, tmp_path):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps({"message": {"usage": {
        "input_tokens": 10, "cache_read_input_tokens": 180000, "cache_creation_input_tokens": 0}}}) + "\n",
        encoding="utf-8")
    ev = {"session_id": "s1", "transcript_path": str(transcript)}
    r1 = run("cold-cache-watch.py", ev, home)
    assert "systemMessage" in json.loads(out(r1))
    assert "180k" in json.loads(out(r1))["systemMessage"]
    r2 = run("cold-cache-watch.py", ev, home)
    assert out(r2).strip() == ""          # reminded once within the TTL


def test_cold_cache_watch_silent_on_small_context(home, tmp_path):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps({"message": {"usage": {"input_tokens": 500}}}) + "\n", encoding="utf-8")
    r = run("cold-cache-watch.py", {"session_id": "s1", "transcript_path": str(transcript)}, home)
    assert out(r).strip() == ""


# ---------------------------------------------------------------- user-correction

@pytest.mark.parametrize("prompt", [
    "no, I said use the other file", "that's wrong", "you forgot the second step",
    "isso está errado", "não, eu disse para usar o outro", "já te disse isso",
])
def test_user_correction_captures(home, prompt):
    r = run("user-correction.py", {"session_id": "s1", "prompt": prompt}, home)
    assert r.returncode == 0
    ctx = json.loads(out(r))["hookSpecificOutput"]["additionalContext"]
    assert "LESSON ENGINE" in ctx
    rows = read_jsonl(home / "lesson-candidates.jsonl")
    assert rows and rows[-1]["type"] == "user-correction" and rows[-1]["processed"] is False


def test_user_correction_no_session_id_does_not_write(home):
    r = run("user-correction.py", {"prompt": "that's wrong"}, home)
    assert r.returncode == 0
    assert "would capture: YES" in out(r)
    assert not (home / "lesson-candidates.jsonl").exists()


def test_user_correction_ignores_normal_and_content_requests(home):
    for p in ("please add a login page", "write a unit test that rejects the wrong option"):
        r = run("user-correction.py", {"session_id": "s1", "prompt": p}, home)
        assert out(r).strip() == ""
    assert not (home / "lesson-candidates.jsonl").exists()


# ---------------------------------------------------------------- lesson-capture

def test_lesson_capture_failure_and_remind_once_per_session(home):
    ev = {"session_id": "s1", "tool_name": "Bash",
          "tool_input": {"command": "python build.py --target x", "description": "build"},
          "tool_response": {"stderr": "Traceback boom"}}
    run("lesson-capture.py", ev, home, args=["failure"])
    rows = read_jsonl(home / "lesson-candidates.jsonl")
    assert len(rows) == 1 and rows[0]["command"].startswith("python build.py")

    r = run("lesson-capture.py", {"session_id": "s1"}, home, args=["remind"])
    assert "still have no lesson" in json.loads(out(r))["systemMessage"]
    r = run("lesson-capture.py", {"session_id": "s1"}, home, args=["remind"])
    assert out(r).strip() == ""               # already reported in this session


def test_lesson_capture_filters_noise(home):
    ev = {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "grep foo file.txt"},
          "tool_response": {"stderr": ""}}
    run("lesson-capture.py", ev, home, args=["failure"])
    assert read_jsonl(home / "lesson-candidates.jsonl") == []


def test_lesson_capture_processed_closes_queue(home):
    ev = {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "make deploy"},
          "tool_response": {"stderr": "x"}}
    run("lesson-capture.py", ev, home, args=["failure"])
    r = run("lesson-capture.py", None, home, args=["processed"], raw="")
    assert "1 candidate(s)" in out(r)
    assert read_jsonl(home / "lesson-candidates.jsonl")[0]["processed"] is True
    r = run("lesson-capture.py", {"session_id": "s2"}, home, args=["remind"])
    assert out(r).strip() == ""


# ---------------------------------------------------------------- lesson-inject

def seed_lesson(home):
    sys.path.insert(0, str(ROOT))
    os.environ["SWARMTIER_HOME"] = str(home)
    from core import learning
    learning.record("deploy script heredoc", "executor", ok=False,
                    note="python inline with a heredoc broke quoting on deploy script; write a file instead")


def test_lesson_inject_injects_and_logs_with_session(home):
    seed_lesson(home)
    r = run("lesson-inject.py", {"session_id": "s1", "prompt": "run the deploy script with a python heredoc"}, home)
    assert r.returncode == 0
    ctx = json.loads(out(r))["hookSpecificOutput"]["additionalContext"]
    assert "heredoc" in ctx
    assert any(x for x in (home).glob("*lookup*")), "lookup must be logged on a real run"


def test_lesson_inject_no_session_does_not_log(home):
    seed_lesson(home)
    before = {p.name for p in home.glob("*lookup*")}
    r = run("lesson-inject.py", {"prompt": "run the deploy script with a python heredoc"}, home)
    assert r.returncode == 0
    assert {p.name for p in home.glob("*lookup*")} == before


def test_lesson_inject_silent_on_short_prompt_and_runtime_noise(home):
    for p in ("ok", "<system-reminder> something long enough here </system-reminder>"):
        r = run("lesson-inject.py", {"session_id": "s1", "prompt": p}, home)
        assert out(r).strip() == ""


# ---------------------------------------------------------------- delegation-ledger

def led(home):
    return read_jsonl(home / "ledger.jsonl")


def test_ledger_foreground_lifecycle(home):
    base = {"session_id": "s1", "tool_name": "Agent", "tool_use_id": "tu1",
            "tool_input": {"description": "scan", "subagent_type": "triage", "model": "haiku",
                           "effort": "low", "run_in_background": False}}
    run("delegation-ledger.py", base, home, args=["start"])
    run("delegation-ledger.py", dict(base, tool_response={"resolvedModel": "haiku-x"}), home, args=["end"])
    events = [e["event"] for e in led(home) if e["task_id"] == "tu1"]
    assert events == ["created", "assigned", "started", "completed"]


def test_ledger_background_closes_on_subagent_stop_and_ignores_unknown(home):
    base = {"session_id": "s1", "tool_name": "Agent", "tool_use_id": "tu2",
            "tool_input": {"description": "scan", "subagent_type": "triage"}}
    run("delegation-ledger.py", base, home, args=["start"])
    run("delegation-ledger.py", dict(base, tool_response={"status": "async_launched", "agentId": "a1"}),
        home, args=["end"])
    assert [e["event"] for e in led(home)][-1] == "started"
    run("delegation-ledger.py", {"session_id": "s1", "agent_id": "ghost"}, home, args=["sub-stop"])
    assert [e["event"] for e in led(home)][-1] == "started"          # unknown agent: no phantom task
    run("delegation-ledger.py", {"session_id": "s1", "agent_id": "a1", "agent_type": "triage"}, home,
        args=["sub-stop"])
    assert [e["event"] for e in led(home)][-1] == "completed"


def test_ledger_failure_and_wait(home):
    ev = {"session_id": "s1", "tool_name": "Agent", "tool_use_id": "tu3", "tool_input": {"description": "x"},
          "error": "boom"}
    run("delegation-ledger.py", ev, home, args=["failure"])
    assert led(home)[-1]["event"] == "failed"
    w = {"session_id": "s1", "tool_name": "AskUserQuestion", "tool_use_id": "q1",
         "tool_input": {"questions": [{"question": "Which one?"}]}}
    run("delegation-ledger.py", w, home, args=["wait"])
    assert led(home)[-1]["event"] == "blocked"
    run("delegation-ledger.py", w, home, args=["answered"])
    assert led(home)[-1]["event"] == "completed"


def test_ledger_no_session_id_writes_nothing(home):
    r = run("delegation-ledger.py", {"tool_name": "Agent", "tool_input": {"description": "x"}}, home,
            args=["start"])
    assert r.returncode == 0 and "ledger would record" in out(r)
    assert led(home) == []


# ---------------------------------------------------------------- hooks.json + hygiene

def test_hooks_json_wires_every_hook_file():
    cfg = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))
    blob = json.dumps(cfg)
    for name in ("require-effort", "cold-cache", "cold-cache-watch", "lesson-capture",
                 "lesson-inject", "user-correction", "delegation-ledger"):
        assert "${CLAUDE_PLUGIN_ROOT}/hooks/%s.py" % name in blob
        assert (HOOKS / (name + ".py")).exists()
    assert set(cfg["hooks"]) >= {"PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop", "SubagentStop"}


def test_hooks_exit_zero_on_garbage_input(home):
    for name, args in (("cold-cache.py", ()), ("cold-cache-watch.py", ()), ("lesson-inject.py", ()),
                       ("user-correction.py", ()), ("delegation-ledger.py", ("start",)),
                       ("lesson-capture.py", ("failure",)), ("lesson-capture.py", ("remind",))):
        assert run(name, None, home, args=args, raw="{{{ not json").returncode == 0
