# petro-agent — Plan v2 (sandbox de analista → informe LAS-only completo)

> v1 está COMPLETO y fue purgado del repo (DV2-14); su detalle vive en el historial git y en
> `planning/blueprint_v2/`. Este es el plan v2 ejecutable: llevar el sistema desde el v2 mínimo
> (fases V2-A..G, hechas) hasta el informe definido en
> `planning/blueprint_v2/10_complete_report_spec.md` (36 capítulos LAS-only, [FIJO]/[MODELO]).

## Goal
Que un LLM local componga, seleccionando de una librería vetada y sin autorar matemática, un
informe petrofísico técnico completo derivable SOLO de archivos LAS — con piso obligatorio
comparable entre modelos y una zona libre que revele profundidad/creatividad.

## Stack
| Layer | Technology |
|---|---|
| Runtime | Python on WSL |
| LLMs (local) | Ollama — Qwen3:30b-a3b, Llama3.1:8b (cascada con fallback señalizado) |
| I/O · Numérico | lasio · numpy |
| Orquestación | LangGraph (determinista, no-LLM) |
| Trazabilidad | ledger JSON (config hash, digests, versiones) · Tests: pytest golden |

## Structure (claves para v2)
```
src/petrophysics/   librería vetada (vsh, phie, sonic, sw, netpay, volumetrics, lithology, registry)
src/agents/         analyst, tool_dispatch, methodology_graph, report_compose, report_template, reviewer
src/eda/            tools EDA read-only (digest numérico que lee el agente)
src/evaluation/     leaderboard + score por modelo
planning/blueprint_v2/  charter, arquitectura, librería, grafo, eval, spec 10, DECISIONS
```

## Non-goals (verbatim del blueprint v2)
- No se le permite al agente escribir/derivar matemática en runtime (libertad de selección, no de autoría).
- No se promete que el modo libre sea más correcto (es más libre).
- No se exige LLM en la nube (local Ollama 16GB; degradar con gracia).

## Invariants (verbatim del blueprint v2)
1. Todo número de una función probada de la librería; el LLM nunca produce un dígito.
2. El agente selecciona y compone; no autora matemática.
3. Cada informe emite un grafo de metodología trazable.
4. Guiado: gates obligatorios. Libre: gates advisory pero siempre corridos y registrados.
5. El reviewer de evaluación es del mismo modelo que el generador.

## Phases

### Phase R1 — Dispatch para todas las familias de métodos (COMPLETED)
Done when: el agente puede seleccionar y EJECUTAR métodos de porosity/vsh/lithology (no solo sw); cada tool_result lleva resumen numérico + hash; un método no ejecutable es objeción, no no-op silencioso.
- [x] Añadir `_run_porosity_method`, `_run_vsh_method`, `_run_lithology_method` (src/agents/tool_dispatch.py) (2026-06-28)
- [x] Presets de matriz/fluido sónico por ID vetado (`MATRIX_PRESETS`, src/petrophysics/registry.py) (2026-06-28)
- [x] Golden tests del dispatch por familia (tests/test_tool_dispatch.py) (2026-06-28)

### Phase R2 — Secciones [FIJO] renderer-only (el dato ya existe en el ledger) (COMPLETED)
Done when: el informe incluye las secciones 3,4,5,6,7,8,10.1,10.2,10.4,11,15,34 desde datos ya presentes, con degradación honesta si falta una curva.
- [x] 12 renderers nuevos: data_inventory, las_qc, standardization, curve_qc, data_prep, intervals, gr_analysis, resistivity_analysis, caliper_quality, lithology, rw, limitations (src/agents/report_template.py) (2026-06-28)
- [x] Ampliar `_MANDATORY_BODY` (9→21) + `_render_known` (src/agents/report_compose.py) (2026-06-28)
- [x] Tests de presencia + degradación honesta (tests/test_report_compose.py) (2026-06-28)

### Phase R3 — Fórmulas faltantes del catálogo 02 + golden tests (COMPLETED)
Done when: `vsh_clavier`, `vsh_steiber`, `phi_density`, `phi_neutron` existen, golden-tested, y entran al registry; hay comparación multi-método de Vsh (sección 13). `litho_mn` se difiere a R4 (crossplot [MODELO], requiere DT).
- [x] `vsh_clavier`, `vsh_steiber` (vsh.py); `phi_density`, `phi_neutron` (phie.py) + registry + dispatch (2026-06-28)
- [x] `vsh_method_comparison` + sección `_vsh` (spec 13) cableada en modo fijo (2026-06-28)
- [x] Golden tests por método + test de la sección de comparación (2026-06-28)
- ~~litho_mn~~ (diferido a R4: crossplot [MODELO], requiere DT)

