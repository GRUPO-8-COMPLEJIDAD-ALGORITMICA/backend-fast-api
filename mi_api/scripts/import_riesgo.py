import geopandas as gpd
from sqlalchemy import create_engine
import os

DB_URL = "postgresql://postgres:postgres@localhost:5432/fastapi_gis"
engine = create_engine(DB_URL)

# Ruta absoluta o ajustada según ubicación real del archivo
shapefile_path = r"../puntos_riesgo/points.shp"

# Verifica que el archivo exista antes de leer
if not os.path.exists(shapefile_path):
    raise FileNotFoundError(f"No se encontró el archivo: {shapefile_path}")

print("Leyendo puntos de riesgo...")
gdf = gpd.read_file(shapefile_path)
gdf = gdf.set_crs(epsg=4326)

# Eliminar columnas duplicadas
gdf = gdf.loc[:, ~gdf.columns.duplicated()]

# Extraer lat/lon
gdf['lat'] = gdf.geometry.y
gdf['lon'] = gdf.geometry.x

# Asegurar columnas requeridas
if 'id' not in gdf.columns:
    gdf['id'] = [str(i) for i in range(1, len(gdf)+1)]

if 'nombre' not in gdf.columns:
    gdf['nombre'] = None

# Reordenar columnas
gdf = gdf[['id', 'nombre', 'lat', 'lon', 'geometry']]

print("Cargando en la tabla puntos_riesgo...")
gdf.to_postgis("puntos_riesgo", engine, if_exists="replace", index=False)
print("\u2705 puntos_riesgo importados con éxito.")