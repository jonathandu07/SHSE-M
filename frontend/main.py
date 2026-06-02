# frontend/main.py
from __future__ import annotations

"""
frontend/main.py
===============================================================================
Point d'entrée frontend STHO-ME / SHSE-M
===============================================================================

Rôle
----
Ce fichier est la façade frontend. Il ne recalcule rien lui-même.

Il appelle exclusivement backend/main.py pour :
- préflight backend ;
- dimensionnement système complet ;
- scénario 100 kW ;
- contrat frontend projet ;
- résolution des inconnues ;
- recalcul projet ;
- optimisation projet ;
- diagnostic / nettoyage logs.

Contrat
-------
- Le frontend conserve toujours le rapport backend brut complet.
- Les données affichables sont dérivées du rapport brut, sans invention.
- Les inconnues backend restent visibles.
- Les erreurs d'import backend sont remontées proprement.
- Compatible GUI Kivy si disponible.
- Compatible CLI si Kivy absent ou si --no-gui est demandé.
"""

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence
import argparse
import copy
import importlib
import importlib.util
import json
import math
import os
import sys
import traceback

from frontend.ensemble.contract_adapter import (
    STATUS_COMPUTED,
    STATUS_PARTIAL,
    annotate_contract_field,
    effective_field_status,
    field_has_trace,
    get_frontend_contract,
    index_contract_fields,
)
from frontend.ensemble.graphs_adapter import collect_backend_charts


# =============================================================================
# Chemins projet
# =============================================================================

_THIS_FILE = Path(__file__).resolve() if "__file__" in globals() else Path.cwd() / "frontend" / "main.py"
_FRONTEND_ROOT = _THIS_FILE.parent
_PROJECT_ROOT = _FRONTEND_ROOT.parent if _FRONTEND_ROOT.name == "frontend" else _FRONTEND_ROOT
_BACKEND_ROOT = _PROJECT_ROOT / "backend"
_BACKEND_MAIN_FILE = _BACKEND_ROOT / "main.py"
_DATA_DIR = _PROJECT_ROOT / "data"
_REPORTS_DIR = _DATA_DIR / "frontend_reports"
PROJECT_NAME = "STHOME"

# Kivy ecrit ses logs au demarrage. Dans l'app Codex/Windows, le dossier
# utilisateur peut etre verrouille ; on route donc les logs dans le workspace.
os.environ.setdefault("KIVY_HOME", str(_PROJECT_ROOT / ".kivy"))

for _candidate in (
    _PROJECT_ROOT,
    _FRONTEND_ROOT,
    _BACKEND_ROOT,
    _BACKEND_ROOT / "modules",
    _BACKEND_ROOT / "modules" / "main",
    _BACKEND_ROOT / "modules" / "systeme",
    Path.cwd(),
):
    try:
        _p = str(_candidate.resolve())
    except Exception:
        _p = str(_candidate)
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _deep_get(data: Any, *path: str) -> Any:
    cur = data
    for key in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)
        if cur is None:
            return None
    return cur


def _display_missing_name(name: Any) -> str:
    labels = {
        "regime_tr_min": "RPM nominal",
        "rpm": "RPM nominal",
        "rpm_nominal": "RPM nominal",
        "pme_pa": "PME",
        "pme": "PME",
        "gabarit (L/W)": "gabarit L/W",
    }
    return labels.get(str(name), str(name).replace("_", " "))


