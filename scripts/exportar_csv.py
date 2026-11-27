#!/usr/bin/env python3
"""
Opsia — Exporta la base de datos SIMULADA a archivos CSV (para Excel o Google Sheets)
Archivo: /scripts/exportar_csv.py

Crea data/csv/ con un archivo por tabla, más dos vistas "legibles" que unen nombres:
  * compras_diarias.csv   fecha, insumo, compra tradicional, consumo real, merma, faltante
  * ventas_detalle.csv    fecha, platillo, porciones e ingreso
Los CSV usan UTF-8 con BOM para que Excel muestre bien los acentos.

Uso:
    python scripts/exportar_csv.py                 # base por defecto: data/restaurante.db
    python scripts/exportar_csv.py --db otra.db --salida otra_carpeta
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

VISTAS = {
    "compras_diarias": """
        SELECT c.fecha, x.dia_semana, x.epoca_anio, x.es_dia_festivo, x.nombre_festivo, x.evento_plaza,
               i.nombre AS insumo, i.unidad, c.compra_tradicional, c.consumo_real,
               c.merma_tradicional, c.faltante_tradicional, i.precio_unitario_mxn,
               ROUND(c.compra_tradicional * i.precio_unitario_mxn, 2) AS compra_mxn, c.origen_dato
        FROM consumo_insumos_diario c
        JOIN insumos i ON i.id = c.insumo_id
        JOIN contexto_diario x ON x.fecha = c.fecha
        ORDER BY c.fecha, i.nombre""",
    "ventas_detalle": """
        SELECT v.fecha, p.nombre AS platillo, p.categoria, v.porciones_vendidas, v.ingreso_mxn, v.origen_dato
        FROM ventas_diarias v JOIN platillos p ON p.id = v.platillo_id
        ORDER BY v.fecha, p.nombre""",
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Exporta la base SIMULADA de Opsia a CSV.")
    p.add_argument("--db", type=Path, default=RAIZ / "data" / "restaurante.db")
    p.add_argument("--salida", type=Path, default=RAIZ / "data" / "csv")
    args = p.parse_args(argv)
    if not args.db.exists():
        print(f"No existe {args.db}. Corre primero: python data/generar_datos.py", file=sys.stderr)
        return 1
    args.salida.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(args.db)
    tablas = [f[0] for f in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
    consultas = {t: f"SELECT * FROM {t}" for t in tablas} | VISTAS
    for nombre, sql in consultas.items():
        cur = con.execute(sql)
        ruta = args.salida / f"{nombre}.csv"
        with ruta.open("w", newline="", encoding="utf-8-sig") as f:
            escritor = csv.writer(f)
            escritor.writerow([c[0] for c in cur.description])
            filas = cur.fetchall()
            escritor.writerows(filas)
        print(f"  {ruta.relative_to(RAIZ) if ruta.is_relative_to(RAIZ) else ruta}  ({len(filas):,} filas)")
    con.close()
    print("\nListo. Todos los registros son SIMULADOS (columna origen_dato).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
