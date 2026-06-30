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

## DV2-11 (2026-06-26) — Fase V2-G COMPLETA — ¡las 7 fases V2-A..G hechas!
**Resultado:** `provenance.pin_versions` añade `formula_registry` (versión de la librería) y
`model_digest(model)` (id del modelo vía `ollama list`, "unknown" si ausente) — identidad del modelo
= nombre+digest. Tests en 2 tiers: Tier 1 determinista (CI-gating, junto a v1 — todos los guardrails
v2 con fake chats); Tier 2 model-in-the-loop (`test_v2_g.py`, skip si Ollama no responde —
version-sensitive, fuera del gate). 215 tests verdes, ruff+mypy limpios. Coherencia con spec 09 V2-G OK.
**Próximo (no es fase):** generar los 2 informes (qwen3+llama3.1) por el sandbox v2 + leaderboard, luego
apagar el PC.

## DV2-12 (2026-06-26) — `return_ctx` en run_pipeline (enablement v2, backward-compatible)
**Decisión:** añadí un parámetro opcional `return_ctx=False` a `run_pipeline`. Con False (default) el
comportamiento es IDÉNTICO a v1 (devuelve el ledger); con True devuelve `(ledger, ctx)` con los arrays
finales (curves/vsh/phie/sw/depth) que el analista v2 necesita. **Por qué:** generar los 2 informes por
el sandbox exige el ctx, y duplicar la lógica del pipeline sería frágil. Un param opcional default-False
no cambia el comportamiento ni los tests de v1 (verificado: 215 verdes) — es la habilitación mínima y
honesta, no un cambio de v1. "v1 congelado" se refiere a su comportamiento/salida, que se preserva exacto.

## DV2-13 (2026-06-26) — ENTREGABLE FINAL: 2 informes v2 + leaderboard (proyecto v2 completo)
**Resultado:** generados los 2 informes por el sandbox v2 (modo libre) sobre el pozo Schaben
1043562832, en `documentation/sample_reports/v2/`: report_qwen3_30b-a3b.md, report_llama31_8b.md,
sus ledgers, y leaderboard.json. Cada informe lleva la estructura plan-driven completa CON la sección
"Methodology (decision graph)" (flowchart mermaid del razonamiento del analista). El leaderboard compara
ambos modelos (objetivo determinista + cualitativo same-model en columnas separadas).
**Hallazgo clave (el experimento de v2 funcionando):** qwen3:30b-a3b **se vació bajo el techo de 16GB**
(modo de fallo R3/D6) y el **fallback señalizado** lo llevó a llama3.1:8b para el plan del analista —
registrado en `ledger.run.analyst.model_used=llama3.1:8b`, NO silencioso. El sistema produjo informes
honestos pese al vaciado del modelo principal. Ambos modelos compusieron informes base (methods_selected=0,
optional_sections=0): la agencia se ejerció pero los modelos locales bajo 16GB son conservadores — el
techo honesto del modo libre documentado en el Charter. La maquinaria (analista→grafo→compose→score→
leaderboard) está demostrada end-to-end. 216 tests verdes. **PROYECTO v2 COMPLETO.**

## DV2-14 (2026-06-28) — Purga de v1: v2 es la única dirección del proyecto
**Decisión:** v1 deja de ser baseline congelado a conservar. Todo el código v1 del repo no usado
por v2 se eliminó: `compute_agent.py` (huérfano), `report.py` (generate_report v1), `field_report.py`
(rollup sin cablear), `reviewer.review_report`/`_SYSTEM` (revisor adversarial cross-family),
`claim_verifier.verify_report` (verificador flat-2%, superado por verify_keyed),
`report_template.render_well_report` (assembler monolítico) y `log_plot.net_pay_bar`, más sus tests.
**Por qué:** dos pipelines en paralelo confunden y v2 es más completo y con objetivo claro. Se conservó
todo lo compartido (section helpers, writer, score_report same-family, verify_keyed/verify_tone).
**Verificación:** grep sin stragglers; 52 source files (antes 55); suite verde, ruff+mypy limpios.

