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

# Imports locaux
from gui.components import COLORS, ModernButton, PremiumCard, TechRow, NeumorphicInput
from frontend.gui.viz_utils import get_viz_figure
from frontend.gui.piece_connector import get_piece_instance
from frontend.gui.pdf_export import build_element_display_sections, export_element_pdf
from frontend.gui.energy_audit import EnergyAuditScreen
from gui.architecture_choice import ArchitectureChoiceScreen

PROJECT_NAME = "STHOME"
PROJECT_SUBTITLE = "Dimensionnement thermo-hybride de sortie"
PROJECT_LOGO = os.path.join(BASE_DIR, "frontend", "images", "logo.png")

# =========================
# Utilitaires
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
# Composants Partages
# =========================
class ArchButton(Button):
    def __init__(self, arch_name, **kwargs):
        super().__init__(text=arch_name, **kwargs)
        self.arch_name = arch_name
        self.background_normal, self.background_down, self.background_color = "", "", (0,0,0,0)
        self.bold, self.selected = True, False
        with self.canvas.before:
            self.bg_color_inst = Color(*COLORS["GF"])
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self.bind(pos=self._upd, size=self._upd)
    def _upd(self, *a): self.rect.pos, self.rect.size = self.pos, self.size
    def set_selected(self, sel: bool):
        self.selected = sel
        self.bg_color_inst.rgba = COLORS["BF"] if sel else COLORS["GF"]
        self.color = COLORS["white"] if sel else COLORS["BF"]

# =========================
# Ecrans Principaux
# =========================

class AutoConfigScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*COLORS["BL"])
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self._update_bg, size=self._update_bg)

        root = ScrollView(do_scroll_x=False)
        page = BoxLayout(orientation="vertical", padding=[80, 60], spacing=30, size_hint_y=None)
        page.bind(minimum_height=page.setter("height"))
        page.add_widget(_build_brand_header(height=120, title_size="42sp", subtitle_size="18sp"))

        input_card = PremiumCard(title="Dimensionnement de la chaine complete", size_hint_y=None, height=420)
        input_card.padding = [40, 30]
        
        info = Label(text="Saisis ton besoin de puissance.", color=COLORS["GAXD"], font_size="16sp", size_hint_y=None, height=40, halign="left")
        info.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        input_card.add_widget(info)

        form = GridLayout(cols=2, spacing=40, size_hint_y=None, height=180, padding=[0, 20])
        val_col = BoxLayout(orientation="vertical", spacing=10)
        val_col.add_widget(Label(text="Puissance", color=COLORS["BF"], bold=True, font_size="16sp", halign="left"))
        self.power_input = NeumorphicInput(text="")
        self.power_input.height = 60
        val_col.add_widget(self.power_input)
        form.add_widget(val_col)

        unit_col = BoxLayout(orientation="vertical", spacing=10)
        unit_col.add_widget(Label(text="Unite", color=COLORS["BF"], bold=True, font_size="16sp", halign="left"))
        self.unit_spinner = Spinner(text="Choisir l'unite...", values=("kW", "chevaux (ch)"), size_hint_y=None, height=60)
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
        Clock.schedule_once(lambda dt: setattr(self.power_input, "focus", True), 0)
    def _update_bg(self, *args): self.bg_rect.pos, self.bg_rect.size = self.pos, self.size

    def launch_generation(self, *_):
        txt_raw = (self.power_input.text or "").strip().replace(",", ".")
        try:
            if not txt_raw: raise ValueError("Puissance manquante")
            val = float(txt_raw)
            if val <= 0: raise ValueError("P > 0 requis")
        except Exception as e:
            self.err.text = f"Erreur : {e}"
            return

        unit_text = self.unit_spinner.text
        if unit_text == "Choisir l'unite...":
            self.err.text = "Erreur : Choisir une unite."
            return
        unite = "kw" if "kW" in unit_text else "ch"
        
        app = App.get_running_app()
        app.target_power = str(val)
        app.engine_params = {
            "architectures_autorisees": ["L", "V", "W", "Etoile", "Boxer"],
            "temps_moteur": 4,
            "mode_carburant": "multi_carburant",
            "carburants_autorises": ["diesel", "essence", "ethanol", "methanol", "gpl", "gnv", "hydrogene"],
            "puissance_entree": val,
            "unite_entree": unite
        }
        self.manager.current = "loading"


class AutoLoadingScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=100, spacing=20)
        self.label = Label(text="Séquençage des calculs physiques...", font_size="24sp", color=COLORS["BF"])
        self.sub_label = Label(text="", font_size="14sp", color=COLORS["BA"])
        layout.add_widget(self.label)
        layout.add_widget(self.sub_label)
        self.add_widget(layout)

    def on_enter(self): Clock.schedule_once(self.run_sim, 0.15)
    def run_sim(self, dt): threading.Thread(target=self.do_math, daemon=True).start()

    def do_math(self):
        app = App.get_running_app()
        ep = app.engine_params or {}
        p_target = float(app.target_power)
        Clock.schedule_once(lambda dt: setattr(self.label, "text", "Calcul de la chaine energetique..."))
        
        try:
            from backend.main import dimensionner_systeme_shsem
            from backend.modules.systeme.database import SecureDatabase
            db = SecureDatabase(db_path=os.path.join(BASE_DIR, "backend", "shse_technical_data.db"),
                                key_path=os.path.join(BASE_DIR, "backend", "secret.key"))
            report_name = f"gui_{str(p_target).replace('.', 'p')}kw"
            
            report = dimensionner_systeme_shsem(
                puissance_traction_kw=p_target, charger_batterie=True,
                vitesse_moteur_thermique_rpm=ep.get("rpm_nominal"),
                pme_pa=ep.get("pme_pa"), pression_max_pa=ep.get("pression_max_pa"),
                rendement_mecanique_cible_min=ep.get("rendement_mecanique_cible_min"),
                carburants_autorises=ep.get("carburants_autorises"),
                mode_carburant=ep.get("mode_carburant"),
                architectures_autorisees=ep.get("architectures_autorisees"),
                moteur_thermique_definition=ep
            )
            
            db.save_main_report(report, report_name=report_name)
            res = db.load_main_report(report_name) or {}
            app.simulation_results = res
            app.current_report_name = report_name

            exploration = res.get("sous_systemes", {}).get("architecture", {}).get("exploration", [])
            target_screen = "arch_choice" if not ep.get("architecture") and exploration else "energy_audit"

        except Exception:
            app.simulation_results = {"__error__": traceback.format_exc()}
            target_screen = "energy_audit"

        Clock.schedule_once(lambda dt: setattr(self.manager, "current", target_screen))


class AutoDashboardScreen(Screen):
    res_pwr = StringProperty("-- kW")
    res_mass = StringProperty("-- kg")
    res_vol = StringProperty("-- m³")
    res_ncyl = StringProperty("--")
    res_arch = StringProperty("--")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=20, spacing=20)
        
        top = BoxLayout(size_hint_y=None, height=60, spacing=20)
        brand = BoxLayout(size_hint_x=0.24, spacing=10)
        if os.path.exists(PROJECT_LOGO):
            brand.add_widget(KivyImage(source=PROJECT_LOGO, size_hint=(None, None), size=(46, 46)))
        brand_txt = BoxLayout(orientation="vertical")
        brand_txt.add_widget(Label(text=PROJECT_NAME, font_size="20sp", bold=True, color=COLORS["BF"]))
        brand_txt.add_widget(Label(text=PROJECT_SUBTITLE, font_size="11sp", color=COLORS["BA"]))
        brand.add_widget(brand_txt)
        top.add_widget(brand)
        
        top.add_widget(Label(text="RESULTATS DE GENERATION", font_size="22sp", bold=True, color=COLORS["BF"], size_hint_x=0.4))
        
        btn_recalc = ModernButton(text="AJUSTER", size_hint_x=0.15)
        btn_recalc.bind(on_press=self.open_adjust_popup)
        top.add_widget(btn_recalc)
        
        back = Button(text="ACCUEIL", size_hint_x=0.15, background_color=(0,0,0,0), color=COLORS["GAXD"])
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "config"))
        top.add_widget(back)
        layout.add_widget(top)

        grid = GridLayout(cols=3, rows=2, spacing=20, size_hint_y=0.68)
        c1 = PremiumCard(title="Puissance"); c1.add_widget(Label(text=self.res_pwr, font_size="30sp", bold=True, color=COLORS["BF"])); grid.add_widget(c1)
        c2 = PremiumCard(title="Cylindree"); c2.add_widget(Label(text=self.res_vol, font_size="26sp", bold=True, color=COLORS["BF"])); grid.add_widget(c2)
        c3 = PremiumCard(title="Architecture"); c3.add_widget(Label(text=self.res_arch, font_size="26sp", bold=True, color=COLORS["BF"])); grid.add_widget(c3)
        
        c4 = PremiumCard(title="Acces Rapide")
        bg = GridLayout(cols=2, spacing=10)
        for txt, screen in [("PIÈCES", "piece_library"), ("AUDIT", "energy_audit"), ("VISU", "advanced_visuals"), ("PDF", "pdf_folder")]:
            b = ModernButton(text=txt, font_size="13sp")
            b.bind(on_press=lambda _, s=screen: setattr(self.manager, "current", s))
            bg.add_widget(b)
        c4.add_widget(bg); grid.add_widget(c4)
        
        c5 = PremiumCard(title="Statut Calcul"); self.status_lbl = Label(text="OK", font_size="28sp", bold=True, color=(30/255, 180/255, 50/255, 1)); c5.add_widget(self.status_lbl); grid.add_widget(c5)
        layout.add_widget(grid)
        
        self.dt_card = PremiumCard(title="CHAINE DE TRACTION", size_hint_y=0.3)
        self.dt_grid = GridLayout(cols=3, spacing=15, padding=10); self.dt_card.add_widget(self.dt_grid)
        layout.add_widget(self.dt_card)
        self.add_widget(layout)

    def on_enter(self, *args):
        app = App.get_running_app()
        report = _safe_dict(app.simulation_results)
        res = _report_resume(report)
        self.res_pwr = f"{float(app.target_power):.1f} kW"
        self.res_arch = str(res.get("Architecture") or "A definir")
        vd = res.get("vd_tot_cc")
        self.res_vol = f"{vd/1000:.2f} L" if vd else "-- L"
        self.status_lbl.text = "ERREUR" if "__error__" in report else "OK"

    def open_adjust_popup(self, *_):
        app = App.get_running_app()
        ep = app.engine_params or {}
        content = BoxLayout(orientation="vertical", padding=20, spacing=12)
        fields = {}
        for lbl, key, d in [("Alesage (mm)", "alesage_mm", ep.get("alesage_mm", 130)), ("Course (mm)", "course_mm", ep.get("course_mm", 150)), ("RPM", "rpm_nominal", ep.get("rpm_nominal", 1500))]:
            row = BoxLayout(size_hint_y=None, height=48, spacing=10)
            row.add_widget(Label(text=lbl, color=COLORS["BF"], size_hint_x=0.4))
            inp = TextInput(text=str(d), multiline=False, size_hint_x=0.6)
            fields[key] = inp; row.add_widget(inp); content.add_widget(row)
        
        def do_recalc(*_):
            new_ep = dict(ep)
            for k, i in fields.items():
                try: 
                    v = float(i.text.replace(",","."))
                    new_ep[k] = v
                    if k=="alesage_mm": new_ep["alesage_m"] = v/1000.0
                    if k=="course_mm": new_ep["course_m"] = v/1000.0
                except: pass
            app.engine_params = new_ep
            popup.dismiss()
            self.manager.current = "loading"
            
        btn = ModernButton(text="RECALCULER", size_hint_y=None, height=52); btn.bind(on_press=do_recalc); content.add_widget(btn)
        popup = Popup(title="Ajuster", content=content, size_hint=(0.5, 0.6)); popup.open()

