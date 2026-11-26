#!/usr/bin/env python3
"""
ZeroMerma AI — Backend y API REST (FastAPI)
Archivo: /backend/main.py

Arranque (desde la raíz del repositorio):
    uvicorn backend.main:app --reload
    # o bien
    python backend/main.py

Abre http://localhost:8000 (aplicación) o http://localhost:8000/docs (documentación interactiva).

Al arrancar, si falta algo, el servidor lo prepara solo:
  * sin data/restaurante.db  -> genera los datos SIMULADOS (Apartado 2)
  * sin lotes a < 24 h        -> refresca las caducidades del inventario para la demo
  * sin ml/modelo_rf.pkl      -> entrena el modelo (Apartado 3)
Se puede desactivar con la variable de entorno ZEROMERMA_AUTOPREPARAR=0.

Endpoints:
  GET  /api/salud                         estado del servidor, base, modelo y Gemini
  GET  /api/catalogo                      insumos y platillos para los selectores
  GET  /api/inventario                    lotes con horas para caducar y semáforo
  POST /api/predecir                      compra sugerida con el modelo Random Forest
  POST /api/optimizar-menu                promociones sobre platillos existentes (Gemini o reglas)
  POST /api/alerta-excedente              proyección de sobrante al cierre y ficha de rescate
  POST /api/alerta-excedente/{id}/enviar  marca el aviso como enviado (envío SIMULADO)
  GET  /api/auditoria                     backtesting de los últimos días cerrados
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

# Permite `python backend/main.py`: agrega la raíz del repo al path de importación.
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402
from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field, field_validator  # noqa: E402

from backend import database as db  # noqa: E402
from backend.services import alerta_excedente, rescate_menu  # noqa: E402
from data import generar_datos  # noqa: E402
from ml import modelo_demanda  # noqa: E402

log = logging.getLogger("zeromerma")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")


def ahora() -> datetime:
    """Hora local del servidor; las caducidades del inventario se generan con la misma referencia."""
    return datetime.now()


def es_simulado(origen: str) -> bool:
    return "SIMULADO" in origen


# =============================================================================
# Preparación automática al arrancar
# =============================================================================

def preparar_entorno() -> None:
    ruta_db, ruta_modelo = db.RUTA_DB, db.RUTA_MODELO
    if not ruta_db.exists():
        log.info("No existe %s: generando datos SIMULADOS...", ruta_db)
        generar_datos.main(["--db", str(ruta_db), "--silencioso"])
    else:
        with db.sesion() as con:
            vigentes_criticos = [l for l in db.listar_lotes(con, ahora())
                                 if l["estado"] == "CRITICO" and not l["caducado"]]
        if not vigentes_criticos:
            log.info("El inventario no tiene lotes a < 24 h (datos viejos): refrescando caducidades...")
            generar_datos.main(["--db", str(ruta_db), "--solo-inventario", "--silencioso"])
    if not ruta_modelo.exists():
        log.info("No existe %s: entrenando el modelo...", ruta_modelo)
        modelo_demanda.entrenar(ruta_db, ruta_modelo, ruta_metricas=None, verbose=False)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    if os.getenv("ZEROMERMA_AUTOPREPARAR", "1") != "0":
        preparar_entorno()
    yield


# =============================================================================
# Aplicación
# =============================================================================

app = FastAPI(
    title="ZeroMerma AI · API",
    description="API del prototipo ZeroMerma AI. **Todos los datos son SIMULADOS.**",
    version="1.0.0",
    lifespan=ciclo_de_vida,
)

# CORS abierto: es una demo local; permite abrir el frontend desde otro puerto mientras se desarrolla.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# =============================================================================
# Modelos Pydantic (entrada y salida)
# =============================================================================

class ImportanciaVariable(BaseModel):
    variable: str
    nombre: str
    porcentaje: float


class Lote(BaseModel):
    lote_id: int
    clave: str
    insumo: str
    categoria: str
    cantidad: float
    unidad: str
    ubicacion: str
    fecha_caducidad: str
    horas_restantes: float
    estado: Literal["CRITICO", "PRECAUCION", "OPTIMO"]
    caducado: bool
    valor_mxn: float
    es_simulado: bool


class InventarioRespuesta(BaseModel):
    consultado_en: str
    resumen: dict[str, int]
    lotes: list[Lote]
    advertencia: str | None = None
    es_simulado: bool


class PrediccionEntrada(BaseModel):
    insumo: str = Field(..., examples=["pollo"], description="Clave ('pollo') o nombre ('Pechuga de pollo').")
    dia_semana: int = Field(..., ge=0, le=6, description="0 = lunes ... 6 = domingo.")
    es_quincena: bool = False
    lluvia: bool = False
    evento: bool = False
    temporada_vacacional: bool = False
    margen_seguridad: float = Field(0.08, ge=0, le=0.25, description="Fracción: 0.08 = 8 %.")


class PrediccionRespuesta(BaseModel):
    insumo: dict
    clientes_estimados: int
    demanda_base: float
    margen_seguridad: float
    margen_recomendado: float
    compra_sugerida: float
    unidad: str
    costo_estimado_mxn: float
    compra_tradicional: float
    costo_tradicional_mxn: float
    merma_evitada: float
    merma_evitada_mxn: float
    riesgo_desabasto: bool
    mensaje_riesgo: str | None
    importancia_variables: list[ImportanciaVariable]
    es_simulado: bool


class OptimizarMenuEntrada(BaseModel):
    horas_umbral: float = Field(24, gt=0, le=72, description="Insumos que caducan dentro de estas horas.")
    max_estrategias: int = Field(3, ge=1, le=5)
    usar_gemini: bool = True


class OptimizarMenuRespuesta(BaseModel):
    modo: Literal["gemini", "fallback"]
    motivo_fallback: str | None
    insumos_criticos: list[dict]
    estrategias: list[dict]
    totales: dict[str, float]
    es_simulado: bool


class AlertaEntrada(BaseModel):
    hora_actual: str = Field(..., examples=["15:00"], description="Formato HH:MM, dentro del servicio (09:00–20:00).")
    ritmo_ventas: Literal["lento", "normal", "rapido"] = "normal"
    platillo: str = Field("enchiladas_suizas", description="Clave del platillo a monitorear.")
    porciones_preparadas: int | None = Field(None, ge=0, description="Si se omite, se estima del historial.")
    porciones_vendidas: int | None = Field(None, ge=0, description="Si se da, el ritmo se mide con este dato.")
    usar_gemini: bool = True

    @field_validator("hora_actual")
    @classmethod
    def formato_hora(cls, v: str) -> str:
        try:
            alerta_excedente.hora_a_decimal(v)
        except Exception:
            raise ValueError("Usa el formato HH:MM, por ejemplo 15:00") from None
        return v


class AlertaRespuesta(BaseModel):
    modo: Literal["gemini", "fallback"]
    motivo_fallback: str | None
    alerta_id: int | None = None
    platillo: dict
    hora_actual: str
    ritmo: str
    factor_ritmo: float
    confianza: str
    proyeccion: dict
    alerta_activa: bool
    ficha: dict | None
    es_simulado: bool


class PuntoAuditoria(BaseModel):
    fecha: str
    compra_tradicional: float
    demanda_real: float
    compra_sugerida: float


class AuditoriaRespuesta(BaseModel):
    insumo: dict
    periodo: dict
    serie: list[PuntoAuditoria]
    totales: dict
    metodologia: str
    es_simulado: bool


# =============================================================================
# Utilidades de errores
# =============================================================================

def error_datos_no_listos(err: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"Datos o modelo no disponibles: {err}. "
                         "Corre `python data/generar_datos.py` y `python ml/modelo_demanda.py entrenar`.")


def conexion():
    if not db.RUTA_DB.exists():
        raise error_datos_no_listos(FileNotFoundError(str(db.RUTA_DB)))
    return db.sesion()


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/api/salud", tags=["Sistema"])
def salud():
    """Estado del servidor. Útil para comprobar que todo arrancó."""
    base = db.RUTA_DB.exists()
    origen = None
    if base:
        with db.sesion() as con:
            origen = db.origen_dataset(con)
    return {
        "estado": "ok" if base and db.RUTA_MODELO.exists() else "incompleto",
        "base_datos": base,
        "modelo_cargado": db.RUTA_MODELO.exists(),
        "gemini_configurado": bool(os.getenv("GEMINI_API_KEY")),
        "frontend": db.RUTA_FRONTEND.exists(),
        "origen_dato": origen,
        "es_simulado": bool(origen) and es_simulado(origen),
    }


@app.get("/api/catalogo", tags=["Sistema"])
def catalogo():
    """Insumos y platillos del menú vigente (para llenar selectores del frontend)."""
    with conexion() as con:
        insumos = [{k: f[k] for k in ("clave", "nombre", "categoria", "unidad", "precio_unitario_mxn", "vida_util_dias")}
                   for f in con.execute("SELECT * FROM insumos ORDER BY categoria, nombre")]
        platillos = [{k: p[k] for k in ("clave", "nombre", "categoria", "precio_venta_mxn", "costo_porcion_mxn", "receta")}
                     for p in db.platillos_con_recetas(con).values()]
        origen = db.origen_dataset(con)
    return {"insumos": insumos, "platillos": platillos, "es_simulado": es_simulado(origen)}


@app.get("/api/inventario", response_model=InventarioRespuesta, tags=["Vista 2 · Rescate en menú"])
def inventario(
    estado: Literal["CRITICO", "PRECAUCION", "OPTIMO"] | None = Query(None, description="Filtra por semáforo."),
    incluir_caducados: bool = Query(True, description="Incluir lotes ya vencidos."),
):
    """
    Lotes del almacén ordenados por horas restantes para caducar.
    Semáforo: CRITICO < 24 h · PRECAUCION ≤ 48 h · OPTIMO > 48 h.
    """
    momento = ahora()
    with conexion() as con:
        lotes = db.listar_lotes(con, momento)
        origen = db.origen_dataset(con)
    resumen = {e: sum(1 for l in lotes if l["estado"] == e) for e in ("CRITICO", "PRECAUCION", "OPTIMO")}
    resumen["caducados"] = sum(1 for l in lotes if l["caducado"])
    if estado:
        lotes = [l for l in lotes if l["estado"] == estado]
    if not incluir_caducados:
        lotes = [l for l in lotes if not l["caducado"]]
    advertencia = None
    if resumen["caducados"]:
        advertencia = (f"{resumen['caducados']} lote(s) ya caducaron. Para la demo, refresca el inventario con "
                       "`python data/generar_datos.py --solo-inventario` o reinicia el servidor.")
    return {
        "consultado_en": momento.replace(microsecond=0).isoformat(),
        "resumen": resumen,
        "lotes": [{**l, "insumo": l["nombre"]} for l in lotes],
        "advertencia": advertencia,
        "es_simulado": es_simulado(origen),
    }


@app.post("/api/predecir", response_model=PrediccionRespuesta, tags=["Vista 1 · Planeador de compras"])
def predecir(entrada: PrediccionEntrada):
    """
    Compra sugerida de un insumo con el modelo Random Forest (ml/modelo_rf.pkl).

    compra_sugerida = demanda_base × (1 + margen_seguridad) · riesgo_desabasto = margen < 4 %.
    La merma evitada compara el sobrante esperado de la compra tradicional típica de ese día
    contra el de la compra sugerida, ponderado por la fracción que caduca según la vida útil.
    """
    try:
        r = modelo_demanda.predecir_compra(
            entrada.insumo, entrada.dia_semana, entrada.es_quincena, entrada.lluvia, entrada.evento,
            entrada.margen_seguridad, entrada.temporada_vacacional, ruta_modelo=db.RUTA_MODELO)
    except FileNotFoundError as err:
        raise error_datos_no_listos(err) from err
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    with conexion() as con:
        info = con.execute("SELECT precio_unitario_mxn, vida_util_dias FROM insumos WHERE clave = ?",
                           (r["insumo"]["clave"],)).fetchone()
    precio, factor = info["precio_unitario_mxn"], generar_datos.factor_caducidad(info["vida_util_dias"])

    # Sobrante esperado = compra − demanda predicha; la merma es la parte que caduca.
    tradicional = r["compra_tradicional_referencia"]
    merma_trad = max(0.0, tradicional - r["demanda_base"]) * factor
    merma_zm = max(0.0, r["compra_sugerida"] - r["demanda_base"]) * factor
    merma_evitada = max(0.0, merma_trad - merma_zm)

    return {
        "insumo": r["insumo"],
        "clientes_estimados": r["comensales_estimados"],
        "demanda_base": r["demanda_base"],
        "margen_seguridad": entrada.margen_seguridad,
        "margen_recomendado": r["margen_recomendado"],
        "compra_sugerida": r["compra_sugerida"],
        "unidad": r["insumo"]["unidad"],
        "costo_estimado_mxn": r["inversion_mxn"],
        "compra_tradicional": tradicional,
        "costo_tradicional_mxn": round(tradicional * precio, 2),
        "merma_evitada": round(merma_evitada, 3),
        "merma_evitada_mxn": round(merma_evitada * precio, 2),
        "riesgo_desabasto": r["riesgo_desabasto"],
        "mensaje_riesgo": r["mensaje_riesgo"],
        "importancia_variables": r["importancia_variables"],
        "es_simulado": es_simulado(r["origen_dato"]),
    }


@app.post("/api/optimizar-menu", response_model=OptimizarMenuRespuesta, tags=["Vista 2 · Rescate en menú"])
def optimizar_menu(entrada: OptimizarMenuEntrada = OptimizarMenuEntrada()):
    """
    Cruza insumos vigentes que caducan dentro de `horas_umbral` con el recetario y propone
    promociones rentables SOLO sobre platillos del menú. Usa Gemini (Apartado 6) si está
    disponible; si no, reglas deterministas (`modo: fallback`). Las cifras siempre se
    recalculan en el backend.
    """
    with conexion() as con:
        r = rescate_menu.optimizar_menu(con, ahora(), entrada.horas_umbral, entrada.max_estrategias,
                                        entrada.usar_gemini)
    r["totales"] = {
        "perdida_evitable_mxn": round(sum(e["perdida_si_se_tira_mxn"] for e in r["estrategias"]), 2),
        "margen_recuperado_mxn": round(sum(e["margen_recuperado_mxn"] for e in r["estrategias"]), 2),
        "valor_critico_total_mxn": round(sum(c["valor_mxn"] for c in r["insumos_criticos"]), 2),
    }
    r["es_simulado"] = es_simulado(r.pop("origen_dato"))
    return r


@app.post("/api/alerta-excedente", response_model=AlertaRespuesta, tags=["Vista 3 · Alerta temprana"])
def alerta_excedente_endpoint(entrada: AlertaEntrada):
    """
    Proyecta las porciones que sobrarán al cierre (20:00) según la hora y el ritmo de ventas.
    Si sobran 3 porciones o más, genera la ficha de recolección temprana.
    """
    try:
        with conexion() as con:
            r = alerta_excedente.evaluar(con, ahora(), entrada.platillo, entrada.hora_actual,
                                         entrada.ritmo_ventas, entrada.porciones_preparadas,
                                         entrada.porciones_vendidas, entrada.usar_gemini)
    except KeyError as err:
        raise HTTPException(status_code=404, detail=f"Platillo no encontrado: {err.args[0]}") from err
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    r["es_simulado"] = es_simulado(r.pop("origen_dato"))
    return r


@app.post("/api/alerta-excedente/{alerta_id}/enviar", tags=["Vista 3 · Alerta temprana"])
def enviar_alerta(alerta_id: int):
    """Marca la ficha como enviada. El envío es SIMULADO: no se contacta a ningún servicio externo."""
    try:
        with conexion() as con:
            return alerta_excedente.marcar_enviada(con, alerta_id)
    except KeyError as err:
        raise HTTPException(status_code=404, detail=f"No existe la alerta {alerta_id}") from err


_CACHE_BACKTEST: dict = {}


@app.get("/api/auditoria", response_model=AuditoriaRespuesta, tags=["Vista 4 · Auditoría"])
def auditoria(
    dias: int = Query(7, ge=1, le=30, description="Últimos días cerrados a comparar."),
    insumo: str = Query("pollo", description="Insumo de la serie diaria (clave)."),
    margen: float | None = Query(None, ge=0, le=0.25, description="Margen fijo. Si se omite, el recomendado por insumo."),
):
    """
    Backtesting: compara, para los últimos `dias` cerrados, la compra tradicional, la demanda real
    y lo que habría sugerido ZeroMerma AI con un modelo entrenado SOLO con los días anteriores.
    Los totales suman los 46 insumos.
    """
    clave_cache = (dias, margen, db.RUTA_DB.stat().st_mtime if db.RUTA_DB.exists() else 0)
    try:
        if clave_cache not in _CACHE_BACKTEST:
            _CACHE_BACKTEST.clear()
            _CACHE_BACKTEST[clave_cache] = modelo_demanda.backtest(dias, margen, db.RUTA_DB, db.RUTA_MODELO)
        bt = _CACHE_BACKTEST[clave_cache]
    except FileNotFoundError as err:
        raise error_datos_no_listos(err) from err
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    claves = [i["clave"] for i in bt["insumos"]]
    if insumo not in claves:
        raise HTTPException(status_code=404, detail=f"Insumo no encontrado: {insumo}")
    j = claves.index(insumo)

    with conexion() as con:
        vida = {f["clave"]: f["vida_util_dias"] for f in con.execute("SELECT clave, vida_util_dias FROM insumos")}
    precios = np.array([i["precio_unitario_mxn"] for i in bt["insumos"]])
    factores = np.array([generar_datos.factor_caducidad(vida[c]) for c in claves])
    es_kg = np.array([i["unidad"] == "kg" for i in bt["insumos"]])
    real, trad, zm = bt["consumo_real"], bt["compra_tradicional"], bt["compra_sugerida"]

    def resumen(compra: np.ndarray) -> dict:
        merma = np.maximum(compra - real, 0) * factores          # lo que caduca y se tira
        faltante = np.maximum(real - compra, 0)
        return {
            "compra_mxn": round(float((compra * precios).sum()), 2),
            "merma_kg": round(float(merma[:, es_kg].sum()), 2),
            "merma_mxn": round(float((merma * precios).sum()), 2),
            "demanda_no_cubierta_pct": round(float((faltante * precios).sum() / (real * precios).sum() * 100), 2),
        }

    t, z = resumen(trad), resumen(zm)
    reduccion = (z["merma_mxn"] - t["merma_mxn"]) / t["merma_mxn"] * 100 if t["merma_mxn"] else 0.0
    info = bt["insumos"][j]
    return {
        "insumo": {"clave": info["clave"], "nombre": info["nombre"], "unidad": info["unidad"],
                   "margen_aplicado": round(float(bt["margenes"][j]), 3)},
        "periodo": {"desde": bt["fechas"][0], "hasta": bt["fechas"][-1], "dias": dias,
                    "modelo_entrenado_hasta": bt["entrenado_hasta"]},
        "serie": [{"fecha": f, "compra_tradicional": round(float(trad[k, j]), 2),
                   "demanda_real": round(float(real[k, j]), 2), "compra_sugerida": round(float(zm[k, j]), 2)}
                  for k, f in enumerate(bt["fechas"])],
        "totales": {
            "tradicional": t,
            "zeromerma": z,
            "ahorro_compra_mxn": round(t["compra_mxn"] - z["compra_mxn"], 2),
            "merma_evitada_kg": round(t["merma_kg"] - z["merma_kg"], 2),
            "merma_evitada_mxn": round(t["merma_mxn"] - z["merma_mxn"], 2),
            "reduccion_merma_pct": round(reduccion, 1),
        },
        "metodologia": ("Modelo reentrenado solo con días anteriores al periodo (sin fuga de datos). "
                        "Merma = sobrante × fracción que caduca según la vida útil del insumo. "
                        "kg solo suma insumos medidos en kg. Precios SIMULADOS."),
        "es_simulado": es_simulado(bt["origen_dato"]),
    }


# =============================================================================
# Frontend estático en "/"  (se monta al final para no tapar las rutas /api)
# =============================================================================

if db.RUTA_FRONTEND.exists():
    app.mount("/", StaticFiles(directory=db.RUTA_FRONTEND, html=True), name="frontend")
else:
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def sin_frontend():
        return ("<!doctype html><meta charset='utf-8'><title>ZeroMerma AI</title>"
                "<body style='font-family:system-ui;max-width:40rem;margin:3rem auto;padding:0 1rem'>"
                "<h1>ZeroMerma AI · API en línea</h1>"
                "<p>La carpeta <code>/frontend</code> aún no existe (Apartado 5).</p>"
                "<p>Prueba la API en <a href='/docs'>/docs</a>. Datos SIMULADOS.</p></body>")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8000")), reload=False)