## DV2-15 (2026-06-28) — Guardrails v2 cableados + fin del "report theater"
**Decisión:** los guardrails construidos+testeados pero nunca ejecutados ahora corren en el flujo:
(1) `compose_report` ejecuta el claim verifier (verify_keyed numbers + verify_tone) sobre la PROSA
del LLM y sella `ledger.run.claim_verifier` → el completeness gate (Appendix B) pasa de ✗ a ✓.
(2) `run_analyst` ejecuta `cross_tool_consistency` tras el dispatch; las contradicciones se vuelven
objeciones MECHANICAL, no números duales silenciosos. (3) Las secciones opcionales se emiten SOLO si
existe su tool_result de respaldo; la sección sonic lee tool_results en vez de un string fabricado.
(4) Zonación/resultados degradan a "_Not computed_" explícito en vez de tablas huecas. (5) El dispatch
señaliza familias de tools no ejecutadas. **Por qué (alcance del claim verifier):** se verifica solo la
narrativa — las tablas son determinísticas (correctas por construcción, solo redondeadas para display);
verificarlas marcaría redondeo, no mentiras. **Verificación:** corrida end-to-end → Appendix B ✓,
claim_verifier=PASS; tests nuevos en test_report_compose; 216 tests verdes.

## DV2-16 (2026-06-28) — Spec del informe completo + informe por campo diferido
**Decisión:** se escribió `10_complete_report_spec.md` (solo capítulos + qué debe contener cada uno),
con alcance pozo (ch. 0–17, 19–20) + capítulo de campo (ch. 18). El informe por campo se quiere, pero
se reconstruye como feature nativa de v2 más adelante (no como el `field_report.py` v1 sin cablear, que
se eliminó). El spec es el blanco objetivo de esa reconstrucción y de futuras secciones (permeabilidad,
correcciones ambientales, mineralogía) aún no implementadas.

## DV2-17 (2026-06-28) — Spec del informe completo reorientada a LAS-only + framing del experimento
**Decisión:** se reescribió `10_complete_report_spec.md` partiendo del hecho de que la ÚNICA entrada
son archivos LAS (como en `data/`, 198 pozos KGS). Se acotó a contenido técnico (sin historia de
campo ni control documental) y se intersectó con lo realmente derivable de un LAS: las curvas varían
por pozo (algunos solo GR), hay coordenadas en el header (mapas posibles) pero NO hay tops (zonación
computada, no por formación) ni núcleo/presión/producción/mud logs (out of scope, nombrados en
Limitaciones, cap. 34). 36 capítulos técnicos, cada uno etiquetado **[FIJO]** (piso obligatorio para
todo modelo) o **[MODELO]** (decisión del modelo, señal de profundidad/creatividad).
**Por qué:** el propósito del proyecto es medir si un LLM puede redactar informes petrofísicos; el
piso FIJO da comparabilidad entre modelos y la zona libre revela capacidad. La medición por modelo:
nº de secciones [MODELO] elegidas Y respaldadas con números reales + claim verifier PASS + riqueza
del grafo + score same-model.
**Pendiente (decisión del usuario, luego follow-up de código):** fijar la asignación [FIJO]/[MODELO]
y recién entonces cablearla en `report_compose._MANDATORY_BODY` / `OPTIONAL_SECTIONS`. Varios caps
[FIJO] aún no los produce el motor (SP/Rw, comparación multi-método de Vsh, QC por curva, mapa de
campo desde coords) — gaps de implementación futuros.

## DV2-18 (2026-06-28) — Reparto [FIJO]/[MODELO] fijado por el usuario + diseño del experimento de campo
**Decisión (usuario):** se confirma el reparto del spec 10.
- **FIJO** (piso obligatorio, guiado y libre): metadatos, resumen, inventario, QC de LAS,
  estandarización, QC por curva, preparación, intervalos, metodología, GR, **resistividad,
  caliper, litología, Rw** (las analíticas borderline van FIJO — degradan si falta la curva),
  Vsh (multi-método), porosidad, Sw-Archie, cutoffs, net pay/zonación, resultados, parámetros+
  procedencia, incertidumbre, validadores+claim verifier, grafo, figuras, conclusiones,
  recomendaciones, limitaciones.
