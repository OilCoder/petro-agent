# Evaluación final de modelos — petro-agent v7→v14

**Fecha**: 2026-07-07 · **Benchmark**: summit v3 (72 pozos, verifier 72/72) — informe del
analista-Claude declarado *techo contaminado* (conocía el proyecto por dentro; no compite,
calibra). **Fuente de cifras**: `debug/dbg_final_evaluation.py` sobre los ledgers/metrics
reales de `outputs/v4..v14` + lectura directa de prosa. Nada de memoria.

Este informe tiene **dos audiencias**: 🖥️ el programador (¿cómo se comporta cada modelo
dentro de un sistema de agentes?) y 🛢️ el petrolero (¿qué tan buenos son los análisis y
quién se acerca a un ingeniero?). Cada sección marca su lente cuando difieren.

---

## 1. Resumen ejecutivo y leaderboard

Tras 8 versiones de batch y 4 rondas de mejoras honestas (memoria, consecuencia,
herramientas, borradores, thinking), el leaderboard final sobre los mismos pozos de
Schaben es:

| # | Modelo (config final) | Zona productora | Precisión de zona¹ | PHIE plausible | Convergencias legítimas² | Costo/batch | Nota |
|---|---|---|---|---|---|---|---|
| 🥇 | **claude-opus-4.8 + thinking** | 4/4 topes ≥700 m | **1.00** | **4/4** | **2** (únicas del proyecto) | ~$13 | El único perfil "senior delegando" |
| 🥈 | **z-ai/glm-5.2 + thinking** | 3/4 | 0.69 | 4/4 | 0 | ~$2 | La revelación calidad/costo |
| 🥉 | **nemotron-ultra 550B free + thinking** | 3/3 | 0.67 | 2/3 | 0 | **$0** | El mejor gratuito |
| 4 | qwen3-max-thinking | 1/4 profunda; final 1176–1350 | 0.62 | 2/4 | 0 | ~$3.5 | El A/B más limpio del proyecto |
| 5 | nemotron-nano-omni 30B free (thinking) | 1/4 en batch; **óptimo en iteración** | 0.47 | 3/4 | 0 | $0 | Convergedor exploratorio: necesita ciclos |
| 6 | gpt-5 (default reasoning) | 2/4 en v13 (su mejor) | 0.77 (v13) → **0.00** (+think) | 1–3 | 0 (**4 ceros estériles** acumulados) | ~$5 | Gran ejecutor, brújula somera |
| 7 | qwen3-max (sin thinking) | 0 profundas en 12 pozos | 0.38–0.45 | 2–3 | 0 | ~$2 | Recortador de overburden |
| 8 | nemotron-super 120B (±thinking) | 0 profundas en ~16 pozos | 0.38 | 1–2 | 0 | $0 | Rígido: inmune a toda palanca |
| 9 | gpt-oss-20b (thinking) | 0 | — | 0 | 0 | $0 | Deriva sin brújula de plausibilidad |
| — | gemma-4 26b/31b | nunca completó | — | — | — | $0 | 9× 429 upstream; sin veredicto |
| — | deepseek-r1, locales (qwen3:30b, llama3.1) | histórico pre-stack | — | — | — | — | Ver §3 |

¹ *Precisión mediana*: fracción del intervalo elegido por el agente que cae DENTRO de la
ventana productora del summit en el mismo pozo. ² *Convergencia legítima*: sin abstención
Y con net pay real (>0.5 m) — distinta del "cero estéril" (converger porque la zona no
tiene nada que objetar… ni pay).

> **Verificación de la vara (2026-07-07, `verificacion-vara-summit.md`).** La vara (mis
> ventanas) fue sometida a 3 pruebas deterministas: perturbación ±100 m, refutación física
> de bordes desde el LAS crudo, y leaderboard bajo la vara más hostil. Resultado: **el
> ranking del top es estable** y el veredicto de las 4 familias es invariante; las 6 bases
> de mis ventanas coinciden con la física (Δ 0–6 m) y el tope (~900 m uniforme = marcador
> regional Mississippiano) carga un juicio interpretativo que la densidad sola no certifica.
> Correcciones honestas que esto impone a la tabla de arriba: (a) la **precisión se lee como
> banda**, no como punto — opus ≈0.68–1.00 según la perturbación, sin solaparse nunca con el
> pelotón medio (≈0.30–0.52); (b) bajo la vara física ensanchada, **opus y nemotron-ultra
> +thinking son co-líderes**: opus mantiene 4/4 zonas y precisión 1.00 pero cede el
> desempate por cobertura (ventana apretada vs zona ensanchada) — el 🥇/🥉 exacto depende de
> si la vara premia precisión o cobertura, nunca de la elección de roca.

