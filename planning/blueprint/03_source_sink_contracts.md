# Source & Sink Contracts — petro-agent

This document defines the upstream and downstream contracts for every data boundary
the pipeline crosses: the LAS curve schema that the system consumes, the report and
ledger schemas it emits, the SLAs each boundary must satisfy, and the volume and
cadence model. It builds on the external-input list in `01_context_interfaces.md`
and the petrophysical equations fixed in `02_problem_data.md`, adding the
precision needed to write validators (Phase 3), the ledger (Phase 8), and the
writer agent (Phase 5).

---

## Upstream schemas (input)

### LAS file — wire contract

The pipeline accepts LAS 2.0 files only (CWLS standard). All other formats
(LAS 3.0, DLIS, WITSML) are rejected at the intake gate with an error.

#### Required header fields

| LAS field | Section | Type | Consumed as |
|---|---|---|---|
| `STRT` | `~Well` | float | Depth top of the log (same unit as depth array) |
| `STOP` | `~Well` | float | Depth base of the log |
| `STEP` | `~Well` | float | Depth increment; must be non-zero and consistent |
| `NULL` | `~Well` | float | Null sentinel; default −9999.25 if absent |
| `WELL` | `~Well` | string | Well name label for report headers |
| `UWI` or `API` | `~Well` | string | Well unique identifier; used to key ledger files |
| `COMP` | `~Well` | string | Operator / company name for report metadata |
| `PROV` | `~Well` | string | Formation / region tag; drives Larionov variant and regional parameter selection |

`PROV` is the formation tag. Recognized values at v1: `paleozoic` (→ Larionov old
rocks), `tertiary` (→ Larionov Tertiary), `unknown` (→ system falls back to
old-rocks with a degradation entry in the ledger). All other values are treated as
`unknown`. The recognized list is a versioned artifact in `src/params/`; it is not
determined by an agent at runtime.

#### Required curves

| Mnemonic | Physical quantity | Expected unit | Numeric range (valid) | Null handling |
|---|---|---|---|---|
| `GR` | Gamma ray | API units | 0 – 300 API | lasio sentinel → masked before compute |
| `RHOB` | Bulk density | g/cc | 1.0 – 3.0 g/cc | masked; triggers bad-hole flag if > 50% of interval |
| `NPHI` | Neutron porosity | v/v fraction | 0.0 – 1.0 v/v | masked; see unit-variant note below |
| `RT` | True resistivity | Ω·m | 0.01 – 50 000 Ω·m (provisional upper bound — to confirm) | masked; passed in linear Ω·m to the engine — the log₁₀ transform is applied only in the validator/cross-plot layer, never on the quantitative path |

The four curves above (`GR`, `RHOB`, `NPHI`, `RT`) are the hard-required set: each is a
direct input to a quantitative computation. If any of them is absent the intake gate
rejects the file with an explicit error message naming the missing curve. There is no
silent fallback for a missing required curve.

**No curve fabrication.** The system never synthesises, imputes, or interpolates a
missing curve. A well lacking the hard-required set is **rejected**; a well missing a
porosity input that supports graceful degradation (density-only / neutron-only PHIE) is
**degraded** with the degradation recorded in the ledger. Missing data is never filled
with a model-derived or guessed curve — it is rejected or degraded, and logged.

#### Optional curves

| Mnemonic | Physical quantity | Expected unit | Role |
|---|---|---|---|
| `CALI` | Caliper | inches | Bad-hole indicator (used with a bit-size constant from the config library); no computation on CALI itself. If absent, bad-hole masking is degraded — see note below |
| `DCAL` | Differential caliper (CALI − bit size) | inches | Preferred bad-hole indicator; if absent the gate uses CALI vs. a bit-size constant from the config library |
| `DT` | Compressional slowness | µs/ft | Reserved for Phase 3 M-N cross-plot; not used in v1 quantitative path |
| `PEF` | Photoelectric factor | barns/electron | Reserved for Phase 3 lithology cross-plot; not used in v1 quantitative path |

**Caliper availability and degraded bad-hole masking.** `CALI` and `DCAL` are both
optional because their availability varies by well and vintage in the Kansas/Schaben
development set (some older wells carry neither). Bad-hole masking degrades gracefully
rather than rejecting the file:

