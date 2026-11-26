#!/usr/bin/env python3
"""
ZeroMerma AI — Generador de datos históricos SIMULADOS
Archivo: /data/generar_datos.py

Crea la base de datos SQLite `data/zeromerma.db` a partir de `data/schema.sql`
y la llena con datos ficticios, pero coherentes, de un restaurante de plaza
comercial en México:

  * catálogo de insumos y menú vigente con su recetario
  * N días de historial (por defecto 180): afluencia, clima, quincena, eventos
  * ventas diarias por platillo
  * consumo diario por insumo vs. compra tradicional "a ojo" (merma y faltantes)
  * inventario actual por lotes, con caducidades relativas a la hora de ejecución
    (siempre hay insumos a menos de 24 h de caducar para la demo)

TODOS los registros llevan origen_dato = 'SIMULADO' (regla de la rúbrica).

Solo usa la librería estándar de Python (no requiere pip install).

Uso:
    python data/generar_datos.py                    # 180 días, semilla 42
    python data/generar_datos.py --dias 365         # más historial
    python data/generar_datos.py --solo-inventario  # solo refresca caducidades antes de la demo
    python data/generar_datos.py --help
"""

from __future__ import annotations

import argparse
import calendar
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

VERSION_SCRIPT = "1.0.0"
ORIGEN = "SIMULADO"

DIR_DATA = Path(__file__).resolve().parent
RUTA_SCHEMA = DIR_DATA / "schema.sql"
RUTA_DB_DEFAULT = DIR_DATA / "zeromerma.db"

FUENTE_PRECIO_PENDIENTE = (
    "SIMULADO - valor provisional. Reemplazar por el precio de PROFECO "
    "'Quién es Quién en los Precios' (consulta pendiente, ver docs/02_base_de_datos.md)"
)

# =============================================================================
# 1. CATÁLOGOS (insumos, platillos, recetario)
# =============================================================================

# clave, nombre, categoría, unidad, precio_unitario_mxn (SIMULADO), vida_util_dias, perecedero, ubicación
INSUMOS = [
    ("pollo",        "Pechuga de pollo",            "proteína",  "kg",  135.0,   3, 1, "refrigerador"),
    ("milanesa",     "Milanesa de res",             "proteína",  "kg",  175.0,   3, 1, "refrigerador"),
    ("huevo",        "Huevo blanco",                "proteína",  "kg",   48.0,  21, 1, "refrigerador"),
    ("crema",        "Crema ácida",                 "lácteo",    "L",    72.0,   7, 1, "refrigerador"),
    ("queso",        "Queso manchego",              "lácteo",    "kg",  189.0,  14, 1, "refrigerador"),
    ("tortilla",     "Tortilla de maíz",            "panadería", "kg",   24.0,   2, 1, "alacena"),
    ("bolillo",      "Pan bolillo",                 "panadería", "pza",   3.5,   1, 1, "alacena"),
    ("jitomate",     "Jitomate saladet",            "verdura",   "kg",   28.0,   5, 1, "alacena"),
    ("tomate_verde", "Tomate verde",                "verdura",   "kg",   30.0,   7, 1, "alacena"),
    ("cebolla",      "Cebolla blanca",              "verdura",   "kg",   30.0,  10, 1, "alacena"),
    ("lechuga",      "Lechuga romana",              "verdura",   "kg",   40.0,   4, 1, "refrigerador"),
    ("aguacate",     "Aguacate hass",               "fruta",     "kg",   75.0,   4, 1, "alacena"),
    ("fruta",        "Fruta de temporada (aguas)",  "fruta",     "kg",   35.0,   4, 1, "refrigerador"),
    ("arroz",        "Arroz blanco",                "abarrote",  "kg",   32.0, 365, 0, "alacena"),
    ("frijol",       "Frijol negro",                "abarrote",  "kg",   38.0, 365, 0, "alacena"),
    ("cafe",         "Café en grano",               "abarrote",  "kg",  320.0,  90, 0, "alacena"),
]

