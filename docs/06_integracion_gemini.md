# 06 · Integración de Google Gemini (sin chatbots)

> **Apartado 6 · Orden 3.1** de la Tabla de Medios y Fines.
> Estado: ✅ implementado y probado sin llave (`tests/test_gemini_service.py`, 22 pruebas; total del repositorio, 65).
> ⏳ **Pendiente:** probar con una `GEMINI_API_KEY` válida. Ver la sección 9.

> ⚠️ Gemini trabaja sobre datos **SIMULADOS** (inventario, menú y precios del Apartado 2). La interfaz siempre indica si un resultado viene de Gemini o del modo respaldo.

## 1. Objetivo

Usar IA generativa solo donde aporta, en **dos tareas cerradas** con salida JSON de esquema fijo:

| Función | Entrada | Salida | Dónde se ve |
|---|---|---|---|
| **A** `generar_promociones_menu(inventario_critico, menu_restaurante)` | Insumos que caducan en < 24 h con su costo, y el recetario | Platillos **del menú actual** con descuento rentable, justificación y texto para el menú digital | Vista 2 |
| **B** `generar_alerta_recoleccion(excedente_proyectado, hora_actual)` | Platillo, porciones, kg, si requiere frío | Ficha operativa: producto, porciones exactas, ventana que termina ≥ 2 h antes del cierre, inocuidad y mensaje | Vista 3 |

No hay caja de chat ni conversación: el usuario pulsa un botón y recibe una propuesta estructurada.

## 2. Medios utilizados

| Medio | Uso |
|---|---|
| SDK oficial `google-genai` 1.33.0 (`from google import genai`; compatible con Python 3.10+) | Cliente de la API de Gemini. |
| Modelo `gemini-3.5-flash-lite` | Rápido y económico para tareas cortas; soporta salidas estructuradas; cambiable con `GEMINI_MODEL`. |
| Structured Outputs: `response_mime_type="application/json"` + `response_schema=<modelo Pydantic>` | La respuesta llega como JSON que cumple el esquema. |
| Pydantic | Define los esquemas y valida la respuesta. |
| `backend/gemini_service.py` | Las dos funciones, validaciones y modo respaldo. |
| `tests/test_gemini_service.py` | 22 pruebas con respuestas simuladas del modelo, sin red. |

### 2.1 Elección del modelo (revisado el 2026-11-27)

