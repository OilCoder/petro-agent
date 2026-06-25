# Problem & Data — petro-agent

## Task definition

The task is supervised petrophysical interpretation from wireline well logs.

Given a set of measured depth-indexed log curves for a single well — the hard-required
set GR, RHOB, NPHI, RT, plus the optional caliper curves CALI and DCAL (both optional;
used for bad-hole masking when present, see `03_source_sink_contracts.md`) — the system
must produce:

1. A per-depth estimate of shale volume (Vsh), effective porosity (PHIE), and water
   saturation (Sw), with associated uncertainty ranges.
2. A set of cutoff-delimited reservoir zones, net-pay summaries, and a confidence
   tier for every quantitative block.
3. A prose report and a JSON ledger in which every emitted number traces to its input
   curves, computation function, function version, parameters, and parameter provenance.

The equations are fixed and domain-selected:

| Output | Equation | Applicable condition |
|---|---|---|
| Vsh | Larionov (old rocks): Vsh = 0.33 · (2^(2 · IGR) − 1), where IGR = (GR − GRmin) / (GRmax − GRmin) | Paleozoic formations; hardcoded for Kansas/Schaben per Invariant 6 |
| PHIE | Density-neutron crossplot: PHIE = (φD + φN) / 2 with density-derived φD = (ρma − ρb) / (ρma − ρfl) | When both RHOB and NPHI are present and hole quality is acceptable |
| Sw | Archie: Sw^n = (a · Rw) / (Rt · φ^m) | Clean-sand / carbonate Archie; degradation recorded in ledger when lithology deviates |

Because the equations are analytically fixed (not trained), this is not a machine-learning
modeling problem — it is a computation-and-interpretation pipeline. The system's
quantitative reliability derives from the tested correctness of the deterministic engine
(golden-tested golden-test suite), from parameter provenance tracking (core-calibrated /
offset-derived / regional-default), and from uncertainty propagation through those
parameters, not from any learned model.

---

## Dataset(s) (source, size)

### Kansas / Schaben — development dataset

| Attribute | Value |
|---|---|
| Source | U.S. Geological Survey (USGS) open data — Kansas Geological Survey (KGS) well log repository, public domain |
| Raw-LAS access | KGS Magellan portal (`https://www.kgs.ku.edu/Magellan/Logs/`), searchable by Ness County / API / lease, or via the bulk `ks_las_files.zip`. Wells are joined to logs via the KGS KID identifier. |
| Formation | Paleozoic (mixed carbonate and clastic section, Schaben oil field, Ness County, Kansas) |
| Scope (v1) | **Field-scale**: the v1 dataset is the **full Schaben well set**, not a single well. The pipeline processes wells one-by-one and a deterministic field-rollup stage aggregates them (per-well results plus field net pay / NTG / HCPV, cross-well zone correlation, and a field net-pay/quality map). |
| Anchor wells | Type-log well **Schaben #4 (API 15-135-21452)** plus the **three cored wells** — used to anchor zonation and as candidate calibration controls (see core note below). |
| Number of wells | Approximately 7–15 wells available in the Schaben area; exact count not yet confirmed — see Open questions |
| Curve availability | GR, RHOB, NPHI, RT present in most wells; CALI / DCAL availability varies by well and vintage |
| Depth range (typical) | Roughly 1 600–2 000 m MD depending on well; exact depths well-specific |
| File format | LAS 2.0 |
| Acquisition friction | Zero — already in use; quality is known from prior work |
| Known characteristics | Old rocks → Larionov old-rocks formula required (not Tertiary). Carbonate intervals present alongside clastics — model-mismatch detection (Phase 3) is relevant here. |
| No core data | Kansas/Schaben wells available for this project carry no core measurements; all parameters (a, m, n, Rw, matrix density) come from regional defaults or offset calibration. This is the primary source of parameter uncertainty for the dev dataset. **This remains the governing assumption — all Kansas outputs are BRACKETED.** |
| Published core (PENDING — do not flip) | KGS has published Schaben core values (Rw = 0.04, m = n = 2, core m ≈ 1.97 intergranular to 2.5 vuggy). These are **published starting points, not confirmed inputs**: treating them as authoritative calibration would lift some Kansas outputs above BRACKETED and amend the confidence architecture. This is a **PENDING logged decision, gated on hands-on verification** that the core is downloadable and depth-registerable to our specific wells. Until verified, the "no core data → BRACKETED" assumption above governs; do **not** flip to a calibrated Kansas path. |

