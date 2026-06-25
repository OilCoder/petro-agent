# Pipeline Architecture — petro-agent

This document specifies the deterministic LangGraph state machine that owns the
per-report execution loop. It builds on the stage sequence sketched in the design
notes (agente-autonomo-informes-petrofisicos.md) and on the contracts fixed in
`03_source_sink_contracts.md`. Together they define what runs, in what order, under
what gating conditions, and how the loop terminates.

---

## Stages

The pipeline is a fixed sequence of named stages. Each stage is a LangGraph node.
Edges between nodes are deterministic Python conditionals — no LLM decides a
transition.

```
load → qc_gate → compute → validate → typify_objections
    → [correct → recompute]* → gating → zonate → write → review → claim_verify → emit
```

The bracketed `[correct → recompute]*` section is the refinement loop: it iterates
until the termination predicate is satisfied (see Orchestration below).

The `review` stage (the dedicated adversarial reviewer) is added in Phase 6; before
Phase 6 the sequence runs `write → claim_verify → emit` directly. The reviewer is a
distinct stage from `claim_verify` — see "The adversarial reviewer and the claim
verifier" under Stage 9b for how the two adversarial roles are separated rather than
conflated.

### Stage 1 — `load`

**Purpose**: ingest the LAS file, apply the mnemonic alias map, normalise depth to
metres, and produce a typed internal structure ready for QC.

**Inputs**: LAS file path (string), config file path (string).

**Actions**:
1. Load the file with lasio, guarding against the `~Other`-before-`~Curve` crash
   (re-order sections before parse; log a `section_reorder` edit if triggered).
2. Apply the mnemonic alias table from `src/params/mnemonic_aliases.json` —
   first match wins; unrecognised mnemonics are passed through unchanged.
3. Detect unit variants: if `NPHI_max > 2.0` convert (`NPHI / 100`) and log a
   `unit_conversion` edit; if `RHOB_max > 10.0` convert (`RHOB / 1000`) and log
   similarly; if the value falls in an ambiguous zone (NPHI between 1.0 and 2.0)
   abort with a diagnostic requiring the operator to confirm units.
4. Verify that all hard-required curves are present (GR, RHOB, NPHI, RT); reject
   with an error naming any missing curve. No partial run. CALI and DCAL are optional
   (bad-hole masking degrades when absent — see `qc_gate` and
   `03_source_sink_contracts.md`).
5. Verify `PROV` header field; if absent or unrecognised, degrade to `unknown` and
   log a `degradation` entry specifying the Larionov fallback applied.
6. Verify depth monotonicity; reject with the depth of the first violation if not.
7. Normalise depth to metres (factor 0.3048 for feet-sourced files; log in ledger).
8. Pin and log the config hash (SHA-256 of the parameter JSON), the git commit SHA
   of `src/`, the lasio/numpy/langgraph library versions, and the LAS null sentinel.

**Outputs**: typed depth-indexed curve dict (numpy float64 arrays), well metadata
struct, validated config dict, ledger `run` and `well` objects, `edits` list.

**Exit condition**: all outputs present and valid. Any violation is a hard abort.

---

### Stage 2 — `qc_gate`

**Purpose**: produce a per-depth data-quality map and mask bad data before any
quantitative computation touches it.

**Inputs**: depth-indexed curve dict from `load`.

**Actions**:
1. Apply the lasio null sentinel mask; any sample equal to the sentinel (within
   1e-3 tolerance) is masked across all curves at that depth.
2. Spike detection on GR, RHOB, NPHI, RT: flag samples exceeding 5 × inter-quartile
   range above the local median in a ±10-sample window; log each spike as a
   `spike_removal` edit with the original value and the depth.
3. Bad-hole masking: if `DCAL` is present, flag depths where `|DCAL| > 2 inches`
   as bad hole; if `DCAL` is absent but `CALI` is present, flag depths where
   `CALI > (bit_size_config + 2)` inches. If both `DCAL` and `CALI` are absent,
   bad-hole masking cannot run — RHOB/NPHI are not bad-hole-masked and a degradation
   entry (`confidence_impact = tier_downgrade`) is logged for the affected PHIE
   computations. Bad-hole samples for RHOB and NPHI (when masking runs) are masked and
   their depth ranges appended to the data-quality map as `DEGRADED`.
4. Physical-range sanity on unmasked samples: RHOB outside [1.0, 3.0], NPHI outside
   [0.0, 1.0], GR outside [0, 300], RT outside [0.01, 50000] → flag as `WARN` in
   the data-quality map; do not mask (the sample may be a genuine extreme value).
