
# DB_PARAMS = {
#     "host": "localhost",
#     "port": "5432",
#     "dbname": "fastapi_gis",
#     "user": "postgres",
#     "password": "postgres"
# }
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any
from shapely.geometry import Point
import networkx as nx
import psycopg2
from pyproj import Transformer
from functools import lru_cache
from geopy.distance import geodesic

from decimal import Decimal

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PARAMS = {
    "host": "localhost",
    "port": "5432",
    "dbname": "fastapi_gis",
    "user": "postgres",
    "password": "postgres"
}

G = None
transformer = Transformer.from_crs("EPSG:32718", "EPSG:4326", always_xy=True)
nodos_respuesta = {}
nodos_riesgo = {}

class Punto(BaseModel):
    id: str
    nombre: str
    lat: float
    lon: float

def reproyectar(x, y):
    lon, lat = transformer.transform(x, y)
    return lat, lon

def ejecutar_query(query: str, params: tuple = ()): 
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    cur.close()
    conn.close()

@app.post("/api/puntos/riesgo")
def cargar_riesgo(puntos: List[Punto]):
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    for p in puntos:
        cur.execute("""
            INSERT INTO puntos_riesgo (id, nombre, lat, lon, geom)
            VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
            ON CONFLICT (id) DO UPDATE SET
                nombre = EXCLUDED.nombre,
                lat = EXCLUDED.lat,
                lon = EXCLUDED.lon,
                geom = EXCLUDED.geom
        """, (p.id, p.nombre, p.lat, p.lon, p.lon, p.lat))
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Puntos de riesgo registrados", "total": len(puntos)}

@app.post("/api/puntos/respuesta")
def cargar_respuesta(puntos: List[Punto]):
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    for p in puntos:
        cur.execute("""
            INSERT INTO puntos_respuesta (id, nombre, lat, lon, geom)
            VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
            ON CONFLICT (id) DO UPDATE SET
                nombre = EXCLUDED.nombre,
                lat = EXCLUDED.lat,
                lon = EXCLUDED.lon,
                geom = EXCLUDED.geom
        """, (p.id, p.nombre, p.lat, p.lon, p.lon, p.lat))
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Puntos de respuesta registrados", "total": len(puntos)}

def cargar_grafo_desde_bd():
    global G
    G = nx.DiGraph()
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute("SELECT id, x, y FROM nodes")
    for node_id, x, y in cur.fetchall():
        lat, lon = reproyectar(x, y)
        G.add_node(node_id, x=float(x), y=float(y), lat=lat, lon=lon)
    cur.execute("SELECT u, v, length, travel_time FROM edges")
    for u, v, length, travel_time in cur.fetchall():
        G.add_edge(u, v, length=float(length), travel_time=float(travel_time))
    cur.close()
    conn.close()

def encontrar_nodo_mas_cercano(lat: float, lon: float, Gref=None) -> int:
    if Gref is None:
        Gref = G
    lat = float(lat)
    lon = float(lon)
    min_dist = float('inf')
    closest_node = None
    for node_id, data in Gref.nodes(data=True):
        node_lat, node_lon = data["lat"], data["lon"]
        dist = (node_lon - lon) ** 2 + (node_lat - lat) ** 2
        if dist < min_dist:
            min_dist = dist
            closest_node = node_id
    return closest_node

@lru_cache(maxsize=2048)
def get_path(Gref, u, v):
    return nx.bellman_ford_path(Gref, u, v, weight="travel_time")

def calcular_tiempo(Gref, path):
    return sum(Gref[u][v]['travel_time'] for u, v in zip(path[:-1], path[1:]))

def subgrafo_con_radio(lat1, lon1, lat2, lon2, radio_km=5.0):
    radio_deg = radio_km / 111
    nodos_filtrados = [
        n for n, d in G.nodes(data=True)
        if (
            min(lat1, lat2) - radio_deg <= d["lat"] <= max(lat1, lat2) + radio_deg and
            min(lon1, lon2) - radio_deg <= d["lon"] <= max(lon1, lon2) + radio_deg
        )
    ]
    return G.subgraph(nodos_filtrados).copy()

@app.on_event("startup")
def precargar():
    cargar_grafo_desde_bd()

@app.post("/api/grafo/desde_bd")
def generar_grafo_desde_bd():
    return {
        "message": "Grafo cargado desde la base de datos",
        "nodos": len(G.nodes),
        "aristas": len(G.edges)
    }

