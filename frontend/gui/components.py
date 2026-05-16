# frontend\gui\components.py
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
from kivy.core.window import Window
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
    MetricRow,
    ModernButton,
    NeoCard,
    PremiumCard,
    SectionTitle,
    StatusBadge,
)


# =============================================================================
# Helpers généraux — aucune donnée inventée
# =============================================================================

def _c(name: str, fallback: Any = (1, 1, 1, 1)) -> Any:
    return COLORS.get(name, fallback)


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
    """
    Fusion profonde prudente.
    - Ignore les None.
    - Ne fabrique aucune valeur.
    - Les valeurs backend plus récentes peuvent écraser les valeurs front.
    """
    out: Dict[str, Any] = dict(base or {})
    if not isinstance(extra, Mapping):
        return out

    for key, value in extra.items():
        if value is None:
            continue

        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = _merge_dict_non_none(dict(out[key]), value)
        else:
            out[str(key)] = value

    return out


def _dedup_dicts(items: Iterable[Mapping[str, Any]], keys: Sequence[str]) -> List[Dict[str, Any]]:
    seen: set[Tuple[str, ...]] = set()
    out: List[Dict[str, Any]] = []

    for item in items:
        if not isinstance(item, Mapping):
            continue
        sig = tuple(str(item.get(k, "")) for k in keys)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(dict(item))

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


def _short_text(value: Any, max_len: int = 180) -> str:
    text = str(value or "").strip()
    if not text:
        return "Aucune description fournie."
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _label(
    text: str,
    *,
    color: Any = None,
    font_size: str = "12sp",
    bold: bool = False,
    height: Optional[float] = None,
) -> Label:
    lbl = Label(
        text=str(text),
        color=color or _c("BFW"),
        font_size=font_size,
        bold=bold,
        halign="left",
        valign="top",
        size_hint_y=None,
        height=height or dp(24),
    )
    lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
    return lbl


def _call_accepts_kwargs(fn: Callable[..., Any]) -> bool:
    try:
        sig = inspect.signature(fn)
    except Exception:
        return True

    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())


def _filter_kwargs(fn: Callable[..., Any], params: Mapping[str, Any]) -> Dict[str, Any]:
    clean = {str(k): v for k, v in dict(params or {}).items() if v is not None}

    if _call_accepts_kwargs(fn):
        return clean

    try:
        sig = inspect.signature(fn)
    except Exception:
        return clean

    accepted = set(sig.parameters.keys())
    return {k: v for k, v in clean.items() if k in accepted}


def _safe_call_method(fn: Callable[..., Any], params: Mapping[str, Any]) -> Any:
    """
    Appelle un hook backend app.* de plusieurs façons.
    Le but est de s'adapter aux noms existants sans casser ton App.
    """
    try:
        sig = inspect.signature(fn)
    except Exception:
        sig = None

    filtered = _filter_kwargs(fn, params)

    attempts: List[Tuple[Tuple[Any, ...], Dict[str, Any]]] = [
        ((), filtered),
        ((dict(params),), {}),
        ((), {}),
    ]

    for args, kwargs in attempts:
        try:
            if sig is not None:
                required = [
                    p
                    for p in sig.parameters.values()
                    if p.default is inspect._empty
                    and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                ]
                if len(required) > 1 and not kwargs:
                    continue
            return fn(*args, **kwargs)
        except TypeError:
            continue

    return None


# =============================================================================
# Extraction récursive backend
# =============================================================================

BACKEND_REPORT_ATTRS: Tuple[str, ...] = (
    "backend_report",
    "last_backend_report",
    "full_report",
    "last_full_report",
    "engine_report",
    "last_engine_report",
    "system_report",
    "last_system_report",
    "report",
    "last_report",
    "raw_report",
    "data_report",
    "all_data",
    "toutes_les_donnees",
    "ui_report",
)

BACKEND_METHOD_CANDIDATES: Tuple[str, ...] = (
    # Hooks directs conseillés dans ton App
    "get_backend_report",
    "collect_backend_report",
    "fetch_backend_report",
    "load_backend_report",
    "refresh_backend_report",
    "sync_backend_report",
    "build_backend_report",

    # Hooks de calcul éventuels
    "run_backend_dimensioning",
    "dimensionner_backend",
    "dimensionner_systeme",
    "compute_backend_report",
    "compute_ui_report",
    "recalculate_backend",
    "recalculate",
    "run_calculation",
)

JSON_REPORT_ATTRS: Tuple[str, ...] = (
    "backend_report_path",
    "report_path",
    "last_report_path",
    "output_json_path",
    "toutes_les_donnees_path",
)

COMMON_JSON_REPORT_NAMES: Tuple[str, ...] = (
    "toutes_les_donnees_completes.json",
    "systeme_complet.json",
    "rapport_systeme.json",
    "rapport_backend.json",
    "test_systeme_complet.json",
)


def _walk_dicts(root: Any, path: str = "") -> Iterable[Tuple[str, Mapping[str, Any]]]:
    if isinstance(root, Mapping):
        yield path, root
        for key, value in root.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield from _walk_dicts(value, child_path)
    elif isinstance(root, list):
        for idx, value in enumerate(root):
            yield from _walk_dicts(value, f"{path}[{idx}]")


def _looks_like_architecture_candidate(item: Any) -> bool:
    if not isinstance(item, Mapping):
        return False

    keys = {str(k).lower() for k in item.keys()}

    architecture_keys = {
        "architecture",
        "architecture_moteur",
        "type_architecture",
        "nom",
        "name",
        "arch",
    }

    score_keys = {
        "score",
        "score_global",
        "score_global_100",
        "score_coherence_100",
        "note",
        "cout",
        "rang",
    }

    geometry_keys = {
        "n_cyl",
        "nb_cyl",
        "nombre_cylindres",
        "bore_mm",
        "stroke_mm",
        "alesage_m",
        "course_m",
        "cylindree_totale_cc",
        "cylindree_totale_m3",
    }

    return bool(keys & architecture_keys) and bool(keys & (score_keys | geometry_keys))


