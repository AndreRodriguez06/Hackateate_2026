# 03 · Modelo predictivo de demanda (Random Forest)

> **Apartado 3 · Orden 1.3** de la Tabla de Medios y Fines.
> Estado: ✅ implementado y probado (`tests/test_modelo_demanda.py`, 9 pruebas).

> ⚠️ **El modelo se entrenó y se evaluó solo con datos SIMULADOS** (`origen_dato = 'SIMULADO'` en `data/restaurante.db`). Las métricas de este documento demuestran que el método funciona sobre reglas conocidas. **No** son una promesa de precisión en un restaurante real. El paquete del modelo guarda la etiqueta `origen_dato` y cada predicción la devuelve.

## 1. Objetivo

Decirle al encargado **cuánto comprar hoy de cada insumo**, con un margen de seguridad que evite quedarse sin platillos (desabasto o *stockout*), y explicar **qué variables** pesaron en la predicción.

## 2. Medios utilizados

| Medio | Uso |
|---|---|
| `data/restaurante.db` (Apartado 2) | Historial de 180 días: contexto, comensales y consumo diario de 46 insumos. |
| scikit-learn 1.5.2 · `RandomForestRegressor` | Modelo de predicción. |
| scikit-learn · `TimeSeriesSplit`, `mean_absolute_error`, `r2_score` | Validación temporal y métricas. |
| joblib | Guarda el modelo en `ml/modelo_rf.pkl`. |
| `ml/modelo_demanda.py` | Entrenamiento, validación, predicción y línea de comandos. |
| `tests/test_modelo_demanda.py` | 9 pruebas automáticas. |

## 3. Cómo ejecutarlo

```bash
pip install -r requirements.txt
python data/generar_datos.py                 # si aún no existe la base
python ml/modelo_demanda.py entrenar         # valida, entrena y guarda ml/modelo_rf.pkl (≈ 5 s)
python ml/modelo_demanda.py predecir --insumo pollo --dia 4 --quincena --lluvia --margen 0.08
python ml/modelo_demanda.py importancias
python -m unittest discover -s tests -v
```

`entrenar` también escribe `ml/metricas.json` con todas las métricas (no se sube a git porque cambia con cada regeneración de datos).

Desde Python (así lo usará el backend en el Apartado 4):

```python
from ml.modelo_demanda import predecir_compra
r = predecir_compra("pollo", dia_semana=4, es_quincena=True, lluvia=True, evento=False, margen_seguridad=0.08)
r["compra_sugerida"], r["riesgo_desabasto"], r["importancia_variables"]
```

## 4. Diseño del modelo

### 4.1 Qué predice

Un **solo Random Forest multisalida**. Con las 5 variables de un día predice al mismo tiempo **47 números**:

- columna 0: comensales del día;
- columnas 1 a 46: consumo de cada insumo, en su unidad (kg, L o pza).

El consumo de un insumo ya incluye la mezcla de platillos de ese día (por ejemplo, con lluvia se vende más pozole y sube el consumo de cerdo), porque en el Apartado 2 se calculó como ventas × recetas.

### 4.2 Variables de entrada

| Variable | Tipo | Por qué está |
|---|---|---|
| `dia_semana` | 0 = lunes … 6 = domingo | La afluencia de una plaza comercial depende sobre todo del día. |
| `es_quincena` | 0/1 | Día de pago y el siguiente. |
| `lluvia` | 0/1 | Pronóstico del día; cambia la afluencia y la mezcla de platillos. |
| `evento_cercano` | 0/1 | Concierto o evento universitario. |
| `temporada_vacacional` | 0/1 | Vacaciones escolares. Es opcional en `predecir_compra` (por defecto `False`). |

Solo se usan variables que el encargado **conoce antes de comprar**. Por eso no entran la temperatura real ni las ventas del mismo día.

### 4.3 Hiperparámetros

| Parámetro | Valor | Motivo |
|---|---|---|
| `n_estimators` | 300 | Más árboles estabilizan el promedio; entrenar tarda menos de 1 s. |
| `min_samples_leaf` | 3 | Cada hoja promedia al menos 3 días: evita memorizar el ruido diario. |
| `max_features` | 1.0 | Con 5 variables, cada árbol puede ver todas. |
| `random_state` | 42 | Resultados reproducibles. |

