# Operational Architecture for AI Agents

## Governable, verifiable, adaptable

This architecture organizes agents that research, analyze, write, code, or take part in specialized workflows. The goal is not a pretty org chart. It is correct, auditable, safe deliverables without turning every task into bureaucracy.

The core principle:

> Instruction defines intent; contract defines the interface; permission limits the action; evidence supports the claim; validation decides whether the deliverable may move forward.

Markdown files are a guidance layer. They do not replace tool isolation, access control, tests, logs, or human decisions on sensitive work.

swarmtier implements the cost and quota half of this architecture (dispatch, effort, swarm, cache, lessons). See [dispatch-line.md](dispatch-line.md), [cost-map.md](cost-map.md) and [scenarios.md](scenarios.md). This document is the governance half.

---

## 1. Design decisions

### 1.1. Separate four documentation responsibilities

| Layer | Question | Canonical artifact | Must not contain |
|---|---|---|---|
| Local policy | Which rules apply in this scope? | INSTRUCTIONS.md | Task tutorials |
| Topology | Who does what and how does the flow connect? | AGENTS.md | Long personas |
| Role | What is this agent's mission, contract, authority, and limit? | agents/<name>.md | Long step-by-step procedures |
| Procedure | How is a repeatable capability executed? | skills/<name>/SKILL.md | Org charts |

The README explains the product; configuration wires the runtime; schemas make boundaries verifiable; data and logs hold state. Alternative names (SOUL.md, framework YAML) are runtime adapters, not a second source of truth.

### 1.2. Precedence and discovery

An architecture fails when instructions from different scopes collide. Declare an explicit order:

1. platform/runtime policy and constraints;
2. direct user instruction;
3. the project's security, privacy, and compliance policies;
4. the INSTRUCTIONS.md closest to the artifact;
5. the applicable AGENTS.md;
6. the agent profile;
7. the triggered skill;
8. preference, memory, and example.

If two instructions of the same priority are materially incompatible, the agent does not silently pick one: it marks the task as blocked or asks the owner for a decision. Local files may specialize rules for child directories, never weaken a higher rule.

### 1.3. Minimal architecture before full architecture

Start with the smallest structure that ensures quality:

~~~text
project/
  INSTRUCTIONS.md
  AGENTS.md
  skills/
    <capability>/SKILL.md
  outputs/
~~~

Add agent profiles when real specialization exists. Add schemas, run records, state, and independent validation when there is persistence, external integration, parallelism, high impact, or an audit need.

Do not create an agent just because a task has a name. A new capability is usually a skill; a new rule belongs in policy; new data belongs in a schema; a new agent requires its own operational boundary.

---

## 2. Operating model

### 2.1. Control roles, not fixed job titles

A simple project can run with a single agent. When needed, distribute the roles below. They can be distinct agents or temporary responsibilities, as long as the authority of each step is clear.

| Role | Decides | Produces | Does not do by default |
|---|---|---|---|
| Orchestrator | path, dependencies, escalation, completion | plan and consolidation | mask specialized work |
| Specialist | domain analysis, collection, or transformation | domain artifact | approve its own critical output |
| Validator | whether evidence, calculation, and contract meet the criterion | validation report | silently fix or complete |
| Curator | form, readability, fit to the request | formatted deliverable | change a material conclusion |
| State manager | changes to the canonical record | versioned update | infer facts without evidence |
| Human approver | exceptions, publication, external impact, material ambiguity | recorded decision | hand off final responsibility without review |

Avoid splitting curation from orchestration when the deliverable is simple. Avoid merging specialist and validator when a failure could cause damage, cost, external publication, a financial decision, a legal claim, or an irreversible change.

In swarmtier the mapping is: the **orchestrator** is the main session (Opus); **specialists** are the `triage` (Haiku), `executor` (Sonnet) and `vision-reader` agents; the **validator** is the orchestrator reopening the source for anything high-risk, never the agent that produced it; the **human approver** is you.

### 2.2. Risk-based flow, not mandatory waterfall

The default flow:

~~~text
input → triage → minimal plan → execution → proportional validation
      → curation → publication check → delivery → retention/state
~~~

It is a decision tree:

