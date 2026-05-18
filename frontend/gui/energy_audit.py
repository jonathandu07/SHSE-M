# frontend/gui/energy_audit.py
from __future__ import annotations

import inspect
import json
import math
import threading
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from frontend.gui.components import (
    COLORS,
    EmptyState,
    JsonTreeView,
    MetricRow,
    ModernButton,
    PremiumCard,
    StatusBadge,
)


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


def _short_text(value: Any, max_len: int = 110) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _count_nodes(value: Any, *, max_depth: int = 8, depth: int = 0) -> int:
    if depth > max_depth:
        return 1

    if isinstance(value, Mapping):
        return 1 + sum(_count_nodes(v, max_depth=max_depth, depth=depth + 1) for v in value.values())

    if isinstance(value, list):
        return 1 + sum(_count_nodes(v, max_depth=max_depth, depth=depth + 1) for v in value)

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


def _section_status(value: Any) -> str:
    if value is None:
        return "missing"

    unknowns = _count_unknowns(value)
    alerts = _count_alerts(value)

    if unknowns > 0:
        return "alerte"
    if alerts > 0:
        return "alerte"

    if isinstance(value, Mapping) and value.get("erreur"):
        return "erreur"

    return "ok"


def _filter_kwargs(fn: Callable[..., Any], params: Mapping[str, Any]) -> Dict[str, Any]:
    clean = {str(k): v for k, v in dict(params or {}).items() if v is not None}

    try:
        sig = inspect.signature(fn)
    except Exception:
        return clean

    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return clean

    accepted = set(sig.parameters.keys())
    return {k: v for k, v in clean.items() if k in accepted}


def _has_power_target(params: Mapping[str, Any]) -> bool:
    for key in (
        "puissance_traction_kw",
        "production_electrique_sortie_w",
        "puissance_bus_dc_w",
        "puissance_moteur_requise_W",
    ):
        value = params.get(key)
        if _is_finite(value) and float(value) > 0.0:
            return True

    return False


# =============================================================================
# Collecteur d'audit backend
# =============================================================================

