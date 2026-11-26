#!/usr/bin/env python3
"""
ZeroMerma AI — Modelo predictivo de demanda (Random Forest)
Archivo: /ml/modelo_demanda.py

Qué hace
--------
1. Lee el historial SIMULADO de `data/restaurante.db` (afluencia, contexto y
   consumo diario de cada insumo, que sale de ventas × recetas).
2. Entrena UN RandomForestRegressor multisalida: con las variables del día
   predice al mismo tiempo los comensales y el consumo de los 46 insumos.
3. Valida sin fuga de datos:
     a) Holdout temporal: entrena con los primeros 5 meses y evalúa con el
        último mes (30 días), que el modelo nunca vio.
     b) TimeSeriesSplit (5 cortes) dentro del periodo de entrenamiento.
   Reporta MAE y R² reales, y los compara contra la compra tradicional "a ojo",
   un promedio por día de la semana y una regresión lineal.
4. Reentrena con todo el historial y guarda `ml/modelo_rf.pkl`.
5. `predecir_compra(...)` aplica la regla de negocio anti-desabasto:
       compra_sugerida = demanda_base × (1 + margen_seguridad)
       riesgo_desabasto = margen_seguridad < 0.04

Todos los datos de entrenamiento están etiquetados como SIMULADO.

Uso
---
    python ml/modelo_demanda.py entrenar
    python ml/modelo_demanda.py predecir --insumo pollo --dia 4 --quincena --lluvia --margen 0.08
    python ml/modelo_demanda.py importancias
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

RAIZ = Path(__file__).resolve().parents[1]
RUTA_DB = RAIZ / "data" / "restaurante.db"
RUTA_MODELO = Path(__file__).resolve().parent / "modelo_rf.pkl"
RUTA_METRICAS = Path(__file__).resolve().parent / "metricas.json"

# Variables de entrada del modelo (columnas de contexto_diario).
# Son las que el encargado conoce ANTES de comprar: calendario, pronóstico y eventos.
VARIABLES = ["dia_semana", "es_quincena", "lluvia", "evento_cercano", "evento_plaza", "es_dia_festivo", "epoca"]
NOMBRES_VARIABLES = {
    "dia_semana": "Día de la semana",
    "es_quincena": "Quincena",
    "lluvia": "Lluvia",
    "evento_cercano": "Evento cercano",
    "evento_plaza": "Evento en la plaza",
    "es_dia_festivo": "Día festivo",
    "epoca": "Época del año",
}
# Época del año codificada como número (mismo orden que data/generar_datos.py: EPOCAS).
EPOCAS = ["regular", "navidena", "cuesta_enero", "verano"]
MIN_DIAS_HISTORICO = 60      # el historial fuera de muestra empieza cuando hay 2 meses para entrenar
PASO_HISTORICO = 30          # se reentrena cada 30 días (ventana creciente)

DIAS_PRUEBA = 30            # "último mes" del holdout temporal
MARGEN_MINIMO_SEGURO = 0.04  # por debajo de 4 % hay riesgo de desabasto
MARGEN_MAXIMO = 0.25
SEMILLA = 42

HIPERPARAMETROS = {
    # Elegidos con TimeSeriesSplit SOLO sobre el periodo de entrenamiento (docs/03_modelo_ml.md, sección 4.3).
    "n_estimators": 300,      # número de árboles
    "max_features": 0.33,     # cada división mira 1/3 de las variables: árboles más distintos entre sí
    "max_depth": 10,          # limita la profundidad para no memorizar el ruido diario
    "min_samples_leaf": 1,
    "random_state": SEMILLA,
    "n_jobs": -1,
}

ORIGEN_DATO = "SIMULADO"


# =============================================================================
# 1. CARGA DE DATOS
# =============================================================================

def cargar_datos(ruta_db: Path = RUTA_DB) -> dict:
    """
    Arma la matriz de entrenamiento:
      X: una fila por día con las VARIABLES de contexto
      Y: una fila por día; columna 0 = comensales, columnas 1..N = consumo de cada insumo
    """
    if not ruta_db.exists():
        raise FileNotFoundError(f"No existe {ruta_db}. Corre primero: python data/generar_datos.py")

    con = sqlite3.connect(ruta_db)
    con.row_factory = sqlite3.Row

    origenes = {r[0] for r in con.execute("SELECT DISTINCT origen_dato FROM contexto_diario")}
    origenes |= {r[0] for r in con.execute("SELECT DISTINCT origen_dato FROM consumo_insumos_diario")}

    insumos = [dict(r) for r in con.execute(
        "SELECT id, clave, nombre, unidad, precio_unitario_mxn FROM insumos ORDER BY id")]
    dias = [dict(r) for r in con.execute(
        "SELECT fecha, comensales, dia_semana, es_quincena, lluvia, evento_cercano, evento_plaza,"
        " es_dia_festivo, epoca_anio FROM contexto_diario ORDER BY fecha")]
    for d in dias:
        d["epoca"] = EPOCAS.index(d["epoca_anio"])
    fila_meta = con.execute("SELECT valor FROM meta_dataset WHERE clave = 'generado_en'").fetchone()

    # Consumo y compra tradicional por (fecha, insumo)
    consumo, compra_trad = {}, {}
    for r in con.execute("SELECT fecha, insumo_id, consumo_real, compra_tradicional FROM consumo_insumos_diario"):
        consumo[(r["fecha"], r["insumo_id"])] = r["consumo_real"]
        compra_trad[(r["fecha"], r["insumo_id"])] = r["compra_tradicional"]
    con.close()

    fechas = [d["fecha"] for d in dias]
    X = np.array([[d[v] for v in VARIABLES] for d in dias], dtype=float)
    Y = np.array([[d["comensales"]] + [consumo[(d["fecha"], i["id"])] for i in insumos] for d in dias])
    T = np.array([[compra_trad[(f, i["id"])] for i in insumos] for f in fechas])

    return {"fechas": fechas, "X": X, "Y": Y, "compra_tradicional": T,
            "insumos": insumos, "origen_dato": "+".join(sorted(origenes)),
            "dataset_generado_en": fila_meta[0] if fila_meta else None}


# =============================================================================
# 2. VALIDACIÓN TEMPORAL Y MÉTRICAS
# =============================================================================

class RandomForestRelativo:
    """
    Random Forest que aprende el ÍNDICE RELATIVO al promedio de cada día de la semana.

    1. base[d] = consumo promedio histórico del día de la semana d (lunes, martes, ...).
    2. El Random Forest aprende  y / base[d]  (1.20 = 20 % arriba de un día normal).
    3. Predicción = índice predicho × base[d].

    Así un festivo o un evento que ocurrió un martes también enseña al modelo qué pasa
    si ocurre un sábado: los efectos se comparten entre días. Se eligió frente al
    Random Forest directo con validación cruzada temporal sobre el periodo de entrenamiento.
    """

    def __init__(self, **parametros):
        self.parametros = parametros

    def fit(self, X: np.ndarray, Y: np.ndarray) -> "RandomForestRelativo":
        dias = X[:, 0].astype(int)
        promedio_general = Y.mean(axis=0)
        self.base_ = np.array([Y[dias == d].mean(axis=0) if (dias == d).any() else promedio_general
                               for d in range(7)])
        self.base_ = np.maximum(self.base_, 1e-9)
        self.rf_ = RandomForestRegressor(**self.parametros).fit(X, Y / self.base_[dias])
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.rf_.predict(X) * self.base_[X[:, 0].astype(int)]

    @property
    def feature_importances_(self) -> np.ndarray:
        return self.rf_.feature_importances_


def _nuevo_rf() -> RandomForestRelativo:
    return RandomForestRelativo(**HIPERPARAMETROS)


def _metricas(y_real: np.ndarray, y_pred: np.ndarray) -> dict:
    """MAE y R² de cada columna, más un MAE relativo (MAE / promedio real) para comparar insumos."""
    mae = mean_absolute_error(y_real, y_pred, multioutput="raw_values")
    r2 = r2_score(y_real, y_pred, multioutput="raw_values")
    promedio = np.maximum(y_real.mean(axis=0), 1e-9)
    return {"mae": mae, "r2": r2, "mae_relativo": mae / promedio}


def _promedio_por_dia(X_ent, Y_ent, X_pru) -> np.ndarray:
    """Línea base ingenua: el promedio histórico del mismo día de la semana."""
    salida = np.zeros((len(X_pru), Y_ent.shape[1]))
    for dia in range(7):
        mascara = X_ent[:, 0] == dia
        if mascara.any():
            salida[X_pru[:, 0] == dia] = Y_ent[mascara].mean(axis=0)
    return salida


def _resumen(nombre: str, met: dict) -> dict:
    """Comensales por separado; para los insumos, promedio simple de sus métricas."""
    return {
        "modelo": nombre,
        "comensales_mae": round(float(met["mae"][0]), 2),
        "comensales_r2": round(float(met["r2"][0]), 3),
        "insumos_mae_relativo_pct": round(float(met["mae_relativo"][1:].mean() * 100), 1),
        "insumos_r2_promedio": round(float(met["r2"][1:].mean()), 3),
    }


def validar(datos: dict, margen_referencia: float = 0.08) -> dict:
    """Holdout del último mes + TimeSeriesSplit + comparación con alternativas."""
    X, Y, fechas = datos["X"], datos["Y"], datos["fechas"]
    if len(X) <= DIAS_PRUEBA + 60:
        raise ValueError("Se necesitan al menos 90 días de historial para validar.")

    corte = len(X) - DIAS_PRUEBA
    X_ent, Y_ent, X_pru, Y_pru = X[:corte], Y[:corte], X[corte:], Y[corte:]

    # --- a) Holdout temporal: entrena con el pasado, evalúa con el último mes ---
    rf = _nuevo_rf().fit(X_ent, Y_ent)
    pred_rf = rf.predict(X_pru)
    met_rf = _metricas(Y_pru, pred_rf)

    # --- Alternativas con exactamente los mismos datos ---
    # Regresión lineal simple: día de la semana como número (0..6), como lo haría un análisis rápido.
    lin = LinearRegression().fit(X_ent, Y_ent)
    met_lin = _metricas(Y_pru, lin.predict(X_pru))
    # Regresión lineal "bien hecha": día de la semana en 7 columnas (one-hot).
    def one_hot(M):  # día y época en columnas separadas; el resto ya es 0/1
        return np.hstack([np.eye(7)[M[:, 0].astype(int)], M[:, 1:-1], np.eye(len(EPOCAS))[M[:, -1].astype(int)]])
    lin_oh = LinearRegression().fit(one_hot(X_ent), Y_ent)
    met_lin_oh = _metricas(Y_pru, lin_oh.predict(one_hot(X_pru)))
    met_prom = _metricas(Y_pru, _promedio_por_dia(X_ent, Y_ent, X_pru))

    # --- b) TimeSeriesSplit dentro del periodo de entrenamiento ---
    cortes, oof_real, oof_pred = [], [], []
    for i, (idx_e, idx_p) in enumerate(TimeSeriesSplit(n_splits=5).split(X_ent), start=1):
        pred_corte = _nuevo_rf().fit(X_ent[idx_e], Y_ent[idx_e]).predict(X_ent[idx_p])
        oof_real.append(Y_ent[idx_p]); oof_pred.append(pred_corte)
        m = _metricas(Y_ent[idx_p], pred_corte)
        cortes.append({"corte": i, "dias_entrenamiento": len(idx_e), "dias_prueba": len(idx_p),
                       "comensales_mae": round(float(m["mae"][0]), 2),
                       "comensales_r2": round(float(m["r2"][0]), 3),
                       "insumos_mae_relativo_pct": round(float(m["mae_relativo"][1:].mean() * 100), 1)})

    # --- c) Margen recomendado por insumo, calculado SOLO con el periodo de entrenamiento ---
    # Con las predicciones "fuera de muestra" de los cortes del TimeSeriesSplit medimos
    # cuánto se quedó corto el modelo. El percentil 90 de ese faltante es el margen que
    # habría cubierto 9 de cada 10 días. Se limita a [4 %, 25 %].
    oof_real = np.vstack(oof_real)[:, 1:]
    oof_pred = np.vstack(oof_pred)[:, 1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        exceso = np.where(oof_pred > 0, oof_real / oof_pred - 1, 0)
    margen_p90 = np.clip(np.quantile(exceso, 0.90, axis=0), MARGEN_MINIMO_SEGURO, MARGEN_MAXIMO)

    # --- d) Impacto de negocio en el mes de prueba (que nadie vio) ---
    insumos = datos["insumos"]
    precios = np.array([i["precio_unitario_mxn"] for i in insumos])
    real_ins, pred_ins = Y_pru[:, 1:], pred_rf[:, 1:]
    trad = datos["compra_tradicional"][corte:]

    def impacto(compra: np.ndarray) -> dict:
        sobrante = np.maximum(compra - real_ins, 0)
        faltante = np.maximum(real_ins - compra, 0)
        return {
            "compra_mxn": round(float((compra * precios).sum()), 0),
            "sobrante_mxn": round(float((sobrante * precios).sum()), 0),
            "demanda_no_cubierta_pct": round(float((faltante * precios).sum() / (real_ins * precios).sum() * 100), 2),
            "dias_insumo_con_faltante_pct": round(float((faltante > 1e-9).mean() * 100), 1),
        }

    detalle_insumos = []
    for j, ins in enumerate(insumos):
        detalle_insumos.append({
            "clave": ins["clave"], "nombre": ins["nombre"], "unidad": ins["unidad"],
            "consumo_promedio_dia": round(float(real_ins[:, j].mean()), 3),
            "mae": round(float(met_rf["mae"][j + 1]), 3),
            "mae_relativo_pct": round(float(met_rf["mae_relativo"][j + 1] * 100), 1),
            "r2": round(float(met_rf["r2"][j + 1]), 3),
            "margen_recomendado_p90": round(float(margen_p90[j]), 3),
        })

    return {
        "periodo_entrenamiento": {"desde": fechas[0], "hasta": fechas[corte - 1], "dias": corte},
        "periodo_prueba": {"desde": fechas[corte], "hasta": fechas[-1], "dias": DIAS_PRUEBA},
        "holdout": {
            "random_forest": _resumen("Random Forest", met_rf),
            "alternativas": [
                _resumen("Promedio por día de la semana", met_prom),
                _resumen("Regresión lineal simple (día como número)", met_lin),
                _resumen("Regresión lineal con día one-hot", met_lin_oh),
            ],
        },
        "time_series_split": cortes,
        "impacto_mes_prueba": {
            "compra_tradicional": impacto(trad),
            f"zeromerma_margen_fijo_{round(margen_referencia * 100)}pct": impacto(pred_ins * (1 + margen_referencia)),
            "zeromerma_margen_recomendado": impacto(pred_ins * (1 + margen_p90)),
            "nota": "Valuado a precios SIMULADOS. Sobrante = compra − consumo real (no todo se tira: "
                    "depende de la vida útil). Demanda no cubierta = valor del faltante / valor del consumo real.",
        },
        "detalle_insumos": detalle_insumos,
        "_margen_p90": {ins["clave"]: float(margen_p90[j]) for j, ins in enumerate(insumos)},
    }


# =============================================================================
# 3. ENTRENAMIENTO FINAL Y GUARDADO
# =============================================================================

def predicciones_historicas(datos: dict, margenes: np.ndarray) -> dict:
    """
    Compra que habría sugerido ZeroMerma AI para CADA día del historial, sin ver ese día:
    ventana creciente, se reentrena cada 30 días con todo lo anterior (primeros 60 días: sin dato).
    compra_sugerida = predicción × (1 + margen recomendado del insumo).
    """
    X, Y = datos["X"], datos["Y"]
    n = len(X)
    sugerida = np.full((n, Y.shape[1] - 1), np.nan)
    for inicio in range(MIN_DIAS_HISTORICO, n, PASO_HISTORICO):
        fin = min(inicio + PASO_HISTORICO, n)
        pred = _nuevo_rf().fit(X[:inicio], Y[:inicio]).predict(X[inicio:fin])[:, 1:]
        sugerida[inicio:fin] = np.maximum(pred, 0) * (1 + margenes)
    return {"fechas": datos["fechas"], "compra_sugerida": np.round(sugerida, 3),
            "primer_dia_comparable": datos["fechas"][MIN_DIAS_HISTORICO] if n > MIN_DIAS_HISTORICO else None,
            "nota": "Fuera de muestra: cada bloque de 30 días se predice con un modelo entrenado solo con días anteriores."}


def importancias_en_porcentaje(modelo: RandomForestRelativo) -> list[dict]:
    """feature_importances_ como porcentajes con 1 decimal que suman exactamente 100."""
    pct = modelo.feature_importances_ * 100
    redondeado = np.round(pct, 1)
    redondeado[np.argmax(redondeado)] += round(100 - redondeado.sum(), 1)  # ajusta el residuo del redondeo
    salida = [{"variable": v, "nombre": NOMBRES_VARIABLES[v], "porcentaje": round(float(p), 1)}
              for v, p in zip(VARIABLES, redondeado)]
    return sorted(salida, key=lambda d: d["porcentaje"], reverse=True)


def entrenar(ruta_db: Path = RUTA_DB, ruta_modelo: Path = RUTA_MODELO,
             ruta_metricas: Path | None = RUTA_METRICAS, verbose: bool = True) -> dict:
    datos = cargar_datos(ruta_db)
    validacion = validar(datos)

    # Una vez validado, el modelo que se usa en producción aprende de TODO el historial.
    modelo = _nuevo_rf().fit(datos["X"], datos["Y"])
    margenes = validacion["_margen_p90"]
    historico = predicciones_historicas(datos, np.array([margenes[i["clave"]] for i in datos["insumos"]]))

    # Compra tradicional típica por insumo y día de la semana (para comparar en la UI).
    trad_por_dia = {}
    for j, ins in enumerate(datos["insumos"]):
        trad_por_dia[ins["clave"]] = [
            round(float(datos["compra_tradicional"][datos["X"][:, 0] == d, j].mean()), 3) for d in range(7)]

    paquete = {
        "modelo": modelo,
        "variables": VARIABLES,
        "salidas": ["comensales"] + [i["clave"] for i in datos["insumos"]],
        "insumos": {i["clave"]: i for i in datos["insumos"]},
        "compra_tradicional_por_dia": trad_por_dia,
        "margen_recomendado_p90": validacion.pop("_margen_p90"),
        "historico": historico,
        "dataset_generado_en": datos["dataset_generado_en"],
        "importancias": importancias_en_porcentaje(modelo),
        "metricas": validacion,
        "hiperparametros": {k: v for k, v in HIPERPARAMETROS.items() if k != "n_jobs"},
        "entrenado_en": datetime.now().replace(microsecond=0).isoformat(),
        "dias_historial": len(datos["fechas"]),
        "origen_dato": datos["origen_dato"],
    }
    ruta_modelo.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(paquete, ruta_modelo, compress=3)

    reporte = {k: paquete[k] for k in ("entrenado_en", "dias_historial", "origen_dato",
                                         "hiperparametros", "importancias", "metricas")}
    if ruta_metricas:
        ruta_metricas.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
    if verbose:
        imprimir_reporte(reporte, ruta_modelo)
    return reporte


def imprimir_reporte(r: dict, ruta_modelo: Path) -> None:
    m = r["metricas"]
    print(f"\n=== Modelo de demanda · datos {r['origen_dato']} ===")
    print(f"Entrenamiento: {m['periodo_entrenamiento']['desde']} a {m['periodo_entrenamiento']['hasta']}"
          f" ({m['periodo_entrenamiento']['dias']} días)")
    print(f"Prueba:        {m['periodo_prueba']['desde']} a {m['periodo_prueba']['hasta']}"
          f" ({m['periodo_prueba']['dias']} días, nunca vistos)\n")
    print(f"{'Modelo':<44}{'Comensales MAE':>15}{'R²':>8}{'Insumos MAE %':>15}{'R² prom.':>10}")
    for fila in [m["holdout"]["random_forest"], *m["holdout"]["alternativas"]]:
        print(f"{fila['modelo']:<44}{fila['comensales_mae']:>15}{fila['comensales_r2']:>8}"
              f"{fila['insumos_mae_relativo_pct']:>15}{fila['insumos_r2_promedio']:>10}")
    print("\nTimeSeriesSplit (dentro del entrenamiento):")
    for c in m["time_series_split"]:
        print(f"  corte {c['corte']}: entrena {c['dias_entrenamiento']:>3} d, prueba {c['dias_prueba']} d"
              f" → comensales MAE {c['comensales_mae']}, R² {c['comensales_r2']}")
    print("\nImpacto en el mes de prueba (precios SIMULADOS):")
    print(f"  {'Estrategia':<34}{'Compra':>12}{'Sobrante':>12}{'No cubierto':>13}{'Días-insumo con faltante':>27}")
    for nombre, v in m["impacto_mes_prueba"].items():
        if nombre == "nota":
            continue
        print(f"  {nombre:<34}{v['compra_mxn']:>12,.0f}{v['sobrante_mxn']:>12,.0f}"
              f"{v['demanda_no_cubierta_pct']:>12}%{v['dias_insumo_con_faltante_pct']:>26}%")
    print("\nImportancia de variables:")
    for i in r["importancias"]:
        print(f"  {i['nombre']:<22}{i['porcentaje']:>6.1f} %")
    print(f"\nModelo guardado en {ruta_modelo}")


# =============================================================================
# 4. PREDICCIÓN Y REGLA DE NEGOCIO ANTI-DESABASTO
# =============================================================================

_CACHE: dict = {}


def cargar_modelo(ruta_modelo: Path = RUTA_MODELO) -> dict:
    """Carga el .pkl una sola vez por proceso (el backend lo llama en cada petición)."""
    clave = str(ruta_modelo)
    if clave not in _CACHE:
        if not ruta_modelo.exists():
            raise FileNotFoundError(f"No existe {ruta_modelo}. Corre: python ml/modelo_demanda.py entrenar")
        _CACHE[clave] = joblib.load(ruta_modelo)
    return _CACHE[clave]


def _resolver_insumo(paquete: dict, insumo: str) -> dict:
    """Acepta la clave ('pollo') o el nombre ('Pechuga de pollo'), sin distinguir mayúsculas."""
    buscado = insumo.strip().lower()
    for clave, info in paquete["insumos"].items():
        if buscado in (clave.lower(), info["nombre"].lower()):
            return info
    raise ValueError(f"Insumo desconocido: {insumo!r}. Opciones: {', '.join(paquete['insumos'])}")


def predecir_compra(insumo: str, dia_semana: int, es_quincena: bool, lluvia: bool, evento: bool,
                    margen_seguridad: float, evento_plaza: bool = False, es_dia_festivo: bool = False,
                    epoca: str = "regular", ruta_modelo: Path = RUTA_MODELO) -> dict:
    """
    Predice cuánto comprar de un insumo para un día.

    Parámetros
    ----------
    insumo:               clave ('pollo') o nombre ('Pechuga de pollo')
    dia_semana:           0 = lunes ... 6 = domingo
    es_quincena, lluvia, evento (cercano), evento_plaza, es_dia_festivo: contexto del día
    epoca:                "regular", "navidena", "cuesta_enero" o "verano"
    margen_seguridad:     fracción entre 0 y 0.25 (0.08 = 8 %)

    Regla de negocio
    ----------------
    compra_sugerida  = demanda_base × (1 + margen_seguridad)
    riesgo_desabasto = margen_seguridad < 0.04
    """
    if not 0 <= int(dia_semana) <= 6:
        raise ValueError("dia_semana debe estar entre 0 (lunes) y 6 (domingo)")
    if not 0 <= margen_seguridad <= MARGEN_MAXIMO:
        raise ValueError(f"margen_seguridad debe estar entre 0 y {MARGEN_MAXIMO}")

    if epoca not in EPOCAS:
        raise ValueError(f"epoca debe ser una de {EPOCAS}")

    paquete = cargar_modelo(ruta_modelo)
    info = _resolver_insumo(paquete, insumo)
    clave = info["clave"]

    fila = np.array([[int(dia_semana), int(bool(es_quincena)), int(bool(lluvia)), int(bool(evento)),
                      int(bool(evento_plaza)), int(bool(es_dia_festivo)), EPOCAS.index(epoca)]], dtype=float)
    prediccion = paquete["modelo"].predict(fila)[0]
    comensales = max(0, round(float(prediccion[0])))
    demanda_base = max(0.0, float(prediccion[paquete["salidas"].index(clave)]))

    compra_sugerida = demanda_base * (1 + margen_seguridad)
    riesgo_desabasto = margen_seguridad < MARGEN_MINIMO_SEGURO
    precio = info["precio_unitario_mxn"]
    tradicional = paquete["compra_tradicional_por_dia"][clave][int(dia_semana)]
    diferencia = tradicional - compra_sugerida

    return {
        "insumo": {"clave": clave, "nombre": info["nombre"], "unidad": info["unidad"]},
        "comensales_estimados": comensales,
        "demanda_base": round(demanda_base, 2),
        "margen_seguridad": margen_seguridad,
        "compra_sugerida": round(compra_sugerida, 2),
        "inversion_mxn": round(compra_sugerida * precio, 2),
        "compra_tradicional_referencia": round(tradicional, 2),
        "diferencia_vs_tradicional": {"cantidad": round(diferencia, 2), "mxn": round(diferencia * precio, 2)},
        "riesgo_desabasto": riesgo_desabasto,
        "mensaje_riesgo": ("Riesgo alto de desabasto: con un margen menor a 4 % la compra puede quedarse "
                           "corta en hora pico." if riesgo_desabasto else None),
        "margen_recomendado": round(paquete["margen_recomendado_p90"][clave], 3),
        "importancia_variables": paquete["importancias"],
        "origen_dato": paquete["origen_dato"],
    }


# =============================================================================
# 5. BACKTESTING ("máquina del tiempo") PARA LA VISTA DE AUDITORÍA
# =============================================================================

def backtest(ultimos_dias: int = 7, margen: float | None = None, ruta_db: Path = RUTA_DB,
             ruta_modelo: Path = RUTA_MODELO) -> dict:
    """
    ¿Qué habría pasado en los últimos `ultimos_dias` días cerrados si se hubiera comprado
    con ZeroMerma AI?

    Para no hacer trampa, entrena un modelo NUEVO solo con los días anteriores a ese
    periodo (el modelo guardado ya los vio). Cada día se compra
    predicción × (1 + margen); si `margen` es None se usa el margen recomendado de
    cada insumo guardado en el modelo.

    Devuelve arreglos por día × insumo con la compra tradicional, el consumo real y la
    compra sugerida, más los datos de cada insumo.
    """
    datos = cargar_datos(ruta_db)
    n = len(datos["X"])
    if not 1 <= ultimos_dias <= n - 60:
        raise ValueError(f"ultimos_dias debe estar entre 1 y {n - 60}")
    corte = n - ultimos_dias

    modelo = _nuevo_rf().fit(datos["X"][:corte], datos["Y"][:corte])
    prediccion = np.maximum(modelo.predict(datos["X"][corte:])[:, 1:], 0)

    claves = [i["clave"] for i in datos["insumos"]]
    if margen is None:
        recomendado = cargar_modelo(ruta_modelo)["margen_recomendado_p90"]
        margenes = np.array([recomendado.get(c, 0.08) for c in claves])
    else:
        if not 0 <= margen <= MARGEN_MAXIMO:
            raise ValueError(f"margen debe estar entre 0 y {MARGEN_MAXIMO}")
        margenes = np.full(len(claves), margen)

    return {
        "fechas": datos["fechas"][corte:],
        "insumos": datos["insumos"],
        "compra_tradicional": datos["compra_tradicional"][corte:],
        "consumo_real": datos["Y"][corte:, 1:],
        "compra_sugerida": prediccion * (1 + margenes),
        "margenes": margenes,
        "entrenado_hasta": datos["fechas"][corte - 1],
        "origen_dato": datos["origen_dato"],
    }


# =============================================================================
# 6. LÍNEA DE COMANDOS
# =============================================================================

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Modelo de demanda de ZeroMerma AI (datos SIMULADOS).")
    sub = p.add_subparsers(dest="comando", required=True)

    e = sub.add_parser("entrenar", help="Valida, entrena y guarda ml/modelo_rf.pkl")
    e.add_argument("--db", type=Path, default=RUTA_DB)
    e.add_argument("--modelo", type=Path, default=RUTA_MODELO, help="Dónde guardar el .pkl")

    pr = sub.add_parser("predecir", help="Calcula la compra sugerida de un insumo")
    pr.add_argument("--insumo", required=True)
    pr.add_argument("--dia", type=int, required=True, help="0 = lunes ... 6 = domingo")
    pr.add_argument("--quincena", action="store_true")
    pr.add_argument("--lluvia", action="store_true")
    pr.add_argument("--evento", action="store_true")
    pr.add_argument("--plaza", action="store_true", help="Evento en la plaza")
    pr.add_argument("--festivo", action="store_true", help="Día festivo")
    pr.add_argument("--epoca", default="regular", choices=EPOCAS)
    pr.add_argument("--margen", type=float, default=0.08)

    sub.add_parser("importancias", help="Muestra la importancia de variables del modelo guardado")

    args = p.parse_args(argv)
    try:
        if args.comando == "entrenar":
            entrenar(args.db, args.modelo)
        elif args.comando == "predecir":
            r = predecir_compra(args.insumo, args.dia, args.quincena, args.lluvia, args.evento,
                                args.margen, args.plaza, args.festivo, args.epoca)
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(cargar_modelo()["importancias"], ensure_ascii=False, indent=2))
    except (FileNotFoundError, ValueError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    # Se ejecuta desde el módulo `ml.modelo_demanda` (no como `__main__`) para que el modelo
    # guardado referencie `ml.modelo_demanda.RandomForestRelativo` y el backend pueda leerlo.
    sys.path.insert(0, str(RAIZ))
    from ml import modelo_demanda as _modulo
    sys.exit(_modulo.main())