# clave, nombre, categoría, precio_venta_mxn (SIMULADO), popularidad_base
# Platos fuertes: popularidad = fracción de comensales que lo piden (suman 1.0).
# Bebidas: popularidad = fracción de comensales que además piden la bebida.
PLATILLOS = [
    ("enchiladas_suizas",  "Enchiladas Suizas",               "plato fuerte", 120.0, 0.16),
    ("chilaquiles_pollo",  "Chilaquiles Especiales con Pollo", "plato fuerte", 110.0, 0.14),
    ("torta_milanesa",     "Torta de Milanesa",               "plato fuerte",  95.0, 0.11),
    ("pollo_plancha",      "Pollo a la Plancha con Arroz",    "plato fuerte", 125.0, 0.10),
    ("tacos_pollo",        "Tacos de Pollo (orden de 3)",     "plato fuerte",  90.0, 0.10),
    ("molletes",           "Molletes con Pico de Gallo",      "plato fuerte",  75.0, 0.08),
    ("sopa_tortilla",      "Sopa de Tortilla",                "plato fuerte",  70.0, 0.08),
    ("huevos_rancheros",   "Huevos Rancheros",                "plato fuerte",  85.0, 0.08),
    ("quesadillas",        "Quesadillas de Queso (3 pzas)",   "plato fuerte",  80.0, 0.08),
    ("ensalada_cesar",     "Ensalada César con Pollo",        "plato fuerte", 105.0, 0.07),
    ("agua_fresca",        "Agua Fresca del Día (500 ml)",    "bebida",        35.0, 0.55),
    ("cafe_americano",     "Café Americano",                  "bebida",        35.0, 0.25),
]

# Recetario: cantidad de cada insumo por UNA porción (misma unidad que el insumo).
RECETAS = {
    "enchiladas_suizas": {"pollo": 0.180, "crema": 0.060, "tortilla": 0.120, "queso": 0.050,
                          "tomate_verde": 0.100, "cebolla": 0.020},
    "chilaquiles_pollo": {"tortilla": 0.150, "pollo": 0.150, "crema": 0.040, "queso": 0.030,
                          "jitomate": 0.100, "cebolla": 0.020, "frijol": 0.060},
    "torta_milanesa":    {"bolillo": 1, "milanesa": 0.150, "aguacate": 0.040, "jitomate": 0.040,
                          "frijol": 0.040, "lechuga": 0.020},
    "pollo_plancha":     {"pollo": 0.220, "arroz": 0.100, "frijol": 0.060, "lechuga": 0.040,
                          "jitomate": 0.040},
    "tacos_pollo":       {"tortilla": 0.100, "pollo": 0.140, "cebolla": 0.020, "aguacate": 0.040,
                          "tomate_verde": 0.040},
    "molletes":          {"bolillo": 1, "frijol": 0.080, "queso": 0.050, "jitomate": 0.040,
                          "cebolla": 0.020},
    "sopa_tortilla":     {"tortilla": 0.060, "jitomate": 0.120, "crema": 0.030, "aguacate": 0.030,
                          "queso": 0.020, "cebolla": 0.020},
    "huevos_rancheros":  {"huevo": 0.120, "tortilla": 0.060, "jitomate": 0.100, "frijol": 0.060,
                          "cebolla": 0.020},
    "quesadillas":       {"tortilla": 0.120, "queso": 0.080, "crema": 0.020},
    "ensalada_cesar":    {"lechuga": 0.150, "pollo": 0.120, "queso": 0.020, "huevo": 0.020},
    "agua_fresca":       {"fruta": 0.120},
    "cafe_americano":    {"cafe": 0.012},
}

# =============================================================================
# 2. SUPUESTOS DE LA SIMULACIÓN (todos SIMULADOS; documentados en /docs)
# =============================================================================

# Comensales base por día de la semana (0 = lunes ... 6 = domingo).
# Plaza comercial: fines de semana más concurridos.
COMENSALES_BASE = [118, 112, 122, 132, 168, 195, 172]