| Class | Example | Minimum controls |
|---|---|---|
| Light | format supplied text; simple local refactor | self-check and review against the request |
| Factual | research, statistics, document comparison | identifiable source, claim tied to evidence, material validation |
| Sensitive | contracts, compliance rules, health, finance, security, production config, personal data | primary source when available, specialized validator, human gate on ambiguity |
| External/irreversible | publish, send, buy, delete, alter the canonical record | explicit, prior, recorded authorization |

A task does not become more reliable just by passing through more agents. It becomes reliable when control is proportional to real risk.

### 2.3. Acceptance criteria before execution

For medium or critical tasks, the orchestrator defines up front:

- outcome and audience;
- limits, cutoff date, and scope;
- accepted input artifacts;
- definition of done;
- who owns each artifact;
- required validation;
- actions that require human approval;
- blocking condition and fallback.

This reduces rework and keeps "done" from meaning only "the model produced an answer".

---

## 3. Contracts, evidence, and state

### 3.1. Handoff contract

Use a formal contract at durable boundaries: between processes, between agents with persistent write access, when using external sources, for reviews, or on risky tasks. Ephemeral handoffs inside one execution can use a light version, but still must declare producer, consumer, and acceptance criterion.

~~~json
{
  "contract_version": "2.0",
  "run_id": "2026-01-15T15-40-22Z_8f9d",
  "task_id": "task_014",
  "parent_task_id": null,
  "status": "running",
  "producer": {"agent": "source-researcher", "version": "1.1.0"},
  "consumer": "domain-analyst",
  "objective": "Locate official evidence for the requested claims.",
  "acceptance_criteria": [
    "Every material claim has at least one locatable piece of evidence.",
    "Publication date and access date are recorded."
  ],
  "input_artifacts": [
    {"path": "runs/.../input/request.json", "sha256": "<hash>"}
  ],
  "output_artifacts": [],
  "claims": [],
  "evidence_refs": [],
  "warnings": [],
  "errors": [],
  "created_at_utc": "2026-01-15T15:40:22Z"
}
~~~

The real schema must validate required fields, formats, and allowed states. Never treat the example as a sufficient schema.

### 3.2. States and transitions

| State | Meaning | Allowed next step |
|---|---|---|
| queued | accepted, not started | running, cancelled |
| running | in progress | succeeded, partial, blocked, failed, cancelled |
| partial | useful part ready, gaps declared | running, needs_human_review, succeeded |
| blocked | depends on information, authorization, or a resource | queued, cancelled |
| needs_human_review | a material decision outside the agent's authority | queued, cancelled |
| succeeded | meets the acceptance criteria | archive/retain |
| failed | did not produce the needed output; cause recorded | queued, cancelled |
| cancelled | intentionally stopped | closed |

Status is not a confidence score. A result can be complete and still contain a moderately supported inference; that must show on the corresponding claim.

### 3.3. A claim is not evidence

A list of links does not show what it proves. For each material conclusion, record:

~~~json
{
  "claim_id": "c-03",
  "kind": "fact",
  "statement": "Verifiable statement in plain language.",
  "support_level": "high",
  "evidence_ids": ["ev-12"],
  "limitations": ["Valid until the stated cutoff date."]
}
~~~

And for each piece of evidence:

~~~json
{
  "evidence_id": "ev-12",
  "source_type": "official",
  "issuer": "issuing body",
  "canonical_url": "https://...",
  "published_at": "2026-01-01",
  "accessed_at_utc": "2026-01-15T15:40:22Z",
  "artifact_sha256": "<hash>",
  "locator": "page 4, paragraph 2",
  "excerpt": "the passage needed to support the claim",
  "validity": "current|superseded|unknown",
  "license_or_use_note": "when applicable"
}
~~~

Use support levels "high", "medium", "low", or "unclassified" only with written criteria. Never convert the model's feeling into decimal precision.

### 3.4. Per-run artifacts

~~~text
runs/<run_id>/
  manifest.json          # state, contract, versions
  events.jsonl           # append-only events
  input/                 # immutable copies or references
  evidence/              # captured source, metadata, hash
  intermediate/          # traceable transformations
  validation/            # reports and test results
  final/                 # deliverable-ready material
~~~

