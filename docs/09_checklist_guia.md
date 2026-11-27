# Checklist: OpsIA contra la Guía del Reto

Revisión inicial y correcciones del repositorio (rama `claude/zeromerma-ai-dashboard-s5nr28`, 2026-11-27) contra `Guia_del_Reto.pdf` (Reto 1 · Segunda Mesa).

Leyenda: ✅ cumple · ⚠️ parcial · ❌ falta · 👥 lo tiene que hacer el equipo (no se resuelve con código)

## 1. Problema e investigación

| # | Lo que pide la guía | Estado | Dónde está / qué falta |
|---|---|---|---|
| 1.1 | Usar la **pregunta oficial** del reto: "¿Cómo podríamos lograr que el alimento que hoy se tira llegue, a tiempo y sin fricción, a quien sí puede aprovecharlo?" | ✅ | `docs/00` sección 1 y README: pregunta oficial y, debajo, nuestra versión acotada. |
| 1.2 | Frase de delimitación: "En [lugar], [usuario] pierde o desperdicia [alimento] cuando [situación], debido posiblemente a [causa]. Hoy lo resuelve mediante [práctica actual]. Necesitamos comprobar [incertidumbre]." | ✅ | `docs/00`, "Frase de delimitación", declarada como hipótesis hasta tener entrevistas. |
| 1.3 | Usuarios identificados y **cómo se identificaron** | ⚠️ | `docs/00`, "Cómo identificamos a los usuarios": recorrido del alimento + evidencia secundaria. Se declara que no hubo entrevistas. |
| 1.4 | Investigación propia: entrevistas a 3–5 personas, observación de cierres o compras | ❌ 👥 | No hay evidencia. Hacer al menos 3 entrevistas cortas (encargados de fonda o de restaurante de plaza) y anotar fecha, perfil y hallazgos. |
| 1.5 | Separar **observado / interpretado / supuesto** | ⚠️ | El plan de negocios separa fuentes (Tabla A 🟢) y supuestos (Tabla B 🟡). Falta la parte "observado" (sale de 1.4). |
| 1.6 | Evidencia secundaria con organización, título, enlace, periodo y fecha de consulta | ✅ | `docs/08` Tabla A y `docs/00` (PNUMA, FAO, PROFECO, DENUE…). Revisar que todas tengan fecha de consulta. |

## 2. Solución y MVP

| # | Lo que pide la guía | Estado | Dónde está / qué falta |
|---|---|---|---|
| 2.1 | Comparar **al menos 3 alternativas de solución** y explicar por qué se descartaron | ✅ | `docs/00`, "Alternativas que consideramos": 4 alternativas con razón de descarte + la elegida. Resumen en el README. |
| 2.2 | MVP con el **flujo completo** funcionando | ✅ | Predicción de compra → rescate de menú → alerta a comedor → historial (`frontend/`, `backend/`). 66 pruebas automáticas y prueba de humo (`docs/07`). |
| 2.3 | Propuesta de valor y decisiones técnicas justificadas | ✅ | `docs/01` (arquitectura y decisiones), `docs/03` (modelo y por qué RF), `docs/06` (Gemini con respaldo). |
| 2.4 | Llevar el alimento "a quien sí puede aprovecharlo" | ✅ | Vista 3 · Alerta a comedores comunitarios con ventana de recolección. |
| 2.5 | Inocuidad: una fecha o foto **no certifica** que un alimento sea apto; acuerdos con el receptor | ✅ | La ficha de rescate muestra el aviso "una fecha o una fotografía no certifican que el alimento sea apto" y pide acuerdo previo con el receptor (`backend/services/alerta_excedente.py`, `frontend/app.js`, prueba en `tests/test_api.py`). También en README, `docs/00` y riesgos de `docs/08`. |
| 2.6 | **Validación con usuarios** (observar a alguien usar el prototipo en una tarea) | ❌ 👥 | Pedir a 2–3 personas que hagan "planear la compra de mañana" y anotar tiempo, dudas y errores. |

## 3. Métricas y datos

| # | Lo que pide la guía | Estado | Dónde está / qué falta |
|---|---|---|---|
| 3.1 | Métrica principal con unidad, periodo y fuente | ✅ | Merma en $MXN y kg (vista Historial, `docs/03`, `docs/07`). |
| 3.2 | Métrica de **efecto no deseado** | ✅ | Demanda no cubierta % (comprar de menos) y `riesgo_desabasto`. |
| 3.3 | Datos simulados **etiquetados** | ✅ | `origen_dato = 'SIMULADO'` en todas las tablas, aviso en README, en la interfaz y en cada doc. |
| 3.4 | No inventar cifras; sin fuente ≤ "Suficiente" | ✅ | Plan de negocios con Tabla A (fuentes) y Tabla B (supuestos marcados). |
| 3.5 | **Los ejemplos ficticios de la guía no pueden presentarse como evidencia** | ✅ | `docs/08` B10: ahora es un **escenario hipotético nuestro**, ya no se atribuye a la guía. |

## 4. Textos agregados

La frase de delimitación y las alternativas ya están en [`docs/00_resumen_proyecto.md`](00_resumen_proyecto.md), sección 1 y 2.

## 5. Repositorio y README