EFECTO_QUINCENA = 0.12        # +12 % comensales en días de pago
EFECTO_LLUVIA = 0.06          # +6 % (plaza techada: la gente se refugia)
EFECTO_EVENTO = 0.15          # +15 % evento cercano (concierto, evento universitario)
EFECTO_VACACIONES = -0.10     # -10 % vacaciones escolares (menos estudiantes)
CRECIMIENTO_PERIODO = 0.03    # +3 % de tendencia a lo largo del historial
RUIDO_COMENSALES = 0.07       # desviación estándar relativa del ruido diario
RUIDO_PLATILLO = 0.10         # desviación estándar relativa por platillo

# Probabilidad de lluvia por mes (perfil de temporada de lluvias del centro de México).
PROB_LLUVIA_MES = [0.05, 0.05, 0.08, 0.12, 0.25, 0.55, 0.65, 0.65, 0.55, 0.25, 0.08, 0.05]
# Temperatura media por mes (°C).
TEMP_MEDIA_MES = [15, 17, 19, 21, 21, 20, 18, 18, 18, 17, 16, 15]

# Mermas operativas al cocinar (recortes, pruebas, accidentes).
MERMA_PREPARACION = 0.03

# Compra tradicional: el encargado compra "lo del día más fuerte de la semana
# pasada" con un colchón aleatorio, y de vez en cuando recorta al tanteo.
COLCHON_TRADICIONAL = (0.95, 1.20)
PROB_RECORTE_TANTEO = 0.08
FACTOR_RECORTE = 0.75


def factor_caducidad(vida_util_dias: int) -> float:
    """Fracción del sobrante de un día que termina caducando (y se tira)."""
    if vida_util_dias <= 2:
        return 0.90
    if vida_util_dias <= 4:
        return 0.50
    if vida_util_dias <= 7:
        return 0.25
    if vida_util_dias <= 14:
        return 0.10
    return 0.0


def redondear_a_empaque(cantidad: float, unidad: str) -> float:
    """El proveedor vende en empaques: piezas enteras o múltiplos de 0.5 kg / 0.5 L."""
    if unidad == "pza":
        return float(int(cantidad + 0.999))
    return round(int(cantidad * 2 + 0.999) / 2, 1)


# =============================================================================
# 3. CALENDARIO: quincenas, vacaciones, eventos y clima
# =============================================================================

def _ajustar_a_dia_habil(d: date) -> date:
    """Si el día de pago cae en fin de semana, se paga el viernes anterior."""
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d - timedelta(days=2)
    return d


def dias_de_pago(anio: int, mes: int) -> list[date]:
    ultimo = calendar.monthrange(anio, mes)[1]
    return [_ajustar_a_dia_habil(date(anio, mes, 15)),
            _ajustar_a_dia_habil(date(anio, mes, ultimo))]


def es_quincena(d: date) -> bool:
    """Día de pago o el día siguiente (cuando más se gasta)."""
    mes_anterior = (d.replace(day=1) - timedelta(days=1))
    pagos = dias_de_pago(d.year, d.month) + dias_de_pago(mes_anterior.year, mes_anterior.month)
    return any(0 <= (d - p).days <= 1 for p in pagos)


def es_temporada_vacacional(d: date) -> bool:
    """Vacaciones escolares aproximadas (verano e invierno)."""
    return ((d.month == 7 and d.day >= 10) or (d.month == 8 and d.day <= 15)
            or (d.month == 12 and d.day >= 15) or (d.month == 1 and d.day <= 7))


# =============================================================================
# 4. GENERACIÓN
# =============================================================================

def crear_esquema(con: sqlite3.Connection) -> None:
    con.executescript(RUTA_SCHEMA.read_text(encoding="utf-8"))


