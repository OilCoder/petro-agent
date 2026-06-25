# Unification — Topics & Open Questions Resolution

## Method

This document consolidates the 11 open topics gathered from the user and the ~24
open questions scattered across the blueprint suite (`planning/blueprint/00–09`)
into one resolution record. It was produced by (1) web-backed research on the four
investigable topics (report anatomy, KGS/Schaben dataset, LLM serving, RAG), (2)
reading every blueprint doc's `## Open questions` section plus the Spanish design
notes in `planning/diseno/` (the original intent and the non-negotiable invariant),
and (3) synthesising both against the project invariant: **every number comes from
tested deterministic code; the LLM only orchestrates, selects, and redacts — it
never computes and never authors math at runtime; the orchestrator is a
deterministic LangGraph state machine; everything is traceable through the JSON
ledger.** Where a question cannot be settled without inspecting real LAS/VOLVE
files, it is marked NEEDS-HANDSON-DATA; where the decision is the user's alone, it
is marked NEEDS-USER-INPUT.

---

## User decisions (applied 2026-06-24)

The user reviewed this document and decided:

- **Topic 3 — scope = WHOLE FIELD (field-scale)**, not single-well. v1 covers the full
  Schaben field: per-well results PLUS field rollup (aggregate net pay, zone correlation,
  field net-pay/quality map). This enlarges scope (multi-well aggregation + maps across
  `03`/`04`/`06`) and strengthens the case for vLLM at larger batch — though Ollama still
  fits v1 on 16 GB (Topic 10). The Topic 3 resolution below is updated; the single-well
  wording is superseded.
- **Topic 8 — no RAG** (confirmed). Keep only the lightweight static **citations table**
  (each parameter → exactly one source); this is NOT paper curation / not RAG. (User may
  still choose to drop even the table.)
- **All other topics — proceed with the recommendation** (own engine, cross-family Llama
  critic, Monte Carlo, Ollama v1, raw-data QC, style-guide split). Decision (a) = second
  model family is taken as final; (b) hard abstention stays deferred to Phase 7.

---

## Topic resolutions (1–11)

### Topic 1 — Real report anatomy

**Decision/Recommendation.** Ship the STANDARD core path only for v1: Vsh
(Larionov old-rocks) → PHIE (density-neutron) → Sw (Archie) → deterministic cutoffs
→ **net sand / net reservoir / net pay** (the three-tier hierarchy, made explicit)
→ NTG → by-zone summary table (net pay, NTG, avg PHIE, avg Sw, avg Vsh) **plus
HCPV / bulk-volume-hydrocarbon per zone**. Adopt the 10-section canonical narrative
skeleton (executive summary; objectives & scope; well & log inventory; data QC;
methodology; parameters & provenance; zonation; results; uncertainty & limitations;
conclusions). Required v1 figures: the composite **triple-combo interpretation
plot** with a net-pay flag track, and one **Pickett plot** (Sw/Rw/m QC, a direct
Archie transform) in addition to the already-specified neutron-density cross-plot.
Defer permeability, shaly-sand Sw models (Waxman-Smits/Dual-Water/Simandoux),
capillary-pressure/saturation-height, fluid-contact picking, multi-mineral solvers,
M-N cross-plot, and histograms/Buckles to a later phase.

**Rationale.** Industry consensus (SPE PetroWiki, SPWLA, Schlumberger) makes the
Vsh→porosity→Sw→cutoffs→net pay→by-zone chain the canonical output; the
credibility differentiator is **traceability of every parameter** and an honest
limitations section — which maps exactly onto the project invariant (engine
produces numbers and the by-zone table; LLM only redacts around ledger-traceable
evidence, never picks a cutoff without recording it). The current schema (`03`)
already has Vsh/PHIE/Sw P10/P90 per zone, cutoffs, net pay + NTG, confidence tiers,
a provenance appendix, and ND + M-N cross-plots. The gaps are: (a) net sand and net
reservoir are not surfaced as distinct tiers (only "net pay" + NTG); (b) no HCPV /
BVW output; (c) no composite triple-combo interpretation plot (only cross-plots);
(d) no Pickett plot (the single most common quick-look Sw/Rw QC, and a better v1
choice than the M-N plot, which needs DT/PEF reserved for Phase 3).

**Status.** RECOMMENDED.

**Conflict to flag — amends 05's "three functions = complete v1 path."** Blueprint
`05_engine_and_validation.md` lines 24–25 state: "The three functions below are the
complete quantitative path for v1. No other petrophysical equation is introduced
before the Phase 8 regression benchmark." Adding deterministic `net_sand` /
`net_reservoir` / `hcpv` / `bvw` **widens that v1 quantitative path** and conflicts
with that statement (and with the Charter Success criteria, which list
PHIE/Vsh/Sw/net-pay only). These are not free additions: each must be its own
frozen, golden-tested function (preserving the invariant — the LLM still never
computes). **This is a logged design amendment, stated openly, not a silent
widening.** Two ways to land it: (i) **amend 05** to read "the three *core* equations
(Vsh/PHIE/Sw) plus deterministic cutoff/aggregation functions (net-sand/net-reservoir/
net-pay/NTG/HCPV/BVW)," explicitly scoping aggregations as non-equation arithmetic
over the three core outputs; **or** (ii) **defer** net_sand/net_reservoir/hcpv/bvw to
a post-core phase and ship only net-pay + NTG in v1, keeping 05 verbatim. Recommended:
(i) — these are cutoff-driven aggregations, not new petrophysical equations, so they
sit naturally one tier above the three core functions; but the call is the user's
because it touches a Charter Success criterion.

