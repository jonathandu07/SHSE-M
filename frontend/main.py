# frontend/main.py
# =========================================================
# SHSE-M - Interface Technique Haute Fidelite (Kivy)
# Doctrine : Zero-Invention & Reporting Passif
# =========================================================

import os
import sys
import io
import threading
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

# CONFIGURATION DU PATH
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

KIVY_HOME = os.path.join(BASE_DIR, ".kivy")
os.makedirs(KIVY_HOME, exist_ok=True)
os.environ.setdefault("KIVY_HOME", KIVY_HOME)

from kivy.config import Config
Config.set("input", "mouse", "mouse,disable_multitouch")
Config.set("graphics", "resizable", "1")

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.image import Image as KivyImage
from kivy.uix.widget import Widget
from kivy.uix.spinner import Spinner
from kivy.properties import StringProperty, DictProperty
from kivy.graphics import Color, RoundedRectangle
from kivy.core.window import Window
from kivy.clock import Clock

# Imports locaux - UNIQUEMENT DEPUIS LES MODULES NEUTRES
from gui.components import COLORS, ModernButton, PremiumCard, TechRow, NeumorphicInput
from frontend.gui.viz_utils import get_viz_figure
from frontend.gui.piece_connector import get_piece_instance
from frontend.gui.pdf_export import build_element_display_sections, export_element_pdf
from frontend.gui.energy_audit import EnergyAuditScreen
from gui.architecture_choice import ArchitectureChoiceScreen
from gui.report_adapter import adapt_backend_report
from gui.raw_report_view import RawReportViewScreen
from gui.pieces_view import PieceLibraryScreen, PieceDetailScreen

# Backend connection (strict)
try:
    from backend.main import dimensionner_systeme_shsem
except ImportError:
    dimensionner_systeme_shsem = None

def fmt_val(v, unit=""):
    if v is None:
        return "INCONNU"
    if isinstance(v, float):
        return f"{v:.2f} {unit}".strip()
    return f"{v} {unit}".strip()

PROJECT_NAME = "STHOME"
PROJECT_SUBTITLE = "Dimensionnement thermo-hybride de sortie"
PROJECT_LOGO = os.path.join(BASE_DIR, "frontend", "images", "logo.png")

# =========================
# Utilitaires de Données
# =========================
def show_popup(title: str, message: str) -> None:
    content = BoxLayout(orientation="vertical", padding=20, spacing=15)
    msg = Label(text=message, color=COLORS["BF"], halign="left", valign="top")
    msg.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
    content.add_widget(msg)
    btn = Button(text="OK", size_hint_y=None, height=44)
    content.add_widget(btn)
    pop = Popup(title=title, content=content, size_hint=(None, None), size=(400, 250),
                background="", background_color=COLORS["white"], separator_color=COLORS["BA"],
                title_color=COLORS["BF"])
    btn.bind(on_press=pop.dismiss)
    pop.open()

def _safe_dict(v): return v if isinstance(v, dict) else {}
def _safe_list(v): return v if isinstance(v, list) else []
def _report_resume(report): return _safe_dict(_safe_dict(report).get("resume_gui")) or _safe_dict(report)

def _build_brand_header(height: int = 104, title_size: str = "40sp", subtitle_size: str = "18sp"):
    outer = BoxLayout(orientation="horizontal", size_hint_y=None, height=height)
    outer.add_widget(Widget(size_hint_x=0.18))
    brand = BoxLayout(orientation="horizontal", spacing=18, size_hint=(None, None), height=height, width=560)
    if os.path.exists(PROJECT_LOGO):
        brand.add_widget(KivyImage(source=PROJECT_LOGO, size_hint=(None, None), 
                                   size=(height - 18, height - 18), allow_stretch=True, keep_ratio=True))
    txt = BoxLayout(orientation="vertical", size_hint=(1, None), height=height, padding=[0, 8, 0, 8], spacing=2)
    title = Label(text=PROJECT_NAME, font_size=title_size, bold=True, color=COLORS["BF"], size_hint_y=None, height=max(42, height-42), halign="left", valign="middle")
    title.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
    txt.add_widget(title)
    sub = Label(text=PROJECT_SUBTITLE, font_size=subtitle_size, color=COLORS["BA"], size_hint_y=None, height=24, halign="left", valign="middle")
    sub.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
    txt.add_widget(sub)
    brand.add_widget(txt)
    outer.add_widget(brand)
    outer.add_widget(Widget(size_hint_x=0.18))
    return outer

