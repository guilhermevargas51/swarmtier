# -*- coding: utf-8 -*-
"""UserPromptSubmit hook: capture the most valuable learning signal there is - the user correcting you.

The most expensive mistake does not fail any command. It slips through, reaches the user, and the
user notices it while reading the result: zero commands failed, zero candidates captured. The
trigger for learning therefore cannot be the model's memory; it has to be the user's message.

What it does: if the prompt carries correction language ("no, I said...", "that's wrong", "you
forgot", "errado", "já te disse"...), it appends a lesson candidate to the shared candidates file
and injects a three-step protocol reminder before the model starts answering:
  1. verify against the SOURCE, never against memory;
  2. look for the same error elsewhere - content errors come in families;
  3. record the lesson as soon as the root cause is clear, without waiting to be asked.

Short messages without correction language pass through untouched: a hook that shouts all the
time is a hook that gets ignored.

Guard: events from real sessions always carry `session_id`; a manual `echo | python` test does
not. Without it the hook only prints what it WOULD do and writes nothing, so tests never
contaminate the real queue.

Manual test (does not write):
    echo '{"prompt":"that is wrong"}' | python hooks/user-correction.py
"""
import re
import sys

from _common import emit, get_data_dir, jsonl_append, now_iso, read_event, run_safely

# English + Brazilian Portuguese correction language.
CORRECTION = re.compile(
    r"\b("
    # English
    r"that'?s (wrong|incorrect|not (right|correct|true))|that is (wrong|incorrect|not (right|correct|true))"
    r"|(this|it) (is|was) (wrong|incorrect)|wrong|incorrect|you (got|have) (it|that) wrong"
    r"|no,? i (said|meant|asked)|i (already )?(told|said)( you)?|i just (told|said)"
    r"|not what i (asked|said|meant|wanted)|you (forgot|missed|ignored)|you (made|made that) up"
    r"|you (hallucinated|invented|misread)|that'?s not (it|how)|doesn'?t match|try again|redo (it|this|that)"
    # Portuguese (Brazil)
    r"|errad[oa]s?|incorret[oa]s?|n[aã]o [eé] assim|n[aã]o est[aá] certo|n[aã]o,? eu (disse|falei|pedi)"
    r"|j[aá] (te )?(disse|falei)|voc[eê] (esqueceu|errou|inventou|ignorou)|inventou|alucinou"
    r"|n[aã]o era isso|n[aã]o bate|corrija|corrige isso|refaz|refa[cç]a"
    r")\b", re.I)

# "wrong" inside a content request is not a correction aimed at the assistant.
# e.g.: "write a unit test that rejects the wrong option".
# Message LENGTH is not a usable criterion (short requests and long corrections both exist);
# what separates them is a BUILD verb together with content vocabulary - that is an order, not a scolding.
CONTENT = re.compile(
    r"\b(wrong (answer|option|statement|choice)|incorrect (answer|option|statement|choice)"
    r"|distractor|false statement)\b", re.I)
BUILD = re.compile(
    r"\b(write|create|make|generate|draft|add|include|build|prepare"
    r"|mont[ae]|cri[ae]|ger[ae]|fa[cç]a|faz|escrev[ae]|adicion[ae]|inclu[ai]|elabor[ae]|prepar[ae])\b", re.I)

MAX_PROMPT = 2000


def is_correction(text):
    return bool(text and CORRECTION.search(text) and not (CONTENT.search(text) and BUILD.search(text)))


PROTOCOL = (
    "LESSON ENGINE - the user pointed out an error; it was recorded as a lesson candidate. "
    "Mandatory protocol before answering: "
    "(1) VERIFY AGAINST THE SOURCE (the file, the spec, the docs), never against memory or against "
    "what an earlier note says about its own source; "
    "(2) LOOK FOR THE SAME ERROR ELSEWHERE, because content errors come in families, not alone; "
    "(3) RECORD the lesson with core.learning.record as soon as the root cause is clear, WITHOUT waiting "
    "to be asked."
)


def main():
    ev = read_event()
    if not ev:
        return
    text = str(ev.get("prompt") or "").strip()

    if not ev.get("session_id"):
        print("[manual test] would capture: %s" % ("YES" if is_correction(text) else "no"))
        return

    if not text or len(text) > MAX_PROMPT or not is_correction(text):
        return

    data = get_data_dir()
    if data:
        jsonl_append(data / "lesson-candidates.jsonl", {
            "ts": now_iso(),
            "type": "user-correction",
            "command": "",
            "description": text[:400],
            "error": "The user pointed out an error: something wrong passed through the assistant "
                     "and reached them. More valuable than a failed command.",
            "processed": False,
        })
    emit("UserPromptSubmit", PROTOCOL)


if __name__ == "__main__":
    run_safely(main)
