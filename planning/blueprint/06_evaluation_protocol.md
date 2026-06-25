# Evaluation Protocol — petro-agent

This document specifies how the complete pipeline is judged to be working correctly.
It builds on the quantitative thresholds stated in the Charter, the VOLVE benchmark
role established in `02_problem_data.md`, the confidence-tier and tone machinery
defined in `03_source_sink_contracts.md` and `04_pipeline_architecture.md`, and
the engine golden-test suite specified in `05_engine_and_validation.md`. It adds
the evaluation-level detail needed to implement Phase 7 (calibration infrastructure)
and Phase 8 (regression run and pass/fail judgment).

---

## Metrics

### Quantitative accuracy metrics — VOLVE regression (Phase 8)

The four metrics below are the Phase 8 pass/fail gate. They compare the pipeline's
per-depth outputs against the Equinor-released accepted interpretation curves for the
VOLVE benchmark wells.

| Output | Metric | Threshold | Failure consequence |
|---|---|---|---|
| PHIE (effective porosity) | Mean Absolute Error, v/v | MAE < 0.03 (3 p.u.) | Pipeline regression failure |
| Vsh (shale volume) | Mean Absolute Error, v/v | MAE < 0.10 | Pipeline regression failure |
| Sw (water saturation) | Mean Absolute Error, v/v | MAE < 0.15 | Pipeline regression failure |
| Net pay | Relative absolute deviation from accepted net pay, per well | Within ±20% | Pipeline regression failure |

Failure on any single threshold — not the average across the four — is a regression
failure. All four must pass for Phase 8 to be declared complete.

