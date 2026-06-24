---
name: blueprint
description: >
  Scaffolding loop that generates a project's foundation document suite BEFORE
  coding, so the project has a stable, drift-proof anchor. Human-gated: one
  document per iteration, you approve each before the next. Use at project start,
  or run again to resume an unfinished suite. Say "blueprint the project",
  "scaffold the foundation", "start the planning docs".
disable-model-invocation: true
argument-hint: "[ml-research | data-pipeline | other | --core]"
allowed-tools: Read Write Edit Bash(mkdir:*) Bash(ls:*) Bash(date:*) Grep Glob Task AskUserQuestion
---

# Blueprint

Generate the foundation document suite in `planning/blueprint/`, one document at a
time, each gated by explicit user approval. The suite is the **stable anchor** for the
whole project: its final document seeds `PLAN.md`. The format catalog (which documents
per kind, required sections, manifest format) lives in `planning-format.md` — this skill
is the **process** that drives it.

## Pre-rendered context

- **Date**: !`date +%Y-%m-%d`
- **Existing manifest** (if resuming):
```!
[ -f planning/blueprint/MANIFEST.md ] && cat planning/blueprint/MANIFEST.md || echo "(no blueprint yet — fresh start)"
```
- **Existing blueprint files**:
```!
ls -1 planning/blueprint/*.md 2>/dev/null || echo "(none)"
```

## Core principle: human-gated, state-on-disk

The loop never advances on its own. After each document is drafted you **stop and wait**
for explicit approval. Progress lives in `planning/blueprint/MANIFEST.md`, not in this
conversation — so the loop is resumable and cannot silently drift. This directly answers
the risk that an uncontrolled loop turns the project into something it wasn't meant to be.

## The 5-step planning cycle

This skill is **Loop 1** of the project. It is a 5-step cycle, not a straight line — code
(Loop 2) does not start until step 5 closes, and an insufficient foundation **returns** here
rather than being patched downstream.

| Step | Name | Fixes | Blueprint doc(s) |
|---|---|---|---|
| 1 | **Charter** | Why + what + Non-goals + Invariants + measurable success | `00_charter` |
| 2 | **Context & Interfaces** | Inputs, outputs, integrations, constraints | `01_context_interfaces` |
| 3 | **Design** | The technical "how" for the kind (method / architecture / data model) | `02–04` (pack) |
| 4 | **Implementation Plan** | Phases + `Done when:` | `09_implementation_plan` |
| 5 | **Validation & Seed** | Coherence check → seed `PLAN.md` → confirm the anchor holds | `PLAN.md` |

Steps 1–4 are the document loop below (§4). Step 5 is the coherence gate (§6). At step 5,
if any phase lacks a solid foundation (unanswered Open question, missing Non-goal/Invariant,
a phase with no verifiable `Done when:`, or a contradiction between docs), **return to the
weak step and re-interview that document** — do not proceed to code on a shaky anchor.

## Procedure

### 1. Determine the project kind

- If `$ARGUMENTS` names a kind (`ml-research`, `data-pipeline`, `other`), use it.
- If a manifest already exists, read its `Kind:` and **resume** — do not re-ask.
- Otherwise ask with `AskUserQuestion`: which kind? (`ml-research` / `data-pipeline` /
  `other`). `other` (or the `--core` flag on any kind) produces the **core docs only**.

### 2. Derive the document list

