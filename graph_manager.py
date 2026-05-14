# graph_manager.py
# Construye el grafo de Transmetro con NetworkX y calcula rutas.

import networkx as nx
import math
import heapq
import itertools

# ── CONSTANTES TARIFARIAS ────────────────────────────────────────────────────
PRECIO_PASAJE_COP = 3_700          # Precio de un pasaje en COP
MAX_TRANSBORDOS_POR_PASAJE = 2     # Transbordos incluidos en un pasaje


# ── CONSTRUCCIÓN DEL GRAFO ────────────────────────────────────────────────────

def construir_grafo(stops, stop_times, trips):
    """
    Construye un grafo NO dirigido donde:
      - Cada nodo es un stop_id con atributos (nombre, lat, lon).
      - Cada arista conecta paradas consecutivas de un mismo viaje.
      - 'weight'  : distancia Haversine en km.
      - 'routes'  : set con TODOS los route_ids que transitan por ese tramo.

    Usar un set en 'routes' permite detectar transbordos reales: si la
    intersección entre las rutas del tramo anterior y el actual es vacía,
    el pasajero DEBE cambiar de vehículo (transbordo real).
    """
    G = nx.Graph()

    stop_info = stops.set_index("stop_id")[["stop_name", "stop_lat", "stop_lon"]].to_dict("index")

    for stop_id, info in stop_info.items():
        G.add_node(
            stop_id,
            nombre=info["stop_name"],
            lat=info["stop_lat"],
            lon=info["stop_lon"],
        )

    trip_to_route = dict(zip(trips["trip_id"], trips["route_id"]))
    st_sorted = stop_times.sort_values(["trip_id", "stop_sequence"])

    for trip_id, grupo in st_sorted.groupby("trip_id"):
        paradas = grupo["stop_id"].tolist()
        route_id = trip_to_route.get(trip_id, "?")

        for i in range(len(paradas) - 1):
            u, v = paradas[i], paradas[i + 1]
            if u not in G.nodes or v not in G.nodes:
                continue

            if G.has_edge(u, v):
                # Acumular la ruta en el set existente
                G[u][v]["routes"].add(route_id)
            else:
                peso = _distancia_km(G, u, v)
                G.add_edge(u, v, weight=peso, routes={route_id})

    componente_mayor = max(nx.connected_components(G), key=len)
    G = G.subgraph(componente_mayor).copy()
    return G


# ── HAVERSINE ─────────────────────────────────────────────────────────────────

def _distancia_km(G, nodo_a, nodo_b):
    """Distancia Haversine en km entre dos nodos del grafo."""
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


# ── TRANSBORDOS ───────────────────────────────────────────────────────────────

def contar_transbordos(G, camino):
    """
    Cuenta los transbordos REALES en un camino usando intersección de sets de rutas.

    Un transbordo ocurre si y sólo si la intersección entre las rutas del tramo
    anterior y las rutas del tramo actual es vacía: el pasajero no puede continuar
    en el mismo vehículo y debe cambiar de bus.

    Precondición: el grafo G fue construido con 'routes' como set por arista.
    """
    if len(camino) < 2:
        return 0

    transbordos = 0
    rutas_activas = None  # None = todavía no hemos tomado ningún tramo

    for i in range(len(camino) - 1):
        data = G.get_edge_data(camino[i], camino[i + 1]) or {}
        rutas_tramo = data.get("routes", set())

        # Compatibilidad con grafos viejos que guardan route como string
        if isinstance(rutas_tramo, str):
            rutas_tramo = {rutas_tramo}

        if rutas_activas is None:
            # Primer tramo: nos subimos a todos los vehículos disponibles
            rutas_activas = set(rutas_tramo)
        else:
            interseccion = rutas_activas & rutas_tramo
            if interseccion:
                # Al menos una ruta en común: continuamos sin transbordo.
                # Las rutas activas se reducen a las que siguen disponibles.
                rutas_activas = interseccion
            else:
                # Ninguna ruta en común: transbordo obligatorio.
                transbordos += 1
                rutas_activas = set(rutas_tramo)

    return transbordos


# ── TARIFA ────────────────────────────────────────────────────────────────────

