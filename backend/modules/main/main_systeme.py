from __future__ import annotations

"""
backend/modules/main/main_systeme.py
===============================================================================
Orchestrateur principal des modules système STHO-ME
===============================================================================

Rôle
----
Ce fichier est la façade backend stable au-dessus des modules fournis dans
`backend/modules/systeme` et de l'orchestrateur haut niveau `backend/ensemble/STHO_ME.py`.

Il ne remplace pas les calculateurs spécialisés. Il coordonne :
- analyse stricte d'une puissance de sortie ;
- génération / sélection de candidats si un espace de recherche est fourni ;
- orchestration complète STHO-ME ;
- résolution d'inconnues ;
- validation de la chaîne de puissance ;
- diagnostic causal ;
- graphiques mécaniques analytiques ;
- dossier de préconception CAO ;
- contrat frontend ;
- sauvegarde optionnelle en repository JSON et/ou base chiffrée.

Principe important
------------------
La puissance demandée par l'utilisateur est interprétée comme puissance utile de
sortie, par exemple la puissance mécanique utile fournie par le ou les moteurs
électriques. Le bus DC, l'alternateur, la batterie, la boîte à crabots et le
moteur thermique sont ensuite vérifiés autour de cette demande.

Aucune valeur métier n'est inventée : lorsqu'une donnée manque, le rapport final
la remonte dans `inconnues` ou `diagnostic` au lieu de masquer le problème.

Placement recommandé
--------------------
backend/modules/main/main_systeme.py
"""

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple
import argparse
import copy
import importlib
import json
import math
import sys
import traceback


# =============================================================================
# Chemins / imports robustes
# =============================================================================

_THIS_FILE = Path(__file__).resolve() if "__file__" in globals() else Path.cwd() / "main_systeme.py"
_THIS_DIR = _THIS_FILE.parent
for _candidate in (
    _THIS_DIR,
    _THIS_DIR.parent,
    _THIS_DIR.parent.parent,
    _THIS_DIR.parent.parent.parent,
    Path.cwd(),
):
    try:
        _s = str(_candidate.resolve())
    except Exception:
        _s = str(_candidate)
    if _s not in sys.path:
        sys.path.insert(0, _s)

_IMPORT_ERRORS: Dict[str, str] = {}
_MISSING = object()


def _import_module_optional(module_names: Sequence[str]) -> Any | None:
    last_error: BaseException | None = None
    for module_name in module_names:
        try:
            return importlib.import_module(module_name)
        except BaseException as exc:  # robustesse orchestrateur
            last_error = exc
    _IMPORT_ERRORS["module:" + "|".join(module_names)] = f"{type(last_error).__name__}: {last_error}"
    return None


def _import_attr_optional(module_names: Sequence[str], attr: str, default: Any = None) -> Any:
    last_error: BaseException | None = None
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            return getattr(module, attr)
        except BaseException as exc:  # robustesse orchestrateur
            last_error = exc
    _IMPORT_ERRORS[f"{attr}@{'|'.join(module_names)}"] = f"{type(last_error).__name__}: {last_error}"
    return default


# Modules système fournis par l'utilisateur.
get_alias_paths = _import_attr_optional(
    ("backend.modules.systeme.aliases", "modules.systeme.aliases", "aliases"),
    "get_alias_paths",
)
canonical_field_name = _import_attr_optional(
    ("backend.modules.systeme.aliases", "modules.systeme.aliases", "aliases"),
    "canonical_field_name",
)
get_first_available_value = _import_attr_optional(
    ("backend.modules.systeme.aliases", "modules.systeme.aliases", "aliases"),
    "get_first_available_value",
)

analyser_puissance_sortie = _import_attr_optional(
    ("backend.modules.systeme.analyse_puissance_sortie", "modules.systeme.analyse_puissance_sortie", "analyse_puissance_sortie"),
    "analyser_puissance_sortie",
)
optimiser_puissance_sortie = _import_attr_optional(
    ("backend.modules.systeme.analyse_puissance_sortie", "modules.systeme.analyse_puissance_sortie", "analyse_puissance_sortie"),
    "optimiser_puissance_sortie",
)

valider_chaine_puissance_sthome = _import_attr_optional(
    ("backend.modules.systeme.chain_validator", "modules.systeme.chain_validator", "chain_validator"),
    "valider_chaine_puissance_sthome",
)

SystemDataRepository = _import_attr_optional(
    ("backend.modules.systeme.data_repository", "modules.systeme.data_repository", "data_repository"),
    "SystemDataRepository",
)
SecureDatabase = _import_attr_optional(
    ("backend.modules.systeme.database", "modules.systeme.database", "database"),
    "SecureDatabase",
)

build_frontend_contract = _import_attr_optional(
    ("backend.modules.systeme.frontend_contract", "modules.systeme.frontend_contract", "frontend_contract"),
    "build_frontend_contract",
)
build_diagnostic_contract = _import_attr_optional(
    ("backend.modules.systeme.frontend_contract", "modules.systeme.frontend_contract", "frontend_contract"),
    "build_diagnostic_contract",
)

resoudre_inconnues_systeme = _import_attr_optional(
    (
        "backend.ensemble.resolution_inconnues",
        "ensemble.resolution_inconnues",
        "backend.modules.systeme.resolution_inconnues",
        "modules.systeme.resolution_inconnues",
        "resolution_inconnues",
    ),
    "resoudre_inconnues_systeme",
)

diagnostiquer_json_sthome = _import_attr_optional(
    ("backend.modules.systeme.json_diagnostic", "modules.systeme.json_diagnostic", "json_diagnostic"),
    "diagnostiquer_json_sthome",
)

