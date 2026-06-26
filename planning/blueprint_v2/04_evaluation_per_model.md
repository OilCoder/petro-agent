# v2 · 04 — Evaluación por modelo (reviewer same-model + leaderboard)

Cómo se mide **qué tan buen analista es un modelo**. Cambio clave respecto a v1: el reviewer ya no es
de otra familia (decorrelación), sino del **mismo modelo** que el generador — porque el objetivo dejó
de ser cazar fallos y pasó a **puntuar la capacidad del modelo** de forma comparable.

## Dos capas de evaluación

| Capa | Quién | Qué mide | Determinista |
|---|---|---|---|
| **Objetiva** | código sobre el grafo de metodología + ledger | cobertura de exploración, métodos elegidos, profundidad del razonamiento, completitud estructural, honestidad (¿respetó la abstención?) | SÍ |
| **Cualitativa** | reviewer LLM del MISMO modelo | calidad de la justificación, pertinencia de los métodos, coherencia narrativa | NO (juicio del modelo) |

La separación es deliberada: la corrección de los números la garantiza el dispatcher (no se evalúa
aquí); el score mide **análisis y composición**, no aritmética. **Solo las objeciones MECHANICAL del
dispatcher/`validate()` bloquean en modo guiado; las objeciones del reviewer LLM se reportan, nunca
bloquean ningún gate** (son evaluación, no control de calidad).

## Métricas objetivas (del grafo + ledger, deterministas)

```python
# src/evaluation/report_score.py
def objective_score(ledger) -> dict:
    return {
      "exploration_coverage": used / available,        # observaciones atendidas / disponibles
      "methods_selected": n,                            # nº de métodos vetados invocados
      "optional_sections": n,                           # secciones opcionales añadidas con justificación
      "reasoning_depth": dag_longest_path,              # cadena de decisión más larga
      "decisions_justified": n_nonempty_rationale / n_decisions,
      "honesty_ok": bool,                               # ver nota: se computa en AMBOS modos
      "invariant_clean": claim_verifier_passed,         # cero números fuera de ledger
    }
```
Estas son comparables entre modelos sin sesgo (las calcula código, no un LLM).

> **`honesty_ok` en modo libre.** Como en modo libre la abstención no se impone, `honesty_ok` se
> computa deterministamente desde el grafo + los flags de los gates (registrados aunque advisory):
> es `False` si el informe **rodea un núcleo flaggeado de abstención con secciones confiadas**
> (Pickett, BVW, etc.) sin reconocer el flag. Se calcula igual en ambos modos — mide honestidad de
> composición, no si el gate bloqueó. Tarea V2-F.

## Métrica cualitativa (reviewer same-model)

```python
# src/agents/reviewer.py  (reorientado de "adversarial" a "scorer")
SCORE_SCHEMA = {
  "completeness": 1-5, "method_appropriateness": 1-5,
  "decision_quality": 1-5, "honesty": 1-5, "narrative": 1-5,
  "objections": [...]   # cualitativas, ADVISORY — NO alimentan ningún gate bloqueante
}
# Los scores 1-5 son METADATA sobre el modelo (evaluación), NO números del cuerpo del
# informe: quedan fuera de Invariant 1 y de la reconciliación del claim_verifier.
def score_report(report, methodology_graph, ledger, chat_same_model) -> dict
```
El reviewer recibe informe + grafo + ledger y devuelve el score estructurado. Como generador y
revisor son el mismo modelo, el resultado mide la **auto-evaluación/capacidad del modelo**.

> Sesgo conocido y aceptado: un modelo evaluándose a sí mismo tiende a ser indulgente. Por eso la
> capa objetiva (determinista, insesgada) es el ancla del leaderboard; el score cualitativo es
> complementario y se reporta junto al modelo, nunca como verdad absoluta. Esto se documenta en el
> informe para que la comparación sea honesta.

## Leaderboard por modelo

```python
# src/evaluation/leaderboard.py
def run_model_comparison(las_path, models: list[str], mode: str) -> dict:
    """Corre el MISMO pozo con cada modelo; tabula objective_score + score_report por modelo."""
```
Salida: una tabla por modelo con las métricas objetivas + cualitativas como **columnas separadas**
(sin composite opaco), persistida en `outputs/evaluation/leaderboard.json` y renderizable.

> **Semántica de ranking.** Se ordena por una métrica objetiva declarada (default: `honesty_ok`
> primero, luego `decisions_justified`), nunca por un score compuesto opaco. La cobertura
> (`exploration_coverage`, `optional_sections`) se **normaliza por pertinencia**: "analizó más" no es
> "analizó mejor" — una sección sin justificación (`rationale` vacío) no suma, y se capa el premio a
> volumen sin justificación. Objetivo y cualitativo se reportan lado a lado, no se funden.

## Conexión con los 2 informes del mandato

Los 2 informes finales (qwen3:30b-a3b y llama3.1:8b, decisión DV2-0) se corren sobre el mismo pozo
Schaben y se evalúan con este protocolo, produciendo un leaderboard de 2 filas — la primera medición
real de la capacidad analítica relativa de los dos modelos del proyecto. Ese es el cierre del build v2.

## Reproducibilidad
El score objetivo es determinista (mismo grafo → mismo score). El score cualitativo se pinea por seed +
digest del modelo y se marca model-version-sensitive; se guarda como golden de referencia pero NO entra
al tier CI-gating determinista (= los 143 tests de v1 MÁS los nuevos guardrails deterministas de
V2-A..G); es model-in-the-loop, tier manual — ver `09_implementation_plan.md` V2-G.
