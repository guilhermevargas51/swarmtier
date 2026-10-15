"""Dispatch ledger: lifecycle events of delegated tasks, append-only.

Central assertion: "a delegated task with no lifecycle event is a SYSTEM ERROR, not a
communication failure." Any dashboard that relies on someone remembering to narrate
will fail; the ledger makes recording a verifiable obligation, and a dashboard only
renders what is already there.

Lifecycle:
    created -> assigned -> started -> blocked | artifact_ready -> completed | failed
    (created/assigned -> cancelled; blocked -> started is a pause, not an end)

State: ``data_dir()/ledger.jsonl`` - a single append-only file, not one folder per run.

Public API:
    record(task_id, event, role=None, model=None, note=None, cost=None, path=None, **extras) -> dict
    read(path=None) -> list ;  by_task(path=None) -> dict
    audit(path=None, now=None) -> list of problems (empty = integrity ok)
    unrecorded_work(known_ids, path=None)   raises LedgerIncomplete

CLI:
    python -m core.ledger             summary + audit
    python -m core.ledger --task ID   history of one task
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta

from core.config import data_dir, jsonl_append, jsonl_read

CREATION = "created"
TERMINAL = ("completed", "failed", "cancelled")
EVENTS = ("created", "assigned", "started", "blocked", "artifact_ready",
          "completed", "failed", "cancelled")

# What may follow what. ``blocked`` returns to ``started``: a block gets resolved.
TRANSITIONS = {
    "created": ("assigned", "cancelled"),
    "assigned": ("started", "blocked", "cancelled"),
    "started": ("blocked", "artifact_ready", "completed", "failed"),
    "blocked": ("started", "failed", "cancelled"),
    "artifact_ready": ("completed", "failed"),
    "completed": (),
    "failed": (),
    "cancelled": (),
}

# Optional extra fields accepted by record(); anything else is ignored silently so a
# caller may send more than the ledger understands without breaking the audit.
EXTRA_FIELDS = ("source", "session", "name", "background", "agent_id", "request",
                "parent", "risk", "stage", "batch", "reason", "output", "tokens",
                "duration_s", "effort")

HOURS_UNTIL_STUCK = 6  # no terminal event and no activity for this long = stuck


class LedgerIncomplete(AssertionError):
    """Work is happening that the ledger does not record."""


def ledger_path():
    return data_dir() / "ledger.jsonl"


def record(task_id, event, role=None, model=None, note=None, cost=None, path=None, **extras) -> dict:
    """Append one event. Never raises on I/O trouble: logging must not break the caller."""
    if event not in EVENTS:
        raise ValueError("unknown event: %r (valid: %s)" % (event, ", ".join(EVENTS)))
    line = {"ts": datetime.now().isoformat(timespec="seconds"),
            "task_id": str(task_id), "event": event}
    for k, v in (("role", role), ("model", model), ("note", note), ("cost", cost)):
        if v is not None:
            line[k] = v
    for k, v in extras.items():
        if k in EXTRA_FIELDS and v is not None and k not in line:
            line[k] = v
    try:
        jsonl_append(path or ledger_path(), line)
    except OSError:
        pass
    return line


def read(path=None) -> list:
    return [e for e in jsonl_read(path or ledger_path()) if "task_id" in e and "event" in e]


def by_task(path=None) -> dict:
    d: dict = {}
    for e in read(path):
        d.setdefault(e["task_id"], []).append(e)
    for v in d.values():
        v.sort(key=lambda x: x.get("ts", ""))
    return d


def audit(path=None, now=None) -> list:
    """Integrity check. Each problem: ``{type, task_id, detail}``.

    Nothing here judges the QUALITY of the work: badly done but well recorded passes;
    excellent but unrecorded does not.
    """
    now = now or datetime.now()
    problems = []
    for tid, events in sorted(by_task(path).items()):
        names = [e["event"] for e in events]
        if names[0] != CREATION:
            problems.append({"type": "no_creation", "task_id": tid,
                             "detail": "first event is %r, expected %r" % (names[0], CREATION)})
        for a, b in zip(names, names[1:]):
            if b not in TRANSITIONS.get(a, ()):
                problems.append({"type": "invalid_transition", "task_id": tid,
                                 "detail": "%s -> %s is not a valid path" % (a, b)})
        if not any(n in TERMINAL for n in names):
            try:
                last = datetime.fromisoformat(events[-1]["ts"])
                idle = now - last
                if idle > timedelta(hours=HOURS_UNTIL_STUCK):
                    problems.append({"type": "stuck", "task_id": tid,
                                     "detail": "no event for %.1f h, last state %r"
                                               % (idle.total_seconds() / 3600, names[-1])})
            except (KeyError, ValueError):
                pass
        for i, n in enumerate(names[:-1]):
            if n in TERMINAL:
                problems.append({"type": "event_after_terminal", "task_id": tid,
                                 "detail": "%r at %d, followed by %r" % (n, i, names[i + 1])})
                break
    return problems


def unrecorded_work(known_ids, path=None) -> bool:
    """Every id in ``known_ids`` (work known to have happened) MUST have events here."""
    recorded = set(by_task(path))
    missing = [t for t in known_ids if str(t) not in recorded]
    if missing:
        raise LedgerIncomplete(
            "%d execution(s) with no lifecycle event: %s%s. This is a system error: some "
            "dispatch path does not record." % (len(missing), ", ".join(map(str, missing[:6])),
                                                " ..." if len(missing) > 6 else ""))
    return True


def _cli(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--task" in argv:
        tid = argv[argv.index("--task") + 1]
        for e in by_task().get(tid, []):
            print("%s  %-16s %s" % (e.get("ts", ""), e["event"], e.get("note", "")))
        return 0
    tasks = by_task()
    print("ledger: %d tasks, %d events" % (len(tasks), len(read())))
    if not tasks:
        print("empty: nothing has been recorded yet, so delegation is still invisible.")
        return 0
    probs = audit()
    for p in probs:
        print("%-22s %-12s %s" % (p["type"], p["task_id"], p["detail"]))
    if not probs:
        print("ok: every task has a complete, valid lifecycle.")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
