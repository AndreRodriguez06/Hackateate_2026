"""
Pruebas del modelo de demanda (Apartado 3).
Ejecutar desde la raíz del repo:
    python -m unittest discover -s tests -v
Requiere: pip install -r requirements.txt
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _importar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


generar_datos = _importar("generar_datos", RAIZ / "data" / "generar_datos.py")
modelo_demanda = _importar("modelo_demanda", RAIZ / "ml" / "modelo_demanda.py")


class TestModeloDemanda(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        carpeta = Path(cls.tmp.name)
        cls.db = carpeta / "restaurante.db"
        cls.pkl = carpeta / "modelo_rf.pkl"
        generar_datos.main(["--db", str(cls.db), "--fecha-fin", "2026-10-31", "--silencioso"])
        cls.reporte = modelo_demanda.entrenar(cls.db, cls.pkl, ruta_metricas=None, verbose=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def predecir(self, **cambios):
        args = dict(insumo="pollo", dia_semana=4, es_quincena=True, lluvia=False, evento=False,
                    margen_seguridad=0.08, ruta_modelo=self.pkl)
        args.update(cambios)
        return modelo_demanda.predecir_compra(**args)

    # --- Validación temporal ---
    def test_prueba_es_el_ultimo_mes_sin_fuga(self):
        m = self.reporte["metricas"]
        self.assertEqual(m["periodo_prueba"]["dias"], 30)
        self.assertGreater(m["periodo_prueba"]["desde"], m["periodo_entrenamiento"]["hasta"])

    def test_metricas_reales_razonables(self):
        rf = self.reporte["metricas"]["holdout"]["random_forest"]
        self.assertGreater(rf["comensales_r2"], 0.7)
        self.assertLess(rf["insumos_mae_relativo_pct"], 20)
        self.assertEqual(len(self.reporte["metricas"]["time_series_split"]), 5)

    def test_entrenado_con_datos_simulados(self):
        self.assertEqual(self.reporte["origen_dato"], "SIMULADO")
        self.assertEqual(self.predecir()["origen_dato"], "SIMULADO")

    # --- Regla de negocio ---
    def test_formula_de_compra(self):
        r = self.predecir(margen_seguridad=0.10)
        self.assertAlmostEqual(r["compra_sugerida"], round(r["demanda_base"] * 1.10, 2), delta=0.02)

    def test_riesgo_desabasto_por_debajo_de_4_pct(self):
        self.assertTrue(self.predecir(margen_seguridad=0.039)["riesgo_desabasto"])
        self.assertFalse(self.predecir(margen_seguridad=0.04)["riesgo_desabasto"])

    def test_mas_comensales_en_fin_de_semana(self):
        self.assertGreater(self.predecir(dia_semana=5)["comensales_estimados"],
                           self.predecir(dia_semana=1)["comensales_estimados"])

    def test_insumo_por_nombre_o_clave(self):
        self.assertEqual(self.predecir(insumo="Pechuga de pollo")["demanda_base"],
                         self.predecir(insumo="pollo")["demanda_base"])

    def test_entradas_invalidas(self):
        with self.assertRaises(ValueError):
            self.predecir(margen_seguridad=0.30)
        with self.assertRaises(ValueError):
            self.predecir(dia_semana=7)
        with self.assertRaises(ValueError):
            self.predecir(insumo="caviar")

    # --- Explicabilidad ---
    def test_importancias_en_porcentaje_suman_100(self):
        imp = self.predecir()["importancia_variables"]
        self.assertEqual(len(imp), len(modelo_demanda.VARIABLES))
        self.assertAlmostEqual(sum(i["porcentaje"] for i in imp), 100.0, places=6)
        self.assertEqual(imp, sorted(imp, key=lambda d: d["porcentaje"], reverse=True))


if __name__ == "__main__":
    unittest.main()
