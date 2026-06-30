# v2 · 11 — Bucle agente (observar→decidir→computar→observar)

El informe se genera mediante un **bucle continuo**: el agente ve los datos que el motor
calcula y, a medida que construye el informe, decide el siguiente paso. Reemplaza el diseño de
"un disparo" (`run_analyst`). Resuelve la incompatibilidad de fondo: **no le damos el pipeline
de interpretación armado — el pipeline EMERGE de las decisiones del agente, reaccionando al
dato real**, pero el LLM nunca calcula (cada paso lo computa el motor).

## Invariante (sin cambios)
Todo número viene de función vetada; el LLM **selecciona el método/acción y compone**, nunca
calcula ni autora matemática. El **orquestador es dueño del loop y de la terminación** — el LLM
nunca decide saltarse el QC ni cuántos pasos correr.

## El loop (lo posee el orquestador determinista)
```
run_analyst_loop(ctx, ledger, mode, chat, model, max_steps=12):
  # Pasada 0 (determinista, NO interpretación): data prep ya hecha (carga, QC, máscaras, EDA)
  graph = MethodologyGraph()
  for step in range(max_steps):
      actions = available_actions(ledger)          # frontera VÁLIDA por física (ver §Prereqs)
      obs     = observation_text(ledger, actions)  # resumen compacto del estado + acciones
      raw     = chat(_LOOP_SYSTEM, obs)            # el agente elige UNA acción (o FINISH)
      action  = parse_action(raw, actions)         # validado contra la whitelist de acciones
      if action is FINISH or action is None: break
      result  = execute_step(action, ctx, ledger)  # el motor computa UNA cosa → actualiza ledger
      graph.add(observation, decision, tool_call)  # un nodo por paso = traza real de razonamiento
  ledger["run"]["analyst_loop"] = {steps_taken, finished_by_agent, hit_max_steps}
  return compose_from_ledger(ledger, graph, mode)
```

## Espacio de acciones (lo que el agente puede elegir en cada paso)
Cada acción = una herramienta determinista. Categorías:
- **Computar propiedad primaria** (con método elegido):
  `compute_vsh(method)` · `compute_phie(method)` · `compute_sw(method, electrical_preset)`
- **Pago**: `apply_cutoffs(cutoff_preset)` → net sand/reservoir/pay · `run_uncertainty()` (Monte Carlo)
- **Análisis opcionales**: `permeability(method)` · `rock_quality(index)` · `electrofacies(k)` ·
  `lithology()` · `sonic_porosity(method)`
- **Observación** (solo lectura — dato de zona, distribución o puntual, nunca el array crudo):
  `histogram(curve)` / `percentiles(curve_or_property)` · `zone_stats()` (resumen por zona) ·
  `value_at(curve, depth)` / `extremes(curve)` · `crossplot_density_neutron()` · `low_resistivity_scan()`
- **FINISH** — terminar y ensamblar.

## Prerrequisitos físicos (el orquestador los impone vía `available_actions`)
La física no es elección. `available_actions(ledger)` devuelve solo lo válido dado lo computado:
- `compute_phie` requiere `vsh` ya computado (corrección de arcilla).
- `compute_sw` requiere `phie`.
- `apply_cutoffs`/net pay requiere `sw`.
- `permeability`/`rock_quality` requieren `phie`+`sw`.
- `run_uncertainty` requiere net pay.
El agente elige el **método y el orden dentro de la frontera válida**; no puede romper la cadena.

## Qué observa el agente cada paso (granularidad de dato — REGLA)
El agente **nunca ve datos masivos** (el array crudo a resolución completa, millones de muestras,
ni imágenes). **Sí puede ver y pedir** (como un analista real):
- **Datos de zona**: resúmenes por intervalo (zona X: top/base, espesor, media de PHIE/Sw/Vsh).
- **Distribuciones**: histogramas, percentiles (P10/P50/P90), media/mediana/rango, conteos de flags.
- **Datos puntuales**: el valor de una curva/propiedad a una profundidad concreta, o el extremo
  (máx/mín) y dónde ocurre.

