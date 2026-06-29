# Informe Petrofísico Completo desde LAS — Spec (v2, experimento LLM)

Propósito del proyecto: medir si un LLM local puede redactar informes petrofísicos, y con
qué profundidad. Esta spec define un informe **completo pero acotado a lo técnico** y
**derivable SOLO de archivos LAS** (única entrada, como en `data/`).

Reglas de alcance:
- Solo contenido TÉCNICO. Sin historia de campo, sin control documental/aprobaciones.
- Análisis que requieren datos no provistos (núcleo, mud log, pruebas de presión, producción,
  completamiento, tops de formación) NO se inventan: se nombran en Limitaciones (cap. 34).
- El informe se ADAPTA a las curvas disponibles por pozo (algunos solo GR; otros GR/RHOB/NPHI/RT).
- Sin tops en el LAS → se usa zonación COMPUTADA por profundidad, no por formación.

Leyenda: **[FIJO]** = todo modelo debe producirlo (piso comparable) · **[MODELO]** = decisión
del modelo (señal de profundidad/creatividad). La asignación es una **propuesta** a fijar por
el usuario antes de cablearla en `report_compose`.

## 0. Metadatos y procedencia  [FIJO]
- UWI, ubicación/coordenadas (del header LAS), fecha de registro, compañía de servicio
- Intervalo registrado, paso de muestreo, valor nulo
- Versiones de motor/librería, config hash (SHA-256), git SHA, modelo + model_digest, modo

## 1. Resumen ejecutivo  [FIJO]
- Alcance, pozos/intervalos evaluados, calidad general de datos
- Resultados clave (Vsh, PHIE, Sw), net pay como rango P10/P50/P90
- Tier de confianza + banner de abstención si no converge
- Incertidumbre dominante, conclusión y recomendación de mayor palanca

## 2. Objetivo y alcance técnico  [MODELO]
- Objetivo del análisis, alcance, supuestos, entregables

## 3. Inventario de datos (desde LAS)  [FIJO]
- Archivos LAS, pozos, curvas por pozo (mnemónico→canónico) con unidades
- Cobertura en profundidad, paso, nulos; ¿coordenadas presentes?
- Datos NO disponibles (sin tops/núcleo/presión/producción)

## 4. QC de archivos LAS  [FIJO]
- Formato/versión, header, lista de curvas, unidades, nombres no estándar
- Curvas duplicadas/constantes, valores físicamente imposibles, nulos, paso

## 5. Estandarización  [FIJO]
- Homologación de mnemónicos y unidades, conversiones
- Curvas principales/auxiliares/descartadas, base de datos final

## 6. QC de registros por curva  [FIJO]
- Por curva disponible: GR, resistividad (prof/media/somera), SP, caliper, densidad,
  neutrón, sónico, PEF
- Washouts (caliper vs bit), gas effect, ciclos saltados, zonas de mala lectura
- Flags de calidad por curva e intervalo

## 7. Preparación de datos  [FIJO]
- Nulos, outliers, despike, interpolación controlada, recorte de inválidos
- Corrección por borehole (si hay caliper); base interpretativa maestra

## 8. Definición de intervalos  [FIJO]
- Intervalo total / válido / excluido (baja calidad o incompleto)
- Zonación COMPUTADA por profundidad (no hay tops de formación en LAS)

## 9. Metodología petrofísica  [FIJO]
- Flujo, curvas usadas, parámetros (matriz/fluido/temperatura/Rw)
- Parámetros de Archie, criterios de corte
- Métodos seleccionados vs alternativos, flujo de QC interpretativo

## 10. Análisis de curvas
- 10.1 Gamma ray: baselines limpio/arcilloso, IGR  [FIJO]
- 10.2 Resistividad: prof/media/somera, invasión, indicadores HC  [FIJO si RT]
- 10.3 SP: baseline lutita, permeabilidad cualitativa, Rw preliminar  [MODELO]
- 10.4 Caliper / calidad de hueco: washouts, efecto en curvas  [FIJO si caliper]
- 10.5 Densidad-neutrón: separación, crossover, gas, litología  [FIJO si RHOB+NPHI]
- 10.6 Sónico: porosidad sónica, ciclos saltados, compactación  [MODELO si DT]
- 10.7 PEF / mineralogía: indicadores litológicos  [MODELO si PEF]

## 11. Interpretación litológica  [FIJO]
- Por reglas y crossplots; clases litológicas; incertidumbre
- (Comparación con núcleo/mud log: NO disponible)

## 12. Crossplots petrofísicos
- RHOB-NPHI, Pickett  [FIJO]
- Hingle, Buckles, M-N, litología, electrofacies  [MODELO]

## 13. Volumen de arcilla (Vsh)  [FIJO]
- Métodos (lineal, Larionov joven/antiguo, Clavier, Steiber), comparación, seleccionado
- Vsh bruto/corregido, por zona, incertidumbre

## 14. Porosidad  [FIJO]
- Densidad, neutrón, sónica; total, efectiva, corregida por arcilla
- Por zona; incertidumbre; (calibración con núcleo: NO disponible)

## 15. Resistividad de agua (Rw)  [FIJO]
- Fuentes (SP, Pickett, default); corrección a temperatura de formación
- Salinidad equivalente; incertidumbre; sensibilidad de Sw a Rw

## 16. Saturación de agua  [FIJO núcleo + MODELO modelos]
- Archie  [FIJO]
- Simandoux / Indonesia / Dual Water / Waxman-Smits  [MODELO]
- a, m, n, Rt; Sw total/efectiva, Sh, Sw irreducible; por zona; sensibilidad; incertidumbre

