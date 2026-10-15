# -*- coding: utf-8 -*-
"""UserPromptSubmit hook: warn when the session comes back from a break longer than the cache TTL.

Why: the prompt cache expires after a period of inactivity (about 60 minutes). The next
message - any message, even a one-word "ok" - then pays to rewrite the WHOLE conversation
for the model, and that bill grows with the conversation size. Idle gaps were the single
largest line of the usage panel (see docs/cost-map.md for how these proportions were measured).

What it does: measures the gap since the previous prompt of the same session and, when it
exceeds the TTL, injects a short warning with two rules:
  1. deliver real work in this turn (do not chain mechanical steps, or the rewrite is paid twice);
  2. compact BEFORE leaving next time - compacting after coming back does not refund what was paid.

What it deliberately does NOT do: invent a money figure. A hook cannot see the context size,
so any cost estimate here would be a guess dressed up as a measurement. It reports minutes
and how many cold returns happened today.

Guards:
  * no session_id (manual test) -> prints what it would do, writes nothing;
  * runtime-generated blocks (<system-reminder>, task notifications) are not the user coming back;
  * silent unless there is something to say - an empty block on every prompt is context pollution.

Config (swarmtier.toml, optional):
    cache_ttl_minutes = 60

Manual test (does not write):
    echo '{"prompt":"hello again"}' | python hooks/cold-cache.py
"""
import sys
import time

from _common import (SYSTEM_NOISE, emit, get_data_dir, load_cfg, read_event,
                     read_json, run_safely, setting, write_json)

MIN_CHARS = 2          # below this it is not a prompt worth measuring
KEEP_SESSIONS = 20
KEEP_DAYS = 30


def main():
    ev = read_event()
    if not ev:
        return
    prompt = str(ev.get("prompt") or "")
    session_id = ev.get("session_id")
    if len(prompt.strip()) < MIN_CHARS or SYSTEM_NOISE.search(prompt):
        return

    cfg = load_cfg()
    try:
        ttl = float(setting(cfg, "cache_ttl_minutes", 60))
    except (TypeError, ValueError):
        ttl = 60.0

    data = get_data_dir()
    state_file = (data / "cold-cache.json") if data else None
    state = read_json(state_file, {}) if state_file else {}
    sessions = state.setdefault("sessions", {})
    days = state.setdefault("days", {})

    now = time.time()
    today = time.strftime("%Y-%m-%d")
    previous = sessions.get(session_id) if session_id else None
    minutes = int((now - previous) / 60) if previous else 0

    warning = None
    if previous and minutes >= ttl:
        day = days.setdefault(today, {"returns": 0, "minutes": 0})
        day["returns"] += 1
        day["minutes"] += minutes
        hours, rest = divmod(minutes, 60)
        idle = "%dh%02dmin" % (hours, rest) if hours else "%dmin" % minutes
        warning = (
            "COLD CACHE - the session sat idle for %s (cache TTL: %d min), so THIS turn "
            "rewrote the whole context for the model. That is cold return number %d today.\n"
            "- Do not chain mechanical steps now: deliver the real work of this turn before "
            "another pause, otherwise the rewrite is paid twice.\n"
            "- If the user is about to leave again: checkpoint, then tell them to compact "
            "BEFORE leaving. Compacting after coming back does not refund what was already "
            "paid, and the rewrite price grows with the conversation size."
            % (idle, int(ttl), day["returns"])
        )

    if session_id:
        sessions[session_id] = now
        cutoff = time.strftime("%Y-%m-%d", time.localtime(now - KEEP_DAYS * 86400))
        for d in [d for d in days if d < cutoff]:
            days.pop(d, None)
        if len(sessions) > KEEP_SESSIONS:
            for k in sorted(sessions, key=lambda k: sessions[k])[:-KEEP_SESSIONS]:
                sessions.pop(k, None)
        if state_file:
            write_json(state_file, state)
    else:
        sys.stderr.write("[manual test: no session_id, nothing was written]\n")

    if warning:
        emit("UserPromptSubmit", warning)


if __name__ == "__main__":
    run_safely(main)
