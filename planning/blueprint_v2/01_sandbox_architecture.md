# v2 · 01 — Arquitectura del sandbox

Cómo se materializa el "analista libre" sobre la infraestructura v1, preservando el invariante.
Hereda el diseño técnico de `planning/VISION_AGENTE_ANALISTA.md` y lo extiende a los dos modos,
el grafo de metodología y la evaluación por modelo.

## 1. Visión de capas

```
  ┌─ AGENTE (LLM, libre) ─────────────────────────────────────────────┐
  │  explora → decide qué métodos/secciones → emite plan + razón       │
  │  NUNCA calcula. Emite IDs de fórmula + args + justificación.        │
  └───────────────┬───────────────────────────────────────────────────┘
                  │ plan (JSON validado)
  ┌─ DISPATCHER (determinista) ───────────────────────────────────────┐
  │  valida contra whitelist+schema · ejecuta la fn vetada ·           │
  │  escribe número+provenance+result_hash al ledger · registra nodo   │
  │  en el GRAFO DE METODOLOGÍA                                        │
  └───────────────┬───────────────────────────────────────────────────┘
                  │ ledger enriquecido + grafo
  ┌─ GATES (deterministas) ───────────────────────────────────────────┐
  │  QC · validadores · consistencia cross-tool · abstención          │
  │  Guiado: OBLIGATORIOS (bloquean). Libre: ADVISORY (registran).     │
  └───────────────┬───────────────────────────────────────────────────┘
                  v
            render (plan-driven) + grafo de metodología + reviewer same-model
```

La inteligencia vive en la capa AGENTE (selección/composición); la honestidad vive en las capas
DISPATCHER (cada número de una tool probada) y GATES (control de calidad). El grafo de metodología
hace visible la frontera: registra qué decidió el agente y qué hizo el código.

## 2. La librería de fórmulas vetada (el "set completo")

El corazón del sandbox: para que la SELECCIÓN sea inteligencia y no relleno, el agente necesita un
menú **rico** de métodos probados por cada propiedad. v1 tiene un solo método por propiedad; v2 los
multiplica. Catálogo objetivo (detalle en `02_formula_library.md`):

| Propiedad | Métodos vetados que el agente puede elegir |
|---|---|
| Vsh | Larionov old-rocks, Larionov terciario, lineal (IGR), Clavier, Steiber |
| Porosidad | densidad, neutrón, densidad-neutrón, sónica (Wyllie/Raymer-Hunt-Gardner), PHIE efectiva (corrección shale) |
| Sw | Archie, Simandoux, Indonesia (Poupon-Leveaux), Waxman-Smits (si hay datos) |
| Litología | crossplot N-D, M-N, MID, PEF (si disponible) |
| Net pay | cutoffs configurables, multi-tier |

