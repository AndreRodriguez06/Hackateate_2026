# ZeroMerma AI

**Control operativo de cocina para reducir la merma de alimentos en restaurantes.** ZeroMerma AI predice cuánto comprar de cada insumo con Machine Learning, propone promociones rentables con Google Gemini para vender lo que está por caducar y avisa a tiempo a comedores comunitarios cuando va a sobrar comida.

> ⚠️ **Entorno de validación: todos los datos son SIMULADOS.** El restaurante, su historial, su inventario y sus precios son ficticios. La sección [Declaración de simulaciones](#declaración-de-simulaciones) detalla qué es simulado y dónde empieza la simulación.

---

## 1. El reto

**Pregunta del reto:** ¿cómo puede un restaurante de plaza comercial reducir la merma de sus insumos perecederos sin quedarse sin platillos para sus clientes?

### Problema delimitado

Un restaurante de plaza comercial en México (caso hipotético) compra sus insumos perecederos **por intuición**: el encargado repite lo del día más fuerte de la semana anterior, con un colchón "por si acaso". El resultado es un ciclo de dos fallas:

- **Sobreinventario:** compra de más, y el pollo, la crema o la tortilla caducan en el almacén y se tiran.
- **Desabasto:** cuando intenta recortar "al tanteo", se queda sin platillos en hora pico.

El problema se delimita a: **un restaurante**, **insumos perecederos**, **decisiones diarias** (compra de la mañana, venta durante el día, sobrante al cierre) y **platillos que ya existen en su menú**. No se aborda la cadena de suministro ni el desperdicio en hogares.

### Usuarios objetivo

| Usuario | Qué necesita | Vista de ZeroMerma AI |
|---|---|---|
| **Encargado de compras** | Saber cuánto comprar hoy sin tirar ni quedarse corto | 1 · Planeador de compras |
| **Personal de cocina y gerente de turno** | Vender hoy lo que está por caducar; saber a media jornada si sobrará comida | 2 · Rescate en menú · 3 · Alerta temprana |
| **Comensales** | Ofertas atractivas en platillos que ya conocen | Menú digital QR (vista previa en la Vista 2) |
| **Receptores: comedores comunitarios y red estudiantil** | Avisos con tiempo, cantidad exacta y cuidados de inocuidad | Ficha de rescate (Vista 3) |
| **Dueño** | Evidencia del ahorro | 4 · Auditoría y backtesting · 5 · Historial de compras |

### Evidencia que sustenta el problema

| Dato | Fuente |
|---|---|
| En 2022 se desperdiciaron **1,050 millones de toneladas** de alimentos en el mundo, casi una quinta parte de los alimentos disponibles para los consumidores. | PNUMA (UNEP), *Food Waste Index Report 2024* — [publicación](https://www.unep.org/resources/publication/food-waste-index-report-2024) · [mensajes clave (PDF)](https://wedocs.unep.org/bitstream/handle/20.500.11822/45275/Food-Waste-Index-2024-key-messages.pdf?sequence=8) |
| De ese total, los **servicios de comida** (restaurantes, cafeterías, comedores) generaron **290 millones de toneladas (≈ 28 %)**: unos 36 kg por persona al año. Los hogares, 60 %; el comercio minorista, 12 %. | PNUMA, *Food Waste Index Report 2024*, mismas fuentes |
| En México se desperdician alrededor de **20.4 millones de toneladas de alimentos al año**, cerca de un tercio de la producción nacional. | Cifra atribuida a la FAO en prensa: [Expansión, 30/09/2025](https://politica.expansion.mx/mexico/2025/09/30/fao-mexico-desperdicia-cada-ano-20-4-millones-de-toneladas-de-alimentos). Otras estimaciones nacionales van de 12.5 a 31 millones de toneladas según metodología y año. |

> El desperdicio del caso (kilos y pesos que aparecen en la aplicación) es **SIMULADO**. Las cifras de esta tabla son reales y sirven de contexto, no como datos del restaurante.

---

## 2. La solución y su flujo principal

ZeroMerma AI acompaña los momentos en que se decide la merma, del día a día al cierre de mes:

```mermaid
flowchart LR
    A["🌅 Mañana<br/><b>1 · Planeador de compras</b><br/>Random Forest predice el consumo<br/>compra = demanda × (1 + margen)"] --> B["🕛 Mediodía<br/><b>2 · Rescate en menú</b><br/>Gemini propone promociones<br/>en platillos existentes y rentables"]
    B --> C["🕒 Tarde<br/><b>3 · Alerta temprana</b><br/>proyección de sobrante al cierre<br/>ficha para comedor comunitario"]
    C --> D["📊 Semana<br/><b>4 · Auditoría</b><br/>backtesting sin fuga de datos<br/>merma evitada en kg y $MXN"]
    D --> E["🗂️ Mes<br/><b>5 · Historial de compras</b><br/>compras registradas día a día<br/>vs. sugerencia del modelo"]
```

```mermaid
flowchart LR
    U[Navegador<br/>frontend/] -- "JSON /api/*" --> API[FastAPI<br/>backend/main.py]
    API --> DB[(SQLite<br/>data/restaurante.db)]
    API --> ML[Random Forest<br/>ml/modelo_rf.pkl]
    API --> G[gemini_service.py]
    G -- "response_schema JSON" --> GEM[[Google Gemini 2.5 Flash]]
    G -. "sin llave / sin red / respuesta inválida" .-> R[Reglas locales<br/>modo respaldo]
    U -. "sin servidor" .-> DEMO[datos_demo.js<br/>modo demo autónoma]
```

Lo más importante del diseño:
- **Python hace las cuentas y la IA decide y redacta.** El backend calcula los descuentos rentables, las ventanas de recolección y las porciones, y valida todo lo que propone Gemini. Gemini no puede inventar platillos ni vender por debajo de 1.5 veces el costo.
- **La demo nunca se cae.** Sin llave de Gemini funciona en modo respaldo; sin servidor, el frontend usa respuestas precalculadas. Ambos modos se indican en pantalla.
- **Anti-desabasto:** alerta si el margen baja de 4 %, y un margen recomendado por insumo calculado con los errores reales del modelo.

### Por qué cada tecnología

| Tecnología | Para qué | Por qué la elegimos |
|---|---|---|
| **SQLite** | Base de datos | Un archivo, sin servidor ni instalación; viene con Python. Suficiente para un restaurante; la columna `origen_dato` con `CHECK` obliga a etiquetar cada registro. |
| **scikit-learn · Random Forest** | Predicción de demanda | Funciona bien con pocos datos tabulares, encuentra combinaciones entre variables sin programarlas a mano (lluvia en fin de semana), no predice cantidades negativas y explica qué variables pesaron (`feature_importances_`). Se compara en cada entrenamiento contra una regresión lineal y un promedio. |
| **FastAPI + Pydantic** | API REST y servidor del frontend | Valida entradas automáticamente, genera documentación interactiva en `/docs` y sirve la API y la página en un solo comando. |
| **HTML + Tailwind CSS + Chart.js + Lucide (CDN)** | Interfaz | Sin compilación ni Node.js: se abre con doble clic. Responsiva para usarse desde el celular en el almacén. |
| **Google Gemini 2.5 Flash (`google-genai`)** | Promociones y fichas de rescate | Rápido y económico para tareas cortas. Con *Structured Outputs* (`response_schema` Pydantic) responde JSON con esquema fijo: no es un chatbot. |

---

## 3. Instalación y ejecución en 3 pasos

**Requisitos:** Python 3.10 a 3.13, Git y conexión a internet (para instalar paquetes y cargar las librerías del frontend desde CDN).

```bash
# 1. Clonar
git clone https://github.com/AndreRodriguez06/Hackateate_2026.git
cd Hackateate_2026

# 2. Instalar dependencias (recomendado dentro de un entorno virtual, ver abajo)
pip install -r requirements.txt

# 3. Generar los datos SIMULADOS y arrancar
python data/generar_datos.py && uvicorn backend.main:app --reload
```

Abrir **<http://localhost:8000>** (aplicación) y **<http://localhost:8000/docs>** (documentación interactiva de la API).

<details>
<summary><b>Entorno virtual, Windows y otras formas de arrancar</b></summary>

Entorno virtual (recomendado, para no mezclar versiones):

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

- En **Windows PowerShell 5**, `&&` no funciona: ejecuta `python data/generar_datos.py` y después `uvicorn backend.main:app --reload`.
- Alternativa al paso 3: `python backend/main.py`. Si falta la base o el modelo, el servidor los genera y entrena solo (≈ 6 s).
- **Sin instalar nada:** doble clic en `frontend/index.html` abre la aplicación en **modo demo autónoma**, con respuestas precalculadas del mismo modelo.
- Si `uvicorn` no se reconoce como comando: `python -m uvicorn backend.main:app --reload`.
</details>

### Activar Gemini (opcional)

```bash
cp .env.example .env               # Windows: copy .env.example .env
```

Edita `.env` y cambia `tu_api_key_aqui` por tu llave de [Google AI Studio](https://aistudio.google.com/apikey). Reinicia el servidor. `.env` **no se sube a git**. Sin llave, todo funciona en **modo respaldo** y la interfaz lo indica.

Para comprobar que Gemini funciona: `python backend/gemini_service.py`. Debe mostrar `"modo_respaldo": false`.

### Verificar que todo funciona

```bash
python -m unittest discover -s tests -v    # 64 pruebas automáticas (datos, modelo, API, Gemini)
python scripts/prueba_humo.py              # 9 casos de punta a punta, con el servidor encendido
```

### Ver la base de datos y simular datos distintos

```bash
python scripts/exportar_csv.py             # exporta todas las tablas a data/csv/ (se abren en Excel)
python data/generar_datos.py --semilla 7   # otro restaurante simulado; el servidor reentrena el modelo solo
```

---

## 4. Declaración de simulaciones

**Dónde empieza la simulación:** en [`data/generar_datos.py`](data/generar_datos.py). Ese script inventa, con reglas documentadas y una semilla fija, el restaurante y sus 365 días de historia. **Todo lo que sale de la base `data/restaurante.db` es SIMULADO.** Cada tabla tiene la columna `origen_dato`, que la base solo acepta como `'SIMULADO'` o `'REAL'`, y cada respuesta de la API incluye `es_simulado`.

| Parte del sistema | ¿Simulado? | Detalle |
|---|---|---|
| Restaurante "Cafetería La Esquina", menú de 30 platillos y recetario | **SIMULADO** | Ficticios; porciones típicas de cocina mexicana. |
| Historial de 365 días: afluencia, clima, quincena, días festivos, época del año, eventos cercanos y en la plaza, ventas, consumo | **SIMULADO** | Reglas en `docs/02_base_de_datos.md`. |
| Compra tradicional "a ojo" y su merma | **SIMULADO** | Es la línea base contra la que se compara. |
| Inventario con caducidades | **SIMULADO** | Relativo a la hora en que se genera, para que siempre haya insumos críticos. |
| Precios de los 46 insumos | **SIMULADO (provisional)** | Pendiente sustituir por PROFECO *Quién es Quién en los Precios*; la columna `fuente_precio` lo indica. |
| Supuestos de negocio: elasticidad del descuento, precio ≥ 1.5 × costo, curva de ventas por hora, horario 09:00–20:00, ventana de 2 h | **SIMULADO** | Constantes en `backend/services/` y `backend/gemini_service.py`. |
| Envío del aviso al comedor comunitario | **SIMULADO** | Solo se registra en la base; no se contacta a nadie. |
| Modo demo autónoma (`frontend/datos_demo.js`) | Respuestas reales del sistema sobre datos **SIMULADOS** | Generado con `scripts/exportar_datos_demo.py`. |
| Algoritmos, modelo Random Forest, validación temporal, API, interfaz | **REAL** | Código funcional que se puede usar con datos reales. |
| Llamadas a Gemini (con llave) | **REAL** | Modelo real que trabaja sobre datos SIMULADOS. |
| Cifras de contexto (PNUMA, FAO) | **REAL** | Con su fuente en la sección 1. |

---

## 5. Resultados sobre datos simulados

Corrida del 2026-11-26. Las cifras cambian ligeramente si se regeneran los datos otro día.

| Indicador | Resultado | Detalle |
|---|---|---|
| Error del modelo en el mes de prueba (nunca visto) | MAE 13.9 comensales (R² 0.83); error medio por insumo 11.0 %. La regresión lineal *one-hot* es mejor en estos datos simulados (9.7 %) y lo reportamos | [`docs/03_modelo_ml.md`](docs/03_modelo_ml.md) |
| Mes de prueba con margen recomendado vs. compra tradicional | −34 % de compra, −82 % de sobrante, demanda no cubierta 0.96 % vs. 1.51 % | ídem |
| Historial completo, 305 días comparables (46 insumos) | $915 mil menos en compras (−29.8 %), merma −72.4 %, demanda no cubierta 0.98 % vs. 1.00 % | [`docs/04_backend_api.md`](docs/04_backend_api.md) |
| Backtesting de la última semana (con Buen Fin) | Merma −84.9 %: 147 kg y $10,819 MXN evitados; esa semana la compra tradicional cubrió mejor la demanda (0.04 % vs. 1.03 % sin cubrir) | ídem |
| Rescate en menú (ejemplo) | 3 promociones rentables sobre $1,891 MXN de insumos críticos | [`docs/06_integracion_gemini.md`](docs/06_integracion_gemini.md) |

> Son resultados de un método real sobre datos **SIMULADOS**: demuestran que el sistema funciona, no prometen ese ahorro en un restaurante real.

---

## 6. Estructura del repositorio

```text
Hackateate_2026/
├── README.md · requirements.txt · .env.example
├── data/        schema.sql · generar_datos.py  →  restaurante.db (se genera)
├── ml/          modelo_demanda.py               →  modelo_rf.pkl (se genera)
├── backend/     main.py · database.py · gemini_service.py · services/ (rescate_menu, alerta_excedente, historial_compras)
├── frontend/    index.html · app.js · datos_demo.js
├── scripts/     exportar_datos_demo.py · exportar_csv.py · prueba_humo.py
├── tests/       64 pruebas automáticas (unittest)
├── docs/        documentación por apartado
└── prueba1/     primer prototipo visual (referencia; cifras ilustrativas)
```

## 7. Documentación

| # | Documento | Contenido |
|---|---|---|
| 01 | [`docs/01_arquitectura.md`](docs/01_arquitectura.md) | Funciones del sistema, arquitectura, contratos de la API y flujo de las 4 vistas |
| 02 | [`docs/02_base_de_datos.md`](docs/02_base_de_datos.md) | Esquema SQLite, generador de datos simulados, menú y recetario |
| 03 | [`docs/03_modelo_ml.md`](docs/03_modelo_ml.md) | Random Forest, validación temporal, métricas y regla anti-desabasto |
| 04 | [`docs/04_backend_api.md`](docs/04_backend_api.md) | Referencia de cada endpoint con ejemplos reales |
| 05 | [`docs/05_frontend_ux.md`](docs/05_frontend_ux.md) | Interfaz, modo demo, decisiones de diseño y guion de la demo |
| 06 | [`docs/06_integracion_gemini.md`](docs/06_integracion_gemini.md) | Esquemas JSON, prompts, validaciones y contingencias |
| 07 | [`docs/07_integracion_pruebas.md`](docs/07_integracion_pruebas.md) | Bitácora de pruebas de punta a punta y checklist de entrega |
| 08 | [`docs/08_plan_negocios.md`](docs/08_plan_negocios.md) | Plan de negocios y viabilidad (en preparación) |

---

## 8. Equipo

| Integrante | Rol | Aportaciones |
|---|---|---|
| Andre | _por completar_ | _por completar_ |
| César | _por completar_ | _por completar_ |
| Isaac | _por completar_ | _por completar_ |
| Diego | _por completar_ | _por completar_ |
| Alan | _por completar_ | _por completar_ |

Áreas del proyecto que conviene repartir para la defensa: datos simulados (02), modelo de ML (03), backend y API (04), interfaz y demo (05), integración con Gemini (06), pruebas (07) y plan de negocios (08).

---

## 9. Limitaciones actuales

- **Datos simulados:** el modelo aprendió reglas que nosotros definimos. Sus métricas prueban el método, no la precisión en un negocio real.
- **Precios provisionales:** aún no se sustituyen por precios consultados en PROFECO.
- **Gemini:** la integración está probada con respuestas simuladas y con la API real hasta la autenticación. Hay que confirmar con una llave válida que los textos generados sean adecuados.
- **Inventario simplificado:** cada día se evalúa por separado; el sobrante no pasa al día siguiente.
- **Supuestos de negocio no medidos:** el aumento de ventas por descuento y la curva de ventas por hora son supuestos.
- **Un solo restaurante, sin usuarios ni contraseñas**; pensado para correr localmente.
- **Envío de avisos simulado:** no hay integración con WhatsApp ni correo.
- **Librerías del frontend por CDN:** sin internet la página pierde estilos y gráficas (la lógica sigue funcionando).
- **Importancia de variables global:** explica el modelo en general, no cada predicción.

## 10. Próximos pasos para un piloto real

1. **Línea base real:** pesar la merma de un restaurante durante 4 semanas antes de usar el sistema.
2. **Cargar datos reales:** exportar ventas e inventario del punto de venta (CSV), registrar con `origen_dato = 'REAL'` y reentrenar el modelo.
3. **Precios reales:** sustituir los precios por PROFECO *Quién es Quién en los Precios* y facturas del proveedor.
4. **Medir el valor de Gemini:** prueba A/B de promociones con texto de Gemini contra texto de plantilla.
5. **Avisos reales:** integrar WhatsApp Business o correo con un comedor comunitario aliado, con protocolo de inocuidad acordado.
6. **Operación:** usuarios y roles, despliegue en la nube, reentrenamiento semanal automático e inventario con arrastre entre días.
7. **Evaluar el piloto:** comparar merma, desabasto y margen contra la línea base del paso 1.

---

<sub>ZeroMerma AI · Prototipo para reto universitario · Todos los datos del restaurante son SIMULADOS.</sub>