**MAE computation**: per-depth, computed only on depth samples where both the pipeline
output and the reference interpretation are non-null. Excluded depths (quality tag
`EXCLUDED` in the pipeline's quality map) are excluded from the MAE denominator.
Samples masked in the reference interpretation (if any) are also excluded.

**Net pay deviation**: for each VOLVE benchmark well, `|pipeline_net_pay_m -
reference_net_pay_m| / reference_net_pay_m`. A well-level pass/fail is applied;
the threshold must be satisfied in every benchmark well individually, not only on
average.

**Cutoffs used for net pay**: the same cutoffs written in the config library
(`vsh_cutoff`, `phie_cutoff`, `sw_cutoff`) are used for both the pipeline run and,
where the reference interpretation documents them, for the accepted interpretation.
If the reference interpretation does not document cutoffs, the pipeline cutoffs are
applied to compute both estimates from the respective depth curves — ensuring
comparability.

**Metric computation code**: implemented in `src/evaluation/volve_metrics.py`
(Phase 8 target). The metric functions are deterministic numpy operations, not LLM
calls. Their correctness is covered by golden tests in `tests/test_volve_metrics.py`
before Phase 8 begins.

---

### Confidence calibration — procedural (Phases 5 onward)

The procedural calibration criterion is enforced within every run, on every dataset,
starting in Phase 5. It is not a VOLVE-specific metric; it is a pipeline-level
correctness condition.

#### Tone-by-confidence gating rules

The writer agent's language is bound to the confidence tier of each computation
block by policy-as-code. The tier is assigned by the deterministic gating stage
(`src/orchestrator/stages.gating`); the writer receives it as a typed field and
has no authority to override it.

The gating stage assigns the tier in two separate steps, exactly as specified by
`04_pipeline_architecture.md` Stage 7 (the source of truth for this machinery):
(1) the base tier is assigned from parameter provenance alone, per the table below;
(2) each irreducible objection affecting the block then downgrades the base tier by one
level (FIRM→QUALIFIED→BRACKETED), floored at `BRACKETED`. The objection count is a
separate downgrade step, not part of the provenance trigger condition.

| Tier (base) | Provenance condition that assigns it | Required writer language |
|---|---|---|
| `FIRM` | All high-leverage parameters (a, m, n, Rw) are `core` or `offset` provenance with narrow uncertainty | Declarative: "The interval shows…", "Net pay is N metres." No hedging required. |
| `QUALIFIED` | At least one high-leverage parameter is `offset` provenance with moderate uncertainty | Qualified: "The interpretation suggests…", "Net pay is approximately N metres." Uncertainty range must appear in the zone block. |
| `BRACKETED` | Any high-leverage parameter is `default` provenance with no local calibration | Explicitly bounded: "Given the absence of core calibration, Sw ranges from X to Y (P10–P90). The point estimate of N should not be used without offset calibration." The stated limitation must appear in the `Limitations` sub-section of the zone block. |

The base tier above is then downgraded one level per irreducible objection on the block
(floored at `BRACKETED`): a `FIRM` base with one model-mismatch or data-limited
objection becomes `QUALIFIED`; with two or more it becomes `BRACKETED`.

**Enforcement**: the claim verifier (`src/agents/claim_verifier`) checks these
rules sentence by sentence after the writer produces the draft. A `BRACKETED` block
that contains a declarative point-estimate sentence without a propagated range is
flagged and returned to the writer for one correction pass. If the sentence cannot
be corrected within one pass, it is removed and a `degradation` entry is written to
the ledger with `confidence_impact = exclusion`.

#### Claim-verifier pass criterion

The claim verifier must find zero residual flags for a run to emit the report under
normal completion. The four checks it applies:

1. Every sentence containing a numerical value must trace to a `computation` entry
   reachable by `(depth_range_m, output_curve)` in the ledger.
2. Every sentence in a `BRACKETED` block must not assert a point estimate without
   stating the propagated P10–P90 range.
3. Every sentence in a `QUALIFIED` block must use a qualifying hedge when asserting a
   value ("approximately", "suggests", "estimated at").
4. The `Limitations and confidence statement` section must explicitly name every
   parameter that carries `provenance = default` in any computation entry.

A run that exits `claim_verify` with zero flags satisfies the procedural calibration
criterion for that run. The ledger records the claim-verifier outcome as a validator
entry: `validator_name = "claim_verifier"`, `check_type = "claim_verification"`,
`result = PASS | FAIL`.

---

### Confidence calibration — statistical (Phase 7 infrastructure, Phase 8 measurement)

This criterion measures whether the system's stated confidence tiers correspond to
observed accuracy on held-out VOLVE benchmark wells. The infrastructure is built in
Phase 7; the measurement is performed in Phase 8 as part of the regression evaluation.

#### What is being calibrated

The pipeline assigns each computation block one of three tiers: `FIRM`, `QUALIFIED`,
`BRACKETED`. Calibration asks: across all blocks assigned `FIRM`, does the pipeline's
actual MAE fall within the narrow uncertainty range that `FIRM` implies? Across all
blocks assigned `BRACKETED`, does the actual MAE fall within the wide uncertainty
range that `BRACKETED` implies?

This is measured using a reliability diagram (calibration curve) and the Expected
Calibration Error (ECE).

#### Reliability diagram (calibration curve)

Because uncertainty is propagated by **Monte Carlo** (per-depth sampling — the
resolved method, not analytic ranges), the P10/P50/P90 fields are true distributional
percentiles. The reliability diagram is therefore **not limited to the three-tier
shape**: it may use finer equal-width bins across all stated half-ranges where the
VOLVE well count permits each bin to be populated reliably; otherwise it falls back to
the per-tier (FIRM/QUALIFIED/BRACKETED) binning below.

For each confidence tier, compute the mean stated uncertainty bound and the mean
observed absolute error across all benchmark wells in that tier:

```
For each tier T in {FIRM, QUALIFIED, BRACKETED}:
  blocks_T = all computation blocks with confidence_tier == T
  mean_stated_half_range_T = mean of (P90 - P10) / 2 over blocks_T
  mean_observed_MAE_T = mean of |predicted - reference| over depth samples in blocks_T
```

Plot `mean_observed_MAE_T` (y-axis) against `mean_stated_half_range_T` (x-axis) for
each tier. Perfect calibration would have all three points on the diagonal. Points
above the diagonal indicate overconfidence (the system claims narrower uncertainty
than its actual error); points below indicate underconfidence.

The diagram is saved as `outputs/evaluation/calibration_reliability_diagram.png`
(Phase 8) and referenced in the evaluation report.

#### Expected Calibration Error (ECE)

ECE is computed as the weighted mean absolute deviation between stated half-range and
observed MAE, weighted by the number of depth samples in each tier:

```
ECE = sum over T of (n_T / N_total) * |mean_observed_MAE_T - mean_stated_half_range_T|
```

where `n_T` is the number of non-excluded depth samples in tier T and `N_total` is
the sum across all tiers.

**ECE threshold**: the specific numeric ECE threshold (success criterion 4 in the
Charter) is deferred to Phase 7. The threshold will be set and logged at Phase 7 exit,
after the calibration infrastructure is implemented and a provisional measurement is taken
on a subset of VOLVE wells (not the full benchmark — contamination guard still
applies). The threshold is then logged as a manifest decision before Phase 8 begins.
The threshold must be logged and approved before any Phase 8 evaluation run.

The infrastructure for measuring ECE — the metric functions, the reliability diagram
generation, and the evaluation report format — is required by v1 and must exist
before the VOLVE blind-test run.

---

## Validation scheme

### VOLVE as pipeline-level blind test

VOLVE serves the same function as a held-out test set in supervised ML, raised to
the pipeline level: it is a blind test of the entire system, not of any single
component. The protocol is analogous to leave-one-well-out (LOWO) cross-validation
but applied to the pipeline as a whole rather than to a learned model.

**What "blind" means in this project**:
- The accepted VOLVE interpretation files (Petrel exports, ASCII curve exports
  with reference Vsh/PHIE/Sw) must not be examined during Phases 0–7.
- Raw VOLVE LAS curve files (without the interpretation overlay) may be examined in
  Phase 8 setup only for the purpose of building the mnemonic-alias mapping layer.
- The metric thresholds (MAE < 0.03 for PHIE, etc.) were set from domain knowledge
  of professional petrophysical practice, not from prior inspection of VOLVE results.
  This is documented here to record that no VOLVE result influenced threshold design.
- The VOLVE benchmark wells must not be used to tune cutoffs, Archie parameters,
  or gating rules at any point before the Phase 8 freeze.

**LOWO-style logic at the pipeline level**:

In classical LOWO, one well is withheld from training and the model predicts it.
Here, the pipeline has no training step. The analogous structure is:

```
Development set (Phases 0–7): Kansas / Schaben wells
  — all iterative design decisions made here
  — no constraint from VOLVE results

Benchmark set (Phase 8 only): VOLVE wells with accepted interpretation
  — single evaluation run; no design decisions may follow from results
  — findings generate a foundation gap report (planning-format.md §A)
    or a new development iteration; they do not flow back into the
    Phase 8 run itself
```

A "pipeline-level LOWO" has exactly one fold: the entire VOLVE benchmark is the
withheld well set. There is no internal cross-validation within VOLVE.

**Field-scale and the regression gate**: although v1 is a whole-field report (per-well
results plus a field rollup — aggregate net pay/NTG/HCPV, a cross-well zone-correlation
panel, and a field net-pay/quality map), the **VOLVE regression gate stays per-well**.
Calibration is per-well: the four pass/fail metrics (PHIE/Vsh/Sw MAE, net-pay deviation)
are computed and judged against each benchmark well's accepted interpretation
individually. The **field-aggregation metrics are descriptive** — they summarise the
per-well outputs for the report and are not part of the Phase 8 pass/fail gate.

**VOLVE well subset for evaluation**: the full set of VOLVE wells with a complete
accepted interpretation is used. Exact well count is confirmed in Phase 8 setup.
A minimum of three wells must carry complete reference Vsh/PHIE/Sw curves; if fewer
are available, Phase 8 is blocked pending a foundation gap report.

---

### Development validation on Kansas (Phases 0–7)

Because Kansas/Schaben wells carry no accepted interpretation (no labels), evaluation
on Kansas during development uses the following proxies:

| Check | What it validates | Phase introduced |
|---|---|---|
| Golden test suite passes | Engine functions compute correctly for known analytic inputs | Phase 0 |
| Physical-bounds validator passes | Outputs are in the physically possible range | Phase 3 |
| Cross-curve consistency validator passes | Computed curves are directionally consistent with each other | Phase 3 |
| Claim verifier finds zero flags | Writer language does not exceed the confidence tier | Phase 5 |
| Circuit breaker does not fire | The loop converges within N iterations | Phase 4 |
| No `DID_NOT_CONVERGE` on Kansas | Pipeline converges on the development dataset | Phase 4 |
| Multi-seed robustness check passes | Results are stable across a fixed set of seeds | Phase 7 |

None of these proxies constitute ground-truth evaluation; they are internal
consistency checks. Ground-truth evaluation occurs only on VOLVE in Phase 8.

---

### Cross-family evaluation (prose, selection, honesty)

Cross-family comparison is **not** a second parallel writer. The architecture keeps a
**single Qwen3:30b-a3b writer**; model diversity comes from the **Phase-6 adversarial
reviewer (Llama3.1:8b, the second model family)**, which critiques the single Qwen
draft. The cross-family comparison of **prose quality, method/parameter-selection
rationale, and claim honesty** is therefore performed by that reviewer at Phase 6 — not
by diffing two independent drafts. The diversity benefit (reduced correlated blind
spots) is a reviewer-decorrelation gain; the deterministic validators still carry the
reliability weight. There is no parallel-draft comparison in the evaluation protocol.

### Engine-reproducibility regression check

The deterministic engine is **byte-reproducible given a fixed input set**: the same LAS
file, the same config, **and the same recorded set of parameter selections** must
produce **byte-identical engine outputs**. This is the regression guarantee that backs
the cross-family work above.

Scope of the guarantee:

- The engine is deterministic **given a fixed selection set** — it is **not** invariant
  to *which model* performs the selection. The compute agent's `correct` loop (an LLM
  node) selects revised parameters from the config library to resolve correctable
  objections; that is the "selects" clause of the invariant, not computation.
