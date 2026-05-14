# graph_manager.py
# Construye el grafo de Transmetro con NetworkX y calcula rutas.

import networkx as nx
import math
import heapq
import itertools

# ── CONSTANTES TARIFARIAS ────────────────────────────────────────────────────
PRECIO_PASAJE_COP = 3_700      # Precio de un pasaje en COP
MAX_BUSES_POR_PASAJE = 3       # Buses cubiertos por un pasaje (1 entrada + 2 transbordos gratis)

# Constante interna del Dijkstra de ahorro:
# Cada pasaje adicional "pesa" _BIG_KM km ficticios, garantizando que
# siempre se prefiera pagar menos pasajes antes que recorrer menos km.
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
       - 'weight' : 0.0  (caminata interna, sin costo).
       - 'routes' : frozenset() vacío.
       - NO cuentan como tomar un nuevo bus.

    Las aristas de transferencia representan la caminata entre plataformas
    dentro de la misma estación física y son transparentes al sistema tarifario.
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
                G[u][v]["routes"].add(route_id)
            else:
                peso = _distancia_km(G, u, v)
                G.add_edge(u, v, weight=peso, routes={route_id}, type="viaje")

    # ── Aristas de transferencia por parent_station ───────────────────────────
    # Paradas de la misma estación física según el campo parent_station del GTFS.
    if "parent_station" in stops.columns:
        grupos_ps = (
            stops.dropna(subset=["parent_station"])
            .groupby("parent_station")["stop_id"]
            .apply(list)
        )
        for _ps, ids in grupos_ps.items():
            ids_en_grafo = [sid for sid in ids if sid in G.nodes]
            for i in range(len(ids_en_grafo)):
                for j in range(i + 1, len(ids_en_grafo)):
                    u, v = ids_en_grafo[i], ids_en_grafo[j]
                    if not G.has_edge(u, v):
                        G.add_edge(u, v, weight=0.0, routes=frozenset(), type="transferencia")

    # ── Aristas de transferencia por stop_name (fallback sin parent_station) ──
    if "stop_name" in stops.columns:
        ya_cubiertos: set = set()
        if "parent_station" in stops.columns:
            ya_cubiertos = set(stops.dropna(subset=["parent_station"])["stop_id"].tolist())

        grupos_nombre = (
            stops[~stops["stop_id"].isin(ya_cubiertos)]
            .dropna(subset=["stop_name"])
            .groupby("stop_name")["stop_id"]
            .apply(list)
        )
        for _nombre, ids in grupos_nombre.items():
            ids_en_grafo = [sid for sid in ids if sid in G.nodes]
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


# ── CONTEO DE BUSES Y TRANSBORDOS ─────────────────────────────────────────────

def _contar_buses(G, camino):
    """
    Cuenta el número de buses distintos tomados en el camino.
    Las aristas de transferencia NO incrementan el contador (son caminatas).

    Relación directa con transbordos:
        transbordos = max(0, buses_tomados - 1)
    """
    if not camino or len(camino) < 2:
        return 0

    buses = 0
    rutas_activas = None

    for i in range(len(camino) - 1):
        data = G.get_edge_data(camino[i], camino[i + 1]) or {}
        if data.get("type") == "transferencia":
            continue  # Caminata interna: no cuenta como bus nuevo

        rutas_tramo = data.get("routes", set())
        if isinstance(rutas_tramo, str):
            rutas_tramo = {rutas_tramo}

        if rutas_activas is None:
            rutas_activas = set(rutas_tramo)
            buses = 1  # Primer bus abordado
        else:
            interseccion = rutas_activas & rutas_tramo
            if interseccion:
                rutas_activas = interseccion  # Mismo bus, continúa
            else:
                buses += 1  # Cambio de bus (transbordo)
                rutas_activas = set(rutas_tramo)

    return buses


def contar_transbordos(G, camino):
    """
    Cuenta los transbordos REALES en un camino.

    Un transbordo = cambio obligatorio de bus (no hay ruta en común).
    Las aristas de transferencia (caminatas dentro de la estación) no cuentan.

    Fórmula: transbordos = buses_tomados - 1  (cuando buses_tomados >= 1)
    """
    buses = _contar_buses(G, camino)
    return max(0, buses - 1)


# ── TARIFA ────────────────────────────────────────────────────────────────────