### Phase R4 — Métodos [MODELO] de profundidad + sus secciones (COMPLETED)
Done when: permeabilidad, derivados, electrofacies, rock typing y crossplots extra existen como tools seleccionables, cada uno respaldado por tool_result, con su sección opcional.
- [x] src/petrophysics/permeability.py (Timur/Coates, MODELO con caveat — DV2-18) (2026-06-28)
- [x] src/petrophysics/rock_quality.py (RQI/FZI/Winland) (2026-06-28)
- [x] src/petrophysics/electrofacies.py (k-means numpy determinista) (2026-06-28)
- [x] Registry + dispatch (familias permeability/rock_quality/facies) + secciones opcionales + golden tests (2026-06-28)
- [x] Crossplots Hingle + Buckles + distribuciones (src/agents/log_plot.py) (2026-07-01)
- ~~Crossplot M-N~~ (diferido: necesita DT, ausente en Schaben)

### Phase R5 — Informe de campo / multi-pozo (nativo v2) — REQUERIDO (DV2-18) (COMPLETED)
Done when: dado un set de LAS se produce un capítulo de campo (estadística cross-well sin sumas, correlación GR, mapa desde coordenadas del header, ranking). Diseño de experimento: 1 pozo fijo (ancla, todos los modelos lo analizan) + 2 pozos de libre elección del modelo.
- [x] Nuevo src/agents/field_report.py + field_map_plot (LAT/LON ahora extraído por el loader) (2026-06-28)
- [x] Selección 1-fijo + 2-libres (`select_wells`) (2026-06-28)
- [x] Tests de agregación (never-sum) + render + selección (2026-06-28)

### Phase R6 — Cablear el split [FIJO]/[MODELO] definitivo (COMPLETED)
Done when: `_MANDATORY_BODY` = [FIJO] acordados; `OPTIONAL_SECTIONS` + `OPTIONAL_REQUIRES` = [MODELO] con su tool de respaldo; modos respetan el split.
- [x] Reparto [FIJO]/[MODELO] fijado por el usuario (DV2-18, 2026-06-28)
- [x] Piso FIJO cableado en `_MANDATORY_BODY` (R2/R3 + Porosidad/Sw) (2026-06-28)
- [x] Secciones [MODELO] en `OPTIONAL_SECTIONS` + `OPTIONAL_REQUIRES` (shaly/sonic/permeability/rock_quality/electrofacies) (2026-06-28)
- [x] Catálogo de secciones opcionales expuesto al prompt del analista (src/agents/analyst.py) (2026-06-28)

### Phase R7 — Verificación e2e + medición por modelo + docs (COMPLETED)
Done when: corrida e2e produce el informe completo ([FIJO] todas + [MODELO] elegidas con número real); el leaderboard mide profundidad por modelo; specs/manifest/PLAN actualizados.
- [x] Métrica `depth_backed` (secciones [MODELO] respaldadas) en objective_score + leaderboard (2026-06-28)
- [x] E2E determinista: modelo elige Simandoux+permeabilidad+rock_quality+electrofacies → 4 secciones con número real, depth_backed=4, claim_verifier PASS (2026-06-28)
- ~~Regenerar los 2 informes de muestra con Ollama~~ (discarded 2026-07-07: superado por los informes finales v14/opus publicados en docs/reports/; el proyecto cerró con el veredicto R15)

