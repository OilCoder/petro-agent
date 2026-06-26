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

### Litología — entrada RHOB/NPHI (+DT/PEF)
| ID | Método | Cuándo | Estado |
|---|---|---|---|
| `litho_nd_crossplot` | crossplot neutrón-densidad | RHOB+NPHI | v1 ✓ (en model_mismatch) |
| `litho_mn` | M-N crossplot | hay DT | nuevo |
| `litho_mid` | MID plot | hay DT+PEF | diferido (poco PEF) |

### Net pay / volumétricos — agregación sobre las 3 propiedades
`apply_cutoffs`, `net_sand`, `net_reservoir`, `compute_net_pay`, `hcpv`, `bvw` (v1 ✓). El agente
elige cutoffs desde un rango vetado, no valores arbitrarios.

## Contrato de cada método

```python
# firma uniforme: arrays de entrada + parámetros nombrados; salida array + metadata
def sw_simandoux(rt, phie, vsh, a, m, n, rw, rsh) -> np.ndarray: ...
# golden tests obligatorios por método: bounds físicos, monotonía, caso analítico
# conocido, NaN passthrough, chequeo dimensional. Sin esto el método NO entra al registry.
```

## Registry

`src/petrophysics/registry.py`:
```python
METHOD_REGISTRY: dict[str, MethodSpec]  # id -> {fn, property, required_curves, params, citation, version}
def available_methods(curves: dict) -> dict[str, list[str]]  # property -> [applicable ids]
```
El registry es la frontera de la agencia: el agente elige IDs de aquí; no puede invocar nada fuera.
Congelado y versionado; añadir un método requiere su golden test + entrada de citación.

## Alcance v2-A (qué se construye primero)
Priorizar lo ejercitable en Schaben: `vsh_linear`, `phi_sonic_wyllie` (donde hay DT),
`sw_simandoux` + `sw_indonesia` (roca shaly — el caso real que dispara las objeciones v1),
`litho_mn` (donde hay DT). Waxman-Smits / MID se difieren (sin CEC/PEF suficiente). Decisión
registrada en `DECISIONS_V2.md` DV2-1.
