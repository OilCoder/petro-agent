<!--
Informe de rumbo: cómo evolucionar petro-agent hacia un "analista junior" agéntico
(LLM que explora datos, decide qué análisis añadir, y llama herramientas deterministas)
SIN romper el invariante (el LLM nunca calcula). Generado 2026-06-25 por una exploración
de diseño orquestada de 10 ciclos (7 facetas → crítica adversarial → síntesis → stress-test
→ informe final), anclada en el código real. Workflow run: wf_03bf07fe-228.
NO es plan ejecutable aún — es la propuesta de rumbo para que el usuario decida.
-->
# Steering report — Evolucionar petro-agent hacia el "analista junior" agéntico sin romper el invariante

## 1. Diagnóstico — el gap entre el sistema prose-only actual y la visión analista

El sistema hoy es un pipeline determinista de topología fija con dos huecos de prosa pegados al final. El grafo de LangGraph (`src/orchestrator/graph.py:52-62`) cablea la secuencia `START → compute → validate → typify → [correct → compute]* → zonate → gating → emit → END`. Cada nodo es una función pura determinista (`src/orchestrator/stages.py`). El LLM solo entra después de que el ledger ya está cerrado: `generate_report` (`src/agents/report.py:37-39`) llama `run_pipeline`, obtiene el ledger completo, y recién entonces invoca `write_narrative`.

El `writer.py` confirma el techo de agencia actual: recibe un digest pre-formateado (`_facts`, `src/agents/writer.py:34-68`), el system prompt le ordena "Write PROSE ONLY... Use ONLY the numbers in the FACTS block" (`src/agents/writer.py:21-31`), y devuelve exactamente dos strings (`executive_summary`, `conclusions`, líneas 97-100). Todo lo demás está congelado en código:

- Qué funciones corren: fijo en los nodos. PHIE siempre densidad-neutrón (`stages.py:68-71`), Sw siempre Archie (`stages.py:74`), sin ramificación por dato.
- Parámetros: `resolve_all` (config) + estimadores data-driven deterministas (`estimate_matrix_density`, `estimate_shale_points`, `estimate_rw` en `lithology.py`). El docstring `lithology.py:6-7` lo dice explícito: "replacing the never-wired LLM compute agent ... the engine selects parameters, it never guesses". La agencia analítica que el `compute_agent` iba a tener fue deliberadamente reemplazada por código y nunca se cableó (`compute_agent.py` existe pero está muerto; `grep tool src/ tests/` no devuelve nada funcional).
- Estructura del informe: 13 secciones fijas con numeración hardcodeada en `render_well_report` (`report_template.py:348-362`; los headings `## 4.`, `## 5.` están escritos a mano en los cuerpos, p.ej. `report_template.py:205,239`), idénticas para todo pozo.
- Decisión/gating/abstención: 100% determinista en `gating()` (`stages.py:135-170`).

El gap con la visión del usuario es total en una dimensión y nulo en otra. La visión pide: pre-forma base → EDA exploratoria → DECIDIR qué análisis añaden completitud → PROPONER cálculos llamando a tools deterministas → ensamblar el mejor informe posible. Hoy no existe ni la fase de exploración, ni la decisión sobre composición, ni el mecanismo de tool-calling, ni la noción de "secciones opcionales según el dato". El LLM tiene cero agencia analítica; es un redactor de relleno con dos slots. Pero la infraestructura del invariante (motor golden-tested, validadores independientes en `validators/harness.py`, gates deterministas, ledger, claim_verifier) está construida y verde (143 tests, ESTADO.md:57). No hay que reconstruir nada; hay que insertar agencia en el lugar correcto sin tocar lo que ya garantiza honestidad, y blindar los huecos que esa agencia abre.

## 2. Principio rector — dar agencia sin romper el invariante

El invariante se descompone en cuatro cláusulas separables, y cada cláusula tiene una frontera distinta; la visión del usuario solo cruza dos de ellas:

