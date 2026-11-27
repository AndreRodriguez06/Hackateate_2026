# 03 · Modelo predictivo de demanda (Random Forest)

> **Apartado 3 · Orden 1.3** de la Tabla de Medios y Fines.
> Estado: ✅ implementado y probado (`tests/test_modelo_demanda.py`, 12 pruebas).

> ⚠️ **El modelo se entrenó y se evaluó solo con datos SIMULADOS** (`origen_dato = 'SIMULADO'` en `data/restaurante.db`). Las métricas de este documento demuestran que el método funciona sobre reglas conocidas; **no** son una promesa de precisión en un restaurante real. El paquete del modelo guarda la etiqueta `origen_dato` y cada predicción la devuelve.

## 1. Objetivo

Decirle al encargado **cuánto comprar hoy de cada insumo**, con un margen de seguridad que evite quedarse sin platillos (desabasto o *stockout*), y explicar **qué variables** pesaron en la predicción.

## 2. Medios utilizados

| Medio | Uso |
|---|---|
| `data/restaurante.db` (Apartado 2) | Historial de 365 días: contexto, comensales y consumo diario de 46 insumos. |
| scikit-learn 1.5.2 · `RandomForestRegressor` | Modelo de predicción. |
| scikit-learn · `TimeSeriesSplit`, `mean_absolute_error`, `r2_score` | Validación temporal y métricas. |
| joblib | Guarda el modelo en `ml/modelo_rf.pkl`. |
| `ml/modelo_demanda.py` | Entrenamiento, validación, predicción, historial fuera de muestra y línea de comandos. |
| `tests/test_modelo_demanda.py` | 12 pruebas automáticas. |

## 3. Cómo ejecutarlo

```bash
pip install -r requirements.txt
python data/generar_datos.py                 # si aún no existe la base
python ml/modelo_demanda.py entrenar         # valida, entrena y guarda ml/modelo_rf.pkl (≈ 10 s)
python ml/modelo_demanda.py predecir --insumo pollo --dia 4 --quincena --lluvia --margen 0.08
python ml/modelo_demanda.py predecir --insumo pollo --dia 5 --festivo --plaza --epoca navidena
python ml/modelo_demanda.py importancias
python -m unittest discover -s tests -v
```

`entrenar` también escribe `ml/metricas.json` con todas las métricas. No se sube a git porque cambia con cada regeneración de datos.

**Reentrenamiento automático.** El modelo guarda la fecha de generación de los datos con los que se entrenó. Al arrancar, el backend compara esa fecha con la de `data/restaurante.db` y **reentrena solo** si no coinciden (por ejemplo, si generaste datos con otra semilla).

Desde Python (así lo usa el backend):

```python
from ml.modelo_demanda import predecir_compra
r = predecir_compra("pollo", dia_semana=5, es_quincena=False, lluvia=False, evento=False,
                    margen_seguridad=0.08, evento_plaza=True, es_dia_festivo=True, epoca="navidena")
r["compra_sugerida"], r["riesgo_desabasto"], r["importancia_variables"]
```

## 4. Diseño del modelo

### 4.1 Qué predice

Un **solo Random Forest multisalida**. Con las 7 variables de un día predice al mismo tiempo **47 números**:
- columna 0: comensales del día;
- columnas 1 a 46: consumo de cada insumo, en su unidad (kg, L o pza).

El consumo de un insumo ya incluye la mezcla de platillos del día; por ejemplo, el 16 de septiembre se vende más pozole y sube el consumo de cerdo.

### 4.2 Variables de entrada

| Variable | Valores | Por qué está |
|---|---|---|
| `dia_semana` | 0 = lunes … 6 = domingo | La afluencia de una plaza comercial depende mucho del día. |
| `es_quincena` | 0/1 | Día de pago y el siguiente. |
| `lluvia` | 0/1 | Pronóstico del día; cambia la afluencia y la mezcla de platillos. |
| `evento_cercano` | 0/1 | Concierto, partido o evento universitario cerca de la plaza. |
| `evento_plaza` | 0/1 | Evento **dentro** de la plaza: Buen Fin, exposición, concierto. |
| `es_dia_festivo` | 0/1 | Festivos oficiales (Ley Federal del Trabajo) y fechas tradicionales (Día de las Madres, 12 de diciembre…). |
| `epoca` | 0 regular · 1 navideña · 2 cuesta de enero · 3 verano | Temporadas de gasto distintas a lo largo del año. |

Solo se usan variables que el encargado **conoce antes de comprar**; por eso no entran la temperatura real ni las ventas del mismo día. En `predecir_compra`, `evento_plaza`, `es_dia_festivo` y `epoca` son opcionales (por defecto: sin evento, no festivo, época regular).

