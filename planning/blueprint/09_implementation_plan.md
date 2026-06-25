# Implementation Plan — petro-agent

## Goal

Build, phase by phase, an autonomous multi-agent system that ingests a LAS 2.0 well
log and produces a defensible petrophysical report — Vsh, PHIE, Sw, cutoffs, net pay,
zones, and conclusions — with no human in the per-report loop, full traceability, and
auto-calibrated confidence. Each phase delivers a verifiable artifact before the next
begins. The system does not promise "always correct"; it promises "always honest about
how correct it is, and provably so."

---

## Phases

### Phase 0 — Deterministic engine (foundation)

Done when: `pytest -q` exits 0 on `tests/test_vsh.py`, `tests/test_phie.py`,
`tests/test_sw.py`, `tests/test_netpay.py`, and `tests/test_volumetrics.py`; a
Kansas/Schaben LAS loads successfully via `src/io/`; and `calc_vsh`, `calc_phie`,
`calc_sw`, `apply_cutoffs`, `compute_net_pay`, `net_sand`,
`net_reservoir`, `hcpv`, and `bvw` produce correct values for
all analytic test fixtures with no skipped or xfail tests.

- [ ] Set up WSL repo and Python environment (devcontainer / Docker target) — project root
- [ ] Load a Kansas/Schaben LAS file using lasio, extracting curve arrays and well
  metadata into a typed internal structure (`src/io/loader.py`)
- [ ] Implement `calc_vsh` — Larionov old-rocks variant; clips IGR and output to [0,1];
  NaN passthrough (`src/petrophysics/vsh.py`, version 0.1.0)
- [ ] Implement `calc_phie` — density-neutron crossplot average; clips output to [0, phie_max];
  density-only and neutron-only NaN fallback paths (`src/petrophysics/phie.py`, version 0.1.0)
- [ ] Implement `calc_sw` — Archie equation; clips output to [0,1]; zero-PHIE guard returns NaN;
  NaN passthrough on rt and phie (`src/petrophysics/sw.py`, version 0.1.0)
- [ ] Implement `apply_cutoffs` and `compute_net_pay` — per-depth net-pay flag
  (`Vsh ≤ vsh_cutoff AND PHIE ≥ phie_cutoff AND Sw ≤ sw_cutoff`, NaN/EXCLUDED → False);
  net-pay thickness summation and net-to-gross ratio with zero-gross guard
  (`src/petrophysics/netpay.py`, version 0.1.0)
- [ ] Implement `net_sand` and `net_reservoir` — deterministic
  cutoff/aggregation functions (not new petrophysical equations) surfacing the three-tier
  net-sand / net-reservoir / net-pay hierarchy over the three core outputs: net sand
  (`Vsh ≤ vsh_cutoff`) and net reservoir (`Vsh ≤ vsh_cutoff AND PHIE ≥ phie_cutoff`),
  each as thickness summation with NaN/EXCLUDED → False (`src/petrophysics/netpay.py`,
  version 0.1.0)
- [ ] Implement `hcpv` and `bvw` — deterministic aggregation arithmetic
  over PHIE and Sw on net-pay depths: hydrocarbon pore volume `PHIE × (1 − Sw)` and
  bulk-volume water `PHIE × Sw`, summed/averaged per interval with zero-thickness guard;
  NaN/EXCLUDED → excluded (`src/petrophysics/volumetrics.py`, version 0.1.0)
- [ ] Golden tests for `calc_vsh`: physical bounds, clean-sand = 0, pure-shale = 0.99
  (Larionov old-rocks at IGR=1; not clipped to 1.0), midpoint analytic value,
  monotonicity, NaN passthrough, tertiary-vs-old-rocks separation, dimensional check
  (`tests/test_vsh.py`)
- [ ] Golden tests for `calc_phie`: physical bounds, zero-porosity case, known-sandstone
  analytic value, monotonicity in rhob and nphi, density-only fallback, neutron-only
  fallback, both-NaN full exclusion, units guard (`tests/test_phie.py`)
- [ ] Golden tests for `calc_sw`: physical bounds, water-zone analytic case, known numeric case,
  monotonicity in rt and phie, zero-PHIE guard, NaN passthrough, m-sensitivity direction,
  dimensional check (`tests/test_sw.py`)
- [ ] Golden tests for `apply_cutoffs` / `compute_net_pay`: all-pass, per-cutoff rejection
  (Vsh, PHIE, Sw), NaN exclusion, thickness summation, net-to-gross with zero-gross guard,
  boundary-inclusive cutoff equality (`tests/test_netpay.py`)
