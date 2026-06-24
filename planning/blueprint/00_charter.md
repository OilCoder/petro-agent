# Charter — petro-agent

## Goal

Build an autonomous multi-agent system that ingests well logs (LAS files) and
produces a defensible petrophysical report — covering Vsh, PHIE, Sw, cutoffs, net
pay, zones, and conclusions — with no human in the per-report loop. Every quantitative
result is computed by a frozen, version-pinned, golden-tested deterministic engine;
every emitted number traces to its input curves, function, version, parameters, and
provenance; and the report's expressed confidence is auto-calibrated and honestly
bounded by the data that exists. The system does not promise "always correct"; it
promises "always honest about how correct it is, and provably so".

## Stakeholders

| Role | Who | What they need from this project |
|---|---|---|
| Developer / portfolio owner | Carlos (OilCoder) | A working system that demonstrates autonomous AI engineering, petrophysical domain expertise, and production-grade reliability practices — visible to recruiters, potential clients, and technical peers |
| Technical peers / reviewers | Petrophysicists, ML engineers, potential collaborators reviewing the repo | Correct petrophysics (equations, parameter choices, Kansas formation considerations), sound ML/agent design, auditable ledger |
| Recruiters / clients | Non-technical or semi-technical evaluators | Evidence that the system is trustworthy (calibrated confidence, traceable ledger) — not just impressive-sounding |
| End-user persona (future) | Petrophysicist or operator consuming reports | A prose report with explicit confidence tiers, provenance-tagged parameters, and a ledger that lets them audit or defend the numbers months later |

## Success criteria (measurable)

All criteria must be met for v1 to be declared done.

### 1. End-to-end autonomy
An unattended run (no human interaction from LAS load to report emit) produces a
readable prose report and a complete, traceable ledger for a Kansas/Schaben well.

### 2. Quantitative correctness — VOLVE regression (Phase 8 pass/fail)
The pipeline's output on the VOLVE benchmark dataset must satisfy all four thresholds
against the accepted interpretation:

| Output | Threshold |
|---|---|
| PHIE | MAE < 0.03 (3 p.u.) |
| Vsh | MAE < 0.10 |
| Sw | MAE < 0.15 |
| Net pay | Within ±20% of the accepted net pay, per benchmark well |

Failure on any one threshold is a pipeline regression failure.

### 3. Confidence calibration — procedural (required from v1)
- Every report block carries a confidence tier assigned by parameter provenance:
  core-calibrated → firm; offset-derived → qualified; regional/global default →
  bracketed with the propagated range and the limitation stated.
- The writer's tone is bound to that tier by policy-as-code (the tier is not advisory;
  it gates what language the writer may use).
- The final claim-verifier passes: no sentence in the emitted report asserts more
  certainty than the ledger supports.

### 4. Confidence calibration — statistical (required from v1)
On the VOLVE benchmark, measure reliability / calibration using a reliability diagram
and Expected Calibration Error (ECE): when the system assigns a confidence level to a
result block, the observed accuracy on held-out VOLVE wells must match that stated
confidence level within a meaningful margin. Threshold is set during Phase 7 once the
calibration methodology is implemented; the infrastructure for measuring ECE is
required by v1.

### 5. Full ledger traceability
Every number in the emitted report traces in the ledger to: input curve(s) + function
name + function version + parameters + parameter provenance + validator results. A
spot-check of any emitted value must be resolvable to its deterministic source in O(1)
ledger lookup.

### 6. Golden test suite passing
All pytest golden tests on the vetted petrophysical engine pass on every run
(pytest -q exits 0). The test suite covers physical bounds, monotonicity,
dimensional correctness, and known analytic cases for calc_vsh, calc_phie, and
calc_sw.

## Non-goals

- **Not "always correct" reports.** The system does not promise correct results; it
  promises results whose confidence is honestly calibrated. A well with no core data
  and no offset calibration produces wide uncertainty ranges and explicit limitations,
  not a confident point estimate.
- **No LLM computing numbers or authoring equations at runtime.** No language model
  may produce a numerical result for the quantitative path, generate a petrophysical
  equation on the fly, or write code that executes on the quantitative path during a
  report run.
- **No agents choosing or authoring their own validators or rubric at runtime.** The
  checklist, validator suite, and gating rules are a versioned artifact built offline
  by the expert. Agents execute the harness; they do not control which checks fire or
  author new ones during a run.
- **No automating the offline harness.** The vetted petrophysical library, the
  validator suite, the regression benchmark, and the gating rules are human-authored
  once, offline. That process is explicitly not part of the runtime system.
- **Not a human-in-the-loop demo.** The earlier MVP (agente-llm-registros) explored
  human-validated agent interaction. This project is the autonomous, per-report
  hands-off system. Interactive or human-gated workflows are out of scope.
- **No cloud LLM in the report runtime.** All inference during a report run uses local
  models via Ollama. Cloud LLM access at report time is not a design option.
- **No third-party petrophysical library for the core equation layer.** The thin layer
  of Larionov, density-neutron PHIE, and Archie equations is authored in-project for
  full ledger transparency. Using a black-box third-party library that hides equation
  variants or null-handling is excluded.

## Invariants

These must hold throughout every phase. Amending any invariant requires a logged
manifest decision and an explicit approval gate — never a silent change.

