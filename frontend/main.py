from __future__ import annotations

import os
import sys
from pathlib import Path
from functools import partial

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
from frontend.gui.energy_audit import EnergyAuditScreen
from frontend.gui.error_view import ErrorScreen
from frontend.gui.exports_view import ExportsScreen
from frontend.gui.home import HomeScreen
from frontend.gui.loading import LoadingScreen
from frontend.gui.missing_requirements import MissingRequirementsScreen
from frontend.gui.pieces_view import PieceDetailScreen, PieceLibraryScreen
from frontend.gui.raw_report_view import RawJsonScreen
from frontend.gui.sketches_view import SketchesScreen
from frontend.gui.three_d_view import ThreeDScreen


PROJECT_NAME = "STHOME"


class STHOMEApp(App):
    title = PROJECT_NAME

    raw_backend_report = DictProperty({})
    ui_report = DictProperty({})
    engine_params = DictProperty({})
    selected_piece = DictProperty({})

    def build(self):
        Window.clearcolor = COLORS["BL"]
        Window.size = (1440, 900)
        self.manager = ScreenManager(transition=FadeTransition())
        self.manager.add_widget(HomeScreen(name="home"))
        self.manager.add_widget(LoadingScreen(name="loading"))
        self.manager.add_widget(DashboardScreen(name="dashboard"))
        self.manager.add_widget(ArchitectureChoiceScreen(name="architecture_choice"))
        self.manager.add_widget(PieceLibraryScreen(name="piece_library"))
        self.manager.add_widget(PieceDetailScreen(name="piece_detail"))
        self.manager.add_widget(SketchesScreen(name="sketches"))
        self.manager.add_widget(ChartsScreen(name="charts"))
        self.manager.add_widget(ThreeDScreen(name="three_d"))
        manager_raw_json = RawJsonScreen(name="raw_json")
        self.manager.add_widget(manager_raw_json)
        self.manager.add_widget(ExportsScreen(name="exports"))
        self.manager.add_widget(EditParametersScreen(name="edit_parameters"))
        self.manager.add_widget(MissingRequirementsScreen(name="missing_requirements"))
        self.manager.add_widget(EnergyAuditScreen(name="energy_audit"))
        self.manager.add_widget(ErrorScreen(name="error"))
        
        # Auto-screenshot for audit if requested via env
        if os.environ.get("STHOME_AUDIT_MODE") == "1":
            from kivy.clock import Clock
            from functools import partial
            Clock.schedule_once(self._run_audit_sequence, 2)
            
        return self.manager

    def _run_audit_sequence(self, dt):
        from kivy.clock import Clock
        from frontend.gui.report_adapter import adapt_backend_report
        
        # Inject dummy data for visualization
        dummy_report = {
            "meta": {"nom_projet": "AUDIT COCKPIT"},
            "resume_gui": {"Architecture": "L4 Hybrid", "score_global_100": 85},
            "derivees_chaine_energie": {"details": {"p_traction_w": 125000, "p_bus_total": 130000}},
            "inconnues": {"critique": [{"nom": "Diamètre Arbre", "raison": "Non spécifié", "subsystem": "Transmission"}]},
            "systeme_complet": {"synthese": {"architectures_candidates": [{"nom": "L4 Hybrid", "score": 90}]}}
        }
        self.raw_backend_report = dummy_report
        self.ui_report = adapt_backend_report(dummy_report)
        
        screens = ["dashboard", "missing_requirements", "energy_audit", "architecture_choice", "edit_parameters", "raw_json"]
        self._screenshot_step(screens, 0)

    def _screenshot_step(self, screens, index):
        from kivy.clock import Clock
        if index >= len(screens):
            self.stop()
            return
            
        name = screens[index]
        self.manager.current = name
        
        def capture_and_next(name, idx, dt):
            import os
            cwd = os.getcwd()
            output_path = os.path.join(cwd, f"audit_{name}.png")
            Window.screenshot(output_path)
            print(f"Captured {output_path}")
            self._screenshot_step(screens, idx + 1)
            
        Clock.schedule_once(partial(capture_and_next, name, index), 1.5)


SHSEMApp = STHOMEApp


if __name__ == "__main__":
    STHOMEApp().run()
