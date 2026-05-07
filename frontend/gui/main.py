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
class ArchButton(Button):
    """Bouton de sélection d'architecture moteur."""
    def __init__(self, arch_name, **kwargs):
        super().__init__(text=arch_name, **kwargs)
        self.arch_name = arch_name
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.bold = True
        self.selected = False
        with self.canvas.before:
            self.bg_color_inst = Color(*COLORS["GF"])
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def set_selected(self, sel: bool):
        self.selected = sel
        self.bg_color_inst.rgba = COLORS["BF"] if sel else COLORS["GF"]
        self.color = COLORS["white"] if sel else COLORS["BF"]


class ConfigScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*COLORS["BL"])
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self._update_bg, size=self._update_bg)

        root = ScrollView(do_scroll_x=False)
        page = BoxLayout(orientation="vertical", padding=[80, 40], spacing=24, size_hint_y=None)
        page.bind(minimum_height=page.setter("height"))

        # Header
        hdr = BoxLayout(orientation="vertical", size_hint_y=None, height=120)
        hdr.add_widget(Label(text="SHSE-M", font_size="52sp", bold=True, color=COLORS["BF"],
                             size_hint_y=None, height=70))
        hdr.add_widget(Label(text="ENGINE GENERATOR", font_size="18sp", color=COLORS["BA"],
                             size_hint_y=None, height=30))
        page.add_widget(hdr)

        # ── Puissance ──
        pwr_card = PremiumCard(title="Puissance cible", size_hint_y=None, height=160)
        pwr_card.add_widget(Label(text="kW demandés au moteur", color=COLORS["GAXD"],
                                   font_size="14sp", size_hint_y=None, height=24))
        self.power_input = NeumorphicInput(text="150")
        self.power_input.hint_text = "Ex: 150"
        pwr_card.add_widget(self.power_input)
        page.add_widget(pwr_card)

        # ── Architecture ──
        arch_card = PremiumCard(title="Architecture moteur", size_hint_y=None, height=130)
        arch_row = BoxLayout(spacing=10, size_hint_y=None, height=52)
        self._arch_btns = {}
        self._selected_arch = "L6"
        for arch in ["L4", "L6", "V8", "V12"]:
            btn = ArchButton(arch, font_size="16sp")
            btn.set_selected(arch == "L6")
            btn.bind(on_press=lambda b, a=arch: self._select_arch(a))
            arch_row.add_widget(btn)
            self._arch_btns[arch] = btn
        arch_card.add_widget(arch_row)
        self._ncyl_lbl = Label(text="Cylindres auto (6)", color=COLORS["GAXD"],
                                font_size="13sp", size_hint_y=None, height=26)
        arch_card.add_widget(self._ncyl_lbl)
        page.add_widget(arch_card)

        # ── Paramètres moteur ──
        param_card = PremiumCard(title="Paramètres moteur détaillés", size_hint_y=None)
        param_card.bind(minimum_height=param_card.setter("height"))
        param_grid = GridLayout(cols=2, spacing=[20, 10], size_hint_y=None)
        param_grid.bind(minimum_height=param_grid.setter("height"))

        def _lbl(txt):
            l = Label(text=txt, color=COLORS["GAXD"], font_size="13sp",
                      size_hint_y=None, height=44, halign="right", valign="middle")
            l.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
            return l

        def _inp(default):
            i = NeumorphicInput(text=str(default))
            i.size_hint_y = None
            i.height = 52
            i.font_size = "18sp"
            return i

        self._fields = {}
        param_defs = [
            ("Alésage (mm)",       "alesage_mm",        "130"),
            ("Course (mm)",        "course_mm",         "150"),
            ("RPM nominal",        "rpm_nominal",       "1500"),
            ("PME (bar)",          "pme_bar",           "15"),
            ("Pression max (bar)", "pression_max_bar",  "80"),
            ("Rend. méca. cible",  "rendement_meca",    "0.85"),
        ]
        for lbl_txt, key, default in param_defs:
            param_grid.add_widget(_lbl(lbl_txt))
            inp = _inp(default)
            self._fields[key] = inp
            param_grid.add_widget(inp)

        param_card.add_widget(param_grid)

        # Sélecteur carburant
        fuel_row = BoxLayout(size_hint_y=None, height=52, spacing=16)
        fuel_row.add_widget(Label(text="Carburant :", color=COLORS["GAXD"],
                                   font_size="14sp", size_hint_x=0.3))
        self._fuel_btns = {}
        self._selected_fuel = "diesel"
        for fuel in ["diesel", "essence"]:
            fb = ArchButton(fuel.upper(), font_size="14sp")
            fb.set_selected(fuel == "diesel")
            fb.bind(on_press=lambda b, f=fuel: self._select_fuel(f))
            fuel_row.add_widget(fb)
            self._fuel_btns[fuel] = fb
        param_card.add_widget(fuel_row)
        page.add_widget(param_card)

        # Erreur + bouton
        self.err = Label(text="", color=COLORS["RF"], font_size="13sp",
                         size_hint_y=None, height=22)
        page.add_widget(self.err)

        self.gen_btn = ModernButton(text="GÉNÉRER LE SYSTÈME", size_hint_y=None, height=64)
        self.gen_btn.bind(on_press=self.launch_generation)
        page.add_widget(self.gen_btn)

        root.add_widget(page)
        self.add_widget(root)

    def _select_arch(self, arch: str):
        self._selected_arch = arch
        for k, b in self._arch_btns.items():
            b.set_selected(k == arch)
        ncyl_map = {"L4": 4, "L6": 6, "V8": 8, "V12": 12}
        self._ncyl_lbl.text = f"Cylindres auto ({ncyl_map.get(arch, '?')})"

    def _select_fuel(self, fuel: str):
        self._selected_fuel = fuel
        for k, b in self._fuel_btns.items():
            b.set_selected(k == fuel)

    def on_enter(self, *args):
        Clock.schedule_once(lambda dt: setattr(self.power_input, "focus", True), 0)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def _read_float(self, key: str, default: float) -> float:
        try:
            return float((self._fields[key].text or "").replace(",", "."))
        except Exception:
            return default

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

        arch = self._selected_arch
        ncyl_map = {"L4": 4, "L6": 6, "V8": 8, "V12": 12}
        ncyl = ncyl_map.get(arch, 6)
        alesage_mm = self._read_float("alesage_mm", 130.0)
        course_mm = self._read_float("course_mm", 150.0)
        rpm = self._read_float("rpm_nominal", 1500.0)
        pme_bar = self._read_float("pme_bar", 15.0)
        p_max_bar = self._read_float("pression_max_bar", 80.0)
        rend_meca = self._read_float("rendement_meca", 0.85)

        self.err.text = ""
        app = App.get_running_app()
        app.target_power = str(val)
        app.engine_params = {
            "architecture": arch,
            "nombre_cylindres": ncyl,
            "alesage_m": alesage_mm / 1000.0,
            "alesage_mm": alesage_mm,
            "course_m": course_mm / 1000.0,
            "course_mm": course_mm,
            "rpm_nominal": rpm,
            "pme_pa": pme_bar * 1e5,
            "pression_max_pa": p_max_bar * 1e5,
            "rendement_mecanique_cible_min": rend_meca,
            "carburant": self._selected_fuel,
            "temps_moteur": 4,
        }
        self.manager.current = "loading"


class LoadingScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=100, spacing=20)
        self.label = Label(text="Séquençage des calculs physiques...",
                           font_size="24sp", color=COLORS["BF"])
        self.sub_label = Label(text="", font_size="14sp", color=COLORS["BA"])
        layout.add_widget(self.label)
        layout.add_widget(self.sub_label)
        self.add_widget(layout)

    def on_enter(self):
        Clock.schedule_once(self.run_sim, 0.15)

    def run_sim(self, dt):
        threading.Thread(target=self.do_math, daemon=True).start()

    def do_math(self):
        import time
        app = App.get_running_app()
        ep = app.engine_params or {}
        p_target = float(app.target_power)

        arch = ep.get("architecture", "L6" if p_target >= 100 else "L4")
        ncyl = ep.get("nombre_cylindres", 6 if p_target >= 100 else 4)
        alesage_m = ep.get("alesage_m", 0.130 if p_target >= 100 else 0.080)
        course_m = ep.get("course_m", 0.150 if p_target >= 100 else 0.090)
        rpm = ep.get("rpm_nominal", 1500.0)
        pme_pa = ep.get("pme_pa", 15.0e5)
        p_max_pa = ep.get("pression_max_pa", 8.0e6)
        carburant = ep.get("carburant", "diesel")

        steps = ["Architecture...", "Cylindrée...", "Vilebrequin...",
                 "Thermodynamique...", "Pièces...", "Finalisation..."]
        for s in steps:
            Clock.schedule_once(lambda dt, msg=f"Calcul : {s}": setattr(self.label, "text", msg))
            time.sleep(0.25)

        sub = (f"{arch} · {ncyl} cyl · Ø{alesage_m*1000:.0f}×{course_m*1000:.0f} mm · "
               f"{rpm:.0f} rpm · {carburant}")
        Clock.schedule_once(lambda dt, m=sub: setattr(self.sub_label, "text", m))

        try:
            from backend.modules.systeme.database import SecureDatabase
            db = SecureDatabase()
            report_name = f"gui_moteur_{int(p_target)}kw"
            db.compute_and_save_from_main(
                report_name=report_name,
                function_name="dimensionner_systeme_shsem",
                puissance_traction_kw=p_target,
                energie_utile_imposee_kwh=100.0,
                puissance_moteur_requise_W=p_target * 1000.0 * 1.1,
                charger_batterie=True,
                vitesse_moteur_thermique_rpm=rpm,
                pression_max_pa=p_max_pa,
                contrainte_admissible_pa=1.8e8,
                rendement_mecanique_cible_min=ep.get("rendement_mecanique_cible_min", 0.85),
                moteur_thermique_definition={
                    "temps_moteur": ep.get("temps_moteur", 4),
                    "nombre_cylindres": ncyl,
                    "architecture": arch,
                    "alesage_m": alesage_m,
                    "course_m": course_m,
                    "rpm_nominal": rpm,
                    "pme_pa": pme_pa,
                    "pression_max_pa": p_max_pa,
                    "carburant": carburant,
                }
            )
            res = db.load_resume_gui()
            app.simulation_results = res or {}
            app.current_report_name = report_name
        except Exception:
            app.simulation_results = {"__error__": traceback.format_exc()}

        class DashboardScreen(Screen):
    res_pwr = StringProperty("-- kW")
    res_mass = StringProperty("-- kg")
    res_vol = StringProperty("-- m³")