def insertar_catalogos(con: sqlite3.Connection) -> tuple[dict, dict]:
    """Inserta insumos, platillos y recetas. Devuelve mapas clave -> id."""
    ids_insumo, ids_platillo = {}, {}
    for i, (clave, nombre, cat, unidad, precio, vida, perecedero, _ubic) in enumerate(INSUMOS, start=1):
        con.execute(
            "INSERT INTO insumos (id, clave, nombre, categoria, unidad, precio_unitario_mxn,"
            " vida_util_dias, perecedero, fuente_precio, origen_dato) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (i, clave, nombre, cat, unidad, precio, vida, perecedero, FUENTE_PRECIO_PENDIENTE, ORIGEN),
        )
        ids_insumo[clave] = i
    for i, (clave, nombre, cat, precio, pop) in enumerate(PLATILLOS, start=1):
        con.execute(
            "INSERT INTO platillos (id, clave, nombre, categoria, precio_venta_mxn, popularidad_base,"
            " activo, origen_dato) VALUES (?,?,?,?,?,?,1,?)",
            (i, clave, nombre, cat, precio, pop, ORIGEN),
        )
        ids_platillo[clave] = i
    for platillo, ingredientes in RECETAS.items():
        for insumo, cantidad in ingredientes.items():
            con.execute(
                "INSERT INTO recetas (platillo_id, insumo_id, cantidad_por_porcion, origen_dato)"
                " VALUES (?,?,?,?)",
                (ids_platillo[platillo], ids_insumo[insumo], cantidad, ORIGEN),
            )
    return ids_insumo, ids_platillo


def simular_contexto(d: date, indice: int, total_dias: int, rng: random.Random) -> dict:
    """Variables de contexto y afluencia de un día."""
    dow = d.weekday()
    quincena = es_quincena(d)
    lluvia = rng.random() < PROB_LLUVIA_MES[d.month - 1]
    prob_evento = 0.12 if dow in (4, 5) else 0.05
    evento = rng.random() < prob_evento
    vacaciones = es_temporada_vacacional(d)
    temperatura = TEMP_MEDIA_MES[d.month - 1] + rng.gauss(0, 2.0) - (2.0 if lluvia else 0.0)

    factor = 1.0
    factor += EFECTO_QUINCENA if quincena else 0.0
    factor += EFECTO_LLUVIA if lluvia else 0.0
    factor += EFECTO_EVENTO if evento else 0.0
    factor += EFECTO_VACACIONES if vacaciones else 0.0
    factor *= 1.0 + CRECIMIENTO_PERIODO * (indice / max(1, total_dias - 1))
    ruido = max(0.6, rng.gauss(1.0, RUIDO_COMENSALES))
    comensales = max(0, round(COMENSALES_BASE[dow] * factor * ruido))

    return {
        "fecha": d.isoformat(), "dia_semana": dow, "mes": d.month,
        "es_fin_de_semana": int(dow >= 5), "es_quincena": int(quincena),
        "lluvia": int(lluvia), "temperatura_c": round(temperatura, 1),
        "evento_cercano": int(evento), "temporada_vacacional": int(vacaciones),
        "comensales": comensales,
    }


def simular_ventas(ctx: dict, rng: random.Random) -> dict[str, int]:
    """Porciones vendidas por platillo en un día, según afluencia y contexto."""
    ventas = {}
    for clave, _nombre, _cat, _precio, pop in PLATILLOS:
        ajuste = 1.0
        if ctx["lluvia"]:
            ajuste *= {"sopa_tortilla": 1.35, "cafe_americano": 1.25,
                       "ensalada_cesar": 0.80, "agua_fresca": 0.85}.get(clave, 1.0)
        if ctx["es_fin_de_semana"]:
            ajuste *= {"chilaquiles_pollo": 1.25, "huevos_rancheros": 1.25}.get(clave, 1.0)
        if ctx["temperatura_c"] >= 22:
            ajuste *= {"agua_fresca": 1.20}.get(clave, 1.0)
        ruido = max(0.5, rng.gauss(1.0, RUIDO_PLATILLO))
        ventas[clave] = max(0, round(ctx["comensales"] * pop * ajuste * ruido))
    return ventas


