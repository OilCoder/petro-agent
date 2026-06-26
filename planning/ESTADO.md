# Estado del proyecto — petro-agent

> **⚠️ v1 CONGELADO · v2 en diseño (2026-06-26).** Lo descrito en este documento es **v1**: el
> pipeline determinista honesto, completo y verde (143 tests), que queda **congelado como baseline
> comparativa**. El proyecto se reorientó a un **sandbox de analista** (el agente analiza, decide y
> compone el informe con libertad, seleccionando de una librería de fórmulas vetada). El diseño v2
> vive en `planning/blueprint_v2/` (ancla: `00_charter.md`). v1 NO se modifica más.

Informe único de estado de **v1**: **qué se hizo** y **qué falta**. Para el detalle granular ver
`PLAN.md` (plan por fases), `DECISIONS.md` (bitácora de decisiones D1–D10) y `blueprint/`
(diseño fundacional v1). Para el rumbo v2: `blueprint_v2/` + `VISION_AGENTE_ANALISTA.md`.

## Qué es

Sistema multi-agente que toma registros de pozo (LAS crudos) y produce un informe
petrofísico (Vsh, PHIE, Sw, cutoffs, net pay, zonas, incertidumbre) **sin humano en el loop
por informe**. Invariante: **cada número sale de código determinista probado; el LLM solo
orquesta, selecciona y redacta — nunca calcula**.

Stack: Python · lasio · numpy · LangGraph (máquina de estados determinista) · Ollama local
(qwen3:30b writer / llama3.1:8b revisor adversarial) · ledger JSON · pytest golden tests.

Datos de desarrollo: campo Schaben (Mississippian, Kansas — KGS público).

---

## ✅ Realizado

### Motor determinista + pipeline (Fases 0–9)
- **Petrofísica congelada y golden-tested**: `calc_vsh` (Larionov old-rocks), `calc_phie`
  (densidad-neutrón, **efectiva** con corrección de shale), `calc_sw` (Archie), net pay
  (cutoffs → net sand → net reservoir → net pay), HCPV/BVW.
- **Parametrización data-driven** (`lithology.py`): matriz `rho_ma`, endpoints de shale y
  **Rw** derivados del dato (no defaults fijos) — reemplaza al `compute_agent` LLM que nunca
  se cableó. Determinista.
- **QC gate** (`qc/`): unidades, nulls, spikes, bad-hole, **hard-mask de valores sentinel-
  like** (el RT de ~1e11 que fabricaba pay), mapa de calidad GOOD/DEGRADED/EXCLUDED.
- **Trazabilidad LAS**: RT elegido por profundidad de investigación (deep-first), provenance
  per-curve (canonical←raw) y metadata de pozo/herramienta (fecha, compañía, campo) al ledger.
- **Parámetros con provenance + citación** (sin RAG, tabla curada congelada).
- **Validadores independientes** (`validators/`): bounds, vsh-phie, rt-sw, model-mismatch
  (crossplot N-D), **plausibilidad física de net pay** (NTG/PHIE inverosímiles → irreducible).
- **Orquestador LangGraph determinista** con loop de objeciones, circuit breaker, y **gate de
  abstención**: un pozo con objeciones MECHANICAL sin resolver o net pay inverosímil **se
  abstiene** (banner ⚠️ "NO es un estimado confiable") en vez de publicar cifras falsas.
- **Incertidumbre**: Monte Carlo P10/P50/P90 + sensibilidad (parámetro dominante).
- **Agentes LLM**: writer (solo prosa, números desde el renderer), revisor adversarial
  (segunda familia de modelo), claim_verifier determinista (reconcilia números + tono).
- **Renderer determinista de informes**: estructura completa (cabecera, metodología,
  parámetros+provenance, zonación, resultados, incertidumbre, QC, conclusiones, apéndices)
  con **todos los números desde el ledger por código**; el LLM solo redacta 2 huecos de prosa.
- **Figuras embebidas**: composite log (5 tracks), Pickett plot, crossplot N-D; bar chart de
  campo.
- **Field report**: estadística cross-well (mean/median/range — **nunca suma de espesores**),
  inventario por pozo, flags de abstención, best-reservoir vs best-data, archivos excluidos.

### Resultado en datos reales (3 pozos Schaben)
- Net pay corregido de inverosímil a creíble: **206/330/437 m → 71/143/179 m** (NTG 0.06–0.15).
- Los 3 pozos **se abstienen honestamente** (objeciones MECHANICAL + PHIE alta para carbonato).
- Informes en `documentation/sample_reports/` (per-pozo + field + figuras + ledgers).

### Verificación
- **143 tests verdes** (`pytest -q`), `ruff` y `mypy` limpios.
- Todo commiteado y pusheado a `main` (GitHub: OilCoder/petro-agent).

---

## ⏳ Falta por hacer (NEEDS-HANDSON — requieren tu mano o una decisión)

### Bloqueado por falta de datos
- **VOLVE (calibración estadística)**: la descarga de Equinor está detrás de login navegado;
  sin ella el ECE / reliability diagram queda **infra-listo pero sin medir**. Charter criterio
  4 sincerado a "infra-ready, unmeasured"; **Fase 8 BLOCKED**. Cerrar = obtener VOLVE y correr
  la regresión.
- **Calibración con core/producción de Schaben**: Rw, cutoffs y la abstención mejorarían con
  dato real; hoy son defaults regionales honestos (tier `bracketed`). Sin esto, los net pay
  siguen sin converger (DID_NOT_CONVERGE) — por diseño, no por bug.

### Decisión de diseño tuya
- **Modelo shaly-sand fino (Thomas-Stieber)**: la corrección lineal de shale no decorrelaciona
  del todo Vsh-PHIE. Un modelo más riguroso lo haría, pero es más trabajo. ¿Vale la pena?

### Trabajo acotado pendiente (sin bloqueo externo)
- **LAS wrapped / `~Other` antes de `~Curve`**: 7 archivos no parsean; falta el reorder-guard
  + fallback y registro N_loaded/N_excluded a nivel de ingesta (parcial: el field report ya
  registra exclusiones).
- **`robustness.py`** (multi-seed): el MC usa una sola semilla (42); falta el chequeo de
  robustez multi-semilla. (Marcado BLOCKED en PLAN, D10.)
- **claim_verifier checks (2)/(3)**: reconciliación posicional de rangos por campo (hoy hay
  check (1) números + check (4) tono).
- **HCPV/NRV de campo**: el field report da net pay cross-well, no volumétrico (necesita área).
- **Validador `data_quality`**: downgrade de FIRM en profundidad DEGRADED — hoy moot (ningún
  run llega a FIRM sin core).

---

## Convenciones / dónde está cada cosa
- Código + tests: `src/`, `tests/`. Informes de muestra: `documentation/sample_reports/`.
- Plan detallado por fases: `planning/PLAN.md`. Decisiones: `planning/DECISIONS.md`.
- Diseño fundacional: `planning/blueprint/`. Bitácora (narrativa): `planning/bitacora/`.