def calcular_costo_pasaje(transbordos: int):
    """
    Calcula el costo del viaje según la cantidad de transbordos.

    Reglas:
      - Un pasaje ($3 700 COP) incluye hasta 2 transbordos (3 rutas).
      - Por cada 3 transbordos adicionales (o fracción) se paga un pasaje extra.
      - Fórmula: pasajes = (transbordos // 3) + 1

    Retorna: (pasajes_necesarios, costo_total_cop)
    """
    pasajes = (transbordos // (MAX_TRANSBORDOS_POR_PASAJE + 1)) + 1
    costo = pasajes * PRECIO_PASAJE_COP
    return pasajes, costo


# ── RUTAS ESTÁNDAR (Dijkstra) ─────────────────────────────────────────────────

def calcular_ruta_dijkstra(G, origen_id, destino_id):
    """
    Dijkstra clásico sin restricción de transbordos.
    Retorna (camino, distancia_km) o (None, None).
    """
    try:
        camino = nx.dijkstra_path(G, origen_id, destino_id, weight="weight")
        distancia = nx.dijkstra_path_length(G, origen_id, destino_id, weight="weight")
        return camino, round(distancia, 3)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None, None


def calcular_ruta_con_tiempo(G, origen_id, destino_id, velocidad_kmh=22):
    """
    Dijkstra + tiempo estimado en minutos.
    Retorna (camino, distancia_km, tiempo_min) o (None, None, None).
    """
    camino, distancia = calcular_ruta_dijkstra(G, origen_id, destino_id)
    if camino is None:
        return None, None, None
    tiempo = round((distancia / velocidad_kmh) * 60, 1)
    return camino, distancia, tiempo


# ── RUTA ECONÓMICA (Dijkstra con límite de transbordos) ───────────────────────

def calcular_ruta_economica(G, origen_id, destino_id, max_transbordos=2):
    """
    Dijkstra extendido que garantiza un máximo de 'max_transbordos' transbordos.

    Estado de búsqueda: (stop_id, n_transbordos, frozenset_rutas_activas)
      - 'rutas_activas' contiene los route_ids disponibles sin transbordar.
      - Un transbordo se contabiliza solo cuando la intersección con el siguiente
        tramo está vacía (mismo criterio que contar_transbordos).

    Usa un contador auxiliar como desempate en el heap para evitar comparar
    frozensets (que no tienen orden total en Python).

    Retorna (camino, distancia_km) o (None, None) si no existe solución
    dentro del límite de transbordos.
    """
    if origen_id not in G.nodes or destino_id not in G.nodes:
        return None, None
    if origen_id == destino_id:
        return [origen_id], 0.0

    INF = float("inf")
    _tie = itertools.count()   # Desempate para heapq (evita comparar frozensets)

    # dist[(stop, transbordos, rutas)] = costo_minimo_conocido
    dist: dict = {}
    # prev[(stop, transbordos, rutas)] = estado_predecesor (para reconstruir camino)
    prev: dict = {}

    estado_ini = (origen_id, 0, frozenset())
    dist[estado_ini] = 0.0
    prev[estado_ini] = None

    # Heap: (costo, tie_break, stop, transbordos, rutas_frozenset)
    heap = [(0.0, next(_tie), origen_id, 0, frozenset())]

    while heap:
        costo, _, stop, transbordos, rutas_activas = heapq.heappop(heap)
        estado = (stop, transbordos, rutas_activas)

        if costo > dist.get(estado, INF):
            continue  # Entrada obsoleta

        if stop == destino_id:
            # Reconstruir camino hacia atrás
            camino = []
            s = estado
            while s is not None:
                camino.append(s[0])
                s = prev.get(s)
            camino.reverse()
            return camino, round(costo, 3)

        for vecino, data in G[stop].items():
            peso = data.get("weight", 1.0)
            rutas_tramo = data.get("routes", set())
            if isinstance(rutas_tramo, str):
                rutas_tramo = frozenset({rutas_tramo})
            else:
                rutas_tramo = frozenset(rutas_tramo)

            nuevo_costo = costo + peso

            if not rutas_activas:
                # Primer movimiento: abordamos en todas las rutas del tramo
                nuevo_estado = (vecino, transbordos, rutas_tramo)
            else:
                comun = rutas_activas & rutas_tramo
                if comun:
                    # Continuamos sin transbordo; rutas activas se estrechan
                    nuevo_estado = (vecino, transbordos, comun)
                elif transbordos < max_transbordos:
                    # Transbordo forzado (no hay ruta en común)
                    nuevo_estado = (vecino, transbordos + 1, rutas_tramo)
                else:
                    continue  # Límite de transbordos alcanzado, no podemos ir aquí

            if nuevo_costo < dist.get(nuevo_estado, INF):
                dist[nuevo_estado] = nuevo_costo
                prev[nuevo_estado] = estado
                heapq.heappush(
                    heap,
                    (nuevo_costo, next(_tie), nuevo_estado[0], nuevo_estado[1], nuevo_estado[2]),
                )

    return None, None  # No existe ruta con las restricciones dadas


def calcular_ruta_economica_con_tiempo(G, origen_id, destino_id,
                                       velocidad_kmh=22, max_transbordos=2):
    """
    Ruta económica + tiempo estimado en minutos.
    Retorna (camino, distancia_km, tiempo_min) o (None, None, None).
    """
    camino, distancia = calcular_ruta_economica(G, origen_id, destino_id, max_transbordos)
    if camino is None:
        return None, None, None
    tiempo = round((distancia / velocidad_kmh) * 60, 1)
    return camino, distancia, tiempo
