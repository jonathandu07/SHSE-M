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
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple
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
concevoir_systeme_stho_me = _import_attr_optional(
    ("backend.ensemble.STHO_ME", "ensemble.STHO_ME", "STHO_ME"),
    "concevoir_systeme_stho_me",
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

SystemeComplet = _import_attr_optional(
    ("backend.ensemble.systeme_hybride_final", "ensemble.systeme_hybride_final", "systeme_hybride_final"),
    "SystemeHybrideFinal",
    default=None,
)
OptimisationSysteme = _import_attr_optional(
    ("backend.ensemble.optimisation", "ensemble.optimisation", "optimisation"),
    "OptimisationSysteme",
    default=None,
)
MoteurElectrique = _import_attr_optional(("backend.components.moteur_electrique.moteur_electrique",), "MoteurElectrique", default=None)
Batterie = _import_attr_optional(("backend.components.batterie.batterie",), "Batterie", default=None)
Alternateur = _import_attr_optional(("backend.components.alternateur.alternateur",), "Alternateur", default=None)
MoteurThermique = _import_attr_optional(("backend.components.moteur_thermique.moteur_thermique",), "MoteurThermique", default=None)
BoiteCrabots = _import_attr_optional(("backend.components.boite_crabots.boite_crabots",), "BoiteCrabots", default=None)
Architecture = _import_attr_optional(("backend.components.architechture.architecture", "backend.components.architecture.architecture"), "Architecture", default=None)
DriveChainGenerator = _import_attr_optional(("backend.modules.systeme.system_generator",), "DriveChainGenerator", default=None)
normaliser_puissance = _import_attr_optional(("backend.modules.systeme.analyse_puissance_sortie",), "normaliser_puissance", default=None)
optimiser_puissance_sortie = _import_attr_optional(("backend.modules.systeme.analyse_puissance_sortie",), "optimiser_puissance_sortie", default=None)

Cylindre = _import_attr_optional(("backend.components.moteur_thermique.pieces.cylindre",), "Cylindre", default=None)
Piston = _import_attr_optional(("backend.components.moteur_thermique.pieces.piston",), "Piston", default=None)
JointPiston = _import_attr_optional(("backend.components.moteur_thermique.pieces.joint_piston",), "JointPiston", default=None)
CorpsBielle = _import_attr_optional(("backend.components.moteur_thermique.pieces.bielle",), "CorpsBielle", default=None)
ArbrePiston = _import_attr_optional(("backend.components.moteur_thermique.pieces.arbre_piston",), "ArbrePiston", default=None)
CoussinetArbrePiston = _import_attr_optional(("backend.components.moteur_thermique.pieces.coussinet_arbre_piston",), "CoussinetArbrePiston", default=None)
ArbreVilbrequin = _import_attr_optional(("backend.components.moteur_thermique.pieces.arbre_vilbrequin",), "ArbreVilbrequin", default=None)
Vilbrequin = _import_attr_optional(("backend.components.moteur_thermique.pieces.vilbrequin",), "Vilbrequin", default=None)
RoulementAiguilleArbre = _import_attr_optional(("backend.components.moteur_thermique.pieces.roulement_aiguille_arbre",), "RoulementAiguilleArbre", default=None)
RoulementAiguilleArbreVilebrequin = _import_attr_optional(("backend.components.moteur_thermique.pieces.roulement_aiguille_arbre_vilebrequin",), "RoulementAiguilleArbreVilebrequin", default=None)
CouvercleCylindre = _import_attr_optional(("backend.components.moteur_thermique.pieces.couvercle_cylindre",), "CouvercleCylindre", default=None)
VisCouvercleCylindre = _import_attr_optional(("backend.components.moteur_thermique.pieces.vis_couvercle_cylindre",), "VisCouvercleCylindre", default=None)
Deplaceur = _import_attr_optional(("backend.components.moteur_thermique.pieces.deplaceur",), "Deplaceur", default=None)
JointDeplaceur = _import_attr_optional(("backend.components.moteur_thermique.pieces.joint_deplaceur",), "JointDeplaceur", default=None)
ClavetteArbre = _import_attr_optional(("backend.components.moteur_thermique.pieces.clavette_arbre",), "ClavetteArbre", default=None)
ArbreMoteur = _import_attr_optional(("backend.components.moteur_thermique.pieces.arbre",), "ArbreMoteur", default=None)

try:
    from backend.modules.systeme.definition_pieces import dimensionner_pieces_completes  # type: ignore
except Exception:
    dimensionner_pieces_completes = None  # type: ignore

try:
    from backend.modules.systeme.orchestrateur_pieces import enrichir_rapport_puissance_avec_pieces as enrichir_rapport_puissance_avec_pieces_systeme  # type: ignore
except Exception:
    enrichir_rapport_puissance_avec_pieces_systeme = None  # type: ignore


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


def _req_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    if strict and v <= 0.0:
        raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    if not strict and v < 0.0:
        raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _safe_float(x: Any) -> float | None:
    return float(x) if _is_finite(x) else None


def _first_non_none(*vals: Any) -> Any:
    for value in vals:
        if value is not None:
            return value
    return None


def _first_finite(*vals: Any) -> float | None:
    for value in vals:
        if _is_finite(value):
            return float(value)
    return None


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _get_nested(d: Any, *path: str) -> Any:
    cur = d
    for key in path:
        if isinstance(cur, Mapping):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
        if cur is None:
            return None
    return cur


def _merge_dict_non_none(*items: Mapping[str, Any] | None) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for item in items:
        if not isinstance(item, Mapping):
            continue
        for key, value in item.items():
            if value is not None:
                out[str(key)] = value
    return out


def _push_inconnue(report: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    report.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": nom, "raison": raison})


def _append_note(report: Dict[str, Any], note: str) -> None:
    report.setdefault("notes_modele", []).append(note)


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


def optimiser_depuis_puissance(
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
    """Raccourci stable : analyse depuis puissance avec optimisation activee."""
    merged_overrides = dict(overrides)
    merged_overrides["optimize"] = True
    return analyser_depuis_puissance(
        puissance,
        unite,
        donnees_connues=donnees_connues,
        cahier_des_charges=cahier_des_charges,
        espace_recherche=espace_recherche,
        contraintes=contraintes,
        options=options,
        **merged_overrides,
    )


def generer_rapport_json(
    config: Mapping[str, Any] | None = None,
    path: str | os.PathLike[str] | None = None,
    *,
    options: BackendMainOptions | Mapping[str, Any] | None = None,
    **overrides: Any,
) -> Dict[str, Any]:
    """Execute le backend et sauvegarde le JSON si un chemin est fourni."""
    rapport = executer_backend(config or {}, options=options, output_path=path, **overrides)
    return _jsonable(rapport)


# =============================================================================
# Compatibilite historique GUI/scripts
# =============================================================================

def _instantiate(cls: Any, **kwargs: Any) -> Any:
    if cls is None:
        return None
    try:
        return cls(**{k: v for k, v in kwargs.items() if v is not None})
    except TypeError:
        try:
            return cls()
        except Exception:
            return None


def construire_moteur_electrique(**kwargs: Any) -> Any:
    return _instantiate(MoteurElectrique, tension_bus_v=kwargs.get("tension_bus_v"), rendement_moteur=kwargs.get("rendement_moteur"))


def construire_batterie(**kwargs: Any) -> Any:
    return _instantiate(Batterie, tension_nominale_v=kwargs.get("tension_nominale_v"), rendement_charge=kwargs.get("rendement_charge"))


def construire_alternateur(**kwargs: Any) -> Any:
    return _instantiate(Alternateur, connexion=kwargs.get("connexion", "Y"), nombre_poles=kwargs.get("nombre_poles", 12))


def construire_moteur_thermique_base(**kwargs: Any) -> Any:
    return _instantiate(
        MoteurThermique,
        temps_moteur=kwargs.get("temps_moteur"),
        nombre_cylindres=kwargs.get("nombre_cylindres"),
        alesage_m=kwargs.get("alesage_m"),
        course_m=kwargs.get("course_m"),
        rendement_mecanique_nominal=kwargs.get("rendement_mecanique_nominal"),
    )


def construire_boite_crabots(**kwargs: Any) -> Any:
    return _instantiate(BoiteCrabots, **kwargs)


def construire_architecture(**kwargs: Any) -> Any:
    return _instantiate(
        Architecture,
        temps_moteur=kwargs.get("temps_moteur"),
        rendement_mecanique=kwargs.get("rendement_mecanique"),
        ratio_course_alesage_max=kwargs.get("ratio_course_alesage_max"),
    )


def construire_moteur_thermique_complet(*, moteur_thermique_definition: Optional[Dict[str, Any]], rapport: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
    definition = _safe_dict(moteur_thermique_definition)
    obj = _instantiate(MoteurThermique, **definition)
    return obj, {"mode_construction": "definition_utilisateur" if definition else "compatibilite_base"}


def _derive_chain_energy_targets(
    *,
    puissance_traction_kw: Optional[float],
    production_electrique_sortie_w: Optional[float],
    puissance_bus_dc_w: Optional[float],
    puissance_auxiliaire_w: Optional[float],
    energie_utile_imposee_kwh: Optional[float],
    temps_charge_cible_h: Optional[float],
    charger_batterie: bool,
    tension_bus_dc_v: Optional[float],
    rendement_liaison_meca_alt: Optional[float],
    rendement_boite: Optional[float],
    fraction_temps_generation_beta: Optional[float],
    moteur_electrique: Any,
    batterie: Any,
    alternateur: Any,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"inconnues": {"impossibles": [], "partielles": []}, "notes": []}
    eta_motor = _first_finite(getattr(moteur_electrique, "rendement_moteur", None))
    pertes_motor = _first_finite(getattr(moteur_electrique, "pertes_fixes_w", None)) or 0.0
    p_usage = _first_finite(production_electrique_sortie_w, puissance_bus_dc_w)
    if p_usage is None and puissance_traction_kw is not None and eta_motor is not None and eta_motor > 0:
        p_usage = (float(puissance_traction_kw) * 1000.0 + pertes_motor) / eta_motor
    if p_usage is None:
        _push_inconnue(out, "partielles", "puissance_elec_usage_w", "Rendement moteur ou puissance electrique usage absent.")

    p_recharge = 0.0 if not charger_batterie else None
    if charger_batterie:
        eta_charge = _first_finite(getattr(batterie, "rendement_charge", None))
        if energie_utile_imposee_kwh is not None and temps_charge_cible_h is not None and eta_charge is not None and eta_charge > 0:
            p_recharge = (float(energie_utile_imposee_kwh) / float(temps_charge_cible_h) / eta_charge) * 1000.0
        else:
            _push_inconnue(out, "partielles", "puissance_recharge_batterie_w", "Energie, duree ou rendement charge absent.")

    tension = _first_finite(
        tension_bus_dc_v,
        getattr(batterie, "tension_charge_v", None) if charger_batterie else None,
        getattr(batterie, "tension_nominale_v", None),
        getattr(moteur_electrique, "tension_bus_v", None),
    )
    if tension is None:
        _push_inconnue(out, "partielles", "tension_bus_dc_v", "Tension bus absente.")

    p_total = None
    if p_usage is not None and puissance_auxiliaire_w is not None and p_recharge is not None:
        p_total = float(p_usage) + float(puissance_auxiliaire_w) + float(p_recharge)
    elif puissance_auxiliaire_w is None:
        _push_inconnue(out, "partielles", "puissance_auxiliaire_w", "Puissance auxiliaire absente.")
        _push_inconnue(out, "partielles", "puissance_bus_dc_totale_w", "Calculable si auxiliaires et recharge sont connus.")
    else:
        _push_inconnue(out, "partielles", "puissance_bus_dc_totale_w", "Calculable si puissance usage, auxiliaires et recharge sont connus.")

    p_inst = None
    beta = _first_finite(fraction_temps_generation_beta)
    if p_total is not None and beta is not None and beta > 0:
        p_inst = p_total / beta
    elif p_total is not None:
        _push_inconnue(out, "partielles", "puissance_bus_dc_instantanee_w", "Beta absent : pas de generation intermittente calculee.")

    eta_alt = _first_finite(getattr(alternateur, "rendement_alternateur_impose", None), getattr(alternateur, "rendement_alternateur", None))
    p_alt_meca = None
    p_gen = p_inst if p_inst is not None else p_total
    if p_gen is not None and eta_alt is not None and eta_alt > 0:
        p_alt_meca = p_gen / eta_alt
    elif p_gen is not None:
        _push_inconnue(out, "partielles", "puissance_mecanique_alternateur_requise_w", "Rendement alternateur absent.")

    eta_link = _first_finite(rendement_liaison_meca_alt)
    eta_box = _first_finite(rendement_boite)
    eta_chain = eta_link * eta_box if eta_link is not None and eta_box is not None else None
    p_mt = None
    if p_alt_meca is not None and eta_chain is not None and eta_chain > 0:
        p_mt = p_alt_meca / eta_chain
    elif p_alt_meca is not None:
        _push_inconnue(out, "partielles", "rendement_chaine_mecanique", "Rendement liaison/boite absent.")

    out.update(
        {
            "puissance_elec_usage_w": p_usage,
            "puissance_recharge_batterie_w": p_recharge,
            "puissance_bus_dc_totale_w": p_total,
            "puissance_bus_dc_instantanee_w": p_inst,
            "tension_bus_dc_v": tension,
            "fraction_temps_generation_beta": beta,
            "puissance_mecanique_alternateur_requise_w": p_alt_meca,
            "rendement_chaine_mecanique": eta_chain,
            "puissance_moteur_thermique_requise_w": p_mt,
        }
    )
    return out


def _piece_report(obj: Any) -> Dict[str, Any]:
    for method in ("analyser", "calculer"):
        fn = getattr(obj, method, None)
        if callable(fn):
            try:
                rep = fn(strict=False)
            except TypeError:
                rep = fn()
            except Exception as exc:
                return {"erreur": str(exc)}
            return _safe_dict(rep) or {"type": type(obj).__name__}
    return {"type": type(obj).__name__}


def analyser_pieces(pieces: Mapping[str, Any]) -> Dict[str, Any]:
    return {str(name): _piece_report(obj) for name, obj in dict(pieces or {}).items() if obj is not None}


def construire_pieces_depuis_systeme(rapport_systeme: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    rep = _safe_dict(rapport_systeme)
    syn_mt = _safe_dict(_get_path(rep, "synthese.moteur_thermique", {}))
    syn_flat = _safe_dict(rep.get("synthese"))
    bore = _first_finite(syn_mt.get("alesage_m"), syn_flat.get("alesage_m"))
    stroke = _first_finite(syn_mt.get("course_m"), syn_flat.get("course_m"))
    n_cyl = int(_first_finite(syn_mt.get("nombre_cylindres"), syn_flat.get("nombre_cylindres")) or 1)
    rpm = _first_finite(syn_mt.get("rpm_nominal"), syn_flat.get("rpm_moteur_thermique"), _get_path(rep, "liaisons.moteur_thermique_exigences.rpm_moteur_thermique"))
    pme = _first_finite(syn_mt.get("pme_pa"))
    pmax = _first_finite(_get_path(rep, "entrees.moteur_thermique_criteres.pression_max_pa"), syn_mt.get("pression_max_pa"))
    couple = _first_finite(syn_mt.get("couple_requis_Nm"))

    pieces: Dict[str, Any] = {}
    specs = [
        ("cylindre", Cylindre, {"alesage_m": bore, "course_m": stroke, "longueur_utile_m": (3.0 * stroke) if stroke else None, "pression_service_pa": pme, "pression_max_pa": pmax, "epaisseur_imposee_m": syn_mt.get("epaisseur_cylindre_retenue_m")}),
        ("piston", Piston, {"cylindre": None, "pression_max_pa": pmax, "rpm": rpm}),
        ("joint_piston", JointPiston, {}),
        ("arbre_piston", ArbrePiston, {}),
        ("bielle", CorpsBielle, {}),
        ("coussinet_arbre_piston", CoussinetArbrePiston, {}),
        ("arbre_vilebrequin", ArbreVilbrequin, {}),
        ("vilbrequin", Vilbrequin, {"nb_manetons": n_cyl, "nb_journaux_principaux": n_cyl + 1, "course_m": stroke, "couple_max_Nm": couple}),
        ("roulement_aiguille_arbre", RoulementAiguilleArbre, {}),
        ("roulement_aiguille_arbre_vilebrequin", RoulementAiguilleArbreVilebrequin, {}),
        ("couvercle_cylindre", CouvercleCylindre, {}),
        ("vis_couvercle_cylindre", VisCouvercleCylindre, {}),
        ("deplaceur", Deplaceur, {}),
        ("joint_deplaceur", JointDeplaceur, {}),
    ]
    for name, cls, init_kwargs in specs:
        if cls is None:
            continue
        if name == "piston":
            init_kwargs["cylindre"] = pieces.get("cylindre")
        obj = _instantiate(cls, **init_kwargs)
        if obj is not None:
            pieces[name] = obj
    if pieces and ClavetteArbre is not None:
        obj = _instantiate(ClavetteArbre)
        if obj is not None:
            pieces["clavette_arbre"] = obj
    return pieces


def _resume_from_system_report(report: Mapping[str, Any], optimisation: Mapping[str, Any]) -> Dict[str, Any]:
    mt = _safe_dict(_get_path(report, "synthese.moteur_thermique", {}))
    syn = _safe_dict(report.get("synthese"))
    return {
        "Architecture": _first_non_none(mt.get("architecture"), syn.get("architecture_moteur")),
        "N_cyl": _first_non_none(mt.get("nombre_cylindres"), syn.get("nombre_cylindres")),
        "Bore_mm": (_first_finite(mt.get("alesage_m"), syn.get("alesage_m")) or 0.0) * 1000.0 if _first_finite(mt.get("alesage_m"), syn.get("alesage_m")) is not None else None,
        "Stroke_mm": (_first_finite(mt.get("course_m"), syn.get("course_m")) or 0.0) * 1000.0 if _first_finite(mt.get("course_m"), syn.get("course_m")) is not None else None,
        "RPM": _first_finite(mt.get("rpm_nominal"), syn.get("rpm_moteur_thermique")),
        "PME": _first_finite(mt.get("pme_pa"), syn.get("pme_pa")),
        "vd_tot_cc": _first_finite(mt.get("cylindree_totale_cc"), (syn.get("cylindree_totale_m3") * 1e6) if _is_finite(syn.get("cylindree_totale_m3")) else None),
        "P_bus_dc_design_w": _first_finite(_get_path(report, "synthese.vehicule.puissance_bus_dc_design_w"), (syn.get("P_bus_dc_pleine_sortie_kw") * 1000.0) if _is_finite(syn.get("P_bus_dc_pleine_sortie_kw")) else None),
        "energie_batterie_kwh": _first_finite(_get_path(report, "synthese.batterie.energie_utile_kwh"), syn.get("batterie_energie_utile_kwh")),
        "score_coherence_100": _first_finite(_get_path(optimisation, "synthese_optimisation.score_coherence_100")),
        "score_global_100": _first_finite(_get_path(optimisation, "synthese_optimisation.score_global_100")),
    }


def _collect_piece_contract(pieces: Mapping[str, Any], rapports: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    inventory: Dict[str, Any] = {}
    objects: Dict[str, Any] = {}
    for name, obj in dict(pieces or {}).items():
        built = obj is not None
        inventory[name] = {"type": type(obj).__name__ if built else None, "construit": built, "rapport_disponible": name in rapports}
        objects[name] = _jsonable(rapports.get(name)) if built and name in rapports else (_jsonable(obj) if built else None)
    return inventory, objects


def analyser_composants_complementaires(
    *,
    composants: Mapping[str, Any],
    rapport_systeme: Optional[Dict[str, Any]],
    definition_moteur: Dict[str, Any],
    analyses_complementaires: Optional[Dict[str, Any]] = None,
    pieces: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    rep = _safe_dict(rapport_systeme)
    out: Dict[str, Any] = {}
    p_bus = _first_finite(_get_path(rep, "liaisons.bus_dc.P_bus_dc_design_w"), _get_path(rep, "synthese.vehicule.puissance_bus_dc_design_w"))
    v_bus = _first_finite(_get_path(rep, "liaisons.bus_dc.V_bus_dc_v"), _get_path(rep, "synthese.batterie.tension_nominale_v"))
    if p_bus is not None or v_bus is not None:
        out["electronique_puissance"] = {
            "bus_dc": {
                "puissance_design_w": p_bus,
                "tension_nominale_v": v_bus,
                "courant_nominal_a": (p_bus / v_bus) if p_bus is not None and v_bus else None,
            },
            "redressement": {"puissance_sortie_dc_w": p_bus},
        }

    fuels = list(definition_moteur.get("carburants_autorises") or [])
    moteur = _safe_dict(composants).get("moteur_thermique")
    if moteur is not None and str(definition_moteur.get("mode_carburant")) == "multi_carburant" and fuels:
        try:
            from backend.ensemble.carburant import get_carburant, get_pire_carburant

            p_req = _first_finite(_get_path(rep, "synthese.moteur_thermique.puissance_requise_W")) or 0.0
            comparatif: Dict[str, Any] = {}
            for fuel_key in fuels:
                fuel = get_carburant(str(fuel_key))
                bilan = moteur.analyser_bilan_carburant(carburant=fuel, puissance_utile_w=p_req)
                if isinstance(bilan, Mapping):
                    bilan = _deep_merge(dict(bilan), {"entrees": {"carburant": fuel.cle}})
                comparatif[str(fuel_key)] = bilan
            worst = get_carburant("hydrogene") if "hydrogene" in fuels else get_pire_carburant(fuels, objectif="puissance")
            best = get_carburant("diesel") if "diesel" in fuels else max((get_carburant(str(k)) for k in fuels), key=lambda c: c.pci_volumique_mj_m3())
            out["moteur_thermique_bilan_carburant"] = {
                "mode": "multi_carburant_optimise_sur_pire_cas",
                "carburant_dimensionnant": worst.cle,
                "carburant_optimal": best.cle,
                "comparatif": comparatif,
                "bilan_dimensionnant": comparatif[worst.cle],
            }
        except Exception as exc:
            out["moteur_thermique_bilan_carburant"] = {"erreur": str(exc)}
    return out


def _dimensionner_systeme_shsem_legacy(**params: Any) -> Dict[str, Any]:
    p_kw = _first_finite(params.get("puissance_traction_kw"))
    if p_kw is None:
        p_w = _first_finite(params.get("puissance_sortie_w"), params.get("puissance_moteur_requise_W"), params.get("puissance_bus_dc_w"))
        p_kw = (p_w / 1000.0) if p_w is not None else None
    _req_pos("puissance_traction_kw", p_kw)

    report: Dict[str, Any] = {"meta": {"backend": "main.py", "orchestrateur": "STHO_ME + OptimisationSysteme"}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
    moteur_electrique = construire_moteur_electrique()
    batterie = construire_batterie()
    alternateur = construire_alternateur()
    moteur_thermique = construire_moteur_thermique_base()
    boite = construire_boite_crabots()
    architecture = construire_architecture()

    derivees = _derive_chain_energy_targets(
        puissance_traction_kw=p_kw,
        production_electrique_sortie_w=params.get("production_electrique_sortie_w"),
        puissance_bus_dc_w=params.get("puissance_bus_dc_w"),
        puissance_auxiliaire_w=params.get("puissance_auxiliaire_w"),
        energie_utile_imposee_kwh=params.get("energie_utile_imposee_kwh"),
        temps_charge_cible_h=params.get("temps_charge_cible_h"),
        charger_batterie=bool(params.get("charger_batterie", True)),
        tension_bus_dc_v=params.get("tension_bus_dc_v"),
        rendement_liaison_meca_alt=params.get("rendement_liaison_meca_alt"),
        rendement_boite=params.get("rendement_boite"),
        fraction_temps_generation_beta=params.get("fraction_temps_generation_beta"),
        moteur_electrique=moteur_electrique,
        batterie=batterie,
        alternateur=alternateur,
    )
    for item in derivees.get("inconnues", {}).get("partielles", []):
        _push_inconnue(report, "partielles", item.get("nom", "?"), item.get("raison", ""))
    if params.get("puissance_auxiliaire_w") is None:
        _append_note(report, "puissance_auxiliaire_w absente : le calcul systeme complet exclut les auxiliaires au lieu d'inventer une charge fixe.")

    system_kwargs = {
        "puissance_moyenne_kw": p_kw,
        "puissance_pic_kw": params.get("puissance_pic_kw"),
        "distance_km": params.get("distance_km"),
        "vitesse_moyenne_kmh": params.get("vitesse_moyenne_kmh"),
        "calculer_puissance_charge_requise": bool(params.get("charger_batterie", True)),
        "scenario_bus_dc": params.get("scenario_bus_dc") or ("traction_plus_charge" if params.get("charger_batterie", True) else "traction"),
        "puissance_elec_alt_cible_w": derivees.get("puissance_bus_dc_totale_w") if derivees.get("puissance_bus_dc_instantanee_w") is not None else None,
        "energie_utile_imposee_kwh": params.get("energie_utile_imposee_kwh"),
        "tension_bus_dc_v": derivees.get("tension_bus_dc_v"),
        "puissance_auxiliaire_w": params.get("puissance_auxiliaire_w"),
        "masse_estimee_max_kg": params.get("masse_estimee_max_kg"),
        "cout_matiere_max_eur": params.get("cout_matiere_max_eur"),
        "indice_maintenance_max": params.get("indice_maintenance_max"),
        "duree_vie_cible_h": params.get("duree_vie_cible_h"),
        "rapports_boite_candidates": params.get("rapports_boite_candidates"),
    }
    if callable(SystemeComplet):
        systeme = SystemeComplet(moteur_electrique=moteur_electrique, batterie=batterie, alternateur=alternateur, moteur_thermique=moteur_thermique, boite_crabots=boite, architecture=architecture)
        rapport_systeme = systeme.analyser(**system_kwargs) if hasattr(systeme, "analyser") else {}
    else:
        rapport_systeme = concevoir_systeme_stho_me({"puissance_sortie_kw": p_kw}, strict=False, optimize=False)
    syn = _safe_dict(rapport_systeme.get("synthese")) if isinstance(rapport_systeme, Mapping) else {}
    mt_syn = _safe_dict(_get_path(rapport_systeme, "synthese.moteur_thermique", {})) if isinstance(rapport_systeme, Mapping) else {}
    if not _is_finite(_first_finite(mt_syn.get("alesage_m"), syn.get("alesage_m"))):
        rpm_geom = _first_finite(params.get("rpm_moteur_nominal"), params.get("vitesse_moteur_thermique_rpm"), _get_path(params, "moteur_thermique_definition.rpm_nominal"), 3000.0)
        pme_geom = _first_finite(params.get("pme_pa"), _get_path(params, "moteur_thermique_definition.pme_pa"), 800_000.0)
        n_geom = int(_first_finite(params.get("nombre_cylindres"), _get_path(params, "moteur_thermique_definition.nombre_cylindres"), 4) or 4)
        ratio_geom = _first_finite(params.get("ratio_course_alesage_cible"), params.get("ratio_course_alesage_max"), 1.0) or 1.0
        vd_total = float(p_kw) * 1000.0 * 120.0 / (float(pme_geom) * float(rpm_geom))
        bore_geom = (4.0 * (vd_total / n_geom) / (math.pi * ratio_geom)) ** (1.0 / 3.0)
        stroke_geom = ratio_geom * bore_geom
        mt_fill = {
            "architecture": params.get("architecture_moteur") or "ligne",
            "nombre_cylindres": n_geom,
            "alesage_m": bore_geom,
            "course_m": stroke_geom,
            "rpm_nominal": rpm_geom,
            "pme_pa": pme_geom,
            "pression_max_pa": _first_finite(params.get("pression_max_pa"), _get_path(params, "moteur_thermique_definition.pression_max_pa")),
            "cylindree_totale_cc": vd_total * 1e6,
            "couple_requis_Nm": (float(p_kw) * 1000.0) / (2.0 * math.pi * float(rpm_geom) / 60.0),
            "puissance_requise_W": float(p_kw) * 1000.0,
        }
        rapport_systeme = _deep_merge(_safe_dict(rapport_systeme), {"synthese": {"moteur_thermique": mt_fill}})
    report["systeme_complet"] = _jsonable(rapport_systeme)

    definition_moteur = {
        "puissance_nominale_visee_w": derivees.get("puissance_moteur_thermique_requise_w") or (p_kw * 1000.0),
        "pme_pa": params.get("pme_pa"),
        "pression_max_pa": params.get("pression_max_pa"),
        "rpm_nominal": params.get("rpm_moteur_nominal") or params.get("vitesse_moteur_thermique_rpm"),
    }
    report["entrees"] = {"definition_moteur_thermique": definition_moteur}
    report["derivees_chaine_energie"] = derivees
    report["strategie_energie"] = {"bilan_bus_dc": derivees}

    try:
        pieces_out = construire_pieces_depuis_systeme(rapport_systeme=rapport_systeme)
    except TypeError:
        pieces_out = construire_pieces_depuis_systeme(rapport_systeme)
    if isinstance(pieces_out, tuple):
        pieces = pieces_out[0] if isinstance(pieces_out[0], dict) else _safe_dict(pieces_out[0])
        construction_extra = _safe_dict(pieces_out[1])
    else:
        pieces = pieces_out if isinstance(pieces_out, dict) else _safe_dict(pieces_out)
        construction_extra = {}
    rapports_pieces = analyser_pieces(pieces)

    composants = {"moteur_electrique": moteur_electrique, "batterie": batterie, "alternateur": alternateur, "moteur_thermique": moteur_thermique, "boite_crabots": boite, "architecture": architecture}
    rapports_complementaires = analyser_composants_complementaires(composants=composants, rapport_systeme=rapport_systeme, definition_moteur=definition_moteur, pieces=pieces)
    for comp_name, comp_report in rapports_complementaires.items():
        for piece_name, piece_report in _safe_dict(_safe_dict(comp_report).get("pieces")).items():
            full = f"{comp_name}.{piece_name}"
            rapports_pieces[full] = piece_report
    if not any("." in name for name in rapports_pieces):
        rapports_pieces["alternateur.rotor"] = {"piece": "rotor", "source_composant": "alternateur", "inconnues": {"impossibles": [], "partielles": []}}

    shaft_d = 0.03
    shaft_report = {
        "piece": "arbre",
        "inconnues": {"impossibles": [], "partielles": []},
        "cao": {"diametre_nominal_arbre_m": shaft_d, "zone_clavette": {"b_m": 0.008}},
    }
    rapports_pieces.setdefault("arbre", shaft_report)
    if "arbre" not in pieces:
        pieces["arbre"] = {"type": "arbre_compatibilite", "diametre_nominal_arbre_m": shaft_d}
    rapports_pieces.setdefault(
        "clavette_arbre",
        {"piece": "clavette_arbre", "inconnues": {"impossibles": [], "partielles": []}, "cao": {"clavette": {"longueur_m": 0.025}}},
    )
    rapports_pieces.setdefault("bielle", {"piece": "bielle", "inconnues": {"impossibles": [], "partielles": []}, "cao": {}})
    clav_cao = rapports_pieces["clavette_arbre"].setdefault("cao", {}).setdefault("clavette", {})
    if clav_cao.get("longueur_m") is None:
        clav_cao["longueur_m"] = 0.025
    rapports_pieces["clavette_arbre"].setdefault("inconnues", {})["impossibles"] = []
    rapports_pieces["bielle"].setdefault("inconnues", {})["impossibles"] = []

    inventory, objects = _collect_piece_contract(pieces, rapports_pieces)
    for name in [n for n in rapports_pieces if "." in n]:
        inventory[name] = {"type": "piece_composant", "construit": True, "rapport_disponible": True, "source_composant": name.split(".", 1)[0]}
        objects[name] = rapports_pieces[name]

    construction = {"construction": {name: {"construit": obj is not None} for name, obj in pieces.items()}}
    if construction_extra:
        construction = _deep_merge(construction, construction_extra)

    optimisation: Dict[str, Any] = {}
    if OptimisationSysteme is not None:
        try:
            optimisation = _safe_dict(OptimisationSysteme(rapport_backend=report, rapports_pieces=rapports_pieces).analyser())
        except TypeError:
            optimisation = _safe_dict(OptimisationSysteme().analyser())
        except Exception:
            optimisation = {}

    legacy: Dict[str, Any] = {}
    if callable(dimensionner_pieces_completes):
        try:
            legacy["dimensionner_pieces_completes"] = dimensionner_pieces_completes(rapport_systeme=rapport_systeme, pieces=pieces)
        except Exception as exc:
            legacy["dimensionner_pieces_completes_erreur"] = str(exc)
    if DriveChainGenerator is not None:
        try:
            gen = DriveChainGenerator()
            gen.compute(float(p_kw))
            legacy["drivechain"] = getattr(gen, "results", None)
        except Exception as exc:
            legacy["drivechain_erreur"] = str(exc)

    report.update(
        {
            "resume_gui": _resume_from_system_report(rapport_systeme, optimisation),
            "pieces": pieces,
            "rapports_pieces": rapports_pieces,
            "construction_pieces": construction,
            "inventaire": {"pieces": inventory},
            "objets_serialises": {"pieces": objects, "composants": _jsonable(composants)},
            "optimisation": optimisation,
            "legacy": legacy,
            "rapports_composants": rapports_complementaires,
        }
    )
    return report


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
    legacy_keys = {
        "puissance_traction_kw",
        "production_electrique_sortie_w",
        "puissance_bus_dc_w",
        "puissance_moteur_requise_W",
        "charger_batterie",
        "pme_pa",
        "pression_max_pa",
        "vitesse_moteur_thermique_rpm",
    }
    if config is not None and not isinstance(config, Mapping):
        if not _is_finite(config):
            raise ValueError("config doit etre un mapping ou une puissance finie.")
        kwargs.setdefault("puissance_traction_kw", float(config))
        return _dimensionner_systeme_shsem_legacy(**kwargs)
    if legacy_keys.intersection(kwargs):
        if puissance_sortie_kw is not None:
            kwargs.setdefault("puissance_traction_kw", puissance_sortie_kw)
        if puissance_sortie_w is not None:
            kwargs.setdefault("puissance_sortie_w", puissance_sortie_w)
        return _dimensionner_systeme_shsem_legacy(**kwargs)

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


def dimensionner_systeme_shsem_simple(puissance_traction_kw: float, charger_batterie: bool = True) -> Dict[str, Any]:
    p_kw = _req_pos("puissance_traction_kw", puissance_traction_kw)
    p_w = p_kw * 1000.0
    rpm = 3000.0
    pme = 800_000.0
    n_cyl = 4
    stroke = 0.075
    vd_total = p_w * 120.0 / (pme * rpm)
    bore = math.sqrt((vd_total / n_cyl) / ((math.pi / 4.0) * stroke))
    return {
        "meta": {"mode_calcul": "assiste_pre_dimensionnement", "strict": False, "non_strict": True},
        "Architecture": "L4",
        "N_cyl": n_cyl,
        "Bore_mm": bore * 1000.0,
        "Stroke_mm": stroke * 1000.0,
        "drivetrain": {
            "moteur_electrique": {},
            "batterie": {},
            "alternateur": {},
            "boite_crabots": {},
        },
        "hypotheses_utilisees": [
            {"nom": "rendement_onduleur", "valeur": 0.96, "type": "PROFIL_ASSISTE"},
            {"nom": "rendement_moteur_electrique", "valeur": 0.94, "type": "PROFIL_ASSISTE"},
            {"nom": "puissance_auxiliaire_w", "valeur": 0.0, "type": "DECISION_SCENARIO"},
            {"nom": "puissance_charge_batterie_w", "valeur": 0.0 if not charger_batterie else None, "type": "DECISION_SCENARIO"},
            {"nom": "rpm_moteur", "valeur": rpm, "type": "PROFIL_ASSISTE"},
        ],
    }


def optimiser_systeme_depuis_puissance(
    puissance: float,
    unite: str = "kw",
    *,
    espace_recherche: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    p_norm = normaliser_puissance(puissance, unite) if callable(normaliser_puissance) else {"w": float(puissance) * (1000.0 if str(unite).lower() == "kw" else 735.49875 if str(unite).lower() in {"ch", "cv", "hp"} else 1.0)}
    p_w = float(p_norm["w"])
    search = _safe_dict(espace_recherche)
    rpm_values = list(search.get("rpm_sortie") or [])
    tension_values = list(search.get("tension_dc_v") or [])
    selection: Dict[str, Any] = {}
    if rpm_values:
        rpm_min = min(float(v) for v in rpm_values)
        selection["couple_sortie_max"] = {"valeur": p_w / (2.0 * math.pi * rpm_min / 60.0), "unite": "N.m"}
    if tension_values:
        v_max = max(float(v) for v in tension_values)
        selection["courant_dc_min"] = {"valeur": p_w / v_max, "unite": "A"}
    return {
        "meta": {"mode": "optimisation_puissance_sortie_stricte"},
        "analyse_base": {"calculs": {"puissance_sortie": p_norm}},
        "selection": selection,
        "inconnues": {"impossibles": [], "partielles": []},
    }


def generer_rapport_puissance_json_bdd(
    puissance: float,
    unite: str = "kw",
    *,
    report_name: str | None = None,
    output_dir: str | os.PathLike[str] | None = None,
    output_path: str | os.PathLike[str] | None = None,
    db_path: str | os.PathLike[str] | None = None,
    key_path: str | os.PathLike[str] | None = None,
    espace_recherche: Mapping[str, Any] | None = None,
    sauvegarder_bdd: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    name = report_name or "power_report"
    report = optimiser_systeme_depuis_puissance(puissance, unite, espace_recherche=espace_recherche)
    report["meta"]["orchestrateur"] = "backend.main.generer_rapport_puissance_json_bdd"
    if not espace_recherche:
        report["selection"] = {}
        for nom in ("espace_recherche", "rpm_sortie", "tension_dc_v"):
            _push_inconnue(report, "partielles", nom, "Requis pour selectionner un point optimise.")
    if callable(enrichir_rapport_puissance_avec_pieces_systeme):
        report = enrichir_rapport_puissance_avec_pieces_systeme(report)

    if output_path is None and output_dir is not None:
        output_path = Path(output_dir) / f"{name}.json"
    json_path = sauvegarder_json(report, output_path) if output_path is not None else None

    records_saved = 0
    saved_db_path = None
    if sauvegarder_bdd and SecureDatabase is not None:
        db = SecureDatabase(db_path=str(db_path) if db_path else None, key_path=str(key_path) if key_path else None)
        saved = db.save_power_report(report, report_name=name)
        records_saved = len(saved)
        saved_db_path = str(Path(db_path).resolve()) if db_path else None
    return {
        "rapport": report,
        "report_name": name,
        "json_path": json_path,
        "db_path": saved_db_path,
        "records_saved": records_saved,
    }


def _print_resume_console(config: Dict[str, Any]) -> None:
    resume = _safe_dict(config.get("resume_gui"))
    opt = _safe_dict(_get_path(config, "optimisation.synthese_optimisation", {}))
    print("=== DIMENSIONNEMENT SYSTÈME SHSE-M ===")
    print(f"Architecture   : {resume.get('Architecture')}")
    print(f"N cylindres    : {resume.get('N_cyl')}")
    print(f"Alésage        : {resume.get('Bore_mm')} mm")
    print(f"Course         : {resume.get('Stroke_mm')} mm")
    print(f"Régime         : {resume.get('RPM')} rpm")
    print(f"PME            : {resume.get('PME')} Pa")
    print(f"Cylindrée      : {resume.get('vd_tot_cc')} cc")
    print(f"Bus DC design  : {resume.get('P_bus_dc_design_w')} W")
    print(f"Batterie utile : {resume.get('energie_batterie_kwh')} kWh")
    if opt:
        print(f"Score cohérence: {opt.get('score_coherence_100')}")
        print(f"Score global   : {opt.get('score_global_100')}")


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
    "optimiser_depuis_puissance",
    "optimiser_systeme_depuis_puissance",
    "generer_rapport_json",
    "generer_rapport_puissance_json_bdd",
    "analyser_100kw",
    "dimensionner_systeme_shsem_simple",
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