### VOLVE — regression / benchmark dataset

| Attribute | Value |
|---|---|
| Source | Equinor VOLVE open dataset (released 2018), publicly available under the Equinor VOLVE licence |
| Location | North Sea, Norway (Jurassic and Cretaceous section, Heimdal Formation and others) |
| Number of wells | 24 wells with log data; a subset carries accepted petrophysical interpretation files (Petrel projects, ASCII exports) |
| Curve availability | Complete suite including GR, RHOB, NPHI, RT, CALI; some wells carry core measurements |
| File format | LAS 2.0 and DLIS (only LAS 2.0 ingested in v1; DLIS is out of scope per 01_context_interfaces.md) |
| Role in this project | Regression / benchmark only; not used during development or parameter tuning. The accepted interpretation provides numerical ground-truth labels against which Phase 8 validates the full pipeline. |
| Curve name mapping | VOLVE uses Equinor-internal mnemonics (e.g., `RHOZ` instead of `RHOB`, `NPOR` instead of `NPHI`). A mnemonic-alias mapping layer is required at pipeline intake for Phase 8. |
| Core data | Selected VOLVE wells carry core porosity and core saturation measurements, making offset / core-calibrated provenance possible for those wells. |

---

## Splits

This project does not perform a train/validation/test split in the machine-learning
sense — no model is fitted to the data. The relevant split is between development use
and benchmark evaluation:

| Role | Dataset | When used | Purpose |
|---|---|---|---|
| Development | Kansas / Schaben | Phases 0–7 | Build, test, and tune the deterministic engine, QC gate, parameter library, validators, orchestrator, LLM agents, and confidence gating. All iterative design decisions are made against Kansas data. |
| Benchmark | VOLVE (subset with accepted interpretation) | Phase 8 only | Blind evaluation of the complete pipeline against an accepted petrophysical interpretation. The pipeline is not modified in response to VOLVE results; findings feed a foundation gap report or a new iteration of the harness. |

The VOLVE benchmark serves the same function as a test set in ML: it must not
influence any upstream design decision. Using VOLVE output to tune parameters or
thresholds before the Phase 8 freeze would invalidate the benchmark.

Within Kansas: during Phases 0–7, all Kansas wells are used freely for development.
No hold-out within Kansas is planned for v1 — the dataset has no training component
that would overfit. The risk is methodological drift toward Kansas-specific geology,
not data leakage in the statistical sense (see Leakage risks below).

---

## Labels

Because no model is trained, "labels" in this project mean accepted reference
interpretations used to measure pipeline correctness, not supervised training targets.

### Kansas / Schaben — no labels

No accepted petrophysical interpretation exists for the Kansas wells in this project's
scope. There is no external ground truth. Parameters (a, m, n, Rw, matrix density)
default to regional literature values, which the system records as `provenance = default`
in the ledger. Confidence for Kansas outputs is therefore `tier = bracketed` for every
parameter-dependent result until offset or core calibration is supplied.

The absence of Kansas labels is not a bug — it is the design condition that drives
the whole uncertainty-propagation and confidence-gating architecture. A system that
only works when ground truth is available is not a useful autonomous system.

### VOLVE — accepted interpretation as labels

The VOLVE benchmark labels come from Equinor-released accepted petrophysical
interpretations (Petrel project exports and associated ASCII files). These are the
outputs of a professional petrophysical workflow conducted by domain experts and are
treated as ground truth for regression evaluation.

Label format: per-depth Vsh, PHIE, Sw curves (exact schema to be confirmed when VOLVE
files are examined in Phase 8), plus net-pay summaries per zone per well.

Validation thresholds against these labels (from the Charter):

| Output | Threshold |
|---|---|
| PHIE | MAE < 0.03 (3 p.u.) |
| Vsh | MAE < 0.10 |
| Sw | MAE < 0.15 |
| Net pay | Within ±20% of accepted net pay, per benchmark well |

Failure on any single threshold is a pipeline regression failure, not a soft warning.

---

## Leakage risks

### 1. Kansas geology baked into default parameter choices

The primary leakage risk is methodological, not statistical: if all iterative design
decisions are made against Kansas Paleozoic data, the pipeline may accumulate implicit
Kansas-specific tuning. The Larionov old-rocks formula is correct for Kansas but
incorrect for Tertiary formations; Archie parameters for Kansas Paleozoic carbonates
differ from North Sea Jurassic sandstones. When the pipeline runs on VOLVE (a North Sea
dataset with a younger stratigraphy and different mineralogy), accumulated Kansas-specific
choices may reduce generality.

