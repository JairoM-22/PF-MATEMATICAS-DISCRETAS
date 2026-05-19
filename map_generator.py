# map_generator.py
# Genera mapas interactivos con Folium para el grafo de Transmetro Barranquilla.

import folium
from folium.plugins import MiniMap
from branca.element import Element
import os
import re
import sys
import webbrowser
import math

# En Windows el stdout usa cp1252 por defecto; caracteres fuera de ese rango
# (flechas, tildes, emojis) lanzan UnicodeEncodeError en print().
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── NORMALIZACIÓN DE INTERSECCIONES ──────────────────────────────────────────
_ADDR_HASH_RE = re.compile(
    r"^([A-Za-záéíóúÁÉÍÓÚüÜñÑ]+\.?)"
    r"\s+"
    r"(\d{1,3}[A-Za-z]?)"
    r"[\s#]+"
    r"(\d{1,3}[A-Za-z]?)"
    r"(?:[\s\-]+\d{1,3}[A-Za-z]?)?"
    r"(?:\s*,.*)?$",
    re.IGNORECASE,
)

def _normalizar_tipo_via(raw: str):
    r = raw.strip().lower().rstrip(".")
    if r in ("carrera", "cra", "cr"):   return "Carrera"
    if r in ("calle", "cl", "cll"):     return "Calle"
    if r in ("diagonal", "diag", "dg"): return "Diagonal"
    if r in ("transversal", "transv", "tv", "tr"): return "Transversal"
    if r in ("avenida", "av", "avda", "avd", "ave"): return "Avenida"
    if r in ("circular", "circ", "cir"): return "Circular"
    return None

_CONTRAPARTE_VIA = {
    "Carrera": "Calle", "Calle": "Carrera",
    "Diagonal": "Carrera", "Transversal": "Calle",
    "Avenida": "Calle", "Circular": "Carrera",
}

def normalizar_interseccion(texto: str) -> str:
    texto = texto.strip()
    m = _ADDR_HASH_RE.match(texto)
    if not m:
        return texto
    tipo_raw, num_ppal, num_cruce = m.group(1), m.group(2), m.group(3)
    tipo_norm = _normalizar_tipo_via(tipo_raw)
    if tipo_norm is None:
        return texto
    contraparte = _CONTRAPARTE_VIA.get(tipo_norm, "Calle")
    return f"{tipo_norm} {num_ppal} con {contraparte} {num_cruce}, Barranquilla, Colombia"

# Centro geográfico de Barranquilla
BARRANQUILLA_LAT = 10.9685
BARRANQUILLA_LON = -74.7813

MAPA_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mapa_ruta.html")


# ── UTILIDADES GEOGRÁFICAS ────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(max(0.0, a)))


def parada_mas_cercana(G, lat: float, lon: float):
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

def limpiar_direccion_nominatim(texto: str) -> str:
    texto_base = texto.split(", Barranquilla")[0]
    match = re.search(r'([a-zA-Z\s]+\d+[a-zA-Z]?)\s*#\s*(\d+[a-zA-Z]?)\s*-\s*(\d+)', texto_base)
    if match:
        return f"{match.group(1).strip()} y {match.group(2).strip()}"
    match2 = re.search(r'([a-zA-Z\s]+\d+[a-zA-Z]?)\s*#\s*(\d+[a-zA-Z]?)', texto_base)
    if match2:
        return f"{match2.group(1).strip()} y {match2.group(2).strip()}"
    return texto_base


def geocodificar_direccion(direccion_texto: str):
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

        geolocator = Nominatim(user_agent="transmetro_baq_app")
        texto = direccion_texto.strip()

        def _geocode(query: str):
            try:
                return geolocator.geocode(query, timeout=10)
            except (GeocoderTimedOut, GeocoderUnavailable):
                return None

        def _con_ciudad(q: str) -> str:
            if "barranquilla" not in q.lower() and "colombia" not in q.lower():
                return f"{q}, Barranquilla, Colombia"
            return q

        # Estrategia 1: interseccion pura
        normalizado = normalizar_interseccion(texto)
        if normalizado != texto:
            print(f"[DEBUG] Buscando interseccion: {normalizado}")
            loc = _geocode(normalizado)
            if loc:
                return loc.latitude, loc.longitude
            alternativa = normalizado.replace(" con ", " y ")
            print(f"[DEBUG] Reintentando con 'y': {alternativa}")
            loc = _geocode(alternativa)
            if loc:
                return loc.latitude, loc.longitude

        # Estrategia 2: texto libre
        loc = _geocode(_con_ciudad(texto))
        if loc:
            return loc.latitude, loc.longitude

        # Estrategia 3: dirección limpiada
        texto_limpio = limpiar_direccion_nominatim(texto)
        if texto_limpio != texto:
            loc = _geocode(_con_ciudad(texto_limpio))
            if loc:
                return loc.latitude, loc.longitude

        return None, None

    except Exception as e:
        print(f"[geocodificar] Error inesperado: {e}")
        return None, None


# ── AUTOCOMPLETADO DE DIRECCIONES ────────────────────────────────────────────