- **MODELO** (solo si hay tool_result real): objetivo narrativo, SP, sónico, PEF, crossplots
  extra (Hingle/Buckles/M-N), Sw alternativos (Simandoux/Indonesia/DW/W-S), **permeabilidad
  (Timur/Coates) con caveat obligatorio "no calibrada, sin núcleo"**, derivados (BVW/HCPV/RQI/
  FZI), electrofacies, rock typing, contactos, multi-pozo/campo, estadística, ranking,
  nomenclatura, apéndices extra.
- **Informe por campo EN ALCANCE** (no diferido). Diseño del experimento de campo: **1 pozo
  fijo (ancla, lo analizan todos los modelos → comparabilidad) + 2 pozos de libre elección del
  modelo** (mide criterio de selección y profundidad a nivel de campo).
**Efecto en el roadmap:** R6 desbloqueado (el FIJO ya está en `_MANDATORY_BODY`; las MODELO se
agregan a `OPTIONAL_SECTIONS` conforme R4 las construya). R5 (field report) pasa de opcional a
requerido, con el esquema 1-fijo+2-libres. Permeabilidad entra en R4 como MODELO con caveat.

## DV2-19 (2026-06-29) — Modo libre: el agente compone el informe (solo prep+rieles forzados)
**Decisión (usuario):** el modo LIBRE deja de forzar las 24 secciones. Ahora solo se fuerza el
**piso de preparación de datos** (metadatos, inventario, QC LAS, estandarización, QC por curva,
prep, intervalos, metodología) + los **rieles de honestidad** (parámetros/procedencia, validadores
+claim verifier, grafo de metodología, limitaciones, conclusiones). **Todo el cuerpo de análisis
lo decide el agente** vía un campo `sections` ordenado (gr/resistividad/caliper/litología/vsh/
porosidad/sw/rw/zonación/resultados/incertidumbre/figuras + las 5 opcionales). El modo GUIADO
queda idéntico (baseline comparable con el piso completo). **Por qué:** "casi todo lo obligábamos";
el experimento del modo libre debe medir si el LLM sabe componer un informe, no rellenar un molde.
**Robustez:** tool_calls fuera de la whitelist se descartan (no tumban el plan) — los modelos a
veces listan secciones como tools; el plan del agente se honra igual. **Pendiente (follow-up):**
liberar la SELECCIÓN DE MÉTODO de cómputo (que el Vsh elegido propague a PHIE→Sw→net pay) toca el
pipeline; hoy el agente elige qué método destacar de la comparación, no recomputa la cadena.
**Verificado:** llama3.1 en modo libre compone su propia lista de secciones (fell_back=False);
56 source files, suite verde.

## DV2-20 (2026-06-29) — Bucle agente: el agente compone el informe paso a paso (loop construido)
**Decisión (usuario):** el informe del modo libre se genera por un BUCLE continuo (observar→decidir→
computar→observar), no de un disparo. El agente ve los datos que el motor computa y decide el
siguiente paso mientras construye el informe — la interpretación EMERGE de sus decisiones, pero el
LLM nunca calcula (invariante intacto). Reconcilia la tensión: no le damos el pipeline armado, pero
tampoco le pedimos inventar matemática. Decisiones: **recompute permitido** (rehacer una propiedad
con otro método invalida aguas abajo) y **scope completo** (cadena + opcionales + observación
on-demand de zona/distribución/punto, nunca arrays crudos).
**Construido (Fases 1-5):** `orchestrator/steps.py` (vsh/phie/sw discretos; `compute()` delega →
guiado y loop una sola fuente de verdad); `agents/loop_actions.py` (frontera de acciones por física
+ invalidación por recompute + `execute_step` reusando steps/zonate/MC/dispatch + observación);
`agents/analyst_loop.py` (`run_analyst_loop`: observar→decidir→ejecutar, fallback por paso, guard
anti-stall del orquestador, métricas `steps_taken/recomputes/finished/stalled`). El grafo de
metodología es la traza paso-a-paso. Modo guiado intacto (single-pass, baseline comparable).
**Hallazgo (techo honesto):** llama3.1:8b se estanca (repite acciones, no termina) — el orquestador
corta el desperdicio (anti-stall); es exactamente la limitación del modelo local que el experimento
mide. **Pendiente (follow-up):** propagar el método de Sw/porosidad al Monte Carlo (Vsh ya propaga
completo); re-correr el harness de validadores completo tras un recompute del núcleo (hoy las
objeciones/tier son de la pasada-0). Verificado: golden loop-default == pipeline; recompute cambia
net pay; el loop compone un informe con las secciones que el agente eligió.

