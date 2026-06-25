# Blueprint Manifest

Kind: hybrid (data-pipeline + ml-research)
Started: 2026-06-24

## Documents
- [x] 00_charter.md (approved 2026-06-24)
- [x] 01_context_interfaces.md (approved 2026-06-24)
- [x] 02_problem_data.md (approved 2026-06-24)
- [x] 03_source_sink_contracts.md (approved 2026-06-24)
- [x] 04_pipeline_architecture.md (approved 2026-06-24)
- [x] 05_engine_and_validation.md (approved 2026-06-24)
- [x] 06_evaluation_protocol.md (approved 2026-06-24)
- [x] 07_site_style_guide.md (approved 2026-06-24)
- [x] 09_implementation_plan.md (approved 2026-06-24)

## Decisions
- 2026-06-24: kind = hybrid (data-pipeline + ml-research). The system is both a
  LAS→report pipeline (QC gate, deterministic state machine, validators) and a
  research/evaluation effort (vetted methods, uncertainty, calibrated confidence,
  VOLVE regression). Merged both packs, renumbered 02–06, dropped ml-research's
  method_experiments (no model training / ablations — equations are fixed).
- 2026-06-24: added 07_site_style_guide (GitHub Pages landing in docs/) — the base
  reserves docs/ but prescribes no visual style; needed as a drift anchor for the page.
- 2026-06-24: report-output format covered inside 03_source_sink_contracts (output
  schema) + 06_evaluation_protocol (tone-by-confidence gating); no dedicated doc.
- 2026-06-24: planning/diseno/ (Obsidian vault notes) kept gitignored; the blueprinter
  reads them as context, the versioned design lives here in planning/blueprint/.
- 2026-06-24: Topic 1 v1-path widening — the deterministic cutoff/aggregation tier
  (`net_sand`/`net_reservoir`/`hcpv`/`bvw`) is added to the v1 quantitative path as
  frozen, golden-tested non-equation functions over the three core outputs (Vsh/PHIE/Sw).
  Widens Charter Success criterion 1; the invariant holds (the LLM never computes or
  authors math). Logged amendment, not a silent widening (see 05 lines 33-39).
- 2026-06-24: decision (c) CLOSED = Monte Carlo for uncertainty propagation.
- 2026-06-24: decision (d) = no RAG for v1; KEEP a static curated citations table
  (each parameter -> exactly one source), wired to the JSON ledger and golden-tested.
- 2026-06-24: decision (a) provisional = second model family (adversarial reviewer,
  Fase 6) pending the user's unstated requirement; revisit before Phase 6.
- 2026-06-25: decision (a) CLOSED = the adversarial reviewer uses a SECOND MODEL FAMILY
  (Llama3.1:8b), different family from the Qwen3:30b-a3b writer, for cross-family
  decorrelation — not a role-only prompt. User-confirmed.
- 2026-06-25: field = Schaben confirmed for v1, design kept FIELD-AGNOSTIC (PROV tag +
  config library + mnemonic aliases) so other fields can be added later. Real data
  inventory (KGS geodatabase + LAS index, KID=KGS_ID join): of 353 Schaben wells, 161
  have LAS; combining runs per well → 28 full density-neutron (modern 2009-2024,
  the v1 working set), 61 single-porosity, 72 GR/RT-only. Chosen over higher-volume
  fields (Bemis-Shutts/Trapp/Chase-Silica) for validatability vs KGS OFR2000-79 + core.
- 2026-06-25: decision (b) RESOLVED = SOFT abstention, not hard refusal. When no
  high-leverage parameter is core/offset-calibrated, the run does NOT hard-refuse to
  emit; it emits with an explicit ABSTENTION banner + tier downgrade (gating sets
  `abstain`/`abstain_reasons`; `src/orchestrator/stages.py`, `gating/rules.py`). Recorded
  late — the PLAN had marked it `[x]` before it was actually logged here (audit BC-05, D8).
- 2026-06-25: decision (e) DEFERRED = the ECE threshold for statistical confidence cannot
  be set: VOLVE was never obtained, so no ECE was measured (Charter criterion 4 amended to
  infra-ready/unmeasured; Phase 8 BLOCKED). Set the threshold once VOLVE is available
  (audit BC-01/BC-05, D8).
