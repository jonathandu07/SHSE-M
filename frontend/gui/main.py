# backend\gui\main.py
# =========================
# PATH + CONFIG (TOUT EN HAUT)
# =========================
import os
import sys
import threading
import importlib
import traceback

# CONFIGURATION DU PATH (Doit être au tout début pour tous les threads)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# IMPORTANT : ces Config DOIVENT être avant tout autre import kivy
from kivy.config import Config
Config.set("input", "mouse", "mouse,disable_multitouch")
Config.set("graphics", "resizable", "1")

"""
SHSE-M - Interface Technique Haute Fidélité
Design : Neumorphisme Premium & Bento Design
Palette de Couleurs Utilisateur Stricte
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.properties import StringProperty, DictProperty
from kivy.graphics import Color, RoundedRectangle
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.lang import Builder

# =========================
# Matplotlib (optionnel)
# =========================
MATPLOTLIB_AVAILABLE = False
try:
    import matplotlib
    matplotlib.use("module://kivy.garden.matplotlib.backend_kivy")
    from kivy.garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except Exception:
    # Tentative sans garden si installé différemment
    try:
        from kivy.garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
        import matplotlib.pyplot as plt
        MATPLOTLIB_AVAILABLE = True
    except Exception:
        print("[AVERTISSEMENT] kivy.garden.matplotlib non trouvé. Les croquis 2D seront remplacés par des placeholders.")

# =========================
# Palette
# =========================
COLORS = {
    "BL": (244/255, 254/255, 254/255, 1),
    "GW": (247/255, 247/255, 255/255, 1),
    "BG": (229/255, 229/255, 229/255, 1),
    "GF": (217/255, 217/255, 217/255, 1),
    "GAXD": (112/255, 112/255, 112/255, 1),
    "VG": (107/255, 108/255, 102/255, 1),
    "JV": (255/255, 198/255, 0/255, 1),
    "BF": (5/255, 20/255, 64/255, 1),
    "BA": (129/255, 161/255, 184/255, 1),
    "BM": (3/255, 34/255, 76/255, 1),
    "BFW": (9/255, 18/255, 38/255, 1),
    "NF": (30/255, 30/255, 30/255, 1),
    "white": (1, 1, 1, 1),
    "black": (0, 0, 0, 1),
    "RF": (236/255, 25/255, 32/255, 1),
}

# =========================
# Input : FIX AZERTY + virgule
# =========================
AZERTY_MAP = {
    "&": "1", "é": "2", '"': "3", "'": "4", "(": "5",
    "-": "6", "è": "7", "_": "8", "ç": "9", "à": "0",
}

class NeumorphicInput(TextInput):
    """Champ de saisie neumorphique : accepte AZERTY + virgule."""
    def insert_text(self, substring, from_undo=False):
        substring = substring.replace(",", ".")
        out = []
        for ch in substring:
            # On ne mappe QUE si ce n'est pas déjà un chiffre/point
            if ch not in "0123456789." and ch in AZERTY_MAP:
                ch = AZERTY_MAP[ch]
            if ch in "0123456789.":
                out.append(ch)
        return super().insert_text("".join(out), from_undo=from_undo)

Builder.load_string("""
<NeumorphicInput>:
    background_normal: ''
    background_active: ''
    background_color: 0, 0, 0, 0
    font_size: '32sp'
    padding: [20, 20]
    halign: 'center'
    multiline: False
    # IMPORTANT: PAS de input_filter ici (AZERTY sinon bloqué)
    foreground_color: 0.02, 0.08, 0.25, 1
    cursor_color: 0.92, 0.10, 0.12, 1
    selection_color: 0.60, 0.80, 0.95, 0.60
    canvas.before:
        Color:
            rgba: 0.85, 0.85, 0.85, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [15]
        Color:
            rgba: 0.97, 0.97, 1, 1
        RoundedRectangle:
            pos: self.x + 2, self.y + 2
            size: self.width - 4, self.height - 4
            radius: [13]
