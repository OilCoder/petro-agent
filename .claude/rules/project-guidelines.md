<!-- description: Project-level index of rules, skills, and enforcement strategy -->

# Project Guidelines

This file is the entry point for understanding the project's conventions.

## Four-layer enforcement model

The base operates on four complementary layers:

| Layer | Mechanism | What it does | Example |
|---|---|---|---|
| **Rules** (`.claude/rules/*.md`) | Advisory context loaded into Claude | Guides decisions during code generation | `code-style.md` tells Claude to use Step/Substep comments |
| **Skills** (`.claude/skills/*/SKILL.md`) | On-demand workflows invoked by Claude or user | Executes multi-step procedures consistently | `/checkpoint` runs plan + docs + bitácora + commit |
| **Agents** (`.claude/agents/*.md`) | Specialized assistants in fresh context | Reviews/designs without polluting main context | `code-reviewer` audits a diff before commit |
| **Hooks** (`.claude/settings.json`) | Deterministic shell commands fired on events | Guarantees actions regardless of Claude's state | `ruff check --fix` after every Edit/Write |

Rules guide. Skills orchestrate. Agents review or design in isolation. Hooks enforce.
A behavior critical for production correctness should land in the hardest layer that can express it.

## Rules index

| Rule | Scope | Purpose |
|---|---|---|
| `code-style.md` | Always loaded | Layout, naming, spacing, step/substep structure |
| `file-naming.md` | Always loaded | File naming conventions and execution order |
| `code-change.md` | Always loaded | Scope and safety of edits |
| `logging-policy.md` | Always loaded | Print and logging control |
| `verification.md` | Always loaded | Verification gate before declaring tasks complete |
| `delegation.md` | Always loaded | Decide between main session, subagent, or agent team |
| `memory-policy.md` | Always loaded | Differentiate bitácora (human) from MEMORY.md (Claude) |
| `commit-style.md` | Always loaded | Conventional Commits subset (9 prefixes) for git history |
| `project-guidelines.md` | Always loaded | Index of rules/skills/agents, enforcement model, validation modes |
| `doc-enforcement.md` | Source files (`paths:`) | Docstring requirements and standards |
| `docs-style.md` | Markdown files (`paths:`) | Markdown documentation format |
| `learning-style.md` | `aprendizaje/**/*.md` (`paths:`) | Study material standard (Explanation layer) |
| `planning-format.md` | `planning/**/*.md` (`paths:`) | Single authority for `planning/`: blueprint suite catalog, manifest, and PLAN.md format (Non-goals/Invariants/Done-when/BLOCKED) |

## Skills index

| Skill | Purpose |
|---|---|
| `/blueprint` | Scaffolding loop: generate the foundation document suite in `planning/blueprint/` before coding (base + new projects) |
| `/checkpoint` | Combined milestone workflow: plan + docs + bitácora + commit + (push/PR) |
| `/bitacora` | Register work session in `planning/bitacora/YYYY-MM-DD.md` |
| `/plan-writing` | Write and update project plans in `planning/` (seeds from blueprint if present) |
| `/phase-executor` | Read and execute a phase from `PLAN.md` in order, with verification gate |
| `/test` | Create test scripts for modules |
| `/investigate` | Create isolated debug scripts for investigation |
| `/document` | Generate documentation for a module (forked context) |
| `/doc-enforce` | Review and enforce docstrings on existing code (forked context) |
| `/study` | Capture project knowledge as atomic study notes in `aprendizaje/` (forked context) |
| `/setup` | Bootstrap a new project from the base template (base only) |

## Agents index

| Agent | Purpose |
|---|---|
| `code-reviewer` | Pre-commit review in fresh context — finds what the author missed |
| `security-reviewer` | OWASP-style vulnerability audit on uncommitted or recent changes |
| `architect` | Interview-driven spec writing for non-trivial features → `planning/specs/*.md` |
| `blueprinter` | Drafts one project-inception foundation document → `planning/blueprint/*.md` (driven by `/blueprint`) |
| `implementer` | Autonomous code writer for self-contained tasks; preloads code-style, verification, doc-enforcement rules |

## Hooks index

The base ships with these hooks in `settings.template.json`. `/setup` copies and customizes them.

| Hook | Event | Purpose |
|---|---|---|
| `statusline` | `StatusLine` | Show branch, dirty state, active phase, bitácora flag |
| `session-start-context` | `SessionStart` | Inject PLAN.md active phase, pending bitácora items, verification commands |
| `stop-suggest-checkpoint` | `Stop` | Suggest `/checkpoint` when work is unrecorded |
| Block `rm -rf` | `PreToolUse` / Bash | Prevent destructive deletes without explicit approval |
| Block force-push | `PreToolUse` / Bash | Prevent `git push --force` and `-f` |
| Block `git reset --hard` | `PreToolUse` / Bash | Prevent discarding uncommitted work |
| Block `--no-verify` | `PreToolUse` / Bash | Prevent skipping pre-commit hooks |
| `check-debug-isolation` | `PostToolUse` / Edit\|Write | Warn if `src/` imports from `debug/` |
| Linter/formatter (stack-specific) | `PostToolUse` / Edit\|Write | Auto-fix style on every save |

## Permissions allowlist

