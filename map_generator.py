# map_generator.py
# Genera mapas interactivos con Folium para el grafo de Transmetro Barranquilla.
# Incluye visualización completa del grafo, geocodificación y búsqueda de parada más cercana.

import folium
from folium.plugins import MiniMap
from branca.element import Element
import os
import webbrowser
import math

# Centro geográfico de Barranquilla
BARRANQUILLA_LAT = 10.9685
BARRANQUILLA_LON = -74.7813

# Archivo de salida del mapa
MAPA_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mapa_ruta.html")


# ── UTILIDADES GEOGRÁFICAS ────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia Haversine en km entre dos coordenadas geográficas."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(max(0.0, a)))


def parada_mas_cercana(G, lat: float, lon: float):
    """
    Encuentra la parada del grafo más cercana a una coordenada.
    Retorna (stop_id, nombre_parada, distancia_km) o (None, None, None) si el grafo está vacío.
    """
    mejor_id = None
    mejor_nombre = None
    mejor_dist = float("inf")

    for nodo, datos in G.nodes(data=True):
        n_lat = datos.get("lat")
        n_lon = datos.get("lon")
        if n_lat is None or n_lon is None:
            continue
        dist = _haversine_km(lat, lon, n_lat, n_lon)
        if dist < mejor_dist:
            mejor_dist = dist
            mejor_id = nodo
            mejor_nombre = datos.get("nombre", str(nodo))

    if mejor_id is None:
        return None, None, None
    return mejor_id, mejor_nombre, round(mejor_dist, 4)


# ── GEOCODIFICACIÓN ───────────────────────────────────────────────────────────

def geocodificar_direccion(direccion_texto: str):
    """
    Geocodifica una dirección de texto usando Nominatim (OpenStreetMap).
    Añade ", Barranquilla, Colombia" automáticamente si no está presente.
    Retorna (lat, lon) si tiene éxito, o (None, None) si falla.
    """
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

        texto = direccion_texto.strip()
        if "barranquilla" not in texto.lower() and "colombia" not in texto.lower():
            texto = f"{texto}, Barranquilla, Colombia"

        geolocator = Nominatim(user_agent="transmetro_baq_app")

        try:
            location = geolocator.geocode(texto, timeout=10)
        except GeocoderTimedOut:
            print(f"[geocodificar] Timeout para: {texto}")
            return None, None
        except GeocoderUnavailable:
            print(f"[geocodificar] Servicio no disponible para: {texto}")
            return None, None

        if location:
            return location.latitude, location.longitude

        return None, None

    except Exception as e:
        print(f"[geocodificar] Error inesperado: {e}")
        return None, None


# ── MAPA PRINCIPAL ────────────────────────────────────────────────────────────

