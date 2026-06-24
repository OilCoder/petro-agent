---
name: plan-writing
description: >
  Write or update the project work plan.
  Use when the user says "write the plan", "update the plan",
  "what's left to do", "create the project phases".
argument-hint: "[phase or context]"
allowed-tools: Read Write Edit Bash(git log:*) Bash(ls:*) Bash(date:*) Grep Glob
---

# Plan Writing

Write or update the work plan in `planning/PLAN.md`.
Follow the format defined in `planning-format.md` rule.

## Pre-rendered context

- **Date**: !`date +%Y-%m-%d`
- **Recent commits (last 14 days)**:
```!
git log --since="14 days ago" --format="%h %ad %s" --date=short 2>/dev/null | head -n30 || echo "(no git history)"
```
- **Current PLAN.md** (if it exists):
```!
[ -f planning/PLAN.md ] && cat planning/PLAN.md || echo "(no PLAN.md yet — needs to be created)"
```
- **Bitácora files in planning/**:
```!
ls -1 planning/bitacora/*.md 2>/dev/null | tail -n5 || echo "(no bitácora files yet)"
```
- **Pending items from latest bitácora**:
```!
LATEST=$(ls -1t planning/bitacora/*.md 2>/dev/null | head -n1); [ -n "$LATEST" ] && grep -E "^- \[ \]" "$LATEST" || echo "(no pending items found)"
```
- **Blueprint implementation plan** (if the project was blueprinted):
```!
[ -f planning/blueprint/09_implementation_plan.md ] && cat planning/blueprint/09_implementation_plan.md || echo "(no blueprint — plan authored from scratch)"
```

## Procedure

### 1. Check current state

The pre-rendered context above provides the recent commits, the existing PLAN.md,
and any pending items from the latest bitácora. Use it directly — do not re-run
those commands.

### 2. Create or update the plan

- If `planning/PLAN.md` does not exist, create it using the template from `planning-format.md`.
- If it exists, update by:
  - Marking completed tasks with `- [x] (YYYY-MM-DD)` using the pre-rendered date.
  - Promoting pending items from the bitácora to plan tasks (if they belong there).
- If `planning/` does not exist, create it.

### 3a. Seed from the blueprint (if one exists)

If `planning/blueprint/09_implementation_plan.md` exists (pre-rendered above), **seed**
`PLAN.md` from it instead of authoring from scratch:

1. Lift each phase from the implementation plan into a `### Phase N — <Name>` block,
   carrying its **`Done when:`** line as the phase's acceptance criterion.
2. Copy the `## Non-goals` and `## Invariants` sections **verbatim** — do not paraphrase.
   They are the drift anchor; changing them requires explicit user approval.
3. Fill `## Goal`, `## Stack`, `## Structure` from the Charter / Context docs.
4. Show the seeded draft and wait for approval before saving.

### 3b. When creating a plan from scratch (no blueprint)

1. Ask the user for: goal, stack, rough phases, and — required — the project's
   **Non-goals** and **Invariants** (what it will NOT do, and what must never change).
2. Draft the plan following the format in `planning-format.md` (including a `Done when:`
   line per phase).
3. Show the draft and wait for approval before saving.
4. Save only to `planning/` once approved.

## Rules

- **Flat checkboxes**: no nesting, one level of depth maximum.
- **Independent phases**: each phase is understandable without reading the others.
- **Mark immediately**: when a task is completed, mark `[x]` with today's date.
- **Never delete tasks**: completed, blocked, and discarded tasks remain visible.
- **Five states** (per `planning-format.md`, same markers as the blueprint manifest):
  - Pending: `- [ ] task`
  - In progress: `- [>] task` — being worked on right now (at most one per phase)
  - Completed: `- [x] task (YYYY-MM-DD)`
  - Blocked: `- [!] task (BLOCKED YYYY-MM-DD: reason)` — hard stop, surface to user, never skip
  - Discarded: `- ~~task~~ (discarded YYYY-MM-DD: reason)` — no checkbox, strikethrough, reason required
- **Non-goals / Invariants required**: `PLAN.md` must carry `## Non-goals` and `## Invariants`
  (verbatim from the blueprint Charter if one exists). Never alter them without explicit user approval.
- **Discard, don't delete**: when a task becomes obsolete (pivot, scope cut, replaced),
  convert it to the discarded form. Always include the date and a specific reason.
  This preserves the record of what was considered and why it was dropped — part of
  the user's learning history.
- **Completed phases**: add `(COMPLETED)` to the phase title when all tasks are
  either `[x]` or discarded.
- **Brevity**: one line per task, no long explanations.
- If the user passes `$ARGUMENTS`, use it as context for creating/updating the relevant phase.

## Discarding tasks (procedure)

When pending items from the latest bitácora indicate a task is no longer relevant,
or the user signals a pivot:

1. Identify the affected task(s) in `PLAN.md`.
2. Convert each from `- [ ] ...` to `- ~~...~~ (discarded YYYY-MM-DD: <reason>)`.
3. Use today's pre-rendered date.
4. The reason must be specific (1 line). If the discard requires longer
   explanation, add an Errors entry to the bitácora and reference it from the
   reason: `(discarded 2026-04-29: see planning/bitacora/2026-04-29.md)`.
5. Never delete the task line. The strikethrough preserves it as a record.

## Relationship with bitácora

The pre-rendered context above already extracts pending items from the latest
bitácora. Promote each `- [ ]` line to a real plan task if it represents
ongoing work, and ignore it if it was an ephemeral note.
