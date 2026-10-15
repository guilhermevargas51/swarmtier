# -*- coding: utf-8 -*-
"""PreToolUse hook for the Agent tool: block any subagent dispatch that has no `effort`.

Why: the effort level is the cheapest cost lever you have, and a subagent that silently
inherits the session's effort is a dispatch nobody decided on. The orchestrator must pick
model + effort for THIS task - the "dispatch line" - and repeat the call.

Exit code 2 blocks the tool call and sends the stderr message back to the model so it can
fix the call on the spot. This is the only hook that blocks on purpose; every other failure
mode (bad JSON, other tools, missing config) exits 0.

Config (swarmtier.toml, optional, top-level keys):
    exempt_agents  = ["vision-reader"]   # subagent_type values allowed without effort (default [])
    forbid_max_for = ["sonnet"]          # models for which effort=max is refused (default ["sonnet"])
"""
import sys

from _common import load_cfg, read_event, setting

VALID_EFFORTS = ("low", "medium", "high", "xhigh", "max")

DISPATCH_LINE = (
    "DISPATCH WITHOUT EFFORT. Choose model + effort for THIS task and repeat the call:\n"
    "  extract / count / list / summarize        -> model haiku,  effort low\n"
    "  classify against a ready criterion        -> haiku,        effort medium\n"
    "  check an edge case                        -> haiku,        effort high\n"
    "  analysis / synthesis outside of code      -> haiku,        effort xhigh (or max if slow is fine)\n"
    "  script / engine / edit with validation    -> sonnet,       effort medium\n"
    "  hard code bug                             -> sonnet,       effort high (never max)\n"
    "  high intelligence outside of code         -> opus,         effort medium\n"
    "  final verdict / what ships / user-facing  -> opus,         effort high\n"
    "Write the dispatch line first: scenario - quota - agent/model + effort - why - who reviews."
)


def main():
    ev = read_event()
    if not ev or ev.get("tool_name") not in ("Agent", "Task"):
        return 0
    tool_input = ev.get("tool_input") or {}

    cfg = load_cfg()
    exempt = setting(cfg, "exempt_agents", []) or []
    if tool_input.get("subagent_type") in exempt:
        return 0

    effort = tool_input.get("effort")
    if effort:
        forbid = setting(cfg, "forbid_max_for", ["sonnet"]) or []
        model = str(tool_input.get("model") or "sonnet").lower()
        if effort == "max" and model in [str(m).lower() for m in forbid]:
            print("effort=max is refused for model '%s' (cost explodes, quality gain is marginal). "
                  "Use high, or switch to a model where max is allowed." % model, file=sys.stderr)
            return 2
        return 0

    print(DISPATCH_LINE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        code = 0  # a broken hook must not block work
    sys.exit(code)
