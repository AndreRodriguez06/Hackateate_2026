"""
OpsIA — Acceso a la base de datos SQLite
Archivo: /backend/database.py

Funciones de consulta que comparten los endpoints. No contiene lógica HTTP.
Las rutas se pueden cambiar con variables de entorno (útil para pruebas):
    OPSIA_DB      ruta del archivo SQLite   (por defecto data/restaurante.db)
    OPSIA_MODELO  ruta del modelo .pkl      (por defecto ml/modelo_rf.pkl)
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RUTA_DB = Path(os.getenv("OPSIA_DB", RAIZ / "data" / "restaurante.db"))
RUTA_MODELO = Path(os.getenv("OPSIA_MODELO", RAIZ / "ml" / "modelo_rf.pkl"))
RUTA_FRONTEND = RAIZ / "frontend"

# Semáforo de caducidad (horas restantes)
HORAS_CRITICO = 24      # < 24 h  -> CRITICO
HORAS_PRECAUCION = 48   # <= 48 h -> PRECAUCION; el resto OPTIMO

# Peso aproximado de los insumos que se compran por pieza (para estimar kg de una porción).
PESO_PIEZA_KG = {"bolillo": 0.07, "pan_hamburguesa": 0.08}


def conectar(ruta: Path | None = None) -> sqlite3.Connection:
    """Abre una conexión nueva. Se usa una por petición (SQLite no comparte conexiones entre hilos)."""
    con = sqlite3.connect(ruta or RUTA_DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


@contextmanager
def sesion(ruta: Path | None = None):
    """`with sesion() as con:` abre la conexión y la CIERRA al salir (el `with` de sqlite3 solo hace commit)."""
    con = conectar(ruta)
    try:
        yield con
    finally:
        con.close()


def origen_dataset(con: sqlite3.Connection) -> str:
    fila = con.execute("SELECT valor FROM meta_dataset WHERE clave = 'origen_dato'").fetchone()
    return fila["valor"] if fila else "DESCONOCIDO"


def estado_por_horas(horas: float) -> str:
    if horas < HORAS_CRITICO:
        return "CRITICO"
    if horas <= HORAS_PRECAUCION:
        return "PRECAUCION"
    return "OPTIMO"


def listar_lotes(con: sqlite3.Connection, ahora: datetime) -> list[dict]:
    """Lotes del inventario con horas restantes y semáforo, ordenados del más urgente al menos."""
    filas = con.execute("""
        SELECT l.id AS lote_id, i.id AS insumo_id, i.clave, i.nombre, i.categoria, i.unidad,
               i.precio_unitario_mxn, l.cantidad, l.fecha_ingreso, l.fecha_caducidad, l.ubicacion,
               l.origen_dato
        FROM inventario_lotes l JOIN insumos i ON i.id = l.insumo_id
    """).fetchall()
    lotes = []
    for f in filas:
        horas = (datetime.fromisoformat(f["fecha_caducidad"]) - ahora).total_seconds() / 3600
        lote = dict(f)
        lote["horas_restantes"] = round(horas, 1)
        lote["estado"] = estado_por_horas(horas)
        lote["caducado"] = horas <= 0
        lote["valor_mxn"] = round(f["cantidad"] * f["precio_unitario_mxn"], 2)
        lote["es_simulado"] = f["origen_dato"] == "SIMULADO"
        lotes.append(lote)
    return sorted(lotes, key=lambda x: x["horas_restantes"])


def insumos_por_clave(con: sqlite3.Connection) -> dict[str, dict]:
    return {f["clave"]: dict(f) for f in con.execute("SELECT * FROM insumos")}


def platillos_con_recetas(con: sqlite3.Connection) -> dict[str, dict]:
    """
    Menú vigente con su receta y costo de insumos por porción:
    {clave: {id, nombre, categoria, precio_venta_mxn, receta: {insumo: cantidad}, costo_porcion_mxn, peso_porcion_kg}}
    """
    platillos = {f["clave"]: {**dict(f), "receta": {}, "costo_porcion_mxn": 0.0, "peso_porcion_kg": 0.0}
                 for f in con.execute("SELECT * FROM platillos WHERE activo = 1")}
    por_id = {p["id"]: p for p in platillos.values()}
    for f in con.execute("""
            SELECT r.platillo_id, i.clave, i.unidad, i.precio_unitario_mxn, r.cantidad_por_porcion
            FROM recetas r JOIN insumos i ON i.id = r.insumo_id"""):
        p = por_id.get(f["platillo_id"])
        if p is None:
            continue
        cantidad = f["cantidad_por_porcion"]
        p["receta"][f["clave"]] = cantidad
        p["costo_porcion_mxn"] += cantidad * f["precio_unitario_mxn"]
        p["peso_porcion_kg"] += cantidad * PESO_PIEZA_KG.get(f["clave"], 1.0 if f["unidad"] != "pza" else 0.05)
    for p in platillos.values():
        p["costo_porcion_mxn"] = round(p["costo_porcion_mxn"], 2)
        p["peso_porcion_kg"] = round(p["peso_porcion_kg"], 3)
    return platillos


def ventas_promedio(con: sqlite3.Connection, dia_semana: int | None = None, semanas: int = 8) -> dict[str, float]:
    """
    Porciones promedio vendidas por platillo en las últimas `semanas` semanas del historial.
    Si se da `dia_semana`, solo promedia ese día (por ejemplo, solo viernes).
    """
    filtro = "AND c.dia_semana = :dia" if dia_semana is not None else ""
    filas = con.execute(f"""
        SELECT p.clave, AVG(v.porciones_vendidas) AS promedio
        FROM ventas_diarias v
        JOIN platillos p ON p.id = v.platillo_id
        JOIN contexto_diario c ON c.fecha = v.fecha
        WHERE v.fecha > date((SELECT MAX(fecha) FROM contexto_diario), :dias) {filtro}
        GROUP BY p.clave
    """, {"dias": f"-{semanas * 7} days", "dia": dia_semana}).fetchall()
    return {f["clave"]: float(f["promedio"]) for f in filas}
