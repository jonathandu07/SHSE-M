from __future__ import annotations

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import COLORS, EmptyState, MetricRow, ModernButton, NeoCard, SectionTitle


class SystemDataScreen(Screen):
    def on_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        app = App.get_running_app()
        ui = dict(app.ui_report or {})
        root = BoxLayout(orientation="vertical", padding=16, spacing=12)
        root.add_widget(self._top_bar())
        tree = ui.get("data_tree") or []
        if not tree:
            root.add_widget(EmptyState(text="Données système indisponibles."))
            self.add_widget(root)
            return
        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(orientation="vertical", spacing=12, size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        for section in tree:
            content.add_widget(self._section_card(section))
        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=58, spacing=10)
        bar.add_widget(Label(text="DONNÉES TECHNIQUES COMPLÈTES", color=COLORS["BFW"], bold=True, font_size="19sp"))
        btn = ModernButton(text="DASHBOARD", size_hint_x=None, width=150)
        btn.bind(on_release=lambda *_: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn)
        return bar

    def _section_card(self, section: dict) -> NeoCard:
        value = section.get("value")
        card = NeoCard(orientation="vertical", size_hint_y=None)
        card.add_widget(SectionTitle(text=str(section.get("name", "section")).upper()))
        card.add_widget(MetricRow("Statut", section.get("status"), source=section.get("source") or ""))
        if isinstance(value, dict):
            for idx, (key, val) in enumerate(value.items()):
                if idx >= 30:
                    card.add_widget(MetricRow("Suite", "voir JSON brut"))
                    break
                card.add_widget(MetricRow(str(key), val))
            rows = min(len(value), 30) + 2
        elif isinstance(value, list):
            card.add_widget(MetricRow("Nombre", len(value)))
            rows = 3
        else:
            card.add_widget(MetricRow("Valeur", value))
            rows = 3
        card.height = max(120, rows * 36)
        return card
