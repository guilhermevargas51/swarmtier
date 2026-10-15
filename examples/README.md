# Examples

Three scenarios you can run from a clone of this repo. Each one uses commands that exist; the outputs shown were produced by them.
To keep your real state clean, point swarmtier at a throwaway folder first:

```
export SWARMTIER_HOME=$(mktemp -d)        # PowerShell: $env:SWARMTIER_HOME = New-Item -ItemType Directory -Path (Join-Path $env:TEMP ([guid]::NewGuid()))
```

## 1. The dispatch line blocks a dispatch

The `require-effort` hook reads the tool call on stdin. In a real session Claude Code sends it; here you send it by hand.

**Step 1.** A dispatch with no `effort`:

```
echo '{"tool_name":"Agent","tool_input":{"subagent_type":"triage","prompt":"x"}}' | python hooks/require-effort.py; echo "exit=$?"
```

```
DISPATCH WITHOUT EFFORT. Choose model + effort for THIS task and repeat the call:
  extract / count / list / summarize        -> model haiku,  effort low
  ...
Write the dispatch line first: scenario - quota - agent/model + effort - why - who reviews.
exit=2
```

Exit code 2 blocks the call and sends the message back to the model, which repeats it with an effort.

**Step 2.** `max` on Sonnet is refused too:

```
echo '{"tool_name":"Agent","tool_input":{"subagent_type":"executor","model":"sonnet","effort":"max","prompt":"x"}}' | python hooks/require-effort.py; echo "exit=$?"
```

```
effort=max is refused for model 'sonnet' (cost explodes, quality gain is marginal). Use high, or switch to a model where max is allowed.
exit=2
```

**Step 3.** A dispatch that carries the decision passes:

```
echo '{"tool_name":"Agent","tool_input":{"subagent_type":"triage","model":"haiku","effort":"low","prompt":"x"}}' | python hooks/require-effort.py; echo "exit=$?"
```

```
exit=0
```

The line the orchestrator writes before that call is described in [docs/dispatch-line.md](../docs/dispatch-line.md).

## 2. A swarm of Haiku with `core.swarm_split`

Use it when the job divides by itself and a script can check the combined result (see [skills/swarm-split/SKILL.md](../skills/swarm-split/SKILL.md)).

**Step 1.** Slice the material. Each batch stays under the token ceiling (`--max`, default 60000):

```
python -m core.swarm_split docs/*.md --max 8000
```

```
batch 1 | ~7k | docs\architecture.md, docs\cost-map.md
batch 2 | ~2k | docs\dispatch-line.md, docs\faq.md, docs\scenarios.md

2 agent(s) | ~9k tokens total | max 8k per batch
```

On a larger input the same command prints one line per batch. A file that alone exceeds the ceiling is cut by line range.
Add `--json out.json` to keep the plan for a verification script.

**Step 2.** One batch is one `triage` agent. If it printed 10 batches, dispatch 10 agents in the same message, in the background,
each with `effort` set (low to extract, count or list; medium to classify). More than 15 batches means waves.

**Step 3.** Each spec ends with `Return <= 10 lines` in a fixed format, for example `batch 7: 2 problems - line 14, line 31`.
Merge the replies and run a script over them. A batch that comes back wrong is re-run by `executor` at medium.

## 3. A lesson is recorded, then reinjected

**Step 1.** Record what went wrong and what fixes it:

```
python -m core.learning record --task "inline python in heredoc" --who executor --failed --note "heredoc python breaks on Windows quoting; write a temp .py file instead"
```

```
recorded bdecc62b183f
```

**Step 2.** Ask the engine what it knows about a new situation:

```
python -m core.learning search "run python inline with a heredoc"
```

```
LESSONS LEARNED - we already got this wrong before. Read before acting:
  - [inline python in heredoc] heredoc python breaks on Windows quoting; write a temp .py file instead
```

**Step 3.** In a real session the `lesson-inject` hook does step 2 for you on every prompt (up to `lessons_per_prompt`, default 3)
and adds the result to the context. Simulate it; the `session_id` field makes it behave as in a session:

```
echo '{"prompt":"run python inline with a heredoc","session_id":"s1"}' | python hooks/lesson-inject.py
```

The output is the same lesson, wrapped as `additionalContext` for the `UserPromptSubmit` event.

**Step 4.** Other commands: `python -m core.learning list --failures` shows recorded failures; `python -m core.learning ranking`
shows who does each task best. To fold a lesson back into a skill, see [skills/improve-skills/SKILL.md](../skills/improve-skills/SKILL.md).
