# 07 · Integración final y pruebas de punta a punta

> **Apartado 7 · Orden 4.1** de la Tabla de Medios y Fines.
> Estado: ✅ el repositorio se instala y corre desde cero con Python 3.10 y 3.13 siguiendo solo el `README.md`. Las secciones 4.1 a 4.5 son la corrida original; la 4.6, la regresión tras los cambios de variables y la Vista 5.
> Todas las pruebas usan datos **SIMULADOS**.

## 1. Objetivo

Demostrar que cualquier persona puede clonar el repositorio, instalarlo y usar el sistema completo siguiendo solo el `README.md`, y dejar registro de las pruebas funcionales de los tres escenarios críticos:
1. **Flujo normal** (*happy path*).
2. **Borde de desabasto** (margen < 4 %).
3. **Modo respaldo de Gemini** (*fallback*).

## 2. Medios utilizados

| Medio | Uso |
|---|---|
| `git clone` desde GitHub en carpeta vacía + entorno virtual nuevo | Simula una computadora limpia. |
| Python 3.10.20 y 3.13.18 | Versión mínima declarada y versión reciente. |
| `requirements.txt` con versiones fijas | Instalación reproducible. |
| `python -m unittest` (66 pruebas; 56 en la corrida original) | Pruebas unitarias y de API. |
| `scripts/prueba_humo.py` (8 casos) | Prueba de punta a punta por HTTP; cualquiera la puede correr. |
| Chromium + Playwright (8 casos) | Prueba de punta a punta en navegador. |
| Llamada real a la API de Gemini con llave falsa | Verifica el respaldo ante un error real de Google. |

## 3. Decisiones de integración

| Decisión | Motivo |
|---|---|
| `google-genai==1.33.0` en lugar de 3.6.1 | La 3.6.1, usada durante el desarrollo, salió hace días y **exige Python ≥ 3.11**. La 1.33.0 acepta Python ≥ 3.9 e incluye todo lo que usamos: `response_schema`, `ThinkingConfig`, `HttpOptions(timeout)`. |
| `httpx==0.28.1` | Lo exige `google-genai` 1.x; se verificó que el `TestClient` de FastAPI 0.115.5 funciona con esta versión. |
| `pydantic==2.10.6` | Versión estable compatible con FastAPI 0.115.5 y `google-genai`. |
| `python-dotenv` para leer `.env` | Estándar; si no estuviera instalado, el sistema tiene un lector mínimo propio. |
| La llave de ejemplo `tu_api_key_aqui` cuenta como "sin llave" | Si alguien copia `.env.example` sin editarlo, el sistema no intenta llamar a Google con un texto de ejemplo. |
| `pandas` incluido en `requirements.txt` | Lo pide la guía del taller para análisis exploratorio. El código actual no lo importa: el modelo trabaja con `sqlite3` y `numpy`. |
| `scripts/prueba_humo.py` solo con librería estándar | Un juez lo corre sin instalar nada adicional. |

## 4. Bitácora de pruebas

Fecha: **2026-11-26**. Repositorio clonado desde GitHub (rama de trabajo) en carpetas vacías.

### 4.1 Instalación desde cero

| ID | Prueba | Python 3.10.20 | Python 3.13.18 |
|---|---|---|---|
| INS-01 | `git clone` | ✅ 0.4 s | ✅ |
| INS-02 | `python -m venv .venv` + `pip install -r requirements.txt` | ✅ 13 s, sin conflictos | ✅ 23 s, sin conflictos |
| INS-03 | Importar todas las dependencias (`fastapi`, `uvicorn`, `pydantic`, `sklearn`, `numpy`, `pandas`, `dotenv`, `google.genai`) | ✅ | ✅ |
| INS-04 | `python data/generar_datos.py` | ✅ 14,159 registros, "Verificación OK" | ✅ |
| INS-05 | `uvicorn backend.main:app`: arranque con entrenamiento automático del modelo | ✅ listo en 5.7 s | ✅ |
| INS-06 | `python -m unittest discover -s tests` | ✅ 56/56 en 11.2 s | ✅ 56/56 |
| INS-07 | `python scripts/prueba_humo.py` | ✅ 8/8 | ✅ 8/8 |

### 4.2 Prueba de humo por HTTP (`scripts/prueba_humo.py`, Python 3.10)

