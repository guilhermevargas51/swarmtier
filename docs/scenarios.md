# Scenarios

The scenario decides **who is in the field**. Dispatching without knowing it means dispatching to a role that
may not exist today. State it in one line in the first reply of each day, and re-read it before any large dispatch.

| | Quota | Who orchestrates | Who executes |
|---|---|---|---|
| **A** | available | the main session (Opus) | native subagents: `triage` (Haiku), `executor` (Sonnet), `vision-reader` |
| **B** | exhausted or unavailable | nobody (or you, by hand) | only checkable, non-private work, on a model outside the quota pool if you have one |

## Scenario A: with quota

- The orchestrator plans, decides, and closes points. It does not read big files.
- Volume goes down the tiers in order of march: Haiku (scan, extract, classify) -> Sonnet (code, scripts, writes) -> Opus only to close a point.
- Parallel scans use the swarm ([cost-map.md](cost-map.md), section 3, explains the 60k-token cap).
- Every dispatch carries the dispatch line and an explicit `effort` ([dispatch-line.md](dispatch-line.md)).
- Pace matters: if one window runs above its safe pace, the other carries the work.
- Before leaving for a long break: save state, compact ([CLAUDE.md](../templates/CLAUDE.md), section 7).

## Scenario B: without quota

- No orchestration runs. This is the right scenario to do the work yourself, not a failure state.
- Do not queue dispatches that will fail. The quota meter in `core/quota/` reports the scenario; trust it over memory, and check the age of the reading.
- Anything with a checkable result and no private data may go to a model outside the quota pool, if you have one configured. Anything risky waits.
- Hooks that need no quota still run: `require-effort`, the ledger, lesson capture and injection.

## Switching

Re-read the scenario when:

- the first reply of the day starts;
- before a large dispatch;
- after any message about a limit or reset.

A reading older than its expected window is not a verdict; check its age first.

See also [faq.md](faq.md) for what works without Haiku or without the quota meter.