> Versión anterior: la variable "vacaciones escolares" se sustituyó por día festivo, época del año y evento en la plaza.

### 4.3 Índice relativo al día de la semana (`RandomForestRelativo`)

El Random Forest no aprende el consumo directamente, sino **cuánto se aleja del promedio de su día de la semana**:

```
base[d]        = consumo promedio de los días d (lunes, martes, …) en el entrenamiento
índice         = consumo del día / base[d]            (1.20 = 20 % arriba de un día normal)
predicción     = índice predicho por el Random Forest × base[d]
```

**Por qué:** los festivos o el Buen Fin ocurren pocas veces al año. Si el modelo aprende valores absolutos, necesita ver "festivo en sábado", "festivo en martes", etc. por separado. Con el índice relativo, un festivo que cayó en martes también le enseña qué pasa si cae en sábado.

**Cómo se decidió:** con validación cruzada temporal (`TimeSeriesSplit`, 5 cortes) **solo sobre el periodo de entrenamiento**, sin mirar el mes de prueba. El error en comensales bajó de 13.25 (Random Forest directo) a 12.14.

### 4.4 Hiperparámetros

| Parámetro | Valor | Motivo |
|---|---|---|
| `n_estimators` | 300 | Más árboles estabilizan el promedio. |
| `max_features` | 0.33 | Cada división mira 1/3 de las variables: árboles más distintos entre sí. |
| `max_depth` | 10 | Limita la profundidad para no memorizar el ruido diario. |
| `min_samples_leaf` | 1 | — |
| `random_state` | 42 | Resultados reproducibles. |

Se eligieron probando 36 combinaciones con `TimeSeriesSplit` sobre el periodo de entrenamiento. Con los valores anteriores (sin límite de profundidad, todas las variables y hojas de 3 días) el error en validación cruzada era de 15.5 comensales; con estos, 13.2.

## 5. Validación sin fuga de datos

1. **Holdout temporal:** entrena con los primeros 335 días y evalúa con los últimos 30 días, que el modelo nunca vio. La prueba `test_prueba_es_el_ultimo_mes_sin_fuga` lo comprueba.
2. **`TimeSeriesSplit` (5 cortes)** dentro del entrenamiento: cada corte entrena con el pasado y prueba con los 55 días siguientes.

Después de validar, el modelo que se guarda se reentrena con **los 365 días**.

### 5.1 Métricas en el mes de prueba

Corrida del 2026-11-26 (entrenamiento 2025-11-26 a 2026-10-26; prueba 2026-10-27 a 2026-11-25, que incluye Día de Muertos, Día de la Revolución y el Buen Fin). Los valores cambian un poco si se regeneran los datos otro día.

| Modelo | Comensales MAE | Comensales R² | Insumos: MAE relativo promedio | Insumos: R² promedio |
|---|---|---|---|---|
| **Random Forest (índice relativo, elegido)** | **13.93** | **0.831** | **11.0 %** | **0.777** |
| Promedio del mismo día de la semana | 13.63 | 0.776 | 12.8 % | 0.661 |
| Regresión lineal simple (día como número 0–6) | 13.67 | 0.790 | 11.6 % | 0.735 |
| Regresión lineal con día y época *one-hot* | 11.31 | 0.887 | 9.7 % | 0.832 |

- **MAE** (error absoluto medio): en promedio el modelo se equivoca por 14 comensales en días de ~159.
- **R²**: proporción de la variación diaria que el modelo explica (1 = perfecto, 0 = igual que adivinar el promedio).
- **MAE relativo**: MAE dividido entre el consumo promedio del insumo, para comparar insumos con unidades distintas.

Ejemplos por insumo: tortilla de maíz, MAE 0.92 kg sobre 10.4 kg/día (8.8 %, R² 0.85); pechuga de pollo, MAE 1.21 kg sobre 13.2 kg/día (9.1 %, R² 0.81). Los insumos de bajo volumen tienen más error relativo: carne molida 14.7 %, pasta de mole 13.4 %.

`TimeSeriesSplit`: el MAE de comensales va de 10.5 a 13.6 según el corte.

### 5.2 Lectura honesta de la comparación

- En **insumos** (lo que define la compra), el Random Forest supera al promedio por día de la semana (11.0 % contra 12.8 %) y a la regresión lineal simple. En **comensales** empata con ellos.
- La regresión lineal con variables *one-hot* es **mejor** en estos datos (9.7 %). Es explicable: el generador del Apartado 2 crea los datos **sumando efectos independientes** (quincena +12 %, festivo +18 %, Buen Fin +20 %…), justo la forma que mejor ajusta una regresión lineal. Con datos reales, donde los efectos se combinan de formas que no conocemos, la ventaja puede invertirse.
- Por eso el script **calcula siempre las alternativas** con los mismos datos. Si con datos reales una alternativa gana de forma consistente, se puede cambiar el modelo sin tocar el resto del sistema.