| ID | Caso | Resultado | Detalle observado |
|---|---|---|---|
| HUMO-01 | Servidor y datos SIMULADOS listos | ✅ | `estado: ok`, `es_simulado: true` |
| HUMO-02 | Frontend servido en `/` | ✅ | `index.html` con distintivo "Datos Simulados" |
| HUMO-03 | Inventario con semáforo | ✅ | 4 críticos de 47 lotes, ordenados por horas |
| HUMO-04 | **Happy path:** viernes de quincena con lluvia, pollo, margen 8 % | ✅ | 186 clientes, compra 15.84 kg, $2,138 MXN, merma evitada $220 |
| HUMO-05 | **Borde de desabasto** | ✅ | 3.9 % → alerta · 4 % → sin alerta · 30 % → error 422 |
| HUMO-06 | Promociones sobre platillos existentes y rentables | ✅ | Modo respaldo (sin llave): Enchiladas Suizas, Hamburguesa Clásica, Pollo a la Plancha; todas con precio ≥ 1.5 × costo |
| HUMO-07 | Alerta temprana a las 15:00 con ritmo lento | ✅ | Ficha de 13 porciones (con 20 preparadas), ventana 16:00–18:00, envío registrado como SIMULADO |
| HUMO-08 | Auditoría de 7 días sin fuga de datos | ✅ | Merma −76.6 %, 95.38 kg, $7,256 MXN; modelo entrenado hasta el día anterior al periodo |

### 4.3 Prueba en navegador (Chromium, servidor de la instalación limpia con Python 3.13)

| ID | Caso | Resultado | Detalle observado |
|---|---|---|---|
| E2E-01 | Carga inicial | ✅ | Distintivo "⚠️ Entorno de Validación: Datos Simulados" e indicador "API conectada" |
| E2E-02 | **Happy path Vista 1:** escenario "Viernes de Quincena + Lluvia" | ✅ | 186 clientes · 15.8 kg · $2,138 MXN · merma evitada 1.63 kg; sin banner de desabasto |
| E2E-03 | **Borde de desabasto en la interfaz** | ✅ | Con 3 % aparece el banner rojo; con 4 % desaparece; el botón "Usar" aplica el margen recomendado (12 %) |
| E2E-04 | **Fallback de Gemini en Vista 2** (sin llave) | ✅ | Distintivo "Reglas locales (modo respaldo)" con el motivo "No hay GEMINI_API_KEY configurada…"; 3 tarjetas y menú QR |
| E2E-05 | Vista 3: alerta, ficha y envío | ✅ | Ficha 4:00–6:00 PM, toast "Envío SIMULADO"; a las 5:30 PM ya no ofrece ficha (sin ventana viable) |
| E2E-06 | Vista 4: auditoría y fuentes | ✅ | −76.6 % · 95.4 kg · $7,256 MXN · demanda no cubierta 0.07 %; acordeón con PROFECO y metodología |
| E2E-07 | Sin servidor (`file://`) | ✅ | Indicador "Modo demo autónoma"; la Vista 1 calcula (116 clientes en martes) |
| E2E-08 | Consola del navegador | ✅ | Sin errores |

Nota: en el entorno de prueba los CDN estaban bloqueados, así que Tailwind, Chart.js y Lucide se sirvieron desde copias locales de las mismas versiones. Falta una prueba con los CDN reales (sección 6).

### 4.4 Modo respaldo de Gemini: casos probados

| ID | Situación | Cómo se probó | Resultado |
|---|---|---|---|
| FB-01 | Sin `.env` ni variable `GEMINI_API_KEY` | Instalación limpia, Vista 2 y prueba de humo | ✅ `modo: fallback`, motivo "No hay GEMINI_API_KEY configurada…"; promociones y ficha completas |
| FB-02 | `.env` copiado sin editar (`tu_api_key_aqui`) | `cp .env.example .env` y arranque | ✅ `gemini_configurado: false`; respaldo inmediato, sin llamar a Google |
| FB-03 | Llave inválida | `.env` con llave falsa: **llamada real** a la API de Google (SDK 1.33.0) | ✅ Google respondió 400; motivo "La GEMINI_API_KEY no es válida."; respuesta en 1.5 s |
| FB-04 | Sin internet o tiempo agotado | Prueba unitaria (`TimeoutError` simulado) | ✅ Respaldo con motivo "Gemini no respondió a tiempo" |
| FB-05 | Gemini inventa un platillo | Prueba unitaria y de API con respuesta simulada | ✅ Rechazado; respaldo con motivo "Platillo fuera del menú…" |
| FB-06 | Descuento que deja el precio bajo costo | Prueba unitaria | ✅ Rechazado ("fuera del rango rentable") |
| FB-07 | Precio equivocado dentro del texto promocional | Prueba unitaria | ✅ Rechazado ("menciona $85, pero la oferta es $90") |
| FB-08 | La ficha cambia las porciones o se sale de la ventana | Pruebas unitarias | ✅ Rechazado; ficha de respaldo con las porciones correctas |
| FB-09 | JSON inválido o vacío | Prueba unitaria con cliente falso | ✅ Respaldo |
| FB-10 | Servidor apagado a mitad de la sesión | Navegador (Apartado 5) | ✅ Toast "Se perdió la conexión…" y modo demo autónoma |