- [ ] Golden tests for `net_sand` / `net_reservoir`: three-tier monotonicity
  (net sand ≥ net reservoir ≥ net pay), thickness summation, per-cutoff rejection,
  NaN/EXCLUDED exclusion (`tests/test_netpay.py`)
- [ ] Golden tests for `hcpv` / `bvw`: HCPV = PHIE × (1 − Sw) known analytic case,
  BVW = PHIE × Sw known analytic case, NaN passthrough, net-pay-only integration,
  zero-thickness guard, physical bounds (`tests/test_volumetrics.py`)

---

### Phase 1 — Data QC gate

Done when: a Kansas/Schaben LAS passes through `qc_gate` and produces a per-depth
data-quality map (`GOOD | DEGRADED | EXCLUDED`) with all edits recorded in the ledger's
`edits` array; no computation call is reachable without the map being produced first.

- [ ] Implement intake unit detection and auto-conversion: NPHI percent→v/v when max > 2.0,
  RHOB kg/m³→g/cc when max > 10.0; ambiguous ranges abort with a diagnostic; each
  conversion logged as a `unit_conversion` edit (`src/io/loader.py`)
- [ ] Implement null masking: apply the lasio null sentinel (default −9999.25, tolerance 1e-3)
  across all curves simultaneously; log as `null_mask` edits (`src/qc/null_handler.py`)
- [ ] Implement spike removal on GR, RHOB, NPHI, RT: ±10-sample window, 5×IQR threshold;
  spike depth set to NaN; original value logged as `spike_removal` edit (`src/qc/spike.py`)
- [ ] Implement bad-hole masking: preferred path uses DCAL > 2 inches; fallback uses
  CALI vs. `bit_size_config` constant from the config library when DCAL is absent; RHOB
  and NPHI masked at bad-hole depths; fallback usage logged as a degradation entry
  (`src/qc/bad_hole.py`)
- [ ] Implement physical-range sanity flags (WARN, not mask) for RHOB, NPHI, GR, RT, CALI
  (`src/qc/range_check.py`)
- [ ] Build per-depth data-quality map: GOOD / DEGRADED / EXCLUDED integer array; abort
  run if > 80% of depth range is EXCLUDED or DEGRADED (`src/qc/quality_map.py`)
- [ ] Tests for null masking, spike removal, bad-hole masking, quality-map construction, and
  the 80% abort threshold (`tests/test_qc.py`)

---

### Phase 2 — Parameters with provenance

Done when: a parameter config JSON loads and resolves every parameter for a Kansas
well to a value, a provenance tier (`core | offset | default`), and a source
description; the SHA-256 config hash is logged in the ledger `run` object; and the
static curated citations table resolves every parameter (a, m, n, Rw, matrix density,
Vsh method, net-pay cutoffs) to exactly one source, with an unknown parameter hard-failing
rather than guessing.

- [ ] Define and implement the config JSON schema: top-level keys `version`,
  `regional_defaults`, `well_overrides`; each parameter entry carries `value`, `unit`,
  `provenance`, and `source_description` (`src/params/schema.py`)
- [ ] Populate `regional_defaults.paleozoic_kansas`: gr_min = 20 API, gr_max = 120 API,
  variant = old_rocks, rho_ma = 2.65 g/cc, rho_fl = 1.00 g/cc, phie_max = 0.45,
  a = 1.0, m = 2.0, n = 2.0, Rw = 0.05 ohm·m, rt_hydrocarbon_floor = 5 ohm·m (provenance
  default; read by the RT–Sw cross-curve validator), vsh_cutoff = 0.40, phie_cutoff = 0.08,
  sw_cutoff = 0.60 (net-pay cutoffs, provenance default), bit_size_config,
  qc_abort_threshold = 0.80, circuit_breaker_n = 3 (`src/params/regional_defaults.json`)
- [ ] Populate `regional_defaults.north_sea_jurassic` with appropriate VOLVE-compatible
  defaults for Rw, a, m, n, matrix density (`src/params/regional_defaults.json`)
- [ ] Implement `well_overrides` lookup: per-well UWI overrides take precedence over regional
  defaults; absent UWI falls through to regional defaults with `provenance = default`
  (`src/params/config_loader.py`)
- [ ] Implement PROV-tag-driven Larionov variant selection: `paleozoic` → old_rocks,
  `tertiary` → tertiary, absent or unrecognised → old_rocks + degradation entry
  (`src/params/config_loader.py`)
- [ ] Implement mnemonic alias table at `src/params/mnemonic_aliases.json` covering GR,
  RHOB (RHOZ, DEN), NPHI (NPOR, TNPH), RT (ILD, RDEEP, AT90), CALI (CAL, C1),
  DCAL (CALX, CALY)
