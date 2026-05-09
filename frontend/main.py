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
from pathlib import Path
from typing import Any, Dict, List, Optional, Mapping

# CONFIGURATION DU PATH (Doit être au tout début pour tous les threads)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Kivy doit journaliser dans le workspace du projet, pas dans un profil
# utilisateur potentiellement non accessible.
KIVY_HOME = os.path.join(BASE_DIR, ".kivy")
KIVY_LOGS = os.path.join(KIVY_HOME, "logs")
os.makedirs(KIVY_LOGS, exist_ok=True)
os.environ.setdefault("KIVY_HOME", KIVY_HOME)

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

# Visualisations Spécialisées
from frontend.gui.viz_utils import resolve_viz_module, get_draw_3d_func, get_viz_figure
from frontend.gui.piece_connector import get_piece_instance
from frontend.gui.pdf_export import export_element_pdf

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


def _merge_front_dicts(*sources):
    out = {}
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key, value in src.items():
            if key not in out:
                out[key] = value
    return out


def _current_piece_payload(report, db_name: str, raw_name: str):
    report = _safe_dict(report)
    inventaire_pieces = _safe_dict(_safe_dict(report.get("inventaire")).get("pieces"))
    rapports_pieces = _safe_dict(report.get("rapports_pieces"))
    construction = _safe_dict(_safe_dict(report.get("construction_pieces")).get("construction"))
    objets = _safe_dict(_safe_dict(report.get("objets_serialises")).get("pieces"))

    key_candidates = []
    for candidate in (db_name, raw_name, raw_name.replace("_", "")):
        if candidate and candidate not in key_candidates:
            key_candidates.append(candidate)

    for key in list(inventaire_pieces.keys()):
        if key not in key_candidates and key.endswith(f".{raw_name}"):
            key_candidates.append(key)

    for key in key_candidates:
        payload = _merge_front_dicts(
            {"piece": key},
            inventaire_pieces.get(key),
            {"rapport": rapports_pieces.get(key)} if isinstance(rapports_pieces.get(key), dict) else {},
            {"objet_serialise": objets.get(key)} if isinstance(objets.get(key), dict) else {},
            {"construction": construction.get(key)} if isinstance(construction.get(key), dict) else {},
        )
        if any(isinstance(payload.get(name), dict) for name in ("rapport", "objet_serialise", "construction")) or isinstance(payload.get("inventaire"), dict):
            payload.setdefault("inventaire", inventaire_pieces.get(key))
            payload.setdefault("objet", _safe_dict(inventaire_pieces.get(key)).get("objet"))
            return payload
    return {}


def _current_component_payload(report, component_name: str):
    report = _safe_dict(report)
    component_inventory = _safe_dict(_safe_dict(report.get("inventaire")).get("composants"))
    analyses = _safe_dict(report.get("analyses_composants"))
    objects = _safe_dict(_safe_dict(report.get("objets_serialises")).get("composants"))

    aliases = {
        "architecture": ("architecture",),
        "alternateur": ("alternateur", "alternateur_bus_dc"),
        "batterie": ("batterie", "batterie_dimensionnement"),
        "moteur_electrique": ("moteur_electrique",),
        "moteur_thermique": (
            "moteur_thermique",
            "moteur_thermique_geometrie",
            "moteur_thermique_cycle",
            "moteur_thermique_point",
            "moteur_thermique_bilan_carburant",
            "construction_moteur_thermique",
        ),
        "boite_crabots": ("boite_crabots", "boite_point", "boite_chaine"),
    }
    names = aliases.get(component_name, (component_name,))

    payload = {"component": component_name}
    inventory = component_inventory.get(component_name)
    if isinstance(inventory, dict):
        payload["inventaire"] = inventory
        payload.update(inventory)

    report_bundle = {}
    for name in names:
        analysis = analyses.get(name)
        if isinstance(analysis, dict):
            report_bundle[name] = analysis
    if report_bundle:
        payload["rapport"] = report_bundle.get(component_name) or next(iter(report_bundle.values()))
        if len(report_bundle) > 1:
            payload["rapports"] = report_bundle

    obj = objects.get(component_name)
    if isinstance(obj, dict):
        payload["objet_serialise"] = obj
        payload.setdefault("objet", obj)

    return payload if len(payload) > 1 else {}


