# backend/main.py
from __future__ import annotations

"""
backend/main.py
===============================================================================
Point d'entrée racine du backend STHO-ME / SHSE-M
===============================================================================

Rôle
----
Ce fichier est la façade principale du backend. Il ne remplace pas les
calculateurs spécialisés et ne duplique pas l'orchestrateur système.

Il délègue à :
- backend.modules.main.main_systeme : orchestration technique complète ;
- backend.modules.main.logs         : diagnostic et nettoyage des logs ;
- backend.modules.systeme.database  : sauvegarde chiffrée si demandée ;
- backend.modules.systeme.data_repository : repository projet si demandé.

Contrat
-------
- Une puissance utilisateur, par exemple 100 kW, est traitée comme puissance
  utile de sortie.
- Les sous-systèmes sont dimensionnés / vérifiés par main_systeme.py.
- Les données manquantes sont remontées dans inconnues, jamais inventées.
- Les anciennes fonctions appelées par la GUI ou les scripts restent disponibles.
- Le fichier reste importable même si certains modules spécialisés sont absents.
"""

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence
import argparse
import copy
import importlib
import json
import math
import os
import sys
import traceback


# =============================================================================
# Chemins / imports robustes
# =============================================================================

_THIS_FILE = Path(__file__).resolve() if "__file__" in globals() else Path.cwd() / "main.py"
_BACKEND_ROOT = _THIS_FILE.parent if _THIS_FILE.name == "main.py" else Path.cwd()
_PROJECT_ROOT = _BACKEND_ROOT.parent if _BACKEND_ROOT.name == "backend" else _BACKEND_ROOT

for _candidate in (
    _BACKEND_ROOT,
    _PROJECT_ROOT,
    _BACKEND_ROOT / "modules",
    _BACKEND_ROOT / "modules" / "main",
    _BACKEND_ROOT / "modules" / "systeme",
    _BACKEND_ROOT / "ensemble",
    Path.cwd(),
    Path("/mnt/data"),  # sandbox only; harmless in the real project
):
    try:
        _p = str(_candidate.resolve())
    except Exception:
        _p = str(_candidate)
    if _p not in sys.path:
        sys.path.insert(0, _p)

_IMPORT_ERRORS: Dict[str, str] = {}


def _import_module_optional(module_names: Sequence[str]) -> Any | None:
    last_error: BaseException | None = None
    for module_name in module_names:
        try:
            return importlib.import_module(module_name)
        except BaseException as exc:
            last_error = exc
    _IMPORT_ERRORS["module:" + "|".join(module_names)] = (
        f"{type(last_error).__name__}: {last_error}" if last_error else "module absent"
    )
    return None


def _import_attr_optional(module_names: Sequence[str], attr: str, default: Any = None) -> Any:
    last_error: BaseException | None = None
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            return getattr(module, attr)
        except BaseException as exc:
            last_error = exc
    _IMPORT_ERRORS[f"{attr}@{'|'.join(module_names)}"] = (
        f"{type(last_error).__name__}: {last_error}" if last_error else "attribut absent"
    )
    return default


# Orchestrateur principal des modules système.
_main_systeme_mod = _import_module_optional(
    (
        "backend.modules.main.main_systeme",
        "modules.main.main_systeme",
        "main_systeme",
    )
)

