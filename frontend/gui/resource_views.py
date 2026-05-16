from __future__ import annotations

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import COLORS, EmptyState, MetricRow, ModernButton, NeoCard, SectionTitle, StatusBadge


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
        root = BoxLayout(orientation="vertical", padding=16, spacing=12)
        root.add_widget(self._top_bar())
        if not resources:
            root.add_widget(EmptyState(text=self.empty_text))
            self.add_widget(root)
            return
        scroll = ScrollView(do_scroll_x=False)
        grid = GridLayout(cols=2, spacing=12, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for item in resources:
            grid.add_widget(self._resource_card(item))
        scroll.add_widget(grid)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=58, spacing=10)
        bar.add_widget(Label(text=self.title, color=COLORS["BFW"], bold=True, font_size="19sp"))
        btn = ModernButton(text="DASHBOARD", size_hint_x=None, width=150)
        btn.bind(on_release=lambda *_: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn)
        return bar

    def _resource_card(self, item: dict) -> NeoCard:
        card = NeoCard(orientation="vertical", size_hint_y=None, height=180)
        card.add_widget(SectionTitle(text=str(item.get("name", "RESSOURCE")).upper()))
        card.add_widget(StatusBadge(status=item.get("status", "indisponible"), size_hint_y=None, height=28))
        card.add_widget(MetricRow("Type", item.get("type")))
        card.add_widget(MetricRow("Module", item.get("path")))
        card.add_widget(MetricRow("Raison", item.get("reason")))
        return card


class SketchesScreen(ResourceListScreen):
    resource_key = "sketches"
    title = "CROQUIS DISPONIBLES"
    empty_text = "Croquis indisponibles : aucun module ou rapport exploitable fourni."


class ChartsScreen(ResourceListScreen):
    resource_key = "charts"
    title = "GRAPHIQUES DISPONIBLES"
    empty_text = "Graphiques indisponibles : le backend n'a pas fourni les données nécessaires."


class ThreeDScreen(ResourceListScreen):
    resource_key = "three_d"
    title = "RESSOURCES 3D"
    empty_text = "3D indisponible : aucun fichier ou rapport exploitable fourni."