Raw data must be preserved or referenced immutably. Processed data must declare which input, transformation, procedure version, and agent produced it. In swarmtier, the delegation ledger (`core/ledger.py`) is the append-only event stream for dispatches.

---

## 4. Authority, writes, and concurrency

### 4.1. Permission matrix

Permissions must exist in the runtime, not only in the prompt. Adapt this matrix:

| Role | Read sources | Network | Write draft | Change canonical state | Publish / external action |
|---|---:|---:|---:|---:|---:|
| Orchestrator | yes | only if needed | plan and consolidation | no, unless explicitly delegated | no |
| Specialist | domain sources | per allowlist | execution artifact | no | no |
| Validator | input and evidence | exceptional | report | no | no |
| State manager | approved artifacts | no | versioned record | yes | no |
| Human | as needed | as needed | yes | yes | yes, when applicable |

Secrets do not enter prompts, manifests, or memory. The agent receives only the temporary capability it needs, through a vault or equivalent mechanism.

### 4.2. Effective single writer

For each canonical artifact, declare an owner. "Any specialist writes to data/" is not a single writer.

| Area | Authorized writer | Mode |
|---|---|---|
| raw sources | designated collector | append-only |
| canonical state | state manager | versioned change |
| final report | designated curator | after material approval |
| configuration/policy | human maintainer | explicit review |

Parallel agents write in separate execution spaces. Only the owner integrates a result into shared state, after validating the input version. This rule prevents lost updates and files with incompatible realities.

### 4.3. Idempotency and recovery

Every external job needs a stable identifier, timeout, retry policy, and error classification:

- recoverable: transient failure, rate limit, temporarily unavailable resource;
- not recoverable: missing credential, invalid schema, permission denied, nonexistent source;
- human: source conflict, missing authorization, material ambiguity.

A retry must not republish, resend, or rewrite an external effect. Before repeating, check the manifest or an idempotency key.

---

## 5. Memory, data, and privacy

### 5.1. Memory is curated context

Memory is not a database, chat history, or log. Separate:

~~~text
state/
  current.md             # readable, approved, short-lived summary
  decisions.jsonl        # append-only decisions and reversals
  registry/              # versioned canonical objects
data/
  raw/                   # original capture
  processed/             # traceable transformation
knowledge/               # curated sources and version
~~~

A memory update needs an owner, date, reason, and a reference to the evidence or decision. Hypothesis, fact, and user preference are different types; label them.

swarmtier's lesson engine follows this rule: a lesson is captured with its cause, stored append-only, and injected back into a later prompt only when it matches the task.

### 5.2. Personal data

Define the purpose before storing user data. Minimize collection, keep identifiers out of examples and logs, apply retention, and allow removal. Personal data must not be sent to another agent or service without need and authorization.

---

## 6. Sources and validation

### 6.1. Source policy

Each domain defines:

- hierarchy: primary, secondary, and internal sources;
- cutoff date;
- conflict rule;
- revalidation frequency or trigger;
- citation requirements;
- license and use restrictions.

If reliable sources disagree, the result records the conflict, each side's evidence, and why it does not synthesize a certainty that does not exist.

### 6.2. Quality gates

| Gate | Question | Failure produces |
|---|---|---|
| Contract | do input and output meet the schema and criteria? | failed or partial |
| Material | does evidence support the conclusions and calculations? | needs_human_review or rework |
| Curation | does the form preserve facts, caveats, and source? | rework |
| Publication | is the action authorized and, where possible, reversible? | blocked |

The validator reports problems with severity, locator, and return guidance. It does not change the content to make the output pass.

### 6.3. High-risk cases

For contract and compliance text, health, finance, security, and production configuration:

- use a primary source and the relevant version/date;
- reproduce the exact locator: article, page, item, paragraph, or record;
- treat ambiguity as human review;
- forbid silent changes to an invoice total, a medical dosage table, a calculation, official data, or a canonical record;
- keep the published original separate from adaptation or simulation.

A suspected error opens human review; it never automatically replaces the published value. Checking is done by reopening the source and comparing number by number against the cited line. Reading a well-written result is not validation: a wrong result with fluent justification is indistinguishable from a right one.

---

## 7. Recommended directory structure