def generar_historial(con: sqlite3.Connection, ids_insumo: dict, ids_platillo: dict,
                      fecha_fin: date, dias: int, rng: random.Random) -> None:
    precios = {p[0]: p[3] for p in PLATILLOS}
    info_insumo = {i[0]: i for i in INSUMOS}
    historial_consumo: dict[str, list[float]] = {clave: [] for clave in ids_insumo}
    fecha_inicio = fecha_fin - timedelta(days=dias - 1)

    for indice in range(dias):
        d = fecha_inicio + timedelta(days=indice)
        ctx = simular_contexto(d, indice, dias, rng)
        con.execute(
            "INSERT INTO contexto_diario (fecha, dia_semana, mes, es_fin_de_semana, es_quincena, lluvia,"
            " temperatura_c, evento_cercano, temporada_vacacional, comensales, origen_dato)"
            " VALUES (:fecha,:dia_semana,:mes,:es_fin_de_semana,:es_quincena,:lluvia,:temperatura_c,"
            " :evento_cercano,:temporada_vacacional,:comensales,'SIMULADO')",
            ctx,
        )

        # Ventas por platillo
        ventas = simular_ventas(ctx, rng)
        for clave, porciones in ventas.items():
            con.execute(
                "INSERT INTO ventas_diarias (fecha, platillo_id, porciones_vendidas, ingreso_mxn, origen_dato)"
                " VALUES (?,?,?,?,?)",
                (ctx["fecha"], ids_platillo[clave], porciones, round(porciones * precios[clave], 2), ORIGEN),
            )

        # Consumo real por insumo = Σ porciones × receta × (1 + merma de preparación)
        consumo = {clave: 0.0 for clave in ids_insumo}
        for platillo, porciones in ventas.items():
            for insumo, cantidad in RECETAS[platillo].items():
                consumo[insumo] += porciones * cantidad
        for insumo in consumo:
            consumo[insumo] *= 1.0 + MERMA_PREPARACION

        # Compra tradicional "a ojo" y sus consecuencias (merma o faltante)
        for insumo, real in consumo.items():
            _c, _n, _cat, unidad, _p, vida, _per, _u = info_insumo[insumo]
            previos = historial_consumo[insumo][-7:]
            referencia = max(previos) if previos else real * 1.10
            compra = referencia * rng.uniform(*COLCHON_TRADICIONAL)
            if rng.random() < PROB_RECORTE_TANTEO:
                compra *= FACTOR_RECORTE
            compra = redondear_a_empaque(compra, unidad)
            sobrante = max(0.0, compra - real)
            faltante = max(0.0, real - compra)
            merma = sobrante * factor_caducidad(vida)
            con.execute(
                "INSERT INTO consumo_insumos_diario (fecha, insumo_id, consumo_real, compra_tradicional,"
                " merma_tradicional, faltante_tradicional, origen_dato) VALUES (?,?,?,?,?,?,?)",
                (ctx["fecha"], ids_insumo[insumo], round(real, 3), compra,
                 round(merma, 3), round(faltante, 3), ORIGEN),
            )
            historial_consumo[insumo].append(real)


# Inventario actual: (insumo, cantidad, horas desde ingreso, horas para caducar).
# Los cuatro primeros coinciden con la vista "Rescate Rentable" del prototipo.
LOTES_INVENTARIO = [
    ("pollo",          7.5,  54,   18),   # CRÍTICO (< 24 h)
    ("crema",          4.0, 146,   22),   # CRÍTICO (< 24 h)
    ("jitomate",       6.0,  72,   48),   # vigilar (< 72 h)
    ("arroz",         12.0, 240,  360),   # estable (15 días)
    ("pollo",         10.0,   6,   66),
    ("tortilla",       5.0,  10,   30),
    ("bolillo",       40.0,   4,   20),   # CRÍTICO (< 24 h)
    ("queso",          3.2, 192,  144),
    ("lechuga",        2.5,  36,   60),
    ("aguacate",       3.0,  56,   40),
    ("fruta",          5.0,  60,   36),
    ("milanesa",       4.0,  12,   60),
    ("huevo",          6.0, 120,  384),
    ("cebolla",        5.0,  96,  144),
    ("tomate_verde",   4.0,  48,  120),
    ("frijol",         8.0, 480, 4800),
    ("cafe",           2.0, 360, 1800),
]