MainSysteme = _import_attr_optional(
    ("backend.modules.main.main_systeme", "modules.main.main_systeme", "main_systeme"),
    "MainSysteme",
)
MainSystemeOptions = _import_attr_optional(
    ("backend.modules.main.main_systeme", "modules.main.main_systeme", "main_systeme"),
    "MainSystemeOptions",
)
analyser_systeme_sthome = _import_attr_optional(
    ("backend.modules.main.main_systeme", "modules.main.main_systeme", "main_systeme"),
    "analyser_systeme_sthome",
)
analyser_depuis_puissance_main = _import_attr_optional(
    ("backend.modules.main.main_systeme", "modules.main.main_systeme", "main_systeme"),
    "analyser_depuis_puissance",
)
analyser_100kw_main = _import_attr_optional(
    ("backend.modules.main.main_systeme", "modules.main.main_systeme", "main_systeme"),
    "analyser_100kw",
)
charger_data_contract_main = _import_attr_optional(
    ("backend.modules.main.main_systeme", "modules.main.main_systeme", "main_systeme"),
    "charger_data_contract",
)
resoudre_inconnues_project_main = _import_attr_optional(
    ("backend.modules.main.main_systeme", "modules.main.main_systeme", "main_systeme"),
    "resoudre_inconnues_project",
)
recalculer_project_main = _import_attr_optional(
    ("backend.modules.main.main_systeme", "modules.main.main_systeme", "main_systeme"),
    "recalculer_project",
)
optimiser_project_main = _import_attr_optional(
    ("backend.modules.main.main_systeme", "modules.main.main_systeme", "main_systeme"),
    "optimiser_project",
)

# Diagnostic logs.
_logs_mod = _import_module_optional(
    (
        "backend.modules.main.logs",
        "modules.main.logs",
        "logs",
    )
)
analyser_logs = _import_attr_optional(
    ("backend.modules.main.logs", "modules.main.logs", "logs"),
    "analyser_logs",
)
analyser_et_nettoyer_logs = _import_attr_optional(
    ("backend.modules.main.logs", "modules.main.logs", "logs"),
    "analyser_et_nettoyer_logs",
)
exporter_rapport_logs_json = _import_attr_optional(
    ("backend.modules.main.logs", "modules.main.logs", "logs"),
    "exporter_rapport_json",
)

# Stockage, optionnel.
SystemDataRepository = _import_attr_optional(
    (
        "backend.modules.systeme.data_repository",
        "modules.systeme.data_repository",
        "data_repository",
    ),
    "SystemDataRepository",
)
SecureDatabase = _import_attr_optional(
    (
        "backend.modules.systeme.database",
        "modules.systeme.database",
        "database",
    ),
    "SecureDatabase",
)


# =============================================================================
# Options publiques
# =============================================================================

@dataclass
class BackendMainOptions:
    project_id: str | None = None
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

    # Options racine backend/main.py
    run_log_diagnostic: bool = False
    clean_logs: bool = False
    log_dir: str | None = None
    log_report_path: str | None = None


@dataclass
class BackendRunResult:
    ok: bool
    rapport: Dict[str, Any]
    preflight: Dict[str, Any] = field(default_factory=dict)
    logs: Dict[str, Any] | None = None
    output_path: str | None = None


# =============================================================================
# Helpers JSON / chemins
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


