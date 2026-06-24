---
paths:
  - "planning/**/*.md"
---

<!-- description: Single authority for the planning/ hub — folder map, blueprint suite catalog, manifest format, and PLAN.md format (incl. Non-goals/Invariants/Done-when/BLOCKED) -->

# Planning Format

This rule is the single authority for everything under `planning/`. It defines the
folder map, the blueprint document suite (project inception), and the `PLAN.md` format
(project execution). Skills drive the procedures (`/blueprint`, `/plan-writing`,
`/phase-executor`); this rule defines the **format** they must produce.

## The `planning/` hub

```
planning/
├── blueprint/      foundation document suite (project inception) — see §A
│   └── MANIFEST.md
├── specs/          single-feature specs written mid-project by the architect agent
├── bitacora/       session journals (YYYY-MM-DD.md) — format owned by bitacora/SKILL.md
├── PLAN.md         the active execution plan — see §B
└── phase_NN_<name>.md   phase-specific plans (optional)
```

`specs/` format is owned by the `architect` agent; `bitacora/` by `bitacora/SKILL.md`.
This rule governs **§A blueprint** and **§B PLAN.md**.

---

## §A — Blueprint suite (project inception)

The blueprint is the **stable anchor** generated once, before coding, by `/blueprint`
(which delegates each document to the `blueprinter` agent). Documents are processed in
filename order; `09_implementation_plan.md` is always last and seeds `PLAN.md`.

### Document catalog

**CORE — every project kind (3 documents):**

| File | Required sections |
|---|---|
| `00_charter.md` | Goal · Stakeholders · Success criteria (measurable) · **Non-goals** · **Invariants** · Constraints (time/compute/data/budget) · Open questions |
| `01_context_interfaces.md` | External inputs (shape + source) · Outputs/artifacts · Integration points · Environment assumptions · Out-of-scope interfaces |
| `09_implementation_plan.md` | Goal · Phases (each with a **Done when:** line) · **Non-goals** (verbatim from Charter) · **Invariants** (verbatim from Charter) · Sequencing/dependencies · Risks |

**KIND PACK — `ml-research` (documents `02`–`04`):**

| File | Required sections |
|---|---|
| `02_problem_data.md` | Task definition · Dataset(s) (source, size) · Splits · Labels · Leakage risks |
| `03_method_experiments.md` | Approach/model · Baselines · Ablations · Hypotheses to test |
| `04_evaluation_protocol.md` | Metrics · Validation scheme · Success thresholds · Reproducibility (seeds, environment) |

**KIND PACK — `data-pipeline` (documents `02`–`04`):**

| File | Required sections |
|---|---|
| `02_source_sink_contracts.md` | Upstream schemas · Output schemas · SLAs · Volume/cadence |
| `03_pipeline_architecture.md` | Stages · Orchestration · Idempotency/retries |
| `04_data_quality_validation.md` | Checks · Expectations · Failure handling · Lineage |

**Kind `other` (or the `--core` flag on any kind)** → CORE documents only (`00`, `01`, `09`).

### Mandatory anti-drift sections

- `00_charter.md` and `09_implementation_plan.md` **must** contain `## Non-goals` and
  `## Invariants`, and they must be specific (not "TBD").
  - **Non-goals**: things the project will explicitly NOT do (prevents feature invention).
  - **Invariants**: things that must always hold — the core goal, the chosen architecture,
    inviolable constraints (prevents the project becoming something else).
- The Implementation Plan copies both **verbatim** from the Charter so it is self-contained
  for `/plan-writing` to lift into `PLAN.md`.
- An approved Invariant may be amended only via a logged manifest decision **and** a fresh
  approval gate — never silently.

### Manifest format (`planning/blueprint/MANIFEST.md`)

The manifest is the loop's on-disk state — `/blueprint` resumes from it.

```markdown
# Blueprint Manifest

Kind: ml-research
Started: YYYY-MM-DD

## Documents
- [ ] 00_charter.md
- [ ] 01_context_interfaces.md
- [ ] 02_problem_data.md
- [ ] 03_method_experiments.md
- [ ] 04_evaluation_protocol.md
- [ ] 09_implementation_plan.md

## Decisions
- YYYY-MM-DD: kind = ml-research (excludes UX/flow docs)
```

Document markers:

| State | Marker | Meaning |
|---|---|---|
| Pending | `[ ]` | Not started |
| In progress | `[>]` | Currently being drafted/interviewed |
| Approved | `[x]` | User-approved — append `(approved YYYY-MM-DD)` |
| Blocked | `[!]` | Hard stop — append `(BLOCKED YYYY-MM-DD: reason)`; do not skip ahead |
| Discarded | `~~strikethrough~~` | Document dropped (rare — e.g. a kind change removed it); append `(discarded YYYY-MM-DD: reason)` |


---

## §B — PLAN.md format (project execution)

`PLAN.md` is the execution projection of the blueprint. When
`planning/blueprint/09_implementation_plan.md` exists, `/plan-writing` seeds `PLAN.md`
from it (carrying Non-goals and Invariants verbatim).

### File format