- `DCAL` present → preferred indicator (`|DCAL| > 2 in` flags bad hole).
- `DCAL` absent, `CALI` present → fallback indicator (`CALI > bit_size_config + 2 in`);
  a degradation entry records that the fallback was used.
- Both absent → bad-hole masking cannot run; RHOB/NPHI are not bad-hole-masked, and a
  degradation entry (`confidence_impact = tier_downgrade`) records that hole-quality
  masking was unavailable for this well. The run proceeds; it is not rejected.

This is a deliberate honesty-over-rejection choice: a missing caliper degrades the
confidence of the affected computations (per Charter Invariant 7) rather than auto-
rejecting wells the system is built to interpret.

#### Unit-variant handling

NPHI is sometimes delivered in percent (0–100) rather than v/v fraction (0.0–1.0),
and RHOB occasionally appears in kg/m³ (1000–3000) rather than g/cc. The intake
validator detects these variants by range:

- If `NPHI_max > 2.0`, the validator converts (`NPHI / 100`) and logs the conversion
  as a named edit in the ledger with the original range observed.
- If `RHOB_max > 10.0`, the validator converts (`RHOB / 1000`) and logs the
  conversion as a named edit in the ledger.

If the detected range falls in an ambiguous zone (e.g., NPHI between 1.0 and 2.0)
the intake gate rejects the file and emits a diagnostic requiring the operator to
confirm units manually. Auto-conversion is only applied when the range is
unambiguous.

#### Mnemonic alias table

Because development uses Kansas/Schaben mnemonics and the Phase 8 regression uses
VOLVE (Equinor-internal mnemonics), the intake layer applies a mnemonic alias
mapping before any computation. The alias table lives in `src/params/mnemonic_aliases.json`
and is versioned. Aliases are applied in order; first match wins.

| Canonical name | Accepted aliases (case-insensitive) |
|---|---|
| `GR` | `GR`, `GRD`, `GRGC`, `GR_EDTC` |
| `RHOB` | `RHOB`, `RHOZ`, `DEN`, `RHOG` |
| `NPHI` | `NPHI`, `NPOR`, `TNPH`, `CN` |
| `RT` | `RT`, `ILD`, `RDEEP`, `AT90`, `RD` |
| `CALI` | `CALI`, `CAL`, `C1` |
| `DCAL` | `DCAL`, `CALX`, `CALY`, `HDCAL` |

Mnemonics not in the alias table and not matching the canonical names are ignored
unless the operator supplies an explicit override in the config file.

#### Depth index

- The depth array is 1-D float64 (MD, measured depth).
- Unit is declared in the `~Well` section (`STRT.M` or `STRT.FT`).
- The pipeline normalises to metres internally; conversion factor (0.3048 for feet)
  is logged in the ledger.
- Monotonically increasing depth is required; violations are rejected at intake.
- The minimum accepted depth sample count is 10; shorter logs are rejected.

#### Null sentinel

The sentinel value is read from the LAS `NULL` field (default −9999.25 if the field
is absent). Any sample equal to the sentinel (within floating-point tolerance of
1e-3) is masked as null before any computation. The sentinel value is logged in the
ledger per run.

---

## Output schemas

### Output 1 — Prose report (Markdown)

**File**: `outputs/<UWI>_<YYYY-MM-DD>_report.md`

The report is a single Markdown file. An external renderer (not bundled with the
pipeline) converts it to HTML or PDF if needed.

#### Top-level structure

```
# Petrophysical Report — <WELL>
## Run metadata
## Well overview
## Data quality summary
## Zones
### Zone <N> — <name>
## Net pay summary
## Conclusions
## Limitations and confidence statement
## Appendix: parameter provenance
```

#### Zone block schema

Each `### Zone <N>` section contains exactly the following sub-sections in order:

