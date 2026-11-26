"""
Pruebas de la API (Apartado 4).
Ejecutar desde la raíz del repo:
    python -m unittest discover -s tests -v
Usa una base y un modelo temporales: no toca data/restaurante.db ni ml/modelo_rf.pkl.
"""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

_TMP = tempfile.TemporaryDirectory()
os.environ["ZEROMERMA_DB"] = str(Path(_TMP.name) / "restaurante.db")
os.environ["ZEROMERMA_MODELO"] = str(Path(_TMP.name) / "modelo_rf.pkl")

from fastapi.testclient import TestClient  # noqa: E402

from backend import database as db  # noqa: E402
from backend.main import app  # noqa: E402
from backend.services import rescate_menu  # noqa: E402

GEMINI = "backend.services.gemini_service"


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cliente = TestClient(app)
        cls.cliente.__enter__()  # dispara el arranque: genera datos y entrena el modelo

    @classmethod
    def tearDownClass(cls):
        cls.cliente.__exit__(None, None, None)
        sys.modules.pop(GEMINI, None)

    def tearDown(self):
        sys.modules.pop(GEMINI, None)

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
        self.assertEqual(len(d["importancia_variables"]), 5)

    def test_predecir_alerta_desabasto(self):
        d = self.cliente.post("/api/predecir", json={"insumo": "crema", "dia_semana": 1,
                                                      "margen_seguridad": 0.02}).json()
        self.assertTrue(d["riesgo_desabasto"])
        self.assertIsNotNone(d["mensaje_riesgo"])

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
        falso = types.ModuleType(GEMINI)
        falso.proponer_promociones = lambda **kw: [{"platillo_clave": "enchiladas_suizas", "descuento_pct": 20,
                                                    "tipo": "descuento", "copy_promocional": "Texto de prueba",
                                                    "margen_recuperado_mxn": 999999}]
        sys.modules[GEMINI] = falso
        d = self.cliente.post("/api/optimizar-menu", json={"max_estrategias": 1}).json()
        self.assertEqual(d["modo"], "gemini")
        e = d["estrategias"][0]
        self.assertEqual(e["copy_promocional"], "Texto de prueba")
        self.assertNotEqual(e["margen_recuperado_mxn"], 999999)      # la cifra la recalcula el backend
        self.assertEqual(e["precio_oferta_mxn"], 96)

    def test_optimizar_menu_rechaza_platillo_inventado(self):
        falso = types.ModuleType(GEMINI)
        falso.proponer_promociones = lambda **kw: [{"platillo_clave": "sushi_de_pollo", "descuento_pct": 20}]
        sys.modules[GEMINI] = falso
        d = self.cliente.post("/api/optimizar-menu", json={}).json()
        self.assertEqual(d["modo"], "fallback")
        self.assertIn("no está en el menú", d["motivo_fallback"])

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
        self.assertEqual(d["ficha"]["ventana_recoleccion"]["inicio"], "16:30")
        self.assertTrue(d["ficha"]["mensaje"])
        enviada = self.cliente.post(f"/api/alerta-excedente/{d['alerta_id']}/enviar").json()
        self.assertTrue(enviada["envio_simulado"])

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
