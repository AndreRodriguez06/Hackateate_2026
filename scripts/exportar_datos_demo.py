#!/usr/bin/env python3
"""
ZeroMerma AI — Exporta los datos del "modo demo autónoma" del frontend
Archivo: /scripts/exportar_datos_demo.py

Genera `frontend/datos_demo.js` con respuestas REALES del backend y del modelo
(calculadas sobre los datos SIMULADOS), para que el frontend funcione aunque se
abra `index.html` sin servidor:

  * predicciones del Random Forest para las 112 combinaciones de contexto
    (7 días × quincena × lluvia × evento × vacaciones) y los 46 insumos
  * inventario, promociones (modo reglas) y auditoría de los 46 insumos
  * ventas promedio por platillo y día, para recalcular la alerta de excedentes en JS

Trabaja sobre COPIAS temporales de la base y el modelo: no escribe en data/restaurante.db.

Uso (desde la raíz del repo, con la base y el modelo ya creados o no):
    python scripts/exportar_datos_demo.py
"""

from __future__ import annotations

import itertools
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
SALIDA = RAIZ / "frontend" / "datos_demo.js"


def main() -> int:
    # 1) Asegura que existan base y modelo reales, y trabaja sobre copias.
    from backend import main as backend_main  # noqa: F401  (rutas por defecto)
    backend_main.preparar_entorno()
    from backend import database as db_real

    tmp = Path(tempfile.mkdtemp())
    shutil.copy(db_real.RUTA_DB, tmp / "restaurante.db")
    shutil.copy(db_real.RUTA_MODELO, tmp / "modelo_rf.pkl")
    db_real.RUTA_DB = tmp / "restaurante.db"          # el backend lee estas rutas en cada petición
    db_real.RUTA_MODELO = tmp / "modelo_rf.pkl"

    import numpy as np
    from fastapi.testclient import TestClient

    from backend import database as db
    from backend import gemini_service
    from backend.services import alerta_excedente
    from data import generar_datos
    from ml import modelo_demanda

    os.environ["ZEROMERMA_AUTOPREPARAR"] = "0"
    os.environ["GEMINI_API_KEY"] = ""   # el respaldo exportado nunca depende de Gemini
    cliente = TestClient(backend_main.app)

    catalogo = cliente.get("/api/catalogo").json()
    inventario = cliente.get("/api/inventario").json()
    optimizar = cliente.post("/api/optimizar-menu", json={"usar_gemini": False}).json()

    # 2) Predicciones del modelo para todas las combinaciones de contexto.
    paquete = modelo_demanda.cargar_modelo(db.RUTA_MODELO)
    combos = list(itertools.product(range(7), (0, 1), (0, 1), (0, 1), (0, 1)))
    pred = paquete["modelo"].predict(np.array(combos, dtype=float))
    predicciones = {"".join(map(str, c)): [round(float(v), 3) for v in fila] for c, fila in zip(combos, pred)}

    with db.sesion() as con:
        insumos_db = db.insumos_por_clave(con)
        platillos = db.platillos_con_recetas(con)
        ventas_por_dia = {d: db.ventas_promedio(con, dia_semana=d) for d in range(7)}

    insumos = []
    for clave in paquete["salidas"][1:]:
        i = insumos_db[clave]
        insumos.append({
            "clave": clave, "nombre": i["nombre"], "unidad": i["unidad"], "categoria": i["categoria"],
            "precio": i["precio_unitario_mxn"],
            "factor_caducidad": generar_datos.factor_caducidad(i["vida_util_dias"]),
            "tradicional_por_dia": paquete["compra_tradicional_por_dia"][clave],
            "margen_recomendado": round(paquete["margen_recomendado_p90"][clave], 3),
        })

    # 3) Auditoría de cada insumo (el backtest se calcula una vez y se reutiliza).
    auditoria = {}
    for i in insumos:
        r = cliente.get("/api/auditoria", params={"insumo": i["clave"]}).json()
        auditoria[i["clave"]] = {"insumo": r["insumo"], "serie": r["serie"]}
    auditoria_totales = {k: r[k] for k in ("periodo", "totales", "metodologia")}

    # 4) Datos para recalcular la alerta de excedentes en el navegador.
    alerta = {
        "apertura": alerta_excedente.APERTURA, "cierre": alerta_excedente.CIERRE,
        "exponente": alerta_excedente.EXPONENTE_CURVA, "colchon": alerta_excedente.COLCHON_PREPARACION,
        "ritmos": alerta_excedente.RITMOS, "sobrante_minimo": alerta_excedente.SOBRANTE_MINIMO,
        "horas_anticipacion": alerta_excedente.HORAS_ANTICIPACION,
        "horas_limite_antes_cierre": alerta_excedente.HORAS_LIMITE_ANTES_CIERRE,
        "ventana_minima": alerta_excedente.VENTANA_MINIMA,
        "recomendaciones": {"refrigerar": gemini_service.recomendaciones_base(True),
                            "ambiente": gemini_service.recomendaciones_base(False)},
        "platillos": {k: {"nombre": p["nombre"], "peso_porcion_kg": p["peso_porcion_kg"],
                          "refrigerar": any(insumos_db[c]["categoria"] in alerta_excedente.CATEGORIAS_REFRIGERAR
                                            for c in p["receta"]),
                          "ventas_por_dia": [round(ventas_por_dia[d].get(k, 0.0), 2) for d in range(7)]}
                      for k, p in platillos.items()},
    }

    datos = {
        "generado_en": datetime.now().replace(microsecond=0).isoformat(),
        "origen_dato": "SIMULADO",
        "nota": "Respuestas precalculadas del backend y del modelo para el modo demo autónoma.",
        "variables": paquete["variables"],
        "importancias": paquete["importancias"],
        "insumos": insumos,
        "predicciones": predicciones,
        "catalogo": catalogo,
        "inventario": inventario,
        "optimizar": optimizar,
        "auditoria": {"por_insumo": auditoria, **auditoria_totales},
        "alerta": alerta,
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        "/* Generado por scripts/exportar_datos_demo.py — NO editar a mano. Datos SIMULADOS. */\n"
        f"window.DATOS_DEMO = {json.dumps(datos, ensure_ascii=False, separators=(',', ':'))};\n",
        encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Escrito {SALIDA} ({SALIDA.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
