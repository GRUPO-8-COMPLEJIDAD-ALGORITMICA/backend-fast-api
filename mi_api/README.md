
## CREAR ENTORNO VIRTUAL CON PYTHON  -V:3.13  recomendado no 14 
## LUEGO ACTIVARLO
venv\Scripts\activate
## LUEGO INSTALAR LAS DEPENDENCIAS DEL REQUERIMENT
## LUEGO SI TIENE DOCKER LEVANTAR EL SERVICIO DE LA BD CON docker-compose 
- docker-compose up -d

## LUEGO EJECUTAR LA QUERY.SQL EN SU BASE DE DATOS

## LUEGO DE TENER LA BD Y EJECUTAR LA QUERY MIGRAR CON LOS SIGUIENTES COMANDOS LOS DATASETS DESDE LA CARPETA APP 
- python import_caminos.py
- python import_respuesta.py
- python import_riesgo.py


## EJECUTAR BACKEND
uvicorn app.main:app --reload
## ALGORITMOS
Usamos Bellman-Ford porque nos permite calcular rutas óptimas entre nodos en un grafo dirigido con pesos asociados al tiempo de viaje. A diferencia de Dijkstra, Bellman-Ford puede adaptarse fácilmente a condiciones futuras más complejas como penalizaciones dinámicas o redireccionamientos. En el contexto de respuesta a emergencias, necesitamos encontrar caminos mínimos en tiempo entre puntos de respuesta y puntos de riesgo, sin asumir que la red es perfectamente jerárquica o positiva."
## FUKERSON