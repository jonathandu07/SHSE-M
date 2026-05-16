from __future__ import annotations

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import COLORS, EmptyState, MetricRow, ModernButton, NeoCard, SectionTitle, StatusBadge
from frontend.gui.report_adapter import extract_architecture_candidates


class ArchitectureChoiceScreen(Screen):
    def on_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        app = App.get_running_app()
        ui = dict(app.ui_report or {})
        candidates = ui.get("architecture_candidates") or []
        
        root = BoxLayout(orientation="vertical", padding=16, spacing=12)
        root.add_widget(self._top_bar())
        
        if not candidates:
            # Check why it's missing
            missing = [m for m in ui.get("missing_requirements", []) if "arch" in str(m.get("label")).lower()]
            reason = "Le backend n'a pas pu générer de candidats car des données critiques sont manquantes."
            
            panel = PremiumCard(title="ARCHITECTURE INDISPONIBLE")
            panel.add_widget(EmptyState(text=reason))
            if missing:
                panel.add_widget(SectionTitle(text="Données nécessaires :", font_size="12sp"))
                for m in missing:
                    panel.add_widget(MetricRow(m["label"], "MANQUANT", status="missing"))
            
            btn = ModernButton(text="COMPLÉTER LES DONNÉES ARCHITECTURE", size_hint_y=None, height=44)
            btn.bind(on_release=lambda _: setattr(self.manager, "current", "edit_parameters"))
            panel.add_widget(btn)
            root.add_widget(panel)
        else:
            scroll = ScrollView(do_scroll_x=False)
            grid = GridLayout(cols=2, spacing=16, size_hint_y=None)
            grid.bind(minimum_height=grid.setter("height"))
            for cand in candidates:
                grid.add_widget(self._candidate_card(cand))
            scroll.add_widget(grid)
            root.add_widget(scroll)
            
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=50, spacing=10)
        lbl = Label(text="SÉLECTION D'ARCHITECTURE SYSTÈME", color=COLORS["BFW"], bold=True, font_size="18sp", halign="left")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)
        
        btn = ModernButton(text="RETOUR DASHBOARD", size_hint_x=None, width=200, font_size="12sp")
        btn.bind(on_release=lambda *_: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn)
        return bar

    def _candidate_card(self, cand: dict) -> NeoCard:
        arch = cand.get("architecture") or cand.get("Architecture") or cand.get("nom") or "INCONNU"
        card = NeoCard(orientation="vertical", size_hint_y=None, height=220, spacing=8)
        
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=30)
        header.add_widget(SectionTitle(text=str(arch)))
        header.add_widget(StatusBadge(status="disponible"))
        card.add_widget(header)
        
        desc = Label(text=str(cand.get("description", "Aucune description fournie")), color=COLORS["GS"], font_size="11sp", size_hint_y=None, height=30, halign="left")
        desc.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        card.add_widget(desc)

        card.add_widget(MetricRow("Score technique", cand.get("score", "?"), "/100"))
        
        btn = ModernButton(text="RETENIR CETTE ARCHITECTURE", size_hint_y=None, height=44, font_size="12sp")
        btn.bind(on_release=lambda *_: self._choose(arch))
        card.add_widget(btn)
        return card

    def _choose(self, arch: str) -> None:
        app = App.get_running_app()
        params = dict(app.engine_params or {})
        params["architecture"] = arch
        app.engine_params = params
        self.manager.current = "loading"