def _architecture_family(name: Any) -> Optional[str]:
    text = str(name or "").strip()
    if not text:
        return None

    low = text.lower()

    if low.startswith("etoile") or low.startswith("étoile"):
        return "Etoile"
    if low.startswith("boxer"):
        return "Boxer"
    if low.startswith("ligne") or low.startswith("inline") or low.startswith("l"):
        return "L"
    if low.startswith("v"):
        return "V"
    if low.startswith("w"):
        return "W"

    if text in {"L", "V", "W", "Etoile", "Boxer"}:
        return text

    return text


def _candidate_architecture(cand: Mapping[str, Any]) -> str:
    return str(
        _first_non_empty(
            cand.get("architecture"),
            cand.get("Architecture"),
            cand.get("architecture_moteur"),
            cand.get("type_architecture"),
            cand.get("nom"),
            cand.get("name"),
            cand.get("arch"),
            _deep_get(cand, "resultats", "architecture"),
            _deep_get(cand, "synthese", "architecture"),
            _deep_get(cand, "meilleur", "architecture"),
            "",
        )
    )


def _candidate_score(cand: Mapping[str, Any]) -> Optional[float]:
    return _first_finite(
        cand.get("score"),
        cand.get("Score"),
        cand.get("note"),
        cand.get("score_global"),
        cand.get("score_global_100"),
        cand.get("score_coherence_100"),
        cand.get("score_technique"),
        _deep_get(cand, "scores", "global"),
        _deep_get(cand, "scores", "score_global"),
        _deep_get(cand, "resultats", "score"),
        _deep_get(cand, "resultats", "score_global"),
        _deep_get(cand, "synthese", "score_global_100"),
        _deep_get(cand, "synthese", "score_coherence_100"),
    )


def _candidate_is_blocking(cand: Mapping[str, Any]) -> bool:
    for key in ("bloquant", "blocking", "invalide", "invalid"):
        if cand.get(key) is True:
            return True

    for key in ("ok", "compatible", "faisable", "valide", "packaging_ok"):
        if cand.get(key) is False:
            return True

    inc = _safe_dict(cand.get("inconnues"))
    if _safe_list(inc.get("impossibles")):
        return True

    return False


def _candidate_status(cand: Mapping[str, Any], selected_arch: Optional[str]) -> str:
    arch = _candidate_architecture(cand)
    if selected_arch and arch == selected_arch:
        return "retenue"
    if _candidate_is_blocking(cand):
        return "bloquant"
    if _candidate_score(cand) is not None:
        return "disponible"
    return "partiel"


def _candidate_sort_key(cand: Mapping[str, Any]) -> Tuple[int, float, str]:
    blocking = 1 if _candidate_is_blocking(cand) else 0
    score = _candidate_score(cand)
    return (blocking, -(score if score is not None else -1.0), _candidate_architecture(cand))


def _normalize_candidate(raw: Mapping[str, Any], *, source_path: str = "") -> Dict[str, Any]:
    """
    Transforme n'importe quel morceau backend exploitable en candidat homogène.
    Ne crée pas de valeurs physiques : ne fait que recopier/converter les unités déjà présentes.
    """
    cand = dict(raw)
    arch = _candidate_architecture(cand)

    n_cyl = _first_non_none(
        cand.get("nombre_cylindres"),
        cand.get("N_cyl"),
        cand.get("n_cyl"),
        cand.get("nb_cyl"),
        cand.get("n_cylindres"),
        _deep_get(cand, "resultats", "nombre_cylindres"),
        _deep_get(cand, "synthese", "nombre_cylindres"),
    )

    bore_m = _first_finite(
        cand.get("alesage_m"),
        cand.get("bore_m"),
        cand.get("B_m"),
        _deep_get(cand, "geometrie", "alesage_m"),
        _deep_get(cand, "resultats", "alesage_m"),
        _deep_get(cand, "synthese", "alesage_m"),
    )
    bore_mm = _first_finite(
        cand.get("Bore_mm"),
        cand.get("bore_mm"),
        cand.get("alesage_mm"),
        _deep_get(cand, "resultats", "bore_mm"),
        _deep_get(cand, "synthese", "Bore_mm"),
    )
    if bore_m is None and bore_mm is not None:
        bore_m = bore_mm / 1000.0

    stroke_m = _first_finite(
        cand.get("course_m"),
        cand.get("stroke_m"),
        cand.get("S_m"),
        _deep_get(cand, "geometrie", "course_m"),
        _deep_get(cand, "resultats", "course_m"),
        _deep_get(cand, "synthese", "course_m"),
    )
    stroke_mm = _first_finite(
        cand.get("Stroke_mm"),
        cand.get("stroke_mm"),
        cand.get("course_mm"),
        _deep_get(cand, "resultats", "stroke_mm"),
        _deep_get(cand, "synthese", "Stroke_mm"),
    )
    if stroke_m is None and stroke_mm is not None:
        stroke_m = stroke_mm / 1000.0

    vd_cc = _first_finite(
        cand.get("vd_tot_cc"),
        cand.get("cylindree_totale_cc"),
        cand.get("displacement_cc"),
        _deep_get(cand, "cylindree", "cylindree_totale_cc"),
        _deep_get(cand, "resultats", "cylindree_totale_cc"),
        _deep_get(cand, "synthese", "cylindree_totale_cc"),
    )
    vd_m3 = _first_finite(
        cand.get("cylindree_totale_m3"),
        cand.get("V_tot_m3"),
        _deep_get(cand, "cylindree", "cylindree_totale_m3"),
        _deep_get(cand, "resultats", "cylindree_totale_m3"),
        _deep_get(cand, "synthese", "cylindree_totale_m3"),
    )
    if vd_cc is None and vd_m3 is not None:
        vd_cc = vd_m3 * 1e6
    if vd_m3 is None and vd_cc is not None:
        vd_m3 = vd_cc / 1e6

    normalized = dict(cand)
    normalized.update(
        {
            "architecture": arch,
            "architecture_family": _architecture_family(arch),
            "nombre_cylindres": _safe_int(n_cyl) if n_cyl is not None else n_cyl,
            "alesage_m": bore_m,
            "course_m": stroke_m,
            "cylindree_totale_m3": vd_m3,
            "cylindree_totale_cc": vd_cc,
            "score": _candidate_score(cand),
            "backend_source_path": source_path,
        }
    )

    return normalized


