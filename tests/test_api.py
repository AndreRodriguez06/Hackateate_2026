"""
Pruebas de la API (Apartado 4).
Ejecutar desde la raíz del repo:
    python -m unittest discover -s tests -v
Usa una base y un modelo temporales: no toca data/restaurante.db ni ml/modelo_rf.pkl.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_TMP = tempfile.TemporaryDirectory()
os.environ["ZEROMERMA_DB"] = str(Path(_TMP.name) / "restaurante.db")
os.environ["ZEROMERMA_MODELO"] = str(Path(_TMP.name) / "modelo_rf.pkl")
os.environ["GEMINI_API_KEY"] = ""   # las pruebas nunca llaman a la API real, aunque exista un .env

from fastapi.testclient import TestClient  # noqa: E402

from backend import database as db  # noqa: E402
from backend import gemini_service  # noqa: E402
from backend.main import app  # noqa: E402
from backend.services import rescate_menu  # noqa: E402



def gemini_falso(*promociones):
    """Sustituye la llamada real a Gemini por una respuesta fija (no usa red ni llave)."""
    respuesta = gemini_service.RespuestaPromociones(promociones=[gemini_service.PromocionGemini(**p) for p in promociones])
    return mock.patch.object(gemini_service, "_generar", return_value=respuesta)


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cliente = TestClient(app)
        cls.cliente.__enter__()  # dispara el arranque: genera datos y entrena el modelo

    @classmethod
    def tearDownClass(cls):
        cls.cliente.__exit__(None, None, None)

    # --- Arranque ---
    def test_arranque_prepara_datos_y_modelo(self):
        r = self.cliente.get("/api/salud").json()
        self.assertEqual(r["estado"], "ok")
        self.assertTrue(r["es_simulado"])

    # --- Inventario ---
    def test_inventario_ordenado_con_semaforo(self):
        r = self.cliente.get("/api/inventario").json()
        horas = [l["horas_restantes"] for l in r["lotes"]]
        self.assertEqual(horas, sorted(horas))
        for l in r["lotes"]:
            esperado = "CRITICO" if l["horas_restantes"] < 24 else "PRECAUCION" if l["horas_restantes"] <= 48 else "OPTIMO"
            self.assertEqual(l["estado"], esperado)
            self.assertTrue(l["es_simulado"])
        self.assertGreaterEqual(r["resumen"]["CRITICO"], 2)

    def test_inventario_filtra_por_estado(self):
        r = self.cliente.get("/api/inventario", params={"estado": "CRITICO"}).json()
        self.assertTrue(r["lotes"])
        self.assertTrue(all(l["estado"] == "CRITICO" for l in r["lotes"]))

    # --- Predicción ---
    def test_predecir(self):
        r = self.cliente.post("/api/predecir", json={"insumo": "pollo", "dia_semana": 4, "es_quincena": True,
                                                      "lluvia": False, "evento": False, "margen_seguridad": 0.10})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertAlmostEqual(d["compra_sugerida"], d["demanda_base"] * 1.10, delta=0.02)
        self.assertFalse(d["riesgo_desabasto"])
        self.assertGreaterEqual(d["merma_evitada_mxn"], 0)
        self.assertTrue(d["es_simulado"])
        self.assertEqual(len(d["importancia_variables"]), 7)

    def test_predecir_alerta_desabasto(self):
        d = self.cliente.post("/api/predecir", json={"insumo": "crema", "dia_semana": 1,
                                                      "margen_seguridad": 0.02}).json()
        self.assertTrue(d["riesgo_desabasto"])
        self.assertIsNotNone(d["mensaje_riesgo"])

    def test_predecir_con_calendario(self):
        d = self.cliente.post("/api/predecir", json={"insumo": "pollo", "dia_semana": 5, "es_dia_festivo": True,
                                                      "evento_plaza": True, "epoca": "navidena"})
        self.assertEqual(d.status_code, 200)
        self.assertEqual(self.cliente.post("/api/predecir", json={"insumo": "pollo", "dia_semana": 1,
                                                                  "epoca": "vacaciones"}).status_code, 422)

    def test_predecir_errores(self):
        self.assertEqual(self.cliente.post("/api/predecir", json={"insumo": "pollo", "dia_semana": 9}).status_code, 422)
        self.assertEqual(self.cliente.post("/api/predecir", json={"insumo": "pollo", "dia_semana": 1,
                                                                  "margen_seguridad": 0.5}).status_code, 422)
        self.assertEqual(self.cliente.post("/api/predecir", json={"insumo": "caviar", "dia_semana": 1}).status_code, 400)

    # --- Optimizar menú ---
    def test_optimizar_menu_fallback(self):
        d = self.cliente.post("/api/optimizar-menu", json={}).json()
        self.assertEqual(d["modo"], "fallback")
        self.assertTrue(d["estrategias"])
        with db.sesion() as con:
            menu = db.platillos_con_recetas(con)
        criticos = {c["clave"] for c in d["insumos_criticos"]}
        for e in d["estrategias"]:
            self.assertIn(e["platillo_clave"], menu)                      # solo platillos existentes
            self.assertTrue(criticos & set(menu[e["platillo_clave"]]["receta"]))
            self.assertGreaterEqual(e["precio_oferta_mxn"], 1.5 * e["costo_insumos_porcion_mxn"])

    def test_optimizar_menu_con_gemini_valido(self):
        with gemini_falso({"platillo_clave": "enchiladas_suizas", "descuento_pct": 20,
                           "insumos_criticos_usados": ["inventado"], "justificacion": "Usa pollo y crema.",
                           "copy_promocional": "Texto de prueba"}):
            d = self.cliente.post("/api/optimizar-menu", json={"max_estrategias": 1}).json()
        self.assertEqual(d["modo"], "gemini")
        e = d["estrategias"][0]
        self.assertEqual(e["copy_promocional"], "Texto de prueba")
        self.assertEqual(e["justificacion"], "Usa pollo y crema.")
        self.assertEqual(e["precio_oferta_mxn"], 96)                       # 120 × (1 − 20 %)
        self.assertTrue(all(r["clave"] != "inventado" for r in e["insumos_rescatados"]))  # cifras del backend

    def test_optimizar_menu_rechaza_platillo_inventado(self):
        with gemini_falso({"platillo_clave": "sushi_de_pollo", "descuento_pct": 20, "insumos_criticos_usados": [],
                           "justificacion": "x", "copy_promocional": "x"}):
            d = self.cliente.post("/api/optimizar-menu", json={}).json()
        self.assertEqual(d["modo"], "fallback")
        self.assertIn("fuera del menú", d["motivo_fallback"])
        self.assertTrue(d["estrategias"])                                   # la demo sigue funcionando

    def test_optimizar_menu_sin_llave_usa_respaldo(self):
        d = self.cliente.post("/api/optimizar-menu", json={}).json()
        self.assertEqual(d["modo"], "fallback")
        self.assertIn("GEMINI_API_KEY", d["motivo_fallback"])

    def test_validacion_rechaza_descuento_no_rentable(self):
        platillo = {"clave": "x", "nombre": "X", "categoria": "plato fuerte", "precio_venta_mxn": 100.0,
                    "costo_porcion_mxn": 60.0, "receta": {"pollo": 0.2}}
        insumos = {"pollo": {"nombre": "Pollo", "unidad": "kg", "precio_unitario_mxn": 135.0}}
        with self.assertRaises(ValueError):
            rescate_menu.validar_propuestas([{"platillo_clave": "x", "descuento_pct": 30}],
                                            {"x": platillo}, {"pollo": 5.0}, insumos, {}, 3)

    # --- Alerta de excedentes ---
    def test_alerta_con_ventas_lentas_genera_ficha(self):
        d = self.cliente.post("/api/alerta-excedente", json={"hora_actual": "15:00", "ritmo_ventas": "lento",
                                                              "porciones_preparadas": 40}).json()
        self.assertTrue(d["alerta_activa"])
        self.assertGreaterEqual(d["proyeccion"]["porciones_sobrantes"], 3)
        self.assertEqual(d["ficha"]["ventana_recoleccion"]["inicio"], "16:00")
        self.assertEqual(d["ficha"]["ventana_recoleccion"]["fin"], "18:00")       # 2 h antes del cierre
        self.assertGreaterEqual(len(d["ficha"]["recomendaciones_inocuidad"]), 2)
        self.assertTrue(d["ficha"]["mensaje"])
        enviada = self.cliente.post(f"/api/alerta-excedente/{d['alerta_id']}/enviar").json()
        self.assertTrue(enviada["envio_simulado"])

    def test_alerta_tarde_sin_ventana_viable(self):
        d = self.cliente.post("/api/alerta-excedente", json={"hora_actual": "17:45", "ritmo_ventas": "lento",
                                                              "porciones_preparadas": 40}).json()
        self.assertTrue(d["alerta_activa"])
        self.assertFalse(d["ventana_viable"])
        self.assertIsNone(d["ficha"])
        self.assertIn("18:00", d["motivo_sin_ficha"])

    def test_alerta_solo_proyeccion_no_registra(self):
        d = self.cliente.post("/api/alerta-excedente", json={"hora_actual": "15:00", "ritmo_ventas": "lento",
                                                              "porciones_preparadas": 40, "generar_ficha": False}).json()
        self.assertTrue(d["alerta_activa"])
        self.assertIsNone(d["ficha"])
        self.assertIsNone(d["alerta_id"])

    def test_alerta_sin_sobrante_no_genera_ficha(self):
        d = self.cliente.post("/api/alerta-excedente", json={"hora_actual": "15:00", "ritmo_ventas": "rapido",
                                                              "porciones_preparadas": 1}).json()
        self.assertFalse(d["alerta_activa"])
        self.assertIsNone(d["ficha"])
        self.assertIsNotNone(d["proyeccion"]["hora_agotamiento_estimada"])

    def test_alerta_errores(self):
        self.assertEqual(self.cliente.post("/api/alerta-excedente", json={"hora_actual": "25:00"}).status_code, 422)
        self.assertEqual(self.cliente.post("/api/alerta-excedente", json={"hora_actual": "07:00"}).status_code, 400)
        self.assertEqual(self.cliente.post("/api/alerta-excedente",
                                           json={"hora_actual": "15:00", "platillo": "caviar"}).status_code, 404)

    # --- Historial de compras ---
    def test_historial_por_mes_todos(self):
        d = self.cliente.get("/api/historial-compras", params={"agrupar": "mes"}).json()
        self.assertEqual(d["unidad"], "MXN")
        self.assertIsNone(d["serie"][0]["compra_sugerida"])                    # primeros días: sin predicción
        self.assertIsNotNone(d["serie"][-1]["compra_sugerida"])
        t = d["totales"]
        self.assertAlmostEqual(t["ahorro_compra_mxn"], t["compra_tradicional_mxn"] - t["compra_sugerida_mxn"], 1)
        self.assertEqual(sum(f["dias"] for f in d["serie"]), d["periodo"]["dias"])
        self.assertTrue(d["es_simulado"])

    def test_historial_por_dia_un_producto(self):
        d = self.cliente.get("/api/historial-compras", params={"agrupar": "dia", "insumo": "pollo"}).json()
        self.assertEqual(d["unidad"], "kg")
        self.assertEqual(len(d["serie"]), d["periodo"]["dias"])
        self.assertEqual(self.cliente.get("/api/historial-compras", params={"insumo": "caviar"}).status_code, 404)
        self.assertEqual(self.cliente.get("/api/historial-compras", params={"agrupar": "anio"}).status_code, 422)

    # --- Auditoría ---
    def test_auditoria_ultimos_7_dias(self):
        d = self.cliente.get("/api/auditoria").json()
        self.assertEqual(len(d["serie"]), 7)
        self.assertLess(d["periodo"]["modelo_entrenado_hasta"], d["periodo"]["desde"])  # sin fuga de datos
        t = d["totales"]
        self.assertAlmostEqual(t["merma_evitada_mxn"], t["tradicional"]["merma_mxn"] - t["zeromerma"]["merma_mxn"], 1)
        self.assertTrue(d["es_simulado"])


if __name__ == "__main__":
    unittest.main()