5. Build the per-depth data-quality map: each depth sample is tagged
   `GOOD | DEGRADED | EXCLUDED`. `EXCLUDED` = all required curves masked, or GR and RT
   both masked; `DEGRADED` = at least one of RHOB/NPHI masked while GR and RT remain;
   `GOOD` = no masking. (The 10-sample minimum is a whole-log intake check at `load`,
   not a per-depth tag — see `03_source_sink_contracts.md`.)
6. If more than 80% of the depth range is `EXCLUDED` or `DEGRADED`, abort the run
   with a diagnostic. A run with negligible usable data is not a valid run.

**Outputs**: masked curve dict, per-depth data-quality map, updated `edits` list.

**Exit condition**: quality map produced and the 80% threshold not exceeded.

---

### Stage 3 — `compute`

**Purpose**: run the three deterministic petrophysical calculations on the masked
curves using the parameter config.

**Inputs**: masked curve dict, validated config dict, per-depth data-quality map.

**Actions**:
1. Select Larionov variant from `PROV` header: `paleozoic` → old-rocks formula;
   `tertiary` → Tertiary formula; `unknown` → old-rocks with a degradation entry.
2. Call `src.petrophysics.vsh.calc_vsh(gr, gr_min, gr_max, variant)` → Vsh array.
3. Call `src.petrophysics.phie.calc_phie(rhob, nphi, rho_ma, rho_fl)` → PHIE array.
   If RHOB or NPHI is masked at a depth, fall back to density-only or neutron-only
   PHIE; log the fallback as a degradation with `confidence_impact = tier_downgrade`.
4. Call `src.petrophysics.sw.calc_sw(rt, phie, a, m, n, rw)` → Sw array.
5. For depths in the `EXCLUDED` quality tier, all three outputs are set to NaN and
   do not produce a `computations` ledger entry.
6. For each non-excluded depth range, append a `computation` entry to the ledger:
   `{computation_id, depth_range_m, output_curve, function, function_version,
   function_module, input_curves, parameters, parameter_provenance,
   parameter_source, result_p50, confidence_tier, validator_ids=[]}`.
   P10 / P90 slots are left null until Phase 7 adds uncertainty propagation.

**Outputs**: Vsh/PHIE/Sw arrays (numpy float64, NaN where excluded), updated ledger
`computations` list, updated `degradations` list.

**Exit condition**: at least one depth range produced a non-NaN computation.

---

### Stage 4 — `validate`

**Purpose**: run the complete fixed validator harness against the computed curves;
collect all objections.

**Inputs**: Vsh/PHIE/Sw arrays, masked curve dict, ledger `computations` list.

**Actions (validator suite — fixed, versioned, external to the agents)**:

1. **Physical bounds** (`src.validators.physical`):
   - Vsh ∈ [0.0, 1.0] for all non-NaN depths.
   - PHIE ∈ [0.0, phie_max] for all non-NaN depths (upper bound from config).
   - Sw ∈ [0.0, 1.0] for all non-NaN depths.
   - Violation → `objection_type = mechanical`.

2. **Cross-curve consistency** (`src.validators.cross_curve`):
   - Vsh–PHIE anti-correlation: in a ±20-sample window, the Pearson correlation
     between Vsh and PHIE must be ≤ +0.3 (shale volumes should not co-occur with
     high porosity without explanation). Strong positive correlation is flagged.
   - RT vs. Sw directional consistency: at depths where computed Sw < 0.4, RT must
     exceed `rt_hydrocarbon_floor` (low Sw co-occurring with low RT is implausible
     without a model-mismatch flag).
   - Violation → `objection_type = support`.

3. **Model-mismatch detection** (`src.validators.model_mismatch`; active from Phase 3):
   - Neutron-density cross-plot: compute position relative to the sandstone,
     limestone, and dolomite reference lines using the matrix density values from the
     config. If more than 30% of non-excluded depths fall outside the mineral triangle,
     raise a `model_mismatch` flag. For v1 the model-mismatch validator relies on this
     neutron-density cross-plot alone.
   - M-N cross-plot (OPTIONAL — DEFERRED for v1): gated on DT/PEF presence; compute M
     and N indices; compare against Schlumberger (1989) reference points; flag
     deviations beyond 0.1 index units as `model_mismatch`. When DT (and PEF) are
     absent the M-N check is skipped and a degradation entry (`validator_id:
     mn_skipped_no_dt`) is logged — see `05_engine_and_validation.md`. For v1 this
     branch defaults off (no M-N artifact emitted); it activates only when DT/PEF are
     present.
   - These are the only validators that generate PNG cross-plot outputs (see
     `03_source_sink_contracts.md`). For v1 only the neutron-density cross-plot PNG is
     emitted; the M-N PNG is deferred behind the DT/PEF gate above.
   - Violation → `objection_type = irreducible` (model mismatch cannot be corrected
     by the agents; it is recorded and propagates to a tier downgrade).

