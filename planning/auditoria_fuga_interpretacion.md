# Auditoría — Fuga de interpretación código → agente (flujo de informe)

**Fecha:** 2026-07-01
**Método:** 5 ciclos de revisión en paralelo, cada uno un lente distinto sobre la
frontera código↔agente, + verificación manual de cada quote contra el código real.
**Invariante auditado:** el código entrega datos de calidad, QC/limpieza y un catálogo
NEUTRAL de herramientas vetadas; **nunca** debe orientar el análisis (qué método/fórmula
usar, dónde hay zonas de interés, qué litología/fluido implica, qué concluir). Toda decisión
interpretativa debe **nacer del agente** — es lo que el experimento mide.

## Veredicto ejecutivo

El **camino cuantitativo se sostiene**: ningún número lo escribe el LLM; renderers, validadores,
`methodology_graph` y el gate `_numeric_literal_issues` refuerzan el invariante. El catálogo de
métodos (`registry.available_methods`) y de secciones es neutral.

**Pero la frontera se cruza en 7 focos.** El patrón raíz es uno solo: **el código toma o
sugiere la decisión interpretativa y la presenta como si fuera del agente** — ya sea
enseñándosela en el prompt/observación, entregándole la conclusión ya masticada en los "FACTS",
o rellenando un default/fallback sin señalarlo en la superficie del informe. Varios de estos
focos son exactamente el andamiaje que se añadió para "llegar al 75%" (zona de interés DV2-24,
cutoffs [FIJO], baseline pre-computado) — el caso que la regla dura del proyecto advierte:
*nunca guionar una decisión de analista para que la demo luzca bien.*

---

## VIOLACIONES (por severidad)

### A. Playbook "overburden → zona de interés" filtrado en 3 superficies  ⬛ CRÍTICO
La selección de la zona de interés es **la** decisión de analista. El código se la entrega hecha,
con criterio y umbral, en tres lugares que se refuerzan:

- **`src/agents/analyst_loop.py:50-53`** (`_LOOP_SYSTEM`, "Your job, in order", paso 0):
  > *"CHECK the interval first… If the top is non-reservoir OVERBURDEN (low RHOB / high
  > frac_rhob_below_2 = not consolidated rock), restrict to the reservoir with
  > set_zone_of_interest… Do this BEFORE refining methods."*
- **`src/agents/loop_actions.py:302-304`** (`note` devuelta al agente como resultado de la
  observación `depth_quality`):
  > *"RHOB ~2.4-2.7 = consolidated rock; low RHOB / high frac_rhob_below_2 = likely overburden
  > or bad data, not reservoir. Restrict with set_zone_of_interest(top,bottom)."*
- **`src/agents/analyst_loop.py:213-218`** (`hint`, repetido cada turno): eco de *"overburden with
  one set_zone_of_interest"*.

**Por qué:** entrega la regla (RHOB bajo ⇒ overburden ⇒ no-reservorio ⇒ restringe), el juicio
("not reservoir") y hasta la herramienta y el orden. Un modelo débil ejecuta el zone-restrict como
reflejo, no como juicio. **Es DV2-24** — se añadió para evitar la abstención por PHIE inflado del
overburden; funciona, pero a costa de guionar la interpretación.
**Fix:** ofrecer `depth_quality` (números por bin) y `set_zone_of_interest` en el catálogo **sin**
explicar qué significa RHOB bajo ni cuándo restringir. Que el agente concluya.

### B. Regla de método "Vsh alto → shaly-sand Sw"  ⬛ CRÍTICO
- **`src/agents/analyst_loop.py:54-56`**:
  > *"recompute a core property with a BETTER method for this rock (e.g. a shaly-sand Sw model
  > when Vsh is high)"*