generer_graphiques_mecaniques = _import_attr_optional(
    ("backend.modules.systeme.mechanical_graphs", "modules.systeme.mechanical_graphs", "mechanical_graphs"),
    "generer_graphiques_mecaniques",
)
construire_dossier_cao_sthome = _import_attr_optional(
    ("backend.modules.systeme.cao_dossier", "modules.systeme.cao_dossier", "cao_dossier"),
    "construire_dossier_cao_sthome",
)

dimensionner_pieces_completes = _import_attr_optional(
    ("backend.modules.systeme.definition_pieces", "modules.systeme.definition_pieces", "definition_pieces"),
    "dimensionner_pieces_completes",
)
dimensionner_pieces_moteur_thermique = _import_attr_optional(
    ("backend.modules.systeme.orchestrateur_pieces", "modules.systeme.orchestrateur_pieces", "orchestrateur_pieces"),
    "dimensionner_pieces_moteur_thermique",
)
enrichir_rapport_puissance_avec_pieces = _import_attr_optional(
    ("backend.modules.systeme.orchestrateur_pieces", "modules.systeme.orchestrateur_pieces", "orchestrateur_pieces"),
    "enrichir_rapport_puissance_avec_pieces",
)

valider_candidate = _import_attr_optional(
    ("backend.modules.systeme.validation_candidates", "modules.systeme.validation_candidates", "validation_candidates"),
    "valider_candidate",
)

DriveChainGenerator = _import_attr_optional(
    ("backend.modules.systeme.system_generator", "modules.systeme.system_generator", "system_generator"),
    "DriveChainGenerator",
)
DimensioningEngine = _import_attr_optional(
    ("backend.modules.systeme.engineering_model", "modules.systeme.engineering_model", "engineering_model"),
    "DimensioningEngine",
)

# Services projets déjà existants. Ils restent appelables via cette façade.
_system_services = _import_module_optional(
    ("backend.modules.systeme.system_services", "modules.systeme.system_services", "system_services")
)

# Orchestrateur ensemble.
STHO_ME = _import_attr_optional(
    ("backend.ensemble.STHO_ME", "ensemble.STHO_ME", "STHO_ME"),
    "STHO_ME",
)

# Optimisation ensemble, optionnelle.
optimiser_rapport_sthome = _import_attr_optional(
    ("backend.ensemble.optimisation", "ensemble.optimisation", "optimisation"),
    "optimiser_rapport_sthome",
)
OptimisationSysteme = _import_attr_optional(
    ("backend.ensemble.optimisation", "ensemble.optimisation", "optimisation"),
    "OptimisationSysteme",
)


# =============================================================================
# Dataclasses publiques
# =============================================================================

@dataclass
class MainSystemeOptions:
    """Options d'exécution de l'orchestrateur principal."""

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


@dataclass
class PipelineStep:
    name: str
    status: str
    message: str | None = None
    error: str | None = None
    duration_ms: float | None = None


# =============================================================================
# Helpers génériques
# =============================================================================

def _is_finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _num(value: Any) -> float | None:
    if _is_finite(value):
        return float(value)
    try:
        if isinstance(value, str) and value.strip():
            out = float(value.replace(",", "."))
            return out if math.isfinite(out) else None
    except Exception:
        return None
    return None


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple, set)) else []


def _deepcopy_jsonable(value: Any) -> Any:
    try:
        return copy.deepcopy(value)
    except Exception:
        return _jsonable(value)


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
            public = {k: v for k, v in vars(value).items() if not str(k).startswith("_") and not callable(v)}
            return {"type": type(value).__name__, "attributs": _jsonable(public, depth=depth + 1, max_depth=max_depth)}
        except Exception:
            pass
    return {"type": type(value).__name__, "repr": repr(value)[:300]}


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
    if not isinstance(path, str) or not path:
        return
    parts = [p for p in path.split(".") if p]
    cur = data
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _merge_dicts(*items: Mapping[str, Any] | None) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for item in items:
        if not isinstance(item, Mapping):
            continue
        for key, value in item.items():
            if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
                out[key] = _merge_dicts(out[key], value)  # type: ignore[arg-type]
            else:
                out[key] = _deepcopy_jsonable(value)
    return out


def _push(report: Dict[str, Any], category: str, name: str, reason: str, **extra: Any) -> None:
    item = {"nom": str(name), "raison": str(reason)}
    item.update({k: v for k, v in extra.items() if v is not None})
    report.setdefault("inconnues", {}).setdefault(category, []).append(item)


def _push_alert(report: Dict[str, Any], category: str, name: str, detail: str, **extra: Any) -> None:
    item = {"nom": str(name), "detail": str(detail)}
    item.update({k: v for k, v in extra.items() if v is not None})
    report.setdefault("alertes", {}).setdefault(category, []).append(item)


