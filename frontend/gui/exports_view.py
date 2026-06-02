# frontend/gui/exports.py
from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

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
from frontend.gui.backend_resource_adapter import build_resource_catalog


# =============================================================================
# Helpers stricts
# =============================================================================

def _is_finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _deep_get(data: Any, *path: str) -> Any:
    cur = data
    for key in path:
        if isinstance(cur, Mapping):
            cur = cur.get(key)
        else:
            return None
        if cur is None:
            return None
    return cur


def _merge_dict_non_none(base: Optional[Dict[str, Any]], extra: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    out = dict(base or {})

    if not isinstance(extra, Mapping):
        return out

    for key, value in extra.items():
        if value is None:
            continue

        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[str(key)] = _merge_dict_non_none(dict(out[key]), value)
        else:
            out[str(key)] = value

    return out


def _short_text(value: Any, max_len: int = 90) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _jsonable(value: Any, *, depth: int = 0, max_depth: int = 8) -> Any:
    if depth > max_depth:
        return {"type": type(value).__name__, "truncated": True}

    if value is None or isinstance(value, (str, int, float, bool)):
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
            return {
                "type": type(value).__name__,
                "attributs": _jsonable(
                    {
                        k: v
                        for k, v in vars(value).items()
                        if not k.startswith("_") and not callable(v)
                    },
                    depth=depth + 1,
                    max_depth=max_depth,
                ),
            }
        except Exception:
            pass

    return str(value)


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


def _count_items(value: Any) -> int:
    if isinstance(value, Mapping):
        return len(value)
    if isinstance(value, list):
        return len(value)
    if value is None:
        return 0
    return 1


def _status_from_available(available: bool, error: bool = False) -> str:
    if error:
        return "erreur"
    return "disponible" if available else "indisponible"


def _open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


# =============================================================================
# Extraction backend
# =============================================================================

class BackendExportCollector:
    REPORT_ATTRS: Tuple[str, ...] = (
        "backend_report",
        "last_backend_report",
        "full_report",
        "last_full_report",
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

    JSON_PATH_ATTRS: Tuple[str, ...] = (
        "backend_report_path",
        "last_report_path",
        "report_path",
        "output_json_path",
        "toutes_les_donnees_path",
    )

    JSON_NAMES: Tuple[str, ...] = (
        "toutes_les_donnees_completes.json",
        "systeme_complet.json",
        "rapport_systeme.json",
        "rapport_backend.json",
        "test_systeme_complet.json",
    )

    def __init__(self, app: Any) -> None:
        self.app = app
        self.sources: List[str] = []
        self.errors: List[Dict[str, Any]] = []

    def collect(self) -> Dict[str, Any]:
        reports: List[Dict[str, Any]] = []

        reports.extend(self._read_app_reports())
        reports.extend(self._read_json_reports())

        backend_report: Dict[str, Any] = {}
        for report in reports:
            backend_report = _merge_dict_non_none(backend_report, report)

        ui_report = _safe_dict(getattr(self.app, "ui_report", {}) or {})

        # Certains écrans stockent déjà des sections exportables dans ui_report.
        if ui_report:
            backend_report.setdefault("ui_report", ui_report)

        backend_report["_exports_sources"] = list(dict.fromkeys(self.sources))
        if self.errors:
            backend_report["_exports_errors"] = self.errors

        try:
            self.app.backend_report = backend_report
            self.app.full_report = backend_report
        except Exception:
            pass

        return {
            "backend_report": backend_report,
            "ui_report": ui_report,
            "sources": self.sources,
            "errors": self.errors,
        }

    def _push_error(self, source: str, error: Any) -> None:
        self.errors.append(
            {
                "source": source,
                "erreur": str(error),
            }
        )

    def _read_app_reports(self) -> List[Dict[str, Any]]:
        reports: List[Dict[str, Any]] = []

        for attr in self.REPORT_ATTRS:
            try:
                value = getattr(self.app, attr, None)
            except Exception:
                continue

            if isinstance(value, Mapping):
                reports.append(dict(value))
                self.sources.append(f"app.{attr}")

        return reports

    def _read_json_reports(self) -> List[Dict[str, Any]]:
        reports: List[Dict[str, Any]] = []
        raw_paths: List[Any] = []

        for attr in self.JSON_PATH_ATTRS:
            try:
                value = getattr(self.app, attr, None)
            except Exception:
                value = None

            if value:
                raw_paths.append(value)

        cwd = Path.cwd()

        for name in self.JSON_NAMES:
            raw_paths.append(cwd / name)
            raw_paths.append(cwd / "backend" / name)
            raw_paths.append(cwd / "backend" / "outputs" / name)
            raw_paths.append(cwd / "exports" / name)

        seen: set[str] = set()

        for raw in raw_paths:
            try:
                path = Path(raw).expanduser().resolve()
            except Exception:
                continue

            if str(path) in seen:
                continue
            seen.add(str(path))

            if not path.is_file():
                continue

            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, Mapping):
                    report = dict(data)
                    report.setdefault("_json_path", str(path))
                    reports.append(report)
                    self.sources.append(f"json:{path}")
            except Exception as exc:
                self._push_error(f"json:{path}", exc)

        return reports


# =============================================================================
# Export descriptors
# =============================================================================

@dataclass
class ExportItem:
    key: str
    label: str
    filename: str
    fmt: str
    data: Any = None
    available: bool = False
    status: str = "indisponible"
    reason: str = ""
    path: Optional[Path] = None
    readonly_existing: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)


