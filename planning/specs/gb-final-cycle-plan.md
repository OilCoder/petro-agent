# GB — Final improvement cycle: evaluation and plan

Date: 2026-07-04 · Branch: `experiment/claude-analyst` · Status: APPROVED (user mandate:
"último ciclo de mejoras", meticulous, memory during the cycle, field identity OK but no
technical field specs, never direct the report, never let them compute).

## Part 1 — Five-axis evaluation: summit (v3) vs measured agents (v11)

### 1. Communication (what one decision actually sees)

The agent decides each step from a STATE JSON capped at 6,500 chars carrying exactly ONE
prior observation (`last_observation`). Every new read evicts the previous one.

**Measured consequence (v11, all models):** ~80% of observations are REPEATS of an
observation already executed in the same well. Extremes: gpt-5 well 25990 = 32/32 pure
observations (`depth_quality` ×16 + `low_res_scan` ×15, zero decisions, chain closed by
deterministic re-close); qwen 26002 = `validate_choice` ×15; ultra 24,881 =
`depth_quality` ×11. The models are not indecisive — they are **amnesic**: they re-buy
the same evidence because the loop cannot show them what they already own.

The summit analyst kept every observation in context permanently. This is the largest
single mechanical gap, and it is exactly the "memory during the cycle" the user mandated.

### 2. Sandbox (loop mechanics)

- Budget 32 steps is adequate — but repeats consume it (gpt-5 spent 100% of one well's
  budget re-reading). Fixing axis 1 effectively multiplies the budget ~3×.
- Wasted-step feedback exists for compute no-ops but NOT for repeated observations
  (known pending item: opus repeated depth_quality 8× unflagged in v10).
- Zone recompute, staleness invalidation, deterministic re-close: sound, no change.

### 3. Tools

- Parity gap opened by summit v3: `sp_rw` (SP→Rw with drift-corrected SSP) and
  `movable_hydrocarbon_index` (Rxo/Rt) exist as vetted functions but agents cannot reach
  them. Rw is the declared dominant uncertainty in every report — the agents deserve the
  same evidence channel.
- `validate_choice` was adopted when offered (qwen ×40); `request_tool` unused (0/15).

### 4. Information provided

- Field pack bins at 100 m dilute the thin deep carbonate: the Mississippian target
  (~1310 m) is invisible in coarse medians, and v11 zones cluster at 184–430 m tops —
  they trim overburden but miss the reservoir (PHIE-plausibility abstention persisted
  15/15). Finer bins in the deep half are engine facts, not direction.
- Regional brief (GA-5) carried technical field specs (lithology, stratigraphy). New
  user rule: FIELD IDENTITY is allowed; technical specifications are NOT. The brief must
  shrink to identity + log-era acquisition caveats; the double leak gate stays.

### 5. Mechanics / methodology of work

- Cross-well memory carries only the agent's scrubbed qualitative note (~1500 chars).
  Their prior ANALYSES (methods chosen, zone, outcome, agreement stats — all ledger
  facts) are not carried. The user mandates carrying analyses too.
- Sequencing works: ultra's evidence_efficiency rose 0.12→0.55 across wells as notes
  accumulated; method consistency appeared field-wide in v11. The lever works — feed it
  more signal.

**Verdict:** after GA, the remaining gap is ~memory (axes 1+5), ~information resolution
(axis 4), and ~tool parity (axis 3). None of it requires directing the report or letting
the model compute.

## Part 2 — The GB levers (all honest; nothing scripts a decision)

### GB-1 — Observation journal (within-well memory; the big one)
The engine keeps a compact journal of every observation already executed this well
(action + target + one-line engine summary, deduplicated). STATE carries
`observations_so_far` (budget-managed, newest last; critical fields still first under
the cap). Repeated observations now also count as `wasted_steps` (the engine tells the
agent "you already own this read" in the NO-OP reply, same as compute no-ops).
- Done when: journal visible in scripted test; a repeated observation returns the
  cached summary + no-op notice; wasted_steps counts it; 4 gates green.

### GB-2 — Cross-well analysis digest (memory between wells)
`case_file` becomes: per prior well, an ENGINE-COMPOSED factual digest (uwi, zone or
none, methods selected + source, net pay P50, abstain flag, validate_choice agreement
if commissioned) + the agent's own scrubbed note. Ledger facts need no scrubbing; the
note stays scrubbed. Cap grows to ~2500 chars (drop-oldest).
- Done when: digest builder unit-tested; driver threads it; scripted carry-over test.

### GB-3 — Brief trimmed to identity (no technical specs)
`regional_brief_kansas.md` keeps ONLY: field identity (Schaben field, Ness County,
Kansas — the field the wells belong to) + log-era acquisition caveats (count-rate
neutron pre-1970s, GR-uranium in carbonates, digitization skepticism). REMOVED:
lithology claims, stratigraphic interval claims, brine claims. Both leak gates stay.
- Done when: brief edited; mechanical leak test still green; 7-focus audit re-recorded.

### GB-4 — Tool parity: rw_evidence + mhi_scan observations
Two new read-only observations, offered when inputs exist:
- `rw_evidence`: engine runs sp_ssp + rw_from_ssp (offset-median RMF, declared) for THIS
  well; returns {ssp_mv, rw_ohmm, assumptions} or an honest unreadable note.
- `mhi_scan`: engine runs movable_hydrocarbon_index (RXO+RT), returns profile stats.
Facts only; adopting or ignoring the evidence stays the agent's call. The agent may cite
it; MC band adoption is NOT automatic (that was the summit analyst's own decision).
- Done when: registered in _OBSERVE_NEEDS with curve gating; runner tests; prompt gains
  one neutral line listing them among observations.

### GB-5 — Field pack depth resolution
`well_depth_bins` gains `fine_bin_m=50` for the deepest 500 m of each well (100 m
above). Same medians, same row gating — pure resolution. Field tops summary unchanged.
- Done when: bins test extended (fine rows appear only in the deep tail); cap re-checked
  in smoke.

### GB-6 — v12 regeneration + final A/B (the last measurement)
Driver `gen_field_report_v12_gb.py` (v11 driver + GB wiring: journal is engine-side,
digest built per well, brief v2, MODEL/OUT_SUB params). Models: nemotron-ultra,
nemotron-super (free, parallel), gpt-5, qwen3-max (paid — user recharged OpenRouter for
this cycle), gemmas opportunistic. Metrics add: `repeated_observations` (should
collapse), zone tops distribution (do they reach the deep block?), evidence_efficiency.
Final comparison: summit v3 vs v12 across the same axes → project conclusions in
bitácora + checkpoint.

## Non-goals
- No formation tops, no reservoir depth hints, no method suggestions — the brief shrinks
  precisely to avoid pre-answering the geology.
- No multi-well single loop (G6 full) — sequenced batch + richer memory captures the
  value at a fraction of the risk.
- No relaxation of any honesty gate; claim verifier stays hard in the summit lane.

## Verification
Per phase: new golden tests + `pytest -q` + `mypy src/` + `ruff check` + `ruff format
--check` + conventional commit. GB-3 re-runs both leak gates. GB-6 smoke (1 well,
scripted) before batch: journal visible, repeat returns cached+no-op, digest carried,
rw_evidence/mhi_scan respond, brief v2 visible.