`settings.template.json` includes a `permissions.allow` list with safe read-only
commands pre-approved (git status/log/diff/show/branch, ls, cat, head, tail, wc, pwd,
date, echo, which, printf, mkdir -p). `/setup` adds stack-specific commands
(pytest, ruff, npm test, etc.) so Claude doesn't prompt for approval during routine work.

## Auto memory

Claude Code provides automatic memory at `~/.claude/projects/<project>/memory/MEMORY.md`.
The first 200 lines load at every session start. Per `memory-policy.md`:

- **MEMORY.md** is Claude's operational manual — build commands, gotchas, factual patterns.
- **Bitácora** (`planning/bitacora/YYYY-MM-DD.md`) is the user's narrative journal — actions, decisions, failures, learnings.

These are **not interchangeable**. Narrative goes to bitácora, factual operational
notes go to MEMORY.md. See `memory-policy.md` for the full boundary.

Maintenance: review MEMORY.md manually (via the `/memory` command) monthly or when it
exceeds 200 lines — merge duplicates and prune stale entries.

## Folder convention (minimum)

After `/setup`, only 5 folders exist. The base does not prescribe more:

```
.claude/         rules, skills, agents, hooks
planning/        planning hub (grows on demand):
  ├── blueprint/   foundation suite (/blueprint)
  ├── specs/       single-feature specs (architect)
  ├── bitacora/    session journals (/bitacora)
  └── PLAN.md      active execution plan
documentation/   code docs (target of /document)
aprendizaje/     study material (target of /study)
docs/            reserved for GitHub Pages landing
```

Other folders (`src/`, `pipeline/`, `tests/`, `data/`, `models/`, `experiments/`)
emerge as the project actually demands them. Path-scoped rules (`doc-enforcement.md`,
`docs-style.md`) already support `src/`, `lib/`, `app/`, and `pipeline/` shapes.

## Enforcement strategy

- Rules apply automatically to all code generated in this project.
- Skills are invoked on demand by the user or triggered by Claude when relevant.
- Hooks fire deterministically on tool events.
- When in doubt about a convention, check the specific rule file.

## Validation modes

| Mode | Description | Phase |
|---|---|---|
| `suggest` | Recommendations and warnings | Prototype / exploration |
| `warn` | Clear violations flagged but not blocking | Active development |
| `strict` | Enforcement with failures | Production / final |

Default mode: `suggest` (prototype phase — Fase 0, building the deterministic engine).
Promote to `warn` once the vetted petrophysical library is stable, `strict` for production reports.

## Progressive enforcement

- **Prototype phase**: `suggest` mode. Focus on speed, rules are advisory.
- **Development phase**: `warn` mode. Rules enforced, violations flagged.
- **Production phase**: `strict` mode. All rules enforced, no exceptions.

## Project structure

Only the 5-folder minimum exists today. The folders below appear as each phase of
`planning/PLAN.md` demands them — do not pre-create them.

```
.claude/          → rules, skills, agents, hooks, scripts
planning/         → PLAN.md (phase roadmap), blueprint/, specs/, bitacora/
documentation/    → code docs (target of /document)
aprendizaje/      → study material in Spanish, exported to Obsidian (/study)
docs/             → reserved for GitHub Pages
# Grown on demand:
src/              → vetted petrophysical engine + agents (created in Fase 0)
tests/            → pytest golden tests (created in Fase 0)
data/             → LAS files (Kansas/Schaben dev, VOLVE regression) — gitignored
debug/            → isolated debug scripts — always gitignored
outputs/          → reports, ledgers, cross-plots — gitignored
```

## Tech constraints

The non-negotiable design invariant overrides everything below:
**every number comes from tested deterministic code. The LLM only orchestrates,
selects, and writes prose — it never computes and never authors math at runtime.**

- **Runtime**: Python on WSL (devcontainer/Docker target).
- **LLMs (local, via Ollama)**: Qwen3:30b-a3b (main agent / writer); Llama3.1:8b
  (fast iteration + second model family for the adversarial reviewer, Fase 6).
  No cloud LLM in the report runtime.
- **I/O**: lasio (LAS files). **Numerics**: numpy.
- **Vetted petrophysics layer** (the project's core asset): own functions
  (Larionov→Vsh, density-neutron→PHIE, Archie→Sw), frozen + versioned + covered by
  pytest golden tests (physical bounds, monotonicity, dimensional checks, known
  analytic cases). The agent selects and parameterizes them; it never writes the equation.
- **Orchestration**: LangGraph state machine — deterministic, **not an LLM**.
- **Validators**: physical rules (numpy) + lithology cross-plots (matplotlib).
- **Traceability**: JSON ledger; pin model/library versions, config hash, seeds.
- **Dev data**: Kansas/Schaben (Paleozoic → Larionov *old rocks*, not Tertiary).
  Regression benchmark (Fase 8): VOLVE (Equinor).

## Verification commands

Required by `verification.md`. Numbers on the quantitative path are only trusted
when their golden tests pass — verification is not optional in this project.

```text
test:        pytest -q
type-check:  mypy src/
lint:        ruff check .
format:      ruff format --check .
```

## Policies

If the project uses immutable principles (e.g., KISS, fail-fast, no-overengineering),
place them in `.claude/policies/` as separate files.

- Policies provide philosophical guidance; rules provide verifiable conventions.
- Policies are optional — not every project needs them.