4. **Data-quality propagation** (`src.validators.data_quality`):
   - For each `DEGRADED` zone: if the computation used a degraded input (masked
     RHOB or NPHI), flag `data_limited`.
   - Violation → `objection_type = irreducible` (data quality is a fact of the
     input, not correctable).

5. Each validator call appends a `validator` entry to the ledger:
   `{validator_id, validator_name, validator_version, depth_range_m, check_type,
   input_curves, result, objection_type, message}`. The `validator_ids` field of
   the affected `computation` entry is updated.

**Outputs**: objection list (typed), updated ledger `validators` list.

**Exit condition**: validator harness ran to completion (even if objections were raised).

---

### Stage 5 — `typify_objections`

**Purpose**: classify every objection as mechanical, support, or irreducible — the
classification that drives loop routing.

**Inputs**: objection list from `validate`.

**Typing rules (deterministic; applied by the orchestrator, not an LLM)**:

| Objection class | Trigger | Loop action |
|---|---|---|
| `mechanical` | Physical bound violated (Vsh < 0, Sw > 1, etc.) — anchored to a testable external fact | Must be corrected by the compute agent; loop continues |
| `support` | A claim in the current draft is not supported by the presented evidence ("not justified by what is presented") — resolvable with better parameter selection or richer justification | Must be addressed by the compute agent or writer; loop continues |
| `irreducible` | Cannot be resolved without data the run does not have (no core, model mismatch confirmed, data-limited zone) | NOT cycled; escalated to the ledger and confidence tier; loop does not re-enter to address this objection |

The `typify_objections` stage reads the validator results and applies the typing
rules above. It produces a split list: `correctable_objections` (mechanical + support)
and `irreducible_objections`.

**Outputs**: `correctable_objections` list, `irreducible_objections` list,
`correctable_count` integer.

---

### Stage 6 — `correct` (conditional — loop body)

**Purpose**: address correctable objections: adjust parameter selection or
computation inputs and re-enter `compute`.

**Entry condition**: `correctable_count > 0` AND circuit breaker not triggered
(see Orchestration below).

**Actor**: compute agent (Qwen3:30b-a3b via Ollama). The agent reads the objection
list and selects revised parameters from the vetted config library. It does not
author equations. It does not choose which validators fire. It does not address
irreducible objections.

**Permitted actions**:
- Select a different parameter value from the config library (e.g., switch from
  regional-default `m` to an offset-calibrated `m` if one exists for this formation).
- Adjust GR min/max bounds for Vsh computation within the physical range declared
  in config.
- Flag that a parameter cannot be resolved from the available config
  (which routes the objection to `irreducible` on the next `typify_objections` pass).

**Forbidden actions** (enforced by the orchestrator, not advisory):
- The compute agent may not modify the validator harness.
- The compute agent may not write new mathematical expressions.
- The compute agent may not override the confidence tier assigned by the gating stage.

**Outputs**: revised parameter selections (dict); the orchestrator routes back to
`compute` with these revisions.

---

### Stage 7 — `gating`

**Entry condition**: `correctable_count == 0` (only irreducible objections remain)
OR circuit breaker triggered.

**Purpose**: assign the final confidence tier to each computation block from
parameter provenance and remaining objections; determine the run convergence status.

**Actions**:
1. For each computation block, determine the confidence tier:
   - All high-leverage parameters (`a`, `m`, `n`, `Rw`) are `core` or `offset` with
     narrow range → `FIRM`.
   - At least one high-leverage parameter is `offset` with moderate range → `QUALIFIED`.
   - Any high-leverage parameter is `default` with no local calibration → `BRACKETED`.
2. Downgrade the tier if irreducible objections affect the block:
   - `model_mismatch` flag → downgrade one tier (FIRM→QUALIFIED; QUALIFIED→BRACKETED).
   - `data_limited` flag → downgrade one tier.
   - Multiple irreducible flags on the same block → floor at `BRACKETED`.
3. Record `convergence_status`:
   - `CONVERGED` if the loop exited because `correctable_count == 0`.
   - `DID_NOT_CONVERGE` if the circuit breaker fired.
