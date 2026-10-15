# -*- coding: utf-8 -*-
"""Lesson capture: turn "something failed" into a lesson candidate, and nag at the end of the
session about the ones nobody turned into a lesson yet.

Recording a lesson takes judgement (what was learned, and why) and cannot be automated. DETECTING
that something failed, and REMINDING that it is still unrecorded, can - and that is where the chain
used to break.

Modes (first CLI argument):
  failure    PostToolUseFailure hook (matcher: Bash) - appends the failure to the candidates file.
  remind     Stop hook - tells the model which failures of today still have no lesson. Each item is
             reported once per session.
  processed  manual - marks today's candidates as processed (use --all for the whole backlog).

Expected noise is filtered out (a grep with no match, a probing `ls`, `--help`, a test suite that
exits non-zero by design): a hook that shouts at every command becomes a hook everyone ignores.

Candidates live in <data_dir>/lesson-candidates.jsonl. Lessons themselves are recorded with
core.learning (see the improve-skills skill).
"""
import json
import os
import re
import sys
import time
from datetime import date

from _common import (PLUGIN_ROOT, get_data_dir, jsonl_append, jsonl_read, now_iso,
                     read_event, read_json, run_safely, write_json)

CANDIDATES = "lesson-candidates.jsonl"
REMINDER_STATE = "lesson-reminder.json"

# An expected failure is not a lesson.
NOISE = re.compile(
    r"\bgrep\b(?!.*\|\s*(python|node))"          # grep without a match is a result, not an error
    r"|\bfind\b.*-name"
    r"|\bls\b\s|\bdir\b\s"
    r"|--help\b|-h\b|--version\b"
    r"|\btest -|\[ -[fdez]\b"
    r"|\bwhich\b|\bwhere\b"
    r"|\bhead\b|\btail\b|\bwc\b"
    r"|2>\s*/dev/null"
    r"|\|\|\s*(true|echo)"
    # robocopy-style tools use non-Unix exit codes: 0..7 are all SUCCESS.
    r"|\brobocopy\b"
    # A test suite reports its RESULT via exit code: 1 means "a case failed", which is its job.
    r"|--fixture\b",
    re.I,
)


def _candidates_file():
    d = get_data_dir()
    return (d / CANDIDATES) if d else None


def capture_failure():
    ev = read_event()
    if not ev:
        return
    tool_input = ev.get("tool_input") or {}
    # Filter on the FULL command and truncate only afterwards: truncating first can hide the keyword.
    full_command = str(tool_input.get("command") or "")
    if not full_command or NOISE.search(full_command):
        return
    resp = ev.get("tool_response") or {}
    if isinstance(resp, dict):
        err = str(resp.get("stderr") or resp.get("error") or resp.get("output") or "")
    else:
        err = str(resp)
    err = err or str(ev.get("error") or "")
    record = {
        "ts": now_iso(),
        "type": "command-failure",
        "command": full_command[:400],
        "error": re.sub(r"\s+", " ", err)[:300],
        "description": str(tool_input.get("description") or "")[:120],
        "processed": False,
    }
    if not ev.get("session_id"):
        print("[manual test] would capture: %s" % record["command"][:80])
        return
    path = _candidates_file()
    if path:
        jsonl_append(path, record)


def _key(r):
    return "failure:" + (r.get("description") or r.get("command") or "")[:58]


def _lessons_today():
    """How many lessons core.learning has for today. None when it cannot be told."""
    try:
        import core.learning as learning
        today = date.today().isoformat()
        return sum(1 for r in learning.load() if str(r.get("ts") or "").startswith(today))
    except Exception:
        return None


def remind():
    ev = read_event() or {}
    session_id = ev.get("session_id")
    path = _candidates_file()
    if not path or not path.exists():
        return
    data_dir = path.parent
    state_file = data_dir / REMINDER_STATE
    state = read_json(state_file, {}) if session_id else {}
    already = set(state.get(session_id, {}).get("reported", [])) if session_id else set()

    today = date.today().isoformat()
    pending = [r for r in jsonl_read(path)
               if not r.get("processed") and str(r.get("ts", "")).startswith(today)
               and _key(r) not in already]
    if not pending:
        return

    sample = " | ".join((r.get("description") or r.get("command") or "")[:58] for r in pending[:4])
    count = _lessons_today()
    tail = "" if count is None else " (%d lessons recorded today)" % count
    msg = (
        "LESSON ENGINE - %d failure(s) from today still have no lesson%s. Before ending the "
        "session, record what became learning with core.learning.record (the improve-skills skill "
        "explains how), then run `python \"%s\" processed`. Pending: %s"
        % (len(pending), tail, os.path.join(PLUGIN_ROOT, "hooks", "lesson-capture.py"), sample)
    )
    print(json.dumps({"systemMessage": msg}, ensure_ascii=False))

    if session_id:
        entry = state.setdefault(session_id, {})
        entry["reported"] = sorted(already | {_key(r) for r in pending})
        # keep the state file small: only the 20 most recent sessions
        if len(state) > 20:
            for k in list(state)[:-20]:
                state.pop(k, None)
        write_json(state_file, state)


def mark_processed():
    """Close today's queue (or everything with --all). Counts only what actually changes."""
    path = _candidates_file()
    if not path or not path.exists():
        print("  0 candidate(s) marked as processed.")
        return
    today = date.today().isoformat()
    everything = "--all" in sys.argv
    lines, changed = [], 0
    with open(str(path), encoding="utf-8") as f:
        for raw in f:
            if not raw.strip():
                continue
            try:
                r = json.loads(raw)
            except ValueError:
                lines.append(raw.rstrip("\n"))   # unreadable lines are kept, never silently dropped
                continue
            if everything or str(r.get("ts", "")).startswith(today):
                if not r.get("processed"):
                    changed += 1
                r["processed"] = True
            lines.append(json.dumps(r, ensure_ascii=False))
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    os.replace(tmp, str(path))
    print("  %d candidate(s) marked as processed." % changed)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "failure"
    if mode == "failure":
        run_safely(capture_failure)
    elif mode == "remind":
        run_safely(remind)
    elif mode == "processed":
        run_safely(mark_processed)
