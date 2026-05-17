# frontend\gui\dashboard.py
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
from kivy.uix.widget import Widget

from frontend.gui.components import (
    COLORS,
    EmptyState,
    GhostButton,
    KpiCard,
    MetricRow,
    ModernButton,
    NeoCard,
    PremiumCard,
    SectionTitle,
    StatusBadge,
)
from frontend.gui.frontend_contract import get_field, field_badge_label


# =============================================================================
# Helpers stricts — aucune valeur inventée
# =============================================================================

def _is_finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _safe_float(value: Any) -> Optional[float]:
    return float(value) if _is_finite(value) else None


def _safe_int(value: Any) -> Optional[int]:
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)

    if _is_finite(value):
        rounded = round(float(value))
        if abs(float(value) - rounded) <= 1e-9:
            return int(rounded)

    return None


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


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


def _first_finite(*values: Any) -> Optional[float]:
    for value in values:
        if _is_finite(value):
            return float(value)
    return None


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


def _fmt_number(value: Any, digits: int = 4) -> str:
    if not _is_finite(value):
        return "—"

    v = float(value)
    av = abs(v)

    if av >= 1_000_000:
        return f"{v / 1_000_000:.{digits}g} M"
    if av >= 1_000:
        return f"{v / 1_000:.{digits}g} k"
    if 0.0 < av < 0.001:
        return f"{v:.{digits}e}"

    return f"{v:.{digits}g}"


def _fmt_percent(value: Any) -> str:
    if not _is_finite(value):
        return "—"

    v = float(value)
    if 0.0 <= v <= 1.0:
        v *= 100.0

    return f"{v:.1f}"


def _fmt_bool(value: Any) -> str:
    if value is True:
        return "OUI"
    if value is False:
        return "NON"
    return "—"


def _short_text(value: Any, max_len: int = 130) -> str:
    text = str(value or "").strip()
    if not text:
        return "—"
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _status_for_value(value: Any) -> str:
    if value is None:
        return "missing"
    if value is False:
        return "alerte"
    return "ok"


def _count_nested_items(block: Any) -> int:
    if isinstance(block, Mapping):
        total = 0
        for value in block.values():
            if isinstance(value, list):
                total += len(value)
            elif isinstance(value, Mapping):
                total += _count_nested_items(value)
        return total

    if isinstance(block, list):
        return len(block)

    return 0


def _flatten_unknowns(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, Mapping):
            inc = node.get("inconnues")
            if isinstance(inc, Mapping):
                for category, values in inc.items():
                    for item in _safe_list(values):
                        if isinstance(item, Mapping):
                            row = dict(item)
                            row.setdefault("categorie", category)
                            row.setdefault("source", path or "racine")
                            out.append(row)

            inconnues_cao = node.get("inconnues_cao")
            if isinstance(inconnues_cao, list):
                for item in inconnues_cao:
                    if isinstance(item, Mapping):
                        row = dict(item)
                        row.setdefault("categorie", "cao")
                        row.setdefault("source", path or "cao")
                        out.append(row)

            for key, value in node.items():
                if isinstance(value, (Mapping, list)):
                    walk(value, f"{path}.{key}" if path else str(key))

        elif isinstance(node, list):
            for index, value in enumerate(node):
                if isinstance(value, (Mapping, list)):
                    walk(value, f"{path}[{index}]")

    walk(report)

    seen: set[Tuple[str, str, str, str]] = set()
    deduped: List[Dict[str, Any]] = []

    for item in out:
        sig = (
            str(item.get("nom", "")),
            str(item.get("piece", "")),
            str(item.get("raison", "")),
            str(item.get("source", "")),
        )
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(item)

    return deduped


def _flatten_alerts(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, Mapping):
            alerts = node.get("alertes")
            if isinstance(alerts, Mapping):
                for category, values in alerts.items():
                    for item in _safe_list(values):
                        if isinstance(item, Mapping):
                            row = dict(item)
                            row.setdefault("categorie", category)
                            row.setdefault("source", path or "racine")
                            out.append(row)

            for key, value in node.items():
                if isinstance(value, (Mapping, list)):
                    walk(value, f"{path}.{key}" if path else str(key))

        elif isinstance(node, list):
            for index, value in enumerate(node):
                if isinstance(value, (Mapping, list)):
                    walk(value, f"{path}[{index}]")

    walk(report)

    seen: set[Tuple[str, str, str]] = set()
    deduped: List[Dict[str, Any]] = []

    for item in out:
        sig = (
            str(item.get("nom", "")),
            str(item.get("detail", "")),
            str(item.get("source", "")),
        )
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(item)

    return deduped


def _call_accepts_varkw(fn: Callable[..., Any]) -> bool:
    try:
        sig = inspect.signature(fn)
    except Exception:
        return True

    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())


def _filter_kwargs(fn: Callable[..., Any], params: Mapping[str, Any]) -> Dict[str, Any]:
    clean = {str(k): v for k, v in dict(params or {}).items() if v is not None}

    if _call_accepts_varkw(fn):
        return clean

    try:
        sig = inspect.signature(fn)
    except Exception:
        return clean

    accepted = set(sig.parameters.keys())
    return {k: v for k, v in clean.items() if k in accepted}


def _safe_call_app_hook(fn: Callable[..., Any], params: Mapping[str, Any]) -> Any:
    filtered = _filter_kwargs(fn, params)

    for args, kwargs in (
        ((), filtered),
        ((dict(params),), {}),
        ((), {}),
    ):
        try:
            return fn(*args, **kwargs)
        except TypeError:
            continue

    return None


# =============================================================================
# Pont direct vers backend/main.py
# =============================================================================

