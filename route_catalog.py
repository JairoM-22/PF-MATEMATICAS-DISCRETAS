# route_catalog.py
# Catálogo de rutas y consultas por parada para el dataset GTFS de Transmetro.

import pandas as pd
from data_loader import cargar_datos

# Caché para evitar releer los archivos GTFS en cada llamada
_cache: dict = {}


def _datos():
    if not _cache:
        stops, stop_times, trips, routes = cargar_datos()
        _cache["stops"] = stops
        _cache["stop_times"] = stop_times
        _cache["trips"] = trips
        _cache["routes"] = routes
    return _cache["stops"], _cache["stop_times"], _cache["trips"], _cache["routes"]


def obtener_catalogo_rutas() -> pd.DataFrame:
    stops, stop_times, trips, routes = _datos()

    trip_route = trips[["trip_id", "route_id"]]
    st_route = stop_times.merge(trip_route, on="trip_id", how="left")

    paradas_por_ruta = (
        st_route.groupby("route_id")["stop_id"].nunique().reset_index()
    )
    paradas_por_ruta.columns = ["route_id", "num_paradas"]

    trips_por_ruta = (
        trips.groupby("route_id")["trip_id"].nunique().reset_index()
    )
    trips_por_ruta.columns = ["route_id", "num_trips"]

    catalogo = routes[["route_id", "route_short_name", "route_long_name"]].copy()
    catalogo = catalogo.merge(paradas_por_ruta, on="route_id", how="left")
    catalogo = catalogo.merge(trips_por_ruta, on="route_id", how="left")

    catalogo["num_paradas"] = catalogo["num_paradas"].fillna(0).astype(int)
    catalogo["num_trips"] = catalogo["num_trips"].fillna(0).astype(int)

    return catalogo.reset_index(drop=True)


def paradas_de_ruta(route_id) -> pd.DataFrame:
    stops, stop_times, trips, _ = _datos()

    route_trips = trips[trips["route_id"] == route_id]["trip_id"].unique()
    st_ruta = stop_times[stop_times["trip_id"].isin(route_trips)].copy()

    orden = (
        st_ruta.groupby("stop_id")["stop_sequence"].mean().reset_index()
    )
    orden.columns = ["stop_id", "seq_promedio"]
    orden = orden.sort_values("seq_promedio").reset_index(drop=True)

    resultado = orden.merge(
        stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]],
        on="stop_id",
        how="left",
    )
    return resultado


def rutas_que_pasan_por_parada(stop_id) -> list:
    _, stop_times, trips, _ = _datos()

    trips_parada = stop_times[stop_times["stop_id"] == stop_id]["trip_id"].unique()
    route_ids = trips[trips["trip_id"].isin(trips_parada)]["route_id"].unique().tolist()
    return route_ids


def imprimir_catalogo():
    cat = obtener_catalogo_rutas()
    sep = "=" * 72
    print(f"\n{sep}")
    print("CATÁLOGO DE RUTAS · TRANSMETRO BARRANQUILLA")
    print(sep)
    print(f"  {'ID':<8} {'Código':<8} {'Nombre':<32} {'Paradas':>8} {'Viajes':>8}")
    print("-" * 72)
    for _, row in cat.iterrows():
        print(
            f"  {str(row['route_id']):<8} {str(row['route_short_name']):<8} "
            f"{str(row['route_long_name']):<32} {row['num_paradas']:>8} {row['num_trips']:>8}"
        )
    print(sep)


def imprimir_paradas_ruta(route_id):
    paradas = paradas_de_ruta(route_id)
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"PARADAS DE RUTA {route_id}  ({len(paradas)} paradas)")
    print(sep)
    for i, row in paradas.iterrows():
        nombre = row.get("stop_name", row["stop_id"])
        print(f"  {i + 1:3}. {nombre}")
    print(sep)