## 5. Validación sin fuga de datos

Un error común es mezclar días al azar entre entrenamiento y prueba: el modelo "ve el futuro" y las métricas salen infladas. Aquí se respeta el orden del tiempo de dos formas:

1. **Holdout temporal.** Entrena con los primeros 150 días (5 meses) y evalúa con los últimos 30 días (1 mes), que el modelo nunca vio. La prueba automática `test_prueba_es_el_ultimo_mes_sin_fuga` comprueba que la primera fecha de prueba sea posterior a la última de entrenamiento.
2. **`TimeSeriesSplit` (5 cortes)** dentro de los 150 días: cada corte entrena con el pasado y prueba con los 25 días siguientes. Sirve para ver si el error es estable y para calcular el margen recomendado (sección 7).

Después de validar, el modelo que se guarda se reentrena con **los 180 días**, porque en producción conviene aprender también del último mes.

### 5.1 Métricas en el mes de prueba

Corrida del 2026-11-26 (entrenamiento 2026-05-30 a 2026-10-26; prueba 2026-10-27 a 2026-11-25). Los valores cambian un poco si se regeneran los datos otro día, porque el historial termina "ayer".

| Modelo | Comensales MAE | Comensales R² | Insumos: MAE relativo promedio | Insumos: R² promedio |
|---|---|---|---|---|
| **Random Forest (elegido)** | **8.76** | **0.905** | **9.2 %** | **0.799** |
| Promedio del mismo día de la semana | 8.98 | 0.893 | 10.5 % | 0.740 |
| Regresión lineal simple (día como número 0–6) | 13.77 | 0.766 | 11.8 % | 0.711 |
| Regresión lineal con día *one-hot* | 8.25 | 0.920 | 8.5 % | 0.840 |

- **MAE** (error absoluto medio): en promedio el modelo se equivoca por 8.8 comensales en días de ~154.
- **R²**: proporción de la variación diaria que el modelo explica (1 = perfecto, 0 = igual que adivinar el promedio).
- **MAE relativo**: MAE dividido entre el consumo promedio del insumo, para comparar insumos con unidades distintas.

Ejemplos por insumo: tortilla de maíz MAE 0.54 kg sobre 9.5 kg/día (5.6 %, R² 0.93); pechuga de pollo MAE 0.76 kg sobre 12.2 kg/día (6.2 %, R² 0.90). Los insumos de bajo volumen tienen más error relativo: pasta de mole 10.5 %, R² 0.59.

`TimeSeriesSplit`: el MAE de comensales va de 8.3 a 14.5 según el corte. Los cortes con menos días de entrenamiento se equivocan más, que es lo esperado.

### 5.2 Lectura honesta de la comparación

- El Random Forest **supera** al promedio por día de la semana y a la regresión lineal simple.
- La regresión lineal con el día codificado *one-hot* queda **ligeramente mejor** (MAE 8.25 contra 8.76). Es explicable: el generador del Apartado 2 crea los datos sumando efectos casi independientes (quincena +12 %, lluvia +6 %, …), que es justo la forma que mejor ajusta una regresión lineal.
- Por eso el script **calcula siempre las alternativas** con los mismos datos. Si con datos reales una alternativa gana de forma consistente, se puede cambiar el modelo sin tocar el resto del sistema, porque `predecir_compra` no cambia su forma de responder.

## 6. Importancia de variables

`feature_importances_` del Random Forest, convertida a porcentajes con un decimal que suman 100 (función `importancias_en_porcentaje`):

| Variable | Importancia |
|---|---|
| Día de la semana | 92.7 % |
| Vacaciones escolares | 2.2 % |
| Evento cercano | 2.1 % |
| Quincena | 1.7 % |
| Lluvia | 1.3 % |

Cómo leerla: es cuánto reduce el error, en promedio en todos los árboles, cada vez que un árbol divide los días usando esa variable. El día de la semana domina porque la diferencia entre un martes (~118 comensales) y un sábado (~213) es mucho mayor que el +12 % de la quincena. Las variables raras (eventos en ~7 % de los días) aportan poco al total aunque sí cambian la predicción del día en que ocurren.

