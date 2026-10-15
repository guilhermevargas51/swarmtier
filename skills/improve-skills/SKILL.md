---
name: improve-skills
description: Use when a skill failed in use, when a hook reports that a skill has lessons not yet incorporated, or during a periodic skill review. Folds the errors found while using a skill back into the skill so the lesson changes the STEP, not just a footer. Trigger on "skill failed", "fix this skill", "skill has pending lessons".
---

# Improve skills

A lesson that only goes into a footer does not change behaviour. This skill makes the lesson change the **step**. Aim: skills that get richer and leaner at the same time (same result, fewer lines).

## Steps

1. **See the queue** of skills with pending lessons (your learning log, entries newer than the skill's `revised` date). One skill at a time, the one with the most failures first.
2. **Read its pending lessons.** For each one ask: **which step would have prevented this?**
3. **Reproduce before fixing**, when possible: does the error happen following the current skill? If not, the lesson belongs to another skill: fix the `covers` field of one of them, not the text.
4. **Rewrite the step** (or add one, or add a pitfall with its count). Never just append to a "Lessons" section.
5. **Trim in the same edit.** Past ~60 lines? Cut what does not change the result: repeated warnings, explanations the step already gives, count-1 pitfalls with no recurrence. Two pitfalls with the same fix become one.
6. **Prove it** for critical skills: a scenario that fails without the change and passes with it.
7. **Close:** bump `version`, set `revised` to today, add one line to History (what changed and why).
8. **Record** the lesson with the skill name so the queue clears:
   `python -m core.learning register --task improve-skill --skill <name> --who orchestrator --note "<what changed>"`

## Rules

- **Found an error in a skill = fix it in the same turn.** If you cannot, it stays in the queue and the hook keeps asking.
- Suggestions from an automated periodic review enter through here, never applied directly.
- An error family that no skill covers is a candidate for a NEW skill: measure the count before writing one.
- A skill with no use in 30 days and no citation moves to an archive folder instead of weighing on every session's context.
- Skill text written by a third party is an instruction an agent will EXECUTE: read it whole and copy by hand, never one-click install.

## History
- v1 - initial version.