**Blueprint impact.** `03_source_sink_contracts.md`: add `net_sand_m` and
`net_reservoir_m` to the zone block (three-tier hierarchy) and add `hcpv` / `bvw`
to the by-zone summary; add the composite triple-combo interpretation PNG and a
Pickett-plot PNG to the Output artifacts; the M-N deferral must also drop/optionalize
the `crossplot_mn.png` output and the M-N schema in `03`. **Deferring M-N is not a
`03`-only edit** — the M-N cross-plot is wired as a Phase-3 output across the suite,
so the deferral must propagate to: `04_pipeline_architecture.md` (lines ~161–164,
442 — the M-N validator check + PNG emission), `05_engine_and_validation.md`
(lines ~543–564 — the full M-N validator spec and its `mn_skipped_no_dt` degradation
path). **Note: `07_site_style_guide.md` needs no edit for the M-N deferral** — its
architecture diagram (the stage-flow string at line ~201, `load → qc_gate → compute →
validate → typify_objections → [correct loop]* → gating → zonate → write → claim_verify
→ emit`) names no cross-plot artifact at all, so there is nothing to "drop" there. The
M-N artifact lives in `03` Output-3 (the cross-plot PNG section, lines ~387–402) and the
`04`/`05` validator specs, not in the `07` diagram. `07` only references cross-plots
generically (line ~161, "cross-plot PNGs may be embedded as evidence"; the line ~230
traceability showcase) and that generic wording needs no M-N-specific change. Concretely:
the M-N branch is **already conditionally skipped when DT is absent** — `05` lines
543–546 specify "If DT is absent, the M-N check is skipped and a degradation entry is
logged (`validator_id: mn_skipped_no_dt`)" — so the **model-mismatch validator already
degrades gracefully without DT and does not strictly *require* M-N**. There is no hard
contradiction to reconcile here. The v1 change is therefore a **cleanup, not a
conflict resolution**: (i) drop/optionalize the `crossplot_mn.png` output, and (ii)
mark the M-N branch **deferred** so v1 relies on the neutron-density cross-plot (and
Pickett QC) only, with M-N gated behind the existing "DT present" condition (extend
it to DT/PEF) rather than emitted as a Phase-3 artifact. The existing `mn_skipped_no_dt`
skip path stays as the degradation record; deferral simply makes "no M-N artifact"
the v1 default instead of a per-well degradation.
`06_evaluation_protocol.md`: note net
sand/net reservoir and HCPV as additional comparable outputs (subject to VOLVE
cutoff comparability, Topic NEEDS-HANDSON). `05_engine_and_validation.md`: **first
amend the "three functions are the complete v1 path" statement per the conflict note
above (logged amendment or deferral)**, then — if amendment (i) is chosen — add
deterministic `net_sand` / `net_reservoir` / `hcpv` / `bvw` functions to the
golden-tested engine.

### Topic 2 — Dataset / field choice

**Decision/Recommendation.** Confirm **Schaben field (Mississippian, Ness County,
Kansas)** as the v1 development dataset; reserve VOLVE for the Phase 8 regression
benchmark (as the roadmap already says). Anchor on the type-log well **Schaben #4
(API 15-135-21452)** plus the **three cored wells**. Pull raw LAS from the KGS
Magellan portal (`https://www.kgs.ku.edu/Magellan/Logs/`), searchable by Ness
County / API / lease, or via the bulk `ks_las_files.zip`; join via the KGS KID
identifier. Build the engine to degrade gracefully to density-only or neutron-only
porosity (older wells may lack RHOB) and record the degradation in the ledger.

**Rationale.** Schaben is the strongest fit on **three confirmed axes**: Paleozoic
carbonate → Larionov old-rocks branch applies directly (explicitly not Tertiary);
free raw lasio-readable LAS; and the GR + resistivity + neutron quartet present
(density on a subset). These three alone justify Schaben over any other KGS field —
no core dependency is needed for the choice. KGS also published the full
Vsh/Pickett/Archie/net-pay workflow on this exact field (PfEFFER, Super-Pickett,
OFR2000-79), which is useful as a methodology cross-check, not as calibrated truth
for *our* wells.

