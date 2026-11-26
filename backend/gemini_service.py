"""
ZeroMerma AI — Integración con Google Gemini (sin chatbots)
Archivo: /backend/gemini_service.py

Dos funciones, cada una con una tarea cerrada y salida JSON con esquema fijo
(Structured Outputs: `response_schema` con modelos Pydantic):

  A) generar_promociones_menu(inventario_critico, menu_restaurante)
       Elige platillos QUE YA EXISTEN en el menú y consumen insumos por caducar,
       propone un descuento rentable y redacta el texto para el menú digital.

  B) generar_alerta_recoleccion(excedente_proyectado, hora_actual)
       Redacta la ficha operativa para un comedor comunitario o la red estudiantil:
       producto, porciones exactas, ventana de recolección que termina al menos
       2 horas antes del cierre y recomendaciones de inocuidad.

Principio de diseño: Python hace las cuentas, Gemini decide y redacta.
  * El prompt ya incluye el descuento máximo rentable de cada platillo y la ventana
    de recolección válida, calculados aquí.
  * Toda respuesta de Gemini se VALIDA contra esas reglas antes de usarse.

Plan de contingencia (modo respaldo):
  Si no hay GEMINI_API_KEY, falta el SDK, no hay internet, se agota la cuota, se
  excede el tiempo o la respuesta no pasa la validación, la función NO lanza error:
  devuelve una respuesta con la misma estructura calculada con reglas locales y
  `"modo_respaldo": true` más el motivo. La demo nunca se cae.

Configuración (variables de entorno o archivo .env en la raíz del repo):
  GEMINI_API_KEY      llave de Google AI Studio (obligatoria para usar Gemini)
  GEMINI_MODEL        por defecto "gemini-2.5-flash"
  GEMINI_TIMEOUT_MS   por defecto 15000 (15 s)
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

from pydantic import BaseModel, Field

RAIZ = Path(__file__).resolve().parents[1]

DESCUENTO_MIN_PCT = 10
DESCUENTO_MAX_PCT = 30
HORAS_MINIMAS_ANTES_CIERRE = 2.0
LONGITUD_COPY = 160


# =============================================================================
# 1. Configuración
# =============================================================================

def _cargar_env() -> None:
    """Lee .env de la raíz (formato CLAVE=valor) sin dependencias extra. No pisa variables ya definidas."""
    archivo = RAIZ / ".env"
    if not archivo.exists():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_env()


def modelo() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def configurado() -> bool:
    """True si hay llave. No garantiza que la llave sea válida ni que haya internet."""
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


class GeminiNoDisponible(Exception):
    """Gemini no se puede usar (sin llave, sin SDK, respuesta vacía…)."""


class RespuestaInvalida(Exception):
    """Gemini respondió, pero la respuesta no cumple las reglas de negocio."""


# =============================================================================
# 2. Esquemas de salida (Structured Outputs)
# =============================================================================

class PromocionGemini(BaseModel):
    platillo_clave: str = Field(description="Clave EXACTA de un platillo de la lista 'platillos_candidatos'.")
    descuento_pct: int = Field(ge=DESCUENTO_MIN_PCT, le=DESCUENTO_MAX_PCT,
                               description="Descuento entero en %. No puede superar 'descuento_maximo_rentable_pct' del platillo.")
    insumos_criticos_usados: list[str] = Field(description="Claves de los insumos críticos que consume este platillo.")
    justificacion: str = Field(max_length=220, description="Una frase para el gerente: por qué este platillo y este descuento.")
    copy_promocional: str = Field(max_length=LONGITUD_COPY,
                                  description="Texto para el menú digital del comensal, máximo 160 caracteres.")


class RespuestaPromociones(BaseModel):
    promociones: list[PromocionGemini] = Field(max_length=5)


class FichaGemini(BaseModel):
    producto: str = Field(description="Nombre del platillo tal como viene en el excedente.")
    porciones: int = Field(ge=1, description="Número EXACTO de porciones del excedente.")
    ventana_inicio: str = Field(description="Hora de inicio de recolección, formato HH:MM de 24 h.")
    ventana_limite: str = Field(description="Hora límite de recolección, formato HH:MM de 24 h.")
    recomendaciones_inocuidad: list[str] = Field(min_length=2, max_length=4,
                                                 description="De 2 a 4 recomendaciones breves y concretas.")
    mensaje: str = Field(max_length=500, description="Mensaje listo para enviar por WhatsApp o correo.")


# =============================================================================
# 3. Llamada a Gemini
# =============================================================================

_CLIENTE = None


def _cliente():
    global _CLIENTE
    if not configurado():
        raise GeminiNoDisponible("No hay GEMINI_API_KEY configurada.")
    if _CLIENTE is None:
        try:
            from google import genai
            from google.genai import types
        except ModuleNotFoundError as err:
            raise GeminiNoDisponible("Falta instalar el SDK: pip install google-genai") from err
        _CLIENTE = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"].strip(),
            http_options=types.HttpOptions(timeout=int(os.getenv("GEMINI_TIMEOUT_MS", "15000"))),
        )
    return _CLIENTE


def _generar(instruccion_sistema: str, contenido: str, esquema: type[BaseModel]) -> BaseModel:
    """Una llamada a Gemini con salida JSON forzada al esquema Pydantic."""
    from google.genai import types

    respuesta = _cliente().models.generate_content(
        model=modelo(),
        contents=contenido,
        config=types.GenerateContentConfig(
            system_instruction=instruccion_sistema,
            response_mime_type="application/json",
            response_schema=esquema,
            temperature=0.3,                                         # creatividad baja: es una tarea operativa
            thinking_config=types.ThinkingConfig(thinking_budget=0),  # sin razonamiento extendido: menor latencia
        ),
    )
    if isinstance(getattr(respuesta, "parsed", None), esquema):
        return respuesta.parsed
    if not getattr(respuesta, "text", None):
        raise GeminiNoDisponible("Gemini devolvió una respuesta vacía.")
    return esquema.model_validate_json(respuesta.text)


def _motivo(err: Exception) -> str:
    """Motivo corto y entendible para mostrar en la interfaz."""
    if isinstance(err, (GeminiNoDisponible, RespuestaInvalida)):
        return str(err)
    texto = str(err).replace("\n", " ")
    codigo = getattr(err, "code", None)
    if "API key not valid" in texto or "API_KEY_INVALID" in texto:
        return "La GEMINI_API_KEY no es válida."
    if codigo == 429 or "RESOURCE_EXHAUSTED" in texto:
        return "Se agotó la cuota de Gemini por ahora."
    if codigo in (401, 403) or "PERMISSION_DENIED" in texto:
        return "La llave de Gemini no tiene permiso para este modelo."
    if isinstance(err, TimeoutError) or "timed out" in texto.lower() or "Timeout" in type(err).__name__:
        return f"Gemini no respondió a tiempo ({type(err).__name__})."
    if "ValidationError" in type(err).__name__:
        return "Gemini devolvió un JSON que no cumple el esquema."
    return f"Falló la llamada a Gemini ({type(err).__name__}): {texto[:160]}"


# =============================================================================
# 4. Función A — Promociones sobre el menú existente
# =============================================================================

INSTRUCCION_PROMOCIONES = f"""Eres el motor de optimización de menú de ZeroMerma AI para un restaurante en México.
No conversas: devuelves únicamente JSON que cumple el esquema.