| Dato | Fuente |
|---|---|
| `gemini-2.5-flash` ya no se ofrece a proyectos nuevos: solo sigue disponible para quienes lo usaban, sin fecha de apagado anunciada en la API de Gemini; Google recomienda 3.5 Flash-Lite o 3.8 Flash para proyectos nuevos. En Google Cloud (Vertex) su retiro está programado para el 20 de octubre de 2026. | Google, [Gemini deprecations](https://ai.google.dev/gemini-api/docs/deprecations) y [ciclo de vida en Google Cloud](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions), consultados el 2026-11-27 |
| `gemini-3.5-flash-lite`: salidas estructuradas soportadas; USD 0.30 por millón de tokens de entrada y USD 2.50 por millón de salida (nivel estándar de pago). | Google, [modelo Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) y [precios de la API](https://ai.google.dev/gemini-api/docs/pricing), consultados el 2026-11-27 |
| `gemini-3.8-flash`: USD 0.75 entrada / 3.75 salida por millón hasta el 31/12/2026, y USD 1.50 / 7.50 desde el 1/1/2027. | Mismas fuentes |

Por eso el modelo por defecto es **`gemini-3.5-flash-lite`**: mismo precio que tenía 2.5 Flash, disponible para llaves nuevas y con salidas estructuradas. Si la llave no tiene acceso a un modelo, el respaldo lo indica: "El modelo … no está disponible para esta llave".

> No se ha probado una llamada exitosa con llave real (ver sección 9).

## 3. Configuración

```bash
pip install -r requirements.txt
cp .env.example .env        # y cambiar tu_api_key_aqui por la llave de Google AI Studio
python backend/main.py
```

| Variable | Por defecto | Uso |
|---|---|---|
| `GEMINI_API_KEY` | (vacía) | Sin llave todo funciona en modo respaldo. |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Modelo a usar. |
| `GEMINI_TIMEOUT_MS` | `15000` | Tiempo máximo de espera antes de pasar al respaldo. |

Se leen de las variables de entorno o del archivo `.env` en la raíz. `.env` está en `.gitignore`: **la llave nunca se sube al repositorio**. `GET /api/salud` responde `gemini_configurado: true/false`.

## 4. Principio de diseño: Python hace las cuentas, Gemini decide y redacta

```mermaid
sequenceDiagram
    participant UI as Frontend
    participant API as FastAPI
    participant R as rescate_menu.py
    participant G as gemini_service.py
    participant GM as Gemini 3.5 Flash-Lite
    UI->>API: POST /api/optimizar-menu
    API->>R: insumos críticos (SQLite)
    R->>G: generar_promociones_menu(críticos, menú)
    G->>G: filtra candidatos y calcula descuento máximo rentable
    G->>GM: instrucción + JSON de candidatos + response_schema
    GM-->>G: JSON {promociones: [...]}
    G->>G: Validación 1: menú, insumos críticos, rango rentable, precio en el texto
    alt válida
        G-->>R: modo_respaldo=false
        R->>R: Validación 2: existencias y ventas; recalcula porciones y $MXN
        R-->>API: modo "gemini"
    else sin llave, red, cuota, tiempo o validación fallida
        G-->>R: modo_respaldo=true + motivo
        R->>R: reglas locales (algoritmo voraz)
        R-->>API: modo "fallback" + motivo
    end
    API-->>UI: estrategias + distintivo de modo
```

| Lo hace Python (determinista, auditable) | Lo hace Gemini (criterio y lenguaje) |
|---|---|
| Qué insumos son críticos (< 24 h y vigentes) | Qué platillos promover entre los candidatos y en qué combinación |
| Qué platillos del menú los usan (candidatos) | Cuánto descuento dar dentro del rango rentable |
| Descuento máximo rentable de cada platillo: `floor((1 − 1.5 × costo / precio) × 100)`, tope 30 % | Justificación de negocio para el gerente |
| Valor de insumo crítico por porción | Texto apetitoso para el comensal, sin mencionar la merma |
| Ventana de recolección permitida (empieza 1 h después, límite cierre − 2 h) | Ventana exacta dentro de lo permitido |
| Porciones, kg y si requiere refrigeración | Recomendaciones de inocuidad y mensaje para WhatsApp |
| Porciones objetivo, pérdida evitada, margen recuperado | — |

## 5. Esquemas JSON (Structured Outputs)

Se definen como modelos Pydantic y se pasan en `response_schema`. El SDK los convierte al formato de esquema de Gemini, conservando tipos, campos obligatorios, rangos y longitudes; esto se verificó con `google.genai._transformers.t_schema`.

### 5.1 Función A · `RespuestaPromociones`

| Campo | Tipo | Restricción |
|---|---|---|
| `promociones` | lista de `PromocionGemini` | máximo 5 |
| `promociones[].platillo_clave` | texto | clave exacta de `platillos_candidatos` |
| `promociones[].descuento_pct` | entero | 10 a 30 (y ≤ máximo rentable del platillo) |
| `promociones[].insumos_criticos_usados` | lista de texto | informativo; el backend lo recalcula de la receta |
| `promociones[].justificacion` | texto | ≤ 220 caracteres |
| `promociones[].copy_promocional` | texto | ≤ 160 caracteres |

```json
{ "promociones": [
  { "platillo_clave": "enchiladas_suizas", "descuento_pct": 25,
    "insumos_criticos_usados": ["pollo", "crema"],
    "justificacion": "Consume pollo y crema a la vez, los dos insumos críticos de mayor valor.",
    "copy_promocional": "Enchiladas Suizas gratinadas con salsa verde cremosa. ¡Pídelas mientras duran!" } ] }
```

Salida de la función (después de validar):

```json
{ "modo_respaldo": false, "motivo_respaldo": null, "modelo": "gemini-3.5-flash-lite",
  "promociones": [ { "platillo_clave": "enchiladas_suizas", "platillo": "Enchiladas Suizas", "tipo": "descuento",
                     "descuento_pct": 25, "precio_normal_mxn": 120.0, "precio_oferta_mxn": 90,
                     "costo_porcion_mxn": 44.55, "insumos_criticos_usados": ["pollo", "crema"],
                     "justificacion": "…", "copy_promocional": "…" } ] }
```

### 5.2 Función B · `FichaGemini`

| Campo | Tipo | Restricción |
|---|---|---|
| `producto` | texto | igual al excedente |
| `porciones` | entero ≥ 1 | **exactamente** las del excedente |
| `ventana_inicio`, `ventana_limite` | texto `HH:MM` | dentro de la ventana permitida; límite ≤ cierre − 2 h |
| `recomendaciones_inocuidad` | lista de texto | 2 a 4 frases |
| `mensaje` | texto | ≤ 500 caracteres |

Salida de la función:

```json
{ "modo_respaldo": false, "motivo_respaldo": null, "modelo": "gemini-3.5-flash-lite", "motivo_sin_ficha": null,
  "ficha": { "producto": "Enchiladas Suizas", "porciones": 4, "cantidad_aprox_kg": 2.1,
             "ventana_inicio": "16:00", "ventana_limite": "17:30", "horas_antes_del_cierre": 2.5,
             "recomendaciones_inocuidad": ["Mantener a 4 °C o menos.", "Llevar en hieleras cerradas.", "Servir hoy mismo."],
             "mensaje": "Hola, equipo del comedor: …" } }
```

## 6. Ingeniería de prompts

Técnicas usadas:

1. **Rol operativo, no conversacional:** "Eres el motor de optimización de menú… No conversas: devuelves únicamente JSON".
2. **Reglas numeradas y verificables:** cada regla del prompt tiene una validación en código. Si Gemini la rompe, se detecta.
3. **Precalcular lo numérico:** el prompt trae `descuento_maximo_rentable_pct`, `valor_critico_por_porcion_mxn` y `ventana_permitida`. El modelo elige dentro de límites; no hace aritmética de la que dependa el dinero.
4. **Contexto estructurado en JSON:** la entrada es JSON, no prosa. Solo se envían los platillos candidatos (los que usan insumos críticos), no todo el menú.
5. **Restricciones de marca:** español de México, ≤ 160 caracteres, sin precios en el texto y **nunca decir al comensal que algo está por caducar**.
6. **Baja temperatura (0.3):** respuestas consistentes para una tarea operativa. Si se configura un modelo de la familia 2.5, además se envía `thinking_budget=0` (sin razonamiento extendido, menor latencia); los modelos más nuevos usan su configuración por defecto.

### 6.1 Instrucción de sistema · Función A

```text
Eres el motor de optimización de menú de Opsia para un restaurante en México.
No conversas: devuelves únicamente JSON que cumple el esquema.

Tarea: proponer promociones para vender HOY insumos que caducan en menos de 24 horas.

Reglas obligatorias:
1. Usa solo claves de 'platillos_candidatos'. Nunca inventes platillos ni ingredientes.
2. Cada promoción debe consumir al menos un insumo de 'insumos_criticos'.
3. descuento_pct es un entero entre 10 y 30 y NO puede superar el
   'descuento_maximo_rentable_pct' del platillo (con ese tope el precio sigue siendo al menos 1.5 veces el costo).
4. Prioriza los platillos que rescatan más valor en pesos de insumos críticos (campo
   'valor_critico_por_porcion_mxn') y que, juntos, cubren insumos críticos distintos.
5. No repitas platillos. Devuelve como máximo el número pedido de promociones.
6. copy_promocional: español de México, máximo 160 caracteres, tono cálido y apetitoso.
   NO escribas precios ni porcentajes (la interfaz los muestra junto al texto). Describe solo ingredientes
   que están en la receta. NUNCA digas al comensal que un ingrediente está por caducar, sobra o se va a tirar.
7. justificacion: una frase para el gerente con el razonamiento de negocio.
```

Contenido enviado (ejemplo real del 2026-11-26, con 1 de los 18 candidatos):

```json
{ "numero_de_promociones": 3,
  "insumos_criticos": [
    { "clave": "pollo", "nombre": "Pechuga de pollo", "cantidad_disponible": 7.5, "unidad": "kg", "costo_unitario_mxn": 135.0, "horas_para_caducar": 17.1 },
    { "clave": "bolillo", "nombre": "Pan bolillo", "cantidad_disponible": 40.0, "unidad": "pza", "costo_unitario_mxn": 3.5, "horas_para_caducar": 19.1 },
    { "clave": "crema", "nombre": "Crema ácida", "cantidad_disponible": 4.0, "unidad": "L", "costo_unitario_mxn": 72.0, "horas_para_caducar": 21.1 },
    { "clave": "carne_molida", "nombre": "Carne molida de res", "cantidad_disponible": 3.0, "unidad": "kg", "costo_unitario_mxn": 150.0, "horas_para_caducar": 22.1 } ],
  "platillos_candidatos": [
    { "clave": "enchiladas_suizas", "nombre": "Enchiladas Suizas", "categoria": "plato fuerte",
      "precio_venta_mxn": 120.0, "costo_porcion_mxn": 44.55, "descuento_maximo_rentable_pct": 30,
      "ingredientes_criticos": [ { "clave": "pollo", "nombre": "Pechuga de pollo", "cantidad_por_porcion": 0.18, "unidad": "kg" },
                                 { "clave": "crema", "nombre": "Crema ácida", "cantidad_por_porcion": 0.06, "unidad": "L" } ],
      "otros_ingredientes": ["tortilla", "queso", "tomate verde", "cebolla"],
      "valor_critico_por_porcion_mxn": 28.62 } ] }
```

### 6.2 Instrucción de sistema · Función B

```text
Eres el módulo de alertas de excedentes de Opsia para un restaurante en México.
No conversas: devuelves únicamente JSON que cumple el esquema.

Tarea: redactar la ficha operativa para que un comedor comunitario o la red estudiantil recoja comida
preparada que sobrará hoy.

Reglas obligatorias:
1. 'producto' y 'porciones' deben copiarse EXACTAMENTE del excedente. No cambies las cantidades.
2. La ventana de recolección debe quedar dentro de 'ventana_permitida': ventana_inicio no antes de su inicio y
   ventana_limite no después de su límite (el límite es 2 horas antes del cierre).
   Formato HH:MM de 24 horas.
3. recomendaciones_inocuidad: de 2 a 4 frases cortas y prácticas (temperatura, transporte, tiempo de consumo).
   Si 'requiere_refrigeracion' es true, incluye mantenerlo a 4 °C o menos.
4. mensaje: español de México, cordial y directo, listo para WhatsApp; incluye producto, porciones, kilos
   aproximados, ventana y punto de entrega. Sin emojis excesivos. No inventes datos que no estén en la entrada.
```

```json
{ "excedente": { "producto": "Enchiladas Suizas", "porciones": 4, "cantidad_aprox_kg": 2.1,
                 "requiere_refrigeracion": true, "punto_entrega": "Cafetería La Esquina (andén de servicio)" },
  "hora_actual": "15:00", "hora_cierre": "20:00",
  "ventana_permitida": { "inicio": "16:00", "limite": "18:00" },
  "destinatario": "Comedor comunitario / Red estudiantil" }
```

## 7. Validaciones (guardarraíles)

Ninguna respuesta de Gemini llega a la pantalla sin pasar por estas comprobaciones. Si una falla, se usa el respaldo y la interfaz muestra el motivo.

| # | Regla | Dónde |
|---|---|---|
| 1 | El JSON cumple el esquema: tipos, campos, rangos y longitudes. | SDK + Pydantic |
| 2 | El platillo existe en el menú **y** usa un insumo crítico. | `gemini_service._validar_promociones` |
| 3 | Sin platillos repetidos. | ídem |
| 4 | El descuento está entre 10 % y el máximo rentable del platillo (precio ≥ 1.5 × costo). | ídem |
| 5 | Si el texto menciona un precio, debe ser el precio de oferta correcto. | ídem |
| 6 | Los insumos usados se toman de la receta, no de lo que diga el modelo. | ídem |
| 7 | Segunda validación con existencias y ventas; porciones y $MXN se recalculan. | `rescate_menu.validar_propuestas` |
| 8 | La ficha conserva **exactamente** las porciones. | `gemini_service._validar_ficha` |
| 9 | La ventana queda dentro de lo permitido (límite ≤ cierre − 2 h), con horas válidas. | ídem |
| 10 | Hay al menos 2 recomendaciones de inocuidad y un mensaje. | ídem |
| 11 | Los textos se insertan en la página como texto, nunca como HTML. | `frontend/app.js` (`esc()`) |

## 8. Plan de contingencia (modo respaldo)

Las dos funciones **nunca lanzan excepciones**: siempre devuelven la misma estructura. Cuando algo falla, la marcan con `"modo_respaldo": true` y `motivo_respaldo`.

| Situación | Motivo que se muestra | Resultado |
|---|---|---|
| Sin `GEMINI_API_KEY` | "No hay GEMINI_API_KEY configurada." | Respaldo |
| Llave inválida | "La GEMINI_API_KEY no es válida." | Respaldo (**probado contra la API real** con una llave falsa) |
| Modelo no disponible para la llave (404) | "El modelo … no está disponible para esta llave. Prueba GEMINI_MODEL=gemini-3.5-flash-lite." | Respaldo |
| Cuota agotada (429) | "Se agotó la cuota de Gemini por ahora." | Respaldo |
| Sin permiso para el modelo (401/403) | "La llave de Gemini no tiene permiso para este modelo." | Respaldo |
| Sin internet o lentitud (> 15 s) | "Gemini no respondió a tiempo (…)" o "Falló la llamada…" | Respaldo |
| SDK no instalado | "Falta instalar el SDK: pip install google-genai" | Respaldo |
| JSON inválido o vacío | "Gemini devolvió un JSON que no cumple el esquema." | Respaldo |
| Falla una validación de la sección 7 | Explica cuál (por ejemplo, "Platillo fuera del menú…") | Respaldo |
| Ninguna ventana de recolección cabe antes del límite | `motivo_sin_ficha`: "Ya no hay tiempo para una recolección segura…" | Sin ficha (no es error) |

Qué contiene el respaldo:
- **Función A:** promociones calculadas con reglas a partir de las mismas entradas: mayor valor crítico por porción, mayor descuento rentable y texto de plantilla con el precio correcto.
- **Dentro del backend:** si Gemini no está disponible, `/api/optimizar-menu` usa su algoritmo voraz (`rescate_menu.estrategias_por_reglas`), que además considera existencias y ventas históricas.
- **Función B:** ficha con la ventana permitida completa, recomendaciones de inocuidad base (refrigeración a 4 °C o menos si lleva proteína o lácteo) y un mensaje de plantilla.
- **Sin servidor:** el frontend tiene además el modo demo autónoma (Apartado 5).

El tiempo máximo de espera (15 s) evita que la demo se congele si la red es lenta.

## 9. Cómo verificar que funciona

**Sin llave (lo que ya se probó):**

```bash
python -m unittest discover -s tests -v     # 65 pruebas, 22 de Gemini
python backend/gemini_service.py            # imprime promociones y ficha en modo respaldo
```

Las 22 pruebas de Gemini comprueban:
- candidatos correctos;
- respaldo sin llave, y también con la llave de ejemplo `tu_api_key_aqui`;
- respuesta válida aceptada;
- rechazo de: platillo inventado, platillo sin insumo crítico, descuento no rentable, precio equivocado en el texto y platillo repetido;
- falla de red;
- límites del esquema;
- ficha: respaldo con ventana 16:00–18:00, respuesta válida, rechazo de porciones cambiadas, rechazo de ventana fuera del límite, y sin ventana viable a las 17:45;
- forma de la llamada al SDK: modelo, `response_mime_type`, `response_schema`, instrucción de sistema; `thinking_budget` solo con la familia 2.5; texto JSON cuando `parsed` viene vacío; JSON inválido;
- modelo no disponible para la llave (404).

Además se probó la llamada real al servidor de Google con una llave falsa: respondió `400 API key not valid` y el sistema pasó al respaldo con el motivo "La GEMINI_API_KEY no es válida.".

**Con llave (pendiente, hacerlo antes de la demo):**

1. Poner la llave en `.env` y ejecutar `python backend/gemini_service.py`.
2. Revisar que diga `"modo_respaldo": false` en ambas funciones y que los textos sean adecuados.
3. Abrir la Vista 2 y pulsar **Optimizar Menú**: el distintivo debe decir **Generado con Gemini · gemini-3.5-flash-lite**.
4. Si sale modo respaldo, el motivo en pantalla dice qué corregir.

> No pudimos probar una llamada exitosa porque no tenemos llave en este entorno. La forma de la petición está verificada con el SDK y contra el servidor de Google hasta la autenticación; el contenido real de las respuestas de Gemini todavía no se ha observado.

## 10. Evidencia: SIMULADO vs. REAL

| Elemento | Origen |
|---|---|
| Inventario crítico, menú, recetas, costos y precios que recibe Gemini | **SIMULADO** |
| Textos y elecciones de Gemini | Generados por un modelo real sobre datos **SIMULADOS** (cuando hay llave) |
| Regla de rentabilidad (precio ≥ 1.5 × costo), tope de 30 % y ventana de 2 h | Supuestos de negocio del prototipo |
| Recomendaciones de inocuidad del respaldo | Prácticas generales (refrigerar a 4 °C o menos, cadena de frío, consumo el mismo día); no sustituyen la normativa sanitaria aplicable |

## 11. Cómo justificar ante los jueces que Gemini aporta valor (y no es un chatbot)

1. **No hay chat.** Son dos funciones con entrada y salida estructuradas, activadas por un botón. El encargado no tiene que saber "pedirle" nada a una IA.
2. **Resuelve lo que las reglas hacen mal:**
   - **Redacción:** un texto apetitoso y distinto para cada platillo, sin delatar que el ingrediente está por caducar. Con plantilla, todos dicen lo mismo.
   - **Criterio de combinación:** elige platillos que juntos cubren insumos distintos, por ejemplo enchiladas para pollo y crema, y hamburguesa para carne molida. Entiende el recetario en lenguaje natural.
   - **Comunicación con terceros:** un mensaje de WhatsApp listo y cordial para el comedor comunitario.
3. **Lo que no le delegamos:** el dinero y las cantidades. Python calcula el descuento máximo rentable, la ventana y las porciones, y valida todo. Gemini no puede hacer que el restaurante venda bajo costo ni prometer porciones que no hay. Hay pruebas automáticas para cada caso.
4. **Valor medible:** cada promoción muestra la pérdida si se tira contra el margen recuperado, con cifras del backend. Ejemplo simulado: enchiladas con 25 % de descuento rescatan $429 en insumos y recuperan $682 de margen.
5. **Contingencia:** sin llave, sin internet o con una respuesta mala, la demo sigue funcionando y dice por qué.
6. **Honestidad:** no tenemos aún una prueba A/B que demuestre que los textos de Gemini venden más que los de plantilla. Es la primera métrica a medir en un piloto real: conversión de la promoción con y sin texto de Gemini.