4. Write the final confidence tier into each `computation` ledger entry.

**Outputs**: per-block confidence tiers (dict), `convergence_status` string, updated
ledger `computations` list.

---

### Stage 7b — `zonate`

**Purpose**: delineate cutoff-delimited reservoir zones from the computed Vsh/PHIE/Sw
curves, apply the net-pay cutoffs, and compute per-zone net pay. This is the stage that
turns per-depth curves into the zone blocks the report schema and the VOLVE net-pay
metric depend on.

**Inputs**: Vsh/PHIE/Sw arrays, per-depth data-quality map, per-block confidence tiers
(from `gating`), validated config dict (cutoffs).

**Actor**: deterministic (`src.orchestrator.stages.zonate`, calling the net-pay engine
function). No LLM participates; cutoffs and zone boundaries are computed, never authored
at runtime.

**Actions**:
1. Read the three net-pay cutoffs from the config library: `vsh_cutoff`, `phie_cutoff`,
   `sw_cutoff` (provenance logged like any other parameter).
2. Compute the per-depth net-pay flag via
   `src.petrophysics.netpay.apply_cutoffs(vsh, phie, sw, vsh_cutoff, phie_cutoff, sw_cutoff)`
   → boolean array: a depth is net pay when `Vsh ≤ vsh_cutoff AND PHIE ≥ phie_cutoff
   AND Sw ≤ sw_cutoff`. `EXCLUDED` and NaN depths are never net pay.
3. Delineate zones from the net-pay flag: contiguous runs of net-pay depths (allowing a
   configurable maximum non-pay gap to merge adjacent runs) become reservoir zones; each
   zone carries `[top_md, base_md]`.
4. Compute per-zone net pay via
   `src.petrophysics.netpay.compute_net_pay(depth, net_pay_flag, depth_step_m)`:
   gross thickness (zone span), net pay (summed net-pay sample thickness), and
   net-to-gross ratio.
5. Assign each zone the lowest confidence tier of any computation block that contributes
   to its net pay (zone tier = min over contributing Vsh/PHIE/Sw blocks).
6. Append a `computation` entry per zone with `output_curve = "net_pay"`,
   `computation_id` (e.g. `net_pay_zone_2`), the cutoffs in `parameters`, the cutoff
   provenance in `parameter_provenance`, `result_p50 = net_pay_m`, and the zone tier.
   The Vsh/PHIE/Sw `computation_id`s created in `compute` (e.g. `vsh_zone_2`) are now
   keyed to these delineated zones.

**Outputs**: zone list (`[{top_md, base_md, gross_m, net_pay_m, ntg, tier, cutoffs}]`),
updated ledger `computations` list (per-zone net-pay entries), `pipeline_net_pay_m`
(per-zone and well-total) consumed by the VOLVE net-pay metric in
`06_evaluation_protocol.md`.

**Exit condition**: the zone list and per-zone net-pay computations are produced (a well
with no net-pay depths produces an empty zone list, which is a valid result).

---

### Stage 8 — `write`

**Purpose**: generate the prose report sections from the ledger, bound by the
confidence tier of each block.

**Actor**: writer agent (Qwen3:30b-a3b via Ollama). The writer receives the ledger
(read-only) and the per-block confidence tiers (read-only). It has no access to the
raw curves or the validator harness.

**Tone policy** (enforced by the claim verifier in the next stage — not advisory):

| Tier | Permitted language |
|---|---|
| `FIRM` | Declarative: "The interval shows…", "Net pay is N metres." |
| `QUALIFIED` | Qualified: "The interpretation suggests…", "Net pay is approximately N metres." Uncertainty range must be stated. |
| `BRACKETED` | Explicitly bounded: "Given the absence of core calibration, Sw ranges from X to Y (P10–P90). The point estimate of N should not be used without offset calibration." The limitation must appear in the Limitations sub-section. |

The writer follows the report schema defined in `03_source_sink_contracts.md`
(zone blocks with fixed sub-sections, Conclusions, Limitations and confidence statement).

**Outputs**: draft prose report (Markdown string).

---

### Stage 9a — `review` (adversarial reviewer — active from Phase 6)

**Purpose**: subject the draft report and the ledger to an independent adversarial
review whose goal is to find faults — overclaims, unsupported interpretations,
parameter selections that the evidence does not justify — before the deterministic
claim verifier runs. This stage is introduced in Phase 6; prior to Phase 6 the
pipeline transitions `write → claim_verify` directly.