- Two different model families (or the same model under best-effort, non-bit-exact
  seeding) may make **different** parameter selections in that loop, yielding different
  — but each fully deterministic-given-the-selection — numbers. That cross-model
  selection divergence is a **ledger-tracked numeric-difference source**, not a
  regression failure: every selection and degradation is recorded, so the difference is
  auditable.
- The regression check therefore compares engine outputs **holding the recorded
  selections fixed**: replay the same LAS + config + recorded selection set and assert
  byte-identical outputs. The ledger surfaces any cross-model selection divergence for
  audit separately, aligned with the best-effort (non-bit-exact) LLM reproducibility
  policy under Reproducibility below.

---

## Success thresholds

### Phase 8 — quantitative regression (hard pass/fail)

All four must be satisfied. Failure on any one is a pipeline regression failure.

| Metric | Hard threshold |
|---|---|
| PHIE MAE (v/v) | < 0.03 |
| Vsh MAE (v/v) | < 0.10 |
| Sw MAE (v/v) | < 0.15 |
| Net pay relative deviation (per well) | ≤ ±20% on every benchmark well |

### Phase 7 — calibration infrastructure (structural requirement)

Before Phase 8 begins, the following must be true:

- `src/evaluation/volve_metrics.py` implements `compute_mae`, `compute_net_pay_deviation`,
  `compute_ece`, and `plot_reliability_diagram` — all deterministic numpy functions.
