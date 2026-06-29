# Complete Petrophysical Report — Chapter Spec (v2 target)

Listing only: chapter/unit names and what each must contain. No explanations.
Scope: per-well report (ch. 0–17, 19–20) + a per-field chapter (ch. 18).

## 0. Cover / metadata
- Well UWI, field, operator, country/basin
- Log date, service company, run number
- Engine + library versions, config hash (SHA-256), git SHA
- Model + model_digest, generation mode (guided/free)
- "No human in the per-report loop" statement

## 1. Executive summary
- Headline rock story (Vsh / PHIE / Sw)
- Net pay as P10/P50/P90 range
- Confidence tier (FIRM / QUALIFIED / BRACKETED)
- Abstention banner when the run did not converge
- Dominant uncertainty driver + single highest-leverage next action

## 2. Well & data inventory
- Curve list (raw mnemonic → canonical) with units
- Depth interval, sampling step, null value
- Missing / aliased curves
- Fallbacks taken (with reason)

## 3. Log quality control (QC)
- Bad-hole / washout summary (caliper vs bit)
- Spike removal, hard-range masks, range warnings (counts)
- Unit conversions applied (counts)
- GR baseline check
- Per-curve histogram stats
- Curves degraded / excluded with reason

## 4. Environmental corrections
- Corrections applied (borehole, mud, temperature) + source
- Corrections NOT applied (explicit) + impact note

## 5. Lithology & mineralogy
- Density-neutron crossplot nearest-lithology call
- Matrix assumption (rho_ma) + source
- Mineral / gas-crossover flags when detected

## 6. Shale volume (Vsh)
- Method selected (Larionov old / tertiary / linear) + rationale
- GR endpoints (gr_min / gr_max) + provenance
- Vsh summary stats

## 7. Porosity
- Method(s): density-neutron; sonic (Wyllie / RHG) when DT present
- Fluid / matrix parameters + provenance, PHIE cap
- Total vs effective porosity (shale-corrected)
- Summary stats

## 8. Water saturation
- Model(s): Archie / Simandoux / Indonesia + selection rationale
- a, m, n, Rw, Rsh + provenance (data-driven vs default)
- Sw summary stats
- Pickett-plot consistency note

## 9. Permeability (when estimable)
- Method (e.g. PHIE-based transform) + caveat
- Explicit "not estimated" + reason when no calibration

## 10. Cutoffs & pay criteria
- Vsh / PHIE / Sw cutoffs + provenance
- Net sand → net reservoir → net pay definition chain

## 11. Net pay & zonation
- Net pay P10/P50/P90, NTG, gross interval
- Per-zone table (top / base / net pay / avg PHIE / avg Sw / avg Vsh)
- Merge tolerance; thickest-N shown, full set in ledger
- Per-zone net pay (never a stacked total)

## 12. Uncertainty & sensitivity
- Monte Carlo P10/P50/P90 (realizations, seed)
- One-at-a-time parameter swing table
- Dominant uncertainty driver
- "Not computed" path when MC unavailable

## 13. Figures & cross-plots
- Composite log, Pickett plot, density-neutron crossplot
- Note: figures are deterministic renderings of computed numbers (not agent-interpreted)

## 14. Methodology (decision graph)
- Observation → decision → tool_call → section DAG (mermaid)
- Tool calls with args + result hashes
- Numeric-literal-free decision prose
- Fallback cascade record (model_used, empty_returns, fell_back)

## 15. Parameters & provenance
- Every parameter: value, unit, provenance tag, frozen citation
- FIRM / QUALIFIED / BRACKETED legend

## 16. Validator objections & interpretation QC
- Bounds, Vsh-PHIE anticorrelation, rt-sw consistency, cross-tool consistency
- Claim verifier result (keyed numbers + tone): PASS / FLAGS — listed, not hidden
- Tools selected but not executed (signaled)

## 17. Comparison / benchmark (when reference exists)
- Vs offset wells or accepted interpretation (e.g. VOLVE)
- Per-model leaderboard: objective score vs qualitative, ranked by objective anchor

## 18. Field chapter (multi-well rollup)
- Per-well inventory table (status, tier, net pay P50, NTG, objections)
- Cross-well statistics (mean / median / range) — never summed thickness
- Field net-pay figure
- Best reservoir quality / best data quality wells
- Excluded wells with reason; N_loaded / N_excluded

## 19. Conclusions & recommendations
- What is defensible vs bracketed
- Highest-leverage data acquisition to reduce the dominant uncertainty

## 20. Appendices
- Ledger excerpt (traceability)
- Completeness gate checklist
- Glossary of symbols / terms
- Frozen references / citations
- Excluded files / runs