Tarea: proponer promociones para vender HOY insumos que caducan en menos de 24 horas.

Reglas obligatorias:
1. Usa solo claves de 'platillos_candidatos'. Nunca inventes platillos ni ingredientes.
2. Cada promoción debe consumir al menos un insumo de 'insumos_criticos'.
3. descuento_pct es un entero entre {DESCUENTO_MIN_PCT} y {DESCUENTO_MAX_PCT} y NO puede superar el
   'descuento_maximo_rentable_pct' del platillo (con ese tope el precio sigue siendo al menos 1.5 veces el costo).
4. Prioriza los platillos que rescatan más valor en pesos de insumos críticos (campo
   'valor_critico_por_porcion_mxn') y que, juntos, cubren insumos críticos distintos.
5. No repitas platillos. Devuelve como máximo el número pedido de promociones.
6. copy_promocional: español de México, máximo {LONGITUD_COPY} caracteres, tono cálido y apetitoso.
   NO escribas precios ni porcentajes (la interfaz los muestra junto al texto). Describe solo ingredientes
   que están en la receta. NUNCA digas al comensal que un ingrediente está por caducar, sobra o se va a tirar.
7. justificacion: una frase para el gerente con el razonamiento de negocio."""


def _descuento_maximo_rentable(precio: float, costo: float) -> int | None:
    from backend.services.rescate_menu import FACTOR_COSTO_MINIMO
    if costo <= 0:
        return DESCUENTO_MAX_PCT
    maximo = math.floor((1 - FACTOR_COSTO_MINIMO * costo / precio) * 100)
    maximo = min(maximo, DESCUENTO_MAX_PCT)
    return maximo if maximo >= DESCUENTO_MIN_PCT else None


def _candidatos(inventario_critico: list[dict], menu_restaurante: list[dict]) -> dict[str, dict]:
    """Platillos del menú que usan insumos críticos y admiten al menos 10 % de descuento rentable."""
    criticos = {i["clave"]: i for i in inventario_critico}
    candidatos = {}
    for p in menu_restaurante:
        usados = [k for k in p["receta"] if k in criticos]
        maximo = _descuento_maximo_rentable(p["precio_venta_mxn"], p["costo_porcion_mxn"])
        if not usados or maximo is None:
            continue
        candidatos[p["clave"]] = {
            "clave": p["clave"], "nombre": p["nombre"], "categoria": p.get("categoria", ""),
            "precio_venta_mxn": p["precio_venta_mxn"], "costo_porcion_mxn": p["costo_porcion_mxn"],
            "descuento_maximo_rentable_pct": maximo,
            "ingredientes_criticos": [{"clave": k, "nombre": criticos[k]["nombre"],
                                       "cantidad_por_porcion": p["receta"][k], "unidad": criticos[k]["unidad"]}
                                      for k in usados],
            "otros_ingredientes": [k.replace("_", " ") for k in p["receta"] if k not in criticos],
            "valor_critico_por_porcion_mxn": round(sum(p["receta"][k] * criticos[k]["costo_unitario_mxn"]
                                                      for k in usados), 2),
        }
    return candidatos


def _armar_promocion(c: dict, descuento: int, usados: list[str], justificacion: str, copy: str) -> dict:
    return {
        "platillo_clave": c["clave"], "platillo": c["nombre"], "tipo": "descuento",
        "descuento_pct": descuento, "precio_normal_mxn": c["precio_venta_mxn"],
        "precio_oferta_mxn": round(c["precio_venta_mxn"] * (1 - descuento / 100)),
        "costo_porcion_mxn": c["costo_porcion_mxn"], "insumos_criticos_usados": usados,
        "justificacion": justificacion, "copy_promocional": copy,
    }


def _validar_promociones(propuestas: list[PromocionGemini], candidatos: dict, maximo: int) -> list[dict]:
    if not propuestas:
        raise RespuestaInvalida("Gemini no propuso promociones.")
    vistas, salida = set(), []
    for p in propuestas[:maximo]:
        c = candidatos.get(p.platillo_clave)
        if c is None:
            raise RespuestaInvalida(f"Platillo fuera del menú o sin insumos críticos: {p.platillo_clave!r}")
        if p.platillo_clave in vistas:
            raise RespuestaInvalida(f"Platillo repetido: {p.platillo_clave}")
        if not DESCUENTO_MIN_PCT <= p.descuento_pct <= c["descuento_maximo_rentable_pct"]:
            raise RespuestaInvalida(f"Descuento de {p.descuento_pct}% en {c['nombre']} fuera del rango rentable "
                                    f"({DESCUENTO_MIN_PCT}–{c['descuento_maximo_rentable_pct']}%).")
        copy = p.copy_promocional.strip()
        if not copy or len(copy) > LONGITUD_COPY:
            raise RespuestaInvalida(f"Texto promocional vacío o demasiado largo en {c['nombre']}.")
        vistas.add(p.platillo_clave)
        # Los insumos usados se toman de la receta, no de lo que diga el modelo.
        usados = [i["clave"] for i in c["ingredientes_criticos"]]
        promo = _armar_promocion(c, p.descuento_pct, usados, p.justificacion.strip(), copy)
        # Si a pesar de la instrucción el texto menciona un precio, debe ser el precio de oferta correcto.
        for monto in re.findall(r"\$\s*(\d+(?:[.,]\d+)?)", copy):
            if round(float(monto.replace(",", "."))) != promo["precio_oferta_mxn"]:
                raise RespuestaInvalida(f"El texto de {c['nombre']} menciona ${monto}, pero la oferta es "
                                        f"${promo['precio_oferta_mxn']}.")
        salida.append(promo)
    return salida


def _promociones_respaldo(candidatos: dict, maximo: int) -> list[dict]:
    """Reglas locales: mayor valor crítico rescatado primero, con el mayor descuento rentable."""
    from backend.services.rescate_menu import copy_por_plantilla
    orden = sorted(candidatos.values(), key=lambda c: c["valor_critico_por_porcion_mxn"], reverse=True)
    salida = []
    for c in orden[:maximo]:
        promo = _armar_promocion(c, c["descuento_maximo_rentable_pct"],
                                 [i["clave"] for i in c["ingredientes_criticos"]],
                                 "Regla local: mayor valor de insumo crítico por porción con el mayor descuento rentable.", "")
        promo["copy_promocional"] = copy_por_plantilla({"platillo": promo["platillo"],
                                                        "precio_oferta_mxn": promo["precio_oferta_mxn"],
                                                        "precio_normal_mxn": promo["precio_normal_mxn"]})
        salida.append(promo)
    return salida


def generar_promociones_menu(inventario_critico: list[dict], menu_restaurante: list[dict],
                             max_promociones: int = 3, usar_gemini: bool = True) -> dict:
    """
    inventario_critico: [{clave, nombre, cantidad, unidad, costo_unitario_mxn, horas_restantes}]
                        (insumos que caducan en menos de 24 h)
    menu_restaurante:   [{clave, nombre, categoria, precio_venta_mxn, costo_porcion_mxn,
                          receta: {clave_insumo: cantidad_por_porcion}}]
    Devuelve: {modo_respaldo, motivo_respaldo, modelo, promociones: [...]}
    """
    candidatos = _candidatos(inventario_critico, menu_restaurante)
    base = {"modo_respaldo": False, "motivo_respaldo": None, "modelo": modelo(), "promociones": []}
    if not candidatos:
        return {**base, "modelo": None,
                "motivo_respaldo": "Ningún platillo del menú usa los insumos críticos con un descuento rentable."}
    if not usar_gemini:
        return {**base, "modo_respaldo": True, "modelo": None, "motivo_respaldo": "Se pidió no usar Gemini.",
                "promociones": _promociones_respaldo(candidatos, max_promociones)}

    contenido = json.dumps({
        "numero_de_promociones": min(max_promociones, len(candidatos)),
        "insumos_criticos": [{"clave": i["clave"], "nombre": i["nombre"], "cantidad_disponible": i["cantidad"],
                              "unidad": i["unidad"], "costo_unitario_mxn": i["costo_unitario_mxn"],
                              "horas_para_caducar": i.get("horas_restantes")} for i in inventario_critico],
        "platillos_candidatos": list(candidatos.values()),
    }, ensure_ascii=False)
    try:
        r = _generar(INSTRUCCION_PROMOCIONES, contenido, RespuestaPromociones)
        return {**base, "promociones": _validar_promociones(r.promociones, candidatos, max_promociones)}
    except Exception as err:  # contingencia: nunca romper la demo
        return {**base, "modo_respaldo": True, "modelo": None, "motivo_respaldo": _motivo(err),
                "promociones": _promociones_respaldo(candidatos, max_promociones)}


# =============================================================================
# 5. Función B — Ficha de recolección para comedores comunitarios
# =============================================================================

INSTRUCCION_FICHA = f"""Eres el módulo de alertas de excedentes de ZeroMerma AI para un restaurante en México.
No conversas: devuelves únicamente JSON que cumple el esquema.

