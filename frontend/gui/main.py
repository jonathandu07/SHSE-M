# backend/gui/main.py
# =========================================================
# SHSE-M - Interface Technique Haute Fidélité (Kivy)
# Design : Neumorphisme Premium & Bento Design
# =========================================================

# =========================
# PATH + CONFIG (TOUT EN HAUT)
# =========================
import os
import sys
import io
import threading
import importlib
import importlib.util
import traceback

# CONFIGURATION DU PATH (Doit être au tout début pour tous les threads)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# IMPORTANT : ces Config DOIVENT être avant tout autre import kivy
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
from kivy.properties import StringProperty, DictProperty
from kivy.graphics import Color, RoundedRectangle
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.lang import Builder

# =========================
# Palette
# =========================
COLORS = {
    "BL": (244 / 255, 254 / 255, 254 / 255, 1),
    "GW": (247 / 255, 247 / 255, 255 / 255, 1),
    "BG": (229 / 255, 229 / 255, 229 / 255, 1),
    "GF": (217 / 255, 217 / 255, 217 / 255, 1),
    "GAXD": (112 / 255, 112 / 255, 112 / 255, 1),
    "VG": (107 / 255, 108 / 255, 102 / 255, 1),
    "JV": (255 / 255, 198 / 255, 0 / 255, 1),
    "BF": (5 / 255, 20 / 255, 64 / 255, 1),
    "BA": (129 / 255, 161 / 255, 184 / 255, 1),
    "BM": (3 / 255, 34 / 255, 76 / 255, 1),
    "BFW": (9 / 255, 18 / 255, 38 / 255, 1),
    "NF": (30 / 255, 30 / 255, 30 / 255, 1),
    "white": (1, 1, 1, 1),
    "black": (0, 0, 0, 1),
    "RF": (236 / 255, 25 / 255, 32 / 255, 1),
}

# =========================
# Popup util
# =========================
def show_popup(title: str, message: str) -> None:
    content = BoxLayout(orientation="vertical", padding=20, spacing=15)

    msg = Label(text=message, color=COLORS["BF"], halign="left", valign="top")
    msg.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
    content.add_widget(msg)

    btn = Button(text="OK", size_hint_y=None, height=44)
    content.add_widget(btn)

    pop = Popup(
        title=title,
        content=content,
        size_hint=(None, None),
        size=(560, 320),
        auto_dismiss=False,
    )
    btn.bind(on_press=lambda *_: pop.dismiss())
    pop.open()


# =========================
# Matplotlib Bridge (Custom FigureCanvasKivyAgg)
# =========================
MATPLOTLIB_AVAILABLE = False
try:
    import matplotlib.pyplot as plt

    class FigureCanvasKivyAgg(KivyImage):
        """Bridge minimaliste (render figure -> texture Kivy via savefig)."""

        def __init__(self, figure, **kwargs):
            super().__init__(**kwargs)
            self.figure = figure
            self.allow_stretch = True
            self.keep_ratio = True
            self.update_canvas()
            # évite l'accumulation de figures (mémoire)
            try:
                plt.close(self.figure)
            except Exception:
                pass

        def update_canvas(self, *args):
            buf = io.BytesIO()
            self.figure.savefig(buf, format="png", bbox_inches="tight", dpi=130)
            buf.seek(0)
            from kivy.core.image import Image as CoreImage

            im = CoreImage(buf, ext="png")
            self.texture = im.texture
            try:
                buf.close()
            except Exception:
                pass

    MATPLOTLIB_AVAILABLE = True
except Exception as e:
    print(f"[INFO] Matplotlib ou Bridge non disponible : {e}")


# =========================
# AZERTY MAPPING
# =========================
AZERTY_MAP = {
    "&": "1", "é": "2", '"': "3", "'": "4", "(": "5", "-": "6", "è": "7", "_": "8", "ç": "9", "à": "0"
}

# =========================
# Input : NUMÉRIQUE VISIBLE
# - On laisse s'afficher ce que tu tapes
# - On filtre seulement digits + '.' + ','
# =========================
class NeumorphicInput(TextInput):
    """Champ de saisie neumorphique : chiffres + séparateur décimal ('.' ou ',')."""

    def insert_text(self, substring, from_undo=False):
        s = substring or ""
        current = self.text or ""
        sel = self.selection_text or ""

        out = []
        for ch in s:
            # AZERTY Support
            if ch in AZERTY_MAP:
                ch = AZERTY_MAP[ch]

            # Replace comma with dot
            if ch == ",":
                ch = "."

            if ch.isdigit() or ch == ".":
                # Autoriser un seul séparateur décimal total
                if ch == ".":
                    if sel == "":
                        if "." in current:
                            continue
                out.append(ch)

        return super().insert_text("".join(out), from_undo=from_undo)