def _unknown_rows(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, Mapping):
            inc = node.get("inconnues")
            if isinstance(inc, Mapping):
                for category, values in inc.items():
                    for item in _safe_list(values):
                        if isinstance(item, Mapping):
                            rows.append(
                                {
                                    "categorie": category,
                                    "source": path or "racine",
                                    "nom": item.get("nom") or item.get("champ") or item.get("piece") or "",
                                    "raison": item.get("raison") or item.get("detail") or "",
                                }
                            )

            inconnues_cao = node.get("inconnues_cao")
            if isinstance(inconnues_cao, list):
                for item in inconnues_cao:
                    if isinstance(item, Mapping):
                        rows.append(
                            {
                                "categorie": "cao",
                                "source": path or "cao",
                                "nom": item.get("nom") or item.get("champ") or item.get("piece") or "",
                                "raison": item.get("raison") or item.get("detail") or "",
                            }
                        )

            for key, value in node.items():
                if isinstance(value, (Mapping, list)):
                    walk(value, f"{path}.{key}" if path else str(key))

        elif isinstance(node, list):
            for idx, value in enumerate(node):
                if isinstance(value, (Mapping, list)):
                    walk(value, f"{path}[{idx}]")

    walk(report)

    seen: set[Tuple[str, str, str, str]] = set()
    out: List[Dict[str, Any]] = []

    for row in rows:
        sig = (
            str(row.get("categorie", "")),
            str(row.get("source", "")),
            str(row.get("nom", "")),
            str(row.get("raison", "")),
        )
        if sig in seen:
            continue
        seen.add(sig)
        out.append(row)

    return out


def _alert_rows(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, Mapping):
            alerts = node.get("alertes")
            if isinstance(alerts, Mapping):
                for category, values in alerts.items():
                    for item in _safe_list(values):
                        if isinstance(item, Mapping):
                            rows.append(
                                {
                                    "categorie": category,
                                    "source": path or "racine",
                                    "nom": item.get("nom") or item.get("label") or "",
                                    "detail": item.get("detail") or item.get("raison") or item.get("value") or "",
                                }
                            )

            for key, value in node.items():
                if isinstance(value, (Mapping, list)):
                    walk(value, f"{path}.{key}" if path else str(key))

        elif isinstance(node, list):
            for idx, value in enumerate(node):
                if isinstance(value, (Mapping, list)):
                    walk(value, f"{path}[{idx}]")

    walk(report)

    seen: set[Tuple[str, str, str, str]] = set()
    out: List[Dict[str, Any]] = []

    for row in rows:
        sig = (
            str(row.get("categorie", "")),
            str(row.get("source", "")),
            str(row.get("nom", "")),
            str(row.get("detail", "")),
        )
        if sig in seen:
            continue
        seen.add(sig)
        out.append(row)

    return out