**Actor**: adversarial reviewer (`src.agents.reviewer`). The model choice — Llama3.1:8b
(second model family, stronger decorrelation) versus an adversarial-role prompt on
Qwen3:30b-a3b (lower operational complexity) — is Charter Open question (a), deferred
to Phase 6 and recorded in the manifest at Phase 6 entry. The reviewer is rewarded for
finding faults, not for approving the draft.

**Actions**:
1. Read the draft report and the ledger (read-only).
2. Produce a typed objection list (`mechanical` / `support` / `irreducible`) using the
   same objection vocabulary as the validator harness.
3. The objection list is routed back through `typify_objections`: correctable
   objections (`mechanical` + `support`) re-enter the `correct → compute → validate`
   refinement loop; irreducible objections escalate to the gating stage and the
   confidence tier. The reviewer does not author equations, does not select parameters,
   and does not write to the validator harness.

**Outputs**: typed reviewer objection list routed to `typify_objections`.

**The adversarial reviewer and the claim verifier — two distinct roles**:

The `claim_verifier` (Stage 9b) carries an "adversarial prompt role" in the sense that
it is rewarded for finding overclaims rather than for approving prose. The Phase 6
`review` stage is a separate, dedicated adversarial agent. The two are not the same
node and must not be conflated:

- **`review` (Stage 9a, Phase 6)** is a *generative* adversarial critic. It can raise
  any of the three objection types about the *interpretation itself* (parameter choice,
  lithology assumption, justification quality), and its correctable objections re-enter
  the compute→validate loop to change the numbers or parameters. It runs before
  `claim_verify`.
- **`claim_verifier` (Stage 9b)** is a *bounded* prose auditor. It does not re-enter the
  compute loop; it checks the draft prose sentence-by-sentence against the ledger that
  the loop already produced, and any flag it raises is resolved in a single writer
  round-trip (or the sentence is removed). Its "adversarial prompt role" governs only
  this prose-vs-ledger audit, not the interpretation.

In short: `review` can change what the numbers are; `claim_verify` can only change what
the prose is allowed to say about numbers the ledger has already fixed.

---

### Stage 9b — `claim_verify`

**Purpose**: audit the draft prose sentence by sentence and confirm no sentence
asserts more certainty than the ledger supports.

**Actor**: claim verifier (Qwen3:30b-a3b via Ollama; adversarial prompt role —
rewarded for finding overclaims, not for approving the draft). This "adversarial
prompt role" is scoped to the prose-vs-ledger audit only; it is distinct from the
dedicated Phase 6 `review` stage (Stage 9a), which is a separate node that can re-enter
the compute loop. See "The adversarial reviewer and the claim verifier" under Stage 9a.

**Checks**:
1. Every sentence that contains a numerical value: does the value appear in a ledger
   `computation` entry reachable by `(depth_range_m, output_curve)`? If not, flag as
   an unsupported claim.
2. Every sentence in a `BRACKETED` block: does it contain a declarative assertion
   about a point estimate without stating the propagated range? If yes, flag.
3. Every sentence in a `QUALIFIED` block: does it use the word "is" without a
   qualifying hedge ("approximately", "suggests", "estimated")? If yes, flag.
4. Does the Limitations sub-section explicitly name every parameter that is
   `provenance = default`? If not, flag.

If any flags are raised, the verifier returns them to the writer for targeted
correction. This exchange is a fixed single round-trip (not a nested loop). If the
writer cannot resolve the flag within one pass (e.g., the claim is structurally
unsupportable given the data), the sentence is removed and the flag is recorded in
the ledger as a `degradation` entry with `confidence_impact = exclusion`.

**Outputs**: approved prose report (Markdown string), updated ledger `degradations`
list if any claims were removed.

---

### Stage 10 — `emit`

**Purpose**: verify ledger completeness and write all output artifacts to disk.

**Actions**:
1. Ledger completeness gate:
   - Every `computation_id` referenced in the report resolves to a `computations`
     entry. Fail if not.
   - Every `validator_id` referenced in a `computation` entry resolves to a
     `validators` entry. Fail if not.
   - Every quantitative claim in the prose resolves to a `computation` entry via
     `(depth_range_m, output_curve)`. Fail if not.
   Failure emits a diagnostic naming the unresolved reference and halts without
   writing any output files.
2. If `convergence_status == DID_NOT_CONVERGE`, prepend a warning block to the
   report: "This report did not converge within the configured iteration limit.
   Unresolved objections are listed in the ledger. Results should be reviewed before
   use." The ledger records the unresolved objections in `validators` with
   `result: WARN`.