### 4.5 Borde de desabasto: resumen

| Nivel | Margen | Esperado | Observado |
|---|---|---|---|
| Modelo (`predecir_compra`) | 3.9 % / 4.0 % | `riesgo_desabasto` true / false | ✅ (prueba unitaria) |
| API (`POST /api/predecir`) | 3.9 % / 4.0 % / 30 % | alerta / sin alerta / 422 | ✅ (HUMO-05) |
| Interfaz (Vista 1) | 3 % / 4 % | banner visible / oculto | ✅ (E2E-03) |

### 4.6 Regresión tras los cambios del 2026-11-26 (festivos, épocas, eventos en la plaza y Vista 5)

Cambios probados:
- se eliminó "vacaciones escolares";
- se agregaron día festivo, época del año y evento en la plaza;
- el historial pasó de 180 a 365 días;
- el modelo pasó a índice relativo con hiperparámetros elegidos por validación cruzada;
- se agregaron la Vista 5 (Historial de compras) y `GET /api/historial-compras`;
- reentrenamiento automático al cambiar los datos, y exportación a CSV.

| ID | Prueba | Resultado | Detalle observado |
|---|---|---|---|
| REG-01 | `python -m unittest discover -s tests` | ✅ 64/64 | Incluye pruebas nuevas de festivos, épocas, Buen Fin, historial fuera de muestra, carga de un modelo entrenado desde la terminal y `/api/historial-compras` |
| REG-02 | `python scripts/prueba_humo.py` | ✅ 9/9 | Caso nuevo HUMO-09: 13 meses, ahorro en compras $914,956, merma −72.4 %, 53 semanas de pollo |
| REG-03 | Vista 1 en navegador (escritorio, `file://` y 390 px) | ✅ | "Lunes de Cuesta de Enero" → 103 clientes; sábado navideño festivo con evento en la plaza → 260 clientes, 23.5 kg de pollo; el selector cambia a "Personalizado" |
| REG-04 | Vista 5 en navegador (escritorio, `file://` y 390 px) | ✅ | Semana/todos: $3,073,057 contra $2,158,100, ahorro $914,956; por mes 13 filas; por día 365 filas; con y sin servidor difieren < $30 por redondeo; sin errores en consola ni desplazamiento horizontal |
| REG-05 | Reentrenamiento automático | ✅ | Un modelo con datos de otra versión se detectó al arrancar ("El modelo se entrenó con otra versión de los datos") y se reentrenó solo |
| REG-06 | `python scripts/exportar_csv.py` | ✅ | 12 archivos CSV en `data/csv/` (compras_diarias: 16,790 filas) |

Defecto encontrado en esta regresión: un modelo entrenado con `python ml/modelo_demanda.py entrenar` guardaba la clase como `__main__.RandomForestRelativo` y el backend no podía leerlo. Se corrigió ejecutando el comando desde el módulo `ml.modelo_demanda`; lo cubre la prueba `test_modelo_entrenado_desde_la_terminal_se_puede_cargar`.

## 5. Defectos encontrados y corregidos durante la integración