# Matplotlib Bridge
MATPLOTLIB_AVAILABLE = False
try:
    import matplotlib.pyplot as plt
    class FigureCanvasKivyAgg(KivyImage):
        def __init__(self, figure, **kwargs):
            super().__init__(**kwargs)
            self.figure = figure
            self.allow_stretch, self.keep_ratio = True, True
            self.update_canvas()
            try: plt.close(self.figure)
            except: pass
        def update_canvas(self, *args):
            buf = io.BytesIO()
            self.figure.savefig(buf, format="png", bbox_inches="tight", dpi=130)
            buf.seek(0)
            from kivy.core.image import Image as CoreImage
            im = CoreImage(buf, ext="png")
            self.texture = im.texture
            try: buf.close()
            except: pass
    MATPLOTLIB_AVAILABLE = True
except Exception as e:
    print(f"[INFO] Matplotlib non disponible : {e}")

# =========================
# Ecrans Principaux
# =========================

class AutoConfigScreen(Screen):
    """
    Page d'accueil minimalist.
    Entree : Puissance + Unite.
    Doctrine : Zero-Invention. Aucun defaut silencieux.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*COLORS["BL"])
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        root = ScrollView(do_scroll_x=False)
        page = BoxLayout(orientation="vertical", padding=[80, 60], spacing=30, size_hint_y=None)
        page.bind(minimum_height=page.setter("height"))
        page.add_widget(_build_brand_header(height=120, title_size="42sp", subtitle_size="18sp"))

        input_card = PremiumCard(title="Definition du Besoin", size_hint_y=None, height=420)
        input_card.padding = [40, 30]
        
        info = Label(text="Saisis ton besoin de puissance pour lancer la chaine de calcul.", 
                     color=COLORS["GAXD"], font_size="16sp", size_hint_y=None, height=40, halign="left")
        info.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        input_card.add_widget(info)

        form = GridLayout(cols=2, spacing=40, size_hint_y=None, height=180, padding=[0, 20])
        
        # Colonne Puissance
        val_col = BoxLayout(orientation="vertical", spacing=10)
        val_col.add_widget(Label(text="Puissance", color=COLORS["white"], bold=True, font_size="16sp", halign="left"))
        self.power_input = NeumorphicInput(text="")
        self.power_input.hint_text = "ex: 150"
        val_col.add_widget(self.power_input)
        form.add_widget(val_col)

        # Colonne Unite (SANS VALEUR PAR DEFAUT)
        unit_col = BoxLayout(orientation="vertical", spacing=10)
        unit_col.add_widget(Label(text="Unite", color=COLORS["white"], bold=True, font_size="16sp", halign="left"))
        self.unit_spinner = Spinner(
            text="Choisir l'unite...", 
            values=("kW", "chevaux (ch)"), 
            size_hint_y=None, height=76,
            background_color=(0.15, 0.17, 0.22, 1),
            color=COLORS["white"]
        )
        unit_col.add_widget(self.unit_spinner)
        form.add_widget(unit_col)
        input_card.add_widget(form)

        self.err = Label(text="", color=COLORS["RF"], font_size="14sp", size_hint_y=None, height=30)
        input_card.add_widget(self.err)
        
        self.gen_btn = ModernButton(text="LANCER LE CALCUL", size_hint_y=None, height=80)
        self.gen_btn.bind(on_press=self.launch_generation)
        input_card.add_widget(self.gen_btn)
        
        page.add_widget(input_card)
        root.add_widget(page)
        self.add_widget(root)

    def on_enter(self, *args):
        self.err.text = ""
        Clock.schedule_once(lambda dt: setattr(self.power_input, "focus", True), 0.1)

    def _update_bg(self, *args): self.bg_rect.pos, self.bg_rect.size = self.pos, self.size

    def launch_generation(self, *_):
        txt_raw = (self.power_input.text or "").strip().replace(",", ".")
        
        try:
            if not txt_raw: raise ValueError("Veuillez saisir une puissance.")
            val = float(txt_raw)
            if val <= 0: raise ValueError("La puissance doit être positive.")
        except Exception as e:
            self.err.text = str(e)
            return

        unit_text = self.unit_spinner.text
        if unit_text == "Choisir l'unite...":
            self.err.text = "Veuillez choisir explicitement l'unite."
            return
            
        unite = "kw" if "kW" in unit_text else "ch"
        
        app = App.get_running_app()
        app.target_power = str(val)
        app.target_unit = unite
        app.engine_params = {
            "puissance_entree": val,
            "unite_entree": unite
        }
        self.manager.current = "loading"


class AutoLoadingScreen(Screen):
    """
    Flux de calcul backend.
    Routage : loading -> arch_choice (si exploration dispo) -> dashboard.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=100, spacing=20)
        self.label = Label(text="Calcul systeme en cours...", font_size="24sp", color=COLORS["BA"])
        self.sub_label = Label(text="", font_size="14sp", color=COLORS["GAXD"])
        layout.add_widget(self.label)
        layout.add_widget(self.sub_label)
        self.add_widget(layout)

    def on_enter(self): 
        self.sub_label.text = "Communication avec le noyau physique..."
        Clock.schedule_once(self.run_sim, 0.2)

    def run_sim(self, dt): threading.Thread(target=self.do_math, daemon=True).start()

    def do_math(self):
        """Calls the backend dimensioning engine without local inventions."""
        app = App.get_running_app()
        params = app.engine_params

        if not dimensionner_systeme_shsem:
            self.on_error("Backend indisponible (main.py non trouvé)")
            return

        try:
            # Backend call with strict parameters
            report = dimensionner_systeme_shsem(**params)
            
            if not report or "erreur" in report:
                self.on_error(report.get("erreur", "Rapport vide"))
                return

            # Storage: Raw first, then Adapt
            app.raw_backend_report = report
            app.ui_report = adapt_backend_report(report)
            
            # Routage vers choix d'architecture si non fige
            exploration = report.get("systeme_complet", {}).get("synthese", {}).get("architectures_candidates", [])
            if not params.get("architecture") and exploration:
                target_screen = "arch_choice"
            else:
                target_screen = "dashboard"
                
            Clock.schedule_once(lambda dt: setattr(self.manager, "current", target_screen))
            
        except Exception as e:
            self.on_error(str(e), traceback.format_exc())

    def on_error(self, msg, trace=""):
        def switch_to_error(dt):
            err_screen = self.manager.get_screen('backend_error')
            err_screen.set_error(msg, trace)
            self.manager.current = 'backend_error'
        Clock.schedule_once(switch_to_error)