def _piece_backend_status(payload):
    data = _safe_dict(payload)
    if not data:
        return {"label": "À calculer", "detail": "Aucune donnée backend disponible.", "color": COLORS["RF"]}

    construit = bool(data.get("construit"))
    rapport = data.get("rapport")
    rapport_disponible = bool(data.get("rapport_disponible")) or (
        isinstance(rapport, dict) and bool(rapport) and "note" not in rapport and "erreur" not in rapport
    )
    if construit and rapport_disponible:
        return {"label": "Calculée", "detail": "Pièce construite avec rapport exploitable.", "color": (0.12, 0.66, 0.24, 1)}
    if construit:
        note = _safe_dict(rapport).get("note") or "Pièce construite avec retour partiel."
        return {"label": "Partielle", "detail": str(note), "color": COLORS["JV"]}
    return {"label": "Non construite", "detail": "Données insuffisantes pour construire cette pièce.", "color": COLORS["RF"]}


def _slugify_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("_", "-", ".") else "_" for ch in str(value).strip().lower())


def _datasheet_root() -> Path:
    return Path(BASE_DIR) / "output" / "datasheets"


def _export_piece_pdf_from_report(report, engine_params, db_name: str, raw_name: str, display_name: str) -> Path:
    payload = _current_piece_payload(report, db_name, raw_name)
    piece_obj = get_piece_instance(raw_name, engine_params or {}, db_data=payload)
    target = _datasheet_root() / "pieces" / f"{_slugify_name(db_name or raw_name)}.pdf"
    return export_element_pdf(
        element_name=raw_name,
        display_name=display_name,
        payload=payload,
        element_obj=piece_obj,
        output_path=target,
        is_component=False,
    )


def _export_component_pdf_from_report(report, engine_params, component_name: str, display_name: str) -> Path:
    payload = _current_component_payload(report, component_name)
    component_obj = get_piece_instance(component_name, engine_params or {}, db_data=payload)
    target = _datasheet_root() / "components" / f"{_slugify_name(component_name)}.pdf"
    return export_element_pdf(
        element_name=component_name,
        display_name=display_name,
        payload=payload,
        element_obj=component_obj,
        output_path=target,
        is_component=True,
    )


