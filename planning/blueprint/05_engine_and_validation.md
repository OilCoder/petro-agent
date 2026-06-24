# Engine & Validation — petro-agent

This document specifies the project's core asset: the vetted deterministic
petrophysical engine, the parameter provenance hierarchy that feeds it, the QC gate
that guards its inputs, and the independent validators that audit its outputs. It
builds on the equations fixed in `02_problem_data.md`, the intake contracts defined
in `03_source_sink_contracts.md`, and the pipeline stages sketched in
`04_pipeline_architecture.md`, adding the implementation detail needed to write the
functions, the golden tests, and the validator harness.

---

## Vetted engine (functions + golden tests)

### What "vetted" means in this project

Every function on the quantitative path must be:
1. Authored once, offline, by the developer — never generated at runtime by an LLM.
2. Version-pinned (semantic version embedded in the function module and logged in the
   ledger's `function_version` field on every call).
3. Covered by a golden test suite that must exit 0 before any code reaches
   `src/petrophysics/`.

The three functions below are the complete quantitative path for v1. No other
petrophysical equation is introduced before the Phase 8 regression benchmark.

---

### `calc_vsh` — Larionov old-rocks (Vsh from GR)

**Module**: `src/petrophysics/vsh.py`
**Version**: starts at `0.1.0`; incremented on any change to the equation or clipping
behaviour.

**Equation**:

```
IGR = (GR - GR_min) / (GR_max - GR_min)
Vsh = 0.33 * (2 ** (2.0 * IGR) - 1.0)
```

This is the Larionov correction for old (pre-Tertiary) rocks. It is the only
permitted variant for Kansas/Schaben data (Invariant 6 in the Charter). The Tertiary
variant (`Vsh = 0.083 * (2**(3.7 * IGR) - 1.0)`) is implemented in the same module
under `variant="tertiary"` to support VOLVE runs, but its activation is controlled by
the `PROV` formation tag in the LAS header — not by an agent prompt.

**Signature**:

```python
def calc_vsh(
    gr: np.ndarray,
    gr_min: float,
    gr_max: float,
    variant: str = "old_rocks",   # "old_rocks" | "tertiary"
) -> np.ndarray:
```

- Input `gr` is a 1-D numpy float64 array of gamma-ray values (API units).
- `gr_min` and `gr_max` are scalar floats drawn from the config library (not from
  the runtime data unless explicitly overridden via offset calibration).
- The function clips IGR to [0.0, 1.0] before applying the Larionov correction, so
  that GR values outside the calibration range produce Vsh at the physical boundary
  rather than outside it.
- Output is clipped to [0.0, 1.0] after computation. NaN inputs propagate as NaN
  outputs (masked depth samples are not un-masked by this function).

**Golden tests** (`tests/test_vsh.py`):

| Test name | What it checks | Analytic expectation |
|---|---|---|
| `test_vsh_bounds_old_rocks` | All outputs ∈ [0.0, 1.0] for GR ∈ [0, 300] API, any valid gr_min/gr_max | Physical bound |
| `test_vsh_clean_sand` | gr = gr_min → Vsh = 0.0 | Analytic: IGR = 0, 0.33*(1-1) = 0 |
| `test_vsh_pure_shale` | gr = gr_max → Vsh = 0.99 | Analytic: IGR = 1, 0.33*(2^2 - 1) = 0.99 (within atol; the output clip to [0,1] does not raise 0.99) |
| `test_vsh_midpoint` | gr = (gr_min + gr_max)/2 → known analytic value | IGR = 0.5 → Vsh = 0.33*(2^1 - 1) = 0.33 |
| `test_vsh_monotonicity` | Vsh is non-decreasing as GR increases from gr_min to gr_max | Monotonicity of Larionov old-rocks |
| `test_vsh_nan_passthrough` | NaN inputs produce NaN outputs; non-NaN unchanged | NaN isolation |
| `test_vsh_tertiary_differs` | Same inputs with variant="tertiary" produce different output than variant="old_rocks" | Variant separation |
| `test_vsh_dimensional` | Function accepts any monotonically scaled GR (not just API) and remains in [0,1] | Dimensionless output regardless of input scale |

Test fixture: GR array `[0, 25, 50, 75, 100, 150, 200]` API with `gr_min=10`,
`gr_max=150`. Expected Vsh values computed analytically and hardcoded as toleranced
assertions (`atol=1e-6`).

---

### `calc_phie` — density-neutron crossplot (PHIE from RHOB + NPHI)

**Module**: `src/petrophysics/phie.py`
**Version**: starts at `0.1.0`.

**Equation**:

```
phi_D = (rho_ma - rhob) / (rho_ma - rho_fl)
PHIE  = (phi_D + nphi) / 2
```

`phi_D` is the density-derived porosity and `nphi` is the neutron porosity already
in v/v fraction (post-unit-conversion at intake). The average of the two is the
crossplot porosity estimate.

**Signature**:

```python
def calc_phie(
    rhob: np.ndarray,    # bulk density, g/cc
    nphi: np.ndarray,    # neutron porosity, v/v fraction
    rho_ma: float,       # matrix density, g/cc (from config)
    rho_fl: float,       # fluid density, g/cc (from config)
) -> np.ndarray:
```

- `rho_ma` default for clean sandstone: 2.65 g/cc. For limestone: 2.71 g/cc.
  For dolomite: 2.87 g/cc. The active value is drawn from the config library and
  logged in the ledger `parameters` object with its provenance.
- `rho_fl` default for liquid-filled pore space: 1.00 g/cc (fresh water or brine,
  depending on config). For gas-bearing zones: 0.0–0.1 g/cc range logged separately.
- Output is clipped to [0.0, 0.45] v/v. The upper bound of 0.45 v/v is a
  physical-plausibility ceiling for consolidated formations; it is stored in the
  config library as `phie_max` so it can be overridden for vuggy carbonates.
- If either `rhob` or `nphi` is NaN at a depth, the fallback is:
  - RHOB masked, NPHI present → `PHIE = nphi` (neutron-only; logged as degradation,
    `confidence_impact = tier_downgrade`).
  - NPHI masked, RHOB present → `PHIE = phi_D` (density-only; logged as degradation,
    `confidence_impact = tier_downgrade`).
  - Both masked → NaN output; depth is in the `EXCLUDED` quality tier.

**Golden tests** (`tests/test_phie.py`):

| Test name | What it checks | Analytic expectation |
|---|---|---|
| `test_phie_bounds` | All outputs ∈ [0.0, 0.45] for physically valid rhob/nphi | Physical bound |
| `test_phie_zero_porosity` | rhob = rho_ma, nphi = 0.0 → PHIE = 0.0 | phi_D = 0, average = 0 |
| `test_phie_known_sandstone` | rhob = 2.00, nphi = 0.30, rho_ma = 2.65, rho_fl = 1.00 → phi_D = 0.40, PHIE = 0.35 | Analytic: (2.65-2.00)/(2.65-1.00) = 0.394; (0.394+0.30)/2 = 0.347; rounded within atol=1e-3 |
| `test_phie_monotonicity_rhob` | PHIE decreases as rhob increases (all else constant) | Denser rock → less porosity |
| `test_phie_monotonicity_nphi` | PHIE increases as nphi increases (all else constant) | More neutron-porosity → more PHIE |
| `test_phie_nan_rhob_fallback` | NaN rhob → output equals nphi (neutron-only path) | Degradation path |
| `test_phie_nan_nphi_fallback` | NaN nphi → output equals phi_D (density-only path) | Degradation path |
| `test_phie_both_nan` | Both NaN → output NaN | Full exclusion |
| `test_phie_dimensional` | Output is dimensionless (v/v) regardless of whether rho_ma/rho_fl are in g/cc or kg/m³ (function requires g/cc — test confirms rejection of kg/m³ range) | Units guard |

---

### `calc_sw` — Archie (Sw from RT, PHIE, a/m/n/Rw)

**Module**: `src/petrophysics/sw.py`
**Version**: starts at `0.1.0`.

**Equation**:

```
Sw^n = (a * Rw) / (Rt * PHIE^m)
Sw   = ((a * Rw) / (Rt * PHIE^m)) ** (1.0 / n)
```

This is the classic Archie equation for clean formations. It is the only Sw method
for v1. When lithology cross-plots (Phase 3) indicate significant clay content,
the system logs a degradation noting that a shaly-sand correction (e.g., Waxman-Smits)
would be more appropriate, but the Archie result is still the output — the degradation
narrows the confidence tier, it does not substitute a different equation.

**Signature**:

```python
def calc_sw(
    rt: np.ndarray,     # true resistivity, ohm·m
    phie: np.ndarray,   # effective porosity, v/v
    a: float,           # tortuosity factor (dimensionless)
    m: float,           # cementation exponent (dimensionless)
    n: float,           # saturation exponent (dimensionless)
    rw: float,          # formation water resistivity, ohm·m at formation temperature
) -> np.ndarray:
```

- Output is clipped to [0.0, 1.0]. Sw > 1.0 before clipping is a physical violation
  that the `validate` stage flags as a `mechanical` objection.
- Division by zero is guarded: if `PHIE == 0` at any depth, output is NaN (no
  porosity → Archie undefined; logged as a depth-specific degradation).
- NaN inputs in `rt` or `phie` propagate as NaN outputs.
- The function does not apply a log₁₀ transform internally. The pipeline passes `rt`
  in linear ohm·m; log transforms for cross-plots are applied by the validator layer,
  not the engine.

**Golden tests** (`tests/test_sw.py`):

| Test name | What it checks | Analytic expectation |
|---|---|---|
| `test_sw_bounds` | All outputs ∈ [0.0, 1.0] for Rt ∈ [0.01, 50000], PHIE ∈ [0.05, 0.45], typical a/m/n/Rw | Physical bound |
| `test_sw_water_zone` | rt = rw/PHIE^m (water-saturated Archie condition) → Sw = 1.0 | Analytic |
| `test_sw_known_case` | rt = 10, PHIE = 0.20, a = 1.0, m = 2.0, n = 2.0, rw = 0.05 → Sw = sqrt(0.05*1/(10*0.04)) = sqrt(0.125) ≈ 0.354 | Analytic; atol=1e-4 |
| `test_sw_monotonicity_rt` | Sw decreases as rt increases (all else constant) | Higher resistivity → lower water saturation |
| `test_sw_monotonicity_phie` | Sw increases as PHIE increases (all else constant, fixed Rt and Rw) | More porosity for same resistivity → more water |
| `test_sw_zero_phie` | PHIE = 0.0 → output NaN (not a crash, not zero) | Guard for division by zero |
| `test_sw_nan_passthrough` | NaN rt or NaN phie → NaN output; non-NaN depths unchanged | NaN isolation |
| `test_sw_archie_m_sensitivity` | Increasing m from 1.5 to 2.5 (all else fixed) monotonically lowers Sw estimate | Cementation exponent direction |
| `test_sw_dimensional` | Output is dimensionless (v/v fraction) for any physically valid input | Dimensionless check |

---

### `apply_cutoffs` / `compute_net_pay` — cutoff application and net pay

**Module**: `src/petrophysics/netpay.py`
**Version**: starts at `0.1.0`; incremented on any change to the cutoff rule or the
net-pay summation behaviour.

This is the deterministic net-pay engine called by the `zonate` pipeline stage
(`04_pipeline_architecture.md` Stage 7b). It applies the three reservoir cutoffs to the
computed Vsh/PHIE/Sw curves to produce a per-depth net-pay flag, and sums net-pay sample
thickness per zone. It does not delineate zone boundaries itself (that is the `zonate`
stage's deterministic grouping of contiguous net-pay runs); it answers, per depth,
"is this sample net pay?" and, per zone, "how many metres of net pay does it contain?".

**Net-pay cutoff rule**:

```
net_pay = (Vsh <= vsh_cutoff) AND (PHIE >= phie_cutoff) AND (Sw <= sw_cutoff)
```

A depth that is NaN in any of Vsh/PHIE/Sw, or tagged `EXCLUDED` in the quality map, is
never net pay (its flag is `False`).

**Signatures**:

```python
def apply_cutoffs(
    vsh: np.ndarray,        # shale volume, v/v
    phie: np.ndarray,       # effective porosity, v/v
    sw: np.ndarray,         # water saturation, v/v
    vsh_cutoff: float,      # max Vsh for net pay (from config)
    phie_cutoff: float,     # min PHIE for net pay (from config)
    sw_cutoff: float,       # max Sw for net pay (from config)
) -> np.ndarray:            # boolean net-pay flag per depth

def compute_net_pay(
    depth: np.ndarray,      # depth array, metres
    net_pay_flag: np.ndarray,  # boolean per-depth flag from apply_cutoffs
    depth_step_m: float,    # depth increment, metres
) -> dict:                  # {"gross_m": float, "net_pay_m": float, "ntg": float}
```

- `apply_cutoffs` returns a boolean array the same length as the inputs; NaN inputs map
  to `False` (never net pay).
- `compute_net_pay` sums `net_pay_flag` over the interval: `net_pay_m = count(True) *
  depth_step_m`; `gross_m` is the zone span (`base_md - top_md`); `ntg = net_pay_m /
  gross_m` (0.0 when `gross_m == 0`). The summation is over the depth range handed to the
  function by the `zonate` stage; the function does not itself find zone boundaries.

**Golden tests** (`tests/test_netpay.py`):

| Test name | What it checks | Analytic expectation |
|---|---|---|
| `test_cutoffs_all_pass` | All samples below Vsh/Sw cutoff and above PHIE cutoff → all flags True | Net-pay rule |
| `test_cutoffs_vsh_rejects` | A sample with Vsh > vsh_cutoff is not net pay even if PHIE/Sw pass | Each cutoff is necessary |
| `test_cutoffs_phie_rejects` | A sample with PHIE < phie_cutoff is not net pay | Each cutoff is necessary |
| `test_cutoffs_sw_rejects` | A sample with Sw > sw_cutoff is not net pay | Each cutoff is necessary |
| `test_cutoffs_nan_excluded` | NaN in any of Vsh/PHIE/Sw → flag False at that depth | Exclusion of undefined samples |
| `test_net_pay_summation` | Known flag array with k True samples at step s → net_pay_m = k·s | Thickness summation |
| `test_net_to_gross` | Known gross and net → ntg = net/gross; ntg = 0 when gross = 0 | Ratio and zero-division guard |
| `test_net_pay_boundary_cutoff_equality` | Sample exactly at the cutoff (Vsh = vsh_cutoff, PHIE = phie_cutoff, Sw = sw_cutoff) is net pay (inclusive bounds) | Boundary-inclusive rule |

Test fixture: hardcoded Vsh/PHIE/Sw arrays with `vsh_cutoff = 0.40`, `phie_cutoff = 0.08`,
`sw_cutoff = 0.60`, `depth_step_m = 0.1524`; expected net-pay flags and net_pay_m computed
analytically and embedded as toleranced assertions.

---

### Shared test infrastructure

All golden tests live in `tests/` and run via `pytest -q`. No test may be skipped or
marked `xfail` without explicit developer approval.

The test fixtures use hardcoded scalar inputs and expected outputs to enforce
reproducibility — no random generation. Each expected value is computed analytically
(not from a prior run) and embedded as a tolerance-bounded assertion.

A pre-deploy check rule: `pytest -q` must exit 0 before any change to
`src/petrophysics/` is considered complete, per `verification.md`.

---

## Parameter provenance

Every parameter that enters a computation function must carry a provenance tier that
is written to the ledger alongside the value. The tier is assigned offline (by the
expert who builds the config) and is immutable at runtime — no agent may promote or
demote a parameter's provenance tier during a run.

### Provenance hierarchy

| Tier | Label in ledger | Source | Uncertainty characterisation |
|---|---|---|---|
| 1 (highest) | `core` | Direct measurement from core plugs recovered from this well or a well in the same reservoir | Narrow: ±10% on Rw; ±0.1 on m/n |
| 2 | `offset` | Calibrated to analogue wells in the same field or the same formation with core data | Moderate: ±20–30% on Rw; ±0.2 on m/n |
| 3 (lowest) | `default` | Regional or global literature values; no local calibration | Wide: ±50% on Rw; ±0.3 on m/n |

The uncertainty widths above are default bounds stored in the config library; they
are used by Phase 7 uncertainty propagation. They are not advisory prose — they are
numeric entries in the config that Phase 7 reads directly.

### Parameters, physical ranges, and defaults

All parameters below are stored in the config library (`src/params/`). The defaults
are the values used when no `core` or `offset` data is available for a well. They
represent geologically reasonable starting points for Paleozoic mixed-carbonate /
clastic sections (Kansas/Schaben context).

#### Vsh parameters

| Parameter | Symbol | Unit | Default value | Physical range | Notes |
|---|---|---|---|---|---|
| GR clean | `gr_min` | API | 20 | 0 – 100 | Corresponds to clean sand or carbonate baseline; may be set from regional statistics |
| GR shale | `gr_max` | API | 120 | 50 – 300 | 100% shale GR; set conservatively for Kansas Paleozoic |
| Larionov variant | `variant` | enum | `old_rocks` | `old_rocks` \| `tertiary` | Locked to `old_rocks` for Kansas (Invariant 6); overridable for VOLVE via `PROV` tag |

#### PHIE parameters

| Parameter | Symbol | Unit | Default value | Physical range | Notes |
|---|---|---|---|---|---|
| Matrix density (sandstone) | `rho_ma` | g/cc | 2.65 | 2.60 – 2.72 | Quartz/feldspar sandstone; override to 2.71 for limestone, 2.87 for dolomite |
| Fluid density | `rho_fl` | g/cc | 1.00 | 0.00 – 1.10 | Fresh water = 1.00; brine ≈ 1.01–1.10; gas ≈ 0.00–0.10 |
| PHIE upper bound | `phie_max` | v/v | 0.45 | 0.30 – 0.50 | Physical clipping ceiling; stored in config, not hardcoded in function |

#### Sw parameters (Archie)

| Parameter | Symbol | Unit | Default value | Physical range | Notes |
|---|---|---|---|---|---|
| Tortuosity factor | `a` | dimensionless | 1.0 | 0.5 – 2.0 | Humble formula uses 0.62; carbonate often 1.0 |
| Cementation exponent | `m` | dimensionless | 2.0 | 1.3 – 3.0 | Most common literature value; lower for vuggy carbonates |
| Saturation exponent | `n` | dimensionless | 2.0 | 1.5 – 2.5 | Default; lower when wettability deviates from water-wet |
| Water resistivity | `Rw` | ohm·m | 0.05 | 0.001 – 1.00 | Formation temperature and salinity dependent; wide range for Kansas brines |
| RT hydrocarbon floor | `rt_hydrocarbon_floor` | ohm·m | 5 | 1 – 50 | Minimum RT expected where computed Sw < 0.4; read by the cross-curve consistency validator (RT–Sw directional check), not by `calc_sw` itself |

#### Net-pay cutoff parameters

These cutoffs are not inputs to `calc_vsh` / `calc_phie` / `calc_sw`; they are read by
the `zonate` stage (`04_pipeline_architecture.md` Stage 7b) and the net-pay engine
(`apply_cutoffs`) to flag net pay, and by the VOLVE net-pay metric in
`06_evaluation_protocol.md`. They live in the same config library and carry provenance
like any other parameter.

| Parameter | Symbol | Unit | Default value | Physical range | Notes |
|---|---|---|---|---|---|
| Vsh cutoff (max) | `vsh_cutoff` | v/v | 0.40 | 0.20 – 0.60 | Net pay requires `Vsh ≤ vsh_cutoff`; conservative for Kansas Paleozoic clastics/carbonates |
| PHIE cutoff (min) | `phie_cutoff` | v/v | 0.08 | 0.03 – 0.15 | Net pay requires `PHIE ≥ phie_cutoff`; minimum economic porosity |
| Sw cutoff (max) | `sw_cutoff` | v/v | 0.60 | 0.40 – 0.70 | Net pay requires `Sw ≤ sw_cutoff`; maximum producible water saturation |

`Rw` has the highest leverage on Sw of any single parameter. A 2× error in Rw
propagates as roughly a √2 error in Sw (for n = 2). When `provenance = default`,
the uncertainty on Rw is ±50%, making the propagated Sw uncertainty dominant.

### Config JSON structure (Phase 2 target)

The parameter config is a single JSON file versioned in `src/params/`. Its SHA-256
hash is logged at run start. The schema has three top-level keys:

```json
{
  "version": "<semver>",
  "regional_defaults": {
    "paleozoic_kansas": { ... },
    "north_sea_jurassic": { ... }
  },
  "well_overrides": {
    "<UWI>": { ... }
  }
}
```

Each parameter entry includes `value`, `unit`, `provenance` (`core`/`offset`/`default`),
and `source_description` (a human-authored string). The `well_overrides` block allows
per-well core or offset values to override the regional defaults without modifying the
defaults block. The exact field names are finalised in Phase 2 (see Open questions).

### Provenance assignment rules

- An expert authors the config file offline; no runtime agent may write to it.
- If `well_overrides` contains an entry for the well's UWI, those values and their
  provenance labels take precedence over `regional_defaults`.
- If no override exists, the value from `regional_defaults` for the formation type
  (selected by the `PROV` tag) is used with `provenance = default`.
- If the `PROV` tag is absent or unrecognised, the `paleozoic_kansas` defaults are
  used with `provenance = default` and a degradation entry is written to the ledger.

---

## QC gate

The QC gate (pipeline Stage 2, `qc_gate`) runs between `load` and `compute`. No
computation executes on data that has not passed through the QC gate.

### Unit sanity checks

Applied to every curve before any masking. These are intake-time checks only;
they do not repeat inside the compute loop.

| Curve | Expected range | Action on violation |
|---|---|---|
| RHOB | 1.0 – 3.0 g/cc | Out-of-range sample flagged as `WARN` in quality map; not masked (may be a genuine extreme formation) |
| NPHI | 0.0 – 1.0 v/v | Same as RHOB |
| GR | 0 – 300 API | Same as RHOB |
| RT | 0.01 – 50 000 ohm·m | Same as RHOB |
| CALI | 3.0 – 30.0 inches | Out-of-range sample flagged as `WARN`; used in bad-hole masking |

Unit variants detected at intake (before the QC gate): NPHI in percent (range > 2.0)
and RHOB in kg/m³ (range > 10.0) are auto-converted and logged as `unit_conversion`
edits. Ambiguous ranges cause intake rejection (see `03_source_sink_contracts.md`).

### Null and spike handling

**Null masking**: the lasio null sentinel (from `~Well NULL` field, default −9999.25)
is applied across all curves simultaneously. Any sample equal to the sentinel (within
1e-3 floating-point tolerance) is masked (set to NaN) before any processing. The
sentinel value is logged in the ledger `well` object.

**Spike removal**: applied to GR, RHOB, NPHI, and RT.
- Window: ±10 depth samples centred on the candidate depth.
- Threshold: the sample exceeds 5 × the inter-quartile range of the local window
  above the local median.
- Action: the spike sample is set to NaN (not interpolated). The original value,
  depth, and curve name are logged as a `spike_removal` edit in the ledger.
- Spike removal is applied once, before bad-hole masking; it does not iterate.

All null and spike edits are recorded in the ledger `edits` array with
`type = null_mask` or `type = spike_removal`. A run with no edits is a run with
clean input data.

### Bad-hole masking (CALI / DCAL / bit size)

A bad-hole depth is one where the borehole is washed out beyond a threshold,
causing density and neutron tools to read formation-fluid mixtures instead of the
formation. Bad-hole RHOB and NPHI are physically unreliable; they must not enter
the PHIE computation.

**Preferred indicator — DCAL (differential caliper)**:
- DCAL = CALI − bit size (in the DCAL curve, this subtraction is already done by
  the logging company at acquisition time).
- A depth is flagged bad hole when `|DCAL| > 2 inches`.

**Fallback indicator — CALI vs. bit size constant**:
- Used when DCAL is absent from the LAS file (common in older Kansas wells).
- `bit_size_config` is a scalar in the config library (e.g., 8.5 inches); the
  engineer authors it from the well program.
- A depth is flagged bad hole when `CALI > (bit_size_config + 2) inches`.
- The absence of DCAL and the use of the bit-size constant are logged as a
  degradation entry (`description: "DCAL absent; bad-hole masking uses CALI vs.
  bit_size_config = <value> in."`).

**No caliper available (DCAL and CALI both absent)**:
- Both CALI and DCAL are optional curves (`03_source_sink_contracts.md`); some older
  Kansas wells carry neither. When both are absent, bad-hole masking cannot run.
- RHOB and NPHI are not bad-hole-masked in this case (no washout indicator exists).
  Their other masks — null sentinel and spike removal — still apply.
- A degradation entry is logged (`description: "No caliper (CALI/DCAL) present;
  bad-hole masking unavailable for this well."`, `confidence_impact = tier_downgrade`)
  affecting every PHIE computation that relies on RHOB/NPHI. The run proceeds; it is
  not rejected.

**Masking action**: at bad-hole depths, RHOB and NPHI are set to NaN. The depth
ranges are appended to the quality map as `DEGRADED`. GR and RT are not masked
on bad-hole alone (GR is less sensitive to washout; RT is logged in the borehole
and is moderately affected but not masked by default in v1 — this is a potential
improvement logged in Open questions).

### Data-quality map

The QC gate produces a per-depth integer array with three values:

| Tag | Integer | Condition |
|---|---|---|
| `GOOD` | 0 | No curve masked at this depth; all range checks pass |
| `DEGRADED` | 1 | At least one required curve masked (RHOB or NPHI masked by bad-hole or spike or null); GR or RT still present |
| `EXCLUDED` | 2 | All required curves masked, or GR and RT both masked (the 10-sample minimum is a whole-log intake check at `load`, not a per-depth tag — see `03_source_sink_contracts.md`) |

`EXCLUDED` depths do not produce any `computation` ledger entry. `DEGRADED` depths
produce a computation entry but with a tier downgrade and a linked degradation entry.

**Abort condition**: if more than 80% of the log depth range is tagged `EXCLUDED`
or `DEGRADED`, the pipeline aborts before entering `compute`, with a diagnostic
naming the fraction and the dominant cause. This threshold is stored in the config
library (`qc_abort_threshold = 0.80`).

---

## Independent validators

The validator harness runs in pipeline Stage 4 (`validate`), after `compute`. The
harness is a versioned artifact in `src/validators/`. Agents execute the harness;
they do not control which validators fire and cannot add or remove validators at
runtime (Invariant 3 in the Charter).

### Physical bounds validator (`src/validators/physical.py`)

Checks that the computed output curves are within the physically possible range for
any formation.

| Curve | Checked range | Violation action |
|---|---|---|
| Vsh | [0.0, 1.0] | Objection typed `mechanical`; computation flagged in ledger |
| PHIE | [0.0, `phie_max`] | Same |
| Sw | [0.0, 1.0] | Same |

A `mechanical` objection is correctable: the compute agent must revise the parameter
selection (e.g., incorrect GR min/max causing Vsh > 1.0) and re-enter `compute`.
Physical-bound violations that persist for three consecutive loop iterations trigger
the circuit breaker.

**Version**: starts at `0.1.0`. The bounds themselves are not hardcoded — `phie_max`
is read from the config library so the validator stays in sync with the engine.

### Cross-curve consistency validator (`src/validators/cross_curve.py`)

Checks directional relationships between computed curves that are physically expected
but do not follow directly from the equations.

| Check | Description | Violation action |
|---|---|---|
| Vsh–PHIE anti-correlation | In a ±20-sample window, the Pearson correlation between Vsh and PHIE must be ≤ +0.3. Strong positive correlation (dirty rock and high porosity co-occurring without explanation) is flagged. | Objection typed `support` |
| RT–Sw directional consistency | At depths where Sw < 0.4 (computed), RT must be > `rt_hydrocarbon_floor` (config default: 5 ohm·m). Low Sw and low RT co-occurring without a model-mismatch flag is implausible. | Objection typed `support` |

A `support` objection means the current interpretation is not supported by the
cross-curve evidence as presented. The compute agent may resolve it by revising
parameters (e.g., selecting a more appropriate `m` that raises RT-implied Sw into
agreement), or by flagging the inconsistency as data-limited (which reclassifies
the objection as `irreducible` on the next typing pass).

### Model-mismatch validator (`src/validators/model_mismatch.py`, active Phase 3)

Detects when the assumed lithology model (sandstone, limestone, or dolomite) is
inconsistent with what the crossplot data indicates. A model mismatch cannot be
corrected by parameter revision — it signals that the wrong equation family was
chosen. All model-mismatch objections are typed `irreducible`.

**Neutron-density crossplot check**:
- For each non-excluded depth sample, compute its position on the neutron-density
  plot relative to the three mineral reference lines (sandstone, limestone, dolomite)
  using the matrix density and neutron response values from the config.
- If more than 30% of non-excluded samples fall outside the triangle bounded by
  the three mineral lines, raise a `model_mismatch` flag for the affected depth range.
- The crossplot PNG (`outputs/<UWI>_..._crossplot_nd.png`) is generated and saved as
  evidence. The validator entry references the PNG file path.

**M-N crossplot check**:
- M index: `M = (Δt_fl - Δt) / (ρb - ρfl) × 0.01` where Δt is compressional
  slowness (DT). If DT is absent, the M-N check is skipped and a degradation entry
  is logged (`validator_id: mn_skipped_no_dt`).
- N index: `N = (Φnfl - Φn) / (ρb - ρfl)` where Φnfl and Φn are neutron porosity
  of fluid and formation, and ρb and ρfl are bulk and fluid density (same density
  denominator as the M index). Formula to be confirmed against the reference before
  freezing.
- Positions compared against Schlumberger (1989) reference mineral points. Deviations
  beyond 0.1 index units (provisional tolerance — to be confirmed against the
  reference) from the nearest mineral point are flagged.
- The crossplot PNG (`outputs/<UWI>_..._crossplot_mn.png`) is generated as evidence.

**Crossplot output specifications** (both PNGs):
- Format: PNG, 300 dpi, white background, 1200 × 900 pixels.
- Sandstone reference line: ρma = 2.65 g/cc, φN-matrix = −0.02 v/v.
- Limestone reference line: ρma = 2.71 g/cc, φN-matrix = 0.00 v/v.
- Dolomite reference line: ρma = 2.87 g/cc, φN-matrix = −0.02 v/v.
- Data points coloured by depth (viridis colormap); zone boundaries as dashed horizontal lines.
- These specific matrix values must be confirmed against the reference used for the
  Kansas/Schaben accepted interpretation before Phase 3 implements the plot (see Open
  questions).

### Data-quality propagation validator (`src/validators/data_quality.py`)

Checks that computations at `DEGRADED` depth ranges are consistently downgraded.
This validator fires `irreducible` (`data_limited`) objections that enforce the QC
gate's quality map in the confidence tier assignment, driving the tier downgrade at
the gating stage.

| Check | Action |
|---|---|
| Any computation entry at a `DEGRADED` depth whose `confidence_tier` is `FIRM` | Flag: downgrade confidence tier to at minimum `QUALIFIED`; log as `irreducible` objection so the gating stage applies the tier change |
| Any computation entry at a `DEGRADED` depth that used a masked input curve (e.g., PHIE computed density-only) without a corresponding `degradation` entry | Flag: missing degradation record; this is an internal consistency error |

---

## Objection typing

Objection typing is applied by pipeline Stage 5 (`typify_objections`). The stage is
deterministic Python — an LLM does not decide the type. The typing rules are fixed
and versioned; they cannot be overridden by the compute agent or writer.

### Three types and their meaning

**`mechanical`** — anchored to a testable external fact; correctible by the compute agent.

A mechanical objection says "this output violates a physical law or a mathematical
constraint that has a definitive answer independent of interpretation." Examples:
- Vsh = 1.12 (exceeds the physical ceiling of 1.0).
- Sw = −0.03 (below the physical floor of 0.0).
- PHIE = 0.52 (exceeds `phie_max = 0.45`).

Loop action: `correct → compute` is entered. The compute agent must revise
parameters so the violation disappears. If the same mechanical violation persists
for three consecutive iterations (circuit breaker condition), it escalates to
`DID_NOT_CONVERGE` treatment — it is not reclassified as irreducible.

**`support`** — a claim is not supported by the evidence as presented; addressable
by better parameter selection or richer justification.

A support objection says "the computed result is internally inconsistent with other
computed curves in a way that suggests the parameter selection is wrong, but cannot
be anchored to a hard physical law violation." Examples:
- Vsh = 0.05 and PHIE = 0.40 co-occurring with Sw = 0.90 in an interval where GR
  is low — suggests either Rw is too low or the interval is water-wet.
- RT–Sw inconsistency (high resistivity, high water saturation) without a model flag.

Loop action: `correct → compute` is entered. The compute agent may select a
different parameter from the config library that resolves the inconsistency. If no
valid parameter exists in the library, the agent flags the objection as
data-limited; on the next `typify_objections` pass this reclassifies it as
`irreducible`. The transition is permanent within a run: an objection reclassified
to `irreducible` does not re-enter the correctable queue.

**`irreducible`** — cannot be resolved without data the current run does not have.

An irreducible objection says "this problem exists and cannot be corrected without
calibration data (cores, offset wells, additional curve types) that is not present."
Examples:
- Model mismatch: the crossplot signature contradicts the assumed lithology model.
- Data-limited zone: PHIE is computed density-only because NPHI is masked; the
  result carries inherent uncertainty that parameter revision cannot reduce.
- Parameter entirely uncalibrated: `Rw` is `provenance = default` and no offset
  calibration exists for this formation — the saturation result has wide uncertainty
  that cannot be narrowed without data.

Loop action: NOT cycled. The objection is escalated directly to the gating stage.
The gating stage applies a confidence-tier downgrade (one level per irreducible
objection, floored at `BRACKETED`). The objection is written to the ledger
`validators` array with `objection_type = irreducible`.

### Routing table

| Objection type | `correct` loop entered? | Confidence impact | Ledger record |
|---|---|---|---|
| `mechanical` | Yes | No direct impact (resolving it is the goal) | `validators[].result = FAIL`, `objection_type = mechanical` |
| `support` | Yes | No direct impact until resolved or reclassified | `validators[].result = FAIL`, `objection_type = support` |
| `irreducible` | No | Tier downgrade (FIRM→QUALIFIED or QUALIFIED→BRACKETED) per occurrence | `validators[].result = FAIL`, `objection_type = irreducible` |
| Any type, circuit breaker fired | No | Floor at `BRACKETED` for affected blocks | `validators[].result = WARN` for unresolved; `convergence_status = DID_NOT_CONVERGE` |

### The anti-Goodhart guard

The loop terminates when `correctable_count == 0`, not when any LLM agent reports
satisfaction. The `correctable_count` is computed by the deterministic
`typify_objections` stage from the validator outputs. The compute agent cannot
satisfy the termination condition by rewriting justifications or prose; it can only
satisfy it by selecting parameters that cause the validator harness to produce no
`mechanical` or `support` objections. This separation — objective termination
predicate, subjective agent action — is the primary structural protection against
the Goodhart failure mode.

---

## Open questions

- **Crossplot matrix density reference values for Kansas carbonates**: the neutron-density
  crossplot requires matrix density and neutron-response reference lines for sandstone,
  limestone, and dolomite. The specific values used in the Kansas/Schaben accepted
  interpretation are unknown. If the crossplot reference values do not match those
  used when the accepted interpretation was built, the model-mismatch detector will
  produce false positives on correct results. These values must be confirmed before
  Phase 3 implements the crossplot validator.

- **RT masking in bad-hole zones**: the current bad-hole masking policy masks RHOB and
  NPHI at washed-out depths but not RT. True resistivity tools are laterolog or
  induction tools that read into the formation rather than the borehole fluid, so their
  response in washout is less severe than density/neutron. However, tool eccentralization
  in large boreholes can affect RT. Whether to add a conditional RT mask for extreme
  washout (CALI > bit_size + N inches, with N configurable) is an open engineering
  decision for Phase 1.

- **GR min/max estimation strategy**: `gr_min` and `gr_max` are currently expert-set
  scalars in the config library. An alternative is to estimate them automatically from
  the GR distribution (e.g., P5 and P95 of the observed GR) on a per-well or per-zone
  basis. Automatic estimation would be deterministic and logged, but would make the
  values data-dependent (a form of data-driven parameter selection). This is deferred
  to Phase 2 parameter provenance design; it would be tagged `provenance = default`
  (derived from the log itself, not from an external calibration source).

- **PHIE upper-bound value for Kansas carbonate zones**: the default `phie_max = 0.45`
  is conservative for clastics but may be too low for vuggy or fractured carbonate
  intervals in the Kansas Paleozoic section. If the Schaben wells have such intervals,
  the physical-bounds validator would flag valid high-porosity readings as violations.
  The appropriate ceiling for Kansas carbonate intervals should be confirmed before
  Phase 1 testing.

- **Spike detection window size and threshold**: the ±10-sample window and 5×IQR
  threshold for spike removal are initial values from literature practice. Their
  appropriateness for the depth-sampling interval of the Kansas/Schaben LAS files (step
  size varies by well vintage) has not been tested. These parameters will be revisited
  during Phase 1 implementation when the first Schaben LAS file is processed.