@app.get("/api/asignacion/caminos")
def obtener_rutas_extremas(
    id_respuesta: str = Query(...),
    id_riesgo: str = Query(...)
):
    if G is None:
        raise HTTPException(status_code=400, detail="Debe cargar el grafo primero")

    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    cur.execute("SELECT lat, lon FROM puntos_respuesta WHERE id = %s", (id_respuesta,))
    r = cur.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Respuesta no encontrada")
    r_lat, r_lon = float(r[0]), float(r[1])

    cur.execute("SELECT lat, lon FROM puntos_riesgo WHERE id = %s", (id_riesgo,))
    p = cur.fetchone()
    if not p:
        raise HTTPException(status_code=404, detail="Riesgo no encontrado")
    p_lat, p_lon = float(p[0]), float(p[1])

    cur.close()
    conn.close()

    subG = subgrafo_con_radio(r_lat, r_lon, p_lat, p_lon, radio_km=5)
    r_node = encontrar_nodo_mas_cercano(r_lat, r_lon, subG)
    p_node = encontrar_nodo_mas_cercano(p_lat, p_lon, subG)

    try:
        mejor_camino = get_path(subG, r_node, p_node)
        peor_camino = max(
            nx.all_simple_paths(subG, r_node, p_node, cutoff=10),
            key=lambda path: calcular_tiempo(subG, path),
            default=[]
        )
    except:
        return {"mejor": None, "peor": None}

    def calcular_distancia(grafo, camino):
        return sum(grafo[u][v]['length'] for u, v in zip(camino[:-1], camino[1:]) if 'length' in grafo[u][v])

    def calcular_velocidad(distancia, tiempo):
        if tiempo <= 0:
            return None
        return (distancia / 1000) / (tiempo / 3600)

    def construir(camino):
        if not camino:
            return None
        tiempo = calcular_tiempo(subG, camino)
        distancia = calcular_distancia(subG, camino)
        velocidad = calcular_velocidad(distancia, tiempo)
        return {
            "camino": [
                {"nodo": n, "lat": subG.nodes[n]["lat"], "lon": subG.nodes[n]["lon"]}
                for n in camino
            ],
            "tiempo_estimado": round(tiempo, 2),
            "distancia_total_metros": round(distancia, 2),
            "velocidad_promedio_kph": round(velocidad, 2) if velocidad else None
        }

    return {
        "desde": id_respuesta,
        "hacia": id_riesgo,
        "mejor": construir(mejor_camino),
        "peor": construir(peor_camino)
    }

@app.post("/api/asignacion/flujo")
def asignar_flujo(payload: Dict[str, List[str]]):
    global G
    if G is None:
        raise HTTPException(status_code=400, detail="Debe cargar el grafo primero")

    ids_respuesta = payload.get("respuestas", [])
    ids_riesgo = payload.get("riesgos", [])

    if not ids_respuesta or not ids_riesgo:
        raise HTTPException(status_code=400, detail="Debe proporcionar listas de ids")

    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    cur.execute("SELECT id, lat, lon FROM puntos_respuesta WHERE id = ANY(%s)", (ids_respuesta,))
    respuestas = cur.fetchall()
    cur.execute("SELECT id, lat, lon FROM puntos_riesgo WHERE id = ANY(%s)", (ids_riesgo,))
    riesgos = cur.fetchall()
    cur.close()
    conn.close()

    all_lats = [float(r[1]) for r in respuestas + riesgos]
    all_lons = [float(r[2]) for r in respuestas + riesgos]
    buffer_deg = 0.01
    min_lat, max_lat = min(all_lats) - buffer_deg, max(all_lats) + buffer_deg
    min_lon, max_lon = min(all_lons) - buffer_deg, max(all_lons) + buffer_deg

    nodos_filtrados = [n for n, d in G.nodes(data=True) if min_lat <= d['lat'] <= max_lat and min_lon <= d['lon'] <= max_lon]
    subgrafo = G.subgraph(nodos_filtrados).copy()

    Gf = nx.DiGraph()
    super_source = "fuente"
    super_sink = "sumidero"
    id_to_node = {}

    for rid, lat, lon in respuestas:
        node = min(subgrafo.nodes, key=lambda n: (subgrafo.nodes[n]['lon'] - float(lon))**2 + (subgrafo.nodes[n]['lat'] - float(lat))**2)
        id_to_node[rid] = node
        Gf.add_edge(super_source, node, capacity=1)

    for pid, lat, lon in riesgos:
        node = min(subgrafo.nodes, key=lambda n: (subgrafo.nodes[n]['lon'] - float(lon))**2 + (subgrafo.nodes[n]['lat'] - float(lat))**2)
        id_to_node[pid] = node
        Gf.add_edge(node, super_sink, capacity=1)

    for rid in ids_respuesta:
        for pid in ids_riesgo:
            if rid in id_to_node and pid in id_to_node:
                try:
                    path = nx.bellman_ford_path(subgrafo, id_to_node[rid], id_to_node[pid], weight="travel_time")
                    Gf.add_edge(id_to_node[rid], id_to_node[pid], capacity=1)
                except:
                    continue

    flow_value, flow_dict = nx.maximum_flow(Gf, super_source, super_sink)
    asignaciones = []

    for rid in ids_respuesta:
        for pid in ids_riesgo:
            if flow_dict.get(id_to_node.get(rid), {}).get(id_to_node.get(pid), 0) > 0:
                try:
                    path = nx.bellman_ford_path(subgrafo, id_to_node[rid], id_to_node[pid], weight="travel_time")
                    asignaciones.append({
                        "desde": rid,
                        "hacia": pid,
                        "camino": [
                            {"nodo": n, "lat": subgrafo.nodes[n]["lat"], "lon": subgrafo.nodes[n]["lon"]}
                            for n in path
                        ]
                    })
                except:
                    continue

    return {"flujo_maximo": flow_value, "asignaciones": asignaciones}


@app.get("/api/puntos/listar")
def listar_puntos():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, lat, lon FROM puntos_respuesta")
    respuestas = cur.fetchall()
    cur.execute("SELECT id, nombre, lat, lon FROM puntos_riesgo")
    riesgos = cur.fetchall()
    cur.close()
    conn.close()
    return {
        "respuestas": [
            {"id": r[0], "nombre": r[1], "lat": float(r[2]), "lon": float(r[3])}
            for r in respuestas
        ],
        "riesgos": [
            {"id": p[0], "nombre": p[1], "lat": float(p[2]), "lon": float(p[3])}
            for p in riesgos
        ]
    }