def _export_full_report_pdfs(report, engine_params) -> Dict[str, Any]:
    report = _safe_dict(report)
    generated_pieces = []
    generated_components = []

    for piece_key, payload in sorted(_safe_dict(_safe_dict(report.get("inventaire")).get("pieces")).items(), key=lambda item: str(item[0])):
        raw_name = str(piece_key).split(".")[-1]
        component_name = (
            _safe_dict(payload).get("source_composant")
            or (str(piece_key).split(".", 1)[0] if "." in str(piece_key) else _safe_dict(payload).get("type"))
            or "systeme"
        )
        display_name = f"{str(component_name).replace('_', ' ').upper()} - {raw_name.replace('_', ' ').upper()}"
        generated_pieces.append(_export_piece_pdf_from_report(report, engine_params, str(piece_key), raw_name, display_name))

    for component_name in sorted(_safe_dict(_safe_dict(report.get("inventaire")).get("composants")).keys()):
        display_name = str(component_name).replace("_", " ").upper()
        generated_components.append(_export_component_pdf_from_report(report, engine_params, str(component_name), display_name))

    return {
        "pieces": generated_pieces,
        "components": generated_components,
        "root": _datasheet_root(),
    }


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

        # Mode carburant
        fuel_row = BoxLayout(size_hint_y=None, height=52, spacing=16)
        fuel_row.add_widget(Label(text="Mode carburant :", color=COLORS["GAXD"],
                                   font_size="14sp", size_hint_x=0.3))
        self._fuel_btns = {}
        self._selected_fuel = "multi_carburant"
        for fuel in ["multi_carburant"]:
            fb = ArchButton(fuel.upper(), font_size="14sp")
            fb.set_selected(True)
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
            "alesage_m": alesage_mm / 1000.0,
            "alesage_mm": alesage_mm,
            "course_m": course_mm / 1000.0,
            "course_mm": course_mm,
            "rpm_nominal": rpm,
            "pme_pa": pme_bar * 1e5,
            "pression_max_pa": p_max_bar * 1e5,
            "rendement_mecanique_cible_min": rend_meca,
            "carburant": None,
            "mode_carburant": self._selected_fuel,
            "carburants_autorises": ["diesel", "essence", "ethanol", "methanol", "gpl", "gnv", "hydrogene"],
            "architectures_autorisees": ["L", "V", "W", "Etoile", "Boxer"],
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

        arch = ep.get("architecture", "AUTO")
        ncyl = ep.get("nombre_cylindres", "--")
        alesage_m = ep.get("alesage_m", 0.130 if p_target >= 100 else 0.080)
        course_m = ep.get("course_m", 0.150 if p_target >= 100 else 0.090)
        rpm = ep.get("rpm_nominal", 1500.0)
        pme_pa = ep.get("pme_pa", 15.0e5)
        p_max_pa = ep.get("pression_max_pa", 8.0e6)
        carburant = ep.get("mode_carburant", "multi_carburant")

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
                carburants_autorises=ep.get("carburants_autorises"),
                mode_carburant=ep.get("mode_carburant"),
                moteur_thermique_definition={
                    "temps_moteur": ep.get("temps_moteur", 4),
                    "alesage_m": alesage_m,
                    "course_m": course_m,
                    "rpm_nominal": rpm,
                    "pme_pa": pme_pa,
                    "pression_max_pa": p_max_pa,
                    "carburants_autorises": ep.get("carburants_autorises"),
                    "mode_carburant": ep.get("mode_carburant"),
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
        for txt, screen in [("LISTE PIÈCES", "piece_library"), ("CROQUIS 2D", "advanced_visuals"),
                             ("VUE VECT.", "vector_view"), ("DOSSIER PDF", "pdf_folder"), 
                             ("FICHE DÉTAIL", "detailed_datasheet")]:
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
        optimisation = _safe_dict(report.get("optimisation"))
        opt_syn = _safe_dict(optimisation.get("synthese_optimisation"))
        if score is None:
            score = opt_syn.get("score_coherence_100")
        if not nb_al:
            nb_al = opt_syn.get("nombre_alertes", 0)
        if not nb_inc:
            nb_inc = opt_syn.get("nombre_inconnues", 0)
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
        except Exception as e:
            self.graph_box.add_widget(Label(text=f"Erreur rendu: {e}", color=COLORS["RF"]))


class AdvancedVisualsScreen(Screen):
    """Écran exploitant les nouveaux croquis 2D spécialisés du backend."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical", padding=20, spacing=15)
        
        # Header
        top = BoxLayout(size_hint_y=None, height=60, spacing=10)
        top.add_widget(Label(text="INGÉNIERIE DÉTAILLÉE (2D SKETCHES)", font_size="20sp",
                             bold=True, color=COLORS["BF"]))
        export = ModernButton(text="PDF", size_hint_x=None, width=120)
        export.bind(on_press=lambda *_: self.export_current_view_pdf())
        top.add_widget(export)
        back = ModernButton(text="RETOUR", size_hint_x=None, width=140)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "dashboard"))
        top.add_widget(back)
        self.layout.add_widget(top)
        
        # Sélecteur de vue
        self.nav = BoxLayout(size_hint_y=None, height=50, spacing=10)
        self.view_btns = {}
        for view in ["Architecture", "Alternateur", "Batterie"]:
            btn = ArchButton(view, font_size="14sp")
            btn.bind(on_press=lambda b, v=view: self.show_view(v))
            self.nav.add_widget(btn)
            self.view_btns[view] = btn
        self.layout.add_widget(self.nav)
        
        # Zone d'affichage
        self.display = PremiumCard(title="Vue technique")
        self.layout.add_widget(self.display)
        
        self.add_widget(self.layout)
        self.current_view = "Architecture"

    def on_enter(self, *args):
        self.show_view(self.current_view)

    def show_view(self, view_name: str):
        self.current_view = view_name
        for k, b in self.view_btns.items():
            b.set_selected(k == view_name)
            
        self.display.clear_widgets()
        app = App.get_running_app()
        ep = app.engine_params or {}
        report = _safe_dict(app.simulation_results)

        try:
            fig = None
            if view_name == "Architecture":
                mod = resolve_viz_module("architechture", "sketches_2d")
                arch_obj = get_piece_instance(
                    "architecture",
                    ep,
                    db_data=_current_component_payload(report, "architecture"),
                )
                if mod and arch_obj:
                    fig = mod.tracer_croquis_architecture_2d(arch_obj, titre="Configuration du Bloc Moteur")

            elif view_name == "Alternateur":
                mod = resolve_viz_module("alternateur", "sketches_2d")
                alt_obj = get_piece_instance(
                    "alternateur",
                    ep,
                    db_data=_current_component_payload(report, "alternateur"),
                )
                if mod and alt_obj:
                    fig = mod.tracer_croquis_alternateur_2d(alt_obj, titre="Coupe Stator/Rotor & Bilan Pertes")

            elif view_name == "Batterie":
                mod = resolve_viz_module("batterie", "sketches_2d")
                batt_obj = get_piece_instance(
                    "batterie",
                    ep,
                    db_data=_current_component_payload(report, "batterie"),
                )
                if mod and batt_obj:
                    fig = mod.tracer_croquis_batterie_2d(batt_obj, titre="Monitoring Pack Batterie (BMS/TMS)")

            if fig:
                self.display.add_widget(FigureCanvasKivyAgg(fig))
            else:
                self.display.add_widget(Label(text=f"Impossible d'instancier {view_name}", color=COLORS["RF"]))
                
        except Exception as e:
            self.display.add_widget(Label(text=f"Erreur : {e}\n{traceback.format_exc()}", 
                                          color=COLORS["RF"], font_size="12sp"))

    def export_current_view_pdf(self):
        app = App.get_running_app()
        report = _safe_dict(app.simulation_results)
        mapping = {
            "Architecture": ("architecture", "ARCHITECTURE"),
            "Alternateur": ("alternateur", "ALTERNATEUR"),
            "Batterie": ("batterie", "BATTERIE"),
        }
        component_name, display_name = mapping.get(self.current_view, ("architecture", self.current_view.upper()))
        try:
            pdf_path = _export_component_pdf_from_report(report, app.engine_params or {}, component_name, display_name)
            show_popup("PDF généré", f"Fiche créée :\n{pdf_path}")
        except Exception as exc:
            show_popup("Erreur PDF", str(exc))


class PdfFolderScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root = BoxLayout(orientation="vertical", padding=20, spacing=20)
        self.add_widget(self.root)

    def on_enter(self, *args):
        self.root.clear_widgets()
        app = App.get_running_app()
        top = BoxLayout(size_hint_y=None, height=60, spacing=10)
        top.add_widget(Label(text="DOSSIER DES FICHES PDF", font_size="22sp",
                             bold=True, color=COLORS["BF"]))
        export_all = ModernButton(text="GÉNÉRER TOUT", size_hint_x=None, width=180)
        export_all.bind(on_press=lambda *_: self.generate_all_pdfs(app))
        top.add_widget(export_all)
        back = ModernButton(text="RETOUR", size_hint_x=None, width=160)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "dashboard"))
        top.add_widget(back)
        self.root.add_widget(top)

        actions = BoxLayout(size_hint_y=None, height=52, spacing=10)
        open_root = ModernButton(text="OUVRIR DOSSIER", size_hint_x=None, width=180)
        open_root.bind(on_press=lambda *_: self.open_datasheet_root())
        actions.add_widget(open_root)
        gen_components = ModernButton(text="PDF COMPOSANTS", size_hint_x=None, width=180)
        gen_components.bind(on_press=lambda *_: self.generate_component_pdfs(app))
        actions.add_widget(gen_components)
        gen_pieces = ModernButton(text="PDF PIÈCES", size_hint_x=None, width=180)
        gen_pieces.bind(on_press=lambda *_: self.generate_piece_pdfs(app))
        actions.add_widget(gen_pieces)
        self.root.add_widget(actions)

        sc = ScrollView()
        grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        self._add_pdf_section(grid, "PIÈCES", _datasheet_root() / "pieces")
        self._add_pdf_section(grid, "COMPOSANTS", _datasheet_root() / "components")
        sc.add_widget(grid)
        self.root.add_widget(sc)

    def _add_pdf_section(self, parent, title: str, directory: Path):
        parent.add_widget(Label(text=title, color=COLORS["BF"], bold=True, size_hint_y=None, height=32))
        if directory.exists():
            files = sorted(f for f in directory.iterdir() if f.suffix.lower() == ".pdf")
            if files:
                for fp in files:
                    row = BoxLayout(size_hint_y=None, height=44, spacing=10)
                    row.add_widget(Label(text=fp.stem.upper(), color=COLORS["GAXD"]))
                    btn = ModernButton(text="OUVRIR", size_hint_x=None, width=140, font_size="13sp")
                    btn.bind(on_press=lambda *_, p=str(fp): os.startfile(p))
                    row.add_widget(btn)
                    parent.add_widget(row)
                return
        parent.add_widget(Label(text=f"Aucun PDF généré pour {title.lower()}.", color=COLORS["RF"], size_hint_y=None, height=30))

    def open_datasheet_root(self):
        root = _datasheet_root()
        root.mkdir(parents=True, exist_ok=True)
        os.startfile(str(root))

    def generate_piece_pdfs(self, app):
        report = _safe_dict(app.simulation_results)
        try:
            generated = []
            for piece_key, payload in sorted(_safe_dict(_safe_dict(report.get("inventaire")).get("pieces")).items(), key=lambda item: str(item[0])):
                raw_name = str(piece_key).split(".")[-1]
                component_name = (
                    _safe_dict(payload).get("source_composant")
                    or (str(piece_key).split(".", 1)[0] if "." in str(piece_key) else _safe_dict(payload).get("type"))
                    or "systeme"
                )
                display_name = f"{str(component_name).replace('_', ' ').upper()} - {raw_name.replace('_', ' ').upper()}"
                generated.append(_export_piece_pdf_from_report(report, app.engine_params or {}, str(piece_key), raw_name, display_name))
            show_popup("PDF générés", f"{len(generated)} fiches pièces générées.")
            self.on_enter()
        except Exception as exc:
            show_popup("Erreur PDF", str(exc))

    def generate_component_pdfs(self, app):
        report = _safe_dict(app.simulation_results)
        generated = []
        try:
            for component_name in sorted(_safe_dict(_safe_dict(report.get("inventaire")).get("composants")).keys()):
                display_name = str(component_name).replace("_", " ").upper()
                generated.append(_export_component_pdf_from_report(report, app.engine_params or {}, component_name, display_name))
            show_popup("PDF générés", f"{len(generated)} fiches composants générées.")
            self.on_enter()
        except Exception as exc:
            show_popup("Erreur PDF", str(exc))

    def generate_all_pdfs(self, app):
        report = _safe_dict(app.simulation_results)
        try:
            generated = _export_full_report_pdfs(report, app.engine_params or {})
            total = len(generated["pieces"]) + len(generated["components"])
            show_popup("PDF générés", f"{total} fiches générées dans :\n{generated['root']}")
            self.on_enter()
        except Exception as exc:
            show_popup("Erreur PDF", str(exc))


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
        entries = []
        app = App.get_running_app()
        report = _safe_dict(app.simulation_results)
        report_pieces = _safe_dict(_safe_dict(report.get("inventaire")).get("pieces"))
        if report_pieces:
            for piece_key, payload in sorted(report_pieces.items(), key=lambda item: str(item[0])):
                piece_data = _safe_dict(payload)
                component_name = (
                    piece_data.get("source_composant")
                    or (str(piece_key).split(".", 1)[0] if "." in str(piece_key) else piece_data.get("type"))
                    or "systeme"
                )
                raw_name = str(piece_key).split(".")[-1]
                entries.append({
                    "component": component_name,
                    "raw_name": raw_name,
                    "db_name": str(piece_key),
                    "display_name": f"{component_name.replace('_', ' ').upper()} - {raw_name.replace('_', ' ').upper()}",
                    "payload": piece_data,
                })
        else:
            components_root = os.path.join(BASE_DIR, "backend", "components")
            if not os.path.exists(components_root):
                self.grid.add_widget(Label(text=f"Dossier introuvable: {components_root}",
                                           color=COLORS["RF"]))
                return
            for component_name in sorted(os.listdir(components_root)):
                pieces_path = os.path.join(components_root, component_name, "pieces")
                if not os.path.isdir(pieces_path):
                    continue
                for f in sorted(f for f in os.listdir(pieces_path) if f.endswith(".py") and f != "__init__.py"):
                    raw_name = f[:-3]
                    entries.append({
                        "component": component_name,
                        "raw_name": raw_name,
                        "db_name": f"{component_name}.{raw_name}",
                        "display_name": f"{component_name.replace('_', ' ').upper()} - {raw_name.replace('_', ' ').upper()}",
                        "payload": {},
                    })
        if not entries:
            self.grid.add_widget(Label(text="Aucune pièce détectée dans backend/components.",
                                       color=COLORS["RF"]))
            return
        for entry in entries:
            card = PremiumCard(title=entry["display_name"], size_hint_y=None, height=120)
            stack = BoxLayout(orientation="vertical", spacing=8)
            status = _piece_backend_status(entry.get("payload"))
            stack.add_widget(Label(
                text=f"{status['label']} | {status['detail'][:54]}",
                color=status["color"],
                font_size="11sp",
                size_hint_y=None,
                height=30,
            ))
            btn = ModernButton(text="VOIR DÉTAILS", font_size="12sp",
                               size_hint_y=None, height=44)
            btn.bind(on_press=lambda _, e=entry: self.view_details(e["display_name"], e["raw_name"], e["db_name"], e["component"], e.get("payload")))
            stack.add_widget(btn)
            card.add_widget(stack)
            self.grid.add_widget(card)

    def view_details(self, display_name, raw_name, db_name, component_name, payload=None):
        app = App.get_running_app()
        app.selected_piece_display = display_name
        app.selected_piece_raw = raw_name
        app.selected_piece_db = db_name
        app.selected_piece_component = component_name
        app.selected_piece_payload = dict(payload or {})
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
        db_name = getattr(app, "selected_piece_db", raw_name)
        ep = app.engine_params or {}
        report = _safe_dict(app.simulation_results)
        selected_payload = _safe_dict(getattr(app, "selected_piece_payload", {}))

        top = BoxLayout(size_hint_y=None, height=62, spacing=10)
        title = Label(text=display_name, font_size="24sp", bold=True,
                      color=COLORS["BF"], halign="left", valign="middle")
        title.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        top.add_widget(title)
        export_btn = ModernButton(text="PDF", size_hint_x=None, width=120)
        export_btn.bind(on_press=lambda *_: self.export_piece_pdf())
        top.add_widget(export_btn)
        back = ModernButton(text="RETOUR LISTE", size_hint_x=None, width=180)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "piece_library"))
        top.add_widget(back)
        self.layout.add_widget(top)

        data = _merge_front_dicts(selected_payload, _current_piece_payload(report, db_name, raw_name))
        try:
            from backend.modules.systeme.database import SecureDatabase
            db = SecureDatabase(
                db_path=os.path.join(BASE_DIR, "backend", "shse_technical_data.db"))
            db_data = (
                db.get_piece_data(db_name)
                or db.get_piece_data(raw_name)
                or db.get_piece_data(raw_name.replace("_", ""))
            )
            if isinstance(db_data, dict):
                data = _merge_front_dicts(data, db_data)
        except Exception as ex:
            print(f"[PIECE_DETAIL DB] {ex}")

        status = _piece_backend_status(data)
        status_row = BoxLayout(size_hint_y=None, height=38, spacing=10)
        status_row.add_widget(Label(
            text=f"État backend : {status['label']} | {status['detail']}",
            color=status["color"],
            font_size="12sp",
            halign="left",
            valign="middle",
        ))
        self.layout.add_widget(status_row)

        # Instanciation et hydratation forcée
        p = get_piece_instance(raw_name, ep, db_data=data)
        
        if p is None:
            # Fallback minimal si l'instanciation échoue
            class PO: pass
            p = PO()
            p.nom = raw_name
            if isinstance(data, dict):
                for k, v in data.items():
                    try: setattr(p, k, v)
                    except Exception: pass

        # On s'assure que ep est aussi injecté (priorité basse)
        for k, v in ep.items():
            if not hasattr(p, k) or getattr(p, k) is None:
                try: setattr(p, k, v)
                except Exception: pass

        grid = GridLayout(cols=4, spacing=12)
        sketch_card = PremiumCard(title="Croquis 2D")
        radar_card = PremiumCard(title="Résistance Mécanique")
        view3d_card = PremiumCard(title="Vue 3D")
        data_card = PremiumCard(title="Données de dimensionnement")

        can_render_piece = bool(data.get("construit")) or p is not None

        if MATPLOTLIB_AVAILABLE and can_render_piece:
            # --- Croquis 2D ---
            try:
                fig2d = get_viz_figure(raw_name, p, "sketches_2d")
                if fig2d:
                    sketch_card.add_widget(FigureCanvasKivyAgg(fig2d))
                else:
                    raise ImportError("Module 2D non trouvé")
            except Exception as e:
                sketch_card.add_widget(Label(text=f"Croquis indisponible\n{str(e)[:80]}",
                                              color=COLORS["RF"], font_size="11sp"))

            # --- Radar Chart ---
            try:
                fig_r = get_viz_figure(raw_name, p, "charts")
                if fig_r:
                    radar_card.add_widget(FigureCanvasKivyAgg(fig_r))
                else:
                    raise ImportError("Module Charts non trouvé")
            except Exception as e:
                radar_card.add_widget(Label(text=f"Radar indisponible\n{str(e)[:80]}",
                                             color=COLORS["RF"], font_size="11sp"))

            # --- Vue 3D ---
            try:
                fig3d = get_viz_figure(raw_name, p, "views_3d")
                if fig3d:
                    view3d_card.add_widget(FigureCanvasKivyAgg(fig3d))
                else:
                    raise ImportError("Module 3D non trouvé")
            except Exception as e:
                view3d_card.add_widget(Label(text=f"Vue 3D indisponible\n{str(e)[:80]}",
                                              color=COLORS["RF"], font_size="11sp"))
        elif MATPLOTLIB_AVAILABLE:
            for card in (sketch_card, radar_card, view3d_card):
                card.add_widget(Label(text="Pièce non construite avec les données actuelles", color=COLORS["RF"]))
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

    def export_piece_pdf(self):
        app = App.get_running_app()
        report = _safe_dict(app.simulation_results)
        raw_name = getattr(app, "selected_piece_raw", "")
        db_name = getattr(app, "selected_piece_db", raw_name)
        display_name = getattr(app, "selected_piece_display", raw_name or "PIÈCE")
        try:
            pdf_path = _export_piece_pdf_from_report(report, app.engine_params or {}, db_name, raw_name, display_name)
            show_popup("PDF généré", f"Fiche créée :\n{pdf_path}")
        except Exception as exc:
            show_popup("Erreur PDF", str(exc))


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
    selected_piece_db = StringProperty("")
    selected_piece_component = StringProperty("")
    selected_piece_payload = DictProperty({})

    def on_start(self):
        # Chargement automatique de la dernière simulation au démarrage
        try:
            from backend.modules.systeme.database import SecureDatabase
            db = SecureDatabase(
                db_path=os.path.join(BASE_DIR, "backend", "shse_technical_data.db"),
                key_path=os.path.join(BASE_DIR, "backend", "secret.key")
            )
            # On cherche le dernier rapport sauvegardé (par défaut "latest" ou le dernier par date)
            records = db.list_records("main_report")
            if records:
                # Trier par date décroissante
                records.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
                latest_name = records[0]["name"]
                res = db.get_record("main_report", latest_name)
                if res:
                    self.simulation_results = res
                    self.current_report_name = latest_name
                    # Restauration des paramètres moteur si présents
                    if "entrees" in res:
                        self.engine_params = res["entrees"]
                        if "puissance_traction_kw" in res["entrees"]:
                            self.target_power = str(res["entrees"]["puissance_traction_kw"])
            print(f"[SHSEM_DB] Auto-load completed: {self.current_report_name}")
        except Exception as ex:
            print(f"[SHSEM_DB] Auto-load skipped: {ex}")

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
        sm.add_widget(AdvancedVisualsScreen(name="advanced_visuals"))
        return sm


if __name__ == "__main__":
    SHSEMApp().run()
