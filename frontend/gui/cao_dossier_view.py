from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import COLORS, MetricRow, ModernButton, NeoCard, PremiumCard, SectionTitle, StatusBadge


class CaoDossierScreen(Screen):
    """Vue passive du dossier CAO/preconception fourni par le backend."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.payload: Dict[str, Any] = {}

    def on_enter(self, *_: Any) -> None:
        self.refresh()

    def refresh(self, *_: Any) -> None:
        self.payload = _build_payload(App.get_running_app())
        self._render()

    def _render(self) -> None:
        self.clear_widgets()
        dossier = _safe_dict(self.payload.get("cao_dossier"))
        resume = _safe_dict(dossier.get("resume"))
        graphs = _safe_dict(self.payload.get("mechanical_graphs"))
        sketches = [dict(s) for s in _safe_list(dossier.get("croquis_2d")) if isinstance(s, Mapping)]
        views = [dict(v) for v in _safe_list(dossier.get("vues_3d")) if isinstance(v, Mapping)]
        graph_rows = [dict(g) for g in _safe_list(graphs.get("graphiques")) if isinstance(g, Mapping)]

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        root.add_widget(self._top_bar(resume))
        root.add_widget(self._summary_panel(resume))

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        content = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        if not dossier:
            panel = PremiumCard(title="Dossier CAO")
            panel.add_widget(_label("Aucun dossier CAO backend disponible.", COLORS["MUTED"]))
            content.add_widget(panel)
        else:
            content.add_widget(self._sketches_panel(sketches))
            content.add_widget(self._views_panel(views))
            content.add_widget(self._graphs_panel(graph_rows))
            content.add_widget(self._solidworks_values_panel(_safe_dict(_safe_dict(dossier.get("donnees_solidworks")).get("valeurs_a_reporter"))))
            content.add_widget(self._actions_panel(_safe_list(dossier.get("actions"))))

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self, resume: Mapping[str, Any]) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(56), spacing=dp(10), padding=[dp(10), dp(5)])
        title = Label(text="DOSSIER CAO / PRECONCEPTION", color=COLORS["BFW"], bold=True, font_size="16sp", halign="left", valign="middle")
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        bar.add_widget(title)
        badge_status = "ok" if resume.get("drawing_data_available") else "alerte"
        bar.add_widget(StatusBadge(status=badge_status, text=str(resume.get("mode") or "indisponible"), size_hint_x=None, width=dp(150)))
        for text, callback, width in (
            ("VOIR CROQUIS", lambda *_: self._scroll_note("croquis"), 120),
            ("VOIR GRAPHIQUES", lambda *_: self._scroll_note("graphiques"), 140),
            ("COPIER COTES", self.copy_solidworks_values, 130),
            ("EXPORT JSON", self.export_json, 120),
            ("DASHBOARD", lambda *_: self._go("dashboard"), 120),
        ):
            btn = ModernButton(text=text, size_hint_x=None, width=dp(width), font_size="10sp")
            btn.bind(on_release=callback)
            bar.add_widget(btn)
        return bar

    def _summary_panel(self, resume: Mapping[str, Any]) -> PremiumCard:
        panel = PremiumCard(title="Statut livrables", size_hint_y=None, height=dp(120))
        grid = GridLayout(cols=6, spacing=dp(8), size_hint_y=None, height=dp(60))
        grid.add_widget(MetricRow("Mode", resume.get("mode"), "", _status(resume.get("mode"))))
        grid.add_widget(MetricRow("Croquis cotes", _bool_text(resume.get("sketches_available")), "", _bool_status(resume.get("sketches_available"))))
        grid.add_widget(MetricRow("3D indicative", _bool_text(resume.get("views_3d_available")), "", _bool_status(resume.get("views_3d_available"))))
        grid.add_widget(MetricRow("Graphes", _bool_text(resume.get("stress_graphs_available")), "", _bool_status(resume.get("stress_graphs_available"))))
        grid.add_widget(MetricRow("SolidWorks", _bool_text(resume.get("solidworks_ready")), "", "missing"))
        grid.add_widget(MetricRow("STEP", _bool_text(resume.get("step_export")), "", "missing"))
        panel.add_widget(grid)
        panel.add_widget(_label(str(resume.get("avertissement") or "Vue indicative, pas un STEP final."), COLORS["MUTED"], height=28))
        return panel

    def _sketches_panel(self, sketches: list[dict[str, Any]]) -> PremiumCard:
        panel = PremiumCard(title=f"Croquis cotes ({len(sketches)})", size_hint_y=None, height=dp(220))
        if not sketches:
            panel.add_widget(_label("Aucun croquis cote disponible.", COLORS["MUTED"]))
            return panel
        for sketch in sketches[:5]:
            panel.add_widget(MetricRow(sketch.get("id"), sketch.get("statut"), "", _status(sketch.get("statut"))))
        return panel

    def _views_panel(self, views: list[dict[str, Any]]) -> PremiumCard:
        panel = PremiumCard(title=f"Vues 3D indicatives ({len(views)})", size_hint_y=None, height=dp(180))
        if not views:
            panel.add_widget(_label("Aucune vue 3D indicative disponible.", COLORS["MUTED"]))
            return panel
        for view in views[:4]:
            panel.add_widget(MetricRow(view.get("id"), view.get("primitive"), "", _status(view.get("status"))))
        return panel

    def _graphs_panel(self, graphs: list[dict[str, Any]]) -> PremiumCard:
        panel = PremiumCard(title=f"Graphiques mecaniques ({len(graphs)})", size_hint_y=None, height=dp(250))
        if not graphs:
            panel.add_widget(_label("Aucun graphique mecanique disponible.", COLORS["MUTED"]))
            return panel
        for graph in graphs[:7]:
            panel.add_widget(MetricRow(graph.get("id"), graph.get("status"), "", _status(graph.get("status"))))
        return panel

    def _solidworks_values_panel(self, values: Mapping[str, Any]) -> PremiumCard:
        panel = PremiumCard(title="Valeurs a reporter dans SolidWorks", size_hint_y=None, height=dp(230))
        if not values:
            panel.add_widget(_label("Aucune valeur de dessin exploitable.", COLORS["MUTED"]))
            return panel
        for key, value in list(values.items())[:7]:
            panel.add_widget(MetricRow(str(key), value, "", "ok"))
        return panel

    def _actions_panel(self, actions: list[Any]) -> PremiumCard:
        panel = PremiumCard(title=f"Actions manquantes ({len(actions)})", size_hint_y=None, height=dp(230))
        if not actions:
            panel.add_widget(_label("Aucune action manquante signalee.", COLORS["MUTED"]))
            return panel
        for action in actions[:6]:
            row = action if isinstance(action, Mapping) else {"action": str(action)}
            panel.add_widget(MetricRow(row.get("champ") or row.get("piece") or "action", row.get("action"), "", "missing"))
        return panel

    def copy_solidworks_values(self, *_: Any) -> None:
        values = _safe_dict(_safe_dict(_safe_dict(self.payload.get("cao_dossier")).get("donnees_solidworks")).get("valeurs_a_reporter"))
        Clipboard.copy(json.dumps(values, ensure_ascii=False, indent=2))

    def export_json(self, *_: Any) -> None:
        out = Path("backend") / "exports" / "frontend_cao_dossier_export.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2), encoding="utf-8")
        Clipboard.copy(str(out.resolve()))

    def _scroll_note(self, section: str) -> None:
        Clipboard.copy(section)

    def _go(self, name: str) -> None:
        if self.manager is not None:
            self.manager.current = name


def _build_payload(app: Any) -> Dict[str, Any]:
    report = _first_report(app)
    frontend = _safe_dict(report.get("frontend"))
    contract = frontend if frontend else report
    return {
        "cao": _safe_dict(contract.get("cao")) or _safe_dict(report.get("cao")),
        "cao_dossier": _safe_dict(contract.get("cao_dossier")) or _safe_dict(report.get("cao_dossier")),
        "mechanical_graphs": _safe_dict(contract.get("mechanical_graphs")) or _safe_dict(report.get("mechanical_graphs")),
    }


def _first_report(app: Any) -> Dict[str, Any]:
    for attr in ("raw_backend_report", "backend_report", "full_report", "last_backend_report", "ui_report"):
        try:
            value = getattr(app, attr, None)
        except Exception:
            continue
        if isinstance(value, Mapping) and value:
            return dict(value)
    return {}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _bool_text(value: Any) -> str:
    if value is True:
        return "OUI"
    if value is False:
        return "NON"
    return "-"


def _bool_status(value: Any) -> str:
    return "ok" if value is True else "missing"


def _status(value: Any) -> str:
    text = str(value or "").lower()
    if text in {"3d_indicative", "croquis_cotes", "available", "exploitable_pour_redessin_solidworks", "partiel_exploitable", "pre_dimensionne"}:
        return "ok"
    if text in {"partial", "pre_dimensionne_partiel", "conceptuel_non_cote"}:
        return "partiel"
    return "missing"


def _label(text: str, color: Any, *, height: int = 32) -> Label:
    label = Label(text=str(text), color=color, font_size="12sp", size_hint_y=None, height=dp(height), halign="left", valign="top")
    label.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
    return label


__all__ = ["CaoDossierScreen"]
