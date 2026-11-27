# OpsIA

*Nombre inspirado en Ops, diosa romana de la abundancia y las cosechas y en la implementación de la IA.*

**El problema:** los restaurantes compran sus insumos perecederos "a ojo". Si compran de más, la comida caduca y se tira; si recortan al tanteo, se quedan sin platillos. **Opsia** predice cuánto comprar de cada insumo (Machine Learning), propone promociones rentables para vender lo que está por caducar (Google Gemini) y avisa a tiempo a comedores comunitarios cuando va a sobrar comida.

> ⚠️ Todos los datos del restaurante son **SIMULADOS** (prototipo de validación).

## Ejecutar

Requiere Python 3.10 o superior.

```bash
git clone https://github.com/AndreRodriguez06/Hackateate_2026.git
cd Hackateate_2026
pip install -r requirements.txt
py data/generar_datos.py && py -m uvicorn backend.main:app --reload
```

Abrir **<http://localhost:8000>**. La primera vez el servidor genera los datos simulados y entrena el modelo (≈ 10 s).

Sin instalar nada: doble clic en `frontend/index.html` abre la aplicación en **modo demo** (sin servidor).

## Llave de Gemini (opcional)

1. Crea una llave en [Google AI Studio](https://aistudio.google.com/apikey).
2. Copia la plantilla: `cp .env.example .env` (Windows: `copy .env.example .env`).
3. En `.env` cambia `tu_api_key_aqui` por tu llave y reinicia el servidor.

Sin llave todo funciona igual: las promociones y avisos se calculan con reglas locales y la pantalla dice **"modo respaldo"**. El archivo `.env` no se sube a git.

---

Documentación completa (problema, evidencia, modelo, API, plan de negocios y pruebas): [`docs/00_resumen_proyecto.md`](docs/00_resumen_proyecto.md).
