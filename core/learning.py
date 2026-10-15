"""Learning engine: record what worked and what failed, retrieve it before acting.

Every episode is ONE line in ``data_dir()/lessons.jsonl``: who did what, whether it
worked, what it cost, and (for failures) why. Lines add up, so you can ask "who does
this task best?" and "what already went wrong here?" instead of relying on memory.

Three rules keep it honest:
  1. Only measured things go in. No score -> leave hits/total empty.
  2. Failures are worth more than successes. A failure MUST carry a note (the why).
  3. Nothing is deleted. A changed conclusion is a new line; "archive" hides a lesson
     from retrieval by appending a marker, never by rewriting the file.

Public API:
    record(task, who, ok=True, note="", ...) -> dict
    search(situation, limit=None, ...)       -> list[dict]   (failure lessons, best first)
    top_for_prompt(situation, ...)           -> str          (compact text for a prompt)

CLI:
    python -m core.learning record --task NAME --who MODEL [--failed --note WHY] [--hits N --total M]
    python -m core.learning list [--failures]
    python -m core.learning search "what I am about to do"
    python -m core.learning ranking [--task NAME]
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from collections import defaultdict
from pathlib import Path

from core.config import data_dir, jsonl_append, jsonl_read, load_config

MIN_TERM_LEN = 4  # shorter words ("with", "this") do not discriminate


def lessons_path() -> Path:
    return data_dir() / "lessons.jsonl"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def lesson_id(rec: dict) -> str:
    """Stable content-addressed id: changing the text changes the id."""
    base = "%s|%s" % (rec.get("task", ""), rec.get("note", ""))
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:12]


def record(task: str, who: str, ok: bool = True, note: str = "", hits=None, total=None,
           cost=None, minutes=None, skill: str = "", path=None) -> dict:
    """Append one episode. ``cost`` is in whatever unit you use consistently (e.g. % of quota).

    Raises ValueError for a failure without a note: an unexplained failure teaches nothing.
    """
    if not task or not who:
        raise ValueError("task and who are required")
    if not ok and not (note or "").strip():
        raise ValueError("a failure needs a note explaining why")
    rec = {"ts": _now(), "task": task, "who": who, "ok": bool(ok), "note": note or ""}
    for k, v in (("hits", hits), ("total", total), ("cost", cost), ("minutes", minutes),
                 ("skill", skill)):
        if v not in (None, ""):
            rec[k] = v
    jsonl_append(path or lessons_path(), rec)
    return rec


def load(path=None) -> list:
    """All episode records (archive markers excluded)."""
    return [r for r in jsonl_read(path or lessons_path())
            if r.get("type") not in ("archive", "unarchive")]


def archived_ids(path=None) -> set:
    """Ids currently archived (a later 'unarchive' marker undoes an 'archive')."""
    out: set = set()
    for r in jsonl_read(path or lessons_path()):
        if r.get("type") == "archive":
            out.add(r.get("id"))
        elif r.get("type") == "unarchive":
            out.discard(r.get("id"))
    return out


def archive(lid: str, reason: str = "", path=None) -> None:
    """Hide a lesson from retrieval. Reversible with :func:`unarchive`."""
    jsonl_append(path or lessons_path(),
                 {"type": "archive", "id": lid, "ts": _now(), "reason": reason})


def unarchive(lid: str, path=None) -> None:
    jsonl_append(path or lessons_path(), {"type": "unarchive", "id": lid, "ts": _now()})


def terms_of(text: str) -> set:
    clean = (text or "").lower().replace("-", " ").replace("_", " ")
    for ch in '.,;:!?()[]{}"\'/\\`':
        clean = clean.replace(ch, " ")
    return {w for w in clean.split() if len(w) >= MIN_TERM_LEN}


def search(situation: str, limit=None, min_score=None, include_success: bool = False,
           records=None, archived=None, path=None) -> list:
    """Lessons relevant to ``situation``, strongest first.

    Failures only by default: success lines say WHO to use (routing), not what to
    avoid. A match on the short task label weighs 3x a match inside a long note, so
    a lesson with a long note does not match everything by accident.
    """
    cfg = load_config()["learning"]
    limit = cfg["max_lessons_in_prompt"] if limit is None else limit
    min_score = cfg["min_score"] if min_score is None else min_score
    records = load(path) if records is None else records
    archived = archived_ids(path) if archived is None else archived
    terms = terms_of(situation)
    if not terms:
        return []
    found = []
    for rec in records:
        if rec.get("ok", True) and not include_success:
            continue
        if not include_success and not rec.get("note"):
            continue
        if lesson_id(rec) in archived:
            continue
        label = (rec.get("task") or "").lower().replace("-", " ")
        body = ("%s %s" % (rec.get("who", ""), rec.get("note", ""))).lower()
        score = 3 * sum(1 for w in terms if w in label) + sum(1 for w in terms if w in body)
        if score >= min_score:
            found.append((score, rec))
    found.sort(key=lambda p: -p[0])
    return [r for _, r in found[:limit]]


def format_bundle(lessons: list, max_note_chars=None) -> str:
    """Compact prompt text. A long bundle becomes noise people learn to skip."""
    if not lessons:
        return ""
    cap = load_config()["learning"]["max_note_chars"] if max_note_chars is None else max_note_chars
    parts = ["LESSONS LEARNED - we already got this wrong before. Read before acting:"]
    for rec in lessons:
        note = (rec.get("note") or "").strip()
        if len(note) > cap:
            note = note[:cap - 3] + "..."
        parts.append("  - [%s] %s" % (rec.get("task", "?"), note))
    return "\n".join(parts)


def top_for_prompt(situation: str, limit=None, path=None) -> str:
    """Search + format in one call; empty string when nothing relevant exists."""
    return format_bundle(search(situation, limit=limit, path=path))


def ranking(task=None, path=None) -> list:
    """Per (task, who): hit rate, total cost, failures. Best hit rate first, ties -> cheaper."""
    agg = defaultdict(lambda: {"hits": 0, "total": 0, "cost": 0.0, "n": 0, "failures": 0})
    for r in load(path):
        if task and r.get("task") != task:
            continue
        a = agg[(r.get("task", "?"), r.get("who", "?"))]
        a["hits"] += r.get("hits") or 0
        a["total"] += r.get("total") or 0
        a["cost"] += r.get("cost") or 0
        a["n"] += 1
        a["failures"] += 0 if r.get("ok", True) else 1
    rows = [{"task": t, "who": w, "rate": (a["hits"] / a["total"]) if a["total"] else None, **a}
            for (t, w), a in agg.items()]
    rows.sort(key=lambda x: (-(x["rate"] if x["rate"] is not None else -1), x["cost"]))
    return rows


def _cli(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m core.learning", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record", aliases=["register"],
                       help="append an episode; 'register' records a LESSON (a failure) unless --ok")
    r.add_argument("--task", required=True, help="task label or free text")
    r.add_argument("--who", default="claude", help="model or person that did it (default: claude)")
    r.add_argument("--failed", action="store_true")
    r.add_argument("--ok", action="store_true", help="with 'register': record a success instead of a lesson")
    r.add_argument("--note", default="")
    r.add_argument("--hits", type=int)
    r.add_argument("--total", type=int)
    r.add_argument("--cost", type=float)
    r.add_argument("--minutes", type=float)
    r.add_argument("--skill", default="")
    ls = sub.add_parser("list", help="list episodes")
    ls.add_argument("--failures", action="store_true")
    s = sub.add_parser("search", help="lessons relevant to a situation")
    s.add_argument("situation", nargs="+")
    k = sub.add_parser("ranking", help="who does each task best")
    k.add_argument("--task")
    a = ap.parse_args(argv)

    if a.cmd in ("record", "register"):
        try:
            # Only failures are injected back into prompts, so 'register' (the verb the skills
            # use for "record what we learned") defaults to a failure; 'record' keeps ok=True.
            failed = a.failed or (a.cmd == "register" and not a.ok)
            rec = record(a.task, a.who, ok=not failed, note=a.note, hits=a.hits,
                         total=a.total, cost=a.cost, minutes=a.minutes, skill=a.skill)
        except ValueError as e:
            print("error: %s" % e, file=sys.stderr)
            return 2
        print("recorded %s" % lesson_id(rec))
    elif a.cmd == "list":
        for rec in load():
            if a.failures and rec.get("ok", True):
                continue
            print("%s  %-4s %-24s %-18s %s" % (rec.get("ts", "?")[:16], "ok" if rec.get("ok", True) else "FAIL",
                                              rec.get("task", "?")[:24], rec.get("who", "?")[:18],
                                              rec.get("note", "")[:80]))
    elif a.cmd == "search":
        text = top_for_prompt(" ".join(a.situation))
        print(text or "nothing recorded about this - a new situation; record the outcome afterwards.")
    elif a.cmd == "ranking":
        for row in ranking(a.task):
            rate = "%.0f%%" % (100 * row["rate"]) if row["rate"] is not None else "n/a"
            print("%-24s %-18s %6s  cost %.3f  failures %d" % (row["task"][:24], row["who"][:18],
                                                              rate, row["cost"], row["failures"]))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
