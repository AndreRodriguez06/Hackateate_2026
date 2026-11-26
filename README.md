# ZeroMerma AI

Plataforma web para reducir el desperdicio de alimentos en un restaurante de plaza comercial: predice compras con Machine Learning, propone promociones rentables con Gemini para insumos por caducar y emite alertas tempranas de excedentes.

> ⚠️ **Todos los datos del proyecto son SIMULADOS** para validar el prototipo. Ver [`docs/02_base_de_datos.md`](docs/02_base_de_datos.md).

## Avance

| Apartado | Estado | Documento |
|---|---|---|
| 1. Funciones y arquitectura | ✅ | [`docs/01_arquitectura.md`](docs/01_arquitectura.md) |
| 2. Base de datos y datos simulados | ✅ | [`docs/02_base_de_datos.md`](docs/02_base_de_datos.md) |
| 3. Modelo predictivo (Random Forest) | ✅ | [`docs/03_modelo_ml.md`](docs/03_modelo_ml.md) |
| 4. Backend y API REST (FastAPI) | ✅ | [`docs/04_backend_api.md`](docs/04_backend_api.md) |
| 5. Interfaz web (frontend) | ✅ | [`docs/05_frontend_ux.md`](docs/05_frontend_ux.md) |
| 6. Integración Gemini | Pendiente | |
| 7. Integración final | Pendiente | |
| 8. Plan de negocios | Pendiente | |

## Probar lo que ya existe

Requiere Python 3.10 o superior.

```bash
pip install -r requirements.txt
python backend/main.py        # genera datos y modelo si faltan → abre http://localhost:8000
```

Documentación interactiva de la API: <http://localhost:8000/docs>.

Otros comandos útiles:

```bash
python data/generar_datos.py              # regenera data/restaurante.db (datos SIMULADOS)
python ml/modelo_demanda.py entrenar      # reentrena e imprime las métricas
python -m unittest discover -s tests -v   # 34 pruebas
```

Sin servidor: doble clic en `frontend/index.html` abre la aplicación en **modo demo autónoma** (respuestas precalculadas del mismo modelo; se regeneran con `python scripts/exportar_datos_demo.py`).

`prueba1/` es el primer prototipo visual (100 % en el navegador, cifras ilustrativas); se conserva como referencia.
