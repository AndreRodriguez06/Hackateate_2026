#!/usr/bin/env python3
"""
ZeroMerma AI — Prueba de humo end-to-end contra el servidor encendido
Archivo: /scripts/prueba_humo.py

Recorre el flujo completo por HTTP, igual que el navegador:
frontend → inventario → predicción (caso normal y borde de desabasto) → promociones →
alerta de excedentes → envío → auditoría.

Solo usa la librería estándar. Uso (con el servidor corriendo en otra terminal):
    python scripts/prueba_humo.py                       # http://localhost:8000
    python scripts/prueba_humo.py http://127.0.0.1:8001

Termina con código 0 si todo pasa y 1 si algo falla.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
resultados: list[tuple[str, bool, str]] = []


def llamar(metodo: str, ruta: str, cuerpo: dict | None = None) -> tuple[int, dict | str]:
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(BASE + ruta, data=datos, method=metodo,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            texto = r.read().decode("utf-8")
            return r.status, json.loads(texto) if "json" in r.headers.get("Content-Type", "") else texto
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def caso(nombre: str):
    def decorador(funcion):
        inicio = time.perf_counter()
        try:
            detalle = funcion() or ""
            resultados.append((nombre, True, f"{detalle} ({(time.perf_counter() - inicio) * 1000:.0f} ms)"))
        except AssertionError as e:
            resultados.append((nombre, False, str(e)))
        except Exception as e:  # el servidor no responde, JSON inesperado...
            resultados.append((nombre, False, f"{type(e).__name__}: {e}"))
        return funcion
    return decorador


@caso("01 Servidor y datos SIMULADOS listos")
def _():
    st, r = llamar("GET", "/api/salud")
    assert st == 200 and r["estado"] == "ok", f"salud: {st} {r}"
    assert r["es_simulado"], "el dataset debería estar etiquetado SIMULADO"
    return f"Gemini configurado: {r['gemini_configurado']}"


@caso("02 Frontend servido en /")
def _():
    st, html = llamar("GET", "/")
    assert st == 200 and "Datos Simulados" in html, "no se encontró el distintivo de datos simulados"
    return "index.html con distintivo"


@caso("03 Inventario con semáforo y lotes críticos")
def _():
    st, r = llamar("GET", "/api/inventario")
    assert st == 200, st
    assert r["resumen"]["CRITICO"] >= 2, f"se esperaban ≥ 2 críticos: {r['resumen']}"
    horas = [l["horas_restantes"] for l in r["lotes"]]
    assert horas == sorted(horas), "no está ordenado por horas restantes"
    return f"{r['resumen']['CRITICO']} críticos de {len(r['lotes'])} lotes"


@caso("04 Happy path: predicción viernes de quincena con lluvia, margen 8 %")
def _():
    st, r = llamar("POST", "/api/predecir", {"insumo": "pollo", "dia_semana": 4, "es_quincena": True,
                                              "lluvia": True, "evento": False, "margen_seguridad": 0.08})
    assert st == 200, f"{st} {r}"
    assert abs(r["compra_sugerida"] - r["demanda_base"] * 1.08) < 0.02, "no cumple demanda × (1 + margen)"
    assert r["riesgo_desabasto"] is False and r["es_simulado"]
    return (f"{r['clientes_estimados']} clientes, compra {r['compra_sugerida']} kg, "
            f"${r['costo_estimado_mxn']:,.0f}, merma evitada ${r['merma_evitada_mxn']:,.0f}")


@caso("05 Borde de desabasto: margen 3.9 % alerta, 4 % no")
def _():
    base = {"insumo": "pollo", "dia_semana": 4, "es_quincena": True, "lluvia": True, "evento": False}
    _, bajo = llamar("POST", "/api/predecir", {**base, "margen_seguridad": 0.039})
    _, justo = llamar("POST", "/api/predecir", {**base, "margen_seguridad": 0.04})
    assert bajo["riesgo_desabasto"] is True and bajo["mensaje_riesgo"], "3.9 % debería alertar"
    assert justo["riesgo_desabasto"] is False, "4 % no debería alertar"
    st, _ = llamar("POST", "/api/predecir", {**base, "margen_seguridad": 0.30})
    assert st == 422, f"margen 30 % debería rechazarse con 422, llegó {st}"
    return "3.9 % → alerta · 4 % → sin alerta · 30 % → 422"


@caso("06 Promociones sobre platillos existentes y rentables")
def _():
    st, r = llamar("POST", "/api/optimizar-menu", {})
    assert st == 200 and r["estrategias"], f"{st} {r}"
    _, cat = llamar("GET", "/api/catalogo")
    menu = {p["clave"] for p in cat["platillos"]}
    for e in r["estrategias"]:
        assert e["platillo_clave"] in menu, f"platillo fuera del menú: {e['platillo_clave']}"
        assert e["precio_oferta_mxn"] >= 1.5 * e["costo_insumos_porcion_mxn"], f"no rentable: {e['platillo']}"
    return f"modo {r['modo']} ({r['motivo_fallback'] or 'Gemini'}) · " + ", ".join(e["platillo"] for e in r["estrategias"])


@caso("07 Alerta temprana: ritmo lento a las 15:00 genera ficha")
def _():
    st, r = llamar("POST", "/api/alerta-excedente", {"hora_actual": "15:00", "ritmo_ventas": "lento",
                                                      "porciones_preparadas": 20})
    assert st == 200 and r["alerta_activa"] and r["ficha"], f"{st} {r}"
    v = r["ficha"]["ventana_recoleccion"]
    assert v["horas_antes_del_cierre"] >= 2, f"la ventana debe cerrar ≥ 2 h antes: {v}"
    st2, env = llamar("POST", f"/api/alerta-excedente/{r['alerta_id']}/enviar")
    assert st2 == 200 and env["envio_simulado"], "el envío debería registrarse como SIMULADO"
    return f"{r['ficha']['porciones']} porciones, {v['inicio']}–{v['fin']}, modo {r['modo']}"


@caso("08 Auditoría de 7 días sin fuga de datos")
def _():
    st, r = llamar("GET", "/api/auditoria?dias=7&insumo=pollo")
    assert st == 200 and len(r["serie"]) == 7, f"{st} {r}"
    assert r["periodo"]["modelo_entrenado_hasta"] < r["periodo"]["desde"], "el modelo vio los días evaluados"
    t = r["totales"]
    return f"merma {t['reduccion_merma_pct']} %, {t['merma_evitada_kg']} kg, ${t['merma_evitada_mxn']:,.0f}"


@caso("09 Historial de compras por mes (todos los productos y uno)")
def _():
    st, r = llamar("GET", "/api/historial-compras?agrupar=mes")
    assert st == 200 and r["unidad"] == "MXN", f"{st} {r}"
    assert r["serie"][0]["compra_sugerida"] is None, "los primeros días no deben tener predicción"
    t = r["totales"]
    st2, p = llamar("GET", "/api/historial-compras?agrupar=semana&insumo=pollo")
    assert st2 == 200 and p["unidad"] == "kg", f"{st2}"
    return (f"{len(r['serie'])} meses · ahorro en compras ${t['ahorro_compra_mxn']:,.0f} · merma {t['reduccion_merma_pct']} % · "
            f"pollo: {len(p['serie'])} semanas")


if __name__ == "__main__":
    print(f"Prueba de humo contra {BASE}\n")
    for nombre, ok, detalle in resultados:
        print(f"{'PASA ' if ok else 'FALLA'}  {nombre}\n       {detalle}")
    fallas = sum(1 for _, ok, _ in resultados if not ok)
    print(f"\n{len(resultados) - fallas}/{len(resultados)} casos pasaron.")
    sys.exit(1 if fallas else 0)
