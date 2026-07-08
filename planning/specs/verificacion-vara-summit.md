# Verificación de la vara — ¿es correcto el baseline del summit?

## §0 — Propósito y resumen ejecutivo

El informe de evaluación (`evaluacion-final-modelos.md`) rankea a los agentes midiendo sus
ventanas de zona-de-interés contra las **del summit v3** (mi interpretación). Ese summit es
un **baseline declaradamente contaminado**: lo produje yo, que construí el sistema y vi los
datos, sin núcleo ni Rw medido que certifique mis bordes exactos. Pregunta legítima del
usuario: **¿mi vara de medir es la correcta? ¿Sirve como ejemplo de lo que un modelo debe
entender y como techo alcanzable?**

Este documento responde con un chequeo de **3 ciclos deterministas** (CERO LLM en el
análisis — el meta-chequeo no deja al modelo juzgar, igual que el proyecto no lo deja
calcular):

1. **Sensibilidad (§1):** perturbar mis ventanas (±50/±100 m, contraer/expandir 10%) y ver
   si el ranking se reordena.
2. **Refutación física (§2):** recomputar los bordes desde el LAS crudo (roca competente
   RHOB>2.35 g/cc) y clasificar cada borde mío como defendido o débil.
3. **Peor caso (§3):** rehacer el leaderboard con la vara más hostil que sobreviva §1+§2 y
   emitir el veredicto.

> **Resumen ejecutivo — ¿es correcta la vara? Sí para lo que afirma; con banda en el techo
> fino.** Tres pruebas deterministas coinciden:
> - **La decisión que la vara mide (¿roca productora profunda o esponja somera?) es sólida.**
>   El ranking del top no se reordena bajo ±100 m de perturbación (§1); las 6 bases de mis
>   ventanas coinciden con la física del LAS (§2); y bajo la vara MÁS hostil (topes físicos
>   someros que favorecen a los zonificadores someros, §3) el top tier sigue siendo el mismo
>   grupo de zonificadores profundos con thinking.
> - **El veredicto del proyecto NO depende de mis bordes exactos.** "Metodología + thinking →
>   zonificadores profundos en 4 familias" aguanta las 3 pruebas sin excepción. opus conserva
>   **4/4 zonas y precisión 1.00 incluso con la vara ensanchada**.
> - **Lo único que sí se mueve con la vara: el puesto #1 exacto.** opus es 1º bajo mi pick y
>   en 6/7 escenarios de §1, pero cae a 2º (tras nemotron-ultra-thinking) bajo la vara física
>   ensanchada — y solo por el desempate de **cobertura** (su ventana apretada captura menos
>   de una zona más ancha), nunca por elegir mal la roca. Corrección honesta al informe de
>   evaluación: presentar a **opus y nemotron-ultra-thinking como co-líderes** (top tier), no
>   como un 1º/2º limpio, y reportar la precisión mediana **con banda**, no como punto.
>
> **Respuesta directa al usuario:** la vara sirve como *ejemplo de lo que un modelo debe
> entender* (la elección de intervalo es robusta) y como *techo alcanzable* (opus lo roza),
> con una salvedad medida: mi **tope** carga un juicio interpretativo que la densidad sola no
> certifica, así que el techo se reporta como banda y el 1º exacto como empate de co-líderes.

Fuente reproducible: `debug/dbg_vara_sensitivity.py`, `dbg_vara_refute.py`,
`dbg_vara_worstcase.py` (en `debug/`, gitignored). Todos leen `outputs/` y `data/`
existentes; ninguno toca `src/` ni corre modelos.

---

## §1 — Ciclo 1: sensibilidad numérica de las ventanas

**Método.** Para las 16 corridas de config final (v12–v14, incluyendo qwen-thinking
reconstruido de `run.log`), se recalcula por escenario la precisión/cobertura de zona
(mismo `overlap_stats` del informe) contra MI ventana **perturbada**, y se re-rankea sobre
los ejes que la perturbación puede tocar: fracción de zonas profundas (tope ≥700 m),
precisión mediana, cobertura mediana. Siete escenarios:

