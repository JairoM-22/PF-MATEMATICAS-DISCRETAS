# ui.py
# Interfaz gráfica moderna con CustomTkinter para visualizar el grafo de Transmetro.

import customtkinter as ctk
from tkinter import messagebox
import threading

from data_loader import cargar_datos, obtener_paradas_unicas
from graph_manager import construir_grafo, calcular_ruta_dijkstra, calcular_ruta_con_tiempo
from map_generator import generar_mapa
import graph_analyzer
import route_catalog

# Configuración visual de CustomTkinter
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# Paleta de colores
COLOR_BG = "#F5F7FA"
COLOR_CARD = "#FFFFFF"
COLOR_PRIMARIO = "#2563EB"
COLOR_TEXTO = "#1E293B"
COLOR_SUBTEXTO = "#64748B"
COLOR_BORDE = "#E2E8F0"
COLOR_EXITO = "#10B981"
COLOR_ERROR = "#EF4444"
COLOR_ANALISIS = "#7C3AED"
FUENTE_TITULO = ("SF Pro Display", 26, "bold")
FUENTE_SUBTITULO = ("SF Pro Display", 13)
FUENTE_NORMAL = ("SF Pro Display", 12)
FUENTE_MONO = ("SF Mono", 11)


class AppTransmetro(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Transmetro Barranquilla · Grafo de Rutas")
        self.geometry("2000x1200")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)

        self.grafo = None
        self.paradas_dict = {}   # {nombre: stop_id}

        self._construir_ui()

        # Carga automática del dataset al iniciar
        self.after(400, self._hilo_cargar)

    # ── CONSTRUCCIÓN DE LA INTERFAZ ──────────────────────────────────────────

    def _construir_ui(self):
        # Encabezado
        frame_header = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=0, height=90)
        frame_header.pack(fill="x")
        frame_header.pack_propagate(False)

        ctk.CTkLabel(
            frame_header,
            text="Transmetro Barranquilla",
            font=FUENTE_TITULO,
            text_color=COLOR_TEXTO,
        ).pack(side="left", padx=32, pady=10)

        ctk.CTkLabel(
            frame_header,
            text="Grafo de rutas · Dijkstra",
            font=FUENTE_SUBTITULO,
            text_color=COLOR_SUBTEXTO,
        ).pack(side="left", padx=0, pady=25)

        # Tarjeta de carga del dataset
        card_carga = self._crear_card(self, titulo="Dataset GTFS")
        card_carga.pack(fill="x", padx=28, pady=(18, 0))

        self.btn_cargar = ctk.CTkButton(
            card_carga,
            text="  Cargar datos GTFS",
            font=FUENTE_NORMAL,
            fg_color=COLOR_PRIMARIO,
            hover_color="#1D4ED8",
            corner_radius=10,
            height=40,
            command=self._hilo_cargar,
        )
        self.btn_cargar.pack(side="left", padx=0, pady=12)

        self.lbl_estado = ctk.CTkLabel(
            card_carga,
            text="Cargando automáticamente…",
            font=FUENTE_NORMAL,
            text_color=COLOR_SUBTEXTO,
        )
        self.lbl_estado.pack(side="left", padx=18, pady=12)

        # Tarjeta de estadísticas del grafo
        card_stats = self._crear_card(self, titulo="Estadísticas del grafo")
        card_stats.pack(fill="x", padx=28, pady=(14, 0))

        self.lbl_nodos = ctk.CTkLabel(card_stats, text="Nodos: —", font=FUENTE_NORMAL, text_color=COLOR_TEXTO)
        self.lbl_nodos.pack(side="left", padx=0, pady=10)

        self.lbl_aristas = ctk.CTkLabel(card_stats, text="  ·  Aristas: —", font=FUENTE_NORMAL, text_color=COLOR_TEXTO)
        self.lbl_aristas.pack(side="left", pady=10)

        # Tarjeta de selección de ruta
        card_ruta = self._crear_card(self, titulo="Calcular ruta más corta")
        card_ruta.pack(fill="x", padx=28, pady=(14, 0))

        fila_dropdowns = ctk.CTkFrame(card_ruta, fg_color="transparent")
        fila_dropdowns.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(fila_dropdowns, text="Origen", font=FUENTE_NORMAL, text_color=COLOR_SUBTEXTO).grid(row=0, column=0, sticky="w")
        self.combo_origen = ctk.CTkComboBox(
            fila_dropdowns,
            values=["— Cargando… —"],
            font=FUENTE_NORMAL,
            width=320,
            state="disabled",
        )
        self.combo_origen.grid(row=1, column=0, padx=(0, 16), pady=(4, 0), sticky="w")

        ctk.CTkLabel(fila_dropdowns, text="Destino", font=FUENTE_NORMAL, text_color=COLOR_SUBTEXTO).grid(row=0, column=1, sticky="w")
        self.combo_destino = ctk.CTkComboBox(
            fila_dropdowns,
            values=["— Cargando… —"],
            font=FUENTE_NORMAL,
            width=320,
            state="disabled",
        )
        self.combo_destino.grid(row=1, column=1, pady=(4, 0), sticky="w")

        self.btn_calcular = ctk.CTkButton(
            card_ruta,
            text="  Calcular ruta",
            font=FUENTE_NORMAL,
            fg_color=COLOR_PRIMARIO,
            hover_color="#1D4ED8",
            corner_radius=10,
            height=40,
            state="disabled",
            command=self._calcular_ruta,
        )
        self.btn_calcular.pack(side="left", pady=(0, 12))

        # ── Tarjeta de Análisis de Red ────────────────────────────────────────
        card_analisis = self._crear_card(self, titulo="Análisis de Red")
        card_analisis.pack(fill="x", padx=28, pady=(14, 0))

        fila_analisis = ctk.CTkFrame(card_analisis, fg_color="transparent")
        fila_analisis.pack(fill="x", pady=(0, 12))

        btn_style = dict(
            font=FUENTE_NORMAL,
            fg_color=COLOR_ANALISIS,
            hover_color="#6D28D9",
            corner_radius=10,
            height=38,
            state="disabled",
        )

        self.btn_metricas = ctk.CTkButton(
            fila_analisis,
            text="Métricas del grafo",
            command=self._calcular_metricas,
            **btn_style,
        )
        self.btn_metricas.pack(side="left", padx=(0, 10))

        self.btn_centralidad = ctk.CTkButton(
            fila_analisis,
            text="Top paradas centrales",
            command=self._hilo_centralidad,
            **btn_style,
        )
        self.btn_centralidad.pack(side="left", padx=(0, 10))

        self.btn_catalogo = ctk.CTkButton(
            fila_analisis,
            text="Ver catálogo de rutas",
            command=self._ver_catalogo,
            **btn_style,
        )
        self.btn_catalogo.pack(side="left", padx=(0, 10))

        self.btn_falla = ctk.CTkButton(
            fila_analisis,
            text="Simular falla de parada",
            command=self._simular_falla,
            **btn_style,
        )
        self.btn_falla.pack(side="left")

        # Tarjeta de resultado
        card_resultado = self._crear_card(self, titulo="Resultado")
        card_resultado.pack(fill="both", expand=True, padx=28, pady=(14, 24))

        self.texto_resultado = ctk.CTkTextbox(
            card_resultado,
            font=FUENTE_MONO,
            fg_color="#F8FAFC",
            text_color=COLOR_TEXTO,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDE,
            state="disabled",
        )
        self.texto_resultado.pack(fill="both", expand=True, pady=(0, 8))

    # ── HELPERS ──────────────────────────────────────────────────────────────

    def _crear_card(self, parent, titulo):
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack_configure()

        ctk.CTkLabel(wrapper, text=titulo.upper(), font=("SF Pro Display", 10, "bold"),
                     text_color=COLOR_SUBTEXTO).pack(anchor="w", padx=2, pady=(0, 2))

        card = ctk.CTkFrame(wrapper, fg_color=COLOR_CARD, corner_radius=14,
                            border_width=1, border_color=COLOR_BORDE)
        card.pack(fill="x")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=6)

        return inner

    def _escribir_resultado(self, texto):
        self.texto_resultado.configure(state="normal")
        self.texto_resultado.delete("1.0", "end")
        self.texto_resultado.insert("1.0", texto)
        self.texto_resultado.configure(state="disabled")

    def _botones_analisis(self, state):
        for btn in (self.btn_metricas, self.btn_centralidad, self.btn_catalogo, self.btn_falla):
            btn.configure(state=state)

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

    # ── LÓGICA DE CARGA ───────────────────────────────────────────────────────

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
        n_nodos = self.grafo.number_of_nodes()
        n_aristas = self.grafo.number_of_edges()

        self.lbl_nodos.configure(text=f"Nodos: {n_nodos:,}")
        self.lbl_aristas.configure(text=f"  ·  Aristas: {n_aristas:,}")
        self.lbl_estado.configure(text=f"✓ Dataset cargado — {len(nombres)} paradas", text_color=COLOR_EXITO)

        self.combo_origen.configure(values=nombres, state="normal")
        self.combo_destino.configure(values=nombres, state="normal")
        self.combo_origen.set(nombres[0] if nombres else "")
        self.combo_destino.set(nombres[-1] if nombres else "")
        self.btn_calcular.configure(state="normal")
        self.btn_cargar.configure(state="normal", text="  Recargar datos")
        self._botones_analisis("normal")

        self._escribir_resultado(
            "✅ Grafo construido correctamente.\n\n"
            "Selecciona origen y destino, luego presiona «Calcular ruta».\n\n"
            "También puedes explorar las métricas del grafo con los botones de «Análisis de Red»."
        )

    def _mostrar_error_carga(self, error):
        self.lbl_estado.configure(text="Error al cargar", text_color=COLOR_ERROR)
        self.btn_cargar.configure(state="normal", text="  Cargar datos GTFS")
        messagebox.showerror("Error al cargar datos", f"No se pudo cargar el dataset GTFS:\n\n{error}")

    # ── CÁLCULO DE RUTA ───────────────────────────────────────────────────────

    def _calcular_ruta(self):
        if self.grafo is None:
            messagebox.showwarning("Grafo no cargado", "Primero carga el dataset GTFS.")
            return

        nombre_origen = self.combo_origen.get()
        nombre_destino = self.combo_destino.get()

        if nombre_origen == nombre_destino:
            messagebox.showwarning("Selección inválida", "El origen y el destino no pueden ser iguales.")
            return

        id_origen = self.paradas_dict.get(nombre_origen)
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

        transbordos = self._contar_transbordos(camino)
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
        print(f"Origen   : {nombre_origen}")
        print(f"Destino  : {nombre_destino}")
        print(f"Paradas  : {len(camino)}")
        print(f"Distancia: {distancia} km")
        print(f"Tiempo   : {tiempo} min")
        print(f"Transbord: {transbordos}")
        print("─" * 60)
        for i, n in enumerate(nombres_camino):
            print(f"  {i + 1}. {n}")
        print("=" * 60)

        generar_mapa(self.grafo, camino)

    # ── ANÁLISIS DE RED ───────────────────────────────────────────────────────

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
        self._botones_analisis("disabled")
        self.btn_calcular.configure(state="disabled")
        threading.Thread(target=self._calcular_centralidad, daemon=True).start()

    def _calcular_centralidad(self):
        try:
            top = graph_analyzer.top_paradas_por_centralidad(self.grafo, n=5)
            self.after(0, lambda: self._mostrar_centralidad(top))
        except Exception as e:
            self.after(0, lambda: self._escribir_resultado(f"❌ Error:\n\n{e}"))
        finally:
            self.after(0, lambda: self._botones_analisis("normal"))
            self.after(0, lambda: self.btn_calcular.configure(state="normal"))

    def _mostrar_centralidad(self, top):
        if "error" in top:
            self._escribir_resultado(f"❌ Error:\n\n{top['error']}")
            return

        lineas = ["🏆  Top 5 Paradas por Centralidad · Transmetro", ""]

        etiquetas = [
            ("degree",      "DEGREE CENTRALITY",      "Paradas más conectadas directamente"),
            ("betweenness", "BETWEENNESS CENTRALITY",  "Paradas con más rutas que pasan por ellas"),
            ("closeness",   "CLOSENESS CENTRALITY",    "Paradas más cercanas al resto de la red"),
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

        nombre = self.combo_origen.get()
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
            f"🔴  Simulación de Falla de Parada",
            "",
            f"  Parada eliminada : {resultado['nombre']}",
            f"  Stop ID          : {resultado['stop_id']}",
            "",
            f"  Componentes antes    : {resultado['componentes_antes']}",
            f"  Componentes después  : {resultado['componentes_despues']}",
            f"  Nodos restantes      : {resultado['nodos_restantes']:,}",
            f"  Aristas restantes    : {resultado['aristas_restantes']:,}",
            "",
            f"  {icono}  {'La red SE FRAGMENTA al eliminar esta parada.' if fragmento else 'La red permanece conectada. Esta parada no es crítica para la conectividad.'}",
        ]
        self._escribir_resultado("\n".join(lineas))