def _dedup_report_lists(report: Dict[str, Any]) -> None:
    inc = report.setdefault("inconnues", {})
    for category in ("impossibles", "partielles", "bloquantes", "non_bloquantes"):
        seen: set[tuple[str, str]] = set()
        out = []
        for item in list(inc.get(category, []) or []):
            if not isinstance(item, Mapping):
                continue
            key = (str(item.get("nom", "")), str(item.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(dict(item))
        inc[category] = out
    alerts = report.setdefault("alertes", {})
    for category, values in list(alerts.items()):
        seen: set[tuple[str, str]] = set()
        out = []
        for item in list(values or []):
            if not isinstance(item, Mapping):
                continue
            key = (str(item.get("nom", "")), str(item.get("detail", "")))
            if key not in seen:
                seen.add(key)
                out.append(dict(item))
        alerts[category] = out


def _merge_unknowns(dst: Dict[str, Any], src: Any, *, prefix: str) -> None:
    if not isinstance(src, Mapping):
        return
    inc = src.get("inconnues")
    if not isinstance(inc, Mapping):
        return
    for category in ("impossibles", "partielles", "bloquantes", "non_bloquantes"):
        for item in list(inc.get(category, []) or []):
            if isinstance(item, Mapping):
                _push(
                    dst,
                    category,
                    f"{prefix}::{item.get('nom', '')}",
                    str(item.get("raison") or item.get("reason") or item.get("detail") or ""),
                    path=item.get("path") or item.get("champ"),
                )


def _extract_power_request(config: Mapping[str, Any]) -> tuple[float | None, str]:
    if get_first_available_value is not None:
        try:
            value, _path = get_first_available_value("puissance_sortie_moteur_electrique_w", config, default=None)
            if _num(value) is not None:
                return float(value), "w"
            value_kw, _path_kw = get_first_available_value("puissance_sortie_moteur_electrique_kw", config, default=None)
            if _num(value_kw) is not None:
                return float(value_kw), "kw"
        except Exception:
            pass
    for path in (
        "puissance_sortie_moteur_electrique_w",
        "puissance_sortie_w",
        "puissance_demandee_w",
        "sortie.puissance_w",
        "entrees.puissance_sortie_w",
    ):
        value = _num(_get_path(config, path))
        if value is not None:
            return value, "w"
    for path in (
        "puissance_sortie_moteur_electrique_kw",
        "puissance_sortie_kw",
        "puissance_demandee_kw",
        "puissance_traction_kw",
        "sortie.puissance_kw",
        "entrees.puissance_sortie_kw",
    ):
        value = _num(_get_path(config, path))
        if value is not None:
            return value, "kw"
    return None, "kw"


def _power_to_w(value: float | None, unit: str) -> float | None:
    if value is None:
        return None
    return float(value) * 1000.0 if unit.lower() == "kw" else float(value)


def _extract_cahier_des_charges(config: Mapping[str, Any]) -> Dict[str, Any]:
    for path in (
        "cahier_des_charges",
        "cdc",
        "criteres_conception",
        "meta.cahier_des_charges",
        "meta.meta_utilisateur.cahier_des_charges",
    ):
        value = _get_path(config, path)
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _extract_known_data(config: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for path in (
        "donnees_connues",
        "known",
        "known_data",
        "entrees.donnees_connues",
        "parametres",
        "composants_definition",
    ):
        value = _get_path(config, path)
        if isinstance(value, Mapping):
            out = _merge_dicts(out, value)
    # Les valeurs au niveau racine peuvent aussi être des données connues.
    for key, value in config.items():
        if key not in {"donnees_connues", "known", "cahier_des_charges", "espace_recherche", "contraintes", "composants", "sous_systemes"}:
            if not isinstance(value, Mapping):
                out.setdefault(str(key), value)
    return out


def _looks_like_power_optimization(config: Mapping[str, Any]) -> bool:
    return isinstance(config.get("espace_recherche"), Mapping) or isinstance(_get_path(config, "analyse_puissance.espace_recherche"), Mapping)


def _count_unknowns(report: Mapping[str, Any]) -> int:
    inc = report.get("inconnues") if isinstance(report, Mapping) else None
    if not isinstance(inc, Mapping):
        return 0
    return sum(len(v or []) for v in inc.values() if isinstance(v, list))


def _call_service(name: str, *args: Any, **kwargs: Any) -> Any:
    if _system_services is None:
        raise RuntimeError("system_services non importable")
    fn = getattr(_system_services, name, None)
    if not callable(fn):
        raise RuntimeError(f"system_services.{name} absent")
    return fn(*args, **kwargs)


# =============================================================================
# Orchestrateur principal
# =============================================================================

@dataclass
class MainSysteme:
    config: Dict[str, Any] = field(default_factory=dict)
    options: MainSystemeOptions = field(default_factory=MainSystemeOptions)
    repository: Any | None = None
    database: Any | None = None

    @classmethod
    def depuis_config(
        cls,
        config: Mapping[str, Any] | None,
        *,
        options: MainSystemeOptions | Mapping[str, Any] | None = None,
        repository: Any | None = None,
        database: Any | None = None,
    ) -> "MainSysteme":
        opts = _coerce_options(options)
        return cls(config=dict(config or {}), options=opts, repository=repository, database=database)

    @classmethod
    def depuis_json(
        cls,
        path: str | Path,
        *,
        options: MainSystemeOptions | Mapping[str, Any] | None = None,
        repository: Any | None = None,
        database: Any | None = None,
    ) -> "MainSysteme":
        p = Path(path).expanduser().resolve()
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        if not isinstance(data, Mapping):
            raise ValueError("Le JSON de configuration doit contenir un objet racine.")
        opts = _coerce_options(options)
        cfg = dict(data)
        cfg.setdefault("meta", {})
        if isinstance(cfg["meta"], dict):
            cfg["meta"].setdefault("source_json", str(p))
        return cls(config=cfg, options=opts, repository=repository, database=database)

    def analyser(self, **overrides: Any) -> Dict[str, Any]:
        opts = _merge_options(self.options, overrides)
        report: Dict[str, Any] = self._new_report(opts)
        config = _merge_dicts(self.config)
        if opts.project_id:
            config.setdefault("project_id", opts.project_id)

        self._load_repository_data(config, report, opts)

        # 1) Analyse puissance stricte / optimisation depuis puissance.
        rapport_puissance = self._run_step(report, "analyse_puissance_sortie", lambda: self._analyse_puissance(config, opts))
        if isinstance(rapport_puissance, Mapping):
            report["analyse_puissance_sortie"] = _jsonable(rapport_puissance)
            _merge_unknowns(report, rapport_puissance, prefix="analyse_puissance_sortie")

        # 2) Orchestration système complète via STHO_ME.
        rapport_sthome = self._run_step(report, "stho_me", lambda: self._analyse_sthome(config, opts))
        if isinstance(rapport_sthome, Mapping):
            report["stho_me"] = _jsonable(rapport_sthome)
            _merge_unknowns(report, rapport_sthome, prefix="stho_me")
        else:
            rapport_sthome = {}

        # 3) Fusion initiale : STHO_ME prioritaire, puis analyse puissance.
        report = self._compose_report(report, rapport_sthome, rapport_puissance)

        # 4) Résolution d'inconnues avec candidats / repository / CDC.
        if opts.resolve_unknowns and not isinstance(report.get("resolution_inconnues"), Mapping):
            resolution = self._run_step(report, "resolution_inconnues", lambda: self._resolve_unknowns(config, report, opts))
            if resolution is not None:
                resolution_dict = _jsonable(resolution)
                report["resolution_inconnues"] = resolution_dict
                config_completee = _get_path(resolution_dict, "config_completee")
                if not isinstance(config_completee, Mapping):
                    config_completee = _get_path(resolution_dict, "payload_resolu")
                if isinstance(config_completee, Mapping):
                    config = _merge_dicts(config, config_completee)
                rapport_apres = _get_path(resolution_dict, "rapport_apres")
                if isinstance(rapport_apres, Mapping):
                    report = self._compose_report(report, rapport_apres, None)
                _merge_unknowns(report, resolution_dict, prefix="resolution_inconnues")

        # 5) Optimisation globale si disponible.
        if opts.optimize:
            optimisation = self._run_step(report, "optimisation", lambda: self._optimize(report, opts))
            if isinstance(optimisation, Mapping):
                report["optimisation"] = _jsonable(optimisation)
                _merge_unknowns(report, optimisation, prefix="optimisation")

        # 6) Dimensionnement / consolidation de pièces si le rapport contient les entrées minimales.
        if opts.enrichir_pieces:
            pieces = self._run_step(report, "pieces", lambda: self._enrich_pieces(report, config, opts))
            if isinstance(pieces, Mapping):
                report["pieces_systeme"] = _jsonable(pieces)
                for key in ("inventaire", "construction_pieces", "rapports_pieces", "objets_serialises"):
                    if key in pieces and key not in report:
                        report[key] = _jsonable(pieces[key])
                _merge_unknowns(report, pieces, prefix="pieces")

        # 7) Validation chaîne de puissance.
        if opts.validate_chain:
            validation = self._run_step(report, "validation_chaine", lambda: self._validate_chain(report, config, opts))
            if isinstance(validation, Mapping):
                report["validation_chaine_100kw"] = _jsonable(validation)

        # 8) Graphiques mécaniques.
        if opts.mechanical_graphs:
            graphs = self._run_step(report, "mechanical_graphs", lambda: self._mechanical_graphs(report, opts))
            if isinstance(graphs, Mapping):
                report["mechanical_graphs"] = _jsonable(graphs)

        # 9) Dossier CAO de préconception.
        if opts.cao_dossier:
            cao = self._run_step(report, "cao_dossier", lambda: self._cao_dossier(report, opts))
            if isinstance(cao, Mapping):
                report["cao_dossier"] = _jsonable(cao)
                report["cao"] = _merge_dicts(_safe_dict(report.get("cao")), _safe_dict(cao.get("resume")))

        # 10) Diagnostic causal.
        if opts.diagnostic:
            diagnostic = self._run_step(report, "diagnostic", lambda: self._diagnostic(report, opts))
            if isinstance(diagnostic, Mapping):
                report["diagnostic"] = _jsonable(diagnostic)

        # 11) Contrat frontend.
        if opts.frontend_contract:
            frontend = self._run_step(report, "frontend_contract", lambda: self._frontend_contract(report, opts))
            if isinstance(frontend, Mapping):
                report["frontend"] = _jsonable(frontend)

        # 12) Synthèse finale.
        self._finalize_synthesis(report, config, opts)

        # 13) Sauvegarde.
        if opts.save_repository or opts.save_database:
            stockage = self._run_step(report, "stockage", lambda: self._save(report, config, opts))
            if isinstance(stockage, Mapping):
                report["stockage"] = _jsonable(stockage)

        _dedup_report_lists(report)
        return _jsonable(report)

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _new_report(self, opts: MainSystemeOptions) -> Dict[str, Any]:
        return {
            "meta": {
                "module": "backend.modules.main.main_systeme",
                "role": "orchestrateur_principal_modules_systeme_sthome",
                "project_id": opts.project_id,
                "strict": opts.strict,
                "report_name": opts.report_name,
            },
            "entrees": _jsonable(self.config),
            "imports": _jsonable(_IMPORT_ERRORS),
            "pipeline": [],
            "sous_systemes": {},
            "rapports": {},
            "synthese": {},
            "inconnues": {"impossibles": [], "partielles": [], "bloquantes": [], "non_bloquantes": []},
            "alertes": {},
            "notes_modele": [
                "main_systeme.py orchestre les modules systeme sans recopier leurs calculs internes.",
                "Aucune valeur metier cachee n'est injectee par cet orchestrateur.",
            ],
        }

    def _run_step(self, report: Dict[str, Any], name: str, fn: Callable[[], Any]) -> Any:
        import time

        start = time.perf_counter()
        try:
            out = fn()
            status = "ok" if out is not None else "skipped"
            report.setdefault("pipeline", []).append(_jsonable(PipelineStep(name=name, status=status, duration_ms=(time.perf_counter() - start) * 1000.0)))
            return out
        except Exception as exc:  # l'orchestrateur doit continuer
            message = f"{type(exc).__name__}: {exc}"
            step = PipelineStep(name=name, status="error", error=message, duration_ms=(time.perf_counter() - start) * 1000.0)
            report.setdefault("pipeline", []).append(_jsonable(step))
            _push(report, "partielles", name, message)
            if self.options.include_traceback:
                report.setdefault("debug", {}).setdefault("tracebacks", {})[name] = traceback.format_exc()
            return None

    def _load_repository_data(self, config: Dict[str, Any], report: Dict[str, Any], opts: MainSystemeOptions) -> None:
        if self.repository is None and opts.project_id and SystemDataRepository is not None:
            try:
                self.repository = SystemDataRepository()
            except Exception as exc:
                _push(report, "partielles", "repository", f"Repository non initialisable: {exc}")
        if self.repository is not None and opts.project_id:
            try:
                repo_params = self.repository.get_project_parameters(opts.project_id)
                if isinstance(repo_params, Mapping) and repo_params:
                    config.update(_merge_dicts(repo_params, config))
                    report["repository"] = {"project_id": opts.project_id, "loaded": True}
            except Exception as exc:
                _push(report, "partielles", "repository", f"Lecture repository impossible: {exc}")

    def _analyse_puissance(self, config: Mapping[str, Any], opts: MainSystemeOptions) -> Dict[str, Any] | None:
        p, unit = _extract_power_request(config)
        if p is None:
            return None
        known = _extract_known_data(config)
        type_sortie = str(config.get("type_sortie") or _get_path(config, "analyse_puissance.type_sortie") or "sortie_utilisateur")
        if _looks_like_power_optimization(config) and optimiser_puissance_sortie is not None:
            espace = _safe_dict(config.get("espace_recherche")) or _safe_dict(_get_path(config, "analyse_puissance.espace_recherche"))
            contraintes = _safe_dict(config.get("contraintes")) or _safe_dict(_get_path(config, "analyse_puissance.contraintes"))
            report = optimiser_puissance_sortie(
                p,
                unit,
                type_sortie=type_sortie,
                donnees_connues=known,
                espace_recherche=espace,
                contraintes=contraintes,
                max_candidats=int(config.get("max_candidats", _get_path(config, "analyse_puissance.max_candidats", 50000))),
            )
            if enrichir_rapport_puissance_avec_pieces is not None and opts.enrichir_pieces:
                try:
                    report = enrichir_rapport_puissance_avec_pieces(report)
                except Exception:
                    pass
            return report
        if analyser_puissance_sortie is not None:
            return analyser_puissance_sortie(p, unit, type_sortie=type_sortie, donnees_connues=known)
        return None

    def _analyse_sthome(self, config: Mapping[str, Any], opts: MainSystemeOptions) -> Dict[str, Any] | None:
        if STHO_ME is None:
            return None
        if hasattr(STHO_ME, "depuis_config"):
            systeme = STHO_ME.depuis_config(dict(config))
        else:
            systeme = STHO_ME(config=dict(config)) if callable(STHO_ME) else None
        if systeme is None:
            return None
        analyser = getattr(systeme, "analyser", None)
        if not callable(analyser):
            return None
        # STHO_ME possède déjà ses propres options ; on évite de dupliquer les étapes ici.
        try:
            return analyser(
                repository=self.repository,
                resolve_unknowns=opts.resolve_unknowns,
                optimize=False,
                frontend_contract=False,
                strict=opts.strict,
            )
        except TypeError:
            try:
                return analyser(repository=self.repository, frontend_contract=False)
            except TypeError:
                return analyser()

    def _compose_report(self, report: Dict[str, Any], rapport_sthome: Any, rapport_puissance: Any) -> Dict[str, Any]:
        base = report
        if isinstance(rapport_sthome, Mapping):
            base["rapports"]["stho_me"] = _jsonable(rapport_sthome)
            for key in ("sous_systemes", "synthese", "liaisons", "cao", "inventaire", "construction_pieces", "rapports_pieces", "objets_serialises", "resolution_inconnues", "donnees_auto_completees", "tracabilite"):
                value = rapport_sthome.get(key)
                if isinstance(value, Mapping):
                    base[key] = _merge_dicts(_safe_dict(base.get(key)), value)
        if isinstance(rapport_puissance, Mapping):
            base["rapports"]["analyse_puissance_sortie"] = _jsonable(rapport_puissance)
            # Remontées utiles pour les modules qui lisent des chemins standard.
            power = _get_path(rapport_puissance, "analyse_base.calculs.puissance_sortie.w")
            if power is None:
                power = _get_path(rapport_puissance, "calculs.puissance_sortie.w")
            if _num(power) is not None:
                base.setdefault("synthese", {}).setdefault("moteur_electrique", {})["puissance_sortie_w"] = float(power)
            selected = _get_path(rapport_puissance, "selection")
            if isinstance(selected, Mapping):
                base.setdefault("analyse_puissance_selection", selected)
        return base

    def _resolve_unknowns(self, config: Mapping[str, Any], report: Mapping[str, Any], opts: MainSystemeOptions) -> Any:
        if resoudre_inconnues_systeme is None:
            return None
        cdc = _extract_cahier_des_charges(config)

        def recalculer(cfg: Dict[str, Any]) -> Dict[str, Any]:
            nested_opts = MainSystemeOptions(
                project_id=opts.project_id,
                strict=opts.strict,
                resolve_unknowns=False,
                optimize=False,
                validate_chain=False,
                diagnostic=False,
                mechanical_graphs=False,
                cao_dossier=False,
                frontend_contract=False,
                save_repository=False,
                save_database=False,
                enrichir_pieces=False,
                include_traceback=opts.include_traceback,
                report_name=opts.report_name,
            )
            return MainSysteme.depuis_config(cfg, options=nested_opts, repository=self.repository, database=self.database).analyser()

        def optimiser(rep: Dict[str, Any]) -> Dict[str, Any]:
            if optimiser_rapport_sthome is not None:
                out = optimiser_rapport_sthome(rapport_backend=rep)
                return out if isinstance(out, dict) else {"resultat": _jsonable(out)}
            return {"synthese_optimisation": {"score_global": _score_report(rep)}}

        try:
            result = resoudre_inconnues_systeme(
                dict(config),
                dict(report),
                cdc,
                repository=self.repository,
                project_id=opts.project_id,
                recalculer=recalculer,
                optimiser=optimiser if opts.optimize else None,
                strict=opts.strict,
                mode="strict" if opts.strict else "projet",
                max_iterations=opts.max_resolution_iterations,
            )
        except TypeError:
            result = resoudre_inconnues_systeme(
                config=dict(config),
                rapport=dict(report),
                cahier_des_charges=cdc,
                repository=self.repository,
                project_id=opts.project_id,
                recalculer=recalculer,
                optimiser=optimiser if opts.optimize else None,
                strict=opts.strict,
                max_iterations=opts.max_resolution_iterations,
            )
        return result.en_dict() if hasattr(result, "en_dict") else result

    def _optimize(self, report: Mapping[str, Any], opts: MainSystemeOptions) -> Dict[str, Any] | None:
        if optimiser_rapport_sthome is not None:
            out = optimiser_rapport_sthome(rapport_backend=dict(report), strict=opts.strict)
            return out if isinstance(out, dict) else {"resultat": _jsonable(out)}
        if OptimisationSysteme is not None:
            obj = OptimisationSysteme()
            for method_name in ("optimiser", "analyser", "calculer"):
                method = getattr(obj, method_name, None)
                if callable(method):
                    out = method(dict(report))
                    return out if isinstance(out, dict) else {"resultat": _jsonable(out)}
        return {
            "synthese_optimisation": {
                "score_global": _score_report(report),
                "mode": "fallback_score_sans_optimiseur",
            },
            "notes_modele": ["Optimiseur ensemble absent : score de cohérence minimal calculé depuis inconnues/validation."],
        }

    def _enrich_pieces(self, report: Mapping[str, Any], config: Mapping[str, Any], opts: MainSystemeOptions) -> Dict[str, Any] | None:
        if dimensionner_pieces_moteur_thermique is None and dimensionner_pieces_completes is None:
            return None
        src = _merge_dicts(config, report)
        p = _first_number(src, (
            "synthese.moteur_thermique.puissance_requise_W",
            "synthese.systeme.puissance_moteur_thermique_arbre_w",
            "validation_chaine_100kw.valeurs.puissance_moteur_thermique_arbre_w",
            "resolution_inconnues.config_completee.puissance_moteur_thermique_arbre_w",
            "puissance_moteur_thermique_arbre_w",
        ))
        rpm = _first_number(src, (
            "synthese.moteur_thermique.rpm_nominal",
            "validation_chaine_100kw.valeurs.rpm_moteur_thermique",
            "rpm_moteur",
            "rpm_moteur_nominal",
        ))
        n_cyl = _first_number(src, ("synthese.moteur_thermique.nombre_cylindres", "nombre_cylindres", "n_cyl"))
        pmax = _first_number(src, ("synthese.moteur_thermique.pression_max_pa", "pression_max_pa", "pmax_pa"))
        if p is None or rpm is None or n_cyl is None or pmax is None:
            return {
                "active": False,
                "inconnues": {
                    "partielles": [
                        {
                            "nom": "pieces_moteur_thermique",
                            "raison": "Requiert puissance thermique arbre, rpm, nombre cylindres et pression max.",
                        }
                    ]
                },
            }
        kwargs = {
            "puissance_cible_w": p,
            "regime_tr_min": rpm,
            "n_cyl": int(round(n_cyl)),
            "pression_max_pa": pmax,
            "pme_pa": _first_number(src, ("synthese.moteur_thermique.pme_pa", "pme_pa")),
            "alesage_m": _first_number(src, ("synthese.moteur_thermique.alesage_m", "alesage_m")),
            "course_m": _first_number(src, ("synthese.moteur_thermique.course_m", "course_m")),
            "longueur_bielle_m": _first_number(src, ("synthese.moteur_thermique.longueur_bielle_m", "longueur_bielle_m")),
            "rapport_systeme": dict(report),
            "pieces_definition": _safe_dict(config.get("pieces_definition")) or _safe_dict(_get_path(config, "pieces")),
            "save_to_db": False,
        }
        fn = dimensionner_pieces_completes or dimensionner_pieces_moteur_thermique
        return fn(**kwargs)

    def _validate_chain(self, report: Mapping[str, Any], config: Mapping[str, Any], opts: MainSystemeOptions) -> Dict[str, Any] | None:
        if valider_chaine_puissance_sthome is None:
            return None
        p, unit = _extract_power_request(config)
        p_w = _power_to_w(p, unit)
        if p_w is None:
            p_w = _first_number(report, (
                "synthese.moteur_electrique.puissance_sortie_w",
                "analyse_puissance_sortie.calculs.puissance_sortie.w",
                "analyse_puissance_sortie.analyse_base.calculs.puissance_sortie.w",
            ))
        if p_w is None:
            return {
                "ok": False,
                "score_chaine_100": 0.0,
                "points_bloquants": [{"name": "puissance_sortie_absente", "reason": "Aucune puissance de sortie à valider."}],
            }
        return valider_chaine_puissance_sthome(dict(report), puissance_sortie_w=float(p_w), strict=opts.strict)

    def _mechanical_graphs(self, report: Mapping[str, Any], opts: MainSystemeOptions) -> Dict[str, Any] | None:
        if generer_graphiques_mecaniques is None:
            return None
        return generer_graphiques_mecaniques(dict(report), strict=opts.strict)

    def _cao_dossier(self, report: Mapping[str, Any], opts: MainSystemeOptions) -> Dict[str, Any] | None:
        if construire_dossier_cao_sthome is None:
            return None
        return construire_dossier_cao_sthome(dict(report), strict=opts.strict)

    def _diagnostic(self, report: Mapping[str, Any], opts: MainSystemeOptions) -> Dict[str, Any] | None:
        if diagnostiquer_json_sthome is None:
            return None
        return diagnostiquer_json_sthome(data=dict(report), source_name="main_systeme", mode="rapport_sthome", strict=opts.strict)

    def _frontend_contract(self, report: Mapping[str, Any], opts: MainSystemeOptions) -> Dict[str, Any] | None:
        if build_frontend_contract is None:
            return None
        return build_frontend_contract(dict(report), project_id=opts.project_id)

    def _save(self, report: Mapping[str, Any], config: Mapping[str, Any], opts: MainSystemeOptions) -> Dict[str, Any]:
        saved: Dict[str, Any] = {"repository": None, "database": None, "errors": []}
        project_id = opts.project_id or str(config.get("project_id") or "default")

        if opts.save_repository:
            repo = self.repository
            if repo is None and SystemDataRepository is not None:
                repo = SystemDataRepository()
                self.repository = repo
            if repo is not None:
                try:
                    if hasattr(repo, "save_optimization_run") and isinstance(report.get("optimisation"), Mapping):
                        repo.save_optimization_run(project_id=project_id, run=report.get("optimisation"))
                    if hasattr(repo, "save_generated_candidate") and isinstance(report.get("resolution_inconnues"), Mapping):
                        for cand in _safe_list(_get_path(report, "resolution_inconnues.candidates"))[:200]:
                            repo.save_generated_candidate(project_id=project_id, candidate=cand)
                    saved["repository"] = {"project_id": project_id, "saved": True}
                except Exception as exc:
                    saved["errors"].append(f"repository: {exc}")

        if opts.save_database:
            db = self.database
            if db is None and SecureDatabase is not None:
                db = SecureDatabase()
                self.database = db
            if db is not None:
                try:
                    if hasattr(db, "save_main_report"):
                        saved["database"] = db.save_main_report(dict(report), report_name=opts.report_name)
                    elif hasattr(db, "save_record"):
                        saved["database"] = {"main_report": db.save_record("main_report", opts.report_name, dict(report))}
                except Exception as exc:
                    saved["errors"].append(f"database: {exc}")
        return saved

    def _finalize_synthesis(self, report: Dict[str, Any], config: Mapping[str, Any], opts: MainSystemeOptions) -> None:
        p_req, unit = _extract_power_request(config)
        p_req_w = _power_to_w(p_req, unit)
        chain = _safe_dict(report.get("validation_chaine_100kw"))
        chain_values = _safe_dict(chain.get("valeurs"))
        synth = _safe_dict(report.get("synthese"))
        synth_system = _safe_dict(synth.get("systeme"))
        if p_req_w is not None:
            synth.setdefault("moteur_electrique", {})["puissance_sortie_demandee_w"] = p_req_w
        for src_key, dst_key in (
            ("puissance_bus_dc_design_w", "P_bus_dc_design_w"),
            ("courant_bus_dc_a", "courant_bus_dc_a"),
            ("puissance_alternateur_electrique_w", "puissance_alternateur_electrique_w"),
            ("puissance_moteur_thermique_arbre_w", "puissance_moteur_thermique_arbre_w"),
        ):
            val = _num(chain_values.get(src_key))
            if val is not None:
                synth_system[dst_key] = val
        if chain:
            synth_system["validation_chaine_ok"] = bool(chain.get("ok"))
            synth_system["score_chaine_100"] = chain.get("score_chaine_100")
        report["synthese"] = synth
        report["synthese"]["systeme"] = synth_system
        report["coherence_systeme"] = _merge_dicts(
            _safe_dict(report.get("coherence_systeme")),
            {
                "score_global": _score_report(report),
                "inconnues_total": _count_unknowns(report),
                "validation_chaine_ok": bool(chain.get("ok")) if chain else None,
            },
        )
        if p_req_w is None:
            _push(report, "impossibles", "puissance_sortie", "Aucune puissance de sortie utilisateur n'a été fournie.")

    # ------------------------------------------------------------------
    # Services façade
    # ------------------------------------------------------------------

    def charger_data_contract(self, project_id: str | None = None) -> Dict[str, Any]:
        project = project_id or self.options.project_id
        if not project:
            raise ValueError("project_id obligatoire pour charger_data_contract")
        try:
            return _call_service("charger_data_contract", project, repository=self.repository)
        except Exception:
            opts = _merge_options(self.options, {"project_id": project, "frontend_contract": True})
            return self.depuis_config(self.config, options=opts, repository=self.repository, database=self.database).analyser().get("frontend", {})

    def resoudre_inconnues_project(self, project_id: str | None = None) -> Dict[str, Any]:
        project = project_id or self.options.project_id
        if not project:
            raise ValueError("project_id obligatoire pour resoudre_inconnues_project")
        return _call_service("resoudre_inconnues_project", project, repository=self.repository)

    def recalculer_project(self, project_id: str | None = None) -> Dict[str, Any]:
        project = project_id or self.options.project_id
        if not project:
            raise ValueError("project_id obligatoire pour recalculer_project")
        return _call_service("recalculer_project", project, repository=self.repository)

    def optimiser_project(self, project_id: str | None = None) -> Dict[str, Any]:
        project = project_id or self.options.project_id
        if not project:
            raise ValueError("project_id obligatoire pour optimiser_project")
        return _call_service("optimiser_project", project, repository=self.repository)


# =============================================================================
# Fonctions publiques de compatibilité
# =============================================================================

def _coerce_options(options: MainSystemeOptions | Mapping[str, Any] | None) -> MainSystemeOptions:
    if isinstance(options, MainSystemeOptions):
        return options
    if isinstance(options, Mapping):
        allowed = set(MainSystemeOptions.__dataclass_fields__.keys())
        return MainSystemeOptions(**{k: v for k, v in options.items() if k in allowed})
    return MainSystemeOptions()


def _merge_options(base: MainSystemeOptions, overrides: Mapping[str, Any] | None) -> MainSystemeOptions:
    if not overrides:
        return base
    data = asdict(base)
    for key, value in overrides.items():
        if key in data and value is not None:
            data[key] = value
    return MainSystemeOptions(**data)


def _score_report(report: Mapping[str, Any]) -> float:
    score = 1.0
    unknowns = _count_unknowns(report)
    score -= min(0.45, 0.015 * unknowns)
    chain = report.get("validation_chaine_100kw")
    if isinstance(chain, Mapping):
        if chain.get("ok") is False:
            score -= 0.25
        chain_score = _num(chain.get("score_chaine_100"))
        if chain_score is not None:
            score = min(score, max(0.0, chain_score / 100.0))
    cao = report.get("cao")
    if isinstance(cao, Mapping) and cao.get("available") is False:
        score -= 0.05
    return round(max(0.0, min(1.0, score)), 4)


def _first_number(data: Mapping[str, Any], paths: Iterable[str]) -> float | None:
    for path in paths:
        value = _num(_get_path(data, path))
        if value is not None:
            return value
    return None


def analyser_systeme_sthome(
    config: Mapping[str, Any] | None = None,
    *,
    options: MainSystemeOptions | Mapping[str, Any] | None = None,
    repository: Any | None = None,
    database: Any | None = None,
    **overrides: Any,
) -> Dict[str, Any]:
    """Point d'entrée principal utilisable par backend, GUI, tests ou scripts."""
    systeme = MainSysteme.depuis_config(config or {}, options=options, repository=repository, database=database)
    return systeme.analyser(**overrides)


def analyser_depuis_puissance(
    puissance: float,
    unite: str = "kw",
    *,
    donnees_connues: Mapping[str, Any] | None = None,
    cahier_des_charges: Mapping[str, Any] | None = None,
    espace_recherche: Mapping[str, Any] | None = None,
    contraintes: Mapping[str, Any] | None = None,
    options: MainSystemeOptions | Mapping[str, Any] | None = None,
    **overrides: Any,
) -> Dict[str, Any]:
    """Raccourci pour lancer tout le pipeline depuis une puissance de sortie."""
    config: Dict[str, Any] = {
        "puissance_sortie_kw" if str(unite).lower() == "kw" else "puissance_sortie_w": puissance,
        "donnees_connues": dict(donnees_connues or {}),
    }
    if cahier_des_charges:
        config["cahier_des_charges"] = dict(cahier_des_charges)
    if espace_recherche:
        config["espace_recherche"] = dict(espace_recherche)
    if contraintes:
        config["contraintes"] = dict(contraintes)
    return analyser_systeme_sthome(config, options=options, **overrides)


def analyser_100kw(
    *,
    donnees_connues: Mapping[str, Any] | None = None,
    cahier_des_charges: Mapping[str, Any] | None = None,
    espace_recherche: Mapping[str, Any] | None = None,
    contraintes: Mapping[str, Any] | None = None,
    options: MainSystemeOptions | Mapping[str, Any] | None = None,
    **overrides: Any,
) -> Dict[str, Any]:
    """Scénario de référence : 100 kW utiles en sortie moteur électrique."""
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


def charger_data_contract(project_id: str, repository: Any | None = None) -> Dict[str, Any]:
    return MainSysteme(options=MainSystemeOptions(project_id=project_id), repository=repository).charger_data_contract(project_id)


def resoudre_inconnues_project(project_id: str, repository: Any | None = None) -> Dict[str, Any]:
    return MainSysteme(options=MainSystemeOptions(project_id=project_id), repository=repository).resoudre_inconnues_project(project_id)


def recalculer_project(project_id: str, repository: Any | None = None) -> Dict[str, Any]:
    return MainSysteme(options=MainSystemeOptions(project_id=project_id), repository=repository).recalculer_project(project_id)


def optimiser_project(project_id: str, repository: Any | None = None) -> Dict[str, Any]:
    return MainSysteme(options=MainSystemeOptions(project_id=project_id), repository=repository).optimiser_project(project_id)


# Alias métier attendus possibles.
dimensionner_systeme_sthome = analyser_systeme_sthome
calculer_systeme_sthome = analyser_systeme_sthome
main_systeme = analyser_systeme_sthome
run_main_systeme = analyser_systeme_sthome


# =============================================================================
# CLI minimal
# =============================================================================

def _load_json_file(path: str | None) -> Dict[str, Any]:
    if not path:
        return {}
    p = Path(path).expanduser().resolve()
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Le fichier JSON doit contenir un objet racine.")
    return data


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Orchestrateur principal STHO-ME")
    parser.add_argument("--config", help="Chemin vers un JSON de configuration", default=None)
    parser.add_argument("--puissance-kw", type=float, default=None, help="Puissance utile de sortie en kW")
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--output", default=None, help="Chemin JSON de sortie")
    parser.add_argument("--non-strict", action="store_true")
    parser.add_argument("--no-resolve", action="store_true")
    parser.add_argument("--no-optimize", action="store_true")
    parser.add_argument("--save-db", action="store_true")
    parser.add_argument("--save-repository", action="store_true")
    args = parser.parse_args(argv)

    config = _load_json_file(args.config)
    if args.puissance_kw is not None:
        config["puissance_sortie_kw"] = args.puissance_kw

    opts = MainSystemeOptions(
        project_id=args.project_id,
        strict=not args.non_strict,
        resolve_unknowns=not args.no_resolve,
        optimize=not args.no_optimize,
        save_database=args.save_db,
        save_repository=args.save_repository,
    )
    report = analyser_systeme_sthome(config, options=opts)
    text = json.dumps(_jsonable(report), ensure_ascii=False, indent=2)
    if args.output:
        out = Path(args.output).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


__all__ = [
    "MainSystemeOptions",
    "PipelineStep",
    "MainSysteme",
    "analyser_systeme_sthome",
    "analyser_depuis_puissance",
    "analyser_100kw",
    "charger_data_contract",
    "resoudre_inconnues_project",
    "recalculer_project",
    "optimiser_project",
    "dimensionner_systeme_sthome",
    "calculer_systeme_sthome",
    "main_systeme",
    "run_main_systeme",
    "main",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