### Phase R8 — Auditoría y remediación de fuga de interpretación (COMPLETED)
Done when: ninguna superficie código→agente orienta el análisis (zona, método, litología, conclusión); base-por-fallo siempre señalada en superficie; completitud medible separando piso [código] de contribución interpretativa [agente]; congelado por tests.
- [x] Auditoría de 7 focos de fuga en 5 ciclos (planning/auditoria_fuga_interpretacion.md) (2026-07-01)
- [x] Quitar playbook overburden→zona + regla Vsh→shaly-sand + ejemplo trabajado (analyst_loop.py, analyst.py, loop_actions.py) (2026-07-01)
- [x] Digest solo materia prima: fuera nearest/gas_effect/low-res-pay-screen (eda/explore.py) (2026-07-01)
- [x] Señalar defaults de preset/método (preset_defaulted, method_source, method_coerced) (tool_dispatch.py, loop_actions.py) (2026-07-01)
- [x] Fallback visible en superficie: field_report label + fell_back=agent_steps==0 (field_report.py, analyst_loop.py) (2026-07-01)
- [x] Renderers sin voz de analista: Data gaps, sin nota Buckles, litología por shares (report_template.py) (2026-07-01)
- [x] Métrica de dos cubos free_floor_ids + completeness_breakdown (report_compose.py, report_score.py) (2026-07-01)
- [x] Test anti-relleno + anti-interpretación (tests/test_completeness_and_filler.py) (2026-07-01)
- [x] Experimento 3 modelos post-fix: zona=None sin guía (nemotron free + gpt-5); 28/37 = piso [código], destreza [MODELO] del agente ~0 (2026-07-01)

### Phase R9 — Informe de campo navegable + track de visión + set de figuras (COMPLETED)
Done when: el informe de campo enlaza a informes por-pozo que existen; un modelo con visión puede leer las figuras CUALITATIVAMENTE (sin números); el set de figuras cubre logs/crossplots + incertidumbre, separando figuras vision-eligible de numéricas human-only.
- [x] `render_field_report` enlaza cada pozo a `report_<uwi>.md` + `well_report_filename` (field_report.py) (2026-07-01)
- [x] Fuga "Best reservoir quality" → "Highest net-to-gross" (ranking factual) (field_report.py) (2026-07-01)
- [x] Track de visión: `make_vision_chat` (client.py) + `examine_figures` con guardarraíl cualitativo (loop_actions.py) + gate en analyst_loop; test con fakes (2026-07-01)
- [x] Figuras vision-eligible: buckles, hingle, distributions (log_plot.py) (2026-07-01)
- [x] Figuras human-only post-loop: tornado + MC distribution (excluidas de visión); `montecarlo` expone realizations (2026-07-01)

### Phase R10 — Calibración demostrada vs VOLVE (Fase 8, "demostrable") (COMPLETED)
Done when: se mide la calibración de la confianza contra ground-truth público (VOLVE CPI de Equinor); si está sobreconfiada, se corrige y se re-demuestra la cobertura.
- [x] Descarga VOLVE 15/9-F-11A (crudo + CPI Equinor VSH/PHIF/SW) — data/volve/ (gitignored) (2026-07-01)
- [x] Motor congelado vs CPI: VSH r=0.96, PHIE r=0.91, SW r=0.87 (debug/dbg_volve_compare.py) (2026-07-01)
- [x] Hallazgo: bandas P10-P90 sobreconfiadas (cobertura 2-35% vs nominal 80%) — solo propagaban parámetros (2026-07-01)
- [x] Fix: `build_method_alts` + `propagate_net_pay` muestrea alternativas de método (Vsh/PHIE) → incertidumbre estructural (montecarlo.py, cableado en loop_actions + graph) (2026-07-01)
- [x] Re-demostrado: cobertura 88-98% (VSH 95%, PHIE 98%, SW 88%) — banda calibrada (2026-07-01)
- [x] Fase 8: AGENTE e2e sobre LAS real de VOLVE (loader→params north-sea→motor→loop→reporte); narrativa descartada (2026-07-01)

