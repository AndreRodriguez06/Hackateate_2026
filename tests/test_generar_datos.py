"""
Pruebas del generador de datos SIMULADOS (Apartado 2).
Ejecutar desde la raíz del repo:
    python -m unittest discover -s tests -v
Solo usa la librería estándar.
"""
import importlib.util
import sqlite3
from contextlib import closing
import tempfile
import unittest
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("generar_datos", RAIZ / "data" / "generar_datos.py")
generar_datos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generar_datos)


class TestGenerarDatos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / "prueba.db"
        codigo = generar_datos.main(["--db", str(cls.db), "--fecha-fin", "2026-10-31", "--silencioso"])
        assert codigo == 0, "el generador terminó con error"
        cls.con = sqlite3.connect(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()
        cls.tmp.cleanup()

    def contar(self, sql):
        return self.con.execute(sql).fetchone()[0]

    def test_un_anio_de_historial_por_defecto(self):
        self.assertEqual(self.contar("SELECT COUNT(*) FROM contexto_diario"), 365)

    def test_todo_etiquetado_como_simulado(self):
        for tabla in generar_datos.TABLAS_CON_ORIGEN:
            with self.subTest(tabla=tabla):
                self.assertEqual(self.contar(f"SELECT COUNT(*) FROM {tabla} WHERE origen_dato <> 'SIMULADO'"), 0)
        self.assertEqual(self.contar("SELECT valor FROM meta_dataset WHERE clave = 'origen_dato'"), "SIMULADO")

    def test_etiqueta_obligatoria_en_esquema(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("INSERT INTO platillos (clave, nombre, categoria, precio_venta_mxn,"
                             " popularidad_base, origen_dato) VALUES ('x','x','x',10,0,'INVENTADO')")

    def test_hay_insumos_criticos_a_menos_de_24h(self):
        n = self.contar("SELECT COUNT(*) FROM inventario_lotes WHERE "
                        "(julianday(fecha_caducidad) - julianday('now','localtime')) * 24 < 24")
        self.assertGreaterEqual(n, 2)

    def test_menu_de_30_platillos_con_catalogo_consistente(self):
        self.assertEqual(self.contar("SELECT COUNT(*) FROM platillos"), 30)
        self.assertEqual(generar_datos.verificar_catalogo(), [])
        # Cada insumo se usa en al menos una receta.
        self.assertEqual(self.contar("SELECT COUNT(*) FROM insumos WHERE id NOT IN "
                                     "(SELECT DISTINCT insumo_id FROM recetas)"), 0)

    def test_cada_platillo_tiene_receta(self):
        self.assertEqual(self.contar("SELECT COUNT(*) FROM platillos WHERE id NOT IN "
                                     "(SELECT DISTINCT platillo_id FROM recetas)"), 0)

    def test_consumo_cuadra_con_ventas_y_recetas(self):
        """El consumo de pollo de un día = Σ porciones × gramos de receta × (1 + merma de preparación)."""
        fecha = self.con.execute("SELECT MIN(fecha) FROM contexto_diario").fetchone()[0]
        esperado = self.contar(
            "SELECT SUM(v.porciones_vendidas * r.cantidad_por_porcion) FROM ventas_diarias v "
            "JOIN recetas r ON r.platillo_id = v.platillo_id JOIN insumos i ON i.id = r.insumo_id "
            f"WHERE v.fecha = '{fecha}' AND i.clave = 'pollo'") * (1 + generar_datos.MERMA_PREPARACION)
        real = self.contar("SELECT consumo_real FROM consumo_insumos_diario c JOIN insumos i ON i.id = c.insumo_id "
                           f"WHERE c.fecha = '{fecha}' AND i.clave = 'pollo'")
        self.assertAlmostEqual(real, esperado, places=2)

    def test_fines_de_semana_mas_concurridos(self):
        semana = self.contar("SELECT AVG(comensales) FROM contexto_diario WHERE es_fin_de_semana = 0")
        finde = self.contar("SELECT AVG(comensales) FROM contexto_diario WHERE es_fin_de_semana = 1")
        self.assertGreater(finde, semana)

    def test_reproducible_con_la_misma_semilla(self):
        otra = Path(self.tmp.name) / "otra.db"
        generar_datos.main(["--db", str(otra), "--fecha-fin", "2026-10-31", "--silencioso"])
        with closing(sqlite3.connect(otra)) as con2:
            a = self.con.execute("SELECT * FROM contexto_diario ORDER BY fecha").fetchall()
            b = con2.execute("SELECT * FROM contexto_diario ORDER BY fecha").fetchall()
        self.assertEqual(a, b)

    def test_dias_festivos_y_epocas(self):
        f = generar_datos.dias_festivos(2026)
        self.assertEqual(f[date(2026, 9, 16)], "Día de la Independencia")
        self.assertEqual(f[date(2026, 4, 3)], "Viernes Santo")               # Pascua 2026: 5 de abril
        self.assertEqual(f[date(2026, 11, 16)], "Día de la Revolución")      # tercer lunes de noviembre
        self.assertEqual(generar_datos.epoca_del_anio(date(2026, 12, 20)), "navidena")
        self.assertEqual(generar_datos.epoca_del_anio(date(2026, 2, 10)), "cuesta_enero")
        self.assertEqual(generar_datos.epoca_del_anio(date(2026, 7, 4)), "verano")
        self.assertTrue(generar_datos.es_buen_fin(date(2026, 11, 13)))       # viernes del puente
        self.assertFalse(generar_datos.es_buen_fin(date(2026, 11, 20)))

    def test_contexto_con_nuevas_variables(self):
        columnas = {c[1] for c in self.con.execute("PRAGMA table_info(contexto_diario)")}
        self.assertTrue({"es_dia_festivo", "nombre_festivo", "epoca_anio", "evento_plaza"} <= columnas)
        self.assertNotIn("temporada_vacacional", columnas)
        epocas = {f[0] for f in self.con.execute("SELECT DISTINCT epoca_anio FROM contexto_diario")}
        self.assertEqual(epocas, set(generar_datos.EPOCAS))                  # 365 días cubren las 4 épocas
        self.assertGreater(self.contar("SELECT COUNT(*) FROM contexto_diario WHERE es_dia_festivo = 1"), 8)

    def test_quincena_se_recorre_a_viernes(self):
        # 15 de noviembre de 2026 es domingo: se paga el viernes 13.
        self.assertTrue(generar_datos.es_quincena(date(2026, 11, 13)))
        self.assertFalse(generar_datos.es_quincena(date(2026, 11, 10)))


if __name__ == "__main__":
    unittest.main()