class AutoDashboardScreen(Screen):
    """The Bento-style dashboard: formal reporting source."""
    
    def on_enter(self):
        self.refresh()

    def refresh(self):
        self.clear_widgets()
        app = App.get_running_app()
        ui = app.ui_report
        
        # Main Container
        root = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # 1. TOP BAR
        top_bar = BoxLayout(size_hint_y=None, height=60, spacing=10)
        top_bar.add_widget(Label(text="[b]DASHBOARD TECHNIQUE SHSE-M[/b]", markup=True, font_size='20sp', size_hint_x=0.7))
        
        btn_config = Button(text="Nouvelle Étude", size_hint_x=0.15)
        btn_config.bind(on_release=lambda x: setattr(self.manager, 'current', 'config'))
        top_bar.add_widget(btn_config)
        
        btn_raw = Button(text="JSON Brut", size_hint_x=0.15, background_color=(0.3, 0.3, 0.5, 1))
        btn_raw.bind(on_release=lambda x: setattr(self.manager, 'current', 'raw_report'))
        top_bar.add_widget(btn_raw)
        
        root.add_widget(top_bar)
        
        if not ui or ui.get("is_empty", True):
            root.add_widget(Label(text="Aucune donnée à afficher. Veuillez lancer une configuration."))
            self.add_widget(root)
            return

        # 2. BENTO GRID
        grid = GridLayout(cols=2, spacing=10, size_hint_y=0.8)
        
        # Section A: Résumé
        sec_a = self.create_bento_box("A: RÉSUMÉ GLOBAL", ui["sections"].get("resume", {"items": []}))
        grid.add_widget(sec_a)
        
        # Section B: Chaîne Énergétique
        sec_b = self.create_bento_box("B: CHAÎNE ÉNERGÉTIQUE", ui["sections"].get("energie", {"items": []}))
        grid.add_widget(sec_b)
        
        # Section C: Sous-systèmes
        sec_c = self.create_bento_box("C: SOUS-SYSTÈMES", ui["sections"].get("sous_systemes", {"items": []}))
        grid.add_widget(sec_c)
        
        # Section D: Inconnues & Alertes
        sec_d = self.create_alert_box(ui.get("unknowns", []), ui.get("alerts", []))
        grid.add_widget(sec_d)
        
        root.add_widget(grid)
        
        # 3. ACTION BAR
        actions = BoxLayout(size_hint_y=None, height=70, spacing=15, padding=[0, 10, 0, 0])
        
        btn_arch = Button(text="CANDIDATS ARCHITECTURE", background_color=(0.2, 0.5, 0.2, 1))
        btn_arch.bind(on_release=lambda x: setattr(self.manager, 'current', 'arch_choice'))
        actions.add_widget(btn_arch)
        
        btn_audit = Button(text="AUDIT ÉNERGÉTIQUE", background_color=(0.2, 0.4, 0.6, 1))
        btn_audit.bind(on_release=lambda x: setattr(self.manager, 'current', 'energy_audit'))
        actions.add_widget(btn_audit)
        
        btn_pieces = Button(text="BIBLIOTHÈQUE PIÈCES", background_color=(0.4, 0.3, 0.5, 1))
        btn_pieces.bind(on_release=lambda x: setattr(self.manager, 'current', 'piece_library'))
        actions.add_widget(btn_pieces)
        
        btn_export = Button(text="EXPORTS / PDF", background_color=(0.6, 0.4, 0.2, 1))
        btn_export.bind(on_release=lambda x: setattr(self.manager, 'current', 'pdf_folder'))
        actions.add_widget(btn_export)
        
        root.add_widget(actions)
        self.add_widget(root)

    def create_bento_box(self, title, section):
        box = BoxLayout(orientation='vertical', padding=10)
        box.add_widget(Label(text=f"[b]{title}[/b]", markup=True, size_hint_y=None, height=30, halign='left'))
        
        content = GridLayout(cols=2, spacing=5)
        for item in section.get("items", []):
            label = Label(text=item["label"], halign='left', size_hint_x=0.6, color=(0.7, 0.7, 0.7, 1))
            val_text = fmt_val(item["value"], item["unit"])
            val = Label(text=val_text, halign='right', size_hint_x=0.4)
            if item.get("status") == "inconnu":
                val.color = (1, 0.5, 0.5, 1)
            content.add_widget(label)
            content.add_widget(val)
            
        box.add_widget(content)
        return box

    def create_alert_box(self, unknowns, alerts):
        box = BoxLayout(orientation='vertical', padding=10)
        box.add_widget(Label(text="[b]D: INCONNUES & ALERTES[/b]", markup=True, size_hint_y=None, height=30, color=(1, 0.8, 0.2, 1)))
        
        scroll = ScrollView()
        list_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=2)
        list_layout.bind(minimum_height=list_layout.setter('height'))
        
        for u in unknowns:
            txt = f"[color=ff8888]• {u['name']}[/color] : {u['reason']}"
            lbl = Label(text=txt, markup=True, size_hint_y=None, height=25, halign='left', font_size='11sp')
            list_layout.add_widget(lbl)
            
        for a in alerts:
            txt = f"[color=ffff88]! {a['name']}[/color] : {a['detail']}"
            lbl = Label(text=txt, markup=True, size_hint_y=None, height=25, halign='left', font_size='11sp')
            list_layout.add_widget(lbl)
            
        if not unknowns and not alerts:
            list_layout.add_widget(Label(text="Aucune alerte ou inconnue.", color=(0.5, 0.8, 0.5, 1)))
            
        scroll.add_widget(list_layout)
        box.add_widget(scroll)
        return box


