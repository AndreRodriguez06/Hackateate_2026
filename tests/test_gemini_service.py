"""
Pruebas de la integración con Gemini (Apartado 6).
Ejecutar desde la raíz del repo:
    python -m unittest discover -s tests -v

NO llaman a la API real de Google: sustituyen la respuesta del modelo con objetos fijos.
Comprueban la forma de la llamada al SDK, la validación de reglas de negocio y el modo respaldo.
"""
import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ["GEMINI_API_KEY"] = ""   # nunca usar una llave real en pruebas

from backend import gemini_service as gs  # noqa: E402

CRITICOS = [
    {"clave": "pollo", "nombre": "Pechuga de pollo", "cantidad": 7.5, "unidad": "kg", "costo_unitario_mxn": 135.0,
     "horas_restantes": 18.0},
    {"clave": "crema", "nombre": "Crema ácida", "cantidad": 4.0, "unidad": "L", "costo_unitario_mxn": 72.0,
     "horas_restantes": 22.0},
]
MENU = [
    {"clave": "enchiladas_suizas", "nombre": "Enchiladas Suizas", "categoria": "plato fuerte",
     "precio_venta_mxn": 120.0, "costo_porcion_mxn": 44.55,
     "receta": {"pollo": 0.18, "crema": 0.06, "tortilla": 0.12}},
    {"clave": "quesadillas", "nombre": "Quesadillas", "categoria": "plato fuerte",
     "precio_venta_mxn": 80.0, "costo_porcion_mxn": 20.0, "receta": {"tortilla": 0.12, "queso": 0.08, "crema": 0.02}},
    {"clave": "caro", "nombre": "Platillo caro", "categoria": "plato fuerte",       # costo alto: sin descuento rentable
     "precio_venta_mxn": 100.0, "costo_porcion_mxn": 62.0, "receta": {"pollo": 0.3}},
    {"clave": "cafe", "nombre": "Café", "categoria": "bebida", "precio_venta_mxn": 35.0, "costo_porcion_mxn": 4.0,
     "receta": {"cafe": 0.012}},                                                    # no usa insumos críticos
]
EXCEDENTE = {"producto": "Enchiladas Suizas", "porciones": 6, "cantidad_aprox_kg": 3.2, "requiere_refrigeracion": True}


def promos(*items):
    return gs.RespuestaPromociones(promociones=[gs.PromocionGemini(**{
        "insumos_criticos_usados": [], "justificacion": "j", "copy_promocional": "Copy", **i}) for i in items])


def ficha(**cambios):
    base = {"producto": "Enchiladas Suizas", "porciones": 6, "ventana_inicio": "16:15", "ventana_limite": "17:45",
            "recomendaciones_inocuidad": ["Refrigerar a 4 °C.", "Consumir hoy."], "mensaje": "Hola, ..."}
    return gs.FichaGemini(**{**base, **cambios})


class TestPromociones(unittest.TestCase):
    def test_candidatos_solo_platillos_del_menu_con_criticos_y_rentables(self):
        c = gs._candidatos(CRITICOS, MENU)
        self.assertEqual(set(c), {"enchiladas_suizas", "quesadillas"})
        self.assertEqual(c["enchiladas_suizas"]["descuento_maximo_rentable_pct"], 30)
        self.assertNotIn("caro", c)  # 100 × 0.9 = 90 < 1.5 × 62 = 93

    def test_sin_llave_devuelve_respaldo_estructurado(self):
        r = gs.generar_promociones_menu(CRITICOS, MENU)
        self.assertTrue(r["modo_respaldo"])
        self.assertIn("GEMINI_API_KEY", r["motivo_respaldo"])
        self.assertTrue(r["promociones"])
        for p in r["promociones"]:
            self.assertGreaterEqual(p["precio_oferta_mxn"], 1.5 * p["costo_porcion_mxn"])
            self.assertTrue(p["copy_promocional"])

    def test_respuesta_valida_de_gemini(self):
        with mock.patch.object(gs, "_generar", return_value=promos(
                {"platillo_clave": "enchiladas_suizas", "descuento_pct": 25, "insumos_criticos_usados": ["caviar"]})):
            r = gs.generar_promociones_menu(CRITICOS, MENU, max_promociones=1)
        self.assertFalse(r["modo_respaldo"])
        p = r["promociones"][0]
        self.assertEqual(p["precio_oferta_mxn"], 90)
        self.assertEqual(p["insumos_criticos_usados"], ["pollo", "crema"])  # de la receta, no del modelo

    def test_rechaza_platillo_inventado(self):
        with mock.patch.object(gs, "_generar", return_value=promos({"platillo_clave": "sushi", "descuento_pct": 20})):
            r = gs.generar_promociones_menu(CRITICOS, MENU)
        self.assertTrue(r["modo_respaldo"])
        self.assertIn("fuera del menú", r["motivo_respaldo"])

    def test_rechaza_platillo_sin_insumos_criticos(self):
        with mock.patch.object(gs, "_generar", return_value=promos({"platillo_clave": "cafe", "descuento_pct": 20})):
            self.assertTrue(gs.generar_promociones_menu(CRITICOS, MENU)["modo_respaldo"])

    def test_rechaza_descuento_por_encima_del_rentable(self):
        menu = [{**MENU[0], "costo_porcion_mxn": 60.0}]  # máximo rentable: 25 %
        with mock.patch.object(gs, "_generar", return_value=promos({"platillo_clave": "enchiladas_suizas",
                                                                    "descuento_pct": 30})):
            r = gs.generar_promociones_menu(CRITICOS, menu)
        self.assertTrue(r["modo_respaldo"])
        self.assertIn("rango rentable", r["motivo_respaldo"])

    def test_rechaza_copy_con_precio_equivocado(self):
        with mock.patch.object(gs, "_generar", return_value=promos({"platillo_clave": "enchiladas_suizas", "descuento_pct": 25,
                                                                    "copy_promocional": "Hoy a solo $85"})):
            r = gs.generar_promociones_menu(CRITICOS, MENU)
        self.assertTrue(r["modo_respaldo"])
        self.assertIn("la oferta es $90", r["motivo_respaldo"])

    def test_acepta_copy_con_precio_correcto(self):
        with mock.patch.object(gs, "_generar", return_value=promos({"platillo_clave": "enchiladas_suizas", "descuento_pct": 25,
                                                                    "copy_promocional": "Hoy a solo $90"})):
            self.assertFalse(gs.generar_promociones_menu(CRITICOS, MENU)["modo_respaldo"])

    def test_rechaza_platillo_repetido(self):
        with mock.patch.object(gs, "_generar", return_value=promos({"platillo_clave": "quesadillas", "descuento_pct": 20},
                                                                   {"platillo_clave": "quesadillas", "descuento_pct": 10})):
            self.assertTrue(gs.generar_promociones_menu(CRITICOS, MENU)["modo_respaldo"])

    def test_falla_de_red_no_rompe(self):
        with mock.patch.object(gs, "_generar", side_effect=TimeoutError("sin internet")):
            r = gs.generar_promociones_menu(CRITICOS, MENU)
        self.assertTrue(r["modo_respaldo"])
        self.assertIn("TimeoutError", r["motivo_respaldo"])
        self.assertTrue(r["promociones"])

    def test_esquema_limita_descuento(self):
        with self.assertRaises(Exception):
            gs.PromocionGemini(platillo_clave="x", descuento_pct=60, insumos_criticos_usados=[], justificacion="",
                               copy_promocional="x")