def _missing_requirements(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Compatibilité tests legacy : lit les inconnues backend sans les résoudre."""
    out: list[dict[str, Any]] = []
    inconnues = _deep_get(report, "analyses_composants", "architecture", "inconnues") or {}
    if not isinstance(inconnues, Mapping):
        return out
    for category in ("impossibles", "partielles", "cao", "backend"):
        values = inconnues.get(category) or []
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, Mapping):
                continue
            raw_name = item.get("nom") or item.get("champ") or item.get("piece") or ""
            out.append(
                {
                    "name": _display_missing_name(raw_name),
                    "raw_name": raw_name,
                    "reason": item.get("raison") or item.get("detail") or "",
                    "category": category,
                }
            )
    return out


def _fuel_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    """Compatibilité tests legacy : expose seulement le résumé carburant backend."""
    block = _deep_get(report, "analyses_composants", "moteur_thermique_bilan_carburant") or {}
    if not isinstance(block, Mapping):
        return {"mode": None, "worst": None, "best": None}
    return {
        "mode": block.get("mode"),
        "worst": block.get("carburant_dimensionnant"),
        "best": block.get("carburant_optimal"),
    }


# =============================================================================
# État imports backend
# =============================================================================

_IMPORT_ERRORS: Dict[str, str] = {}


def _record_import_error(name: str, exc: BaseException | str) -> None:
    if isinstance(exc, BaseException):
        _IMPORT_ERRORS[name] = f"{type(exc).__name__}: {exc}"
    else:
        _IMPORT_ERRORS[name] = str(exc)


def _load_backend_main_module() -> Any | None:
    """
    Charge backend/main.py sans confondre avec frontend/main.py.

    Ordre :
    1. backend.main
    2. import direct depuis backend/main.py
    """
    module_names = ("backend.main",)

    for module_name in module_names:
        try:
            return importlib.import_module(module_name)
        except BaseException as exc:
            _record_import_error(f"module:{module_name}", exc)

    if _BACKEND_MAIN_FILE.exists():
        try:
            spec = importlib.util.spec_from_file_location("sthome_backend_main", str(_BACKEND_MAIN_FILE))
            if spec is None or spec.loader is None:
                raise ImportError(f"spec invalide pour {_BACKEND_MAIN_FILE}")
            module = importlib.util.module_from_spec(spec)
            sys.modules.setdefault("sthome_backend_main", module)
            spec.loader.exec_module(module)
            return module
        except BaseException as exc:
            _record_import_error(f"file:{_BACKEND_MAIN_FILE}", exc)

    _record_import_error("backend_main_file", f"Fichier introuvable : {_BACKEND_MAIN_FILE}")
    return None


_BACKEND_MAIN = _load_backend_main_module()


def _backend_attr(name: str, default: Any = None) -> Any:
    if _BACKEND_MAIN is None:
        _record_import_error(f"attr:{name}", "backend/main.py non chargé")
        return default
    try:
        return getattr(_BACKEND_MAIN, name)
    except BaseException as exc:
        _record_import_error(f"attr:{name}", exc)
        return default


BackendMainOptions = _backend_attr("BackendMainOptions")
preflight_backend = _backend_attr("preflight_backend")
executer_backend = _backend_attr("executer_backend")
analyser_depuis_puissance = _backend_attr("analyser_depuis_puissance")
analyser_100kw = _backend_attr("analyser_100kw")
dimensionner_systeme_shsem = _backend_attr("dimensionner_systeme_shsem")
charger_data_contract = _backend_attr("charger_data_contract")
resoudre_inconnues_project = _backend_attr("resoudre_inconnues_project")
recalculer_project = _backend_attr("recalculer_project")
optimiser_project = _backend_attr("optimiser_project")
analyser_logs_backend = _backend_attr("analyser_logs_backend")
charger_json_backend = _backend_attr("charger_json")
sauvegarder_json_backend = _backend_attr("sauvegarder_json")

try:
    from frontend.ensemble.visualisation_orchestrator import construire_tableau_pages_visualisation
except BaseException as exc:  # pragma: no cover - dependance frontend optionnelle
    construire_tableau_pages_visualisation = None  # type: ignore[assignment]
    _record_import_error("frontend.ensemble.visualisation_orchestrator", exc)


# =============================================================================
# Options frontend
# =============================================================================

@dataclass
class FrontendMainOptions:
    project_id: str | None = None

    # Scénario par défaut de la GUI.
    # Ce n'est pas une donnée technique cachée : c'est seulement le scénario
    # d'appel si aucune configuration n'est fournie.
    default_power_kw: float | None = 100.0

    strict: bool = True
    resolve_unknowns: bool = True
    optimize: bool = True
    validate_chain: bool = True
    diagnostic: bool = True
    mechanical_graphs: bool = True
    cao_dossier: bool = True
    frontend_contract: bool = True
    save_repository: bool = False
    save_database: bool = False
    enrichir_pieces: bool = True
    include_traceback: bool = False
    max_resolution_iterations: int = 5
    report_name: str = "latest"

    run_log_diagnostic: bool = False
    clean_logs: bool = False
    log_dir: str | None = None
    log_report_path: str | None = None

    output_dir: str | None = None
    raw_report_name: str = "backend_raw_latest.json"
    ui_report_name: str = "frontend_ui_latest.json"


@dataclass
class FrontendRunState:
    ok: bool
    status: str
    action: str
    raw_report: Dict[str, Any] = field(default_factory=dict)
    ui_report: Dict[str, Any] = field(default_factory=dict)
    preflight: Dict[str, Any] = field(default_factory=dict)
    backend_available: bool = False
    backend_exports: Dict[str, bool] = field(default_factory=dict)
    import_errors: Dict[str, str] = field(default_factory=dict)
    output_paths: Dict[str, str] = field(default_factory=dict)


# =============================================================================
# Helpers JSON / données
# =============================================================================

def _is_finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _num(value: Any) -> float | None:
    if _is_finite(value):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            out = float(value.replace(",", "."))
            return out if math.isfinite(out) else None
        except Exception:
            return None
    return None


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _jsonable(value: Any, *, depth: int = 0, max_depth: int = 14) -> Any:
    if depth > max_depth:
        return {"type": type(value).__name__, "truncated": True}

    if value is None or isinstance(value, (str, int, bool)):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)

    if isinstance(value, Path):
        return str(value)

    if is_dataclass(value) and not isinstance(value, type):
        try:
            return _jsonable(asdict(value), depth=depth + 1, max_depth=max_depth)
        except Exception:
            return {"type": type(value).__name__}

    if isinstance(value, Mapping):
        return {
            str(k): _jsonable(v, depth=depth + 1, max_depth=max_depth)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v, depth=depth + 1, max_depth=max_depth) for v in value]

    for method_name in ("en_dict", "as_dict", "to_dict", "dict", "model_dump"):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                return _jsonable(method(), depth=depth + 1, max_depth=max_depth)
            except Exception:
                pass

    if hasattr(value, "__dict__"):
        try:
            public = {
                str(k): v
                for k, v in vars(value).items()
                if not str(k).startswith("_") and not callable(v)
            }
            return {
                "type": type(value).__name__,
                "attributs": _jsonable(public, depth=depth + 1, max_depth=max_depth),
            }
        except Exception:
            pass

    return {"type": type(value).__name__, "repr": repr(value)[:300]}


def _deep_merge(*items: Mapping[str, Any] | None) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    for item in items:
        if not isinstance(item, Mapping):
            continue

        for key, value in item.items():
            if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
                out[key] = _deep_merge(out[key], value)  # type: ignore[arg-type]
            else:
                try:
                    out[key] = copy.deepcopy(value)
                except Exception:
                    out[key] = _jsonable(value)

    return out


def _get_path(data: Any, path: str, default: Any = None) -> Any:
    if not isinstance(path, str) or not path:
        return default

    if isinstance(data, Mapping) and path in data:
        return data[path]

    cur = data
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return default

    return cur


def _set_path(data: Dict[str, Any], path: str, value: Any) -> None:
    cur = data
    parts = path.split(".")
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _load_json(path: str | os.PathLike[str]) -> Dict[str, Any]:
    if callable(charger_json_backend):
        return charger_json_backend(path)

    p = Path(path).expanduser().resolve()
    raw = json.loads(p.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("Le fichier JSON doit contenir un objet racine.")
    return raw


def _save_json(data: Mapping[str, Any], path: str | os.PathLike[str], *, indent: int = 2) -> str:
    if callable(sauvegarder_json_backend):
        return sauvegarder_json_backend(data, path, indent=indent)

    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_jsonable(data), ensure_ascii=False, indent=indent), encoding="utf-8")
    return str(p)


def _flatten_mapping(
    data: Any,
    *,
    prefix: str = "",
    max_depth: int = 6,
    depth: int = 0,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    if depth > max_depth:
        return out

    if isinstance(data, Mapping):
        for key, value in data.items():
            k = str(key)
            full = f"{prefix}.{k}" if prefix else k
            out[full] = value
            if isinstance(value, Mapping):
                out.update(_flatten_mapping(value, prefix=full, max_depth=max_depth, depth=depth + 1))

    return out


def _count_items(value: Any) -> int:
    if isinstance(value, Mapping):
        return len(value)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    if value is None:
        return 0
    return 1


def _label_from_key(key: str) -> str:
    labels = {
        "meta": "Métadonnées",
        "entrees": "Entrées",
        "calculs": "Calculs",
        "sous_systemes": "Sous-systèmes",
        "liaisons": "Liaisons système",
        "synthese": "Synthèse",
        "criteres_conception": "Critères de conception",
        "cao": "CAO / SolidWorks",
        "pieces": "Pièces",
        "composants": "Composants",
        "mechanical_graphs": "Graphiques mécaniques",
        "graphes": "Graphes",
        "graphs": "Graphes",
        "inconnues": "Inconnues",
        "alertes": "Alertes",
        "preflight": "Préflight backend",
        "logs": "Logs",
        "notes_modele": "Notes modèle",
        "output_path": "Sortie fichier",
    }
    return labels.get(key, key.replace("_", " ").strip().title())


def _status_from_report(report: Mapping[str, Any], preflight: Mapping[str, Any] | None = None) -> str:
    pf = _safe_dict(preflight)
    if pf and pf.get("ok") is False:
        return "bloque"

    if report.get("ok") is False:
        return "bloque"

    inc = _safe_dict(report.get("inconnues"))
    impossibles = inc.get("impossibles") or []
    if isinstance(impossibles, Sequence) and not isinstance(impossibles, (str, bytes)) and len(impossibles) > 0:
        return "attention"

    alertes = _safe_dict(report.get("alertes"))
    if any(bool(v) for v in alertes.values()):
        return "attention"

    return "ok"


def _ok_from_status(status: str) -> bool:
    return status in ("ok", "attention")


def _backend_exports_status() -> Dict[str, bool]:
    return {
        "BackendMainOptions": BackendMainOptions is not None,
        "preflight_backend": callable(preflight_backend),
        "executer_backend": callable(executer_backend),
        "analyser_depuis_puissance": callable(analyser_depuis_puissance),
        "analyser_100kw": callable(analyser_100kw),
        "dimensionner_systeme_shsem": callable(dimensionner_systeme_shsem),
        "charger_data_contract": callable(charger_data_contract),
        "resoudre_inconnues_project": callable(resoudre_inconnues_project),
        "recalculer_project": callable(recalculer_project),
        "optimiser_project": callable(optimiser_project),
        "analyser_logs_backend": callable(analyser_logs_backend),
        "charger_json": callable(charger_json_backend),
        "sauvegarder_json": callable(sauvegarder_json_backend),
    }


# =============================================================================
# Normalisation frontend
# =============================================================================

def _extract_inconnues(report: Mapping[str, Any]) -> Dict[str, list[dict[str, Any]]]:
    inc = _safe_dict(report.get("inconnues"))
    return {
        "impossibles": list(inc.get("impossibles") or []),
        "partielles": list(inc.get("partielles") or []),
    }


def _extract_alertes(report: Mapping[str, Any]) -> Dict[str, Any]:
    alertes = _safe_dict(report.get("alertes"))
    if not alertes:
        return {}
    return _jsonable(alertes)


def _extract_kpis(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """
    Extraction prudente de KPI depuis des chemins connus + recherche de secours.

    Aucun KPI n'est inventé :
    - si la valeur n'existe pas dans le rapport, elle n'est pas affichée ;
    - les unités sont uniquement déclaratives selon le champ trouvé.
    """
    specs: list[tuple[str, str, str, str]] = [
        ("Puissance utile sortie", "synthese.moteur_electrique.puissance_sortie_w", "W", "sortie"),
        ("Puissance utile sortie", "calculs.puissance_sortie.kw", "kW", "sortie"),
        ("Puissance utile sortie", "entrees.puissance.kw", "kW", "sortie"),
        ("Puissance utile sortie", "puissance_sortie_kw", "kW", "sortie"),

        ("Bus DC design", "synthese.systeme.P_bus_dc_design_w", "W", "bus_dc"),
        ("Bus DC design", "synthese.vehicule.puissance_bus_dc_design_w", "W", "bus_dc"),
        ("Bus DC design", "liaisons.bus_dc.P_bus_dc_design_w", "W", "bus_dc"),
        ("Tension bus DC", "synthese.vehicule.tension_bus_dc_v", "V", "bus_dc"),
        ("Tension bus DC", "liaisons.bus_dc.V_bus_dc_v", "V", "bus_dc"),

        ("Alternateur électrique", "synthese.alternateur.P_electrique_W", "W", "alternateur"),
        ("Alternateur mécanique", "synthese.alternateur.P_mecanique_W", "W", "alternateur"),
        ("Couple alternateur", "synthese.alternateur.couple_mecanique_Nm", "Nm", "alternateur"),
        ("Rendement alternateur", "synthese.alternateur.rendement", "", "alternateur"),

        ("Moteur thermique", "synthese.moteur_thermique.puissance_requise_W", "W", "moteur_thermique"),
        ("Couple thermique", "synthese.moteur_thermique.couple_requis_Nm", "Nm", "moteur_thermique"),
        ("Régime thermique", "synthese.moteur_thermique.rpm_nominal", "rpm", "moteur_thermique"),
        ("PME", "synthese.moteur_thermique.pme_pa", "Pa", "moteur_thermique"),
        ("Nombre cylindres", "synthese.moteur_thermique.nombre_cylindres", "", "moteur_thermique"),

        ("Alesage", "synthese.moteur_thermique.alesage_m", "m", "architecture"),
        ("Course", "synthese.moteur_thermique.course_m", "m", "architecture"),
        ("Cylindrée", "synthese.moteur_thermique.cylindree_totale_m3", "m³", "architecture"),

        ("Dossier de definition", "cao.solidworks_ready", "", "cao"),
        ("Score validation", "validation.score", "/100", "validation"),
        ("Score validation", "diagnostic.score", "/100", "diagnostic"),
    ]

    found: list[dict[str, Any]] = []
    used_names: set[str] = set()
    contract_fields = _contract_fields_by_path(report)

    for label, path, unit, group in specs:
        raw = _get_path(report, path)
        if raw is None:
            continue

        value = raw
        if isinstance(raw, bool):
            display = "Oui" if raw else "Non"
        elif _is_finite(raw):
            n = float(raw)
            if unit == "W" and abs(n) >= 1000.0:
                display = round(n / 1000.0, 3)
                unit_display = "kW"
            elif unit == "Pa" and abs(n) >= 100000.0:
                display = round(n / 100000.0, 3)
                unit_display = "bar"
            else:
                display = round(n, 6)
                unit_display = unit
            unit = unit_display
        else:
            display = raw

        sig = f"{label}:{group}"
        if sig in used_names:
            continue
        used_names.add(sig)

        found.append(
            _display_value_metadata(report, path, contract_fields)
            | {
                "label": label,
                "value": value,
                "display": display,
                "unit": unit,
                "group": group,
                "source_path": path,
            }
        )

    # Recherche de secours pour quelques clés fréquentes si les chemins exacts changent.
    flat = _flatten_mapping(report, max_depth=5)
    fallback_keys = {
        "puissance_sortie_kw": ("Puissance utile sortie", "kW", "sortie"),
        "puissance_sortie_w": ("Puissance utile sortie", "W", "sortie"),
        "P_bus_dc_design_w": ("Bus DC design", "W", "bus_dc"),
        "P_mecanique_W": ("Puissance mécanique", "W", "mecanique"),
        "couple_mecanique_Nm": ("Couple mécanique", "Nm", "mecanique"),
        "rpm_nominal": ("Régime nominal", "rpm", "mecanique"),
        "solidworks_ready": ("Dossier de definition", "", "cao"),
    }

    existing_labels = {str(k.get("label")) for k in found}
    for path, value in flat.items():
        leaf = path.split(".")[-1]
        if leaf not in fallback_keys:
            continue
        label, unit, group = fallback_keys[leaf]
        if label in existing_labels:
            continue
        if not (_is_finite(value) or isinstance(value, bool)):
            continue

        if isinstance(value, bool):
            display = "Oui" if value else "Non"
        else:
            n = float(value)
            if unit == "W" and abs(n) >= 1000.0:
                display = round(n / 1000.0, 3)
                unit = "kW"
            else:
                display = round(n, 6)

        found.append(
            _display_value_metadata(report, path, contract_fields)
            | {
                "label": label,
                "value": value,
                "display": display,
                "unit": unit,
                "group": group,
                "source_path": path,
            }
        )
        existing_labels.add(label)

    return found


def _contract_fields_by_path(report: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    contract = get_frontend_contract(report)
    return index_contract_fields(contract) if contract else {}


def _display_value_metadata(report: Mapping[str, Any], path: str, contract_fields: Mapping[str, Mapping[str, Any]] | None = None) -> Dict[str, Any]:
    field = dict((contract_fields or {}).get(path) or {})
    if not field:
        field = _find_trace_for_path(report, path)
    if field:
        annotated = annotate_contract_field(field)
        return {
            "status": effective_field_status(annotated),
            "raw_status": annotated.get("raw_status"),
            "confidence": annotated.get("confidence") or ("traced" if field_has_trace(annotated) else "untraced_report_value"),
            "trace_present": field_has_trace(annotated),
            "trace": annotated.get("trace") if isinstance(annotated.get("trace"), Mapping) else {},
            "display_warning": annotated.get("display_warning"),
        }
    return {
        "status": STATUS_PARTIAL,
        "raw_status": None,
        "confidence": "untraced_report_value",
        "trace_present": False,
        "trace": {},
        "display_warning": "Valeur brute sans trace backend : affichage partiel uniquement.",
    }


def _find_trace_for_path(report: Mapping[str, Any], path: str) -> Dict[str, Any]:
    trace = _safe_dict(_get_path(report, "tracabilite.valeurs"))
    item = trace.get(path)
    if isinstance(item, Mapping):
        return {"path": path, "status": item.get("status") or item.get("source") or STATUS_COMPUTED, "trace": dict(item), "confidence": item.get("confidence")}
    for hyp in _safe_list(report.get("hypotheses_resolues")):
        if not isinstance(hyp, Mapping):
            continue
        champ = hyp.get("champ")
        if champ == path or str(champ or "").split(".")[-1] == path.split(".")[-1]:
            return {
                "path": path,
                "status": hyp.get("status") or hyp.get("type_resolution"),
                "trace": dict(hyp),
                "confidence": hyp.get("niveau_confiance"),
            }
    return {}


def _extract_raw_sections(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    preferred_order = [
        "meta",
        "entrees",
        "calculs",
        "sous_systemes",
        "liaisons",
        "synthese",
        "criteres_conception",
        "validation",
        "diagnostic",
        "cao",
        "pieces",
        "composants",
        "mechanical_graphs",
        "graphes",
        "graphs",
        "inconnues",
        "alertes",
        "logs",
        "preflight",
        "notes_modele",
        "output_path",
    ]

    sections: list[dict[str, Any]] = []
    used: set[str] = set()

    def add_section(key: str, value: Any) -> None:
        if key in used:
            return
        used.add(key)
        sections.append(
            {
                "key": key,
                "title": _label_from_key(key),
                "type": type(value).__name__,
                "count": _count_items(value),
                "data": _jsonable(value),
            }
        )

    for key in preferred_order:
        if key in report:
            add_section(key, report[key])

    for key, value in report.items():
        if key not in used:
            add_section(str(key), value)

    return sections


def _extract_graph_blocks(report: Mapping[str, Any]) -> Dict[str, Any]:
    candidates = {}

    for key in ("mechanical_graphs", "graphes", "graphs", "courbes", "plots"):
        value = report.get(key)
        if value:
            candidates[key] = _jsonable(value)

    cao = _safe_dict(report.get("cao"))
    for key in ("graphes", "graphs", "contraintes", "rdm", "solidworks"):
        if key in cao:
            candidates[f"cao.{key}"] = _jsonable(cao[key])

    summary = collect_backend_charts(report)
    return {
        "status": summary.get("status"),
        "charts": summary.get("charts", []),
        "missing_fields": summary.get("missing_fields", []),
        "warnings": summary.get("warnings", []),
        "raw_blocks": candidates,
    }


def _extract_cao_block(report: Mapping[str, Any]) -> Dict[str, Any]:
    cao = _safe_dict(report.get("cao"))
    out = dict(cao)

    solidworks_ready = _get_path(report, "cao.solidworks_ready")
    if solidworks_ready is not None:
        out["solidworks_ready"] = bool(solidworks_ready)

    return _jsonable(out)


def _extract_piece_blocks(report: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    for key in ("pieces", "inventaire_pieces", "piece_inventory"):
        value = report.get(key)
        if value:
            out[key] = _jsonable(value)

    sous_systemes = _safe_dict(report.get("sous_systemes"))
    for comp_name, comp_report in sous_systemes.items():
        if isinstance(comp_report, Mapping) and isinstance(comp_report.get("pieces"), Mapping):
            out[f"sous_systemes.{comp_name}.pieces"] = _jsonable(comp_report.get("pieces"))

    composants = _safe_dict(report.get("composants"))
    for comp_name, comp_report in composants.items():
        if isinstance(comp_report, Mapping) and isinstance(comp_report.get("pieces"), Mapping):
            out[f"composants.{comp_name}.pieces"] = _jsonable(comp_report.get("pieces"))

    return out


def build_frontend_ui_report(
    raw_report: Mapping[str, Any],
    *,
    preflight: Mapping[str, Any] | None = None,
    action: str = "run",
) -> Dict[str, Any]:
    report = _jsonable(raw_report)
    pf = _jsonable(preflight or raw_report.get("preflight") or {})

    status = _status_from_report(_safe_dict(report), _safe_dict(pf))
    inconnues = _extract_inconnues(_safe_dict(report))
    alertes = _extract_alertes(_safe_dict(report))
    kpis = _extract_kpis(_safe_dict(report))
    raw_sections = _extract_raw_sections(_safe_dict(report))

    summary_cards = [
        {
            "title": "Backend",
            "value": "Disponible" if _BACKEND_MAIN is not None else "Indisponible",
            "status": "ok" if _BACKEND_MAIN is not None else "bloque",
        },
        {
            "title": "Préflight",
            "value": str(_get_path(pf, "status", "inconnu")),
            "status": "ok" if _get_path(pf, "ok") is not False else "bloque",
        },
        {
            "title": "Inconnues impossibles",
            "value": len(inconnues.get("impossibles") or []),
            "status": "attention" if inconnues.get("impossibles") else "ok",
        },
        {
            "title": "Inconnues partielles",
            "value": len(inconnues.get("partielles") or []),
            "status": "attention" if inconnues.get("partielles") else "ok",
        },
        {
            "title": "Sections brutes",
            "value": len(raw_sections),
            "status": "ok",
        },
    ]

    return {
        "meta": {
            "frontend_entrypoint": "frontend.main",
            "backend_entrypoint": "backend.main",
            "action": action,
            "status": status,
            "ok": _ok_from_status(status),
            "project_root": str(_PROJECT_ROOT),
            "backend_root": str(_BACKEND_ROOT),
            "frontend_root": str(_FRONTEND_ROOT),
        },
        "summary_cards": summary_cards,
        "kpis": kpis,
        "raw_sections": raw_sections,
        "inconnues": inconnues,
        "alertes": alertes,
        "cao": _extract_cao_block(_safe_dict(report)),
        "pieces": _extract_piece_blocks(_safe_dict(report)),
        "graphs": _extract_graph_blocks(_safe_dict(report)),
        "preflight": pf,
        "backend_exports": _backend_exports_status(),
        "import_errors": dict(_IMPORT_ERRORS),
        "raw_report": report,
    }


# =============================================================================
# Conversion options frontend -> backend
# =============================================================================

def _coerce_frontend_options(
    options: FrontendMainOptions | Mapping[str, Any] | None = None,
    **overrides: Any,
) -> FrontendMainOptions:
    if isinstance(options, FrontendMainOptions):
        data = asdict(options)
    elif isinstance(options, Mapping):
        data = {
            k: v
            for k, v in options.items()
            if k in FrontendMainOptions.__dataclass_fields__
        }
    else:
        data = {}

    for key, value in overrides.items():
        if key in FrontendMainOptions.__dataclass_fields__ and value is not None:
            data[key] = value

    return FrontendMainOptions(**data)


def _make_backend_options(opts: FrontendMainOptions) -> Any:
    data = {
        "project_id": opts.project_id,
        "strict": opts.strict,
        "resolve_unknowns": opts.resolve_unknowns,
        "optimize": opts.optimize,
        "validate_chain": opts.validate_chain,
        "diagnostic": opts.diagnostic,
        "mechanical_graphs": opts.mechanical_graphs,
        "cao_dossier": opts.cao_dossier,
        "frontend_contract": opts.frontend_contract,
        "save_repository": opts.save_repository,
        "save_database": opts.save_database,
        "enrichir_pieces": opts.enrichir_pieces,
        "include_traceback": opts.include_traceback,
        "max_resolution_iterations": opts.max_resolution_iterations,
        "report_name": opts.report_name,
        "run_log_diagnostic": opts.run_log_diagnostic,
        "clean_logs": opts.clean_logs,
        "log_dir": opts.log_dir,
        "log_report_path": opts.log_report_path,
    }

    if BackendMainOptions is not None:
        try:
            allowed = getattr(BackendMainOptions, "__dataclass_fields__", {})
            clean = {k: v for k, v in data.items() if k in allowed}
            return BackendMainOptions(**clean)
        except Exception:
            pass

    return data


def _prepare_config(
    config: Mapping[str, Any] | None = None,
    *,
    puissance_kw: float | None = None,
    puissance_w: float | None = None,
    opts: FrontendMainOptions,
) -> Dict[str, Any]:
    cfg = dict(config or {})

    has_power = any(k in cfg for k in ("puissance_sortie_kw", "puissance_sortie_w"))

    if puissance_w is not None:
        cfg["puissance_sortie_w"] = float(puissance_w)
    elif puissance_kw is not None:
        cfg["puissance_sortie_kw"] = float(puissance_kw)
    elif not has_power and opts.default_power_kw is not None:
        cfg["puissance_sortie_kw"] = float(opts.default_power_kw)
        cfg.setdefault("meta_frontend", {})["scenario_par_defaut"] = "default_power_kw"

    if opts.project_id:
        cfg.setdefault("project_id", opts.project_id)

    return cfg


def _make_error_report(action: str, exc: BaseException | str) -> Dict[str, Any]:
    if isinstance(exc, BaseException):
        msg = f"{type(exc).__name__}: {exc}"
        tb = traceback.format_exc()
    else:
        msg = str(exc)
        tb = None

    report: Dict[str, Any] = {
        "ok": False,
        "meta": {
            "entrypoint": "frontend.main",
            "action": action,
            "mode": "frontend_backend_error",
        },
        "erreur": msg,
        "preflight": {
            "ok": False,
            "status": "bloque",
            "import_errors": dict(_IMPORT_ERRORS),
        },
        "inconnues": {
            "impossibles": [
                {
                    "nom": "backend.main",
                    "raison": msg,
                }
            ],
            "partielles": [],
        },
        "alertes": {
            "imports": [
                {"nom": k, "detail": v}
                for k, v in _IMPORT_ERRORS.items()
            ]
        },
    }

    if tb:
        report["traceback"] = tb

    return report


# =============================================================================
# Bridge frontend <-> backend
# =============================================================================

class FrontendBackendBridge:
    """
    Objet central utilisable par la GUI.

    Attributs principaux :
    - raw_report : rapport backend brut complet ;
    - ui_report  : données normalisées pour affichage ;
    - state      : état complet frontend/backend.
    """

    def __init__(
        self,
        *,
        options: FrontendMainOptions | Mapping[str, Any] | None = None,
        initial_config: Mapping[str, Any] | None = None,
    ) -> None:
        self.options = _coerce_frontend_options(options)
        self.initial_config: Dict[str, Any] = dict(initial_config or {})
        self.raw_report: Dict[str, Any] = {}
        self.ui_report: Dict[str, Any] = {}
        self.preflight_report: Dict[str, Any] = {}
        self.state: Dict[str, Any] = {}

    def preflight(self) -> Dict[str, Any]:
        if not callable(preflight_backend):
            self.preflight_report = _make_error_report(
                "preflight",
                "backend.main.preflight_backend est indisponible.",
            )["preflight"]
            return self.preflight_report

        try:
            self.preflight_report = preflight_backend(
                check_logs=self.options.run_log_diagnostic,
                log_dir=self.options.log_dir,
                include_traceback=self.options.include_traceback,
            )
        except BaseException as exc:
            self.preflight_report = _make_error_report("preflight", exc)["preflight"]

        return _jsonable(self.preflight_report)

    def run(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        puissance_kw: float | None = None,
        puissance_w: float | None = None,
        action: str = "run",
        output_path: str | os.PathLike[str] | None = None,
    ) -> Dict[str, Any]:
        opts = self.options
        cfg = _prepare_config(
            config if config is not None else self.initial_config,
            puissance_kw=puissance_kw,
            puissance_w=puissance_w,
            opts=opts,
        )

        preflight = self.preflight()

        try:
            if not callable(executer_backend):
                raise RuntimeError("backend.main.executer_backend est indisponible.")

            backend_opts = _make_backend_options(opts)
            raw = executer_backend(
                cfg,
                options=backend_opts,
                output_path=output_path,
                run_preflight=True,
            )

            if not isinstance(raw, Mapping):
                raw = {"resultat": _jsonable(raw)}

            self.raw_report = _jsonable(raw)
            frontend_inputs = _safe_dict(cfg.get("frontend_inputs"))
            if frontend_inputs:
                self.raw_report.setdefault("frontend_inputs", frontend_inputs)

        except BaseException as exc:
            self.raw_report = _make_error_report(action, exc)

        self.raw_report.setdefault("preflight", preflight)
        self.ui_report = build_frontend_ui_report(self.raw_report, preflight=preflight, action=action)
        self.state = self._build_state(action=action)
        return self.state

    def run_100kw(self) -> Dict[str, Any]:
        try:
            if callable(analyser_100kw):
                backend_opts = _make_backend_options(self.options)
                raw = analyser_100kw(options=backend_opts)
                if not isinstance(raw, Mapping):
                    raw = {"resultat": _jsonable(raw)}
                preflight = self.preflight()
                self.raw_report = _jsonable(raw)
                self.raw_report.setdefault("preflight", preflight)
                self.ui_report = build_frontend_ui_report(self.raw_report, preflight=preflight, action="100kw")
                self.state = self._build_state(action="100kw")
                return self.state

            return self.run({"puissance_sortie_kw": 100.0}, action="100kw")

        except BaseException as exc:
            preflight = self.preflight()
            self.raw_report = _make_error_report("100kw", exc)
            self.raw_report.setdefault("preflight", preflight)
            self.ui_report = build_frontend_ui_report(self.raw_report, preflight=preflight, action="100kw")
            self.state = self._build_state(action="100kw")
            return self.state

    def logs(self, *, apply: bool = False) -> Dict[str, Any]:
        preflight = self.preflight()

        try:
            if not callable(analyser_logs_backend):
                raise RuntimeError("backend.main.analyser_logs_backend est indisponible.")

            raw = analyser_logs_backend(
                log_dir=self.options.log_dir,
                apply=apply,
                report_path=self.options.log_report_path,
                include_traceback=self.options.include_traceback,
            )
            self.raw_report = {
                "meta": {"entrypoint": "frontend.main", "action": "logs"},
                "logs": _jsonable(raw),
                "preflight": preflight,
            }

        except BaseException as exc:
            self.raw_report = _make_error_report("logs", exc)
            self.raw_report.setdefault("preflight", preflight)

        self.ui_report = build_frontend_ui_report(self.raw_report, preflight=preflight, action="logs")
        self.state = self._build_state(action="logs")
        return self.state

    def project_action(self, action: str, project_id: str | None = None) -> Dict[str, Any]:
        pid = project_id or self.options.project_id
        preflight = self.preflight()

        if not pid:
            self.raw_report = _make_error_report(
                f"project:{action}",
                "project_id manquant pour une action projet.",
            )
            self.raw_report.setdefault("preflight", preflight)
            self.ui_report = build_frontend_ui_report(self.raw_report, preflight=preflight, action=f"project:{action}")
            self.state = self._build_state(action=f"project:{action}")
            return self.state

        mapping: Dict[str, Callable[..., Any] | None] = {
            "contract": charger_data_contract,
            "resolve": resoudre_inconnues_project,
            "recalculate": recalculer_project,
            "optimize": optimiser_project,
        }

        fn = mapping.get(action)
        if not callable(fn):
            self.raw_report = _make_error_report(
                f"project:{action}",
                f"Action projet indisponible ou inconnue : {action}",
            )
            self.raw_report.setdefault("preflight", preflight)
            self.ui_report = build_frontend_ui_report(self.raw_report, preflight=preflight, action=f"project:{action}")
            self.state = self._build_state(action=f"project:{action}")
            return self.state

        try:
            raw = fn(pid)
            if not isinstance(raw, Mapping):
                raw = {"resultat": _jsonable(raw)}
            self.raw_report = _jsonable(raw)
            self.raw_report.setdefault("preflight", preflight)

        except BaseException as exc:
            self.raw_report = _make_error_report(f"project:{action}", exc)
            self.raw_report.setdefault("preflight", preflight)

        self.ui_report = build_frontend_ui_report(self.raw_report, preflight=preflight, action=f"project:{action}")
        self.state = self._build_state(action=f"project:{action}")
        return self.state

    def save_reports(
        self,
        *,
        output_dir: str | os.PathLike[str] | None = None,
        raw_name: str | None = None,
        ui_name: str | None = None,
    ) -> Dict[str, str]:
        out_dir = Path(output_dir or self.options.output_dir or _REPORTS_DIR).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        raw_path = out_dir / (raw_name or self.options.raw_report_name)
        ui_path = out_dir / (ui_name or self.options.ui_report_name)

        paths = {
            "raw_report": _save_json(self.raw_report, raw_path),
            "ui_report": _save_json(self.ui_report, ui_path),
        }

        if self.state:
            self.state.setdefault("output_paths", {}).update(paths)

        return paths

    def technical_visualization(self) -> Dict[str, Any]:
        """Construit le tableau de visualisation technique depuis le rapport courant."""
        if callable(construire_tableau_pages_visualisation):
            return construire_tableau_pages_visualisation(_safe_dict(self.raw_report))
        return {
            "title": "Visualisation technique",
            "summary": {},
            "components": [],
            "pieces_by_family": {},
            "solidworks": {"step_export": False, "solidworks_ready": False},
            "error": "frontend.ensemble.visualisation_orchestrator indisponible",
        }

    def _build_state(self, *, action: str) -> Dict[str, Any]:
        status = _get_path(self.ui_report, "meta.status", "bloque")
        state = FrontendRunState(
            ok=_ok_from_status(str(status)),
            status=str(status),
            action=action,
            raw_report=self.raw_report,
            ui_report=self.ui_report,
            preflight=self.preflight_report,
            backend_available=_BACKEND_MAIN is not None,
            backend_exports=_backend_exports_status(),
            import_errors=dict(_IMPORT_ERRORS),
        )
        return _jsonable(asdict(state))


# =============================================================================
# API simple pour autres écrans GUI
# =============================================================================

_DEFAULT_BRIDGE: FrontendBackendBridge | None = None


def get_backend_bridge(
    *,
    options: FrontendMainOptions | Mapping[str, Any] | None = None,
    initial_config: Mapping[str, Any] | None = None,
    reset: bool = False,
) -> FrontendBackendBridge:
    global _DEFAULT_BRIDGE

    if reset or _DEFAULT_BRIDGE is None:
        _DEFAULT_BRIDGE = FrontendBackendBridge(options=options, initial_config=initial_config)

    return _DEFAULT_BRIDGE


def refresh_backend_data(
    config: Mapping[str, Any] | None = None,
    *,
    puissance_kw: float | None = None,
    puissance_w: float | None = None,
    options: FrontendMainOptions | Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    bridge = get_backend_bridge(options=options, initial_config=config, reset=options is not None)
    return bridge.run(config, puissance_kw=puissance_kw, puissance_w=puissance_w)


def get_ui_report() -> Dict[str, Any]:
    bridge = get_backend_bridge()
    return bridge.ui_report


def get_raw_report() -> Dict[str, Any]:
    bridge = get_backend_bridge()
    return bridge.raw_report


def get_technical_visualization_report(report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Expose le tableau de visualisation technique depuis frontend/main.py."""
    source = _safe_dict(report) if report is not None else get_raw_report()
    if callable(construire_tableau_pages_visualisation):
        return construire_tableau_pages_visualisation(source)
    return {
        "title": "Visualisation technique",
        "summary": {},
        "components": [],
        "pieces_by_family": {},
        "solidworks": {"step_export": False, "solidworks_ready": False},
        "error": "frontend.ensemble.visualisation_orchestrator indisponible",
    }


def lancer_calcul_puissance_sortie(*, valeur: float, unite: str = "kW") -> Dict[str, Any]:
    """Lance le backend depuis une puissance de sortie moteur electrique explicite."""
    from frontend.ensemble.power_input import build_design_input_payload

    payload = build_design_input_payload(valeur, unite)
    bridge = get_backend_bridge()
    state = bridge.run(payload["backend_config"], action="power_input")
    if isinstance(state, dict):
        state["inputs"] = payload["inputs"]
        state.setdefault("warnings", []).extend(payload.get("warnings", []))
        state.setdefault("errors", []).extend(payload.get("errors", []))
    return state


def charger_rapport_backend(
    *,
    puissance: float | None = None,
    unite: str = "kW",
    scenario: str | None = None,
) -> Dict[str, Any]:
    """
    Charge ou retourne le rapport backend courant.

    Aucun scenario n'est lance implicitement : le scenario 100 kW n'est execute
    que si scenario vaut explicitement "100kw" ou "100_kW".
    """
    bridge = get_backend_bridge()
    if puissance is not None:
        lancer_calcul_puissance_sortie(valeur=puissance, unite=unite)
        return _safe_dict(bridge.raw_report)

    key = str(scenario or "").strip().lower()
    if key in {"100kw", "100_kw", "100-kW".lower()}:
        bridge.run_100kw()
    elif key in {"run", "default", "backend"}:
        bridge.run()
    return _safe_dict(bridge.raw_report)


def charger_frontend_contract(report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    source = _safe_dict(report) if report is not None else charger_rapport_backend()
    try:
        from frontend.ensemble.contract_adapter import get_frontend_contract

        return get_frontend_contract(source)
    except BaseException as exc:
        _record_import_error("frontend.ensemble.contract_adapter", exc)
        return _safe_dict(source.get("frontend_contract")) or _safe_dict(source.get("frontend"))


def charger_diagnostic(report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    source = _safe_dict(report) if report is not None else charger_rapport_backend()
    return _safe_dict(source.get("diagnostic")) or _safe_dict(_get_path(source, "frontend.diagnostic"))


def charger_cao_dossier(report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    source = _safe_dict(report) if report is not None else charger_rapport_backend()
    contract = charger_frontend_contract(source)
    return _safe_dict(contract.get("cao_dossier")) or _safe_dict(source.get("cao_dossier"))


def charger_mechanical_graphs(report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    source = _safe_dict(report) if report is not None else charger_rapport_backend()
    contract = charger_frontend_contract(source)
    return _safe_dict(contract.get("mechanical_graphs")) or _safe_dict(source.get("mechanical_graphs"))


def charger_visualisations(report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    source = _safe_dict(report) if report is not None else charger_rapport_backend()
    try:
        from frontend.ensemble.screen_models import build_visualisation_model

        return build_visualisation_model({"raw_report": source})
    except BaseException as exc:
        _record_import_error("frontend.ensemble.screen_models.visualisations", exc)
        return get_technical_visualization_report(source)


def charger_etat_frontend_complet(
    *,
    puissance: float | None = None,
    unite: str = "kW",
    scenario: str | None = None,
) -> Dict[str, Any]:
    """Retourne l'etat frontend complet consomme par frontend/ensemble et GUI."""
    errors: list[str] = []
    warnings: list[str] = []
    inputs: Dict[str, Any] = {}
    try:
        if puissance is not None:
            state = lancer_calcul_puissance_sortie(valeur=puissance, unite=unite)
            raw_report = _safe_dict(state.get("raw_report"))
            inputs = _safe_dict(state.get("inputs"))
            errors.extend(str(err) for err in (state.get("errors") or []) if err)
            warnings.extend(str(warn) for warn in (state.get("warnings") or []) if warn)
        else:
            raw_report = charger_rapport_backend(scenario=scenario)
    except BaseException as exc:
        raw_report = {}
        errors.append(f"rapport_backend: {type(exc).__name__}: {exc}")

    frontend_contract = charger_frontend_contract(raw_report)
    diagnostic = charger_diagnostic(raw_report)
    cao_dossier = charger_cao_dossier(raw_report)
    mechanical_graphs = charger_mechanical_graphs(raw_report)
    visualisations = charger_visualisations(raw_report)

    if not raw_report:
        warnings.append("Aucun rapport backend courant. Fournir un rapport ou demander un scenario explicite.")

    return {
        "inputs": {
            "puissance_sortie": inputs.get("puissance_sortie"),
            "unite": inputs.get("unite", unite),
            **inputs,
        },
        "raw_report": raw_report,
        "frontend_contract": frontend_contract,
        "diagnostic": diagnostic,
        "cao_dossier": cao_dossier,
        "mechanical_graphs": mechanical_graphs,
        "visualisations": visualisations,
        "errors": errors,
        "warnings": warnings,
    }


# =============================================================================
# GUI Kivy principale
# =============================================================================

def _try_import_kivy() -> Dict[str, Any]:
    try:
        from kivy.app import App
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.screenmanager import Screen, ScreenManager

        return {
            "ok": True,
            "App": App,
            "BoxLayout": BoxLayout,
            "Button": Button,
            "Label": Label,
            "ScrollView": ScrollView,
            "Screen": Screen,
            "ScreenManager": ScreenManager,
        }
    except BaseException as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _make_kivy_app_class(kivy: Mapping[str, Any]) -> Any:
    App = kivy["App"]
    BoxLayout = kivy["BoxLayout"]
    Label = kivy["Label"]
    Screen = kivy["Screen"]
    ScreenManager = kivy["ScreenManager"]

    from frontend.gui.components import COLORS, GhostButton, ModernButton, PremiumCard, SectionTitle

    class STHOMEFrontendApp(App):  # type: ignore[misc, valid-type]
        title = "STHO-ME / SHSE-M"

        def __init__(
            self,
            *,
            bridge: FrontendBackendBridge,
            auto_run: bool = True,
            **kwargs: Any,
        ) -> None:
            super().__init__(**kwargs)
            self.bridge = bridge
            self.auto_run = auto_run

            self.backend_state: Dict[str, Any] = {}
            self.raw_report: Dict[str, Any] = {}
            self.ui_report: Dict[str, Any] = {}

            self.status_label: Any = None
            self.summary_label: Any = None
            self.screen_manager: Any = None

        def build(self) -> Any:
            try:
                from kivy.core.window import Window

                Window.clearcolor = COLORS["BL"]
            except Exception:
                pass

            root = BoxLayout(orientation="vertical", padding=10, spacing=8)
            root.add_widget(self._top_shell_bar())
            self.screen_manager = ScreenManager()
            self._register_screens()
            self.screen_manager.current = "home" if self.screen_manager.has_screen("home") else "dashboard"
            root.add_widget(self.screen_manager)
            return root

        def _top_shell_bar(self) -> Any:
            shell = BoxLayout(orientation="vertical", size_hint_y=None, height=108, spacing=8)
            header = BoxLayout(orientation="horizontal", size_hint_y=None, height=40, spacing=8)

            title = Label(
                text="STHO-ME / SHSE-M",
                color=COLORS["BFW"],
                bold=True,
                font_size="18sp",
                halign="left",
                valign="middle",
            )
            title.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
            header.add_widget(title)

            self.status_label = Label(
                text="Prêt",
                color=COLORS["MUTED"],
                font_size="12sp",
                halign="right",
                valign="middle",
                size_hint_x=0.45,
            )
            self.status_label.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
            header.add_widget(self.status_label)
            shell.add_widget(header)

            nav = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=8)
            for label, target in (
                ("Accueil", "home"),
                ("Dashboard", "dashboard"),
                ("Paramètres", "edit_parameters"),
                ("Diagnostic", "json_diagnostic"),
                ("Visualisation", "technical_visualization"),
                ("CAO", "cao_dossier"),
                ("JSON", "raw_json"),
            ):
                btn = GhostButton(text=label.upper(), font_size="10sp")
                btn.bind(on_release=lambda _btn, screen=target: self.go(screen))
                nav.add_widget(btn)

            run_btn = ModernButton(text="RECALCULER", size_hint_x=None, width=150, font_size="10sp")
            run_btn.bind(on_release=lambda *_: self.refresh_backend())
            nav.add_widget(run_btn)

            scenario_btn = ModernButton(text="100 kW", size_hint_x=None, width=100, font_size="10sp")
            scenario_btn.bind(on_release=lambda *_: self.run_100kw())
            nav.add_widget(scenario_btn)

            shell.add_widget(nav)
            return shell

        def _register_screens(self) -> None:
            assert self.screen_manager is not None
            specs = [
                ("home", "frontend.gui.home", "HomeScreen"),
                ("loading", "frontend.gui.loading", "LoadingScreen"),
                ("dashboard", "frontend.gui.dashboard", "DashboardScreen"),
                ("edit_parameters", "frontend.gui.edit_parameters", "EditParametersScreen"),
                ("architecture_choice", "frontend.gui.architecture_choice", "ArchitectureChoiceScreen"),
                ("missing_requirements", "frontend.gui.missing_requirements", "MissingRequirementsScreen"),
                ("json_diagnostic", "frontend.gui.json_diagnostic_view", "JsonDiagnosticScreen"),
                ("technical_visualization", "frontend.gui.technical_visualization", "TechnicalVisualizationScreen"),
                ("cao_dossier", "frontend.gui.cao_dossier_view", "CaoDossierScreen"),
                ("raw_json", "frontend.gui.raw_report_view", "RawJsonScreen"),
                ("energy_audit", "frontend.gui.energy_audit", "EnergyAuditScreen"),
                ("system_data", "frontend.gui.system_data", "SystemDataScreen"),
                ("pieces", "frontend.gui.pieces_view", "PieceLibraryScreen"),
                ("resources", "frontend.gui.resource_views", "ResourceListScreen"),
                ("exports", "frontend.gui.exports_view", "ExportsScreen"),
                ("error", "frontend.gui.error_view", "ErrorScreen"),
            ]
            for name, module_name, class_name in specs:
                try:
                    module = importlib.import_module(module_name)
                    screen_cls = getattr(module, class_name)
                    self.screen_manager.add_widget(screen_cls(name=name))
                except Exception as exc:
                    self.screen_manager.add_widget(self._fallback_screen(name, f"{module_name}.{class_name}", exc))

        def _fallback_screen(self, name: str, source: str, exc: BaseException) -> Any:
            screen = Screen(name=name)
            card = PremiumCard(title=f"{name} indisponible", padding=22, spacing=12)
            card.add_widget(SectionTitle(text=str(source)))
            label = Label(
                text=f"{type(exc).__name__}: {exc}",
                color=COLORS["RS"],
                halign="left",
                valign="top",
            )
            label.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
            card.add_widget(label)
            screen.add_widget(card)
            return screen

        def go(self, screen_name: str) -> None:
            if self.screen_manager is not None and self.screen_manager.has_screen(screen_name):
                self.screen_manager.current = screen_name
                return
            if self.status_label is not None:
                self.status_label.text = f"Page indisponible : {screen_name}"

        def on_start(self) -> None:
            if self.auto_run:
                self.refresh_backend()

        def _sync_from_bridge(self, state: Mapping[str, Any]) -> None:
            self.backend_state = _jsonable(state)
            self.raw_report = _safe_dict(self.bridge.raw_report)
            self.ui_report = _safe_dict(self.bridge.ui_report)
            self.backend_report = self.raw_report
            self.raw_backend_report = self.raw_report
            self.full_report = self.raw_report

            status = _get_path(self.ui_report, "meta.status", "inconnu")
            action = _get_path(self.ui_report, "meta.action", "run")
            if self.status_label is not None:
                self.status_label.text = f"Action : {action} | Statut : {status}"

            if self.summary_label is not None:
                self.summary_label.text = self._make_summary_text()

        def refresh_backend(self) -> None:
            state = self.bridge.run()
            self._sync_from_bridge(state)

        def run_100kw(self) -> None:
            state = self.bridge.run_100kw()
            self._sync_from_bridge(state)

        def run_logs(self) -> None:
            state = self.bridge.logs(apply=False)
            self._sync_from_bridge(state)

        def save_reports(self) -> None:
            paths = self.bridge.save_reports()
            self.backend_state.setdefault("output_paths", {}).update(paths)
            if self.status_label is not None:
                self.status_label.text = f"Rapports sauvegardés : {paths.get('ui_report')}"

        def _make_summary_text(self) -> str:
            ui = _safe_dict(self.ui_report)
            cards = list(ui.get("summary_cards") or [])
            kpis = list(ui.get("kpis") or [])
            inconnues = _safe_dict(ui.get("inconnues"))
            raw_sections = list(ui.get("raw_sections") or [])

            lines: list[str] = []

            lines.append("SYNTHÈSE")
            lines.append("-" * 80)
            for card in cards:
                if isinstance(card, Mapping):
                    lines.append(f"{card.get('title')}: {card.get('value')} [{card.get('status')}]")

            lines.append("")
            lines.append("KPI CALCULÉS")
            lines.append("-" * 80)
            if kpis:
                for kpi in kpis:
                    if not isinstance(kpi, Mapping):
                        continue
                    unit = str(kpi.get("unit") or "")
                    display = kpi.get("display")
                    lines.append(f"{kpi.get('label')}: {display} {unit}  ({kpi.get('source_path')})")
            else:
                lines.append("Aucun KPI calculé disponible.")

            lines.append("")
            lines.append("INCONNUES IMPOSSIBLES")
            lines.append("-" * 80)
            impossibles = list(inconnues.get("impossibles") or [])
            if impossibles:
                for item in impossibles[:30]:
                    if isinstance(item, Mapping):
                        lines.append(f"- {item.get('nom')}: {item.get('raison')}")
            else:
                lines.append("Aucune.")

            lines.append("")
            lines.append("INCONNUES PARTIELLES")
            lines.append("-" * 80)
            partielles = list(inconnues.get("partielles") or [])
            if partielles:
                for item in partielles[:30]:
                    if isinstance(item, Mapping):
                        lines.append(f"- {item.get('nom')}: {item.get('raison')}")
            else:
                lines.append("Aucune.")

            lines.append("")
            lines.append("SECTIONS BACKEND DISPONIBLES")
            lines.append("-" * 80)
            for section in raw_sections:
                if isinstance(section, Mapping):
                    lines.append(
                        f"- {section.get('title')} | key={section.get('key')} | "
                        f"type={section.get('type')} | count={section.get('count')}"
                    )

            return "\n".join(lines)

    return STHOMEFrontendApp


# =============================================================================
# CLI
# =============================================================================

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Frontend STHO-ME / SHSE-M")

    parser.add_argument("--config", default=None, help="Chemin JSON de configuration frontend/backend")
    parser.add_argument("--project-id", default=None)

    parser.add_argument("--puissance-kw", type=float, default=None, help="Puissance utile de sortie en kW")
    parser.add_argument("--puissance-w", type=float, default=None, help="Puissance utile de sortie en W")
    parser.add_argument("--no-default-power", action="store_true", help="Ne pas injecter le scénario GUI 100 kW par défaut")

    parser.add_argument("--action", choices=("run", "100kw", "preflight", "logs", "contract", "resolve", "recalculate", "optimize"), default="run")

    parser.add_argument("--non-strict", action="store_true")
    parser.add_argument("--no-resolve", action="store_true")
    parser.add_argument("--no-optimize", action="store_true")
    parser.add_argument("--no-validation", action="store_true")
    parser.add_argument("--no-diagnostic", action="store_true")
    parser.add_argument("--no-graphs", action="store_true")
    parser.add_argument("--no-cao", action="store_true")
    parser.add_argument("--no-frontend-contract", action="store_true")

    parser.add_argument("--logs", action="store_true", help="Inclure diagnostic logs")
    parser.add_argument("--clean-logs", action="store_true", help="Appliquer nettoyage logs")
    parser.add_argument("--log-dir", default=None)
    parser.add_argument("--log-report", default=None)

    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--output-raw", default=None)
    parser.add_argument("--output-ui", default=None)

    parser.add_argument("--no-gui", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    parser.add_argument("--include-traceback", action="store_true")

    return parser


def _options_from_args(args: argparse.Namespace) -> FrontendMainOptions:
    return FrontendMainOptions(
        project_id=args.project_id,
        default_power_kw=None if args.no_default_power else 100.0,
        strict=not bool(args.non_strict),
        resolve_unknowns=not bool(args.no_resolve),
        optimize=not bool(args.no_optimize),
        validate_chain=not bool(args.no_validation),
        diagnostic=not bool(args.no_diagnostic),
        mechanical_graphs=not bool(args.no_graphs),
        cao_dossier=not bool(args.no_cao),
        frontend_contract=not bool(args.no_frontend_contract),
        include_traceback=bool(args.include_traceback),
        run_log_diagnostic=bool(args.logs),
        clean_logs=bool(args.clean_logs),
        log_dir=args.log_dir,
        log_report_path=args.log_report,
        output_dir=args.output_dir,
    )


def _load_config_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    if not args.config:
        return {}
    return _load_json(args.config)


def _execute_action(
    bridge: FrontendBackendBridge,
    *,
    action: str,
    config: Mapping[str, Any],
    puissance_kw: float | None,
    puissance_w: float | None,
) -> Dict[str, Any]:
    if action == "preflight":
        pf = bridge.preflight()
        bridge.raw_report = {
            "meta": {"entrypoint": "frontend.main", "action": "preflight"},
            "preflight": pf,
        }
        bridge.ui_report = build_frontend_ui_report(bridge.raw_report, preflight=pf, action="preflight")
        bridge.state = bridge._build_state(action="preflight")
        return bridge.state

    if action == "logs":
        return bridge.logs(apply=bridge.options.clean_logs)

    if action == "100kw":
        return bridge.run_100kw()

    if action in ("contract", "resolve", "recalculate", "optimize"):
        return bridge.project_action(action)

    return bridge.run(
        config,
        puissance_kw=puissance_kw,
        puissance_w=puissance_w,
        action="run",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    opts = _options_from_args(args)

    try:
        config = _load_config_from_args(args)
    except BaseException as exc:
        err = _make_error_report("load_config", exc)
        print(json.dumps(_jsonable(err), ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    bridge = get_backend_bridge(options=opts, initial_config=config, reset=True)

    # Mode CLI pur
    if args.no_gui or args.print_json:
        state = _execute_action(
            bridge,
            action=args.action,
            config=config,
            puissance_kw=args.puissance_kw,
            puissance_w=args.puissance_w,
        )

        output_paths: Dict[str, str] = {}
        if args.output_dir or args.output_raw or args.output_ui:
            output_paths = bridge.save_reports(
                output_dir=args.output_dir,
                raw_name=args.output_raw,
                ui_name=args.output_ui,
            )
            state.setdefault("output_paths", {}).update(output_paths)

        print(json.dumps(_jsonable(state), ensure_ascii=False, indent=2))
        return 0 if state.get("ok") else 2

    # Mode GUI Kivy si disponible
    kivy = _try_import_kivy()
    if not kivy.get("ok"):
        state = _execute_action(
            bridge,
            action=args.action,
            config=config,
            puissance_kw=args.puissance_kw,
            puissance_w=args.puissance_w,
        )
        state.setdefault("gui", {})["kivy"] = kivy
        print(json.dumps(_jsonable(state), ensure_ascii=False, indent=2))
        return 0 if state.get("ok") else 2

    AppClass = _make_kivy_app_class(kivy)
    app = AppClass(bridge=bridge, auto_run=True)
    app.run()
    return 0


__all__ = [
    "PROJECT_NAME",
    "FrontendMainOptions",
    "FrontendRunState",
    "FrontendBackendBridge",
    "build_frontend_ui_report",
    "charger_cao_dossier",
    "charger_diagnostic",
    "charger_etat_frontend_complet",
    "charger_frontend_contract",
    "charger_mechanical_graphs",
    "charger_rapport_backend",
    "charger_visualisations",
    "get_backend_bridge",
    "get_technical_visualization_report",
    "lancer_calcul_puissance_sortie",
    "refresh_backend_data",
    "get_ui_report",
    "get_raw_report",
    "_fuel_summary",
    "_missing_requirements",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
