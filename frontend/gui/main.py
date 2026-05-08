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


def _safe_dict(value):
    return value if isinstance(value, dict) else {}


def _report_resume(report):
    report_dict = _safe_dict(report)
    resume = _safe_dict(report_dict.get("resume_gui"))
    return resume if resume else report_dict


def _flatten_mapping(data, prefix="", depth=0, max_depth=3):
    if depth > max_depth or not isinstance(data, dict):
        return
    for key, value in sorted(data.items(), key=lambda item: str(item[0])):
        label = f"{prefix}{str(key).replace('_', ' ').capitalize()}"
        if isinstance(value, dict):
            yield from _flatten_mapping(value, f"{label} > ", depth + 1, max_depth=max_depth)
        elif isinstance(value, (list, tuple)):
            if not value:
                yield label, "[]"
            elif all(not isinstance(item, (dict, list, tuple)) for item in value[:6]):
                yield label, ", ".join(str(item) for item in value[:6])
            else:
                yield label, f"[{len(value)} elements]"
        elif value is None:
            yield label, "-"
        else:
            yield label, str(value)


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
            from backend.main import dimensionner_systeme_shsem
            from backend.modules.systeme.database import SecureDatabase

            db = SecureDatabase(
                db_path=os.path.join(BASE_DIR, "backend", "shse_technical_data.db"),
                key_path=os.path.join(BASE_DIR, "backend", "secret.key"),
            )
            report_name = f"gui_moteur_{str(p_target).replace('.', 'p')}kw"
            report = dimensionner_systeme_shsem(
                puissance_traction_kw=p_target,
                charger_batterie=True,
                vitesse_moteur_thermique_rpm=rpm,
                pme_pa=pme_pa,
                pression_max_pa=p_max_pa,
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
                },
            )
            record_ids = db.save_main_report(report, report_name=report_name)
            res = db.load_main_report(report_name) or {}
            if isinstance(res, dict):
                res["stockage_front"] = {
                    "report_name": report_name,
                    "db_path": db.db_path,
                    "records_saved": len(record_ids),
                }
            app.simulation_results = res or {}
            app.current_report_name = report_name

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
        top = BoxLayout(size_hint_y=None, height=60, spacing=20)
        ttl = Label(text="RÉSULTATS DE GÉNÉRATION", font_size="22sp", bold=True,
                    color=COLORS["BF"], size_hint_x=0.55, halign="left", valign="middle")
        ttl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        top.add_widget(ttl)
        btn_adj = ModernButton(text="AJUSTER", size_hint_x=0.2, font_size="14sp")
        btn_adj.bind(on_press=self.open_adjust_popup)
        top.add_widget(btn_adj)
        back = Button(text="RECONFIGURER", size_hint_x=0.25,
                      background_color=(0, 0, 0, 0), color=COLORS["GAXD"])
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "config"))
        top.add_widget(back)
        layout.add_widget(top)

        grid = GridLayout(cols=3, rows=2, spacing=20, size_hint_y=0.68)
        c1 = PremiumCard(title="Performances")
        lbl_pwr = Label(text=self.res_pwr, font_size="30sp", bold=True, color=COLORS["BF"])
        self.bind(res_pwr=lambda _, v: setattr(lbl_pwr, "text", v))
        c1.add_widget(lbl_pwr)
        c1.add_widget(Label(text="Système Hybride Optimisé", color=COLORS["JV"]))
        grid.add_widget(c1)

        c2 = PremiumCard(title="Cylindrée")
        lbl_vol = Label(text=self.res_vol, font_size="26sp", bold=True, color=COLORS["BF"])
        self.bind(res_vol=lambda _, v: setattr(lbl_vol, "text", v))
        c2.add_widget(lbl_vol)
        lbl_mass = Label(text=self.res_mass, color=COLORS["BA"])
        self.bind(res_mass=lambda _, v: setattr(lbl_mass, "text", v))
        c2.add_widget(lbl_mass)
        grid.add_widget(c2)

        c3 = PremiumCard(title="Architecture")
        lbl_arch = Label(text=self.res_arch, font_size="26sp", bold=True, color=COLORS["BF"])
        self.bind(res_arch=lambda _, v: setattr(lbl_arch, "text", v))
        c3.add_widget(lbl_arch)
        lbl_ncyl = Label(text="-- cylindres", color=COLORS["GAXD"])
        self.bind(res_ncyl=lambda _, v: setattr(lbl_ncyl, "text", f"{v} cyl."))
        c3.add_widget(lbl_ncyl)
        grid.add_widget(c3)

        c4 = PremiumCard(title="Accès Rapide")
        bg = GridLayout(cols=2, spacing=10)
        for txt, screen in [("LISTE PIÈCES", "piece_library"), ("VUE VECT.", "vector_view"),
                             ("DOSSIER PDF", "pdf_folder"), ("FICHE DÉTAIL", "detailed_datasheet")]:
            b = ModernButton(text=txt, font_size="13sp")
            b.bind(on_press=lambda _, s=screen: setattr(self.manager, "current", s))
            bg.add_widget(b)
        c4.add_widget(bg)
        grid.add_widget(c4)

        c5 = PremiumCard(title="Alertes Santé")
        self.health_lbl = Label(text="OK", font_size="38sp", bold=True,
                                color=(30/255, 180/255, 50/255, 1))
        c5.add_widget(self.health_lbl)
        c5.add_widget(Label(text="Facteur sécurité > 1.5", color=COLORS["GAXD"]))
        grid.add_widget(c5)
        layout.add_widget(grid)

        self.dt_card = PremiumCard(title="CHAÎNE DE TRACTION", size_hint_y=0.3)
        self.dt_grid = GridLayout(cols=3, spacing=15, padding=10)
        self.dt_card.add_widget(self.dt_grid)
        layout.add_widget(self.dt_card)
        self.add_widget(layout)

    def open_adjust_popup(self, *_):
        app = App.get_running_app()
        ep = app.engine_params or {}
        content = BoxLayout(orientation="vertical", padding=20, spacing=12)
        fields = {}
        for lbl, key, default in [
            ("Alésage (mm)", "alesage_mm", ep.get("alesage_mm", ep.get("alesage_m", 0.13) * 1000)),
            ("Course (mm)", "course_mm", ep.get("course_mm", ep.get("course_m", 0.15) * 1000)),
            ("RPM", "rpm_nominal", ep.get("rpm_nominal", 1500)),
            ("PME (bar)", "pme_bar", ep.get("pme_pa", 15e5) / 1e5),
        ]:
            row = BoxLayout(size_hint_y=None, height=48, spacing=10)
            row.add_widget(Label(text=lbl, color=COLORS["BF"], size_hint_x=0.45, font_size="13sp"))
            inp = TextInput(text=str(round(float(default), 2)), multiline=False,
                            font_size="16sp", size_hint_x=0.55, size_hint_y=None, height=44)
            fields[key] = inp
            row.add_widget(inp)
            content.add_widget(row)

        def do_recalc(*_):
            new_ep = dict(ep)
            for k, inp in fields.items():
                try:
                    v = float(inp.text.replace(",", "."))
                    new_ep[k] = v
                    if k == "alesage_mm":
                        new_ep["alesage_m"] = v / 1000
                    if k == "course_mm":
                        new_ep["course_m"] = v / 1000
                    if k == "pme_bar":
                        new_ep["pme_pa"] = v * 1e5
                except Exception:
                    pass
            app.engine_params = new_ep
            popup.dismiss()
            self.manager.current = "loading"

        btn = ModernButton(text="RECALCULER", size_hint_y=None, height=52)
        btn.bind(on_press=do_recalc)
        content.add_widget(btn)
        popup = Popup(title="Ajuster les paramètres", content=content, size_hint=(0.55, 0.72))
        popup.open()

    def on_enter(self, *args):
        app = App.get_running_app()
        report = _safe_dict(app.simulation_results)
        if "__error__" in report:
            self.res_pwr = "ERREUR"
            self.res_arch = "Voir logs"
            self.res_ncyl = "--"
            self.res_mass = "--"
            self.res_vol = "--"
            show_popup("Erreur backend", str(report["__error__"])[:400])
            return
        res = _report_resume(report)
        p = float(app.target_power)
        n_cyl = res.get("N_cyl") or 0
        self.res_pwr = f"{p:.1f} kW"
        self.res_ncyl = str(n_cyl) if n_cyl else "--"
        self.res_arch = str(res.get("Architecture") or "?")
        vd = res.get("vd_tot_cc")
        self.res_vol = f"{vd / 1000:.2f} L" if vd else "--"
        self.dt_grid.clear_widgets()

        def _f(v, u="", d=1):
            if v is None:
                return "—"
            try:
                return f"{float(v):.{d}f} {u}".strip()
            except Exception:
                return str(v)

        bore_mm = res.get("Bore_mm")
        stroke_mm = res.get("Stroke_mm")
        rpm = res.get("RPM")
        pme_pa = res.get("PME_Pa") or res.get("PME")
        force_b = res.get("Force_bielle_N")
        energie = res.get("energie_batterie_kwh")
        p_bus = res.get("P_bus_dc_design_w")
        score = res.get("score_coherence_100")
        nb_inc = res.get("nb_inconnues", 0)
        nb_al = res.get("nb_alertes", 0)
        cao = _safe_dict(report.get("cao"))
        stockage = _safe_dict(report.get("stockage_front"))
        self.res_mass = (
            f"{float(energie):.1f} kWh batterie" if isinstance(energie, (int, float))
            else _f((float(p_bus) / 1000.0) if isinstance(p_bus, (int, float)) else None, "kW bus")
        )
        sc = (30/255, 180/255, 50/255, 1) if (score or 0) >= 80 else COLORS["RF"]

        for title, lines in [
            ("MOTEUR THERMIQUE", [
                f"Alésage: {_f(bore_mm, 'mm')}  Course: {_f(stroke_mm, 'mm')}",
                f"RPM: {_f(rpm, 'tr/min', 0)}",
                f"PME: {_f((pme_pa / 1e5) if pme_pa else None, 'bar')}",
                f"F bielle: {_f(force_b, 'N', 0)}",
            ]),
            ("SYSTEME", [
                f"Bus DC: {_f((p_bus / 1000.0) if p_bus else None, 'kW')}",
                f"Énergie batterie: {_f(energie, 'kWh')}",
                f"CAO détaillée: {'Oui' if cao.get('solidworks_ready_detaille') else 'Non'}",
            ]),
            ("QUALITÉ", [
                f"Score: {_f(score, '%', 0)}",
                f"Inconnues: {nb_inc}  Alertes: {nb_al}",
                f"BDD: {stockage.get('records_saved', 0)} enregistrements" if stockage else "BDD: -",
            ]),
        ]:
            box = BoxLayout(orientation="vertical", spacing=3)
            box.add_widget(Label(text=title, color=COLORS["BF"], bold=True,
                                 font_size="12sp", size_hint_y=None, height=26))
            for ln in lines:
                c = sc if "Score" in ln else COLORS["GAXD"]
                box.add_widget(Label(text=ln, color=c, font_size="11sp",
                                     size_hint_y=None, height=20))
            self.dt_grid.add_widget(box)


class VectorViewScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=20, spacing=20)
        top = BoxLayout(size_hint_y=None, height=60, spacing=10)
        top.add_widget(Label(text="VUE VECTORIELLE TECHNIQUE", font_size="22sp",
                             bold=True, color=COLORS["BF"]))
        back = ModernButton(text="RETOUR", size_hint_x=None, width=160)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "dashboard"))
        top.add_widget(back)
        root.add_widget(top)
        self.graph_box = PremiumCard(title="Graphiques")
        root.add_widget(self.graph_box)
        self.add_widget(root)

    def on_enter(self, *args):
        self.graph_box.clear_widgets()
        app = App.get_running_app()
        report = _safe_dict(app.simulation_results)
        res = _report_resume(report)
        if not (MATPLOTLIB_AVAILABLE and res) or "__error__" in report:
            self.graph_box.add_widget(Label(text="Données indisponibles.", color=COLORS["GAXD"]))
            return
        try:
            fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
            bore_mm = res.get("Bore_mm")
            stroke_mm = res.get("Stroke_mm")
            ep_cyl_mm = _safe_dict(_safe_dict(report.get("cao")).get("pieces")).get("cylindre", {}).get("epaisseur_cylindre_mm")
            force_bielle = res.get("Force_bielle_N")

            ax = axes[0]
            dim_labels = []
            dim_values = []
            for label, value in (("AlÃ©sage", bore_mm), ("Course", stroke_mm), ("Ep. cylindre", ep_cyl_mm)):
                if isinstance(value, (int, float)):
                    dim_labels.append(label)
                    dim_values.append(float(value))
            if dim_values:
                ax.bar(dim_labels, dim_values, color=["#0B4F6C", "#F4A259", "#5B8E7D"][:len(dim_values)])
                ax.set_ylabel("mm")
                ax.set_title("Cotes moteur")
                ax.grid(True, axis="y", alpha=0.25)
            else:
                ax.text(0.5, 0.5, "Cotes moteur indisponibles.", ha="center", va="center")
                ax.axis("off")

            ax2 = axes[1]
            effort_labels = []
            effort_values = []
            if isinstance(force_bielle, (int, float)):
                effort_labels.append("F bielle (kN)")
                effort_values.append(float(force_bielle) / 1000.0)
            couple = res.get("couple_moyen_Nm")
            if isinstance(couple, (int, float)):
                effort_labels.append("Couple (Nm)")
                effort_values.append(float(couple))
            if effort_values:
                ax2.bar(effort_labels, effort_values, color=["#BC4B51", "#7D5BA6"][:len(effort_values)])
                ax2.set_title("Efforts principaux")
                ax2.grid(True, axis="y", alpha=0.25)
            else:
                ax2.text(0.5, 0.5, "Efforts indisponibles.", ha="center", va="center")
                ax2.axis("off")

            fig.tight_layout()
            self.graph_box.add_widget(FigureCanvasKivyAgg(fig))
            return
            l_max = res.get("L_max_m")
            w_max = res.get("W_max_m")
            if isinstance(l_max, (int, float)) and isinstance(w_max, (int, float)) and l_max > 0 and w_max > 0:
                ax.add_patch(plt.Rectangle((0, 0), l_max, w_max, fill=True, alpha=0.1))
                ax.plot([0, l_max, l_max, 0, 0], [0, 0, w_max, w_max, 0], lw=2)
                ax.set_title("Encombrement estimé")
                ax.set_aspect("equal")
                ax.grid(True, alpha=0.3)
            else:
                ax.text(0.5, 0.5, "Clés L_max_m / W_max_m absentes.", ha="center", va="center")
                ax.axis("off")
            self.graph_box.add_widget(FigureCanvasKivyAgg(fig))
        except Exception as e:
            self.graph_box.add_widget(Label(text=f"Erreur : {e}", color=COLORS["RF"]))


class PdfFolderScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root = BoxLayout(orientation="vertical", padding=20, spacing=20)
        self.add_widget(self.root)

    def on_enter(self, *args):
        self.root.clear_widgets()
        top = BoxLayout(size_hint_y=None, height=60, spacing=10)
        top.add_widget(Label(text="DOSSIER DES FICHES PDF", font_size="22sp",
                             bold=True, color=COLORS["BF"]))
        back = ModernButton(text="RETOUR", size_hint_x=None, width=160)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "dashboard"))
        top.add_widget(back)
        self.root.add_widget(top)
        pdf_dir = os.path.join(BASE_DIR, "output", "datasheets", "pieces")
        sc = ScrollView()
        grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        if os.path.exists(pdf_dir):
            for f in sorted(f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")):
                row = BoxLayout(size_hint_y=None, height=44, spacing=10)
                row.add_widget(Label(text=f.replace(".pdf", "").upper(), color=COLORS["GAXD"]))
                btn = ModernButton(text="OUVRIR", size_hint_x=None, width=140, font_size="13sp")
                fp = os.path.join(pdf_dir, f)
                btn.bind(on_press=lambda *_, p=fp: os.startfile(p))
                row.add_widget(btn)
                grid.add_widget(row)
        else:
            grid.add_widget(Label(text="Aucun PDF généré.", color=COLORS["RF"]))
        sc.add_widget(grid)
        self.root.add_widget(sc)


class DetailedDatasheetScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root = BoxLayout(orientation="vertical", padding=20, spacing=16)
        self.add_widget(self.root)

    def on_enter(self, *args):
        self.root.clear_widgets()
        app = App.get_running_app()
        report = _safe_dict(app.simulation_results)
        res = _report_resume(report)
        top = BoxLayout(size_hint_y=None, height=62, spacing=10)
        top.add_widget(Label(text="FICHE DÉTAILLÉE SYSTÈME", font_size="20sp",
                             bold=True, color=COLORS["BF"]))
        back = ModernButton(text="RETOUR", size_hint_x=None, width=160)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "dashboard"))
        top.add_widget(back)
        self.root.add_widget(top)
        sc = ScrollView(do_scroll_x=False)
        page = GridLayout(cols=1, spacing=16, size_hint_y=None, padding=[2, 2])
        page.bind(minimum_height=page.setter("height"))
        sc.add_widget(page)
        self.root.add_widget(sc)
        sections = [
            ("Résumé", res),
            ("Synthèse", _safe_dict(report.get("synthese"))),
            ("CAO", _safe_dict(report.get("cao"))),
            ("Inventaire", _safe_dict(report.get("inventaire"))),
            ("Inconnues", _safe_dict(report.get("inconnues_resume"))),
            ("Stockage", _safe_dict(report.get("stockage_front"))),
        ]
        for title, section_data in sections:
            card = PremiumCard(title=title, size_hint_y=None)
            card.bind(minimum_height=card.setter("height"))
            stack = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None)
            stack.bind(minimum_height=stack.setter("height"))
            added = False
            for label, value in _flatten_mapping(section_data):
                stack.add_widget(TechRow(label, value))
                added = True
            if not added:
                stack.add_widget(Label(text="Aucune donnée disponible.", color=COLORS["GAXD"], size_hint_y=None, height=28))
            card.add_widget(stack)
            page.add_widget(card)


class PieceLibraryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        l = BoxLayout(orientation="vertical", padding=20, spacing=20)
        top = BoxLayout(size_hint_y=None, height=60, spacing=10)
        top.add_widget(Label(text="BIBLIOTHÈQUE TECHNIQUE", font_size="22sp",
                             bold=True, color=COLORS["BF"]))
        back = ModernButton(text="RETOUR", size_hint_x=None, width=160)
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
            self.grid.add_widget(Label(text=f"Dossier introuvable: {pieces_path}",
                                       color=COLORS["RF"]))
            return
        for f in sorted(f for f in os.listdir(pieces_path)
                        if f.endswith(".py") and f != "__init__.py"):
            raw_name = f[:-3]
            display_name = raw_name.replace("_", " ").upper()
            card = PremiumCard(title=display_name, size_hint_y=None, height=120)
            btn = ModernButton(text="VOIR DÉTAILS", font_size="12sp",
                               size_hint_y=None, height=44)
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
        ep = app.engine_params or {}

        top = BoxLayout(size_hint_y=None, height=62, spacing=10)
        title = Label(text=display_name, font_size="24sp", bold=True,
                      color=COLORS["BF"], halign="left", valign="middle")
        title.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        top.add_widget(title)
        back = ModernButton(text="RETOUR LISTE", size_hint_x=None, width=180)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "piece_library"))
        top.add_widget(back)
        self.layout.add_widget(top)

        data = None
        try:
            from backend.modules.systeme.database import SecureDatabase
            db = SecureDatabase(
                db_path=os.path.join(BASE_DIR, "backend", "shse_technical_data.db"))
            data = db.get_piece_data(raw_name) or db.get_piece_data(raw_name.replace("_", ""))
        except Exception as ex:
            print(f"[PIECE_DETAIL DB] {ex}")

        class PO:
            pass
        p = PO()
        p.nom = raw_name
        if isinstance(data, dict):
            for k, v in data.items():
                setattr(p, k, v)
        for k, v in ep.items():
            if not hasattr(p, k):
                setattr(p, k, v)

        grid = GridLayout(cols=4, spacing=12)
        sketch_card = PremiumCard(title="Croquis 2D")
        radar_card = PremiumCard(title="Résistance Mécanique")
        view3d_card = PremiumCard(title="Vue 3D")
        data_card = PremiumCard(title="Données de dimensionnement")

        if MATPLOTLIB_AVAILABLE:
            try:
                mod = importlib.import_module(f"frontend.pieces.sketches_2d.{raw_name}")
                fig, ax = plt.subplots(figsize=(4, 4))
                mod.draw(ax, p)
                sketch_card.add_widget(FigureCanvasKivyAgg(fig))
            except Exception as e:
                sketch_card.add_widget(Label(text=f"Croquis indisponible\n{str(e)[:80]}",
                                              color=COLORS["RF"], font_size="11sp"))
            try:
                chart_mod = importlib.import_module(f"frontend.pieces.charts.{raw_name}")
                fig_r = plt.figure(figsize=(4, 4))
                ax_r = fig_r.add_subplot(111, polar=True)
                chart_mod.plot_data(ax_r, p)
                radar_card.add_widget(FigureCanvasKivyAgg(fig_r))
            except Exception as e:
                radar_card.add_widget(Label(text=f"Radar indisponible\n{str(e)[:80]}",
                                             color=COLORS["RF"], font_size="11sp"))
            try:
                from frontend.pieces.views_3d import get_draw_3d
                from frontend.gui.piece_connector import get_piece_instance
                from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
                draw_3d = get_draw_3d(raw_name)
                piece_real = get_piece_instance(raw_name, ep)
                fig3d = plt.figure(figsize=(4, 4))
                ax3d = fig3d.add_subplot(111, projection="3d")
                draw_3d(ax3d, piece_real if piece_real is not None else p)
                view3d_card.add_widget(FigureCanvasKivyAgg(fig3d))
            except Exception as e:
                view3d_card.add_widget(Label(text=f"Vue 3D indisponible\n{str(e)[:80]}",
                                              color=COLORS["RF"], font_size="11sp"))
        else:
            for card in (sketch_card, radar_card, view3d_card):
                card.add_widget(Label(text="Matplotlib non disponible", color=COLORS["GAXD"]))

        sc = ScrollView(do_scroll_x=False)
        stack = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None, padding=[0, 6, 0, 0])
        stack.bind(minimum_height=stack.setter("height"))

        def _flat(d, prefix="", depth=0):
            if depth > 4 or not isinstance(d, dict):
                return
            for k, v in sorted(d.items(), key=lambda x: str(x)):
                key = f"{prefix}{k}".replace("_", " ").capitalize()
                if v is None:
                    yield key, "—"
                elif isinstance(v, bool):
                    yield key, "Oui" if v else "Non"
                elif isinstance(v, (int, float)):
                    try:
                        fv = float(v)
                        yield key, (f"{fv:.3e}" if abs(fv) >= 1e6 or (0 < abs(fv) < 1e-3)
                                    else f"{fv:.4g}")
                    except Exception:
                        yield key, str(v)
                elif isinstance(v, str):
                    yield key, v[:80]
                elif isinstance(v, (list, tuple)):
                    yield key, f"[{len(v)} éléments]"
                elif isinstance(v, dict):
                    yield from _flat(v, f"{key} › ", depth + 1)

        if isinstance(data, dict) and data:
            for ks, vs in _flat(data):
                stack.add_widget(TechRow(ks, vs))
        else:
            stack.add_widget(Label(text="Données non calculées.\nLancez une génération.",
                                   color=COLORS["RF"], size_hint_y=None, height=70))
        sc.add_widget(stack)
        data_card.add_widget(sc)

        grid.add_widget(sketch_card)
        grid.add_widget(radar_card)
        grid.add_widget(view3d_card)
        grid.add_widget(data_card)
        self.layout.add_widget(grid)


# =========================
# App
# =========================
class SHSEMApp(App):
    target_power = StringProperty("150")
    simulation_results = DictProperty({})
    engine_params = DictProperty({})
    current_report_name = StringProperty("")
    selected_piece_display = StringProperty("")
    selected_piece_raw = StringProperty("")

    def build(self):
        Window.clearcolor = COLORS["BL"]
        Window.size = (1280, 860)
        sm = ScreenManager(transition=FadeTransition())
        sm.add_widget(ConfigScreen(name="config"))
        sm.add_widget(LoadingScreen(name="loading"))
        sm.add_widget(DashboardScreen(name="dashboard"))
        sm.add_widget(PieceLibraryScreen(name="piece_library"))
        sm.add_widget(PieceDetailScreen(name="piece_detail"))
        sm.add_widget(VectorViewScreen(name="vector_view"))
        sm.add_widget(PdfFolderScreen(name="pdf_folder"))
        sm.add_widget(DetailedDatasheetScreen(name="detailed_datasheet"))
        return sm


if __name__ == "__main__":
    SHSEMApp().run()