Mitigation: the parameter library (Phase 2) separates regional defaults by formation
type and keeps them in versioned, human-authored config files. The system selects
parameters by provenance and formation tag declared in the LAS header — it does not
hardcode Kansas values. The Larionov variant selection is controlled by the formation
tag, not by a hardcoded constant. This prevents Kansas-specific defaults from silently
propagating to VOLVE runs.

### 2. VOLVE benchmark contamination

Any use of VOLVE data before the Phase 8 freeze — including manual inspection of the
accepted interpretation to inform cutoff thresholds, Archie parameters, or gating rules
— contaminates the benchmark. The accepted interpretation files must not be opened or
examined during Phases 0–7. The VOLVE curve files (raw logs without interpretation)
may be examined to build the mnemonic-alias mapping layer.

Mitigation: VOLVE accepted interpretation files are accessed for the first time in
Phase 8 only. This constraint must be honored by both the developer and the automated
loop. Examination of raw VOLVE log curves (without the interpretation overlay) for
mnemonic mapping in Phase 8 setup is permitted.

### 3. Threshold selection from knowledge of VOLVE

If the Charter success thresholds (MAE < 0.03 for PHIE, etc.) were chosen because the
developer knows the VOLVE data distribution, the evaluation is partially contaminated.
The thresholds in the Charter were set based on domain knowledge of what constitutes
a professionally defensible petrophysical result, not by examining VOLVE output. This
is acceptable but must be documented.

### 4. Curve name alias mapping from VOLVE interpretation

When building the mnemonic-alias mapping layer for VOLVE (Phase 8), the developer
may see the curve list from the accepted interpretation files, which reveals which
curves were used and implicitly which were trusted. This is a minor leakage risk.
Mitigation: build the alias map from the raw VOLVE LAS headers only, not from the
interpretation project files.

### 5. No statistical leakage risk within Kansas

Because no model is fitted to Kansas data and no cross-validation is performed,
there is no train/test leakage risk within the Kansas development set. The deterministic
engine does not learn from Kansas data; it executes fixed equations with supplied
parameters. Any "overfitting to Kansas" is geological, not statistical (see risk 1).

---

## Open questions

- **Exact Kansas well count and curve availability**: the exact number of Schaben wells
  with the hard-required curve set (GR, RHOB, NPHI, RT) has not been verified. Some
  wells may be missing RHOB or NPHI, restricting PHIE calculation to density-only or
  neutron-only fallback. Caliper (CALI/DCAL) availability also varies by well; its
  absence degrades bad-hole masking rather than rejecting the well (see
  `03_source_sink_contracts.md`). The count and curve inventory should be confirmed
  before Phase 0 begins.

- **VOLVE accepted interpretation format**: the exact format, schema, and depth
  registration of the Equinor-released accepted interpretation (Petrel exports vs.
  ASCII curve exports vs. PDF reports) determines how Phase 8 labels are ingested and
  compared. This must be confirmed when Phase 8 setup begins.

- **VOLVE well subset for regression**: not all 24 VOLVE wells carry a complete accepted
  interpretation. The subset of wells usable as benchmark labels has not been identified.
  Phase 8 planning requires knowing which wells, how many, and whether they cover a
  representative range of conditions.

- **Larionov formula applicability on VOLVE**: VOLVE is a North Sea Jurassic–Cretaceous
  dataset. The old-rocks Larionov formula is not necessarily the most appropriate variant
  for those formations (Tertiary formula may be more accurate for some intervals). The
  Larionov variant to use on VOLVE, and whether the system correctly selects it via the
  formation tag, must be confirmed before Phase 8. Selecting the wrong Larionov variant
  on VOLVE would introduce a systematic Vsh bias that could cause a regression failure.

- **Regional default parameters for North Sea / VOLVE**: the parameter library (Phase 2)
  must include a **separate North Sea / Jurassic set of defaults** (Rw, a, m, n, matrix
  density) distinct from the Kansas Paleozoic defaults, or the VOLVE run will use
  geologically inappropriate defaults. This is a **Phase 2 action** (not an open question)
  even though VOLVE is a Phase 8 concern.

- **Schaben default-parameter rows for the citations table**: the Schaben Paleozoic
  default parameters (Archie a, m, n, Rw, matrix density, Larionov old-rocks branch) supply
  the default-parameter rows for the Phase-2 curated citations table (each parameter → one
  source). These rows must be authored in Phase 2 alongside the North Sea / Jurassic set.