| Sub-section | Content |
|---|---|
| **Interval** | Top MD – Base MD (metres), formation name if available |
| **Data quality** | Quality tier for this interval: `GOOD` / `DEGRADED` / `EXCLUDED` with a one-sentence reason |
| **Vsh** | P50 value (v/v), P10–P90 range (v/v), method (Larionov old-rocks), GR min/max used |
| **PHIE** | P50 value (v/v), P10–P90 range (v/v), method (density-neutron), matrix density used |
| **Sw** | P50 value (v/v), P10–P90 range (v/v), method (Archie), a/m/n/Rw values and provenance |
| **Cutoffs applied** | Vsh cutoff, PHIE cutoff, Sw cutoff — values and source (config library version) |
| **Net hierarchy** | Three-tier net thickness (m): `net_sand_m` (Vsh cutoff only), `net_reservoir_m` (Vsh + PHIE cutoffs), `net_pay_m` (Vsh + PHIE + Sw cutoffs) — each a deterministic cutoff/aggregation over the engine's `vsh`/`phie`/`sw` curves |
| **Net pay** | Gross thickness (m), net pay (m), net-to-gross ratio (dimensionless) |
| **Hydrocarbon volume** | Per-zone `hcpv` (hydrocarbon pore volume, PHIE·(1−Sw) aggregated over net pay) and `bvw` (bulk volume water, PHIE·Sw) — deterministic aggregations over the engine outputs, surfaced in the by-zone summary |
| **Confidence tier** | One of three tiers (see tone policy below) |
| **Limitations** | One or more bullet points stating what the data or parameters cannot support |

The zone block must not contain tables other than the ones implied by the schema
above. Prose is used for narrative; structured facts go in the sub-sections.

#### Confidence tier and tone policy

The confidence tier is computed from parameter provenance (Phase 2) and propagated
uncertainty (Phase 7). It is not chosen by the writer agent; it is assigned by the
gating stage and passed to the writer as a typed field.

The tier is assigned in two separate steps, exactly as specified by the gating stage
(`04_pipeline_architecture.md` Stage 7, the source of truth for this machinery):

1. **Base tier from parameter provenance alone** — the table below assigns the base
   tier from the provenance of the high-leverage parameters (a, m, n, Rw); irreducible
   objections play no part in this step.
2. **Downgrade from irreducible objections** — each irreducible objection that affects
   the block (model mismatch, data-limited) downgrades the base tier by one level
   (FIRM→QUALIFIED→BRACKETED), floored at `BRACKETED`. This is a separate step applied
   after the base tier is set; the objection count is never folded into the trigger
   condition below.

| Tier (base) | Provenance trigger condition | Permitted writer language |
|---|---|---|
| `FIRM` | All high-leverage parameters (a, m, n, Rw) are core-calibrated or offset-derived with narrow uncertainty | Declarative statements: "The interval shows…", "Net pay is N metres." |
| `QUALIFIED` | At least one high-leverage parameter is offset-derived with moderate uncertainty | Qualified statements: "The interpretation suggests…", "Net pay is approximately N metres." Uncertainty range must be stated. |
| `BRACKETED` | Any high-leverage parameter is a regional/global default with no local calibration | Explicitly bounded statements: "Given the absence of core calibration, Sw ranges from X to Y (P10–P90). The point estimate of N should not be used without offset calibration." The limitation must be stated in the Limitations sub-section. |

The claim verifier (Phase 5) checks, sentence by sentence, that no emitted sentence
asserts certainty above the tier. A `BRACKETED` block must not contain declarative
sentences about point estimates.

#### Report-level sections

**Run metadata** contains: run timestamp (ISO 8601 UTC), git commit SHA of `src/`,
pipeline version, ledger file path, config file hash (SHA-256), pinned library
versions (lasio, numpy, langgraph).

**Conclusions** is a 3–7 sentence prose summary written by the writer agent, bound
to the lowest confidence tier of any zone that contributes to net pay.

**Limitations and confidence statement** is generated by the claim verifier and
states explicitly any parameter that is regional-default, any interval excluded
from net pay due to data quality, and that uncertainty propagation is Monte Carlo
(P10/P50/P90 are true percentiles).

---

### Output 2 — JSON ledger

**File**: `outputs/<UWI>_<YYYY-MM-DD>_ledger.json`

The ledger is the primary traceability artifact. Every number in the prose report
must resolve to a ledger entry in O(1) lookup via `(depth_range_m, output_curve)` key.
Ledger completeness is a gating condition: the pipeline does not emit the report
until the ledger covers all quantitative claims.

#### Top-level structure

