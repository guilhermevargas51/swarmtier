"""Lesson injection: the lesson reaches the prompt BEFORE the task, not after the error.

A learning log that is only written and never read repeats the same mistakes. This
module is the arrow that goes back: given what the agent is about to do, it looks up
failure lessons, builds a compact bundle for the prompt, and logs every lookup.

Central assertion: "a task dispatched without a lesson lookup is a system error, not
forgetfulness." So a lookup is logged even when it finds nothing (``executed`` with an
empty list). That is what separates "did not look" from "looked, nothing there".

Negative guard: ``injected`` requires a non-empty lesson list. Recording "injected"
with nothing injected would be the system claiming something it did not do.

Retry brake: the same piece of work (identified by an ANCHOR such as a file path or a
ticket id, never by the wording of the prompt) is blocked on its 3rd attempt inside a
time window - the lesson was already delivered twice and did not stick.

Public API:
    lookup(situation, session_id=None, ...) -> (bundle_text, record)
    validate_lookup(record)                  raises LookupInvalid
    work_anchor(text)                        -> {"work_id", "state", "anchors"}
    unlooked_dispatches(known)               raises DispatchWithoutLookup

CLI:
    python -m core.lesson_inject "text about the task"   show what would be injected
    python -m core.lesson_inject --audit                 lookup counts by status
"""
from __future__ import annotations

import hashlib
import re
import sys
from datetime import datetime

from core import learning
from core.config import data_dir, jsonl_append, jsonl_read, load_config

STATUSES = ("executed", "injected", "skipped", "blocked")
#   executed  lookup ran; the list may be empty (a new situation) - legitimate.
#   injected  lookup ran AND returned lessons that were attached to the context.
#   skipped   lookup deliberately skipped, with a stated reason.
#   blocked   same work, N-th identical attempt: lessons were already delivered and did not stick.


class LookupInvalid(AssertionError):
    """A lookup record that claims more than it did."""


class DispatchWithoutLookup(AssertionError):
    """A dispatch happened that the lookup log does not know about."""


def lookups_path():
    return data_dir() / "lookups.jsonl"


# --------------------------------------------------------------------------
# Work identity (embedded, minimal)
# --------------------------------------------------------------------------
# The original system used a separate module that classified asks into work types
# and extracted a typed anchor. Most of it depended on domain-specific work anchors.
# What is kept is the idea that matters: identity comes from an ARTIFACT, not from prose,
# because a key built from the text of whoever is being measured can be dodged by simply
# rephrasing. Two generic anchors are recognised: file paths and ticket-like ids.
_PATH_RE = re.compile(r"[\w./\\-]{2,}\.[A-Za-z][A-Za-z0-9]{1,5}\b")
_TICKET_RE = re.compile(r"\b[A-Z]{2,6}-\d{1,5}\b|#\d{1,6}\b")


def work_anchor(text: str) -> dict:
    """Return ``{"work_id", "state", "anchors"}``.

    ``state`` is ``resolved`` when an anchor exists, else ``ambiguous`` (no counter is
    created or inherited; no model is asked to guess whether it is a retry).
    """
    text = text or ""
    anchors = sorted({a.replace("\\", "/").lower() for a in _PATH_RE.findall(text)}
                     | {a.lower() for a in _TICKET_RE.findall(text)})
    anchors = [a for a in anchors if not re.fullmatch(r"\d+\.\d+", a)]  # drop bare versions like 3.14
    if not anchors:
        return {"work_id": None, "state": "ambiguous", "anchors": []}
    work_id = hashlib.sha256("|".join(anchors).encode("utf-8")).hexdigest()[:12]
    return {"work_id": work_id, "state": "resolved", "anchors": anchors}


