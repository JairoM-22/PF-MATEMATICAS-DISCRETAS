# ui.py — Transmetro Rutas: Modern Transit Route Planner
# Pure tkinter + tkinter.ttk. No external libraries.

import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox
import threading
from collections import defaultdict
import math

from data_loader import cargar_datos, obtener_paradas_unicas
from graph_manager import (
    construir_grafo,
    buscar_ruta_optima,
    calcular_costo_pasaje,
)
from map_generator import (
    generar_mapa_grafo,
    geocodificar_direccion,
    parada_mas_cercana,
    get_address_suggestions,
    normalizar_interseccion,
)
import graph_analyzer
import route_catalog

# ════════════════════════════════════════════════════════════════════════════════
# DESIGN SYSTEM
# ════════════════════════════════════════════════════════════════════════════════

class AppTheme:
    PRIMARY        = "#0A2463"
    ACCENT         = "#E63946"
    ACCENT_HOVER   = "#C1121F"
    PRIMARY_HOVER  = "#072360"
    SURFACE        = "#F8F9FA"
    CARD           = "#FFFFFF"
    TEXT_PRIMARY   = "#1D1D1D"
    TEXT_SECONDARY = "#6B7280"
    TEXT_MUTED     = "#9CA3AF"
    SUCCESS        = "#2EC4B6"
    WARNING        = "#F59E0B"
    ERROR          = "#EF4444"
    BORDER         = "#E5E7EB"
    PILL_SEL_BG    = "#0A2463"
    PILL_UNS_BG    = "#FFFFFF"

    FONT_FAMILY = "Segoe UI"
    F_HEAD  = (FONT_FAMILY, 10, "bold")
    F_LABEL = (FONT_FAMILY, 10)
    F_BODY  = (FONT_FAMILY, 11)
    F_BTN   = (FONT_FAMILY, 11, "bold")
    F_MONO  = ("Consolas", 10)

    PAD   = 12
    PAD_S = 6
    PAD_L = 16

    SIDEBAR = 360
    HEADER  = 56
    SBAR    = 28


def _apply_style():
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("TCombobox",
        font=AppTheme.F_BODY,
        fieldbackground=AppTheme.CARD,
        background=AppTheme.CARD,
        foreground=AppTheme.TEXT_PRIMARY,
        arrowcolor=AppTheme.PRIMARY,
        relief="solid", borderwidth=1, padding=5)
    s.map("TCombobox",
        fieldbackground=[("readonly", AppTheme.CARD)])
    s.configure("TSeparator", background=AppTheme.BORDER)
    s.configure("Vertical.TScrollbar",
        troughcolor=AppTheme.SURFACE,
        background=AppTheme.BORDER,
        arrowcolor=AppTheme.TEXT_SECONDARY)


_CONTRAPARTE_BUILDER = {
    "Calle": "Carrera", "Carrera": "Calle",
    "Diagonal": "Carrera", "Transversal": "Calle",
    "Avenida": "Calle", "Circular": "Carrera",
}

# ════════════════════════════════════════════════════════════════════════════════
# CUSTOM WIDGETS
# ════════════════════════════════════════════════════════════════════════════════

class _Card(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=AppTheme.CARD,
            highlightthickness=1, highlightbackground=AppTheme.BORDER,
            relief=tk.FLAT, **kw)

class _SecLabel(tk.Label):
    def __init__(self, parent, text, **kw):
        super().__init__(parent, text=text,
            font=AppTheme.F_HEAD, fg=AppTheme.TEXT_SECONDARY,
            bg=AppTheme.CARD, **kw)

class _NavBtn(tk.Button):
    def __init__(self, parent, text, command=None, **kw):
        super().__init__(parent, text=text,
            font=AppTheme.F_BTN,
            bg=AppTheme.PRIMARY, fg=AppTheme.CARD,
            activebackground=AppTheme.PRIMARY_HOVER,
            activeforeground=AppTheme.CARD,
            bd=0, relief=tk.FLAT, cursor="hand2",
            padx=AppTheme.PAD, pady=7,
            command=command, **kw)

class _AccentBtn(tk.Button):
    def __init__(self, parent, text, command=None, **kw):
        super().__init__(parent, text=text,
            font=AppTheme.F_BTN,
            bg=AppTheme.ACCENT, fg=AppTheme.CARD,
            activebackground=AppTheme.ACCENT_HOVER,
            activeforeground=AppTheme.CARD,
            bd=0, relief=tk.FLAT, cursor="hand2",
            padx=AppTheme.PAD, pady=8,
            command=command, **kw)

class _PillGroup(tk.Frame):
    def __init__(self, parent, options, command, default=0, bg=None, **kw):
        bg = bg or AppTheme.CARD
        super().__init__(parent, bg=bg, **kw)
        self._command = command
        self._btns = []
        self._var = tk.StringVar(value=options[default])

        for i, opt in enumerate(options):
            btn = tk.Button(
                self, text=opt,
                font=AppTheme.F_LABEL,
                bd=1, relief=tk.SOLID,
                cursor="hand2",
                padx=8, pady=4,
                command=lambda v=opt: self._select(v))
            btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                     padx=(0 if i == 0 else 2, 0))
            self._btns.append((btn, opt))

        self._select(options[default], fire=False)

    def _select(self, value, fire=True):
        self._var.set(value)
        for btn, opt in self._btns:
            if opt == value:
                btn.configure(bg=AppTheme.PILL_SEL_BG, fg=AppTheme.CARD, relief=tk.FLAT)
            else:
                btn.configure(bg=AppTheme.PILL_UNS_BG, fg=AppTheme.TEXT_PRIMARY, relief=tk.SOLID)
        if fire and self._command:
            self._command(value)

    def get(self):
        return self._var.get()

    def set(self, value):
        self._select(value, fire=False)


class _StatusBar(tk.Frame):
    _COLORS = {"idle": "#9CA3AF", "loading": "#0A2463",
               "success": "#2EC4B6", "error": "#EF4444"}

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=AppTheme.SURFACE, height=AppTheme.SBAR,
            relief=tk.GROOVE, bd=1, **kw)
        self.pack_propagate(False)
        self._dot = tk.Label(self, text="●", font=("Arial", 13),
            fg=self._COLORS["idle"], bg=AppTheme.SURFACE)
        self._dot.pack(side=tk.LEFT, padx=(10, 4))
        self._msg = tk.Label(self, text="Iniciando...", font=AppTheme.F_LABEL,
            fg=AppTheme.TEXT_SECONDARY, bg=AppTheme.SURFACE, anchor=tk.W)
        self._msg.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def set(self, text, kind="idle"):
        self._msg.configure(text=text)
        self._dot.configure(fg=self._COLORS.get(kind, self._COLORS["idle"]))


