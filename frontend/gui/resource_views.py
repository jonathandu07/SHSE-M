from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.backend_resource_adapter import build_resource_catalog, generate_or_load_resource
from frontend.gui.components import (
    COLORS,
    EmptyState,
    MetricRow,
    ModernButton,
    NeoCard,
    PremiumCard,
    SectionTitle,
    StatusBadge,
)


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _short_path(path: Any, max_len: int = 54) -> str:
    if not path:
        return ""
    text = str(path)
    name = Path(text).name
    if len(text) <= max_len:
        return text
    return f".../{name}" if name else text[-max_len:]


def _short_text(value: Any, max_len: int = 110) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "..."


def _resource_catalog_from_app(app: Any) -> Dict[str, List[Dict[str, Any]]]:
    ui = _safe_dict(getattr(app, "ui_report", {}) or {})
    resources = ui.get("resources")
    if isinstance(resources, Mapping):
        return {
            str(key): [dict(item) for item in _safe_list(value) if isinstance(item, Mapping)]
            for key, value in resources.items()
        }

    raw = _safe_dict(
        getattr(app, "raw_backend_report", None)
        or getattr(app, "backend_report", None)
        or getattr(app, "full_report", None)
        or {}
    )
    payload = build_resource_catalog(raw)
    resources = _safe_dict(payload.get("resources"))
    if ui is not None:
        ui["resources"] = resources
        ui["resource_summary"] = payload.get("resource_summary", {})
        try:
            app.ui_report = ui
        except Exception:
            pass
    return {
        str(key): [dict(item) for item in _safe_list(value) if isinstance(item, Mapping)]
        for key, value in resources.items()
    }


