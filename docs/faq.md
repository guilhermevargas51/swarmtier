# FAQ

**Is this official from Anthropic?**
No. swarmtier is an independent, community project that works with Claude Code. It is not made, endorsed, or supported by Anthropic.

**Does it work without Haiku?**
Yes. Haiku is the cheapest tier, so you save the most with it, but the pieces are independent. The effort hook, the
cold-cache warning, the ledger and the lesson engine do not need it. Without Haiku, point `triage` at Sonnet low and expect
the swarm to cost more. See [cost-map.md](cost-map.md).

**Which operating systems?**
Windows, macOS and Linux. The hooks and the core are Python with UTF-8 handling and no shell-only dependencies.
Use Python 3.9 or newer. Paths come from the configuration, not from fixed locations.

**Where is my data stored?**
Locally, in `data_dir` from your config ([config.example.toml](../templates/config.example.toml)), or a `.swarmtier/` folder
in the project by default. That holds the delegation ledger, lessons, and session timestamps. Nothing is sent anywhere by
swarmtier itself.

**How do I turn off a hook?**
Remove or comment its entry in `hooks/hooks.json` (or disable the plugin in Claude Code). To only exempt certain agents
from the effort check, list them in `exempt_agents`.

**Why is `effort` mandatory on every dispatch?**
Without it a subagent inherits the session's effort, which is usually higher than the task needs. Choosing effort per dispatch is
the cheapest lever available. See [dispatch-line.md](dispatch-line.md).

**Can I trust the cost numbers?**
The model and effort table comes from the public Artificial Analysis pages, with the date and source on the page. The spend shares
were measured on one user's panel and are given as proportions only. Your numbers will differ: [cost-map.md](cost-map.md),
section 5, shows how to measure your own.

**Does the orchestrator ever skip review?**
No. Anything with a factual or legal claim, a reference value, or a canonical record is checked by reopening the source, not by reading
the agent's write-up. See [architecture.md](architecture.md), section 6.3.
