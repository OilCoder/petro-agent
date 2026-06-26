# v2 · 03 — Grafo de metodología (la cadena de pensamiento)

El artefacto que hace **visible y auditable** el razonamiento del agente: qué exploró, qué decidió
añadir, qué herramienta ejecutó, y qué sección produjo. Es el aporte central de v2 sobre v1 —
convierte una caja negra ("el LLM redactó") en una cadena de decisión trazable y comparable.

## Modelo de datos

Un DAG dirigido y acíclico. Nodos tipados, aristas `depends_on`. Serializable a JSON, persistido en
el ledger bajo `methodology_graph`, renderizable a Mermaid/texto en el informe.

```python
# src/agents/methodology_graph.py
NODE_TYPES = ("observation", "decision", "tool_call", "section")

@dataclass(frozen=True)
class GraphNode:
    id: str                      # "obs_1", "dec_1", ...
    type: str                    # one of NODE_TYPES
    depends_on: tuple[str, ...]  # parent node ids
    payload: dict                # type-specific (ver abajo)

@dataclass
class MethodologyGraph:
    mode: str                    # "guided" | "free"
    model: str                   # "qwen3:30b-a3b"
    model_digest: str            # from provenance.pin_versions (model identity = name + digest, V2-G)
    nodes: list[GraphNode]
    def add(self, ...) -> str    # returns new node id
    def to_json(self) -> dict
    def to_mermaid(self) -> str  # flowchart for the report
    def validate(self) -> list[str]
        # acyclic · ids unique · deps exist · tool_call.payload.result_ledger_key resolves to a
        # ledger entry with its result_hash · NO loose numeric literal in decision/observation
        # payloads (regex: a digit not part of a ledger-key reference) -> MECHANICAL objection
```

### Payload por tipo
- **observation**: `{tool, finding, source_ledger_key}` — qué vio el agente en el EDA (de una tool).
- **decision**: `{rationale, considered, chosen}` — qué decidió y por qué (texto del LLM; NO números).
- **tool_call**: `{tool, args, result_ledger_key, result_hash}` — qué se ejecutó (lo escribe el dispatcher).
- **section**: `{section_id}` — qué sección se añadió al informe.

Un método **rechazado** (elegido fuera del registry o no aplicable) produce un nodo `tool_call` con
`payload.status="rejected"` y `payload.reason`, para que el rastro registre la agencia
intentada-pero-rechazada (no se ejecuta ni escribe número; alimenta `honesty_ok`/scoring).

## Quién escribe cada nodo (preserva el invariante)

| Nodo | Lo crea | Por qué importa al invariante |
|---|---|---|
| observation | el dispatcher (al pre-computar EDA) | número de una tool, no del LLM |
| decision | el agente LLM (texto de razón) | el LLM aporta JUICIO, nunca un dígito |
| tool_call | el dispatcher (al ejecutar) | el número y su hash los pone el código |
| section | el ensamblador del render | composición determinista del plan |

El LLM solo aporta los nodos `decision` (y los IDs que enlazan). Todo número referenciado por el grafo
vive en el ledger bajo una clave; el grafo apunta a la clave, no embebe el número. Así el grafo es
trazable y el LLM sigue sin producir cifras.

## Validación (gate determinista)

`validate()` corre antes de emitir: el grafo debe ser acíclico, IDs únicos, toda `depends_on` existe,
y todo `tool_call.result_ledger_key` resuelve a una entrada real del ledger con su `result_hash`. Un
grafo inválido es una objeción MECHANICAL (bloquea en guiado, advierte en libre).

## Render en el informe

Sección "Metodología (cadena de decisión)": el `to_mermaid()` como diagrama + una tabla legible
(observación → decisión → acción → sección). En modo libre, esta sección es obligatoria aunque los
gates sean advisory — es el control de honestidad que reemplaza al bloqueo.

## Uso comparativo entre modelos (el experimento de v2)

Dos modelos sobre el MISMO pozo producen grafos distintos: distinto número de observaciones atendidas,
distintas decisiones, distintos métodos elegidos, distintas secciones. Métricas derivables del grafo,
deterministas (no opinión del LLM). Las claves canónicas las define `objective_score()` en
`04_evaluation_per_model.md`; aquí se nombran idénticas:
- `exploration_coverage` = `n_observations_used` / `n_observations_available` (cobertura de exploración),
- `methods_selected`, `optional_sections`,
- `reasoning_depth` = **camino dirigido más largo sobre TODOS los tipos de nodo del DAG**,
- `decisions_justified` = decisiones con `rationale` no vacío / total de decisiones.

Estas métricas alimentan el scoring por modelo (`04_evaluation_per_model.md`) junto con el juicio del
reviewer same-model. El grafo es la evidencia objetiva; el reviewer es el juicio cualitativo.

## Persistencia y reproducibilidad

Se guarda en el ledger (`run.methodology_graph`) y se versiona con el run. Dadas las mismas tool-calls
(deterministas) y el mismo plan del LLM, el grafo se reconstruye idéntico. La parte no-determinista (el
texto de las decisiones del LLM) se pinea por seed + digest del modelo; su variabilidad se acepta y se
hace detectable, no se pretende bit-exact (ver riesgos del informe de visión).
