from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = Path(__file__).resolve().parent
for path in (BASE_DIR, FRONTEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

KIVY_HOME = BASE_DIR / ".kivy"
KIVY_HOME.mkdir(exist_ok=True)
os.environ.setdefault("KIVY_HOME", str(KIVY_HOME))

from kivy.config import Config

Config.set("input", "mouse", "mouse,disable_multitouch")
Config.set("graphics", "resizable", "1")

from kivy.app import App
from kivy.core.window import Window
from kivy.properties import DictProperty
from kivy.uix.screenmanager import FadeTransition, ScreenManager

from frontend.gui.architecture_choice import ArchitectureChoiceScreen
from frontend.gui.charts_view import ChartsScreen
from frontend.gui.components import COLORS
from frontend.gui.dashboard import DashboardScreen
from frontend.gui.edit_parameters import EditParametersScreen
from frontend.gui.error_view import ErrorScreen
from frontend.gui.exports_view import ExportsScreen
from frontend.gui.home import HomeScreen
from frontend.gui.loading import LoadingScreen
from frontend.gui.pieces_view import PieceDetailScreen, PieceLibraryScreen
from frontend.gui.raw_report_view import RawJsonScreen
from frontend.gui.sketches_view import SketchesScreen
from frontend.gui.system_data import SystemDataScreen
from frontend.gui.three_d_view import ThreeDScreen


PROJECT_NAME = "STHOME"


def _missing_requirements(report: dict) -> list[dict]:
    """Compatibilite GUI: extrait les inconnues critiques du rapport backend."""
    if not isinstance(report, dict):
        return []

    labels = {
        "regime_tr_min": "RPM nominal",
        "rpm_nominal": "RPM nominal",
        "rpm": "RPM nominal",
        "pme_pa": "PME",
        "pme": "PME",
        "gabarit (l/w)": "gabarit L/W",
        "gabarit_l_w": "gabarit L/W",
    }

    out = []
    arch = (
        report.get("analyses_composants", {})
        .get("architecture", {})
        .get("inconnues", {})
    )
    for category in ("impossibles", "partielles"):
        items = arch.get(category, []) if isinstance(arch, dict) else []
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                raw_name = str(item.get("nom", item.get("champ", "INCONNU")))
                reason = str(item.get("raison", item.get("detail", "")))
            else:
                raw_name = str(item)
                reason = ""
            normalized = raw_name.strip().lower()
            out.append(
                {
                    "name": labels.get(normalized, raw_name),
                    "raw_name": raw_name,
                    "reason": reason,
                    "category": category,
                }
            )
    return out


def _fuel_summary(report: dict) -> dict:
    """Compatibilite GUI: resume le bloc multi-carburant sans valeur inventee."""
    if not isinstance(report, dict):
        return {"mode": None, "worst": None, "best": None}
    block = (
        report.get("analyses_composants", {})
        .get("moteur_thermique_bilan_carburant", {})
    )
    if not isinstance(block, dict):
        block = {}
    return {
        "mode": block.get("mode"),
        "worst": block.get("carburant_dimensionnant"),
        "best": block.get("carburant_optimal"),
    }


class STHOMEApp(App):
    title = PROJECT_NAME

    raw_backend_report = DictProperty({})
    ui_report = DictProperty({})
    engine_params = DictProperty({})
    selected_piece = DictProperty({})

    def build(self):
        Window.clearcolor = COLORS["BL"]
        Window.size = (1440, 900)
        manager = ScreenManager(transition=FadeTransition())
        manager.add_widget(HomeScreen(name="home"))
        manager.add_widget(LoadingScreen(name="loading"))
        manager.add_widget(DashboardScreen(name="dashboard"))
        manager.add_widget(ArchitectureChoiceScreen(name="architecture_choice"))
        manager.add_widget(SystemDataScreen(name="system_data"))
        manager.add_widget(PieceLibraryScreen(name="piece_library"))
        manager.add_widget(PieceDetailScreen(name="piece_detail"))
        manager.add_widget(SketchesScreen(name="sketches"))
        manager.add_widget(ChartsScreen(name="charts"))
        manager.add_widget(ThreeDScreen(name="three_d"))
        manager.add_widget(RawJsonScreen(name="raw_json"))
        manager.add_widget(ExportsScreen(name="exports"))
        manager.add_widget(EditParametersScreen(name="edit_parameters"))
        manager.add_widget(ErrorScreen(name="error"))
        return manager


SHSEMApp = STHOMEApp


if __name__ == "__main__":
    STHOMEApp().run()