**On core control — NEEDS-HANDSON-DATA, not settled fact.** Published KGS reports
mention Schaben core (cored wells, plug porosity in the ~4–26 % range,
permeability, and lithology-dependent Archie m around 1.97 intergranular /
2.2–2.5 vuggy). **This is a candidate calibration source, not a confirmed input to
this project.** It directly contradicts blueprint `02_problem_data.md` line 50 ("No
core data | Kansas/Schaben wells … carry no core measurements; all parameters …
come from regional defaults or offset calibration") and the confidence
architecture built on it (`02` lines 94–100 Kansas → `tier = bracketed`; Charter
Success criterion 3; `03` confidence tiers). **Resolution: keep blueprint 02 as the
governing assumption (Kansas uncalibrated → BRACKETED) until the published core is
verified downloadable and depth-registerable to our specific wells** (see Needs
hands-on data and the Foundation-gap proposal below). Only then does it become a
golden-test ground truth for PHIE/Sw and amend 02 — via a logged decision, never
silently.

> **Foundation-gap proposal (do not auto-apply).** *Where*: `02_problem_data.md`
> line 50 + lines 94–100, Charter Success criterion 3, `03` confidence tiers.
> *Gap*: blueprint asserts "no core data → all Kansas outputs BRACKETED," but KGS
> has published Schaben core that, if usable, would supply calibration ground truth
> and lift some Kansas outputs above BRACKETED. *Why it blocks*: the two cannot both
> stand — either Kansas stays uncalibrated (current design) or the confidence
> architecture must admit a calibrated Kansas path. *Options*: (1) **recommended** —
> treat the published core as NEEDS-HANDSON-DATA, keep BRACKETED until verified, then
> amend 02 by logged decision; (2) adopt the core now as authoritative and amend 02
> + the confidence architecture up front (faster, but commits before verification);
> (3) ignore the core entirely and stay uncalibrated for v1. *Decision needed*: may
> KGS-published Schaben core be treated as authoritative calibration once
> depth-registered, overriding blueprint 02's "no core data"? — user's call.

**Status.** RECOMMENDED on the three confirmed axes (file-level curve completeness
**and** core-data usability are both NEEDS-HANDSON-DATA; the blueprint-02 amendment
above is NEEDS-USER-INPUT).

**Blueprint impact.** `02_problem_data.md`: add the confirmed KGS Magellan access
URL, the KID join mechanism, and the anchor wells (Schaben #4 + 3 cored). Do **not**
yet rewrite line 50 / the BRACKETED confidence statement — that edit is gated on the
Foundation-gap decision above; record it as a pending logged decision, not an
applied change. `07_site_style_guide.md`: fill the "Kansas/Schaben public data
source link" open question with the Magellan URL.

### Topic 3 — Report scope: single-well vs whole-field

**Decision (USER = FIELD-SCALE).** v1 = **whole-field report** covering all wells in
the Schaben field: per-well computation (one LAS → one ledger entry set) PLUS a
**field-aggregation/rollup layer** — aggregate net pay / NTG / HCPV, a cross-well
**zone-correlation panel**, and a **field net-pay / quality map**. Wells are still
processed one-by-one by the deterministic engine; the invariant is unchanged. The
field report adds a deterministic rollup + a field-summary writer pass on top.

**Rationale.** Chosen by the user for a stronger portfolio showcase. The per-well
deterministic path (one LAS → one ledger → one report block) is unchanged and keeps
the invariant clean; field-scale adds multi-well aggregation, cross-well zonation
alignment, and a map — real added work, accepted consciously. See `planning/informe_preform.md`
for a dummy field-scale report mockup validating the content.

**Status.** RESOLVED (USER = field-scale).

**Blueprint impact (now non-trivial).** `03_source_sink_contracts.md`: add a
field-rollup output schema (aggregate net pay/NTG/HCPV + per-well summary table) and
the field net-pay/quality map + zone-correlation panel to the figure set.
`04_pipeline_architecture.md`: add a deterministic **field-aggregation stage** after
the per-well runs, plus a field-summary writer pass. `06_evaluation_protocol.md`:
VOLVE regression stays **per-well** (calibration is per-well); field metrics are
descriptive. `02_problem_data.md`: pull the full Schaben well set, not one well.
Topic 10: vLLM becomes a stronger Phase-8+ candidate for the multi-well batch, but
Ollama still fits v1 on 16 GB (sequential per-well prose).

### Topic 4 — Calculation engine: own vs external library

**Decision/Recommendation.** Keep the **own vetted petrophysics engine** (Larionov
→ Vsh, density-neutron → PHIE, Archie → Sw), frozen + versioned + golden-tested, on
top of lasio (I/O) and numpy (numerics). Do **not** adopt petropy/welly on the
quantitative path for v1.

**Rationale.** The invariant requires every number to come from tested
deterministic code whose equations are frozen and covered by golden tests (physical
bounds, monotonicity, dimensional checks, known analytic cases). An external lib is
acceptable *only* if version-pinned and wrapped in the same golden tests — at which
point, for three well-understood equations, the wrapper plus its golden suite is as
much work as owning the functions, while adding a dependency surface and a
provenance/version-pinning burden. Owning the engine is the project's core asset and
keeps the LLM-never-authors-math boundary crisp. (lasio/numpy stay, as they already
are I/O and numerics, not the petrophysics math.)

**Status.** RESOLVED (confirms current invariant).

**Blueprint impact.** None — reaffirms `05_engine_and_validation.md`. Optionally add
a one-line note that external petrophysics libs are out of scope unless
version-pinned and golden-test-wrapped.

### Topic 5 — Multi-model report generation

**Disambiguation first — "multi-model" does NOT mean a second parallel writer.** The
blueprint architecture has a **single writer node** at the write stage (`04` Stage 8
and the `04` node-map both list `write = Qwen3:30b-a3b` only; `03`'s `model_tags`
schema carries one `writer = qwen3:30b-a3b` slot), and it reserves **Llama3.1:8b
exclusively for the Phase-6 adversarial reviewer** (`04` Stage 9 / Topic 6). There
are therefore two distinct mechanisms that the original "generate the prose with ≥2
models" wording conflated:

- **(a) A genuine second *parallel* writer** — two models each emit a full draft and
  the drafts are compared. This is **out of scope for v1** and is *not* what is
  recommended here: it would require logged amendments to the **`04` node map** (a new
  write-stage path/node), the **`04` stage sequence** (`write` becomes a fan-out/compare
  step), and the **`03` `model_tags` schema** (a second writer slot) — none of which the
  current single-writer design has. Recommending it would silently widen the
  architecture, so it is explicitly deferred.
- **(b) One writer + one cross-family critic** — Qwen3:30b-a3b writes the single draft;
  Llama3.1:8b (the second family) reviews it adversarially at Phase 6. **This is what
  "multi-model" actually means in this project**, and it is the *same* mechanism as
  Topic 6 (adversarial reviewer, decision (a)).

**Decision/Recommendation.** Adopt **(b)**: keep the **single Qwen3:30b-a3b writer**
and obtain model diversity through the **Phase-6 cross-family adversarial reviewer
(Llama3.1:8b)** — i.e. reviewer decorrelation, not dual prose generation. The
diversity benefit (reduced correlated blind spots in prose, method/parameter-selection
rationale, and claim-honesty) comes from the critic comparing against Qwen's draft,
**never from comparing numbers**: every number comes from the deterministic engine, not
the LLM. Be precise about what this guarantees. The engine is **byte-deterministic given
its inputs — a fixed config plus a fixed set of parameter selections.** It is **not**
invariant to *which model* performs the selection: the compute agent's `correct` loop
(`04` Stage 6, an LLM node) **selects** revised parameters from the config library to
resolve correctable objections — exactly the "orchestrates, **selects**, and redacts"
clause of the invariant. Two different model families (or the same model under Topic 10's
best-effort, non-bit-exact seeding) can make different parameter selections in that loop,
yielding different — but each fully deterministic-given-the-selection — numbers. That
cross-model selection divergence is a **tracked, ledger-visible source of numeric
difference, not an invariant violation**: every selection and every degradation is
recorded, so the difference is auditable, not silent. Both
models fit the ~16 GB VRAM ceiling sequentially (Llama3.1:8b comfortably; Qwen3-30B-A3B
with IQ3/Q3 quant or partial CPU offload — see Topic 10), loaded/unloaded around the
write→review boundary. The actual decorrelation mechanism is therefore **already fully
specified by Topic 6** — this topic adds only the regression guarantee that the engine is
reproducible **for a fixed config and a fixed recorded set of parameter selections**,
regardless of which model produced that selection.

**Rationale.** Diversity reduces correlated blind spots in prose and
selection/justification, but the design notes are explicit that diversity *reduces*
correlation, it does not eliminate shared-training blind spots — **the real
guarantee comes from the deterministic validators, not from model diversity.** A
second *parallel writer* would buy little over the critic (the validators carry the
reliability weight) while widening the architecture; a cross-family *critic* delivers
the same decorrelation at the cost of a model already in the stack. So the recommended
multi-model footprint is the reviewer only; the numeric path stays
single-source-of-truth and the write stage stays single-writer.

**Status.** RECOMMENDED (interpretation (b) — reviewer decorrelation; a second
parallel writer is explicitly OUT OF SCOPE for v1).

**Blueprint impact.** No write-stage changes — the single-writer design in `04`
(node map + stage sequence) and the `03` `model_tags` schema stand unchanged; a
second parallel writer is **not** added (that would need the logged `04`/`03`
amendments described above and is deferred). `06_evaluation_protocol.md`: state that
cross-family comparison evaluates **prose/selection/honesty via the Phase-6
reviewer** (not via a parallel draft), and add the engine-reproducibility regression
check: **same LAS + same config + same recorded parameter selections → byte-identical
engine outputs** (the engine is deterministic given a fixed selection set, not invariant
to which model performs the selection). Cross-model divergence in the `correct` loop's
parameter selection is itself a **tracked, ledger-visible** source of numeric difference,
not a regression failure — the check compares outputs *holding the recorded selections
fixed*, and the ledger surfaces any selection divergence for audit (aligned with Topic
10's best-effort, non-bit-exact LLM reproducibility). The decorrelation mechanism itself
is recorded under Topic 6 / `04` Stage 9, not as a new write-stage path.

### Topic 6 — Adversarial reviewer (INCOMPLETE)

**Decision/Recommendation.** Resolve decision **(a) = use the second model family
(Llama3.1:8b)** as the adversarial reviewer, rather than a role-only adversarial
prompt on Qwen. It provides genuine cross-family decorrelation at acceptable
operational cost (the model is already in the stack for the fast path), and on
16 GB it coexists with the 30B model via sequential load/unload (Ollama keep_alive
eviction). The loop terminates on **"every remaining objection is irreducible,"**
not on "the critic has no objections" (the anti-Goodhart rule from the design
notes).

**Rationale.** Different model family → lower shared-prior risk than a role prompt
on the same weights; the design notes already prefer "another model family for the
critic, or at least an adversarial role." The deterministic validators carry most of
the reliability weight, so this is a marginal-but-positive decorrelation gain.

**Status.** RECOMMENDED for (a); but the user's sentence "...I need ___" was left
unfinished — the **specific unstated requirement for the adversarial reviewer is
still pending** → NEEDS-USER-INPUT.

**Blueprint impact.** `00_charter.md` / `09_implementation_plan.md` open question (a):
record the recommendation (second family) as provisional, pending the user's
unstated need. Do not mark (a) closed until the user completes the requirement.

### Topic 7 — Uncertainty propagation = Monte Carlo (RESOLVED)

**Decision/Recommendation.** **Monte Carlo** per-depth sampling (not analytic
ranges). Decision (c) is CLOSED by the user.

**Rationale & implications.** Monte Carlo produces true distributional outputs, so
P10/P50/P90 ledger fields are genuine percentiles (resolving the analytic-range
naming ambiguity in `03`). It enables the **reliability diagram / ECE** natively and
fits the dual procedural+statistical calibration the design calls for. Its compute
cost is **numpy/CPU**, not VRAM — so it does not compete with the LLM for the 16 GB
GPU budget and does not affect the Ollama serving decision (Topic 10).

**Status.** RESOLVED — decision (c) CLOSED.

**Blueprint impact.** `06_evaluation_protocol.md`: fix the uncertainty method to
Monte Carlo; the reliability-diagram binning can use finer bins (no longer limited
to the analytic three-tier shape, subject to VOLVE well count). `03`: confirm
`result_p10`/`result_p50`/`result_p90` are true percentiles (drop the
`lower_bound`/`upper_bound` fallback wording). `09`: mark (c) resolved = Monte Carlo.

### Topic 8 — RAG over petrophysics papers (decision (d))

**Decision/Recommendation.** **Do not use RAG for v1.** Ship a **static curated
citations table** keyed to each parameter (a, m, n, Rw, matrix density, Vsh method),
with columns: value/default, valid range, source (author, year), locator (page/DOI),
and applicability scope (formation age / lithology). Seed it with Archie 1942
(m, n = 2.0 defaults; note `a` originates from Winsauer 1952 / Wyllie & Gregory
1953, not Archie's original), Larionov 1969 **older-rocks** branch (correct for
Paleozoic Kansas), and the KGS/USGS Schaben values (Rw = 0.04, m = n = 2) plus the
regional Glick Field m range (2.10–2.75). Wire it into the JSON ledger so every
parameter selection emits a frozen citation; cover it with golden tests (every
parameter resolves to exactly one source; unknown parameter → hard fail, never a
guess).

**Rationale.** The justification surface is tiny, closed, and stable — a
lookup-table-shaped problem, not a search-shaped one, far below the ~50–100k-token
threshold where RAG buys anything. RAG's headline failure mode (hallucinated /
misattributed citations) directly attacks the system's traceability invariant; a
curated table gives deterministic, auditable provenance at a fraction of the cost
and preserves the LLM-only-renders-the-citation-it-is-handed rule.

**Status.** RECOMMENDED (resolves (d) = no RAG for v1). The user's extra unstated
questions on this topic → NEEDS-USER-INPUT.

**Blueprint impact.** `09` / `00` open question (d): record "no RAG for v1; curated
citations table instead." `09_implementation_plan.md` Phase 2: add a
citations-table-schema task and extend the Phase-2 Done-when to require it (it does
not exist in the current Phase 2). `05_engine_and_validation.md` / `03`: add the
citations table schema and its ledger join (config hash, version pinning) — this
extends 05's canonical config JSON structure (lines ~357–373), which currently has
only `version` / `regional_defaults` / `well_overrides`. `02`: note the Schaben
default parameter row set.

### Topic 9 — Raw-data premise (CONFIRMED)

**Decision/Recommendation.** Input is **raw KGS LAS with no manual preprocessing**;
the automated QC gate (Phase 1) handles depth match, unit conversion, washout/spike
masking, and logs every edit. Confirmed feasible.

**Rationale & implications.** Feasibility rests on loader/QC robustness: lasio reads
the CWLS ASCII natively; the `01`/`03` unit-variant contract already auto-converts
unambiguous NPHI (%→v/v) and RHOB (kg/m³→g/cc) and rejects ambiguous ranges, all
logged. The hard constraint is **minimum-curve intake**: the system cannot fabricate
missing curves — a well lacking the hard-required set (GR, RHOB, NPHI, RT) is
rejected or degraded (density-only / neutron-only PHIE) with the degradation logged
in the ledger; it is never imputed.

**Status.** CONFIRMED.

**Blueprint impact.** None structural — reaffirms `01`/`03`/`04` Stage 1 (load) and
Stage QC. Optionally add an explicit "no curve fabrication; reject or degrade +
log" line to the intake contract in `03`.

### Topic 10 — LLM serving framework: vLLM vs Ollama

**Decision/Recommendation.** **Ollama for v1.** Keep the engine behind a thin
interface so an Ollama→vLLM swap is a config change, not a rewrite. Reserve **vLLM
for a future Phase-8+ field-wide batch mode on a larger GPU (24 GB+/multi-GPU)**.

**Rationale.** On a ~16 GB GPU the gating constraint is *fitting* Qwen3-30B-A3B
(30.5B total params, all weights resident), not throughput. **Research-derived estimate
(pending hands-on verification):** at Q4_K_M the GGUF weights are ~16.8–18.6 GB, which
*on these numbers* would leave little or no usable KV-cache headroom — so the likely
path is IQ3/Q3 quant, KV-cache quantization, or partial CPU offload. **This is an
estimate, not a measured fact**: actual VRAM fit is NEEDS-HANDSON-DATA (see Status and
Needs-hands-on), and it must not be stated as "Q4 cannot fit on any backend" — only
hands-on measurement on the real 16 GB GPU can settle whether Q4_K_M fits. Whatever the
verdict, **only Ollama/llama.cpp degrade gracefully** (GGUF + CPU layer offload) if Q4
turns out not to fit; vLLM effectively requires the whole model in VRAM
(24 GB+/multi-GPU). For a single-user
*sequential* workload the throughput gap is small (~62 vs ~71 tok/s on
Llama-3.1-8B), so vLLM's continuous-batching advantage is irrelevant per report.
Ollama's native WSL install (no CUDA-kernel compilation) is far simpler.
Determinism is **not load-bearing**: the invariant keeps every number in
deterministic Python, so best-effort seed pinning (greedy decode, fixed seed/ctx,
pinned model+engine digests in the ledger) suffices; bit-exact LLM prose is not
required for correctness.

**Status.** RECOMMENDED (scope-dependent on Topic 3; actual VRAM fit is
NEEDS-HANDSON-DATA).

**Blueprint impact.** `04`/`05`: confirm Ollama as the v1 serving layer behind a
thin swappable interface; record the chosen quant (IQ3/Q3_K_M or Q4 + offload) and
quantized KV cache, and pin Ollama + model digests in the ledger. `05` open question
"Ollama seed determinism": resolve as best-effort (greedy + pinned seed/ctx/build,
record digests; not bit-exact).

**Conflict to flag — gated on hands-on quant verification (amends 00 Charter + 09 R3 if
the IQ3/Q3 finding holds).** The Charter constraint (`00` lines 144–145) gives "Q4_K_M
or equivalent … to fit within ~16 GB VRAM" as the example quant, and Risk R3 (`09` lines
488–490) assumes "Q4_K_M quantization for Qwen3:30b-a3b is expected to fit within 16 GB."
If hands-on measurement confirms Q4_K_M does **not** leave usable KV-cache headroom and
the verified quant is IQ3/Q3 + offload, both statements become inaccurate. **Treat this
exactly like the Topic 1 Charter conflict: a logged amendment, stated openly, not a
silent change** — amend the `00` example from "Q4_K_M … to fit" to the verified quant,
and update R3's "Q4_K_M expected to fit" assumption to match. Do **not** apply the
amendment until hands-on data confirms the fit (it is NEEDS-HANDSON-DATA today); record
it as a pending logged decision. Conversely, if Q4_K_M *does* fit on the real GPU, no
amendment is needed and the Charter/R3 example stands.

### Topic 11 — Site style guide as HTML vs doc

**Decision/Recommendation.** **Split it.** Keep a slim strategy doc
(`07_site_style_guide.md` reduced to messaging/positioning/audience/content rules)
and move the visuals into an actual HTML "living style guide" living under `docs/`.
Timing: a **style scaffold (tokens, fonts, color, type scale, component shells) can
be built now**; the **full site needs a demo and waits until post-Phase 5** (when
there is a rendered report/ledger to showcase).

**Rationale.** A prose doc cannot own visual truth; an HTML living style guide is
self-demonstrating and is the natural home for the design tokens, while the strategy
(what the site says and to whom) belongs in planning. This also matches the
docs-style rule's two-surface model (`docs/` = GitHub Pages, owns visuals;
`planning/`/`documentation/` own prose). Building only the scaffold now avoids
"coming soon" teaser content for unbuilt features.