```json
{
  "run": { ... },
  "well": { ... },
  "edits": [ ... ],
  "computations": [ ... ],
  "validators": [ ... ],
  "degradations": [ ... ],
  "citations": [ ... ]
}
```

#### `run` object

```json
{
  "timestamp_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "git_commit_sha": "<40-char hex>",
  "pipeline_version": "<semver>",
  "config_hash_sha256": "<64-char hex>",
  "library_versions": {
    "lasio": "<version>",
    "numpy": "<version>",
    "langgraph": "<version>",
    "ollama_client": "<version>"
  },
  "model_tags": {
    "compute_agent": "qwen3:30b-a3b",
    "writer": "qwen3:30b-a3b",
    "claim_verifier": "qwen3:30b-a3b",
    "reviewer": "<resolved at Phase 6 — Charter Open question (a); null until then>"
  },
  "llm_seed": <int>,
  "uncertainty_method": "monte_carlo",
  "monte_carlo_seeds": [<int>, ...],
  "depth_unit_source": "M | FT",
  "depth_unit_internal": "M"
}
```

`model_tags` carries one slot per LLM role actually invoked: `compute_agent`, `writer`,
and `claim_verifier` (all served by Qwen3:30b-a3b in v1, logged with their pinned model
tag), and `reviewer` for the Phase 6 adversarial reviewer. The `reviewer` slot is `null`
until Charter Open question (a) is resolved at Phase 6 entry; the resolved value is
either `llama3.1:8b` or `qwen3:30b-a3b` (adversarial prompt). `llm_seed` is the Ollama
`seed` parameter pinned for all LLM calls (see `06_evaluation_protocol.md`).
`uncertainty_method` is fixed to `monte_carlo` for v1: per-depth Monte Carlo sampling
produces true distributional outputs, so `result_p10`/`result_p50`/`result_p90` are
genuine percentiles. `monte_carlo_seeds` records the seed(s) pinned for the sampling.

#### `well` object

```json
{
  "well_name": "<string>",
  "uwi": "<string>",
  "operator": "<string>",
  "formation_tag": "<string>",
  "las_null_sentinel": -9999.25,
  "depth_top_m": <float>,
  "depth_base_m": <float>,
  "depth_step_m": <float>,
  "sample_count": <int>
}
```

#### `edits` array — one entry per intake transformation

Each element records a named edit applied at intake (unit conversion, null masking,
spike removal):

```json
{
  "edit_id": "<string — slug>",
  "type": "unit_conversion | null_mask | spike_removal | section_reorder",
  "curve": "<mnemonic>",
  "depth_range_m": [<top>, <base>],
  "description": "<one sentence>",
  "original_range": [<min>, <max>],
  "converted_range": [<min>, <max>]
}
```

`depth_range_m` for null masks is the union of all masked intervals; for
single-point spike removals it is `[depth, depth]`.

#### `computations` array — one entry per quantitative result block

```json
{
  "computation_id": "<string — slug, e.g. 'vsh_zone_2'>",
  "depth_range_m": [<top>, <base>],
  "output_curve": "vsh | phie | sw",
  "function": "<function name, e.g. 'calc_vsh'>",
  "function_version": "<semver>",
  "function_module": "<dotted module path, e.g. 'src.petrophysics.vsh'>",
  "input_curves": ["GR", "..."],
  "parameters": {
    "<param_name>": <value>,
    "...": "..."
  },
  "parameter_provenance": {
    "<param_name>": "core | offset | default",
    "...": "..."
  },
  "parameter_source": {
    "<param_name>": "<config_key or literal description>",
    "...": "..."
  },
  "result_p10": <float>,
  "result_p50": <float>,
  "result_p90": <float>,
  "result_unit": "v/v | ohm_m | ...",
  "confidence_tier": "FIRM | QUALIFIED | BRACKETED",
  "validator_ids": ["<validator_id>", "..."]
}
```

`result_p10`, `result_p50`, and `result_p90` are true percentiles of the per-depth
Monte Carlo distribution (`uncertainty_method = monte_carlo`). They are always
populated; there is no analytic-range fallback in v1.

#### `validators` array — one entry per validator execution