# --------------------------------------------------------------------------
# Validation guard
# --------------------------------------------------------------------------
def validate_lookup(record: dict) -> bool:
    """Runs on EVERY write, not only in tests."""
    st = record.get("status")
    if st not in STATUSES:
        raise LookupInvalid("unknown status %r (valid: %s)" % (st, ", ".join(STATUSES)))
    if st == "injected" and not record.get("lessons"):
        raise LookupInvalid('status "injected" with an empty lesson list; an empty list is "executed"')
    if st in ("skipped", "blocked") and not record.get("reason"):
        raise LookupInvalid('status "%s" needs a stated reason; skipping silently is the gap this closes' % st)
    return True


# --------------------------------------------------------------------------
# Retry brake
# --------------------------------------------------------------------------
def count_attempts(work_id, path=None, now=None, window_min=None) -> int:
    """Lookups for this work_id inside the recent window. No anchor -> 0 (no counter)."""
    if not work_id:
        return 0
    window_min = load_config()["learning"]["retry_window_min"] if window_min is None else window_min
    now = now or datetime.now()
    n = 0
    for rec in jsonl_read(path or lookups_path()):
        if rec.get("work_id") != work_id:
            continue
        try:
            ts = datetime.fromisoformat(rec.get("ts", ""))
        except ValueError:
            continue
        if (now - ts).total_seconds() <= window_min * 60:
            n += 1
    return n


# --------------------------------------------------------------------------
# The lookup
# --------------------------------------------------------------------------
def lookup(situation: str, session_id=None, lessons_file=None, log_file=None, now=None,
           skip_reason=None):
    """Search lessons for ``situation``, log the lookup, return ``(bundle_text, record)``.

    ``bundle_text`` is "" when nothing is injected (new situation, skipped or blocked).
    """
    cfg = load_config()["learning"]
    log = log_file or lookups_path()
    ident = work_anchor(situation)
    attempts = count_attempts(ident["work_id"], path=log, now=now)

    reason = None
    lessons: list = []
    if skip_reason:
        status, reason = "skipped", skip_reason
    else:
        lessons = learning.search(situation, path=lessons_file)
        if attempts >= cfg["retry_limit"]:
            status = "blocked"
            reason = ("same work, attempt %d inside %d min: the lessons were already delivered and did "
                      "not stick. Change approach or bring new evidence." % (attempts + 1, cfg["retry_window_min"]))
        else:
            status = "injected" if lessons else "executed"

    record = {
        "ts": (now or datetime.now()).isoformat(timespec="seconds"),
        "status": status,
        "situation": (situation or "")[:200],
        "lessons": [learning.lesson_id(x) for x in lessons],
        "work_id": ident["work_id"],
        "anchors": ident["anchors"],
        "identity_state": ident["state"],
        "attempt": attempts + 1,
    }
    if reason:
        record["reason"] = reason
    if session_id:
        record["session_id"] = session_id
    validate_lookup(record)  # the guard runs BEFORE writing
    jsonl_append(log, record)
    text = learning.format_bundle(lessons) if status == "injected" else ""
    return text, record


def read_lookups(path=None) -> list:
    return jsonl_read(path or lookups_path())


def unlooked_dispatches(known: list, path=None) -> bool:
    """Every known dispatch situation must have a lookup. Raises if one does not."""
    seen = {r.get("situation", "")[:60] for r in read_lookups(path)}
    missing = [d for d in known if d[:60] not in seen]
    if missing:
        sample = ", ".join(repr(m[:40]) for m in missing[:3])
        raise DispatchWithoutLookup("%d dispatch(es) without a lesson lookup: %s%s"
                                    % (len(missing), sample, " ..." if len(missing) > 3 else ""))
    return True


def _cli(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--audit"]:
        counts: dict = {}
        for r in read_lookups():
            counts[r.get("status", "?")] = counts.get(r.get("status", "?"), 0) + 1
        print("lookups: %s" % (", ".join("%s=%d" % kv for kv in sorted(counts.items())) or "none"))
        return 0
    if not argv:
        print(__doc__)
        return 2
    text = learning.top_for_prompt(" ".join(argv))
    print(text or "(no lessons would be injected)")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
