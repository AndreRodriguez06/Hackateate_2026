"""
ZeroMerma AI — Rescate rentable en menú
Archivo: /backend/services/rescate_menu.py

Cruza los insumos a punto de caducar con el recetario y propone promociones
SOLO sobre platillos que ya existen en el menú.

Dos modos:
  * "gemini":   backend/gemini_service.py (Apartado 6) elige
                platillos, descuentos y redacta el texto. El backend NO confía en sus
                cuentas: valida cada propuesta y recalcula todas las cifras aquí.
  * "fallback": reglas deterministas de este archivo. Se usa si Gemini no está
                integrado, no hay llave, falla la cuota o la respuesta no pasa la validación.

Supuestos de negocio (SIMULADOS, documentados en docs/04_backend_api.md):
  * El precio de oferta debe ser al menos 1.5 × el costo de insumos de la porción.
  * Elasticidad: cada 10 puntos de descuento suben las ventas del platillo 20 %.
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime

from backend import database as db
from backend import gemini_service

DESCUENTOS_POSIBLES = (30, 25, 20, 15, 10)   # en %, de mayor a menor
FACTOR_COSTO_MINIMO = 1.5                    # precio_oferta >= 1.5 × costo por porción
ELASTICIDAD = 2.0                            # +20 % de ventas por cada 10 % de descuento


# -----------------------------------------------------------------------------
# Cálculo financiero común a ambos modos
# -----------------------------------------------------------------------------

def calcular_estrategia(platillo: dict, descuento_pct: float, porciones: int,
                        disponibles: dict[str, float], insumos: dict[str, dict]) -> dict:
    """
    Cifras de una promoción. `disponibles` = cantidad de cada insumo crítico que aún falta rescatar.

    perdida_si_se_tira_mxn: valor de los insumos críticos que esta promoción consume
                            (lo que se perdería si se tiraran).
    margen_recuperado_mxn:  porciones × (precio de oferta − costo de insumos por porción).
    """
    precio_oferta = round(platillo["precio_venta_mxn"] * (1 - descuento_pct / 100))
    rescatados = []
    for clave, por_porcion in platillo["receta"].items():
        if disponibles.get(clave, 0) > 0:
            cantidad = min(por_porcion * porciones, disponibles[clave])
            rescatados.append({
                "clave": clave,
                "nombre": insumos[clave]["nombre"],
                "cantidad": round(cantidad, 3),
                "unidad": insumos[clave]["unidad"],
                "valor_mxn": round(cantidad * insumos[clave]["precio_unitario_mxn"], 2),
            })
    return {
        "platillo_clave": platillo["clave"],
        "platillo": platillo["nombre"],
        "categoria": platillo["categoria"],
        "descuento_pct": descuento_pct,
        "precio_normal_mxn": platillo["precio_venta_mxn"],
        "precio_oferta_mxn": precio_oferta,
        "costo_insumos_porcion_mxn": platillo["costo_porcion_mxn"],
        "porciones_objetivo": porciones,
        "insumos_rescatados": rescatados,
        "perdida_si_se_tira_mxn": round(sum(r["valor_mxn"] for r in rescatados), 2),
        "margen_recuperado_mxn": round(porciones * (precio_oferta - platillo["costo_porcion_mxn"]), 2),
    }


def descuento_rentable(platillo: dict) -> int | None:
    """Mayor descuento de la lista que mantiene el precio >= 1.5 × costo. None si ninguno."""
    for d in DESCUENTOS_POSIBLES:
        if platillo["precio_venta_mxn"] * (1 - d / 100) >= FACTOR_COSTO_MINIMO * platillo["costo_porcion_mxn"]:
            return d
    return None


def porciones_con_promocion(ventas_dia: float, descuento_pct: float) -> int:
    return max(1, math.ceil(ventas_dia * (1 + ELASTICIDAD * descuento_pct / 100)))


def copy_por_plantilla(est: dict) -> str:
    ahorro = est["precio_normal_mxn"] - est["precio_oferta_mxn"]
    return (f"¡Solo hoy! {est['platillo']} a ${est['precio_oferta_mxn']:.0f} "
            f"(antes ${est['precio_normal_mxn']:.0f}, ahorras ${ahorro:.0f}). "
            f"Preparado al momento con ingredientes del día. Disponible hasta agotar existencias.")


# -----------------------------------------------------------------------------
# Modo fallback: reglas deterministas
# -----------------------------------------------------------------------------

def estrategias_por_reglas(platillos: dict, criticos: dict[str, float], insumos: dict,
                           ventas: dict[str, float], maximo: int) -> list[dict]:
    """
    Algoritmo voraz: en cada vuelta elige el platillo que rescata más valor de insumos
    críticos todavía disponibles, aplica su descuento rentable y descuenta lo rescatado.
    """
    disponibles = dict(criticos)
    elegidas = []
    for _ in range(maximo):
        mejor = None
        for p in platillos.values():
            if p["clave"] in {e["platillo_clave"] for e in elegidas}:
                continue
            if not any(disponibles.get(k, 0) > 0 for k in p["receta"]):
                continue
            d = descuento_rentable(p)
            if d is None:
                continue
            est = calcular_estrategia(p, d, porciones_con_promocion(ventas.get(p["clave"], 1.0), d),
                                      disponibles, insumos)
            if mejor is None or est["perdida_si_se_tira_mxn"] > mejor["perdida_si_se_tira_mxn"]:
                mejor = est
        if mejor is None or mejor["perdida_si_se_tira_mxn"] <= 0:
            break
        mejor["tipo"] = "descuento"
        mejor["copy_promocional"] = copy_por_plantilla(mejor)
        elegidas.append(mejor)
        for r in mejor["insumos_rescatados"]:
            disponibles[r["clave"]] = max(0.0, disponibles[r["clave"]] - r["cantidad"])
    return elegidas


# -----------------------------------------------------------------------------
# Modo gemini: validación de la propuesta
# -----------------------------------------------------------------------------

def validar_propuestas(propuestas: list[dict], platillos: dict, criticos: dict, insumos: dict,
                       ventas: dict, maximo: int) -> list[dict]:
    """
    Acepta una propuesta solo si:
      1. el platillo existe en el menú vigente,
      2. usa al menos un insumo crítico,
      3. el descuento está entre 0 y 50 % y deja el precio >= 1.5 × costo.
    Las cifras se recalculan aquí; de Gemini solo se toman platillo, descuento, tipo y texto.
    """
    disponibles = dict(criticos)
    validas = []
    for prop in propuestas[:maximo]:
        p = platillos.get(str(prop.get("platillo_clave", "")))
        if p is None:
            raise ValueError(f"Gemini propuso un platillo que no está en el menú: {prop.get('platillo_clave')!r}")
        if not any(disponibles.get(k, 0) > 0 for k in p["receta"]):
            raise ValueError(f"{p['nombre']} no usa insumos críticos pendientes")
        d = float(prop.get("descuento_pct", 0))
        if not 0 <= d <= 50:
            raise ValueError(f"Descuento fuera de rango para {p['nombre']}: {d}")
        if p["precio_venta_mxn"] * (1 - d / 100) < FACTOR_COSTO_MINIMO * p["costo_porcion_mxn"]:
            raise ValueError(f"El descuento de {d}% en {p['nombre']} deja el precio por debajo del mínimo rentable")
        est = calcular_estrategia(p, d, porciones_con_promocion(ventas.get(p["clave"], 1.0), d), disponibles, insumos)
        est["tipo"] = str(prop.get("tipo") or "descuento")
        est["copy_promocional"] = str(prop.get("copy_promocional") or copy_por_plantilla(est))[:400]
        est["justificacion"] = str(prop.get("justificacion") or "")[:300]
        validas.append(est)
        for r in est["insumos_rescatados"]:
            disponibles[r["clave"]] = max(0.0, disponibles[r["clave"]] - r["cantidad"])
    if not validas:
        raise ValueError("Gemini no devolvió propuestas válidas")
    return validas


# -----------------------------------------------------------------------------
# Punto de entrada del endpoint
# -----------------------------------------------------------------------------

def optimizar_menu(con: sqlite3.Connection, ahora: datetime, horas_umbral: float = 24,
                   max_estrategias: int = 3, usar_gemini: bool = True) -> dict:
    lotes = db.listar_lotes(con, ahora)
    # Nunca se promociona comida caducada: solo lotes vigentes dentro del umbral.
    criticos: dict[str, float] = {}
    horas_min: dict[str, float] = {}
    for lote in lotes:
        if not lote["caducado"] and lote["horas_restantes"] <= horas_umbral:
            criticos[lote["clave"]] = criticos.get(lote["clave"], 0.0) + lote["cantidad"]
            horas_min[lote["clave"]] = min(horas_min.get(lote["clave"], 1e9), lote["horas_restantes"])

    insumos = db.insumos_por_clave(con)
    resumen_criticos = [{"clave": k, "nombre": insumos[k]["nombre"], "cantidad": round(v, 3),
                         "unidad": insumos[k]["unidad"], "costo_unitario_mxn": insumos[k]["precio_unitario_mxn"],
                         "horas_restantes": horas_min[k],
                         "valor_mxn": round(v * insumos[k]["precio_unitario_mxn"], 2)}
                        for k, v in criticos.items()]
    respuesta = {"modo": "fallback", "motivo_fallback": None, "modelo": None, "insumos_criticos": resumen_criticos,
                 "estrategias": [], "origen_dato": db.origen_dataset(con)}
    if not criticos:
        respuesta["motivo_fallback"] = f"No hay insumos vigentes a menos de {horas_umbral:g} h de caducar."
        return respuesta

    platillos = db.platillos_con_recetas(con)
    ventas = db.ventas_promedio(con, dia_semana=ahora.weekday())

    estrategias, motivo = None, None
    resultado = gemini_service.generar_promociones_menu(
        resumen_criticos,
        [{k: p[k] for k in ("clave", "nombre", "categoria", "precio_venta_mxn", "costo_porcion_mxn", "receta")}
         for p in platillos.values()],
        max_estrategias, usar_gemini=usar_gemini)
    if resultado["modo_respaldo"] or not resultado["promociones"]:
        motivo = resultado["motivo_respaldo"] or "Gemini no propuso promociones."
    else:
        try:
            # Segunda validación, ahora con existencias y ventas: las cifras se recalculan aquí.
            estrategias = validar_propuestas(resultado["promociones"], platillos, criticos, insumos, ventas,
                                             max_estrategias)
            respuesta["modo"] = "gemini"
            respuesta["modelo"] = resultado["modelo"]
        except ValueError as err:
            motivo = f"La propuesta de Gemini no pasó la validación del backend: {err}"

    if estrategias is None:
        estrategias = estrategias_por_reglas(platillos, criticos, insumos, ventas, max_estrategias)
        respuesta["motivo_fallback"] = motivo

    respuesta["estrategias"] = estrategias
    _registrar(con, ahora, respuesta["modo"], estrategias, platillos)
    return respuesta


def _registrar(con: sqlite3.Connection, ahora: datetime, modo: str, estrategias: list[dict], platillos: dict) -> None:
    """Bitácora en la tabla promociones_generadas (etiquetada SIMULADO)."""
    for e in estrategias:
        con.execute(
            "INSERT INTO promociones_generadas (creado_en, modo, platillo_id, descuento_pct, precio_oferta_mxn,"
            " copy_promocional, respuesta_json, origen_dato) VALUES (?,?,?,?,?,?,?, 'SIMULADO')",
            (ahora.replace(microsecond=0).isoformat(), modo, platillos[e["platillo_clave"]]["id"],
             e["descuento_pct"], e["precio_oferta_mxn"], e["copy_promocional"],
             json.dumps(e, ensure_ascii=False)))
    con.commit()