```json
{
  "validator_id": "<string — slug>",
  "validator_name": "<human-readable name>",
  "validator_version": "<semver>",
  "depth_range_m": [<top>, <base>],
  "check_type": "physical_bounds | cross_curve | model_mismatch | data_quality | claim_verification",
  "input_curves": ["..."],
  "result": "PASS | FAIL | WARN | NA",
  "objection_type": "mechanical | support | irreducible | null",
  "message": "<one sentence>"
}
```

`objection_type` is `null` when `result` is `PASS` or `NA`.

#### `degradations` array — one entry per honesty event

```json
{
  "degradation_id": "<string — slug>",
  "phase": "<pipeline stage name>",
  "description": "<one sentence — what degraded and why>",
  "fallback_applied": "<what the system did instead>",
  "affects_computation_ids": ["<computation_id>", "..."],
  "confidence_impact": "tier_downgrade | uncertainty_widening | exclusion"
}
```

Degradations record every case where the system fell back from the preferred method:
missing curve causing PHIE fallback to density-only, unknown formation tag causing
Larionov variant fallback, parameter with no local calibration forced to regional
default, and similar events. A run with zero degradation entries is a run that had
all required data and calibration.

#### `citations` array — curated citations table, joined to the ledger

A static, version-pinned citations table (not RAG, not paper curation) maps every
parameter selection to exactly one source. Each parameter the engine consumes
(`a`, `m`, `n`, `Rw`, matrix density, Vsh/Larionov method) resolves to a frozen
citation; an unknown parameter is a hard fail, never a guessed source. The table is
covered by golden tests (every parameter resolves to exactly one source).

```json
{
  "parameter": "<param_name — e.g. 'm', 'Rw', 'matrix_density_limestone'>",
  "value": <value or default>,
  "valid_range": [<min>, <max>],
  "source": "<author, year — e.g. 'Archie 1942'>",
  "locator": "<page / DOI / report id>",
  "applicability": "<formation age / lithology scope — e.g. 'Paleozoic carbonate'>"
}
```

**Ledger join.** Each `computations[].parameters` selection emits the matching
`citations` entry by `parameter` key, joined under the run's `config_hash_sha256` and
the pinned config version. The citation is frozen at selection time so every parameter
in the prose report resolves to a value *and* its provenance in O(1) lookup. The
citations table is part of the canonical config artifact (version-pinned alongside
`regional_defaults` / `well_overrides`).

---

### Output 3 — Figure images (PNG)

**Files**: `outputs/<UWI>_<YYYY-MM-DD>_triplecombo.png`,
`outputs/<UWI>_<YYYY-MM-DD>_crossplot_nd.png`,
`outputs/<UWI>_<YYYY-MM-DD>_pickett.png`

