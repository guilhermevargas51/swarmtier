# -*- coding: utf-8 -*-
"""UserPromptSubmit hook: inject the relevant lessons BEFORE the task starts.

lesson-capture closes the "going" half of the loop (error -> written lesson). This hook closes
the "coming back" half (written lesson -> prompt, before the same error can happen again).

Why a hook and not `claude -p --append-system-prompt-file`: that flag only exists in
non-interactive mode, while most real work - and most repeated mistakes - happen in the
interactive session. A UserPromptSubmit hook reaches both. It also INJECTS and PROVES in the same
place: core.lesson_inject.lookup() logs every lookup - even an empty one - so "the hook was off"
is a detectable state instead of an assumption.

Guards:
  * no session_id (manual test) -> prints what it would inject, logs nothing;
  * prompts shorter than MIN_CHARS are conversation ("ok", "go on"), not tasks;
  * runtime-generated blocks are never looked up;
  * stays silent when nothing relevant is found.

Config (swarmtier.toml, optional):
    lessons_per_prompt = 3

Manual test (does not write):
    echo '{"prompt":"run python inline with a heredoc"}' | python hooks/lesson-inject.py
"""
import sys

from _common import SYSTEM_NOISE, emit, load_cfg, read_event, run_safely, setting

MIN_CHARS = 12


def main():
    ev = read_event()
    if not ev:
        return
    prompt = str(ev.get("prompt") or "")
    session_id = ev.get("session_id")
    if len(prompt.strip()) < MIN_CHARS or SYSTEM_NOISE.search(prompt):
        return

    try:
        limit = max(1, int(setting(load_cfg(), "lessons_per_prompt", 3)))
    except (TypeError, ValueError):
        limit = 3

    try:
        if session_id:
            # lookup() reads lessons_per_prompt from the config itself and logs the lookup.
            from core.lesson_inject import lookup
            bundle, _record = lookup(prompt, session_id=session_id)
        else:
            from core import learning
            bundle = learning.format_bundle(learning.search(prompt, limit=limit))
            sys.stderr.write("[manual test: no session_id, nothing was logged]\n")
    except Exception:
        return  # engine unavailable never breaks the session

    if bundle:
        emit("UserPromptSubmit", bundle)


if __name__ == "__main__":
    run_safely(main)