def get_address_suggestions(query: str) -> list:
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

        texto = query.strip()
        if len(texto) < 3:
            return []

        normalizado = normalizar_interseccion(texto)
        if normalizado != texto:
            texto_busqueda = normalizado
        elif "barranquilla" not in texto.lower() and "colombia" not in texto.lower():
            texto_busqueda = f"{texto}, Barranquilla, Colombia"
        else:
            texto_busqueda = texto

        geolocator = Nominatim(user_agent="transmetro_baq_autocomplete", timeout=5)
        results = geolocator.geocode(
            texto_busqueda,
            exactly_one=False,
            limit=5,
            viewbox=[(11.03, -74.85), (10.90, -74.70)],
            bounded=True,
        )
        if not results:
            return []
        return [r.address for r in results]

    except Exception:
        return []


# ── MAPA PRINCIPAL ────────────────────────────────────────────────────────────

def generar_mapa_grafo(
    G,
    ruta_resaltada=None,
    route_id_resaltado=None,
    origen_coords=None,
    destino_coords=None,
    parada_origen=None,
    parada_destino=None,
):
    """
    Genera el mapa completo de la red Transmetro con capas interactivas.

    ruta_resaltada     - Lista ordenada de stop_ids (camino Dijkstra).
    route_id_resaltado - route_id str de una linea GTFS: escanea todas las
                         aristas del grafo cuyo atributo 'routes' lo contenga.
    """
    # ── Construir conjuntos de aristas/nodos resaltados ────────────────────────
    aristas_ruta: set = set()
    set_ruta:     set = set()

    if route_id_resaltado is not None:
        rid = str(route_id_resaltado)
        for u, v, data in G.edges(data=True):
            routes = data.get("routes", set())
            if rid in routes:
                aristas_ruta.add((u, v))
                aristas_ruta.add((v, u))
                set_ruta.add(u)
                set_ruta.add(v)
        print(f"[DEBUG] route_id={rid} -> {len(aristas_ruta)//2} aristas, {len(set_ruta)} nodos")

    elif ruta_resaltada and len(ruta_resaltada) >= 2:
        set_ruta = set(ruta_resaltada)
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
    MiniMap(position="bottomright", width=160, height=120, zoom_level_offset=-5).add_to(mapa)

    fg_red     = folium.FeatureGroup(name="Red Transmetro", show=True)
    fg_paradas = folium.FeatureGroup(name="Paradas",        show=True)

    # ── Aristas ───────────────────────────────────────────────────────────────
    aristas = list(G.edges(data=True))
    n_aristas = len(aristas)
    print(f"\n  Dibujando {n_aristas} aristas...")

    aristas_normales   = []
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
        lat    = datos.get("lat")
        lon    = datos.get("lon")
        nombre = datos.get("nombre", str(nodo))

        if lat is None or lon is None:
            continue

        es_origen  = nodo == parada_origen
        es_destino = nodo == parada_destino
        en_ruta    = nodo in set_ruta

        if es_origen:
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(f"<b>ORIGEN</b><br>{nombre}", max_width=260),
                tooltip=nombre,
                icon=folium.Icon(color="green", icon="play", prefix="fa"),
            ).add_to(fg_paradas)

        elif es_destino:
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(f"<b>DESTINO</b><br>{nombre}", max_width=260),
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

    # ── Ubicación real del usuario ────────────────────────────────────────────
    if origen_coords is not None:
        lat_o, lon_o = origen_coords
        folium.Marker(
            location=[lat_o, lon_o],
            popup=folium.Popup("Tu ubicacion", max_width=160),
            tooltip="Tu ubicacion",
            icon=folium.Icon(color="purple", icon="user", prefix="fa"),
        ).add_to(mapa)
        if parada_origen and parada_origen in G.nodes:
            p = G.nodes[parada_origen]
            p_lat, p_lon = p.get("lat"), p.get("lon")
            if p_lat and p_lon:
                folium.PolyLine(
                    locations=[[lat_o, lon_o], [p_lat, p_lon]],
                    color="#7c3aed", weight=2, dash_array="8 6", opacity=0.8,
                ).add_to(mapa)

    if destino_coords is not None:
        lat_d, lon_d = destino_coords
        folium.Marker(
            location=[lat_d, lon_d],
            popup=folium.Popup("Tu destino", max_width=160),
            tooltip="Tu destino",
            icon=folium.Icon(color="orange", icon="map-marker", prefix="fa"),
        ).add_to(mapa)
        if parada_destino and parada_destino in G.nodes:
            p = G.nodes[parada_destino]
            p_lat, p_lon = p.get("lat"), p.get("lon")
            if p_lat and p_lon:
                folium.PolyLine(
                    locations=[[p_lat, p_lon], [lat_d, lon_d]],
                    color="#ea580c", weight=2, dash_array="8 6", opacity=0.8,
                ).add_to(mapa)

    fg_red.add_to(mapa)
    fg_paradas.add_to(mapa)
    folium.LayerControl(collapsed=False).add_to(mapa)

    # Guardar con UTF-8 explícito para evitar UnicodeEncodeError en Windows (cp1252)
    html_str = mapa.get_root().render()
    with open(MAPA_HTML, "w", encoding="utf-8") as f:
        f.write(html_str)
    webbrowser.open(f"file:///{MAPA_HTML}")
    print(f"[OK] Mapa guardado en: {MAPA_HTML}")


def generar_mapa(G, camino):
    generar_mapa_grafo(
        G,
        ruta_resaltada=camino,
        parada_origen=camino[0] if camino else None,
        parada_destino=camino[-1] if camino else None,
    )