| Cláusula del invariante | ¿Agencia del LLM aquí? | Por qué |
|---|---|---|
| (a) El LLM nunca calcula un número | NO — frontera dura | El número sale del motor golden-tested. El LLM pide que se calcule, no produce el dígito. |
| (b) El LLM nunca escribe la ecuación en runtime | NO — frontera dura | Selecciona una función probada de un menú cerrado; no inyecta matemática. |
| (c) El orquestador (loop, gates, terminación) es determinista | NO — frontera dura | El LLM nunca decide saltarse QC ni cuándo abstenerse. |
| (d) Cada número es trazable en el ledger | NO — frontera dura | Toda tool-call y su resultado se registran con su clave y hash. |

La frontera exacta, en una frase: el LLM gana agencia sobre la EXPLORACIÓN (qué mirar del dato) y la COMPOSICIÓN (qué análisis/secciones incluir y en qué orden para dar completitud); nunca sobre el CÁLCULO (lo hacen tools deterministas), ni sobre los GATES (QC, validadores, abstención siguen siendo nodos deterministas obligatorios e in-saltables).

- Agencia SÍ: "este pozo tiene RHOB+NPHI de buena calidad y un intervalo de baja resistividad — vale correr un Pickett plot y añadir una sección de saturación irreducible". Eso es selección y composición.
- Agencia NO: calcular el Sw, decidir el cutoff de Vsh fuera del menú, o decidir que el QC se omite porque "el dato se ve bien".

Honestidad sobre el techo de esta agencia. Varias tools de EDA que el analista consulta encierran ellas mismas umbrales interpretativos (qué cuenta como RT "baja", qué tan "cerca" de la línea de litología, qué percentiles de GR son clean/shale). Esas decisiones petrofísicas están pre-tomadas en código determinista. Por tanto la "agencia analítica" del LLM es, en lo esencial, selección sobre un menú de exploraciones pre-pensadas, no descubrimiento abierto. Esto no es un defecto a esconder: es lo que preserva el invariante. La forma honesta de presentarlo es un sistema de dos capas auditable: (capa 1) umbrales deterministas citados y versionados como cualquier parámetro de `params/citations.py`; (capa 2) el toggle del LLM, logueado. Opcionalmente, dar al analista la facultad de parametrizar un umbral desde un enum cerrado (p.ej. percentil RT-low ∈ {5,10,15}) le da agencia genuina pero acotada sin que escriba matemática. El analista junior resultante elige bien del repertorio; no expande el repertorio.

El patrón que materializa esto es tool-calling con un orquestador que sigue siendo dueño del loop. El LLM no es el loop; es un nodo dentro de un super-loop determinista que (i) le ofrece un menú cerrado de tools, (ii) ejecuta solo tools de una whitelist con contratos validados, (iii) intercala gates deterministas obligatorios que no puede saltar, (iv) registra cada llamada en el ledger. La diferencia con un agente ReAct suelto es que el control de terminación, los gates y la whitelist viven en LangGraph, no en la cabeza del modelo.

## 3. Arquitectura objetivo — el agente analista tool-calling

Hoy el LLM corre después del grafo. La arquitectura objetivo lo inserta como un nodo acotado dentro del grafo. La ubicación es la decisión crítica, y debe resolverse contra la topología REAL, que tiene un loop de corrección: el grafo real es `compute → validate → typify → [correct → compute]* → zonate → gating → emit` (`graph.py:52-62`), donde `compute` (`stages.py:46-84`) reescribe vsh/phie/sw y la calibración en cada iteración. Si el analista corriera entre `validate` y `typify`, vería curvas obsoletas que el loop sobrescribe, o tendría que correr N veces dentro del loop (N inferencias de 30B en 16GB — la explosión de costo exacta que hay que evitar).

Resolución: el analista corre una sola vez, sobre la arista `zonate → gating` (`graph.py:60`) — después de que el loop de corrección converge y después de que `zonate` produjo el `summary` y `net_pay_total_m`, pero antes de `gating`. Así ve vsh/phie/sw finales y la agregación de net pay, corre exactamente una inferencia, y aún precede al gate determinista de abstención. Las tools opcionales que necesiten agregación llaman a las MISMAS funciones vetadas (`netpay.py`, `volumetrics.py`) para que sus números sean consistentes con el núcleo.