def generar_inventario(con: sqlite3.Connection, ids_insumo: dict, ahora: datetime) -> None:
    ubicacion = {i[0]: i[7] for i in INSUMOS}
    con.execute("DELETE FROM inventario_lotes")
    for n, (insumo, cantidad, horas_ingreso, horas_caducar) in enumerate(LOTES_INVENTARIO, start=1):
        ingreso = (ahora - timedelta(hours=horas_ingreso)).replace(microsecond=0)
        caducidad = (ahora + timedelta(hours=horas_caducar)).replace(microsecond=0)
        con.execute(
            "INSERT INTO inventario_lotes (id, insumo_id, cantidad, fecha_ingreso, fecha_caducidad,"
            " ubicacion, origen_dato) VALUES (?,?,?,?,?,?,?)",
            (n, ids_insumo[insumo], cantidad, ingreso.isoformat(), caducidad.isoformat(),
             ubicacion[insumo], ORIGEN),
        )


def guardar_metadatos(con: sqlite3.Connection, args: argparse.Namespace, fecha_fin: date, ahora: datetime) -> None:
    meta = {
        "origen_dato": ORIGEN,
        "advertencia": "Todos los registros son SIMULADOS para validar el prototipo. "
                       "No representan operaciones de ningún restaurante real.",
        "version_script": VERSION_SCRIPT,
        "generado_en": ahora.replace(microsecond=0).isoformat(),
        "semilla": str(args.semilla),
        "dias_historial": str(args.dias),
        "fecha_inicio": (fecha_fin - timedelta(days=args.dias - 1)).isoformat(),
        "fecha_fin": fecha_fin.isoformat(),
    }
    con.executemany("INSERT OR REPLACE INTO meta_dataset (clave, valor) VALUES (?,?)", meta.items())


# =============================================================================
# 5. RESUMEN Y VERIFICACIÓN
# =============================================================================

TABLAS_CON_ORIGEN = ["insumos", "platillos", "recetas", "contexto_diario", "ventas_diarias",
                     "consumo_insumos_diario", "inventario_lotes"]


def verificar(con: sqlite3.Connection) -> list[str]:
    """Devuelve una lista de errores (vacía si todo está bien)."""
    errores = []
    for tabla in TABLAS_CON_ORIGEN:
        sin_etiqueta = con.execute(
            f"SELECT COUNT(*) FROM {tabla} WHERE origen_dato <> 'SIMULADO'").fetchone()[0]
        if sin_etiqueta:
            errores.append(f"{tabla}: {sin_etiqueta} registros sin etiqueta SIMULADO")
    if con.execute("SELECT COUNT(*) FROM contexto_diario").fetchone()[0] < 150:
        errores.append("contexto_diario tiene menos de 150 días")
    criticos = con.execute(
        "SELECT COUNT(*) FROM inventario_lotes "
        "WHERE (julianday(fecha_caducidad) - julianday('now', 'localtime')) * 24 < 24").fetchone()[0]
    if criticos < 2:
        errores.append("hay menos de 2 lotes a menos de 24 h de caducar")
    huerfanas = con.execute("PRAGMA foreign_key_check").fetchall()
    if huerfanas:
        errores.append(f"{len(huerfanas)} referencias rotas (foreign keys)")
    return errores


