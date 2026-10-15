# Security

## What swarmtier does and does not touch

- **No network.** The code in `core/` and `hooks/` makes no network calls.
- **No tokens or credentials.** It does not read your Claude token, API keys or login files. Quota is a number you type
  with `python -m core.quota set` (copied from `/usage`).
- **Local state only.** The ledger, lessons and timestamps live in `SWARMTIER_HOME`, `data_dir` from your config, or
  `~/.swarmtier`. Delete the folder and the state is gone.
- **One hook blocks.** `require-effort` blocks an `Agent` call that has no `effort`. Every other hook exits 0 on any failure
  and never stops your session.
- **Hooks run as you.** They are Python scripts started by Claude Code with your permissions. Read them before installing;
  they are short.

## Reporting a vulnerability

Please do not put details of a security problem in a public issue. Use GitHub's private vulnerability reporting on this
repository (Security tab, "Report a vulnerability"). If that is not available, open an issue that says only that you have a
security report and ask for a private way to send it. Include what you ran, what happened, and what you expected.

This is a volunteer project: no bounty and no formal response time.

## Scope

In scope: code in this repository, including `hooks/`, `core/`, `scripts/` and the plugin manifests.
Out of scope: Claude Code itself, Anthropic services, and third-party plugins.