- [ ] Implement config hash computation (SHA-256 of the JSON file) and log into ledger
  `run.config_hash_sha256` at pipeline start (`src/params/config_loader.py`)
- [ ] Define the static curated citations-table schema (no RAG): one row per parameter
  with columns `value`/`default`, `valid_range`, `source` (author, year), `locator`
  (page/DOI), and `applicability_scope` (formation age / lithology); seed Archie 1942
  (m, n = 2.0; `a` from Winsauer 1952 / Wyllie & Gregory 1953), Larionov 1969 older-rocks,
  and KGS/USGS Schaben values (Rw = 0.04, m = n = 2); wire it into the JSON ledger so every
  parameter selection emits a frozen citation (`src/params/citations.py`,
  `src/params/citations_table.json`)
- [ ] Tests for provenance lookup, PROV-tag routing, alias resolution, hash computation,
  well-override precedence, and the citations table (every parameter resolves to exactly
  one source; unknown parameter → hard fail, never a guess) (`tests/test_params.py`)

---

### Phase 3 — Independent validators

Done when: the validator harness in `src/validators/` runs to completion on computed
Vsh/PHIE/Sw arrays and returns a typed objection list; the model-mismatch validator
produces neutron-density and M-N crossplot PNGs in `outputs/`; all validator modules
have golden tests that pass.

- [ ] Implement physical-bounds validator: Vsh, PHIE, Sw against [0,1] and [0, phie_max];
  violations typed `mechanical`; version logged per validator entry
  (`src/validators/physical.py`, version 0.1.0)
- [ ] Implement cross-curve consistency validator: Vsh–PHIE anti-correlation check (Pearson
  ≤ +0.3 in ±20-sample window); RT–Sw directional consistency (low Sw with low RT flags);
  violations typed `support` (`src/validators/cross_curve.py`, version 0.1.0)
- [ ] Implement model-mismatch validator: neutron-density crossplot position relative to
  sandstone / limestone / dolomite reference lines; flag if > 30% of non-excluded samples
  fall outside the mineral triangle; M-N crossplot check (skipped with degradation if DT
  absent); all violations typed `irreducible`
  (`src/validators/model_mismatch.py`, version 0.1.0)
- [ ] Implement data-quality propagation validator: enforce tier downgrade for any FIRM
  computation at a DEGRADED depth; flag missing degradation records as internal consistency
  errors (`src/validators/data_quality.py`, version 0.1.0)
- [ ] Implement crossplot PNG generation: neutron-density (1200 × 900 px, 300 dpi, viridis
  depth colormap, lithology reference lines); M-N crossplot (Schlumberger 1989 reference
  points); output to `outputs/<UWI>_<YYYY-MM-DD>_crossplot_nd.png` and `_crossplot_mn.png`
  (`src/validators/crossplot.py`)
- [ ] Implement `typify_objections` stage: deterministic Python; splits objection list into
  `correctable_objections` (mechanical + support) and `irreducible_objections`; computes
  `correctable_count` (`src/orchestrator/stages.py`)
- [ ] Tests for each validator module and the typing stage (`tests/test_validators.py`,
  `tests/test_typify.py`)

---

### Phase 4 — Orchestrator and loop

Done when: a single call to the LangGraph pipeline on a Kansas/Schaben LAS runs the
deterministic stages from `load` through `emit` without human intervention, emitting
`ledger.json` (plus the Phase 3 crossplot PNGs) but not `report.md` (the writer agent
is a Phase 5 node); the `zonate` stage delineates cutoff-delimited net-pay zones and
writes per-zone net-pay computations to the ledger; the circuit breaker fires correctly
when driven through a deterministic stub `correct` node on a synthetic non-converging
input; `convergence_status` is written to the ledger; and a field run over the multi-well
Schaben set produces, after the per-well runs, a deterministic field-rollup ledger object
(aggregate net pay / NTG / HCPV plus a per-well summary table), a field net-pay/quality
map PNG, and a cross-well zone-correlation panel PNG in `outputs/`.

- [ ] Implement the LangGraph `StateGraph` in `src/orchestrator/graph.py` with state
  fields: `las_path`, `config_path`, `curves`, `quality_map`, `vsh`, `phie`, `sw`,
  `ledger`, `objections`, `correctable_count`, `iteration`, `prev_correctable`,
  `confidence_tiers`, `convergence_status`, `draft_report`
- [ ] Wire pipeline stages as deterministic LangGraph nodes: `load`, `qc_gate`, `compute`,
  `validate`, `typify_objections`, `gating`, `zonate`, `emit` (`src/orchestrator/stages.py`)