class BackendAuditCollector:
    """
    Récupère le maximum de données disponibles pour l'audit technique.

    Sources :
    - rapports déjà présents dans App ;
    - hooks éventuels de l'App ;
    - exports JSON ;
    - rafraîchissement via frontend.main si demandé.
    """

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

    APP_HOOKS: Tuple[str, ...] = (
        "get_backend_report",
        "collect_backend_report",
        "fetch_backend_report",
        "load_backend_report",
        "refresh_backend_report",
        "sync_backend_report",
        "compute_backend_report",
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

    def collect(self, *, force_recalculate: bool = False) -> Dict[str, Any]:
        reports: List[Dict[str, Any]] = []

        reports.extend(self._read_app_reports())
        reports.extend(self._call_app_hooks())
        reports.extend(self._read_json_reports())

        if force_recalculate:
            direct = self._call_backend_main()
            if direct is not None:
                reports.append(direct)

        # Relire après hooks/recalcul, car l'App peut avoir muté app.backend_report.
        reports.extend(self._read_app_reports())

        backend_report: Dict[str, Any] = {}
        for report in reports:
            backend_report = _merge_dict_non_none(backend_report, report)

        backend_report["_energy_audit_sources"] = list(dict.fromkeys(self.sources))
        if self.errors:
            backend_report["_energy_audit_errors"] = self.errors

        ui_report = _safe_dict(getattr(self.app, "ui_report", {}) or {})
        raw_sections = build_raw_sections(ui_report=ui_report, backend_report=backend_report)

        ui_report = _merge_dict_non_none(
            ui_report,
            {
                "raw_sections": raw_sections,
                "energy_audit_sources": backend_report.get("_energy_audit_sources", []),
                "energy_audit_errors": backend_report.get("_energy_audit_errors", []),
            },
        )

        try:
            self.app.backend_report = backend_report
            self.app.full_report = backend_report
            self.app.ui_report = ui_report
        except Exception:
            pass

        return {
            "backend_report": backend_report,
            "ui_report": ui_report,
            "raw_sections": raw_sections,
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

    def _call_app_hooks(self) -> List[Dict[str, Any]]:
        reports: List[Dict[str, Any]] = []

        for name in self.APP_HOOKS:
            fn = getattr(self.app, name, None)
            if not callable(fn):
                continue

            try:
                out = fn()
            except TypeError:
                try:
                    out = fn(dict(getattr(self.app, "engine_params", {}) or {}))
                except Exception as exc:
                    self._push_error(f"app.{name}", exc)
                    continue
            except Exception as exc:
                self._push_error(f"app.{name}", exc)
                continue

            if isinstance(out, Mapping):
                reports.append(dict(out))
                self.sources.append(f"app.{name}")

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

    def _call_backend_main(self) -> Optional[Dict[str, Any]]:
        params = _safe_dict(getattr(self.app, "engine_params", {}) or {})

        if not params:
            self._push_error(
                "frontend.main.refresh_backend_data",
                "app.engine_params vide : recalcul impossible.",
            )
            return None

        if not _has_power_target(params):
            self._push_error(
                "frontend.main.refresh_backend_data",
                "cible de puissance absente : renseigner puissance_traction_kw, "
                "production_electrique_sortie_w, puissance_bus_dc_w ou puissance_moteur_requise_W.",
            )
            return None

        try:
            from frontend.main import refresh_backend_data  # type: ignore
        except Exception as exc:
            self._push_error("frontend.main.refresh_backend_data", f"import impossible : {exc}")
            return None

        try:
            state = refresh_backend_data(params)
            report = _safe_dict(state.get("raw_report")) if isinstance(state, Mapping) else {}

            if not isinstance(report, Mapping):
                self._push_error(
                    "frontend.main.refresh_backend_data",
                    f"retour non dict : {type(report).__name__}",
                )
                return None

            out = dict(report)
            out.setdefault("_source_hook", "frontend.main.refresh_backend_data")
            self.sources.append("frontend.main.refresh_backend_data")
            return out

        except Exception as exc:
            self._push_error(
                "frontend.main.refresh_backend_data",
                f"{exc}\n{traceback.format_exc()}",
            )
            return None


# =============================================================================
# Construction des sections d'audit
# =============================================================================

def _section(name: str, value: Any, *, priority: int = 100) -> Dict[str, Any]:
    return {
        "name": str(name),
        "value": value,
        "priority": int(priority),
        "status": _section_status(value),
        "nodes": _count_nodes(value) if value is not None else 0,
        "unknowns": _count_unknowns(value) if value is not None else 0,
        "alerts": _count_alerts(value) if value is not None else 0,
    }


def build_raw_sections(*, ui_report: Mapping[str, Any], backend_report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """
    Reconstruit raw_sections depuis le backend complet.

    Si ui_report contient déjà raw_sections, on les conserve, puis on ajoute
    les sections backend manquantes.
    """
    sections: List[Dict[str, Any]] = []

    for item in _safe_list(ui_report.get("raw_sections")):
        if isinstance(item, Mapping):
            sections.append(
                _section(
                    item.get("name", "section"),
                    item.get("value"),
                    priority=int(item.get("priority", 100)),
                )
            )

    def add_if_present(name: str, value: Any, priority: int) -> None:
        if value is None:
            return
        if isinstance(value, Mapping) and not value:
            return
        if isinstance(value, list) and not value:
            return
        sections.append(_section(name, value, priority=priority))

    # Sections centrales backend/main.py
    add_if_present("Résumé GUI", backend_report.get("resume_gui"), 1)
    add_if_present("Synthèse globale", backend_report.get("synthese"), 2)
    add_if_present("Système complet", backend_report.get("systeme_complet"), 3)
    add_if_present("Chaîne énergétique / liaisons", _deep_get(backend_report, "systeme_complet", "liaisons"), 4)
    add_if_present("Sous-systèmes", _deep_get(backend_report, "systeme_complet", "sous_systemes"), 5)
    add_if_present("CAO / SolidWorks", backend_report.get("cao"), 6)
    add_if_present("Analyses composants", backend_report.get("analyses_composants"), 7)
    add_if_present("Construction pièces", backend_report.get("construction_pieces"), 8)
    add_if_present("Rapports pièces", backend_report.get("rapports_pieces"), 9)
    add_if_present("Optimisation inter-pièces", backend_report.get("optimisation"), 10)
    add_if_present("Toutes données composants", backend_report.get("toutes_les_donnees_composants"), 11)
    add_if_present("Legacy", backend_report.get("legacy"), 12)
    add_if_present("Inconnues consolidées", backend_report.get("inconnues"), 13)
    add_if_present("Alertes consolidées", backend_report.get("alertes"), 14)
    add_if_present("Sources audit", backend_report.get("_energy_audit_sources"), 90)
    add_if_present("Erreurs audit", backend_report.get("_energy_audit_errors"), 91)

    # Fallback : si rien n'a été trouvé, afficher le rapport complet.
    if not sections and backend_report:
        sections.append(_section("Rapport backend complet", dict(backend_report), priority=999))

    # Déduplication par nom, en gardant la section la plus riche.
    by_name: Dict[str, Dict[str, Any]] = {}
    for sec in sections:
        name = str(sec.get("name", "section"))
        old = by_name.get(name)

        if old is None:
            by_name[name] = sec
            continue

        if int(sec.get("nodes", 0)) >= int(old.get("nodes", 0)):
            by_name[name] = sec

    out = list(by_name.values())
    out.sort(key=lambda item: (int(item.get("priority", 100)), str(item.get("name", ""))))
    return out


# =============================================================================
# Écran
# =============================================================================

class EnergyAuditScreen(Screen):
    """
    Audit technique complet.

    Version renforcée :
    - récupère les données backend complètes ;
    - reconstruit raw_sections automatiquement ;
    - affiche sources, erreurs, inconnues, alertes ;
    - permet sync mémoire et recalcul backend/main.py ;
    - filtre les sections par recherche texte.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._sync_running = False
        self._last_payload: Dict[str, Any] = {}
        self._query = ""

    def on_enter(self, *_: Any) -> None:
        self.refresh(force_collect=True, force_recalculate=False)

    # -------------------------------------------------------------------------
    # Synchronisation
    # -------------------------------------------------------------------------

    def refresh(self, *, force_collect: bool = False, force_recalculate: bool = False) -> None:
        if force_collect or force_recalculate:
            self._start_collect(force_recalculate=force_recalculate)
            return

        app = App.get_running_app()
        ui = _safe_dict(getattr(app, "ui_report", {}) or {})
        backend = _safe_dict(getattr(app, "backend_report", {}) or {})
        raw_sections = build_raw_sections(ui_report=ui, backend_report=backend)

        self._render(raw_sections=raw_sections, sources=[], errors=[], syncing=False)

    def _start_collect(self, *, force_recalculate: bool) -> None:
        if self._sync_running:
            return

        self._sync_running = True
        self._render(raw_sections=[], sources=[], errors=[], syncing=True)

        app = App.get_running_app()

        def worker() -> None:
            try:
                payload = BackendAuditCollector(app).collect(force_recalculate=force_recalculate)
            except Exception as exc:
                payload = {
                    "backend_report": {},
                    "ui_report": {},
                    "raw_sections": [],
                    "sources": [],
                    "errors": [
                        {
                            "source": "EnergyAuditScreen._start_collect",
                            "erreur": f"{exc}\n{traceback.format_exc()}",
                        }
                    ],
                }

            Clock.schedule_once(lambda *_: self._finish_collect(payload), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_collect(self, payload: Mapping[str, Any]) -> None:
        self._sync_running = False
        self._last_payload = dict(payload)

        self._render(
            raw_sections=_safe_list(payload.get("raw_sections")),
            sources=[str(s) for s in _safe_list(payload.get("sources"))],
            errors=[dict(e) for e in _safe_list(payload.get("errors")) if isinstance(e, Mapping)],
            syncing=False,
        )

    # -------------------------------------------------------------------------
    # Rendu
    # -------------------------------------------------------------------------

    def _render(
        self,
        *,
        raw_sections: List[Dict[str, Any]],
        sources: List[str],
        errors: List[Dict[str, Any]],
        syncing: bool,
    ) -> None:
        self.clear_widgets()

        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        root.add_widget(self._top_bar(syncing=syncing))
        root.add_widget(self._summary_bar(raw_sections, sources, errors, syncing=syncing))
        root.add_widget(self._search_bar())

        if syncing:
            root.add_widget(
                self._info_panel(
                    title="SYNCHRONISATION BACKEND",
                    text=(
                        "Récupération de l'audit technique depuis les rapports backend, "
                        "les hooks App, les exports JSON et, si demandé, frontend.main."
                    ),
                    status="calculée",
                )
            )
            self.add_widget(root)
            return

        filtered = self._filter_sections(raw_sections)

        if not filtered:
            root.add_widget(
                EmptyState(
                    text="Audit technique indisponible : aucune donnée backend exploitable.",
                    action_text="SYNCHRONISER",
                    callback=lambda *_: self.refresh(force_collect=True),
                )
            )
            self.add_widget(root)
            return

        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(16),
            size_hint_y=None,
            padding=[0, dp(10)],
        )
        content.bind(minimum_height=content.setter("height"))

        if errors:
            content.add_widget(self._errors_panel(errors))

        for section in filtered:
            content.add_widget(self._section_panel(section))

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self, *, syncing: bool) -> BoxLayout:
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(54),
            spacing=dp(10),
        )

        title = "AUDIT DE CONFORMITÉ TECHNIQUE — BACKEND"
        if syncing:
            title += " — SYNCHRONISATION"

        lbl = Label(
            text=title,
            color=COLORS["BFW"],
            bold=True,
            font_size="17sp",
            halign="left",
            valign="middle",
        )
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)

        btn_sync = ModernButton(text="SYNC", size_hint_x=None, width=dp(90), font_size="11sp")
        btn_sync.bind(on_release=lambda *_: self.refresh(force_collect=True, force_recalculate=False))
        bar.add_widget(btn_sync)

        btn_recalc = ModernButton(text="RECALCULER", size_hint_x=None, width=dp(130), font_size="11sp")
        btn_recalc.bind(on_release=lambda *_: self.refresh(force_collect=True, force_recalculate=True))
        bar.add_widget(btn_recalc)

        btn_json = ModernButton(text="JSON", size_hint_x=None, width=dp(80), font_size="11sp")
        btn_json.bind(on_release=lambda *_: self._go("raw_report"))
        bar.add_widget(btn_json)

        btn = ModernButton(text="RETOUR DASHBOARD", size_hint_x=None, width=dp(190), font_size="11sp")
        btn.bind(on_release=lambda *_: self._go("dashboard"))
        bar.add_widget(btn)

        return bar

    def _summary_bar(
        self,
        sections: List[Dict[str, Any]],
        sources: List[str],
        errors: List[Dict[str, Any]],
        *,
        syncing: bool,
    ) -> PremiumCard:
        panel = PremiumCard(title="Résumé audit", size_hint_y=None, height=dp(102))

        grid = GridLayout(cols=6, spacing=dp(8), size_hint_y=None, height=dp(54))

        unknowns = sum(int(sec.get("unknowns", 0)) for sec in sections)
        alerts = sum(int(sec.get("alerts", 0)) for sec in sections)
        nodes = sum(int(sec.get("nodes", 0)) for sec in sections)
        critical = sum(1 for sec in sections if sec.get("status") in {"alerte", "erreur", "missing"})

        grid.add_widget(MetricRow("Sections", len(sections), "", "ok" if sections else "missing"))
        grid.add_widget(MetricRow("Nœuds", nodes, "", "ok" if nodes else "missing"))
        grid.add_widget(MetricRow("Inconnues", unknowns, "", "alerte" if unknowns else "ok"))
        grid.add_widget(MetricRow("Alertes", alerts, "", "alerte" if alerts else "ok"))
        grid.add_widget(MetricRow("Sources", len(sources), "", "ok" if sources else "missing"))
        grid.add_widget(MetricRow("Erreurs", len(errors), "", "alerte" if errors else ("calculée" if syncing else "ok")))

        panel.add_widget(grid)

        if critical:
            panel.add_widget(
                Label(
                    text=f"{critical} section(s) nécessitent une vérification technique.",
                    color=COLORS["RS"],
                    font_size="11sp",
                    halign="left",
                    size_hint_y=None,
                    height=dp(22),
                )
            )

        return panel

    def _search_bar(self) -> BoxLayout:
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(44),
            spacing=dp(10),
        )

        search = TextInput(
            text=self._query,
            hint_text="Filtrer les sections : cao, moteur, inconnues, optimisation, pièces...",
            multiline=False,
            background_color=COLORS["BL"],
            foreground_color=COLORS["BFW"],
            cursor_color=COLORS["RS"],
            font_size="13sp",
            padding=[dp(10), dp(8)],
        )

        def on_text(_: Any, value: str) -> None:
            self._query = value.strip().lower()
            payload = self._last_payload or {}
            sections = _safe_list(payload.get("raw_sections"))

            if not sections:
                app = App.get_running_app()
                sections = build_raw_sections(
                    ui_report=_safe_dict(getattr(app, "ui_report", {}) or {}),
                    backend_report=_safe_dict(getattr(app, "backend_report", {}) or {}),
                )

            self._render(
                raw_sections=sections,
                sources=[str(s) for s in _safe_list(payload.get("sources"))],
                errors=[dict(e) for e in _safe_list(payload.get("errors")) if isinstance(e, Mapping)],
                syncing=False,
            )

        search.bind(text=on_text)
        bar.add_widget(search)

        clear = ModernButton(text="CLEAR", size_hint_x=None, width=dp(90), font_size="11sp")
        clear.bind(on_release=lambda *_: setattr(search, "text", ""))
        bar.add_widget(clear)

        return bar

    def _filter_sections(self, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        query = (self._query or "").strip().lower()
        if not query:
            return sections

        out: List[Dict[str, Any]] = []
        for sec in sections:
            name = str(sec.get("name", "")).lower()
            status = str(sec.get("status", "")).lower()

            if query in name or query in status:
                out.append(sec)
                continue

            value = sec.get("value")
            try:
                preview = json.dumps(value, ensure_ascii=False, default=str)[:4000].lower()
            except Exception:
                preview = str(value).lower()

            if query in preview:
                out.append(sec)

        return out

    def _info_panel(self, *, title: str, text: str, status: str) -> PremiumCard:
        panel = PremiumCard(title=title, size_hint_y=None, height=dp(170))
        panel.add_widget(StatusBadge(status=status, size_hint_y=None, height=dp(24)))
        panel.add_widget(
            Label(
                text=text,
                color=COLORS["BFW"],
                font_size="13sp",
                halign="left",
                valign="top",
            )
        )
        return panel

    def _errors_panel(self, errors: List[Dict[str, Any]]) -> PremiumCard:
        panel = PremiumCard(title="Erreurs de récupération / recalcul", size_hint_y=None)
        panel.height = dp(74 + min(len(errors), 6) * 36)

        box = BoxLayout(orientation="vertical", spacing=dp(2), size_hint_y=None)
        box.bind(minimum_height=box.setter("height"))

        for err in errors[:6]:
            box.add_widget(
                MetricRow(
                    str(err.get("source", "backend")),
                    _short_text(err.get("erreur"), 120),
                    "",
                    "alerte",
                )
            )

        panel.add_widget(box)
        return panel

    def _section_panel(self, section: Mapping[str, Any]) -> PremiumCard:
        name = str(section.get("name", "section")).upper()
        value = section.get("value")
        status = str(section.get("status", _section_status(value)))

        nodes = int(section.get("nodes", _count_nodes(value) if value is not None else 0))
        unknowns = int(section.get("unknowns", _count_unknowns(value) if value is not None else 0))
        alerts = int(section.get("alerts", _count_alerts(value) if value is not None else 0))

        # Hauteur dynamique : assez grande pour lire, mais pas infinie.
        dynamic_height = dp(210 + min(nodes, 36) * 11)
        height = max(dp(260), min(dp(760), dynamic_height))

        panel = PremiumCard(title=name, size_hint_y=None, height=height)

        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(34),
            spacing=dp(8),
        )

        header.add_widget(StatusBadge(status=status, size_hint_x=None, width=dp(110)))
        header.add_widget(MetricRow("Nœuds", nodes, "", "ok" if nodes else "missing"))
        header.add_widget(MetricRow("Inconnues", unknowns, "", "alerte" if unknowns else "ok"))
        header.add_widget(MetricRow("Alertes", alerts, "", "alerte" if alerts else "ok"))
        panel.add_widget(header)

        if value is None:
            panel.add_widget(EmptyState(text="Aucune donnée enregistrée pour cette section."))
            panel.height = dp(150)
            return panel

        tree = JsonTreeView(value)
        panel.add_widget(tree)

        return panel

    def _go(self, screen_name: str) -> None:
        if self.manager is not None:
            self.manager.current = screen_name
