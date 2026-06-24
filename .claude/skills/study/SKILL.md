---
name: study
description: >
  Generate or update atomic study notes that capture the knowledge applied in the
  project — software AND domain (petroleum, geology, ML, data engineering, math).
  Produces didactic material with intuition, LaTeX formulas, Mermaid flowcharts, and
  verified bibliographic references. Use when the user says "study material", "explain
  this concept", "aprende esto", "material de estudio", "documenta el conocimiento",
  or after a phase introduces a new technique worth learning.
argument-hint: "[concept or module to capture]"
allowed-tools: Read Write Edit Bash(ls:*) Bash(date:*) Grep Glob WebSearch WebFetch
context: fork
agent: general-purpose
paths:
  - "aprendizaje/**/*.md"
---

# Aprende (Study Material)

Capture the knowledge applied in the project as **atomic study notes** in
`aprendizaje/`, following the `learning-style.md` rule. One note per concept,
written as didactic material the user can study and retain.

This is the **Explanation** layer. It is *not* `documentation/` (reference) and
*not* the bitácora (journal). See `learning-style.md` for the boundary.

## Pre-rendered context

- **Date**: !`date +%Y-%m-%d`
- **Existing study notes**:
```!
ls -1 aprendizaje/*.md 2>/dev/null || echo "(no aprendizaje/ notes yet)"
```
- **Recent changes (to detect new concepts)**:
```!
git diff --stat HEAD~3 HEAD 2>/dev/null | tail -n20 || echo "(no recent diff)"
```
- **Active phase from PLAN.md**:
```!
[ -f planning/PLAN.md ] && grep -E "^### Phase " planning/PLAN.md | grep -v "(COMPLETED)" | head -n1 || echo "(no PLAN.md)"
```

## Procedure

### 1. Identify the concept(s)

- If `$ARGUMENTS` names a concept or module, use it.
- Otherwise infer the concepts introduced by the recent diff / active phase —
  include **domain** concepts, not only code (e.g., a new petrophysical formula,
  a geological assumption, an ML technique, a data-engineering pattern).
- One note per concept (atomic). If several concepts appear, produce/​update one
  note each. State the list to the user before writing.

### 2. Check for an existing note

- If a note for the concept already exists in `aprendizaje/`, **update** it
  (extend, don't rewrite from scratch — preserve the user's edits).
- If not, create `aprendizaje/NN_<slug>.md` with the next free `NN`.
- If `aprendizaje/` does not exist, create it.

### 3. Draft the note per `learning-style.md`

Follow the required structure: Intuición → Formalismo (LaTeX) → Flujo (Mermaid) →
Contexto de dominio → Cómo se aplica en este proyecto (link to `src/...`) → Por qué
esto y no la alternativa → Autoevaluación → Referencias.

- **Intuición** and **Cómo se aplica en este proyecto** are mandatory.
- Write Spanish prose, English technical/domain terms (per `learning-style.md`).
- Add LaTeX for every formula and a Mermaid flowchart for any multi-step mechanism.
- Wikilink prerequisites: `[[NN_prerequisite]]`.

### 4. Verify references before citing them

Per `learning-style.md`, references must be **real**:

1. For each source you intend to cite, **search the web to confirm it exists**
   (WebSearch / WebFetch). Capture a stable identifier: DOI, ISBN, or official URL.
2. Include only verified sources. **Never invent** authors, titles, years, DOIs,
   or page numbers.
3. If a needed reference cannot be verified, write
   `> [referencia por confirmar: <what to search for>]` and flag it in the report —
   do not fabricate a plausible-looking citation.

### 5. Save and report

- Save to `aprendizaje/NN_<slug>.md`.
- Report to the user:
  - Note(s) created/updated (path)
  - Concept(s) captured and their domain
  - References verified (with identifiers) and any left "por confirmar"
  - Wikilinks added

## Rules

- **Atomic**: one concept per note. Do not bundle unrelated concepts.
- **Didactic, not reference**: teach the concept; do not describe code contracts
  (that belongs in `documentation/`).
- **All knowledge counts**: capture domain knowledge (petroleum, geology, etc.) as
  readily as code/ML knowledge — the goal is that *everything* in the project is
  understandable later.
- **Verified references only**: confirm a source is real before citing it; mark the
  unverifiable as "por confirmar" rather than inventing it.
- **Update, don't clobber**: when a note exists, extend it and keep prior content.
- **No fabrication**: every formula, claim, and citation must be correct. If unsure
  about a domain fact, say so rather than asserting it.

## Relationship with other skills

- `/document` writes **reference** docs to `documentation/` — complementary, not the same.
- `/checkpoint` calls this skill to capture the new concepts of a milestone.
- The bitácora records *what you did*; `/study` records *what to understand*.