### Phase R11 — Pulido post-validación + generalización de calibración (COMPLETED)
Done when: se corrigen los glitches destapados por VOLVE/v5 (provenance del grafo, §14 Vsh selected, unidad de profundidad JWLF) y se mide la generalización de la calibración en más pozos.
- [x] Generalización calibración: 4 pozos VOLVE (F11A/F1A/F4/F5) — PHIE 98% + SW 92% generalizan; VSH 65% NO (banda solo Larionov-GR) (2026-07-01)
- [x] Edge de profundidad JWLF: DEPTH en "0.1 in" vs "M" — normalizado a metros en el harness de calibración (2026-07-01)
- [x] Fix #4 §14 Vsh "Selected" vacío: fallback `vsh_larionov_{variant}`→`_old_rocks` no matcheaba la clave `_old`; mapeo correcto + test (loop_actions.py) (2026-07-01)
- [x] Fix #3 provenance del grafo: `result_ledger_key` apuntaba a `ledger:<action>` (nunca clave real); mapa acción→clave real + observaciones sin clave (analyst_loop.py, tool_dispatch.py) + test (2026-07-01)
- ~~Narrativa VOLVE vs Final Well Report~~ (descartado: sin informe narrativo público que comparar)
- [x] `vsh_neutron_density` (indicador de arcilla NO-GR) formalizado: función vetada + golden tests + banda (build_method_alts) + §14; VSH cobertura 65%→71% (parcial: CPI usa multi-mineral) (2026-07-01)
- [x] `multi_seed_robustness` cableado al ledger + §19 del reporte (loop + guiado) + test; confirmado en el pipeline de VOLVE (2026-07-01)
- [x] Fase 8 e2e: pipeline determinista + agente completo sobre LAS real de VOLVE (region north_sea_jurassic) → reporte (2026-07-01)
- [x] `vsh_neutron_density` ahora SELECCIONABLE por el agente: registrado en METHOD_REGISTRY (available_methods) + dispatch en vsh_step (loop) y _run_vsh_method (guiado) + tests (2026-07-01)
- [x] Loader: flip de profundidad invertida (deepest-first) + unidades pulgada/0.1-in — 198/198 Schaben cargan (era 197); + test (src/io/loader.py) (2026-07-01)
- [x] VSH multi-mineral: `vsh_multimineral` (solve 2-mineral matriz+arcilla+porosidad desde RHOB+NPHI) formalizado — función vetada + golden tests + registry (seleccionable) + 2 dispatchers + banda + §14. Cobertura VSH 72%→**79%** (nominal 80%); las 3 propiedades calibradas (VSH 79 / PHIE 99 / SW 95) (2026-07-01)

### Phase R12 — Subir la destreza [MODELO] del agente (sin fugar) (COMPLETED) — medido: la destreza es model-bound; sin ganancia de opcionales ni en frontier
Done when: `interpretive_choices` sube como destreza REAL (respaldada por número, no relleno) sin reintroducir fuga; medido y re-auditado. Baseline: ~1 choice/pozo, 0 opcionales (v3/v4/v5).
- [x] A1 — Reencuadrar `_LOOP_SYSTEM`: "baseline ya computado" → invitar a componer el análisis completo que el dato justifique (meta, no interpretación) (2026-07-01)
- [x] A2 — Afordances neutras: catálogo de opcionales con qué computa + curvas requeridas (factual) en `observation_text` (`_OPTIONAL_DESC`) (2026-07-01)
- [x] A3 — Re-auditar los strings cambiados contra el invariante de 7-focos (los 3 cambios son meta/factual, sin fuga) (2026-07-01)
- [x] B — Self-critique step neutral antes de `finish` (`_completeness_critique`: opcionales aplicables no añadidos + métodos en default), one-shot (2026-07-01)
- [x] C — Evaluación A/B (NEW r12 vs OLD pre-r12): A/B local qwen3:30b hecho → invariante-seguro, sin daño al informe (tool_results vacío ambos), pero SIN ganancia de destreza (esperado: destreza es model-bound, DV2-22). Validación de nube HECHA (2026-07-02, leg PAID de v7: gpt-5/opus-4.8/deepseek-r1/qwen3-max): el perfil persiste incluso en frontier — 1 interpretive choice/pozo, 0 opcionales, sin zona (opus se involucra más: 10-12 pasos + examine_figures, pero tampoco añade opcionales). Y es seed-invariante (v7_random_seed): la identidad analítica es del modelo, no del muestreo (2026-07-02)
- [x] Guardarraíl: cada cambio re-auditado; anti-filler + 3 tests nuevos del critique verdes; medido en Ollama local (2026-07-01)

### Phase R13 — Crítico auto-adversarial same-model (nudge de un disparo al finish) (COMPLETED)
Done when: al pedir `finish`, el MISMO modelo hace un pase escéptico que intenta refutar las ELECCIONES del analista (método/zona/opcionales/conclusiones, nunca los números) usando la evidencia del ledger; sus objeciones se le devuelven una vez y reconsidera; determinista el orquestador (LLM no decide compuertas), sin cruzar modelos ([[no-cross-model-critic]]).
- [x] `_skeptic_pass` + `_choices_digest` + `_skeptic_evidence` + `_parse_objections` en analyst_loop.py: pase same-model que refuta elecciones (meta, no dirige; no toca números) (2026-07-01)
- [x] `_finish_review` integra `_completeness_critique` + `_skeptic_pass` en el manejo de `finish` (ambos one-shot vía flag `reviewed`, sin loop) (2026-07-01)
- [x] Guardarraíl anti-fuga: `_SKEPTIC_SYSTEM` cuestiona ("¿lo justifica el dato?"), no prescribe método/conclusión; re-auditado vs 7-focos — sin fuga (2026-07-01)
- [x] Tests deterministas (4): dispara ≤1 vez, surface de objeciones alcanza al agente, reconsidera, no bloquea terminación; +unit de `_skeptic_pass`/`_finish_review` (2026-07-01)