| # | Lo que pide la guía | Estado | Dónde está / qué falta |
|---|---|---|---|
| 5.1 | Código, `/docs` y evidencia del proceso | ✅ | `docs/00`–`docs/08`, bitácora de pruebas en `docs/07`. |
| 5.2 | Historial con **aportaciones de varios integrantes** y mensajes comprensibles | ⚠️ 👥 | Hay commits de AndreRodriguez06, CesarE-gith y DiegoHR14. Faltan Isaac y Alan. |
| 5.3 | **Issues o tablero de tareas** | ❌ 👥 | El repositorio tiene 0 issues. Crear issues (uno por apartado o tarea) o un tablero de GitHub Projects con responsables. |
| 5.4 | README: nombre y descripción | ✅ | |
| 5.5 | README: reto y problema **con evidencia** | ✅ | README, "Evidencia del problema" (PNUMA y FAO con enlace). |
| 5.6 | README: usuarios y cómo se identificaron | ⚠️ | README, "Usuarios": cómo se identificaron y aviso de que faltan entrevistas. |
| 5.7 | README: solución, flujo, propuesta de valor y decisiones | ✅ | README, "Solución y flujo" con enlace a las alternativas. |
| 5.8 | README: tecnologías y por qué | ✅ | README, tabla "Tecnologías". |
| 5.9 | README: requisitos, instalación, configuración sin secretos | ✅ | Python ≥ 3.10, pasos, `.env.example`, `.env` en `.gitignore`. |
| 5.10 | README: evidencia, **capturas** y partes simuladas | ✅ | README, "Capturas" (4 vistas en `docs/capturas/`) y "Qué es simulado". |
| 5.11 | README: **integrantes, roles y perfiles** + enlace al plan de negocios y fuentes | ⚠️ 👥 | README, "Equipo" con nombres y enlace al plan de negocios. Falta llenar el **rol** de cada uno y el GitHub de Isaac y Alan. |
| 5.12 | README: limitaciones y próximos pasos | ✅ | README, "Limitaciones y próximos pasos". |

> El README conserva las instrucciones breves para ejecutar y agrega secciones cortas con enlace a cada doc completo.

## 6. Presentación y demo

| # | Lo que pide la guía | Estado | Dónde está / qué falta |
|---|---|---|---|
| 6.1 | Demo en vivo declarando qué es simulado | ✅ | Guion de 8 min en `docs/05`; la interfaz muestra "SIMULADO" y "modo respaldo". |
| 6.2 | **Video o capturas de respaldo** por si falla la demo | ⚠️ 👥 | Existe el modo demo sin servidor (`frontend/index.html`), pero falta grabar un video corto (2–3 min) y guardar capturas. |
| 6.3 | Defensa de 25 min (10 presentación / 8 demo / 7 preguntas) | ✅ | Reparto en `docs/07` y respuestas preparadas en `docs/08`. |
| 6.4 | Diapositivas con: problema, evidencia, usuarios, investigación, alternativas, solución, métricas, negocio, equipo | ❌ 👥 | No hay presentación en el repo. Necesita 1.2, 1.4, 2.1 y 2.6 para quedar completa. |

## 7. Plan de negocios

| # | Lo que pide la guía | Estado | Dónde está / qué falta |
|---|---|---|---|
| 7.1 | Modelo de ingresos, costos, punto de equilibrio | ✅ | `docs/08` (P = $799, CV = $427.33, N* = CF/(P−CV)). |
| 7.2 | Tamaño de mercado con fuente | ✅ | DENUE (INEGI) en `docs/08`. |
| 7.3 | Competidores / alternativas actuales | ✅ | 5 comparados en `docs/08`. |
| 7.4 | Crecimiento y adquisición de clientes | ✅ | Piloto de 14 días y canales en `docs/08`. |
| 7.5 | Costos de **capacitación, coordinación y transporte** | ✅ | `docs/08` B13–B15 y tabla 4.2: capacitación $37.50/mes, coordinación $75/mes, transporte a cargo del receptor. Punto de equilibrio recalculado (14 / 41 / 81 restaurantes). |

## 8. Rúbrica (cómo vamos)

| Criterio | Peso | Situación |
|---|---|---|
| Creatividad | 15 | Fuerte: combinación ML + Gemini + redistribución. |
| Razonamiento | 15 | Fuerte en datos y modelo; débil en investigación propia y alternativas (1.4, 2.1). |
| Trabajo en equipo | 10 | Débil: faltan commits de 2 integrantes, issues/tablero y roles en el README. |
| Presentación | 20 | Pendiente (6.4). |
| Demo | 20 | Fuerte: flujo completo, modo respaldo y modo sin servidor; falta video (6.2). |
| Entregables | 10 | Bien: README completo salvo los roles. |
| Negocio | 10 | Bien: costos completos y supuestos marcados. |

## 9. Lista de revisión final

- [x] Pregunta oficial del reto + frase de delimitación (1.1, 1.2)
- [ ] 3–5 entrevistas u observaciones registradas (1.4) y validación con usuarios (2.6)
- [x] 3 alternativas con razón de descarte (2.1)
- [x] Aviso de inocuidad en la alerta (2.5)
- [x] El 10 % de merma ya no se atribuye a la guía (3.5)
- [x] README con capturas, evidencia, tecnologías y limitaciones (5.5–5.12) · [ ] roles de cada integrante (5.11)
- [ ] Commits de los 5 integrantes e issues o tablero (5.2, 5.3)
- [x] Costos de capacitación, coordinación y transporte (7.5)
- [ ] Video de respaldo y diapositivas (6.2, 6.4)