Read the catalog for this kind from `planning-format.md` (it defines the ordered document
list, each document's required sections, and the manifest format). The list is always:
the **core** docs (`00_charter`, `01_context_interfaces`, `09_implementation_plan`) plus,
unless `--core`/`other`, the kind's pack (`02`–`04`). Documents are processed in filename
order so `09_implementation_plan` is always last.

### 3. Ensure the manifest

```bash
mkdir -p planning/blueprint
```

If `planning/blueprint/MANIFEST.md` does not exist, create it per `planning-format.md`:
record `Kind:`, today's date (pre-rendered), and the full document checklist with every
entry `[ ]` pending. If it exists, use it as-is (resume).

### 4. The loop — one document per iteration

For the **first non-approved** document in the manifest (markers per `planning-format.md`:
`[x]` approved · `[>]` in progress · `[ ]` pending · `[!]` blocked):

1. Mark it `[>]` in the manifest.
2. **Delegate to the `blueprinter` agent** via `Task`. Pass it: the target filename and
   title, the document's required sections (from `planning-format.md`), the project kind,
   and the paths of all already-**approved** documents to read as context.
3. When the agent returns, **present the draft to the user and STOP**. Ask (plainly or via
   `AskUserQuestion`): **approve**, **revise**, or **stop**.
   - **Approve** → mark `[x] (approved <date>)` in the manifest, advance to the next document.
   - **Revise** → re-invoke the `blueprinter` for the same document with the user's feedback.
   - **Stop** → leave the document `[>]`, exit cleanly. Re-running `/blueprint` resumes here.
4. Repeat until `09_implementation_plan.md` is approved.

Never draft the next document before the current one is approved. Never auto-approve.

### 5. Blocked and scope-change conditions

- **Blocked**: if a document depends on something unresolved (e.g. a data schema not yet
  available), record it in that document's `## Open questions` and mark the manifest line
  `[!] (BLOCKED <date>: reason)`. A blocked document is a **hard stop** — do not skip
  ahead, because later documents depend on it. Surface it to the user.
- **Kind change mid-loop**: never re-scope silently. Stop, log the proposed change in the
  manifest's Decisions section, ask the user to confirm, then re-derive the remaining list.
- **Invariant change**: amend an already-approved Invariant only via a logged manifest
  decision **and** a fresh approval gate on the affected document.

### 6. Step 5 — Validation & Seed (close the planning loop)

This is the final step of the 5-step cycle. The planning loop does not end at the last
document — it ends at a **validated, seeded `PLAN.md`**. Code (Loop 2) cannot start before this.

When `09_implementation_plan.md` is approved:

1. **Coherence check** — before seeding anything, verify the foundation actually holds:
   - Every phase has a verifiable `Done when:` criterion.
   - `## Non-goals` and `## Invariants` exist and are specific (not "TBD").
   - No phase depends on an unanswered `## Open questions` item.
   - No contradiction between documents (e.g. a phase that violates a stated Non-goal).
   - **If any check fails → produce a Foundation gap report** (format in `planning-format.md`:
     where · gap · why it blocks · 2-3 options with a recommendation · the decision needed),
     present it, and **RETURN to the weak step** once the user chooses. Diagnose and propose
     options — never pick for the user. Log the return in the manifest's Decisions section.
     Do **not** proceed; a shaky anchor is exactly what makes Loop 2 drift later.
2. **Seed the plan**: run `/plan-writing` to create `planning/PLAN.md` from
   `09_implementation_plan.md` (carrying `## Non-goals` and `## Invariants` **verbatim**,
   and each phase's `Done when:`).
3. **Present the seeded `PLAN.md` and STOP for approval** — the final gate of the planning loop.
4. On approval, report that the anchor is ready and Loop 2 can now run:

   > Planning loop complete (5/5). The anchor (`PLAN.md` with Non-goals/Invariants/Done-when)
   > is ready. The autonomous coding loop can now run on a feature branch:
   > `bash .claude/scripts/promptloop.sh 5`

## Rules

- One document per iteration; explicit approval between each. No exceptions.
- The catalog and formats are defined once in `planning-format.md` — read them there,
  don't restate them. This skill owns the process, not the format.
- `planning/blueprint/` subfolders and the manifest are created at runtime, never by `/setup`.
- Delegate drafting to the `blueprinter` agent (fresh context) — keep this orchestration
  session lean across what may be a long, multi-document interview.
