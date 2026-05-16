# frontend/gui/raw_report_view.py
from __future__ import annotations

import json
import math
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from frontend.gui.components import (
    COLORS,
    JsonViewer,
    MetricRow,
    ModernButton,
    PremiumCard,
    StatusBadge,
)

try:
    from frontend.gui.report_adapter import save_json_report
except Exception:  # pragma: no cover
    save_json_report = None  # type: ignore


# =============================================================================
# Helpers stricts
# =============================================================================

def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _is_finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _jsonable(value: Any, *, depth: int = 0, max_depth: int = 8) -> Any:
    if depth > max_depth:
        return {"type": type(value).__name__, "truncated": True}

    if value is None or isinstance(value, (str, int, float, bool)):
        if _is_finite(value):
            return float(value)
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, Mapping):
        return {
            str(k): _jsonable(v, depth=depth + 1, max_depth=max_depth)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            _jsonable(v, depth=depth + 1, max_depth=max_depth)
            for v in value
        ]

    if hasattr(value, "en_dict") and callable(getattr(value, "en_dict")):
        try:
            return _jsonable(value.en_dict(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            attrs = {
                key: val
                for key, val in vars(value).items()
                if not key.startswith("_") and not callable(val)
            }
            return {
                "type": type(value).__name__,
                "attributs": _jsonable(attrs, depth=depth + 1, max_depth=max_depth),
            }
        except Exception:
            pass

    return str(value)


def _json_dumps(data: Any) -> str:
    return json.dumps(
        _jsonable(data),
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    )


def _count_nodes(value: Any, *, depth: int = 0, max_depth: int = 8) -> int:
    if value is None:
        return 0

    if depth > max_depth:
        return 1

    if isinstance(value, Mapping):
        return 1 + sum(_count_nodes(v, depth=depth + 1, max_depth=max_depth) for v in value.values())

    if isinstance(value, list):
        return 1 + sum(_count_nodes(v, depth=depth + 1, max_depth=max_depth) for v in value)

    return 1


def _count_unknowns(value: Any) -> int:
    total = 0

    def walk(node: Any) -> None:
        nonlocal total

        if isinstance(node, Mapping):
            inc = node.get("inconnues")
            if isinstance(inc, Mapping):
                for values in inc.values():
                    if isinstance(values, list):
                        total += len(values)

            inconnues_cao = node.get("inconnues_cao")
            if isinstance(inconnues_cao, list):
                total += len(inconnues_cao)

            for child in node.values():
                if isinstance(child, (Mapping, list)):
                    walk(child)

        elif isinstance(node, list):
            for child in node:
                if isinstance(child, (Mapping, list)):
                    walk(child)

    walk(value)
    return total


def _count_alerts(value: Any) -> int:
    total = 0

    def walk(node: Any) -> None:
        nonlocal total

        if isinstance(node, Mapping):
            alerts = node.get("alertes")
            if isinstance(alerts, Mapping):
                for values in alerts.values():
                    if isinstance(values, list):
                        total += len(values)

            for child in node.values():
                if isinstance(child, (Mapping, list)):
                    walk(child)

        elif isinstance(node, list):
            for child in node:
                if isinstance(child, (Mapping, list)):
                    walk(child)

    walk(value)
    return total


def _short_text(value: Any, max_len: int = 140) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _merge_non_none(base: Optional[Mapping[str, Any]], extra: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    out = dict(base or {})

    if not isinstance(extra, Mapping):
        return out

    for key, value in extra.items():
        if value is None:
            continue

        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[str(key)] = _merge_non_none(out[key], value)
        else:
            out[str(key)] = value

    return out


def _write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    if save_json_report is not None:
        try:
            save_json_report(_jsonable(data), path)
            return path
        except Exception:
            pass

    path.write_text(_json_dumps(data), encoding="utf-8")
    return path


def _status_for_data(data: Any) -> str:
    if data is None:
        return "missing"
    if isinstance(data, Mapping) and not data:
        return "missing"
    if isinstance(data, list) and not data:
        return "missing"
    if _count_unknowns(data) or _count_alerts(data):
        return "alerte"
    return "ok"


# =============================================================================
# Collecte des rapports
# =============================================================================

REPORT_ATTRS: Tuple[str, ...] = (
    "raw_backend_report",
    "backend_report",
    "full_report",
    "last_backend_report",
    "engine_report",
    "last_engine_report",
    "system_report",
    "last_system_report",
    "raw_report",
    "report",
    "last_report",
    "all_data",
    "toutes_les_donnees",
)

UI_ATTRS: Tuple[str, ...] = (
    "ui_report",
)

EXTRA_ATTRS: Tuple[str, ...] = (
    "engine_params",
    "selected_architecture",
    "selected_architecture_candidate",
    "selected_piece",
    "piece_library",
    "piece_library_diagnostics",
    "last_error_payload",
    "backend_sync_errors",
    "dashboard_backend_errors",
    "energy_audit_errors",
    "edit_parameters_errors",
)


def collect_raw_sources(app: Any) -> Dict[str, Any]:
    sources: Dict[str, Any] = {}

    for attr in REPORT_ATTRS:
        try:
            value = getattr(app, attr, None)
        except Exception:
            continue

        if isinstance(value, Mapping) and value:
            sources[attr] = dict(value)

    for attr in UI_ATTRS:
        try:
            value = getattr(app, attr, None)
        except Exception:
            continue

        if isinstance(value, Mapping) and value:
            sources[attr] = dict(value)

    for attr in EXTRA_ATTRS:
        try:
            value = getattr(app, attr, None)
        except Exception:
            continue

        if value is not None and value != {} and value != []:
            sources[attr] = _jsonable(value)

    return sources


def build_complete_debug_bundle(app: Any) -> Dict[str, Any]:
    sources = collect_raw_sources(app)

    merged_backend: Dict[str, Any] = {}
    for attr in REPORT_ATTRS:
        value = sources.get(attr)
        if isinstance(value, Mapping):
            merged_backend = _merge_non_none(merged_backend, value)

    ui_report = _safe_dict(sources.get("ui_report"))
    engine_params = _safe_dict(sources.get("engine_params"))

    return {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "screen": "RawJsonScreen",
            "sources_detected": list(sources.keys()),
            "backend_sources_count": len([k for k in sources if k in REPORT_ATTRS]),
            "ui_present": bool(ui_report),
            "engine_params_present": bool(engine_params),
        },
        "engine_params": engine_params,
        "saisie_home": engine_params.get("saisie_home"),
        "backend_report_merged": merged_backend,
        "raw_backend_report": sources.get("raw_backend_report"),
        "backend_report": sources.get("backend_report"),
        "full_report": sources.get("full_report"),
        "ui_report": ui_report,
        "selected_architecture": sources.get("selected_architecture"),
        "selected_architecture_candidate": sources.get("selected_architecture_candidate"),
        "selected_piece": sources.get("selected_piece"),
        "piece_library_diagnostics": sources.get("piece_library_diagnostics"),
        "errors": {
            "last_error_payload": sources.get("last_error_payload"),
            "backend_sync_errors": sources.get("backend_sync_errors"),
            "dashboard_backend_errors": sources.get("dashboard_backend_errors"),
            "energy_audit_errors": sources.get("energy_audit_errors"),
            "edit_parameters_errors": sources.get("edit_parameters_errors"),
        },
        "all_sources_raw": sources,
    }


def build_source_map(app: Any) -> Dict[str, Any]:
    bundle = build_complete_debug_bundle(app)

    return {
        "COMPLET": bundle,
        "BACKEND MERGÉ": bundle.get("backend_report_merged") or {},
        "RAW BACKEND": bundle.get("raw_backend_report") or {},
        "BACKEND REPORT": bundle.get("backend_report") or {},
        "FULL REPORT": bundle.get("full_report") or {},
        "UI REPORT": bundle.get("ui_report") or {},
        "ENGINE PARAMS": bundle.get("engine_params") or {},
        "SAISIE HOME": bundle.get("saisie_home") or {},
        "PIÈCE SÉLECTIONNÉE": bundle.get("selected_piece") or {},
        "ARCHITECTURE SÉLECTIONNÉE": {
            "selected_architecture": bundle.get("selected_architecture"),
            "selected_architecture_candidate": bundle.get("selected_architecture_candidate"),
        },
        "ERREURS": bundle.get("errors") or {},
        "SOURCES BRUTES": bundle.get("all_sources_raw") or {},
    }


def filter_json_data(data: Any, query: str) -> Any:
    query = (query or "").strip().lower()
    if not query:
        return data

    def match_scalar(value: Any) -> bool:
        return query in str(value).lower()

    def walk(node: Any) -> Any:
        if isinstance(node, Mapping):
            out: Dict[str, Any] = {}

            for key, value in node.items():
                key_match = query in str(key).lower()
                child = walk(value)

                if key_match:
                    out[str(key)] = _jsonable(value)
                elif child not in (None, {}, []):
                    out[str(key)] = child

            return out

        if isinstance(node, list):
            kept = []

            for item in node:
                child = walk(item)
                if child not in (None, {}, []):
                    kept.append(child)

            return kept

        return node if match_scalar(node) else None

    result = walk(data)
    return result if result not in (None, {}, []) else {
        "filtre": query,
        "resultat": "Aucune correspondance dans la source sélectionnée.",
    }


# =============================================================================
# Écran JSON brut
# =============================================================================

class RawJsonScreen(Screen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.viewer = JsonViewer()
        self.source_map: Dict[str, Any] = {}
        self.current_source_name = "COMPLET"
        self.current_data: Any = {}
        self.query = ""
        self.last_message = ""

        self.source_spinner: Spinner
        self.search_input: TextInput
        self.status_badge: StatusBadge
        self.summary_panel: PremiumCard
        self.summary_grid: GridLayout
        self.message_label: Label

        self._build_ui()

    # -------------------------------------------------------------------------
    # UI
    # -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.clear_widgets()

        root = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(10),
        )

        root.add_widget(self._top_bar())
        root.add_widget(self._controls())
        root.add_widget(self._summary())
        root.add_widget(self.viewer)

        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(54),
            spacing=dp(10),
            padding=[dp(10), dp(5)],
        )

        lbl = Label(
            text="DONNÉES BRUTES / DEBUG JSON",
            color=COLORS["BFW"],
            bold=True,
            font_size="16sp",
            halign="left",
            valign="middle",
        )
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)

        self.status_badge = StatusBadge(status="missing", size_hint_x=None, width=dp(110))
        bar.add_widget(self.status_badge)

        buttons = (
            ("RAFRAÎCHIR", self.refresh_data, 110),
            ("COPIER", self.copy_json, 100),
            ("SAUVER", self.save_json, 100),
            ("SAUVER TOUT", self.save_all_json, 125),
            ("DASHBOARD", self.go_dashboard, 130),
        )

        for text, cb, width in buttons:
            btn = ModernButton(text=text, size_hint_x=None, width=dp(width), font_size="11sp")
            btn.bind(on_release=cb)
            bar.add_widget(btn)

        return bar

    def _controls(self) -> BoxLayout:
        controls = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(46),
            spacing=dp(10),
            padding=[dp(10), 0],
        )

        self.source_spinner = Spinner(
            text=self.current_source_name,
            values=("COMPLET",),
            size_hint_x=None,
            width=dp(230),
            background_normal="",
            background_color=COLORS["BFW"],
            color=COLORS["BL"],
            bold=True,
            font_size="12sp",
        )
        self.source_spinner.bind(text=self._on_source_changed)
        controls.add_widget(self.source_spinner)

        self.search_input = TextInput(
            text="",
            hint_text="Rechercher dans le JSON : puissance, pme, architecture, erreur, pièce...",
            multiline=False,
            background_color=COLORS["BL"],
            foreground_color=COLORS["BFW"],
            cursor_color=COLORS["RS"],
            font_size="12sp",
            padding=[dp(10), dp(8)],
        )
        self.search_input.bind(text=self._on_search_changed)
        controls.add_widget(self.search_input)

        clear_btn = ModernButton(text="CLEAR", size_hint_x=None, width=dp(90), font_size="11sp")
        clear_btn.bind(on_release=lambda *_: setattr(self.search_input, "text", ""))
        controls.add_widget(clear_btn)

        return controls

    def _summary(self) -> PremiumCard:
        self.summary_panel = PremiumCard(
            title="Résumé JSON",
            size_hint_y=None,
            height=dp(108),
        )

        self.summary_grid = GridLayout(cols=5, spacing=dp(8), size_hint_y=None, height=dp(46))
        self.summary_panel.add_widget(self.summary_grid)

        self.message_label = Label(
            text="",
            color=COLORS["GS"],
            font_size="11sp",
            size_hint_y=None,
            height=dp(28),
            halign="left",
            valign="middle",
        )
        self.message_label.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        self.summary_panel.add_widget(self.message_label)

        return self.summary_panel

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def on_enter(self, *_: Any) -> None:
        self.refresh_data()

    def refresh_data(self, *_: Any) -> None:
        app = App.get_running_app()
        self.source_map = build_source_map(app)

        source_names = tuple(self.source_map.keys())
        self.source_spinner.values = source_names

        if self.current_source_name not in self.source_map:
            self.current_source_name = "COMPLET"

        self.source_spinner.text = self.current_source_name
        self.current_data = self.source_map.get(self.current_source_name, {})

        self._render_current()

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def _render_current(self) -> None:
        data = self.current_data
        if self.query:
            data = filter_json_data(data, self.query)

        self._set_viewer_text(_json_dumps(data) if data else "AUCUN RAPPORT DISPONIBLE")
        self._render_summary(data)

    def _set_viewer_text(self, text: str) -> None:
        try:
            self.viewer.text_input.text = text
        except Exception:
            pass

    def _render_summary(self, data: Any) -> None:
        nodes = _count_nodes(data)
        unknowns = _count_unknowns(data)
        alerts = _count_alerts(data)

        text = _json_dumps(data) if data else ""
        size_kb = len(text.encode("utf-8")) / 1024 if text else 0.0

        status = _status_for_data(data)
        self.status_badge.status = status
        self.status_badge.text = status.upper()

        self.summary_grid.clear_widgets()
        self.summary_grid.add_widget(MetricRow("Source", self.current_source_name, "", status))
        self.summary_grid.add_widget(MetricRow("Nœuds", nodes, "", "ok" if nodes else "missing"))
        self.summary_grid.add_widget(MetricRow("Taille", f"{size_kb:.1f}", "kio", "ok" if size_kb else "missing"))
        self.summary_grid.add_widget(MetricRow("Inconnues", unknowns, "", "alerte" if unknowns else "ok"))
        self.summary_grid.add_widget(MetricRow("Alertes", alerts, "", "alerte" if alerts else "ok"))

        if self.last_message:
            self.message_label.text = _short_text(self.last_message, 220)
        elif self.query:
            self.message_label.text = f"Filtre actif : {self.query!r}"
        else:
            self.message_label.text = "Affichage JSON complet de la source sélectionnée."

    # -------------------------------------------------------------------------
    # Events
    # -------------------------------------------------------------------------

    def _on_source_changed(self, _: Spinner, value: str) -> None:
        self.current_source_name = value
        self.current_data = self.source_map.get(value, {})
        self.last_message = ""
        self._render_current()

    def _on_search_changed(self, _: TextInput, value: str) -> None:
        self.query = value.strip()
        self.last_message = ""
        self._render_current()

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def copy_json(self, *_: Any) -> None:
        try:
            Clipboard.copy(self.viewer.text_input.text)
            self.last_message = "JSON copié dans le presse-papiers."
        except Exception as exc:
            self.last_message = f"Copie impossible : {exc}"

        self._render_current()

    def save_json(self, *_: Any) -> None:
        try:
            data = self.current_data
            if self.query:
                data = filter_json_data(data, self.query)

            if not data:
                self.last_message = "Aucune donnée à sauvegarder."
                self._render_current()
                return

            output_dir = self._output_dir()
            filename = f"{self._safe_filename(self.current_source_name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            path = output_dir / filename

            _write_json(path, data)
            self.last_message = f"JSON sauvegardé : {path}"

        except Exception as exc:
            self.last_message = f"Sauvegarde impossible : {exc}\n{traceback.format_exc()}"

        self._render_current()

    def save_all_json(self, *_: Any) -> None:
        try:
            app = App.get_running_app()
            bundle = build_complete_debug_bundle(app)

            output_dir = self._output_dir()
            path = output_dir / f"debug_bundle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            _write_json(path, bundle)
            self.last_message = f"Bundle complet sauvegardé : {path}"

        except Exception as exc:
            self.last_message = f"Sauvegarde du bundle impossible : {exc}\n{traceback.format_exc()}"

        self._render_current()

    def go_dashboard(self, *_: Any) -> None:
        if self.manager is not None:
            self.manager.current = "dashboard"

    # -------------------------------------------------------------------------
    # Paths
    # -------------------------------------------------------------------------

    def _output_dir(self) -> Path:
        app = App.get_running_app()

        raw = _first_non_empty(
            getattr(app, "debug_output_dir", None),
            getattr(app, "export_dir", None),
            getattr(app, "exports_dir", None),
            Path.cwd() / "output",
        )

        path = Path(raw).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    def _safe_filename(self, value: str) -> str:
        raw = str(value or "json").strip().lower()
        out = []

        for char in raw:
            if char.isalnum():
                out.append(char)
            else:
                out.append("_")

        return "_".join(part for part in "".join(out).split("_") if part) or "json"


RawReportViewScreen = RawJsonScreen