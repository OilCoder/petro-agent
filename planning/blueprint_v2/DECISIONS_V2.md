# DECISIONS v2 — registro de decisiones del run autónomo

Log de TODAS las decisiones tomadas durante el build autónomo de v2, mientras el usuario está
ausente y yo (senior a cargo) decido sin consultar. Para revisión a su regreso. Decisiones de
diseño previas confirmadas por el usuario están en `MANIFEST.md`.

---

## DV2-0 (2026-06-26) — Modelos para los 2 informes
**Decisión:** generar los 2 informes finales con **qwen3:30b-a3b** y **llama3.1:8b** (los dos ya
integrados). **Por qué:** son los únicos modelos locales del proyecto; usar ambos materializa el
objetivo de v2 (scoring por modelo / comparación) y reaprovecha la cascada de fallback ya probada.
qwen3 es el más capaz (mejor analista esperado); llama3.1 es el fiable bajo el techo de 16GB. El
contraste entre sus grafos de metodología es justamente el experimento que v2 quiere medir.

## DV2-1 (2026-06-26) — Alcance de la librería de fórmulas (spec 02)
**Decisión:** ver `02_formula_library.md`. Resumen: ≥2 métodos vetados por propiedad, priorizando
los que el dato Schaben (carbonato, curvas GR/RHOB/NPHI/RT, a veces DT/PEF) permite ejercer, para
que la SELECCIÓN del agente sea una decisión real y no teórica.

## DV2-2 (2026-06-26) — Pasada de coherencia del blueprint v2 (2 ciclos)
**Decisión:** corrí 2 ciclos de coherencia orquestados (run wf_fc79fe6d-18c) sobre los 6 docs v2.
Resultado: 31 inconsistencias (1 crítica, 6 high, 17 medium, 7 low). **Apliqué** la crítica, las 6
high y los mediums materiales; los lows se folded o quedan capturados. Cambios clave:
- Las objeciones del reviewer same-model son **advisory** (no bloquean gates); solo MECHANICAL del
  dispatcher/validate bloquean en guiado (era contradicción crítica entre 04 y 00/01).
- Cutoffs/params eléctricos (a,m,n,Rw,Rsh) desde **presets vetados por ID o tool (`rw_pickett`)**,
  nunca del LLM (cierra una fuga del invariante en 02).
- Esquema canónico del grafo unificado entre 01 y 03 (payload anidado, `result_ledger_key`,
  `result_hash`, `model_digest`); ejemplo usa `sw_simandoux` (método real de 02), no Pickett.
- `validate()` del grafo rechaza literales numéricos sueltos en nodos decision/observation (MECHANICAL).
- Métricas del grafo (03) adoptan las claves canónicas de `objective_score()` (04).
- El **modo lo fija el invocador**, nunca el LLM (elegir libre = saltarse QC). Metodología obligatoria
  en modo libre. `max_steps`=2, pre-digest ≤~800 tokens, recompute-libre vía tool (no matemática del LLM).
**Por qué:** el usuario insistió en un blueprint sin contradicciones como ancla del code-gen; estas
fugas habrían propagado bugs al código. La pasada las cerró antes de escribir una línea.

## DV2-3 (2026-06-26) — Proceso: coherencia plan↔código por fase (recomendación del usuario)
**Decisión (adoptada del usuario):** al cerrar CADA fase v2, antes del checkpoint, correr un ciclo de
coherencia entre lo planeado (blueprint v2) y lo programado (código), para atrapar derivas respecto al
plan. Y **checkpoint obligatorio al completar cada fase**. Lo incorporo al protocolo del run autónomo.