**Por qué:** el "e.g." es una regla concreta de selección de método (qué fórmula para qué roca) —
justo lo que el experimento mide. Ancla hacia Simandoux cuando ve Vsh alto.
**Fix:** frasear neutro ("puedes recomputar una propiedad con otro método vetado si los datos lo
justifican, a lo sumo una vez"), sin la condición→método.

### C. Ejemplo JSON trabajado en el prompt del analista  ⬛ ALTO
- **`src/agents/analyst.py:45-48`** (`_SYSTEM`), ejemplo:
  > `sections: [gr_analysis, lithology, vsh, porosity, sw, zonation, results, uncertainty,
  > shaly_sand_saturation]`, `tool_calls: [{sw_simandoux, carbonate_default}]`,
  > `rationale: "dolomitic shaly section, so include lithology and a shaly-sand saturation"`

**Por qué:** aunque dice "copy the structure not the values", el contenido es un plan petrofísico
plausible y completo: método concreto (Simandoux), preset concreto (carbonate), y un rationale que
encadena litología→método. Es el único ejemplo de "decisión buena" que ve el modelo → lo copia.
**Fix:** ejemplo con placeholders neutros (`<section_id>`, `<optional_tool_id>`, `<preset_id>`) que
NO formen un plan real, o solo el esquema de tipos.

### D. El digest "FACTS" entrega conclusiones, no materia prima  ⬛ ALTO
El agente debería recibir números; recibe veredictos:

- **`src/eda/explore.py:104`** — `nearest = max(shares…)`: ejecuta el argmax y entrega la
  **litología dominante** ya decidida. Se surface en `analyst.py:66-72` ("lithology nearest X") y se
  imprime en el informe bajo el encabezado forzado *"Lithology interpretation"* (`report_template.py:467-478`).
  **Fix:** entregar solo `shares` (fracción por matriz); que el agente decida cuál domina.
- **`src/eda/explore.py:106`** — `gas_effect_flag`: etiqueta un cruce numérico como **conclusión de
  fluido (gas/HC)**. Umbrales `0.10 / 2.4 / 0.05` hardcodeados y no citados.
  **Fix:** eliminar el flag o reportar solo la fracción numérica con umbrales citados, sin la etiqueta "gas".
- **`src/eda/explore.py:110-137`** — `low_resistivity_scan`: devuelve `intervals` (spans donde
  `RT ≤ p10` **y** `PHIE > 0.08`) = **pre-identifica zonas prospectivas** (el screen clásico de
  low-resistivity pay). El docstring recomienda el método: *"select Simandoux/Pickett"*. El `0.08`
  es un cutoff interpretativo oculto y no citado (contradice el claim del módulo de thresholds "CITED").
  **Fix:** reportar percentiles de RT crudos por profundidad sin cruzarlos con un cutoff de PHIE; quitar la recomendación de método.
- *(borderline)* **`src/eda/explore.py:140-146`** — `gr_baseline_check` etiqueta p5/p95 como
  `clean`/`shale`, pre-asignando la lectura litológica de los endpoints GR. Renombrar a `gr_p5/gr_p95`.

### E. Defaults interpretativos silenciosos (base-por-fallo = base-por-elección)  ⬛ ALTO
Cuando el agente omite un preset/método, el motor rellena uno **interpretativo** y lo reporta como
estado final, sin distinguir "lo eligió el agente" de "lo puso el motor":

- **`src/agents/tool_dispatch.py:68-70`** — Sw sin preset ⇒ `carbonate_default`. `a/m/n/Rw` cambian
  el Sw materialmente, y **Kansas/Schaben es carbonato**: el default empuja hacia la respuesta correcta
  sin que el agente la gane. `validate_plan` explícitamente no rechaza presets (`:60-62`) y no se marca
  degradación.
- **`src/agents/tool_dispatch.py:130-138`** — porosidad sónica sin preset ⇒ `limestone`, **y el
  signaling es engañoso**: la línea 138 reporta `"preset": args.get("matrix_preset")` = `None`
  aunque computó con `limestone`.
- **`src/agents/loop_actions.py:263-273`** — `_exec_optional` afirma "(signaled)" al coercer un método
  alucinado al default, pero **no escribe ningún registro** de la substitución (cf. `dispatch()` que sí
  señala en `run.tools_not_executed`).

**Fix transversal:** cada vez que el dispatcher rellena una elección, escribir un flag de origen en el
ledger (`preset_defaulted: true` / `method_source: "engine_default"` / `method_coerced`), o rechazar
como objeción mecánica. Reportar siempre el preset **efectivo**.

### F. Fallback determinista presentado como elección del agente en la SUPERFICIE  ⬛ ALTO
- **`src/agents/field_report.py:277-278`** — `render_field_report` imprime
  `"Selection (free, quality-aware): […]"` leyendo solo `selection['selected']`; **ignora
  `selection['fell_back']` y `selection['rationale']`** que sí existen (`:124-137`). Una selección de
  pozos hecha por el código se rotula como elección libre del analista.
- **`src/agents/analyst_loop.py:392, 438`** — un paso caído al default (`_default_next`) crea un nodo
  de grafo (`"step: <action>"`) **idéntico** a uno elegido por el agente, y el grafo sí se renderiza.
  Además `fell_back = steps_taken == 0`, pero `steps_taken` cuenta también los pasos default → un run
  donde el modelo devolvió vacío en TODOS los turnos y el default ejecutó los 5 pasos canónicos termina
  con `fell_back = False`: **un informe 100% determinista se reporta como análisis del agente.**

**Fix:** que la señal (`fell_back`, `rationale`, pasos-default vs pasos-agente) llegue a la superficie
del informe; redefinir `fell_back` como "el agente no aportó ninguna decisión propia".

### G. El código redacta interpretación/recomendación en renderers  🟨 MEDIO
- **`src/agents/report_template.py:635-654`** — sección `## Recommendations` **redactada por código**
  ("acquire Core…", "Priority — the dominant driver is X: acquire Y") y **forzada** en modo libre vía
  `_FREE_TAIL` (`report_compose.py:93`). *Atenuante:* solo recomienda adquirir datos de calibración
  (genérico, tipo riel de limitaciones), no decisiones de reservorio. Aun así usa voz de analista y
  título "Recommendations". **Fix:** reencuadrar como riel neutro ("Data gaps for calibration", hechos
  sin el imperativo "acquire"), o sacarla de `_FREE_TAIL` y que el agente decida.
- **`src/agents/report_template.py:558-566`** — nota interpretativa *"A near-constant BVW… suggests
  irreducible water (Buckles)"*. Es priming de libro insertado por código (sección opcional, no forzada).
  **Fix:** dejar solo el número; que el agente escriba el contexto de Buckles si aplica.
- **`src/agents/report_template.py:467-478`** — encabezado *"Lithology **interpretation**"* forzado, que
  imprime el `nearest` (ver D). **Fix:** bajar el tono a "Density-neutron crossplot lithology (engine output)".

---

## Borderline aceptables (señalizados — se dejan como están, con nota)
- **Cutoffs de net-pay** como defaults regionales (`params/regional_defaults.json`): interpretativos, pero
  llevan `provenance:"default"`, `gating/rules.py` los degrada a tier `bracketed` y emite
  `high_leverage_flag`. Señalización correcta. Confirmar que el agente puede sobreescribirlos vía `apply_cutoffs`.
- **`heuristic_section_plan`** (`report_compose.py:202-216`): compone un cuerpo completo cuando el agente
  falla, pero `analyst.py:232` marca el rationale "deterministic heuristic (analyst unavailable)" y ese
  texto sí llega al grafo. OK mientras ese nodo se renderice siempre.
- **Descriptores del registry** "(shaly sand)", "(old rocks)" (`registry.py`): son citas/nombres estándar
  de los modelos, no recomendación de uso en ESTE pozo. Aceptable; si se quiere máxima neutralidad, dejar
  solo la cita bibliográfica.
- **`graph.model`** guarda el modelo *pedido*, no el *usado* (`analyst.py:202`): hoy no se renderiza, pero
  conviene setear `graph.model = used` tras el cascade.

## Lo que está limpio (contraste)
`registry.available_methods` (filtra por curvas, sin ranking) · resúmenes `_run_*` neutros (número +
método + hash + `calibrated:False`) · `dispatch()` señala no-ejecutables · `writer.py`/`reviewer.py`/
`claim_verifier.py` (formato + rieles, sin dictar conclusiones) · `methodology_graph._numeric_literal_issues`
(gate que refuerza el invariante) · `select_wells` (filtro neutral) · `set_zone_of_interest` **no** está en
`_DEFAULT_ORDER` (el fallback nunca elige zona — solo el agente).

## Patrón raíz y prioridad de arreglo
1. **A + B + C** (prompts/observaciones enseñan la interpretación) — máxima prioridad: es donde el
   experimento se auto-contamina más directamente.
2. **D** (el digest entrega conclusiones) — quitar `nearest`, `gas_effect_flag`, el screen prospectivo.
3. **E + F** (defaults/fallback confundidos con elección del agente) — un flag de origen transversal en el
   ledger + que la señal llegue a la superficie.
4. **G** (voz de analista en renderers) — reencuadrar o mover al agente.

> **Nota honesta:** A, D (parcial) y E son andamiaje que se añadió deliberadamente para subir el
> desempeño (DV2-24, baseline por defecto que casualmente acierta en carbonato). Quitarlos casi
> seguro **bajará** la cifra de acierto — pero esa cifra es hoy en parte mérito del código, no del
> agente. Decidir qué quitar es una decisión de diseño del experimento, no mecánica.