**Status.** RECOMMENDED.

**Blueprint impact.** `07_site_style_guide.md`: trim to a strategy doc; add a
pointer to the future `docs/` HTML style guide. Defer the GIF/demo decision to
Phase 5 completion (matches its existing open question).

---

## Open questions resolution

### Canonical (a–e) — from `00_charter.md` / `09_implementation_plan.md`

- **(a) Adversarial reviewer — second family vs role-only prompt.** RECOMMEND
  second model family (Llama3.1:8b); record as provisional pending the user's
  unfinished requirement (Topic 6). Not closed.
- **(b) Hard abstention as a product decision.** DEFER to Phase 7 entry —
  genuine product call (refuse to emit when no high-leverage param is calibrated);
  engineering can implement either. NEEDS-USER-INPUT before gating rules finalize.
- **(c) Uncertainty propagation method.** **CLOSED → Monte Carlo** (Topic 7).
- **(d) RAG vs system-prompt knowledge.** RESOLVE → **no RAG for v1; curated
  citations table** wired to the ledger (Topic 8). Revisit only if a large
  unstructured regional corpus appears post-Phase 8.
- **(e) ECE numeric threshold.** DEFER to Phase 7 exit — cannot be set before the
  calibration infrastructure measures a provisional ECE on a non-benchmark VOLVE
  subset; log as a manifest decision; Phase 8 hard-blocked until recorded.

