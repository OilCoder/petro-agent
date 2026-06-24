# petro-agent — Agente petrofísico autónomo

## Goal
Build, phase by phase, an autonomous multi-agent system that turns well logs (LAS)
into a defensible petrophysical report (Vsh, PHIE, Sw, cutoffs, net pay, zones,
conclusions) with no human in the per-report loop, full traceability, and
auto-calibrated confidence.

## Stack
| Layer | Technology |
|---|---|
| Language / runtime | Python on WSL (devcontainer/Docker target) |
| LLMs (local) | Ollama — Qwen3:30b-a3b (main/writer), Llama3.1:8b (fast + 2nd family) |
| Log I/O | lasio |
| Numerics | numpy |
| Vetted petrophysics | own functions (Larionov→Vsh, density-neutron→PHIE, Archie→Sw) |
| Orchestration | LangGraph state machine (deterministic, not an LLM) |
| Validators | numpy (physical rules) + matplotlib (cross-plots) |
| Traceability | JSON ledger (pinned versions, config hash, seeds) |
| Tests | pytest (golden tests) |

## Structure
```
src/        vetted engine + agents (grows from Fase 0)
tests/      pytest golden tests
data/       LAS files — Kansas/Schaben (dev), VOLVE (regression) — gitignored
outputs/    reports, ledgers, cross-plots — gitignored
planning/   this plan + bitacora/
```

## Non-goals
- Do NOT promise "always correct" reports — the promise is honest, calibrated confidence.
- Do NOT let any LLM compute numbers or author equations at runtime.
- Do NOT let agents author or choose their own validators/rubric at runtime.
- Do NOT automate the harness (vetted library, validators, regression set, gating
  rules) — those are built once, offline, by the expert.
- Do NOT build a human-in-the-loop demo (that was the earlier MVP scope).

## Invariants
- Every number on the quantitative path comes from frozen, version-pinned,
  golden-tested deterministic code. The LLM only orchestrates, selects, and writes.
- The orchestrator is a deterministic state machine, never an LLM.
- The validator harness is fixed, versioned, and external to the agents; they run it
  but never control which checks fire.
- The loop terminates on "only irreducible objections remain", never on "the critic
  has no objections".
- Every emitted number traces in the ledger to: input curves + function + version +
  parameters + provenance + validator results.
- Kansas/Schaben is Paleozoic → Larionov *old rocks*, never Tertiary.

## Phases

### Phase 0 — Deterministic engine (foundation)
Done when: given a Kansas LAS, `calc_vsh` and `calc_phie` produce correct, reproducible values with passing golden tests.
- [ ] Set up WSL repo + environment (devcontainer/Docker)
- [ ] Load a Kansas/Schaben LAS into a DataFrame with lasio (src/io)
- [ ] Implement `calc_vsh` (Larionov old rocks) (src/petrophysics)
- [ ] Implement `calc_phie` (density-neutron) (src/petrophysics)
- [ ] Golden tests: Vsh ∈ [0,1], PHIE ∈ [0,φmax], dimensional check, known analytic cases (tests/)
- [ ] Implement `calc_sw` (Archie) + its golden tests (src/petrophysics, tests/)

### Phase 1 — Data QC gate
Done when: no computation runs on unchecked data; a per-depth data-quality map is produced.
- [ ] Unit sanity checks (RHOB ~1.0–3.0 g/cc, etc.) (src/qc)
- [ ] Null and spike handling with logged edits (src/qc)
- [ ] Bad-hole masking via CALI/DCAL/bit size (src/qc)
- [ ] Per-depth data-quality map feeding the gating (src/qc)

### Phase 2 — Parameters with provenance
Done when: every parameter is emitted tagged with its provenance (core → offset → default).
- [ ] Config library with regional defaults (a, m, n, Rw, matrix density) (src/params)
- [ ] Provenance hierarchy: cores → offset → default (src/params)
- [ ] Each parameter labeled with its provenance (src/params)

### Phase 3 — Independent validators
Done when: the system detects and classifies its own problems (mechanical/support/irreducible).
- [ ] Physical bounds + cross-curve consistency checks (src/validators)
- [ ] Lithology cross-plots (neutron-density, M-N) → model-mismatch detection (src/validators)
- [ ] Objection typing: mechanical/physical · support · irreducible (src/validators)

### Phase 4 — Orchestrator + loop
Done when: the pipeline runs unattended and knows when to stop.
- [ ] Deterministic state machine (LangGraph) (src/orchestrator)
- [ ] compute→validate→correct loop, ends at "only irreducible objections" (src/orchestrator)
- [ ] Non-convergence circuit breaker (src/orchestrator)

### Phase 5 — Local LLM agents (Ollama)
Done when: the system generates a first prose report tied to the ledger.
- [ ] Compute agent (selects method/params from the vetted library) (src/agents)
- [ ] Writer (prose tied to the ledger, tone by confidence) (src/agents)
- [ ] Claim verifier (no sentence asserts more than the data supports) (src/agents)

### Phase 6 — Adversarial reviewer
Done when: generator and critic are decorrelated and objections route by type.
- [ ] Second agent in adversarial role (rewarded for finding faults) (src/agents)
- [ ] Decision (a): second local family (Llama) vs the writer's Qwen
- [ ] Loop integration: route objections by type (src/orchestrator)

### Phase 7 — Uncertainty + confidence
Done when: the report states its own auto-calibrated confidence.
- [ ] Decision (c): Monte Carlo propagation vs analytic ranges (src/uncertainty)
- [ ] Sensitivity analysis (which parameter dominates net pay) (src/uncertainty)
- [ ] Gating rules: firm / qualified / abstention (src/gating)
- [ ] Multi-seed robustness validator feeding the gating (src/gating)
- [ ] Decision (b): hard abstention?

### Phase 8 — Traceability + evaluation
Done when: the report is defensible months later and reproduces VOLVE within tolerance.
- [ ] Complete ledger (each number → curve + function + version + params + provenance + validators) (src/ledger)
- [ ] Pin versions, seeds, config hash (src/ledger)
- [ ] Regression against VOLVE: reproduces the accepted interpretation within tolerance (tests/regression)

## Conventions
- Code and comments in English; `snake_case`; petrophysical symbols keep domain names
  (`vsh`, `phie`, `sw`, `rhob`, `nphi`, `gr`, `rt`).
- Every quantitative function is frozen + golden-tested before any agent may call it.
- One task = one action; mark `[x]` with date on completion; never delete tasks.
- Parked design decisions (a)/(b)/(c) live in their phases — resolve, don't forget.
