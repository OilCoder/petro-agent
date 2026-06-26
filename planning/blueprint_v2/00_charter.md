# Charter v2 — petro-agent como sandbox de analista petrofísico

> **v2 reframe (2026-06-26).** v1 (pipeline determinista honesto, 143 tests verdes) queda
> **congelado** como baseline comparativa (ver `planning/ESTADO.md`). v2 reorienta el proyecto
> de *"el orquestador dicta todo, el LLM redacta"* a *"un agente analiza, decide y compone el
> informe con libertad, seleccionando de una librería de fórmulas vetada"*. El determinismo se
> mueve del **pipeline** a la **librería + los gates + el grafo de metodología**.

## Goal

Construir un **sandbox** donde un agente (LLM) actúe como **analista petrofísico**: explore los
datos de un pozo, **decida con su propio juicio** qué métodos aplicar y qué análisis añaden
completitud, y **componga el mejor informe posible** — llamando a herramientas deterministas,
nunca calculando él mismo. El objetivo no es solo producir informes correctos, sino **medir
cuánta capacidad de análisis y decisión** tiene un modelo dado, de forma trazable y comparable.

## Stakeholders

| Stakeholder | Interés |
|---|---|
| Owner / usuario (analista-in-the-loop) | Revisa el build autónomo y compara la capacidad analítica de los modelos |
| Modelos locales (qwen3:30b-a3b, llama3.1:8b) | Sujetos evaluados — el sandbox mide su análisis y composición |
| Consumidores del informe | Reciben un informe trazable, honesto sobre sus límites |

## Los dos modos (conviven)

| Modo | Filosofía | Gates QC/abstención | Para qué |
|---|---|---|---|
| **Guiado** | El informe arranca de una **pre-forma base** (el dummy) que asegura lo mínimo; el agente añade sobre esa guía | **Obligatorios** (piso de seguridad) | Producción / informe defendible |
| **Libre** | El agente decide **qué informe construir** desde cero, a voluntad | **Advisory** (se registran, no bloquean) | Experimentación / medir la inteligencia del modelo |

El modo guiado es la evolución directa de v1 (pre-forma + secciones opcionales). El modo libre
es el sandbox puro: máxima libertad de composición, los gates informan pero no imponen.

## Invariante v2 (evolucionado)

**Cada número sale de código determinista probado. El agente tiene libertad TOTAL sobre QUÉ
método usar y CÓMO componer el informe — selecciona y parametriza desde una librería de
fórmulas vetada (golden tests), pero nunca escribe matemática en runtime.**

Lo que **cambia** respecto a v1:
- El agente, no el orquestador, decide **qué fórmulas aplicar**, en qué orden, y qué secciones
  construir. Ya no hay una topología de pipeline fija que dicte el método.
- El agente produce un **grafo de metodología** (su cadena de pensamiento) que justifica cada
  decisión, auditable y comparable entre modelos.

Lo que **se mantiene** (el núcleo de honestidad de v1):
- El agente **nunca calcula un número ni escribe una ecuación** — pide que se calcule llamando
  a una función probada. Cada número es trazable en el ledger a su tool de origen.
- En **modo guiado** los gates deterministas (QC, validadores, abstención) son **obligatorios e
  in-saltables** — el agente es libre en el QUÉ del informe, no en saltarse el control de calidad.
- En **modo libre** los gates corren igual y se **registran**, pero son advisory: el grafo de
  metodología y el reviewer son el control.

## Success criteria (v2)

Criterios medibles del sandbox (distintos de los de v1, que medían corrección):
1. **Agencia trazable** — todo informe v2 emite un **grafo de metodología** que muestra, paso a
   paso, qué exploró el agente, qué decidió añadir, y por qué. Reconstruible y diffeable.
2. **Cero cálculo del LLM** — el claim_verifier (reconciliación por clave de ledger) confirma que
   cada número del informe provino de una tool, no del modelo. Sin excepción.
3. **Librería de fórmulas completa y vetada** — un set de métodos petrofísicos (multi-método para
   Vsh, PHIE, Sw, litología, etc.) suficientemente rico para que la SELECCIÓN sea una decisión
   real, todos golden-tested.
4. **Evaluación por modelo** — un reviewer **del mismo modelo** califica la calidad del informe,
   de modo que se pueda **puntuar y comparar modelos** (qwen3 vs llama3.1 vs futuros) por su
   capacidad de análisis y composición.
5. **Dos modos funcionales** — el mismo pozo produce un informe guiado (con gates) y uno libre
   (sandbox), ambos con su grafo de metodología.

## Non-goals (v2)

- **No** se le permite al agente escribir o derivar matemática nueva en runtime (eso violaría el
  invariante; la libertad es de SELECCIÓN, no de autoría matemática).
- **No** se reemplaza v1: queda congelado e intacto como baseline comparativa.
- **No** se promete que el modo libre sea "más correcto" — es más libre; la corrección de los
  números sigue dependiendo de la librería vetada y de la calibración (que sigue NEEDS-HANDSON).
- **No** se exige LLM en la nube: la restricción local (Ollama, 16GB) se mantiene; el sandbox
  debe degradar con gracia (fallback señalizado).

## Invariants (v2 — no se violan sin aprobación + gate)

1. Todo número proviene de una función probada de la librería vetada; el LLM nunca produce un dígito.
2. El agente selecciona y compone; no autora matemática en runtime.
3. Cada informe emite un grafo de metodología trazable (la cadena de decisión del agente).
4. Modo guiado: gates QC/abstención obligatorios. Modo libre: gates advisory pero siempre corridos y registrados.
5. El reviewer de evaluación es del **mismo modelo** que el generador (medición por modelo), no de otra familia.
6. El **modo (guiado/libre) lo fija el invocador** (humano u orquestador determinista) en la entrada del run;
   el agente LLM **nunca elige su propio modo** (elegir modo libre = saltarse el QC, prohibido).

> **Nota sobre el reviewer (cambio respecto a v1).** v1 usaba un reviewer adversarial de otra familia
> para decorrelación; v2 lo **reorienta** a scorer del mismo modelo (medición por modelo, ver `04`).
> Esto elimina el check de familia independiente: el único guard numérico determinista pasa a ser el
> claim_verifier (reconciliación por clave). El reviewer same-model da un score cualitativo
> COMPLEMENTARIO (sesgo de auto-indulgencia conocido), no el control primario de honestidad — ese rol
> lo cumplen el grafo de metodología (visible, objetivo) y los flags de los gates registrados.

## Constraints

- Runtime local (Ollama: qwen3:30b-a3b / llama3.1:8b; techo de 16GB VRAM, vaciado bajo carga).
- Reproducibilidad/trazabilidad vía ledger + grafo de metodología + pineado del digest del modelo.
- Reutiliza la infraestructura v1 (motor golden-tested, validadores, gates, renderer) — v2 inserta
  agencia, no reconstruye.

## Open questions (a resolver en el resto del suite v2)

- Alcance exacto de la librería de fórmulas (¿qué métodos por cada propiedad? — `02_formula_library.md`).
- Esquema y persistencia del grafo de metodología (`03_methodology_graph.md`).
- Protocolo de scoring del reviewer same-model (`04_evaluation_per_model.md`).
- Topología del nodo agente y el loop EXPLORE→DECIDE→DISPATCH (`01_sandbox_architecture.md`).