def imprimir_resumen(con: sqlite3.Connection, ruta_db: Path) -> None:
    print(f"\nBase de datos: {ruta_db}")
    print("Registros por tabla (todos SIMULADOS):")
    total = 0
    for tabla in TABLAS_CON_ORIGEN:
        n = con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        total += n
        print(f"  {tabla:<26} {n:>6}")
    print(f"  {'TOTAL':<26} {total:>6}")

    ini, fin, prom, lluvia, quin = con.execute(
        "SELECT MIN(fecha), MAX(fecha), AVG(comensales), AVG(lluvia), AVG(es_quincena)"
        " FROM contexto_diario").fetchone()
    print(f"\nHistorial: {ini} a {fin} | comensales promedio/día: {prom:.0f}"
          f" | días con lluvia: {lluvia:.0%} | días de quincena: {quin:.0%}")

    kg, mxn, faltante = con.execute(
        "SELECT SUM(c.merma_tradicional), SUM(c.merma_tradicional * i.precio_unitario_mxn),"
        " SUM(c.faltante_tradicional > 0)"
        " FROM consumo_insumos_diario c JOIN insumos i ON i.id = c.insumo_id").fetchone()
    print(f"Compra tradicional (SIMULADA): merma {kg:,.1f} unidades ≈ ${mxn:,.0f} MXN;"
          f" {faltante} insumo-días con desabasto")

    print("\nInventario a menos de 24 h de caducar:")
    for nombre, cantidad, unidad, horas in con.execute(
            "SELECT i.nombre, l.cantidad, i.unidad,"
            " ROUND((julianday(l.fecha_caducidad) - julianday('now','localtime')) * 24, 1) AS h"
            " FROM inventario_lotes l JOIN insumos i ON i.id = l.insumo_id"
            " WHERE h < 24 ORDER BY h"):
        print(f"  - {nombre}: {cantidad} {unidad} (caduca en {horas} h)")


# =============================================================================
# 6. PUNTO DE ENTRADA
# =============================================================================

def parsear_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Genera la base de datos SIMULADA de ZeroMerma AI.")
    p.add_argument("--db", type=Path, default=RUTA_DB_DEFAULT, help="Ruta del archivo SQLite a crear.")
    p.add_argument("--dias", type=int, default=180, help="Días de historial (mínimo 150).")
    p.add_argument("--semilla", type=int, default=42, help="Semilla aleatoria (misma semilla = mismos datos).")
    p.add_argument("--fecha-fin", type=date.fromisoformat, default=None,
                   help="Último día del historial (AAAA-MM-DD). Por defecto: ayer.")
    p.add_argument("--solo-inventario", action="store_true",
                   help="No toca el historial; solo regenera los lotes con caducidades relativas a ahora.")
    p.add_argument("--silencioso", action="store_true", help="No imprime el resumen.")
    args = p.parse_args(argv)
    if args.dias < 150:
        p.error("--dias debe ser al menos 150 (requisito del proyecto)")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parsear_argumentos(argv)
    ahora = datetime.now()
    fecha_fin = args.fecha_fin or (ahora.date() - timedelta(days=1))
    args.db.parent.mkdir(parents=True, exist_ok=True)

    if args.solo_inventario:
        if not args.db.exists():
            print(f"No existe {args.db}. Corre primero el script sin --solo-inventario.", file=sys.stderr)
            return 1
        con = sqlite3.connect(args.db)
        ids_insumo = dict(con.execute("SELECT clave, id FROM insumos"))
        generar_inventario(con, ids_insumo, ahora)
        con.execute("INSERT OR REPLACE INTO meta_dataset VALUES ('inventario_actualizado_en', ?)",
                    (ahora.replace(microsecond=0).isoformat(),))
    else:
        if args.db.exists():
            args.db.unlink()  # se regenera desde cero para que sea reproducible
        con = sqlite3.connect(args.db)
        con.execute("PRAGMA foreign_keys = ON")
        rng = random.Random(args.semilla)
        crear_esquema(con)
        ids_insumo, ids_platillo = insertar_catalogos(con)
        generar_historial(con, ids_insumo, ids_platillo, fecha_fin, args.dias, rng)
        generar_inventario(con, ids_insumo, ahora)
        guardar_metadatos(con, args, fecha_fin, ahora)

    con.commit()
    errores = verificar(con)
    if not args.silencioso:
        imprimir_resumen(con, args.db)
    con.close()

    if errores:
        print("\nVERIFICACIÓN FALLIDA:", *errores, sep="\n  - ", file=sys.stderr)
        return 1
    if not args.silencioso:
        print("\nVerificación OK: todos los registros están etiquetados como SIMULADO.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
