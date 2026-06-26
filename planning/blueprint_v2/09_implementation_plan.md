# v2 · 09 — Plan de implementación (de v1 congelado al sandbox)

Migración aditiva: cada fase deja el sistema funcionando y mantiene los 143 tests de v1 verdes.
Los **guardrails aterrizan ANTES que la agencia** (no se cablea el LLM hasta que la jaula
determinista que atrapa sus fugas esté probada). v1 queda intacto como baseline comparativa.

## Non-goals (verbatim del Charter v2)
- No se le permite al agente escribir/derivar matemática en runtime (libertad de selección, no de autoría).
- No se reemplaza v1 (congelado e intacto).
- No se promete que el modo libre sea más correcto (es más libre).
- No se exige LLM en la nube (local Ollama 16GB; degradar con gracia).

## Invariants (verbatim del Charter v2)
1. Todo número de una función probada de la librería; el LLM nunca produce un dígito.
2. El agente selecciona y compone; no autora matemática.
3. Cada informe emite un grafo de metodología trazable.
4. Guiado: gates obligatorios. Libre: gates advisory pero siempre corridos y registrados.
5. El reviewer de evaluación es del mismo modelo que el generador.

## Fases

### Fase V2-A — Librería de fórmulas vetada (amplía el motor) — DONE 2026-06-26
Done when: existen ≥2 métodos golden-tested por propiedad (Vsh, porosidad, Sw, litología) y una tool
`available_methods(curves)` que reporta cuáles son aplicables dado el set de curvas.
- Implementar Simandoux / Indonesia (Sw), porosidad sónica (Wyllie/RHG), Larionov terciario + lineal (Vsh)
  ya existentes o nuevos, M-N crossplot — todos como funciones puras con golden tests (`src/petrophysics/`).
- `available_methods(curves)` determinista (`src/petrophysics/registry.py`).

### Fase V2-B — Toolset EDA + grafo de metodología (esqueleto) — DONE 2026-06-26
Done when: `src/eda/` produce observaciones deterministas; existe el schema del grafo de metodología y se
persiste un grafo trivial (solo-obligatorias) en el ledger.
- Toolset EDA read-only golden-tested (`src/eda/explore.py`).
- Schema + persistencia del grafo de metodología (`src/agents/methodology_graph.py`); render mermaid/texto.

### Fase V2-C — Dispatcher + contrato + reconciliación por clave + consistencia cross-tool (sin LLM)  — DONE 2026-06-26
Done when: un plan JSON fabricado se valida, ejecuta tools de la whitelist, escribe número+hash al ledger
y nodos al grafo; el claim_verifier de campo flaggea un número 1.9%-off; la consistencia cross-tool levanta
MECHANICAL ante outputs contradictorios. Todo testeado sin modelo.
- `src/agents/tool_dispatch.py`; claim_verifier por clave de ledger; validador de consistencia en el harness.

### Fase V2-D — Pre-forma plan-driven + catálogo de secciones + los dos modos (heurística, sin LLM)
Done when: el render es plan-driven (numeración por orden de plan); el catálogo de secciones obligatorias/
opcionales existe; el pipeline corre en modo guiado (gates obligatorios) y libre (gates advisory) con un
`section_plan` producido por heurística determinista.
- Refactor `report_template.py` a plan-driven; `SECTION_CATALOG`; flag de modo en `run` (lo fija el
  invocador, no el LLM). La sección **Metodología es entrada OBLIGATORIA del catálogo en modo libre**.
- Restricción `ABSTENTION_SAFE` (guiado); gates advisory + visibilidad de flags (libre).
- `graph.validate()` corre como gate MECHANICAL (bloquea en guiado, advierte en libre) — ver `03` §Validación.

### Fase V2-E — Nodo agente con LLM (EXPLORE→DECIDE→DISPATCH) + fallback señalizado
Done when: el LLM produce el plan (métodos + secciones + razón) que alimenta el grafo de metodología; cae
con banner visible si falla; `analyst_trace`/grafo reproducibles mientras el modelo responda.
- Nodo agente en `zonate→gating`; wrapper de `client.py` (timeout, empty=fallo, cascada qwen3→llama3.1→heurística).
- **Contrato de nodos** (ver `03` §Quién escribe cada nodo): el LLM aporta SOLO nodos `decision` (IDs de
  fórmula + args + razón, sin números); el dispatcher escribe `observation`/`tool_call` (número+hash); el
  ensamblador escribe `section`. `max_steps` (default 2) lo impone el orquestador; test de que el LLM no lo excede.
- **Entregable**: sobre el mismo pozo Schaben, un informe **guiado** y uno **libre** con el mismo modelo,
  cada uno con su grafo de metodología (los 2 informes finales DV2-0 usan ambos modelos × este patrón).

### Fase V2-F — Reviewer same-model + scoring por modelo
Done when: un reviewer del mismo modelo califica el informe (score estructurado + objeciones) y el score se
persiste de forma comparable entre modelos; existe un comando para correr el mismo pozo con N modelos y
tabular sus scores.
- Reviewer same-model (`src/agents/reviewer.py` reorientado a scoring); tabla de evaluación por modelo.

### Fase V2-G — Tests en dos tiers + pineado del digest del modelo
Done when: los guardrails deterministas (dispatcher, reconciliación, consistencia, modos) están en el tier
CI-gating junto a los de v1; los tests model-in-the-loop están en un tier manual no-gating; el ledger pinea
el digest del modelo.
- Tier 1 determinista (fake chats); Tier 2 model-in-the-loop (golden de grafo, tolerancia semántica).
- Extender `provenance.pin_versions` con el **digest del modelo** Y la **versión del registry/librería de
  fórmulas** (`MethodSpec.version`), de modo que cada número trace a la versión exacta del método + modelo.

## Riesgos (del informe de visión, vigentes)
- Tool-calling local nunca ejercitado (qwen3/16GB, vaciado) → la cascada de fallback es condición de viabilidad.
- Reproducibilidad bit-exact del paso LLM no garantizable → se garantiza detectabilidad (grafo, empty_returns,
  digest) y reproducibilidad de los números (deterministas dadas las tool-calls).
- La agencia es selección sobre un menú vetado, no descubrimiento abierto — el techo honesto del modo libre.
- La exactitud sigue dependiendo de la calibración (VOLVE/core, NEEDS-HANDSON); v2 mejora composición e
  inteligencia, no exactitud.
