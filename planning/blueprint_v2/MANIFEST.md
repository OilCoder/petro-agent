# Blueprint v2 Manifest — petro-agent sandbox

Kind: hybrid (ml-research + data-pipeline), v2 reframe of a frozen v1.
Started: 2026-06-26

## Contexto
v1 (pipeline determinista honesto, 143 tests verdes) está **congelado** como baseline comparativa.
v2 reorienta el proyecto a un **sandbox de analista**: el agente analiza, decide y compone el informe
con libertad, seleccionando de una librería de fórmulas vetada. Origen: análisis del usuario 2026-06-26
sobre `planning/VISION_AGENTE_ANALISTA.md`.

## Documents
- [x] 00_charter.md (goal · 2 modos · invariante v2 · success criteria · non-goals · invariants) — drafted 2026-06-26
- [x] 01_sandbox_architecture.md (capas · librería · loop del agente · grafo de metodología · gates por modo · eval) — drafted 2026-06-26
- [x] 09_implementation_plan.md (fases V2-A..G, de v1 congelado al sandbox) — drafted 2026-06-26
- [x] 02_formula_library.md (catálogo de métodos vetados por propiedad + registry + firmas) — drafted 2026-06-26
- [x] 03_methodology_graph.md (schema, persistencia, render, métricas comparativas) — drafted 2026-06-26
- [x] 04_evaluation_per_model.md (reviewer same-model + score objetivo/cualitativo + leaderboard) — drafted 2026-06-26

## Decisions (usuario, 2026-06-26)
- 2026-06-26: **Invariante v2** = librería vetada; el agente elige/parametriza pero NO escribe matemática
  en runtime. "Cada número de código probado" sobrevive; la inteligencia está en la selección/composición.
- 2026-06-26: **Gates** = obligatorios en modo guiado, advisory en modo libre (producción vs experimentación).
- 2026-06-26: **Estrategia doc** = congelar v1 como baseline, arrancar blueprint v2 separado (no reescribir v1).
- 2026-06-26: **Reviewer** = del MISMO modelo que el generador (medición por modelo), no de otra familia (cambia
  el propósito de decorrelación a scoring/comparación de modelos).
- 2026-06-26: **Grafo de metodología** = artefacto nuevo obligatorio; la cadena de pensamiento del agente,
  auditable y comparable entre modelos.
- 2026-06-26: **Dos modos conviven** = guiado (pre-forma dummy como base) + libre (el agente decide el informe).
