# The dispatch line

One line the orchestrator writes **before every delegation**. Without it, it does not dispatch.
It forces three decisions that otherwise get skipped: who does the work, at what effort, and who reviews.

All values in this document (percentages, paces, scenario letters) are example values, not measurements.

## Format

```
Scenario X · 5h N% / week N% (Nx pace) · -> agent/model + effort · why · who reviews
```

| Field | Meaning |
|---|---|
| Scenario | `A` (quota available) or `B` (no quota). See [scenarios.md](scenarios.md). |
| 5h N% / week N% | Current use of the 5-hour and weekly windows, from your quota meter (`core/quota/`). |
| (Nx pace) | Week use divided by how much of the week has passed. Above 1x you are burning faster than the week allows. |
| -> agent/model + effort | The destination. Effort is mandatory; the `require-effort` hook blocks a dispatch without one. |
| why | The reason this tier gets it right, taken from [cost-map.md](cost-map.md). |
| who reviews | The person or step that checks the result. Never the agent that produced it for risky work. |

A second short line states the orchestrator's own effort whenever the kind of work changes:
`effort: low | medium | high`.

## Pace decides

If a window is **above its safe pace**, the other window carries the work. Choose the model by **total cost**
(price + rework + your review), not price alone. A cheap model that errs on a risky claim is expensive.

## Examples

**1. Scan, many files (swarm)**

```
Scenario A · 5h 18% / week 41% (0.9x pace) · -> 8x triage/Haiku + low · extract and count across 8 batches (split by swarm_split), a script checks the totals · reviewed by the script, then the orchestrator reads 8 lines
```

**2. Write a script**

```
Scenario A · 5h 32% / week 58% (1.4x pace) · -> executor/Sonnet + medium · code with a test, week is over pace so no Opus subagent · reviewed against the test and one run of the real input
```

**3. Risky claim, no quota for subagents**

```
Scenario B · 5h 96% / week 63% (1.1x pace) · -> orchestrator only, effort high · verdict on a claim that needs the source reopened, nothing cheaper may state it · reviewed by the user
```

## What the hook enforces

The line itself is a habit written into the template ([CLAUDE.md](../templates/CLAUDE.md), section 2). The one part the
tooling enforces is **effort**: `hooks/require-effort.py` blocks an `Agent` call with no `effort`, and blocks
`max` on Sonnet. Agents you list in `exempt_agents` ([config.example.toml](../templates/config.example.toml)) are skipped.
