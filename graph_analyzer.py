# graph_analyzer.py
# Métricas y análisis estructural del grafo de Transmetro.

import networkx as nx
from collections import Counter


def calcular_metricas_globales(G):
    try:
        grados = [d for _, d in G.degree()]
        n = len(grados)

        try:
            clustering = round(nx.average_clustering(G), 6)
        except Exception:
            clustering = None

        return {
            "nodos": G.number_of_nodes(),
            "aristas": G.number_of_edges(),
            "densidad": round(nx.density(G), 6),
            "clustering_promedio": clustering,
            "grado_promedio": round(sum(grados) / n, 2) if n else 0,
            "grado_max": max(grados) if grados else 0,
            "grado_min": min(grados) if grados else 0,
            "es_conexo": nx.is_connected(G),
            "num_componentes": nx.number_connected_components(G),
        }
    except Exception as e:
        return {"error": str(e)}


def calcular_degree_centrality(G):
    try:
        return nx.degree_centrality(G)
    except Exception:
        return {}


def calcular_betweenness_centrality(G, muestra=200):
    try:
        k = min(muestra, G.number_of_nodes())
        return nx.betweenness_centrality(G, k=k, weight="weight", normalized=True)
    except Exception:
        return {}


def calcular_closeness_centrality(G):
    try:
        return nx.closeness_centrality(G, distance="weight")
    except Exception:
        return {}


def _nombre(G, stop_id):
    return G.nodes[stop_id].get("nombre", str(stop_id))


def top_paradas_por_centralidad(G, n=10):
    try:
        deg = calcular_degree_centrality(G)
        bet = calcular_betweenness_centrality(G)
        clo = calcular_closeness_centrality(G)

        def top(d):
            return [
                (sid, _nombre(G, sid), round(v, 6))
                for sid, v in sorted(d.items(), key=lambda x: x[1], reverse=True)[:n]
            ]

        return {"degree": top(deg), "betweenness": top(bet), "closeness": top(clo)}
    except Exception as e:
        return {"error": str(e)}


def distribucion_grado(G):
    try:
        return Counter(d for _, d in G.degree())
    except Exception:
        return Counter()


def nodos_criticos(G, top_n=5):
    try:
        bet = calcular_betweenness_centrality(G)
        return [
            (sid, _nombre(G, sid), round(v, 6))
            for sid, v in sorted(bet.items(), key=lambda x: x[1], reverse=True)[:top_n]
        ]
    except Exception:
        return []


def simular_falla_parada(G, stop_id):
    try:
        if stop_id not in G.nodes:
            return {"error": f"La parada '{stop_id}' no existe en el grafo."}

        nombre = _nombre(G, stop_id)
        comp_antes = nx.number_connected_components(G)

        G2 = G.copy()
        G2.remove_node(stop_id)

        comp_despues = nx.number_connected_components(G2)

        return {
            "stop_id": stop_id,
            "nombre": nombre,
            "componentes_antes": comp_antes,
            "componentes_despues": comp_despues,
            "se_fragmento": comp_despues > comp_antes,
            "nodos_restantes": G2.number_of_nodes(),
            "aristas_restantes": G2.number_of_edges(),
        }
    except Exception as e:
        return {"error": str(e)}


def imprimir_reporte_completo(G):
    sep = "=" * 60
    print(f"\n{sep}")
    print("REPORTE DE ANÁLISIS · GRAFO TRANSMETRO BARRANQUILLA")
    print(sep)

    m = calcular_metricas_globales(G)
    if "error" in m:
        print(f"Error: {m['error']}")
        return

    print(f"\n  Nodos (paradas)      : {m['nodos']:,}")
    print(f"  Aristas (conexiones) : {m['aristas']:,}")
    print(f"  Densidad             : {m['densidad']}")
    print(f"  Clustering promedio  : {m['clustering_promedio']}")
    print(f"  Grado promedio       : {m['grado_promedio']}")
    print(f"  Grado máximo         : {m['grado_max']}")
    print(f"  Grado mínimo         : {m['grado_min']}")
    print(f"  Grafo conexo         : {'Sí' if m['es_conexo'] else 'No'}")
    print(f"  Componentes          : {m['num_componentes']}")

    top = top_paradas_por_centralidad(G, n=5)
    if "error" not in top:
        for clave, etiqueta in [("degree", "DEGREE"), ("betweenness", "BETWEENNESS"), ("closeness", "CLOSENESS")]:
            print(f"\n  TOP 5 · {etiqueta} CENTRALITY")
            for i, (_, nombre, val) in enumerate(top[clave], 1):
                print(f"    {i}. {nombre}  ({val})")

    print(f"\n{sep}\n")
