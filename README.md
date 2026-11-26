# ZeroMerma AI

Plataforma web para reducir el desperdicio de alimentos en un restaurante de plaza comercial: predice compras con Machine Learning, propone promociones rentables con Gemini para insumos por caducar y emite alertas tempranas de excedentes.

> ⚠️ **Todos los datos del proyecto son SIMULADOS** para validar el prototipo. Ver [`docs/02_base_de_datos.md`](docs/02_base_de_datos.md).

## Avance

| Apartado | Estado | Documento |
|---|---|---|
| 1. Funciones y arquitectura | ✅ | [`docs/01_arquitectura.md`](docs/01_arquitectura.md) |
| 2. Base de datos y datos simulados | ✅ | [`docs/02_base_de_datos.md`](docs/02_base_de_datos.md) |
| 3. Modelo predictivo (Random Forest) | ✅ | [`docs/03_modelo_ml.md`](docs/03_modelo_ml.md) |
| 4. Backend FastAPI | Pendiente | |
| 5. Frontend | Prototipo visual en [`prueba1/`](prueba1/) | |
| 6. Integración Gemini | Pendiente | |
| 7. Integración final | Pendiente | |
| 8. Plan de negocios | Pendiente | |

## Probar lo que ya existe

Requiere Python 3.10 o superior.

```bash
pip install -r requirements.txt
python data/generar_datos.py              # crea data/restaurante.db con datos SIMULADOS
python ml/modelo_demanda.py entrenar      # valida y guarda ml/modelo_rf.pkl
python ml/modelo_demanda.py predecir --insumo pollo --dia 4 --quincena --margen 0.08
python -m unittest discover -s tests -v   # 19 pruebas
```

El prototipo visual se abre con doble clic en `prueba1/index.html`.