## 17. Permeabilidad (log-based, sin calibrar)  [MODELO]
- Timur / Coates / Wyllie-Rose; relación phi-k; calidad de roca
- Caveat obligatorio: no calibrada (sin núcleo)

## 18. Parámetros derivados  [MODELO]
- BVW, HCPV, Phi-H, RQI, FZI, Winland R35, índice de calidad de reservorio

## 19. Electrofacies  [MODELO]
- Clustering no supervisado sobre curvas (sin etiquetas de núcleo)
- Nº de facies, estadística, interpretación, reservorio vs no-reservorio

## 20. Rock typing  [MODELO]
- Tipos de roca petrofísicos/hidráulicos (sin calibrar), flow units

## 21. Cutoffs petrofísicos  [FIJO]
- Criterios net sand/reservoir/pay; cutoffs Vsh/PHIE/Sw + procedencia
- Sensibilidad y justificación

## 22. Net reservoir y net pay  [FIJO]
- Gross, net sand, net reservoir, net pay, NTG
- Por zona; acumulado; propiedades ponderadas por espesor; pay flags

## 23. Contactos de fluidos (log-based, cualitativo)  [MODELO]
- Indicadores OWC/GWC por Sw/resistividad; cualitativo
- (Free water level por presión: NO disponible)

## 24. Evaluación por pozo  [FIJO]
- Resumen, curvas, calidad, zonas computadas, litología
- Vsh/PHIE/Sw/k, net reservoir/pay, zonas candidatas, riesgos, recomendación

## 25. Multi-pozo / campo  [MODELO]
- Correlación por GR (sin tops), estadística cross-well (nunca sumas)
- Mapa de campo desde coordenadas del header, overview de net pay, ranking

## 26. Análisis estadístico  [MODELO]
- Distribuciones por curva/pozo/zona, histogramas, boxplots, correlaciones, atípicos

## 27. Incertidumbre y sensibilidad  [FIJO]
- Monte Carlo P10/P50/P90 (realizaciones, seed)
- Sensibilidad por parámetro (Rw/a/m/n/cutoffs), driver dominante
- Escenarios bajo/base/alto

## 28. Ranking de oportunidades  [MODELO]
- Pozos/zonas/intervalos por calidad/pay/riesgo; score integrado

## 29. Metodología (grafo de decisión)  [FIJO]
- DAG observación→decisión→tool_call→sección (mermaid)
- Tool calls con args + hashes; prosa de decisión sin números; registro del fallback

## 30. Parámetros y procedencia  [FIJO]
- Cada parámetro: valor, unidad, procedencia, cita congelada
- Leyenda FIRM/QUALIFIED/BRACKETED

## 31. Objeciones de validadores y verificación de afirmaciones  [FIJO]
- Bounds, anticorrelación Vsh-PHIE, consistencia rt-sw, cross-tool
- Resultado del claim verifier (números + tono): PASS/FLAGS, listado no escondido
- Tools no ejecutados (señalizado)

## 32. Conclusiones  [FIJO]
- Por calidad de datos, litología, Vsh, PHIE, Sw, k, net reservoir/pay
- Mejores pozos/zonas, riesgos

## 33. Recomendaciones  [FIJO]
- Datos a adquirir (núcleo/presión/producción/registros) para calibrar y reducir
  la incertidumbre dominante

## 34. Limitaciones del estudio  [FIJO]
- Solo LAS: sin calibración de núcleo, sin presión (sin contactos verdaderos),
  sin producción, sin mud logs, sin tops (zonación computada)
- Disponibilidad de curvas por pozo; escala vertical/lateral

## 35. Nomenclatura y referencias  [MODELO]
- Abreviaturas, símbolos, unidades, referencias de fórmulas y software

## 36. Apéndices y entregables  [MODELO]
- Tabla de resultados por profundidad, tracks por pozo, crossplots, tabla de parámetros
- Completeness gate, extracto del ledger, artefactos reproducibles

---

## El experimento — qué se fija y qué se mide

**Piso FIJO** (obligatorio para todo modelo, andamiaje de honestidad + núcleo técnico, para
comparar modelos en igualdad): cap. 0, 1, 3-9, 10.1, 11, 12 (RHOB-NPHI + Pickett), 13, 14, 15,
16 (Archie), 21, 22, 24, 27, 29, 30, 31, 32, 33, 34. Mapean a `report_compose._MANDATORY_BODY`
+ el completeness gate.

**Zona de DECISIÓN del modelo** (señal de profundidad/creatividad): cap. 2, 10.3/10.6/10.7,
12 (Hingle/Buckles/M-N), 16 (Simandoux/Indonesia/DW/W-S), 17, 18, 19, 20, 23, 25, 26, 28, 35,
36. Mapean a `OPTIONAL_SECTIONS` (modo libre), cada una respaldada por un tool_result real.

**Qué medimos por modelo:** cuántas secciones [MODELO] eligió **y respaldó con números reales**
(profundidad), qué combinaciones (creatividad), y la calidad (claim verifier PASS + riqueza del
grafo de metodología + score same-model). El piso FIJO garantiza comparabilidad; la zona libre
revela capacidad.

> **Reparto CONFIRMADO por el usuario (DV2-18, 2026-06-28).** Las analíticas borderline
> (resistividad, caliper, litología, Rw) van **FIJO** (degradan si falta la curva). La
> permeabilidad va **MODELO con caveat** "no calibrada (sin núcleo)". El **informe por campo
> está en alcance** (no diferido), con diseño de experimento **1 pozo fijo (ancla comparable)
> + 2 pozos de libre elección del modelo**. Se cablea en `report_compose._MANDATORY_BODY` /
> `OPTIONAL_SECTIONS` conforme R4 construye cada método MODELO.