```
   DETERMINISTIC ORCHESTRATOR (LangGraph — owns loop + gates + termination)
   LAS -> load -> qc_gate -> compute ----+
                                         | (det)
              +------ correct loop ------+
              |  typify -> [correct -> compute]*   (max iters = cb_n, det)
              +--------------------------+
                                         v
                                      zonate            (det: summary, net_pay)
                                         v
                          +---- [ANALYST NODE] ----+   <- runs ONCE, here
                          |  EXPLORE -> DECIDE      |      (1 inference)
                          +-----------+------------+
                                      v
                       cross-tool consistency validator   (det, FIX 8)
                                      v
                                   gating              (det, MANDATORY, un-skippable)
                                      |  abstain? -> restrict section_plan (det, FIX 6)
                                      v
                                    emit -> render (plan-driven, det)
```

Sub-loop del analista (acotado):

```
  state: ledger-so-far + EDA pre-digest (compact) + section catalog + tools already called
   1. EXPLORE  -> all EDA tools are PRE-COMPUTED deterministically (cheap, read-only)
                  BEFORE the LLM is called; the LLM receives a COMPACT pre-digest (~10 lines,
                  like writer.py:_facts), never the raw per-curve dicts
   2. DECIDE   -> ONE LLM turn emits a BATCH section_plan (JSON), validated by jsonschema:
                  {"section_plan":[{"id":"<catalog_id>","rationale":"...",
                    "tools":[{"tool":"...","args":{...}}]}]}
   3. DISPATCH -> orchestrator (NOT the LLM) validates each tool against whitelist+schema,
                  runs the DETERMINISTIC fn, writes result under a NAMED ledger key + result_hash
   4. every number came from a tool; the LLM produced only ids + rationale, never a digit
```

Puntos no-negociables:
- El sub-loop tiene `max_steps` determinista (espejo del `circuit_breaker_n`, `graph.py:97`). El LLM no controla la terminación. Idealmente 1–2 turnos LLM, porque todo el EDA barato ya está pre-computado.
- El analista solo emite el JSON de plan; nunca números en prosa. La prosa (writer actual) sigue siendo el último paso, con el ledger ya cerrado.
- `gating()` y la abstención corren después del analista, sobre el ledger enriquecido, sin que el LLM pueda evitarlos.

## 4. Toolset de exploración (EDA) que hay que construir

No existe hoy ninguna tool de EDA — el sistema calcula directo, sin mirar primero. Hay que construir un módulo nuevo `src/eda/` con funciones read-only, deterministas, golden-tested, cuyo output sea un dict serializable (numbers, no arrays crudos). Leen del estado que el grafo ya tiene (`curves`, `depth_m`, `quality_map` en `PipelineState`, `state.py:17-25`). Firmas propuestas:

```python
# src/eda/explore.py  — all deterministic, all return JSON-serializable dicts

def curve_inventory(curves: dict[str, np.ndarray], depth_m: np.ndarray) -> dict:
    """Which canonical curves exist, % non-null, depth span. -> {curve: {present, pct_valid, min, max}}"""

def depth_coverage(curves: dict, depth_m: np.ndarray, step_m: float) -> dict:
    """Gaps, logged interval, sample count. -> {top, base, gross_m, n_samples, gaps:[...]}"""

def histogram_stats(curve: np.ndarray, bins: int = 20) -> dict:
    """Robust distribution summary (p5/p50/p95, mode bin, skew flag). No raw array out."""

def crossplot_density_neutron(rhob, nphi, vsh, line_tol: float) -> dict:
    """% near sandstone/limestone/dolomite lines, gas-effect flag. line_tol is a CITED threshold."""

def low_resistivity_scan(rt: np.ndarray, depth_m, phie, rt_low_pctile: int) -> dict:
    """Flags intervals where RT is low (percentile-based, CITED) but PHIE decent. -> {intervals:[...]}"""

def gr_baseline_check(gr: np.ndarray) -> dict:
    """Clean/shale GR endpoints actually present vs assumed gr_min/gr_max. -> {gr_clean_p5, gr_shale_p95}"""

def badhole_summary(quality_map) -> dict:
    """% depth in GOOD/DEGRADED/EXCLUDED from the existing qc quality_map."""
```

