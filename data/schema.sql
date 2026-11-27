-- =============================================================================
-- OpsIA — Esquema de base de datos (SQLite)
-- Archivo: /data/schema.sql
--
-- Regla de la rúbrica: TODO registro ficticio se marca con origen_dato = 'SIMULADO'.
-- Si algún día se cargan datos de un restaurante real, se marcan como 'REAL'.
-- La restricción CHECK impide guardar un registro sin etiqueta de origen.
-- =============================================================================

PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- Metadatos del dataset: quién lo generó, cuándo, con qué semilla y su origen.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta_dataset (
    clave       TEXT PRIMARY KEY,
    valor       TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- Catálogo de insumos (materia prima que compra el restaurante).
-- precio_unitario_mxn: precio de referencia por unidad de compra.
-- fuente_precio: de dónde sale el precio. Mientras no se capture el valor de
--   PROFECO "Quién es Quién en los Precios", el precio es SIMULADO y la fuente
--   lo dice explícitamente.
-- vida_util_dias: días que dura el insumo en almacén antes de caducar.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS insumos (
    id                    INTEGER PRIMARY KEY,
    clave                 TEXT    NOT NULL UNIQUE,
    nombre                TEXT    NOT NULL,
    categoria             TEXT    NOT NULL,
    unidad                TEXT    NOT NULL CHECK (unidad IN ('kg', 'L', 'pza')),
    precio_unitario_mxn   REAL    NOT NULL CHECK (precio_unitario_mxn > 0),
    vida_util_dias        INTEGER NOT NULL CHECK (vida_util_dias > 0),
    perecedero            INTEGER NOT NULL CHECK (perecedero IN (0, 1)),
    fuente_precio         TEXT    NOT NULL,
    origen_dato           TEXT    NOT NULL DEFAULT 'SIMULADO' CHECK (origen_dato IN ('SIMULADO', 'REAL'))
);

-- -----------------------------------------------------------------------------
-- Menú vigente del restaurante (platillos que YA existen; Gemini solo puede
-- sugerir promociones sobre estos, nunca inventar platillos nuevos).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platillos (
    id                  INTEGER PRIMARY KEY,
    clave               TEXT    NOT NULL UNIQUE,
    nombre              TEXT    NOT NULL,
    categoria           TEXT    NOT NULL,
    precio_venta_mxn    REAL    NOT NULL CHECK (precio_venta_mxn > 0),
    popularidad_base    REAL    NOT NULL CHECK (popularidad_base >= 0),
    activo              INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    origen_dato         TEXT    NOT NULL DEFAULT 'SIMULADO' CHECK (origen_dato IN ('SIMULADO', 'REAL'))
);

-- -----------------------------------------------------------------------------
-- Recetario: cuánto de cada insumo lleva UNA porción de cada platillo.
-- cantidad_por_porcion está en la misma unidad que el insumo (kg, L o pza).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS recetas (
    platillo_id           INTEGER NOT NULL REFERENCES platillos(id),
    insumo_id             INTEGER NOT NULL REFERENCES insumos(id),
    cantidad_por_porcion  REAL    NOT NULL CHECK (cantidad_por_porcion > 0),
    origen_dato           TEXT    NOT NULL DEFAULT 'SIMULADO' CHECK (origen_dato IN ('SIMULADO', 'REAL')),
    PRIMARY KEY (platillo_id, insumo_id)
);

-- -----------------------------------------------------------------------------
-- Contexto diario: una fila por día con las variables que usa el modelo de ML
-- (calendario, quincena, días festivos, época del año, clima, eventos cercanos y
-- eventos en la plaza) y la afluencia real (comensales).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contexto_diario (
    fecha                 TEXT    PRIMARY KEY,            -- 'YYYY-MM-DD'
    dia_semana            INTEGER NOT NULL CHECK (dia_semana BETWEEN 0 AND 6),  -- 0 = lunes
    mes                   INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    es_fin_de_semana      INTEGER NOT NULL CHECK (es_fin_de_semana IN (0, 1)),
    es_quincena           INTEGER NOT NULL CHECK (es_quincena IN (0, 1)),
    es_dia_festivo        INTEGER NOT NULL CHECK (es_dia_festivo IN (0, 1)),
    nombre_festivo        TEXT,                                   -- NULL si no es festivo
    epoca_anio            TEXT    NOT NULL CHECK (epoca_anio IN ('regular', 'navidena', 'cuesta_enero', 'verano')),
    lluvia                INTEGER NOT NULL CHECK (lluvia IN (0, 1)),
    temperatura_c         REAL    NOT NULL,
    evento_cercano        INTEGER NOT NULL CHECK (evento_cercano IN (0, 1)),
    evento_plaza          INTEGER NOT NULL CHECK (evento_plaza IN (0, 1)),   -- Buen Fin, exposición, concierto en la plaza
    comensales            INTEGER NOT NULL CHECK (comensales >= 0),
    origen_dato           TEXT    NOT NULL DEFAULT 'SIMULADO' CHECK (origen_dato IN ('SIMULADO', 'REAL'))
);

-- -----------------------------------------------------------------------------
-- Ventas diarias por platillo (lo que salió de cocina cada día).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ventas_diarias (
    fecha                 TEXT    NOT NULL REFERENCES contexto_diario(fecha),
    platillo_id           INTEGER NOT NULL REFERENCES platillos(id),
    porciones_vendidas    INTEGER NOT NULL CHECK (porciones_vendidas >= 0),
    ingreso_mxn           REAL    NOT NULL CHECK (ingreso_mxn >= 0),
    origen_dato           TEXT    NOT NULL DEFAULT 'SIMULADO' CHECK (origen_dato IN ('SIMULADO', 'REAL')),
    PRIMARY KEY (fecha, platillo_id)
);

-- -----------------------------------------------------------------------------
-- Consumo diario de cada insumo y comparación contra la compra "a ojo".
-- consumo_real:          lo que la cocina realmente usó (variable objetivo del ML).
-- compra_tradicional:    lo que el encargado compró por intuición ese día.
-- merma_tradicional:     lo que se tiró por caducidad con la compra tradicional.
-- faltante_tradicional:  lo que faltó (desabasto) con la compra tradicional.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS consumo_insumos_diario (
    fecha                 TEXT    NOT NULL REFERENCES contexto_diario(fecha),
    insumo_id             INTEGER NOT NULL REFERENCES insumos(id),
    consumo_real          REAL    NOT NULL CHECK (consumo_real >= 0),
    compra_tradicional    REAL    NOT NULL CHECK (compra_tradicional >= 0),
    merma_tradicional     REAL    NOT NULL CHECK (merma_tradicional >= 0),
    faltante_tradicional  REAL    NOT NULL CHECK (faltante_tradicional >= 0),
    origen_dato           TEXT    NOT NULL DEFAULT 'SIMULADO' CHECK (origen_dato IN ('SIMULADO', 'REAL')),
    PRIMARY KEY (fecha, insumo_id)
);

-- -----------------------------------------------------------------------------
-- Inventario actual por lote, con fecha y hora de caducidad.
-- Las caducidades se calculan relativas al momento en que se corre el script,
-- para que siempre existan insumos a menos de 24 h de caducar en la demo.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inventario_lotes (
    id                    INTEGER PRIMARY KEY,
    insumo_id             INTEGER NOT NULL REFERENCES insumos(id),
    cantidad              REAL    NOT NULL CHECK (cantidad >= 0),
    fecha_ingreso         TEXT    NOT NULL,               -- ISO 8601 'YYYY-MM-DDTHH:MM:SS'
    fecha_caducidad       TEXT    NOT NULL,               -- ISO 8601 'YYYY-MM-DDTHH:MM:SS'
    ubicacion             TEXT    NOT NULL CHECK (ubicacion IN ('refrigerador', 'congelador', 'alacena')),
    origen_dato           TEXT    NOT NULL DEFAULT 'SIMULADO' CHECK (origen_dato IN ('SIMULADO', 'REAL'))
);

-- -----------------------------------------------------------------------------
-- Bitácoras que llenará el backend (Apartados 4 y 6). Se crean vacías.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS promociones_generadas (
    id                    INTEGER PRIMARY KEY,
    creado_en             TEXT    NOT NULL,
    modo                  TEXT    NOT NULL CHECK (modo IN ('gemini', 'fallback')),
    platillo_id           INTEGER NOT NULL REFERENCES platillos(id),
    descuento_pct         REAL    NOT NULL,
    precio_oferta_mxn     REAL    NOT NULL,
    copy_promocional      TEXT    NOT NULL,
    respuesta_json        TEXT    NOT NULL,
    origen_dato           TEXT    NOT NULL DEFAULT 'SIMULADO' CHECK (origen_dato IN ('SIMULADO', 'REAL'))
);

CREATE TABLE IF NOT EXISTS alertas_excedente (
    id                    INTEGER PRIMARY KEY,
    creado_en             TEXT    NOT NULL,
    modo                  TEXT    NOT NULL CHECK (modo IN ('gemini', 'fallback')),
    platillo_id           INTEGER NOT NULL REFERENCES platillos(id),
    porciones_excedentes  INTEGER NOT NULL CHECK (porciones_excedentes >= 0),
    ventana_inicio        TEXT    NOT NULL,
    ventana_fin           TEXT    NOT NULL,
    ficha_json            TEXT    NOT NULL,
    enviada               INTEGER NOT NULL DEFAULT 0 CHECK (enviada IN (0, 1)),
    origen_dato           TEXT    NOT NULL DEFAULT 'SIMULADO' CHECK (origen_dato IN ('SIMULADO', 'REAL'))
);

-- Índices para las consultas más frecuentes del backend.
CREATE INDEX IF NOT EXISTS idx_ventas_platillo   ON ventas_diarias (platillo_id, fecha);
CREATE INDEX IF NOT EXISTS idx_consumo_insumo    ON consumo_insumos_diario (insumo_id, fecha);
CREATE INDEX IF NOT EXISTS idx_lotes_caducidad   ON inventario_lotes (fecha_caducidad);