class TestFicha(unittest.TestCase):
    def test_sin_llave_respaldo_con_ventana_2h_antes_del_cierre(self):
        r = gs.generar_alerta_recoleccion(EXCEDENTE, "15:00")
        self.assertTrue(r["modo_respaldo"])
        f = r["ficha"]
        self.assertEqual(f["porciones"], 6)
        self.assertEqual((f["ventana_inicio"], f["ventana_limite"]), ("16:00", "18:00"))
        self.assertGreaterEqual(f["horas_antes_del_cierre"], 2)
        self.assertTrue(any("4 °C" in x for x in f["recomendaciones_inocuidad"]))

    def test_respuesta_valida_de_gemini(self):
        with mock.patch.object(gs, "_generar", return_value=ficha()):
            r = gs.generar_alerta_recoleccion(EXCEDENTE, "15:00")
        self.assertFalse(r["modo_respaldo"])
        self.assertEqual(r["ficha"]["ventana_limite"], "17:45")
        self.assertEqual(r["ficha"]["horas_antes_del_cierre"], 2.25)

    def test_rechaza_porciones_cambiadas(self):
        with mock.patch.object(gs, "_generar", return_value=ficha(porciones=10)):
            r = gs.generar_alerta_recoleccion(EXCEDENTE, "15:00")
        self.assertTrue(r["modo_respaldo"])
        self.assertEqual(r["ficha"]["porciones"], 6)

    def test_rechaza_ventana_despues_del_limite(self):
        with mock.patch.object(gs, "_generar", return_value=ficha(ventana_limite="19:00")):
            self.assertTrue(gs.generar_alerta_recoleccion(EXCEDENTE, "15:00")["modo_respaldo"])

    def test_sin_ventana_viable_no_hay_ficha(self):
        r = gs.generar_alerta_recoleccion(EXCEDENTE, "17:45")
        self.assertIsNone(r["ficha"])
        self.assertIn("18:00", r["motivo_sin_ficha"])


class TestLlamadaAlSDK(unittest.TestCase):
    """Verifica la forma de la llamada a google-genai con un cliente falso (sin red)."""

    def test_structured_output_con_esquema_pydantic(self):
        esperado = promos({"platillo_clave": "quesadillas", "descuento_pct": 20})
        modelos = mock.Mock()
        modelos.generate_content.return_value = SimpleNamespace(parsed=esperado, text=esperado.model_dump_json())
        with mock.patch.object(gs, "_cliente", return_value=SimpleNamespace(models=modelos)):
            r = gs.generar_promociones_menu(CRITICOS, MENU)
        self.assertFalse(r["modo_respaldo"])
        kwargs = modelos.generate_content.call_args.kwargs
        self.assertEqual(kwargs["model"], "gemini-2.5-flash")
        cfg = kwargs["config"]
        self.assertEqual(cfg.response_mime_type, "application/json")
        self.assertIs(cfg.response_schema, gs.RespuestaPromociones)
        self.assertIn("No conversas", cfg.system_instruction)
        self.assertIn("platillos_candidatos", kwargs["contents"])

    def test_si_parsed_viene_vacio_usa_el_texto_json(self):
        texto = ficha().model_dump_json()
        modelos = mock.Mock()
        modelos.generate_content.return_value = SimpleNamespace(parsed=None, text=texto)
        with mock.patch.object(gs, "_cliente", return_value=SimpleNamespace(models=modelos)):
            self.assertFalse(gs.generar_alerta_recoleccion(EXCEDENTE, "15:00")["modo_respaldo"])

    def test_json_invalido_activa_respaldo(self):
        modelos = mock.Mock()
        modelos.generate_content.return_value = SimpleNamespace(parsed=None, text="esto no es json")
        with mock.patch.object(gs, "_cliente", return_value=SimpleNamespace(models=modelos)):
            self.assertTrue(gs.generar_alerta_recoleccion(EXCEDENTE, "15:00")["modo_respaldo"])


if __name__ == "__main__":
    unittest.main()