def _candidate_from_resume_gui(resume_gui: Mapping[str, Any], *, source_path: str) -> Optional[Dict[str, Any]]:
    if not isinstance(resume_gui, Mapping):
        return None

    arch = _first_non_empty(resume_gui.get("Architecture"), resume_gui.get("architecture"))
    if not arch:
        return None

    return _normalize_candidate(
        {
            "architecture": arch,
            "description": "Architecture issue du bloc resume_gui backend.",
            "nombre_cylindres": resume_gui.get("N_cyl"),
            "Bore_mm": resume_gui.get("Bore_mm"),
            "Stroke_mm": resume_gui.get("Stroke_mm"),
            "RPM": resume_gui.get("RPM"),
            "PME_Pa": _first_non_none(resume_gui.get("PME_Pa"), resume_gui.get("PME")),
            "Pmax_Pa": resume_gui.get("Pmax_Pa"),
            "Couple_max_Nm": resume_gui.get("Couple_max_Nm"),
            "couple_moyen_Nm": resume_gui.get("couple_moyen_Nm"),
            "vd_tot_cc": resume_gui.get("vd_tot_cc"),
            "P_bus_dc_design_w": resume_gui.get("P_bus_dc_design_w"),
            "energie_batterie_kwh": resume_gui.get("energie_batterie_kwh"),
            "score_coherence_100": resume_gui.get("score_coherence_100"),
            "score_global_100": resume_gui.get("score_global_100"),
            "nb_pieces_construites": resume_gui.get("nb_pieces_construites"),
            "nb_inconnues": resume_gui.get("nb_inconnues"),
        },
        source_path=source_path,
    )


