# petro-agent — Agente petrofísico autónomo

## Goal
Build, phase by phase, an autonomous multi-agent system that turns well logs (LAS)
into a defensible petrophysical report (Vsh, PHIE, Sw, cutoffs, net pay, zones,
conclusions) with no human in the per-report loop, full traceability, and
auto-calibrated confidence — honest about how correct it is, and provably so.

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
src/io/            LAS loader, intake unit detection
src/petrophysics/  vetted engine (vsh, phie, sw, netpay, volumetrics) — frozen + golden-tested
src/qc/            data-quality gate (null, spike, bad-hole, range, quality map)
src/params/        config library, provenance, mnemonic aliases, config hash
src/validators/    physical / cross-curve / model-mismatch / data-quality + crossplots
src/orchestrator/  LangGraph graph + deterministic stages (per-well + field rollup)
src/field/         deterministic field aggregation (rollup, zone-correlation, net-pay/quality map)
src/agents/        Ollama agents (compute, writer, claim verifier, reviewer)
src/uncertainty/   propagation + sensitivity
src/evaluation/    robustness, VOLVE metrics + runner
tests/             pytest golden tests (tests/regression/ for VOLVE)
data/              LAS files — Kansas/Schaben (dev), VOLVE (regression) — gitignored
outputs/           reports, ledgers, cross-plots, evaluation — gitignored
planning/          this plan + blueprint/ + bitacora/
```

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

## Phases

### Phase 0 — Deterministic engine (foundation) (COMPLETED 2026-06-25)
Done when: `pytest -q` exits 0 on `tests/test_vsh.py`, `tests/test_phie.py`, `tests/test_sw.py`, `tests/test_netpay.py`, and `tests/test_volumetrics.py`; a Kansas/Schaben LAS loads successfully via `src/io/`; and `calc_vsh`, `calc_phie`, `calc_sw`, `apply_cutoffs`, `compute_net_pay`, `net_sand`, `net_reservoir`, `hcpv`, and `bvw` produce correct values for all analytic test fixtures with no skipped or xfail tests.
- [x] Set up WSL repo and Python environment (devcontainer / Docker target) — project root
- [x] Load a Kansas/Schaben LAS file with lasio, extracting curve arrays and well metadata into a typed internal structure (`src/io/loader.py`)
- [x] Implement `calc_vsh` — Larionov old-rocks variant, clips IGR and output to [0,1], NaN passthrough (`src/petrophysics/vsh.py`, version 0.1.0)
- [x] Implement `calc_phie` — density-neutron crossplot average, clips to [0, phie_max], density-only and neutron-only NaN fallback paths (`src/petrophysics/phie.py`, version 0.1.0)
- [x] Implement `calc_sw` — Archie equation, clips to [0,1], zero-PHIE guard returns NaN, NaN passthrough on rt and phie (`src/petrophysics/sw.py`, version 0.1.0)
- [x] Implement `apply_cutoffs` and `compute_net_pay` — per-depth net-pay flag, thickness summation, net-to-gross with zero-gross guard (`src/petrophysics/netpay.py`, version 0.1.0)
- [x] Implement `net_sand`, `net_reservoir` — deterministic cutoff/aggregation functions over the three core outputs (three-tier net sand/net reservoir/net pay hierarchy), not new petrophysical equations (`src/petrophysics/netpay.py`, version 0.1.0)
- [x] Implement `hcpv`, `bvw` — deterministic aggregation arithmetic over PHIE and Sw (hydrocarbon pore volume and bulk-volume-water), not new petrophysical equations (`src/petrophysics/volumetrics.py`, version 0.1.0)
- [x] Golden tests for `calc_vsh`: physical bounds, clean-sand, pure-shale, midpoint analytic, monotonicity, NaN passthrough, tertiary-vs-old-rocks separation, dimensional check (`tests/test_vsh.py`)
- [x] Golden tests for `calc_phie`: physical bounds, zero-porosity, known-sandstone analytic, monotonicity in rhob and nphi, density-only fallback, neutron-only fallback, both-NaN exclusion, units guard (`tests/test_phie.py`)
- [x] Golden tests for `calc_sw`: physical bounds, water-zone analytic, known numeric, monotonicity in rt and phie, zero-PHIE guard, NaN passthrough, m-sensitivity direction, dimensional check (`tests/test_sw.py`)
- [x] Golden tests for `apply_cutoffs` / `compute_net_pay`: all-pass, per-cutoff rejection, NaN exclusion, thickness summation, net-to-gross zero-gross guard, boundary-inclusive cutoff equality (`tests/test_netpay.py`)
- [x] Golden tests for `net_sand` / `net_reservoir`: three-tier monotonic ordering (net pay ≤ net reservoir ≤ net sand), thickness summation, per-cutoff rejection, NaN exclusion (`tests/test_netpay.py`)
- [x] Golden tests for `hcpv` / `bvw`: HCPV = net pay × PHIE × (1−Sw) analytic case, BVW = PHIE × Sw analytic case, NaN passthrough, net-pay-only integration, zero-thickness guard, physical bounds (`tests/test_volumetrics.py`)

### Phase 1 — Data QC gate
Done when: a Kansas/Schaben LAS passes through `qc_gate` and produces a per-depth data-quality map (`GOOD | DEGRADED | EXCLUDED`) with all edits recorded in the ledger's `edits` array; no computation call is reachable without the map being produced first.
- [ ] Implement intake unit detection and auto-conversion: NPHI percent→v/v when max > 2.0, RHOB kg/m³→g/cc when max > 10.0; ambiguous ranges abort with a diagnostic; each conversion logged as a `unit_conversion` edit (`src/io/loader.py`)
- [ ] Implement null masking: apply lasio null sentinel (default −9999.25, tolerance 1e-3) across all curves simultaneously; log as `null_mask` edits (`src/qc/null_handler.py`)
- [ ] Implement spike removal on GR, RHOB, NPHI, RT: ±10-sample window, 5×IQR threshold; spike depth set to NaN; original value logged as `spike_removal` edit (`src/qc/spike.py`)
- [ ] Implement bad-hole masking: preferred DCAL > 2 inches; fallback CALI vs. `bit_size_config` when DCAL absent; RHOB and NPHI masked at bad-hole depths; fallback usage logged as degradation (`src/qc/bad_hole.py`)
- [ ] Implement physical-range sanity flags (WARN, not mask) for RHOB, NPHI, GR, RT, CALI (`src/qc/range_check.py`)
- [ ] Build per-depth data-quality map: GOOD / DEGRADED / EXCLUDED integer array; abort run if > 80% of depth range is EXCLUDED or DEGRADED (`src/qc/quality_map.py`)
- [ ] Tests for null masking, spike removal, bad-hole masking, quality-map construction, and the 80% abort threshold (`tests/test_qc.py`)

### Phase 2 — Parameters with provenance
Done when: a parameter config JSON loads and resolves every parameter for a Kansas well to a value, a provenance tier (`core | offset | default`), and a source description; the static citations table resolves every parameter to exactly one source (unknown parameter → hard fail) and joins into the ledger; the SHA-256 config hash is logged in the ledger `run` object.
- [ ] Define and implement the config JSON schema: top-level `version`, `regional_defaults`, `well_overrides`; each parameter carries `value`, `unit`, `provenance`, `source_description` (`src/params/schema.py`)
- [ ] Populate `regional_defaults.paleozoic_kansas`: gr_min/gr_max, variant=old_rocks, rho_ma, rho_fl, phie_max, a, m, n, Rw, rt_hydrocarbon_floor, vsh/phie/sw cutoffs, bit_size_config, qc_abort_threshold, circuit_breaker_n (`src/params/regional_defaults.json`)
- [ ] Populate `regional_defaults.north_sea_jurassic` with VOLVE-compatible defaults for Rw, a, m, n, matrix density (variant set for Jurassic) (`src/params/regional_defaults.json`)
- [ ] Implement `well_overrides` lookup: per-well UWI overrides take precedence over regional defaults; absent UWI falls through with `provenance = default` (`src/params/config_loader.py`)
- [ ] Implement PROV-tag-driven Larionov variant selection: `paleozoic`→old_rocks, `tertiary`→tertiary, absent/unrecognised→old_rocks + degradation entry (`src/params/config_loader.py`)
- [ ] Implement mnemonic alias table covering GR, RHOB (RHOZ, DEN), NPHI (NPOR, TNPH), RT (ILD, RDEEP, AT90), CALI (CAL, C1), DCAL (CALX, CALY) (`src/params/mnemonic_aliases.json`)
- [ ] Implement config hash computation (SHA-256 of the JSON file) and log into ledger `run.config_hash_sha256` at pipeline start (`src/params/config_loader.py`)
- [ ] Define and implement the static citations-table schema (per parameter: value/default, valid range, source author/year, locator page/DOI, applicability scope) seeded with Archie 1942, Larionov 1969 old-rocks, and KGS/USGS Schaben values; wire it to the ledger so each parameter selection emits a frozen citation (no RAG) (`src/params/citations.py`, `src/params/citations.json`)
- [ ] Tests for provenance lookup, PROV-tag routing, alias resolution, hash computation, well-override precedence, and citations resolution (every parameter resolves to exactly one source; unknown parameter hard-fails) (`tests/test_params.py`)

### Phase 3 — Independent validators
Done when: the validator harness in `src/validators/` runs to completion on computed Vsh/PHIE/Sw arrays and returns a typed objection list; the model-mismatch validator produces a neutron-density crossplot PNG and a Pickett-plot PNG in `outputs/` (the M-N crossplot is deferred for v1, gated on DT/PEF presence, with the existing `mn_skipped_no_dt` degradation path retained); all validator modules have golden tests that pass.
- [ ] Implement physical-bounds validator: Vsh, PHIE, Sw against [0,1] and [0, phie_max]; violations typed `mechanical`; version logged (`src/validators/physical.py`, version 0.1.0)
- [ ] Implement cross-curve consistency validator: Vsh–PHIE anti-correlation (Pearson ≤ +0.3, ±20-sample window); RT–Sw directional consistency; violations typed `support` (`src/validators/cross_curve.py`, version 0.1.0)
- [ ] Implement model-mismatch validator: neutron-density crossplot vs. sandstone/limestone/dolomite reference lines (flag if > 30% outside mineral triangle); M-N crossplot deferred for v1 (gated on DT/PEF presence — skipped with `mn_skipped_no_dt` degradation when DT/PEF absent, which is the v1 default); violations typed `irreducible` (`src/validators/model_mismatch.py`, version 0.1.0)
- [ ] Implement data-quality propagation validator: enforce tier downgrade for any FIRM computation at a DEGRADED depth; flag missing degradation records as internal consistency errors (`src/validators/data_quality.py`, version 0.1.0)
- [ ] Implement crossplot PNG generation: neutron-density (1200×900 px, 300 dpi, viridis depth colormap, lithology reference lines) to `outputs/<UWI>_<YYYY-MM-DD>_crossplot_nd.png`, and a Pickett plot (log-log RT vs. PHIE with Sw/Rw/m reference lines, an Archie transform) to `_pickett.png`; the M-N crossplot (Schlumberger 1989 reference points → `_crossplot_mn.png`) is deferred for v1, emitted only when DT/PEF is present (`src/validators/crossplot.py`)
- [ ] Implement `typify_objections` stage: deterministic Python; splits into `correctable_objections` (mechanical + support) and `irreducible_objections`; computes `correctable_count` (`src/orchestrator/stages.py`)
- [ ] Tests for each validator module and the typing stage (`tests/test_validators.py`, `tests/test_typify.py`)

### Phase 4 — Orchestrator and loop
Done when: a single LangGraph call on a Kansas/Schaben LAS runs the deterministic stages from `load` through `emit` without human intervention, emitting `ledger.json` plus the Phase 3 crossplot PNGs but not `report.md`; the `zonate` stage delineates cutoff-delimited net-pay zones and writes per-zone net-pay computations to the ledger; a deterministic field-aggregation pass over multiple per-well ledgers produces a field rollup (aggregate net pay/NTG/HCPV + per-well summary table) and writes it to a field ledger; the circuit breaker fires correctly via a deterministic stub `correct` node on a synthetic non-converging input; `convergence_status` is written to the ledger.
- [ ] Implement the LangGraph `StateGraph` with state fields (`las_path`, `config_path`, `curves`, `quality_map`, `vsh`, `phie`, `sw`, `ledger`, `objections`, `correctable_count`, `iteration`, `prev_correctable`, `confidence_tiers`, `convergence_status`, `draft_report`) (`src/orchestrator/graph.py`)
- [ ] Wire pipeline stages as deterministic LangGraph nodes: `load`, `qc_gate`, `compute`, `validate`, `typify_objections`, `gating`, `zonate`, `emit` (`src/orchestrator/stages.py`)
- [ ] Implement loop edges: route to `correct` when `correctable_count > 0` and breaker not triggered, else to `gating`; `correct`→`compute`→`validate`; `correct` is a deterministic no-op stub this phase (`src/orchestrator/graph.py`)
- [ ] Implement circuit breaker: track `consecutive_non_decrease`; fire when count ≥ N (N=3 from config); set `convergence_status = DID_NOT_CONVERGE`; route to `gating` (`src/orchestrator/stages.py`)
- [ ] Implement `gating` stage: assign FIRM / QUALIFIED / BRACKETED from parameter provenance; one-tier downgrade per irreducible objection, floor at BRACKETED; write `convergence_status` to ledger (`src/orchestrator/stages.py`)
- [ ] Implement `zonate` stage: read cutoffs from config, call `apply_cutoffs`, delineate contiguous net-pay runs into zones, call `compute_net_pay` per zone, assign each zone the lowest contributing tier, append per-zone `net_pay` entries and expose `pipeline_net_pay_m` (`src/orchestrator/stages.py`)
- [ ] Implement `emit` stage: ledger completeness gate (all computation_ids and validator_ids resolve); prepend DID_NOT_CONVERGE warning block when applicable; write ledger.json and crossplot PNGs to `outputs/` (`src/orchestrator/stages.py`)
- [ ] Implement version-pinning check at `load`: verify installed lasio, numpy, langgraph versions match `pyproject.toml` pins; abort on mismatch; log versions in `run` object (`src/orchestrator/stages.py`)
- [ ] Implement deterministic field-aggregation pass: roll up per-well ledgers across the Schaben field into aggregate net pay/NTG/HCPV plus a per-well summary table; emit a field ledger (no LLM; arithmetic over per-well outputs) (`src/field/rollup.py`)
- [ ] Integration test: end-to-end run writes ledger.json (with per-zone `net_pay` entries) plus crossplot PNGs; the field-aggregation pass over multiple per-well ledgers writes a field rollup with aggregate net pay/NTG/HCPV; circuit-breaker test drives the `correct` stub on synthetic non-converging input and produces a `DID_NOT_CONVERGE` entry (`tests/test_pipeline.py`)

### Phase 5 — Local LLM agents (Ollama)
Done when: a single end-to-end pipeline run on a Kansas/Schaben well produces a Markdown prose report and a complete JSON ledger; a field-summary writer pass produces the whole-field report (per-well blocks plus the field rollup, a cross-well zone-correlation panel, and a field net-pay/quality map); the claim verifier finds zero residual flags; the `claim_verifier` ledger entry carries `result = PASS`.
- [ ] Implement compute agent: receives correctable objections and current parameters, selects revised parameters from the config library via Qwen3:30b-a3b (Ollama), never authors equations; flags data-limited objections for reclassification when no valid parameter exists (`src/agents/compute_agent.py`)
- [ ] Implement writer agent: receives read-only ledger and per-block confidence tiers; generates prose per the report schema, tone bound to each block's tier (FIRM→declarative, QUALIFIED→qualified, BRACKETED→bounded); Qwen3:30b-a3b via Ollama (`src/agents/writer.py`)
- [ ] Implement claim verifier: audits draft sentence by sentence on four conditions (value traces to ledger, BRACKETED no point estimates, QUALIFIED hedges, Limitations names default-provenance params); returns flags for one correction pass; removes unresolvable sentences as degradation entries (`src/agents/claim_verifier.py`)
- [ ] Wire compute agent as the `correct` LangGraph node (`src/orchestrator/graph.py`)
- [ ] Wire writer and claim verifier as `write` and `claim_verify` LangGraph nodes (`src/orchestrator/graph.py`)
- [ ] Pin LLM seed (`run.llm_seed`) at invocation; log model tags in `run.model_tags`; verify Ollama determinism on the target build; log degradation if seed non-determinism is confirmed (`src/agents/ollama_client.py`)
- [ ] Resolve decision (d) — RAG vs. system-prompt knowledge for parameter justification: RESOLVED as no RAG for v1 (the Phase-2 static citations table supplies provenance); document the knowledge boundary so the writer only renders the citation it is handed (`src/agents/compute_agent.py`)
- [ ] Implement field-summary writer pass: generate the whole-field report from the field ledger (per-well prose blocks plus the field rollup narrative), tone bound to each block's tier; render the cross-well zone-correlation panel and the field net-pay/quality map figures (`src/field/field_writer.py`, `src/field/field_figures.py`)
- [ ] End-to-end test: pipeline on a Kansas LAS produces report.md, a ledger.json with `claim_verifier result = PASS`, and no unresolved flags; a multi-well run produces the field report with the rollup, zone-correlation panel, and field net-pay/quality map (`tests/test_e2e.py`)

### Phase 6 — Adversarial reviewer
Done when: a second adversarial agent reviews the draft before the claim verifier; objections from the adversarial reviewer route through `typify_objections` and feed the loop; generator and critic use decorrelated models or prompts; design decision (a) is resolved and recorded in the manifest.
- [x] Decision (a) — RESOLVED (2026-06-25): adversarial reviewer uses the second model family Llama3.1:8b; recorded in `planning/blueprint/MANIFEST.md`
- [ ] Implement adversarial reviewer: receives draft report and ledger; produces a typed objection list (mechanical / support / irreducible) rewarded for finding faults; uses the chosen model (`src/agents/reviewer.py`)
- [ ] Wire adversarial reviewer before `claim_verify`; reviewer objections route back through `typify_objections` so correctable ones re-enter the compute→validate loop (`src/orchestrator/graph.py`)
- [ ] Log reviewer model tag and seed in `run.model_tags` (`src/agents/ollama_client.py`)
- [ ] Test: adversarial reviewer introduces a mechanical objection on a synthetic draft; the loop re-enters `compute` and resolves it before re-entering `write` (`tests/test_reviewer.py`)

### Phase 7 — Uncertainty and confidence
Done when: the pipeline propagates parameter uncertainty through Vsh, PHIE, and Sw computations via Monte Carlo per-depth sampling and writes true-percentile P10/P50/P90 slots in the ledger; sensitivity analysis identifies the dominant parameter for net pay; the multi-seed robustness check passes; the ECE threshold is set, logged as a manifest decision, and the reliability diagram infrastructure is in place.
- [ ] Resolve decision (c) — uncertainty propagation method: CLOSED as Monte Carlo per-depth sampling (true distributional outputs, not analytic ranges); record in `planning/blueprint/MANIFEST.md`; implement with seed management and `run.monte_carlo_seeds` (`src/uncertainty/propagation.py`)
- [ ] Resolve decision (b) — hard abstention policy (refuse to emit when no high-leverage parameter is calibrated); record in `planning/blueprint/MANIFEST.md`; implement the gating-stage abstention path if chosen (`src/orchestrator/stages.py`)
- [ ] Implement Monte Carlo uncertainty propagation: per-depth parameter sampling through Vsh, PHIE, Sw; P10/P50/P90 are true percentiles of the sampled distribution; written to `computations[].result_p10`, `result_p50`, and `result_p90`; sampling widths from config defaults (`src/uncertainty/propagation.py`)
- [ ] Implement sensitivity analysis: identify which of a, m, n, Rw contributes most to net-pay uncertainty per zone; log as ledger metadata and require the writer to mention it in the zone Limitations sub-section (`src/uncertainty/sensitivity.py`)
- [ ] Implement multi-seed robustness check: three fixed seed sets; P50 agreement within 1% relative, P10–P90 widths within 5%, consistent tier; failures logged as degradation with `confidence_impact = uncertainty_widening` (`src/evaluation/robustness.py`)
- [ ] Implement ECE and reliability diagram infrastructure: `compute_mae`, `compute_net_pay_deviation`, `compute_ece`, `plot_reliability_diagram` (`src/evaluation/volve_metrics.py`)
- [ ] Set and log ECE threshold: provisional ECE measurement on a non-benchmark VOLVE subset (raw LAS curves only); propose threshold; record as a manifest decision (`planning/blueprint/MANIFEST.md`)
- [ ] Tests for propagation, sensitivity analysis, robustness check, and metric functions (`tests/test_uncertainty.py`, `tests/test_volve_metrics.py`)

### Phase 8 — Traceability and evaluation
Done when: the pipeline produces a complete JSON ledger in which every emitted number traces in O(1) to its source; a full unattended run on VOLVE benchmark wells satisfies all four regression thresholds (PHIE MAE < 0.03, Vsh MAE < 0.10, Sw MAE < 0.15, net pay within ±20% per well); and the reliability diagram and ECE measurement are emitted to `outputs/evaluation/`.
- [ ] Verify and complete ledger coverage: every `computation` and `validator` entry carries all required fields; every `degradation` entry has `confidence_impact`; ledger completeness gate enforced at `emit` (`src/orchestrator/stages.py`)
- [ ] Implement full run metadata pinning: git commit SHA of `src/`, pipeline version, lasio/numpy/langgraph/ollama_client versions, model tags, config hash, LAS SHA-256, LLM seed, monte_carlo_seeds — written to the ledger `run` object at start (`src/orchestrator/stages.py`)
- [ ] Implement VOLVE mnemonic alias mapping: RHOZ→RHOB, NPOR→NPHI, and other Equinor mnemonics confirmed from raw VOLVE LAS headers (not interpretation files) (`src/params/mnemonic_aliases.json`)
- [ ] Implement VOLVE regression runner: invokes the full pipeline on each benchmark well, collects per-well MAE and net-pay deviation via the Phase 7 metrics, writes results to `outputs/evaluation/` (`src/evaluation/volve_runner.py`)
- [ ] Run VOLVE regression: confirm PHIE MAE < 0.03, Vsh MAE < 0.10, Sw MAE < 0.15, net pay within ±20% per well; emit reliability diagram to `outputs/evaluation/calibration_reliability_diagram.png` (`src/evaluation/volve_runner.py`)
- [ ] Regression golden test: encode the four thresholds as assertions; must pass (`tests/regression/test_volve_regression.py`)
- [ ] Confirm minimum three VOLVE wells carry complete reference Vsh/PHIE/Sw curves; if fewer than three, block Phase 8 with a foundation gap report (`src/evaluation/volve_runner.py`)

## Conventions
- Code and comments in English; `snake_case`; petrophysical symbols keep domain names
  (`vsh`, `phie`, `sw`, `rhob`, `nphi`, `gr`, `rt`).
- Every quantitative function is frozen + golden-tested before any agent may call it.
- One task = one action; mark `[x]` with date on completion; never delete tasks.
- Parked design decisions (a) Phase 6, (b)/(c) Phase 7, (d) Phase 5, (e) Phase 7 exit —
  resolve in-phase and record in the manifest; never forget.
- Confidence is dual: procedural (provenance-tiered, tone-bound by policy-as-code) from
  v1, and statistical (reliability diagram + ECE on VOLVE) — both required for v1.
