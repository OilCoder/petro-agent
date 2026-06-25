<!--
PRE-FORM / MOCKUP of the petrophysical report output.
ALL VALUES ARE DUMMY — placeholders to validate WHAT INFORMATION the report carries
and HOW confidence is expressed. Not a real interpretation. Field-scale (Topic 3 = whole field).
Figures are described as [FIG] placeholders (the real ones are matplotlib PNGs).
-->

# Petrophysical Interpretation Report — Schaben Field (DUMMY)

| | |
|---|---|
| **Field** | Schaben (Mississippian "Mississippi Lime"), Ness County, Kansas |
| **Operator / source** | Kansas Geological Survey — public LAS (Magellan) |
| **Wells in this report** | 6 (SCH-1, SCH-2, SCH-3, SCH-4, SCH-7, SCH-9) |
| **Report scope** | Field-wide (per-well results + field rollup) |
| **Run ID** | `petroagent-run-2026-06-24T14:55:03Z-DUMMY` |
| **Engine / pipeline version** | `engine 0.1.0` · `pipeline 0.1.0` |
| **Generated** | autonomously, no human in the per-report loop |
| **Ledger** | `outputs/schaben_field_2026-06-24/ledger.json` (every number below traces here) |

> **Confidence legend.** Each result block is tagged by parameter provenance:
> **● FIRM** (core-calibrated) · **◐ QUALIFIED** (offset-derived) · **○ BRACKETED** (regional/global default — reported as a range, with the dominant uncertainty stated).
> The system does not claim "always correct" — it states how well-supported each number is.

---

## 1. Executive summary

The Schaben field (6 wells, Mississippian carbonate) was interpreted autonomously
from raw LAS. Aggregate **field net pay = 41.2 m** across 6 wells (mean 6.9 m/well,
P10–P90 across wells 3.1–11.4 m). The principal reservoir interval is the **Osage/Meramec
chert-rich carbonate** between ~1,360–1,440 m. **Water saturation is the dominant
uncertainty**: Rw and the Archie cementation exponent *m* are **regional defaults (○ BRACKETED)**
for all wells except SCH-4, so field-wide Sw and therefore net pay carry wide ranges.
SCH-2 and SCH-9 are flagged for **washout (bad-hole)** over part of the pay interval; their
density-porosity there is masked and the affected net pay is reported low-confidence.

> ○ **BRACKETED — read with the stated range.** Field net pay P10/P50/P90 = **31.8 / 41.2 / 58.6 m**.
> The spread is driven almost entirely by Rw (regional default 0.04 Ω·m, ±0.02) and *m*
> (default 2.0, range 1.97–2.5 for vuggy carbonate). If a single core-measured Rw became
> available, this range would tighten materially. This is the most important caveat in the report.

---

## 2. Objectives and scope

- Compute Vsh, PHIE, Sw, cutoffs, and net pay for all 6 Schaben wells from raw KGS LAS.
- Aggregate to **field-level** net pay, zone correlation, and a quality/net-pay map.
- Quantify uncertainty by **Monte Carlo** propagation of parameter ranges (P10/P50/P90).
- State the confidence tier of every block; emit a fully traceable ledger.
- **Out of scope (v1):** permeability, shaly-sand Sw models (Waxman-Smits/Dual-Water),
  saturation-height, fluid-contact picking, multi-mineral solvers.

---

## 3. Field and well inventory

| Well | API (KID) | Interval (m) | GR | RHOB | NPHI | RT | CALI | Core? | Intake |
|---|---|---|---|---|---|---|---|---|---|
| SCH-1 | 15-135-2xxxx | 1300–1480 | ✓ | ✓ | ✓ | ✓ | ✓ | – | ACCEPTED |
| SCH-2 | 15-135-2xxxx | 1310–1475 | ✓ | ✓ | ✓ | ✓ | ✓ | – | ACCEPTED (washout) |
| SCH-3 | 15-135-2xxxx | 1295–1465 | ✓ | ✓ | ✓ | ✓ | – | – | ACCEPTED (no CALI → no bad-hole mask) |
| SCH-4 | 15-135-21452 | 1320–1490 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ACCEPTED (type log + core) |
| SCH-7 | 15-135-2xxxx | 1305–1470 | ✓ | – | ✓ | ✓ | ✓ | – | ACCEPTED (neutron-only PHIE, degraded) |
| SCH-9 | 15-135-2xxxx | 1330–1485 | ✓ | ✓ | ✓ | ✓ | ✓ | – | ACCEPTED (washout) |
| SCH-5 | 15-135-2xxxx | — | ✓ | – | – | ✓ | – | – | **REJECTED** (no NPHI & no RHOB → cannot compute PHIE) |

> Note: SCH-5 was **rejected at intake** — the system never fabricates missing curves.
> SCH-7 lacks RHOB → PHIE computed neutron-only and **degradation logged** in the ledger.

