# ui.py
# Interfaz gráfica moderna con CustomTkinter para visualizar el grafo de Transmetro.

import customtkinter as ctk
from tkinter import messagebox
import threading

from data_loader import cargar_datos, obtener_paradas_unicas
from graph_manager import construir_grafo, calcular_ruta_dijkstra, calcular_ruta_con_tiempo
from map_generator import (
    generar_mapa,
    generar_mapa_grafo,
    geocodificar_direccion,
    parada_mas_cercana,
)
import graph_analyzer
import route_catalog

# Configuración visual de CustomTkinter
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# Paleta de colores estilo Apple Moderno
COLOR_BG       = "#F2F2F7"  # System Gray 6 (Light)
COLOR_CARD     = "#FFFFFF"
COLOR_PRIMARIO = "#007AFF"  # Apple Blue
COLOR_TEXTO    = "#1C1C1E"  # Label Color
COLOR_SUBTEXTO = "#8E8E93"  # Secondary Label
COLOR_BORDE    = "#D1D1D6"  # Separator
COLOR_EXITO    = "#34C759"  # Apple Green
COLOR_ERROR    = "#FF3B30"  # Apple Red

FUENTE_TITULO    = ("Segoe UI", 28, "bold")
FUENTE_SUBTITULO = ("Segoe UI", 14)
FUENTE_NORMAL    = ("Segoe UI", 12)
FUENTE_BOTON     = ("Segoe UI", 12, "bold")
FUENTE_MONO      = ("Consolas", 11)