### Doc-specific open questions

- **01 — LAS unit variants at intake.** Already RESOLVED in `03` (auto-convert
  unambiguous, reject ambiguous, log as `unit_conversion`).
- **01 — VOLVE curve-name mapping.** RESOLVE location fixed
  (`src/params/mnemonic_aliases.json`); remaining Phase-8 work is adding confirmed
  VOLVE aliases. NEEDS-HANDSON-DATA (VOLVE headers).
- **01/02/03 — Config JSON schema version.** DEFER to Phase 2 (prerequisite for
  ledger writer); the citations-table schema (Topic 8) must join it. **Note: this is
  a new Phase-2 deliverable.** Blueprint `09_implementation_plan.md` Phase 2 (Done-when
  + task list) currently has no citations-table work, and the canonical config schema
  in `05` (lines ~357–373) has only `version` / `regional_defaults` / `well_overrides`
  keys. Adopting the curated table therefore requires **amending 09 Phase 2** (add a
  citations-table-schema task and extend its Done-when to cover it) **and amending the
  05 config JSON structure** (add the citations join + version pinning). Without those
  amendments the recommendation is unanchored to any phase's acceptance criterion —
  flag, do not assume it slots into Phase 2 unchanged.
- **02 — Kansas well count & curve availability.** NEEDS-HANDSON-DATA — pull
  Schaben LAS, confirm per-well GR/RHOB/NPHI/RT (+CALI); engine degrades gracefully.