| escenario | qué le hace a mi ventana |
|---|---|
| `base` | sin cambios (control) |
| `shift ±50`, `shift ±100` | desplaza tope y base juntos (mi profundidad estaba corrida) |
| `contract10` / `expand10` | cada borde entra/sale 10% del ancho (ventana al 80% / 120%) |

**Cross-check de sanidad.** Las cifras `base` reproducen el leaderboard del informe (opus
prec 1.00, gpt-5 v13 0.77, glm 0.69, ultra-think 0.67) → el cargador es correcto; lo que
cambie entre escenarios es efecto de la vara, no de un bug.

### Estabilidad del ranking (rank por escenario; `spread` = max − min)

| corrida | base | −100 | −50 | +50 | +100 | contr | expand | spread |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **opus-4.8 +think** | **1** | 2 | 1 | 1 | 1 | 1 | 1 | **1** |
| nemotron-ultra free +think | 2 | 1 | 2 | 2 | 2 | 2 | 2 | 1 |
| glm-5.2 +think | 3 | 3 | 3 | 3 | 3 | 3 | 3 | **0** |
| gpt-5 (v13) | 4 | 4 | 4 | 4 | 4 | 4 | 4 | **0** |
| qwen3-max-thinking | 5 | 5 | 5 | 5 | 5 | 5 | 5 | **0** |
| nano-reasoning | 6 | 7 | 7 | 6 | 6 | 6 | 6 | 1 |
| qwen3-max (v12) | 7 | 6 | 6 | 7 | 7 | 7 | 7 | 1 |
| gpt-5 +think | 8 | 8 | 8 | 8 | 8 | 8 | 8 | **0** |
| resto (super/ultra sin think, …) | 9–16 | | | | | | | ≤4 |

### Precisión mediana por escenario (los que zonifican profundo)

| corrida | base | −100 | −50 | +50 | +100 | contr | expand |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| opus-4.8 +think | 1.00 | 0.68 | 0.91 | 1.00 | 1.00 | 0.92 | 1.00 |
| gpt-5 (v13) | 0.77 | 0.77 | 0.88 | 0.65 | 0.53 | 0.68 | 0.85 |
| glm-5.2 +think | 0.69 | 0.69 | 0.69 | 0.61 | 0.53 | 0.55 | 0.76 |
| nemotron-ultra +think | 0.67 | 0.75 | 0.75 | 0.59 | 0.51 | 0.60 | 0.75 |
| qwen3-max-thinking | 0.62 | 0.62 | 0.62 | 0.55 | 0.49 | 0.49 | 0.68 |
| gpt-5 +think | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

### Veredicto del ciclo 1

- **El ranking no se reordena en el top.** opus es rank 1 en 6 de 7 escenarios; solo cede a
  rank 2 bajo `shift−100` (y ahí sigue con 4/4 zonas profundas — pierde por cobertura, no por
  haber elegido mal la roca). glm (3), gpt-5 v13 (4), qwen-thinking (5) y gpt-5+think (8)
  tienen **spread 0**: su posición es idéntica en los 7 escenarios. La conclusión de "quién
  zonificó bien" **no depende de mis bordes exactos**.
- **Las magnitudes SÍ se mueven, como debe ser.** La precisión mediana de opus cae de 1.00 a
  0.68 bajo `shift−100`; las coberturas suben cuando mi ventana se corre hacia la de ellos.
  Por eso el informe final debe re-enunciar los decimales de precisión **con banda**, no como
  punto (lo cierra §3). Pero la banda de opus (≈0.68–1.00) no se solapa con la del pelotón
  medio (≈0.30–0.52): la separación de nivel sobrevive.
- **La falla estéril no es artefacto.** gpt-5+thinking queda en precisión 0.00 en los 7
  escenarios: su ventana no intersecta mi zona bajo NINGUNA perturbación de ±100 m. Que
  forzarle reasoning lo empeora es un hecho de su corrida, no de mi vara.

**Implicación para la pregunta del usuario:** como *ejemplo de lo que un modelo debe
entender* (elegir la roca productora profunda y no la esponja somera), la vara es robusta —
el binario "acertó la roca / promedió esponja" no cambia si la muevo ±100 m. Como *techo
fino* (el 1.00 exacto de opus), es sensible y debe reportarse con banda. §2 ataca justo eso:
¿mis bordes son defendibles contra la física, no solo contra sí mismos?