| Attribute | Value |
|---|---|
| Format | PNG, 300 dpi, white background |
| Size | 1200 × 900 pixels (triple-combo: 1200 × 1600, portrait) |
| Triple-combo interpretation plot | Composite depth track: GR + Vsh track, RHOB/NPHI overlay track, RT track, and a computed-curve track (PHIE, Sw) with a **net-pay flag** column; zone boundaries as horizontal lines. The primary interpretation figure referenced in the report body |
| Neutron-density cross-plot | X-axis: NPHI (v/v, increasing right), Y-axis: RHOB (g/cc, increasing down); lithology lines for clean sandstone, limestone, dolomite at the matrix values used in this run; data points coloured by depth, zones delineated by boundary lines |
| Pickett plot | log₁₀(RT) vs log₁₀(PHIE) with Archie Sw lines (constant-Sw isolines for the run's a/m/n/Rw); a direct Sw/Rw/m QC plot; data points coloured by depth |
| Zone overlays | Each net-pay zone boundary plotted as a horizontal dashed line on the triple-combo and neutron-density plots |
| Generated by | `matplotlib` in `src/validators/`; not on the critical path for the quantitative result |
| Referenced in report | The triple-combo in the report body; cross-plot and Pickett plot by relative file path in the Appendix section |

The cross-plot and Pickett plot are informational evidence for the model-mismatch and
Sw/Rw validators (Phase 3). They are not emitted until Phase 3 is implemented; prior
phases produce no PNG output.

**M-N cross-plot — deferred (v1).** The M-N cross-plot (`crossplot_mn.png`) is **not
emitted in v1**: it requires `DT` (and `PEF`), which are reserved for a later phase. The
model-mismatch validator relies on the neutron-density cross-plot for v1; the M-N branch
is gated on `DT`/`PEF` presence and, when those curves are absent, the existing
`mn_skipped_no_dt` degradation path records the skip. No `crossplot_mn.png` is produced
by default in v1.

---

### Output 4 — Field rollup (whole-field scope)

v1 is a **whole-field report**: each well is still processed one-by-one by the
deterministic engine (one LAS → one ledger → one per-well report block), and a
deterministic **field-aggregation pass** runs after all per-well runs to roll the
per-well results into a field-level artifact set. The aggregation is non-LLM
arithmetic over the per-well ledgers; the invariant is unchanged.

**Files**: `outputs/<FIELD>_<YYYY-MM-DD>_field_report.md`,
`outputs/<FIELD>_<YYYY-MM-DD>_field_rollup.json`

#### Field rollup JSON schema

```json
{
  "field": "<field name, e.g. 'Schaben'>",
  "run_timestamp_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "wells_included": ["<uwi>", "..."],
  "wells_rejected": [{"uwi": "<uwi>", "reason": "<one sentence>"}, "..."],
  "aggregate": {
    "total_net_pay_m": <float>,
    "field_ntg": <float>,
    "total_hcpv": <float>,
    "net_pay_p10_m": <float>,
    "net_pay_p50_m": <float>,
    "net_pay_p90_m": <float>
  },
  "per_well_summary": [
    {
      "uwi": "<string>",
      "well_name": "<string>",
      "net_sand_m": <float>,
      "net_reservoir_m": <float>,
      "net_pay_m": <float>,
      "ntg": <float>,
      "avg_phie": <float>,
      "avg_sw": <float>,
      "hcpv": <float>,
      "confidence_tier": "FIRM | QUALIFIED | BRACKETED"
    }
  ]
}
```

The `aggregate` block sums/averages the per-well three-tier net hierarchy and HCPV;
`per_well_summary` is the field summary table rendered in the field report. Field-level
P10/P50/P90 net pay are aggregated from the per-well Monte Carlo distributions. The
field confidence statement is bound to the lowest per-well confidence tier that
contributes to field net pay.

#### Field figures (PNG)

**Files**: `outputs/<FIELD>_<YYYY-MM-DD>_netpay_map.png`,
`outputs/<FIELD>_<YYYY-MM-DD>_zone_correlation.png`

| Attribute | Value |
|---|---|
| Format | PNG, 300 dpi, white background |
| Field net-pay / quality map | Plan-view map of well locations coloured/sized by net pay (and confidence tier); a field-quality overview |
| Cross-well zone-correlation panel | Side-by-side per-well tracks aligned on formation tops/zone boundaries across the field; a stratigraphic correlation view |
| Generated by | `matplotlib` in `src/validators/`; field-aggregation pass, not on the per-well critical path |
| Referenced in report | By relative file path in the field report body |

---

## SLAs

### Intake gate

| Condition | System response |
|---|---|
| Missing required curve | Reject with error; list the missing mnemonic(s); no partial run |
| Required header field absent | Reject with error; name the field |
| Depth not monotonically increasing | Reject with error; report first violation depth |
| LAS format not 2.0 | Reject with error |
| Unambiguous unit variant detected | Auto-convert; log edit; continue |
| Ambiguous unit variant | Reject with error; require operator confirmation |
| `PROV` tag not recognized | Downgrade to `unknown`; log degradation; continue with Larionov old-rocks fallback |

### Ledger completeness gate

The report is not emitted unless:
1. Every `computation_id` referenced in the report has a corresponding entry in `computations`.
2. Every `validator_id` referenced in any `computation` entry has a corresponding entry in `validators`.
3. Every quantitative claim in the report prose has a corresponding `computation_id` that can be identified by `(depth_range_m, output_curve)`.

Failure of any of these conditions causes the pipeline to halt and emit a diagnostic
naming the unresolved reference. It does not emit a partial report.

### Convergence and circuit breaker

| Condition | System response |
|---|---|
| Correctable-objection count decreases monotonically | Loop continues |
| Correctable-objection count does not decrease after N iterations (N = 3 in v1, configurable) | Circuit breaker fires; report emitted with `convergence_status: DID_NOT_CONVERGE`; all unresolved objections logged in `validators` with `result: WARN` |
| All remaining objections classified as irreducible | Loop terminates; report emitted normally |

The convergence threshold N = 3 is set in the config library; it is not determined
by an agent at runtime.

### Error propagation policy

No exception or error is silently swallowed. Every caught exception is either:
- Re-raised (for fatal conditions that halt the run), or
- Logged as a degradation entry with `confidence_impact` set and execution continuing
  with the fallback applied.

A run that completes without raising an exception but with degradation entries is a
valid run. The presence of degradation entries narrows the confidence tier of affected
computations but does not invalidate the run.

---

## Volume / cadence

### Per-run scope

One pipeline invocation processes exactly one well (one LAS file). Batch processing
is supported by invoking the pipeline N times sequentially or in parallel; the
pipeline has no internal batch-loop. Each run produces one report, one ledger, and
(from Phase 3) one or more figure PNGs (triple-combo, neutron-density cross-plot,
Pickett plot).

### File naming convention

Output files follow the pattern `<UWI>_<YYYY-MM-DD>_<artifact>.<ext>`. If `UWI` is
absent from the LAS header, the `WELL` name is used after sanitising to ASCII
alphanumeric and underscores. The timestamp is the UTC date of the run.

### Expected volume (v1 development)

| Dataset | Wells | Approximate depth samples per well | Expected ledger size per well |
|---|---|---|---|
| Kansas / Schaben (dev) | 7–15 | 1 500 – 5 000 | 50–200 KB JSON |
| VOLVE (regression, Phase 8) | subset of 24 | up to 20 000 | up to 1 MB JSON |

These are order-of-magnitude estimates. No streaming or chunked I/O is required
for v1 at these volumes; all depth arrays fit in memory as numpy float64 arrays
(< 1 MB per curve per well).

### Cadence

The pipeline is invoked on-demand, not on a schedule. There is no always-on service,
no queue, and no concurrent run assumption in v1. A single run on a Kansas/Schaben
well (all phases implemented) is expected to complete in under 10 minutes on the
target hardware (16 GB VRAM GPU, WSL2), dominated by LLM inference time. No SLA is
set for latency in v1 because the system is not a service; it is a batch tool run
by the developer.

### Storage

All outputs are written to `outputs/` (gitignored). The developer is responsible
for archiving runs of interest. No retention policy is enforced by the pipeline;
no automatic cleanup is performed. Data files live in `data/` (gitignored); they
are not bundled with the repository and must be placed there by the operator before
invocation.

---

## Open questions

- **Config JSON schema version for `parameters` and `parameter_provenance` fields.**
  The exact field names, units, and enum values for the parameter config JSON are
  defined during Phase 2. The ledger's `computations[].parameters` object mirrors
  the config schema; finalising the schema is a prerequisite for implementing the
  ledger writer. Until Phase 2 closes this, the ledger schema above is provisional
  for those fields.

- **Convergence threshold N.**
  The circuit-breaker iteration limit is set to 3 in v1. Whether this is appropriate
  cannot be determined until Phase 4 integration testing shows typical convergence
  patterns on Kansas data. The value is configurable; it will be revisited as part of
  Phase 4 acceptance.

- **Cross-plot matrix density values for limestone and dolomite.**
  The neutron-density cross-plot lithology lines require matrix density and neutron
  response values for the reference minerals. Kansas/Schaben has carbonates. The
  specific values (e.g., ρma for dolomite: 2.87 g/cc, φN-matrix: −0.02 v/v) must
  be confirmed against the reference used for the accepted Kansas interpretation
  before Phase 3 implements the cross-plot validator.

- **`DID_NOT_CONVERGE` report emission policy.**
  When the circuit breaker fires, the current schema emits a report with
  `convergence_status: DID_NOT_CONVERGE`. Whether to emit the partial prose report
  in this state, or emit only the ledger with an error header and no prose, is a
  product decision (related to Charter Open question (b) on hard abstention). Deferred
  to Phase 4 / Phase 7.
