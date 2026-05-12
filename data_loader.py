# data_loader.py
# Carga los archivos GTFS y prepara los datos para construir el grafo.

import pandas as pd
import os

# Directorio GTFS: primero busca en el propio proyecto, luego en Downloads como fallback
_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gtfs-baq")
_FALLBACK = r"C:\Users\jairo\Downloads\gtfs-baq"
GTFS_DIR = _LOCAL if os.path.isdir(_LOCAL) else _FALLBACK

def cargar_datos():
    # Lee los archivos GTFS necesarios y retorna DataFrames limpios.
    # Retorna: stops, stop_times, trips, routes
    stops = pd.read_csv(os.path.join(GTFS_DIR, "stops.txt"))
    stop_times = pd.read_csv(os.path.join(GTFS_DIR, "stop_times.txt"))
    trips = pd.read_csv(os.path.join(GTFS_DIR, "trips.txt"))
    routes = pd.read_csv(os.path.join(GTFS_DIR, "routes.txt"))

    # Solo conservar paraderos físicos (location_type == 0 o vacío)
    stops = stops[stops["location_type"].isin([0]) | stops["location_type"].isna()]

    # Columnas esenciales para stop_times
    stop_times = stop_times[["trip_id", "stop_id", "stop_sequence"]].copy()

    return stops, stop_times, trips, routes

def obtener_paradas_unicas(stops):
    # Retorna un diccionario {stop_id: stop_name} solo de paradas con nombre.
    paradas = stops.dropna(subset=["stop_name"])
    return dict(zip(paradas["stop_id"], paradas["stop_name"]))