def _jsonable(value: Any, *, depth: int = 0, max_depth: int = 12) -> Any:
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
        return {str(k): _jsonable(v, depth=depth + 1, max_depth=max_depth) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v, depth=depth + 1, max_depth=max_depth) for v in value]
    if hasattr(value, "en_dict") and callable(getattr(value, "en_dict")):
        try:
            return _jsonable(value.en_dict(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "as_dict") and callable(getattr(value, "as_dict")):
        try:
            return _jsonable(value.as_dict(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        try:
            return _jsonable(value.to_dict(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            public = {
                str(k): v
                for k, v in vars(value).items()
                if not str(k).startswith("_") and not callable(v)
            }
            return {"type": type(value).__name__, "attributs": _jsonable(public, depth=depth + 1, max_depth=max_depth)}
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


def charger_json(path: str | os.PathLike[str]) -> Dict[str, Any]:
    p = Path(path).expanduser().resolve()
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Le fichier JSON doit contenir un objet racine.")
    return data


def sauvegarder_json(data: Mapping[str, Any], path: str | os.PathLike[str], *, indent: int = 2) -> str:
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_jsonable(data), ensure_ascii=False, indent=indent), encoding="utf-8")
    return str(p)


def _coerce_options(options: BackendMainOptions | Mapping[str, Any] | None, **overrides: Any) -> BackendMainOptions:
    if isinstance(options, BackendMainOptions):
        data = asdict(options)
    elif isinstance(options, Mapping):
        data = {k: v for k, v in options.items() if k in BackendMainOptions.__dataclass_fields__}
    else:
        data = {}
    for key, value in overrides.items():
        if key in BackendMainOptions.__dataclass_fields__ and value is not None:
            data[key] = value
    return BackendMainOptions(**data)


def _to_main_systeme_options(opts: BackendMainOptions) -> Any:
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
    }
    if MainSystemeOptions is not None:
        try:
            return MainSystemeOptions(**data)
        except Exception:
            pass
    return data


def _extract_power_config(
    puissance_kw: float | None = None,
    puissance_w: float | None = None,
    *,
    donnees_connues: Mapping[str, Any] | None = None,
    cahier_des_charges: Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    if puissance_w is not None:
        cfg["puissance_sortie_w"] = float(puissance_w)
    elif puissance_kw is not None:
        cfg["puissance_sortie_kw"] = float(puissance_kw)
    if donnees_connues:
        cfg["donnees_connues"] = dict(donnees_connues)
    if cahier_des_charges:
        cfg["cahier_des_charges"] = dict(cahier_des_charges)
    if extra:
        cfg = _deep_merge(cfg, extra)
    return cfg


# =============================================================================
# Préflight backend
# =============================================================================

def preflight_backend(
    *,
    check_logs: bool = False,
    log_dir: str | os.PathLike[str] | None = None,
    include_traceback: bool = False,
) -> Dict[str, Any]:
    """Vérifie l'état minimal du backend sans lancer de dimensionnement lourd."""
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str | None = None, blocking: bool = False) -> None:
        checks.append({"name": name, "ok": bool(ok), "blocking": bool(blocking), "detail": detail})

    add("backend_root", _BACKEND_ROOT.exists(), str(_BACKEND_ROOT), blocking=False)
    add("main_systeme_module", _main_systeme_mod is not None, _IMPORT_ERRORS.get("module:backend.modules.main.main_systeme|modules.main.main_systeme|main_systeme"), blocking=True)
    add("MainSysteme", MainSysteme is not None, _IMPORT_ERRORS.get("MainSysteme@backend.modules.main.main_systeme|modules.main.main_systeme|main_systeme"), blocking=True)
    add("analyser_systeme_sthome", callable(analyser_systeme_sthome), _IMPORT_ERRORS.get("analyser_systeme_sthome@backend.modules.main.main_systeme|modules.main.main_systeme|main_systeme"), blocking=True)
    add("logs_module", _logs_mod is not None, _IMPORT_ERRORS.get("module:backend.modules.main.logs|modules.main.logs|logs"), blocking=False)
    add("SystemDataRepository", SystemDataRepository is not None, _IMPORT_ERRORS.get("SystemDataRepository@backend.modules.systeme.data_repository|modules.systeme.data_repository|data_repository"), blocking=False)
    add("SecureDatabase", SecureDatabase is not None, _IMPORT_ERRORS.get("SecureDatabase@backend.modules.systeme.database|modules.systeme.database|database"), blocking=False)

    logs_report = None
    if check_logs and callable(analyser_logs):
        try:
            logs_report = analyser_logs(log_dir or (_BACKEND_ROOT / "logs"), cleanup_apply=False, max_lines_per_file=5000)
            add("logs_diagnostic", True, "diagnostic logs exécuté", blocking=False)
        except Exception as exc:
            add("logs_diagnostic", False, f"{type(exc).__name__}: {exc}", blocking=False)
            if include_traceback:
                logs_report = {"traceback": traceback.format_exc()}

    blocking_failed = [c for c in checks if c.get("blocking") and not c.get("ok")]
    status = "ok" if not blocking_failed else "bloque"
    return {
        "status": status,
        "ok": not blocking_failed,
        "checks": checks,
        "import_errors": dict(_IMPORT_ERRORS),
        "logs": logs_report,
    }


# =============================================================================
# Orchestration principale
# =============================================================================

def executer_backend(
    config: Mapping[str, Any] | None = None,
    *,
    options: BackendMainOptions | Mapping[str, Any] | None = None,
    repository: Any | None = None,
    database: Any | None = None,
    output_path: str | os.PathLike[str] | None = None,
    run_preflight: bool = True,
    **overrides: Any,
) -> Dict[str, Any]:
    """Point d'entrée racine : préflight optionnel, puis délégation à main_systeme.py."""
    opts = _coerce_options(options, **overrides)
    cfg = dict(config or {})
    preflight = preflight_backend(check_logs=False, include_traceback=opts.include_traceback) if run_preflight else {"ok": True, "status": "skipped"}

    if not preflight.get("ok") and analyser_systeme_sthome is None:
        rapport = {
            "meta": {"module": "backend.main", "mode": "preflight_failed"},
            "preflight": preflight,
            "inconnues": {
                "impossibles": [
                    {
                        "nom": "backend.modules.main.main_systeme",
                        "raison": "main_systeme.py est requis pour dimensionner le système.",
                    }
                ],
                "partielles": [],
            },
            "alertes": {"imports": [{"nom": k, "detail": v} for k, v in _IMPORT_ERRORS.items()]},
        }
    else:
        main_opts = _to_main_systeme_options(opts)
        if callable(analyser_systeme_sthome):
            rapport = analyser_systeme_sthome(
                cfg,
                options=main_opts,
                repository=repository,
                database=database,
            )
        elif MainSysteme is not None and hasattr(MainSysteme, "depuis_config"):
            systeme = MainSysteme.depuis_config(cfg, options=main_opts, repository=repository, database=database)
            rapport = systeme.analyser()
        else:
            raise RuntimeError("Aucun orchestrateur main_systeme exploitable n'est disponible.")

    if not isinstance(rapport, Mapping):
        rapport = {"resultat": _jsonable(rapport)}

    final = dict(rapport)
    final.setdefault("meta", {})
    if isinstance(final["meta"], dict):
        final["meta"].setdefault("entrypoint", "backend.main")
    final["preflight"] = preflight

    if opts.run_log_diagnostic or opts.clean_logs:
        final["logs"] = analyser_logs_backend(
            log_dir=opts.log_dir,
            apply=opts.clean_logs,
            report_path=opts.log_report_path,
            include_traceback=opts.include_traceback,
        )

    if output_path:
        final["output_path"] = sauvegarder_json(final, output_path)

    return _jsonable(final)


def analyser_depuis_puissance(
    puissance: float,
    unite: str = "kw",
    *,
    donnees_connues: Mapping[str, Any] | None = None,
    cahier_des_charges: Mapping[str, Any] | None = None,
    espace_recherche: Mapping[str, Any] | None = None,
    contraintes: Mapping[str, Any] | None = None,
    options: BackendMainOptions | Mapping[str, Any] | None = None,
    **overrides: Any,
) -> Dict[str, Any]:
    """Raccourci racine depuis une puissance utile de sortie."""
    if callable(analyser_depuis_puissance_main):
        main_opts = _to_main_systeme_options(_coerce_options(options, **overrides))
        return analyser_depuis_puissance_main(
            puissance,
            unite,
            donnees_connues=donnees_connues,
            cahier_des_charges=cahier_des_charges,
            espace_recherche=espace_recherche,
            contraintes=contraintes,
            options=main_opts,
        )
    cfg = _extract_power_config(
        puissance_kw=float(puissance) if str(unite).lower() == "kw" else None,
        puissance_w=float(puissance) if str(unite).lower() == "w" else None,
        donnees_connues=donnees_connues,
        cahier_des_charges=cahier_des_charges,
        extra={"espace_recherche": dict(espace_recherche or {}), "contraintes": dict(contraintes or {})},
    )
    return executer_backend(cfg, options=options, **overrides)


def analyser_100kw(
    *,
    donnees_connues: Mapping[str, Any] | None = None,
    cahier_des_charges: Mapping[str, Any] | None = None,
    espace_recherche: Mapping[str, Any] | None = None,
    contraintes: Mapping[str, Any] | None = None,
    options: BackendMainOptions | Mapping[str, Any] | None = None,
    **overrides: Any,
) -> Dict[str, Any]:
    """Scénario de référence : 100 kW utiles en sortie moteur électrique."""
    if callable(analyser_100kw_main):
        main_opts = _to_main_systeme_options(_coerce_options(options, **overrides))
        return analyser_100kw_main(
            donnees_connues=donnees_connues,
            cahier_des_charges=cahier_des_charges,
            espace_recherche=espace_recherche,
            contraintes=contraintes,
            options=main_opts,
        )
    return analyser_depuis_puissance(
        100.0,
        "kw",
        donnees_connues=donnees_connues,
        cahier_des_charges=cahier_des_charges,
        espace_recherche=espace_recherche,
        contraintes=contraintes,
        options=options,
        **overrides,
    )


def dimensionner_systeme_shsem(
    config: Mapping[str, Any] | None = None,
    *,
    puissance_sortie_kw: float | None = None,
    puissance_sortie_w: float | None = None,
    donnees_connues: Mapping[str, Any] | None = None,
    cahier_des_charges: Mapping[str, Any] | None = None,
    options: BackendMainOptions | Mapping[str, Any] | None = None,
    output_path: str | os.PathLike[str] | None = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Compatibilité historique attendue par les scripts et la base.

    `puissance_sortie_kw` ou `puissance_sortie_w` reste une puissance utile de
    sortie. Les rendements et grandeurs amont sont gérés par main_systeme.py.
    """
    cfg = dict(config or {})
    power_cfg = _extract_power_config(
        puissance_kw=puissance_sortie_kw,
        puissance_w=puissance_sortie_w,
        donnees_connues=donnees_connues,
        cahier_des_charges=cahier_des_charges,
        extra=kwargs,
    )
    cfg = _deep_merge(power_cfg, cfg)
    return executer_backend(cfg, options=options, output_path=output_path)


# Alias usuels du projet.
dimensionner_systeme_shse_m = dimensionner_systeme_shsem
dimensionner_systeme_sthome = dimensionner_systeme_shsem
calculer_systeme_sthome = dimensionner_systeme_shsem
calculer_systeme_shsem = dimensionner_systeme_shsem
run_backend = executer_backend


# =============================================================================
# Services projet / GUI
# =============================================================================

def charger_data_contract(project_id: str, repository: Any | None = None) -> Dict[str, Any]:
    if callable(charger_data_contract_main):
        return charger_data_contract_main(project_id, repository=repository)
    return executer_backend({"project_id": project_id}, options={"project_id": project_id, "frontend_contract": True}, repository=repository)


def resoudre_inconnues_project(project_id: str, repository: Any | None = None) -> Dict[str, Any]:
    if callable(resoudre_inconnues_project_main):
        return resoudre_inconnues_project_main(project_id, repository=repository)
    return executer_backend({"project_id": project_id}, options={"project_id": project_id, "resolve_unknowns": True}, repository=repository)


def recalculer_project(project_id: str, repository: Any | None = None) -> Dict[str, Any]:
    if callable(recalculer_project_main):
        return recalculer_project_main(project_id, repository=repository)
    return executer_backend({"project_id": project_id}, options={"project_id": project_id}, repository=repository)


def optimiser_project(project_id: str, repository: Any | None = None) -> Dict[str, Any]:
    if callable(optimiser_project_main):
        return optimiser_project_main(project_id, repository=repository)
    return executer_backend({"project_id": project_id}, options={"project_id": project_id, "optimize": True}, repository=repository)


# =============================================================================
# Logs
# =============================================================================

def analyser_logs_backend(
    *,
    log_dir: str | os.PathLike[str] | None = None,
    apply: bool = False,
    report_path: str | os.PathLike[str] | None = None,
    include_traceback: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Analyse/nettoie les logs en appelant backend.modules.main.logs."""
    if callable(analyser_et_nettoyer_logs) and apply:
        try:
            return analyser_et_nettoyer_logs(
                log_dir or (_BACKEND_ROOT / "logs"),
                apply=True,
                report_path=report_path,
                **kwargs,
            )
        except TypeError:
            return analyser_et_nettoyer_logs(log_dir or (_BACKEND_ROOT / "logs"), apply=True)
    if callable(analyser_logs):
        try:
            report = analyser_logs(
                log_dir or (_BACKEND_ROOT / "logs"),
                cleanup_apply=bool(apply),
                **kwargs,
            )
        except TypeError:
            report = analyser_logs(log_dir or (_BACKEND_ROOT / "logs"))
        if report_path and callable(exporter_rapport_logs_json):
            try:
                exporter_rapport_logs_json(report, report_path)
            except Exception:
                if include_traceback:
                    report.setdefault("debug", {})["export_logs_traceback"] = traceback.format_exc()
        return _jsonable(report)
    return {
        "meta": {"module": "backend.main", "mode": "logs_unavailable"},
        "inconnues": {
            "impossibles": [
                {
                    "nom": "backend.modules.main.logs",
                    "raison": "Module logs.py non importable.",
                }
            ],
            "partielles": [],
        },
        "import_errors": dict(_IMPORT_ERRORS),
    }


# =============================================================================
# CLI
# =============================================================================

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Point d'entrée backend STHO-ME / SHSE-M")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Lance le pipeline système complet")
    _add_common_run_args(run)

    p100 = sub.add_parser("100kw", help="Lance le scénario de référence 100 kW")
    _add_common_run_args(p100)

    pf = sub.add_parser("preflight", help="Vérifie les imports et chemins backend")
    pf.add_argument("--logs", action="store_true", help="Inclure un diagnostic léger des logs")
    pf.add_argument("--log-dir", default=None)
    pf.add_argument("--output", default=None)
    pf.add_argument("--print-json", action="store_true")

    logs = sub.add_parser("logs", help="Analyse/nettoie backend/logs")
    logs.add_argument("--log-dir", default=None)
    logs.add_argument("--apply", action="store_true", help="Appliquer réellement le nettoyage")
    logs.add_argument("--report", default=None)
    logs.add_argument("--output", default=None)
    logs.add_argument("--print-json", action="store_true")

    project = sub.add_parser("project", help="Actions projet repository/frontend")
    project.add_argument("action", choices=("contract", "resolve", "recalculate", "optimize"))
    project.add_argument("--project-id", required=True)
    project.add_argument("--output", default=None)
    project.add_argument("--print-json", action="store_true")

    # Compatibilité : sans sous-commande, on accepte les options de run.
    _add_common_run_args(parser)
    return parser


def _add_common_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=None, help="Chemin JSON de configuration")
    parser.add_argument("--puissance-kw", type=float, default=None, help="Puissance utile de sortie en kW")
    parser.add_argument("--puissance-w", type=float, default=None, help="Puissance utile de sortie en W")
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--output", default=None, help="Chemin JSON de sortie")
    parser.add_argument("--non-strict", action="store_true")
    parser.add_argument("--no-resolve", action="store_true")
    parser.add_argument("--no-optimize", action="store_true")
    parser.add_argument("--no-validation", action="store_true")
    parser.add_argument("--no-diagnostic", action="store_true")
    parser.add_argument("--no-graphs", action="store_true")
    parser.add_argument("--no-cao", action="store_true")
    parser.add_argument("--no-frontend", action="store_true")
    parser.add_argument("--save-db", action="store_true")
    parser.add_argument("--save-repository", action="store_true")
    parser.add_argument("--logs", action="store_true", help="Inclure diagnostic logs")
    parser.add_argument("--clean-logs", action="store_true", help="Nettoyer les logs obsolètes")
    parser.add_argument("--log-dir", default=None)
    parser.add_argument("--print-json", action="store_true")


def _load_config_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    config = charger_json(args.config) if getattr(args, "config", None) else {}
    if getattr(args, "puissance_w", None) is not None:
        config["puissance_sortie_w"] = float(args.puissance_w)
    elif getattr(args, "puissance_kw", None) is not None:
        config["puissance_sortie_kw"] = float(args.puissance_kw)
    return config


def _options_from_args(args: argparse.Namespace) -> BackendMainOptions:
    return BackendMainOptions(
        project_id=getattr(args, "project_id", None),
        strict=not bool(getattr(args, "non_strict", False)),
        resolve_unknowns=not bool(getattr(args, "no_resolve", False)),
        optimize=not bool(getattr(args, "no_optimize", False)),
        validate_chain=not bool(getattr(args, "no_validation", False)),
        diagnostic=not bool(getattr(args, "no_diagnostic", False)),
        mechanical_graphs=not bool(getattr(args, "no_graphs", False)),
        cao_dossier=not bool(getattr(args, "no_cao", False)),
        frontend_contract=not bool(getattr(args, "no_frontend", False)),
        save_database=bool(getattr(args, "save_db", False)),
        save_repository=bool(getattr(args, "save_repository", False)),
        run_log_diagnostic=bool(getattr(args, "logs", False)),
        clean_logs=bool(getattr(args, "clean_logs", False)),
        log_dir=getattr(args, "log_dir", None),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    command = args.command or "run"

    try:
        if command == "preflight":
            report = preflight_backend(check_logs=args.logs, log_dir=args.log_dir, include_traceback=True)
            if args.output:
                sauvegarder_json(report, args.output)
            if args.print_json or not args.output:
                print(json.dumps(_jsonable(report), ensure_ascii=False, indent=2))
            return 0 if report.get("ok") else 2

        if command == "logs":
            report = analyser_logs_backend(log_dir=args.log_dir, apply=args.apply, report_path=args.report)
            out = args.output or args.report
            if out:
                sauvegarder_json(report, out)
            if args.print_json or not out:
                print(json.dumps(_jsonable(report), ensure_ascii=False, indent=2))
            status = str(_get_path(report, "diagnostic.status", "ok"))
            return 2 if status == "critique" else 1 if status == "attention" else 0

        if command == "project":
            if args.action == "contract":
                report = charger_data_contract(args.project_id)
            elif args.action == "resolve":
                report = resoudre_inconnues_project(args.project_id)
            elif args.action == "recalculate":
                report = recalculer_project(args.project_id)
            else:
                report = optimiser_project(args.project_id)
            if args.output:
                sauvegarder_json(report, args.output)
            if args.print_json or not args.output:
                print(json.dumps(_jsonable(report), ensure_ascii=False, indent=2))
            return 0

        config = _load_config_from_args(args)
        if command == "100kw" and not any(k in config for k in ("puissance_sortie_kw", "puissance_sortie_w")):
            config["puissance_sortie_kw"] = 100.0

        opts = _options_from_args(args)
        report = executer_backend(config, options=opts, output_path=args.output)
        if args.print_json or not args.output:
            print(json.dumps(_jsonable(report), ensure_ascii=False, indent=2))
        return 0

    except Exception as exc:
        error = {
            "ok": False,
            "erreur": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


__all__ = [
    "BackendMainOptions",
    "BackendRunResult",
    "preflight_backend",
    "executer_backend",
    "analyser_depuis_puissance",
    "analyser_100kw",
    "dimensionner_systeme_shsem",
    "dimensionner_systeme_shse_m",
    "dimensionner_systeme_sthome",
    "calculer_systeme_sthome",
    "calculer_systeme_shsem",
    "charger_data_contract",
    "resoudre_inconnues_project",
    "recalculer_project",
    "optimiser_project",
    "analyser_logs_backend",
    "charger_json",
    "sauvegarder_json",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