def _extract_candidates_from_report(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """
    Récupère les architectures depuis tous les emplacements plausibles du backend :
    - architecture_candidates front éventuel
    - resume_gui
    - systeme_complet.sous_systemes.architecture.*
    - analyses_composants.*.exploration / meilleur / meilleurs_par_architecture
    - rapports imbriqués divers
    """
    candidates: List[Dict[str, Any]] = []

    for path, node in _walk_dicts(report):
        # 1) Listes explicites de candidats
        for key in (
            "architecture_candidates",
            "architectures_candidates",
            "candidats_architecture",
            "candidates_architecture",
            "candidates",
            "exploration",
        ):
            value = node.get(key)
            if isinstance(value, list):
                for idx, item in enumerate(value):
                    if _looks_like_architecture_candidate(item):
                        candidates.append(
                            _normalize_candidate(
                                item,
                                source_path=f"{path}.{key}[{idx}]" if path else f"{key}[{idx}]",
                            )
                        )

        # 2) Meilleur candidat isolé
        for key in ("meilleur", "best", "solution", "architecture_retenue"):
            value = node.get(key)
            if _looks_like_architecture_candidate(value):
                candidates.append(
                    _normalize_candidate(
                        value,
                        source_path=f"{path}.{key}" if path else key,
                    )
                )

        # 3) Meilleurs par architecture : dict[str, dict]
        value = node.get("meilleurs_par_architecture")
        if isinstance(value, Mapping):
            for arch_key, item in value.items():
                if isinstance(item, Mapping):
                    merged = dict(item)
                    merged.setdefault("architecture", arch_key)
                    candidates.append(
                        _normalize_candidate(
                            merged,
                            source_path=f"{path}.meilleurs_par_architecture.{arch_key}",
                        )
                    )

        # 4) resume_gui
        if "resume_gui" in node and isinstance(node.get("resume_gui"), Mapping):
            cand = _candidate_from_resume_gui(
                node["resume_gui"],
                source_path=f"{path}.resume_gui" if path else "resume_gui",
            )
            if cand is not None:
                candidates.append(cand)

    # 5) resume_gui racine
    root_resume = _safe_dict(report.get("resume_gui"))
    cand = _candidate_from_resume_gui(root_resume, source_path="resume_gui")
    if cand is not None:
        candidates.append(cand)

    # Dédup : on garde la version la plus riche à architecture égale + source proche
    by_key: Dict[str, Dict[str, Any]] = {}
    for cand in candidates:
        arch = _candidate_architecture(cand)
        n_cyl = cand.get("nombre_cylindres")
        key = f"{arch}|{n_cyl}"

        old = by_key.get(key)
        if old is None:
            by_key[key] = cand
            continue

        old_richness = sum(1 for v in old.values() if v is not None)
        new_richness = sum(1 for v in cand.values() if v is not None)
        if new_richness >= old_richness:
            by_key[key] = _merge_dict_non_none(old, cand)

    out = list(by_key.values())
    out.sort(key=_candidate_sort_key)
    return out


def _collect_unknowns(report: Mapping[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {
        "impossibles": [],
        "partielles": [],
        "cao": [],
        "backend": [],
    }

    for path, node in _walk_dicts(report):
        inc = node.get("inconnues")
        if isinstance(inc, Mapping):
            for category in ("impossibles", "partielles", "cao"):
                for item in _safe_list(inc.get(category)):
                    if isinstance(item, Mapping):
                        enriched = dict(item)
                        enriched.setdefault("source", path or "racine")
                        out.setdefault(category, []).append(enriched)

        # Cas spécial : cao.inconnues_cao
        inconnues_cao = node.get("inconnues_cao")
        if isinstance(inconnues_cao, list):
            for item in inconnues_cao:
                if isinstance(item, Mapping):
                    enriched = dict(item)
                    enriched.setdefault("source", path or "cao")
                    out["cao"].append(enriched)

        # Cas spécial : erreurs construction_debug
        construction_debug = node.get("construction_debug")
        if isinstance(construction_debug, Mapping):
            for name, dbg in construction_debug.items():
                if isinstance(dbg, Mapping) and dbg.get("erreur"):
                    out["backend"].append(
                        {
                            "nom": str(name),
                            "raison": str(dbg.get("erreur")),
                            "source": f"{path}.construction_debug" if path else "construction_debug",
                        }
                    )

    for key in list(out.keys()):
        out[key] = _dedup_dicts(out[key], keys=("nom", "piece", "champ", "raison", "source"))

    return out


def _collect_alerts(report: Mapping[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}

    for path, node in _walk_dicts(report):
        alerts = node.get("alertes")
        if not isinstance(alerts, Mapping):
            continue

        for category, values in alerts.items():
            for item in _safe_list(values):
                if isinstance(item, Mapping):
                    enriched = dict(item)
                    enriched.setdefault("source", path or "racine")
                    out.setdefault(str(category), []).append(enriched)

    for key in list(out.keys()):
        out[key] = _dedup_dicts(out[key], keys=("nom", "detail", "source"))

    return out


def _build_ui_report_from_backend(backend_report: Mapping[str, Any]) -> Dict[str, Any]:
    candidates = _extract_candidates_from_report(backend_report)
    unknowns = _collect_unknowns(backend_report)
    alerts = _collect_alerts(backend_report)

    ui: Dict[str, Any] = {
        "architecture_candidates": candidates,
        "inconnues": unknowns,
        "alertes": alerts,
        "backend_report_present": bool(backend_report),
        "backend_sources": _safe_list(backend_report.get("_backend_sources")),
    }

    resume_gui = _safe_dict(backend_report.get("resume_gui"))
    if resume_gui:
        ui["resume_gui"] = resume_gui

    cao = _safe_dict(backend_report.get("cao"))
    if cao:
        ui["cao"] = cao

    optimisation = _safe_dict(backend_report.get("optimisation"))
    if optimisation:
        ui["optimisation"] = optimisation

    return ui


# =============================================================================
# Collecteur backend
# =============================================================================

class BackendReportHarvester:
    """
    Récupère le maximum d'information backend disponible.

    Priorité :
      1. attributs déjà présents dans App ;
      2. méthodes App de synchronisation/calcul ;
      3. fichiers JSON exportés ;
      4. appel direct à backend.main.dimensionner_systeme_shsem si les params existent.
    """

    def __init__(self, app: Any, *, force_backend_call: bool = False) -> None:
        self.app = app
        self.force_backend_call = force_backend_call
        self.errors: List[Dict[str, Any]] = []
        self.sources: List[str] = []

    def harvest(self) -> Dict[str, Any]:
        params = _safe_dict(getattr(self.app, "engine_params", {}) or {})
        reports: List[Dict[str, Any]] = []

        # 1) Attributs déjà chargés
        reports.extend(self._read_report_attrs())

        # 2) Fichiers JSON exportés
        reports.extend(self._read_json_reports())

        # 3) Hooks App
        reports.extend(self._call_app_backend_methods(params))

        # 4) Attributs relus après hooks, car certains hooks mutent app.ui_report/backend_report
        reports.extend(self._read_report_attrs())

        # 5) Appel backend strict direct si nécessaire ou demandé
        if self.force_backend_call or not self._has_architecture_candidates(reports):
            direct = self._call_backend_main(params)
            if direct:
                reports.append(direct)

        merged: Dict[str, Any] = {}
        for report in reports:
            merged = _merge_dict_non_none(merged, report)

        merged["_backend_sources"] = list(dict.fromkeys(self.sources))
        if self.errors:
            merged.setdefault("_backend_errors", self.errors)

        ui_report = _merge_dict_non_none(
            _safe_dict(getattr(self.app, "ui_report", {}) or {}),
            _build_ui_report_from_backend(merged),
        )

        # Si app.ui_report contenait déjà des candidats non présents dans backend, on les conserve.
        existing_candidates = [
            c for c in _safe_list(_safe_dict(getattr(self.app, "ui_report", {}) or {}).get("architecture_candidates"))
            if isinstance(c, Mapping)
        ]
        backend_candidates = [
            c for c in _safe_list(ui_report.get("architecture_candidates"))
            if isinstance(c, Mapping)
        ]

        all_candidates = [_normalize_candidate(c, source_path=str(c.get("backend_source_path", "app.ui_report"))) for c in existing_candidates]
        all_candidates += [_normalize_candidate(c, source_path=str(c.get("backend_source_path", "backend")))) for c in backend_candidates]

        ui_report["architecture_candidates"] = _dedup_candidates(all_candidates)

        return {
            "backend_report": merged,
            "ui_report": ui_report,
            "errors": self.errors,
            "sources": self.sources,
        }

    def _has_architecture_candidates(self, reports: List[Mapping[str, Any]]) -> bool:
        for report in reports:
            if _extract_candidates_from_report(report):
                return True
        return False

    def _push_error(self, source: str, exc: Exception | str) -> None:
        self.errors.append(
            {
                "source": source,
                "erreur": str(exc),
            }
        )

    def _read_report_attrs(self) -> List[Dict[str, Any]]:
        reports: List[Dict[str, Any]] = []

        for attr in BACKEND_REPORT_ATTRS:
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

        for attr in JSON_REPORT_ATTRS:
            try:
                value = getattr(self.app, attr, None)
            except Exception:
                value = None
            if value:
                raw_paths.append(value)

        cwd = Path.cwd()
        for name in COMMON_JSON_REPORT_NAMES:
            raw_paths.append(cwd / name)
            raw_paths.append(cwd / "backend" / name)
            raw_paths.append(cwd / "backend" / "logs" / name)
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

    def _call_app_backend_methods(self, params: Mapping[str, Any]) -> List[Dict[str, Any]]:
        reports: List[Dict[str, Any]] = []

        for method_name in BACKEND_METHOD_CANDIDATES:
            fn = getattr(self.app, method_name, None)
            if not callable(fn):
                continue

            try:
                out = _safe_call_method(fn, params)
            except Exception as exc:
                self._push_error(f"app.{method_name}", exc)
                continue

            if isinstance(out, Mapping):
                report = dict(out)
                report.setdefault("_method_source", f"app.{method_name}")
                reports.append(report)
                self.sources.append(f"app.{method_name}")

        return reports

    def _call_backend_main(self, params: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Appel direct de l'orchestrateur strict.
        Ne passe que les paramètres connus par la signature.
        N'utilise PAS le helper simple par défaut, car il injecte des hypothèses GUI.
        """
        if not isinstance(params, Mapping) or not params:
            self._push_error(
                "backend.main.dimensionner_systeme_shsem",
                "engine_params vide : appel backend strict ignoré.",
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
                    f"Import impossible : {exc} / {exc2}",
                )
                return None

        try:
            kwargs = _filter_kwargs(dimensionner_systeme_shsem, params)
            if not kwargs:
                self._push_error(
                    "backend.main.dimensionner_systeme_shsem",
                    "Aucun paramètre compatible avec la signature backend.",
                )
                return None

            report = dimensionner_systeme_shsem(**kwargs)
            if isinstance(report, Mapping):
                out = dict(report)
                out.setdefault("_method_source", "backend.main.dimensionner_systeme_shsem")
                self.sources.append("backend.main.dimensionner_systeme_shsem")
                return out

            self._push_error(
                "backend.main.dimensionner_systeme_shsem",
                f"Retour non mapping : {type(report).__name__}",
            )
            return None

        except Exception as exc:
            self._push_error("backend.main.dimensionner_systeme_shsem", exc)
            return None


def _dedup_candidates(candidates: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}

    for cand in candidates:
        if not isinstance(cand, Mapping):
            continue

        norm = _normalize_candidate(cand, source_path=str(cand.get("backend_source_path", "")))
        arch = _candidate_architecture(norm)
        n_cyl = norm.get("nombre_cylindres")
        key = f"{arch}|{n_cyl}"

        old = by_key.get(key)
        if old is None:
            by_key[key] = norm
            continue

        old_richness = sum(1 for v in old.values() if v is not None)
        new_richness = sum(1 for v in norm.values() if v is not None)

        if new_richness >= old_richness:
            by_key[key] = _merge_dict_non_none(old, norm)

    out = list(by_key.values())
    out.sort(key=_candidate_sort_key)
    return out


# =============================================================================
# Écran Kivy
# =============================================================================

class ArchitectureChoiceScreen(Screen):
    """
    Écran de sélection d'architecture.

    Correction majeure :
    - ne dépend plus uniquement de app.ui_report ;
    - va chercher les données dans le backend déjà calculé ;
    - tente les hooks backend de l'App ;
    - lit les JSON exportés si présents ;
    - peut appeler l'orchestrateur backend strict avec app.engine_params ;
    - reconstruit architecture_candidates depuis resume_gui / systeme_complet / analyses_composants / optimisation.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._sync_running = False
        self._last_backend_report: Dict[str, Any] = {}
        self._last_ui_report: Dict[str, Any] = {}
        self._last_errors: List[Dict[str, Any]] = []
        self._last_sources: List[str] = []

    def on_enter(self, *_: Any) -> None:
        self.refresh(force_backend=True)

    # -------------------------------------------------------------------------
    # Synchronisation
    # -------------------------------------------------------------------------

    def refresh(self, *, force_backend: bool = False) -> None:
        if force_backend:
            self._render_loading()
            self._start_backend_sync(force_backend_call=True)
            return

        app = App.get_running_app()
        ui = _safe_dict(getattr(app, "ui_report", {}) or {})
        backend = _safe_dict(getattr(app, "backend_report", {}) or {})

        if backend:
            ui = _merge_dict_non_none(ui, _build_ui_report_from_backend(backend))

        self._render(ui_report=ui, backend_report=backend)

    def _start_backend_sync(self, *, force_backend_call: bool = False) -> None:
        if self._sync_running:
            return

        self._sync_running = True
        app = App.get_running_app()

        def worker() -> None:
            try:
                payload = BackendReportHarvester(
                    app,
                    force_backend_call=force_backend_call,
                ).harvest()
            except Exception as exc:
                payload = {
                    "backend_report": {},
                    "ui_report": _safe_dict(getattr(app, "ui_report", {}) or {}),
                    "errors": [
                        {
                            "source": "ArchitectureChoiceScreen._start_backend_sync",
                            "erreur": str(exc),
                            "trace": traceback.format_exc(),
                        }
                    ],
                    "sources": [],
                }

            Clock.schedule_once(lambda *_: self._finish_backend_sync(payload), 0)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_backend_sync(self, payload: Mapping[str, Any]) -> None:
        self._sync_running = False

        app = App.get_running_app()

        backend_report = _safe_dict(payload.get("backend_report"))
        ui_report = _safe_dict(payload.get("ui_report"))
        errors = _safe_list(payload.get("errors"))
        sources = [str(s) for s in _safe_list(payload.get("sources"))]

        self._last_backend_report = backend_report
        self._last_ui_report = ui_report
        self._last_errors = [dict(e) for e in errors if isinstance(e, Mapping)]
        self._last_sources = sources

        try:
            app.backend_report = backend_report
            app.ui_report = ui_report
            app.backend_sync_errors = self._last_errors
            app.backend_sync_sources = self._last_sources
        except Exception:
            pass

        self._render(ui_report=ui_report, backend_report=backend_report)

    # -------------------------------------------------------------------------
    # Rendu principal
    # -------------------------------------------------------------------------

    def _render_loading(self) -> None:
        self.clear_widgets()

        root = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(10),
        )
        root.add_widget(self._top_bar(count=0, selected_arch="", backend_status="synchronisation"))

        panel = PremiumCard(title="SYNCHRONISATION BACKEND", bg=_c("BFW_08"))
        panel.add_widget(
            _label(
                "Récupération des rapports backend, des candidats d’architecture, du resume_gui, des rapports pièces et des inconnues consolidées.",
                color=_c("BFW"),
                font_size="13sp",
                height=dp(58),
            )
        )
        panel.add_widget(
            _label(
                "Aucune valeur n’est inventée côté interface : l’écran attend les données calculées ou exportées par le backend.",
                color=_c("GS"),
                font_size="11sp",
                height=dp(42),
            )
        )

        root.add_widget(panel)
        self.add_widget(root)

    def _render(self, *, ui_report: Mapping[str, Any], backend_report: Mapping[str, Any]) -> None:
        self.clear_widgets()

        app = App.get_running_app()
        params = _safe_dict(getattr(app, "engine_params", {}) or {})

        selected_arch = str(
            _first_non_empty(
                params.get("architecture"),
                params.get("architecture_moteur"),
                params.get("architecture_forcee"),
                ui_report.get("selected_architecture"),
                "",
            )
        )

        candidates = [
            _normalize_candidate(c, source_path=str(c.get("backend_source_path", "ui_report")))
            for c in _safe_list(ui_report.get("architecture_candidates"))
            if isinstance(c, Mapping)
        ]
        candidates = _dedup_candidates(candidates)

        backend_status = "ok" if backend_report else "indisponible"
        if self._last_errors and not backend_report:
            backend_status = "erreur"
        elif self._last_errors:
            backend_status = "alerte"

        root = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(10),
        )
        root.add_widget(
            self._top_bar(
                count=len(candidates),
                selected_arch=selected_arch,
                backend_status=backend_status,
            )
        )

        root.add_widget(self._backend_summary_panel(ui_report, backend_report))

        if not candidates:
            root.add_widget(self._empty_panel(ui_report))
        else:
            root.add_widget(self._candidates_panel(candidates, selected_arch))

        self.add_widget(root)

    def _top_bar(self, *, count: int, selected_arch: str, backend_status: str) -> BoxLayout:
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(62),
            spacing=dp(10),
            padding=[dp(10), dp(5)],
        )

        left = BoxLayout(orientation="vertical", spacing=dp(2))

        left.add_widget(
            _label(
                "SÉLECTION D'ARCHITECTURE",
                color=_c("BFW"),
                font_size="16sp",
                bold=True,
                height=dp(28),
            )
        )

        subtitle = f"{count} candidat(s) récupéré(s)"
        if selected_arch:
            subtitle += f" · sélection actuelle : {selected_arch}"

        left.add_widget(
            _label(
                subtitle,
                color=_c("GS"),
                font_size="11sp",
                height=dp(22),
            )
        )

        bar.add_widget(left)

        bar.add_widget(StatusBadge(status=backend_status, size_hint_x=None, width=dp(120)))

        btn_sync = ModernButton(
            text="SYNC BACKEND",
            size_hint_x=None,
            width=dp(140),
            font_size="11sp",
        )
        btn_sync.bind(on_release=lambda *_: self.refresh(force_backend=True))
        bar.add_widget(btn_sync)

        btn_back = ModernButton(
            text="RETOUR DASHBOARD",
            size_hint_x=None,
            width=dp(180),
            font_size="11sp",
        )
        btn_back.bind(on_release=lambda *_: self._go("dashboard"))
        bar.add_widget(btn_back)

        return bar

    def _backend_summary_panel(self, ui_report: Mapping[str, Any], backend_report: Mapping[str, Any]) -> NeoCard:
        card = NeoCard(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(86),
            spacing=dp(8),
            padding=dp(10),
        )

        resume_gui = _safe_dict(
            _first_non_none(
                ui_report.get("resume_gui"),
                backend_report.get("resume_gui"),
                {},
            )
        )

        cao = _safe_dict(
            _first_non_none(
                ui_report.get("cao"),
                backend_report.get("cao"),
                {},
            )
        )

        card.add_widget(
            MetricRow(
                "Sources backend",
                len(self._last_sources),
                "",
                status="ok" if self._last_sources else "missing",
            )
        )
        card.add_widget(
            MetricRow(
                "Architecture GUI",
                resume_gui.get("Architecture"),
                "",
                status="ok" if resume_gui.get("Architecture") else "missing",
            )
        )
        card.add_widget(
            MetricRow(
                "Pièces construites",
                resume_gui.get("nb_pieces_construites"),
                "",
                status="ok" if resume_gui.get("nb_pieces_construites") is not None else "missing",
            )
        )
        card.add_widget(
            MetricRow(
                "SolidWorks détaillé",
                _fmt_bool(cao.get("solidworks_ready_detaille")),
                "",
                status="ok" if cao.get("solidworks_ready_detaille") is True else "alerte",
            )
        )

        return card

    # -------------------------------------------------------------------------
    # Rendu absence candidat
    # -------------------------------------------------------------------------

    def _empty_panel(self, ui_report: Mapping[str, Any]) -> PremiumCard:
        panel = PremiumCard(
            title="ARCHITECTURE INDISPONIBLE",
            bg=_c("BFW_08"),
        )

        box = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=[dp(20), dp(8)],
            size_hint_y=None,
        )
        box.bind(minimum_height=box.setter("height"))

        box.add_widget(
            _label(
                "Aucun candidat d’architecture n’a été récupéré depuis le backend.",
                color=_c("RS"),
                font_size="14sp",
                bold=True,
                height=dp(34),
            )
        )

        reasons = self._missing_reasons(ui_report)
        for reason in reasons[:12]:
            box.add_widget(
                _label(
                    reason,
                    color=_c("BFW"),
                    font_size="11sp",
                    height=dp(36),
                )
            )

        if self._last_errors:
            box.add_widget(
                _label(
                    "Dernières erreurs de synchronisation :",
                    color=_c("RS"),
                    font_size="12sp",
                    bold=True,
                    height=dp(28),
                )
            )
            for err in self._last_errors[:5]:
                box.add_widget(
                    _label(
                        f"• {err.get('source', 'backend')} — {err.get('erreur', '')}",
                        color=_c("GS"),
                        font_size="10sp",
                        height=dp(36),
                    )
                )

        panel.add_widget(box)

        panel.add_widget(
            EmptyState(
                text="DONNÉES BACKEND INSUFFISANTES OU NON SYNCHRONISÉES",
                action_text="SYNCHRONISER LE BACKEND",
                callback=lambda *_: self.refresh(force_backend=True),
            )
        )

        return panel

    def _missing_reasons(self, ui_report: Mapping[str, Any]) -> List[str]:
        reasons: List[str] = []

        inconnues = _safe_dict(ui_report.get("inconnues"))

        for category in ("impossibles", "partielles", "cao", "backend"):
            for item in _safe_list(inconnues.get(category)):
                if not isinstance(item, Mapping):
                    continue

                nom = str(_first_non_empty(item.get("nom"), item.get("champ"), item.get("piece"), "")).strip()
                raison = str(item.get("raison", "")).strip()
                source = str(item.get("source", "")).strip()

                msg = "• "
                if nom:
                    msg += nom
                if raison:
                    msg += f" — {raison}" if nom else raison
                if source:
                    msg += f" [{source}]"

                if msg != "• ":
                    reasons.append(msg)

        if not reasons:
            reasons = [
                "• Aucun bloc `architecture_candidates`, `resume_gui`, `exploration`, `meilleur` ou `meilleurs_par_architecture` trouvé.",
                "• Vérifie que l’App stocke bien le rapport backend dans `app.backend_report`, `app.full_report`, `app.last_report` ou `app.ui_report`.",
                "• Vérifie que `app.engine_params` contient les paramètres nécessaires pour appeler `dimensionner_systeme_shsem`.",
            ]

        seen = set()
        out = []
        for reason in reasons:
            if reason in seen:
                continue
            seen.add(reason)
            out.append(reason)

        return out

    # -------------------------------------------------------------------------
    # Rendu candidats
    # -------------------------------------------------------------------------

    def _candidates_panel(self, candidates: List[Mapping[str, Any]], selected_arch: str) -> ScrollView:
        scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)

        cols = 1 if Window.width < dp(980) else 2

        grid = GridLayout(
            cols=cols,
            spacing=dp(16),
            size_hint_y=None,
            padding=[dp(2), dp(2), dp(8), dp(8)],
        )
        grid.bind(minimum_height=grid.setter("height"))

        for cand in candidates:
            grid.add_widget(self._candidate_card(dict(cand), selected_arch))

        scroll.add_widget(grid)
        return scroll

    def _candidate_card(self, cand: Dict[str, Any], selected_arch: str) -> NeoCard:
        arch = _candidate_architecture(cand)
        score = _candidate_score(cand)
        status = _candidate_status(cand, selected_arch)

        rows = self._extract_metric_rows(cand)

        height = dp(252 + 32 * len(rows))
        card = NeoCard(
            orientation="vertical",
            size_hint_y=None,
            height=height,
            spacing=dp(8),
            padding=dp(12),
        )

        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(34),
            spacing=dp(8),
        )
        header.add_widget(SectionTitle(text=str(arch)))
        header.add_widget(StatusBadge(status=status))
        card.add_widget(header)

        desc = _first_non_empty(
            cand.get("description"),
            cand.get("resume"),
            cand.get("commentaire"),
            cand.get("backend_source_path"),
            "Architecture récupérée depuis le backend.",
        )

        card.add_widget(
            _label(
                _short_text(desc, max_len=190),
                color=_c("GS"),
                font_size="11sp",
                height=dp(46),
            )
        )

        card.add_widget(
            MetricRow(
                "Score technique",
                _fmt_number(score) if score is not None else None,
                "/100",
                status="ok" if score is not None else "missing",
            )
        )

        for label, value, unit, row_status in rows:
            card.add_widget(MetricRow(label, value, unit, status=row_status))

        diag = self._candidate_diagnostic(cand)
        if diag:
            card.add_widget(
                _label(
                    diag,
                    color=_c("RS") if _candidate_is_blocking(cand) else _c("GS"),
                    font_size="10sp",
                    height=dp(42),
                )
            )

        btn = ModernButton(
            text="RETENIR CETTE ARCHITECTURE",
            size_hint_y=None,
            height=dp(44),
            font_size="12sp",
        )
        btn.disabled = _candidate_is_blocking(cand)
        btn.bind(on_release=lambda *_args, _arch=arch, _cand=cand: self._choose(_arch, _cand))
        card.add_widget(btn)

        return card

    def _extract_metric_rows(self, cand: Mapping[str, Any]) -> List[Tuple[str, Any, str, str]]:
        rows: List[Tuple[str, Any, str, str]] = []

        def add(label: str, value: Any, unit: str = "", *, status: Optional[str] = None) -> None:
            if value is None:
                return
            rows.append((label, value, unit, status or "ok"))

        n_cyl = _first_non_none(
            cand.get("nombre_cylindres"),
            cand.get("N_cyl"),
            cand.get("nb_cyl"),
            cand.get("n_cyl"),
        )
        add("Cylindres", n_cyl)

        bore_m = _safe_float(cand.get("alesage_m"))
        if bore_m is not None:
            add("Alésage", _fmt_number(bore_m * 1000.0), "mm")

        stroke_m = _safe_float(cand.get("course_m"))
        if stroke_m is not None:
            add("Course", _fmt_number(stroke_m * 1000.0), "mm")

        vd_cc = _safe_float(cand.get("cylindree_totale_cc"))
        if vd_cc is not None:
            add("Cylindrée", _fmt_number(vd_cc), "cm³")

        rpm = _first_finite(cand.get("RPM"), cand.get("rpm"), cand.get("rpm_nominal"), cand.get("regime_tr_min"))
        if rpm is not None:
            add("Régime", _fmt_number(rpm), "rpm")

        pme = _first_finite(cand.get("PME_Pa"), cand.get("PME"), cand.get("pme_pa"))
        if pme is not None:
            add("PME", _fmt_number(pme / 1e5), "bar")

        pmax = _first_finite(cand.get("Pmax_Pa"), cand.get("P_max"), cand.get("pression_max_pa"))
        if pmax is not None:
            add("Pression max", _fmt_number(pmax / 1e5), "bar")

        torque = _first_finite(cand.get("couple_moyen_Nm"), cand.get("Couple_max_Nm"), cand.get("couple_max_Nm"))
        if torque is not None:
            add("Couple", _fmt_number(torque), "Nm")

        bus = _first_finite(cand.get("P_bus_dc_design_w"), cand.get("puissance_bus_dc_design_w"))
        if bus is not None:
            add("Bus DC design", _fmt_number(bus), "W")

        battery = _first_finite(cand.get("energie_batterie_kwh"), cand.get("E_batterie_kwh"))
        if battery is not None:
            add("Batterie utile", _fmt_number(battery), "kWh")

        mass = _first_finite(cand.get("masse_kg"), cand.get("masse_estimee_kg"), cand.get("masse_totale_kg"))
        if mass is not None:
            add("Masse estimée", _fmt_number(mass), "kg")

        lmax = _first_finite(cand.get("L_max_m"), cand.get("longueur_m"), cand.get("longueur_dispo_m"))
        wmax = _first_finite(cand.get("W_max_m"), cand.get("largeur_m"), cand.get("largeur_dispo_m"))
        if lmax is not None and wmax is not None:
            add("Packaging", f"{_fmt_number(lmax)} × {_fmt_number(wmax)}", "m")

        nb_unknown = _first_finite(cand.get("nb_inconnues"))
        if nb_unknown is not None:
            add("Inconnues backend", _fmt_number(nb_unknown), "", status="alerte" if nb_unknown > 0 else "ok")

        nb_pieces = _first_finite(cand.get("nb_pieces_construites"))
        if nb_pieces is not None:
            add("Pièces construites", _fmt_number(nb_pieces), "")

        source = cand.get("backend_source_path")
        if source:
            add("Source", _short_text(source, 42), "", status="disponible")

        return rows[:12]

    def _candidate_diagnostic(self, cand: Mapping[str, Any]) -> str:
        if _candidate_is_blocking(cand):
            inc = _safe_dict(cand.get("inconnues"))
            impossibles = _safe_list(inc.get("impossibles"))
            if impossibles and isinstance(impossibles[0], Mapping):
                nom = str(impossibles[0].get("nom", "")).strip()
                raison = str(impossibles[0].get("raison", "")).strip()
                return _short_text(f"Blocage : {nom} — {raison}", max_len=170)

            return "Architecture bloquée par au moins une contrainte backend."

        if not cand.get("backend_source_path"):
            return "Candidat disponible, mais source backend non tracée."

        return ""

    # -------------------------------------------------------------------------
    # Sélection
    # -------------------------------------------------------------------------

    def _choose(self, arch: str, cand: Mapping[str, Any]) -> None:
        app = App.get_running_app()

        params = dict(getattr(app, "engine_params", {}) or {})
        arch_family = _architecture_family(arch)

        params["architecture"] = str(arch)
        params["architecture_candidate"] = dict(cand)
        params["architecture_backend_source"] = cand.get("backend_source_path")

        # Pour backend strict : utiliser la famille L/V/W/Etoile/Boxer quand possible.
        if arch_family:
            params["architecture_moteur"] = arch_family
            params["architecture_forcee"] = arch_family

        n_cyl = _safe_int(cand.get("nombre_cylindres"))
        if n_cyl is not None:
            params["nombre_cylindres"] = n_cyl
            params["n_cyl"] = n_cyl

        for target_key, candidate_keys in {
            "alesage_m": ("alesage_m",),
            "course_m": ("course_m",),
            "cylindree_totale_m3": ("cylindree_totale_m3",),
            "rpm_moteur_nominal": ("RPM", "rpm", "rpm_nominal", "regime_tr_min"),
            "pme_pa": ("PME_Pa", "PME", "pme_pa"),
            "pression_max_pa": ("Pmax_Pa", "P_max", "pression_max_pa"),
            "couple_moteur_max_Nm": ("Couple_max_Nm", "couple_max_Nm", "couple_moyen_Nm"),
        }.items():
            value = _first_non_none(*(cand.get(k) for k in candidate_keys))
            if value is not None:
                params[target_key] = value

        app.engine_params = params

        try:
            app.selected_architecture = str(arch)
            app.selected_architecture_candidate = dict(cand)
        except Exception:
            pass

        ui_report = dict(getattr(app, "ui_report", {}) or {})
        ui_report["selected_architecture"] = str(arch)
        ui_report["selected_architecture_candidate"] = dict(cand)
        app.ui_report = ui_report

        # Déclenche un recalcul si ton App expose un hook compatible.
        for method_name in (
            "on_architecture_selected",
            "request_recalculation",
            "request_recalculate",
            "recalculate_backend",
            "recalculate",
            "run_calculation",
            "start_calculation",
        ):
            fn = getattr(app, method_name, None)
            if callable(fn):
                try:
                    Clock.schedule_once(lambda *_args, _fn=fn: _safe_call_method(_fn, params), 0)
                    break
                except Exception:
                    pass

        self._go("loading")

    def _go(self, screen_name: str) -> None:
        if self.manager is not None:
            self.manager.current = screen_name