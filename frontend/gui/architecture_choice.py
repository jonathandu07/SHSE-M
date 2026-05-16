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
        report = dict(app.raw_backend_report or {})
        candidates = extract_architecture_candidates(report)
        root = BoxLayout(orientation="vertical", padding=16, spacing=12)
        root.add_widget(self._top_bar())
        if not candidates:
            root.add_widget(EmptyState(text="Architecture indisponible : le backend n'a pas fourni de candidats."))
            self.add_widget(root)
            return

        scroll = ScrollView(do_scroll_x=False)
        grid = GridLayout(cols=2, spacing=12, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for cand in candidates:
            grid.add_widget(self._candidate_card(cand))
        scroll.add_widget(grid)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=58, spacing=10)
        bar.add_widget(Label(text="ARCHITECTURES PROPOSÉES PAR LE BACKEND", color=COLORS["BFW"], bold=True, font_size="19sp"))
        btn = ModernButton(text="DASHBOARD", size_hint_x=None, width=150)
        btn.bind(on_release=lambda *_: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn)
        return bar

    def _candidate_card(self, cand: dict) -> NeoCard:
        arch = cand.get("architecture") or cand.get("Architecture") or cand.get("nom") or "INCONNU"
        card = NeoCard(orientation="vertical", size_hint_y=None, height=260)
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=38)
        header.add_widget(SectionTitle(text=str(arch)))
        header.add_widget(StatusBadge(status=str(cand.get("statut") or cand.get("status") or "calculée"), size_hint_x=None, width=130))
        card.add_widget(header)
        for label, key in (
            ("Type", "type"),
            ("Cylindres", "nombre_cylindres"),
            ("Score", "score"),
            ("Alésage", "alesage_m"),
            ("Course", "course_m"),
            ("Source", "source"),
        ):
            card.add_widget(MetricRow(label, cand.get(key) or cand.get(key.capitalize())))
        btn = ModernButton(text="CHOISIR ET RECALCULER", size_hint_y=None, height=44)
        btn.bind(on_release=lambda *_: self._choose(arch))
        card.add_widget(btn)
        return card

    def _choose(self, arch: str) -> None:
        if not arch or arch == "INCONNU":
            return
        app = App.get_running_app()
        params = dict(app.engine_params or {})
        params["architecture"] = arch
        app.engine_params = params
        self.manager.current = "loading"