# =========================
# Ecrans de Reporting Specifiques
# =========================

class AdvancedVisualsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical", padding=20, spacing=15)
        top = BoxLayout(size_hint_y=None, height=60, spacing=10)
        top.add_widget(Label(text="VISUALISATION TECHNIQUE", font_size="20sp", bold=True, color=COLORS["BA"]))
        back = ModernButton(text="RETOUR", size_hint_x=None, width=140)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "dashboard"))
        top.add_widget(back)
        self.layout.add_widget(top)
        self.display = PremiumCard(title="Rendu 3D / Sketches")
        self.layout.add_widget(self.display)
        self.add_widget(self.layout)

    def on_enter(self, *args):
        self.display.clear_widgets()
        app = App.get_running_app()
        report = _safe_dict(app.simulation_results)
        # On ne genere que si les donnees existent
        if "__error__" in report or not report.get("sous_systemes"):
            self.display.add_widget(Label(text="Visualisation indisponible - Donnees techniques insuffisantes.", color=COLORS["RF"]))
            return
        self.display.add_widget(Label(text="Rendu des croquis backend en cours...", color=COLORS["GAXD"]))

class PdfFolderScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical", padding=20, spacing=15)
        top = BoxLayout(size_hint_y=None, height=60, spacing=10)
        top.add_widget(Label(text="EXPORTATIONS PDF", font_size="20sp", bold=True, color=COLORS["BA"]))
        back = ModernButton(text="RETOUR", size_hint_x=None, width=140)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "dashboard"))
        top.add_widget(back)
        self.layout.add_widget(top)
        self.content = PremiumCard(title="Fiches techniques")
        self.layout.add_widget(self.content)
        self.add_widget(self.layout)

    def on_enter(self, *args):
        self.content.clear_widgets()
        app = App.get_running_app()
        if not app.simulation_results or "__error__" in app.simulation_results:
            self.content.add_widget(Label(text="Export indisponible - Calcul non converge.", color=COLORS["RF"]))
            return
        self.content.add_widget(Label(text="Generation des fiches PDF basees sur le rapport backend.", color=COLORS["GAXD"]))

