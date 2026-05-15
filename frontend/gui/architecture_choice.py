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
        header = BoxLayout(size_hint_y=None, height=40)
        arch_lbl = Label(text=f"{data.get('architecture')} {data.get('N_cyl')}", 
                         bold=True, font_size="22sp", color=COLORS["BA"])
        header.add_widget(arch_lbl)
        self.add_widget(header)
        
        # Details
        grid = GridLayout(cols=2, spacing=5)
        def _add_row(k, v):
            grid.add_widget(Label(text=k, color=COLORS["GAXD"], font_size="13sp", halign="left"))
            grid.add_widget(Label(text=v, color=COLORS["white"], font_size="14sp", halign="right"))
            
        _add_row("Score Global", f"{data.get('score_global', 0):.2f}")
        _add_row("Alesage x Course", f"{data.get('bore_mm', 0):.1f}x{data.get('course_mm', 0):.1f} mm")
        _add_row("Cylindree Unit.", f"{data.get('cylindree_unit_cc', 0):.0f} cc")
        _add_row("Masse Est.", f"{data.get('masse_relative', 0):.1f} kg*")
        _add_row("Cout Maint.", f"{data.get('cout_maintenance_eur', 0):.0f} €*")
        
        self.add_widget(grid)
        
        # Disclaimer
        self.add_widget(Label(text="*Valeurs relatives/estimees", font_size="10sp", color=COLORS["GAXD"], size_hint_y=None, height=15))
        
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
        header.add_widget(Label(text="Selectionne l'architecture moteur proposee par le backend pour ton besoin de puissance.", 
                                color=COLORS["GAXD"]))
        root.add_widget(header)
        
        # ScrollView for grid
        scroll = ScrollView(do_scroll_x=False)
        self.grid = GridLayout(cols=3, spacing=30, size_hint_y=None, padding=[0, 20])
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll.add_widget(self.grid)
        root.add_widget(scroll)
        
        # Footer / Manual override
        footer = BoxLayout(size_hint_y=None, height=60, spacing=20)
        btn_manual = ModernButton(text="AFFINER LES PARAMETRES (MODE EXPERT)", size_hint_x=0.4)
        btn_manual.bind(on_release=self.go_manual)
        footer.add_widget(btn_manual)
        
        btn_back = ModernButton(text="RETOUR", size_hint_x=0.2)
        btn_back.bind(on_release=self.go_back)
        footer.add_widget(btn_back)
        
        root.add_widget(footer)
        self.add_widget(root)

    def _upd_bg(self, *a):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def on_pre_enter(self):
        self.update_grid()

    def update_grid(self):
        self.grid.clear_widgets()
        app = App.get_running_app()
        report = app.simulation_results
        
        # On cherche l'exploration dans le rapport
        exploration = []
        try:
            # Structure type SystemeComplet
            exploration = report.get("sous_systemes", {}).get("architecture", {}).get("exploration", [])
        except:
            pass
            
        if not exploration:
            self.grid.add_widget(Label(text="Aucune architecture candidate trouvee.\nLe backend n'a pas pu converger avec ces parametres.",
                                       color=COLORS["RF"], halign="center"))
            return

        for cand in exploration:
            card = CandidateCard(data=cand, on_select=self.select_candidate)
            self.grid.add_widget(card)

    def select_candidate(self, cand):
        app = App.get_running_app()
        # On injecte le choix dans engine_params pour le prochain calcul complet
        app.engine_params.update({
            "architecture": cand.get("architecture"),
            "nombre_cylindres": cand.get("N_cyl"),
            "alesage_mm": cand.get("bore_mm"),
            "course_mm": cand.get("course_mm"),
        })
        # On peut maintenant lancer le dimensionnement complet ou aller au dashboard
        # Le dashboard affichera les inconnues restantes si on n'a pas tout choisi
        self.manager.current = "loading"

    def go_manual(self, *args):
        # Pour l'instant, on n'a pas d'écran manuel "expert" compatible 
        # (on a supprimé l'ancien QuickConfig), on pourrait en recréer un
        # ou simplement rester sur ce flux guidé.
        pass

    def go_back(self, *args):
        self.manager.current = "config"