**La frase del proyecto**: el modelo que en v10 hizo **cero decisiones en 16 pasos**
(opus) terminó siendo, con las condiciones naturales del ingeniero, **el único agente
cuyas ventanas caen al 100% en roca productora** y el único que convergió legítimamente
con pay — incluida la del pozo que todos los demás fallan (24,881: 1150–1350 m, 13.0 m de
pay, PHIE 0.146).

---

## 2. Metodología de evaluación

- **Benchmark**: mis 25 zonas clase-A del summit v3 (topes 900–1100 m, Mississippiano
  consolidado), con contaminación declarada — sirven de "respuesta del profesor", no de
  competidor. La abstención del sistema NO penaliza: sin core ni Rw medido, abstenerse es
  lo correcto (yo también abstengo en 24/25 clase-A).
- **Ejes cuantitativos** (script E1): zona (existencia, tope ≥700 m, precisión/cobertura
  vs summit), plausibilidad física (PHIE ≤ 0.25 en carbonato), convergencias legítimas vs
  ceros estériles, autoría de métodos, eficiencia de evidencia (decisiones/observaciones),
  repeticiones de lectura, uso real de herramientas, respuesta al reintento, disciplina de
  borradores (revisiones aceptadas/rechazadas por el claim verifier).
- **Eje cualitativo** (lectura directa): prosa de resúmenes ejecutivos en pozos-ancla
  (24,881 y 25990) — historia de roca, tono ligado al tier, argumentación de evidencia.
- **"Aceptable"** = zona en roca correcta + física plausible + honestidad intacta +
  prosa defendible. No exige convergencia (el techo ahí es de datos).

---

## 3. La evolución v7→v14 — qué cambió cada ronda y qué produjo

| Era | Estado de los agentes | Evidencia |
|---|---|---|
| v4–v7 (pre-autor) | Revisores pasivos de un pipeline precomputado: 0 zonas, 0–1 decisiones; los 4 frontier convergían a un perfil idéntico entre seeds | tabla E1: zones=0/4 en todas las filas v4–v7 |
| v8–v10 (flip autor) | Autoran métodos (authored_core 7–12) pero **nadie zonea** (1/24, solo qwen — adjudicada como roca equivocada); promedian overburden → PHIE 0.35–0.40, pays de 200–470 m, abstención universal | v10: opus authored=0 (el famoso "observador puro") |
| v11 (GA: field pack, evidencia) | **La zona aparece: 13/15 pozos** — pero somera (recorte de overburden); ~80% de las observaciones eran RELECTURAS (amnesia del slot único) | gpt-5: un pozo con 32/32 pasos releyendo 2 observaciones |
| v12 (GB: journal, digest, paridad) | Relecturas **0** en todos; compromiso ↑ (authored 10→26); eficiencia hasta 1.2; primera adopción de rw_evidence/mhi | tabla v12 |
| v13 (GC: reintento, hipótesis, localización) | El reintento MUEVE zonas: gpt-5 cruza a 900–1326 y refina a 1040–1300; qwen baja topes 3/4; precisión gpt-5 llega a 0.77 | retry_moved_zone en tabla |
| v14 (GD + thinking) | Borradores revisados por todos (49 aceptadas, 2 rechazadas por el verifier en total); **thinking transforma a los híbridos**: ultra 0→3/3 profundas; y opus produce el mejor resultado del proyecto | §1 |

🛢️ Para el petrolero: en v7 estos "analistas" reportaban 300 m de pay en lutitas someras
con porosidad de esponja. En v14, los mejores entregan ventanas Mississippianas correctas
con porosidades creíbles y pays de 2–13 m — el orden de magnitud real de Schaben.

---

## 4. Fichas por modelo