| # | Defecto | Cómo se detectó | Corrección |
|---|---|---|---|
| 1 | `google-genai` 3.6.1 no instala en Python 3.10 | Revisión de `requires_python` en PyPI | Versión fijada en 1.33.0 y probada con Python 3.10 |
| 2 | Conflicto `httpx` 0.27 contra `google-genai` 1.x | Resolución de dependencias | `httpx==0.28.1`; `TestClient` verificado |
| 3 | Copiar `.env.example` sin editar provocaba una llamada a Google con una llave de ejemplo | Revisión de la nueva plantilla | La llave de ejemplo cuenta como "sin llave" (prueba FB-02) |
| 4 | Gemini podía escribir un precio erróneo en el texto promocional | Revisión visual (Apartado 6) | Instrucción "no escribas precios" y validación del monto (FB-07) |
| 5 | La ventana de recolección podía terminar 1.5 h antes del cierre | Requisito del Apartado 6 | Límite de 2 h antes del cierre; sin ficha si ya no cabe |
| 6 | Mover el slider de hora llenaba la bitácora de fichas | Revisión del Apartado 5 | Parámetro `generar_ficha: false` para solo proyectar |
| 7 | Conexiones SQLite sin cerrar | Avisos `ResourceWarning` en las pruebas | `database.sesion()` cierra siempre |

## 6. Pendientes de verificar antes de la entrega

| Pendiente | Responsable | Cómo |
|---|---|---|
| Llamada exitosa a Gemini con una llave real | Quien tenga la llave | `python backend/gemini_service.py` → `"modo_respaldo": false` en ambas funciones; revisar que los textos sean adecuados |
| Interfaz con los CDN reales (internet normal) | Cualquiera | Abrir <http://localhost:8000> y confirmar estilos, iconos y gráficas |
| Windows (cmd / PowerShell) | Quien use Windows | Seguir el README; en PowerShell 5 correr los comandos del paso 3 por separado |
| Firefox y Safari | Cualquiera | Recorrer las 5 vistas |
| Rama de trabajo fusionada a la rama principal | Dueño del repositorio | El `git clone` del README descarga la rama principal |

## 7. Checklist de verificación previa a la entrega

En una computadora que **no** haya tenido el proyecto:

- [ ] `git clone` del repositorio y `cd Hackateate_2026`.
- [ ] `python --version` muestra 3.10 o superior.
- [ ] `python -m venv .venv`, activarlo y `pip install -r requirements.txt` sin errores.
- [ ] `python data/generar_datos.py` termina con "Verificación OK".
- [ ] `uvicorn backend.main:app --reload` arranca y <http://localhost:8000> muestra el distintivo ámbar y "API conectada".
- [ ] `python -m unittest discover -s tests` → 66 pruebas OK.
- [ ] Con el servidor encendido, `python scripts/prueba_humo.py` → 9/9.
- [ ] Sin `.env`: la Vista 2 muestra "Reglas locales (modo respaldo)".
- [ ] Con `.env` y llave real: la Vista 2 muestra "Generado con Gemini · gemini-3.5-flash-lite".
- [ ] Doble clic en `frontend/index.html` → "Modo demo autónoma".
- [ ] `git status` no muestra `.env` ni `*.db` ni `*.pkl` para subir.
- [ ] Tabla de equipo del README completa con roles y aportaciones reales.
- [ ] Enlaces de la Tabla A de `docs/08_plan_negocios.md` revisados el día de la entrega (precios de nube, Gemini y tipo de cambio cambian).

## 8. Reparto de la defensa (25 minutos)

| Bloque | Tiempo | Contenido |
|---|---|---|
| **Presentación** | 10 min | Problema y evidencia (2) · usuarios y solución en 4 momentos (2) · arquitectura y por qué cada tecnología (2) · resultados sobre datos simulados y honestidad metodológica (2) · plan de negocios (2) |
| **Demo en vivo** | 8 min | Guion de [`05_frontend_ux.md`](05_frontend_ux.md), sección 10: Vista 1 con desabasto → Vista 2 con Gemini → Vista 3 con ficha → Vista 4 → respaldo sin servidor |
| **Preguntas** | 7 min | Cada integrante responde sobre su área; preguntas preparadas al final de cada documento de `/docs` |

Recomendaciones para la demo:
- Arrancar el servidor 5 minutos antes y abrir la aplicación una vez, para que el navegador guarde las librerías del CDN.
- Tener `frontend/index.html` abierto con doble clic en otra pestaña, como respaldo.
- Si Gemini falla en vivo, no ocultarlo: el distintivo de modo respaldo es parte de la demostración.

## 9. Cómo repetir estas pruebas

```bash
python -m unittest discover -s tests -v        # 66 pruebas
uvicorn backend.main:app                       # en otra terminal
python scripts/prueba_humo.py                  # 9 casos de punta a punta
```

Las pruebas en navegador se hicieron con Playwright fuera del repositorio. Para repetirlas a mano, seguir el checklist de la sección 7 y el guion de la demo.