Tarea: redactar la ficha operativa para que un comedor comunitario o la red estudiantil recoja comida
preparada que sobrará hoy.

Reglas obligatorias:
1. 'producto' y 'porciones' deben copiarse EXACTAMENTE del excedente. No cambies las cantidades.
2. La ventana de recolección debe quedar dentro de 'ventana_permitida': ventana_inicio no antes de su inicio y
   ventana_limite no después de su límite (el límite es {HORAS_MINIMAS_ANTES_CIERRE:g} horas antes del cierre).
   Formato HH:MM de 24 horas.
3. recomendaciones_inocuidad: de 2 a 4 frases cortas y prácticas (temperatura, transporte, tiempo de consumo).
   Si 'requiere_refrigeracion' es true, incluye mantenerlo a 4 °C o menos.
4. mensaje: español de México, cordial y directo, listo para WhatsApp; incluye producto, porciones, kilos
   aproximados, ventana y punto de entrega. Sin emojis excesivos. No inventes datos que no estén en la entrada."""


def _hhmm_a_horas(texto: str) -> float:
    h, m = texto.strip().split(":")
    h, m = int(h), int(m)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Hora inválida: {texto!r}")
    return h + m / 60


def _horas_a_hhmm(h: float) -> str:
    total = round(h * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def recomendaciones_base(requiere_refrigeracion: bool) -> list[str]:
    if requiere_refrigeracion:
        return ["Mantener en refrigeración a 4 °C o menos hasta la entrega.",
                "Transportar en contenedores cerrados y limpios, sin romper la cadena de frío.",
                "Consumir el mismo día; recalentar una sola vez hasta que esté bien caliente en el centro."]
    return ["Conservar tapado y en un lugar fresco y limpio.",
            "Consumir el mismo día de la entrega."]


def _ficha_respaldo(exc: dict, inicio: float, limite: float, cierre: float) -> dict:
    recomendaciones = recomendaciones_base(bool(exc.get("requiere_refrigeracion")))
    punto = exc.get("punto_entrega", "Cafetería La Esquina")
    return {
        "producto": exc["producto"], "porciones": int(exc["porciones"]),
        "cantidad_aprox_kg": exc.get("cantidad_aprox_kg"),
        "ventana_inicio": _horas_a_hhmm(inicio), "ventana_limite": _horas_a_hhmm(limite),
        "horas_antes_del_cierre": round(cierre - limite, 2),
        "recomendaciones_inocuidad": recomendaciones,
        "mensaje": (f"Hola, somos {punto}. Hoy tenemos {exc['porciones']} porciones de {exc['producto']}"
                    f"{' (aprox. ' + str(exc['cantidad_aprox_kg']) + ' kg)' if exc.get('cantidad_aprox_kg') else ''}"
                    f" disponibles para donación. Pueden recogerlas entre {_horas_a_hhmm(inicio)} y "
                    f"{_horas_a_hhmm(limite)}. {recomendaciones[0]}"),
    }


def _validar_ficha(f: FichaGemini, exc: dict, inicio: float, limite: float, cierre: float) -> dict:
    if f.porciones != int(exc["porciones"]):
        raise RespuestaInvalida(f"Gemini cambió las porciones ({f.porciones} en lugar de {exc['porciones']}).")
    try:
        ini, lim = _hhmm_a_horas(f.ventana_inicio), _hhmm_a_horas(f.ventana_limite)
    except ValueError as err:
        raise RespuestaInvalida(f"Hora con formato inválido: {err}") from err
    if not (inicio - 1e-6 <= ini < lim <= limite + 1e-6):
        raise RespuestaInvalida(f"Ventana {f.ventana_inicio}–{f.ventana_limite} fuera de lo permitido "
                                f"({_horas_a_hhmm(inicio)}–{_horas_a_hhmm(limite)}).")
    recomendaciones = [r.strip() for r in f.recomendaciones_inocuidad if r.strip()]
    if len(recomendaciones) < 2 or not f.mensaje.strip():
        raise RespuestaInvalida("Faltan recomendaciones de inocuidad o el mensaje.")
    return {
        "producto": exc["producto"], "porciones": int(exc["porciones"]),
        "cantidad_aprox_kg": exc.get("cantidad_aprox_kg"),
        "ventana_inicio": _horas_a_hhmm(ini), "ventana_limite": _horas_a_hhmm(lim),
        "horas_antes_del_cierre": round(cierre - lim, 2),
        "recomendaciones_inocuidad": recomendaciones, "mensaje": f.mensaje.strip(),
    }


def generar_alerta_recoleccion(excedente_proyectado: dict, hora_actual: str, hora_cierre: str = "20:00",
                               usar_gemini: bool = True) -> dict:
    """
    excedente_proyectado: {producto, porciones, cantidad_aprox_kg, requiere_refrigeracion, punto_entrega?}
    hora_actual / hora_cierre: "HH:MM"
    Devuelve: {modo_respaldo, motivo_respaldo, modelo, ficha | None, motivo_sin_ficha}
    """
    from backend.services.alerta_excedente import ventana_recoleccion

    h, cierre = _hhmm_a_horas(hora_actual), _hhmm_a_horas(hora_cierre)
    base = {"modo_respaldo": False, "motivo_respaldo": None, "modelo": modelo(), "ficha": None, "motivo_sin_ficha": None}
    ventana = ventana_recoleccion(h, cierre)
    if ventana is None:
        return {**base, "modelo": None, "motivo_sin_ficha": (
            f"Ya no hay tiempo para una recolección segura: debe terminar al menos "
            f"{HORAS_MINIMAS_ANTES_CIERRE:g} h antes del cierre ({_horas_a_hhmm(cierre - HORAS_MINIMAS_ANTES_CIERRE)}). "
            "Aprovechen el excedente internamente.")}
    inicio, limite = ventana
    if not usar_gemini:
        return {**base, "modo_respaldo": True, "modelo": None, "motivo_respaldo": "Se pidió no usar Gemini.",
                "ficha": _ficha_respaldo(excedente_proyectado, inicio, limite, cierre)}

    contenido = json.dumps({
        "excedente": {k: excedente_proyectado.get(k) for k in
                      ("producto", "porciones", "cantidad_aprox_kg", "requiere_refrigeracion", "punto_entrega")},
        "hora_actual": _horas_a_hhmm(h), "hora_cierre": _horas_a_hhmm(cierre),
        "ventana_permitida": {"inicio": _horas_a_hhmm(inicio), "limite": _horas_a_hhmm(limite)},
        "destinatario": "Comedor comunitario / Red estudiantil",
    }, ensure_ascii=False)
    try:
        f = _generar(INSTRUCCION_FICHA, contenido, FichaGemini)
        return {**base, "ficha": _validar_ficha(f, excedente_proyectado, inicio, limite, cierre)}
    except Exception as err:  # contingencia: nunca romper la demo
        return {**base, "modo_respaldo": True, "modelo": None, "motivo_respaldo": _motivo(err),
                "ficha": _ficha_respaldo(excedente_proyectado, inicio, limite, cierre)}


# =============================================================================
# 6. Prueba rápida desde la terminal
# =============================================================================

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(RAIZ))
    from datetime import datetime

    from backend import database as db

    with db.sesion() as con:
        ahora = datetime.now()
        criticos = [{"clave": l["clave"], "nombre": l["nombre"], "cantidad": l["cantidad"], "unidad": l["unidad"],
                     "costo_unitario_mxn": l["precio_unitario_mxn"], "horas_restantes": l["horas_restantes"]}
                    for l in db.listar_lotes(con, ahora) if l["estado"] == "CRITICO" and not l["caducado"]]
        menu = list(db.platillos_con_recetas(con).values())
    print("Gemini configurado:", configurado(), "| modelo:", modelo())
    print(json.dumps(generar_promociones_menu(criticos, menu), ensure_ascii=False, indent=2))
    print(json.dumps(generar_alerta_recoleccion(
        {"producto": "Enchiladas Suizas", "porciones": 6, "cantidad_aprox_kg": 3.2, "requiere_refrigeracion": True},
        "15:00"), ensure_ascii=False, indent=2))
