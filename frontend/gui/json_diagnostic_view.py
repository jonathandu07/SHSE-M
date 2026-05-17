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

from frontend.gui.components import COLORS, MetricRow, ModernButton, NeoCard, PremiumCard, SectionTitle, StatusBadge


def build_json_diagnostic_for_app(app: Any) -> dict[str, Any]:
    data = _first_report(app)
    if not data:
        return {
            "diagnostic": {
                "meta": {"type_detecte": "inconnu"},
                "resume": {"statut": "bloque", "score_diagnostic_100": 0, "nb_causes_racines": 0, "nb_symptomes": 0},
                "causes_racines": [],
                "symptomes": [],
                "patchs_proposes": [],
                "notes": ["Aucun JSON backend disponible en memoire."],
            }
        }
    try:
        from backend.modules.systeme.system_services import diagnostiquer_json_data

        return diagnostiquer_json_data(data, source_name="frontend.app", strict=True)
    except Exception as exc:
        return {
            "diagnostic": {
                "meta": {"type_detecte": "inconnu"},
                "resume": {"statut": "bloque", "score_diagnostic_100": 0, "nb_causes_racines": 0, "nb_symptomes": 0},
                "causes_racines": [],
                "symptomes": [],
                "patchs_proposes": [],
                "notes": [f"Diagnostic indisponible: {exc}"],
            }
        }


