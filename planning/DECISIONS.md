# Decisions log — autonomous run (user away)

Off-blueprint decisions taken at my discretion during the autonomous build, each with
justification, so they are auditable on return. Newest first.

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