- [ ] Implement loop edges: after `typify_objections` route to `correct` when
  `correctable_count > 0` and circuit breaker not triggered; otherwise route to `gating`;
  after `correct` always route to `compute`; after `compute` always route to `validate`.
  In this phase `correct` is a deterministic no-op stub (the LLM compute agent is wired in
  Phase 5); the circuit-breaker test drives the loop via this stub or by injecting
  objection counts (`src/orchestrator/graph.py`)
- [ ] Implement circuit breaker: track `consecutive_non_decrease`; fire when count ≥ N
  (N = 3, read from config); set `convergence_status = DID_NOT_CONVERGE`; route to
  `gating` (`src/orchestrator/stages.py`)
- [ ] Implement `gating` stage: assign FIRM / QUALIFIED / BRACKETED from parameter
  provenance; apply one-tier downgrade per irreducible objection, floor at BRACKETED;
  write `convergence_status` to ledger (`src/orchestrator/stages.py`)
- [ ] Implement `zonate` stage: read `vsh_cutoff` / `phie_cutoff` / `sw_cutoff` from the
  config; call `apply_cutoffs` for the per-depth net-pay flag; delineate contiguous net-pay
  runs into zones; call `compute_net_pay` per zone (gross/net/net-to-gross); assign each
  zone the lowest contributing tier; append per-zone `net_pay` computation entries to the
  ledger and expose `pipeline_net_pay_m` (`src/orchestrator/stages.py`)
- [ ] Implement `emit` stage: ledger completeness gate (all computation_ids and
  validator_ids resolve); prepend DID_NOT_CONVERGE warning block when applicable; write
  ledger.json and crossplot PNGs to `outputs/` (report.md and the prose-claim trace check
  are added when the writer agent lands in Phase 5) (`src/orchestrator/stages.py`)
- [ ] Implement version-pinning check at `load`: verify installed lasio, numpy, langgraph
  versions match `pyproject.toml` pins; abort on mismatch; log versions in `run` object
  (`src/orchestrator/stages.py`)
- [ ] Implement the deterministic `field_aggregate` stage (field-scale): run after all
  per-well pipelines complete; deterministic Python, no LLM; reads each well's ledger and
  rolls up aggregate net pay / NTG / HCPV across the Schaben field, builds a per-well
  summary table, and aligns cutoff-delimited zones across wells into correlated field
  zones; writes a field-rollup object to the field ledger (`src/orchestrator/field.py`)
- [ ] Implement the field net-pay/quality map PNG: per-well net-pay (and quality-tier)
  values rendered at well locations across the field; output to
  `outputs/field_<YYYY-MM-DD>_netpay_map.png` (`src/orchestrator/field_plots.py`)
- [ ] Implement the cross-well zone-correlation panel PNG: aligned zone tops/net-pay
  flags across wells in a single correlation panel; output to
  `outputs/field_<YYYY-MM-DD>_zone_correlation.png` (`src/orchestrator/field_plots.py`)
- [ ] Integration test: single end-to-end run on a Kansas/Schaben LAS exits without error
  and writes ledger.json (including per-zone `net_pay` computation entries from `zonate`)
  plus the Phase 3 crossplot PNGs (report.md is added in Phase 5); circuit-breaker test
  drives the `correct` stub on synthetic non-converging input and produces a
  `DID_NOT_CONVERGE` ledger entry (`tests/test_pipeline.py`)
- [ ] Field integration test: a multi-well run produces per-well ledgers, then a
  deterministic field-rollup object (aggregate net pay / NTG / HCPV + per-well summary
  table), the field net-pay/quality map PNG, and the cross-well zone-correlation panel
  PNG; field aggregation runs only after every per-well run completes
  (`tests/test_field.py`)

---

### Phase 5 — Local LLM agents (Ollama)

Done when: a single end-to-end pipeline run on a Kansas/Schaben well produces a
Markdown prose report and a complete JSON ledger; the claim verifier finds zero residual
flags; `claim_verifier` entry in the ledger carries `result = PASS`; and a field run
produces a field-summary prose report rolling up the per-well report blocks plus the
aggregate net pay / NTG / HCPV, the field net-pay/quality map, and the zone-correlation
panel, with every field-level number traced to the deterministic field-rollup ledger.

- [ ] Implement compute agent (`src/agents/compute_agent.py`): receives correctable
  objection list and current parameters; selects revised parameters from the config
  library; calls Qwen3:30b-a3b via Ollama API; does not author equations; if no valid
  parameter exists in the library, flags objection as data-limited for reclassification
  on the next `typify_objections` pass
- [ ] Implement writer agent (`src/agents/writer.py`): receives read-only ledger and
  per-block confidence tiers; generates prose following the report schema in
  `03_source_sink_contracts.md`; tone bound to the confidence tier of each block
  (FIRM → declarative, QUALIFIED → qualified, BRACKETED → explicitly bounded);
  calls Qwen3:30b-a3b via Ollama API
