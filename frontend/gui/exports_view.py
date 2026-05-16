from __future__ import annotations

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import COLORS, EmptyState, MetricRow, ModernButton, NeoCard, SectionTitle, StatusBadge


class ExportsScreen(Screen):
    def on_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        app = App.get_running_app()
        exports = (app.ui_report or {}).get("exports") or []
        root = BoxLayout(orientation="vertical", padding=16, spacing=12)
        root.add_widget(self._top_bar())
        if not exports:
            root.add_widget(EmptyState(text="Exports indisponibles : aucun rapport backend."))
            self.add_widget(root)
            return
        scroll = ScrollView(do_scroll_x=False)
        grid = GridLayout(cols=2, spacing=12, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for item in exports:
            grid.add_widget(self._card(item))
        scroll.add_widget(grid)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=58, spacing=10)
        bar.add_widget(Label(text="EXPORTS", color=COLORS["BFW"], bold=True, font_size="19sp"))
        btn = ModernButton(text="DASHBOARD", size_hint_x=None, width=150)
        btn.bind(on_release=lambda *_: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn)
        return bar

    def _card(self, item: dict) -> NeoCard:
        card = NeoCard(orientation="vertical", size_hint_y=None, height=170)
        card.add_widget(SectionTitle(text=str(item.get("label", "EXPORT")).upper()))
        card.add_widget(StatusBadge(status=item.get("status", "indisponible"), size_hint_y=None, height=28))
        card.add_widget(MetricRow("Disponible", "Oui" if item.get("available") else "Non"))
        card.add_widget(MetricRow("Raison", item.get("reason") or ""))
        return card
