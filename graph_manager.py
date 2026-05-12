# graph_manager.py
# Construye el grafo de Transmetro con NetworkX y calcula rutas.

import networkx as nx
import math

def construir_grafo(stops, stop_times, trips):
    # Construye un grafo NO dirigido donde:
    #   Cada nodo es un stop_id con atributos (nombre, lat, lon).
    #   Cada arista conecta paradas consecutivas dentro de un mismo trip.
    #   El peso es la distancia geográfica aproximada (en km).
    # Usamos Graph (no dirigido) para que Dijkstra pueda encontrar rutas en ambas
    # direcciones, dado que el dataset GTFS puede no tener todos los sentidos.
    G = nx.Graph()

    # Diccionarios de atributos de paradas
    stop_info = stops.set_index("stop_id")[["stop_name", "stop_lat", "stop_lon"]].to_dict("index")

    # Agregar nodos al grafo
    for stop_id, info in stop_info.items():
        G.add_node(
            stop_id,
            nombre=info["stop_name"],
            lat=info["stop_lat"],
            lon=info["stop_lon"],
        )

    # Mapeo trip_id -> route_id para etiquetar aristas
    trip_to_route = dict(zip(trips["trip_id"], trips["route_id"]))

    # Ordenar stop_times por trip y secuencia
    st_sorted = stop_times.sort_values(["trip_id", "stop_sequence"])

    # Agregar aristas: conexiones entre paradas consecutivas
    for trip_id, grupo in st_sorted.groupby("trip_id"):
        paradas = grupo["stop_id"].tolist()
        route_id = trip_to_route.get(trip_id, "?")

        for i in range(len(paradas) - 1):
            origen = paradas[i]
            destino = paradas[i + 1]

            # Solo agregar si ambos nodos existen en el grafo
            if origen in G.nodes and destino in G.nodes:
                peso = _distancia_km(G, origen, destino)
                # Si ya existe la arista, no la duplicamos
                if not G.has_edge(origen, destino):
                    G.add_edge(origen, destino, weight=peso, route=route_id)

    # Quedarse solo con el componente conectado más grande.
    # Esto garantiza que Dijkstra siempre encuentre rutas entre paradas.
    componente_mayor = max(nx.connected_components(G), key=len)
    G = G.subgraph(componente_mayor).copy()

    return G

def _distancia_km(G, nodo_a, nodo_b):
    # Calcula la distancia aproximada en km entre dos nodos usando la fórmula de Haversine.
    # Si alguno no tiene coordenadas, retorna 1.0 como peso por defecto.
    try:
        lat1 = math.radians(G.nodes[nodo_a]["lat"])
        lon1 = math.radians(G.nodes[nodo_a]["lon"])
        lat2 = math.radians(G.nodes[nodo_b]["lat"])
        lon2 = math.radians(G.nodes[nodo_b]["lon"])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        return round(6371 * c, 4)  # Radio terrestre en km
    except Exception:
        return 1.0

def calcular_ruta_con_tiempo(G, origen_id, destino_id, velocidad_kmh=22):
    # Igual que calcular_ruta_dijkstra pero también retorna tiempo estimado en minutos.
    # Velocidad promedio de bus urbano en Barranquilla: ~22 km/h.
    # Retorna: (camino, distancia_km, tiempo_minutos) o (None, None, None).
    camino, distancia = calcular_ruta_dijkstra(G, origen_id, destino_id)
    if camino is None:
        return None, None, None
    tiempo = round((distancia / velocidad_kmh) * 60, 1)
    return camino, distancia, tiempo


def calcular_ruta_dijkstra(G, origen_id, destino_id):
    # Aplica el algoritmo de Dijkstra de NetworkX para encontrar
    # el camino más corto entre dos paradas.
    # Dijkstra explora los nodos por costo acumulado creciente,
    # garantizando el camino de menor peso total.
    # Retorna: (lista de stop_ids, distancia total en km)
    # O (None, None) si no hay camino.
    try:
        camino = nx.dijkstra_path(G, origen_id, destino_id, weight="weight")
        distancia = nx.dijkstra_path_length(G, origen_id, destino_id, weight="weight")
        return camino, round(distancia, 3)
    except nx.NetworkXNoPath:
        return None, None
    except nx.NodeNotFound:
        return None, None
