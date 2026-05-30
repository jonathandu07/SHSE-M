"""
Chemin : frontend/gui/technical_visualization.py
But :
    Afficher le cockpit de visualisation technique construit par frontend/ensemble.
Pourquoi ce fichier existe :
    La GUI est une couche de pages. Elle ne parcourt pas le JSON backend en
    profondeur et n'appelle pas les calculateurs : elle affiche le tableau de
    visualisations, les statuts CAO, les graphes et les actions disponibles.
Donnees consommees :
    Rapport backend brut charge par l'application et payload de
    frontend.ensemble.visualisation_orchestrator.
Livrables produits :
    Page Kivy listant systeme, composants, pieces, couverture et dossier
    SolidWorks de preconception.
Limites :
    - ne calcule aucune valeur metier ;
    - ne produit pas de STEP ;
    - ne valide aucun candidat ;
    - la 3D affichee est indicative.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping

from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.ensemble.screen_models import build_visualisation_model
from frontend.gui.components import COLORS, EmptyState, MetricRow, ModernButton, PremiumCard, SectionTitle, StatusBadge


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _short(value: Any, max_len: int = 84) -> str:
    text = str(value or "")
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "..."


def _status(value: Any) -> str:
    low = str(value or "").lower()
    if low in {"available", "ok"}:
        return "ok"
    if low in {"partial", "computed", "derived", "validated_by_optimization", "candidate_from_cdc", "candidate_from_power_profile", "candidate_optimized"}:
        return "partiel"
    if low in {"error", "impossible"}:
        return "error"
    return "missing"


def build_technical_visualization_payload(report: Mapping[str, Any]) -> Dict[str, Any]:
    """Construit le payload GUI depuis le rapport backend, sans calcul metier."""
    return build_visualisation_model({"raw_report": dict(report or {})})


class TechnicalVisualizationScreen(Screen):
    def on_enter(self, *_: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        app = App.get_running_app()
        report = _safe_dict(
            getattr(app, "raw_backend_report", None)
            or getattr(app, "backend_report", None)
            or getattr(app, "full_report", None)
            or getattr(app, "raw_report", None)
            or {}
        )
        self.payload = build_technical_visualization_payload(report)

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        root.add_widget(self._top_bar())

        if not report:
            root.add_widget(EmptyState(text="AUCUN RAPPORT BACKEND CHARGE"))
            self.add_widget(root)
            return

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        content = BoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        content.add_widget(self._system_panel())
        content.add_widget(self._coverage_panel())
        content.add_widget(self._components_panel())
        content.add_widget(self._pieces_panel())
        content.add_widget(self._solidworks_panel())
        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(58), spacing=dp(10), padding=[dp(10), dp(5)])
        title = Label(text="VISUALISATION TECHNIQUE", color=COLORS["BFW"], bold=True, font_size="16sp", halign="left")
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        bar.add_widget(title)
        for label, callback, width in (
            ("COPIER JSON", self.copy_payload, 130),
            ("DOSSIER CAO", lambda *_: self._go("cao_dossier"), 130),
            ("JSON BRUT", lambda *_: self._go("raw_json"), 110),
            ("DASHBOARD", lambda *_: self._go("dashboard"), 120),
        ):
            btn = ModernButton(text=label, size_hint_x=None, width=dp(width), font_size="11sp")
            btn.bind(on_release=callback)
            bar.add_widget(btn)
        return bar

    def _system_panel(self) -> PremiumCard:
        system = _safe_dict(self.payload.get("system"))
        chain = _safe_dict(system.get("power_chain"))
        diagnostic = _safe_dict(system.get("diagnostic"))
        cao = _safe_dict(system.get("cao_dossier"))
        panel = PremiumCard(title="Vue systeme", size_hint_y=None, height=dp(210))
        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(150))
        grid.add_widget(MetricRow("Chaine puissance", "OK" if chain.get("ok") else "partiel/bloque", "", "ok" if chain.get("ok") else "alerte"))
        grid.add_widget(MetricRow("Score chaine", chain.get("score_chaine_100"), "/100", "ok" if chain.get("score_chaine_100") else "missing"))
        grid.add_widget(MetricRow("Strategie energie", "presente" if system.get("strategy") else "absente", "", "ok" if system.get("strategy") else "missing"))
        grid.add_widget(MetricRow("Causes racines", len(_safe_list(diagnostic.get("causes_racines"))), "", "alerte" if diagnostic.get("causes_racines") else "ok"))
        grid.add_widget(MetricRow("Dossier CAO", "present" if cao else "absent", "", "ok" if cao else "missing"))
        grid.add_widget(MetricRow("Graphes mecaniques", "present" if _safe_dict(system.get("mechanical_graphs")) else "voir dossier", "", "partiel"))
        panel.add_widget(grid)
        panel.add_widget(Label(text="Les vues sont indicatives : aucun STEP final n'est produit.", color=COLORS["MUTED"], size_hint_y=None, height=dp(32)))
        return panel

    def _coverage_panel(self) -> PremiumCard:
        coverage = _safe_dict(self.payload.get("coverage"))
        summary = _safe_dict(coverage.get("summary"))
        panel = PremiumCard(title="Couverture frontend", size_hint_y=None, height=dp(180))
        panel.add_widget(MetricRow("Pieces backend", summary.get("backend_pieces"), "", "partiel"))
        panel.add_widget(MetricRow("Pieces frontend", summary.get("frontend_pieces"), "", "partiel"))
        panel.add_widget(MetricRow("Contrats passifs", summary.get("render_contract_supported"), "", "ok" if summary.get("render_contract_supported") else "missing"))
        panel.add_widget(MetricRow("Modules legacy demo", summary.get("legacy_hidden_demo"), "", "alerte" if summary.get("legacy_hidden_demo") else "ok"))
        panel.add_widget(MetricRow("Defaults a auditer", summary.get("dangerous_defaults_files"), "", "alerte" if summary.get("dangerous_defaults_files") else "ok"))
        return panel

    def _components_panel(self) -> PremiumCard:
        rows = [dict(r) for r in _safe_list(self.payload.get("components")) if isinstance(r, Mapping)]
        panel = PremiumCard(title=f"Composants ({len(rows)})", size_hint_y=None, height=dp(80 + max(1, len(rows)) * 38))
        if not rows:
            panel.add_widget(EmptyState(text="Aucun composant backend detecte."))
            return panel
        for row in rows:
            panel.add_widget(MetricRow(row.get("component"), row.get("status"), "", _status(row.get("status"))))
        return panel

    def _pieces_panel(self) -> PremiumCard:
        families = _safe_dict(self.payload.get("pieces_by_family"))
        total = sum(len(_safe_list(v)) for v in families.values())
        panel = PremiumCard(title=f"Pieces ({total})", size_hint_y=None, height=dp(120 + max(1, total) * 34))
        if not families:
            panel.add_widget(EmptyState(text="Aucune piece frontend/backend detectee."))
            return panel
        for family, pieces in families.items():
            panel.add_widget(SectionTitle(text=str(family).upper()))
            for piece in _safe_list(pieces)[:18]:
                if isinstance(piece, Mapping):
                    legacy = " | legacy" if piece.get("legacy_hidden_demo") else ""
                    label = f"{piece.get('piece')} | croquis={piece.get('backend_sketches') or piece.get('has_sketches')} | 3D={piece.get('backend_views_3d') or piece.get('has_mesh_3d')} | graphes={piece.get('backend_graphs')}{legacy}"
                    panel.add_widget(MetricRow(_short(label, 70), piece.get("status"), "", _status(piece.get("status"))))
        return panel

    def _solidworks_panel(self) -> PremiumCard:
        sw = _safe_dict(self.payload.get("solidworks"))
        panel = PremiumCard(title="Dossier SolidWorks", size_hint_y=None, height=dp(170))
        panel.add_widget(MetricRow("Cotes disponibles", "via contrats piece", "", "partiel" if sw.get("cao_dossier") else "missing"))
        panel.add_widget(MetricRow("Graphiques", "backend" if sw.get("mechanical_graphs") else "absents", "", "ok" if sw.get("mechanical_graphs") else "missing"))
        panel.add_widget(MetricRow("SolidWorks ready", bool(sw.get("solidworks_ready")), "", "missing"))
        panel.add_widget(MetricRow("STEP export", bool(sw.get("step_export")), "", "missing"))
        panel.add_widget(Label(text="Cette page aide au redessin SolidWorks ; elle n'applique aucun patch.", color=COLORS["MUTED"], size_hint_y=None, height=dp(32)))
        return panel

    def copy_payload(self, *_: Any) -> None:
        Clipboard.copy(json.dumps(self.payload, ensure_ascii=False, indent=2))

    def _go(self, target: str) -> None:
        if self.manager and self.manager.has_screen(target):
            self.manager.current = target


__all__ = ["TechnicalVisualizationScreen", "build_technical_visualization_payload"]