class BackendMainBridge:
    """
    Source de vérité : backend/main.py.

    Ordre :
    1. récupérer les rapports déjà stockés dans App ;
    2. appeler les hooks App si présents ;
    3. appeler directement backend.main.dimensionner_systeme_shsem(**app.engine_params) ;
    4. reconstruire app.ui_report depuis le rapport backend complet.
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

    APP_HOOKS: Tuple[str, ...] = (
        "get_backend_report",
        "collect_backend_report",
        "refresh_backend_report",
        "sync_backend_report",
        "compute_backend_report",
        "run_backend_dimensioning",
        "dimensionner_backend",
        "dimensionner_systeme",
        "recalculate_backend",
        "run_calculation",
        "recalculate",
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
        self.errors: List[Dict[str, Any]] = []
        self.sources: List[str] = []

    def sync(self, *, force_backend_call: bool = False) -> Dict[str, Any]:
        params = _safe_dict(getattr(self.app, "engine_params", {}) or {})
        reports: List[Dict[str, Any]] = []

        reports.extend(self._read_app_reports())
        reports.extend(self._read_json_reports())

        if force_backend_call or not reports:
            reports.extend(self._call_app_hooks(params))

        if force_backend_call or not reports:
            direct = self._call_dimensionner_systeme_shsem(params)
            if direct is not None:
                reports.append(direct)

        # Relire après hooks : certains hooks mutent app.backend_report/app.ui_report
        reports.extend(self._read_app_reports())

        backend_report: Dict[str, Any] = {}
        for report in reports:
            backend_report = _merge_dict_non_none(backend_report, report)

        backend_report["_dashboard_backend_sources"] = list(dict.fromkeys(self.sources))
        if self.errors:
            backend_report["_dashboard_backend_errors"] = self.errors

        ui_from_backend = build_dashboard_ui_from_backend(backend_report)

        existing_ui = _safe_dict(getattr(self.app, "ui_report", {}) or {})
        ui_report = _merge_dict_non_none(existing_ui, ui_from_backend)

        try:
            self.app.backend_report = backend_report
            self.app.full_report = backend_report
            self.app.ui_report = ui_report
            self.app.dashboard_backend_sources = self.sources
            self.app.dashboard_backend_errors = self.errors
        except Exception:
            pass

        return {
            "backend_report": backend_report,
            "ui_report": ui_report,
            "sources": self.sources,
            "errors": self.errors,
        }

    def _push_error(self, source: str, error: Any) -> None:
        self.errors.append({"source": source, "erreur": str(error)})

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

    def _call_app_hooks(self, params: Mapping[str, Any]) -> List[Dict[str, Any]]:
        reports: List[Dict[str, Any]] = []

        for name in self.APP_HOOKS:
            fn = getattr(self.app, name, None)
            if not callable(fn):
                continue

            try:
                out = _safe_call_app_hook(fn, params)
            except Exception as exc:
                self._push_error(f"app.{name}", exc)
                continue

            if isinstance(out, Mapping):
                report = dict(out)
                report.setdefault("_source_hook", f"app.{name}")
                reports.append(report)
                self.sources.append(f"app.{name}")

        return reports

    def _call_dimensionner_systeme_shsem(self, params: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        if not params:
            self._push_error(
                "backend.main.dimensionner_systeme_shsem",
                "app.engine_params vide : impossible d'appeler l'orchestrateur strict.",
            )
            return None

        try:
            from backend.main import dimensionner_systeme_shsem  # type: ignore
        except Exception as exc:
            try:
                from main import dimensionner_systeme_shsem  # type: ignore
            except Exception as exc2:
                self._push_error(
                    "backend.main.dimensionner_systeme_shsem",
                    f"import impossible : {exc} / {exc2}",
                )
                return None

        try:
            kwargs = _filter_kwargs(dimensionner_systeme_shsem, params)

            # Garde-fou : backend/main.py exige au moins une cible de puissance.
            has_power_target = any(
                kwargs.get(k) is not None
                for k in (
                    "puissance_traction_kw",
                    "production_electrique_sortie_w",
                    "puissance_bus_dc_w",
                    "puissance_moteur_requise_W",
                )
            )

            if not has_power_target:
                self._push_error(
                    "backend.main.dimensionner_systeme_shsem",
                    "cible de puissance absente : fournir puissance_traction_kw, production_electrique_sortie_w, puissance_bus_dc_w ou puissance_moteur_requise_W.",
                )
                return None

            report = dimensionner_systeme_shsem(**kwargs)

            if not isinstance(report, Mapping):
                self._push_error(
                    "backend.main.dimensionner_systeme_shsem",
                    f"retour non dict : {type(report).__name__}",
                )
                return None

            out = dict(report)
            out.setdefault("_source_hook", "backend.main.dimensionner_systeme_shsem")
            self.sources.append("backend.main.dimensionner_systeme_shsem")
            return out

        except Exception as exc:
            self._push_error("backend.main.dimensionner_systeme_shsem", exc)
            return None


# =============================================================================
# Construction ui_report depuis backend/main.py
# =============================================================================

def _metric(label: str, value: Any, unit: str = "", status: Optional[str] = None) -> Dict[str, Any]:
    return {
        "label": label,
        "value": value,
        "unit": unit,
        "status": status or _status_for_value(value),
    }


def _contract_metric(contract: Mapping[str, Any], path: str, label: str, unit: str = "") -> Dict[str, Any]:
    field = get_field(contract, path) if isinstance(contract, Mapping) else None
    if not field:
        return _metric(label, None, unit, "missing")
    status = "ok" if str(field.get("status")) in {"computed", "database", "derived", "input", "validated_by_optimization"} else "alerte"
    return {
        "label": label,
        "value": field.get("value"),
        "unit": field.get("unit") or unit,
        "status": status,
        "source": field.get("source"),
        "badge": field_badge_label(field),
        "path": path,
    }


def _chain_check(chain: Mapping[str, Any], name: str) -> Dict[str, Any]:
    checks = chain.get("checks", []) if isinstance(chain, Mapping) else []
    for check in checks:
        if isinstance(check, Mapping) and check.get("name") == name:
            return dict(check)
    return {}


def _subsystem(name: str, report: Any, *, required: bool = False) -> Dict[str, Any]:
    if isinstance(report, Mapping):
        if report.get("erreur"):
            status = "erreur"
        elif _count_nested_items(report.get("inconnues")) > 0:
            status = "alerte"
        else:
            status = "ok"
    elif report is None:
        status = "missing" if required else "indisponible"
    else:
        status = "ok"

    return {
        "name": name,
        "status": status,
    }


def _make_resume_candidate(report: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    gui = _safe_dict(report.get("resume_gui"))
    if not gui:
        return None

    if not _first_non_empty(gui.get("Architecture"), gui.get("N_cyl")):
        return None

    return {
        "architecture": gui.get("Architecture"),
        "nombre_cylindres": gui.get("N_cyl"),
        "alesage_m": (_safe_float(gui.get("Bore_mm")) / 1000.0) if _safe_float(gui.get("Bore_mm")) is not None else None,
        "course_m": (_safe_float(gui.get("Stroke_mm")) / 1000.0) if _safe_float(gui.get("Stroke_mm")) is not None else None,
        "cylindree_totale_cc": gui.get("vd_tot_cc"),
        "RPM": gui.get("RPM"),
        "PME_Pa": _first_non_none(gui.get("PME_Pa"), gui.get("PME")),
        "Pmax_Pa": gui.get("Pmax_Pa"),
        "Couple_max_Nm": gui.get("Couple_max_Nm"),
        "couple_moyen_Nm": gui.get("couple_moyen_Nm"),
        "Force_bielle_N": gui.get("Force_bielle_N"),
        "P_bus_dc_design_w": gui.get("P_bus_dc_design_w"),
        "energie_batterie_kwh": gui.get("energie_batterie_kwh"),
        "score_coherence_100": gui.get("score_coherence_100"),
        "score_global_100": gui.get("score_global_100"),
        "nb_pieces_construites": gui.get("nb_pieces_construites"),
        "nb_alertes": gui.get("nb_alertes"),
        "nb_inconnues": gui.get("nb_inconnues"),
        "description": "Candidat reconstruit depuis backend/main.py -> resume_gui.",
        "backend_source_path": "resume_gui",
    }


def build_dashboard_ui_from_backend(report: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(report, Mapping) or not report:
        return {"is_empty": True}

    gui = _safe_dict(report.get("resume_gui"))
    systeme_complet = _safe_dict(report.get("systeme_complet"))
    synth = _safe_dict(report.get("synthese"))
    synth_systeme = _safe_dict(synth.get("systeme"))
    synth_mt = _safe_dict(synth.get("moteur_thermique"))
    synth_opt = _safe_dict(synth.get("optimisation"))

    sc_synth = _safe_dict(systeme_complet.get("synthese"))
    sc_veh = _safe_dict(sc_synth.get("vehicule"))
    sc_batt = _safe_dict(sc_synth.get("batterie"))
    sc_alt = _safe_dict(sc_synth.get("alternateur"))
    sc_mt = _safe_dict(sc_synth.get("moteur_thermique"))

    frontend_contract = _safe_dict(report.get("frontend"))
    contract_cao = _safe_dict(frontend_contract.get("cao"))
    cao_dossier = _safe_dict(report.get("cao_dossier")) or _safe_dict(frontend_contract.get("cao_dossier"))
    cao_resume = _safe_dict(cao_dossier.get("resume"))
    mechanical_graphs = _safe_dict(report.get("mechanical_graphs")) or _safe_dict(frontend_contract.get("mechanical_graphs"))
    cao = _merge_dict_non_none(_safe_dict(report.get("cao")), contract_cao)
    cao = _merge_dict_non_none(cao, cao_resume)
    chain_validation = _safe_dict(report.get("validation_chaine_100kw")) or _safe_dict(_deep_get(report, "frontend", "chain_validation"))
    chain_values = _safe_dict(chain_validation.get("valeurs"))
    chain_livrables = _safe_dict(chain_validation.get("livrables"))
    diagnostic = _safe_dict(report.get("diagnostic")) or _safe_dict(frontend_contract.get("diagnostic"))
    diagnostic_resume = _safe_dict(diagnostic.get("resume"))
    root_causes = [dict(c) for c in _safe_list(diagnostic.get("causes_racines")) if isinstance(c, Mapping)]
    analyses = _safe_dict(report.get("analyses_composants"))
    construction = _safe_dict(report.get("construction_pieces"))
    pieces = _safe_dict(report.get("rapports_pieces"))
    optimisation = _safe_dict(report.get("optimisation"))
    legacy = _safe_dict(report.get("legacy"))

    unknowns = _flatten_unknowns(report)
    alerts = _flatten_alerts(report)

    score_coherence = _first_non_none(
        gui.get("score_coherence_100"),
        synth_opt.get("score_coherence_100"),
        _deep_get(optimisation, "synthese_optimisation", "score_coherence_100"),
    )
    score_global = _first_non_none(
        gui.get("score_global_100"),
        synth_opt.get("score_global_100"),
        _deep_get(optimisation, "synthese_optimisation", "score_global_100"),
    )

    puissance_demandee_kw = None
    p_bus = _first_finite(
        gui.get("P_bus_dc_design_w"),
        sc_veh.get("puissance_bus_dc_design_w"),
        synth_systeme.get("P_bus_dc_design_w"),
    )
    if p_bus is not None:
        puissance_demandee_kw = p_bus / 1000.0

    power_chain = [
        _contract_metric(frontend_contract, "synthese.moteur_electrique.puissance_sortie_w", "Sortie moteur electrique", "W"),
        _contract_metric(frontend_contract, "synthese.systeme.P_bus_dc_design_w", "Bus DC design", "W"),
        _metric("Alternateur electrique", chain_values.get("puissance_alternateur_electrique_w"), "W", _status_for_value(chain_values.get("puissance_alternateur_electrique_w"))),
        _metric("Moteur thermique arbre", chain_values.get("puissance_moteur_thermique_arbre_w"), "W", _status_for_value(chain_values.get("puissance_moteur_thermique_arbre_w"))),
        _metric("Regime thermique", chain_values.get("rpm_moteur_thermique"), "rpm", _status_for_value(chain_values.get("rpm_moteur_thermique"))),
        _metric("Couple thermique", chain_values.get("couple_moteur_thermique_nm"), "Nm", _status_for_value(chain_values.get("couple_moteur_thermique_nm"))),
        _metric("Score chaine", chain_validation.get("score_chaine_100"), "/100", "ok" if chain_validation.get("ok") else ("alerte" if chain_validation else "missing")),
    ]

    boite_check = _chain_check(chain_validation, "boite_reliable")
    couple_check = _chain_check(chain_validation, "couple_moteur_thermique_calculable")
    materials = _safe_list(_deep_get(mechanical_graphs, "context", "materiaux_autorises"))
    mechanical_presizing = bool(chain_livrables.get("mechanical_presizing_ok") or cao.get("drawing_data_available"))
    mechanical_closure = [
        _metric("Couple connu", _fmt_bool(couple_check.get("ok")) if couple_check else _fmt_bool(chain_values.get("couple_moteur_thermique_nm") is not None), "", "ok" if (couple_check.get("ok") if couple_check else chain_values.get("couple_moteur_thermique_nm") is not None) else "alerte"),
        _metric("Arbre dimensionnable", _fmt_bool(mechanical_presizing), "", "ok" if mechanical_presizing else "alerte"),
        _metric("Boite/crabots", _fmt_bool(boite_check.get("ok")) if boite_check else "-", "", "ok" if boite_check.get("ok") else "alerte"),
        _metric("Alternateur relie", _fmt_bool(boite_check.get("ok")) if boite_check else "-", "", "ok" if boite_check.get("ok") else "alerte"),
        _metric("Materiaux candidats", ", ".join(str(x) for x in materials[:3]) or None, "", "ok" if materials else "missing"),
        _metric("Graphes mecaniques", mechanical_graphs.get("graphs_available"), "", "ok" if mechanical_graphs.get("graphs_available") else "alerte"),
    ]

    cao_preconception = [
        _metric("Mode", cao.get("mode"), "", "ok" if cao.get("mode") not in (None, "indisponible") else "missing"),
        _metric("Croquis cotes", _fmt_bool(cao.get("sketches_available")), "", "ok" if cao.get("sketches_available") else "alerte"),
        _metric("3D indicative", _fmt_bool(cao.get("views_3d_available")), "", "ok" if cao.get("views_3d_available") else "alerte"),
        _metric("Graphiques contraintes", _fmt_bool(cao.get("stress_graphs_available")), "", "ok" if cao.get("stress_graphs_available") else "alerte"),
        _metric("Donnees SolidWorks", _fmt_bool(cao.get("drawing_data_available")), "", "ok" if cao.get("drawing_data_available") else "alerte"),
        _metric("SolidWorks ready", _fmt_bool(cao.get("solidworks_ready")), "", "ok" if cao.get("solidworks_ready") else "alerte"),
        _metric("STEP export", _fmt_bool(cao.get("step_export")), "", "ok" if cao.get("step_export") else "alerte"),
    ]

    diagnostic_causal = {
        "status": diagnostic_resume.get("statut") or ("bloque" if root_causes else "indisponible"),
        "score": diagnostic_resume.get("score_diagnostic_100"),
        "root_causes_count": diagnostic_resume.get("nb_causes_racines", len(root_causes)),
        "symptoms_count": diagnostic_resume.get("nb_symptomes"),
        "duplicates_count": diagnostic_resume.get("nb_doublons_probables"),
        "root_causes": root_causes[:4],
    }

    energy_chain = [
        _metric("Puissance totale demandée", puissance_demandee_kw, "kW"),
        _metric("Puissance bus DC", p_bus, "W"),
        _metric("Batterie utile", _first_non_none(gui.get("energie_batterie_kwh"), sc_batt.get("energie_utile_kwh")), "kWh"),
        _metric("Architecture", gui.get("Architecture"), ""),
        _metric("Nombre cylindres", gui.get("N_cyl"), ""),
        _metric("Alésage", gui.get("Bore_mm"), "mm"),
        _metric("Course", gui.get("Stroke_mm"), "mm"),
        _metric("Régime moteur", gui.get("RPM"), "rpm"),
        _metric("PME", _first_non_none(gui.get("PME_Pa"), gui.get("PME")), "Pa"),
        _metric("Pmax", gui.get("Pmax_Pa"), "Pa"),
        _metric("Couple max", gui.get("Couple_max_Nm"), "Nm"),
        _metric("Couple moyen", gui.get("couple_moyen_Nm"), "Nm"),
        _metric("Force bielle", gui.get("Force_bielle_N"), "N"),
        _metric("Validation chaine 100 kW", chain_validation.get("score_chaine_100"), "%", "ok" if chain_validation.get("ok") else "alerte"),
        _metric("Cylindrée totale", gui.get("vd_tot_cc"), "cc"),
        _metric("Score cohérence", score_coherence, "%"),
        _metric("Score global", score_global, "%"),
    ]

    # Nettoyage : conserver les lignes utiles, mais ne pas masquer les valeurs None critiques.
    priority_labels = {
        "Puissance totale demandée",
        "Puissance bus DC",
        "Batterie utile",
        "Architecture",
        "Nombre cylindres",
        "Score cohérence",
        "Score global",
    }
    energy_chain = [
        item for item in energy_chain
        if item["value"] is not None or item["label"] in priority_labels
    ]

    subsystems = [
        _subsystem("Système complet", systeme_complet, required=True),
        _subsystem("Moteur thermique", sc_mt or synth_mt, required=True),
        _subsystem("Moteur électrique", _deep_get(systeme_complet, "sous_systemes", "moteur_electrique")),
        _subsystem("Batterie", sc_batt),
        _subsystem("Alternateur", sc_alt),
        _subsystem("Architecture", _deep_get(analyses, "architecture") or gui),
        _subsystem("Boîte à crabots", _deep_get(analyses, "boite_crabots")),
        _subsystem("Construction pièces", construction),
        _subsystem("Rapports pièces", pieces),
        _subsystem("Optimisation", optimisation),
        _subsystem("CAO", cao),
        _subsystem("Legacy", legacy),
    ]

    alert_rows: List[Dict[str, Any]] = []
    for item in alerts[:10]:
        label = _first_non_empty(item.get("nom"), item.get("categorie"), "Alerte")
        value = _first_non_empty(item.get("detail"), item.get("raison"), item.get("source"), "")
        alert_rows.append(_metric(str(label), _short_text(value, 90), "", "alerte"))

    unknown_rows: List[Dict[str, Any]] = []
    for item in unknowns[:12]:
        label = _first_non_empty(item.get("nom"), item.get("piece"), item.get("champ"), item.get("categorie"), "Inconnue")
        value = _first_non_empty(item.get("raison"), item.get("source"), "")
        unknown_rows.append(_metric(str(label), _short_text(value, 100), "", "missing"))

    candidate = _make_resume_candidate(report)
    architecture_candidates = [candidate] if candidate else []

    dashboard = {
        "title": "STHOME COCKPIT — BACKEND MAIN",
        "summary": {
            "missing_count": len(unknowns),
            "alert_count": len(alerts),
            "backend_sources_count": len(_safe_list(report.get("_dashboard_backend_sources"))),
            "pieces_count": len(pieces),
            "components_count": len(_safe_dict(report.get("toutes_les_donnees_composants"))),
            "solidworks_ready": _first_non_none(
                cao.get("solidworks_ready"),
                cao.get("solidworks_ready_detaille"),
            ),
            "chain_validation": {
                "available": bool(chain_validation),
                "ok": bool(chain_validation.get("ok")),
                "score_chaine_100": chain_validation.get("score_chaine_100"),
                "main_blocking_point": _safe_list(chain_validation.get("points_bloquants"))[0] if _safe_list(chain_validation.get("points_bloquants")) else None,
            },
            "cao_preconception": {
                "mode": cao.get("mode"),
                "sketches_available": bool(cao.get("sketches_available")),
                "views_3d_available": bool(cao.get("views_3d_available")),
                "stress_graphs_available": bool(cao.get("stress_graphs_available")),
                "drawing_data_available": bool(cao.get("drawing_data_available")),
                "solidworks_ready": bool(cao.get("solidworks_ready")),
                "step_export": bool(cao.get("step_export")),
            },
        },
        "power_chain": power_chain,
        "mechanical_closure": mechanical_closure,
        "cao_preconception": cao_preconception,
        "diagnostic_causal": diagnostic_causal,
        "energy_chain": energy_chain,
        "subsystems": subsystems,
        "alerts": alert_rows,
        "unknowns": unknown_rows,
        "actions": [
            {"label": "Architecture", "target": "architecture_choice"},
            {"label": "Manques", "target": "missing_requirements"},
            {"label": "Diagnostic JSON", "target": "json_diagnostic"},
            {"label": "Paramètres", "target": "edit_parameters"},
            {"label": "Rapport brut", "target": "raw_json"},
            {"label": "Dossier CAO", "target": "cao_dossier"},
            {"label": "Dashboard", "target": "dashboard"},
        ],
    }

    return {
        "is_empty": False,
        "dashboard": dashboard,
        "resume_gui": gui,
        "cao": cao,
        "architecture_candidates": architecture_candidates,
        "backend_report_present": True,
        "backend_sources": _safe_list(report.get("_dashboard_backend_sources")),
        "backend_errors": _safe_list(report.get("_dashboard_backend_errors")),
        "inconnues": report.get("inconnues"),
        "alertes": report.get("alertes"),
        "frontend_contract": frontend_contract,
        "cao_dossier": cao_dossier,
        "mechanical_graphs": mechanical_graphs,
    }


# =============================================================================
# Dashboard musclé
# =============================================================================

class DashboardScreen(Screen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._sync_running = False
        self._last_backend_report: Dict[str, Any] = {}
        self._last_ui_report: Dict[str, Any] = {}
        self._last_errors: List[Dict[str, Any]] = []
        self._last_sources: List[str] = []

    def on_enter(self, *_: Any) -> None:
        # Affiche immédiatement ce qui existe, puis synchronise backend/main.py.
        self.refresh(force_backend=False)
        self.sync_backend(force_backend_call=False)

    # -------------------------------------------------------------------------
    # Synchronisation backend
    # -------------------------------------------------------------------------

    def sync_backend(self, *, force_backend_call: bool = True) -> None:
        if self._sync_running:
            return

        self._sync_running = True
        self._render_syncing()

        app = App.get_running_app()

        def worker() -> None:
            try:
                payload = BackendMainBridge(app).sync(force_backend_call=force_backend_call)
            except Exception as exc:
                payload = {
                    "backend_report": {},
                    "ui_report": _safe_dict(getattr(app, "ui_report", {}) or {}),
                    "sources": [],
                    "errors": [
                        {
                            "source": "DashboardScreen.sync_backend",
                            "erreur": str(exc),
                            "trace": traceback.format_exc(),
                        }
                    ],
                }

            Clock.schedule_once(lambda *_: self._finish_sync(payload), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_sync(self, payload: Mapping[str, Any]) -> None:
        self._sync_running = False

        backend_report = _safe_dict(payload.get("backend_report"))
        ui_report = _safe_dict(payload.get("ui_report"))
        errors = [dict(e) for e in _safe_list(payload.get("errors")) if isinstance(e, Mapping)]
        sources = [str(s) for s in _safe_list(payload.get("sources"))]

        self._last_backend_report = backend_report
        self._last_ui_report = ui_report
        self._last_errors = errors
        self._last_sources = sources

        self._render(ui_report, backend_report)

    # -------------------------------------------------------------------------
    # Rendu principal
    # -------------------------------------------------------------------------

    def refresh(self, *, force_backend: bool = False) -> None:
        if force_backend:
            self.sync_backend(force_backend_call=True)
            return

        app = App.get_running_app()

        backend_report = _safe_dict(
            _first_non_none(
                getattr(app, "backend_report", None),
                getattr(app, "full_report", None),
                getattr(app, "last_backend_report", None),
                {},
            )
        )

        ui_report = _safe_dict(getattr(app, "ui_report", {}) or {})

        if backend_report:
            ui_report = _merge_dict_non_none(
                ui_report,
                build_dashboard_ui_from_backend(backend_report),
            )

        self._render(ui_report, backend_report)

    def _render_syncing(self) -> None:
        self.clear_widgets()

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        root.add_widget(self._top_bar("STHOME COCKPIT — SYNCHRONISATION", backend_status="calculée"))

        panel = PremiumCard(title="Synchronisation backend/main.py", bg=COLORS["BFW_08"])
        panel.add_widget(
            Label(
                text=(
                    "Récupération du rapport complet depuis backend/main.py : "
                    "resume_gui, systeme_complet, CAO, analyses composants, rapports pièces, optimisation, inconnues et alertes."
                ),
                color=COLORS["BFW"],
                font_size="13sp",
                halign="left",
                valign="top",
            )
        )
        root.add_widget(panel)

        self.add_widget(root)

    def _render(self, ui_report: Mapping[str, Any], backend_report: Mapping[str, Any]) -> None:
        self.clear_widgets()

        ui = _safe_dict(ui_report)
        dash = _safe_dict(ui.get("dashboard"))

        backend_errors = _safe_list(ui.get("backend_errors")) or self._last_errors
        backend_sources = _safe_list(ui.get("backend_sources")) or self._last_sources

        if not ui or ui.get("is_empty"):
            root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
            root.add_widget(self._top_bar("STHOME COCKPIT", backend_status="missing"))
            root.add_widget(self._empty_backend_panel(backend_errors))
            self.add_widget(root)
            return

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        root.add_widget(
            self._top_bar(
                dash.get("title", "STHOME COCKPIT"),
                backend_status="ok" if backend_report else "missing",
            )
        )

        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            size_hint_y=None,
            padding=[dp(4), dp(4)],
        )
        content.bind(minimum_height=content.setter("height"))

        summary = _safe_dict(dash.get("summary"))

        content.add_widget(self._backend_state_panel(summary, backend_sources, backend_errors))
        content.add_widget(self._kpi_row(ui))

        tier1 = BoxLayout(size_hint_y=None, height=dp(260), spacing=dp(12))
        tier1.add_widget(self._technical_metric_panel("Chaîne puissance", _safe_list(dash.get("power_chain"))))
        tier1.add_widget(self._technical_metric_panel("Fermeture mécanique", _safe_list(dash.get("mechanical_closure"))))
        content.add_widget(tier1)

        tier2 = BoxLayout(size_hint_y=None, height=dp(260), spacing=dp(12))
        tier2.add_widget(self._technical_metric_panel("Dossier CAO / Préconception", _safe_list(dash.get("cao_preconception")), action=("OUVRIR DOSSIER", "cao_dossier")))
        tier2.add_widget(self._diagnostic_causal_panel(_safe_dict(dash.get("diagnostic_causal"))))
        content.add_widget(tier2)

        tier3 = BoxLayout(size_hint_y=None, height=dp(240), spacing=dp(12))
        tier3.add_widget(self._missing_summary_panel(summary.get("missing_count", 0), _safe_list(dash.get("unknowns"))))
        tier3.add_widget(self._next_actions_panel(_safe_list(dash.get("alerts"))))
        content.add_widget(tier3)

        tier4 = BoxLayout(size_hint_y=None, height=dp(300), spacing=dp(12))
        tier4.add_widget(self._energy_chain_panel(_safe_list(dash.get("energy_chain"))))
        tier4.add_widget(self._subsystems_panel(_safe_list(dash.get("subsystems"))))
        content.add_widget(tier4)

        content.add_widget(self._actions_panel(_safe_list(dash.get("actions"))))

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    # -------------------------------------------------------------------------
    # Top bar
    # -------------------------------------------------------------------------

    def _top_bar(self, title: str, *, backend_status: str = "inconnu") -> BoxLayout:
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(58),
            spacing=dp(10),
            padding=[dp(10), dp(5)],
        )

        lbl = Label(
            text=str(title).upper(),
            color=COLORS["BFW"],
            bold=True,
            font_size="16sp",
            halign="left",
            valign="middle",
        )
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)

        bar.add_widget(StatusBadge(status=backend_status, size_hint_x=None, width=dp(110)))

        buttons = (
            ("SYNC", lambda *_: self.sync_backend(force_backend_call=False), 90),
            ("RECALCULER", lambda *_: self.sync_backend(force_backend_call=True), 120),
            ("DIAG JSON", lambda *_: self._go("json_diagnostic"), 115),
            ("ÉDITER", lambda *_: self._go("edit_parameters"), 100),
            ("JSON", lambda *_: self._go("raw_json"), 80),
            ("ACCUEIL", lambda *_: self._go("home"), 100),
        )

        for text, callback, width in buttons:
            btn = ModernButton(text=text, size_hint_x=None, width=dp(width), font_size="11sp")
            btn.bind(on_release=callback)
            bar.add_widget(btn)

        return bar

    # -------------------------------------------------------------------------
    # Panels
    # -------------------------------------------------------------------------

    def _empty_backend_panel(self, errors: List[Any]) -> PremiumCard:
        panel = PremiumCard(title="Aucun rapport backend disponible", bg=COLORS["RS_18"])

        panel.add_widget(
            Label(
                text=(
                    "Le dashboard n’a trouvé ni rapport en mémoire, ni JSON exporté, "
                    "ni résultat exploitable depuis backend.main.dimensionner_systeme_shsem."
                ),
                color=COLORS["RS"],
                bold=True,
                font_size="13sp",
                halign="left",
                valign="top",
            )
        )

        if errors:
            box = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)
            box.bind(minimum_height=box.setter("height"))

            for err in errors[:6]:
                if not isinstance(err, Mapping):
                    continue
                box.add_widget(
                    MetricRow(
                        str(err.get("source", "backend")),
                        _short_text(err.get("erreur"), 90),
                        "",
                        "alerte",
                    )
                )

            panel.add_widget(box)

        panel.add_widget(
            EmptyState(
                text="PARAMÈTRES OU CIBLE DE PUISSANCE MANQUANTS",
                action_text="ÉDITER LES PARAMÈTRES",
                callback=lambda *_: self._go("edit_parameters"),
            )
        )

        return panel

    def _backend_state_panel(
        self,
        summary: Mapping[str, Any],
        sources: List[Any],
        errors: List[Any],
    ) -> NeoCard:
        panel = NeoCard(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(82),
            spacing=dp(8),
            padding=dp(8),
        )

        panel.add_widget(
            MetricRow(
                "Sources backend",
                summary.get("backend_sources_count", len(sources)),
                "",
                "ok" if sources else "missing",
            )
        )
        panel.add_widget(
            MetricRow(
                "Pièces",
                summary.get("pieces_count"),
                "",
                _status_for_value(summary.get("pieces_count")),
            )
        )
        panel.add_widget(
            MetricRow(
                "Composants",
                summary.get("components_count"),
                "",
                _status_for_value(summary.get("components_count")),
            )
        )
        panel.add_widget(
            MetricRow(
                "SolidWorks",
                _fmt_bool(summary.get("solidworks_ready")),
                "",
                "ok" if summary.get("solidworks_ready") else "alerte",
            )
        )
        chain = _safe_dict(summary.get("chain_validation"))
        panel.add_widget(
            MetricRow(
                "Chaine 100 kW",
                chain.get("score_chaine_100"),
                "%",
                "ok" if chain.get("ok") else ("alerte" if chain.get("available") else "missing"),
            )
        )
        panel.add_widget(
            MetricRow(
                "Erreurs sync",
                len(errors),
                "",
                "alerte" if errors else "ok",
            )
        )

        return panel

    def _kpi_row(self, ui: Mapping[str, Any]) -> BoxLayout:
        dash = _safe_dict(ui.get("dashboard"))
        summary = _safe_dict(dash.get("summary"))

        kpi_row = BoxLayout(size_hint_y=None, height=dp(116), spacing=dp(12))

        p_req = self._find_value(ui, "Puissance totale demandée")
        score = _first_non_none(
            self._find_value(ui, "Score global"),
            self._find_value(ui, "Score cohérence"),
            self._find_value(ui, "Score technique"),
        )
        arch = self._find_value(ui, "Architecture")
        n_cyl = self._find_value(ui, "Nombre cylindres")

        kpi_row.add_widget(KpiCard("Puissance demandée", p_req, "kW", _status_for_value(p_req)))
        kpi_row.add_widget(KpiCard("Score", score, "%", _status_for_value(score)))
        kpi_row.add_widget(KpiCard("Architecture", arch, "", _status_for_value(arch)))
        kpi_row.add_widget(KpiCard("Cylindres", n_cyl, "", _status_for_value(n_cyl)))
        kpi_row.add_widget(
            KpiCard(
                "Données à compléter",
                summary.get("missing_count"),
                "",
                "alerte" if summary.get("missing_count") else "ok",
            )
        )
        kpi_row.add_widget(
            KpiCard(
                "Alertes",
                summary.get("alert_count"),
                "",
                "alerte" if summary.get("alert_count") else "ok",
            )
        )

        return kpi_row

    def _technical_metric_panel(
        self,
        title: str,
        items: List[Dict[str, Any]],
        *,
        action: Optional[Tuple[str, str]] = None,
    ) -> PremiumCard:
        panel = PremiumCard(title=title, size_hint_x=0.5)

        container = BoxLayout(orientation="vertical", spacing=dp(2), size_hint_y=None)
        container.bind(minimum_height=container.setter("height"))

        if not items:
            container.add_widget(Label(text="Aucune donnée backend fournie.", color=COLORS["RS"], font_size="12sp"))
        else:
            for item in items[:8]:
                container.add_widget(
                    MetricRow(
                        item.get("label", ""),
                        item.get("value"),
                        item.get("unit", ""),
                        item.get("status", ""),
                    )
                )

        panel.add_widget(container)

        if action:
            label, target = action
            btn = GhostButton(text=label, size_hint_y=None, height=dp(34), font_size="10sp")
            btn.bind(on_release=lambda *_: self._go(target))
            panel.add_widget(btn)

        return panel

    def _diagnostic_causal_panel(self, diagnostic: Mapping[str, Any]) -> PremiumCard:
        panel = PremiumCard(title="Diagnostic causal", size_hint_x=0.5)
        status = diagnostic.get("status")
        panel.add_widget(MetricRow("Statut", str(status or "indisponible").upper(), "", "alerte" if status == "bloque" else _status_for_value(status)))
        panel.add_widget(MetricRow("Score", diagnostic.get("score"), "/100", _status_for_value(diagnostic.get("score"))))
        panel.add_widget(MetricRow("Causes racines", diagnostic.get("root_causes_count"), "", "alerte" if diagnostic.get("root_causes_count") else "ok"))
        panel.add_widget(MetricRow("Symptômes", diagnostic.get("symptoms_count"), "", "alerte" if diagnostic.get("symptoms_count") else "ok"))

        causes = [dict(c) for c in _safe_list(diagnostic.get("root_causes")) if isinstance(c, Mapping)]
        for cause in causes[:2]:
            panel.add_widget(
                MetricRow(
                    _short_text(cause.get("titre") or cause.get("id") or "Cause", 34),
                    _short_text(cause.get("raison"), 62),
                    "",
                    "alerte",
                )
            )

        btn = GhostButton(text="VOIR DIAGNOSTIC", size_hint_y=None, height=dp(34), font_size="10sp")
        btn.bind(on_release=lambda *_: self._go("json_diagnostic"))
        panel.add_widget(btn)
        return panel

    def _energy_chain_panel(self, items: List[Dict[str, Any]]) -> PremiumCard:
        panel = PremiumCard(title="Chaîne énergétique / moteur", size_hint_x=0.62)

        container = BoxLayout(orientation="vertical", spacing=dp(2), size_hint_y=None)
        container.bind(minimum_height=container.setter("height"))

        priority = [
            "Puissance totale demandée",
            "Puissance bus DC",
            "Batterie utile",
            "Architecture",
            "Nombre cylindres",
            "Alésage",
            "Course",
            "Régime moteur",
            "PME",
            "Pmax",
            "Couple max",
            "Couple moyen",
            "Cylindrée totale",
            "Score cohérence",
            "Score global",
        ]

        visible = 0

        for label in priority:
            item = next((i for i in items if i.get("label") == label), None)
            if not item:
                continue

            container.add_widget(
                MetricRow(
                    item.get("label", ""),
                    item.get("value"),
                    item.get("unit", ""),
                    item.get("status", ""),
                )
            )
            visible += 1

            if visible >= 13:
                break

        for item in items:
            if visible >= 13:
                break
            if item.get("label") in priority:
                continue

            container.add_widget(
                MetricRow(
                    item.get("label", ""),
                    item.get("value"),
                    item.get("unit", ""),
                    item.get("status", ""),
                )
            )
            visible += 1

        panel.add_widget(container)
        return panel

    def _subsystems_panel(self, items: List[Dict[str, Any]]) -> PremiumCard:
        panel = PremiumCard(title="Sous-systèmes backend", size_hint_x=0.38)

        scroll = ScrollView(do_scroll_x=False)
        container = BoxLayout(orientation="vertical", spacing=dp(2), size_hint_y=None)
        container.bind(minimum_height=container.setter("height"))

        if not items:
            container.add_widget(Label(text="Aucun sous-système détecté.", color=COLORS["RS"]))
        else:
            for item in items:
                row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(32), spacing=dp(8))

                name = Label(
                    text=str(item.get("name", "Sous-système")),
                    color=COLORS["GS"],
                    font_size="11sp",
                    halign="left",
                    valign="middle",
                    size_hint_x=0.64,
                )
                name.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
                row.add_widget(name)

                row.add_widget(
                    StatusBadge(
                        status=item.get("status", "inconnu"),
                        size=(dp(86), dp(22)),
                        font_size="9sp",
                        size_hint_x=None,
                        width=dp(92),
                    )
                )

                container.add_widget(row)

        scroll.add_widget(container)
        panel.add_widget(scroll)
        return panel

    def _missing_summary_panel(self, count: int, unknowns: List[Dict[str, Any]]) -> PremiumCard:
        panel = PremiumCard(
            title="Données à compléter",
            size_hint_x=0.5,
            bg=COLORS["RS_18"] if count else COLORS["BL"],
        )

        if not count:
            panel.add_widget(Label(text="Système complet selon le rapport backend.", color=COLORS["NG"], bold=True))
            return panel

        panel.add_widget(
            Label(
                text=f"{count} manque(s) consolidé(s) depuis backend/main.py.",
                color=COLORS["RS"],
                bold=True,
                font_size="14sp",
                size_hint_y=None,
                height=dp(30),
            )
        )

        box = BoxLayout(orientation="vertical", spacing=dp(2), size_hint_y=None)
        box.bind(minimum_height=box.setter("height"))

        for item in unknowns[:4]:
            box.add_widget(
                MetricRow(
                    item.get("label", "Inconnue"),
                    item.get("value", ""),
                    "",
                    "missing",
                )
            )

        panel.add_widget(box)

        btn = GhostButton(text="VOIR LES DÉTAILS", size_hint_y=None, height=dp(38))
        btn.bind(on_release=lambda *_: self._go("missing_requirements"))
        panel.add_widget(btn)

        return panel

    def _next_actions_panel(self, alerts: List[Dict[str, Any]]) -> PremiumCard:
        panel = PremiumCard(title="Alertes / Actions", size_hint_x=0.5)

        if not alerts:
            panel.add_widget(Label(text="Aucune alerte critique consolidée.", color=COLORS["NG"], font_size="12sp"))
            return panel

        container = BoxLayout(orientation="vertical", spacing=dp(2), size_hint_y=None)
        container.bind(minimum_height=container.setter("height"))

        for alert in alerts[:5]:
            container.add_widget(
                MetricRow(
                    alert.get("label", "Alerte"),
                    alert.get("value", ""),
                    alert.get("unit", ""),
                    "alerte",
                )
            )

        panel.add_widget(container)
        return panel

    def _actions_panel(self, actions: List[Dict[str, Any]]) -> PremiumCard:
        panel = PremiumCard(title="Accès rapides", height=dp(104), size_hint_y=None)

        default_actions = [
            {"label": "Architecture", "target": "architecture_choice"},
            {"label": "Manques", "target": "missing_requirements"},
            {"label": "Paramètres", "target": "edit_parameters"},
            {"label": "JSON", "target": "raw_json"},
            {"label": "Accueil", "target": "home"},
        ]

        actions = actions or default_actions

        grid = GridLayout(cols=min(6, max(1, len(actions))), spacing=dp(8))

        for action in actions:
            label = str(action.get("label", "Action")).upper()
            target = str(action.get("target", "dashboard"))

            btn = ModernButton(text=label, font_size="10sp")
            btn.bind(on_release=lambda _, t=target: self._go(t))
            grid.add_widget(btn)

        panel.add_widget(grid)
        return panel

    # -------------------------------------------------------------------------
    # Utils écran
    # -------------------------------------------------------------------------

    def _find_value(self, ui: Mapping[str, Any], label: str) -> Any:
        for item in _safe_list(_deep_get(ui, "dashboard", "energy_chain")):
            if isinstance(item, Mapping) and item.get("label") == label:
                return item.get("value")
        return None

    def _go(self, screen_name: str) -> None:
        if self.manager is not None:
            self.manager.current = screen_name
