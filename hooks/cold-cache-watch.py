# -*- coding: utf-8 -*-
"""Stop hook: a "leaving soon?" reminder at the end of a turn, BEFORE the cache goes cold.

History: an earlier version of this tool ran a background watcher that pinged the user shortly
before the cache expired. A background process can only help if it has an out-of-band channel
(push message, desktop notification) - which a portable plugin does not have. So the watcher was
dropped, and the useful part became this: at the end of a turn, when the conversation is large,
the user sees a one-line reminder of what to do if they are about to step away.

Behaviour:
  * records the end-of-turn timestamp and the context size (read from the last `usage` block
    of the transcript: input + cache read + cache creation tokens);
  * if the context is at least `min_tokens` and no reminder was shown for this session within
    the last TTL minutes, prints a short user-visible `systemMessage`;
  * otherwise stays silent. It never blocks the stop.

Config (swarmtier.toml, optional):
    cache_ttl_minutes = 60
    cache_watch_min_tokens = 100000   # below this, a cold return is cheap enough to ignore

Manual test (does not write):
    echo '{"transcript_path":"/path/to/t.jsonl"}' | python hooks/cold-cache-watch.py
"""
import json
import sys
import time

from _common import get_data_dir, load_cfg, read_event, read_json, run_safely, setting, write_json

USAGE_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
TAIL_BYTES = 400000
KEEP_SESSIONS = 20


def context_tokens(transcript_path):
    """Context size at the last assistant response, from the transcript tail. 0 if unknown."""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - TAIL_BYTES))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except Exception:
        return 0
    for line in reversed(lines):
        if '"usage"' not in line:
            continue
        try:
            usage = (json.loads(line).get("message") or {}).get("usage") or {}
        except ValueError:
            continue
        total = sum(int(usage.get(k) or 0) for k in USAGE_KEYS)
        if total:
            return total
    return 0


def main():
    ev = read_event()
    if not ev:
        return
    cfg = load_cfg()
    try:
        ttl = float(setting(cfg, "cache_ttl_minutes", 60))
        min_tokens = int(setting(cfg, "cache_watch_min_tokens", 100000))
    except (TypeError, ValueError):
        ttl, min_tokens = 60.0, 100000

    session_id = ev.get("session_id")
    tokens = context_tokens(str(ev.get("transcript_path") or ""))
    now = time.time()

    data = get_data_dir()
    state_file = (data / "cold-cache-watch.json") if data else None
    state = read_json(state_file, {}) if state_file else {}
    sessions = state.setdefault("sessions", {})
    last = sessions.get(session_id, {}) if session_id else {}

    remind = tokens >= min_tokens and (now - float(last.get("reminded") or 0)) >= ttl * 60
    if remind:
        k = tokens // 1000
        msg = (
            "Cache note: this conversation is about %dk tokens. If you are stepping away for more than "
            "~%d min, the prompt cache will expire and the next message pays to rewrite all of it. "
            "Leaving? Say so (the state gets saved) and run /compact first - or /clear if the work is "
            "finished. Coming back soon? Send the next request before the cache expires." % (k, int(ttl))
        )
        print(json.dumps({"systemMessage": msg}, ensure_ascii=False))

    if session_id:
        entry = {"ended": now, "tokens": tokens, "reminded": last.get("reminded", 0)}
        if remind:
            entry["reminded"] = now
        sessions[session_id] = entry
        if len(sessions) > KEEP_SESSIONS:
            for k2 in sorted(sessions, key=lambda k2: sessions[k2].get("ended", 0))[:-KEEP_SESSIONS]:
                sessions.pop(k2, None)
        if state_file:
            write_json(state_file, state)
    else:
        sys.stderr.write("[manual test: no session_id, nothing was written]\n")


if __name__ == "__main__":
    run_safely(main)
