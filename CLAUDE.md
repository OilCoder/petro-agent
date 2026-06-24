# petro-agent — Agente petrofísico autónomo

Sistema multi-agente que toma registros de pozo (LAS) y produce un informe
petrofísico (Vsh, PHIE, Sw, cutoffs, net pay, zonas, conclusiones) **sin humano
en el loop por informe**, donde cada afirmación está atada a evidencia trazable y
la confianza está calibrada automáticamente. No promete "siempre correcto";
promete "honesto sobre cuánto acierta, y demostrable".

## ⛔ Invariante no-negociable

**Cada número sale de código determinista probado. El LLM solo orquesta,
selecciona y redacta — nunca calcula, y nunca escribe la ecuación en runtime.**

- Todo número del camino cuantitativo viene del motor determinista versionado
  (lasio/numpy + la capa de funciones petrofísicas propia: Larionov→Vsh,
  densidad-neutrón→PHIE, Archie→Sw), **congelada + cubierta por golden tests**.
- El agente *selecciona y parametriza* funciones probadas; no inyecta matemática
  ad-hoc al camino cuantitativo. Si falta un método, cae al válido más cercano y
  **registra la degradación en el ledger**.
- El orquestador (LangGraph) es **determinista, no un LLM** — es dueño del loop,
  las compuertas y la terminación. Un LLM nunca decide si se salta el QC.
- Diseño completo (los 9 problemas, el techo honesto) en
  `planning/diseno/agente-autonomo-informes-petrofisicos.md`.

## Convenciones de lenguaje

| Superficie | Idioma |
|---|---|
| Código y comentarios | Inglés |
| Planes (`planning/PLAN.md`), specs, commits | Inglés |
| Bitácora (`planning/bitacora/`) | Español |
| Material de estudio (`aprendizaje/`) | Español (con términos técnicos en inglés) |

## Stack y entorno

- **Runtime**: Python sobre WSL (objetivo: devcontainer/Docker).
- **LLMs locales (Ollama)**: Qwen3:30b-a3b (agente principal/redactor);
  Llama3.1:8b (iteración rápida + segunda familia para el revisor adversarial,
  Fase 6). Sin LLM en la nube en el runtime del informe.
- **I/O**: lasio · **Numérico**: numpy · **Orquestación**: LangGraph
  (máquina de estados, no-LLM) · **Validadores**: numpy + matplotlib (cross-plots)
  · **Trazabilidad**: ledger JSON (versiones, hash de config, seeds pineados)
  · **Tests**: pytest (golden tests).
- **Datos**: Kansas/Schaben (desarrollo — paleozoico → **Larionov rocas viejas**,
  NO terciaria). Regresión (Fase 8): VOLVE.

## Cómo se construye

Por las **9 fases** de `planning/diseno/hoja-de-ruta.md`. El orden importa; cada fase corre y
entrega algo verificable. El sistema autónomo completo es la Fase 8 con todas las
anteriores integradas. Estado actual: **Fase 0** — motor determinista (lasio carga
un LAS, `calc_vsh` + `calc_phie` con golden tests). `planning/PLAN.md` es la fuente
de verdad del estado real de cada fase.

## Configuración (claude-project-base)

Este proyecto usa la base de `OilCoder/claude-project-base` (cuatro capas: las
reglas guían, los skills orquestan, los agentes revisan/diseñan aislados, los hooks
imponen).

- **Reglas**: `.claude/rules/` (13) — siempre cargadas + scoped por path.
- **Skills**: `.claude/skills/` (11) — `/blueprint`, `/plan-writing`,
  `/phase-executor`, `/checkpoint`, `/bug-fix`, `/bitacora`, `/test`,
  `/investigate`, `/document`, `/doc-enforce`, `/study`.
- **Agentes**: `.claude/agents/` (5) — `code-reviewer`, `security-reviewer`,
  `architect`, `blueprinter`, `implementer`.
- **Hooks**: `.claude/settings.json` — statusline, contexto al inicio de sesión,
  sugerencia de `/checkpoint`, bloqueo de comandos destructivos, debug-isolation,
  y linter Python (ruff format + ruff check --fix) en cada Edit/Write.
- **Loop autónomo**: `.claude/scripts/promptloop.sh` — ejecuta `PLAN.md` fase a
  fase en una rama dedicada (no desde una sesión interactiva).

## Verificación (obligatoria antes de declarar algo "hecho")

Ningún número se confía hasta que sus golden tests pasan. Comandos en
`.claude/rules/project-guidelines.md`:

```text
test:        pytest -q
type-check:  mypy src/
lint:        ruff check .
format:      ruff format --check .
```

## Estructura

Solo existen las 5 carpetas mínimas (`.claude/`, `planning/`, `documentation/`,
`aprendizaje/`, `docs/`). `src/`, `tests/`, `data/`, etc. se crean cuando la fase
correspondiente lo demande — no antes.