def calcular_costo_pasaje(buses_tomados: int):
    """
    Calcula el costo del viaje según el número de buses tomados.

    Reglas tarifarias de Transmetro:
      - 1 pasaje ($3,700 COP) cubre 1, 2 o 3 buses (hasta 2 transbordos gratuitos).
      - Al tomar el 4to bus se requiere un 2do pasaje.
      - Al tomar el 7mo bus se requiere un 3er pasaje.
      - Fórmula: pasajes = ceil(buses_tomados / 3)

    Retorna: (pasajes_necesarios, costo_total_cop)
    """
    if buses_tomados <= 0:
        return 0, 0
    pasajes = math.ceil(buses_tomados / MAX_BUSES_POR_PASAJE)
    costo = pasajes * PRECIO_PASAJE_COP
    return pasajes, costo


# ── DIJKSTRA ESTÁNDAR (modo Rápido) ──────────────────────────────────────────

def calcular_ruta_dijkstra(G, origen_id, destino_id):
    """
    Dijkstra clásico: minimiza la distancia total en km.
    Retorna (camino, distancia_km) o (None, None).
    """
    try:
        camino = nx.dijkstra_path(G, origen_id, destino_id, weight="weight")
        distancia = nx.dijkstra_path_length(G, origen_id, destino_id, weight="weight")
        return camino, round(distancia, 3)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None, None


def calcular_ruta_con_tiempo(G, origen_id, destino_id, velocidad_kmh=22):
    """Dijkstra + tiempo estimado. Retorna (camino, km, min) o (None, None, None)."""
    camino, distancia = calcular_ruta_dijkstra(G, origen_id, destino_id)
    if camino is None:
        return None, None, None
    tiempo = round((distancia / velocidad_kmh) * 60, 1)
    return camino, distancia, tiempo


# ── DIJKSTRA DE AHORRO (modo Ahorro — costo tarifario real) ──────────────────

def _dijkstra_ahorro(G, origen_id, destino_id):
    """
    Dijkstra con función de costo basada en el sistema tarifario real de Transmetro.

    Costo efectivo = pasajes_pagados × _BIG_KM + km_reales

    Esto garantiza que:
      - Una ruta que cuesta 1 pasaje SIEMPRE vence a una de 2 pasajes,
        sin importar la distancia física.
      - Entre dos rutas con igual número de pasajes, se elige la más corta.

    La frontera de pasajes ocurre cada 3 buses (1→1 pasaje, 4→2 pasajes,
    7→3 pasajes, etc.). Al cruzar esa frontera, el costo efectivo sube en
    _BIG_KM, garantizando que el algoritmo la evite si existe una alternativa.

    Estado de búsqueda: (stop_id, buses_tomados, frozenset_rutas_activas)
      - buses_tomados  : cantidad de buses distintos abordados hasta el nodo.
      - rutas_activas  : routes con las que se puede continuar sin transbordo.

    Aristas de transferencia (type='transferencia'):
      - Peso 0, no incrementan buses_tomados.
      - Representan la caminata entre plataformas de la misma estación.

    Usa itertools.count() como desempate en heapq (evita comparar frozensets).

    Retorna (camino, distancia_km_real, buses_tomados) o (None, None, None).
    """
    if origen_id not in G.nodes or destino_id not in G.nodes:
        return None, None, None
    if origen_id == destino_id:
        return [origen_id], 0.0, 0

    INF = float("inf")
    _tie = itertools.count()

    dist: dict = {}   # estado → costo_efectivo_mínimo_conocido
    prev: dict = {}   # estado → estado_predecesor (para reconstruir camino)

    estado_ini = (origen_id, 0, frozenset())
    dist[estado_ini] = 0.0
    prev[estado_ini] = None

    # Heap: (costo_efectivo, tie_break, stop_id, buses_tomados, rutas_frozenset)
    heap = [(0.0, next(_tie), origen_id, 0, frozenset())]

    while heap:
        costo_ef, _, stop, buses, rutas_activas = heapq.heappop(heap)
        estado = (stop, buses, rutas_activas)

        if costo_ef > dist.get(estado, INF):
            continue  # Entrada obsoleta

        if stop == destino_id:
            # Reconstruir camino hacia atrás
            camino = []
            s = estado
            while s is not None:
                camino.append(s[0])
                s = prev.get(s)
            camino.reverse()
            # Distancia real (sin el componente ficticio de pasajes)
            km_real = sum(
                G[camino[i]][camino[i + 1]].get("weight", 0.0)
                for i in range(len(camino) - 1)
            )
            return camino, round(km_real, 3), buses

        for vecino, data in G[stop].items():
            peso = data.get("weight", 0.0)
            edge_type = data.get("type", "viaje")

            if edge_type == "transferencia":
                # Caminata interna: sin costo tarifario, sin nuevo bus
                nuevo_estado = (vecino, buses, rutas_activas)
                nuevo_costo_ef = costo_ef  # peso = 0.0

            else:
                # Arista de viaje: verificar si hay cambio de bus
                rutas_tramo = data.get("routes", set())
                if isinstance(rutas_tramo, str):
                    rutas_tramo = frozenset({rutas_tramo})
                else:
                    rutas_tramo = frozenset(rutas_tramo)

                if not rutas_activas:
                    # ── Primer abordaje ────────────────────────────────────────
                    # Primer bus siempre paga 1 pasaje completo.
                    nuevo_buses = 1
                    nuevo_estado = (vecino, nuevo_buses, rutas_tramo)
                    nuevo_costo_ef = costo_ef + peso + _BIG_KM  # 1er pasaje

                else:
                    comun = rutas_activas & rutas_tramo
                    if comun:
                        # ── Mismo bus, sin transbordo ──────────────────────────
                        nuevo_buses = buses
                        nuevo_estado = (vecino, nuevo_buses, comun)
                        nuevo_costo_ef = costo_ef + peso

                    else:
                        # ── Transbordo: se toma un nuevo bus ──────────────────
                        nuevo_buses = buses + 1
                        # ¿Se cruza la frontera de pasajes?
                        # Cada 3 buses = 1 pasaje → frontera en bus 4, 7, 10...
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

    return None, None, None  # No existe ruta en el grafo