- [ ] Implement claim verifier (`src/agents/claim_verifier.py`): audits draft prose
  sentence by sentence; checks four conditions (numerical value traces to ledger,
  BRACKETED blocks do not assert point estimates without P10–P90, QUALIFIED blocks use
  qualifying hedges, Limitations section names all default-provenance parameters);
  returns flags to the writer for a single correction pass; unresolvable sentences are
  removed and logged as degradation entries with `confidence_impact = exclusion`
- [ ] Wire compute agent as the `correct` LangGraph node (`src/orchestrator/graph.py`)
- [ ] Implement field-summary writer (`src/agents/field_writer.py`): receives the
  read-only deterministic field-rollup ledger and per-well report blocks; generates the
  field-scale prose report (aggregate net pay / NTG / HCPV, per-well summary table,
  references to the field net-pay/quality map and zone-correlation panel); every
  field-level number traces to the field-rollup ledger, none computed by the LLM; tone
  bound to each block's confidence tier; calls Qwen3:30b-a3b via Ollama API
- [ ] Wire writer and claim verifier as `write` and `claim_verify` LangGraph nodes
  (`src/orchestrator/graph.py`)
- [ ] Pin LLM seed (`run.llm_seed`) at invocation; log model tags in `run.model_tags`;
  verify Ollama determinism on the target build; log as degradation if seed
  non-determinism is confirmed (`src/agents/ollama_client.py`)
- [ ] Decision (d) — RAG vs. system-prompt knowledge for parameter justification: resolve
  and implement; if RAG, add `src/retrieval/`; if system-prompt, document the knowledge
  boundary in `src/agents/compute_agent.py`
- [ ] End-to-end test: pipeline on a Kansas LAS produces a report.md, a ledger.json with
  `claim_verifier result = PASS`, and no unresolved flags (`tests/test_e2e.py`)

---

### Phase 6 — Adversarial reviewer

Done when: a second adversarial agent reviews the draft before the claim verifier;
objections from the adversarial reviewer route through `typify_objections` and feed the
loop; generator and critic use decorrelated models or prompts; design decision (a) is
resolved and recorded in the manifest.

- [x] Decision (a) — RESOLVED (2026-06-25): adversarial reviewer uses the second model
  family **Llama3.1:8b** (different family from the Qwen3:30b-a3b writer), not a
  role-only prompt; recorded in `planning/blueprint/MANIFEST.md` under Decisions
- [ ] Implement adversarial reviewer (`src/agents/reviewer.py`): receives draft report and
  ledger; produces a typed objection list (mechanical / support / irreducible) rewarded
  for finding faults, not for approving the draft; uses Llama3.1:8b (second model family)
- [ ] Wire adversarial reviewer before `claim_verify` in the LangGraph graph; reviewer
  objections route back through `typify_objections` so correctable ones re-enter the
  compute→validate loop (`src/orchestrator/graph.py`)
- [ ] Log reviewer model tag and seed in `run.model_tags` (`src/agents/ollama_client.py`)
- [ ] Test: adversarial reviewer introduces a mechanical objection on a synthetic draft;
  the loop re-enters `compute` and resolves it before re-entering `write`
  (`tests/test_reviewer.py`)

---

### Phase 7 — Uncertainty and confidence

Done when: the pipeline propagates parameter uncertainty through Vsh, PHIE, and Sw
computations and writes P10/P50/P90 slots in the ledger; sensitivity analysis identifies
the dominant parameter for net pay; the multi-seed robustness check passes; the ECE
threshold is set, logged as a manifest decision, and the reliability diagram
infrastructure is in place.

- [ ] Decision (c) — CLOSED as Monte Carlo per-depth sampling: implement Monte Carlo
  per-depth sampling in `src/uncertainty/propagation.py` with seed management and
  population of `run.monte_carlo_seeds`
- [ ] Decision (b) — resolve hard abstention policy: can the system refuse to emit a report
  when no high-leverage parameter (a, m, n, Rw) is constrained by calibration? Record
  decision in `planning/blueprint/MANIFEST.md`; implement the policy in
  `src/orchestrator/stages.py` (gating stage abstention path, if chosen)
- [ ] Implement uncertainty propagation: P10/P50/P90 computed for Vsh, PHIE, and Sw per
  depth range; written to `computations[].result_p10` and `result_p90` in the ledger;
  uncertainty widths read from the config library defaults
  (`src/uncertainty/propagation.py`)
- [ ] Implement sensitivity analysis: identify which parameter (a, m, n, Rw) contributes
  most to the net-pay uncertainty for each zone; log result as a metadata field in the
  ledger and require the writer to mention it in the zone Limitations sub-section
  (`src/uncertainty/sensitivity.py`)