### Phase R14 — Flip "autor, no revisor" (modo free; guided intacto como control A/B) (COMPLETED) — el techo ERA el entorno: 1→7 choices/pozo en free
Done when: en modo autor el pass-0 es solo descriptivo, el agente autora la interpretación (zona → método por propiedad con evidencia numérica del motor → cierre de cadena), el gate/abstención se computa post-loop sobre la cadena FINAL (cierra el banner stale), y el A/B v7↔v8 mide si el techo de destreza era del entorno. Rama: `feature/r14-author-mode`. Invariante intacto: el motor computa todo número; los fallbacks deterministas siguen midiendo (`default_steps`/`fell_back`/`reclosed_steps`).
- [x] R14-A `sw_method_comparison` (sw.py, golden tests) + `sw_summary.methods` en `_exec_sw` + tabla en `_sw` + observación read-only `compare_methods` (vsh/porosity/sw) con re-audit de fuga (2026-07-02)
- [x] R14-B provenance/scoring: `method_source` en `_exec_vsh`; tupla de `completeness_breakdown` amplía a vsh; keys aditivas `authored_core`/`core_methods_defaulted`; `_vsh` deja de hardcodear "engine's selection" (2026-07-02)
- [x] R14-C `run_descriptive_pass` (graph.py, hermana de run_pipeline) + `emit_descriptive` (stages.py, params helper compartido) + `generate_descriptive_figures` raw (log_plot.py) + tests/test_descriptive_pass.py; run_pipeline byte-idéntico (2026-07-02)
- [x] R14-D `src/orchestrator/finalize.py`: re-valida + `gate_decision` compartido con stages.gating + figuras + persist sobre la cadena FINAL; regresión banner-stale en tests/test_finalize.py; verificar semántica DID_NOT_CONVERGE contra ledgers v7 (2026-07-02)
- [x] R14-E loop autor: kwarg `author`, `_LOOP_SYSTEM_AUTHOR` (auditado 7 focos), salta `seed_baseline_sections`, `vsh` en stale_or_pending; tests/test_analyst_loop_author.py (scripted authored_core==3; modelo-basura → reclose + fell_back) (2026-07-02)
- [x] R14-F driver `debug/gen_field_report_v8_author.py` + smoke local + batch free en `outputs/v8` + lectura A/B vs v7 en bitácora (leg de pago solo con OK del usuario) (2026-07-02)

### Phase R15 — Ciclo final: condiciones naturales del ingeniero (GA+GB+GC+GD) (COMPLETED) — veredicto: la metodología + thinking produce zonificadores profundos en 4 familias de modelos
Done when: el agente trabaja con las condiciones de un ingeniero real (memoria intra-ciclo, memoria entre pozos, hipótesis, consecuencia, borradores, thinking), cada palanca con golden tests y medida en batch; veredicto final y calibración junior/senior en bitácora. Rama: `experiment/claude-analyst`.
- [x] GA: field pack (src/eda/field_study.py) + evidence_efficiency/request_tool + validate_choice + field notes cross-well + brief regional con doble gate anti-fuga (2026-07-04)
- [x] GB: journal de observaciones (repeticiones = no-ops medidos; mató ~80% de relecturas) + digest de análisis cross-well + brief solo-identidad + rw_evidence/mhi_scan + bins finos profundos (2026-07-05)
- [x] GC: interval_stats + objection_profile + reintento con el propio fracaso (publica SIEMPRE el intento 2) + review_attempts (2026-07-05)
- [x] GD: revise_narrative — el escritor relee su borrador renderizado; el verifier rechaza revisiones con números sin respaldo (src/agents/writer.py) (2026-07-05)
- [x] Cliente: `make_chat(reasoning=True)` — thinking opt-in OpenRouter; los nemotron híbridos corrían apagados (src/agents/client.py) (2026-07-06)
- [x] Summit v3 (72/72 verifier PASS): sp_rw (banda 0.041–0.054 confirma el default 0.04) + mhi + gross/NTG sobre la ventana analizada (2026-07-04)
- [x] Medición final: iterate15 (la iteración amplifica lo que el modelo es) + matriz v13↔v14 free/pago × thinking + calibración junior/senior — bitácoras 2026-07-04/05/06 (2026-07-06)