- **02 — VOLVE accepted-interpretation format / well subset / Larionov variant /
  North Sea defaults.** DEFER to Phase 8; all NEEDS-HANDSON-DATA except "add a North
  Sea/Jurassic default parameter set in Phase 2" (action, not a question).
- **03 — P10/P90 representation.** RESOLVED by (c): Monte Carlo → true percentiles;
  drop the `lower_bound`/`upper_bound` fallback.
- **03/04 — `DID_NOT_CONVERGE` prose-emission policy.** DEFER to Phase 4 acceptance;
  tied to (b) abstention. NEEDS-USER-INPUT (product).
- **03 — Convergence threshold N (=3).** DEFER to Phase 4 integration testing on
  Kansas data; configurable.
- **03/05 — Cross-plot matrix density for limestone/dolomite (e.g. ρma dolomite
  2.87, φN −0.02).** NEEDS-HANDSON-DATA — must match the Kansas accepted
  interpretation reference to avoid false-positive model-mismatch flags.
- **04 — Cache implementation scope.** DEFER — JSON `(las_sha256, config_sha256)`
  lookup in `outputs/`; future optimisation, Phase 8 or later.
- **04 — `claim_verify` round-trip limit.** RESOLVE → keep 1 correction pass for v1,
  make it configurable (0/1/N) in Phase 5.
