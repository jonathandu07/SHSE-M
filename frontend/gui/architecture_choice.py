from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle
from kivy.app import App
from kivy.properties import DictProperty, ListProperty
from kivy.clock import Clock

from gui.components import COLORS, ModernButton
from gui.report_adapter import extract_architecture_candidates

def fmt_value(value, unit="", decimals=1):
    if value is None:
        return "INCONNU"
    try:
        return f"{float(value):.{decimals}f}{unit}"
    except Exception:
        return str(value)

class CandidateCard(BoxLayout):
    def __init__(self, data, on_select, **kwargs):
        super().__init__(orientation="vertical", padding=20, spacing=10, size_hint_y=None, height=320, **kwargs)
        self.data = data
        self.on_select = on_select
        
        with self.canvas.before:
            Color(*COLORS["BF"])
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[15])
        self.bind(pos=self._upd, size=self._upd)
        
        # Header: Architecture + N_cyl
        arch_type = data.get('architecture') or data.get('Architecture', 'INCONNUE')
        n_cyl = data.get('nombre_cylindres') or data.get('N_cyl') or data.get('n_cyl', '?')
        
        header = BoxLayout(size_hint_y=None, height=40)
        arch_lbl = Label(text=f"{arch_type} {n_cyl}", 
                         bold=True, font_size="22sp", color=COLORS["BA"])
        header.add_widget(arch_lbl)
        self.add_widget(header)
        
        # Details
        grid = GridLayout(cols=2, spacing=5)
        def _add_row(k, v):
            grid.add_widget(Label(text=k, color=COLORS["GAXD"], font_size="13sp", halign="left"))
            grid.add_widget(Label(text=v, color=COLORS["white"], font_size="14sp", halign="right"))
            
        _add_row("Score Global", fmt_value(data.get("score_global"), decimals=2))
        
        # Alesage x Course : INCONNU si l'un manque
        b = data.get("alesage_mm") or data.get("bore_mm")
        c = data.get("course_mm") or data.get("stroke_mm")
        
        if b is None or c is None:
            ac_val = "INCONNU"
        else:
            ac_val = f"{float(b):.1f}x{float(c):.1f} mm"
        _add_row("Alesage x Course", ac_val)

        _add_row("Cylindree Unit.", fmt_value(data.get("cylindree_unit_cc"), unit=" cc", decimals=0))
        _add_row("Masse Est.", fmt_value(data.get("masse_relative") or data.get("masse_kg"), unit=" kg*", decimals=1))
        
        self.add_widget(grid)
        
        # Button
        btn = ModernButton(text="CHOISIR CETTE ARCHITECTURE", size_hint_y=None, height=50)
        btn.bind(on_release=lambda x: self.on_select(self.data))
        self.add_widget(btn)

    def _upd(self, *a):
        self.rect.pos = self.pos
        self.rect.size = self.size

class ArchitectureChoiceScreen(Screen):
    candidates = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*COLORS["BL"])
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self._upd_bg, size=self._upd_bg)
        
        root = BoxLayout(orientation="vertical", padding=[60, 40], spacing=20)
        
        # Header
        header = BoxLayout(orientation="vertical", size_hint_y=None, height=100)
        header.add_widget(Label(text="ARCHITECTURES CANDIDATES", font_size="32sp", bold=True, color=COLORS["white"]))
        header.add_widget(Label(text="Sélectionnez l'architecture proposée par le backend.", 
                                color=COLORS["GAXD"]))
        root.add_widget(header)
        
        # ScrollView for grid
        scroll = ScrollView(do_scroll_x=False)
        self.grid = GridLayout(cols=3, spacing=30, size_hint_y=None, padding=[0, 20])
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll.add_widget(self.grid)
        root.add_widget(scroll)
        
        # Footer
        footer = BoxLayout(size_hint_y=None, height=60, spacing=20)
        btn_back = ModernButton(text="ANNULER / RETOUR", size_hint_x=0.2)
        btn_back.bind(on_release=self.go_back)
        footer.add_widget(btn_back)
        
        root.add_widget(footer)
        self.add_widget(root)

    def _upd_bg(self, *a):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def on_enter(self):
        self.update_grid()

    def update_grid(self):
        self.grid.clear_widgets()
        app = App.get_running_app()
        report = getattr(app, 'raw_backend_report', {})
        
        exploration = extract_architecture_candidates(report)
            
        if not exploration:
            self.grid.add_widget(Label(text="Données indisponibles — le backend n'a pas fourni de candidats d'architecture.",
                                       color=COLORS["RF"], halign="center"))
            return

        for cand in exploration:
            card = CandidateCard(data=cand, on_select=self.select_candidate)
            self.grid.add_widget(card)

    def select_candidate(self, cand):
        app = App.get_running_app()
        
        # Strict payload rules: only send present fields
        payload = {}
        
        # Architecture type
        arch = cand.get('architecture') or cand.get('Architecture')
        if arch is not None:
            payload["architecture"] = arch
            
        # Number of cylinders
        n_cyl = cand.get('nombre_cylindres') or cand.get('N_cyl')
        if n_cyl is not None:
            payload["nombre_cylindres"] = n_cyl
            
        # Dimensions (only if present)
        b = cand.get('alesage_mm') or cand.get('bore_mm')
        if b is not None:
            payload["alesage_mm"] = b
            
        c = cand.get('course_mm') or cand.get('stroke_mm')
        if c is not None:
            payload["course_mm"] = c
            
        # Update app state and reload
        app.engine_params.update(payload)
        self.manager.current = "loading"

    def go_back(self, *args):
        self.manager.current = "config"