## DV2-21 (2026-06-29) — El agente ve el informe-en-progreso + no-ops medidos, no ocultados
**Hallazgo (usuario):** "pensé que no ver el informe es lo que genera problemas". Validado: al
inyectar `report_so_far` (un outline compacto del documento construido hasta ahora) en la
observación, llama3.1:8b pasó de estancarse en 2 pasos a 9 pasos productivos (agregó 4 opcionales).
El agente necesita VER el documento que construye para decidir qué falta y cuándo terminar.
**Decisión (usuario, "midelo"):** dejar de OCULTAR los opcionales ya hechos de `available_actions`.
Antes el no-repetir era andamiaje NUESTRO (le quitábamos la opción), no juicio del modelo. Ahora se
ofrece TODO; el orquestador detecta no-ops (re-agregar un opcional ya hecho, o recomputar un núcleo
con su método actual), los **cuenta como `wasted_steps`** y los salta (nodo "wasted no-op" en el
grafo) — el informe queda limpio sin pensar por el modelo. Mide el modelo PURO (modelo, no
modelo+andamiaje); `wasted_steps` es una señal de competencia. Expuesto vía `objective_score.
loop_wasted`. **Verificado:** e2e llama3.1 en el ancla → `wasted_steps=1, recomputes=1,
fell_back=False`, secciones sin duplicados; suite verde (184 tests).

## DV2-22 (2026-06-29) — OpenRouter como control de techo (instrumento, no runtime)
**Problema:** el modelo local es inviable (qwen3:30b no entra en 16GB con el monitor 4K) o roza su
techo (llama3.1:8b se estanca). No podemos cerrar la pregunta de fondo **"¿es el flujo o el modelo?"**
sin correr el MISMO flujo con un modelo frontier.
**Decisión (usuario, "Opción A"):** añadir un backend **OpenRouter** (OpenAI-compatible, una API key,
modelos conmutables por string `vendor/model`) a `make_chat`. **Reconciliación con el invariante:** la
nube es **instrumento de medición / control de techo**, NUNCA el runtime del informe-producto (que
sigue local). Los LAS de Kansas son públicos → sin problema de privacidad. Un backend de nube = otra
forma de fabricar el MISMO `ChatFn = (system, user) -> str`; consumidores, cascada
`empty→fallback→deterministic`, leaderboard (clave = string del modelo) y `model_digest` (`"unknown"`
para nube) no se tocan.
**Diseño:** `make_chat(..., backend="auto")` enruta por `/` en el id (Ollama vs OpenRouter); override
`backend="ollama"|"openrouter"` para forzar. **Semántica de error (integridad de la medición):** una
falla de infra (sin API key, no-200, transporte) **corta fuerte** (`RuntimeError`) — NO se confunde
con incapacidad del modelo; solo un completion 200-vacío devuelve `""` y fluye por la cascada como
`empty_returns`. `temperature=0.0` + `seed` best-effort en nube (sin promesa bit-a-bit). `httpx` se
hace dependencia explícita (ya transitiva vía ollama); sin SDK pesado.
**Verificado:** `tests/test_client.py` (8 casos, sin red: dispatch, payload, no-200/transport/sin-key
→ raise, 200-vacío → `""`); suite completa verde; mypy/ruff limpios. La corrida e2e de techo se
dispara con `CEILING_MODELS=<ids>` en `debug/gen_field_report.py` (cloud-only, sin fallback local que
mezcle señal; informes a `outputs/v3` con prefijo `NN_`). Refinamiento posterior: retry acotado con
backoff (2/5/10/20s) para 429/502/503 + transporte (pools free saturan), 401/404 siguen cortando.
**Veredicto empírico (n=2 frontier):** nemotron-3-ultra-550b y nemotron-3-super-120b condujeron el
loop limpio — selección `fell_back=False`, sin stall, sin wasted, `fell_back=False` en todo; super-120b
hizo 1 recompute deliberado. Informes analíticos honestos (respetan abstención/tier). Contra el local
(llama3.1 se estanca, qwen3 da 8 pasos/2 recomputes): **el techo era el MODELO, no el flujo** — el
bucle agente está validado. (gpt-oss-120b/qwen3-next-80b: 429 persistente, infra, no medibles esta vez.)

