"""
OpsIA — Historial de compras (vista 5)
Archivo: /backend/services/historial_compras.py

Muestra, para todo el historial guardado en la base de datos:
  * lo que se compró cada día con el método tradicional ("a ojo"),
  * lo que realmente se consumió,
  * lo que habría sugerido OpsIA, predicho SIN ver ese día
    (modelo con ventana creciente, ver ml/modelo_demanda.py: predicciones_historicas),
agrupado por día, semana o mes, para un insumo o para todos (en $MXN, porque kg, L y
piezas no se pueden sumar entre sí).

Todos los datos son SIMULADOS.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import numpy as np

from backend import database as db
from data import generar_datos

AGRUPACIONES = ("dia", "semana", "mes")
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _clave_periodo(fecha: str, agrupar: str) -> tuple[str, str]:
    """(clave ordenable, etiqueta legible) del periodo al que pertenece la fecha."""
    d = date.fromisoformat(fecha)
    if agrupar == "dia":
        return fecha, f"{d.day} {MESES[d.month - 1]} {d.year}"
    if agrupar == "semana":
        lunes = d - timedelta(days=d.weekday())
        return lunes.isoformat(), f"Sem. {lunes.day} {MESES[lunes.month - 1]} {lunes.year}"
    return f"{d.year}-{d.month:02d}", f"{MESES[d.month - 1].capitalize()} {d.year}"


def construir(con: sqlite3.Connection, paquete: dict, agrupar: str = "semana", insumo: str = "todos") -> dict:
    if agrupar not in AGRUPACIONES:
        raise ValueError(f"agrupar debe ser uno de {AGRUPACIONES}")
    historico = paquete.get("historico")
    if not historico:
        raise LookupError("El modelo guardado no tiene historial fuera de muestra. Reentrénalo.")

    insumos = [dict(f) for f in con.execute(
        "SELECT id, clave, nombre, unidad, precio_unitario_mxn, vida_util_dias FROM insumos ORDER BY id")]
    claves = [i["clave"] for i in insumos]
    if insumo != "todos" and insumo not in claves:
        raise KeyError(insumo)
    if paquete["salidas"][1:] != claves:
        raise LookupError("El modelo no corresponde a la base de datos actual. Reentrénalo.")

    fechas = [f[0] for f in con.execute("SELECT fecha FROM contexto_diario ORDER BY fecha")]
    if fechas != list(historico["fechas"]):
        raise LookupError("El historial del modelo no coincide con las fechas de la base. Reentrénalo.")
    idx_fecha = {f: k for k, f in enumerate(fechas)}
    idx_insumo = {i["id"]: k for k, i in enumerate(insumos)}

    n, m = len(fechas), len(insumos)
    trad, real = np.zeros((n, m)), np.zeros((n, m))
    for f in con.execute("SELECT fecha, insumo_id, compra_tradicional, consumo_real FROM consumo_insumos_diario"):
        k, j = idx_fecha[f["fecha"]], idx_insumo[f["insumo_id"]]
        trad[k, j], real[k, j] = f["compra_tradicional"], f["consumo_real"]
    zm = np.asarray(historico["compra_sugerida"], dtype=float)
    comparable = ~np.isnan(zm).any(axis=1)                      # días con predicción fuera de muestra

    precios = np.array([i["precio_unitario_mxn"] for i in insumos])
    factores = np.array([generar_datos.factor_caducidad(i["vida_util_dias"]) for i in insumos])
    es_kg = np.array([i["unidad"] == "kg" for i in insumos])
    zm0 = np.nan_to_num(zm)
    merma_trad = np.maximum(trad - real, 0) * factores
    merma_zm = np.maximum(zm0 - real, 0) * factores
    faltante_trad = np.maximum(real - trad, 0)
    faltante_zm = np.maximum(real - zm0, 0)

    if insumo == "todos":
        col = slice(None)
        unidad, info = "MXN", {"clave": "todos", "nombre": "Todos los productos", "unidad": "MXN"}
        en_unidad = lambda M: (M * precios).sum(axis=1)          # noqa: E731  (todo en pesos)
    else:
        j = claves.index(insumo)
        col = slice(j, j + 1)
        unidad, info = insumos[j]["unidad"], {k: insumos[j][k] for k in ("clave", "nombre", "unidad")}
        en_unidad = lambda M: M[:, col].sum(axis=1)               # noqa: E731
    en_mxn = lambda M: (M[:, col] * precios[col]).sum(axis=1)    # noqa: E731

    diario = {
        "compra_tradicional": en_unidad(trad), "consumo_real": en_unidad(real), "compra_sugerida": en_unidad(zm0),
        "compra_tradicional_mxn": en_mxn(trad), "compra_sugerida_mxn": en_mxn(zm0),
        "merma_tradicional_mxn": en_mxn(merma_trad), "merma_opsia_mxn": en_mxn(merma_zm),
    }

    # --- Agrupación por periodo ---
    grupos: dict[str, dict] = {}
    for k, f in enumerate(fechas):
        clave, etiqueta = _clave_periodo(f, agrupar)
        g = grupos.setdefault(clave, {"periodo": clave, "etiqueta": etiqueta, "desde": f, "hasta": f,
                                      "dias": 0, "dias_comparables": 0, "_idx": []})
        g["hasta"] = f
        g["dias"] += 1
        g["dias_comparables"] += int(comparable[k])
        g["_idx"].append(k)

    serie = []
    for g in grupos.values():
        idx = g.pop("_idx")
        completo = g["dias_comparables"] == g["dias"]           # solo se compara un periodo con predicción todos sus días
        fila = {**g}
        for nombre in ("compra_tradicional", "consumo_real", "compra_tradicional_mxn", "merma_tradicional_mxn"):
            fila[nombre] = round(float(diario[nombre][idx].sum()), 2)
        for nombre in ("compra_sugerida", "compra_sugerida_mxn", "merma_opsia_mxn"):
            fila[nombre] = round(float(diario[nombre][idx].sum()), 2) if completo else None
        fila["ahorro_compra_mxn"] = (round(fila["compra_tradicional_mxn"] - fila["compra_sugerida_mxn"], 2)
                                     if completo else None)
        fila["merma_evitada_mxn"] = (round(fila["merma_tradicional_mxn"] - fila["merma_opsia_mxn"], 2)
                                     if completo else None)
        serie.append(fila)

    # --- Totales solo sobre los días comparables ---
    c = comparable
    valor_real = (real[c][:, col] * precios[col]).sum()
    kg_col = es_kg[col]
    totales = {
        "dias_comparables": int(c.sum()),
        "compra_tradicional_mxn": round(float((trad[c][:, col] * precios[col]).sum()), 2),
        "compra_sugerida_mxn": round(float((zm0[c][:, col] * precios[col]).sum()), 2),
        "merma_tradicional_mxn": round(float((merma_trad[c][:, col] * precios[col]).sum()), 2),
        "merma_opsia_mxn": round(float((merma_zm[c][:, col] * precios[col]).sum()), 2),
        "merma_evitada_kg": round(float((merma_trad[c][:, col] - merma_zm[c][:, col])[:, kg_col].sum()), 2),
        "demanda_no_cubierta_tradicional_pct": round(float((faltante_trad[c][:, col] * precios[col]).sum() / valor_real * 100), 2) if valor_real else 0.0,
        "demanda_no_cubierta_opsia_pct": round(float((faltante_zm[c][:, col] * precios[col]).sum() / valor_real * 100), 2) if valor_real else 0.0,
    }
    totales["ahorro_compra_mxn"] = round(totales["compra_tradicional_mxn"] - totales["compra_sugerida_mxn"], 2)
    totales["merma_evitada_mxn"] = round(totales["merma_tradicional_mxn"] - totales["merma_opsia_mxn"], 2)
    totales["reduccion_merma_pct"] = (round((totales["merma_opsia_mxn"] / totales["merma_tradicional_mxn"] - 1) * 100, 1)
                                      if totales["merma_tradicional_mxn"] else 0.0)

    primer = historico.get("primer_dia_comparable")
    return {
        "insumo": info,
        "agrupar": agrupar,
        "unidad": unidad,
        "periodo": {"desde": fechas[0], "hasta": fechas[-1], "dias": n,
                    "primer_dia_comparable": primer, "dias_sin_prediccion": int((~comparable).sum())},
        "serie": serie,
        "totales": totales,
        "metodologia": ("Compra tradicional y consumo real: registros diarios de la base (SIMULADOS). "
                        "Compra sugerida: predicción fuera de muestra (cada bloque de 30 días se predice con un "
                        "modelo entrenado solo con los días anteriores) × (1 + margen recomendado del insumo). "
                        f"Los primeros {int((~comparable).sum())} días no tienen predicción porque el modelo necesita "
                        "historial para entrenar. Merma = sobrante × fracción que caduca según la vida útil."),
        "origen_dato": db.origen_dataset(con),
    }