---

## 4. Data QC summary

Raw LAS, no manual preprocessing — the automated QC gate produced a per-depth quality map.

| Well | Unit fixes | Spikes removed | Bad-hole (washout) % | Quality |
|---|---|---|---|---|
| SCH-1 | NPHI %→v/v | 4 | 2% | GOOD |
| SCH-2 | – | 7 | 19% (1402–1419 m) | DEGRADED over pay |
| SCH-3 | RHOB kg/m³→g/cc | 2 | n/a (no CALI) | GOOD (unmasked) |
| SCH-4 | – | 1 | 0% | GOOD |
| SCH-7 | NPHI %→v/v | 3 | 3% | GOOD (PHIE degraded) |
| SCH-9 | – | 9 | 22% (1451–1470 m) | DEGRADED over pay |

[FIG: per-well **data-quality track** — GOOD / DEGRADED / EXCLUDED vs depth]

---

## 5. Methodology

| Step | Method (frozen, golden-tested) | Version |
|---|---|---|
| Vsh | Larionov **old rocks** (Paleozoic) from GR | `calc_vsh 0.1.0` |
| PHIE | Density–neutron crossplot average (neutron-only fallback where RHOB absent) | `calc_phie 0.1.0` |
| Sw | Archie | `calc_sw 0.1.0` |
| Net pay | Vsh/PHIE/Sw cutoffs → net sand → net reservoir → net pay → NTG | `netpay 0.1.0` |
| Uncertainty | **Monte Carlo** per-depth sampling of parameter ranges → P10/P50/P90 | `mc 0.1.0` |

All numbers are produced by the deterministic engine. The LLM only selects methods/
parameters from the vetted library and writes this prose — it never computes a number.

---

## 6. Parameters and provenance

| Parameter | Value (P50) | Range | Provenance | Source (citation) | Tier |
|---|---|---|---|---|---|
| GR clean / clay | 18 / 110 API | ±10 | per-well P5/P95 | data-derived | ◐ |
| Matrix density ρma | 2.71 g/cc | 2.68–2.87 | regional (limestone/dolomite) | KGS OFR2000-79 | ◐ |
| Archie a | 1.0 | fixed | default | Winsauer 1952 | ○ |
| Archie m | 2.0 | 1.97–2.5 | default (vuggy carbonate) | Archie 1942 / KGS Schaben | ○ |
| Archie n | 2.0 | fixed | default | Archie 1942 | ○ |
| Rw | 0.04 Ω·m | 0.02–0.06 | regional | KGS Schaben | ○ |
| Rw (SCH-4 only) | 0.038 Ω·m | ±0.005 | **core/SP-derived** | well SCH-4 core | ● |

> The **citations table** (not RAG) gives each parameter exactly one frozen source in the ledger.
> SCH-4 is the only well with a core-constrained Rw → its Sw block is **● FIRM**; all others **○ BRACKETED**.

---

## 7. Zonation (field-correlated)

| Zone | Top–Base (m, datum) | Lithology | Present in |
|---|---|---|---|
| Z1 — Upper chert | ~1,360–1,392 | cherty dolomite | all 6 |
| Z2 — Main pay | ~1,392–1,428 | vuggy limestone | all 6 |
| Z3 — Tight base | ~1,428–1,452 | tight dolomite | SCH-1/3/4/9 |

[FIG: **zone-correlation panel** — GR + net-pay flag across the 6 wells, flattened on Z1 top]

---

## 8. Results

### 8.1 Per-well summary

| Well | Gross (m) | Net pay (m) P10/P50/P90 | NTG | Avg PHIE | Avg Sw P50 | Avg Vsh | Tier |
|---|---|---|---|---|---|---|---|
| SCH-1 | 120 | 6.4 / 8.1 / 10.0 | 0.21 | 0.12 | 0.38 | 0.16 | ○ |
| SCH-2 | 110 | 2.0 / 3.1 / 4.6 | 0.11 | 0.10 | 0.46 | 0.22 | ○ (washout) |
| SCH-3 | 105 | 5.2 / 6.7 / 8.8 | 0.19 | 0.11 | 0.41 | 0.18 | ○ |
| SCH-4 | 125 | 9.6 / 11.4 / 13.1 | 0.30 | 0.14 | 0.31 | 0.13 | ● Sw firm |
| SCH-7 | 108 | 4.1 / 5.5 / 7.2 | 0.16 | 0.10 | 0.43 | 0.19 | ◐ (PHIE degraded) |
| SCH-9 | 115 | 4.0 / 6.4 / 9.0 | 0.17 | 0.11 | 0.40 | 0.20 | ○ (washout) |
| **Field** | **683** | **31.8 / 41.2 / 58.6** | **0.19** | **0.12** | **0.39** | **0.18** | mixed |

