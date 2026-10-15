---
name: swarm-split
description: Use when a job splits on its own into many independent pieces (classify 500 tickets, extract fields from 40 invoices, check 30 files) and a script can verify the result. Slices the material into batches under the Haiku token ceiling and tells you how many triage agents to dispatch in parallel. Trigger on "swarm", "fan out", "many files", "in parallel", "batch".
---

# Swarm split

Per unit of quota, small-context Haiku does about 14x the work of Sonnet (`docs/cost-map.md`, section 3), so a swarm of 10-15 `triage` agents in parallel uses roughly the quota of ONE Sonnet run of similar size. It works only when the job divides by itself and something cheap can check the answer.

## When to use it

All three must hold:
1. The work **divides on its own** (N files, N rows, N documents) with no dependency between pieces.
2. A **script can verify** the combined result (counts match, schema validates, sample agrees).
3. It is **not** a factual verdict against a source of truth. Those stay with the top-tier model.

If any fails, use a single `executor` or keep the work.

## How to run

1. Slice the material. Above ~100k tokens of context you get ~5x less work per unit of quota (`docs/cost-map.md`), so each batch gets at most ~60k tokens of material:
   ```
   python -m core.swarm_split <files, folders or globs> [--max 60000] [--json out.json]
   ```
   It prints one line per batch (`batch 3 - ~41k - file.md (l.1-900), other.md`) and the total number of agents. A file that alone exceeds the ceiling is cut by line range.
2. One batch = one agent. **More than 15 batches means waves** (15 per wave); beyond that the returns flowing back into the orchestrator eat the savings.
3. Dispatch **all agents of a wave in the SAME message, in the background**, each with an explicit `effort` (Haiku low = extract/count/list; medium = classify against a criterion, the default; high = edge cases).
4. Each agent returns at most 10 closed lines (`batch 7: 2 problems - line 14, line 31`), never the material.
5. Run the verification script over the merged results. A batch that came back wrong or stalled is re-run by an `executor` (Sonnet, medium).

Do not wait for the swarm in a foreground loop: dispatch in the background, end the turn, and process results as they arrive.

## Each agent's spec must include

- the criterion/taxonomy, ready-made (agents never invent it)
- its batch (files and line ranges from the slicer)
- `Return <= 10 lines` in a fixed format a script can parse
- the instruction to answer `CANNOT CLASSIFY` instead of guessing
