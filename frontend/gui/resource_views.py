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
        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        grid = GridLayout(cols=2, spacing=16, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for item in resources:
            grid.add_widget(self._resource_card(item))
        scroll.add_widget(grid)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=50, spacing=10)
        lbl = Label(text=self.title, color=COLORS["BFW"], bold=True, font_size="18sp", halign="left")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)
        
        btn = ModernButton(text="RETOUR DASHBOARD", size_hint_x=None, width=200, font_size="12sp")
        btn.bind(on_release=lambda *_: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn)
        return bar

    def _resource_card(self, item: dict) -> NeoCard:
        card = NeoCard(orientation="vertical", size_hint_y=None, height=200, spacing=8)
        card.add_widget(SectionTitle(text=str(item.get("name", "RESSOURCE")).upper()))
        card.add_widget(StatusBadge(status=item.get("status", "indisponible")))
        
        path = str(item.get("path", "Non spécifié"))
        if len(path) > 40:
            path = "..." + path[-37:]
            
        card.add_widget(MetricRow("Type / Source", item.get("type", "?")))
        card.add_widget(MetricRow("Localisation", path))
        
        reason = item.get("reason", "")
        if reason:
            lbl = Label(text=f"Note: {reason}", color=COLORS["RS"], font_size="10sp", halign="left", size_hint_y=None, height=20)
            lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
            card.add_widget(lbl)
            
        btn = ModernButton(text="OUVRIR LA RESSOURCE", size_hint_y=None, height=40, font_size="11sp")
        btn.disabled = item.get("status") != "disponible"
        card.add_widget(btn)
        return card


class SketchesScreen(ResourceListScreen):
    resource_key = "sketches"
    title = "CROQUIS D'INGÉNIERIE 2D"
    empty_text = "Aucun croquis disponible pour cette configuration."


class ChartsScreen(ResourceListScreen):
    resource_key = "charts"
    title = "GRAPHES DE PERFORMANCE"
    empty_text = "Données de performance insuffisantes pour générer des graphes."


class ThreeDScreen(ResourceListScreen):
    resource_key = "three_d"
    title = "MODÈLES NUMÉRIQUES 3D"
    empty_text = "Fichiers CAO non générés ou indisponibles."
