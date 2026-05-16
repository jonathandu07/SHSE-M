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
    EmptyState,
    ModernButton,
    PremiumCard,
    SectionTitle,
)


class MissingRequirementsScreen(Screen):
    """
    Écran centralisant tous les manques critiques identifiés par le backend.
    Enforce la doctrine "Zero-Invention" en traitant les inconnues comme des actions à accomplir.
    """
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
            root.add_widget(EmptyState(text="Calcul système fermé : toutes les données critiques sont complètes."))
            self.add_widget(root)
            return

        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        content = BoxLayout(orientation="vertical", spacing=20, size_hint_y=None, padding=[0, 10])
        content.bind(minimum_height=content.setter("height"))

        # Groupement par sous-système pour la clarté
        groups = {}
        for item in missing:
            sub = item.get("subsystem", "Général")
            if sub not in groups:
                groups[sub] = []
            groups[sub].append(item)

        for sub, items in groups.items():
            content.add_widget(SectionTitle(text=f"ORIENTATION : {sub.upper()}", font_size="13sp"))
            
            grid = GridLayout(cols=2, spacing=16, size_hint_y=None)
            grid.bind(minimum_height=grid.setter("height"))
            
            for item in items:
                card = ActionCard(
                    title=item.get("name", "Donnée inconnue"),
                    detail=f"RAISON : {item.get('reason', 'Indisponible')}\n"
                           f"PATH ATTENDU : {item.get('raw_path', 'N/A')}",
                    action_text="RÉSOUDRE",
                    callback=lambda _, t=item: self._on_resolve(t)
                )
                grid.add_widget(card)
            content.add_widget(grid)

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=50, spacing=10)
        lbl = Label(text="DONNÉES À COMPLÉTER / MANQUES BACKEND", color=COLORS["RS"], bold=True, font_size="18sp", halign="left")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)
        
        btn_back = ModernButton(text="RETOUR DASHBOARD", size_hint_x=None, width=200, font_size="12sp")
        btn_back.bind(on_release=lambda _: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn_back)
        
        return bar

    def _on_resolve(self, item: dict) -> None:
        """Redirige l'utilisateur vers l'écran d'édition pour combler le manque."""
        self.manager.current = "edit_parameters"