- **05 — RT masking in bad-hole zones.** RESOLVE → v1 does not mask RT (laterolog/
  induction read into the formation); add a configurable extreme-washout RT mask
  (CALI > bit_size + N) as a Phase-1 option only if data shows the need.
- **05/09(f) — GR min/max estimation strategy.** DEFER to Phase 2 → keep expert-set
  scalars by default; offer auto P5/P95 estimation tagged `provenance = default`
  (data-derived). NEEDS-HANDSON-DATA to choose per dataset.
- **05 — PHIE upper-bound for Kansas carbonates (phie_max 0.45).** NEEDS-HANDSON-DATA
  — raise the ceiling if vuggy/fractured intervals exist, to avoid false bound flags.
- **05 — Spike detection window / threshold (±10 samples, 5×IQR).** NEEDS-HANDSON-DATA
  — revisit on the first real Schaben LAS (sampling interval varies by vintage).
- **05 — Ollama seed determinism.** RESOLVE → best-effort (greedy + pinned
  seed/ctx/build/digests in ledger), not bit-exact; acceptable per the invariant
  (Topic 10).
- **06 — VOLVE well subset size.** NEEDS-HANDSON-DATA; if <3 wells carry complete
  reference curves, Phase 8 is blocked pending a foundation gap report.
- **06 — Reliability-diagram binning.** RESOLVE → with Monte Carlo (c), use finer
  equal-width bins where VOLVE well count permits; else fall back to three tiers.
- **06 — Net-pay cutoff comparability on VOLVE.** NEEDS-HANDSON-DATA — confirm
  Equinor cutoffs; if materially different, foundation gap report before Phase 8.
- **07 — Author contact / demo GIF timing / Kansas data URL / VOLVE attribution /
  fonts.** RESOLVE the data URL = KGS Magellan (Topic 2); DEFER GIF to Phase 5;
  contact/fonts/VOLVE-attribution are implementation-time cosmetic choices
  (NEEDS-USER-INPUT for contact preference).

---

## Blueprint updates needed

- [ ] `03_source_sink_contracts.md` — add `net_sand_m`, `net_reservoir_m`, and
  `hcpv`/`bvw` to the zone block / by-zone summary (Topic 1).
- [ ] `03_source_sink_contracts.md` — add composite triple-combo interpretation PNG
  and Pickett-plot PNG to Output artifacts; keep ND cross-plot, defer M-N — also
  drop/optionalize `crossplot_mn.png` and the M-N schema (Topic 1).
- [ ] `04_pipeline_architecture.md` — make the M-N validator check + PNG emission
  (lines ~161–164, 442) optional/deferred; the model-mismatch validator relies on the
  ND cross-plot for v1, M-N branch gated on DT/PEF presence (Topic 1).
- [ ] `05_engine_and_validation.md` — mark the M-N validator spec (lines ~543–564)
  deferred and drop/optionalize the `crossplot_mn.png` output; the existing
  `mn_skipped_no_dt` skip path already lets the model-mismatch validator degrade
  without M-N, so this is a cleanup (M-N defaults off in v1), not a contradiction
  fix (Topic 1).
- [ ] `07_site_style_guide.md` — **no M-N edit needed**: the architecture diagram (the
  stage-flow string at line ~201) names no cross-plot artifact, so there is nothing to
  drop there. The M-N artifact lives in `03` Output-3 (lines ~387–402) and the `04`/`05`
  validator specs; `07` only references cross-plots generically (line ~161, line ~230
  traceability showcase) and needs no M-N-specific change (Topic 1).
- [ ] `03_source_sink_contracts.md` — set P10/P50/P90 as true percentiles (Monte
  Carlo), drop `lower_bound`/`upper_bound` fallback wording (Topic 7).
- [ ] `03_source_sink_contracts.md` — add explicit "no curve fabrication: reject or
  degrade + log" to the intake contract (Topic 9).
- [ ] `05_engine_and_validation.md` — amend the "three functions are the complete v1
  path" statement (lines 24–25) before adding any new function: either scope
  net-sand/net-reservoir/HCPV/BVW as deterministic cutoff/aggregation functions (not
  new equations) via a logged amendment, or defer them and keep 05 verbatim
  (Topic 1). If amended, add golden-tested `net_sand`/`net_reservoir`/`hcpv`/`bvw`
  functions; add the curated citations-table schema + ledger join (Topics 1, 8).
- [ ] `05_engine_and_validation.md` — resolve RT-masking, GR min/max, Ollama-seed
  open questions per the resolutions above.
- [ ] `06_evaluation_protocol.md` — set uncertainty method = Monte Carlo; allow
  finer reliability-diagram bins; add cross-family prose/selection/honesty comparison
  **via the Phase-6 adversarial reviewer** (single writer + cross-family critic, not a
  parallel second writer) and the engine-reproducibility regression check — **same LAS +
  same config + same recorded parameter selections → byte-identical engine outputs**
  (deterministic given a fixed selection set, not invariant to which model selects;
  cross-model `correct`-loop selection divergence is a ledger-tracked numeric-difference
  source, not a failure) (Topics 5, 6, 7). No write-stage / `model_tags` change —
  single-writer design stands.