Cada función con golden tests (bounds, casos analíticos) igual que la petrofísica. Honestidad de la capa de umbrales: cada parámetro interpretativo (`line_tol`, `rt_low_pctile`, percentiles de `gr_baseline_check`) se registra como un parámetro citado y versionado en `params/citations.py`, y se vuelca a la tabla de provenance del informe. Así la "decisión" que el LLM toggle-a es ella misma trazable y revisable. El valor para el analista: estas son las "observaciones parciales" desde las que decide qué análisis añaden completitud — pero el pre-digest que se le pasa al LLM debe ser compacto (ver sección 7), no el blob crudo de 7 curvas, que es precisamente lo que dispara el vaciado de qwen3 bajo carga.

## 5. Pre-forma base + composición por completitud

La estructura del informe se parte en dos clases.

Secciones OBLIGATORIAS (pre-forma base, render determinista existente): cabecera + leyenda (`_header`, `_legend`), metodología (`_methodology`), parámetros y provenance (`_parameters`), resultados core Vsh/PHIE/Sw/net pay/NTG (`_results`), QC y objeciones (`_data_quality`), incertidumbre (`_uncertainty`), banner de abstención si aplica (`_abstention_banner`), apéndices de trazabilidad + completeness gate (`_appendix_ledger`, `_appendix_checklist`), y los dos slots de prosa LLM. Son el invariante de completitud: ningún informe puede omitirlas.

Secciones OPCIONALES (el analista las decide según el dato): litología extendida (cuando `crossplot_density_neutron` muestra mezcla), Pickett + discusión de Rw (cuando hay intervalo de baja resistividad), saturación irreducible / BVW (caso real Schaben), gas-effect, zona de transición.

Mecánica del render plan-driven, resolviendo la numeración hardcodeada. Hoy `render_well_report` (`report_template.py:337-363`) toma una lista fija de 13 secciones con headings numéricos escritos a mano (`## 4. Zonation`, `## 5. Results` en `report_template.py:205,239`). Insertar opcionales entre ellas renumeraría todo o las dejaría fuera de orden. El refactor:

1. Se elimina el número del cuerpo de cada `render_<id>` (devuelven `## Zonation`, no `## 4. Zonation`); el número lo asigna el ensamblador según el orden del plan armado. Así insertar Litología-QC entre Results y Uncertainty renumera limpio.
2. Se define `SECTION_CATALOG = {id: render_fn}` como dict cerrado y congelado. Las obligatorias siempre van; las opcionales van iff están en el `section_plan` Y su tool produjo una entrada de ledger no-nula.
3. El analista emite IDs de ese catálogo cerrado con su justificación y las tool-calls que las alimentan. El catálogo cerrado es lo que mantiene la agencia acotada: elige de un menú, no inventa secciones.

Cada sección opcional tiene un `render_<id>(ledger)` determinista pre-escrito; el LLM nunca escribe la tabla, solo decide incluirla. Dos tests distintos: (a) regresión byte-idéntica con `section_plan` fijado al ordenamiento solo-obligatorias actual; (b) test separado que asserta que las opcionales se renderizan en las posiciones definidas por el catálogo (intercaladas), no apendizadas al final — esto último contradiría la visión de "mejor informe" con la litología-QC junto a Resultados.

## 6. Preservación del invariante bajo agencia

Ocho mecanismos blindan el invariante una vez que el LLM tiene agencia. El orden importa: estos guardrails se construyen ANTES de cablear el LLM (ver sección 8).