# ── FUNCIÓN MAESTRA DE BÚSQUEDA ───────────────────────────────────────────────

def buscar_ruta_optima(G, ids_origen, ids_destino, modo="ahorro", velocidad_kmh=22):
    """
    Función maestra de búsqueda de rutas para Transmetro.

    Parámetros:
      ids_origen  : stop_id (str) o lista de stop_ids.
      ids_destino : stop_id (str) o lista de stop_ids.
      modo        : 'ahorro' | 'rapido'

        'ahorro' → Minimiza pasajes pagados.
                   Entre rutas con igual costo tarifario, elige la más corta.
                   Usa _dijkstra_ahorro con costo = pasajes × _BIG_KM + km.

        'rapido' → Minimiza distancia/tiempo.
                   Puede pagar más pasajes si la ruta es más corta.
                   Usa Dijkstra clásico (weight='weight').

      velocidad_kmh: Para calcular el tiempo estimado.

    Cuando se pasan listas de IDs, prueba TODAS las combinaciones
    (origen × destino) y devuelve el par óptimo según el modo elegido.
    Esto permite seleccionar la plataforma más conveniente en estaciones
    con múltiples stop_ids.

    Retorna: (camino, distancia_km, buses_tomados) o (None, None, None).

    El tiempo estimado se calcula externamente:
        tiempo_min = round((distancia_km / velocidad_kmh) * 60, 1)
    """
    # Normalizar entradas a listas
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
                # Criterio primario: menos pasajes. Secundario: menos distancia.
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
                # Criterio: menos distancia
                es_mejor = distancia < mejor_distancia

            if es_mejor:
                mejor_camino = camino
                mejor_distancia = distancia
                mejor_buses = buses

    if mejor_camino is None:
        return None, None, None

    return mejor_camino, mejor_distancia, int(mejor_buses)


# ── COMPATIBILIDAD CON CÓDIGO ANTERIOR ───────────────────────────────────────
# Estas funciones delegan a la nueva API para no romper importaciones externas.

def calcular_ruta_economica(G, origen_id, destino_id, max_transbordos=None):
    """Alias → _dijkstra_ahorro. Retorna (camino, distancia_km)."""
    camino, distancia, _ = _dijkstra_ahorro(G, origen_id, destino_id)
    return camino, distancia


def calcular_ruta_economica_con_tiempo(G, origen_id, destino_id,
                                       velocidad_kmh=22, max_transbordos=None):
    """Alias → buscar_ruta_optima(modo='ahorro'). Retorna (camino, km, min)."""
    camino, distancia, buses = buscar_ruta_optima(
        G, origen_id, destino_id, modo="ahorro", velocidad_kmh=velocidad_kmh
    )
    if camino is None:
        return None, None, None
    return camino, distancia, round((distancia / velocidad_kmh) * 60, 1)


def resolver_mejor_origen(G, ids_origen, ids_destino, economico=True, velocidad_kmh=22):
    """Alias → buscar_ruta_optima. Retorna (camino, km, min)."""
    modo = "ahorro" if economico else "rapido"
    camino, distancia, buses = buscar_ruta_optima(
        G, ids_origen, ids_destino, modo=modo, velocidad_kmh=velocidad_kmh
    )
    if camino is None:
        return None, None, None
    return camino, distancia, round((distancia / velocidad_kmh) * 60, 1)