1. **Every number on the quantitative path comes from frozen, version-pinned,
   golden-tested deterministic code.** The LLM only orchestrates, selects, and writes
   prose. It never computes and never authors math at runtime.

2. **The orchestrator is a deterministic state machine (LangGraph), never an LLM.**
   The orchestrator owns the pipeline loop, the gating compuertas, and the termination
   condition. No language model decides whether to skip a QC step.

3. **The validator harness is fixed, versioned, and external to the agents.** Agents
   execute validators from the frozen harness; they have no write access to the
   harness and cannot choose which checks fire.

4. **The loop terminates on "only irreducible objections remain", never on "the critic
   has no objections".** The termination predicate is typed objection exhaustion, not
   LLM agreement. A loop that tries to resolve a genuinely data-limited objection must
   be circuit-broken, not satisfied by prose rewriting.

5. **Every emitted number traces in the ledger** to: input curves + function name +
   function version + parameters + parameter provenance + validator results. Ledger
   completeness is a gating condition for report emission, not a post-hoc artifact.

6. **Kansas/Schaben data is Paleozoic (old rocks) — Larionov old-rocks formula,
   never Tertiary.** Applying the wrong Larionov variant is exactly the model-mismatch
   class this system is designed to detect; it must not commit it internally.

7. **The system degrades honestly, not silently.** If a required method is unavailable,
   execution falls to the nearest valid method and the degradation is recorded in the
   ledger. No silent fallback, no invented precision.

## Constraints (time / compute / data / budget)

### Time
Part-time development; no hard deadline. The 9-phase roadmap is the pacing structure.
Each phase delivers a verifiable artifact before the next begins.

### Compute / hardware
- Hardware ceiling: approximately 16 GB VRAM GPU (WSL + GPU passthrough target).
- Qwen3:30b-a3b (MoE architecture) must run quantized (e.g., Q4_K_M or equivalent)
  to fit within ~16 GB VRAM. This is a binding constraint on model selection,
  quantization level, and per-run latency. If a model variant does not fit, it is not
  a viable option regardless of quality.
- Llama3.1:8b fits comfortably within this ceiling and is the preferred fast-iteration
  and adversarial-reviewer candidate.
- Runtime environment: Python on WSL; devcontainer / Docker is the target
  reproducibility envelope.

### LLMs
- All LLM inference in the report runtime is local via Ollama. No cloud LLM calls
  during report generation.
- Primary agent / writer: Qwen3:30b-a3b (quantized). Secondary / adversarial
  reviewer candidate: Llama3.1:8b (second model family for decorrelation).

### Data
- Development data: Kansas / Schaben dataset (Paleozoic, quality known, zero
  acquisition friction). Hard-required curves (absence rejects the file): GR, RHOB,
  NPHI, RT. Caliper curves (CALI, DCAL) are optional — used for bad-hole masking when
  present; when both are absent the masking degrades honestly and the affected
  computations are tier-downgraded (see `03_source_sink_contracts.md`). DT
  (compressional slowness) and PEF (photoelectric factor) are also accepted optional
  curves, reserved for the Phase 3 M-N / lithology cross-plots and not on the v1
  quantitative path.
- Regression / benchmark (Phase 8): VOLVE (Equinor open dataset), which carries an
  accepted petrophysical interpretation against which the pipeline is validated.
- Data files are gitignored; they are not bundled with the repository.

### Budget
No external services budget. Stack is entirely open-source and local.

## Open questions

- **(a) Adversarial reviewer — second model family vs. role-only adversarial prompt.**
  Decision deferred to Phase 6. The question is whether using Llama3.1:8b as the
  reviewer (different model family, lower shared-prior risk) adds enough decorrelation
  value over a role-only adversarial prompt on Qwen to justify the operational
  complexity. The deterministic validators carry most of the reliability weight; this
  is a marginal decorrelation question.

- **(b) Hard abstention as a product decision.**
  Decision deferred to Phase 7. Can the system refuse to emit a report when no
  high-leverage parameter (a, m, n, Rw) is constrained by calibration? This is not an
  engineering question — it is a product decision about what the market / client
  tolerates. Engineering can implement either policy; the choice must be made before
  the gating rules are finalized.

- **(c) Uncertainty propagation method — Monte Carlo vs. analytic ranges.**
  Decision deferred to Phase 7. Monte Carlo (full per-depth sampling) gives
  distributional outputs and enables a reliability diagram natively; analytic ranges
  are simpler and faster but less expressive. The choice affects the ECE measurement
  infrastructure and the P10/P50/P90 output format.

- **(d) RAG over petrophysical papers vs. system-prompt knowledge.**
  Decision deferred to Phase 5. Whether the compute agent retrieves parameter
  justifications from a curated paper store (RAG) or relies on model knowledge plus
  the config library determines the scope of Phase 5 and the provenance chain for
  parameter selection rationale.

- **(e) ECE calibration threshold for statistical confidence criterion.**
  The specific ECE target (Success criterion 4) cannot be set before Phase 7
  implements the reliability measurement infrastructure on VOLVE. A provisional
  threshold will be set and logged at Phase 7 exit (after the calibration
  infrastructure is implemented and a provisional measurement is taken), recorded as
  a manifest decision.
