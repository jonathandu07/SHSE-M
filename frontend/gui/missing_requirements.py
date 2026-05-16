from __future__ import annotations

from typing import Any

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import (
    COLORS,
    EmptyState,
    FilterChips,
    ModernButton,
    RequirementCard,
    SearchBar,
    SectionTitle,
    GhostButton,
)


class MissingRequirementsScreen(Screen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.search_query = ""
        self.active_filter = "Tous"

    def on_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        app = App.get_running_app()
        ui = dict(app.ui_report or {})
        missing = ui.get("missing_requirements", [])
        
        root = BoxLayout(orientation="vertical", padding=12, spacing=10)
        root.add_widget(self._top_bar())

        if not missing:
            root.add_widget(EmptyState(text="SYSTÈME COMPLET", action_text="RETOUR DASHBOARD", callback=lambda _: setattr(self.manager, "current", "dashboard")))
            self.add_widget(root)
            return

        # Filters and Search
        subsystems = list(set(item.get("subsystem", "Général") for item in missing))
        controls = BoxLayout(orientation="vertical", size_hint_y=None, height=90, spacing=5)
        controls.add_widget(SearchBar(callback=self._on_search))
        controls.add_widget(FilterChips(filters=subsystems, callback=self._on_filter))
        root.add_widget(controls)

        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        self.content = BoxLayout(orientation="vertical", spacing=12, size_hint_y=None, padding=[4, 10])
        self.content.bind(minimum_height=self.content.setter("height"))

        self._populate_items(missing)

        scroll.add_widget(self.content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _populate_items(self, items: list[dict]) -> None:
        self.content.clear_widgets()
        
        filtered = [
            item for item in items 
            if (self.active_filter == "Tous" or item.get("subsystem") == self.active_filter) and
               (self.search_query.lower() in item.get("name", "").lower() or self.search_query.lower() in item.get("reason", "").lower())
        ]
        
        if not filtered:
            self.content.add_widget(Label(text="Aucun résultat pour ces filtres.", color=COLORS["GS"]))
            return

        for item in filtered[:20]:
            card = RequirementCard(
                name=item.get("name", "Inconnu"),
                subsystem=item.get("subsystem", "Général"),
                priority=item.get("priority", "partiel"),
                reason=item.get("reason", "Donnée nécessaire pour fermer le calcul."),
            )
            # Find the RESOLVE button in the card
            # In RequirementCard, it's a GhostButton inside a BoxLayout
            self._bind_resolve_btn(card, item)
            self.content.add_widget(card)
        
        if len(filtered) > 20:
            self.content.add_widget(Label(text=f"... et {len(filtered)-20} autres éléments. Affinez la recherche.", color=COLORS["GS"], font_size="11sp"))

    def _bind_resolve_btn(self, card: RequirementCard, item: dict) -> None:
        for child in card.children:
            if isinstance(child, BoxLayout):
                for sub in child.children:
                    if isinstance(sub, GhostButton) and sub.text == "RÉSOUDRE":
                        sub.bind(on_release=lambda _, t=item: self._on_resolve(t))

    def _on_search(self, query: str) -> None:
        self.search_query = query
        app = App.get_running_app()
        self._populate_items(app.ui_report.get("missing_requirements", []))

    def _on_filter(self, filter_name: str) -> None:
        self.active_filter = filter_name
        app = App.get_running_app()
        self._populate_items(app.ui_report.get("missing_requirements", []))

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=54, spacing=10, padding=[10, 5])
        lbl = Label(text="DONNÉES À COMPLÉTER", color=COLORS["RS"], bold=True, font_size="16sp", halign="left")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)
        
        btn_back = ModernButton(text="RETOUR DASHBOARD", size_hint_x=None, width=180, font_size="11sp")
        btn_back.bind(on_release=lambda _: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn_back)
        return bar

    def _on_resolve(self, item: dict) -> None:
        self.manager.current = "edit_parameters"