class _AutocompleteDropdown:
    _ROW_H = 36
    _MAX   = 5

    def __init__(self, root, entry, on_select):
        self._root = root
        self._entry = entry
        self._on_select = on_select
        self._win = None
        self._body = None
        self._current = []

    def update(self, suggestions):
        if not suggestions:
            self.hide(); return
        self._current = suggestions
        self._ensure_win()
        self._build(suggestions)
        self._reposition()
        self._win.deiconify()
        self._win.lift()

    def hide(self):
        if self._win and self._win.winfo_exists():
            self._win.withdraw()

    def _ensure_win(self):
        if self._win and self._win.winfo_exists():
            return
        self._win = tk.Toplevel(self._root)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        border = tk.Frame(self._win, bg="#C7C7CC")
        border.pack(fill="both", expand=True)
        self._body = tk.Frame(border, bg=AppTheme.CARD)
        self._body.pack(fill="both", expand=True, padx=1, pady=1)

    def _build(self, suggestions):
        for c in self._body.winfo_children():
            c.destroy()
        for idx, addr in enumerate(suggestions):
            display = (addr[:58] + "...") if len(addr) > 61 else addr
            full = addr
            row = tk.Frame(self._body, bg=AppTheme.CARD, height=self._ROW_H, cursor="hand2")
            row.pack(fill="x"); row.pack_propagate(False)
            ico = tk.Label(row, text=" o ", bg=AppTheme.CARD,
                fg=AppTheme.PRIMARY, font=("Segoe UI", 9), cursor="hand2")
            ico.pack(side=tk.LEFT)
            lbl = tk.Label(row, text=display, bg=AppTheme.CARD,
                fg=AppTheme.TEXT_PRIMARY, font=AppTheme.F_LABEL,
                anchor="w", cursor="hand2")
            lbl.pack(side=tk.LEFT, fill="both", expand=True, padx=(0, 8))
            if idx < len(suggestions) - 1:
                tk.Frame(self._body, bg=AppTheme.BORDER, height=1).pack(fill="x", padx=8)

            def _enter(e, r=row, i=ico, l=lbl):
                for w in (r, i, l): w.configure(bg=AppTheme.SURFACE)
            def _leave(e, r=row, i=ico, l=lbl):
                for w in (r, i, l): w.configure(bg=AppTheme.CARD)
            def _click(e, a=full):
                self._on_select(a); self.hide()
            for w in (row, ico, lbl):
                w.bind("<Enter>", _enter)
                w.bind("<Leave>", _leave)
                w.bind("<Button-1>", _click)

    def _reposition(self):
        self._entry.update_idletasks()
        x  = self._entry.winfo_rootx()
        y  = self._entry.winfo_rooty() + self._entry.winfo_height() + 2
        ew = self._entry.winfo_width()
        n  = min(len(self._current), self._MAX)
        self._win.geometry(f"{ew}x{n * self._ROW_H + 2}+{x}+{y}")


# ════════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ════════════════════════════════════════════════════════════════════════════════