1. Contrato de tool-call congelado + validación jsonschema. Un único schema para el turno-batch: `{"section_plan":[{"id":"<catalog_id>","rationale":"...","tools":[{"tool":"<name>","args":{...}}]}]}`, validado con `jsonschema` antes de cualquier dispatch. `id` debe estar en `SECTION_CATALOG`; `tool` en `ALLOWED_TOOLS`; `args` valida contra el schema de esa función. Cualquier cosa malformada o fuera de whitelist se descarta, se cuenta como paso fallido, no se ejecuta. Reutiliza el parseo tolerante de `reviewer.py:38-54` pero con la corrección del punto 7 sobre el fallo silencioso.

2. El orquestador, no el LLM, hace el dispatch. Valida `args`, llama la función determinista Python, captura el resultado, lo escribe al ledger bajo una clave nombrada con su tool de origen y un `result_hash`. El LLM nunca ve ni produce el número. Esto es literalmente el invariante (a)+(b).

3. Reconciliación a nivel de campo — NO reusar el claim_verifier plano. Aquí el draft original se equivocaba y hay que invertirlo. El `verify_report` actual (`claim_verifier.py:54-71`) colecta TODOS los números del ledger en un `set[float]` plano (`_collect_numbers`, líneas 18-31) y aprueba cualquier decimal de la prosa que esté a `rel_tol=0.02` de cualquiera del set. Añadir secciones opcionales (pickett_params, hcpv, bvw, sat. irreducible) agranda el set y debilita monotónicamente el verificador: un valor alucinado es más probable que caiga a 2% de algún número de un set más grande. Por tanto: cada número tool-derivado se escribe bajo una clave de ledger nombrada con su tool y `result_hash`; el verificador de campo comprueba que cada decimal de una sección opcional mapea a la clave específica de ledger que esa sección renderiza — no a "cualquier número a 2%". Esta es la check (2)/(3) que ESTADO.md:83 marca como no construida, y es prerrequisito de la agencia, no una extensión posterior. Test de regresión: inyectar un número alucinado 1.9% off de un valor real de ledger y assertar que el verificador de campo lo flaggea (el plano actual lo pasa). Mantener el check de tono (`verify_tone`, líneas 38-51) intacto pero extendido (punto 6).

4. Reproducibilidad / seeds — con la salvedad honesta. El chat está pineado (`seed=42, temperature=0.0`, `client.py:37`) y las tools (EDA + petrofísica) son deterministas, así que mismas tool-calls dan mismos números. Se registra la traza completa (`run.analyst_trace`) para que un re-run sea auditable y diffeable. Salvedad que el draft ocultaba: seed+temp 0 NO hacen determinista el paso LLM cuando qwen3:30b-a3b devuelve VACÍO bajo presión de VRAM — eso es no-determinismo a nivel de scheduler/OS, no del sampler. La mitigación no es el seed; es el fallback señalizado (punto 7) más el pineado del digest del modelo (sección 8, Fase G).

5. Gates deterministas mandatorios. `gating()` (`stages.py:135-170`) corre como nodo después del analista. El LLM no tiene una tool "skip_qc" ni "force_firm" — no están en la whitelist y no existen como función. La abstención (`abstain_reasons`, `stages.py:159-162`) la calcula código sobre objeciones MECHANICAL e implausibilidad de net pay; el analista no la puede tocar.

6. Abstención DOMINA la composición (cierra el bypass del espíritu del invariante). Hueco crítico real en Schaben: los 3 pozos se abstienen (MECHANICAL + PHIE alta para carbonato, ESTADO.md:52-53). El banner solo se renderiza si `run['abstain']` (`report_template.py:129-140`). Si el analista rodea un núcleo que se abstiene con secciones de análisis confiado (discusión de Rw por Pickett, tablas BVW), el informe se lee como un estudio confiable mientras el gate dispara en silencio — el humano hojea el análisis rico y se pierde el banner. El invariante literal se preserva, pero el espíritu (comunicación honesta de la abstención) se evade por composición. Fix determinista, en el dispatcher (no en el LLM): si `abstain` es True, se intersecta el `section_plan` pedido con una allowlist `ABSTENTION_SAFE` (solo secciones diagnósticas/de limitación; se caen Pickett/BVW que implican un resultado defendible) y se registra el drop en `analyst_trace`. Además, `verify_tone` se extiende a TODA sección opcional renderizada (no solo los dos slots de prosa) para consistencia de tier/abstención. Test: ledger que se abstiene + analista pidiendo Pickett → Pickett dropeado, banner presente, tono consistente.

