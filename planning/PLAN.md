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

### Phase R4 — Métodos [MODELO] de profundidad + sus secciones
Done when: permeabilidad, derivados, electrofacies, rock typing y crossplots extra existen como tools seleccionables, cada uno respaldado por tool_result, con su sección opcional.
- [ ] src/petrophysics/permeability.py (Timur/Coates, MODELO con caveat "no calibrada, sin núcleo" — DV2-18)
- [ ] src/petrophysics/rock_quality.py (RQI/FZI/Winland)
- [ ] src/petrophysics/electrofacies.py (clustering no supervisado)
- [ ] Crossplots Hingle/Buckles/M-N (src/agents/log_plot.py)
- [ ] Registry + dispatch + renderers opcionales + golden tests

### Phase R5 — Informe de campo / multi-pozo (nativo v2) — REQUERIDO (DV2-18)
Done when: dado un set de LAS se produce un capítulo de campo (estadística cross-well sin sumas, correlación GR, mapa desde coordenadas del header, ranking). Diseño de experimento: 1 pozo fijo (ancla, todos los modelos lo analizan) + 2 pozos de libre elección del modelo.
- [ ] Nuevo src/agents/field_report.py (reconstruido) + figura de campo + mapa desde LAT/LON del header
- [ ] Selección 1-fijo + 2-libres (ancla determinista + elección del modelo)
- [ ] Tests de agregación (never-sum) + render + selección

### Phase R6 — Cablear el split [FIJO]/[MODELO] definitivo
Done when: `_MANDATORY_BODY` = [FIJO] acordados; `OPTIONAL_SECTIONS` + `OPTIONAL_REQUIRES` = [MODELO] con su tool de respaldo; modos respetan el split.
- [x] Reparto [FIJO]/[MODELO] fijado por el usuario (DV2-18, 2026-06-28)
- [x] Piso FIJO ya cableado en `_MANDATORY_BODY` (R2/R3)
- [ ] Agregar cada sección [MODELO] a `OPTIONAL_SECTIONS` + `OPTIONAL_REQUIRES` conforme R4 la construya
- [ ] Ampliar el catálogo del prompt del analista con las IDs nuevas (src/agents/analyst.py)

### Phase R7 — Verificación e2e + medición por modelo + docs
Done when: corrida e2e produce el informe completo ([FIJO] todas + [MODELO] elegidas con número real); el leaderboard mide profundidad por modelo; specs/manifest/PLAN actualizados.
- [ ] Métrica de profundidad en el leaderboard (src/evaluation/leaderboard.py)
- [ ] Regenerar informes de muestra; actualizar DECISIONS_V2/MANIFEST

## Conventions
- Cada fórmula nueva entra al registry SOLO con golden test (bounds, monotonía, caso analítico, NaN passthrough).
- Una sección [MODELO] aparece SOLO si existe su tool_result de respaldo (sin theater).
- Verificación obligatoria por fase: `pytest -q`, `mypy src/`, `ruff check .`, `ruff format --check .`.