Cada método es una función pura golden-tested (como `calc_vsh`). El agente elige por **disponibilidad
de curvas + su análisis del dato** (ej.: "hay DT → puedo añadir porosidad sónica y M-N"; "roca sucia
→ Simandoux mejor que Archie"). Una tool `available_methods(curves)` le dice qué es aplicable; él decide.

## 3. El loop del agente (EXPLORE → DECIDE → DISPATCH)

Ubicación (igual que el informe de visión): un nodo agente en la arista `zonate → gating` del grafo
v1 — corre **una vez**, ve datos finales, precede a los gates. En **modo libre** el agente puede además
re-pedir cómputo del núcleo (elegir otro método de Sw y recomputar vía tool), porque ya no está atado a
la topología fija; en **modo guiado** parte del núcleo v1 ya calculado y solo añade.

```
EXPLORE  → tools de EDA deterministas pre-computadas (curve_inventory, crossplots,
           low_resistivity_scan…) → pre-digest COMPACTO al LLM (no el blob crudo: anti-vaciado)
DECIDE   → 1–2 turnos LLM emiten el plan: métodos a aplicar + secciones a incluir + razón de cada uno
DISPATCH → el orquestador valida y ejecuta cada tool; cada número → ledger (clave+hash);
           cada decisión → nodo del grafo de metodología
```

**Terminación**: `max_steps` determinista (default **2 turnos LLM**, en la config del run), impuesto por
el orquestador — el LLM no puede excederlo (test V2-E). **Pre-digest**: EXPLORE pre-computa el EDA y
pasa al LLM un digest compacto (**≤ ~800 tokens**, regla de selección: solo observaciones con flag
activo), nunca el blob crudo de curvas (anti-vaciado). **Recompute en modo libre**: un segundo DISPATCH
de otro método de núcleo (vía tool, capado por `max_steps`, reconciliado por el claim_verifier) — no es
matemática del LLM, es otra tool. Fallback en cascada señalizado (qwen3 → llama3.1 → heurística
determinista + banner "analyst unavailable"), nunca silencioso.

## 4. El grafo de metodología (la cadena de pensamiento)

Artefacto nuevo de v2, además del ledger. Un **DAG persistido** que captura el razonamiento del agente:

```json
{
  "methodology_graph": {
    "mode": "free", "model": "qwen3:30b-a3b", "model_digest": "sha256:ad8156...",
    "nodes": [
      {"id": "obs_1", "type": "observation", "depends_on": [],
       "payload": {"tool": "model_mismatch_nd", "finding": "roca sucia",
                   "source_ledger_key": "ledger:eda.litho"}},
      {"id": "dec_1", "type": "decision", "depends_on": ["obs_1"],
       "payload": {"rationale": "roca sucia -> Simandoux mejor que Archie",
                   "chosen": "sw_simandoux"}},
      {"id": "act_1", "type": "tool_call", "depends_on": ["dec_1"],
       "payload": {"tool": "sw_simandoux", "args": {"electrical_preset": "carbonate_default"},
                   "result_ledger_key": "ledger:sw_simandoux", "result_hash": "..."}},
      {"id": "sec_1", "type": "section", "depends_on": ["act_1"],
       "payload": {"section_id": "shaly_sand_saturation"}}
    ]
  }
}
```

- **Tipos de nodo**: observation (qué vio en el EDA), decision (qué decidió y por qué), tool_call
  (qué ejecutó), section (qué añadió al informe). Las aristas son `depends_on`.
- **Para qué**: (a) auditar la cadena de pensamiento; (b) reproducir/diffear runs; (c) **comparar
  modelos** — dos modelos sobre el mismo pozo producen grafos distintos, y ahí se ve quién analiza mejor.
- Se renderiza como una sección del informe (texto/mermaid) y se persiste en el ledger.

## 5. Gates por modo

Reutiliza los gates v1 (`gating()`, validadores, abstención, consistencia cross-tool) sin cambios de
lógica; cambia solo su **autoridad** según el modo:

- **Guiado**: si los gates disparan abstención u objeciones MECHANICAL, **bloquean** — el informe lleva
  banner de abstención y la composición se restringe a `ABSTENTION_SAFE` (no se rodea un núcleo que se
  abstiene con análisis confiado). Es v1 + agencia de composición acotada.
- **Libre**: los gates corren y se **registran** en el ledger y el grafo, pero **no bloquean** — el agente
  compone a voluntad. El informe muestra los flags de los gates como advertencias, y el reviewer los
  pondera al calificar. La honestidad pasa del bloqueo determinista a la **visibilidad** (grafo + flags).
  La **sección Metodología (grafo) es OBLIGATORIA en modo libre** — es el control de honestidad que
  reemplaza al bloqueo determinista (ver `03` §Render). El claim_verifier (reconciliación por clave, con
  tolerancia epsilon definida para redondeo en prosa) sigue corriendo en ambos modos.

## 6. Evaluación por modelo (reviewer same-model)

Cambio respecto a v1 (donde el reviewer era de otra familia para decorrelación). En v2 el reviewer es
**del mismo modelo** que el generador, y su rol es **calificar la calidad del informe** para poder
**puntuar el modelo**:

- Entrada: el informe + su grafo de metodología + el ledger.
- Salida: un **score estructurado** (p.ej. completitud, justificación de decisiones, uso apropiado de
  métodos, honestidad sobre límites) + objeciones.
- Como generador y revisor son el mismo modelo, el score mide la **auto-consistencia y capacidad del
  modelo** — base para un leaderboard por modelo (qwen3 vs llama3.1 vs futuros).
- Sigue siendo determinista el claim_verifier (reconciliación por clave de ledger): el scoring del LLM
  evalúa CALIDAD, no corrección numérica (eso lo garantiza el dispatcher).

## 7. Qué se reutiliza de v1 (no se reconstruye)

Motor petrofísico golden-tested · validadores independientes · `gating()`/abstención · renderer
determinista (`report_template.py`, ahora plan-driven) · ledger + provenance · claim_verifier (extendido
a reconciliación por clave) · cliente Ollama (extendido con timeout + fallback señalizado).