7. Fallback EXPLÍCITO y SEÑALIZADO, nunca silencioso. Hueco crítico: `reviewer.py:_parse_objections` devuelve `[]` ante cualquier basura; trasladado al analista, el análogo silencioso es "no se llamó ninguna tool" = pre-forma base con CERO análisis. No se puede distinguir "qwen3 vacío bajo carga de 16GB" de "qwen3 eligió deliberadamente el informe mínimo". Ambos dan `section_plan=base-only`. Fix: wrapper en `client.py` que (a) pone un timeout de request a Ollama (hoy no hay, `client.py:30-39`), (b) trata completaciones vacías/whitespace como FALLO duro, no como "sin tools", (c) reintenta una vez y luego cae en cascada qwen3 -> llama3.1. Campo nuevo en el ledger: `run['analyst'] = {model_used, n_steps, empty_returns, fell_back_to_deterministic}`. El fallback determinista produce la pre-forma base y pone un banner visible "(analyst unavailable — base report only)" para que un base-por-fallo nunca se confunda con un base-por-elección. Test: inyectar un fake chat que devuelve vacío y assertar `fell_back_to_deterministic=True` y banner presente.

8. Validador de consistencia cross-tool (cierra el dual-number contradictorio). Hueco: `estimate_rw` (`lithology.py:96-133`) ya elige Rw data-driven en el `compute` congelado. Si el analista llama un `pickett_params` que deriva un Rw DISTINTO, el ledger tiene dos Rw conflictivos, ambos tool-derived y trazables; el `_facts` del writer y el claim_verifier los aplanan y el informe podría citar el que el LLM prefiera. El menú cerrado restringe qué tools, no si sus outputs son mutuamente consistentes con `compute()`. Fix: un validador determinista de consistencia que corre en el harness (`validators/harness.py`) después del analista, sobre el ledger enriquecido: p.ej. cualquier Rw derivado por el analista debe igualar `calibration['Rw']` de compute dentro de tolerancia, si no, objeción MECHANICAL (que alimenta gating y puede disparar abstención). Así un output contradictorio se vuelve un problema de convergencia determinista, no un dual-number silencioso.

(Mecanismo anti-drift transversal) El catálogo cerrado: `ALLOWED_TOOLS` y `SECTION_CATALOG` son listas congeladas, versionadas, con tests. El LLM compone dentro del catálogo. Convierte "agencia analítica" en "selección sobre un espacio finito y auditado".

## 7. Viabilidad en modelos locales

El tool-calling es el punto de mayor riesgo dado el techo de 16GB y el dato conocido de que qwen3:30b-a3b devuelve VACÍO bajo carga. Análisis honesto:

- Tool-calling nativo de Ollama, NO. Ollama soporta `tools=[...]`, pero su fiabilidad bajo carga local es desigual y qwen3 ya tiene historial de vaciado. Es más robusto un protocolo de tool-call por JSON-en-texto: el LLM emite el bloque JSON del `section_plan`, el orquestador lo parsea (regex tolerante estilo `reviewer.py:35-54`) y lo valida con jsonschema. Degrada con gracia: basura -> descartada -> paso fallido -> fallback señalizado (no crash, no silencio).