class AppTransmetro(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Transmetro Rutas — Barranquilla")
        self.geometry("1320x820")
        self.minsize(1100, 700)
        self.configure(bg=AppTheme.SURFACE)
        _apply_style()

        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-1320)//2}+{(sh-820)//2}")

        self.grafo           = None
        self.paradas_dict    = {}
        self.modo_ruta       = "rapido"
        self.modo_busq       = "libre"
        self.modo_geo        = "rapido"
        self._rutas_catalog  = None
        self._route_names    = {}
        self._debounce       = {"origen": None, "destino": None}

        self._build_ui()
        self._setup_autocomplete()
        self.after(400, self._hilo_cargar)

    # ────────────────────────────────────────────────────────────────────────────
    # UI BUILD
    # ────────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        hdr = tk.Frame(self, bg=AppTheme.PRIMARY, height=AppTheme.HEADER)
        hdr.pack(side=tk.TOP, fill=tk.X)
        hdr.pack_propagate(False)

        tk.Label(hdr, text="🚌", font=("Arial", 22),
            bg=AppTheme.PRIMARY, fg=AppTheme.CARD).pack(side=tk.LEFT, padx=(16, 8), pady=8)

        ttl = tk.Frame(hdr, bg=AppTheme.PRIMARY)
        ttl.pack(side=tk.LEFT, pady=8)
        tk.Label(ttl, text="Transmetro Rutas", font=(AppTheme.FONT_FAMILY, 15, "bold"),
            bg=AppTheme.PRIMARY, fg=AppTheme.CARD).pack(anchor=tk.W)
        tk.Label(ttl, text="Barranquilla  Planificador de Rutas",
            font=AppTheme.F_LABEL, bg=AppTheme.PRIMARY, fg=AppTheme.TEXT_MUTED).pack(anchor=tk.W)

        self.statusbar = _StatusBar(self)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

        main = tk.Frame(self, bg=AppTheme.SURFACE)
        main.pack(fill=tk.BOTH, expand=True)

        sidebar_outer = tk.Frame(main, bg=AppTheme.SURFACE,
            width=AppTheme.SIDEBAR, highlightthickness=0)
        sidebar_outer.pack(side=tk.LEFT, fill=tk.Y,
            padx=(AppTheme.PAD_S, 0), pady=AppTheme.PAD_S)
        sidebar_outer.pack_propagate(False)

        canvas = tk.Canvas(sidebar_outer, bg=AppTheme.SURFACE,
            highlightthickness=0, width=AppTheme.SIDEBAR - 14)
        sb = ttk.Scrollbar(sidebar_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.left_panel = tk.Frame(canvas, bg=AppTheme.SURFACE)
        win_id = canvas.create_window((0, 0), window=self.left_panel, anchor="nw")

        def _on_resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())
        self.left_panel.bind("<Configure>", _on_resize)
        canvas.bind("<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self._build_sidebar()

        right_outer = tk.Frame(main, bg=AppTheme.SURFACE)
        right_outer.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True,
            padx=AppTheme.PAD_S, pady=AppTheme.PAD_S)

        self._build_results_panel(right_outer)

    def _build_results_panel(self, parent):
        card = _Card(parent)
        card.pack(fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(card, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y, pady=1)

        self.txt_resultado = tk.Text(
            card,
            font=(AppTheme.FONT_FAMILY, 11),
            fg=AppTheme.TEXT_PRIMARY,
            bg=AppTheme.CARD,
            relief=tk.FLAT,
            wrap=tk.WORD,
            yscrollcommand=vsb.set,
            state=tk.DISABLED,
            padx=24, pady=20,
            cursor="arrow",
        )
        self.txt_resultado.pack(fill=tk.BOTH, expand=True)
        vsb.configure(command=self.txt_resultado.yview)

        FF = AppTheme.FONT_FAMILY
        T  = self.txt_resultado

        T.tag_configure("title",
            font=(FF, 18, "bold"), foreground=AppTheme.PRIMARY,
            spacing1=4, spacing3=2)
        T.tag_configure("subtitle",
            font=(FF, 11), foreground=AppTheme.TEXT_SECONDARY,
            spacing3=12)
        T.tag_configure("section",
            font=(FF, 9, "bold"), foreground=AppTheme.TEXT_MUTED,
            spacing1=14, spacing3=4)
        T.tag_configure("met_val",
            font=(FF, 14, "bold"), foreground=AppTheme.PRIMARY)
        T.tag_configure("met_label",
            font=(FF, 9), foreground=AppTheme.TEXT_MUTED)
        T.tag_configure("cost_val",
            font=(FF, 14, "bold"), foreground=AppTheme.ACCENT)
        T.tag_configure("origin",
            font=(FF, 12, "bold"), foreground=AppTheme.SUCCESS,
            spacing1=8, lmargin1=8, lmargin2=8)
        T.tag_configure("dest",
            font=(FF, 12, "bold"), foreground=AppTheme.ACCENT,
            spacing1=4, lmargin1=8, lmargin2=8)
        T.tag_configure("bus_line",
            font=(FF, 11, "bold"), foreground=AppTheme.CARD,
            background=AppTheme.PRIMARY,
            spacing1=10, spacing3=2, lmargin1=8, lmargin2=8)
        T.tag_configure("bus_dir",
            font=(FF, 10), foreground=AppTheme.TEXT_SECONDARY,
            lmargin1=8, lmargin2=8)
        T.tag_configure("stop",
            font=(FF, 10), foreground=AppTheme.TEXT_SECONDARY,
            lmargin1=28, lmargin2=28, spacing1=1)
        T.tag_configure("transfer",
            font=(FF, 11, "bold"), foreground=AppTheme.WARNING,
            spacing1=8, lmargin1=8, lmargin2=8)
        T.tag_configure("walk",
            font=(FF, 10, "italic"), foreground=AppTheme.TEXT_MUTED,
            spacing1=6, lmargin1=8, lmargin2=8)
        T.tag_configure("muted",
            font=(FF, 10), foreground=AppTheme.TEXT_MUTED,
            lmargin1=8)
        T.tag_configure("placeholder",
            font=(FF, 13), foreground=AppTheme.TEXT_MUTED,
            justify=tk.CENTER, spacing1=4)

    def _build_sidebar(self):
        P  = AppTheme.PAD
        PS = AppTheme.PAD_S

        # ── Card 1: Ruta por parada ───────────────────────────────────────────
        c1 = _Card(self.left_panel)
        c1.pack(fill=tk.X, padx=PS, pady=(PS, 0))
        _SecLabel(c1, "RUTA POR PARADA").pack(anchor=tk.W, padx=P, pady=(P, PS))

        tk.Label(c1, text="Origen", font=AppTheme.F_LABEL,
            fg=AppTheme.TEXT_SECONDARY, bg=AppTheme.CARD).pack(anchor=tk.W, padx=P)
        self.combo_origen = ttk.Combobox(c1, state="disabled", height=8)
        self.combo_origen.pack(fill=tk.X, padx=P, pady=(2, PS))

        dr = tk.Frame(c1, bg=AppTheme.CARD)
        dr.pack(fill=tk.X, padx=P)
        tk.Label(dr, text="Destino", font=AppTheme.F_LABEL,
            fg=AppTheme.TEXT_SECONDARY, bg=AppTheme.CARD).pack(side=tk.LEFT)
        tk.Button(dr, text="swap", font=("Arial", 11, "bold"),
            bg=AppTheme.SURFACE, fg=AppTheme.PRIMARY,
            activebackground=AppTheme.BORDER, bd=1, relief=tk.SOLID,
            cursor="hand2", padx=6, pady=1,
            command=self._swap_stations).pack(side=tk.RIGHT)

        self.combo_destino = ttk.Combobox(c1, state="disabled", height=8)
        self.combo_destino.pack(fill=tk.X, padx=P, pady=(2, PS))

        tk.Label(c1, text="Modo de optimizacion", font=AppTheme.F_LABEL,
            fg=AppTheme.TEXT_SECONDARY, bg=AppTheme.CARD).pack(anchor=tk.W, padx=P)
        self.modo_pills = _PillGroup(c1,
            ["Menor distancia", "Menor costo"],
            command=self._on_modo_change, bg=AppTheme.CARD)
        self.modo_pills.pack(fill=tk.X, padx=P, pady=(3, PS))

        self.btn_calcular = _AccentBtn(c1, "Buscar Ruta", command=self._calcular_ruta)
        self.btn_calcular.configure(state=tk.DISABLED)
        self.btn_calcular.pack(fill=tk.X, padx=P, pady=(0, P))

        # ── Card 2: Busqueda Inteligente ──────────────────────────────────────
        c2 = _Card(self.left_panel)
        c2.pack(fill=tk.X, padx=PS, pady=(PS, 0))
        _SecLabel(c2, "BUSQUEDA INTELIGENTE").pack(anchor=tk.W, padx=P, pady=(P, PS))

        self.busq_pills = _PillGroup(c2,
            ["Busqueda Libre", "Constructor"],
            command=self._on_busq_mode, bg=AppTheme.CARD)
        self.busq_pills.pack(fill=tk.X, padx=P, pady=(0, PS))

        self.frame_busq_slot = tk.Frame(c2, bg=AppTheme.CARD)
        self.frame_busq_slot.pack(fill=tk.X, padx=P, pady=(0, PS))

        self.frame_libre = tk.Frame(self.frame_busq_slot, bg=AppTheme.CARD)
        self.frame_libre.pack(fill=tk.X)

        tk.Label(self.frame_libre, text="Tu ubicacion (direccion)",
            font=AppTheme.F_LABEL, fg=AppTheme.TEXT_SECONDARY, bg=AppTheme.CARD).pack(anchor=tk.W)
        self.entry_origen = tk.Entry(self.frame_libre,
            font=AppTheme.F_BODY, relief=tk.SOLID, bd=1,
            fg=AppTheme.TEXT_PRIMARY, bg=AppTheme.CARD,
            insertbackground=AppTheme.PRIMARY)
        self.entry_origen.pack(fill=tk.X, pady=(2, PS))

        tk.Label(self.frame_libre, text="A donde vas (direccion)",
            font=AppTheme.F_LABEL, fg=AppTheme.TEXT_SECONDARY, bg=AppTheme.CARD).pack(anchor=tk.W)
        self.entry_destino = tk.Entry(self.frame_libre,
            font=AppTheme.F_BODY, relief=tk.SOLID, bd=1,
            fg=AppTheme.TEXT_PRIMARY, bg=AppTheme.CARD,
            insertbackground=AppTheme.PRIMARY)
        self.entry_destino.pack(fill=tk.X, pady=(2, PS))

        self.frame_constr = tk.Frame(self.frame_busq_slot, bg=AppTheme.CARD)

        _TIPOS   = ["Calle", "Carrera", "Diagonal", "Transversal", "Avenida", "Circular"]
        _NUMS    = [str(i) for i in range(1, 121)]
        _SUFIJOS = ["", "A", "B", "C", "D", "Sur", "Norte", "Bis"]
        _PLACAS  = [str(i) for i in range(1, 100)]

        def _bloque(parent, label_text, campo):
            tk.Label(parent, text=label_text, font=(AppTheme.FONT_FAMILY, 9, "bold"),
                fg=AppTheme.PRIMARY, bg=AppTheme.CARD).pack(anchor=tk.W, pady=(PS, 2))
            r1 = tk.Frame(parent, bg=AppTheme.CARD); r1.pack(fill=tk.X, pady=(0, 2))
            tipo = ttk.Combobox(r1, values=_TIPOS, width=10, state="readonly")
            tipo.set("Calle"); tipo.pack(side=tk.LEFT, padx=(0, 3))
            num  = ttk.Combobox(r1, values=_NUMS, width=5)
            num.set("1");  num.pack(side=tk.LEFT, padx=(0, 3))
            suf  = ttk.Combobox(r1, values=_SUFIJOS, width=5)
            suf.set("");   suf.pack(side=tk.LEFT)
            r2 = tk.Frame(parent, bg=AppTheme.CARD); r2.pack(fill=tk.X, pady=(0, 2))
            tk.Label(r2, text="#", font=AppTheme.F_BODY,
                fg=AppTheme.TEXT_SECONDARY, bg=AppTheme.CARD).pack(side=tk.LEFT, padx=(0, 2))
            cruce = ttk.Combobox(r2, values=_NUMS, width=5)
            cruce.set("1"); cruce.pack(side=tk.LEFT, padx=(0, 3))
            tk.Label(r2, text="-", font=AppTheme.F_BODY,
                fg=AppTheme.TEXT_SECONDARY, bg=AppTheme.CARD).pack(side=tk.LEFT, padx=(0, 2))
            placa = ttk.Combobox(r2, values=_PLACAS, width=5)
            placa.set("1"); placa.pack(side=tk.LEFT)
            prev = tk.Label(parent, text="", font=(AppTheme.FONT_FAMILY, 9, "italic"),
                fg=AppTheme.PRIMARY, bg=AppTheme.CARD, anchor=tk.W)
            prev.pack(fill=tk.X, pady=(0, 2))
            widgets = {"tipo": tipo, "num": num, "suf": suf,
                       "cruce": cruce, "placa": placa, "preview": prev}
            for w in (tipo, num, suf, cruce, placa):
                w.bind("<<ComboboxSelected>>", lambda e, c=campo: self._actualizar_preview(c))
                w.bind("<KeyRelease>",          lambda e, c=campo: self._actualizar_preview(c))
            return widgets

        self.constr_o = _bloque(self.frame_constr, "Origen", "origen")
        ttk.Separator(self.frame_constr, orient="horizontal").pack(fill=tk.X, pady=PS)
        self.constr_d = _bloque(self.frame_constr, "Destino", "destino")

        tk.Label(c2, text="Modo de optimizacion", font=AppTheme.F_LABEL,
            fg=AppTheme.TEXT_SECONDARY, bg=AppTheme.CARD).pack(anchor=tk.W, padx=P, pady=(PS, 2))
        self.modo_geo_pills = _PillGroup(c2,
            ["Menor distancia", "Menor costo"],
            command=self._on_modo_geo_change, bg=AppTheme.CARD)
        self.modo_geo_pills.pack(fill=tk.X, padx=P, pady=(0, PS))

        self.btn_geo = _AccentBtn(c2, "Buscar por Direccion",
            command=self._calcular_ruta_por_direccion)
        self.btn_geo.configure(state=tk.DISABLED)
        self.btn_geo.pack(fill=tk.X, padx=P, pady=(0, P))

        # ── Card 3: Ver Ruta en Mapa ──────────────────────────────────────────
        c3 = _Card(self.left_panel)
        c3.pack(fill=tk.X, padx=PS, pady=(PS, 0))
        _SecLabel(c3, "VER RUTA EN MAPA").pack(anchor=tk.W, padx=P, pady=(P, PS))

        tk.Label(c3, text="Selecciona una ruta",
            font=AppTheme.F_LABEL, fg=AppTheme.TEXT_SECONDARY, bg=AppTheme.CARD
        ).pack(anchor=tk.W, padx=P)
        self.combo_ruta_mapa = ttk.Combobox(c3, state="disabled", height=8)
        self.combo_ruta_mapa.pack(fill=tk.X, padx=P, pady=(2, PS))

        self.btn_ver_ruta = _NavBtn(c3, "Mostrar ruta en mapa",
            command=self._ver_ruta_en_mapa)
        self.btn_ver_ruta.configure(state=tk.DISABLED)
        self.btn_ver_ruta.pack(fill=tk.X, padx=P, pady=(0, P))

        # ── Card 4: Analisis del Grafo ────────────────────────────────────────
        c4 = _Card(self.left_panel)
        c4.pack(fill=tk.X, padx=PS, pady=(PS, PS))
        _SecLabel(c4, "ANALISIS DEL GRAFO").pack(anchor=tk.W, padx=P, pady=(P, PS))

        self.btn_metricas = _NavBtn(c4, "Metricas globales",
            command=self._calcular_metricas)
        self.btn_metricas.configure(state=tk.DISABLED)
        self.btn_metricas.pack(fill=tk.X, padx=P, pady=(0, PS))

        self.btn_centralidad = _NavBtn(c4, "Medidas de centralidad",
            command=self._calcular_centralidad)
        self.btn_centralidad.configure(state=tk.DISABLED)
        self.btn_centralidad.pack(fill=tk.X, padx=P, pady=(0, P))

    # ────────────────────────────────────────────────────────────────────────────
    # RESULTS PANEL helpers
    # ────────────────────────────────────────────────────────────────────────────

    def _r(self, text, tag=None):
        self.txt_resultado.configure(state=tk.NORMAL)
        if tag:
            self.txt_resultado.insert(tk.END, text, tag)
        else:
            self.txt_resultado.insert(tk.END, text)
        self.txt_resultado.configure(state=tk.DISABLED)

    def _r_clear(self):
        self.txt_resultado.configure(state=tk.NORMAL)
        self.txt_resultado.delete("1.0", tk.END)
        self.txt_resultado.configure(state=tk.DISABLED)

    # ────────────────────────────────────────────────────────────────────────────
    # ROUTE SEGMENTATION
    # ────────────────────────────────────────────────────────────────────────────

    def _parsear_segmentos(self, camino):
        segmentos = []
        if len(camino) < 2:
            return segmentos

        seg_paradas   = [camino[0]]
        rutas_activas = None
        ruta_seg      = None
        en_bus        = False

        for i in range(len(camino) - 1):
            u, v = camino[i], camino[i + 1]
            data = self.grafo.get_edge_data(u, v) or {}
            tipo = data.get("type", "viaje")

            if tipo == "transferencia":
                if en_bus and len(seg_paradas) > 1:
                    segmentos.append({
                        "tipo": "bus",
                        "route_id": ruta_seg,
                        "paradas": seg_paradas[:],
                    })
                seg_paradas   = [v]
                rutas_activas = None
                ruta_seg      = None
                en_bus        = False
                continue

            rutas_tramo = set(data.get("routes", set()))

            if rutas_activas is None:
                rutas_activas = rutas_tramo
                ruta_seg      = next(iter(rutas_tramo), None)
                seg_paradas.append(v)
                en_bus = True
            else:
                interseccion = rutas_activas & rutas_tramo
                if interseccion:
                    rutas_activas = interseccion
                    ruta_seg      = next(iter(interseccion), ruta_seg)
                    seg_paradas.append(v)
                else:
                    segmentos.append({
                        "tipo": "bus",
                        "route_id": ruta_seg,
                        "paradas": seg_paradas[:],
                    })
                    seg_paradas   = [camino[i], v]
                    rutas_activas = rutas_tramo
                    ruta_seg      = next(iter(rutas_tramo), None)

        if en_bus and len(seg_paradas) > 1:
            segmentos.append({
                "tipo": "bus",
                "route_id": ruta_seg,
                "paradas": seg_paradas,
            })

        return segmentos

    # ────────────────────────────────────────────────────────────────────────────
    # RESULTS RENDERER
    # ────────────────────────────────────────────────────────────────────────────

    def _mostrar_resultado_ruta(self, nombre_o, nombre_d,
                                distancia, buses_tomados, camino,
                                origen_info=None, destino_info=None):
        tiempo      = round((distancia / 22) * 60, 1)
        transbordos = max(0, buses_tomados - 1)
        pasajes, costo = calcular_costo_pasaje(buses_tomados)
        segmentos   = self._parsear_segmentos(camino)

        self._r_clear()

        self._r("  Ruta encontrada\n", "title")
        self._r(f"  {nombre_o}  ->  {nombre_d}\n", "subtitle")

        self._r("\n")
        self._r(f"  {distancia:.2f} km", "met_val")
        self._r("   distancia\n", "met_label")
        self._r(f"  {tiempo} min", "met_val")
        self._r("   tiempo estimado\n", "met_label")
        self._r(f"  {buses_tomados} bus{'es' if buses_tomados > 1 else ''}", "met_val")
        if transbordos:
            self._r(f"   ({transbordos} transbordo{'s' if transbordos > 1 else ''})\n", "met_label")
        else:
            self._r("   sin transbordos\n", "met_label")
        self._r(f"  {pasajes} pasaje{'s' if pasajes > 1 else ''}  *  ", "met_val")
        self._r(f"${costo:,} COP\n", "cost_val")

        self._r("\n")
        self._r("  " + "-" * 48 + "\n", "muted")
        self._r("  ITINERARIO\n", "section")
        self._r("  " + "-" * 48 + "\n", "muted")

        if origen_info:
            self._r(f"\n  Camina {origen_info['walk_m']} m hasta la primera parada\n", "walk")

        for idx, seg in enumerate(segmentos):
            paradas  = seg["paradas"]
            route_id = seg.get("route_id")
            rname    = self._route_names.get(str(route_id), str(route_id) if route_id else "?")

            nom_inicio = self.grafo.nodes.get(paradas[0], {}).get("nombre", str(paradas[0]))

            if idx == 0:
                self._r(f"\n  {nom_inicio}\n", "origin")
            else:
                self._r(f"\n  Transborda en  {nom_inicio}\n", "transfer")

            nom_final = self.grafo.nodes.get(paradas[-1], {}).get("nombre", str(paradas[-1]))
            self._r(f"  {rname}  ", "bus_line")
            self._r(f"  ->  direccion {nom_final}\n", "bus_dir")

            middle = paradas[1:-1]
            if middle:
                for sid in middle:
                    nom = self.grafo.nodes.get(sid, {}).get("nombre", str(sid))
                    self._r(f"  |   {nom}\n", "stop")
            else:
                self._r("  |   (parada directa)\n", "stop")

        if segmentos:
            nom_dest = self.grafo.nodes.get(
                segmentos[-1]["paradas"][-1], {}).get("nombre",
                segmentos[-1]["paradas"][-1])
            self._r(f"\n  {nom_dest}\n", "dest")

        if destino_info:
            self._r(f"  Camina {destino_info['walk_m']} m hasta tu destino\n", "walk")

        self._r("\n  " + "-" * 48 + "\n", "muted")
        self._r(f"  {len(camino)} paradas en total\n", "muted")

        self.txt_resultado.configure(state=tk.NORMAL)
        self.txt_resultado.see("1.0")
        self.txt_resultado.configure(state=tk.DISABLED)

    # ────────────────────────────────────────────────────────────────────────────
    # CALLBACKS
    # ────────────────────────────────────────────────────────────────────────────

    def _on_modo_change(self, value):
        self.modo_ruta = "ahorro" if "costo" in value.lower() else "rapido"

    def _on_modo_geo_change(self, value):
        self.modo_geo = "ahorro" if "costo" in value.lower() else "rapido"

    def _on_busq_mode(self, value):
        self.modo_busq = "libre" if "Libre" in value else "constructor"
        if self.modo_busq == "libre":
            self.frame_constr.pack_forget()
            self.frame_libre.pack(fill=tk.X)
        else:
            self.frame_libre.pack_forget()
            self.frame_constr.pack(fill=tk.X)

    def _swap_stations(self):
        a, b = self.combo_origen.get(), self.combo_destino.get()
        self.combo_origen.set(b); self.combo_destino.set(a)

    def _actualizar_preview(self, campo):
        try:
            c = self.constr_o if campo == "origen" else self.constr_d
            tipo  = c["tipo"].get().strip()
            num   = c["num"].get().strip()
            suf   = c["suf"].get().strip()
            cruce = c["cruce"].get().strip()
            if not num:
                c["preview"].configure(text=""); return
            base = f"{tipo} {num}{suf}"
            if cruce:
                cp = _CONTRAPARTE_BUILDER.get(tipo, "Calle")
                preview = f"{base} con {cp} {cruce}"
            else:
                preview = base
            c["preview"].configure(text=f"-> {preview}")
        except Exception:
            pass

    def _ensamblar_direccion(self, campo):
        c = self.constr_o if campo == "origen" else self.constr_d
        tipo  = c["tipo"].get().strip()
        num   = c["num"].get().strip()
        suf   = c["suf"].get().strip()
        cruce = c["cruce"].get().strip()
        if not num:
            return ""
        base = f"{tipo} {num}{suf}"
        if cruce:
            cp = _CONTRAPARTE_BUILDER.get(tipo, "Calle")
            return f"{base} con {cp} {cruce}, Barranquilla, Colombia"
        return f"{base}, Barranquilla, Colombia"

    # ── Carga inicial silenciosa ───────────────────────────────────────────────

    def _hilo_cargar(self):
        self.statusbar.set("Iniciando...", "loading")
        threading.Thread(target=self._cargar_dataset, daemon=True).start()

    def _cargar_dataset(self):
        try:
            stops, stop_times, trips, routes = cargar_datos()
            self.grafo = construir_grafo(stops, stop_times, trips)

            paradas_raw = obtener_paradas_unicas(stops)
            pbn = defaultdict(list)
            for sid, nombre in paradas_raw.items():
                if sid in self.grafo.nodes:
                    pbn[nombre].append(sid)
            nombres = sorted(pbn.keys())
            self.paradas_dict = dict(pbn)

            self._route_names = {}
            for _, row in routes.iterrows():
                rid   = str(row.get("route_id", ""))
                short = str(row.get("route_short_name", "")).strip()
                long_ = str(row.get("route_long_name",  "")).strip()
                self._route_names[rid] = short or long_ or rid

            try:
                cat = route_catalog.obtener_catalogo_rutas()
                rutas_items = [
                    f"{row['route_short_name']} -- {row['route_long_name']}"
                    for _, row in cat.iterrows()
                ]
                self._rutas_catalog = cat
            except Exception:
                rutas_items = []
                self._rutas_catalog = None

            self.after(0, lambda: self._ui_tras_carga(nombres, rutas_items))

        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._error_carga(err))

    def _ui_tras_carga(self, nombres, rutas_items):
        n = len(nombres)
        self.statusbar.set(f"Listo  -  {n} estaciones disponibles", "success")

        self.combo_origen.configure(values=nombres, state="readonly")
        self.combo_destino.configure(values=nombres, state="readonly")
        self.combo_origen.set(nombres[0] if nombres else "")
        self.combo_destino.set(nombres[-1] if nombres else "")

        if rutas_items:
            self.combo_ruta_mapa.configure(values=rutas_items, state="readonly")
            self.combo_ruta_mapa.set(rutas_items[0])

        for btn in (self.btn_calcular, self.btn_geo,
                    self.btn_ver_ruta, self.btn_metricas, self.btn_centralidad):
            btn.configure(state=tk.NORMAL)

        self._r_clear()
        self._r("\n")
        self._r("  Transmetro Barranquilla\n", "title")
        self._r("  Planificador de rutas\n\n", "subtitle")
        self._r("  " + "-" * 48 + "\n", "muted")
        self._r("  MODOS DE BUSQUEDA\n", "section")
        self._r("  " + "-" * 48 + "\n", "muted")
        self._r("\n  Menor distancia\n", "met_val")
        self._r("      Minimiza kilometros recorridos.\n", "met_label")
        self._r("\n  Menor costo\n", "cost_val")
        self._r("      Minimiza pasajes pagados.\n"
                "      1 pasaje = hasta 3 buses = $3,700 COP.\n", "met_label")
        self._r("\n  " + "-" * 48 + "\n", "muted")
        self._r("  Selecciona origen y destino\n"
                "  y presiona Buscar Ruta.\n", "walk")

    def _error_carga(self, err):
        self.statusbar.set("Error al iniciar", "error")
        messagebox.showerror("Error al cargar la red", f"No se pudo inicializar la red:\n\n{err}")

    # ── Route by station ──────────────────────────────────────────────────────

    def _calcular_ruta(self):
        if self.grafo is None:
            messagebox.showwarning("No disponible", "La red aun esta iniciando, espera un momento.")
            return
        nom_o = self.combo_origen.get()
        nom_d = self.combo_destino.get()
        if nom_o == nom_d:
            messagebox.showwarning("Seleccion invalida", "Origen y destino son iguales.")
            return
        ids_o = self.paradas_dict.get(nom_o, [])
        ids_d = self.paradas_dict.get(nom_d, [])
        if not ids_o or not ids_d:
            messagebox.showerror("Error", "No se encontraron IDs de parada.")
            return

        self.btn_calcular.configure(state=tk.DISABLED, text="Calculando...")
        self.statusbar.set("Calculando ruta...", "loading")

        def _run():
            camino, dist, buses = buscar_ruta_optima(
                self.grafo, ids_o, ids_d, modo=self.modo_ruta)
            self.after(0, lambda: self._mostrar_ruta_parada(nom_o, nom_d, camino, dist, buses))

        threading.Thread(target=_run, daemon=True).start()

    def _mostrar_ruta_parada(self, nom_o, nom_d, camino, dist, buses):
        self.btn_calcular.configure(state=tk.NORMAL, text="Buscar Ruta")
        if camino is None:
            self.statusbar.set("Sin conexion", "error")
            self._r_clear()
            self._r("\n\n  Sin ruta disponible\n", "title")
            self._r(f"\n  {nom_o}  ->  {nom_d}\n\n", "subtitle")
            self._r("  Las paradas seleccionadas no estan conectadas.\n", "walk")
            return

        self._mostrar_resultado_ruta(nom_o, nom_d, dist, buses, camino)
        self.statusbar.set(f"Ruta: {dist:.1f} km", "success")
        threading.Thread(target=lambda: generar_mapa_grafo(
            self.grafo, ruta_resaltada=camino,
            parada_origen=camino[0], parada_destino=camino[-1]),
            daemon=True).start()

    # ── Route by address ──────────────────────────────────────────────────────

    def _calcular_ruta_por_direccion(self):
        if self.grafo is None:
            messagebox.showwarning("No disponible", "La red aun esta iniciando, espera un momento.")
            return

        if self.modo_busq == "libre":
            txt_o = self.entry_origen.get().strip()
            txt_d = self.entry_destino.get().strip()
        else:
            txt_o = self._ensamblar_direccion("origen")
            txt_d = self._ensamblar_direccion("destino")

        if not txt_o or not txt_d:
            messagebox.showwarning("Campos vacios", "Ingresa ambas direcciones.")
            return

        self.btn_geo.configure(state=tk.DISABLED, text="Geocodificando...")
        self.statusbar.set("Geocodificando...", "loading")
        self._r_clear()
        self._r("\n\n  Geocodificando direcciones...\n", "placeholder")

        threading.Thread(target=self._hilo_geo, args=(txt_o, txt_d), daemon=True).start()

    def _hilo_geo(self, txt_o, txt_d):
        try:
            lat_o, lon_o = geocodificar_direccion(txt_o)
            if lat_o is None:
                self.after(0, lambda: self._geo_error(
                    f"No se encontro la direccion de origen:\n{txt_o}")); return

            lat_d, lon_d = geocodificar_direccion(txt_d)
            if lat_d is None:
                self.after(0, lambda: self._geo_error(
                    f"No se encontro la direccion de destino:\n{txt_d}")); return

            stop_o, nom_o, dist_o = parada_mas_cercana(self.grafo, lat_o, lon_o)
            stop_d, nom_d, dist_d = parada_mas_cercana(self.grafo, lat_d, lon_d)

            camino, dist, buses = buscar_ruta_optima(
                self.grafo, stop_o, stop_d, modo=self.modo_geo)

            walk_o = round(dist_o * 1000)
            walk_d = round(dist_d * 1000)

            def _show():
                self._mostrar_resultado_ruta(
                    nom_o, nom_d, dist, buses, camino,
                    origen_info={"walk_m": walk_o},
                    destino_info={"walk_m": walk_d})
                self.statusbar.set(f"Ruta por direccion: {dist:.1f} km", "success")
                generar_mapa_grafo(
                    self.grafo, ruta_resaltada=camino,
                    origen_coords=(lat_o, lon_o),
                    destino_coords=(lat_d, lon_d),
                    parada_origen=stop_o, parada_destino=stop_d)

            self.after(0, _show)

        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._geo_error(f"Error inesperado:\n{err}"))
        finally:
            self.after(0, lambda: self.btn_geo.configure(
                state=tk.NORMAL, text="Buscar por Direccion"))

    def _geo_error(self, msg):
        self.statusbar.set("Direccion no encontrada", "error")
        messagebox.showerror("Direccion no encontrada", msg)
        self._r_clear()
        self._r("\n\n  Direccion no encontrada\n", "title")
        self._r("\n  Intenta con formatos como:\n", "walk")
        self._r("  Carrera 54 con Calle 72\n", "stop")
        self._r("  Portal del Prado\n", "stop")

    # ── Ver ruta en mapa ──────────────────────────────────────────────────────

    def _ver_ruta_en_mapa(self):
        if self.grafo is None or self._rutas_catalog is None:
            messagebox.showwarning("No disponible", "La red aun esta iniciando, espera un momento.")
            return
        sel = self.combo_ruta_mapa.get()
        if not sel:
            return

        try:
            cat   = self._rutas_catalog
            short = sel.split(" -- ")[0].strip()
            row   = cat[cat["route_short_name"].astype(str) == short]
            if row.empty:
                messagebox.showwarning("Ruta no encontrada", f"No se encontro: {short}")
                return
            route_id = row.iloc[0]["route_id"]
        except Exception as e:
            messagebox.showerror("Error", str(e)); return

        rid_str = str(route_id)
        self.btn_ver_ruta.configure(state=tk.DISABLED, text="Generando mapa...")
        self.statusbar.set(f"Generando mapa para ruta {short}...", "loading")

        def _run():
            try:
                generar_mapa_grafo(self.grafo, route_id_resaltado=rid_str)
                self.after(0, lambda: self.statusbar.set(
                    f"Mapa generado para {short}", "success"))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: messagebox.showerror("Error", err))
                self.after(0, lambda: self.statusbar.set("Error al generar mapa", "error"))
            finally:
                self.after(0, lambda: self.btn_ver_ruta.configure(
                    state=tk.NORMAL, text="Mostrar ruta en mapa"))

        threading.Thread(target=_run, daemon=True).start()

    # ── Analisis del grafo ────────────────────────────────────────────────────

    def _calcular_metricas(self):
        if self.grafo is None:
            messagebox.showwarning("No disponible", "La red aun esta iniciando, espera un momento.")
            return
        self.btn_metricas.configure(state=tk.DISABLED, text="Calculando...")
        self.statusbar.set("Calculando metricas globales...", "loading")
        self._r_clear()
        self._r("\n\n  Calculando metricas del grafo...\n", "placeholder")
        threading.Thread(target=self._hilo_metricas, daemon=True).start()

    def _hilo_metricas(self):
        try:
            m = graph_analyzer.calcular_metricas_globales(self.grafo)
            self.after(0, lambda: self._mostrar_metricas(m))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._ana_error(err))
        finally:
            self.after(0, lambda: self.btn_metricas.configure(
                state=tk.NORMAL, text="Metricas globales"))

    def _mostrar_metricas(self, m):
        if "error" in m:
            self._ana_error(m["error"]); return

        self.statusbar.set("Metricas calculadas", "success")
        self._r_clear()

        self._r("  Metricas del Grafo\n", "title")
        self._r("  Red de Transmetro Barranquilla\n\n", "subtitle")
        self._r("  " + "-" * 48 + "\n", "muted")
        self._r("  ESTRUCTURA\n", "section")
        self._r("  " + "-" * 48 + "\n", "muted")

        rows = [
            ("Paradas (nodos)",        f"{m['nodos']:,}"),
            ("Conexiones (aristas)",   f"{m['aristas']:,}"),
            ("Densidad",               str(m['densidad'])),
            ("Coeficiente clustering", str(m['clustering_promedio'])
                                        if m['clustering_promedio'] is not None else "N/D"),
            ("Grado promedio",         str(m['grado_promedio'])),
            ("Grado maximo",           str(m['grado_max'])),
            ("Grado minimo",           str(m['grado_min'])),
            ("Grafo conexo",           "Si" if m['es_conexo'] else "No"),
            ("Componentes conexas",    str(m['num_componentes'])),
        ]
        for label, val in rows:
            self._r(f"\n  {label}\n", "met_label")
            self._r(f"  {val}\n", "met_val")

        self._r("\n  " + "-" * 48 + "\n", "muted")

        self.txt_resultado.configure(state=tk.NORMAL)
        self.txt_resultado.see("1.0")
        self.txt_resultado.configure(state=tk.DISABLED)

    def _calcular_centralidad(self):
        if self.grafo is None:
            messagebox.showwarning("No disponible", "La red aun esta iniciando, espera un momento.")
            return
        self.btn_centralidad.configure(state=tk.DISABLED, text="Calculando...")
        self.btn_metricas.configure(state=tk.DISABLED)
        self.statusbar.set("Calculando centralidades...", "loading")
        self._r_clear()
        self._r("\n\n  Calculando medidas de centralidad...\n", "placeholder")
        threading.Thread(target=self._hilo_centralidad, daemon=True).start()

    def _hilo_centralidad(self):
        try:
            top = graph_analyzer.top_paradas_por_centralidad(self.grafo, n=30)
            self.after(0, lambda: self._mostrar_centralidad(top))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._ana_error(err))
        finally:
            self.after(0, lambda: self.btn_centralidad.configure(
                state=tk.NORMAL, text="Medidas de centralidad"))
            self.after(0, lambda: self.btn_metricas.configure(state=tk.NORMAL))

    @staticmethod
    def _dedup_centralidad(entradas, top_n=10):
        seen   = set()
        result = []
        for sid, nombre, val in entradas:
            if nombre not in seen:
                seen.add(nombre)
                result.append((sid, nombre, val))
                if len(result) >= top_n:
                    break
        return result

    def _mostrar_centralidad(self, top):
        if "error" in top:
            self._ana_error(top["error"]); return

        self.statusbar.set("Centralidades calculadas", "success")
        self._r_clear()

        self._r("  Medidas de Centralidad\n", "title")
        self._r("  Las paradas mas importantes de la red\n\n", "subtitle")

        secciones = [
            ("degree",      "DEGREE CENTRALITY",
             "Paradas con mas conexiones directas"),
            ("betweenness", "BETWEENNESS CENTRALITY",
             "Paradas clave para el flujo de rutas  -  nodos criticos"),
            ("closeness",   "CLOSENESS CENTRALITY",
             "Paradas mas cercanas (en distancia) al resto de la red"),
        ]

        for clave, titulo, desc in secciones:
            entradas_raw   = top.get(clave, [])
            entradas_dedup = self._dedup_centralidad(entradas_raw, top_n=10)

            self._r("  " + "-" * 48 + "\n", "muted")
            self._r(f"  {titulo}\n", "section")
            self._r(f"  {desc}\n\n", "walk")

            for rank, (sid, nombre, val) in enumerate(entradas_dedup, 1):
                tag   = "origin" if rank == 1 else ("met_val" if rank <= 3 else "bus_dir")
                medal = {1: "1.", 2: "2.", 3: "3."}.get(rank, f"   {rank}.")
                self._r(f"  {medal}  {nombre}\n", tag)
                self._r(f"       {val}\n", "met_label")

        self._r("\n  " + "-" * 48 + "\n", "muted")
        self.txt_resultado.configure(state=tk.NORMAL)
        self.txt_resultado.see("1.0")
        self.txt_resultado.configure(state=tk.DISABLED)

    def _ana_error(self, msg):
        self.statusbar.set("Error en el analisis", "error")
        self._r_clear()
        self._r("\n\n  Error en el analisis\n", "title")
        self._r(f"\n  {msg}\n", "walk")

    # ── Autocomplete ─────────────────────────────────────────────────────────

    def _setup_autocomplete(self):
        self._dropdowns = {
            "origen":  _AutocompleteDropdown(self, self.entry_origen,
                on_select=lambda a: self._sel_addr(a, "origen")),
            "destino": _AutocompleteDropdown(self, self.entry_destino,
                on_select=lambda a: self._sel_addr(a, "destino")),
        }
        _SKIP = {"Escape", "Return", "KP_Enter", "Tab",
                 "Left", "Right", "Home", "End", "Prior", "Next", "Up", "Down",
                 "Shift_L", "Shift_R", "Control_L", "Control_R",
                 "Alt_L", "Alt_R", "Caps_Lock", "Num_Lock"}

        for campo, entry in (("origen", self.entry_origen),
                              ("destino", self.entry_destino)):
            def _kr(e, c=campo):
                if e.keysym == "Escape":
                    self._dropdowns[c].hide(); return
                if e.keysym in _SKIP: return
                if self._debounce[c]:
                    self.after_cancel(self._debounce[c])
                q = (self.entry_origen if c == "origen" else self.entry_destino).get().strip()
                if len(q) < 3:
                    self._dropdowns[c].hide(); return
                self._debounce[c] = self.after(480,
                    lambda q=q, c=c: self._fetch_suggestions(q, c))
            entry.bind("<KeyRelease>", _kr)
            entry.bind("<FocusOut>",
                lambda e, c=campo: self.after(250, self._dropdowns[c].hide))

        self.bind("<Configure>", lambda e: [
            d.hide() for d in self._dropdowns.values()] if e.widget is self else None)

    def _fetch_suggestions(self, query, campo):
        def _work():
            suggestions = get_address_suggestions(query)
            self.after(0, lambda s=suggestions, q=query, c=campo:
                self._show_suggestions(s, q, c))
        threading.Thread(target=_work, daemon=True).start()

    def _show_suggestions(self, suggestions, query, campo):
        entry = self.entry_origen if campo == "origen" else self.entry_destino
        if entry.get().strip().lower() != query.lower():
            return
        self._dropdowns[campo].update(suggestions)

    def _sel_addr(self, address, campo):
        entry = self.entry_origen if campo == "origen" else self.entry_destino
        entry.delete(0, tk.END)
        entry.insert(0, address)
        self._dropdowns[campo].hide()
        entry.focus_set()


# ════════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = AppTransmetro()
    app.mainloop()