- Their golden tests in `tests/test_volve_metrics.py` pass (`pytest -q` exits 0).
- The ECE threshold is set, logged as a manifest decision, and approved.
  Phase 8 is blocked until this decision exists.

### Phase 5 onward — procedural calibration (required on every run)

- The claim verifier finds zero residual flags in the emitted report.
- Every computation block's `confidence_tier` is assigned by the gating stage, not
  by the writer agent.
- The ledger's `validators` array contains a `claim_verifier` entry with
  `result = PASS` for every emitted report.

### Phase 7 — multi-seed robustness (required before Phase 8)

When Monte Carlo uncertainty propagation is active, the pipeline is run with at least
three independently sampled seed sets (see Reproducibility below). The robustness
check passes when:

- The P50 values (Vsh, PHIE, Sw) agree across seeds within 1% relative deviation.
- The P10–P90 range width agrees across seeds within 5% relative deviation.
- No single seed produces a confidence tier different from the consensus tier.

If the robustness check fails, the seed set is flagged in the ledger and the run
emits a degradation entry (`confidence_impact = uncertainty_widening`). The P50
value is retained; the P10–P90 range is widened to the envelope across all seeds.

### ECE threshold — deferred to Phase 7

The specific numeric ECE threshold is deferred. It will be set and logged at Phase 7
exit (after the calibration infrastructure is implemented and a provisional
measurement is taken) as described above. Until it is set, the ECE infrastructure must exist and the ECE
value must be measurable, but no pass/fail judgment is possible.