- El vaciado correlaciona con la longitud del prompt. Es un fenómeno de context-length/VRAM. Por eso NO se le pasa el blob crudo de EDA (curve_inventory + depth_coverage + histogram_stats por 7 curvas es enorme y dispara el vacío). Se pre-computa todo el EDA determinista barato y se le da al LLM un pre-digest compacto (~10 líneas, como `writer.py:_facts:34-68`); los dicts completos van al ledger, no al prompt. Hay que medir el tamaño serializado y poner una aserción de token-count en el test del dispatcher, manteniendo el prompt bajo un techo seguro medido. Esto reconcilia "pre-computar todo, 1–2 turnos" con "no inflar el prompt".

- Fallback en cascada (espejo del que ya existe — el repo ya cayó a llama3.1:8b para los informes finales, commit a933665): (1) qwen3:30b-a3b para el analista; (2) si devuelve vacío / JSON inválido tras 1 reintento, cae a llama3.1:8b (más débil, fiable); (3) si llama3.1 tampoco produce un `section_plan` válido, fallback determinista: pre-forma base sin opcionales, con el banner "(analyst unavailable)". El informe nunca falla por culpa del LLM — pierde composición inteligente, conserva completitud y honestidad. Cada caída se registra en `run['analyst']`.

- Presupuesto de pasos chico y medido. `max_steps` bajo (1–2 turnos LLM idealmente). Cada turno es una inferencia de 30B en 16GB: lento y con riesgo de vaciado. El draft hand-waveaba el costo; hay que medir la latencia por turno y fijar el timeout en consecuencia. Para un build autónomo de 2 días sin humano (MEMORY autonomous-run-mandate), un loop que degrada en silencio en cada hipo de VRAM produciría informes base indistinguibles de fallos — de ahí que el fallback señalizado (6.7) sea condición de viabilidad, no un adorno.

- El techo del modelo débil es real pero aceptable. llama3.1:8b puede componer un `section_plan` razonable (es selección sobre un catálogo, no razonamiento abierto); su justificación será más pobre. La calidad de la justificación no afecta los números (deterministas) ni los gates (deterministas).

## 8. Hoja de ruta por fases (los GUARDRAILS aterrizan ANTES que la agencia)

Principio de secuenciación, corrigiendo el draft: el LLM no se cablea hasta que la jaula determinista que atrapa sus fugas de números, sus tools contradictorias y su bypass de abstención esté probada y verde. Cada fase es aditiva, deja el sistema funcionando y mantiene los 143 tests verdes.

- Fase A — Toolset EDA determinista (`src/eda/`). Funciones read-only con golden tests; umbrales interpretativos registrados como parámetros citados en `params/citations.py`. Entregable: pytest verde sobre `tests/test_eda_*`; corren sobre los 3 pozos Schaben y emiten dicts plausibles. Cero cambio al pipeline.

- Fase B — Catálogo de secciones + render plan-driven. Refactor de `render_well_report` para quitar los números hardcodeados de los cuerpos y asignarlos por orden de plan; `SECTION_CATALOG` cerrado; `render_<id>` para 3–4 opcionales. Entregable: con `section_plan` solo-obligatorias el informe es byte-idéntico al actual (test de regresión); test separado de posicionamiento intercalado de opcionales.

- Fase C — Dispatcher + contrato jsonschema + whitelist + reconciliación de campo + consistencia cross-tool. `src/agents/tool_dispatch.py`: valida tool-call contra schema, ejecuta la función determinista, escribe resultado+provenance bajo clave nombrada+result_hash, registra en `analyst_trace`. Construir AQUÍ el claim_verifier de campo (reemplaza el set plano para números tool-derivados) Y el validador de consistencia cross-tool en el harness. Sin LLM aún — testeado con tool-calls fabricadas y números alucinados. Entregable: dispatcher rechaza tools fuera de whitelist y args inválidos; verificador de campo flaggea el número 1.9%-off; consistencia cross-tool levanta MECHANICAL ante Rw contradictorio.

- Fase D — Nodo analista en el grafo (heurística determinista + restricción de abstención). Insertar el nodo en la arista `zonate -> gating` (`graph.py:60`). Primera versión: NO llama LLM, usa una heurística determinista para el `section_plan`. Construir AQUÍ la restricción `ABSTENTION_SAFE` y la extensión de `verify_tone` a secciones opcionales. Entregable: pipeline corre con opcionales activadas por dato, todo determinista; un ledger que se abstiene dropea Pickett y mantiene el banner; tests verdes.