- [ ] Implement multi-seed robustness check: three fixed seed sets
  ([1001,1002,…], [2001,2002,…], [3001,3002,…]) hardcoded in
  `src/evaluation/robustness.py`; P50 values must agree within 1% relative deviation
  across seeds; P10–P90 widths within 5%; confidence tier must be consistent; failures
  logged as degradation entries with `confidence_impact = uncertainty_widening`
- [ ] Implement ECE and reliability diagram infrastructure: `compute_mae`,
  `compute_net_pay_deviation`, `compute_ece`, and `plot_reliability_diagram` in
  `src/evaluation/volve_metrics.py`; golden tests in `tests/test_volve_metrics.py`
- [ ] Set and log ECE threshold: take a provisional ECE measurement on a non-benchmark
  VOLVE subset (raw LAS curves only, no interpretation overlay); propose threshold;
  record as a manifest decision in `planning/blueprint/MANIFEST.md`; Phase 8 is blocked
  until this decision is logged
- [ ] Tests for propagation, sensitivity analysis, robustness check, and metric functions
  (`tests/test_uncertainty.py`, `tests/test_volve_metrics.py`)

---

### Phase 8 — Traceability and evaluation

Done when: the pipeline produces a complete JSON ledger in which every emitted number
traces in O(1) to its source; a full unattended run on VOLVE benchmark wells satisfies
all four regression thresholds (PHIE MAE < 0.03, Vsh MAE < 0.10, Sw MAE < 0.15, net
pay within ±20% per well); and the reliability diagram and ECE measurement are emitted
to `outputs/evaluation/`.

- [ ] Verify and complete ledger coverage: every `computation` entry has `function`,
  `function_version`, `function_module`, `input_curves`, `parameters`,
  `parameter_provenance`, `parameter_source`, `result_p50`, `confidence_tier`, and
  `validator_ids`; every `validator` entry has `validator_version`, `check_type`, and
  `objection_type`; every `degradation` entry has `confidence_impact`; ledger completeness
  gate enforced at `emit` (`src/orchestrator/stages.py`)
- [ ] Implement full run metadata pinning: git commit SHA of `src/`, pipeline version,
  lasio / numpy / langgraph / ollama_client versions, model tags, config hash, LAS file
  SHA-256, LLM seed, monte_carlo_seeds list — all written to the ledger `run` object at
  pipeline start (`src/orchestrator/stages.py`)
- [ ] Implement VOLVE mnemonic alias mapping: build alias table entries for RHOZ → RHOB,
  NPOR → NPHI, and other Equinor mnemonics confirmed from raw VOLVE LAS headers (not
  from interpretation files); add to `src/params/mnemonic_aliases.json`
- [ ] Implement VOLVE regression runner: `src/evaluation/volve_runner.py` invokes the full
  pipeline on each VOLVE benchmark well and collects per-well MAE and net-pay deviation;
  calls `compute_mae`, `compute_net_pay_deviation`, and `compute_ece` from
  `src/evaluation/volve_metrics.py`; writes results to `outputs/evaluation/`
- [ ] Run VOLVE regression: execute `volve_runner.py` on all benchmark wells with accepted
  interpretation; confirm PHIE MAE < 0.03, Vsh MAE < 0.10, Sw MAE < 0.15, and net pay
  within ±20% per well; emit reliability diagram to
  `outputs/evaluation/calibration_reliability_diagram.png`
- [ ] Regression golden test: `tests/regression/test_volve_regression.py` encodes the four
  thresholds as assertions; test must pass (`pytest -q tests/regression/`) before Phase 8
  is declared complete
- [ ] Confirm minimum three VOLVE wells carry complete reference Vsh/PHIE/Sw curves; if
  fewer than three wells are available, block Phase 8 with a foundation gap report
  (see Open questions)

---

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

---

## Sequencing and dependencies

Each phase assumes all prior phases are complete and their artifacts are passing their
verification gates. No phase may begin before `pytest -q` exits 0 on all tests
introduced by preceding phases.

