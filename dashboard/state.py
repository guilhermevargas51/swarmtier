"""Pure reducer: dispatch-ledger events -> board state.

No I/O in ``build_state``; ``load_state`` is the thin wrapper that reads
``core.ledger`` (``data_dir()/ledger.jsonl``). Agent and model names come from the
ledger itself: nothing is hard-coded here.

Columns (a task sits in exactly one place, decided by its LAST event):

    Plan            created / assigned
    Doing           started (or blocked on something other than you)
    Waiting on you  blocked with role == "user-input"
    Check           artifact_ready
    Done            completed

Failed and cancelled tasks go to a separate "Stalled or failed" strip. Any task whose
last event is older than ``OLDER_AFTER_HOURS`` is folded out of the columns into
"older", so the board shows what is alive.
"""
from __future__ import annotations

from datetime import datetime, timedelta

WAIT_ROLE = "user-input"
OLDER_AFTER_HOURS = 48
MAX_CARDS = 40  # per column; the rest is only counted

COLUMNS = (
    ("plan", "Plan"),
    ("doing", "Doing"),
    ("waiting", "Waiting on you"),
    ("check", "Check"),
    ("done", "Done"),
)


def _parse_ts(value) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def _column_of(last: dict) -> str:
    ev = last.get("event")
    if ev in ("failed", "cancelled"):
        return "stalled"
    if ev == "completed":
        return "done"
    if ev == "artifact_ready":
        return "check"
    if ev == "blocked":
        return "waiting" if last.get("role") == WAIT_ROLE else "doing"
    if ev == "started":
        return "doing"
    return "plan"  # created / assigned


def _card(task_id: str, events: list[dict], now: datetime) -> dict:
    last = events[-1]
    first = events[0]

    def pick(key):
        for e in reversed(events):
            if e.get(key):
                return e[key]
        return None

    title = first.get("note") or pick("note") or task_id
    ts = _parse_ts(last.get("ts"))
    age_h = round((now - ts).total_seconds() / 3600, 1) if ts else None
    return {
        "task_id": task_id,
        "title": str(title)[:160],
        "state": last.get("event"),
        "role": pick("role"),
        "model": pick("model"),
        "effort": pick("effort"),
        "cost": pick("cost"),
        "note": last.get("note") if last.get("note") != title else None,
        "ts": last.get("ts"),
        "age_hours": age_h,
        "events": len(events),
    }


def build_state(events: list[dict], now: datetime | None = None) -> dict:
    """Reduce a list of ledger events into the board structure (pure)."""
    now = now or datetime.now()
    by_task: dict[str, list[dict]] = {}
    for e in events:
        if "task_id" in e and "event" in e:
            by_task.setdefault(str(e["task_id"]), []).append(e)

    cols = {cid: [] for cid, _ in COLUMNS}
    stalled: list[dict] = []
    older: list[dict] = []
    cutoff = now - timedelta(hours=OLDER_AFTER_HOURS)

    for tid, evs in by_task.items():
        evs.sort(key=lambda x: str(x.get("ts", "")))
        card = _card(tid, evs, now)
        ts = _parse_ts(evs[-1].get("ts"))
        if ts is not None and ts < cutoff:
            older.append(card)
            continue
        col = _column_of(evs[-1])
        (stalled if col == "stalled" else cols[col]).append(card)

    def newest(c):
        return str(c["ts"] or "")

    for lst in (*cols.values(), stalled, older):
        lst.sort(key=newest, reverse=True)

    columns = []
    for cid, title in COLUMNS:
        cards = cols[cid]
        columns.append({"id": cid, "title": title, "count": len(cards),
                        "cards": cards[:MAX_CARDS]})
    return {
        "generated": now.isoformat(timespec="seconds"),
        "tasks": len(by_task),
        "older_after_hours": OLDER_AFTER_HOURS,
        "columns": columns,
        "stalled": {"title": "Stalled or failed", "count": len(stalled),
                    "cards": stalled[:MAX_CARDS]},
        "older": {"title": "Older", "count": len(older), "cards": older[:MAX_CARDS]},
    }


def load_state(path=None, now: datetime | None = None) -> dict:
    """Read the ledger (default ``data_dir()/ledger.jsonl``) and reduce it."""
    from core import ledger

    return build_state(ledger.read(path), now)