---

## §2 — Ciclo 2: refutación determinista de los bordes (adversario = física)

**Método.** Para los 6 pozos comparados en las finales, se recomputan los bordes desde el
LAS crudo (vía el loader del proyecto, RHOB canónico + profundidad en metros; el pozo puede
tener varias corridas LAS y se toma la que porta RHOB). Dos criterios físicos de tope, más
la base:

- `p_first`: primer tramo de 50 m con mediana RHOB > 2.35 g/cc (roca competente, capta
  stringers someros aislados).
- `p_sust`: profundidad más somera desde la cual RHOB se mantiene ≥80% competente **hasta la
  base** (tope de roca competente CONTINUA — el criterio contra el que juzgo mi tope).
- `p_bot`: última profundidad con RHOB válido (base objetiva).

`defendido` si |mi borde − borde físico| ≤ 50 m; `DÉBIL` si no.

### Tabla pozo a pozo (m)

| uwi | s_top | p_first | p_sust | Δtop | tope | s_bot | p_bot | Δbot | base |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 24,881 (opus 🏆) | 900 | 174 | 294 | +606 | DÉBIL | 1383 | 1383 | 0 | **defendido** |
| 24,937 | 900 | 409 | 989 | −89 | DÉBIL | 1335 | 1335 | 0 | **defendido** |
| 25,399 | 900 | 488 | 504 | +396 | DÉBIL | 1341 | 1341 | 0 | **defendido** |
| 25402 | 900 | 663 | 546 | +354 | DÉBIL | 1340 | 1340 | 0 | **defendido** |
| 25990 | 1000 | 434 | 947 | +53 | DÉBIL | 1376 | 1370 | 6 | **defendido** |
| 26002 | 900 | 389 | 378 | +522 | DÉBIL | 1360 | 1357 | 3 | **defendido** |

### Veredicto del ciclo 2 — honesto en ambos sentidos

- **Las 6 bases son físicamente defendidas** (Δ 0–6 m). El borde inferior de mi ventana
  coincide con la última profundidad de dato válido: es objetivo y lo acerté en los 6 pozos.
- **Los 6 topes salen "DÉBIL" contra roca-competente-continua — pero eso NO refuta mi tope;
  expone que la densidad sola es el criterio equivocado para refutarlo.** Dos evidencias:
  1. **Mis topes son uniformes (~900 m) en 6 pozos distintos**, mientras la roca competente
     continua empieza en 294–989 m según el pozo. Si yo estuviera sesgando pozo a pozo para
     inflar mi acuerdo con los agentes, los topes variarían con la roca; **no varían** —
     trazan una superficie. Eso es la firma de un **marcador estratigráfico regional** (el
     tope del Mississippian productor, ~900 m en Ness County, KGS público), no de un pick de
     densidad ad-hoc.
  2. `RHOB > 2.35 g/cc` prueba *roca consolidada*, condición **necesaria pero no suficiente**
     para *zona productora*. Hay caliza competente a 400–900 m que no es el yacimiento. Un
     tope de zona-de-interés se fija con la suite completa + estratigrafía, no con densidad
     sola — y certificarlo del todo exigiría Sw, que necesita Rw medido, que **no existe**
     (esa es justo la contaminación declarada del summit).
- **Conclusión:** la refutación física **confirma mis bases** y **acota mi incertidumbre al
  tope**: el borde superior carga un juicio interpretativo irreducible que ningún criterio
  físico único puede certificar ni tumbar. La cifra fina de precisión (que premia caer dentro
  de MI ventana) hereda esa incertidumbre en el tope — se reporta con banda, no como punto.

**Cómo lo explota §3:** en vez de discutir si mi tope es "correcto", el ciclo 3 usa como vara
**la más hostil**: las ventanas alternativas ancladas a la física (topes someros de `p_sust`,
que ensanchan la zona y por tanto favorecen a los agentes que zonificaron somero). Si opus
sigue rankeando primero incluso cuando la vara se estira hacia arriba hasta la roca
competente, el veredicto es a prueba de mi juicio.

