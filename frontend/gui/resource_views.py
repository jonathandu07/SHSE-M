# frontend\gui\resource_views.py
from __future__ import annotations

from typing import Any

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import (
    COLORS,
    EmptyState,
    ModernButton,
    ResourceCard,
)


class ResourceListScreen(Screen):
    resource_key = ""
    title = ""
    empty_text = "Ressource indisponible."

    def on_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        app = App.get_running_app()
        ui = dict(app.ui_report or {})
        resources = ui.get(self.resource_key) or []
        
        root = BoxLayout(orientation="vertical", padding=12, spacing=10)
        root.add_widget(self._top_bar())
        
        if not resources:
            root.add_widget(EmptyState(text=self.empty_text))
            self.add_widget(root)
            return
            
        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        grid = GridLayout(cols=1, spacing=12, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        
        for item in resources:
            card = ResourceCard(
                name=item.get("name", "Ressource"),
                rtype=item.get("type", "Document"),
                subsystem=item.get("subsystem", "Général"),
                status=item.get("status", "indisponible")
            )
            grid.add_widget(card)
            
        scroll.add_widget(grid)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=54, spacing=10, padding=[10, 5])
        lbl = Label(text=self.title.upper(), color=COLORS["BFW"], bold=True, font_size="16sp", halign="left")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)
        
        btn = ModernButton(text="RETOUR DASHBOARD", size_hint_x=None, width=180, font_size="11sp")
        btn.bind(on_release=lambda *_: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn)
        return bar


class SketchesScreen(ResourceListScreen):
    resource_key = "sketches"
    title = "CROQUIS D'INGÉNIERIE"
    empty_text = "AUCUN CROQUIS DISPONIBLE"


class ChartsScreen(ResourceListScreen):
    resource_key = "charts"
    title = "GRAPHES DE PERFORMANCE"
    empty_text = "DONNÉES DE PERFORMANCE INSUFFISANTES"


class ThreeDScreen(ResourceListScreen):
    resource_key = "three_d"
    title = "MODÈLES NUMÉRIQUES 3D"
    empty_text = "FICHIEURS CAO NON GÉNÉRÉS"