3. Write `outputs/<UWI>_<YYYY-MM-DD>_report.md`.
4. Write `outputs/<UWI>_<YYYY-MM-DD>_ledger.json`.
5. Write cross-plot PNGs (active from Phase 3): for v1, the neutron-density
   cross-plot `outputs/<UWI>_<YYYY-MM-DD>_crossplot_nd.png` only. The M-N cross-plot
   `_crossplot_mn.png` is OPTIONAL/DEFERRED — emitted only when DT/PEF are present
   (see Stage 4 model-mismatch detection); when DT is absent it is not written and the
   `mn_skipped_no_dt` degradation is recorded.

**Outputs**: three artifact files on disk; nothing returned to the orchestrator
(the per-well run is complete).

---

## Field-scale aggregation (whole-field scope)

v1 scope is **whole-field**: the pipeline above runs **per well** (one LAS → one
ledger → one report block), unchanged, for every well in the Schaben field. After
all per-well runs complete, two deterministic field-scale passes run on top of the
per-well ledgers. The per-well deterministic path and the LLM-never-computes
invariant are untouched — these passes are **deterministic aggregation over outputs
the engine already produced**, not new petrophysical computation.

### Stage 11 — `field_aggregate`

**Purpose**: roll up the per-well results into field-level totals and a cross-well
zonation, from the per-well ledgers only.

**Inputs**: the set of per-well ledgers and zone lists produced by the per-well runs
(`outputs/<UWI>_<YYYY-MM-DD>_ledger.json` for every well in the field).

**Actor**: deterministic (`src.orchestrator.stages.field_aggregate`). No LLM
participates; field totals and zone correlation are computed, never authored at
runtime.

**Actions**:
1. Aggregate net pay / NTG / HCPV across wells: sum per-well net pay, compute the
   field net-to-gross, and aggregate per-zone HCPV/BVW into field totals. Each
   aggregate is a deterministic arithmetic rollup over per-well `computation` entries
   the engine already produced.
2. Cross-well zonation: align the per-well delineated zones into field-level zone
   groups (a cross-well zone-correlation panel), keyed by formation/zone identity.
3. Carry confidence tiers up: each field aggregate inherits the lowest confidence
   tier of any per-well block contributing to it (field tier = min over contributing
   wells).
4. Append a `field_aggregation` block to a field ledger recording each aggregate, the
   contributing well/zone `computation_id`s, and the aggregate confidence tier, so
   every field number resolves back to per-well ledger entries.

**Outputs**: field rollup struct (aggregate net pay/NTG/HCPV, per-well summary
table), cross-well zone-correlation groups, field ledger `field_aggregation` block.

**Exit condition**: every field aggregate resolves to the per-well ledger entries it
was computed from.

### Stage 12 — `field_write`

**Purpose**: generate the field-summary report (per-well summary table, field
totals, cross-well zone-correlation panel, field net-pay/quality map) from the field
aggregation block.

**Actor**: field-summary writer (Qwen3:30b-a3b via Ollama). The writer receives the
field aggregation block and per-well confidence tiers (read-only); it has no access
to raw curves or the validator harness, and follows the same tier-bound tone policy
as Stage 8. The field net-pay/quality map is rendered deterministically from the
per-well/field aggregates; the writer only redacts prose around it.

**Outputs**: field-summary report (Markdown), field net-pay/quality map and
cross-well zone-correlation panel PNGs, written to `outputs/`.

---

## Orchestration

### The LangGraph state machine

The orchestrator is implemented in `src/orchestrator/` as a LangGraph `StateGraph`.
Every node is a deterministic Python function or a bounded LLM agent call; every
edge condition is a deterministic Python predicate. No LLM selects the next node.

**LLM serving layer (v1 = Ollama).** All LLM-bounded nodes (`correct`, `write`,
`review`, `claim_verify`, `field_write`) reach the model through a thin swappable
serving interface; v1 uses **Ollama** behind that interface, so an Ollama→vLLM swap
is a config change, not a rewrite. **vLLM is reserved for a future Phase-8+
field-wide batch mode** on a larger GPU (24 GB+/multi-GPU), where continuous batching
across many wells pays off; it is out of scope for v1, which serves the per-well
prose sequentially on the 16 GB target.