# Autres ecrans techniques (PieceLibrary, etc.) - Versions minimalistes pour main.py
class PieceLibraryScreen(Screen):
    def on_enter(self, *args):
        self.clear_widgets()
        layout = BoxLayout(orientation="vertical", padding=20)
        layout.add_widget(Label(text="BIBLIOTHEQUE (En developpement)", font_size="24sp", color=COLORS["BF"]))
        btn = ModernButton(text="RETOUR", size_hint_y=None, height=60)
        btn.bind(on_press=lambda *_: setattr(self.manager, "current", "dashboard"))
        layout.add_widget(btn)
        self.add_widget(layout)

class PieceDetailScreen(Screen): pass
class VectorViewScreen(Screen): pass
class PdfFolderScreen(Screen): pass
class DetailedDatasheetScreen(Screen): pass
class AdvancedVisualsScreen(Screen): pass

# =========================
# Application
# =========================
class SHSEMApp(App):
    title = PROJECT_NAME
    target_power = StringProperty("150")
    simulation_results = DictProperty({})
    engine_params = DictProperty({})
    current_report_name = StringProperty("")

    def build(self):
        Window.clearcolor = COLORS["BL"]
        Window.size = (1280, 860)
        sm = ScreenManager(transition=FadeTransition())
        sm.add_widget(AutoConfigScreen(name="config"))
        sm.add_widget(AutoLoadingScreen(name="loading"))
        sm.add_widget(AutoDashboardScreen(name="dashboard"))
        sm.add_widget(PieceLibraryScreen(name="piece_library"))
        sm.add_widget(PieceDetailScreen(name="piece_detail"))
        sm.add_widget(VectorViewScreen(name="vector_view"))
        sm.add_widget(PdfFolderScreen(name="pdf_folder"))
        sm.add_widget(DetailedDatasheetScreen(name="detailed_datasheet"))
        sm.add_widget(AdvancedVisualsScreen(name="advanced_visuals"))
        sm.add_widget(EnergyAuditScreen(name="energy_audit"))
        sm.add_widget(ArchitectureChoiceScreen(name="arch_choice"))
        return sm

if __name__ == "__main__":
    SHSEMApp().run()