class BackendErrorScreen(Screen):
    """Clean error display when backend fails."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=40, spacing=20)
        self.layout.add_widget(Label(text="[b]ERREUR BACKEND[/b]", markup=True, font_size='24sp', color=(1, 0.3, 0.3, 1)))
        
        self.error_label = Label(text="Une erreur inattendue est survenue.", halign='center', valign='middle')
        self.layout.add_widget(self.error_label)
        
        self.trace_input = TextInput(readonly=True, background_color=(0.1, 0.1, 0.1, 1), foreground_color=(1, 0.5, 0.5, 1))
        self.layout.add_widget(self.trace_input)
        
        btn = Button(text="Retour à la configuration", size_hint_y=None, height=50)
        btn.bind(on_release=self.go_back)
        self.layout.add_widget(btn)
        
        self.add_widget(self.layout)

    def set_error(self, msg, trace=""):
        self.error_label.text = f"Message : {msg}"
        self.trace_input.text = trace

    def go_back(self, instance):
        self.manager.current = 'config'

class PieceLibraryScreen(Screen): pass
class PieceDetailScreen(Screen): pass
class VectorViewScreen(Screen): pass
class DetailedDatasheetScreen(Screen): pass

# =========================
# Application
# =========================
class SHSEMApp(App):
    title = PROJECT_NAME
    target_power = StringProperty("150")
    target_unit = StringProperty("kw")
    
    # New strict reporting storage
    raw_backend_report = DictProperty({})
    ui_report = DictProperty({})
    
    engine_params = DictProperty({})
    current_report_name = StringProperty("")
    selected_piece = DictProperty({}) # For detail view

    def build(self):
        Window.clearcolor = COLORS["BL"]
        Window.size = (1280, 860)
        sm = ScreenManager(transition=FadeTransition())
        
        # Core Screens
        sm.add_widget(AutoConfigScreen(name="config"))
        sm.add_widget(AutoLoadingScreen(name="loading"))
        sm.add_widget(AutoDashboardScreen(name="dashboard"))
        
        # Feature Screens
        sm.add_widget(RawReportViewScreen(name="raw_report"))
        sm.add_widget(PieceLibraryScreen(name="piece_library"))
        sm.add_widget(PieceDetailScreen(name="piece_detail"))
        sm.add_widget(BackendErrorScreen(name="backend_error"))
        
        # Legacy/Other Screens
        sm.add_widget(PdfFolderScreen(name="pdf_folder"))
        sm.add_widget(AdvancedVisualsScreen(name="advanced_visuals"))
        sm.add_widget(EnergyAuditScreen(name="energy_audit"))
        sm.add_widget(ArchitectureChoiceScreen(name="arch_choice"))
        
        return sm

if __name__ == "__main__":
    SHSEMApp().run()
