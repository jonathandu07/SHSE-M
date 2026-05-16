from __future__ import annotations

import json
from pathlib import Path

from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

from frontend.gui.components import COLORS, JsonViewer, ModernButton
from frontend.gui.report_adapter import save_json_report


class RawJsonScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.viewer = JsonViewer()
        root = BoxLayout(orientation="vertical", padding=16, spacing=12)
        root.add_widget(self._top_bar())
        root.add_widget(self.viewer)
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=50, spacing=10)
        lbl = Label(text="EXPLORATEUR DE DONNÉES BRUTES (JSON)", color=COLORS["BFW"], bold=True, font_size="18sp", halign="left")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)
        
        for text, cb in (("COPIER", self.copy_json), ("SAUVEGARDER", self.save_json), ("RETOUR", self.go_dashboard)):
            btn = ModernButton(text=text, size_hint_x=None, width=120, font_size="11sp")
            btn.bind(on_release=cb)
            bar.add_widget(btn)
        return bar

    def on_enter(self, *_):
        app = App.get_running_app()
        report = app.raw_backend_report or {}
        # Ensure pretty print and Courier font (handled in component)
        self.viewer.text_input.text = json.dumps(report, ensure_ascii=False, indent=2) if report else "Aucun rapport disponible."

    def copy_json(self, *_):
        Clipboard.copy(self.viewer.text_input.text)

    def save_json(self, *_):
        app = App.get_running_app()
        if not app.raw_backend_report:
            return
        save_json_report(dict(app.raw_backend_report), Path("output") / "last_frontend_report.json")

    def go_dashboard(self, *_):
        self.manager.current = "dashboard"


RawReportViewScreen = RawJsonScreen