| Phase | Hard prerequisites |
|---|---|
| Phase 0 | Python environment and lasio installed; at least one Kansas/Schaben LAS file in `data/` |
| Phase 1 | Phase 0 complete: `calc_vsh`, `calc_phie`, `calc_sw` exist and pass golden tests |
| Phase 2 | Phase 1 complete: QC gate produces a validated quality map before config lookup can be meaningfully tested end-to-end |
| Phase 3 | Phase 2 complete: parameter config library (provenance, formation tag) is required by the model-mismatch validator to select matrix density reference values |
| Phase 4 | Phase 3 complete: all validator modules and the typify stage must exist before the LangGraph loop can be wired; no placeholder stubs are permitted in the orchestrator |
| Phase 5 | Phase 4 complete: Ollama service running with Qwen3:30b-a3b pre-pulled; full pipeline loop wired before LLM agents are inserted as nodes |
| Phase 6 | Phase 5 complete: decision (a) resolved before implementing the adversarial reviewer; Llama3.1:8b pre-pulled |
| Phase 7 | Phase 6 complete: uncertainty propagation method (decision c) and abstention policy (decision b) must be resolved before implementation; ECE threshold must be set and logged before Phase 8 is unblocked |
| Phase 8 | Phase 7 complete and ECE threshold logged; VOLVE LAS files in `data/`; accepted interpretation files available but not examined before Phase 8 begins; minimum three VOLVE benchmark wells confirmed to carry complete reference curves |

**Critical path within phases:**

- Within Phase 0, `calc_sw` depends on `calc_phie` being available (PHIE is an input
  to `calc_sw`); `calc_phie` depends on the LAS loader being in place.
- Within Phase 4, the `emit` stage depends on the `gating` stage, which depends on
  `typify_objections`, which depends on the validator harness from Phase 3.
- Within Phase 7, the ECE threshold manifest decision is the sole unblocking condition
  for Phase 8; it must exist before any Phase 8 work begins.
- VOLVE accepted interpretation files must not be examined during Phases 0–7;
  examination before Phase 8 contaminates the benchmark.

**Parked design decisions and their blocking phases:**

| Decision | Resolves in | Blocks |
|---|---|---|
| (a) Adversarial reviewer model choice | CLOSED 2026-06-25 = Llama3.1:8b (second family) | — |
| (b) Hard abstention policy | Phase 7 | Phase 7 gating implementation |
| (c) Uncertainty propagation method | CLOSED 2026-06-24 = Monte Carlo | Phase 7 propagation and Phase 8 ECE infrastructure |
| (d) RAG vs. system-prompt knowledge | RESOLVED 2026-06-24 = no RAG (curated citations table) | Phase 5 compute agent (implementation only) |
| (e) ECE numeric threshold | Phase 7 exit | Phase 8 start (hard block) |

---

## Risks

### R1 — Model mismatch: wrong Larionov variant on VOLVE

**Description**: VOLVE is a North Sea Jurassic–Cretaceous dataset. If the formation
tag `PROV` in the VOLVE LAS headers is absent or maps to `unknown`, the pipeline falls
back to Larionov old-rocks (Kansas default). If the appropriate variant for VOLVE
formations is Tertiary, Vsh will be systematically under-estimated, likely causing the
Vsh MAE to fail its threshold.

**Likelihood**: medium — VOLVE header metadata quality is unknown until Phase 8.

**Impact**: high — a systematic Vsh bias propagates to Sw (via Vsh-corrected PHIE in
shaly-sand scenarios) and may cause a pipeline regression failure on multiple metrics.

**Mitigation**: the mnemonic alias mapping task in Phase 8 includes confirming the
formation tags in raw VOLVE LAS headers. The North Sea / Jurassic regional defaults
must be populated in Phase 2 (including the Larionov variant field set to `tertiary`
for Jurassic intervals) even though VOLVE is a Phase 8 concern.

---

### R2 — Uncalibrated Archie parameters dominate VOLVE Sw error

**Description**: Kansas/Schaben wells carry no core data. All Archie parameters
(a, m, n, Rw) are `provenance = default`. For VOLVE, even if core data exists in
the Equinor interpretation, the config library must be populated with those values
before the regression run. If VOLVE runs with Kansas-default parameters, the Sw MAE
will far exceed 0.15 v/v.

**Likelihood**: medium — requires deliberate Phase 2 action to populate VOLVE well
overrides.

**Impact**: high — Sw MAE failure is a Phase 8 hard block.

**Mitigation**: Phase 2 must include a `well_overrides` block for at least the VOLVE
benchmark wells with calibrated or offset-derived parameters where available in the
Equinor data. This cannot wait for Phase 8 setup; the schema must be ready in Phase 2
and the values populated in Phase 8 setup before the regression run.

---

### R3 — Qwen3:30b-a3b does not fit in 16 GB VRAM

**Description**: the 16 GB VRAM ceiling is a hard hardware constraint. Qwen3:30b-a3b
is a MoE model that must run quantized (Q4_K_M or equivalent) to fit. If the
quantized model exceeds VRAM capacity — due to context length during a long pipeline
run, KV-cache growth, or a larger model revision — inference will fail or fall back to
slow CPU offloading.