def generar_mapa_grafo(
    G,
    ruta_resaltada=None,
    origen_coords=None,
    destino_coords=None,
    parada_origen=None,
    parada_destino=None,
):
    """
    Genera el mapa completo de la red Transmetro con capas interactivas.

    Parámetros:
        G               – Grafo NetworkX con nodos (nombre, lat, lon) y aristas (weight, route).
        ruta_resaltada  – Lista de stop_ids que forman la ruta calculada (se dibuja encima).
        origen_coords   – (lat, lon) de la ubicación real del usuario.
        destino_coords  – (lat, lon) del destino real del usuario.
        parada_origen   – stop_id de la parada más cercana al origen.
        parada_destino  – stop_id de la parada más cercana al destino.
    """
    set_ruta = set(ruta_resaltada) if ruta_resaltada else set()

    # Construir conjunto de aristas que pertenecen a la ruta resaltada
    aristas_ruta: set = set()
    if ruta_resaltada and len(ruta_resaltada) >= 2:
        for i in range(len(ruta_resaltada) - 1):
            a, b = ruta_resaltada[i], ruta_resaltada[i + 1]
            aristas_ruta.add((a, b))
            aristas_ruta.add((b, a))

    # ── Mapa base ─────────────────────────────────────────────────────────────
    mapa = folium.Map(
        location=[BARRANQUILLA_LAT, BARRANQUILLA_LON],
        zoom_start=13,
        tiles="CartoDB positron",
    )

    # Título flotante centrado
    titulo_html = """
    <div style="
        position: fixed; top: 14px; left: 50%; transform: translateX(-50%);
        z-index: 1000; background: white; padding: 8px 22px; border-radius: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.18);
        font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px;
        font-weight: 700; color: #1E293B; pointer-events: none;">
        🚌&nbsp; Red Transmetro &middot; Barranquilla
    </div>
    """
    mapa.get_root().html.add_child(Element(titulo_html))

    # MiniMap en esquina inferior derecha
    MiniMap(position="bottomright", width=160, height=120, zoom_level_offset=-5).add_to(mapa)

    # ── Feature Groups (capas activables) ─────────────────────────────────────
    fg_red = folium.FeatureGroup(name="Red Transmetro", show=True)
    fg_paradas = folium.FeatureGroup(name="Paradas", show=True)

    # ── Aristas ───────────────────────────────────────────────────────────────
    aristas = list(G.edges(data=True))
    n_aristas = len(aristas)
    print(f"\n  Dibujando {n_aristas} aristas...")

    # Primero dibujar aristas normales (fondo), luego las de la ruta (encima)
    aristas_normales = []
    aristas_destacadas = []
    for u, v, _ in aristas:
        if (u, v) in aristas_ruta:
            aristas_destacadas.append((u, v))
        else:
            aristas_normales.append((u, v))

    for idx, (u, v) in enumerate(aristas_normales + aristas_destacadas):
        if idx > 0 and idx % 500 == 0:
            print(f"  Aristas procesadas: {idx}/{n_aristas}...")

        u_d = G.nodes.get(u, {})
        v_d = G.nodes.get(v, {})
        lat_u, lon_u = u_d.get("lat"), u_d.get("lon")
        lat_v, lon_v = v_d.get("lat"), v_d.get("lon")

        if None in (lat_u, lon_u, lat_v, lon_v):
            continue

        en_ruta = (u, v) in aristas_ruta

        folium.PolyLine(
            locations=[[lat_u, lon_u], [lat_v, lon_v]],
            color="#2563EB" if en_ruta else "#94a3b8",
            weight=5 if en_ruta else 1.5,
            opacity=0.9 if en_ruta else 0.35,
        ).add_to(fg_red)

    print(f"  Aristas completadas ({n_aristas}).")
    print("  Generando nodos...")

    # ── Nodos ─────────────────────────────────────────────────────────────────
    for nodo, datos in G.nodes(data=True):
        lat = datos.get("lat")
        lon = datos.get("lon")
        nombre = datos.get("nombre", str(nodo))

        if lat is None or lon is None:
            continue

        es_origen = nodo == parada_origen
        es_destino = nodo == parada_destino
        en_ruta = nodo in set_ruta

        if es_origen:
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(f"<b>🟢 ORIGEN</b><br>{nombre}", max_width=260),
                tooltip=nombre,
                icon=folium.Icon(color="green", icon="play", prefix="fa"),
            ).add_to(fg_paradas)

        elif es_destino:
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(f"<b>🔴 DESTINO</b><br>{nombre}", max_width=260),
                tooltip=nombre,
                icon=folium.Icon(color="red", icon="flag", prefix="fa"),
            ).add_to(fg_paradas)

        elif en_ruta:
            folium.CircleMarker(
                location=[lat, lon],
                radius=7,
                color="#2563EB",
                fill=True,
                fill_color="#DBEAFE",
                fill_opacity=1.0,
                tooltip=nombre,
                popup=folium.Popup(nombre, max_width=200),
            ).add_to(fg_paradas)

        else:
            folium.CircleMarker(
                location=[lat, lon],
                radius=4,
                color="#64748b",
                fill=True,
                fill_opacity=0.7,
                tooltip=nombre,
            ).add_to(fg_paradas)

    # ── Ubicación real del usuario (origen) ───────────────────────────────────
    if origen_coords is not None:
        lat_o, lon_o = origen_coords
        folium.Marker(
            location=[lat_o, lon_o],
            popup=folium.Popup("📍 Tu ubicación", max_width=160),
            tooltip="Tu ubicación",
            icon=folium.Icon(color="purple", icon="user", prefix="fa"),
        ).add_to(mapa)

        # Línea punteada desde ubicación hasta la parada de abordaje
        if parada_origen and parada_origen in G.nodes:
            p = G.nodes[parada_origen]
            p_lat, p_lon = p.get("lat"), p.get("lon")
            if p_lat and p_lon:
                folium.PolyLine(
                    locations=[[lat_o, lon_o], [p_lat, p_lon]],
                    color="#7c3aed",
                    weight=2,
                    dash_array="8 6",
                    opacity=0.8,
                    popup=folium.Popup("🚶 Camina hasta esta parada", max_width=200),
                ).add_to(mapa)

    # ── Ubicación real del destino ────────────────────────────────────────────
    if destino_coords is not None:
        lat_d, lon_d = destino_coords
        folium.Marker(
            location=[lat_d, lon_d],
            popup=folium.Popup("🏁 Tu destino", max_width=160),
            tooltip="Tu destino",
            icon=folium.Icon(color="orange", icon="map-marker", prefix="fa"),
        ).add_to(mapa)

        # Línea punteada desde la parada de bajada hasta el destino
        if parada_destino and parada_destino in G.nodes:
            p = G.nodes[parada_destino]
            p_lat, p_lon = p.get("lat"), p.get("lon")
            if p_lat and p_lon:
                folium.PolyLine(
                    locations=[[p_lat, p_lon], [lat_d, lon_d]],
                    color="#ea580c",
                    weight=2,
                    dash_array="8 6",
                    opacity=0.8,
                    popup=folium.Popup("🚶 Camina hasta tu destino", max_width=200),
                ).add_to(mapa)

    # ── Agregar capas y control ───────────────────────────────────────────────
    fg_red.add_to(mapa)
    fg_paradas.add_to(mapa)
    folium.LayerControl(collapsed=False).add_to(mapa)

    # ── Guardar y abrir ───────────────────────────────────────────────────────
    mapa.save(MAPA_HTML)
    webbrowser.open(f"file:///{MAPA_HTML}")
    print(f"[OK] Mapa guardado en: {MAPA_HTML}")


# ── WRAPPER DE COMPATIBILIDAD ─────────────────────────────────────────────────

def generar_mapa(G, camino):
    """
    Wrapper de compatibilidad con llamadas existentes.
    Llama a generar_mapa_grafo con la ruta resaltada y marcadores de origen/destino.
    """
    generar_mapa_grafo(
        G,
        ruta_resaltada=camino,
        parada_origen=camino[0] if camino else None,
        parada_destino=camino[-1] if camino else None,
    )
