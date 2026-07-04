# Agent-gap analysis: why the Claude-session summit exceeds every measured agent, and what closes the gap

Source investigation: `debug/dbg_claude_vs_agents.py` (2026-07-04) over the summit-v2 artifacts
vs the v7–v10 agent ledgers. Companion narrative in `planning/bitacora/2026-07-03.md`.

## Measured facts (shared well 15-135-25945)

| Analyst | zone | methods chosen | tool_results | evidence calls |
|---|---|---|---|---|
| Claude session (summit v2) | yes | 3/3 | 6 | 2 |
| gpt-5 (author) | no | 0/3 | 0 | **15** |
| opus-4.8 (author) | no | 0/3 | 0 | **16** |
| qwen3-max (author) | no | 3/3 | 0 | 8 |
| nemotron-ultra (author) | no | 3/3 | 0 | 3 |

- **Inverse observation/commitment relationship**: the most capable models observed the most
  and committed the least. Observation without an interpretive framework does not converge.
- **9 of 12 headline features** of the summit report ride on engine functions that did not
  exist before the experiment (toolbox extension = pillar-2 privilege agents lack).
- The summit decisions were made OUTSIDE any loop, over an unbounded field-wide context
  (198-file census, cross-well bins tables, a sonic cross-validation) BEFORE any per-well
  execution. Agents get 16–24 steps, a 5.2 KB observation, and no memory across wells.

## Gap decomposition (by weight)

1. **Field-level study before well-level decisions (~biggest lever).** The summit's zone
   criterion came from a 25-well RHOB-bins table read as ONE object. The loop shows one well
   at a time with no cross-well memory. An analyst without the field view cannot have field
   consistency.
2. **Domain priors.** "Mississippian lives deep", "uranium inflates GR in carbonate",
   "Permian evaporites are out of scope", "NPHI/RHOB mismatch smells dolomitic" — none of
   this is in the observation surface, and none is derivable from a single well's STATE.
3. **Toolbox extension (pillar 2).** When the analysis needed Swirr, M-N, Umaa, PLSS, the
   summit ADDED vetted functions. Agents select from a frozen menu.
4. **Hypothesis→test→verdict workflow.** The summit formed hypotheses and commissioned
   discriminating measurements (M-N to adjudicate the dolomite suspicion; sonic to validate
   the count-rate transform). The loop's actions support observation, not experiment design.
5. **Budget and context.** Unbounded context and iteration vs 16–24 steps and 5.2 KB.
6. **Model-side commitment.** Even with identical environments, frontier models split into
   non-committing profiles (gpt-5/opus: 15-16 observations, 0 choices). Environment cannot
   fully fix this; it can only measure it.

## Improvement roadmap (honest levers only — nothing scripts a decision)

| # | Change | Closes | Invariant/leak status |
|---|---|---|---|
| G1 | **Field-study pass**: a deterministic pre-phase computes the cross-well evidence pack (per-well depth-bin tables for every curve, formation-top candidates, field percentiles) and puts it in EVERY well's observation. | gap 1 | Pure engine data — the same bins table the summit read. No direction. |
| G2 | **Field memory / case file**: a persistent notes artifact the agent writes per well and re-reads on the next well (its own words, carried across the batch). | gap 1 | Agent-authored; orchestrator only stores/replays it. |
| G3 | **Regional knowledge pack as DATA**: a vetted reference brief (formation tops by county, lithology expectations, tool-era caveats like GR-uranium and count-rate neutron) loaded as a document the agent may read — the equivalent of the regional literature a human analyst studies. | gap 2 | The riskiest lever: must be REFERENCE (facts with citations), never instructions. Audit against the 7 leak foci; phrased as geology, not as actions. |
| G4 | **Tool-request channel**: the agent may EMIT a spec for a missing computation ("I need Rxo/RT ratio"); a human (or a separate build phase) implements it vetted+golden before a re-run. Agents never execute unvetted math — they REQUEST it. | gap 3 | Request ≠ execute; the invariant holds; latency is a re-run. |
| G5 | **Commission-a-check action**: `validate_choice(property)` runs the engine's independent cross-check (e.g. sonic-vs-selected porosity where DT exists) and returns agreement stats. | gap 4 | Engine computes; agent commissions — same class as compare_methods. |
| G6 | **Batch-level loop**: one loop instance over N wells (observe any well, decide any well) with a larger budget, instead of N isolated loops. | gaps 1+5 | Orchestrator change only. |
| G7 | **Measure commitment explicitly**: `evidence_efficiency = committed_choices / evidence_calls` in the leaderboard, so the gpt-5/opus profile is a visible score, not a hidden pathology. | gap 6 | Measurement, not nudge. |

Suggested order: G1 (cheap, biggest) → G7 (free) → G2 → G5 → G6 → G3 (careful, leak-audited)
→ G4 (process change).

## Honest expectation

G1+G2+G5+G6 should move capable models substantially on zone and consistency (the summit's
zone came FROM the field view). G3 is the decisive one for priors and the most delicate to do
honestly. Even with everything, gap 6 (commitment) is the model's own — the system's job is to
make it measurable and to stop hiding it, which after G7 it will be.