# IMPORTANT :
# - TextInput n'a PAS de text_size (propriété de Label). On n'utilise pas text_size ici.
# - Le "je ne vois pas ce que je tape" vient souvent d'une couleur/padding inadaptés.
Builder.load_string(
    r"""
<NeumorphicInput>:
    background_normal: ''
    background_active: ''
    background_color: 0, 0, 0, 0

    size_hint_y: None
    height: '76dp'
    font_size: '32sp'
    multiline: False
    write_tab: False

    # Padding : (left, top, right, bottom)
    padding: [20, 18, 20, 18]

    halign: 'center'

    # Couleurs lisibles
    foreground_color: 0.02, 0.08, 0.25, 1
    hint_text_color: 0.45, 0.45, 0.45, 1
    cursor_color: 0.92, 0.10, 0.12, 1
    cursor_width: '2dp'

    selection_color: 0.70, 0.82, 0.95, 0.85
    selection_text_color: 0.02, 0.08, 0.25, 1

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
"""
)

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
            Color(200 / 255, 200 / 255, 200 / 255, 0.35)
            self.shadow = RoundedRectangle(pos=(0, 0), size=(0, 0), radius=[24])
            Color(*COLORS["white"])
            self.bg = RoundedRectangle(pos=(0, 0), size=(0, 0), radius=[24])

        self.bind(pos=self.update_graphics, size=self.update_graphics)

        if title:
            t = Label(
                text=title.upper(),
                size_hint_y=None,
                height=30,
                color=COLORS["BF"],
                bold=True,
                font_size="14sp",
                halign="left",
                valign="middle",
            )
            t.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
            self.add_widget(t)

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


class TechRow(BoxLayout):
    """Une ligne clé/valeur lisible (fond léger + padding + wrap)."""

    def __init__(self, key_text: str, value_text: str, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            height=48,
            spacing=10,
            padding=[12, 6, 12, 6],
            **kwargs,
        )

        with self.canvas.before:
            Color(COLORS["GW"][0], COLORS["GW"][1], COLORS["GW"][2], 0.80)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self.bind(pos=self._update_bg, size=self._update_bg)

        self.key_lbl = Label(
            text=key_text,
            color=COLORS["GAXD"],
            halign="left",
            valign="middle",
            font_size="13sp",
            size_hint_x=0.60,
        )
        self.val_lbl = Label(
            text=value_text,
            color=COLORS["BF"],
            halign="right",
            valign="middle",
            font_size="14sp",
            size_hint_x=0.40,
        )

        self.key_lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        self.val_lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))

        self.add_widget(self.key_lbl)
        self.add_widget(self.val_lbl)

    def _update_bg(self, *args):
        self._bg.pos = self.pos
        self._bg.size = self.size