### claude-opus-4.8 (+thinking) — 🥇 el analista
- **Fortalezas**: precisión de zona 1.00 (4/4 ventanas 100% dentro de roca productora,
  todas MÁS apretadas que las mías — recall 0.48: elige el corazón del intervalo);
  4/4 PHIE plausible; las 2 únicas convergencias legítimas con pay; **la mejor prosa de
  agente** — explica el *porqué* del bracket ("its 13.9 m swing means the wide envelope
  reflects genuine parameter uncertainty"), tono perfecto por tier.
- **Perfil**: authored_core bajo (0–1) — delega los métodos al default del motor y
  concentra TODO el juicio en el intervalo. Es el patrón de un senior con un asistente.
- **Fallas**: no ARGUMENTA la evidencia en prosa (usó rw_evidence 2×, jamás la cita);
  ancla su ventana 1150–1330 entre pozos (funciona aquí; sería riesgo en campo
  heterogéneo). Costo: el más caro (~$13/batch).
- **Evolución**: 0 decisiones (v10) → mejor agente (v14). El caso de estudio del proyecto.

### z-ai/glm-5.2 (+thinking) — 🥈 la revelación
- 3/4 profundas y 4/4 PHIE plausible EN SU DEBUT, ~$2/batch; reintentos 4/4 con 2 zonas
  movidas. Prosa correcta y honesta ("thinly developed within a predominantly
  non-reservoir section"). Falla: precisión 0.69 — ventanas más anchas que las de opus,
  arrastran sección de transición.

### nemotron-ultra 550B free (+thinking) — 🥉 el mejor gratis
- El A/B interno más elocuente del sistema: **sin thinking 0 profundas en 12 pozos; con
  thinking 3/3** (700–1323 consistente). Rico en opcionales (4/pozo), notas de campo que
  compusieron el efecto. Falla: su ventana profunda aún arrastra PHIE alto en un pozo
  (0.361 → objeción) — le falta el refinamiento fino de opus. Gratis.

### qwen3-max-thinking vs qwen3-max — el experimento gemelo
- Mismo linaje, misma data, mismo stack: **sin thinking 0 zonas profundas en 12 pozos;
  la variante thinking** produjo 1176.2–1350 m (la zona batch más fina del proyecto,
  precisión 0.62/recall 1.0 mediana) y en su corrida final 3/4 ventanas profundas en
  ledger. Falla: lentitud extrema (el batch más largo del proyecto, 3 corridas por
  incidentes) y un artefacto: sus report .md en disco pueden corresponder a intentos
  previos del batch interrumpido — la decisión FINAL vive en el ledger.

### gpt-5 — el gran ejecutor con brújula somera
- El mejor en mecánica: reintentos que aprenden (v13: 292–512 → 900–1326 → refina
  1040–1300; precisión 0.77), uso completo de herramientas, borradores disciplinados.
- **Su falla característica: los ceros estériles** — 4 acumulados (converge eligiendo
  zonas someras SIN pay, que el gate deja pasar porque un cero honesto no dispara
  plausibilidad). Y la sorpresa medida: **el reasoning explícito lo EMPEORÓ** (precisión
  0.77→0.00 mediana; su razonamiento por defecto ya operaba y forzar effort medium le
  restó geología). Prosa telegráfica, sin narrativa.

### nemotron-nano-omni 30B free — el convergedor exploratorio
- En batch (1 reintento) se queda corto (1/4 profunda). En **iteración larga** es otra
  cosa: explora (900–1100 → peor → peor) y clava el óptimo en la iter 4 (1076–1176,
  PHIE 0.189) sosteniéndolo hasta el corte. Un 30B GRATIS que con suficientes ciclos
  supera a modelos 15× más grandes. Prosa concisa y correcta.

### nemotron-super 120B — el rígido
- Recibió TODO el arsenal (memoria, consecuencia, thinking, 6 iteraciones de espejo) y
  jamás salió de zonas someras (~16 pozos, 0 profundas; plateau exacto tras un paso de
  aprendizaje en iterate15). No falla ruidosamente: repite con confianza. Es la
  demostración de que las condiciones no fabrican juicio. Prosa mecánica con P90 absurdos
  (245 m).

### gpt-oss-20b — la deriva
- Itera pero sin brújula: persigue porosidad alta en roca somera (PHIE 0.35→0.44
  empeorando), 9 iteraciones de rebote. Cualitativamente el patrón más peligroso:
  movimiento confiado en la dirección equivocada.

### Los que no pudieron competir
- **gemma-4 26b/31b**: 9 fallos 429 upstream en 3 días — el pool free de Google no
  sostiene un batch. Sin veredicto de capacidad.
- **deepseek-r1** (v10_paid): pre-stack — authored 12 pero 0 zonas; nunca re-probado.
- **Locales (qwen3:30b, llama3.1 8b)**: validaron el loop en v2–v3 (stall/churn) — el
  techo local que motivó el instrumento cloud.

---

## 5. ¿Quién aplicó mejor la metodología?

🖥️ Medido por uso REAL de cada palanca (no por tenerla disponible):

| Palanca | Mejor aplicación | Peor |
|---|---|---|
| Journal (no releer) | Todos post-GB: 0 repeticiones en ~30 pozos | (pre-GB: gpt-5 32/32) |
| compare/validate_choice | qwen3-max (40 usos v11); opus/glm (dosificado: 3–4) | qwen-think final (0: decide directo) |
| rw_evidence / mhi_scan | gpt-5 (4+3 — el más curioso); glm (3+3) | qwen/nano (0) |
| Reintento que aprende | gpt-5 v13 y opus (2/3 movieron zona a mejor) | super (0 movimientos en 8 reintentos) |
| Notas/digest cross-well | ultra (eficiencia 0.12→0.55 con notas) y opus (propagó su ventana) | — |
| Borradores GD | Todos (49 revisiones); el verifier rechazó 2 intentos de número inventado (qwen, nano) — la guardia funcionó en vivo | — |
| interval_stats / review_attempts | Subutilizadas por todos (el smoke las validó; los modelos casi no las piden) | — |

**Veredicto**: *mejor metodología ≠ más herramientas usadas*. gpt-5 es el usuario más
intensivo del instrumental y no es el mejor analista; opus usa poco y decide bien. La
metodología óptima observada es la de opus: **pocas lecturas, la decisión correcta,
delegar lo mecánico** — con la reserva de que casi nadie ARGUMENTA la evidencia en la
prosa (la usan para decidir, no para defender; el summit hace ambas).

---

## 6. Taxonomía de fallas (dónde y por qué fallan)

1. **Amnesia** (~80% relecturas) — ✅ RESUELTA por sistema (journal GB-1). Ya no es del modelo.
2. **Zona somera**: recortar overburden y quedarse en la sección porosa no productora
   (184–550 m). Persistente en super, qwen-sin-thinking, gpt-5+think. Causa: leen
   "porosidad alta = interesante" en vez de "consolidación = evaluable".
3. **Ceros estériles**: converger en zonas sin pay (gpt-5 ×4). El gate se comporta
   (un cero honesto no es implausible) pero el modelo lo lee como éxito. Mitigación
   futura: puntuar interpretación defendible, no ausencia de objeciones (riesgo Goodhart
   documentado).
4. **Rigidez**: inmunidad a la consecuencia (super). Se mide (plateau), no se corrige.
5. **Deriva sin brújula**: iterar hacia el atractor equivocado (gpt-oss-20b persiguiendo
   PHIE alto). Peor que la rigidez: movimiento confiado y errado.
6. **Argumentación rasa**: eligen bien y justifican pobre ("gave a smoother trend");
   nadie discute sistema de lodo, era de herramienta ni modelo litológico.
7. **No-adopción de evidencia Rw**: la banda SP→Rw existe como observación; ninguno la
   incorpora al argumento ni cuestiona el default con ella.
8. **Anclaje cross-well**: la memoria homogeneiza (qwen copió una zona dígito a dígito;
   opus fija 1150–1330 en 3 pozos). Aquí benigno; riesgo en campos heterogéneos.
9. **Infraestructura** (no del modelo): cuota free 1000/día, 429 upstream de pools
   populares, 402/401 de créditos/key — 3 días de incidentes documentados.

---

## 7. Costos (medidos, no estimados)

| Config | Costo/batch (4 pozos con reintentos+borradores) | $/pozo-aceptable³ |
|---|---|---|
| nemotron-ultra free + thinking | $0 (cuota 1000 req/día) | $0 |
| nano free (en iteración, 6 ciclos) | $0 | $0 |
| glm-5.2 | ~$2 | ~$0.7 |
| qwen3-max-thinking | ~$3.5 (por corrida; costó ×3 por incidentes) | ~$1.7 |
| gpt-5 | ~$5 | — (0 pozos plenamente aceptables) |
| opus-4.8 | ~$13 | **~$3.3** |
| **Total pagado del proyecto** (v7→v14, todos los legs) | **≈ $50** | |

³ pozo-aceptable = zona productora + PHIE plausible. La lectura económica: **la frontera
calidad/costo la definen ultra-free y glm-5.2**; opus compra la última milla (precisión
1.00 y convergencias) a 6× el precio de glm. El thinking se factura como salida — es el
driver del costo en todos los pagos.

---

## 8. Contra el summit: lo alcanzado y la brecha residual

**Alcanzado** (los mejores agentes vs mi informe):
- Zona: opus/qwen-think/nano eligen DENTRO de mis ventanas, a veces más fino que yo.
- Física: PHIE plausible campo-wide en opus/glm — la objeción que definió 10 versiones,
  superada.
- Honestidad: idéntica por construcción (es del sistema): 0 números sin respaldo en ~60
  informes; 2 intentos rechazados en vivo.

**Brecha residual** (lo que sigue siendo solo del summit):
- **Síntesis de campo**: 72 pozos en dos clases etiquetadas, mapa PLSS, estadística
  cross-well, capítulo vintage — los agentes hacen 4 pozos sin correlacionarlos.
- **Calibración**: adoptar la banda SP→Rw en el MC con provenance fue MI decisión de
  analista; ningún agente la tomó.
- **Argumentación de evidencia en prosa**: mi resumen cita el SP-Rw con asunciones
  declaradas; el mejor agente (opus) decide bien pero argumenta genérico.
- **Calibración junior/senior** (bitácora 2026-07-06): los mejores = junior sólido
  rozando mid en pozo individual; la seniority visible (QC, brackets, abstención) vive
  en el MOTOR. Nadie toca calibración de parámetros, correlación ni economía.

---

## 9. Hallazgos transversales y recomendaciones

**Hallazgos** (cada uno con su experimento):
1. **El entorno era la mitad del problema** — y esa mitad se resolvió por ingeniería:
   autor-no-revisor (1→7 decisiones), journal (80%→0 relecturas), consecuencia
   (zona 1/24→13/15), borradores (49 revisiones sin una fuga de números).
2. **El thinking transforma a los híbridos que corrían apagados** (ultra 0→3/3;
   gemelo qwen 0→profundas) **y no añade nada a los que ya piensan** (gpt-5 empeoró).
3. **La iteración amplifica lo que el modelo ya es**: al rígido lo sella (super), al
   explorador lo converge (nano), al sin-brújula lo pasea (gpt-oss).
4. **La honestidad es del sistema, el juicio es del modelo** — la combinación
   honestidad-senior + juicio-junior ya es útil; la distribución de juicio entre
   modelos quedó medida, no supuesta.
5. **El dinero no compra juicio linealmente**: super (120B, gratis o pago) < nano (30B,
   gratis, con ciclos); y el mejor pagó su precio en la decisión, no en el tamaño.

**Recomendaciones de producción** 🖥️:
- Pipeline free-primero: **ultra+thinking** para el barrido; escalar a **glm-5.2** los
  pozos donde ultra abstenga feo; reservar **opus** para pozos de decisión (su $3.3 por
  pozo-aceptable es el mejor $/calidad del tier alto).
- No usar gpt-5 sin un guard anti-cero-estéril (puntuar pay>0 en la convergencia).
- Nano solo con presupuesto de iteración (≥4 ciclos); super y gpt-oss-20b: no.
- Presupuestar la cuota free (1000 req/día) y verificar la key tras cada recarga.

---

## Anexos

**A. Matriz completa**: salida de `debug/dbg_final_evaluation.py` (reproducible;
columnas: zonas, deep700, precisión/cobertura vs summit, plausibilidad, convergencias,
autoría, eficiencia, herramientas, reintentos, borradores).

**B. Trayectorias iterate15** (pozo 25990, benchmark 900+):
- super: ∅ → 205.7–1376 → plateau exacto ×4 (corte).
- nano: 900–1100 → 800–1300 → 600–700 → **1076–1176 (PHIE 0.189)** → sostiene ×2 (corte).
- gpt-oss-20b: ∅ → 205–1326 → … deriva somera con PHIE creciente (0.35→0.44), 9 iters.

**C. Incidentes operativos**: gemma 9× 429 upstream; cuota free agotada 1 día (1000);
402 créditos ×2 (gpt-5 v14-default parcial 2/4; qwen 3/4); 401 key revocada tras recarga
(qwen re-runs; opus completó antes). Ninguno afectó la integridad de los datos usados aquí.

**D. Nota de artefacto**: los `report_*.md` de qwen3-max-thinking en disco pueden
corresponder a intentos previos de sus batches interrumpidos; la decisión final de cada
pozo es la del `*_ledger.json` (fuente usada por este informe).