- [ ] `02_problem_data.md` — add KGS Magellan access URL, KID join, anchor wells
  (Schaben #4 + 3 cored), core calibration source, North Sea default param set
  reminder for Phase 2 (Topic 2).
- [ ] `00_charter.md` / `09_implementation_plan.md` — mark (c) CLOSED = Monte Carlo;
  record (d) = no RAG/curated table; record (a) provisional = second model family
  pending the user's requirement (Topics 6, 7, 8).
- [ ] `09_implementation_plan.md` — add a citations-table-schema task to Phase 2 and
  extend the Phase-2 Done-when to cover it; `05_engine_and_validation.md` — extend the
  config JSON structure (lines ~357–373) with the citations join + version pinning
  (Topic 8).
- [ ] `04_pipeline_architecture.md` — confirm Ollama as v1 serving behind a thin
  swappable interface; note vLLM as Phase-8+ batch path (Topic 10).
- [ ] `00_charter.md` (lines 144–145) / `09_implementation_plan.md` R3 (lines 488–490) —
  **pending hands-on quant verification**: if the IQ3/Q3 finding holds (Q4_K_M does not
  fit with usable KV-cache headroom on the real 16 GB GPU), log an amendment changing the
  Charter's "Q4_K_M … to fit" example and R3's "Q4_K_M expected to fit" assumption to the
  verified quant. Do not apply until hands-on data confirms; if Q4 fits, no change
  (Topic 10).
- [ ] `07_site_style_guide.md` — trim to a strategy doc; point to a future `docs/`
  HTML living style guide; fill the Kansas data URL (Topics 11, 2).

---

## Needs hands-on data confirmation

- Per-well Schaben curve completeness: do GR, RHOB, NPHI, RT (and CALI) co-exist on
  the same wells? Exact LAS mnemonics (GR vs SGR/CGR; RHOB vs DEN/RHOZ; NPHI vs
  NPOR/PHIN; ILD/LLD/RT; CALI), depth coverage/units, null gaps. (Topics 2, 9)
- KID→LAS retrieval pattern verified by an actual Magellan query. (Topic 2)
- Schaben core data in `core_analysis_wells.xlsx` downloadable and depth-registerable
  to the LAS; freeze Rw / a / m / n / matrix-density per lithology for golden tests
  (KGS Rw=0.04, m=n=2, core m 1.97–2.5 are **published starting points, not confirmed
  inputs** — until verified, blueprint 02's "no core data → BRACKETED" governs; see
  the Topic 2 Foundation-gap proposal). (Topics 2, 8)
- Formation tops / Mississippian unconformity per well to define analysis interval
  and net-pay zones. (Topics 1, 2)
- Cross-plot matrix density reference values matching the Kansas accepted
  interpretation (avoid model-mismatch false positives). (Topics 1, blueprint 03/05)
- PHIE ceiling, spike window/threshold, GR min/max strategy validated on the first
  real Schaben LAS. (blueprint 05)
- Actual VRAM footprint of Qwen3-30B-A3B on the real 16 GB GPU at Q4 vs IQ3/Q3 +
  quantized KV cache; per-report wall-clock; best-effort reproducibility verified by
  diffing two fixed-seed runs; confirm the exact Ollama quant artifact + pin digest;
  Llama3.1:8b co-residency / load-unload latency. (Topic 10)
- VOLVE: accepted-interpretation format, usable well subset (≥3 with complete
  reference curves), correct Larionov variant, North Sea defaults, cutoff
  comparability. (Topics 2, 5; blueprint 02/06)
- Larionov-1969 older-rocks coefficient/form pinned against a primary reference
  before it becomes a golden test. (Topic 8)

---

## Still needs user input

- **Topic 3 — single-well vs whole-field for v1.** I recommend single-well
  (batch-capable), but if the portfolio goal is a field-scale showcase that is a
  product decision only the user can make; it cascades into `03`/`04`/`06` and
  Topic 10 (vLLM).
- **Topic 2 — may KGS-published Schaben core override blueprint 02's "no core
  data"?** If the published core (Rw, m, n, matrix density) is verified
  depth-registerable to our wells, treating it as authoritative calibration would
  lift some Kansas outputs above BRACKETED and amend `02_problem_data.md` line 50 +
  the Charter confidence architecture. This is a blueprint-amendment decision, not a
  research finding — only the user can authorize overriding a design condition (see
  the Topic 2 Foundation-gap proposal). Default until then: keep BRACKETED.
- **Topic 6 — the adversarial reviewer's unstated requirement.** The user's
  sentence "...but I need ___" was left unfinished. The model-family recommendation
  (second family, Llama3.1:8b) is provisional until the user states the actual need.
- **Topic 8 — the user's extra (unstated) RAG questions.** The no-RAG/curated-table
  recommendation stands, but the user flagged additional questions here that were
  not provided.
- **(b) Hard abstention policy.** Refuse to emit a report when no high-leverage
  Archie parameter (a, m, n, Rw) is calibration-constrained? Product decision,
  required before Phase 7 gating rules are finalized; ties to the
  `DID_NOT_CONVERGE` prose-emission policy.
- **Cosmetic site choices.** Author contact (LinkedIn/mailto/none) and fonts
  (Google vs self-hosted) — user preference at build time (Topic 11).