El digest base de cada paso (texto compacto) lleva: propiedades ya computadas (método + media +
flags), curvas disponibles, hallazgos EDA (badhole %, low-res, litología), qué falta, y la lista
de **acciones válidas ahora**. Si el agente quiere más detalle, lo pide con una **acción de
observación** (zona / distribución / punto) — que devuelve dato resumido, nunca el array crudo.

## Pasos de cómputo (decomposición de `stages.compute()`)
El loop computa propiedad por propiedad usando el estado acumulado, reusando las funciones
petrofísicas vetadas:
- `compute_vsh(method)` → `_vsh_by_method(...)` (ya existe, R-método) → `ledger.vsh`
- `compute_phie(method)` → `calc_phie(rhob,nphi,…,vsh)` / `phi_density` / `phi_neutron` → `ledger.phie`
- `compute_sw(method,preset)` → `calc_sw` / `sw_simandoux` / `sw_indonesia` → `ledger.sw`
- `apply_cutoffs(preset)` → `apply_cutoffs` + zonación → net pay
- `run_uncertainty()` → `propagate_net_pay` + `sensitivity_net_pay`
- opcionales → los runners ya existentes en `tool_dispatch`
**Garantía de no-regresión:** el modo GUIADO sigue usando `stages.compute()` (la cadena
monolítica, idéntica). El loop usa pasos discretos que llaman a las MISMAS funciones; un golden
test verifica que "loop con la secuencia default" == "guiado" (mismos números).

## Terminación (orquestador)
- El agente emite `FINISH`, **o** se alcanza `max_steps` (techo, default 12), **o** no quedan
  acciones útiles. Se registra `steps_taken`, `finished_by_agent`, `hit_max_steps` (honesto).
- Fallback señalizado: si el modelo se vacía/da basura en un paso, ese paso cae a la acción
  determinista por defecto (la siguiente del orden canónico) y se marca — el loop no se cuelga.

## El informe emerge del ledger acumulado
Las secciones corresponden a lo que el agente computó (sección presente ⇒ número real, ya es el
invariante). `compose_from_ledger` arma: prep+rieles forzados (DV2-19) + las secciones que el
agente fue construyendo, en su orden. El **grafo de metodología es la traza paso-a-paso real**
(un nodo por decisión), no un único nodo de decisión.

## Modos
- **Libre** = el loop (el agente conduce).
- **Guiado** = secuencia determinista completa (el `stages.compute()` actual + piso fijo) —
  baseline comparable, sin LLM en el loop. Así los dos experimentos miden cosas distintas.

## Costo y control
- N llamadas al LLM por informe (una por paso). Con modelos locales lentos: ~12 llamadas. Lento
  pero factible. `max_steps=12` (medio), seed pineado, decoding determinista.
- Cascada de fallback por paso (qwen3→llama3.1→default determinista), siempre señalizada.

## Archivos a tocar
- Nuevo `src/agents/analyst_loop.py`: el loop + `observation_text` + `parse_action` +
  `available_actions`.
- Nuevo `src/agents/steps.py`: pasos de cómputo discretos (vsh/phie/sw/cutoffs/uncertainty) que
  producen arrays reusando `petrophysics/*` (decomposición de `stages.compute`).
- `report_compose`: `compose_from_ledger` ya casi está (secciones gated por dato); ajustar orden.
- `methodology_graph`: nodos por paso (ya soporta el schema).
- Tests: loop determinista con fake chat (decisiones scripteadas); enforcement de prereqs;
  techo `max_steps`; terminación; **no-regresión loop-default == guiado**.

## Riesgos
- Decomponer `compute()` sin romper el comportamiento congelado → golden test de equivalencia.
- Calidad del modelo local: decisiones pobres o loops improductivos → `max_steps` + acciones
  válidas acotan; un paso inválido cae al default.
- Lentitud: ~12 llamadas/informe.

## Fases de construcción (sugerido)
1. `steps.py` (pasos discretos) + golden test loop-default == guiado (sin LLM aún).
2. `available_actions` (frontera por física) + tests de prereqs.
3. `analyst_loop` con fake chat (loop determinista scripteado) + max_steps/terminación.
4. Prompt `_LOOP_SYSTEM` + `observation_text` + integración con modelo real; medir.
5. `compose_from_ledger` desde el ledger acumulado + grafo paso-a-paso.