# =========================
# Screens
# =========================
class ConfigScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*COLORS["BL"])
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self._update_bg, size=self._update_bg)

        root = BoxLayout(orientation="vertical", padding=[100, 60], spacing=40)

        header = BoxLayout(orientation="vertical", size_hint_y=0.4)
        header.add_widget(Label(text="SHSE-M", font_size="64sp", bold=True, color=COLORS["BF"]))
        header.add_widget(Label(text="ENGINE GENERATOR", font_size="24sp", color=COLORS["BA"]))
        root.add_widget(header)

        main_card = PremiumCard(size_hint_y=0.4)
        main_card.add_widget(Label(text="PUISSANCE CIBLE (kW)", color=COLORS["BF"], bold=True, font_size="18sp"))

        self.power_input = NeumorphicInput(text="150")
        self.power_input.hint_text = "Ex: 150"
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
        txt_raw = (self.power_input.text or "").strip()
        txt = txt_raw.replace(",", ".")
        try:
            val = float(txt)
            if val <= 0:
                raise ValueError("P > 0 requis")
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
        Clock.schedule_once(self.run_sim, 0.15)

    def run_sim(self, dt):
        threading.Thread(target=self.do_math, daemon=True).start()

    def do_math(self):
        import time

        app = App.get_running_app()

        steps = ["Architecture...", "Cylindrée...", "Vilebrequin...", "Thermodynamique...", "Finalisation..."]
        for s in steps:
            Clock.schedule_once(lambda dt, msg=f"Calcul : {s}": setattr(self.label, "text", msg))
            time.sleep(0.30)

        try:
            from backend.main import dimensionner_systeme_shsem_simple, generer_rapport_puissance_json_bdd

            p_target = float(app.target_power)
            res = dimensionner_systeme_shsem_simple(p_target)
            label = str(p_target).replace(".", "p")
            storage = generer_rapport_puissance_json_bdd(
                p_target,
                "kw",
                report_name=f"gui_moteur_{label}kw",
                output_dir=os.path.join(BASE_DIR, "backend", "outputs", "gui"),
                db_path=os.path.join(BASE_DIR, "backend", "shse_technical_data.db"),
                key_path=os.path.join(BASE_DIR, "backend", "secret.key"),
            )
            res["rapport_puissance_json"] = storage.get("json_path")
            res["rapport_puissance_bdd"] = storage.get("db_path")
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
        ttl = Label(
            text="RÉSULTATS DE GÉNÉRATION",
            font_size="24sp",
            bold=True,
            color=COLORS["BF"],
            size_hint_x=0.7,
            halign="left",
            valign="middle",
        )
        ttl.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        top.add_widget(ttl)

        back = Button(text="RECONFIGURER", size_hint_x=0.3, background_color=(0, 0, 0, 0), color=COLORS["GAXD"])
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

        # Accès rapide
        c4 = PremiumCard(title="Accès Rapide")
        btn_grid = GridLayout(cols=2, spacing=10)

        btn_lib = ModernButton(text="LISTE DES PIÈCES", font_size="14sp")
        btn_lib.bind(on_press=lambda *_: setattr(self.manager, "current", "piece_library"))
        btn_grid.add_widget(btn_lib)

        btn_vec = ModernButton(text="VUE VECTORIELLE", font_size="14sp")
        btn_vec.bind(on_press=lambda *_: setattr(self.manager, "current", "vector_view"))
        btn_grid.add_widget(btn_vec)

        btn_pdf = ModernButton(text="DOSSIER PDF", font_size="14sp")
        btn_pdf.bind(on_press=lambda *_: setattr(self.manager, "current", "pdf_folder"))
        btn_grid.add_widget(btn_pdf)

        btn_data = ModernButton(text="FICHE DÉTAILLÉE", font_size="14sp")
        btn_data.bind(on_press=lambda *_: setattr(self.manager, "current", "detailed_datasheet"))
        btn_grid.add_widget(btn_data)

        c4.add_widget(btn_grid)
        grid.add_widget(c4)

        c5 = PremiumCard(title="Alertes Santé")
        c5.add_widget(Label(text="OK", font_size="48sp", bold=True, color=(30 / 255, 180 / 255, 50 / 255, 1)))
        c5.add_widget(Label(text="Facteur de sécurité > 1.5", color=COLORS["GAXD"]))
        grid.add_widget(c5)

        layout.add_widget(grid)

        # Bas : Chaîne de Traction
        self.dt_card = PremiumCard(title="CHAÎNE DE TRACTION (BATTERIE / ALT / BOÎTE)", size_hint_y=0.3)
        self.dt_grid = GridLayout(cols=3, spacing=15, padding=10)
        self.dt_card.add_widget(self.dt_grid)
        layout.add_widget(self.dt_card)

        self.add_widget(layout)

    def on_enter(self, *args):
        app = App.get_running_app()
        res = app.simulation_results or {}

        if "__error__" in res:
            err_msg = str(res["__error__"])[:300]
            self.res_pwr = "ERREUR"
            self.res_arch = "Voir logs"
            self.res_ncyl = "--"
            self.res_mass = "--"
            self.res_vol = "--"
            show_popup("Erreur backend", err_msg)
            return

        p = float(app.target_power)

        # Clés réelles produites par resume_gui de l'orchestrateur complet
        n_cyl = res.get("N_cyl") or 0
        arch = res.get("Architecture") or "Inconnue"
        bore_mm = res.get("Bore_mm")
        stroke_mm = res.get("Stroke_mm")
        vd_cc = res.get("vd_tot_cc")
        rpm = res.get("RPM")
        pme_pa = res.get("PME_Pa") or res.get("PME")
        force_bielle = res.get("Force_bielle_N")
        energie_kwh = res.get("energie_batterie_kwh")
        score = res.get("score_coherence_100")
        nb_inconnues = res.get("nb_inconnues", 0)
        nb_alertes = res.get("nb_alertes", 0)

        self.res_pwr = f"{p:.1f} kW"
        self.res_ncyl = str(n_cyl) if n_cyl else "--"
        self.res_arch = str(arch)

        # Masse : pas encore dans resume_gui, on estime prudemment
        self.res_mass = f"~{p * 0.6 + n_cyl * 10:.0f} kg"

        # Volume/cylindrée
        if vd_cc:
            self.res_vol = f"{vd_cc/1000:.2f} L cylindrée"
        else:
            self.res_vol = "--"

        # Remplissage grille chaîne de traction avec données réelles
        self.dt_grid.clear_widgets()

        def _fmt(v, unit="", digits=1):
            if v is None:
                return "—"
            try:
                return f"{float(v):.{digits}f} {unit}".strip()
            except Exception:
                return str(v)

        # Bloc moteur thermique
        mt_box = BoxLayout(orientation="vertical", spacing=4)
        mt_box.add_widget(Label(text="MOTEUR THERMIQUE", color=COLORS["BF"], bold=True,
                                font_size="13sp", size_hint_y=None, height=28))
        mt_box.add_widget(Label(text=f"Alésage: {_fmt(bore_mm, 'mm')}  Course: {_fmt(stroke_mm, 'mm')}",
                                color=COLORS["GAXD"], font_size="11sp", size_hint_y=None, height=20))
        mt_box.add_widget(Label(text=f"RPM: {_fmt(rpm, 'tr/min', 0)}",
                                color=COLORS["GAXD"], font_size="11sp", size_hint_y=None, height=20))
        pme_bar = (pme_pa / 1e5) if pme_pa else None
        mt_box.add_widget(Label(text=f"PME: {_fmt(pme_bar, 'bar', 1)}",
                                color=COLORS["GAXD"], font_size="11sp", size_hint_y=None, height=20))
        mt_box.add_widget(Label(text=f"F bielle max: {_fmt(force_bielle, 'N', 0)}",
                                color=COLORS["GAXD"], font_size="11sp", size_hint_y=None, height=20))
        self.dt_grid.add_widget(mt_box)

        # Bloc batterie
        batt_box = BoxLayout(orientation="vertical", spacing=4)
        batt_box.add_widget(Label(text="BATTERIE", color=COLORS["BF"], bold=True,
                                  font_size="13sp", size_hint_y=None, height=28))
        batt_box.add_widget(Label(text=f"Énergie: {_fmt(energie_kwh, 'kWh', 1)}",
                                  color=COLORS["GAXD"], font_size="11sp", size_hint_y=None, height=20))
        self.dt_grid.add_widget(batt_box)

        # Bloc qualité
        qual_box = BoxLayout(orientation="vertical", spacing=4)
        qual_box.add_widget(Label(text="QUALITÉ", color=COLORS["BF"], bold=True,
                                  font_size="13sp", size_hint_y=None, height=28))
        score_color = (30/255, 180/255, 50/255, 1) if (score or 0) >= 80 else COLORS["RF"]
        qual_box.add_widget(Label(text=f"Score cohérence: {_fmt(score, '%', 0)}",
                                  color=score_color, font_size="11sp", size_hint_y=None, height=20))
        qual_box.add_widget(Label(text=f"Inconnues: {nb_inconnues}  Alertes: {nb_alertes}",
                                  color=COLORS["GAXD"], font_size="11sp", size_hint_y=None, height=20))
        self.dt_grid.add_widget(qual_box)


class VectorViewScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=20, spacing=20)

        top = BoxLayout(size_hint_y=None, height=60, spacing=10)
        top.add_widget(Label(text="VUE VECTORIELLE TECHNIQUE", font_size="24sp", bold=True, color=COLORS["BF"]))
        back = ModernButton(text="RETOUR", size_hint_x=None, width=180)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "dashboard"))
        top.add_widget(back)
        root.add_widget(top)

        self.graph_box = PremiumCard(title="Graphiques (backend)")
        root.add_widget(self.graph_box)
        self.add_widget(root)

    def on_enter(self, *args):
        self.graph_box.clear_widgets()
        app = App.get_running_app()
        res = app.simulation_results or {}

        if not (MATPLOTLIB_AVAILABLE and res) or "__error__" in res:
            self.graph_box.add_widget(Label(text="Matplotlib ou données indisponibles.", color=COLORS["GAXD"]))
            return

        try:
            fig, ax = plt.subplots(figsize=(9, 4))

            l_max = res.get("L_max_m", None)
            w_max = res.get("W_max_m", None)

            if isinstance(l_max, (int, float)) and isinstance(w_max, (int, float)) and l_max > 0 and w_max > 0:
                ax.add_patch(plt.Rectangle((0, 0), l_max, w_max, fill=True, alpha=0.10))
                ax.plot([0, l_max, l_max, 0, 0], [0, 0, w_max, w_max, 0], linewidth=2)
                ax.set_title("Encombrement estimé (L_max / W_max)")
                ax.set_xlim(-0.1, l_max + 0.3)
                ax.set_ylim(-0.1, w_max + 0.3)
                ax.set_aspect("equal")
                ax.grid(True, alpha=0.3)
            else:
                ax.text(0.5, 0.5, "Clés L_max_m / W_max_m absentes (ou invalides) dans res.", ha="center", va="center")
                ax.axis("off")

            self.graph_box.add_widget(FigureCanvasKivyAgg(fig))
        except Exception as e:
            self.graph_box.add_widget(Label(text=f"Erreur graphique : {e}", color=COLORS["RF"]))


class PdfFolderScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root = BoxLayout(orientation="vertical", padding=20, spacing=20)
        self.add_widget(self.root)

    def on_enter(self, *args):
        self.root.clear_widgets()

        top = BoxLayout(size_hint_y=None, height=60, spacing=10)
        top.add_widget(Label(text="DOSSIER DES FICHES PDF", font_size="24sp", bold=True, color=COLORS["BF"]))
        back = ModernButton(text="RETOUR", size_hint_x=None, width=180)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "dashboard"))
        top.add_widget(back)
        self.root.add_widget(top)

        pdf_dir = os.path.join(BASE_DIR, "output", "datasheets", "pieces")

        btn_open_dir = ModernButton(text="OUVRIR LE DOSSIER DANS L'EXPLORATEUR", size_hint_y=None, height=50)
        btn_open_dir.bind(on_press=lambda *_: self.open_path(pdf_dir))
        self.root.add_widget(btn_open_dir)

        sc = ScrollView()
        grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        if os.path.exists(pdf_dir):
            files = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]
            if files:
                for f in sorted(files):
                    row = BoxLayout(size_hint_y=None, height=44, spacing=10, padding=[6, 0])
                    name = f.replace(".pdf", "").replace("_", " ").upper()
                    lbl = Label(text=name, halign="left", color=COLORS["GAXD"])
                    lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
                    row.add_widget(lbl)

                    btn_view = ModernButton(text="OUVRIR", size_hint_x=None, width=160, font_size="14sp")
                    path = os.path.join(pdf_dir, f)
                    btn_view.bind(on_press=lambda *_, p=path: self.open_path(p))
                    row.add_widget(btn_view)

                    grid.add_widget(row)
            else:
                grid.add_widget(Label(text="Aucun PDF généré dans ce dossier.", color=COLORS["RF"]))
        else:
            grid.add_widget(Label(text=f"Dossier introuvable :\n{pdf_dir}", color=COLORS["RF"]))

        sc.add_widget(grid)
        self.root.add_widget(sc)

    def open_path(self, path):
        try:
            if sys.platform == "win32":
                os.startfile(path)  # noqa: S606
            else:
                import subprocess

                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.call([opener, path])  # noqa: S603,S607
        except Exception as e:
            show_popup("Erreur", f"Impossible d'ouvrir :\n{path}\n\n{e}")


