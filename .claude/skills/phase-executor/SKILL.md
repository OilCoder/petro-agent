---
name: phase-executor
description: >
  Read and execute a phase from the project plan in order.
  Use when the user says "execute the phase", "work on phase N",
  "implement phase N", "run phase", or references a phase by name or number.
argument-hint: "[phase number or name]"
allowed-tools: Read Write Edit Bash Bash(date:*) Bash(git:*) Grep Glob
---

# Phase Executor

Read `PLAN.md`, present an execution plan, wait for approval, and execute
the phase's tasks in order, updating checkboxes as each one is completed.

## Pre-rendered context

- **Date**: !`date +%Y-%m-%d`
- **Branch**: !`git branch --show-current 2>/dev/null || echo "(not a git repo)"`
- **PLAN.md**:
```!
[ -f planning/PLAN.md ] && cat planning/PLAN.md || echo "(no PLAN.md found — run /plan-writing first)"
```
- **Project guidelines (verification commands and tech constraints)**:
```!
[ -f .claude/rules/project-guidelines.md ] && sed -n '/## Verification commands/,/^## /p' .claude/rules/project-guidelines.md || echo "(no project-guidelines.md found)"
```

## Before writing any code

1. The PLAN.md is already pre-rendered above. Identify the requested phase from `$ARGUMENTS` and extract its task list **and its `Done when:` line**.
2. **Drift check (anti-drift gate)**: read the `## Non-goals` and `## Invariants` sections
   of `PLAN.md`. If any task in this phase would violate a Non-goal or an Invariant, **stop
   and ask the user** — do not code around it, do not silently re-interpret the task. The
   Non-goals/Invariants are the project's anchor; honoring them is what keeps execution from
   drifting into a different project.
3. Present a short plan to the user:
   - Files to create or modify
   - Order of execution
   - The phase's `Done when:` acceptance criterion
   - Any ambiguity that needs user input
4. **Wait for explicit user approval** before proceeding.

## Execution rules

### Scope

- Only create or modify files listed in the phase tasks.
- Never touch files from other phases.
- If a required file from a previous phase is missing, or a task cannot proceed (unresolved
  dependency, failing precondition), **do not improvise around it**: mark the task
  `- [!] ... (BLOCKED YYYY-MM-DD: reason)` per `planning-format.md`, stop, and surface it to
  the user. A blocked task is a hard stop, never a silent skip.

### Order

- Execute tasks in the order they appear in `PLAN.md`.
- **Skip discarded tasks** (those in `~~strikethrough~~` form) — they are part of
  the historical record but are not active work.
- Complete each task fully before moving to the next.
- Mark the task you start as `- [>]` (in progress), and flip it to `- [x]` immediately after
  completing it. This keeps `PLAN.md` showing live progress. (In the autonomous loop the
  step is atomic, so `[>]` may be momentary.)
- If a task becomes obsolete during execution (e.g., a previous task made it
  redundant), do **not** silently skip — instead, propose discarding it to the
  user and mark it per `planning-format.md` (`~~task~~ (discarded YYYY-MM-DD: reason)`).

### Code

- Follow all rules in `.claude/rules/`.
- Apply the project's style, naming, and logging conventions.
- Respect `doc-enforcement`: docstrings on all public functions.

### Conventions

- Project-specific conventions are respected per `project-guidelines.md`.
- Do not assume conventions — read them from the guidelines file.

## Before completing the phase — verification gate

Per `verification.md`, a phase must not be marked `(COMPLETED)` until its
result has been verified. Before declaring the phase done:

1. **Check the phase's `Done when:` criterion** — it is the phase's acceptance target.
   The phase is not complete until that criterion is demonstrably met.
2. Read `project-guidelines.md` to find the project's verification commands
   (under **Tech constraints** or referenced from `package.json` /
   `pyproject.toml`).
3. Run the relevant subset for the type of change:
   - Code changes → test command (`pytest`, `npm test`, etc.)
   - Type-annotated code → type checker (`mypy`, `tsc --noEmit`)
   - Always → linter and formatter on the changed files
4. If the `Done when:` criterion is unmet or any verification fails:
   - Do **not** mark the phase complete.
   - Address the root cause, not the symptom.
   - Re-run the verification.
5. If no verification command exists for this type of change, say so
   explicitly in the report instead of claiming verified.

## After completing the phase

1. Mark the phase title as `(COMPLETED)` in `PLAN.md` — only after the
   verification gate above has passed.
2. Report to the user:
   - Files created
   - Functions implemented
   - Decisions made during execution
   - Verification commands run and their outcome
3. Flag anything that needs user review before starting the next phase.
4. If the `/bitacora` skill is available, suggest logging the session.

## Loop mode (non-interactive)

When invoked by the autonomous loop (`.claude/scripts/promptloop.sh`) — signalled by a
prompt that says **"NON-INTERACTIVE LOOP MODE"** — behave exactly as above with these
differences. The loop runs one fresh `claude -p` per phase, so there is no human in the
turn to approve.

- **Skip the human approval gate only.** Do not wait for "Before writing any code → wait
  for approval"; proceed on the **first** non-completed phase. Every other gate stays:
  the drift check, the verification gate, and the `Done when:` criterion are all mandatory.
- **The automated gates replace the human.** They are the only thing standing in for your
  judgment now — never weaken or skip them to "make progress".
- **On success**: mark the phase `(COMPLETED)` and create exactly **one** conventional
  commit for the phase. One phase = one commit (the loop relies on HEAD advancing).
- **On any block** — ambiguity, a missing dependency, a Non-goal/Invariant conflict, or a
  failing verification you cannot fix at the root — **stop**: mark the affected task
  `- [!] ... (BLOCKED YYYY-MM-DD: reason)` and do **not** commit partial or unverified work.
  The loop detects the BLOCKED marker and halts for human review.
- **Never guess, never improvise, never partial-commit.** A clean BLOCKED stop is always
  preferable to drifting. The loop's safety depends on you failing loudly, not quietly.
- **Foundation gaps return to Loop 1 — with a diagnosis, not a shrug.** If a task is blocked
  because the *plan itself* is insufficient (a phase whose `Done when:` can't be met as
  specified, a missing decision the blueprint never settled, a requirement that contradicts an
  Invariant), do not code around it. Emit a **Foundation gap report** (format in
  `planning-format.md`: where · gap · why it blocks · 2-3 remediation options with a
  recommendation · the decision needed), set the BLOCKED reason to point at it, and stop so
  the user can decide and return to the planning loop (`/blueprint` step 5 or `/plan-writing`).
  Diagnose and propose alternatives; never choose for the user. This is the feedback edge that
  keeps execution from drifting off a weak plan.

