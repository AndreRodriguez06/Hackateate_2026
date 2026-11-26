# ZeroMerma AI

Plataforma web para reducir el desperdicio de alimentos en un restaurante de plaza comercial: predice compras con Machine Learning, propone promociones rentables con Gemini para insumos por caducar y emite alertas tempranas de excedentes.

> ⚠️ **Todos los datos del proyecto son SIMULADOS** para validar el prototipo. Ver [`docs/02_base_de_datos.md`](docs/02_base_de_datos.md).

## Avance

| Apartado | Estado | Documento |
|---|---|---|
| 1. Funciones y arquitectura | ✅ | [`docs/01_arquitectura.md`](docs/01_arquitectura.md) |
| 2. Base de datos y datos simulados | ✅ | [`docs/02_base_de_datos.md`](docs/02_base_de_datos.md) |
| 3. Modelo predictivo | Pendiente | |
| 4. Backend FastAPI | Pendiente | |
| 5. Frontend | Prototipo visual en [`prueba1/`](prueba1/) | |
| 6. Integración Gemini | Pendiente | |
| 7. Integración final | Pendiente | |
| 8. Plan de negocios | Pendiente | |

## Probar lo que ya existe

Requiere Python 3.10 o superior. No hace falta instalar paquetes todavía.

```bash
python data/generar_datos.py              # crea data/zeromerma.db con datos SIMULADOS
python -m unittest discover -s tests -v   # 9 pruebas del generador
```

El prototipo visual se abre con doble clic en `prueba1/index.html`.
