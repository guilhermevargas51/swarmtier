# -*- coding: utf-8 -*-
"""Delegation ledger hook: records every subagent dispatch, wait and failure, so the record stops
depending on anybody remembering to narrate.

Modes (first CLI argument), and the events they are wired to in hooks.json:
  start     PreToolUse   (Agent|Task)                     -> created, assigned, started
  end       PostToolUse  (Agent|Task)                     -> completed (foreground) / link only (background)
  failure   PostToolUseFailure (Agent|Task)               -> failed
  sub-stop  SubagentStop                                  -> completed (resolves the background link)
  wait      PreToolUse (AskUserQuestion|ExitPlanMode) and Notification(permission_prompt)
                                                          -> blocked (the user's turn)
  answered  PostToolUse (AskUserQuestion|ExitPlanMode)    -> closes the open waits of the session

Payload fields used (documented hook payloads):
  * PostToolUse of Agent in background: tool_response.status == "async_launched" with agentId,
    resolvedModel. Foreground responses carry resolvedModel too.
  * SubagentStop: agent_id, agent_type. It also fires for INTERNAL agents; an agent_id with no known
    link is ignored silently (no phantom task).

The hook is silent by design on every path and always exits 0: a record is important, but never
more important than the work itself. Without session_id (manual test) it only announces what it
would record.

Storage: the ledger itself lives in core.ledger; the background agent_id -> task_id links live in
<data_dir>/delegation-links.json.
"""
import hashlib
import json
import sys

from _common import get_data_dir, read_event, read_json, run_safely, write_json

TERMINAL = ("completed", "failed", "cancelled")
MAX_LINKS = 500


# --- thin adapters over core.ledger (record / read) ---------------------------------

def _ledger():
    import core.ledger as ledger
    return ledger


def _record(ledger, task_id, event, role=None, model=None, note=None, **extra):
    return ledger.record(task_id, event, role=role, model=model, note=note, **extra)


def _events(ledger):
    return list(ledger.read() or [])


def _field(entry, *names):
    for n in names:
        if n in entry:
            return entry[n]
    return None


def _is_terminal(ledger, task_id):
    last = None
    for e in _events(ledger):
        if str(_field(e, "task_id")) == str(task_id):
            last = e.get("event")
    return last in TERMINAL


# --- helpers ---------------------------------------------------------------------------------

def _task_id(ev):
    """Correlate the start event with the end event (same tool_use_id)."""
    tid = ev.get("tool_use_id") or ev.get("toolUseId")
    if tid:
        return str(tid)
    raw = json.dumps(ev.get("tool_input") or {}, sort_keys=True, ensure_ascii=False)
    return "h-" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def _description(ev):
    ti = ev.get("tool_input") or {}
    return str(ti.get("description") or ti.get("prompt") or "")[:120]


def _role(ev):
    ti = ev.get("tool_input") or {}
    return ti.get("subagent_type") or ti.get("name") or None


def _links_file():
    d = get_data_dir()
    return (d / "delegation-links.json") if d else None


def _load_links():
    f = _links_file()
    return read_json(f, {}) if f else {}


def _save_links(links):
    f = _links_file()
    if f:
        if len(links) > MAX_LINKS:
            for k in list(links)[:-MAX_LINKS]:
                links.pop(k, None)
        write_json(f, links)


# --- modes -----------------------------------------------------------------------------------

def handle(mode, ev):
    ledger = _ledger()
    session = ev.get("session_id")
    ti = ev.get("tool_input") or {}
    resp = ev.get("tool_response") or {}
    tid = _task_id(ev)
    role = _role(ev)

    if mode == "start":
        # Claude Code runs Agent in the background BY DEFAULT: a missing parameter means background;
        # only an explicit run_in_background=False is foreground.
        background = bool(ti.get("run_in_background", True))
        model = ti.get("model")
        extra = dict(source="hook", session=session, name=ti.get("name"), background=background,
                     effort=ti.get("effort"))
        _record(ledger, tid, "created", role=role, model=model, note=_description(ev), **extra)
        _record(ledger, tid, "assigned", role=role, model=model, **extra)
        _record(ledger, tid, "started", role=role, model=model, **extra)

    elif mode == "end":
        is_async = isinstance(resp, dict) and resp.get("status") == "async_launched"
        real_model = resp.get("resolvedModel") if isinstance(resp, dict) else None
        if is_async:
            agent_id = resp.get("agentId")
            if agent_id:
                links = _load_links()
                links[str(agent_id)] = tid
                _save_links(links)
                return  # SubagentStop records the real end
        _record(ledger, tid, "completed", role=role, model=real_model, session=session)

    elif mode == "failure":
        r = resp if isinstance(resp, dict) else {}
        err = str(r.get("stderr") or r.get("error") or ev.get("error")
                  or (resp if isinstance(resp, str) else "") or "")[:200]
        _record(ledger, tid, "failed", role=role, note=err, session=session)

    elif mode == "sub-stop":
        agent_id = ev.get("agent_id")
        task = _load_links().get(str(agent_id)) if agent_id else None
        # No known link: probably an internal agent (prompt suggestion, side question). Ignore.
        if task and not _is_terminal(ledger, task):
            _record(ledger, task, "completed", role=ev.get("agent_type"), session=session,
                    agent_id=agent_id)

    elif mode == "wait":
        reason = ev.get("notification_type") or ev.get("tool_name") or "wait"
        questions = ti.get("questions") if isinstance(ti.get("questions"), list) else []
        if questions and isinstance(questions[0], dict):
            text = str(questions[0].get("question") or "")[:200]
        else:
            text = str(ev.get("message") or "")[:200]
        wid = "wait:%s:%s" % (str(session)[:8], tid)
        extra = dict(source="hook", session=session, name=reason)
        for event in ("created", "assigned", "started"):
            _record(ledger, wid, event, role="user-input", note=text if event == "created" else None, **extra)
        _record(ledger, wid, "blocked", role="user-input", note=text, **extra)

    elif mode == "answered":
        open_waits = {}
        prefix = "wait:%s:" % str(session)[:8]
        for e in _events(ledger):
            t = str(_field(e, "task_id") or "")
            if t.startswith(prefix):
                open_waits[t] = e.get("event") not in TERMINAL
        for wid, is_open in open_waits.items():
            if is_open:
                _record(ledger, wid, "started", role="user-input", session=session)
                _record(ledger, wid, "completed", role="user-input", session=session)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "start"
    ev = read_event()
    if ev is None:
        return
    if not ev.get("session_id"):
        print("[manual test] ledger would record: %s %s" % (mode, _task_id(ev)))
        return
    try:
        handle(mode, ev)
    except Exception:
        return  # a failing record must not break the workflow


if __name__ == "__main__":
    run_safely(main)
