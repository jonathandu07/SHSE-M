from __future__ import annotations

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import (
    COLORS,
    ActionCard,
    BentoGrid,
    EmptyState,
    KpiCard,
    MetricRow,
    ModernButton,
    PremiumCard,
    SectionTitle,
)


class MissingRequirementsScreen(Screen):
    def on_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        app = App.get_running_app()
        ui = dict(app.ui_report or {})
        missing = ui.get("missing_requirements", [])
        
        root = BoxLayout(orientation="vertical", padding=16, spacing=12)
        root.add_widget(self._top_bar())

        if not missing:
            root.add_widget(EmptyState(text="Toutes les données techniques sont complètes."))
            self.add_widget(root)
            return

        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(orientation="vertical", spacing=20, size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        # Group missing by subsystem or type
        groups = {}
        for item in missing:
            sub = item.get("subsystem", "Général")
            if sub not in groups:
                groups[sub] = []
            groups[sub].append(item)

        for sub, items in groups.items():
            content.add_widget(SectionTitle(text=f"SOUS-SYSTÈME : {sub.upper()}", height=40))
            
            grid = GridLayout(cols=2, spacing=12, size_hint_y=None)
            grid.bind(minimum_height=grid.setter("height"))
            
            for item in items:
                card = ActionCard(
                    title=item.get("label", "Donnée inconnue"),
                    detail=f"Raison : {item.get('missing_reason', 'Indisponible')}\n"
                           f"Source attendue : {item.get('source_expected', 'Backend path')}\n"
                           f"Chemins testés : {', '.join(item.get('candidates', []))}",
                    action_text="COMPLÉTER",
                    callback=lambda _, t=item: self._on_complete(t)
                )
                grid.add_widget(card)
            content.add_widget(grid)

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=58, spacing=10)
        bar.add_widget(Label(text="DONNÉES À COMPLÉTER", color=COLORS["BFW"], bold=True, font_size="20sp", halign="left"))
        
        btn_back = ModernButton(text="RETOUR DASHBOARD", size_hint_x=None, width=200)
        btn_back.bind(on_release=lambda _: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn_back)
        
        btn_home = ModernButton(text="ACCUEIL", size_hint_x=None, width=120)
        btn_home.bind(on_release=lambda _: setattr(self.manager, "current", "home"))
        bar.add_widget(btn_home)
        
        return bar

    def _on_complete(self, item: dict) -> None:
        # For now, redirect to edit parameters
        app = App.get_running_app()
        # We could pre-fill or focus on the key if possible
        self.manager.current = "edit_parameters"