class JsonDiagnosticScreen(Screen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.payload: Dict[str, Any] = {}

    def on_enter(self, *_: Any) -> None:
        self.refresh()

    def refresh(self, *_: Any) -> None:
        app = App.get_running_app()
        self.payload = build_json_diagnostic_for_app(app)
        try:
            app.json_diagnostic_report = self.payload
        except Exception:
            pass
        self._render()

    def _render(self) -> None:
        self.clear_widgets()
        diagnostic = _safe_dict(self.payload.get("diagnostic"))
        resume = _safe_dict(diagnostic.get("resume"))
        causes = [dict(c) for c in _safe_list(diagnostic.get("causes_racines")) if isinstance(c, Mapping)]
        symptoms = [dict(s) for s in _safe_list(diagnostic.get("symptomes")) if isinstance(s, Mapping)]

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        root.add_widget(self._top_bar(str(resume.get("statut") or "inconnu")))
        root.add_widget(self._summary_panel(resume))

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        content = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        if not causes:
            panel = PremiumCard(title="Causes racines")
            panel.add_widget(_label("Aucune cause racine evidente detectee.", COLORS["GS"]))
            content.add_widget(panel)
        else:
            for cause in causes[:20]:
                content.add_widget(self._cause_card(cause))

        if symptoms:
            panel = PremiumCard(title=f"Symptomes dedupliques ({len(symptoms)})", size_hint_y=None, height=dp(180))
            for symptom in symptoms[:4]:
                panel.add_widget(MetricRow(symptom.get("champ"), _short(symptom.get("raison"), 90), "", "alerte"))
            content.add_widget(panel)

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self, status: str) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(56), spacing=dp(10), padding=[dp(10), dp(5)])
        title = Label(text="DIAGNOSTIC JSON", color=COLORS["BFW"], bold=True, font_size="16sp", halign="left", valign="middle")
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        bar.add_widget(title)
        bar.add_widget(StatusBadge(status="alerte" if status == "bloque" else "ok", size_hint_x=None, width=dp(110)))
        for text, callback, width in (
            ("RAFRAICHIR", self.refresh, 120),
            ("COPIER JSON", self.copy_diagnostic, 130),
            ("PARAMETRES", lambda *_: self._go("edit_parameters"), 130),
            ("JSON BRUT", lambda *_: self._go("raw_json"), 110),
            ("DASHBOARD", lambda *_: self._go("dashboard"), 120),
        ):
            btn = ModernButton(text=text, size_hint_x=None, width=dp(width), font_size="11sp")
            btn.bind(on_release=callback)
            bar.add_widget(btn)
        return bar

    def _summary_panel(self, resume: Mapping[str, Any]) -> PremiumCard:
        panel = PremiumCard(title="Resume diagnostic", size_hint_y=None, height=dp(105))
        grid = GridLayout(cols=5, spacing=dp(8), size_hint_y=None, height=dp(48))
        grid.add_widget(MetricRow("Statut", str(resume.get("statut", "inconnu")).upper(), "", "alerte" if resume.get("statut") == "bloque" else "ok"))
        grid.add_widget(MetricRow("Score", resume.get("score_diagnostic_100"), "/100", "alerte"))
        grid.add_widget(MetricRow("Causes", resume.get("nb_causes_racines"), "", "alerte" if resume.get("nb_causes_racines") else "ok"))
        grid.add_widget(MetricRow("Symptomes", resume.get("nb_symptomes"), "", "alerte" if resume.get("nb_symptomes") else "ok"))
        grid.add_widget(MetricRow("Doublons", resume.get("nb_doublons_probables"), "", "partiel" if resume.get("nb_doublons_probables") else "ok"))
        panel.add_widget(grid)
        return panel

    def _cause_card(self, cause: Mapping[str, Any]) -> NeoCard:
        impact = _safe_dict(cause.get("impact"))
        patch = _safe_list(cause.get("patchs_proposes"))
        first_patch = patch[0] if patch and isinstance(patch[0], Mapping) else {}
        card = NeoCard(orientation="vertical", size_hint_y=None, height=dp(230), spacing=dp(6), padding=dp(12))
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(32), spacing=dp(8))
        header.add_widget(SectionTitle(text=str(cause.get("titre") or cause.get("id") or "Cause").upper()))
        header.add_widget(StatusBadge(status="alerte", size_hint_x=None, width=dp(110)))
        card.add_widget(header)
        card.add_widget(_label(_short(cause.get("raison"), 190), COLORS["BFW"], height=42))
        grid = GridLayout(cols=2, spacing=dp(4), size_hint_y=None, height=dp(72))
        grid.add_widget(MetricRow("Champ", cause.get("champ"), "", "missing"))
        grid.add_widget(MetricRow("Sous-systeme", cause.get("sous_systeme"), "", "alerte"))
        grid.add_widget(MetricRow("Impact", impact.get("nb_symptomes_expliques"), "sympt.", "alerte"))
        grid.add_widget(MetricRow("Priorite", cause.get("priorite"), "/100", "alerte"))
        card.add_widget(grid)
        actions = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(8))
        for text, callback in (
            ("COPIER CHEMIN", lambda *_: self._copy(cause.get("champ"))),
            ("COPIER RAISON", lambda *_: self._copy(cause.get("raison"))),
            ("COPIER PATCH", lambda *_: self._copy(json.dumps(first_patch, ensure_ascii=False, indent=2))),
        ):
            btn = ModernButton(text=text, font_size="10sp")
            btn.bind(on_release=callback)
            actions.add_widget(btn)
        card.add_widget(actions)
        return card

    def copy_diagnostic(self, *_: Any) -> None:
        Clipboard.copy(json.dumps(self.payload, ensure_ascii=False, indent=2))

    def _copy(self, value: Any) -> None:
        Clipboard.copy(str(value or ""))

    def _go(self, name: str) -> None:
        if self.manager is not None:
            self.manager.current = name


def _first_report(app: Any) -> Dict[str, Any]:
    for attr in ("json_diagnostic_source", "raw_backend_report", "backend_report", "full_report", "last_backend_report", "ui_report"):
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
    return value if isinstance(value, list) else []


def _short(value: Any, limit: int = 120) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _label(text: str, color: Any, *, height: int = 28) -> Label:
    label = Label(text=str(text), color=color, font_size="12sp", size_hint_y=None, height=dp(height), halign="left", valign="top")
    label.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
    return label
