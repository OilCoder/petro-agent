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

## DV2-4 (2026-06-26) — litho_mn diferido en V2-A
**Decisión:** no construí `litho_mn` (M-N crossplot) en V2-A pese a estar en el catálogo de `02`.
**Por qué:** `litho_nd_crossplot` (v1) ya cubre litología; M-N necesita DT y aporta poco sobre N-D
para el screening; lo difiero para mantener V2-A enfocado en dar choice real donde más importa (Sw
shaly-sand, que es el caso que dispara las objeciones v1). No está en METHOD_REGISTRY → no se ofrece.
Coherente con la política de "diferidos fuera del registry" (DV2-2). Reevaluable si se quiere M-N.

## DV2-5 (2026-06-26) — Fase V2-A COMPLETA (coherencia plan↔código OK)
**Resultado:** librería ampliada (vsh_linear, sw_simandoux, sw_indonesia, phi_sonic_wyllie/rhg) +
`registry.py` (METHOD_REGISTRY, available_methods, ELECTRICAL_PRESETS, CUTOFF_PRESETS), todo
golden-tested. 158 tests verdes, ruff+mypy limpios. Coherencia con `02` verificada (única deriva:
litho_mn diferido, DV2-4). Done-when de V2-A cumplido (≥2 métodos/propiedad + available_methods).

## DV2-6 (2026-06-26) — Fase V2-B COMPLETA (EDA + grafo de metodología)
**Resultado:** `src/eda/explore.py` (curve_inventory, depth_coverage, histogram_stats,
crossplot_density_neutron, low_resistivity_scan, gr_baseline_check, badhole_summary — read-only,
dicts serializables). `src/agents/methodology_graph.py` (GraphNode + MethodologyGraph con
add/to_json/to_mermaid/validate). `validate()` es gate determinista: acíclico, deps existen, claves
de ledger resuelven, y **rechaza literales decimales en prosa de nodos decision/observation** (el LLM
referencia claves, no embebe números) — el guard del invariante. 173 tests verdes. Coherencia con
specs 01/03 verificada.

## DV2-7 (2026-06-26) — Fase V2-C COMPLETA (dispatcher + guardrails, sin LLM)
**Resultado:** `src/agents/tool_dispatch.py` (validate_plan contra whitelist `METHOD_REGISTRY` +
EDA tools; dispatch ejecuta la fn determinista, escribe `ledger['tool_results'][key]` con
result_hash, añade nodo tool_call al grafo). `verify_keyed` en claim_verifier (tolerancia 0.5%,
atrapa números que derivan de su result de tool). `cross_tool_consistency` en validators/physical
(MECHANICAL si un mean_sw de tool contradice el avg_sw del núcleo). 183 tests verdes, todo sin modelo.
**Scope:** el dispatch ejecuta métodos Sw + tools EDA como camino demostrado; las otras familias de
método (Vsh, porosidad, litología) se cablean idénticamente — pendiente mecánico para V2-D/E, no
bloqueante. Done-when de V2-C cumplido (plan fabricado valida/ejecuta/escribe; keyed flaggea 1.9%-off;
consistencia levanta MECHANICAL). Coherencia con spec 09 V2-C verificada.

## DV2-8 (2026-06-26) — Fase V2-D COMPLETA (composer plan-driven, sin tocar v1)
**Decisión clave:** NO refactoricé `report_template.py` in-place (v1 congelado); creé
`src/agents/report_compose.py` que REUTILIZA las funciones de sección de v1 (number-stripped) y
re-numera por orden de plan. **Por qué:** evita romper los tests de v1 y mantiene v1 intacto como
baseline; el "byte-identical regression" del spec se sustituye por "el composer guiado incluye todas
las secciones obligatorias" (testeado). Implementa: SECTION_CATALOG (oblig./opcional cerrado), 2 modos
(guiado gates obligatorios + ABSTENTION_SAFE; libre advisory + sección de grafo obligatoria),
heuristic_section_plan (determinista, stand-in del LLM), graph.validate() como gate MECHANICAL
(bloquea guiado, advierte libre). 199 tests verdes. Coherencia con spec 09 V2-D verificada (deriva:
composer separado, documentada arriba). El modo lo fija el invocador (param), nunca el LLM.

## DV2-9 (2026-06-26) — Fase V2-E COMPLETA (analista LLM + fallback señalizado)
**Resultado:** `src/agents/analyst.py`: build_eda_digest (pre-digest compacto), run_analyst con
cascada qwen3→llama3.1→heurística determinista, SIEMPRE señalizada en `ledger.run.analyst`
(model_used, empty_returns, fell_back_to_deterministic). El LLM emite SOLO el plan (optional_sections
+ tool_calls + rationale, sin números); el dispatcher ejecuta y escribe número+hash; el grafo se
persiste en `ledger.run.methodology_graph`. Testeado con fake chats (Tier 1, sin Ollama): plan válido,
fallback por vacío, fallback determinista por todo-falla, rechazo de tool fuera de whitelist. 205 verdes.
**Decisión (max_steps):** el analista hace UN turno DECIDE por modelo (1 inferencia), dentro del
max_steps=2 del plan; la terminación la impone el código (loop de cascada acotado), no el LLM —
cumple el invariante "orquestador determinista dueño de la terminación". La cascada real con Ollama
se ejercita al generar los 2 informes. Coherencia con spec 09 V2-E verificada.

## DV2-10 (2026-06-26) — Fase V2-F COMPLETA (evaluación por modelo)
**Resultado:** `src/evaluation/report_score.py` (objective_score determinista: exploration_coverage,
methods_selected, optional_sections, reasoning_depth, decisions_justified, honesty_ok, invariant_clean
— claves canónicas de spec 04; honesty_ok se computa en AMBOS modos: False si un núcleo que se
abstiene se rodea de secciones confiadas). `score_report` same-model en reviewer.py (advisory, scores
1-5 = metadata del modelo, fuera del claim_verifier; default mid en output ilegible, no premia al que
no se autoevalúa). `src/evaluation/leaderboard.py` (objetivo y cualitativo en columnas SEPARADAS, sin
composite opaco; ranking por honesty→decisions_justified→coverage). Mejoré el analista para añadir un
nodo de observación por hallazgo EDA (hace medible la cobertura). 213 verdes. Coherencia con spec 04 OK.