```
State fields:
  las_path              str
  config_path           str
  curves                dict[str, np.ndarray]
  quality_map           np.ndarray
  vsh / phie / sw       np.ndarray
  ledger                dict              (built incrementally)
  objections            list[Objection]
  correctable_count     int
  iteration             int               (starts at 0)
  prev_correctable      int               (for circuit breaker; starts at -1)
  confidence_tiers      dict[str, str]
  convergence_status    str
  zones                 list[dict]        (cutoff-delimited net-pay zones; from zonate)
  draft_report          str
```

### Node map

| Node | Function / actor | LangGraph type |
|---|---|---|
| `load` | `src.orchestrator.stages.load` | deterministic |
| `qc_gate` | `src.orchestrator.stages.qc_gate` | deterministic |
| `compute` | `src.orchestrator.stages.compute` (calls petrophysics engine) | deterministic |
| `validate` | `src.orchestrator.stages.validate` (calls validator harness) | deterministic |
| `typify_objections` | `src.orchestrator.stages.typify_objections` | deterministic |
| `correct` | `src.agents.compute_agent` (Qwen3:30b-a3b via Ollama) | LLM-bounded |
| `gating` | `src.orchestrator.stages.gating` | deterministic |
| `zonate` | `src.orchestrator.stages.zonate` (calls net-pay engine) | deterministic |
| `write` | `src.agents.writer` (Qwen3:30b-a3b via Ollama) | LLM-bounded |
| `review` (Phase 6) | `src.agents.reviewer` (Llama3.1:8b or Qwen3:30b-a3b adversarial prompt — choice deferred to Phase 6) | LLM-bounded |
| `claim_verify` | `src.agents.claim_verifier` (Qwen3:30b-a3b via Ollama) | LLM-bounded |
| `emit` | `src.orchestrator.stages.emit` | deterministic |

### Loop edges

After `typify_objections`, the state router applies the following conditions in
order:

```python
if circuit_breaker_triggered(state):
    → gating
elif state["correctable_count"] == 0:
    → gating
else:
    → correct
```

After `correct`:
```python
→ compute        # always; revised params feed a new compute pass
```

After `compute`:
```python
→ validate       # always
```

After `validate`:
```python
→ typify_objections  # always
```

This forms the refinement loop: `typify → correct → compute → validate → typify`.

**Review-stage edges (active from Phase 6).** When the `review` stage is present, the
edges after `gating` are:

```python
# after gating
→ zonate         # always; delineate zones and compute net pay

# after zonate
→ write          # always

# after write
→ review         # Phase 6+; before Phase 6, → claim_verify directly

# after review
if review_correctable_count > 0 and not circuit_breaker_triggered(state):
    → typify_objections   # re-enter the refinement loop to address the objections
else:
    → claim_verify        # only irreducible reviewer objections remain (or breaker fired)
```

The reviewer's objections are merged into the objection list that `typify_objections`
classifies, so a correctable reviewer objection re-enters the same
`correct → compute → validate → typify` loop as a validator objection. The termination
predicate is unchanged: the loop exits to `claim_verify` only when
`correctable_count == 0` (no correctable validator *or* reviewer objections remain) or
the circuit breaker fires. The reviewer therefore cannot extend the loop indefinitely —
its correctable objections are subject to the same monotonic-decrease circuit breaker as
every other correctable objection (see Circuit breaker below).

### Termination predicate

The loop exits when **only irreducible objections remain** — `correctable_count == 0`.
The loop does NOT exit when the critic has no objections; it exits when the typed
objection set is empty of correctable items. This is the anti-Goodhart guard:
it is impossible for prose rewriting to satisfy the predicate, because the predicate
checks `correctable_count`, not LLM agreement.

---

## Idempotency / Retries

### Reproducibility guarantee

Given the same input LAS file and the same config file, two runs of the pipeline
must produce bitwise-identical JSON ledgers and functionally equivalent prose
(minor phrasing variation in LLM output is acceptable; no numerical difference is
acceptable).

This guarantee is achieved by pinning every source of non-determinism at run start:

| Source | Pinning mechanism |
|---|---|
| Python library versions | `pyproject.toml` pins + verified at `load` and logged in ledger |
| Config parameters | SHA-256 hash of the config JSON logged in ledger; the hash is also the de-duplication key for caching |
| Petrophysical functions | `function_version` (semver) logged per computation; functions are frozen, not generated at runtime |
| Validator harness | Versioned artifact; version logged per validator entry |
| LLM model | Model tag (`qwen3:30b-a3b`) pinned at invocation; logged in `run.model_tags` |
| Monte Carlo seeds | All seeds pinned and logged in `run.monte_carlo_seeds` (active from Phase 7; empty list before that) |
| Iteration count | Deterministic (same inputs → same objections → same loop count) |

