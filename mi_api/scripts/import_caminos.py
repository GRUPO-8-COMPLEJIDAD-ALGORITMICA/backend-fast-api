import networkx as nx
import pandas as pd
from sqlalchemy import create_engine, text
from shapely.geometry import Point, LineString
from shapely.wkt import loads as wkt_loads
import json
import psycopg2
from psycopg2 import sql

DB_HOST = "localhost"
DB_NAME = "fastapi_gis"
DB_USER = "postgres"
DB_PASSWORD = "postgres"
DB_PORT = "5432"

DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DB_URL)

path = "../caminos_lima/grafo_lima.graphml"

def parse_geometry_string(geom_str):
    if not geom_str:
        return None
    try:
        return wkt_loads(geom_str)
    except Exception as e:
        print(f"Error parseando la cadena de geometría (se esperaba WKT): '{geom_str}' - {e}")
        return None

def load_graphml_to_postgres(graphml_path, engine):
    print(f"Cargando el archivo GraphML: {graphml_path}")
    G = nx.read_graphml(graphml_path)
    print(f"Archivo GraphML cargado. Nodos: {len(G.nodes)}, Aristas: {len(G.edges)}")

    conn_pg = None
    try:
        conn_pg = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT)
        cur_pg = conn_pg.cursor()
        conn_pg.autocommit = False

        print("Preparando e insertando nodos...")
        node_data_for_insert = []
        for node_id, data in G.nodes(data=True):
            x = float(data.get('x')) if data.get('x') is not None else None
            y = float(data.get('y')) if data.get('y') is not None else None
            geom_wkt = f"POINT({x} {y})" if x is not None and y is not None else None
            node_data_for_insert.append((
                node_id,
                x,
                y,
                int(data.get('street_count')) if data.get('street_count') else None,
                data.get('highway'),
                data.get('junction'),
                data.get('railway'),
                data.get('ref'),
                geom_wkt
            ))

        node_columns = ["id", "x", "y", "street_count", "highway", "junction", "railway", "ref", "geom"]

        node_insert_query = sql.SQL(
            "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT (id) DO NOTHING"
        ).format(
            sql.Identifier("nodes"),
            sql.SQL(', ').join(map(sql.Identifier, node_columns)),
            sql.SQL(', ').join([
                sql.Placeholder() for _ in node_columns[:-1]
            ] + [
                sql.SQL("ST_SetSRID(ST_GeomFromText({}), 32718)").format(sql.Placeholder())
            ])
        )

        if node_data_for_insert:
            cur_pg.executemany(node_insert_query, node_data_for_insert)
            print(f"Insertados {len(node_data_for_insert)} nodos.")
        else:
            print("No hay nodos para insertar.")

        print("Preparando e insertando aristas...")
        edge_data_for_insert = []
        for u, v, key, data in G.edges(keys=True, data=True):
            geom_shapely = parse_geometry_string(data.get('geometry'))
            geom_wkt = geom_shapely.wkt if geom_shapely else None

            osmid_raw = data.get('osmid')
            osmid_processed = None
            if osmid_raw is not None:
                try:
                    parsed_osmid = json.loads(osmid_raw)
                    if isinstance(parsed_osmid, list):
                        osmid_processed = parsed_osmid
                    else:
                        osmid_processed = [parsed_osmid]
                except (json.JSONDecodeError, TypeError):
                    try:
                        single_id = int(osmid_raw)
                        osmid_processed = [single_id]
                    except ValueError:
                        osmid_processed = [str(osmid_raw)]

            osmid_processed = json.dumps(osmid_processed) if osmid_processed else None

            edge_data_for_insert.append((
                u,
                v,
                osmid_processed,
                float(data.get('length')) if data.get('length') else None,
                float(data.get('travel_time')) if data.get('travel_time') else None,
                float(data.get('speed_kph')) if data.get('speed_kph') else None,
                data.get('oneway', 'False').lower() == 'true',
                data.get('reversed', 'False').lower() == 'true',
                data.get('highway'),
                data.get('name'),
                data.get('maxspeed'),
                data.get('ref'),
                data.get('lanes'),
                data.get('service'),
                data.get('bridge'),
                data.get('access'),
                data.get('tunnel'),
                data.get('junction'),
                data.get('width'),
                geom_wkt
            ))

        edge_columns = [
            "u", "v", "osmid", "length", "travel_time", "speed_kph", "oneway", "reversed",
            "highway", "name", "maxspeed", "ref", "lanes", "service", "bridge", "access",
            "tunnel", "junction", "width", "geom"
        ]

        edge_insert_placeholders = []
        for col_name in edge_columns:
            if col_name == "osmid":
                edge_insert_placeholders.append(sql.SQL("CAST({} AS JSONB)").format(sql.Placeholder()))
            elif col_name == "geom":
                edge_insert_placeholders.append(sql.SQL("ST_SetSRID(ST_GeomFromText({}), 32718)").format(sql.Placeholder()))
            else:
                edge_insert_placeholders.append(sql.Placeholder())

        edge_insert_query = sql.SQL(
            "INSERT INTO {} ({}) VALUES ({})"
        ).format(
            sql.Identifier("edges"),
            sql.SQL(', ').join(map(sql.Identifier, edge_columns)),
            sql.SQL(', ').join(edge_insert_placeholders)
        )

        if edge_data_for_insert:
            cur_pg.executemany(edge_insert_query, edge_data_for_insert)
            print(f"Insertadas {len(edge_data_for_insert)} aristas.")
        else:
            print("No hay aristas para insertar.")

        conn_pg.commit()
        print("\u2705 Datos cargados en la tabla con éxito.")

    except psycopg2.Error as e:
        if conn_pg:
            conn_pg.rollback()
        print(f"Error de base de datos: {e}")
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")
    finally:
        if conn_pg:
            cur_pg.close()
            conn_pg.close()

if __name__ == "__main__":
    load_graphml_to_postgres(path, engine)
