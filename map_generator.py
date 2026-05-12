# map_generator.py
# Genera el mapa interactivo con Folium y lo abre en el navegador.

import folium
import os
import webbrowser

# Centro aproximado de Barranquilla
BARRANQUILLA_LAT = 10.965
BARRANQUILLA_LON = -74.796

# Archivo de salida del mapa
MAPA_HTML = os.path.join(os.path.dirname(__file__), "mapa_ruta.html")

def generar_mapa(G, camino):
    # Crea un mapa Folium con:
    #   - Marcadores para cada parada de la ruta encontrada.
    #   - Una línea que dibuja el recorrido entre ellas.
    # Abre el mapa automáticamente en el navegador.
    mapa = folium.Map(
        location=[BARRANQUILLA_LAT, BARRANQUILLA_LON],
        zoom_start=13,
        tiles="CartoDB positron",   # Estilo minimalista claro
    )

    # Coordenadas de la ruta para dibujar la línea
    coordenadas = []

    for i, stop_id in enumerate(camino):
        nodo = G.nodes[stop_id]
        lat = nodo.get("lat")
        lon = nodo.get("lon")
        nombre = nodo.get("nombre", stop_id)

        if lat is None or lon is None:
            continue

        coordenadas.append([lat, lon])

        # Estación de origen: marcador verde
        if i == 0:
            icono = folium.Icon(color="green", icon="play", prefix="fa")
            popup = f"<b>🟢 ORIGEN</b><br>{nombre}"

        # Estación de destino: marcador rojo
        elif i == len(camino) - 1:
            icono = folium.Icon(color="red", icon="flag", prefix="fa")
            popup = f"<b>🔴 DESTINO</b><br>{nombre}"

        # Paradas intermedias: marcadores azules pequeños
        else:
            icono = folium.Icon(color="blue", icon="circle", prefix="fa")
            popup = f"<b>Parada {i}</b><br>{nombre}"

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup, max_width=250),
            tooltip=nombre,
            icon=icono,
        ).add_to(mapa)

    # Dibujar la línea de la ruta
    if len(coordenadas) >= 2:
        folium.PolyLine(
            locations=coordenadas,
            color="#2563EB",       # Azul moderno
            weight=4,
            opacity=0.85,
            tooltip="Ruta más corta (Dijkstra)",
        ).add_to(mapa)

    # Guardar y abrir el mapa
    mapa.save(MAPA_HTML)
    webbrowser.open(f"file:///{MAPA_HTML}")
    print(f"\n✅ Mapa guardado en: {MAPA_HTML}")
