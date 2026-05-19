# graph_manager.py
# Construye el grafo de Transmetro con NetworkX y calcula rutas.

import networkx as nx
import math
import heapq
import itertools
import pandas as pd

# ── CONSTANTES TARIFARIAS ────────────────────────────────────────────────────
PRECIO_PASAJE_COP = 3_700
MAX_BUSES_POR_PASAJE = 3
_BIG_KM = 10_000


# ── CONSTRUCCIÓN DEL GRAFO ────────────────────────────────────────────────────

def construir_grafo(stops, stop_times, trips):
    """
    Construye un grafo NO dirigido con dos tipos de aristas:

    1. Aristas de VIAJE (type='viaje'):
       - Conectan paradas consecutivas de un mismo trip.
       - 'weight' : distancia Haversine en km.
       - 'routes' : set con todos los route_ids que transitan el tramo.

    2. Aristas de TRANSFERENCIA (type='transferencia'):
       - Conectan stop_ids que comparten parent_station o stop_name.
       - 'weight' : 0.0
       - 'routes' : frozenset() vacío.
    """
    G = nx.Graph()

    # Normalizar stop_id a str para que coincida con los str de stop_times
    stops_norm = stops.copy()
    stops_norm["stop_id"] = stops_norm["stop_id"].astype(str)
    stop_info = stops_norm.set_index("stop_id")[
        ["stop_name", "stop_lat", "stop_lon"]
    ].to_dict("index")

    for stop_id, info in stop_info.items():
        G.add_node(
            stop_id,
            nombre=info["stop_name"],
            lat=float(info["stop_lat"]),
            lon=float(info["stop_lon"]),
        )

    # Normalizar route/trip ids a str
    trip_to_route = {
        str(tid): str(rid)
        for tid, rid in zip(trips["trip_id"], trips["route_id"])
    }

    # CRITICO: forzar stop_sequence a entero ANTES de ordenar.
    # Si la columna es object/string, sort_values ordena lexicograficamente:
    # "1","10","11","2","3"... creando aristas entre paradas no consecutivas.
    st = stop_times.copy()
    st["stop_sequence"] = (
        pd.to_numeric(st["stop_sequence"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    st["trip_id"] = st["trip_id"].astype(str)
    st["stop_id"]  = st["stop_id"].astype(str)
    st_sorted = st.sort_values(["trip_id", "stop_sequence"])

    # sort=False: el DataFrame ya esta ordenado; groupby no debe re-ordenar.
    for trip_id, grupo in st_sorted.groupby("trip_id", sort=False):
        paradas_raw = grupo["stop_id"].tolist()

        # Eliminar stop_ids consecutivos duplicados
        paradas = [paradas_raw[0]]
        for p in paradas_raw[1:]:
            if p != paradas[-1]:
                paradas.append(p)

        route_id = trip_to_route.get(str(trip_id), "?")

        for i in range(len(paradas) - 1):
            u, v = paradas[i], paradas[i + 1]
            if u == v:
                continue
            if u not in G.nodes or v not in G.nodes:
                continue

            if G.has_edge(u, v):
                G[u][v]["routes"].add(route_id)
            else:
                peso = _distancia_km(G, u, v)
                G.add_edge(u, v, weight=peso, routes={route_id}, type="viaje")

    # ── Aristas de transferencia por parent_station ───────────────────────────
    if "parent_station" in stops_norm.columns:
        grupos_ps = (
            stops_norm.dropna(subset=["parent_station"])
            .groupby("parent_station")["stop_id"]
            .apply(list)
        )
        for _ps, ids in grupos_ps.items():
            ids_en_grafo = [str(sid) for sid in ids if str(sid) in G.nodes]
            for i in range(len(ids_en_grafo)):
                for j in range(i + 1, len(ids_en_grafo)):
                    u, v = ids_en_grafo[i], ids_en_grafo[j]
                    if not G.has_edge(u, v):
                        G.add_edge(u, v, weight=0.0, routes=frozenset(), type="transferencia")

    # ── Aristas de transferencia por stop_name ──────────────────────────────
    if "stop_name" in stops_norm.columns:
        ya_cubiertos: set = set()
        if "parent_station" in stops_norm.columns:
            ya_cubiertos = set(
                stops_norm.dropna(subset=["parent_station"])["stop_id"].astype(str).tolist()
            )

        grupos_nombre = (
            stops_norm[~stops_norm["stop_id"].isin(ya_cubiertos)]
            .dropna(subset=["stop_name"])
            .groupby("stop_name")["stop_id"]
            .apply(list)
        )
        for _nombre, ids in grupos_nombre.items():
            ids_en_grafo = [str(sid) for sid in ids if str(sid) in G.nodes]
            if len(ids_en_grafo) > 1:
                for i in range(len(ids_en_grafo)):
                    for j in range(i + 1, len(ids_en_grafo)):
                        u, v = ids_en_grafo[i], ids_en_grafo[j]
                        if not G.has_edge(u, v):
                            G.add_edge(u, v, weight=0.0, routes=frozenset(), type="transferencia")

    componente_mayor = max(nx.connected_components(G), key=len)
    G = G.subgraph(componente_mayor).copy()
    return G


# ── HAVERSINE ─────────────────────────────────────────────────────────────────

def _distancia_km(G, nodo_a, nodo_b):
    try:
        lat1 = math.radians(G.nodes[nodo_a]["lat"])
        lon1 = math.radians(G.nodes[nodo_a]["lon"])
        lat2 = math.radians(G.nodes[nodo_b]["lat"])
        lon2 = math.radians(G.nodes[nodo_b]["lon"])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return round(6371 * 2 * math.asin(math.sqrt(a)), 4)
    except Exception:
        return 1.0


# ── CONTEO DE BUSES Y TRANSBORDOS ─────────────────────────────────────────────

def _contar_buses(G, camino):
    if not camino or len(camino) < 2:
        return 0

    buses = 0
    rutas_activas = None

    for i in range(len(camino) - 1):
        data = G.get_edge_data(camino[i], camino[i + 1]) or {}
        if data.get("type") == "transferencia":
            continue

        rutas_tramo = data.get("routes", set())
        if isinstance(rutas_tramo, str):
            rutas_tramo = {rutas_tramo}

        if rutas_activas is None:
            rutas_activas = set(rutas_tramo)
            buses = 1
        else:
            interseccion = rutas_activas & rutas_tramo
            if interseccion:
                rutas_activas = interseccion
            else:
                buses += 1
                rutas_activas = set(rutas_tramo)

    return buses


def contar_transbordos(G, camino):
    buses = _contar_buses(G, camino)
    return max(0, buses - 1)


# ── TARIFA ────────────────────────────────────────────────────────────────────

def calcular_costo_pasaje(buses_tomados: int):
    if buses_tomados <= 0:
        return 0, 0
    pasajes = math.ceil(buses_tomados / MAX_BUSES_POR_PASAJE)
    costo = pasajes * PRECIO_PASAJE_COP
    return pasajes, costo


# ── DIJKSTRA ESTÁNDAR ─────────────────────────────────────────────────────────

def calcular_ruta_dijkstra(G, origen_id, destino_id):
    try:
        camino = nx.dijkstra_path(G, origen_id, destino_id, weight="weight")
        distancia = nx.dijkstra_path_length(G, origen_id, destino_id, weight="weight")
        return camino, round(distancia, 3)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None, None


def calcular_ruta_con_tiempo(G, origen_id, destino_id, velocidad_kmh=22):
    camino, distancia = calcular_ruta_dijkstra(G, origen_id, destino_id)
    if camino is None:
        return None, None, None
    tiempo = round((distancia / velocidad_kmh) * 60, 1)
    return camino, distancia, tiempo


# ── DIJKSTRA DE AHORRO ────────────────────────────────────────────────────────

def _dijkstra_ahorro(G, origen_id, destino_id):
    if origen_id not in G.nodes or destino_id not in G.nodes:
        return None, None, None
    if origen_id == destino_id:
        return [origen_id], 0.0, 0

    INF = float("inf")
    _tie = itertools.count()

    dist: dict = {}
    prev: dict = {}

    estado_ini = (origen_id, 0, frozenset())
    dist[estado_ini] = 0.0
    prev[estado_ini] = None

    heap = [(0.0, next(_tie), origen_id, 0, frozenset())]

    while heap:
        costo_ef, _, stop, buses, rutas_activas = heapq.heappop(heap)
        estado = (stop, buses, rutas_activas)

        if costo_ef > dist.get(estado, INF):
            continue

        if stop == destino_id:
            camino = []
            s = estado
            while s is not None:
                camino.append(s[0])
                s = prev.get(s)
            camino.reverse()
            km_real = sum(
                G[camino[i]][camino[i + 1]].get("weight", 0.0)
                for i in range(len(camino) - 1)
            )
            return camino, round(km_real, 3), buses

        for vecino, data in G[stop].items():
            peso = data.get("weight", 0.0)
            edge_type = data.get("type", "viaje")

            if edge_type == "transferencia":
                nuevo_estado = (vecino, buses, rutas_activas)
                nuevo_costo_ef = costo_ef
            else:
                rutas_tramo = data.get("routes", set())
                if isinstance(rutas_tramo, str):
                    rutas_tramo = frozenset({rutas_tramo})
                else:
                    rutas_tramo = frozenset(rutas_tramo)

                if not rutas_activas:
                    nuevo_buses = 1
                    nuevo_estado = (vecino, nuevo_buses, rutas_tramo)
                    nuevo_costo_ef = costo_ef + peso + _BIG_KM
                else:
                    comun = rutas_activas & rutas_tramo
                    if comun:
                        nuevo_buses = buses
                        nuevo_estado = (vecino, nuevo_buses, comun)
                        nuevo_costo_ef = costo_ef + peso
                    else:
                        nuevo_buses = buses + 1
                        pasajes_antes = math.ceil(buses / MAX_BUSES_POR_PASAJE)
                        pasajes_despues = math.ceil(nuevo_buses / MAX_BUSES_POR_PASAJE)
                        delta_pasajes = pasajes_despues - pasajes_antes
                        nuevo_estado = (vecino, nuevo_buses, rutas_tramo)
                        nuevo_costo_ef = costo_ef + peso + delta_pasajes * _BIG_KM

            if nuevo_costo_ef < dist.get(nuevo_estado, INF):
                dist[nuevo_estado] = nuevo_costo_ef
                prev[nuevo_estado] = estado
                heapq.heappush(
                    heap,
                    (nuevo_costo_ef, next(_tie),
                     nuevo_estado[0], nuevo_estado[1], nuevo_estado[2]),
                )

    return None, None, None


# ── FUNCIÓN MAESTRA DE BÚSQUEDA ───────────────────────────────────────────────

def buscar_ruta_optima(G, ids_origen, ids_destino, modo="ahorro", velocidad_kmh=22):
    if isinstance(ids_origen, str):
        ids_origen = [ids_origen]
    if isinstance(ids_destino, str):
        ids_destino = [ids_destino]

    mejor_camino = None
    mejor_distancia = float("inf")
    mejor_buses = float("inf")

    for o in ids_origen:
        for d in ids_destino:
            if o == d:
                continue

            if modo == "ahorro":
                camino, distancia, buses = _dijkstra_ahorro(G, o, d)
            else:
                camino, distancia = calcular_ruta_dijkstra(G, o, d)
                buses = _contar_buses(G, camino) if camino else 0

            if camino is None or distancia is None:
                continue

            if modo == "ahorro":
                pasajes_cand = math.ceil(buses / MAX_BUSES_POR_PASAJE) if buses > 0 else 0
                pasajes_mej = (
                    math.ceil(mejor_buses / MAX_BUSES_POR_PASAJE)
                    if mejor_buses != float("inf") else float("inf")
                )
                es_mejor = (
                    pasajes_cand < pasajes_mej
                    or (pasajes_cand == pasajes_mej and distancia < mejor_distancia)
                )
            else:
                es_mejor = distancia < mejor_distancia

            if es_mejor:
                mejor_camino = camino
                mejor_distancia = distancia
                mejor_buses = buses

    if mejor_camino is None:
        return None, None, None

    return mejor_camino, mejor_distancia, int(mejor_buses)


# ── COMPATIBILIDAD ───────────────────────────────────────────────────────────

def calcular_ruta_economica(G, origen_id, destino_id, max_transbordos=None):
    camino, distancia, _ = _dijkstra_ahorro(G, origen_id, destino_id)
    return camino, distancia


def calcular_ruta_economica_con_tiempo(G, origen_id, destino_id,
                                       velocidad_kmh=22, max_transbordos=None):
    camino, distancia, buses = buscar_ruta_optima(
        G, origen_id, destino_id, modo="ahorro", velocidad_kmh=velocidad_kmh
    )
    if camino is None:
        return None, None, None
    return camino, distancia, round((distancia / velocidad_kmh) * 60, 1)


def resolver_mejor_origen(G, ids_origen, ids_destino, economico=True, velocidad_kmh=22):
    modo = "ahorro" if economico else "rapido"
    camino, distancia, buses = buscar_ruta_optima(
        G, ids_origen, ids_destino, modo=modo, velocidad_kmh=velocidad_kmh
    )
    if camino is None:
        return None, None, None
    return camino, distancia, round((distancia / velocidad_kmh) * 60, 1)