---

## Reproducibility (seeds, environment)

### Pinned library versions

At the start of every run, `src/orchestrator/stages.load` verifies that the installed
versions of the critical libraries match the versions declared in `pyproject.toml`.
Any mismatch aborts the run. The verified versions are logged in the ledger's `run`
object:

```json
"library_versions": {
  "lasio": "<version>",
  "numpy": "<version>",
  "langgraph": "<version>",
  "ollama_client": "<version>"
}
```

Version pinning is managed in `pyproject.toml`. The devcontainer / Docker image is
the canonical reproducibility envelope: a run inside the devcontainer with the same
LAS file and config file must produce the same ledger as a prior run under the same
image.

### Config hash

The SHA-256 hash of the parameter config JSON file is computed at the start of every
run (after the file is loaded, before any computation) and written to `run.config_hash_sha256`
in the ledger. Two runs are comparable only when their config hashes match. A changed
config file produces a different hash; the developer is responsible for archiving
prior ledgers if both versions are needed.

The config hash also serves as the cache key: if a future invocation presents the
same LAS file (identified by SHA-256 of the file contents) and the same config hash,
the pipeline may serve the cached ledger and report from `outputs/` without recomputing
(see `04_pipeline_architecture.md`).

### Pinned seeds

Stochastic steps in the pipeline are limited to:

1. **Monte Carlo uncertainty propagation** (Phase 7, when active): per-parameter
   perturbation samples drawn from the uncertainty distribution.
2. **LLM sampling** (writer, compute agent, claim verifier): temperature and sampling
   controlled by the model invocation parameters.

All seeds are pinned and logged in `run.monte_carlo_seeds`. The field is an ordered
list of integers; the i-th element is the seed for the i-th sampled parameter
distribution. Before Phase 7, the list is empty and the field is present but
unpopulated.

**LLM seeds**: Ollama's API exposes a `seed` parameter. The pipeline pins this seed
for all LLM calls and logs it in the `run` object as `llm_seed`. The same `llm_seed`
and model tag must produce identical token sequences from Ollama (within the same
model version); minor phrasing variation is acceptable but no numerical change is
acceptable in prose that references ledger values. If Ollama does not honour the seed
parameter deterministically on the target build, this is logged as a degradation with
`confidence_impact = uncertainty_widening` on the prose section, not on the
quantitative path.

### Multi-seed robustness run

