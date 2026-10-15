"""CLI: ``python -m core.quota set --5h 42 --week 64`` | ``python -m core.quota show [--json]``."""
from __future__ import annotations

import argparse
import json
import sys

from core.quota import is_stale
from core.quota.claude import ClaudeProvider, quota_file, write_reading
from core.quota.effort import pace


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m core.quota",
                                 description="Record and show your Claude quota (copied from /usage).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set", help="write a reading with a timestamp")
    s.add_argument("--5h", dest="h5", type=float, help="percent used in the 5-hour window")
    s.add_argument("--week", type=float, help="percent used in the weekly window")
    s.add_argument("--resets-5h", help="ISO time the 5-hour window resets (optional)")
    s.add_argument("--resets-week", help="ISO time the weekly window resets (optional)")
    sh = sub.add_parser("show", help="show the current reading with its age")
    sh.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "set":
        if a.h5 is None and a.week is None:
            print("error: give --5h and/or --week", file=sys.stderr)
            return 2
        try:
            write_reading(a.h5, a.week, a.resets_5h, a.resets_week)
        except ValueError as e:
            print("error: %s" % e, file=sys.stderr)
            return 2
        print("saved to %s" % quota_file())
        return 0

    r = ClaudeProvider().read()
    r["stale"] = is_stale(r)
    r["pace"] = pace(r["weekly_pct"], r["resets_at"]["weekly"])
    if a.json:
        print(json.dumps(r, indent=1))
        return 0
    if r["window_5h_pct"] is None and r["weekly_pct"] is None:
        print("quota unknown: %s" % r.get("error", "no data"))
        return 1
    print("5h window: %s%%   weekly: %s%%   (age %ss%s)   weekly pace: %s"
          % (r["window_5h_pct"], r["weekly_pct"], r["age_s"], ", STALE" if r["stale"] else "",
             r["pace"]["verdict"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
