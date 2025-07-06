import geopandas as gpd
from sqlalchemy import create_engine, text
import pandas as pd

DB_URL = "postgresql://postgres:postgres@localhost:5432/fastapi_gis"
engine = create_engine(DB_URL)

# Leer el archivo shapefile y asegurar CRS
print("Leyendo puntos de respuesta...")
gdf = gpd.read_file("../puntos_respuesta/points.shp")
gdf = gdf.set_crs(epsg=4326)

# Eliminar columnas duplicadas
gdf = gdf.loc[:, ~gdf.columns.duplicated()]

# Extraer latitud y longitud desde la geometría
print("Extrayendo lat/lon...")
gdf['lat'] = gdf.geometry.y
gdf['lon'] = gdf.geometry.x

# Reordenar y renombrar columnas si es necesario
if 'id' not in gdf.columns:
    gdf['id'] = [str(i) for i in range(1, len(gdf)+1)]  # ID como string

if 'nombre' not in gdf.columns:
    gdf['nombre'] = None  # Campo vacío si no existe

# Reordenar columnas según la tabla destino
cols = ['id', 'nombre', 'lat', 'lon', 'geometry']
gdf = gdf[cols]

# Escribir en PostGIS con reemplazo
print("Cargando en la tabla puntos_respuesta...")
gdf.to_postgis("puntos_respuesta", engine, if_exists="replace", index=False)
print("\u2705 puntos_respuesta importados con éxito.")
