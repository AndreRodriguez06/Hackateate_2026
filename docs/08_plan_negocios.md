# 08 · Plan de negocios y análisis de viabilidad

> **Apartado 8 · Orden 5.1** de la Tabla de Medios y Fines. Versión del 2026-11-27.

> **Regla de este documento.** Cada cifra pertenece a una de tres categorías, y nunca se mezclan:
>
> | Etiqueta | Qué significa | Dónde está |
> |---|---|---|
> | 🟢 **FUENTE** | Dato publicado por una institución o proveedor, con título y fecha. | Tabla A (sección 0) |
> | 🟡 **SUPUESTO** | Valor que elegimos nosotros para modelar; se muestra la fórmula y por qué se eligió. **Debe validarse en el piloto.** | Tabla B (sección 0) |
> | 🔵 **SIMULADO** | Resultado del prototipo sobre datos ficticios, reproducible con el código del repositorio. | Secciones 1 y 5 |
>
> Ninguna cifra de este plan describe a un restaurante real.

---

## 0. Tablas de datos

### Tabla A · 🟢 Datos con fuente verificable

Consultados entre el 2026-11-26 y el 2026-11-27. Los precios de proveedores cambian: se reconsultan antes de presentar.

| # | Dato | Institución · título · periodo | Enlace |
|---|---|---|---|
| A1 | En 2022 se desperdiciaron **1,050 millones de toneladas** de alimentos en el mundo, casi una quinta parte de lo disponible para consumidores. | PNUMA (UNEP) · *Food Waste Index Report 2024* · datos 2022 | [Publicación](https://www.unep.org/resources/publication/food-waste-index-report-2024) · [Mensajes clave (PDF)](https://wedocs.unep.org/bitstream/handle/20.500.11822/45275/Food-Waste-Index-2024-key-messages.pdf?sequence=8) |
| A2 | De ese total, los **servicios de comida** generaron **290 millones de t (≈ 28 %)**, unos 36 kg por persona al año; hogares 60 %, comercio minorista 12 %. | PNUMA · *Food Waste Index Report 2024* · 2022 | Mismas fuentes |
| A3 | México desperdicia unos **20.4 millones de toneladas de alimentos al año, ≈ 34 % de su producción nacional**. | Estimación atribuida a la **FAO**, citada en la Guía del Reto; reportada por Expansión el 30/09/2025 | [Expansión](https://politica.expansion.mx/mexico/2025/09/30/fao-mexico-desperdicia-cada-ano-20-4-millones-de-toneladas-de-alimentos) |
| A4 | La rama SCIAN **7225** (servicios de preparación de alimentos y bebidas: comida corrida, antojitos, cafeterías, fuentes de sodas, autoservicio, etc.) tenía **740,231 unidades económicas**; Ciudad de México **55,753**, Estado de México 89,408, Jalisco 48,957. | Secretaría de Economía · **DataMéxico** con **DENUE de INEGI, mayo de 2026** | [DataMéxico, rama 7225](https://www.economia.gob.mx/datamexico/es/profile/industry/restaurants-and-other-eating-places) |
| A5 | Qué incluye la rama 7225: "todos los restaurantes de comida corrida, de pescados y mariscos, de preparación de antojitos, tacos y tortas, cafeterías, fuentes de sodas, neverías y los de autoservicio, entre otros". | INEGI · *Conociendo los servicios de preparación de alimentos y bebidas* | [INEGI (PDF)](https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/nueva_estruc/889463911982.pdf) |
| A6 | El DENUE se actualizó por completo con los Censos Económicos 2024 y permite ubicar establecimientos por actividad, localización y tamaño (ejemplo de INEGI: "ubicar cafeterías de diversos tamaños en un área específica como clientes potenciales"). | INEGI · boletín DENUE 05/2025 | [Boletín (PDF)](https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2025/denue/denue2025_05.pdf) · [Mapa DENUE](https://www.inegi.org.mx/app/mapa/denue/) · [Descarga masiva](https://www.inegi.org.mx/app/descarga/) |
| A7 | Tortilla de maíz: precio promedio nacional en tortillerías **$24.27 MXN/kg** (segunda semana de abril de 2026). PROFECO monitorea 603 tortillerías. | PROFECO · *Quién es Quién en los Precios*, 16 de abril de 2026 | [QQP (PDF)](https://www.gob.mx/cms/uploads/attachment/file/1071506/v5__MA_ANERA_DEL_PUEBLO_16_DE_ABRIL_DE_2026_compressed__1_.pdf) · [Portal QQP](https://qqp.profeco.gob.mx) |
| A8 | Gemini API, modelo **`gemini-3.5-flash-lite`**: **USD 0.30 por millón de tokens de entrada** y **USD 2.50 por millón de salida** (nivel estándar de pago); soporta salidas estructuradas. | Google · *Gemini Developer API pricing* y ficha del modelo | [Precios](https://ai.google.dev/gemini-api/docs/pricing) · [Modelo](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) |
| A9 | Un token equivale a **unos 4 caracteres** (regla general de Google). | Google · *Understand and count tokens* | [Tokens](https://ai.google.dev/gemini-api/docs/tokens) |
| A10 | `gemini-2.5-flash` ya no se ofrece a proyectos nuevos; Google recomienda 3.5 Flash-Lite o 3.8 Flash. | Google · *Gemini deprecations* | [Retiros](https://ai.google.dev/gemini-api/docs/deprecations) |
| A11 | **Render:** capa gratuita con 750 horas de instancia al mes; el servicio se duerme tras 15 min sin uso y tarda ~1 min en despertar. Instancia **Starter: USD 7/mes**, 0.5 CPU, 512 MB, siempre encendida. | Render · páginas de hosting y precios | [Render](https://render.com/hosting/python) |
| A12 | **Railway:** plan Hobby **USD 5/mes** que incluye USD 5 de uso. Tarifas: **RAM USD 10 por GB-mes, CPU USD 20 por vCPU-mes, volumen USD 0.15 por GB-mes**, salida de red USD 0.05/GB. | Railway · *Pricing Plans* | [Railway](https://docs.railway.com/pricing/plans) |
| A13 | Tipo de cambio FIX de Banxico: entre **17.39 y 17.60 pesos por dólar** en julio de 2026 (último dato encontrado). | Banco de México · tipo de cambio FIX | [Banxico](https://www.banxico.org.mx/tipcamb/tipCamMIAction.do) |
| A14 | **Cheaf** (México, Chile y Argentina): marketplace donde negocios venden excedentes con descuento en "paquetes sorpresa"; cobra **comisión por pedido** (25 % según una nota de 2025); el negocio no paga si no vende. | Expansión (2020) · iProfesional (2025) | [Expansión](https://expansion.mx/tecnologia/2020/09/28/esta-app-evita-que-los-restaurantes-tiren-comida) · [iProfesional](https://www.iprofesional.com/negocios/439169-como-funciona-cheaf-la-app-furor-para-comprar-comida-mucho-mas-barata) |
| A15 | **Too Good To Go:** su página oficial de disponibilidad menciona Europa, Estados Unidos, Canadá y Australia; **no encontramos confirmación de que opere para consumidores en México**. | Too Good To Go · *¿Dónde está disponible?* | [TGTG](https://toogoodtogo.com/es/about-us/in-my-area) |
| A16 | **Soft Restaurant** (National Soft): POS con inventario (proveedores, presentaciones de ingredientes, mínimos y máximos, compras). Precio **no publicado**; se cotiza con el proveedor. | Comparasoftware · Capterra | [Comparasoftware](https://www.comparasoftware.com/soft-restaurant) · [Capterra](https://www.capterra.com/p/200701/Soft-Restaurant/) |
| A17 | **Poster POS:** POS en la nube para pequeños y medianos negocios de comida, con inventario, recetas, reportes y app para el dueño. Precio para México **no encontrado** en fuentes públicas. | Unilever Food Solutions México · Capterra México | [UFS](https://www.unileverfoodsolutions.com.mx/tendencias/software-pos.html) · [Capterra](https://www.capterra.mx/software/141470/poster-pos) |

**Lo que no encontramos y por eso no citamos:** precio de licencia de Soft Restaurant y de Poster en México, tasa de merma promedio de restaurantes mexicanos, número de restaurantes ubicados en plazas comerciales, y precios PROFECO 2026 de pechuga de pollo y crema con fecha precisa. Ver la sección 2.2 para el procedimiento de consulta.

### Tabla B · 🟡 Supuestos del modelo (validar en el piloto)

| # | Variable | Valor | Por qué este valor | Cómo se valida |
|---|---|---|---|---|
| B1 | Tipo de cambio (TC) | **18.00 MXN/USD** | FIX más reciente encontrado (A13, ≤ 17.60) más ~2 % de colchón para no subestimar costos en dólares. | Consultar el FIX del día en Banxico. |
| B2 | Precio de suscripción (P) | **$799 MXN/mes** por restaurante | Debe ser **menor al 10 %** del ahorro mensual estimado del ejemplo (sección 5: $10,579), para que el dueño recupere la suscripción en días, y cubrir el costo variable (B6). | Entrevistas de disposición a pagar durante el piloto. |
| B3 | Tokens por llamada de promociones | **5,943 de entrada / 585 de salida** | Medido en el prototipo: 15,848 caracteres de entrada (instrucción + datos + esquema) y hasta 1,559 de salida, ÷ 4 (A9) × 1.5 de colchón, porque el español suele usar más tokens que el inglés. | Leer `usage_metadata` de las respuestas reales. |
| B4 | Tokens por ficha de rescate | **906 de entrada / 384 de salida** | Igual que B3: 2,416 y 1,025 caracteres medidos. | Ídem. |
| B5 | Uso de Gemini por restaurante | **60 optimizaciones + 30 fichas al mes** | 2 optimizaciones de menú y 1 ficha por día, 30 días. | Bitácoras `promociones_generadas` y `alertas_excedente`. |
| B6 | Hosting por restaurante | **USD 7.15/mes** | Instancia dedicada (como el prototipo, una base por restaurante) en Railway (A12): 0.5 GB RAM × $10 + 0.1 vCPU promedio × $20 + 1 GB de volumen × $0.15. Cruce: Render Starter cuesta USD 7 (A11). | Facturación real del proveedor. |
| B7 | Soporte por restaurante | **1 hora/mes × $150 MXN/h** | Valor de referencia del tiempo del equipo para resolver dudas y revisar capturas. | Registrar horas reales en el piloto. |
| B8 | Comisión de cobro | **4 % del precio** | Referencia conservadora para pasarelas de pago con tarjeta. | Cotizar con la pasarela elegida. |
| B9 | Costos fijos mensuales del negocio (CF) | **$5,000 / $15,000 / $30,000 MXN** (tres escenarios) | Desde operar con el equipo fundador sin sueldo hasta pagar medio tiempo de desarrollo y ventas. | Presupuesto real del equipo. |
| B10 | Tasa de merma base del restaurante | **10 % de las compras de insumos** | Valor de ejemplo propuesto por la Guía del Reto. **No es un promedio de la industria.** | Pesar la merma 4 semanas antes del piloto. |
| B11 | Tasa de merma con Opsia | **6.5 % de las compras** | Reducción relativa de 35 %, la **mitad** de la observada en la simulación (−72 %, sección 1), para no prometer de más. | Pesar la merma durante el piloto. |
| B12 | Compras mensuales de insumos del restaurante de ejemplo | **$302,267.85 MXN** | Compra tradicional del restaurante **SIMULADO** (sección 1): $3,073,056.50 en 305 días × 30 / 305. | Facturas del restaurante piloto. |

---

## 1. Problema y propuesta de valor

### 1.1 El problema

El desperdicio de alimentos es un problema de escala mundial y nacional (A1, A3), y los **servicios de comida** generan cerca de 28 % del desperdicio en el último eslabón de la cadena (A2).

Dentro de un restaurante, el problema se vuelve financiero en dos lugares:
1. **Sobrecompra intuitiva:** el encargado compra "lo del día más fuerte de la semana pasada, más un colchón". Lo que no se usa caduca en el almacén y es dinero pagado que se tira.
2. **Recorte al tanteo:** cuando intenta comprar menos sin datos, se queda sin platillos en hora pico y pierde ventas.

### 1.2 La propuesta de valor

> **Opsia le dice al restaurante cuánto comprar, cómo vender lo que está por caducar y a quién avisar antes de tirar comida, con cifras en pesos que se pueden auditar.**

| Momento | Pérdida que ataca | Cómo lo hace | Evidencia en el prototipo (🔵 SIMULADO) |
|---|---|---|---|
| Antes de comprar | Sobrecompra | Predicción por insumo con Random Forest y margen de seguridad recomendado | 305 días: compras −29.8 %, merma −72.4 %, demanda no cubierta 0.98 % contra 1.00 % de la compra a ojo |
| Insumos por caducar | Caducidad en almacén | Promociones sobre platillos **del menú actual**, nunca por debajo de 1.5 × costo, con texto redactado por Gemini | Ejemplo: $1,890 MXN de insumos críticos; 3 promociones rescatan $1,217 y recuperan $2,098 de margen |
| Antes del cierre | Comida preparada sobrante | Proyección de sobrante y ficha para comedor comunitario, con ventana que termina 2 h antes del cierre | Ficha con porciones, kg, ventana e inocuidad |
| Fin de mes | Falta de evidencia | Historial de compras contra consumo y contra sugerencia del modelo | Vista 4 por día, semana o mes, con zoom |

Cómo reproducir la evidencia: `python backend/main.py` y `GET /api/historial-compras?agrupar=mes` (ver `04_backend_api.md`, sección 4.9). Datos del restaurante **SIMULADOS**.

---

## 2. Segmento de clientes y mercado objetivo

### 2.1 Segmento inicial

**Restaurantes de comida corrida, cafeterías y locales gastronómicos independientes en plazas comerciales urbanas de México**, que:
- compran insumos perecederos varias veces por semana;
- tienen un menú estable de 15 a 40 platillos;
- no tienen un sistema de pronóstico (compran "a ojo" o con Excel);
- tienen un responsable de compras con celular o computadora.

**Por qué empezar aquí:**
- la afluencia de una plaza depende de factores que el modelo usa: día, quincena, festivos, época del año y eventos en la plaza;
- muchos locales concentrados en un solo lugar abaratan la venta en persona y el piloto;
- su tamaño no justifica un ERP de cadena.

**Fuera del segmento inicial:** cadenas con sistemas corporativos, dark kitchens y puestos sin inventario formal.

### 2.2 Cómo dimensionar el mercado con el DENUE (sin inventar cifras)

**Universo de referencia (🟢 A4):** 740,231 unidades económicas en la rama 7225 en México y 55,753 en la Ciudad de México (DENUE, mayo de 2026). **Este no es nuestro mercado**: incluye taquerías, neverías, puestos y negocios que no son nuestro segmento. Solo sirve como techo.

**Procedimiento para obtener el mercado direccionable** (lo puede repetir cualquiera):

1. Descargar el DENUE de la entidad objetivo (por ejemplo, Ciudad de México) desde la [descarga masiva de INEGI](https://www.inegi.org.mx/app/descarga/), sector 72.
2. Filtrar las **clases SCIAN** del segmento dentro de la rama 7225: restaurantes de comida corrida o a la carta, cafeterías y fuentes de sodas, y antojitos. Los códigos exactos de 6 dígitos se toman del catálogo [SCIAN México 2023](https://www.inegi.org.mx/contenidos/app/scian/estructura2023.pdf).
3. Filtrar por **ubicación en centro comercial**. El DENUE registra la dirección del establecimiento; revisar en el diccionario de datos de la descarga los campos de centro comercial y número de local. Si no estuvieran disponibles, cruzar la dirección con el listado de plazas de la ciudad.
4. Filtrar por **tamaño** (estrato de personal ocupado), por ejemplo de 6 a 50 personas, para excluir micro-puestos y cadenas grandes.
5. El conteo resultante es **N_SAM** (mercado direccionable).

**Fórmulas** (se llenan con el conteo del paso 5; hasta entonces no se presenta ninguna cifra de mercado):

```
Ingreso potencial anual (SAM)        = N_SAM × P × 12
Clientes alcanzables a 12 meses (SOM) = N_SAM × tasa de adopción         (tasa: 🟡 supuesto a validar)
Ingreso anual alcanzable             = SOM × P × 12
```

Ejemplo de cómo se lee (sin datos inventados): si el paso 5 diera N_SAM establecimientos y se lograra una adopción de 1 %, el ingreso anual sería N_SAM × 0.01 × $799 × 12.

---

## 3. Análisis competitivo

### 3.1 Tabla comparativa

| Criterio | Alternativa 1 · Hojas de cálculo y bitácoras (Excel, cuaderno) | Alternativa 2 · POS tradicional (Soft Restaurant, Poster) | Alternativa 3 · Apps de rescate al cierre (Cheaf; Too Good To Go como referencia internacional) | **Opsia** |
|---|---|---|---|---|
| Problema que resuelve | Registrar compras e inventario | Ventas, comandas, inventario, recetas y reportes (A16, A17) | Vender excedentes con descuento al final del día (A14) | **Comprar lo justo**, vender lo que caduca y avisar a tiempo |
| ¿Predice cuánto comprar? | No: depende del criterio de quien llena la hoja | Registra existencias y mínimos/máximos (A16); no encontramos pronóstico de demanda por clima, quincena o festivos en las fuentes revisadas | No | **Sí**: por insumo, con 7 variables de contexto y margen anti-desabasto |
| ¿Actúa antes de que el insumo caduque? | Solo si alguien revisa | Puede mostrar existencias; no propone qué platillo vender | No: actúa con comida ya preparada | **Sí**: promociones en platillos del menú actual, nunca bajo 1.5 × costo |
| Comida preparada que sobra | No | No | **Sí**, venta con descuento; el negocio paga comisión (A14) | **Sí**, aviso temprano a comedores comunitarios con ficha de inocuidad |
| Momento en que actúa | Después (registro) | Durante la operación | Al cierre | **Antes de comprar, durante el día y antes del cierre** |
| Costo para el restaurante | Sin licencia (tiempo del personal) | Licencia: **precio no publicado**, se cotiza (A16, A17) | **Comisión por pedido** (25 % según nota de 2025, A14); sin costo fijo | 🟡 Suscripción de $799 MXN/mes (B2, supuesto a validar) |
| Limitación principal | Error humano; nadie lo actualiza en hora pico | Ve el pasado; no recomienda la compra | Recupera solo una parte del valor; no evita la sobrecompra | Necesita datos de ventas e inventario; prototipo con datos simulados |

### 3.2 Diferenciador claro

1. **Prevenir en lugar de rematar.** Las apps de rescate recuperan una fracción del valor de la comida que ya sobró; Opsia ataca la causa, que es la sobrecompra. Son **complementarias**: la Vista 3 podría publicar el excedente en una app de rescate en vez de, o además de, avisar a un comedor.
2. **Recomendación accionable y explicable.** Un POS dice cuánto hay; Opsia dice cuánto comprar, por qué (importancia de variables) y con qué margen.
3. **IA con guardarraíles financieros.** Gemini elige y redacta, pero el backend impide promociones bajo costo y platillos inventados (`06_integracion_gemini.md`).
4. **Se integra, no sustituye.** El restaurante conserva su POS; Opsia consume sus exportaciones de ventas.

---

## 4. Modelo de ingresos y estructura de costos

### 4.1 Modelo de ingresos

- **Suscripción mensual B2B (SaaS)** por restaurante: 🟡 **P = $799 MXN/mes** (B2).
- **Piloto gratuito de 14 días** (sección 6).
- Sin comisión por venta: el ahorro completo queda en el restaurante.

### 4.2 Costo variable por restaurante (CV)

| Concepto | Fórmula | Resultado mensual |
|---|---|---|
| Gemini · promociones | 60 llamadas × (5,943 tokens × USD 0.30 + 585 × USD 2.50) / 1,000,000 | USD 0.1947 |
| Gemini · fichas | 30 llamadas × (906 × USD 0.30 + 384 × USD 2.50) / 1,000,000 | USD 0.0370 |
| **Gemini total** | (A8, A9, B3, B4, B5) | **USD 0.23 ≈ $4.17 MXN** |
| Hosting | 0.5 GB × 10 + 0.1 vCPU × 20 + 1 GB × 0.15 (A12, B6) | **USD 7.15 ≈ $128.70 MXN** |
| Soporte | 1 h × $150 (B7) | **$150.00 MXN** |
| Comisión de cobro | 4 % × $799 (B8) | **$31.96 MXN** |
| **CV total** | suma, con TC = 18.00 (B1) | **$314.83 MXN** |

**Margen de contribución por restaurante:** P − CV = 799 − 314.83 = **$484.17 MXN/mes**.

Lectura:
- **Gemini es casi gratis** frente a todo lo demás: $4.17 MXN al mes por restaurante con los supuestos de uso.
- El costo dominante es el **soporte humano**, seguido del hosting. Una arquitectura multi-restaurante (una instancia para varios) bajaría el hosting; no lo asumimos para no ser optimistas.
- En la capa gratuita de Render (A11) el prototipo se puede mostrar sin costo, pero se duerme tras 15 minutos sin uso: sirve para demos, no para operación.

### 4.3 Punto de equilibrio (break-even)

```
N* = CF / (P − CV)          N* = número de restaurantes suscritos para cubrir los costos fijos
```

| Escenario de costos fijos (B9) | Cálculo | Restaurantes necesarios |
|---|---|---|
| CF = $5,000 MXN/mes (equipo fundador sin sueldo; dominio, herramientas) | 5,000 / 484.17 = 10.3 | **11** |
| CF = $15,000 MXN/mes (medio tiempo de una persona) | 15,000 / 484.17 = 31.0 | **31** |
| CF = $30,000 MXN/mes (equipo pequeño) | 30,000 / 484.17 = 62.0 | **62** |

**Sensibilidad (variables que más mueven el resultado):**
- Si el soporte se reduce a 30 min/mes: CV = $239.83, margen = $559.17, y con CF = $15,000 bastan **27** restaurantes.
- Si el precio validado fuera $499: margen = $499 − (128.70 + 4.17 + 150 + 19.96) = $196.17, y con CF = $15,000 se necesitarían **77**. Por eso el precio debe validarse con datos de ahorro reales.

---

## 5. Ejemplo de impacto económico (🔵 simulado y auditable)

### 5.1 Base del ejemplo

**Restaurante de ejemplo:** el restaurante SIMULADO del repositorio (365 días, 30 platillos, 46 insumos).

```
Compras mensuales de insumos (C) = compra tradicional en 305 días comparables × 30 / 305
                                 = $3,073,056.50 × 30 / 305 = $302,267.85 MXN                    (B12)
```

Origen del dato: `GET /api/historial-compras?agrupar=mes`, campo `totales.compra_tradicional_mxn` (corrida del 2026-11-26, semilla 42).

### 5.2 Cálculo paso a paso (tasas de la Guía del Reto)

| Paso | Fórmula | Resultado |
|---|---|---|
| 1. Merma mensual actual | C × 10 % (B10) | 302,267.85 × 0.10 = **$30,226.78** |
| 2. Merma con Opsia | C × 6.5 % (B11) | 302,267.85 × 0.065 = **$19,647.41** |
| 3. Ahorro bruto mensual | (1) − (2) = C × 3.5 % | **$10,579.37** |
| 4. Costo de la suscripción | P (B2) | **$799.00** |
| 5. **Margen neto recuperado** | (3) − (4) | **$9,780.37 MXN/mes** |
| 6. Retorno sobre la suscripción | (5) / (4) | **12.2 veces** |
| 7. Días para pagar la suscripción | P / ((3) / 30) | **2.3 días** |
| 8. Reducción relativa de la merma | (10 % − 6.5 %) / 10 % | **35 %** |

Cada peso de merma evitada es margen neto: el insumo ya no se compra, o se vende en lugar de tirarse. No se cuenta aquí el ahorro adicional por comprar menos (sección 5.3), para no sumar dos veces.

### 5.3 Contraste con lo que midió la simulación

| Indicador (305 días comparables) | Compra tradicional | Opsia | Fuente |
|---|---|---|---|
| Compra de insumos | $3,073,056.50 | $2,158,100.02 (−29.8 %) | `/api/historial-compras` |
| Merma (lo que caduca) | $411,235.19 (13.4 % de lo comprado) | $113,674.79 (5.3 % de lo comprado) | ídem |
| Merma evitada por mes | — | $29,268.24 | (411,235.19 − 113,674.79) × 30 / 305 |
| Demanda no cubierta | 1.00 % | 0.98 % | ídem |

El ejemplo de la sección 5.2 supone una reducción de merma de 35 %, la **mitad** de la simulada (72 %). Si la reducción real fuera la simulada, el ahorro sería unas 2.8 veces mayor ($29,268 contra $10,579). Presentamos el escenario conservador.

**Advertencia:** la tasa de merma simulada (13.4 %) sale de un supuesto del generador (compra "a ojo" con colchón de −5 % a +20 % sobre el día más fuerte de la semana anterior). No representa a la industria. La tasa real se mide en el piloto (B10).

---

## 6. Adquisición de primeros usuarios, riesgos y próximos pasos

### 6.1 Piloto gratuito de 14 días

| Día | Actividad | Entregable |
|---|---|---|
| −7 a 0 | Visita a restaurantes de una misma plaza; firma de carta de piloto; **pesaje de merma diario** como línea base (sin el sistema) | Línea base de merma en kg y $ |
| 0 | Carga de menú, recetas y precios de proveedor; exportación de ventas del POS (CSV) de al menos 60 días | Base de datos con `origen_dato = 'REAL'` |
| 1 a 14 | Uso diario: compra sugerida (mañana), promociones (mediodía), alerta (tarde) | Bitácoras de uso |
| 14 | Comparación contra la línea base: merma, desabasto, horas de uso | Reporte de ahorro auditable |
| 15 | Oferta de suscripción con el ahorro medido | Conversión a pago o razones de rechazo |

**Cómo conseguir los primeros restaurantes:**
- visita en persona a locales de una plaza cercana a la universidad;
- el argumento es el reporte de ahorro gratuito, no la tecnología;
- se busca una alianza con un comedor comunitario o la red estudiantil, que da valor social y razón para hablar con la administración de la plaza.

**Métricas de éxito del piloto:**
- reducción de merma en $ frente a la línea base;
- días con desabasto igual o menor;
- uso de al menos 5 de 7 días por semana;
- disposición a pagar P.

### 6.2 Riesgos y mitigación

| Riesgo | Impacto | Mitigación |
|---|---|---|
| **Mala captura de inventario** (nadie registra lotes o caducidades) | La Vista 2 recomienda sobre datos falsos | Captura mínima: solo insumos perecederos; registro con foto de la factura al recibir; recordatorio diario; el sistema marca datos viejos |
| **Resistencia al cambio** del encargado de compras | No se usa la recomendación | El encargado decide; el sistema sugiere y explica (importancia de variables, margen). Mostrar el ahorro de su propia semana |
| **Historial insuficiente** (menos de 60 días) | Predicción débil | Arrancar con el promedio por día de la semana y activar el modelo cuando haya historial; el sistema ya compara contra esa línea base |
| **Datos simulados no representan la realidad** | Las cifras del prototipo no se cumplen | El plan usa un escenario conservador (35 % contra 72 % simulado); el piloto mide la línea base real |
| **Dependencia de Gemini** (precio, retiro de modelos, cuota) | Sin texto de promociones | Modo respaldo con reglas locales; modelo configurable (ya ocurrió con `gemini-2.5-flash`, A10); costo de Gemini < 2 % del CV |
| **Inocuidad en donaciones** | Riesgo sanitario y reputacional | Ventana que termina 2 h antes del cierre, refrigeración a 4 °C o menos, protocolo firmado con el comedor receptor y revisión de la normativa aplicable antes de operar |
| **Precio no aceptado** | No se alcanza el punto de equilibrio | Validar disposición a pagar en el piloto; planes por número de platillos o cobro ligado al ahorro medido |
| **Competencia de POS** que agregue pronóstico | Pérdida de diferenciación | Integrarse con el POS (CSV o API) en lugar de competir; enfoque en merma y rescate |

### 6.3 Próximos pasos

1. **Consultar precios PROFECO** de los 46 insumos en *Quién es Quién en los Precios* y reemplazar los precios SIMULADOS (`docs/02_base_de_datos.md`, sección 7).
2. **Dimensionar el mercado** con el procedimiento DENUE de la sección 2.2 para una alcaldía piloto.
3. **Probar Gemini con una llave real** y medir los tokens reales para reemplazar B3 y B4.
4. **Piloto de 14 días** con 3 a 5 restaurantes de una plaza.
5. **Arquitectura multi-restaurante** y autenticación para bajar el hosting por cliente.
6. **Integración con WhatsApp** para avisos reales a comedores comunitarios.

---

## 7. Cómo defender los números ante los jueces (guía para Alan y Diego)

**Regla de oro:** antes de decir una cifra, digan su color. "Según el PNUMA…" (🟢), "Nuestro supuesto es…" (🟡), "En la simulación…" (🔵).

| Si preguntan… | Respuesta segura | No digan |
|---|---|---|
| "¿Cuánto ahorra un restaurante?" | "No lo sabemos todavía para un restaurante real. En un escenario conservador, de 10 % a 6.5 % de merma sobre $302 mil de compras, serían $9,780 al mes netos. La simulación dio más, pero es simulada; el piloto lo medirá." | "Ahorra $10 mil al mes" sin contexto |
| "¿De dónde sale el 10 %?" | "Es el valor de ejemplo de la Guía del Reto, marcado como supuesto (B10). No encontramos un promedio verificable de merma en restaurantes mexicanos; por eso el piloto empieza pesando la merma." | "Es el promedio de la industria" |
| "¿Cuál es su mercado?" | "El techo es la rama 7225: 740,231 establecimientos según DENUE 2026. Nuestro segmento es un subconjunto; aquí está el procedimiento para contarlo." | Cualquier número de mercado no calculado |
| "¿Por qué $799?" | "Es un supuesto: menos del 10 % del ahorro conservador y por encima del costo variable de $315. Lo validamos en el piloto." | "Es lo que cobra la competencia" (no encontramos precios publicados) |
| "¿Y si Gemini sube de precio?" | "Gemini cuesta unos $4 al mes por restaurante con nuestro uso medido; aunque se multiplicara por 10, seguiría siendo menor que el hosting. Y hay modo respaldo." | "La IA es gratis" |
| "¿Por qué no usar Cheaf?" | "Es complementaria: Cheaf vende lo que ya sobró y cobra comisión; nosotros evitamos que sobre. Podríamos publicar el excedente ahí." | Hablar mal del competidor |
| "¿Too Good To Go está en México?" | "No encontramos confirmación de que opere para consumidores en México; lo usamos como referencia internacional." | Afirmar que opera |
| "¿Los precios de insumos son de PROFECO?" | "Son simulados provisionales. Verificamos uno: tortilla $24.27/kg en PROFECO (abril de 2026) y nuestro valor simulado era $24. Reemplazar los 46 es un próximo paso." | "Todos vienen de PROFECO" |

**Antes de presentar:**
- volver a abrir los enlaces de la Tabla A (precios de nube, Gemini, tipo de cambio) por si cambiaron;
- tener abierto este documento en la sección 0;
- si un juez señala un supuesto, aceptarlo y explicar cómo se valida: eso suma en metodología.