> El prototipo `prueba1/` muestra pesos ilustrativos (45 %, 30 %, 15 %, 10 %). En el Apartado 5 el frontend mostrará estos valores reales del modelo.

Es una importancia **global** del modelo (igual para todos los insumos y días), no una explicación de una predicción concreta.

## 7. Regla de negocio anti-desabasto

### 7.1 Fórmula

```
demanda_base      = predicción del Random Forest para ese insumo y ese día
compra_sugerida   = demanda_base × (1 + margen_seguridad)          margen entre 0 y 0.25
inversion_mxn     = compra_sugerida × precio_unitario (SIMULADO)
riesgo_desabasto  = margen_seguridad < 0.04
```

Ejemplo (viernes de quincena con lluvia, pechuga de pollo): `demanda_base` = 14.66 kg. Con margen 8 %, `compra_sugerida` = 14.66 × 1.08 = 15.83 kg. Con margen 2 %, `riesgo_desabasto = true`.

### 7.2 Margen recomendado por insumo

Un margen fijo de 8 % **no alcanza** para todos los insumos. Por eso el modelo calcula un `margen_recomendado` para cada uno:

1. Con los cortes del `TimeSeriesSplit` (solo datos de entrenamiento) se obtienen predicciones "fuera de muestra".
2. Para cada insumo se mide cuánto se quedó corta la predicción cada día: `real / predicho − 1`.
3. El **percentil 90** de ese valor es el margen que habría cubierto 9 de cada 10 días.
4. Se limita entre 4 % y 25 %.

Mediana entre los 46 insumos: 16 %. Pechuga de pollo: 11.6 %. Tortilla: 11.4 %. Insumos de bajo volumen y más variables (carne molida, chipotle): ~21 %.

`predecir_compra` devuelve este valor para que la interfaz pueda sugerirlo, pero el margen sigue siendo decisión del encargado.

### 7.3 Resultado en el mes de prueba

Las tres estrategias se evalúan contra el consumo real del último mes. Los montos usan precios SIMULADOS.

| Estrategia | Compra | Sobrante | Demanda no cubierta | Días-insumo con algún faltante |
|---|---|---|---|---|
| Compra tradicional "a ojo" | $288,712 | $113,820 | 1.05 % | 4.7 % |
| ZeroMerma, margen fijo 8 % | $186,421 | $12,965 | 1.86 % | 27.2 % |
| **ZeroMerma, margen recomendado** | **$197,900** | **$22,151** | **0.56 %** | **11.1 %** |

Definiciones:
- **Sobrante**: lo comprado que no se usó ese día, valuado en pesos. No todo se tira; la merma depende de la vida útil (Apartado 2, sección 5.4).
- **Demanda no cubierta**: valor de lo que faltó entre el valor de lo que se consumió.
- **Días-insumo con faltante**: de las 30 × 46 combinaciones, en cuántas faltó *cualquier* cantidad, aunque sea pequeña.

Lectura:
- Con el margen recomendado se compra **31 % menos** y el sobrante baja **81 %**, mientras que la demanda no cubierta es **menor** que con la compra tradicional (0.56 % contra 1.05 %).
- Hay más días con algún faltante (11.1 % contra 4.7 %), pero son faltantes pequeños: en conjunto valen 0.56 % de lo consumido. La compra tradicional tiene menos días con faltante porque compra de más casi siempre, y cuando falla es por recortes grandes.
- Con margen fijo de 8 % el sobrante es mínimo, pero 27 % de los días-insumo tienen faltante. Por eso la interfaz alerta con margen bajo y sugiere el margen recomendado.