### 8.2 Field rollup

- **Field net pay (P50):** 41.2 m · **HCPV (bulk-volume-hydrocarbon proxy):** 0.41 m·frac (DUMMY)
- **Best well:** SCH-4 (core-calibrated, highest NTG, lowest Sw) — the only ● FIRM Sw.
- **Weakest data:** SCH-2, SCH-9 (washout over pay); SCH-3 (no CALI → bad-hole not maskable, treat NTG as optimistic).

[FIG: **field net-pay map** — bubble/contour of net pay over the 6 well locations]

### 8.3 Detailed well example — SCH-4 (type log)

[FIG: **composite triple-combo plot** — Track1 GR+CALI · Track2 RT(log) · Track3 RHOB+NPHI · Track4 PHIE · Track5 Sw · Track6 net-pay flag]
[FIG: **Pickett plot** — log Rt vs log PHIE, Sw lines; confirms m≈2.0, Rw≈0.038]
[FIG: **neutron-density crossplot** — lithology check vs limestone/dolomite lines]

| Zone | Net pay (m) | PHIE | Sw P10/P50/P90 | Vsh | Tier |
|---|---|---|---|---|---|
| Z1 | 2.1 | 0.11 | 0.30/0.35/0.42 | 0.12 | ● |
| Z2 | 8.0 | 0.16 | 0.22/0.27/0.34 | 0.10 | ● |
| Z3 | 1.3 | 0.09 | 0.41/0.48/0.57 | 0.19 | ◐ |

> ● **FIRM (SCH-4).** With a core-constrained Rw (0.038 Ω·m), Z2 water saturation is
> **Sw = 0.27 (P10/P90 0.22–0.34)** — a comparatively tight range. Net pay over Z2 is 8.0 m.

---

## 9. Uncertainty and limitations

- **Propagation:** Monte Carlo (2,000 realizations) over the parameter ranges of §6,
  per depth, giving the P10/P50/P90 fields throughout.
- **Sensitivity:** field net pay is dominated by **Rw (52%)** and **m (29%)** — both
  *regional defaults* for 5 of 6 wells. **This is what the report most wants you to know:
  the headline number rests on uncalibrated parameters except in SCH-4.**
- **Calibration (statistical):** reliability/ECE is reported against the VOLVE benchmark
  (separate run); on this field it is **not** measurable (no ground truth) — confidence
  here is *procedural* (provenance tiers), not yet empirically calibrated.
- **Data limits:** SCH-2/SCH-9 washout, SCH-3 no CALI, SCH-7 neutron-only PHIE, SCH-5 rejected.
- **Honest ceiling:** without core in most wells, Sw is genuinely range-bounded, not a
  confident point. The system reports the range and names the cause; it does not invent precision.

---

## 10. Conclusions

1. Schaben shows a coherent Mississippian pay interval (Z2) across all 6 wells; field
   net pay P50 ≈ 41 m, but with a **wide P10–P90 (32–59 m)** driven by default Rw/m.
2. **SCH-4 is the anchor** — core-calibrated, ● FIRM Sw, the most defensible well.
3. **Highest-value next action:** a single core/produced-water Rw on a second well would
   collapse most of the field-wide Sw uncertainty.
4. Bad-hole intervals (SCH-2, SCH-9) and SCH-3's missing CALI are flagged; their net pay
   is reported low-confidence, not silently trusted.

---

## Appendix A — Ledger excerpt (traceability, DUMMY)

```json
{
  "number": {"well": "SCH-4", "zone": "Z2", "name": "Sw_p50", "value": 0.27},
  "from": {
    "curves": ["RT@1402.3m=12.4", "PHIE@1402.3m=0.162"],
    "function": "calc_sw", "version": "0.1.0",
    "params": {"a": 1.0, "m": 2.0, "n": 2.0, "Rw": 0.038},
    "provenance": {"Rw": "core:SCH-4", "m": "default:Archie1942", "n": "default", "a": "default:Winsauer1952"},
    "validators": ["bounds:pass", "cross_curve:pass", "mn_skipped_no_dt"],
    "uncertainty": {"method": "monte_carlo", "n": 2000, "p10": 0.22, "p90": 0.34},
    "confidence_tier": "FIRM"
  }
}
```

## Appendix B — Checklist / completeness gate (DUMMY)

| Item | Present | Note |
|---|---|---|
| All wells QC'd before compute | ✓ | quality map per well |
| Every number ledger-traced | ✓ | O(1) lookup |
| Confidence tier on every block | ✓ | §6 provenance |
| Parameter citations frozen | ✓ | §6 table |
| Bad-hole flagged not hidden | ✓ | §4 |
| Rejected wells listed with reason | ✓ | SCH-5 |
| Uncertainty propagated (MC) | ✓ | §9 |