**Likelihood**: low to medium — Q4_K_M quantization for Qwen3:30b-a3b is expected to
fit within 16 GB based on architecture specifications, but this must be verified
empirically in Phase 5.

**Impact**: high — no local LLM inference means no agents and no prose generation;
the entire Phase 5–8 stack is blocked.

**Mitigation**: verify VRAM fit in Phase 5 before wiring the compute agent as a
LangGraph node. If the model does not fit, fall back to Llama3.1:8b as the primary
agent for all roles and update the manifest with a decision record. The pipeline
architecture does not require Qwen specifically; any Ollama-served model that fits is
acceptable, but the quality difference must be assessed.

---

### R4 — Non-convergence on Kansas data (circuit breaker fires every run)

**Description**: if the correctable-objection count does not decrease monotonically on
real Kansas/Schaben wells — due to oscillating parameter corrections, poorly
calibrated GR min/max bounds, or an inherent RT–Sw inconsistency in the formation —
the circuit breaker fires on every run and every Kansas report emits
`DID_NOT_CONVERGE`. This is a correctness signal (the data is genuinely hard), but
it means the system never produces a FIRM or QUALIFIED confidence tier on the
development dataset and cannot demonstrate the loop's intended behaviour.

**Likelihood**: medium — Kansas wells have no core calibration; the default
parameters may produce persistent `mechanical` violations on some intervals.

**Impact**: medium — development dataset utility is reduced; Phase 6–7 work on
adversarial review and calibration becomes harder to test.

**Mitigation**: the circuit-breaker threshold N = 3 is configurable. If persistent
non-convergence is observed on Kansas in Phase 4 acceptance testing, the threshold
can be increased or the compute agent's parameter-revision range can be widened. The
root cause must be diagnosed (logged in the bitácora) before increasing N — the
circuit breaker exists to catch genuine oscillation, not to be tuned away.

---

### R5 — VOLVE benchmark well count below the minimum

**Description**: if fewer than three VOLVE wells carry complete accepted Vsh/PHIE/Sw
reference curves, the Phase 8 hard block fires. The exact subset is unknown until
Phase 8 setup opens the VOLVE data.

**Likelihood**: low — the Equinor VOLVE release is documented to include accepted
interpretations for multiple wells, but the exact curve completeness has not been
verified.

**Impact**: medium — Phase 8 is blocked; v1 declaration is delayed; the regression
evaluation may require a reformulated validation scheme.

**Mitigation**: confirm the VOLVE well subset as the first action of Phase 8 setup.
If the count is below three, emit a foundation gap report before any other Phase 8
work proceeds.

---

## Open questions

- **(a) Adversarial reviewer — model family decision. CLOSED (2026-06-25).** The
  adversarial reviewer uses the second model family **Llama3.1:8b** (different family
  from the Qwen3:30b-a3b writer) for genuine cross-family decorrelation — not a
  role-only prompt on Qwen. Implemented at Phase 6.

- **(b) Hard abstention policy.** Whether the system should refuse to emit any prose
  report when no high-leverage Archie parameter is constrained by calibration. Resolve at
  Phase 7 entry. Engineering can implement either policy; the choice is a product decision.

- **(c) Uncertainty propagation method.** CLOSED → **Monte Carlo** per-depth sampling
  (full distributional outputs, true P10/P50/P90 percentiles, enables ECE measurement
  natively). Compute cost is numpy/CPU, not VRAM. Analytic ranges are not used.

- **(d) RAG vs. system-prompt knowledge for parameter justification.** RESOLVED →
  **no RAG for v1**; instead a lightweight static **curated citations table** (each
  parameter → exactly one source) wired to the JSON ledger so every selection emits a
  frozen citation. Not paper curation, not search. Revisit only if a large unstructured
  regional corpus appears post-Phase 8.

- **(e) ECE numeric threshold.** Cannot be set before Phase 7 implements the calibration
  infrastructure and takes a provisional measurement on a non-benchmark VOLVE subset. Must
  be set, proposed, and logged as a manifest decision before Phase 8 begins — Phase 8 is
  hard-blocked until this decision is recorded.

- **(f) GR min/max estimation strategy.** Whether `gr_min` and `gr_max` for Vsh are
  expert-set scalars in the config (current design) or estimated automatically from the
  GR distribution (P5/P95 per well or per zone). Automatic estimation is deterministic
  and logged but makes the values data-dependent. Deferred to Phase 2 implementation.

- **(g) `DID_NOT_CONVERGE` prose emission policy.** Whether the pipeline emits a prose
  report with a non-convergence warning block (current design) or emits only the ledger
  with no prose when the circuit breaker fires. Related to question (b). Resolve during
  Phase 4 acceptance testing.