def _split_resources_by_status(items: Iterable[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    available: List[Dict[str, Any]] = []
    unavailable: List[Dict[str, Any]] = []
    for item in items:
        record = dict(item)
        if record.get("status") == "available":
            available.append(record)
        else:
            unavailable.append(record)
    return available, unavailable


class ResourceListScreen(Screen):
    resource_key = ""
    title = ""
    empty_text = "Ressource indisponible."

    def on_enter(self, *_: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        app = App.get_running_app()
        catalog = _resource_catalog_from_app(app)
        resources = [dict(item) for item in _safe_list(catalog.get(self.resource_key)) if isinstance(item, Mapping)]
        available, unavailable = _split_resources_by_status(resources)

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        root.add_widget(self._top_bar(len(available), len(unavailable)))

        if not resources:
            root.add_widget(EmptyState(text=self.empty_text))
            self.add_widget(root)
            return

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        content = BoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        if available:
            content.add_widget(self._section("RESSOURCES DISPONIBLES", available))
        if unavailable:
            content.add_widget(self._section("INDISPONIBLES / PARTIELLES", unavailable))

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self, available_count: int, unavailable_count: int) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(58), spacing=dp(10), padding=[dp(10), dp(5)])
        lbl = Label(text=self.title.upper(), color=COLORS["BFW"], bold=True, font_size="16sp", halign="left")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)
        bar.add_widget(StatusBadge(status="available" if available_count else "unavailable", size_hint_x=None, width=dp(120)))
        bar.add_widget(MetricRow("Disponibles", available_count, "", "ok" if available_count else "missing"))
        bar.add_widget(MetricRow("Non pretes", unavailable_count, "", "alerte" if unavailable_count else "ok"))

        btn = ModernButton(text="RETOUR DASHBOARD", size_hint_x=None, width=dp(180), font_size="11sp")
        btn.bind(on_release=lambda *_: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn)
        return bar

    def _section(self, title: str, items: List[Dict[str, Any]]) -> PremiumCard:
        panel = PremiumCard(title=title, size_hint_y=None)
        grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for item in items:
            grid.add_widget(self._resource_card(item))
        panel.add_widget(grid)
        panel.height = dp(58) + sum(dp(238) for _ in items)
        return panel

    def _resource_card(self, item: Dict[str, Any]) -> NeoCard:
        status = str(item.get("status") or "unavailable")
        path = item.get("path")
        missing_inputs = [str(v) for v in _safe_list(item.get("missing_inputs")) if str(v)]
        reason = item.get("reason") or ""
        generator_available = bool(item.get("generator_available") and item.get("function"))
        path_exists = bool(path and Path(str(path)).is_file())

        card = NeoCard(orientation="vertical", size_hint_y=None, height=dp(230), spacing=dp(6), padding=dp(10))
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(32), spacing=dp(8))
        header.add_widget(SectionTitle(text=str(item.get("name") or "Ressource").upper()))
        header.add_widget(StatusBadge(status=status, size_hint_x=None, width=dp(118)))
        card.add_widget(header)

        card.add_widget(MetricRow("Type", item.get("type") or self.resource_key, "", status))
        card.add_widget(MetricRow("Source", _short_text(item.get("source") or "non detectee", 64), "", "ok" if item.get("source") else "missing"))
        card.add_widget(MetricRow("Fonction", _short_text(item.get("function") or "absente", 64), "", "ok" if item.get("function") else "missing"))
        card.add_widget(MetricRow("Fichier", _short_path(path) if path_exists else "aucun fichier existant", "", "ok" if path_exists else "missing"))
        card.add_widget(MetricRow("Raison", _short_text(reason or "Ressource generee ou donnee disponible.", 72), "", "alerte" if reason else "ok"))
        card.add_widget(MetricRow("Donnees manquantes", ", ".join(missing_inputs[:4]) if missing_inputs else "aucune liste fournie", "", "alerte" if missing_inputs else "ok"))

        buttons = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(38), spacing=dp(8))
        open_btn = ModernButton(text="OUVRIR", font_size="10sp")
        open_btn.disabled = not path_exists
        open_btn.bind(on_release=lambda *_args, p=path: self._open_path(p))
        buttons.add_widget(open_btn)

        generate_btn = ModernButton(text="GENERER", font_size="10sp")
        generate_btn.disabled = not generator_available
        generate_btn.bind(on_release=lambda *_args, r=item: self._generate(r))
        buttons.add_widget(generate_btn)

        missing_btn = ModernButton(text="MANQUANTS", font_size="10sp")
        missing_btn.disabled = not (missing_inputs or reason)
        missing_btn.bind(on_release=lambda *_args, r=item: self._show_missing(r))
        buttons.add_widget(missing_btn)
        card.add_widget(buttons)

        return card

    def _open_path(self, path: Any) -> None:
        if not path or not Path(str(path)).is_file():
            return
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception:
            Clipboard.copy(str(path))

    def _generate(self, item: Mapping[str, Any]) -> None:
        app = App.get_running_app()
        raw = _safe_dict(getattr(app, "raw_backend_report", {}) or {})
        result = generate_or_load_resource(dict(item), raw)
        try:
            app.last_resource_generation = result
        except Exception:
            pass
        self.refresh()

    def _show_missing(self, item: Mapping[str, Any]) -> None:
        app = App.get_running_app()
        try:
            app.selected_missing_resource = dict(item)
        except Exception:
            pass
        if self.manager is not None:
            self.manager.current = "missing_requirements"


class SketchesScreen(ResourceListScreen):
    resource_key = "sketches"
    title = "CROQUIS D'INGENIERIE"
    empty_text = "AUCUN CROQUIS BACKEND DISPONIBLE"


class ChartsScreen(ResourceListScreen):
    resource_key = "charts"
    title = "GRAPHES DE PERFORMANCE"
    empty_text = "GRAPHIQUE INDISPONIBLE : AUCUN GENERATEUR BACKEND TROUVE"


class ThreeDScreen(ResourceListScreen):
    resource_key = "three_d"
    title = "MODELES NUMERIQUES 3D"
    empty_text = "3D INDISPONIBLE : DONNEES CAO OU GENERATEUR ABSENTS"

