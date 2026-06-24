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
