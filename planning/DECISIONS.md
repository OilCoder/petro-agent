# Decisions log — autonomous run (user away)

Off-blueprint decisions taken at my discretion during the autonomous build, each with
justification, so they are auditable on return. Newest first.

---

## D6 (2026-06-25, Phase 8) — Final reports: invariant proven; writer prompt hardened

Generated 3 canonical reports with qwen3:30b-a3b (writer) + llama3.1:8b (reviewer),
cross-family, in `documentation/sample_reports/`. Two findings:

1. **The invariant works, demonstrably.** On 2 of 3 wells the deterministic
   `claim_verifier` returned **FLAGS** — qwen3:30b introduced a decimal not in the
   ledger, and the verifier caught it. No LLM-introduced number is trusted. This is the
   project's central promise, observed in action.
2. **Even a strong local model needs firm domain framing.** qwen3:30b initially
   misread the report genre as "data-convergence / optimization assessment" (driven by
   the `convergence_status` field) and described net-pay zone thicknesses as "oscillating
   outliers". I hardened the writer system prompt (explicit petrophysics framing; defined
   `convergence_status` as an internal QC flag, not an optimizer; demanded a rock/fluids
   interpretation) and reframed the user prompt; then regenerated the reports.

**Watch items (NEEDS-HANDSON, recorded for the user's return):** net-pay values are high
(~200-400 m) due to deferred zonation-merging + cutoff/Rw calibration — the `bracketed`
tier and high-leverage warning already flag these as low-confidence. VOLVE regression
data was not obtainable autonomously (navigation-gated Equinor download); the regression
FRAMEWORK is built and tested, awaiting the data.

---

## D5 (2026-06-25, Phase 5) — Proof report used llama3.1:8b; qwen3:30b-a3b is canonical writer

The writer agent is designed to run **qwen3:30b-a3b**, but qwen was still downloading
(~30 min) when Phase 5 code was ready. To satisfy the Phase-5 done-when (a real prose
report + ledger, claim-verifier PASS) without idling, I generated the proof report with
**llama3.1:8b** (already downloaded). It worked end-to-end (report.md written, claim
verifier PASS) but the **quality was poor** — the 8B model conflated petrophysical
"convergence_status" with optimizer convergence. This empirically confirms qwen3:30b-a3b
as the canonical writer (and is exactly the kind of thing the Topic-5 multi-model
comparison surfaces).

**Decisions:**
1. Phase 5 marked complete on the functional done-when (the agent path works).
2. Strengthened the writer system prompt with explicit petrophysics framing + a definition
   of `convergence_status` (helps any model).
3. **The canonical reports the user will review will be (re)generated with qwen3:30b-a3b**
   in the Phase-8 field run, once the model finishes downloading. Tracked in AUTONOMOUS_RUN.md.

---

## D4 (2026-06-25, Phase 4) — KGS "DCAL" is the caliper, not a differential; + over-mask guard

**Problem found running the pipeline E2E on a real Schaben well:** QC aborted with
"100% of depths unusable". Cause: this well's `DCAL` curve has median 8.87 in (max 16.9),
i.e. it is the **caliper (hole diameter)**, not a true differential caliper (which centers
near 0). My bad-hole rule `|DCAL| > 2 in` therefore flagged ~100% of the well as washed
out → RHOB/NPHI masked everywhere → QC abort.

**Decision (two guards in `src/qc/masks.py:bad_hole_mask`):**
1. If a provided `DCAL` has `median(|DCAL|) > 4 in`, reinterpret it as a **caliper** and
   apply the caliper rule (`CALI > bit_size + 2`) instead, logging a degradation.
2. If any bad-hole indicator flags **> 50%** of the well, treat it as miscalibrated:
   skip bad-hole masking and log a degradation (honest degradation, not silently nuking
   a whole well).

**Why at my discretion:** a real data-convention gotcha (KGS mnemonic naming), only
visible on real data. The fix is conservative and logged in the ledger. After it, the
pipeline runs E2E on the real well (ledger.json + cross-plot emitted, circuit breaker
fires as designed). **Watch item:** the run produced 225 fragmented zones / ~200 m net
pay — zonation granularity + cutoff/Rw calibration will be refined; the `bracketed`
confidence tier already flags these as low-confidence.

---

## D3 (2026-06-25, Phase 1) — Consolidated QC modules into masks.py + gate.py

The blueprint sketched separate `null_handler.py` / `spike.py` / `bad_hole.py` /
`range_check.py` / `quality_map.py`. I merged the masking primitives into
`src/qc/masks.py` and the orchestrator + quality map into `src/qc/gate.py`. **Why:**
they are small, tightly-coupled functions sharing the `Edit`/edits pattern; two
cohesive files read better than five one-function files and reduce import churn. No
behavior change — every blueprint QC function exists (mask_nulls, remove_spikes,
bad_hole_mask, range_flags, detect_units, _build_quality_map, qc_gate) and is tested
(`tests/test_qc.py`). Purely an internal layout choice; the public `qc_gate` contract
matches the Phase-1 done-when.

---

## D1 (2026-06-25, Phase 0) — Corrected two inverted Archie monotonicity directions in blueprint 05

**What the blueprint said (wrong).** `05_engine_and_validation.md` golden-test table for
`calc_sw` described:
- `test_sw_monotonicity_phie`: "Sw **increases** as PHIE increases" — *physically wrong*.
- `test_sw_archie_m_sensitivity`: "increasing m ... monotonically **lowers** Sw" — *physically wrong*.

**The correct physics.** Archie: `Sw = ((a·Rw)/(Rt·PHIE^m))^(1/n) ∝ PHIE^(-m/n)`. For PHIE ∈ (0,1):
- As **PHIE increases**, `PHIE^(-m/n)` **decreases** → **Sw DECREASES** (not increases).
- As **m increases**, the exponent `-m/n` is more negative and `PHIE^(-m/n)` (PHIE<1)
  **grows** → **Sw INCREASES** (not lowers). Numeric check (a=1,Rw=0.05,Rt=10,PHIE=0.2,n=2):
  m=1.5 → Sw=0.236; m=2.5 → Sw=0.529. Higher m → higher Sw. Confirmed.

**Decision.** Implemented `calc_sw` with the correct Archie formula (correct by construction)
and wrote the golden tests asserting the **correct** directions (`tests/test_sw.py`:
`test_sw_monotonicity_phie` = Sw decreases with PHIE; `test_sw_m_sensitivity` = Sw rises with m).
**Amended `05_engine_and_validation.md`** to match the correct physics.

**Why at my discretion.** This is a factual physics error in the spec, not a design choice —
there is one correct answer (Archie is unambiguous). The coherence loops checked cross-doc
*consistency*, not physics, so it slipped through; implementing + testing surfaced it. No
design tradeoff for the user to decide.

**Impact.** None on the invariant or architecture; the engine is more correct than the spec was.

---

## D2 (2026-06-25, Phase 0) — Minor, planned deviations (no spec conflict)

- **Mnemonic aliases embedded in `src/io/loader.py` for Phase 0.** The blueprint moves them
  to `src/params/mnemonic_aliases.json` in Phase 2; embedding now avoids a forward dependency.
  Will be refactored to the JSON in Phase 2 (already a Phase-2 task).
- **`mypy` `python_version = "3.12"`** (was 3.10): the venv interpreter is 3.12 and numpy 2.5
  stubs use 3.12 syntax; targeting 3.10 produced a spurious stub error. Project still supports
  >=3.10 at runtime.
- **Test data strategy:** golden tests use a committed synthetic LAS fixture
  (`tests/fixtures/synthetic_oldrocks.las`) for reproducibility; a separate integration test
  loads a real Schaben LAS only if `data/` is populated (skips otherwise), honoring the
  Phase-0 "loads a Kansas/Schaben LAS" done-when without depending on gitignored data.
