# Cost map

Which model and effort for which work, and the numbers behind the choice.
Used by [templates/CLAUDE.md](../templates/CLAUDE.md) and the dispatch line ([dispatch-line.md](dispatch-line.md)).

## 1. Public benchmark: model x effort

Source: Artificial Analysis, Intelligence Index v4.3.2 ("Default Fallback"), pages
`artificialanalysis.ai/models/releases/claude-{opus,sonnet,haiku}-5-5`, read on 2026-10-07; re-read the pages yourself.
Cost per task is Artificial Analysis's benchmark cost, not a measurement of any user's spend.
Hallucination is AA-Omniscience: of the questions the model did not know, how many it answered anyway (lower is better).
Re-check the pages before relying on these numbers; they change with each release.

| Model - effort | Index | $ per task | Hallucination | Output tokens per task |
|---|---:|---:|---:|---:|
| Haiku low | 29.4 | 0.02 | 45% | 9k |
| Haiku medium | 34.5 | 0.05 | 45% | 20k |
| Haiku high | 37.8 | 0.08 | 45% | 37k |
| Haiku xhigh | 41.2 | 0.12 | 44% | 66k |
| Haiku max | 43.4 | 0.21 | 40% | 129k |
| Sonnet low | 35.9 | 0.42 | 50% | 5k |
| Sonnet medium | 40.8 | 0.59 | 51% | 8k |
| Sonnet high | 46.8 | 1.12 | 65% | 19k |
| Sonnet xhigh | 51.9 | 2.75 | 63% | 48k |
| Sonnet max | 56.0 | 7.67 | 47% | 147k |
| Opus low | 42.3 | 0.55 | 68% | 3k |
| Opus medium | 51.2 | 1.34 | 68% | 12k |
| Opus high | 53.6 | 1.82 | 68% | 18k |
| Opus xhigh | 56.0 | 3.46 | 66% | 40k |
| Opus max | 57.6 | 5.98 | 59% | 84k |

## 2. What the numbers decide

1. **Haiku xhigh (41.2, $0.12) matches Sonnet medium (40.8, $0.59) at one fifth of the price**, with lower
   hallucination (44% vs 51%). Outside code, Sonnet low/medium loses its reason to exist.
2. **Haiku max (43.4, $0.21) is about Opus low (42.3, $0.55)**, with the lowest hallucination of the family.
3. **Sonnet high and xhigh lose to Opus medium** (51.2 at $1.34). A subagent that needs high
   intelligence goes to Opus medium, not Sonnet high/xhigh.
4. **Opus medium gives about 96% of Opus high (51.2 vs 53.6) for about 74% of the cost.** Keep the
   session in medium and raise to high only when it matters.
5. **Sonnet is for code**, in medium; high if stuck; max never (the most expensive point on the table).
6. **Haiku is verbose** at xhigh/max (66k-129k output tokens per task): slow, so use it in the background.
7. **Low hallucination is not knowing the facts.** Haiku refuses more; it does not know more. Facts that must
   be exact stay with the orchestrator checking the source.

The resulting map (also in the template):

| Work | Model - effort |
|---|---|
| extract, count, list, summarize | Haiku - low |
| classify or check against a ready criterion | Haiku - medium |
| checkable edge case | Haiku - high, then max if it errs |
| analysis/synthesis outside code | Haiku - xhigh |
| code, script | Sonnet - medium (high if stuck, never max) |
| subagent needing high intelligence | Opus - medium |
| risky claim, decision, talking to the user | Opus, session in medium |

## 3. Quota is a separate currency from price

Quota (the 5-hour and weekly windows of a subscription) is not priced like the API. Method: measured on one
heavy-usage Claude Code account over 30 days from the usage dashboard; your numbers will differ (see
"How to measure your own"). The same quota pool yielded very different amounts of work per model:

| Pool | Relative work per unit of quota |
|---|---|
| Opus | 1x (baseline) |
| Sonnet | about 2x |
| Haiku, context above 100k | about 5.5x |
| Haiku, context up to 100k | **about 27x** (about 14x Sonnet) |

So Haiku below 100k of context is the cheapest unit of work by a wide margin, which is why the swarm is capped at
about 60k tokens per agent ([architecture.md](architecture.md) describes the governance side; the cap lives in
[config.example.toml](../templates/config.example.toml) as `swarm_max_tokens`).

## 4. Measured shares of spend

Method: measured on one heavy-usage Claude Code account over 30 days from the usage dashboard. They are shares,
not dollar amounts, and your numbers will differ; see "How to measure your own" below.

| Finding | Share |
|---|---|
| Tool results (file reads plus shell output) | about 69% of all spend (reads about 27%, shell about 26%) |
| Model reasoning | about 0.1% |
| Model replies | about 2.6% |
| Cache churn from idle gaps | the largest single line of the panel, larger than model switches |
| Messages above 150k of context | about 94% of usage |
| Most expensive messages | all one-word messages ("go", "hi", "."): tiny prompt, huge cache rewrite |

What each one drives in swarmtier:

- 69% in tool results -> "the orchestrator never reads big files" and the Haiku summarizer rule.
- Idle gaps -> the `cold-cache` hook and the "checkpoint and compact before leaving" rule.
- One-word messages -> "the return must bring work".
- Model switches -> "never switch model mid-session; test a new model in a new session".

## 5. How to measure your own

1. Take your usage export or panel for a fixed window (30 days is enough).
2. Split cost by **component**: cache reads, cache writes, tool results, assistant text, reasoning.
3. Find the **ten most expensive messages** and read their length. If they are very short, the cost is cache, not the prompt.
4. Sum **idle gaps**: consecutive messages in one session separated by more than the cache TTL
   (`cache_ttl_minutes`, default 60). Price each as one full-context cache rewrite.
5. Count **model switches** inside sessions and price each as a cache rewrite as well.
6. Compare shares, not totals. The shares transfer between users; absolute amounts do not.
7. Re-measure after one week of using swarmtier and compare the same shares.

Do not publish a dollar figure from your own usage; keep it in proportions.