def _dashboard_rows(ui_report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    dash = _safe_dict(ui_report.get("dashboard"))

    for section_name in ("energy_chain", "alerts", "unknowns"):
        for item in _safe_list(dash.get(section_name)):
            if not isinstance(item, Mapping):
                continue

            rows.append(
                {
                    "section": section_name,
                    "label": item.get("label") or item.get("name") or "",
                    "value": item.get("value") or "",
                    "unit": item.get("unit") or "",
                    "status": item.get("status") or "",
                }
            )

    for item in _safe_list(dash.get("subsystems")):
        if not isinstance(item, Mapping):
            continue

        rows.append(
            {
                "section": "subsystems",
                "label": item.get("name") or "",
                "value": item.get("status") or "",
                "unit": "",
                "status": item.get("status") or "",
            }
        )

    return rows


def _make_export_dir(app: Any) -> Path:
    raw = _first_non_empty(
        getattr(app, "export_dir", None),
        getattr(app, "exports_dir", None),
        getattr(app, "backend_export_dir", None),
    )

    if raw:
        path = Path(raw).expanduser()
    else:
        path = Path.cwd() / "exports"

    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def build_export_items(
    *,
    backend_report: Mapping[str, Any],
    ui_report: Mapping[str, Any],
    export_dir: Path,
) -> List[ExportItem]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def item(
        key: str,
        label: str,
        filename: str,
        fmt: str,
        data: Any,
        reason_if_missing: str,
        *,
        meta: Optional[Dict[str, Any]] = None,
    ) -> ExportItem:
        available = data is not None
        if isinstance(data, Mapping) and not data:
            available = False
        if isinstance(data, list) and not data:
            available = False

        return ExportItem(
            key=key,
            label=label,
            filename=filename,
            fmt=fmt,
            data=data,
            available=available,
            status=_status_from_available(available),
            reason="" if available else reason_if_missing,
            path=export_dir / filename,
            meta=meta or {},
        )

    items: List[ExportItem] = [
        item(
            "backend_full_json",
            "Rapport backend complet",
            f"backend_report_full_{timestamp}.json",
            "json",
            dict(backend_report) if backend_report else None,
            "Aucun rapport backend complet en mémoire.",
        ),
        item(
            "ui_report_json",
            "Rapport UI complet",
            f"ui_report_full_{timestamp}.json",
            "json",
            dict(ui_report) if ui_report else None,
            "Aucun ui_report disponible.",
        ),
        item(
            "resume_gui_json",
            "Résumé GUI",
            f"resume_gui_{timestamp}.json",
            "json",
            backend_report.get("resume_gui") or ui_report.get("resume_gui"),
            "Bloc resume_gui absent.",
        ),
        item(
            "systeme_complet_json",
            "Système complet",
            f"systeme_complet_{timestamp}.json",
            backend_report.get("systeme_complet"),
            "json",
            backend_report.get("systeme_complet"),
            "Bloc systeme_complet absent.",
        ),
        item(
            "cao_json",
            "Definition / CAO",
            f"cao_solidworks_{timestamp}.json",
            "json",
            backend_report.get("cao") or ui_report.get("cao"),
            "Bloc CAO absent.",
        ),
        item(
            "analyses_composants_json",
            "Analyses composants",
            f"analyses_composants_{timestamp}.json",
            "json",
            backend_report.get("analyses_composants"),
            "Bloc analyses_composants absent.",
        ),
        item(
            "construction_pieces_json",
            "Construction pièces",
            f"construction_pieces_{timestamp}.json",
            "json",
            backend_report.get("construction_pieces"),
            "Bloc construction_pieces absent.",
        ),
        item(
            "rapports_pieces_json",
            "Rapports pièces",
            f"rapports_pieces_{timestamp}.json",
            "json",
            backend_report.get("rapports_pieces"),
            "Bloc rapports_pieces absent.",
        ),
        item(
            "optimisation_json",
            "Optimisation inter-pièces",
            f"optimisation_{timestamp}.json",
            "json",
            backend_report.get("optimisation"),
            "Bloc optimisation absent.",
        ),
        item(
            "architecture_candidates_json",
            "Candidats architecture",
            f"architecture_candidates_{timestamp}.json",
            "json",
            ui_report.get("architecture_candidates") or backend_report.get("architecture_candidates"),
            "Aucun candidat d’architecture disponible.",
        ),
        item(
            "unknowns_csv",
            "Inconnues consolidées CSV",
            f"inconnues_{timestamp}.csv",
            "csv",
            _unknown_rows(backend_report),
            "Aucune inconnue consolidée trouvée.",
            meta={"columns": ["categorie", "source", "nom", "raison"]},
        ),
        item(
            "alerts_csv",
            "Alertes consolidées CSV",
            f"alertes_{timestamp}.csv",
            "csv",
            _alert_rows(backend_report),
            "Aucune alerte consolidée trouvée.",
            meta={"columns": ["categorie", "source", "nom", "detail"]},
        ),
        item(
            "dashboard_csv",
            "Dashboard CSV",
            f"dashboard_{timestamp}.csv",
            "csv",
            _dashboard_rows(ui_report),
            "Aucune donnée dashboard exportable.",
            meta={"columns": ["section", "label", "value", "unit", "status"]},
        ),
    ]

    # Intégration des exports déjà déclarés par le front.
    resource_catalog = _safe_dict(ui_report.get("resources"))
    if not resource_catalog:
        resource_payload = build_resource_catalog(dict(backend_report))
        resource_catalog = _safe_dict(resource_payload.get("resources"))

    for rtype in ("pdf", "json", "cao"):
        for resource_idx, resource in enumerate(_safe_list(resource_catalog.get(rtype))):
            if not isinstance(resource, Mapping):
                continue

            status = str(resource.get("status") or "unavailable")
            path_value = resource.get("path")
            path = Path(path_value).expanduser() if path_value else None
            data = resource.get("data") if resource.get("data") is not None else None
            is_existing_file = bool(path and path.is_file())
            export_fmt = "json" if rtype in {"json", "cao"} else "pdf"

            items.append(
                ExportItem(
                    key=f"resource_{rtype}_{resource_idx}",
                    label=str(resource.get("name") or f"Ressource {rtype}"),
                    filename=path.name if path else f"resource_{rtype}_{resource_idx + 1}_{timestamp}.json",
                    fmt=export_fmt,
                    data=data if data is not None else dict(resource),
                    available=(status == "available" and (data is not None or is_existing_file)),
                    status=status,
                    reason=str(resource.get("reason") or ("Fichier existant" if is_existing_file else "")),
                    path=path or (export_dir / f"resource_{rtype}_{resource_idx + 1}_{timestamp}.json"),
                    readonly_existing=is_existing_file,
                    meta=dict(resource),
                )
            )

    for idx, raw in enumerate(_safe_list(ui_report.get("exports"))):
        if not isinstance(raw, Mapping):
            continue

        path_value = raw.get("path")
        path = Path(path_value).expanduser() if path_value else None

        items.append(
            ExportItem(
                key=str(raw.get("key") or f"ui_export_{idx}"),
                label=str(raw.get("label") or raw.get("name") or f"Export UI {idx + 1}"),
                filename=path.name if path else f"ui_export_{idx + 1}_{timestamp}.json",
                fmt=str(raw.get("format") or raw.get("fmt") or "json"),
                data=raw.get("value") or raw.get("data"),
                available=bool(raw.get("available")) or (path.is_file() if path else False),
                status=str(raw.get("status") or ("disponible" if raw.get("available") else "indisponible")),
                reason=str(raw.get("reason") or ""),
                path=path or (export_dir / f"ui_export_{idx + 1}_{timestamp}.json"),
                readonly_existing=bool(path and path.is_file() and raw.get("data") is None and raw.get("value") is None),
                meta=dict(raw),
            )
        )

    # Déduplication par key + label.
    seen: set[Tuple[str, str]] = set()
    out: List[ExportItem] = []

    for exp in items:
        sig = (exp.key, exp.label)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(exp)

    return out


def write_export(item: ExportItem) -> Path:
    if item.path is None:
        raise ValueError("Chemin d'export absent.")

    item.path.parent.mkdir(parents=True, exist_ok=True)

    if item.readonly_existing and item.path.is_file():
        return item.path

    if not item.available:
        raise ValueError(item.reason or "Export indisponible.")

    if item.fmt.lower() == "json":
        item.path.write_text(
            json.dumps(_jsonable(item.data), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return item.path

    if item.fmt.lower() == "csv":
        rows = _safe_list(item.data)
        columns = _safe_list(item.meta.get("columns"))

        if not rows:
            raise ValueError("Aucune ligne CSV à exporter.")

        if not columns:
            first = rows[0]
            columns = list(first.keys()) if isinstance(first, Mapping) else ["value"]

        with item.path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[str(c) for c in columns], delimiter=";")
            writer.writeheader()

            for row in rows:
                if isinstance(row, Mapping):
                    writer.writerow({str(c): row.get(c, "") for c in columns})
                else:
                    writer.writerow({"value": row})

        return item.path

    raise ValueError(f"Format non supporté : {item.fmt!r}")


# =============================================================================
# Écran exports
# =============================================================================

class ExportsScreen(Screen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.export_items: List[ExportItem] = []
        self.export_dir: Optional[Path] = None
        self.last_message = ""
        self.last_errors: List[Dict[str, Any]] = []
        self.last_sources: List[str] = []

    def on_enter(self, *_: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()

        app = App.get_running_app()

        collector = BackendExportCollector(app)
        payload = collector.collect()

        backend_report = _safe_dict(payload.get("backend_report"))
        ui_report = _safe_dict(payload.get("ui_report"))

        self.last_errors = [dict(e) for e in _safe_list(payload.get("errors")) if isinstance(e, Mapping)]
        self.last_sources = [str(s) for s in _safe_list(payload.get("sources"))]

        self.export_dir = _make_export_dir(app)
        self.export_items = build_export_items(
            backend_report=backend_report,
            ui_report=ui_report,
            export_dir=self.export_dir,
        )

        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        root.add_widget(self._top_bar())
        root.add_widget(self._summary_panel())

        available = [item for item in self.export_items if item.available or item.readonly_existing]

        if not self.export_items or not available:
            root.add_widget(
                EmptyState(
                    text="Exports indisponibles : aucun rapport backend exploitable.",
                    action_text="RETOUR DASHBOARD",
                    callback=lambda *_: self._go("dashboard"),
                )
            )
            self.add_widget(root)
            return

        scroll = ScrollView(do_scroll_x=False)
        grid = GridLayout(cols=2, spacing=dp(12), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        for item in self.export_items:
            grid.add_widget(self._card(item))

        scroll.add_widget(grid)
        root.add_widget(scroll)
        self.add_widget(root)

    # -------------------------------------------------------------------------
    # UI
    # -------------------------------------------------------------------------

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(58),
            spacing=dp(10),
        )

        lbl = Label(
            text="EXPORTS BACKEND / CAO / AUDIT",
            color=COLORS["BFW"],
            bold=True,
            font_size="18sp",
            halign="left",
            valign="middle",
        )
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)

        buttons = (
            ("RAFRAÎCHIR", self.refresh, 120),
            ("TOUT EXPORTER", self.export_all, 150),
            ("DOSSIER", self.open_export_folder, 110),
            ("DASHBOARD", lambda *_: self._go("dashboard"), 140),
        )

        for text, callback, width in buttons:
            btn = ModernButton(text=text, size_hint_x=None, width=dp(width), font_size="11sp")
            btn.bind(on_release=callback)
            bar.add_widget(btn)

        return bar

    def _summary_panel(self) -> PremiumCard:
        available_count = sum(1 for item in self.export_items if item.available or item.readonly_existing)
        unavailable_count = len(self.export_items) - available_count
        exported_count = sum(1 for item in self.export_items if item.path and item.path.is_file())

        panel = PremiumCard(title="Résumé exports", size_hint_y=None, height=dp(118))

        grid = GridLayout(cols=5, spacing=dp(8), size_hint_y=None, height=dp(48))
        grid.add_widget(MetricRow("Exports détectés", len(self.export_items), "", "ok" if self.export_items else "missing"))
        grid.add_widget(MetricRow("Disponibles", available_count, "", "ok" if available_count else "missing"))
        grid.add_widget(MetricRow("Indisponibles", unavailable_count, "", "alerte" if unavailable_count else "ok"))
        grid.add_widget(MetricRow("Fichiers existants", exported_count, "", "ok" if exported_count else "missing"))
        grid.add_widget(MetricRow("Sources backend", len(self.last_sources), "", "ok" if self.last_sources else "missing"))
        panel.add_widget(grid)

        message = self.last_message or f"Dossier : {self.export_dir or Path.cwd() / 'exports'}"
        lbl = Label(
            text=_short_text(message, 180),
            color=COLORS["BFW"],
            font_size="11sp",
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(26),
        )
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        panel.add_widget(lbl)

        if self.last_errors:
            err = self.last_errors[0]
            panel.add_widget(
                Label(
                    text=_short_text(f"Erreur source : {err.get('source')} — {err.get('erreur')}", 180),
                    color=COLORS["RS"],
                    font_size="10sp",
                    halign="left",
                    size_hint_y=None,
                    height=dp(22),
                )
            )

        return panel

    def _card(self, item: ExportItem) -> NeoCard:
        error = item.status.lower() in {"erreur", "error"}
        status = _status_from_available(item.available or item.readonly_existing, error=error)

        card = NeoCard(
            orientation="vertical",
            size_hint_y=None,
            height=dp(230),
            spacing=dp(6),
            padding=dp(10),
        )

        card.add_widget(SectionTitle(text=str(item.label).upper()))
        card.add_widget(StatusBadge(status=status, size_hint_y=None, height=dp(26)))

        card.add_widget(MetricRow("Format", item.fmt.upper(), "", status))
        card.add_widget(MetricRow("Disponible", "Oui" if item.available or item.readonly_existing else "Non", "", status))
        card.add_widget(MetricRow("Éléments", _count_items(item.data), "", status))
        card.add_widget(MetricRow("Nœuds", _count_nodes(item.data), "", status))

        reason = item.reason or ("Fichier existant" if item.readonly_existing else "")
        card.add_widget(MetricRow("Raison", _short_text(reason, 48), "", "alerte" if reason else "ok"))

        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(38), spacing=dp(8))

        export_btn = ModernButton(text="EXPORTER", font_size="10sp")
        export_btn.disabled = not (item.available or item.readonly_existing)
        export_btn.bind(on_release=lambda *_args, exp=item: self.export_one(exp))
        btn_row.add_widget(export_btn)

        copy_btn = ModernButton(text="COPIER CHEMIN", font_size="10sp")
        copy_btn.disabled = item.path is None
        copy_btn.bind(on_release=lambda *_args, exp=item: self.copy_path(exp))
        btn_row.add_widget(copy_btn)

        card.add_widget(btn_row)

        return card

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def export_one(self, item: ExportItem, *_: Any) -> None:
        try:
            path = write_export(item)
            self.last_message = f"Export généré : {path}"
            Clipboard.copy(str(path))
        except Exception as exc:
            self.last_message = f"Échec export {item.label} : {exc}"
            self.last_errors.append(
                {
                    "source": f"export:{item.key}",
                    "erreur": f"{exc}\n{traceback.format_exc()}",
                }
            )

        self.refresh()

    def export_all(self, *_: Any) -> None:
        ok = 0
        failed = 0

        for item in self.export_items:
            if not (item.available or item.readonly_existing):
                continue

            try:
                write_export(item)
                ok += 1
            except Exception as exc:
                failed += 1
                self.last_errors.append(
                    {
                        "source": f"export_all:{item.key}",
                        "erreur": f"{exc}\n{traceback.format_exc()}",
                    }
                )

        self.last_message = f"Exports terminés : {ok} fichier(s) généré(s), {failed} échec(s)."
        self.refresh()

    def copy_path(self, item: ExportItem, *_: Any) -> None:
        if item.path is None:
            self.last_message = "Aucun chemin à copier."
        else:
            Clipboard.copy(str(item.path))
            self.last_message = f"Chemin copié : {item.path}"

        self.refresh()

    def open_export_folder(self, *_: Any) -> None:
        try:
            folder = self.export_dir or Path.cwd() / "exports"
            _open_folder(folder)
            self.last_message = f"Dossier ouvert : {folder}"
        except Exception as exc:
            self.last_message = f"Impossible d’ouvrir le dossier : {exc}"
            self.last_errors.append(
                {
                    "source": "open_export_folder",
                    "erreur": f"{exc}\n{traceback.format_exc()}",
                }
            )

        self.refresh()

    def _go(self, screen_name: str) -> None:
        if self.manager is not None:
            self.manager.current = screen_name
