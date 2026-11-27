"""
OpsIA — Alerta temprana de excedentes
Archivo: /backend/services/alerta_excedente.py

A media jornada proyecta cuántas porciones de un platillo sobrarán al cierre y,
si el sobrante es suficiente, arma una ficha de recolección para un comedor
comunitario o la red del campus.

Supuestos (SIMULADOS, documentados en docs/04_backend_api.md):
  * Horario: abre 09:00, cierra 20:00.
  * Curva de ventas acumuladas: fracción vendida = ((h − apertura) / horas de servicio) ^ 0.8
    (se vende un poco más rápido al inicio que al final).
  * La cocina prepara 10 % más que la venta promedio del mismo día de la semana.
  * Ritmo: lento = 70 % de lo normal (−30 %), normal = 100 %, rápido = 115 %.
  * Ventana de recolección: empieza 1 h después del aviso y termina al menos 2 h antes
    del cierre (18:00), para que el comedor alcance a distribuir la comida el mismo día.

La ficha (texto, recomendaciones de inocuidad) la redacta Gemini a través de
backend/gemini_service.py; si no está disponible, ese módulo devuelve un respaldo.
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime

from backend import database as db
from backend import gemini_service

APERTURA = 9.0
CIERRE = 20.0
EXPONENTE_CURVA = 0.8
COLCHON_PREPARACION = 1.10
RITMOS = {"lento": 0.70, "normal": 1.00, "rapido": 1.15}
SOBRANTE_MINIMO = 3            # porciones; por debajo se aprovecha en comida del personal
HORAS_ANTICIPACION = 1.0       # la recolección empieza 1 h después del aviso
HORAS_LIMITE_ANTES_CIERRE = gemini_service.HORAS_MINIMAS_ANTES_CIERRE   # 2 h
VENTANA_MINIMA = 0.5           # una ventana de menos de 30 min no es operable
CATEGORIAS_REFRIGERAR = {"proteína", "lácteo"}
# Una fecha o una foto no certifican que un alimento sea apto (Guía del Reto, inocuidad).
AVISO_RESPONSABILIDAD = ("Una fecha de caducidad o una fotografía no certifican que el alimento sea apto. "
                         "La donación se hace solo con un acuerdo previo con el receptor, que revisa "
                         "temperatura, olor y aspecto al recibirlo. Ante cualquier duda, no se dona.")


def hora_a_decimal(texto: str) -> float:
    """'15:30' -> 15.5. Lanza ValueError si el formato no es HH:MM."""
    horas, minutos = texto.strip().split(":")
    h, m = int(horas), int(minutos)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Hora inválida: {texto!r}")
    return h + m / 60


def decimal_a_hora(h: float) -> str:
    total = round(h * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def fraccion_vendida(h: float) -> float:
    avance = min(max((h - APERTURA) / (CIERRE - APERTURA), 0.0), 1.0)
    return avance ** EXPONENTE_CURVA


def _redondear_arriba_15(h: float) -> float:
    return math.ceil(h * 4 - 1e-9) / 4


def ventana_recoleccion(h: float, cierre: float = CIERRE) -> tuple[float, float] | None:
    """
    Ventana para recoger: empieza 1 h después del aviso (o en 15 min si ya es tarde) y
    termina al menos 2 h antes del cierre. None si ya no cabe una ventana de 30 min.
    """
    limite = cierre - HORAS_LIMITE_ANTES_CIERRE
    for anticipacion in (HORAS_ANTICIPACION, 0.25):
        inicio = _redondear_arriba_15(h + anticipacion)
        if limite - inicio >= VENTANA_MINIMA - 1e-9:
            return inicio, limite
    return None


def requiere_refrigeracion(platillo: dict, insumos: dict) -> bool:
    return bool({insumos[k]["categoria"] for k in platillo["receta"]} & CATEGORIAS_REFRIGERAR)


def evaluar(con: sqlite3.Connection, ahora: datetime, platillo_clave: str, hora_actual: str,
            ritmo: str = "normal", porciones_preparadas: int | None = None,
            porciones_vendidas: int | None = None, usar_gemini: bool = True,
            generar_ficha: bool = True) -> dict:
    """
    Proyección de cierre y, si aplica, ficha de rescate temprano.
    Con generar_ficha=False solo proyecta (no llama a Gemini ni escribe en la bitácora);
    el frontend lo usa mientras el usuario mueve el slider de hora.
    """
    h = hora_a_decimal(hora_actual)
    if not APERTURA <= h < CIERRE:
        raise ValueError(f"La hora debe estar dentro del servicio ({decimal_a_hora(APERTURA)} a "
                         f"{decimal_a_hora(CIERRE)}).")
    platillos = db.platillos_con_recetas(con)
    if platillo_clave not in platillos:
        raise KeyError(platillo_clave)
    platillo = platillos[platillo_clave]
    insumos = db.insumos_por_clave(con)

    esperado = db.ventas_promedio(con, dia_semana=ahora.weekday()).get(platillo_clave, 0.0)
    preparadas = porciones_preparadas if porciones_preparadas is not None else math.ceil(esperado * COLCHON_PREPARACION)
    f = fraccion_vendida(h)

    if porciones_vendidas is not None:
        # Ritmo real observado: lo vendido contra lo que se esperaba vender a esta hora.
        factor = porciones_vendidas / max(esperado * f, 1e-9)
        vendidas = porciones_vendidas
        ritmo_usado = "medido"
    else:
        if ritmo not in RITMOS:
            raise ValueError(f"ritmo debe ser uno de {list(RITMOS)}")
        factor = RITMOS[ritmo]
        vendidas = round(esperado * factor * f)
        ritmo_usado = ritmo

    proyeccion_cierre = max(vendidas, round(esperado * factor))
    sobrante = max(0, preparadas - proyeccion_cierre)
    agotamiento = None
    if proyeccion_cierre > preparadas and esperado * factor > 0:
        # Hora en que la venta acumulada alcanzaría lo preparado.
        avance = (preparadas / (esperado * factor)) ** (1 / EXPONENTE_CURVA)
        agotamiento = decimal_a_hora(APERTURA + avance * (CIERRE - APERTURA))

    respuesta = {
        "modo": "fallback",
        "motivo_fallback": None,
        "platillo": {"clave": platillo_clave, "nombre": platillo["nombre"]},
        "hora_actual": decimal_a_hora(h),
        "ritmo": ritmo_usado,
        "factor_ritmo": round(factor, 2),
        "confianza": "baja" if f < 0.35 else "media" if f < 0.6 else "alta",
        "proyeccion": {
            "porciones_preparadas": preparadas,
            "vendidas_hasta_ahora": vendidas,
            "ventas_esperadas_al_cierre": proyeccion_cierre,
            "porciones_sobrantes": sobrante,
            "hora_agotamiento_estimada": agotamiento,
        },
        "alerta_activa": sobrante >= SOBRANTE_MINIMO,
        "ventana_viable": ventana_recoleccion(h) is not None,
        "ficha": None,
        "motivo_sin_ficha": None,
        "origen_dato": db.origen_dataset(con),
    }
    if not respuesta["alerta_activa"] or not generar_ficha:
        return respuesta

    resultado = gemini_service.generar_alerta_recoleccion(
        {"producto": platillo["nombre"], "porciones": sobrante,
         "cantidad_aprox_kg": round(sobrante * platillo["peso_porcion_kg"], 1),
         "requiere_refrigeracion": requiere_refrigeracion(platillo, insumos),
         "punto_entrega": "Cafetería La Esquina (andén de servicio)"},
        decimal_a_hora(h), decimal_a_hora(CIERRE), usar_gemini=usar_gemini)
    respuesta["modo"] = "fallback" if resultado["modo_respaldo"] else "gemini"
    respuesta["motivo_fallback"] = resultado["motivo_respaldo"]
    if resultado["ficha"] is None:
        respuesta["motivo_sin_ficha"] = resultado["motivo_sin_ficha"]
        return respuesta

    f = resultado["ficha"]
    ficha = {
        "alimento": f"{f['porciones']} porciones de {f['producto']}",
        "platillo": f["producto"],
        "porciones": f["porciones"],
        "cantidad_aprox_kg": f["cantidad_aprox_kg"],
        "ventana_recoleccion": {"inicio": f["ventana_inicio"], "fin": f["ventana_limite"],
                                "horas_antes_del_cierre": f["horas_antes_del_cierre"]},
        "recomendaciones_inocuidad": f["recomendaciones_inocuidad"],
        "nota_inocuidad": " ".join(f["recomendaciones_inocuidad"]),
        "aviso_responsabilidad": AVISO_RESPONSABILIDAD,
        "destinatario_sugerido": "Comedor comunitario / Red Campus",
        "mensaje": f["mensaje"],
    }
    respuesta["ficha"] = ficha

    cur = con.execute(
        "INSERT INTO alertas_excedente (creado_en, modo, platillo_id, porciones_excedentes, ventana_inicio,"
        " ventana_fin, ficha_json, enviada, origen_dato) VALUES (?,?,?,?,?,?,?,0,'SIMULADO')",
        (ahora.replace(microsecond=0).isoformat(), respuesta["modo"], platillo["id"], ficha["porciones"],
         ficha["ventana_recoleccion"]["inicio"], ficha["ventana_recoleccion"]["fin"],
         json.dumps(ficha, ensure_ascii=False)))
    con.commit()
    respuesta["alerta_id"] = cur.lastrowid
    return respuesta


def marcar_enviada(con: sqlite3.Connection, alerta_id: int) -> dict:
    """Simula el envío del aviso (no se conecta a ningún servicio de mensajería)."""
    fila = con.execute("SELECT id, enviada FROM alertas_excedente WHERE id = ?", (alerta_id,)).fetchone()
    if fila is None:
        raise KeyError(alerta_id)
    con.execute("UPDATE alertas_excedente SET enviada = 1 WHERE id = ?", (alerta_id,))
    con.commit()
    return {"alerta_id": alerta_id, "enviada": True, "envio_simulado": True,
            "mensaje": "Aviso registrado. En este prototipo el envío es SIMULADO: no se contacta a nadie."}