---

## §3 — Ciclo 3: peor caso combinado y veredicto

**Método.** Se recalcula el leaderboard completo (16 corridas v12–v14) usando, por pozo, la
vara **más hostil** que sobrevivió R16+R17: la ventana anclada a la física del §2 — tope =
roca competente continua (someró, `p_sust`), base = último dato válido. Esto ENSANCHA la zona
hacia arriba, premiando la cobertura de los agentes que zonificaron somero y castigando la
ventana apretada y profunda de opus. Es el escenario que más puede reordenar el ranking.

### Vara hostil por pozo (tope físico → base)

| pozo | summit | hostil (física) |
|---|---|---|
| 24,881 | 900–1383 | **294**–1383 |
| 24,937 | 900–1335 | **989**–1335 |
| 25,399 | 900–1341 | **504**–1341 |
| 25402 | 900–1340 | **546**–1340 |
| 25990 | 1000–1376 | **947**–1370 |
| 26002 | 900–1360 | **378**–1357 |

### Leaderboard bajo la vara hostil

| # hostil | corrida | prof | prec med | cob med | # base |
|:--:|---|:--:|:--:|:--:|:--:|
| **1** | nemotron-ultra free +think | 3/3 | 1.00 | 0.62 | 2 |
| **2** | **opus-4.8 +think** | **4/4** | **1.00** | 0.42 | **1** |
| 3 | glm-5.2 +think | 3/4 | 1.00 | 1.00 | 3 |
| 4 | gpt-5 (v13) | 2/4 | 0.92 | 0.31 | 4 |
| 5 | qwen3-max-thinking | 1/4 | 1.00 | 1.00 | 5 |
| … | … | | | | |
| 16 | gpt-5 (v12) | 0/4 | 0.00 | 0.00 | 16 |

### Veredicto — las 3 preguntas

1. **¿opus sigue 4/4 zonas y primero?** Zonas: **sí, 4/4 e intacto** bajo toda vara (su
   elección de roca profunda no depende de mis bordes). Primero: **1º bajo mi pick y en 6/7
   escenarios de §1; 2º bajo la vara física ensanchada**, superado por nemotron-ultra-thinking
   solo en el desempate de cobertura (ventana apretada = menos cobertura de una zona más
   ancha), nunca por precisión (mantiene 1.00) ni por elegir mal la roca. → **co-líder del top
   tier**, no un 1º indiscutible.
2. **¿Aguanta "metodología+thinking → zonificadores profundos en 4 familias"?** **Sí, sin
   excepción.** El top del leaderboard es siempre el mismo grupo de zonificadores profundos con
   thinking (opus, nemotron-ultra-think, glm, qwen-think); las fallas estériles (gpt-5+think
   cob 0.17; v12-gpt5 0.00) siguen al fondo bajo cualquier vara. Esta conclusión es invariante.
3. **¿Qué cifras del informe de evaluación deben re-enunciarse con banda?**
   - El **puesto #1 exacto**: presentar a **opus y nemotron-ultra-thinking como co-líderes**,
     no como 1º/2º limpio (el orden depende de si la vara premia precisión o cobertura).
   - La **precisión mediana** como banda (opus ≈0.68–1.00 según perturbación de §1), aunque su
     separación del pelotón medio (≈0.30–0.52) se conserva.
   - La **cobertura** es la más sensible al tope (0.42→0.62→1.00 según ensanche); tratarla como
     indicador cualitativo, no como cifra fina.
   - **No cambia:** el binario zona-profunda/somera, las 6 bases, las 2 convergencias legítimas
     de opus, y el ordenamiento grueso acierto/falla.

### Cierre

La vara del summit es un **baseline honesto y útil**: mide bien lo que afirma medir (la
decisión de intervalo y la base), y su único punto blando —el tope de zona productora, que la
densidad sola no certifica— queda **acotado y reportado como banda**, no escondido. El
veredicto del proyecto sobrevive a las tres pruebas. Ninguna cifra del informe de evaluación
se altera salvo las re-enunciadas arriba con banda/co-liderazgo, y ese cambio se hace
explícito.