## 6. Importancia de variables

`feature_importances_` del Random Forest, en porcentajes con un decimal que suman 100 (`importancias_en_porcentaje`):

| Variable | Importancia |
|---|---|
| Época del año | 25.1 % |
| Lluvia | 18.3 % |
| Día de la semana | 15.9 % |
| Quincena | 11.7 % |
| Evento en la plaza | 11.1 % |
| Día festivo | 10.6 % |
| Evento cercano | 7.3 % |

**Cómo leerla:** como el modelo aprende el índice relativo, **el día de la semana ya fija la base** (un sábado normal). Las importancias dicen qué variables hacen que un día quede **por arriba o por abajo** de esa base. La época del año pesa más porque afecta a muchos días seguidos (diciembre +15 %, cuesta de enero −12 %). Los festivos y eventos son raros, pero cuando ocurren mueven mucho la demanda.

Es una importancia **global** del modelo (igual para todos los insumos y días), no la explicación de una predicción concreta.

## 7. Regla de negocio anti-desabasto

### 7.1 Fórmula

```
demanda_base      = predicción del modelo para ese insumo y ese día
compra_sugerida   = demanda_base × (1 + margen_seguridad)          margen entre 0 y 0.25
inversion_mxn     = compra_sugerida × precio_unitario (SIMULADO)
riesgo_desabasto  = margen_seguridad < 0.04
```

Ejemplo (viernes de quincena con lluvia, pechuga de pollo): `demanda_base` = 15.06 kg. Con margen 8 %, `compra_sugerida` = 15.06 × 1.08 = 16.27 kg. Con margen 2 %, `riesgo_desabasto = true`.

### 7.2 Margen recomendado por insumo

Un margen fijo de 8 % **no alcanza** para todos los insumos. El modelo calcula un `margen_recomendado` para cada uno:

1. Con los cortes del `TimeSeriesSplit` (solo datos de entrenamiento) obtiene predicciones "fuera de muestra".
2. Para cada insumo mide cuánto se quedó corta la predicción cada día: `real / predicho − 1`.
3. El **percentil 90** de ese valor es el margen que habría cubierto 9 de cada 10 días.
4. Se limita entre 4 % y 25 %.

Valores: pechuga de pollo 14.4 %, tortilla 13.5 %, mediana de los 46 insumos 21.6 %. Los de bajo volumen y más variables (carne molida, mole) llegan al tope de 25 %.

### 7.3 Resultado en el mes de prueba

Las tres estrategias se evalúan contra el consumo real del último mes, valuado a precios SIMULADOS.

| Estrategia | Compra | Sobrante | Demanda no cubierta | Días-insumo con algún faltante |
|---|---|---|---|---|
| Compra tradicional "a ojo" | $322,472 | $133,832 | 1.51 % | 4.7 % |
| Opsia, margen fijo 8 % | $195,397 | $10,579 | 3.51 % | 42.2 % |
| **Opsia, margen recomendado** | **$214,025** | **$24,318** | **0.96 %** | **12.4 %** |

Lectura:
- Con el margen recomendado se compra **34 % menos** y el sobrante baja **82 %**, y la demanda no cubierta es **menor** que con la compra tradicional (0.96 % contra 1.51 %).
- Hay más días con algún faltante (12.4 % contra 4.7 %), pero son faltantes pequeños: en conjunto valen 0.96 % de lo consumido.
- Con margen fijo de 8 %, 42 % de los días-insumo tienen faltante. Por eso la interfaz alerta con margen bajo y sugiere el margen recomendado.

## 8. Historial fuera de muestra (Vista 4 · Historial de compras)

Para mostrar cuánto se habría ahorrado en **todo** el historial, `predicciones_historicas()` calcula la compra que habría sugerido el modelo **para cada día, sin haber visto ese día**:

- Los primeros 60 días no tienen predicción: el modelo necesita historial para entrenar.
- Después, cada bloque de 30 días se predice con un modelo entrenado **solo con los días anteriores** (ventana creciente).
- Compra sugerida = predicción × (1 + margen recomendado del insumo).

El resultado se guarda dentro de `modelo_rf.pkl` (`paquete["historico"]`) y lo usa `GET /api/historial-compras`. Resultado sobre los 305 días comparables (todos los insumos, precios SIMULADOS): compra $3.07 M (tradicional) contra $2.16 M (Opsia), es decir **$915 mil menos (−29.8 %)**; merma −72.4 %; demanda no cubierta 0.98 % contra 1.00 %.

> Simplificación: el margen recomendado se calcula con el periodo de entrenamiento y se aplica a todo el historial.

