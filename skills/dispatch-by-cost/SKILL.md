---
name: dispatch-by-cost
description: Use BEFORE delegating any work to a subagent (Agent tool) or before choosing a model/effort for a task. Forces the dispatch line (scenario, quota, agent/model + effort, why, who reviews) and picks the cheapest tier that gets the task right. Trigger on "delegate", "dispatch", "which model", "spawn agents", or any plan that sends work to a subagent.
---

# Dispatch by cost

The orchestrator (your most capable, most expensive model) plans, decides and talks to the human. Everything else goes down to the **cheapest tier that gets it right the first time**. Without the dispatch line below, do not dispatch.

## 1. The dispatch line (mandatory, before every delegation)

Write exactly one line before each `Agent` call:

```
Scenario X · quota 5h N% / week N% (pace) · -> agent/model + effort · why · who reviews
```

Example:
`Scenario with-quota · quota 5h 22% / week 41% (1.3x the pace) · -> triage/haiku + medium · classify 500 tickets against a fixed taxonomy · script samples 20 results`

Also state **your own** effort when you change work blocks (one line: `effort: low - chain of confirmations`, `effort: medium - conversation`, `effort: high - verdict on a high-stakes fact`).

Always pass `effort` explicitly on the dispatch; a dispatch without it inherits the session's effort and hides the cost.

## 2. Scenarios

| Scenario | Quota | Orchestrates | Executes |
|---|---|---|---|
| **With quota** | available | top-tier model | native subagents: Haiku, Sonnet, vision-reader |
| **Without quota** | exhausted | nobody | the human works; only checkable, non-private tasks go to a free/local model |

Read the scenario and the pace from the quota meter before large dispatches. **The pace rules**: if one quota pool (e.g. weekly Opus) runs ahead of its pace, move work to the other pool. Stale quota readings are not a verdict; check their age.

## 3. Cost map: work -> model, effort

Each job goes to the cheapest tier that gets it right. Index and cost ratios come from public benchmark data (see `docs/cost-map.md`).

| Work | Who - effort |
|---|---|
| extract, count, list, summarize a log or file | Haiku - low (swarm if it splits) |
| classify / check against a ready criterion | Haiku - medium |
| edge case that a script can check | Haiku - high; if wrong, Haiku - max |
| analysis / synthesis outside code | Haiku - xhigh (scores like Sonnet medium at about 1/5 of the cost); max only when not in a hurry |
| code, script, pipeline | Sonnet - medium; high if stuck; max never |
| subagent that needs high intelligence | Opus - medium (beats Sonnet high/xhigh) |
| verdict on a high-stakes fact, final decision, talking to the human | Opus (you) - medium session, high only at the decisive moment |

Rule of thumb: the same quota stretches roughly an order of magnitude further on small-context Haiku than on Opus.

## 4. Total cost, not price

Choose by **total cost = price + rework + your review time**. A cheap model that errs on a factual task is expensive: the retry is what drains the quota. Dispatch rule: `P(first-try success) / quota`. Checkable bulk work goes to the cheapest model; anything whose errors are silent (contract clauses, invoice totals, compliance rules, transcription, taxonomy decisions, permanent rules) stays up.

## 5. The orchestrator does not read big files

Every token the orchestrator reads is re-read on each turn until compaction, and costs many times what Haiku costs.

1. Tool output over ~30 lines (log, grep, file returned by an agent): a `triage` agent at low effort reads it and returns at most 10 lines. You read the summary, never the raw output.
2. To verify an agent's delivery against a source: Haiku at medium builds the **check table** (`item - answer - quoted excerpt - source line`, one row each). You give the verdict on the table and open the original only on the row that does not close.
3. Every dispatch spec ends with `Return <= N lines` and, when there is verification, the table ready. The agent that produces delivers the proof with it.
4. Exception: images the human sends (only you see them) and a verdict on the single line that failed.

**Return from any agent: at most 10 lines.**

## 6. The orchestrator's three control points

1. **Before closing the plan:** what goes in, what stays out, and the definition of done.
2. **The same test failed twice:** the worker stops retrying and you decide: raise the model, change the approach, or give up.
3. **Before saying "done" to the human:** compare against an APPROVED reference, not against the worker's own test. A worker can "fix" something, pass its own test, and still change the real behaviour. For generated media (audio, images), compare the first output against an approved reference before releasing the batch.

## 7. What to delegate and what to keep

Delegate what has a **checkable result**. Keep what **fails silently**: asserting facts from a source, transcribing images, deciding taxonomy, writing permanent rules, calibrating thresholds. Review means reopening the source and checking number by number against the cited line. Reading the delivery and approving it is not review.

Pack the work: if you are about to chain more than two mechanical actions, stop and send them as one dispatch. The gain is in block size, not in the number of dispatches. A dispatch for a 20-second grep costs more than doing it.

For work that splits into many independent pieces, use the `swarm-split` skill.
