# ui.py
# Interfaz gráfica moderna con CustomTkinter para visualizar el grafo de Transmetro.

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading
from collections import defaultdict

from data_loader import cargar_datos, obtener_paradas_unicas
from graph_manager import (
    construir_grafo,
    buscar_ruta_optima,
    contar_transbordos,
    calcular_costo_pasaje,
)
from map_generator import (
    generar_mapa,
    generar_mapa_grafo,
    geocodificar_direccion,
    parada_mas_cercana,
    get_address_suggestions,
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


# ── DROPDOWN DE AUTOCOMPLETADO ────────────────────────────────────────────────

class _AutocompleteDropdown:
    """
    Ventana flotante de sugerencias de autocompletado para campos de dirección.

    Se posiciona automáticamente justo debajo del Entry de referencia usando
    coordenadas de pantalla (winfo_rootx/y), funciona aunque el Entry esté
    dentro de un CTkScrollableFrame u otros contenedores anidados.

    Estética Apple Moderno:
      - Fondo blanco con borde gris #C7C7CC de 1px (igual que los separadores).
      - Hover: fondo #F2F2F7 (System Gray 6).
      - Ícono ⊙ en azul Apple #007AFF.
      - Separador fino #F2F2F7 entre items.
    """

    _ROW_H = 38   # Altura fija de cada fila (px)
    _MAX_N = 5    # Máximo de sugerencias visibles

    def __init__(self, root, entry_widget, on_select):
        self._root      = root
        self._entry     = entry_widget
        self._on_select = on_select
        self._win       = None   # tk.Toplevel
        self._body      = None   # Frame interior blanco
        self._current   = []     # Lista de direcciones completas actuales

    # ── API pública ──────────────────────────────────────────────────────────

    def update(self, suggestions: list):
        """Muestra o actualiza el dropdown con las nuevas sugerencias."""
        if not suggestions:
            self.hide()
            return
        self._current = suggestions
        self._ensure_win()
        self._build_items(suggestions)
        self._reposition()
        self._win.deiconify()
        self._win.lift()

    def hide(self):
        """Oculta el dropdown (sin destruirlo, para reutilizarlo)."""
        if self._win and self._win.winfo_exists():
            self._win.withdraw()

    def visible(self) -> bool:
        return (
            self._win is not None
            and self._win.winfo_exists()
            and self._win.state() != "withdrawn"
        )

    # ── Internos ─────────────────────────────────────────────────────────────

    def _ensure_win(self):
        """Crea el Toplevel si no existe o fue destruido."""
        if self._win and self._win.winfo_exists():
            return

        self._win = tk.Toplevel(self._root)
        self._win.overrideredirect(True)       # Sin barra de título ni botones
        self._win.attributes("-topmost", True) # Siempre por encima

        # Marco exterior = borde 1px color #C7C7CC
        border = tk.Frame(self._win, bg="#C7C7CC")
        border.pack(fill="both", expand=True)

        # Área interior blanca con 1px de separación del borde
        self._body = tk.Frame(border, bg="#FFFFFF")
        self._body.pack(fill="both", expand=True, padx=1, pady=1)

    def _build_items(self, suggestions: list):
        """Elimina items anteriores y construye los nuevos."""
        for child in self._body.winfo_children():
            child.destroy()

        for idx, addr in enumerate(suggestions):
            is_last  = (idx == len(suggestions) - 1)
            display  = (addr[:62] + "…") if len(addr) > 65 else addr
            full_addr = addr   # captura explícita para el closure

            # ── Fila ──────────────────────────────────────────────────────
            row = tk.Frame(self._body, bg="#FFFFFF",
                           height=self._ROW_H, cursor="hand2")
            row.pack(fill="x")
            row.pack_propagate(False)

            ico = tk.Label(row, text=" ⊙ ", bg="#FFFFFF",
                           fg="#007AFF", font=("Segoe UI", 10),
                           cursor="hand2")
            ico.pack(side="left")

            lbl = tk.Label(row, text=display, bg="#FFFFFF",
                           fg="#1C1C1E", font=("Segoe UI", 10),
                           anchor="w", cursor="hand2")
            lbl.pack(side="left", fill="both", expand=True, padx=(0, 12))

            # ── Separador fino entre filas (no en la última) ───────────────
            if not is_last:
                tk.Frame(self._body, bg="#F2F2F7",
                         height=1).pack(fill="x", padx=12)

            # ── Hover y click ──────────────────────────────────────────────
            def _enter(e, r=row, i=ico, l=lbl):
                for w in (r, i, l):
                    w.configure(bg="#F2F2F7")

            def _leave(e, r=row, i=ico, l=lbl):
                for w in (r, i, l):
                    w.configure(bg="#FFFFFF")

            def _click(e, a=full_addr):
                self._on_select(a)
                self.hide()

            for w in (row, ico, lbl):
                w.bind("<Enter>", _enter)
                w.bind("<Leave>", _leave)
                w.bind("<Button-1>", _click)

    def _reposition(self):
        """Posiciona el Toplevel justo debajo del Entry en coordenadas de pantalla."""
        self._entry.update_idletasks()
        x  = self._entry.winfo_rootx()
        y  = self._entry.winfo_rooty() + self._entry.winfo_height() + 3
        ew = self._entry.winfo_width()
        n  = min(len(self._current), self._MAX_N)
        h  = n * self._ROW_H + 2   # +2 por padding del borde
        self._win.geometry(f"{ew}x{h}+{x}+{y}")


# ─────────────────────────────────────────────────────────────────────────────

class AppTransmetro(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Transmetro · Smart Route Optimizer")
        self.geometry("1280x850")
        self.minsize(1100, 750)
        self.configure(fg_color=COLOR_BG)

        self.grafo = None
        self.paradas_dict = {}   # {nombre_parada: [stop_id, ...]}  (lista por si hay varias plataformas)
        self.modo_ruta = "rapido"  # "rapido" | "ahorro"

        self._construir_ui()
        self._setup_autocomplete()   # Debe ir después de _construir_ui (necesita los Entry)

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

        # ── Selector de modo de ruta ───────────────────────────────────────────
        ctk.CTkLabel(card_ruta, text="Tipo de ruta", font=FUENTE_NORMAL,
                     text_color=COLOR_SUBTEXTO).pack(anchor="w")

        self.seg_modo = ctk.CTkSegmentedButton(
            card_ruta,
            values=["Mas Rapida", "Sin Costo Adicional"],
            font=FUENTE_NORMAL,
            height=34,
            command=self._cambiar_modo_ruta,
        )
        self.seg_modo.set("Mas Rapida")
        self.seg_modo.pack(fill="x", pady=(2, 10))

        self.lbl_modo_info = ctk.CTkLabel(
            card_ruta,
            text="Sin limite de transbordos",
            font=("Segoe UI", 10),
            text_color=COLOR_SUBTEXTO,
        )
        self.lbl_modo_info.pack(anchor="w", pady=(0, 6))

        self.btn_calcular = ctk.CTkButton(
            card_ruta,
            text="Calcular Ruta Optima",
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

    def _cambiar_modo_ruta(self, valor):
        """Callback del CTkSegmentedButton para cambiar el modo de enrutamiento."""
        if valor == "Sin Costo Adicional":
            self.modo_ruta = "ahorro"
            self.lbl_modo_info.configure(
                text="Minimiza pasajes. 1 pasaje = hasta 3 buses ($3,700 COP)",
                text_color=COLOR_PRIMARIO,
            )
        else:
            self.modo_ruta = "rapido"
            self.lbl_modo_info.configure(
                text="Minimiza distancia/tiempo. Puede pagar mas pasajes.",
                text_color=COLOR_SUBTEXTO,
            )

    def _bloque_tarifa(self, buses_tomados: int) -> str:
        """
        Genera el bloque de texto con la informacion tarifaria real de Transmetro.
        Recibe 'buses_tomados' (cantidad de buses distintos abordados en el viaje).
        """
        pasajes, costo = calcular_costo_pasaje(buses_tomados)
        transbordos = max(0, buses_tomados - 1)
        lineas = [
            "  COSTO DEL VIAJE",
            f"    Buses tomados  : {buses_tomados}",
            f"    Transbordos    : {transbordos}",
            f"    Pasajes a pagar: {pasajes}",
            f"    Costo Total    : ${costo:,} COP",
            f"    [1 pasaje cubre 1, 2 o 3 buses — 2 transbordos gratis]",
        ]
        return "\n".join(lineas)

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
            # Agrupar stop_ids por nombre: un nombre puede tener varias plataformas
            paradas_por_nombre = defaultdict(list)
            for sid, nombre in paradas_raw.items():
                if sid in self.grafo.nodes:
                    paradas_por_nombre[nombre].append(sid)
            nombres_ordenados = sorted(paradas_por_nombre.keys())
            self.paradas_dict = dict(paradas_por_nombre)

            self.after(0, lambda: self._actualizar_ui_tras_carga(nombres_ordenados))

        except Exception as e:
            self.after(0, lambda: self._mostrar_error_carga(str(e)))

    def _actualizar_ui_tras_carga(self, nombres):
        n_nodos  = self.grafo.number_of_nodes()
        n_aristas = self.grafo.number_of_edges()

        self.lbl_nodos.configure(text=f"Nodos: {n_nodos:,}")
        self.lbl_aristas.configure(text=f"  ·  Aristas: {n_aristas:,}")
        n_estaciones = len(nombres)
        n_plataformas = sum(len(v) for v in self.paradas_dict.values())
        self.lbl_estado.configure(
            text=f"✓ Dataset cargado — {n_estaciones} estaciones / {n_plataformas} plataformas",
            text_color=COLOR_EXITO,
        )

        self.combo_origen.configure(values=nombres, state="normal")
        self.combo_destino.configure(values=nombres, state="normal")
        self.combo_origen.set(nombres[0] if nombres else "")
        self.combo_destino.set(nombres[-1] if nombres else "")

        self.btn_cargar.configure(state="normal", text="  Recargar datos")
        self._todos_los_botones("normal")

        self._escribir_resultado(
            "Grafo construido correctamente.\n\n"
            "MODOS DE RUTA:\n"
            "  'Mas Rapida'         - Minimiza distancia/tiempo. Dijkstra clasico.\n"
            "                         Puede usar mas pasajes si la ruta es mas corta.\n\n"
            "  'Sin Costo Adicional'- Minimiza pasajes pagados.\n"
            "                         1 pasaje cubre 1, 2 o 3 buses ($3,700 COP).\n"
            "                         Al tomar el 4to bus se paga un 2do pasaje.\n\n"
            "TARIFA REAL TRANSMETRO:\n"
            "  1 pasaje  = hasta 3 buses (0, 1 o 2 transbordos) = $3,700 COP\n"
            "  2 pasajes = hasta 6 buses (3, 4 o 5 transbordos) = $7,400 COP\n"
            "  Formula   : pasajes = ceil(buses_tomados / 3)\n\n"
            "• Selecciona paradas y presiona Calcular para ver la ruta y el costo.\n"
            "• Usa Busqueda Inteligente para geocodificar direcciones de texto.\n"
            "• Ver red completa en mapa abre Folium con toda la red."
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
            messagebox.showwarning("Seleccion invalida", "El origen y el destino no pueden ser iguales.")
            return

        ids_origen  = self.paradas_dict.get(nombre_origen, [])
        ids_destino = self.paradas_dict.get(nombre_destino, [])

        if not ids_origen or not ids_destino:
            messagebox.showerror("Error", "No se encontraron los IDs de las paradas seleccionadas.")
            return

        # ── Buscar ruta con la función maestra ───────────────────────────────
        camino, distancia, buses_tomados = buscar_ruta_optima(
            self.grafo, ids_origen, ids_destino, modo=self.modo_ruta
        )

        if camino is None:
            self._escribir_resultado(
                "No se encontro ruta entre:\n\n"
                f"  Origen : {nombre_origen}\n"
                f"  Destino: {nombre_destino}\n\n"
                "Las paradas pueden no estar conectadas en el grafo."
            )
            return

        # ── Calcular métricas y tarifa ────────────────────────────────────────
        tiempo         = round((distancia / 22) * 60, 1)
        transbordos    = max(0, buses_tomados - 1)
        pasajes, costo = calcular_costo_pasaje(buses_tomados)
        nombres_camino = [self.grafo.nodes[sid].get("nombre", sid) for sid in camino]

        etiqueta_modo = (
            "Modo Ahorro — Minimo costo tarifario"
            if self.modo_ruta == "ahorro"
            else "Modo Rapido — Minima distancia"
        )

        lineas = [
            f"  {etiqueta_modo}",
            "",
            f"  Origen  : {nombre_origen}",
            f"  Destino : {nombre_destino}",
            "",
            f"  Paradas      : {len(camino)}",
            f"  Distancia    : {distancia} km",
            f"  Tiempo est.  : {tiempo} min  (22 km/h promedio)",
            "",
            "  " + "-" * 50,
            self._bloque_tarifa(buses_tomados),
            "  " + "-" * 50,
            "",
        ]
        for i, nombre in enumerate(nombres_camino):
            prefijo = "[O]" if i == 0 else ("[D]" if i == len(nombres_camino) - 1 else "   ")
            lineas.append(f"  {prefijo}  {nombre}")

        self._escribir_resultado("\n".join(lineas))

        # Consola
        print("\n" + "=" * 60)
        print(etiqueta_modo)
        print(f"Origen  : {nombre_origen}  |  Destino: {nombre_destino}")
        print(f"Paradas : {len(camino)} | Dist: {distancia} km | Tiempo: {tiempo} min")
        print(f"Buses: {buses_tomados} | Transbordos: {transbordos} | Pasajes: {pasajes} | ${costo:,} COP")
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

            # 4. Buscar ruta con la función maestra (respeta el modo seleccionado)
            camino, distancia, buses_tomados = buscar_ruta_optima(
                self.grafo, stop_o, stop_d, modo=self.modo_ruta
            )

            if camino is None:
                self.after(0, lambda: self._escribir_resultado(
                    "No se encontro ruta entre las paradas mas cercanas:\n\n"
                    f"  Origen  : {nombre_o}\n"
                    f"  Destino : {nombre_d}\n\n"
                    "Las paradas pueden no estar conectadas en el grafo."
                ))
                return

            tiempo_bus     = round((distancia / 22) * 60, 1)
            transbordos    = max(0, buses_tomados - 1)
            pasajes, costo = calcular_costo_pasaje(buses_tomados)
            nombres_camino = [self.grafo.nodes[sid].get("nombre", sid) for sid in camino]

            # Tiempo de caminata: velocidad peatonal ~5 km/h = 0.0833 km/min
            walk_o = round(dist_o / 0.0833, 1)
            walk_d = round(dist_d / 0.0833, 1)

            etiqueta_modo = (
                "Modo Ahorro — Minimo costo tarifario"
                if self.modo_ruta == "ahorro"
                else "Modo Rapido — Minima distancia"
            )

            lineas = [
                f"  Ruta por Direccion · {etiqueta_modo}",
                "",
                "  -- Origen",
                f"     {texto_o}",
                f"     Parada mas cercana : {nombre_o}",
                f"     Distancia a pie    : {dist_o * 1000:.0f} m  (~{walk_o} min caminando)",
                "",
                "  -- Destino",
                f"     {texto_d}",
                f"     Parada mas cercana : {nombre_d}",
                f"     Distancia a pie    : {dist_d * 1000:.0f} m  (~{walk_d} min caminando)",
                "",
                "  -- Ruta en bus",
                f"     Paradas     : {len(camino)}",
                f"     Distancia   : {distancia} km",
                f"     Tiempo bus  : {tiempo_bus} min  (22 km/h promedio)",
                f"     Tiempo total: ~{round(walk_o + tiempo_bus + walk_d, 1)} min",
                "",
                "  " + "-" * 50,
                self._bloque_tarifa(buses_tomados),
                "  " + "-" * 50,
                "",
            ]
            for i, nombre in enumerate(nombres_camino):
                prefijo = "[O]" if i == 0 else ("[D]" if i == len(nombres_camino) - 1 else "   ")
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
                text="Buscar Ruta por Direccion"))
            self.after(0, lambda: self.lbl_estado.configure(
                text=f"✓ Dataset cargado — {len(self.paradas_dict)} estaciones",
                text_color=COLOR_EXITO,
            ))

    # ══════════════════════════════════════════════════════════════════════════
    # AUTOCOMPLETADO DE DIRECCIONES
    # ══════════════════════════════════════════════════════════════════════════

    def _setup_autocomplete(self):
        """
        Inicializa el sistema de autocompletado para los campos de Búsqueda
        Inteligente.

        - Crea un _AutocompleteDropdown por cada Entry de dirección.
        - Enlaza <KeyRelease> con debounce de 500ms para no saturar Nominatim.
        - Enlaza <FocusOut> con retardo de 250ms para que el click del dropdown
          pueda registrarse antes de que se oculte la ventana.
        - Enlaza <Configure> en la ventana principal para cerrar dropdowns si el
          usuario mueve o redimensiona la ventana.
        """
        self._debounce_ids = {"origen": None, "destino": None}

        self._dropdowns = {
            "origen": _AutocompleteDropdown(
                self,
                self.entry_direccion_origen,
                on_select=lambda addr: self._select_address(addr, "origen"),
            ),
            "destino": _AutocompleteDropdown(
                self,
                self.entry_direccion_destino,
                on_select=lambda addr: self._select_address(addr, "destino"),
            ),
        }

        # KeyRelease → debounce
        self.entry_direccion_origen.bind(
            "<KeyRelease>", lambda e: self._on_address_key(e, "origen")
        )
        self.entry_direccion_destino.bind(
            "<KeyRelease>", lambda e: self._on_address_key(e, "destino")
        )

        # FocusOut → ocultar con retardo para que el click del dropdown registre
        self.entry_direccion_origen.bind(
            "<FocusOut>",
            lambda e: self.after(250, self._dropdowns["origen"].hide),
        )
        self.entry_direccion_destino.bind(
            "<FocusOut>",
            lambda e: self.after(250, self._dropdowns["destino"].hide),
        )

        # Configure en la ventana principal → cerrar dropdowns al mover/redimensionar
        self.bind("<Configure>", self._on_win_configure)

    def _on_win_configure(self, event):
        """Cierra todos los dropdowns si la ventana principal cambia de tamaño o posición."""
        if event.widget is self and hasattr(self, "_dropdowns"):
            for d in self._dropdowns.values():
                d.hide()

    def _on_address_key(self, event, campo: str):
        """
        Handler de <KeyRelease> para los campos de dirección.
        Implementa debounce de 500ms: cancela el timer anterior y programa uno
        nuevo en cada pulsación, de modo que la API solo se consulta cuando el
        usuario se detiene medio segundo.
        """
        # Teclas que no deben disparar búsqueda nueva
        _SKIP = {
            "Escape", "Return", "KP_Enter", "Tab",
            "Left", "Right", "Home", "End", "Prior", "Next",
            "Up", "Down",
            "Shift_L", "Shift_R", "Control_L", "Control_R",
            "Alt_L", "Alt_R", "Meta_L", "Meta_R",
            "Caps_Lock", "Num_Lock", "Scroll_Lock",
        }

        if event.keysym == "Escape":
            self._dropdowns[campo].hide()
            return
        if event.keysym in _SKIP:
            return

        # Cancelar debounce previo
        if self._debounce_ids[campo]:
            self.after_cancel(self._debounce_ids[campo])
            self._debounce_ids[campo] = None

        entry = (
            self.entry_direccion_origen
            if campo == "origen"
            else self.entry_direccion_destino
        )
        query = entry.get().strip()

        if len(query) < 3:
            self._dropdowns[campo].hide()
            return

        # Programar búsqueda en 500ms
        self._debounce_ids[campo] = self.after(
            500,
            lambda q=query, c=campo: self._dispatch_suggestions(q, c),
        )

    def _dispatch_suggestions(self, query: str, campo: str):
        """
        Lanza un hilo daemon para consultar Nominatim sin bloquear la UI.
        Cuando el hilo termina, agenda _apply_suggestions en el hilo principal
        mediante self.after(0, ...).
        """
        def _worker():
            sugerencias = get_address_suggestions(query)
            self.after(
                0,
                lambda s=sugerencias, q=query, c=campo:
                    self._apply_suggestions(s, q, c),
            )

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_suggestions(self, suggestions: list, sent_query: str, campo: str):
        """
        Muestra las sugerencias recibidas en el dropdown correspondiente.

        Si el texto actual del Entry ya difiere del query que se envió (el usuario
        siguió escribiendo mientras esperaba la respuesta), descarta el resultado
        para evitar mostrar sugerencias obsoletas.
        """
        entry = (
            self.entry_direccion_origen
            if campo == "origen"
            else self.entry_direccion_destino
        )
        current = entry.get().strip()
        # Descartar respuestas tardías (el query ya cambió)
        if current.lower() != sent_query.lower():
            return
        self._dropdowns[campo].update(suggestions)

    def _select_address(self, address: str, campo: str):
        """
        Rellena el Entry con la dirección seleccionada del dropdown y
        devuelve el foco al campo para que el usuario pueda editarla si quiere.
        """
        entry = (
            self.entry_direccion_origen
            if campo == "origen"
            else self.entry_direccion_destino
        )
        entry.delete(0, "end")
        entry.insert(0, address)
        entry.focus_set()

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
        ids     = self.paradas_dict.get(nombre, [])
        stop_id = ids[0] if ids else None

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