class AppTransmetro(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Transmetro · Smart Route Optimizer")
        self.geometry("1280x850")
        self.minsize(1100, 750)
        self.configure(fg_color=COLOR_BG)

        self.grafo = None
        self.paradas_dict = {}   # {nombre_parada: stop_id}

        self._construir_ui()

        # Carga automática del dataset al iniciar (400 ms de gracia para que la UI renderice)
        self.after(400, self._hilo_cargar)

    # ══════════════════════════════════════════════════════════════════════════
    # CONSTRUCCIÓN DE LA INTERFAZ
    # ══════════════════════════════════════════════════════════════════════════

    def _construir_ui(self):
        # ── Encabezado ────────────────────────────────────────────────────────
        frame_header = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=0, height=80)
        frame_header.pack(fill="x")
        frame_header.pack_propagate(False)

        ctk.CTkLabel(
            frame_header,
            text="Transmetro",
            font=FUENTE_TITULO,
            text_color=COLOR_TEXTO,
        ).pack(side="left", padx=(40, 10), pady=10)

        ctk.CTkLabel(
            frame_header,
            text="Barranquilla · Route Intelligence",
            font=FUENTE_SUBTITULO,
            text_color=COLOR_SUBTEXTO,
        ).pack(side="left", padx=0, pady=(22, 10))

        # ── Contenedor Principal (2 Columnas) ─────────────────────────────────
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # PANEL IZQUIERDO (Controles)
        self.left_panel = ctk.CTkScrollableFrame(
            container, 
            fg_color="transparent", 
            width=420,
            label_text="CONTROLES",
            label_font=("Segoe UI", 10, "bold"),
            label_text_color=COLOR_SUBTEXTO
        )
        self.left_panel.pack(side="left", fill="both", padx=(0, 10))

        # PANEL DERECHO (Resultados)
        right_panel = ctk.CTkFrame(container, fg_color="transparent")
        right_panel.pack(side="right", fill="both", expand=True, padx=(10, 0))

        # ── Tarjeta: Dataset GTFS ─────────────────────────────────────────────
        card_carga = self._crear_card(self.left_panel, titulo="Dataset GTFS")

        self.btn_cargar = ctk.CTkButton(
            card_carga,
            text="Cargar datos GTFS",
            font=FUENTE_BOTON,
            fg_color=COLOR_PRIMARIO,
            hover_color="#005BB7",
            corner_radius=12,
            height=40,
            command=self._hilo_cargar,
        )
        self.btn_cargar.pack(fill="x", pady=(10, 5))

        self.lbl_estado = ctk.CTkLabel(
            card_carga,
            text="Esperando carga...",
            font=FUENTE_NORMAL,
            text_color=COLOR_SUBTEXTO,
        )
        self.lbl_estado.pack(pady=5)

        # ── Tarjeta: Estadísticas ─────────────────────────────────────────────
        card_stats = self._crear_card(self.left_panel, titulo="Estado de la Red")

        self.lbl_nodos = ctk.CTkLabel(card_stats, text="Nodos: —", font=FUENTE_NORMAL, text_color=COLOR_TEXTO)
        self.lbl_nodos.pack(anchor="w")

        self.lbl_aristas = ctk.CTkLabel(card_stats, text="Aristas: —", font=FUENTE_NORMAL, text_color=COLOR_TEXTO)
        self.lbl_aristas.pack(anchor="w")

        self.btn_ver_red = ctk.CTkButton(
            card_stats,
            text="Ver red completa en mapa",
            font=FUENTE_BOTON,
            fg_color=COLOR_PRIMARIO,
            hover_color="#005BB7",
            corner_radius=12,
            height=36,
            state="disabled",
            command=self._ver_red_completa,
        )
        self.btn_ver_red.pack(fill="x", pady=(10, 5))

        # ── Tarjeta: Ruta por Parada ──────────────────────────────────────────
        card_ruta = self._crear_card(self.left_panel, titulo="Ruta más corta")

        ctk.CTkLabel(card_ruta, text="Origen", font=FUENTE_NORMAL, text_color=COLOR_SUBTEXTO).pack(anchor="w")
        self.combo_origen = ctk.CTkComboBox(
            card_ruta,
            values=["— Cargando… —"],
            font=FUENTE_NORMAL,
            width=360,
            height=35,
            state="disabled",
            corner_radius=8
        )
        self.combo_origen.pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(card_ruta, text="Destino", font=FUENTE_NORMAL, text_color=COLOR_SUBTEXTO).pack(anchor="w")
        self.combo_destino = ctk.CTkComboBox(
            card_ruta,
            values=["— Cargando… —"],
            font=FUENTE_NORMAL,
            width=360,
            height=35,
            state="disabled",
            corner_radius=8
        )
        self.combo_destino.pack(fill="x", pady=(2, 10))

        self.btn_calcular = ctk.CTkButton(
            card_ruta,
            text="Calcular Ruta Óptima",
            font=FUENTE_BOTON,
            fg_color=COLOR_PRIMARIO,
            hover_color="#005BB7",
            corner_radius=12,
            height=44,
            state="disabled",
            command=self._calcular_ruta,
        )
        self.btn_calcular.pack(fill="x", pady=5)

        # ── Tarjeta: Buscar por dirección ─────────────────────────────────────
        card_geo = self._crear_card(self.left_panel, titulo="Búsqueda Inteligente")

        ctk.CTkLabel(card_geo, text="Tu ubicación", font=FUENTE_NORMAL, text_color=COLOR_SUBTEXTO).pack(anchor="w")
        self.entry_direccion_origen = ctk.CTkEntry(
            card_geo,
            font=FUENTE_NORMAL,
            placeholder_text="Ej: Calle 72 con Carrera 46",
            height=35,
            corner_radius=8
        )
        self.entry_direccion_origen.pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(card_geo, text="A dónde vas", font=FUENTE_NORMAL, text_color=COLOR_SUBTEXTO).pack(anchor="w")
        self.entry_direccion_destino = ctk.CTkEntry(
            card_geo,
            font=FUENTE_NORMAL,
            placeholder_text="Ej: Portal del Prado",
            height=35,
            corner_radius=8
        )
        self.entry_direccion_destino.pack(fill="x", pady=(2, 10))

        self.btn_ruta_direccion = ctk.CTkButton(
            card_geo,
            text="Buscar Ruta por Dirección",
            font=FUENTE_BOTON,
            fg_color=COLOR_PRIMARIO,
            hover_color="#005BB7",
            corner_radius=12,
            height=44,
            state="disabled",
            command=self._calcular_ruta_por_direccion,
        )
        self.btn_ruta_direccion.pack(fill="x", pady=5)

        # ── Tarjeta: Herramientas de Análisis ─────────────────────────────────
        card_analisis = self._crear_card(self.left_panel, titulo="Análisis Avanzado")

        btn_style = dict(
            font=FUENTE_BOTON,
            fg_color=COLOR_PRIMARIO,
            hover_color="#005BB7",
            corner_radius=12,
            height=38,
            state="disabled",
        )

        self.btn_metricas = ctk.CTkButton(card_analisis, text="Métricas del Grafo", command=self._calcular_metricas, **btn_style)
        self.btn_metricas.pack(fill="x", pady=4)

        self.btn_centralidad = ctk.CTkButton(card_analisis, text="Nodos más importantes", command=self._hilo_centralidad, **btn_style)
        self.btn_centralidad.pack(fill="x", pady=4)

        self.btn_catalogo = ctk.CTkButton(card_analisis, text="Catálogo de Rutas", command=self._ver_catalogo, **btn_style)
        self.btn_catalogo.pack(fill="x", pady=4)

        self.btn_falla = ctk.CTkButton(card_analisis, text="Simular Falla Crítica", command=self._simular_falla, **btn_style)
        self.btn_falla.pack(fill="x", pady=4)

        # ── PANEL DERECHO: RESULTADOS ─────────────────────────────────────────
        card_resultado = self._crear_card(right_panel, titulo="RESULTADOS Y ANÁLISIS")

        self.texto_resultado = ctk.CTkTextbox(
            card_resultado,
            font=FUENTE_MONO,
            fg_color="#F8F8F8",
            text_color=COLOR_TEXTO,
            corner_radius=12,
            border_width=0,
            state="disabled",
        )
        self.texto_resultado.pack(fill="both", expand=True, pady=10)

    # ══════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _crear_card(self, parent, titulo):
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(fill="x", pady=(0, 15))  # Espaciado entre tarjetas
        
        ctk.CTkLabel(wrapper, text=titulo.upper(), font=("Segoe UI", 11, "bold"),
                     text_color=COLOR_SUBTEXTO).pack(anchor="w", padx=10, pady=(10, 5))

        card = ctk.CTkFrame(wrapper, fg_color=COLOR_CARD, corner_radius=16,
                            border_width=0)
        card.pack(fill="both", expand=True)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=15)

        return inner

    def _escribir_resultado(self, texto):
        self.texto_resultado.configure(state="normal")
        self.texto_resultado.delete("1.0", "end")
        self.texto_resultado.insert("1.0", texto)
        self.texto_resultado.configure(state="disabled")

    def _botones_analisis(self, state):
        for btn in (self.btn_metricas, self.btn_centralidad, self.btn_catalogo, self.btn_falla):
            btn.configure(state=state)

    def _todos_los_botones(self, state):
        """Habilita o deshabilita todos los botones de acción."""
        self._botones_analisis(state)
        self.btn_calcular.configure(state=state)
        self.btn_ruta_direccion.configure(state=state)
        self.btn_ver_red.configure(state=state)

    def _contar_transbordos(self, camino):
        if len(camino) < 2:
            return 0
        transbordos = 0
        ruta_actual = None
        for i in range(len(camino) - 1):
            data = self.grafo.get_edge_data(camino[i], camino[i + 1]) or {}
            ruta = data.get("route")
            if ruta_actual is not None and ruta != ruta_actual:
                transbordos += 1
            ruta_actual = ruta
        return transbordos

    # ══════════════════════════════════════════════════════════════════════════
    # LÓGICA DE CARGA
    # ══════════════════════════════════════════════════════════════════════════

    def _hilo_cargar(self):
        self.btn_cargar.configure(state="disabled", text="  Cargando…")
        self.lbl_estado.configure(text="Leyendo archivos GTFS…", text_color=COLOR_SUBTEXTO)
        threading.Thread(target=self._cargar_dataset, daemon=True).start()

    def _cargar_dataset(self):
        try:
            self.lbl_estado.configure(text="Cargando stops y stop_times…")
            stops, stop_times, trips, routes = cargar_datos()

            self.lbl_estado.configure(text="Construyendo grafo…")
            self.grafo = construir_grafo(stops, stop_times, trips)

            paradas_raw = obtener_paradas_unicas(stops)
            paradas_en_grafo = {
                nombre: sid
                for sid, nombre in paradas_raw.items()
                if sid in self.grafo.nodes
            }
            nombres_ordenados = sorted(paradas_en_grafo.keys())
            self.paradas_dict = paradas_en_grafo

            self.after(0, lambda: self._actualizar_ui_tras_carga(nombres_ordenados))

        except Exception as e:
            self.after(0, lambda: self._mostrar_error_carga(str(e)))

    def _actualizar_ui_tras_carga(self, nombres):
        n_nodos  = self.grafo.number_of_nodes()
        n_aristas = self.grafo.number_of_edges()

        self.lbl_nodos.configure(text=f"Nodos: {n_nodos:,}")
        self.lbl_aristas.configure(text=f"  ·  Aristas: {n_aristas:,}")
        self.lbl_estado.configure(
            text=f"✓ Dataset cargado — {len(nombres)} paradas", text_color=COLOR_EXITO
        )

        self.combo_origen.configure(values=nombres, state="normal")
        self.combo_destino.configure(values=nombres, state="normal")
        self.combo_origen.set(nombres[0] if nombres else "")
        self.combo_destino.set(nombres[-1] if nombres else "")

        self.btn_cargar.configure(state="normal", text="  Recargar datos")
        self._todos_los_botones("normal")

        self._escribir_resultado(
            "✅ Grafo construido correctamente.\n\n"
            "• Selecciona paradas y presiona «Calcular ruta» para usar Dijkstra.\n"
            "• Ingresa direcciones de texto y presiona «Calcular ruta desde mis direcciones»\n"
            "  para geocodificar y encontrar las paradas más cercanas.\n"
            "• Presiona «Ver red completa en mapa» para explorar toda la red en Folium.\n"
            "• Usa los botones de «Análisis de Red» para métricas del grafo."
        )

    def _mostrar_error_carga(self, error):
        self.lbl_estado.configure(text="Error al cargar", text_color=COLOR_ERROR)
        self.btn_cargar.configure(state="normal", text="  Cargar datos GTFS")
        messagebox.showerror("Error al cargar datos", f"No se pudo cargar el dataset GTFS:\n\n{error}")

    # ══════════════════════════════════════════════════════════════════════════
    # CÁLCULO DE RUTA POR PARADA (Dijkstra clásico)
    # ══════════════════════════════════════════════════════════════════════════

    def _calcular_ruta(self):
        if self.grafo is None:
            messagebox.showwarning("Grafo no cargado", "Primero carga el dataset GTFS.")
            return

        nombre_origen  = self.combo_origen.get()
        nombre_destino = self.combo_destino.get()

        if nombre_origen == nombre_destino:
            messagebox.showwarning("Selección inválida", "El origen y el destino no pueden ser iguales.")
            return

        id_origen  = self.paradas_dict.get(nombre_origen)
        id_destino = self.paradas_dict.get(nombre_destino)

        if not id_origen or not id_destino:
            messagebox.showerror("Error", "No se encontraron los IDs de las paradas seleccionadas.")
            return

        camino, distancia, tiempo = calcular_ruta_con_tiempo(self.grafo, id_origen, id_destino)

        if camino is None:
            self._escribir_resultado(
                f"❌ No se encontró ruta entre:\n\n"
                f"  Origen:  {nombre_origen}\n"
                f"  Destino: {nombre_destino}\n\n"
                f"Las paradas pueden no estar conectadas en el grafo."
            )
            return

        transbordos   = self._contar_transbordos(camino)
        nombres_camino = [self.grafo.nodes[sid].get("nombre", sid) for sid in camino]

        lineas = [
            "🗺️  Ruta más corta · Dijkstra",
            "",
            f"  Origen  : {nombre_origen}",
            f"  Destino : {nombre_destino}",
            "",
            f"  Paradas      : {len(camino)}",
            f"  Distancia    : {distancia} km",
            f"  Tiempo est.  : {tiempo} min  (velocidad promedio 22 km/h)",
            f"  Transbordos  : {transbordos}",
            "",
            "─" * 52,
            "",
        ]
        for i, nombre in enumerate(nombres_camino):
            prefijo = "🟢" if i == 0 else ("🔴" if i == len(nombres_camino) - 1 else "  •")
            lineas.append(f"  {prefijo}  {nombre}")

        self._escribir_resultado("\n".join(lineas))

        print("\n" + "=" * 60)
        print("RUTA MÁS CORTA (Dijkstra)")
        print(f"Origen   : {nombre_origen}  |  Destino: {nombre_destino}")
        print(f"Paradas  : {len(camino)}  |  Distancia: {distancia} km  |  Tiempo: {tiempo} min")
        print(f"Transbordos: {transbordos}")
        print("─" * 60)
        for i, n in enumerate(nombres_camino):
            print(f"  {i + 1}. {n}")
        print("=" * 60)

        generar_mapa(self.grafo, camino)

    # ══════════════════════════════════════════════════════════════════════════
    # CÁLCULO DE RUTA POR DIRECCIÓN (Geocodificación)
    # ══════════════════════════════════════════════════════════════════════════

    def _calcular_ruta_por_direccion(self):
        if self.grafo is None:
            messagebox.showwarning("Grafo no cargado", "Primero carga el dataset GTFS.")
            return

        texto_o = self.entry_direccion_origen.get().strip()
        texto_d = self.entry_direccion_destino.get().strip()

        if not texto_o or not texto_d:
            messagebox.showwarning("Campos vacíos", "Ingresa ambas direcciones antes de calcular.")
            return

        # Deshabilitar botones durante el proceso
        self._todos_los_botones("disabled")
        self.btn_ruta_direccion.configure(text="  Geocodificando…")
        self.lbl_estado.configure(text="Geocodificando direcciones…", text_color=COLOR_SUBTEXTO)
        self._escribir_resultado("⏳ Geocodificando direcciones con OpenStreetMap…\n\nEsto puede tardar unos segundos.")

        threading.Thread(
            target=self._hilo_ruta_por_direccion,
            args=(texto_o, texto_d),
            daemon=True,
        ).start()

    def _hilo_ruta_por_direccion(self, texto_o: str, texto_d: str):
        try:
            # 1. Geocodificar origen
            lat_o, lon_o = geocodificar_direccion(texto_o)
            if lat_o is None:
                self.after(0, lambda: messagebox.showerror(
                    "Dirección no encontrada",
                    f"No se encontró la dirección de origen:\n\n«{texto_o}»\n\n"
                    "Intenta ser más específico, ej:\n«Calle 84 #45-10, Barranquilla»"
                ))
                return

            # 2. Geocodificar destino
            lat_d, lon_d = geocodificar_direccion(texto_d)
            if lat_d is None:
                self.after(0, lambda: messagebox.showerror(
                    "Dirección no encontrada",
                    f"No se encontró la dirección de destino:\n\n«{texto_d}»\n\n"
                    "Intenta ser más específico, ej:\n«Calle 30 #38-15, Centro, Barranquilla»"
                ))
                return

            # 3. Encontrar paradas más cercanas
            stop_o, nombre_o, dist_o = parada_mas_cercana(self.grafo, lat_o, lon_o)
            stop_d, nombre_d, dist_d = parada_mas_cercana(self.grafo, lat_d, lon_d)

            if stop_o is None or stop_d is None:
                self.after(0, lambda: messagebox.showerror(
                    "Error", "No se pudieron encontrar paradas cercanas en el grafo."
                ))
                return

            # 4. Dijkstra entre las dos paradas
            camino, distancia, tiempo_bus = calcular_ruta_con_tiempo(self.grafo, stop_o, stop_d)

            if camino is None:
                self.after(0, lambda: self._escribir_resultado(
                    f"❌ No se encontró ruta entre las paradas más cercanas:\n\n"
                    f"  Origen  : {nombre_o}\n"
                    f"  Destino : {nombre_d}\n\n"
                    f"Las paradas pueden no estar conectadas en el componente principal."
                ))
                return

            transbordos    = self._contar_transbordos(camino)
            nombres_camino = [self.grafo.nodes[sid].get("nombre", sid) for sid in camino]

            # Tiempo de caminata: velocidad peatonal ~5 km/h = 0.0833 km/min
            walk_o = round(dist_o / 0.0833, 1)
            walk_d = round(dist_d / 0.0833, 1)

            lineas = [
                "📍  Ruta desde tus direcciones · Geocodificación + Dijkstra",
                "",
                f"  ── Origen ingresado",
                f"     «{texto_o}»",
                f"     Parada más cercana : {nombre_o}",
                f"     Distancia a pie    : {dist_o * 1000:.0f} m  (~{walk_o} min caminando)",
                "",
                f"  ── Destino ingresado",
                f"     «{texto_d}»",
                f"     Parada más cercana : {nombre_d}",
                f"     Distancia a pie    : {dist_d * 1000:.0f} m  (~{walk_d} min caminando)",
                "",
                f"  ── Ruta en bus (Dijkstra)",
                f"     Paradas     : {len(camino)}",
                f"     Distancia   : {distancia} km",
                f"     Tiempo bus  : {tiempo_bus} min  (velocidad promedio 22 km/h)",
                f"     Transbordos : {transbordos}",
                f"     Tiempo total est. : {round(walk_o + tiempo_bus + walk_d, 1)} min",
                "",
                "─" * 52,
                "",
            ]
            for i, nombre in enumerate(nombres_camino):
                prefijo = "🟢" if i == 0 else ("🔴" if i == len(nombres_camino) - 1 else "  •")
                lineas.append(f"  {prefijo}  {nombre}")

            resultado_texto = "\n".join(lineas)

            # Capturar valores para el lambda (evitar closure sobre variables mutables)
            _camino = camino
            _stop_o, _stop_d = stop_o, stop_d
            _lat_o, _lon_o = lat_o, lon_o
            _lat_d, _lon_d = lat_d, lon_d

            def _mostrar():
                self._escribir_resultado(resultado_texto)
                generar_mapa_grafo(
                    self.grafo,
                    ruta_resaltada=_camino,
                    origen_coords=(_lat_o, _lon_o),
                    destino_coords=(_lat_d, _lon_d),
                    parada_origen=_stop_o,
                    parada_destino=_stop_d,
                )

            self.after(0, _mostrar)

        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._escribir_resultado(f"❌ Error inesperado:\n\n{err}"))

        finally:
            self.after(0, lambda: self._todos_los_botones("normal"))
            self.after(0, lambda: self.btn_ruta_direccion.configure(
                text="  Calcular ruta desde mis direcciones"))
            self.after(0, lambda: self.lbl_estado.configure(
                text=f"✓ Dataset cargado — {len(self.paradas_dict)} paradas",
                text_color=COLOR_EXITO,
            ))

    # ══════════════════════════════════════════════════════════════════════════
    # VER RED COMPLETA EN MAPA
    # ══════════════════════════════════════════════════════════════════════════

    def _ver_red_completa(self):
        if self.grafo is None:
            messagebox.showwarning("Grafo no cargado", "Primero carga el dataset GTFS.")
            return

        self._todos_los_botones("disabled")
        self.btn_ver_red.configure(text="  Generando mapa…")
        self._escribir_resultado("⏳ Generando mapa de la red completa…\n\nEsto puede tardar unos segundos.")

        def _hilo():
            try:
                generar_mapa_grafo(self.grafo)
                self.after(0, lambda: self._escribir_resultado(
                    "✅ Mapa de la red completa generado y abierto en el navegador.\n\n"
                    "  • Usa el panel de capas (esquina superior derecha) para activar/desactivar\n"
                    "    la capa «Red Transmetro» y la capa «Paradas».\n"
                    "  • El minimapa (esquina inferior derecha) te da contexto de ubicación."
                ))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._escribir_resultado(f"❌ Error al generar mapa:\n\n{err}"))
            finally:
                self.after(0, lambda: self._todos_los_botones("normal"))
                self.after(0, lambda: self.btn_ver_red.configure(text="  Ver red completa en mapa"))

        threading.Thread(target=_hilo, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # ANÁLISIS DE RED
    # ══════════════════════════════════════════════════════════════════════════

    def _calcular_metricas(self):
        if self.grafo is None:
            messagebox.showwarning("Grafo no cargado", "Primero carga el dataset GTFS.")
            return

        m = graph_analyzer.calcular_metricas_globales(self.grafo)
        if "error" in m:
            self._escribir_resultado(f"❌ Error calculando métricas:\n\n{m['error']}")
            return

        lineas = [
            "📊  Métricas Globales del Grafo · Transmetro",
            "",
            f"  Nodos (paradas)       : {m['nodos']:,}",
            f"  Aristas (conexiones)  : {m['aristas']:,}",
            f"  Densidad              : {m['densidad']}",
            f"  Clustering promedio   : {m['clustering_promedio']}",
            f"  Grado promedio        : {m['grado_promedio']}",
            f"  Grado máximo          : {m['grado_max']}",
            f"  Grado mínimo          : {m['grado_min']}",
            f"  Grafo conexo          : {'Sí ✓' if m['es_conexo'] else 'No ✗'}",
            f"  Componentes           : {m['num_componentes']}",
        ]
        self._escribir_resultado("\n".join(lineas))

    def _hilo_centralidad(self):
        if self.grafo is None:
            messagebox.showwarning("Grafo no cargado", "Primero carga el dataset GTFS.")
            return
        self._escribir_resultado(
            "⏳ Calculando centralidades…\n\n"
            "Betweenness usa muestreo (k=200) para grafos grandes.\n"
            "Por favor espera unos segundos."
        )
        self._todos_los_botones("disabled")
        threading.Thread(target=self._calcular_centralidad, daemon=True).start()

    def _calcular_centralidad(self):
        try:
            top = graph_analyzer.top_paradas_por_centralidad(self.grafo, n=5)
            self.after(0, lambda: self._mostrar_centralidad(top))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._escribir_resultado(f"❌ Error:\n\n{err}"))
        finally:
            self.after(0, lambda: self._todos_los_botones("normal"))

    def _mostrar_centralidad(self, top):
        if "error" in top:
            self._escribir_resultado(f"❌ Error:\n\n{top['error']}")
            return

        lineas = ["🏆  Top 5 Paradas por Centralidad · Transmetro", ""]

        etiquetas = [
            ("degree",      "DEGREE CENTRALITY",     "Paradas más conectadas directamente"),
            ("betweenness", "BETWEENNESS CENTRALITY", "Paradas con más rutas que pasan por ellas"),
            ("closeness",   "CLOSENESS CENTRALITY",   "Paradas más cercanas al resto de la red"),
        ]

        for clave, titulo, desc in etiquetas:
            lineas += [f"  ── {titulo}", f"     {desc}", ""]
            for i, (_, nombre, val) in enumerate(top[clave], 1):
                lineas.append(f"    {i}. {nombre}  ({val})")
            lineas.append("")

        self._escribir_resultado("\n".join(lineas))

    def _ver_catalogo(self):
        if self.grafo is None:
            messagebox.showwarning("Grafo no cargado", "Primero carga el dataset GTFS.")
            return
        try:
            cat = route_catalog.obtener_catalogo_rutas()
            lineas = [
                "🚌  Catálogo de Rutas · Transmetro Barranquilla",
                "",
                f"  {'ID':<8} {'Código':<8} {'Nombre':<30} {'Paradas':>8} {'Viajes':>8}",
                "  " + "─" * 66,
            ]
            for _, row in cat.iterrows():
                lineas.append(
                    f"  {str(row['route_id']):<8} {str(row['route_short_name']):<8} "
                    f"{str(row['route_long_name']):<30} {row['num_paradas']:>8} {row['num_trips']:>8}"
                )
            self._escribir_resultado("\n".join(lineas))
        except Exception as e:
            self._escribir_resultado(f"❌ Error al cargar catálogo:\n\n{e}")

    def _simular_falla(self):
        if self.grafo is None:
            messagebox.showwarning("Grafo no cargado", "Primero carga el dataset GTFS.")
            return

        nombre  = self.combo_origen.get()
        stop_id = self.paradas_dict.get(nombre)

        if not stop_id:
            messagebox.showerror("Error", "No se encontró el ID de la parada seleccionada.")
            return

        resultado = graph_analyzer.simular_falla_parada(self.grafo, stop_id)

        if "error" in resultado:
            self._escribir_resultado(f"❌ Error en simulación:\n\n{resultado['error']}")
            return

        fragmento = resultado["se_fragmento"]
        icono = "⚠️" if fragmento else "✅"

        lineas = [
            "🔴  Simulación de Falla de Parada",
            "",
            f"  Parada eliminada : {resultado['nombre']}",
            f"  Stop ID          : {resultado['stop_id']}",
            "",
            f"  Componentes antes    : {resultado['componentes_antes']}",
            f"  Componentes después  : {resultado['componentes_despues']}",
            f"  Nodos restantes      : {resultado['nodos_restantes']:,}",
            f"  Aristas restantes    : {resultado['aristas_restantes']:,}",
            "",
            f"  {icono}  "
            f"{'La red SE FRAGMENTA al eliminar esta parada.' if fragmento else 'La red permanece conectada. Esta parada no es crítica para la conectividad.'}",
        ]
        self._escribir_resultado("\n".join(lineas))