## 8. Decisiones técnicas

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| Un modelo multisalida | 46 modelos, uno por insumo | Un solo archivo, una sola importancia de variables y predicciones coherentes entre insumos del mismo día. |
| Predecir consumo de insumos | Predecir comensales y multiplicar por un promedio | El consumo ya incluye cómo cambia la mezcla de platillos con el contexto. |
| Holdout del último mes + `TimeSeriesSplit` | Partición aleatoria (`train_test_split`) | La aleatoria deja que el modelo vea el futuro. |
| Margen recomendado con errores de entrenamiento | Calcularlo con el mes de prueba | Usar el mes de prueba para ajustar el margen y luego evaluarlo con el mismo mes inflaría el resultado. |
| Comparar siempre contra alternativas | Reportar solo el Random Forest | Los jueces pueden pedir una línea base; también protege contra elegir un modelo peor. |
| `joblib` con metadatos en el `.pkl` | Guardar solo el modelo | El paquete incluye insumos, métricas, importancias, margen recomendado y `origen_dato`. |

## 9. Evidencia: SIMULADO vs. REAL

| Elemento | Origen |
|---|---|
| Datos de entrenamiento y prueba | **SIMULADO** (Apartado 2). |
| Métricas MAE y R² | Calculadas de verdad, pero **sobre datos SIMULADOS**. |
| Montos en pesos de la sección 7.3 | **SIMULADO** (precios provisionales del Apartado 2). |
| Algoritmo, validación temporal y fórmula de compra | Método real, reutilizable con datos de un restaurante. |

## 10. Cómo verificar que funciona

1. `python ml/modelo_demanda.py entrenar` imprime las tablas de las secciones 5.1 y 7.3 y crea `ml/modelo_rf.pkl`.
2. `python ml/modelo_demanda.py predecir --insumo pollo --dia 4 --margen 0.02` devuelve `"riesgo_desabasto": true`; con `--margen 0.08`, `false`.
3. `python -m unittest discover -s tests -v`: las 9 pruebas del modelo comprueban:
   - el periodo de prueba es el último mes y es posterior al entrenamiento;
   - R² de comensales mayor a 0.7 y error relativo de insumos menor a 20 %;
   - modelo y predicciones etiquetados como `SIMULADO`;
   - `compra_sugerida = demanda_base × (1 + margen)`;
   - `riesgo_desabasto` es verdadero con 3.9 % y falso con 4 %;
   - más comensales en sábado que en martes;
   - el insumo se encuentra por clave o por nombre;
   - entradas inválidas (margen 30 %, día 7, insumo inexistente) dan error;
   - las importancias suman 100 y están ordenadas.

## 11. Preguntas probables de los jueces

**¿Cómo funciona un Random Forest?**
Entrena cientos de árboles de decisión. Cada árbol aprende reglas del tipo "si es sábado y hay quincena, el consumo de pollo es ~X" a partir de una muestra al azar de los días. Para predecir, se promedian las respuestas de todos los árboles. Promediar muchos árboles distintos reduce el error de cada uno por separado.

**¿Por qué no una regresión lineal?**
Una regresión lineal simple supone que cada día de la semana suma lo mismo que el anterior (lunes 0, martes 1, …). Pero el sábado no es "el lunes más 5 pasos": el error sube de 8.8 a 13.8 comensales. Se puede corregir codificando el día *one-hot*, y en nuestros datos simulados esa versión queda ligeramente mejor, porque los simulamos sumando efectos. Elegimos Random Forest porque:
- encuentra solo las interacciones (por ejemplo, lluvia en fin de semana), sin que tengamos que adivinarlas y programarlas;
- nunca predice cantidades negativas ni fuera del rango visto;
- trae la importancia de variables para explicar al encargado;
- es robusto a días atípicos.

Y lo sostenemos con evidencia: el script compara las dos en cada entrenamiento.

**¿Cómo evitan el desabasto si compran menos?**
Con tres capas:
1. el margen de seguridad sobre la predicción;
2. la alerta cuando el margen baja de 4 %;
3. un margen recomendado por insumo, calculado con los errores reales del modelo en días que no había visto.

En el mes de prueba, con el margen recomendado, la demanda no cubierta fue 0.56 % contra 1.05 % de la compra tradicional, con 81 % menos sobrante.

**¿No están evaluando con los mismos datos que inventaron?**
Sí: los datos son SIMULADOS y lo decimos. Lo que demostramos es que el método recupera reglas conocidas sin ver el mes de prueba. Con datos reales se corre el mismo `entrenar` y se obtienen métricas reales.
