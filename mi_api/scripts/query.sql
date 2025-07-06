CREATE EXTENSION IF NOT EXISTS postgis; -- Asegúrate de que PostGIS esté habilitado

CREATE TABLE IF NOT EXISTS nodes (
    id BIGINT PRIMARY KEY,
    x NUMERIC, -- Longitude o Easting
    y NUMERIC, -- Latitude o Northing
    street_count INTEGER,
    highway VARCHAR(255),
    junction VARCHAR(255),
    railway VARCHAR(255),
    ref VARCHAR(255),
    geom GEOMETRY(Point, 32718) -- Columna de geometría PostGIS para puntos, usando UTM zona 18S
);

CREATE TABLE IF NOT EXISTS edges (
    id SERIAL PRIMARY KEY, -- ID auto-incrementable para la tabla de aristas
    u BIGINT, -- ID del nodo de origen
    v BIGINT, -- ID del nodo de destino
    osmid JSONB, -- O TEXT, si JSONB no es una opción o no lo necesitas
    length NUMERIC,
    travel_time NUMERIC,
    speed_kph NUMERIC,
    oneway BOOLEAN,
    reversed BOOLEAN,
    highway VARCHAR(255),
    name TEXT,
    maxspeed VARCHAR(255),
    ref VARCHAR(255),
    lanes VARCHAR(255),
    service VARCHAR(255),
    bridge VARCHAR(255),
    access VARCHAR(255),
    tunnel VARCHAR(255),
    junction VARCHAR(255),
    width VARCHAR(255),
    geom GEOMETRY(LineString, 32718) -- Columna de geometría PostGIS para LineStrings, usando UTM zona 18S
);

-- Añadir restricciones de clave externa (opcional, pero buena práctica)
ALTER TABLE IF EXISTS edges DROP CONSTRAINT IF EXISTS fk_source_node;
ALTER TABLE IF EXISTS edges ADD CONSTRAINT fk_source_node FOREIGN KEY (u) REFERENCES nodes(id);

ALTER TABLE IF EXISTS edges DROP CONSTRAINT IF EXISTS fk_target_node;
ALTER TABLE IF EXISTS edges ADD CONSTRAINT fk_target_node FOREIGN KEY (v) REFERENCES nodes(id);


CREATE TABLE IF NOT EXISTS puntos_riesgo (
    id TEXT PRIMARY KEY,
    nombre TEXT,
    lat NUMERIC,
    lon NUMERIC,
    geom GEOMETRY(Point, 4326)
);

CREATE TABLE IF NOT EXISTS puntos_respuesta (
    id TEXT PRIMARY KEY,
    nombre TEXT,
    lat NUMERIC,
    lon NUMERIC,
    geom GEOMETRY(Point, 4326)
);