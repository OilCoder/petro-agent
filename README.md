# petro-agent

**The LLM decides. The engine computes. Nobody lies.**

An autonomous multi-agent system that turns raw well logs (LAS) into complete petrophysical
reports — Vsh, porosity, saturation, net pay, uncertainty — **with no human intervention in
the process**. Every number comes from deterministic, golden-tested code; the language model
only chooses methods, intervals and analyses, and writes prose. When the result isn't
credible, the report says so on its front page.

📊 **Full report & interactive site:** <https://oilcoder.github.io/petro-agent/>

## Highlights

- **0** numbers written by the LLM — a claim verifier ties every figure in the prose to a
  per-well JSON ledger, and rejects the rest (it happened live).
- **198** Kansas wells (Schaben field — chosen *because* it deceives: two thirds of the
  column reads like spectacular porosity and is shallow sponge; you can only pass by
  analyzing, not by computing).
- Engine validated against VOLVE's public interpretation (North Sea, untuned):
  **r = 0.87–0.96**; P10–P90 bands honestly recalibrated from overconfident (1.8–35%
  coverage) to calibrated (88–98%).
- Eight agent versions measured against a declared-contaminated expert baseline — the best
  final agent (claude-opus-4.8 + thinking) chose **4/4 zones 100% inside producing rock**;
  the yardstick itself was stress-tested with three deterministic cycles.
- Total measured cost of the whole experimental arc: **~$50**.

## The site

| Page | What it tells |
|---|---|
| [Home](https://oilcoder.github.io/petro-agent/) | The problem, the invariant, methodology, results, verdict |
| [Petrophysical engineer](https://oilcoder.github.io/petro-agent/petrolero.html) | Can an AI read the formation? The rock-focused verdict |
| [Software engineer](https://oilcoder.github.io/petro-agent/ingenieria.html) | Architecture, the experimental lever phases, costs, transferable lessons |
| [Journal](https://oilcoder.github.io/petro-agent/proceso.html) | The evolution, chapter by chapter: problem → decision → result |
| [Well catalog](https://oilcoder.github.io/petro-agent/reports/pozos.html) | 71 per-well reports + every final agent's wells, unabridged |

## Stack

Python · lasio · numpy · LangGraph (deterministic state machine — not an LLM) · matplotlib ·
pytest golden tests · local Ollama runtime, with cloud frontier models used only as a
measuring instrument.

---

### Español

Sistema multi-agente autónomo que convierte registros de pozo (LAS) en informes petrofísicos
completos **sin intervención humana en el proceso**. Cada número sale de código determinista
cubierto por golden tests; el modelo solo elige métodos, intervalos y análisis, y redacta.
El informe completo y el sitio interactivo (bilingüe) están en
**<https://oilcoder.github.io/petro-agent/>** — incluye el veredicto por modelo, los 71
informes de pozo íntegros, el diario de desarrollo capítulo a capítulo y un *mea culpa*
honesto de lo que faltó.

**Autor:** [OilCoder](https://oilcoder.github.io/)