```markdown
# <Project or Phase Name>

## Goal
One sentence. What does this plan accomplish?

## Stack (only in PLAN.md)
Simple table: Layer | Technology

## Structure (only in PLAN.md)
Folder tree showing key paths and their purpose.

## Non-goals
- Explicitly NOT doing X (carried verbatim from the blueprint Charter).

## Invariants
- Must always hold: <core goal / architecture constraint that must never be violated>.

## Phases

### Phase N — <Name>
Done when: <one-line, verifiable acceptance criterion for the whole phase>
- [ ] Task description (file or module it targets)
- [>] Task in progress (being worked on right now)
- [x] Task completed (YYYY-MM-DD)
- [!] Task blocked (BLOCKED YYYY-MM-DD: reason)
- ~~Discarded task description~~ (discarded YYYY-MM-DD: short reason)

### Phase N+1 — <Name>
Done when: ...
- [ ] ...

## Conventions
Short bullet list of naming rules or constraints relevant to this plan.
```

### Writing rules

- Use plain Markdown only. No HTML, no frontmatter, no badges.
- Tasks use `- [ ]` checkboxes. One task = one action.
- Each task should name the file or module it targets.
- No sub-tasks, no nested checkboxes. Keep it flat.
- No status tables, no emoji columns, no progress bars.
- Avoid vague tasks like "improve X" or "refactor Y". Be specific.
- Phases must be independent — a phase should not depend on assumptions from another phase unless explicitly stated.
- Every phase has exactly one `Done when:` line — a verifiable criterion (`/phase-executor`
  treats it as the phase's acceptance target alongside the verification gate).
- `## Non-goals` and `## Invariants` are required in `PLAN.md`; if a blueprint exists they
  are copied verbatim from it, otherwise authored with the user.

### Task states

| State | Marker | Format |
|---|---|---|
| Pending | `- [ ]` | `- [ ] Task description` |
| In progress | `- [>]` | `- [>] Task description` (being worked on right now) |
| Completed | `- [x]` | `- [x] Task description (YYYY-MM-DD)` |
| Blocked | `- [!]` | `- [!] Task description (BLOCKED YYYY-MM-DD: reason)` |
| Discarded | `~~strikethrough~~`, no checkbox | `- ~~Task description~~ (discarded YYYY-MM-DD: reason)` |

These markers match the blueprint manifest's (§A) so the whole `planning/` hub speaks one
language: `[ ]` pending · `[>]` in progress · `[x]` done/approved · `[!]` blocked. (`~~…~~`
discarded applies to plan tasks; the manifest rarely drops a document.)

### Update rules

- **In-progress tasks**: mark the task you are actively working on `- [>]`, and flip it to
  `- [x]` the moment it's done. Keep at most one `[>]` task per phase — it shows, at a glance
  and in git history, what is being worked on right now. (In the autonomous loop, phases are
  atomic, so `[>]` may be brief or skipped; it matters most for human-paced work.)
- Mark completed tasks as `- [x]` immediately after finishing them.
- **Blocked tasks**: when a task cannot proceed (missing dependency, unresolved decision,
  failing precondition), mark it `- [!] ... (BLOCKED YYYY-MM-DD: reason)` and surface it to
  the user. A blocked task is a **hard stop signal** — do not silently skip or improvise
  around it. It is the loop-safe state that keeps automation from drifting.
- **Discarded tasks**: when a task becomes obsolete (project pivoted, scope cut, approach
  abandoned, replaced), do **not** delete it. Drop the checkbox, wrap the description in
  `~~...~~`, and append `(discarded YYYY-MM-DD: reason)`.
- Reasons for discarding/blocking must be specific. Examples:
  - `(discarded 2026-04-25: scope creep, moved to Phase 5)`
  - `(discarded 2026-05-02: experiment failed, see planning/bitacora/2026-05-02.md)`
  - `(BLOCKED 2026-05-03: source schema unconfirmed, awaiting vendor)`
- The bitácora's `Errors` section captures the **detail**; `PLAN.md` preserves the **public
  record** that the option was considered and dropped/blocked.
- Do not delete tasks, ever — completed, blocked, discarded, or pending.
- Do not add new tasks to a phase without user approval.
- Never change a stated Non-goal or Invariant without explicit user approval (they are the
  drift anchor; silently altering them defeats the whole point).
- If a phase is fully completed (all tasks `[x]` or discarded), add `(COMPLETED)` to the title.
- Never rewrite or reformat existing content — only update task states and phase titles.

## Foundation gap report (the return signal)

When the foundation is insufficient — caught by the §A step-5 coherence check, or by a
Loop 2 `BLOCKED` that traces to a weak plan rather than a code bug — the return to planning
is **not** a bare "blocked, your turn". It carries a structured report so the decision is
informed. The agent **diagnoses and proposes; the user decides** (never auto-applied — the
choice defines the project and is the anti-drift gate).

Report format (present to the user; log a one-line pointer in the manifest Decisions):

```markdown
### Foundation gap — <short title>
- **Where**: phase N / doc 0X / Invariant "<…>"
- **Gap**: what is missing, undefined, or contradictory (concrete, not vague).
- **Why it blocks**: the consequence of proceeding as-is.
- **Options**:
  1. <recommended> — tradeoff / cost
  2. <alternative> — tradeoff / cost
  3. <alternative> — tradeoff / cost
- **Decision needed**: the one question only you can answer.
```

Rules: always give at least two options with the recommended one first; never pick for the
user; never proceed past the gap until the user chooses. If the agent genuinely sees no
viable option, say so explicitly rather than inventing one.

## Cross-references

- See `blueprint/SKILL.md` and `blueprinter` agent for generating the §A suite.
- See `plan-writing/SKILL.md` for the procedure to create/seed and update `PLAN.md`.
- See `phase-executor/SKILL.md` for phase execution (reads Non-goals/Invariants, honors Done-when/BLOCKED).
- See `bitacora/SKILL.md` for session logging that feeds into plan updates.