### Phase R16 — Vara del summit, ciclo 1: sensibilidad numérica de las ventanas
Done when: `debug/dbg_vara_sensitivity.py` recalcula precisión/cobertura de zona y el leaderboard bajo perturbaciones de las ventanas del summit (shift ±50 m y ±100 m; bordes contraídos/expandidos 10%) para cada corrida de config final (v12–v14: opus, glm, gpt-5, ultra-think, super, qwen-thinking reconstruido), y `planning/specs/verificacion-vara-summit.md` §1 presenta las tablas por escenario con un veredicto explícito de estabilidad del ranking. Todo determinista (numpy/json sobre outputs/ existentes) — CERO LLM en el análisis.
- [ ] `debug/dbg_vara_sensitivity.py`: cargar ventanas del summit (`outputs/claude_report/wells_metrics.json`, campo `zone`) y las corridas finales reutilizando la lógica de carga de `debug/dbg_final_evaluation.py` (incluida la reconstrucción de qwen-thinking desde run.log)
- [ ] Implementar los escenarios de perturbación y recalcular por agente: zona-profunda (tope ≥700 m), precisión/cobertura de solape mediana, y posición en el ranking por escenario
- [ ] Crear `planning/specs/verificacion-vara-summit.md` con §0 (propósito: la vara es baseline declarado, no verdad de terreno) y §1 (tablas + veredicto de estabilidad: qué cambia y qué no con la vara temblando)

### Phase R17 — Vara del summit, ciclo 2: refutación determinista de los bordes
Done when: para cada pozo usado en las comparaciones finales, los criterios físicos de borde se recomputan desde el LAS crudo (`data/`, vía lasio/numpy: primer tramo con RHOB sostenido >2.35 g/cc en ventana móvil de 50 m, y última profundidad con curvas válidas) y cada borde de ventana del summit queda clasificado `defendido` / `débil` con su ventana alternativa defendible cuando aplique; resultados en §2 del spec. Sin tocar `src/` y sin LLM: el "adversario" es el criterio físico recomputado, no una relectura.
- [ ] `debug/dbg_vara_refute.py`: para los pozos comparados (los de las corridas v12–v14), recomputar desde el LAS el tope de roca consolidada (RHOB sostenido >2.35 g/cc) y la base con datos válidos, y contrastar contra `zone.top_m`/`zone.bottom_m` del summit
- [ ] Clasificar cada borde (defendido si |delta| ≤ 50 m; débil si >50 m) y derivar la ventana alternativa anclada al criterio físico para los débiles
- [ ] Escribir §2 del spec con la tabla pozo a pozo (borde summit vs borde físico vs delta) y el veredicto por pozo

### Phase R18 — Vara del summit, ciclo 3: peor caso combinado y veredicto
Done when: `debug/dbg_vara_worstcase.py` recalcula el leaderboard completo usando como vara las ventanas alternativas más hostiles que sobrevivieron R16+R17 (por pozo: la física de R17 si difiere, y el peor escenario de R16), y §3 del spec responde explícitamente: (1) ¿opus sigue 4/4 zonas y primero?, (2) ¿la conclusión "metodología+thinking → zonificadores profundos en 4 familias" aguanta?, (3) ¿qué cifras del informe de evaluación deben re-enunciarse con banda en vez de punto? Resumen ejecutivo al tope del spec.
- [ ] `debug/dbg_vara_worstcase.py`: construir la vara hostil combinada (R17 física por pozo + peor escenario R16) y recalcular precisión/cobertura/ranking finales
- [ ] Escribir §3 del spec (veredicto a las 3 preguntas) + resumen ejecutivo en §0
- [ ] Registrar el ciclo en `planning/bitacora/2026-07-07.md` (sección nueva, con errores y hallazgos)

## Conventions
- Cada fórmula nueva entra al registry SOLO con golden test (bounds, monotonía, caso analítico, NaN passthrough).
- Una sección [MODELO] aparece SOLO si existe su tool_result de respaldo (sin theater).
- Verificación obligatoria por fase: `pytest -q`, `mypy src/`, `ruff check .`, `ruff format --check .`.