### Config-hash-keyed caching

Every run logs its config hash (`run.config_hash_sha256`). If a future invocation
presents the same LAS file (identified by SHA-256 of the file contents) and the
same config hash, the system may serve the cached ledger and report from `outputs/`
without re-running the quantitative path. Cache invalidation occurs when either
hash changes. This is an optimisation, not a correctness concern — the quantitative
path is deterministic regardless.

Implementation note: the cache lookup is performed in the `load` stage. If a cached
ledger exists and both hashes match, the `load` stage transitions directly to `emit`
(skipping all intermediate stages). The cache is consulted, never written to, inside
the loop — only `emit` writes to `outputs/`.

### Retry policy

The pipeline does not retry automatically on transient errors. The failure modes are:

| Failure mode | Action |
|---|---|
| LAS file missing or unreadable | Abort at `load` with a diagnostic; no retry |
| Required curve missing | Abort at `load`; no retry |
| Ollama model not available (connection refused or model not pulled) | Abort at the first LLM node with a diagnostic naming the model; no retry |
| Physical-bounds violation (validator `FAIL`) | Routed through `correct → compute` loop; handled by the circuit breaker if persistent |
| Circuit breaker fires | Emit with `DID_NOT_CONVERGE`; no retry — the operator reviews and may re-run with a revised config |
| Ledger completeness gate fails | Abort at `emit` with a diagnostic; no partial output files are written |

There is no background retry queue. The pipeline is invoked on-demand; if it fails,
the developer re-runs after inspecting the diagnostic.

### Idempotent output naming

Output files follow the pattern `<UWI>_<YYYY-MM-DD>_<artifact>.<ext>`. A re-run
on the same well on the same day overwrites the prior outputs. This is intentional:
two runs on the same day with the same config must produce identical ledgers (given
the reproducibility guarantee above), so overwriting is safe. A run with a changed
config produces a different config hash; the operator is responsible for archiving
prior outputs if they need both versions.

---

## Circuit breaker

The non-convergence circuit breaker guards against infinite loops caused by
oscillating objections (a parameter correction resolves one objection but introduces
another, cycling indefinitely).

**Predicate**: after each `typify_objections` pass, the orchestrator compares
`correctable_count` with `prev_correctable_count` (the count from the previous pass).

```python
if correctable_count >= prev_correctable_count and iteration > 0:
    # count did not decrease — potential oscillation
    consecutive_non_decrease += 1
else:
    consecutive_non_decrease = 0

if consecutive_non_decrease >= N:          # N = 3 (configurable in config library)
    circuit_breaker_triggered = True
```

`N = 3` means: if the correctable objection count fails to decrease for three
consecutive loop iterations, the circuit breaker fires. `N` is read from the config
library at run start and logged in the ledger; it is not determined by an agent.

When the circuit breaker fires:
1. `convergence_status` is set to `DID_NOT_CONVERGE`.
2. The state transitions to `gating` with the unresolved objections intact.
3. The gating stage assigns the lowest possible confidence tier (`BRACKETED`) to all
   computation blocks that have unresolved correctable objections.
4. All unresolved objections are written to the ledger `validators` list with
   `result: WARN`.
5. The emit stage prepends the non-convergence warning block to the report.
6. All output files are written normally; the run is not aborted.

A `DID_NOT_CONVERGE` report is a valid run result. It is marked explicitly and
honestly; the operator decides whether to investigate and re-run.

---

## Open questions

- **`DID_NOT_CONVERGE` prose report policy**: the schema above emits a prose report
  with a warning block when the circuit breaker fires. An alternative is to emit only
  the ledger (no prose) in this state, forcing the operator to inspect the ledger
  before seeing conclusions. This is a product decision (related to Charter Open
  question (b) on hard abstention) deferred to Phase 4 acceptance testing.

- **Cache implementation scope for v1**: the config-hash-keyed cache described above
  requires a small lookup table mapping `(las_sha256, config_sha256)` to a prior
  output path. In v1 this could be a JSON file in `outputs/`; whether to implement it
  in Phase 8 or leave it as a future optimisation has not been decided.

- **`claim_verify` round-trip limit**: the single round-trip between verifier and
  writer (one correction pass) is specified here. If the corrected draft still
  contains flagged claims after one pass, the sentence is removed. Whether the
  round-trip limit should be configurable (0 = verifier only reads; 1 = one
  correction pass; N = N passes) is an open design question for Phase 5.