The multi-seed robustness check (Phase 7) runs the pipeline three times on the same
input with three distinct seed sets:

```
seed_set_1 = [1001, 1002, 1003, ...]
seed_set_2 = [2001, 2002, 2003, ...]
seed_set_3 = [3001, 3002, 3003, ...]
```

The exact seed lists are hardcoded in `src/evaluation/robustness.py` and covered by
a golden test. They are not generated at runtime; they are fixed in the source file
and versioned. This ensures that "multi-seed robustness" means the same thing across
Phase 7, Phase 8, and any future re-evaluation.

The robustness check is not a separate pipeline invocation mode — it is a thin
wrapper in `src/evaluation/robustness.py` that calls the pipeline three times and
compares the resulting ledgers. It reports pass/fail per the thresholds in
"Success thresholds — Phase 7" above.

### Environment reproducibility envelope

| Layer | Mechanism |
|---|---|
| OS / system libraries | devcontainer image (target); WSL2 (development) |
| Python version | `pyproject.toml` `requires-python` field |
| Python packages | `pyproject.toml` pinned dependencies + lock file |
| Ollama model version | Full model tag pinned at invocation (`qwen3:30b-a3b`, `llama3.1:8b`); logged in `run.model_tags` |
| Petrophysical functions | Semantic version embedded in module (`__version__`) and logged per computation |
| Validator harness | Semantic version logged per validator entry |
| Config file | SHA-256 hash logged at run start |
| Input LAS file | SHA-256 hash of the file contents logged at run start |
| Monte Carlo seeds | Logged in `run.monte_carlo_seeds` |
| LLM seed | Logged in `run.llm_seed` |

A run is considered reproducible when a fresh invocation in the same environment
with the same LAS hash, config hash, and seed list produces a ledger with bitwise-
identical quantitative fields. Minor phrasing variation in LLM-generated prose is
tolerated; any numerical field difference in the ledger is a reproducibility failure.

---

## Open questions

- **ECE numeric threshold**: the specific ECE target cannot be set before Phase 7
  implements the calibration infrastructure and takes a provisional measurement on
  a non-benchmark subset. It will be set and logged at Phase 7 exit (after the
  calibration infrastructure is implemented and a provisional measurement is taken)
  as a manifest decision (Charter Open question (e)). Phase 8 is blocked until this
  decision is recorded.

- **VOLVE well subset size**: the exact number of VOLVE wells with complete accepted
  Vsh/PHIE/Sw reference curves has not been confirmed. Phase 8 setup must establish
  this count. If fewer than three wells carry complete reference curves, Phase 8 is
  blocked pending a foundation gap report.

- **Reliability diagram binning strategy**: RESOLVED. With Monte Carlo uncertainty
  propagation the stated half-ranges are true percentiles, so the diagram is no longer
  limited to three per-tier bins. Use finer equal-width bins across all tiers where the
  VOLVE well count populates each bin reliably; otherwise fall back to the three-tier
  (FIRM/QUALIFIED/BRACKETED) binning. The bin count is chosen at Phase 7 once the VOLVE
  well count is confirmed.

- **Ollama seed determinism**: Ollama's `seed` parameter is documented but its
  determinism guarantee is version-dependent. If the Ollama version in use does not
  produce byte-identical outputs for the same seed, the LLM prose output is
  non-deterministic. This does not affect the quantitative path (which is fully
  deterministic) but it does affect run-to-run report diff analysis. The actual
  behaviour must be verified during Phase 5 implementation.

- **Net pay cutoff comparability on VOLVE**: if the VOLVE accepted interpretation
  used different cutoff values than the ones in the pipeline's config, net pay
  comparisons are not apples-to-apples. The cutoff values used by the Equinor
  interpretation must be confirmed when the reference files are opened in Phase 8.
  If they differ materially, the net pay threshold evaluation methodology requires
  a foundation gap report before Phase 8 can be declared complete.