- Fase E — LLM en el nodo analista (con cascada de fallback señalizado). Reemplazar la heurística por el LLM tool-calling (EXPLORE pre-computado -> DECIDE batch), con la heurística de Fase D como red. Construir AQUÍ el wrapper de `client.py` (timeout, empty=fallo, retry, cascada) y el campo `run['analyst']` con el banner "(analyst unavailable)". seed=42, `analyst_trace` al ledger. Entregable: corre sobre Schaben; el `analyst_trace` es reproducible mientras el modelo responda; si el LLM falla, cae con banner visible sin romper el informe.

- Fase F — Tests de agencia en dos tiers. Tier 1 (determinista, CI-gating, junto a los 143): dispatcher + jsonschema + verificador de campo + restricción de abstención + consistencia cross-tool, todo con tool-calls fabricadas y fake chats (sin modelo). Tier 2 (model-in-the-loop, NO-gating, manual): smoke test "¿el LLM decide con sensatez?" guardado como `analyst_trace` golden para un pozo conocido, comparado con tolerancia semántica (set-equality del `section_plan`), explícitamente marcado como model-version-sensitive y excluido del invariante de 143 tests.

- Fase G — Pineado del digest del modelo en la provenance. Extender `provenance.pin_versions` (`provenance.py:40-59`) para registrar el digest del modelo (`ollama show <model>`/quantization), no solo la versión del paquete ollama. Entregable: dos runs con el mismo seed pero un tag re-pulled de qwen3 son detectables en el ledger; test que asserta la presencia del digest.

## 9. Riesgos y techo honesto

El techo honesto: esta arquitectura le da al LLM agencia real pero acotada — selección sobre un espacio finito de exploraciones y composiciones auditadas, con los umbrales interpretativos pre-tomados (y citados) en código determinista. NO lo convierte en un petrofísico que inventa métodos nuevos; por diseño no puede, y eso es lo que preserva el invariante. El analista junior resultante elige bien del repertorio; no lo expande. Si el usuario espera que el LLM derive un modelo shaly-sand nuevo en runtime (Thomas-Stieber, ESTADO.md:75), eso viola el invariante y queda fuera de alcance.

Riesgos vivos, ordenados por severidad:

1. El tool-calling nunca se ha ejercitado en estos modelos locales. Toda la premisa de la Fase E está sin validar. Mitigación: la cascada de fallback señalizado garantiza que el sistema sigue produciendo informes honestos aunque el tool-calling resulte inviable en qwen3:30b sobre 16GB — degradaría a heurística determinista + base-form con banner, nunca a un fallo silencioso.

2. Vaciado de VRAM no-determinista. Seed+temp 0 no lo arreglan. Mitigación: pre-digest compacto, timeout medido, empty=fallo, pineado del digest del modelo. Aceptamos que la reproducibilidad bit-exact del paso LLM no es garantizable; lo que sí garantizamos es la detectabilidad (ledger registra empty_returns, fell_back, model digest) y la reproducibilidad de los números (deterministas dadas las tool-calls).

3. La agencia es, en lo esencial, selección sobre umbrales pre-pensados. Si el usuario esperaba exploración abierta, el techo decepciona. Lo honesto es presentarlo como sistema de dos capas auditable, no venderlo como descubrimiento.

4. La exactitud sigue siendo el cuello de botella, y esta migración no la toca. La calibración real (VOLVE bloqueado, core/producción Schaben ausente — ESTADO.md:64-71) es lo que haría converger los net pay; hoy los 3 pozos se abstienen por diseño. Esta migración mejora la completitud y la inteligencia de composición, no la exactitud de los números. Un informe más rico y mejor compuesto sobre un núcleo que se abstiene sigue siendo un informe que se abstiene — y el mecanismo 6.6 existe precisamente para que esa abstención no se diluya bajo el análisis añadido.
