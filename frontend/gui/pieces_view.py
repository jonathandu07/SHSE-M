from __future__ import annotations

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import COLORS, EmptyState, MetricRow, ModernButton, NeoCard, SectionTitle, StatusBadge
from frontend.gui.report_adapter import extract_piece_list


class PieceLibraryScreen(Screen):
    def on_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        app = App.get_running_app()
        pieces = extract_piece_list(dict(app.raw_backend_report or {}))
        root = BoxLayout(orientation="vertical", padding=16, spacing=12)
        root.add_widget(self._top_bar())
        if not pieces:
            root.add_widget(EmptyState(text="Pièces indisponibles : le backend n'a pas fourni de bibliothèque."))
            self.add_widget(root)
            return
        scroll = ScrollView(do_scroll_x=False)
        grid = GridLayout(cols=3, spacing=12, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for piece in pieces:
            grid.add_widget(self._piece_card(piece))
        scroll.add_widget(grid)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=58, spacing=10)
        bar.add_widget(Label(text="BIBLIOTHÈQUE DES PIÈCES", color=COLORS["BFW"], bold=True, font_size="19sp"))
        btn = ModernButton(text="DASHBOARD", size_hint_x=None, width=150)
        btn.bind(on_release=lambda *_: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn)
        return bar

    def _piece_card(self, piece: dict) -> NeoCard:
        card = NeoCard(orientation="vertical", size_hint_y=None, height=230)
        card.add_widget(SectionTitle(text=piece.get("name", "PIÈCE").upper()))
        card.add_widget(StatusBadge(status=piece.get("status", "inconnu"), size_hint_y=None, height=28))
        card.add_widget(MetricRow("Type", piece.get("type")))
        card.add_widget(MetricRow("Matériau", piece.get("material")))
        card.add_widget(MetricRow("Dimensions", len(piece.get("dimensions") or {})))
        card.add_widget(MetricRow("Inconnues", len(piece.get("unknowns") or {})))
        btn = ModernButton(text="DÉTAIL", size_hint_y=None, height=40)
        btn.bind(on_release=lambda *_: self._open_detail(piece))
        card.add_widget(btn)
        return card

    def _open_detail(self, piece: dict) -> None:
        app = App.get_running_app()
        app.selected_piece = piece
        self.manager.current = "piece_detail"


class PieceDetailScreen(Screen):
    def on_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        app = App.get_running_app()
        piece = dict(app.selected_piece or {})
        root = BoxLayout(orientation="vertical", padding=16, spacing=12)
        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=58, spacing=10)
        top.add_widget(Label(text=str(piece.get("name", "PIÈCE")).upper(), color=COLORS["BFW"], bold=True, font_size="19sp"))
        for text, target in (("PDF", "exports"), ("RETOUR", "piece_library")):
            btn = ModernButton(text=text, size_hint_x=None, width=130)
            btn.bind(on_release=lambda _, t=target: setattr(self.manager, "current", t))
            top.add_widget(btn)
        root.add_widget(top)
        if not piece:
            root.add_widget(EmptyState(text="Aucune pièce sélectionnée."))
            self.add_widget(root)
            return
        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(orientation="vertical", spacing=12, size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        content.add_widget(self._section("Synthèse", {"type": piece.get("type"), "statut": piece.get("status"), "materiau": piece.get("material")}))
        content.add_widget(self._section("Dimensions", piece.get("dimensions") or {}))
        content.add_widget(self._section("Contraintes", piece.get("constraints") or {}))
        content.add_widget(self._section("Inconnues", {u.get("name"): u.get("reason") for u in piece.get("unknowns", [])}))
        content.add_widget(self._section("Données complètes", piece.get("data") or {}))
        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _section(self, title: str, data: dict) -> NeoCard:
        card = NeoCard(orientation="vertical", size_hint_y=None)
        card.add_widget(SectionTitle(text=title.upper()))
        if not data:
            card.add_widget(EmptyState(text="INDISPONIBLE"))
        else:
            count = 0
            for key, value in data.items():
                if count >= 40:
                    card.add_widget(MetricRow("Suite", "voir JSON brut"))
                    break
                card.add_widget(MetricRow(str(key), value))
                count += 1
        card.height = max(120, 44 + min(40, max(1, len(data))) * 36)
        return card