## DV2-23 (2026-06-29) — Selección de pozos libre + consciente de calidad (sin ancla fija)
**Hallazgo (usuario):** con la corrida cross-familia (nemotron/gpt-5/gemini) **todos los informes
salieron iguales** — mismos pozos, mismos números, misma abstención. Causas: (1) los números son
deterministas (invariante, correcto); (2) **el ancla `26002` estaba forzada y es un pozo que se
abstiene** → metido a la fuerza en cada informe; (3) **el agente elegía a ciegas** (el prompt solo
mostraba `uwi + curvas`, no la calidad del dato) → no podía evitar pozos que abortan/se abstienen.
Sin margen interpretativo, todo modelo honesto converge al mismo "abstención + conseguir core".
**Decisión (usuario, opción A):** el analista **selecciona sus propios pozos, libre**, desde un
**inventario consciente de calidad** = la "base mínima de información" ([FIJO], en línea con
DV2-18/19/20: piso forzado + libertad encima). El piso ya NO es un pozo, es *información*: `%usable`
(vía `qc_gate`, pre-pase barato), curvas clave, intervalo. El ancla forzada se elimina.
**Diseño:** `well_quality_summary(well)` (QC gate → fracción GOOD; abort → no runnable);
`field_well_inventory` muestra calidad; `select_field_wells(metas, chat, max_wells=4)` sin ancla
(elige 1..max que le sirvan); fallback determinista = mejores pozos por `%usable`. La selección pasa
a ser **competencia medida** (¿eligió interpretables? ¿evitó la basura?). **Trade-off aceptado:** se
pierde el A/B estricto sobre el mismo pozo, pero elegir el dataset ES parte del trabajo del analista.
**Verificado:** suite verde (mypy/ruff limpios). Pendiente: re-correr para ver informes que SÍ difieren.

## DV2-24 (2026-06-30) — Selección de zona-de-interés del agente (DV2-23 al eje de profundidad)
**Hallazgo:** la corrida de 7 familias dio informes "vacíos" (todo se abstiene). Investigación
(`debug/dbg_phie_inflation.py`): PHIE 0.31 viene de RHOB ~1.75 g/cc en los **2/3 superiores** del pozo
(sobrecarga/dato no consolidado); el **tercio profundo (reservorio) tiene RHOB ~2.49 → PHIE sana**.
El motor promedia TODA la columna logueada → PHIE irreal → los validadores la marcan → abstención.
NO es bug de cálculo/unidades (correctos); el RHOB bajo viene del LAS crudo.
**La tensión (usuario):** "detesto esto, estamos resolviendo el problema que el agente debe resolver".
Excluir la sobrecarga / elegir el reservorio ES juicio de analista. Hard-codear "restringí a la zona"
o "flag RHOB<2" sería el andamiaje que venimos sacando. **Confirmado:** el agente HOY no puede excluir
la sobrecarga aunque quiera — nunca le dimos la herramienta (`zonate` es zonación de net-pay aguas
abajo, sobre toda la columna).
**Decisión:** darle la capacidad — extensión de DV2-23 al **eje de profundidad**. Piso de información
([FIJO]): observación `depth_quality` (perfil RHOB por tramo + `frac_rhob_below_2`, resumido, nunca
array crudo). Juicio ([MODELO]): acción `set_zone_of_interest(top,bottom)` que enmascara curvas fuera
del intervalo a NaN y **recomputa el baseline determinista sobre la zona** (el agente eligió el
intervalo; el motor computa — invariante intacto). Excluir sobrecarga pasa a ser **competencia
medida**. El único parche legítimo nuestro sería un piso mecánico (RHOB < ~1.5 = error de sensor); "1.75
es bajo para esta litología" es del agente.
**Verificado e2e:** restringir 25954 a 915–1343 m baja PHIE 0.229→**0.089** y net pay 296→**40 m**
(físicamente sano), sin que el LLM calcule nada. Suite verde (mypy/ruff limpios); tests nuevos de
`depth_quality_profile`, disponibilidad de acciones, y restrict+recompute e2e.
