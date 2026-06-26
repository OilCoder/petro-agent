# v2 · 02 — Librería de fórmulas vetada

El menú cerrado de métodos petrofísicos probados desde el que el agente **elige** (no inventa).
Para que la selección sea inteligencia y no relleno, cada propiedad ofrece ≥2 métodos vetados.
Cada función es pura, versionada y golden-tested (igual que `calc_vsh`), vive en `src/petrophysics/`,
y se registra en `params/citations.py`. El agente nunca escribe estas fórmulas; las invoca por ID.

## Principio de selección

Una tool determinista `available_methods(curves) -> dict[str, list[str]]` reporta, dado el set de
curvas presentes, qué métodos son aplicables por propiedad. El agente elige de esa lista según su
análisis del dato (litología, calidad, disponibilidad de DT/PEF, carácter shaly). Si elige un método
no aplicable, el dispatcher lo rechaza (objeción MECHANICAL → no se ejecuta).

## Catálogo

### Vsh (shale volume) — entrada GR (±SP)
| ID | Método | Cuándo | Estado |
|---|---|---|---|
| `vsh_larionov_old` | Larionov rocas viejas (Paleozoico) | default Schaben | v1 ✓ |
| `vsh_larionov_tertiary` | Larionov terciario | rocas jóvenes | v1 ✓ (variante) |
| `vsh_linear` | IGR lineal | conservador / screening | nuevo |
| `vsh_clavier` | Clavier 1971 | alternativa no lineal | nuevo |
| `vsh_steiber` | Steiber | alternativa no lineal | nuevo |

### Porosidad — entrada RHOB / NPHI / DT
| ID | Método | Cuándo | Estado |
|---|---|---|---|
| `phi_density` | porosidad densidad | solo RHOB | nuevo (split de v1) |
| `phi_neutron` | porosidad neutrón | solo NPHI | nuevo (split de v1) |
| `phie_density_neutron` | crossplot D-N, PHIE efectiva (corrección shale) | RHOB+NPHI (default) | v1 ✓ |
| `phi_sonic_wyllie` | Wyllie time-average | hay DT | nuevo |
| `phi_sonic_rhg` | Raymer-Hunt-Gardner | hay DT, no consolidado | nuevo |

### Sw (saturación de agua) — entrada RT + PHIE (+Vsh)
| ID | Método | Cuándo | Estado |
|---|---|---|---|
| `sw_archie` | Archie | roca limpia | v1 ✓ |
| `sw_simandoux` | Simandoux | roca shaly | nuevo |
| `sw_indonesia` | Poupon-Leveaux (Indonesia) | shaly, alta Vsh | nuevo |
| `sw_waxman_smits` | Waxman-Smits | hay CEC/Qv (raro) | diferido (sin dato) |

**Inputs eléctricos (a, m, n, Rw, Rsh) — productores vetados, nunca del LLM.** El agente NO
suministra estos números; los provee el código vía:
| ID | Productor | Estado |
|---|---|---|
| `rw_pickett` | Rwa por método Pickett (RT·PHIE^m/a en zona limpia porosa) | v1 ✓ (`estimate_rw`) |
| `electrical_preset` | tabla vetada de presets (a,m,n,Rw,Rsh) por litología/cuenca, por ID | nuevo |
El agente elige el ID del productor/preset; el valor numérico sale de la función o la tabla vetada.

### Litología — entrada RHOB/NPHI (+DT/PEF)
| ID | Método | Cuándo | Estado |
|---|---|---|---|
| `litho_nd_crossplot` | crossplot neutrón-densidad | RHOB+NPHI | v1 ✓ (en model_mismatch) |
| `litho_mn` | M-N crossplot | hay DT | nuevo |
| `litho_mid` | MID plot | hay DT+PEF | diferido (poco PEF) |

### Net pay / volumétricos — agregación sobre las 3 propiedades
`apply_cutoffs`, `net_sand`, `net_reservoir`, `compute_net_pay`, `hcpv`, `bvw` (v1 ✓). El agente
elige cutoffs desde un **enum DISCRETO de presets vetados por ID** (p.ej. `cutoff_set="carbonate_conservative"`),
no valores arbitrarios — el valor numérico lo provee el código del preset, nunca el LLM.

## Contrato de cada método

```python
# firma uniforme: arrays de entrada + parámetros nombrados; salida array + metadata
def sw_simandoux(rt, phie, vsh, a, m, n, rw, rsh) -> np.ndarray: ...
# golden tests obligatorios por método: bounds físicos, monotonía, caso analítico
# conocido, NaN passthrough, chequeo dimensional. Sin esto el método NO entra al registry.
```
`a/m/n/rw/rsh` provienen de un productor vetado (`rw_pickett`) o de un `electrical_preset` por ID,
nunca del LLM. El agente elige el método y el preset/productor; el código entrega los números.

## Registry

`src/petrophysics/registry.py`:
```python
METHOD_REGISTRY: dict[str, MethodSpec]  # id -> {fn, property, required_curves, params, citation, version}
def available_methods(curves: dict) -> dict[str, list[str]]  # property -> [applicable ids]
```
El registry es la frontera de la agencia: el agente elige IDs de aquí; no puede invocar nada fuera.
Congelado y versionado; añadir un método requiere su golden test + entrada de citación.

**Métodos diferidos** (Waxman-Smits, MID) están catalogados arriba por completitud del roadmap pero
**NO están en `METHOD_REGISTRY`** (sin golden test → no los devuelve `available_methods`) hasta que
existan dato + test. Elegir un ID fuera del registry es objeción MECHANICAL (no se ejecuta).

**Normalización de mnemónicos.** `available_methods` consume curvas ya canonicalizadas. La tabla
canónica (mnemónico, aliases, unidades, mayúsculas) vive en `src/params/mnemonic_aliases.json` (v1 ✓);
el paso de normalización de alias del loader corre ANTES de `available_methods`.

## Alcance v2-A (qué se construye primero)
Priorizar lo ejercitable en Schaben: `vsh_linear`, `phi_sonic_wyllie` (donde hay DT),
`sw_simandoux` + `sw_indonesia` (roca shaly — el caso real que dispara las objeciones v1),
`litho_mn` (donde hay DT). Waxman-Smits / MID se difieren (sin CEC/PEF suficiente). Decisión
registrada en `DECISIONS_V2.md` DV2-1.