## 9. Decisiones técnicas

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| Un modelo multisalida | 46 modelos, uno por insumo | Un solo archivo, una sola importancia de variables y predicciones coherentes entre insumos del mismo día. |
| Índice relativo al día de la semana | Random Forest sobre valores absolutos | Comparte lo aprendido de eventos raros entre días; mejor en validación cruzada. |
| Hiperparámetros elegidos con `TimeSeriesSplit` del entrenamiento | Elegirlos mirando el mes de prueba | Elegirlos con el mes de prueba inflaría las métricas. |
| 365 días de historial | 180 días | Con 180 días (junio a noviembre) el modelo nunca vería diciembre ni enero. |
| Holdout del último mes + `TimeSeriesSplit` | Partición aleatoria (`train_test_split`) | La aleatoria deja que el modelo vea el futuro. |
| Margen recomendado con errores de entrenamiento | Calcularlo con el mes de prueba | Usar el mismo mes para ajustar y evaluar inflaría el resultado. |
| Comparar siempre contra alternativas | Reportar solo el Random Forest | Los jueces pueden pedir una línea base; también protege contra elegir un modelo peor. |
| Reentrenar si los datos cambiaron | Usar un `.pkl` viejo | Evita que el modelo y la base no correspondan. |

## 10. Evidencia: SIMULADO vs. REAL

| Elemento | Origen |
|---|---|
| Datos de entrenamiento y prueba | **SIMULADO** (Apartado 2) |
| Métricas MAE y R² | Calculadas de verdad, pero **sobre datos SIMULADOS** |
| Montos en pesos de las secciones 7.3 y 8 | **SIMULADO** (precios provisionales del Apartado 2) |
| Calendario de días festivos | Fechas reales (Ley Federal del Trabajo y tradiciones); su **efecto** en ventas es SIMULADO |
| Algoritmo, validación temporal y fórmula de compra | Método real, reutilizable con datos de un restaurante |

## 11. Cómo verificar que funciona

1. `python ml/modelo_demanda.py entrenar` imprime las tablas de las secciones 5.1 y 7.3 y crea `ml/modelo_rf.pkl`.
2. `python ml/modelo_demanda.py predecir --insumo pollo --dia 4 --margen 0.02` devuelve `"riesgo_desabasto": true`; con `--margen 0.08`, `false`.
3. `python -m unittest discover -s tests -v`: las 12 pruebas del modelo comprueban:
   - el periodo de prueba es el último mes y es posterior al entrenamiento;
   - R² de comensales mayor a 0.7 y error relativo de insumos menor a 20 %;
   - modelo y predicciones etiquetados `SIMULADO`;
   - `compra_sugerida = demanda_base × (1 + margen)`;
   - `riesgo_desabasto` es verdadero con 3.9 % y falso con 4 %;
   - más comensales en sábado que en martes, y en un sábado navideño festivo que en uno de cuesta de enero;
   - el historial fuera de muestra empieza en el día 60;
   - un modelo entrenado desde la terminal lo puede cargar el backend;
   - entradas inválidas (margen 30 %, día 7, insumo o época inexistentes) dan error;
   - las importancias suman 100 y están ordenadas.

## 12. Preguntas probables de los jueces

**¿Cómo funciona un Random Forest?**
Entrena cientos de árboles de decisión, cada uno con una muestra al azar de los días y de las variables. Cada árbol aprende reglas del tipo "si es época navideña y hay evento en la plaza, el día queda 35 % arriba de lo normal". Para predecir, se promedian todos los árboles.

**¿Por qué no una regresión lineal?**
La regresión lineal simple supone que el sábado es "el lunes más 5 pasos" y no maneja combinaciones de variables. La versión *one-hot* sí funciona bien, y **en nuestros datos simulados es mejor**, porque los generamos sumando efectos. Elegimos Random Forest porque:
- encuentra solo las combinaciones entre variables, sin programarlas a mano;
- nunca predice cantidades negativas;
- explica qué variables pesaron;
- es robusto a días atípicos.

Lo sostenemos con evidencia: el script compara ambos en cada entrenamiento y lo reportamos aunque no nos favorezca.

**¿Cómo evitan el desabasto si compran menos?**
Con tres capas:
1. el margen de seguridad;
2. la alerta cuando el margen baja de 4 %;
3. un margen recomendado por insumo, calculado con los errores reales del modelo en días que no había visto.

En el mes de prueba, la demanda no cubierta fue 0.96 % contra 1.51 % de la compra tradicional, con 82 % menos sobrante.

**¿No están evaluando con datos que ustedes inventaron?**
Sí: los datos son SIMULADOS y lo decimos. Lo que demostramos es que el método recupera reglas conocidas sin ver el mes de prueba. Con datos reales se corre el mismo `entrenar`.