""")

# =========================
# UI Components
# =========================
class PremiumCard(BoxLayout):
    def __init__(self, title="", **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = [20, 20]
        self.spacing = 10
        with self.canvas.before:
            Color(200/255, 200/255, 200/255, 0.4)
            self.shadow = RoundedRectangle(pos=(0, 0), size=(0, 0), radius=[24])
            Color(*COLORS["white"])
            self.bg = RoundedRectangle(pos=(0, 0), size=(0, 0), radius=[24])
        self.bind(pos=self.update_graphics, size=self.update_graphics)

        if title:
            self.add_widget(Label(
                text=title.upper(),
                size_hint_y=None, height=30,
                color=COLORS["BF"],
                bold=True, font_size="14sp",
                halign="left", valign="middle"
            ))

    def update_graphics(self, *args):
        self.shadow.pos = (self.x + 6, self.y - 6)
        self.shadow.size = self.size
        self.bg.pos = self.pos
        self.bg.size = self.size

class ModernButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.bold = True
        self.color = COLORS["white"]
        if "font_size" not in kwargs:
            self.font_size = "18sp"
        with self.canvas.before:
            self.bg_color = Color(*COLORS["BF"])
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[20])
        self.bind(pos=self.update_graphics, size=self.update_graphics)

    def on_state(self, instance, value):
        self.bg_color.rgba = COLORS["BM"] if value == "down" else COLORS["BF"]

    def update_graphics(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

# =========================
# Screens
# =========================
class ConfigScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*COLORS["BL"])
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        root = BoxLayout(orientation="vertical", padding=[100, 60], spacing=40)

        header = BoxLayout(orientation="vertical", size_hint_y=0.4)
        header.add_widget(Label(text="SHSE-M", font_size="64sp", bold=True, color=COLORS["BF"]))
        header.add_widget(Label(text="ENGINE GENERATOR", font_size="24sp", color=COLORS["BA"]))
        root.add_widget(header)

        main_card = PremiumCard(size_hint_y=0.4)
        main_card.add_widget(Label(text="PUISSANCE CIBLE (kW)", color=COLORS["BF"], bold=True, font_size="18sp"))

        self.power_input = NeumorphicInput(text="150")
        self.power_input.foreground_color = COLORS["BF"]
        self.power_input.cursor_color = COLORS["RF"]
        main_card.add_widget(self.power_input)

        self.err = Label(text="", color=COLORS["RF"], font_size="14sp", size_hint_y=None, height=20)
        main_card.add_widget(self.err)

        root.add_widget(main_card)

        self.gen_btn = ModernButton(text="GÉNÉRER LE SYSTÈME", size_hint_y=0.2)
        self.gen_btn.bind(on_press=self.launch_generation)
        root.add_widget(self.gen_btn)

        self.add_widget(root)

    def on_enter(self, *args):
        Clock.schedule_once(lambda dt: setattr(self.power_input, "focus", True), 0)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def launch_generation(self, *_):
        txt = (self.power_input.text or "").strip().replace(",", ".")
        try:
            val = float(txt)
            if val <= 0: raise ValueError("P > 0 requis")
            if val > 5000:
                self.err.text = "Limite: 5000 kW (Physique)"
                return
        except Exception as e:
            self.err.text = f"Entrée invalide: {e}"
            return

        self.err.text = ""
        app = App.get_running_app()
        app.target_power = str(val)
        self.manager.current = "loading"

class LoadingScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=100)
        self.label = Label(text="Séquençage des calculs physiques...", font_size="24sp", color=COLORS["BF"])
        layout.add_widget(self.label)
        self.add_widget(layout)

    def on_enter(self):
        Clock.schedule_once(self.run_sim, 0.2)

    def run_sim(self, dt):
        threading.Thread(target=self.do_math, daemon=True).start()

    def do_math(self):
        import time
        app = App.get_running_app()

        steps = ["Architecture...", "Cylindrée...", "Vilebrequin...", "Thermodynamique...", "Finalisation..."]
        for s in steps:
            Clock.schedule_once(lambda dt, msg=f"Calcul : {s}": setattr(self.label, "text", msg))
            time.sleep(0.35)

        try:
            from backend.main import dimensionner_systeme_shsem
            p_target = float(app.target_power)
            res = dimensionner_systeme_shsem(p_target)
            app.simulation_results = res or {}
        except Exception:
            app.simulation_results = {"__error__": traceback.format_exc()}

        Clock.schedule_once(lambda dt: setattr(self.manager, "current", "dashboard"))

class DashboardScreen(Screen):
    res_pwr = StringProperty("-- kW")
    res_mass = StringProperty("-- kg")
    res_vol = StringProperty("-- m³")
    res_ncyl = StringProperty("--")
    res_arch = StringProperty("--")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=20, spacing=20)

        top = BoxLayout(size_hint_y=0.1, spacing=20)
        top.add_widget(Label(
            text="RÉSULTATS DE GÉNÉRATION",
            font_size="24sp", bold=True, color=COLORS["BF"],
            size_hint_x=0.7, halign="left", valign="middle"
        ))
        back = Button(text="RECONFIGURER", size_hint_x=0.3, background_color=(0,0,0,0), color=COLORS["GAXD"])
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "config"))
        top.add_widget(back)
        layout.add_widget(top)

        grid = GridLayout(cols=3, rows=2, spacing=20, size_hint_y=0.8)

        c1 = PremiumCard(title="Performances")
        lbl_pwr = Label(text=self.res_pwr, font_size="36sp", bold=True, color=COLORS["BF"])
        self.bind(res_pwr=lambda _, v: setattr(lbl_pwr, "text", v))
        c1.add_widget(lbl_pwr)
        c1.add_widget(Label(text="Système Hybride Optimisé", color=COLORS["JV"]))
        grid.add_widget(c1)

        c2 = PremiumCard(title="Dimensions")
        lbl_mass = Label(text=self.res_mass, font_size="36sp", bold=True, color=COLORS["BF"])
        self.bind(res_mass=lambda _, v: setattr(lbl_mass, "text", v))
        c2.add_widget(lbl_mass)
        lbl_vol = Label(text=self.res_vol, color=COLORS["BA"])
        self.bind(res_vol=lambda _, v: setattr(lbl_vol, "text", v))
        c2.add_widget(lbl_vol)
        grid.add_widget(c2)

        c3 = PremiumCard(title="Architecture")
        lbl_arch = Label(text=self.res_arch, font_size="28sp", bold=True, color=COLORS["BF"])
        self.bind(res_arch=lambda _, v: setattr(lbl_arch, "text", v))
        c3.add_widget(lbl_arch)
        lbl_ncyl = Label(text="-- cylindres", color=COLORS["GAXD"])
        self.bind(res_ncyl=lambda _, v: setattr(lbl_ncyl, "text", f"{v} cylindres"))
        c3.add_widget(lbl_ncyl)
        grid.add_widget(c3)

        c4 = PremiumCard(title="Accès Rapide")
        btn_grid = GridLayout(cols=2, spacing=10)

        btn_lib = ModernButton(text="LISTE DES PIÈCES", font_size="14sp")
        btn_lib.bind(on_press=lambda *_: setattr(self.manager, "current", "piece_library"))
        btn_grid.add_widget(btn_lib)

        btn_grid.add_widget(ModernButton(text="VUE VECTORIELLE", font_size="14sp"))
        btn_grid.add_widget(ModernButton(text="DOSSIER PDF", font_size="14sp"))
        btn_grid.add_widget(ModernButton(text="SIMULATION LIVE", font_size="14sp"))
        c4.add_widget(btn_grid)
        grid.add_widget(c4)

        c5 = PremiumCard(title="Alertes Santé")
        c5.add_widget(Label(text="OK", font_size="48sp", bold=True, color=(30/255, 180/255, 50/255, 1)))
        c5.add_widget(Label(text="Facteur de sécurité > 1.5", color=COLORS["GAXD"]))
        grid.add_widget(c5)

        layout.add_widget(grid)

        # Bas : Chaîne de Traction
        self.dt_card = PremiumCard(title="CHAÎNE DE TRACTION (BATTERIE / ALT / BOÎTE)", size_hint_y=0.3)
        self.dt_grid = GridLayout(cols=3, spacing=15, padding=10)
        self.dt_card.add_widget(self.dt_grid)
        layout.add_widget(self.dt_card)

        # Footer
        footer = BoxLayout(size_hint_y=0.1, spacing=20)

    def on_enter(self, *args):
        app = App.get_running_app()
        res = app.simulation_results or {}

        if "__error__" in res:
            self.res_pwr = "ERREUR"
            self.res_arch = "backend"
            self.res_ncyl = "--"
            self.res_mass = "--"
            self.res_vol = "--"
            return

        p = float(app.target_power)
        n = res.get("N_cyl", 0)
        arch = res.get("Architecture", "Inconnue")

        self.res_pwr = f"{p:.1f} kW"
        self.res_ncyl = f"{n}"
        self.res_arch = str(arch)

        m_tot = res.get('masse_totale_kg', p * 0.6 + n * 10)
        v_est = (p * 0.002) + (n * 0.05)
        self.res_mass = f"{m_tot:.0f} kg"
        self.res_vol = f"{v_est:.2f} m³"

        # Remplissage Détails Transmission
        self.dt_grid.clear_widgets()
        dt = res.get('drivetrain', {})
        for comp_name, specs in dt.items():
            box = BoxLayout(orientation='vertical', spacing=5)
            box.add_widget(Label(text=comp_name.upper(), color=COLORS['BF'], bold=True, font_size='14sp', size_hint_y=None, height=30))
            for k, v in specs.items():
                short_k = k.replace('_', ' ').capitalize()[:15]
                box.add_widget(Label(text=f"{short_k}: {v}", color=COLORS['GAXD'], font_size='11sp', size_hint_y=None, height=20))
            self.dt_grid.add_widget(box)

class PieceLibraryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        l = BoxLayout(orientation="vertical", padding=20, spacing=20)

        top = BoxLayout(size_hint_y=0.1)
        top.add_widget(Label(text="BIBLIOTHÈQUE TECHNIQUE", font_size="24sp", bold=True, color=COLORS["BF"]))
        back = ModernButton(text="RETOUR", size_hint_x=0.2)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "dashboard"))
        top.add_widget(back)
        l.add_widget(top)

        sc = ScrollView()
        self.grid = GridLayout(cols=3, spacing=20, size_hint_y=None, padding=10)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        sc.add_widget(self.grid)
        l.add_widget(sc)

        self.add_widget(l)

    def on_enter(self, *args):
        self.grid.clear_widgets()

        pieces_path = os.path.join(BASE_DIR, "backend", "pieces")
        if not os.path.exists(pieces_path):
            self.grid.add_widget(Label(text=f"Dossier introuvable: {pieces_path}", color=COLORS["RF"]))
            return

        files = [f for f in os.listdir(pieces_path) if f.endswith(".py") and f != "__init__.py"]
        for f in sorted(files):
            raw_name = f[:-3]
            display_name = raw_name.replace("_", " ").upper()
            card = PremiumCard(title=display_name, size_hint_y=None, height=120)
            btn = ModernButton(text="VOIR DÉTAILS", font_size="12sp")
            btn.bind(on_press=lambda _, dn=display_name, rn=raw_name: self.view_details(dn, rn))
            card.add_widget(btn)
            self.grid.add_widget(card)

    def view_details(self, display_name, raw_name):
        app = App.get_running_app()
        app.selected_piece_display = display_name
        app.selected_piece_raw = raw_name
        self.manager.current = "piece_detail"

class PieceDetailScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical", padding=20, spacing=20)
        self.add_widget(self.layout)

    def on_enter(self, *args):
        self.layout.clear_widgets()
        app = App.get_running_app()
        display_name = getattr(app, "selected_piece_display", "PIÈCE")
        raw_name = getattr(app, "selected_piece_raw", "")

        top = BoxLayout(size_hint_y=0.1, spacing=10)
        top.add_widget(Label(text=display_name, font_size="28sp", bold=True, color=COLORS["BF"]))
        back = ModernButton(text="RETOUR LISTE", size_hint_x=0.2)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "piece_library"))
        top.add_widget(back)
        self.layout.add_widget(top)

        grid = GridLayout(cols=3, spacing=15, size_hint_y=0.9)

        # ---- 1. Croquis 2D
        sketch_card = PremiumCard(title="Croquis 2D")
        # --- 2. Radar Chart (Nouveau)
        radar_card = PremiumCard(title="Résistance Mécanique")
        # --- 3. Données
        data_card = PremiumCard(title="Données Techniques")

        data = None
        try:
            from backend.database import SecureDatabase
            db = SecureDatabase()
            data = db.get_piece_data(raw_name)
        except Exception:
            pass

        if MATPLOTLIB_AVAILABLE:
            # Rendu Croquis
            try:
                draw_mod = importlib.import_module(f"frontend.pieces.sketches_2d.{raw_name}")
                fig, ax = plt.subplots(figsize=(4, 4))
                class PO: pass
                p = PO()
                p.nom = raw_name
                if data:
                    for k, v in data.items(): setattr(p, k, v)
                draw_mod.draw(ax, p)
                sketch_card.add_widget(FigureCanvasKivyAgg(plt.gcf()))
            except Exception as e:
                sketch_card.add_widget(Label(text=f"No Sketch: {e}", color=COLORS["RF"]))

            # Rendu Radar
            try:
                import matplotlib.pyplot as plt
                plt.clf()
                chart_mod = importlib.import_module(f"frontend.pieces.charts.{raw_name}")
                fig_r = plt.figure(figsize=(4, 4))
                ax_r = fig_r.add_subplot(111, polar=True)
                chart_mod.plot_data(ax_r, p)
                radar_card.add_widget(FigureCanvasKivyAgg(fig_r))
            except Exception as e:
                radar_card.add_widget(Label(text=f"No Radar: {e}", color=COLORS["RF"]))
        if not MATPLOTLIB_AVAILABLE:
            fallback = BoxLayout(orientation="vertical", padding=40)
            fallback.add_widget(Label(text="[ SCHÉMA TECHNIQUE ]", bold=True, font_size="24sp", color=COLORS["BF"]))
            fallback.add_widget(Label(text=f"ID: {raw_name.upper()}", color=COLORS["GAXD"]))
            fallback.add_widget(Label(text="Matplotlib-Kivy non détecté", font_size="12sp", color=COLORS["GAXD"]))
            sketch_card.add_widget(fallback)

        grid.add_widget(sketch_card)
        grid.add_widget(radar_card)

        # ---- Données techniques
        data_card = PremiumCard(title="Données de Dimensionnement")
        sc = ScrollView()
        data_grid = GridLayout(cols=2, spacing=10, size_hint_y=None, padding=10)
        data_grid.bind(minimum_height=data_grid.setter("height"))

        if data:
            for k in sorted(data.keys()):
                v = data[k]
                lbl_key = Label(
                    text=k.replace("_", " ").capitalize(),
                    color=COLORS["GAXD"],
                    halign="left",
                    size_hint_y=None, height=40,
                    font_size="14sp"
                )
                lbl_key.bind(size=lbl_key.setter("text_size"))
                data_grid.add_widget(lbl_key)

                val_str = f"{v:.4f}" if isinstance(v, float) else str(v)
                data_grid.add_widget(Label(text=val_str, color=COLORS["BF"], bold=True, size_hint_y=None, height=40))
        else:
            data_grid.add_widget(Label(text="Données non calculées.\nLancez une génération.", color=COLORS["RF"]))

        sc.add_widget(data_grid)
        data_card.add_widget(sc)
        grid.add_widget(data_card)

        self.layout.add_widget(grid)

# =========================
# App
# =========================
class SHSEMApp(App):
    target_power = StringProperty("150")
    simulation_results = DictProperty({})
    selected_piece_display = StringProperty("")
    selected_piece_raw = StringProperty("")

    def build(self):
        Window.clearcolor = COLORS["BL"]
        Window.size = (1200, 800)

        sm = ScreenManager(transition=FadeTransition())
        sm.add_widget(ConfigScreen(name="config"))
        sm.add_widget(LoadingScreen(name="loading"))
        sm.add_widget(DashboardScreen(name="dashboard"))
        sm.add_widget(PieceLibraryScreen(name="piece_library"))
        sm.add_widget(PieceDetailScreen(name="piece_detail"))
        return sm

if __name__ == "__main__":
    SHSEMApp().run()