~~~text
workspace/
  README.md
  INSTRUCTIONS.md
  AGENTS.md
  config/
    agent-registry.yaml
    permissions.yaml
  contracts/
    execution-envelope.schema.json
    evidence.schema.json
    <domain>.schema.json
  agents/
    orchestrator.md
    <specialist>.md
    validator.md
  skills/
    <capability>/SKILL.md
  policies/
    sources.md
    retention.md
  runs/
  state/
  data/
    raw/
    processed/
  knowledge/
  outputs/
  tests/
    fixtures/
    contracts/
    regression/
~~~

Projects from different domains should be isolated below this shared platform. Do not mix memory, sources, or policies between unrelated domains. Share only contracts, universal policies, and genuinely common tools.

---

## 8. When to create, merge, or remove an agent

Create an agent only if all, or nearly all, of these answers are "yes":

1. Is the responsibility separable and does it not fit in a skill?
2. Does the agent require its own context, tools, or permissions?
3. Do input and output have their own contract?
4. Is there a relevant risk of overlap or error without this boundary?
5. Is there a clear criterion to validate the result?
6. Is the coordination cost lower than the quality or parallelism gain?

If the answer is no, prefer a skill, a function, a schema, or a rule. Remove agents that never receive independent tasks, duplicate ownership, or add only a "second opinion" with no divergence criterion.

---

## 9. Testing and evaluation

An architecture is only trustworthy if its promises are tested.

| Level | What to verify |
|---|---|
| Schema | valid and invalid contracts; required fields; state transitions |
| Deterministic | calculations, transformations, scripts |
| Fixture | anonymized real sources or stable samples, including conflict and absence |
| Integration | handoff, ownership, retry, and blocking of unauthorized writes |
| Regression | representative tasks with acceptance criteria and expected results |
| Human | clarity, safety, usefulness, and decisions under ambiguity |

Version agents, skills, and schemas. A change in procedure or contract that alters results must trigger a regression test and a decision record.

Every check needs a positive control: a deliberately bad input the check must catch. A scan that returns zero on a broken pattern looks identical to a scan that returns zero on clean data.

---

## 10. Progressive adoption

### Phase 1: clarity

Write lean INSTRUCTIONS.md and AGENTS.md. Define owner, output, and limit for the most important flow.

### Phase 2: reliable repetition

Extract repeated procedures into skills with trigger, precondition, steps, result, and failures.

### Phase 3: real boundaries

Create agent profiles and contracts only at interfaces that need specialization, parallelism, or review.

### Phase 4: persistence and quality

Introduce a run manifest, hashed evidence, a single owner, schema validation, and fixtures.

### Phase 5: external automation

Before publishing, writing to a third-party service, or running an irreversible operation, implement human approval, idempotency, logs, and a recovery path.

---

## 11. Architecture acceptance checklist

### Governance

- [ ] Instruction precedence and the scope of each file are explicit.
- [ ] Each canonical artifact has an owner.
- [ ] Permissions are enforced by the runtime, not merely described.
- [ ] External and irreversible actions have a human gate.

### Operation

- [ ] The flow varies with risk and does not impose useless steps.
- [ ] Persistent handoffs have a versioned contract and acceptance criterion.
- [ ] States have transitions and a defined next step.
- [ ] Parallelism uses separate workspaces and controlled integration.

### Quality

- [ ] Material claims point to locatable evidence.
- [ ] Facts, inferences, and recommendations are not confused.
- [ ] Failures, conflicts, and uncertainty appear in the output.
- [ ] Proportional validation exists, with regression tests for relevant changes.

### State

- [ ] Raw data, processed data, memory, and logs are separate.
- [ ] Memory and state updates carry a reason and a reference.
- [ ] A privacy, retention, and personal-data removal policy exists.

---

## Summary

A good agent architecture is not a large set of personas. It is a system where:

~~~text
policy limits the scope
  → topology defines the path
  → contract makes the handoff verifiable
  → permission prevents improper action
  → evidence supports the conclusion
  → validation measures acceptance
  → owner preserves state
  → human decides what cannot be delegated
~~~

With this, agents can be small, specialized, and replaceable, and the system stays understandable when a source fails, a task is parallelized, or an answer must be audited.