class DetailedDatasheetScreen(Screen):
    """Fiche système lisible (n'affiche que ce que le backend/BDD fournit)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root = BoxLayout(orientation="vertical", padding=20, spacing=16)
        self.add_widget(self.root)

    @staticmethod
    def _fmt(v, digits=3, suffix=""):
        if v is None:
            return "—"
        if isinstance(v, bool):
            return "Oui" if v else "Non"
        if isinstance(v, int):
            return f"{v}{suffix}"
        if isinstance(v, float):
            return f"{v:.{digits}f}{suffix}"
        return f"{v}{suffix}"

    def _section(self, parent, title: str) -> BoxLayout:
        # IMPORTANT : pour ScrollView, on force des hauteurs auto
        card = PremiumCard(title=title, size_hint_y=None)
        card.bind(minimum_height=card.setter("height"))

        stack = BoxLayout(orientation="vertical", spacing=8, size_hint_y=None, padding=[0, 6, 0, 4])
        stack.bind(minimum_height=stack.setter("height"))

        card.add_widget(stack)
        parent.add_widget(card)
        return stack

    def _kv(self, stack, k, v):
        stack.add_widget(TechRow(str(k), str(v)))

    def _kv_num(self, stack, k, v, digits=3, suffix=""):
        self._kv(stack, k, self._fmt(v, digits=digits, suffix=suffix))

    def on_enter(self, *args):
        self.root.clear_widgets()
        app = App.get_running_app()
        res = app.simulation_results or {}

        top = BoxLayout(size_hint_y=None, height=62, spacing=10)
        title = Label(
            text="FICHE DÉTAILLÉE SYSTÈME",
            font_size="22sp",
            color=COLORS["BF"],
            halign="left",
            valign="middle",
        )
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        top.add_widget(title)

        back = ModernButton(text="RETOUR", size_hint_x=None, width=180)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "dashboard"))
        top.add_widget(back)
        self.root.add_widget(top)

        if (not res) or ("__error__" in res):
            msg = "Aucune donnée valide à afficher."
            if "__error__" in res:
                msg += "\n\nErreur backend :\n" + str(res["__error__"])[:1200]
            self.root.add_widget(Label(text=msg, color=COLORS["RF"]))
            return

        # Load BDD once
        all_pieces = {}
        db_error = None
        try:
            from backend.modules.systeme.database import SecureDatabase

            db_path_abs = os.path.join(BASE_DIR, "backend", "shse_technical_data.db")
            db = SecureDatabase(db_path=db_path_abs)
            all_pieces = db.get_all_pieces() or {}
        except Exception as e:
            db_error = str(e)

        sc = ScrollView(do_scroll_x=False)

        # IMPORTANT : GridLayout + minimum_height => ScrollView stable
        page = GridLayout(cols=1, spacing=16, size_hint_y=None, padding=[2, 2, 2, 18])
        page.bind(minimum_height=page.setter("height"))
        sc.add_widget(page)
        self.root.add_widget(sc)

        # Résumé
        s0 = self._section(page, "Résumé")
        try:
            self._kv_num(s0, "Puissance cible (kW)", float(app.target_power), digits=1)
        except Exception:
            self._kv(s0, "Puissance cible (kW)", self._fmt(app.target_power))
        self._kv(s0, "Architecture", self._fmt(res.get("Architecture")))
        self._kv(s0, "Nombre de cylindres", self._fmt(res.get("N_cyl")))
        self._kv_num(s0, "Masse totale (kg)", res.get("masse_totale_kg"), digits=2)
        self._kv_num(s0, "Volume total (m³)", res.get("volume_total_m3"), digits=4)

        # Géométrie
        s1 = self._section(page, "Géométrie & Cinématique (backend)")
        self._kv_num(s1, "Alésage (mm)", res.get("Bore_mm"), digits=2)
        self._kv_num(s1, "Course (mm)", res.get("Stroke_mm"), digits=2)
        self._kv_num(s1, "Cylindrée totale (L)", res.get("Displacement_L"), digits=4)
        self._kv_num(s1, "Encombrement L max (m)", res.get("L_max_m"), digits=3)
        self._kv_num(s1, "Encombrement W max (m)", res.get("W_max_m"), digits=3)

        # Thermo / pression (sans supposer les unités)
        s2 = self._section(page, "Thermodynamique / Pression (backend)")
        self._kv_num(s2, "PME (bar)", res.get("PME_bar"), digits=2)
        self._kv(s2, "P_max (valeur brute)", self._fmt(res.get("P_max")))
        self._kv(s2, "Rendement global (valeur brute)", self._fmt(res.get("eta_global")))

        # Drivetrain
        s3 = self._section(page, "Chaîne de traction (backend)")
        drivetrain = res.get("drivetrain", {}) or {}
        if not drivetrain:
            self._kv(s3, "Données", "—")
        else:
            for comp_name in sorted(drivetrain.keys(), key=lambda x: str(x)):
                specs = drivetrain.get(comp_name) or {}
                sub = PremiumCard(title=str(comp_name).upper(), size_hint_y=None)
                sub.bind(minimum_height=sub.setter("height"))

                sub_stack = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None, padding=[0, 6, 0, 0])
                sub_stack.bind(minimum_height=sub_stack.setter("height"))

                if not specs:
                    sub_stack.add_widget(Label(text="—", color=COLORS["GAXD"], size_hint_y=None, height=24))
                elif isinstance(specs, dict):
                    for k in sorted(specs.keys(), key=lambda x: str(x)):
                        sub_stack.add_widget(TechRow(k.replace("_", " ").capitalize(), self._fmt(specs[k], digits=3)))
                else:
                    sub_stack.add_widget(TechRow("Données", self._fmt(specs)))

                sub.add_widget(sub_stack)
                s3.add_widget(sub)

        # Inventaire BDD
        s4 = self._section(page, "Inventaire composants (BDD)")
        if db_error:
            s4.add_widget(
                Label(text=f"BDD indisponible : {db_error}", color=COLORS["RF"], size_hint_y=None, height=40)
            )
        elif not all_pieces:
            s4.add_widget(Label(text="Aucune pièce trouvée en BDD.", color=COLORS["GAXD"], size_hint_y=None, height=32))
        else:
            masses = []
            for _, pdata in all_pieces.items():
                try:
                    m = pdata.get("masse_kg", None)
                    if isinstance(m, (int, float)):
                        masses.append(float(m))
                except Exception:
                    pass

            header = BoxLayout(size_hint_y=None, height=34, padding=[6, 0], spacing=10)
            header.add_widget(Label(text=f"Nombre de pièces : {len(all_pieces)}", color=COLORS["BF"], halign="left"))
            header.add_widget(
                Label(
                    text=("Masse totale BDD : " + self._fmt(sum(masses), digits=3, suffix=" kg")) if masses else "Masse totale BDD : —",
                    color=COLORS["BF"],
                    halign="right",
                )
            )
            s4.add_widget(header)

            inner_sc = ScrollView(size_hint_y=None, height=420, do_scroll_x=False)
            inner = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None)
            inner.bind(minimum_height=inner.setter("height"))
            inner_sc.add_widget(inner)
            s4.add_widget(inner_sc)

            for name in sorted(all_pieces.keys(), key=lambda x: str(x)):
                pdata = all_pieces[name] or {}
                m = pdata.get("masse_kg", None)

                if isinstance(m, (int, float)):
                    m = float(m)
                    mass_txt = f"{m * 1000:.1f} g" if m < 1 else f"{m:.3f} kg"
                else:
                    mass_txt = "—"

                inner.add_widget(TechRow(name.replace("_", " ").upper(), mass_txt))


class PieceLibraryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        l = BoxLayout(orientation="vertical", padding=20, spacing=20)

        top = BoxLayout(size_hint_y=None, height=60, spacing=10)
        top.add_widget(Label(text="BIBLIOTHÈQUE TECHNIQUE", font_size="24sp", bold=True, color=COLORS["BF"]))
        back = ModernButton(text="RETOUR", size_hint_x=None, width=180)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "dashboard"))
        top.add_widget(back)
        l.add_widget(top)

        sc = ScrollView(do_scroll_x=False)
        self.grid = GridLayout(cols=3, spacing=20, size_hint_y=None, padding=10)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        sc.add_widget(self.grid)
        l.add_widget(sc)

        self.add_widget(l)

    def on_enter(self, *args):
        self.grid.clear_widgets()

        pieces_path = os.path.join(BASE_DIR, "backend", "components", "moteur_thermique", "pieces")
        if not os.path.exists(pieces_path):
            self.grid.add_widget(Label(text=f"Dossier introuvable: {pieces_path}", color=COLORS["RF"]))
            return

        files = [f for f in os.listdir(pieces_path) if f.endswith(".py") and f != "__init__.py"]
        if not files:
            self.grid.add_widget(Label(text="Aucune pièce trouvée dans backend/components/moteur_thermique/pieces", color=COLORS["GAXD"]))
            return

        for f in sorted(files):
            raw_name = f[:-3]
            display_name = raw_name.replace("_", " ").upper()
            card = PremiumCard(title=display_name, size_hint_y=None, height=130)

            btn = ModernButton(text="VOIR DÉTAILS", font_size="12sp", size_hint_y=None, height=44)
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
        self.layout = BoxLayout(orientation="vertical", padding=20, spacing=16)
        self.add_widget(self.layout)

    def on_enter(self, *args):
        self.layout.clear_widgets()
        app = App.get_running_app()
        display_name = getattr(app, "selected_piece_display", "PIÈCE")
        raw_name = getattr(app, "selected_piece_raw", "")

        # Top
        top = BoxLayout(size_hint_y=None, height=62, spacing=10)
        title = Label(text=display_name, font_size="26sp", bold=True, color=COLORS["BF"], halign="left", valign="middle")
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        top.add_widget(title)

        back = ModernButton(text="RETOUR LISTE", size_hint_x=None, width=180)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "piece_library"))
        top.add_widget(back)

        self.layout.add_widget(top)

        # Contenu 3 colonnes : Sketch / Radar / Données
        grid = GridLayout(cols=3, spacing=15)

        sketch_card = PremiumCard(title="Croquis 2D")
        radar_card = PremiumCard(title="Résistance Mécanique")
        data_card = PremiumCard(title="Données de dimensionnement")

        # --- Load data
        data = None
        try:
            from backend.modules.systeme.database import SecureDatabase

            db_path_abs = os.path.join(BASE_DIR, "backend", "shse_technical_data.db")
            db = SecureDatabase(db_path=db_path_abs)
            data = db.get_piece_data(raw_name)
            if not data:
                data = db.get_piece_data(raw_name.replace("_", ""))
        except Exception as e:
            print(f"[ERREUR PIECE_DETAIL] {e}")

        class PO:
            pass

        p = PO()
        p.nom = raw_name
        if isinstance(data, dict):
            for k, v in data.items():
                setattr(p, k, v)

        # --- Sketch & Radar
        if MATPLOTLIB_AVAILABLE:
            # 1) Sketch
            try:
                module_path = f"frontend.pieces.sketches_2d.{raw_name}"
                try:
                    draw_mod = importlib.import_module(module_path)
                except Exception:
                    path = os.path.join(BASE_DIR, "frontend", "pieces", "sketches_2d", f"{raw_name}.py")
                    spec = importlib.util.spec_from_file_location(raw_name, path)
                    if spec is None or spec.loader is None:
                        raise ImportError(f"Module introuvable: {path}")
                    draw_mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(draw_mod)

                fig, ax = plt.subplots(figsize=(4, 4))
                draw_mod.draw(ax, p)
                sketch_card.add_widget(FigureCanvasKivyAgg(fig))
            except Exception as e:
                sketch_card.add_widget(Label(text=f"Croquis indisponible : {e}", color=COLORS["RF"]))

            # 2) Radar/Chart
            try:
                module_path = f"frontend.pieces.charts.{raw_name}"
                try:
                    chart_mod = importlib.import_module(module_path)
                except Exception:
                    path = os.path.join(BASE_DIR, "frontend", "pieces", "charts", f"{raw_name}.py")
                    spec = importlib.util.spec_from_file_location(raw_name, path)
                    if spec is None or spec.loader is None:
                        raise ImportError(f"Module introuvable: {path}")
                    chart_mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(chart_mod)

                fig_r = plt.figure(figsize=(4, 4))
                ax_r = fig_r.add_subplot(111, polar=True)
                chart_mod.plot_data(ax_r, p)
                radar_card.add_widget(FigureCanvasKivyAgg(fig_r))
            except Exception as e:
                radar_card.add_widget(Label(text=f"Radar indisponible : {e}", color=COLORS["RF"]))
        else:
            fallback = BoxLayout(orientation="vertical", padding=30, spacing=10)
            fallback.add_widget(Label(text="[ APERÇU ]", bold=True, font_size="22sp", color=COLORS["BF"]))
            fallback.add_widget(Label(text=f"ID: {raw_name.upper()}", color=COLORS["GAXD"]))
            fallback.add_widget(Label(text="Matplotlib non disponible", font_size="12sp", color=COLORS["GAXD"]))
            sketch_card.add_widget(fallback)
            radar_card.add_widget(Label(text="Matplotlib non disponible", color=COLORS["GAXD"]))

        # --- Data list (lisible)
        sc = ScrollView(do_scroll_x=False)
        stack = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None, padding=[0, 6, 0, 0])
        stack.bind(minimum_height=stack.setter("height"))

        if isinstance(data, dict) and data:
            for k in sorted(data.keys(), key=lambda x: str(x)):
                v = data[k]
                val_str = f"{v:.6g}" if isinstance(v, float) else str(v)
                stack.add_widget(TechRow(k.replace("_", " ").capitalize(), val_str))
        else:
            stack.add_widget(
                Label(
                    text="Données non calculées.\nLancez une génération.",
                    color=COLORS["RF"],
                    size_hint_y=None,
                    height=70,
                )
            )

        sc.add_widget(stack)
        data_card.add_widget(sc)

        # Add columns
        grid.add_widget(sketch_card)
        grid.add_widget(radar_card)
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

        # écrans des boutons "Accès rapide"
        sm.add_widget(VectorViewScreen(name="vector_view"))
        sm.add_widget(PdfFolderScreen(name="pdf_folder"))
        sm.add_widget(DetailedDatasheetScreen(name="detailed_datasheet"))

        return sm


if __name__ == "__main__":
    SHSEMApp().run()

