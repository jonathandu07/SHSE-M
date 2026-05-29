# backend/ensemble/STHO_ME.py
from __future__ import annotations

"""
STHO_ME.py — orchestrateur système complet STHO-ME / SHSE-M
===============================================================================

Rôle
----
Ce fichier est l'orchestrateur haut niveau du système STHO-ME. Il ferme la chaîne :

    besoin utilisateur / mission
    -> puissance utile de sortie réellement disponible
    -> un ou plusieurs moteurs électriques de sortie
    -> bus DC + auxiliaires + pertes
    -> batterie tampon
    -> alternateur
    -> boîte à crabots
    -> un ou plusieurs moteurs thermiques dans leur cycle optimal
    -> architecture / pièces / CAO / graphiques / contrat frontend

Principes
---------
- La puissance demandée par l'utilisateur, par exemple 100 kW, est interprétée
  comme puissance utile de sortie, pas comme puissance alternateur ni puissance
  thermique.
- La batterie est un tampon énergétique : elle stabilise le bus DC et absorbe les
  pics, mais elle ne masque pas une génération sous-dimensionnée.
- La boîte à crabots maintient le moteur thermique dans son cycle optimal et adapte
  le régime alternateur.
- Aucun rendement, coefficient véhicule, matière, BSFC ou cote constructeur n'est
  inventé. Si une valeur manque, elle remonte dans `inconnues`.
- Le fichier reste importable même si certains composants spécialisés sont absents.

Entrée recommandée
------------------
    rapport = concevoir_systeme_stho_me({
        "sortie": {"puissance_sortie_max_w": 100_000},
        "moteurs_sortie": [{"nom": "traction", "puissance_max_w": 100_000,
                             "rendement_moteur": 0.94, "tension_bus_v": 400}],
        "moteurs_thermiques": [{"nom": "thermique", "puissance_arbre_max_w": 140_000,
                                 "rpm_optimal": 3000, "bsfc_g_kwh": 230}],
        "batterie": {"tension_nominale_v": 400, "capacite_nominale_kwh": 20},
        "transmission_generation": {"rendement_boite": 0.94,
                                      "rendement_alternateur": 0.92,
                                      "rendement_redressement": 0.96,
                                      "rpm_alternateur_cible": 9000,
                                      "rapports_boite": [2.5, 3.0, 3.2, 3.5]},
    })

Compatibilité
-------------
Le script accepte aussi les anciens blocs :
- config["composants"]["moteur_electrique"], config["analyses"], config["pieces"] ;
- puissance_sortie_kw / puissance_sortie_w à la racine ;
- orthographes architecture / architechture.
"""

import copy
import importlib
import inspect
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# =============================================================================
# Chemins / imports robustes
# =============================================================================

_THIS_FILE = Path(__file__).resolve() if "__file__" in globals() else Path.cwd() / "STHO_ME.py"
_THIS_DIR = _THIS_FILE.parent
for candidate in (
    _THIS_DIR,
    _THIS_DIR.parent,
    _THIS_DIR.parent.parent,
    Path.cwd(),
    Path("/mnt/data"),  # utile en sandbox, sans effet en projet si absent
):
    try:
        p = str(candidate.resolve())
    except Exception:
        p = str(candidate)
    if p not in sys.path:
        sys.path.insert(0, p)

_IMPORT_ERRORS: Dict[str, str] = {}


def _import_attr_optional(module_names: Sequence[str], attr: str, *, default: Any = None) -> Any:
    last_error: Optional[BaseException] = None
    for module_name in module_names:
        try:
            mod = importlib.import_module(module_name)
            return getattr(mod, attr)
        except BaseException as exc:
            last_error = exc
    _IMPORT_ERRORS[f"{attr}@{module_names[0] if module_names else '?'}"] = (
        f"{type(last_error).__name__}: {last_error}" if last_error else "chemins absents"
    )
    return default


# Résolution / optimisation / stratégie énergie.
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
CahierDesChargesSTHOME = _import_attr_optional(
    ("backend.ensemble.resolution_inconnues", "ensemble.resolution_inconnues", "resolution_inconnues"),
    "CahierDesChargesSTHOME",
)
optimiser_rapport_sthome = _import_attr_optional(
    ("backend.ensemble.optimisation", "ensemble.optimisation", "optimisation"),
    "optimiser_rapport_sthome",
)
OptimisationSysteme = _import_attr_optional(
    ("backend.ensemble.optimisation", "ensemble.optimisation", "optimisation"),
    "OptimisationSysteme",
)
calculer_strategie_couplage = _import_attr_optional(
    ("backend.ensemble.strategie_energie", "ensemble.strategie_energie", "strategie_energie"),
    "calculer_strategie_couplage",
)

# Orchestrateur global final déjà produit.
concevoir_systeme_hybride_final = _import_attr_optional(
    (
        "backend.ensemble.systeme_hybride_final",
        "ensemble.systeme_hybride_final",
        "systeme_hybride_final",
    ),
    "concevoir_systeme_hybride_final",
)

# Composants.
MoteurElectrique = _import_attr_optional(
    (
        "backend.components.moteur_electrique.moteur_electrique",
        "backend.components.moteur_electrique",
        "components.moteur_electrique.moteur_electrique",
        "components.moteur_electrique",
        "moteur_electrique",
    ),
    "MoteurElectrique",
)
concevoir_moteur_electrique = _import_attr_optional(
    (
        "backend.components.moteur_electrique.moteur_electrique",
        "backend.components.moteur_electrique",
        "components.moteur_electrique.moteur_electrique",
        "components.moteur_electrique",
        "moteur_electrique",
    ),
    "concevoir_moteur_electrique",
)
construire_moteur_electrique = _import_attr_optional(
    (
        "backend.components.moteur_electrique.moteur_electrique",
        "backend.components.moteur_electrique",
        "components.moteur_electrique.moteur_electrique",
        "components.moteur_electrique",
        "moteur_electrique",
    ),
    "construire_moteur_electrique",
)

Batterie = _import_attr_optional(
    (
        "backend.components.batterie.batterie",
        "backend.components.batterie",
        "components.batterie.batterie",
        "components.batterie",
        "batterie_robuste",
        "batterie",
    ),
    "Batterie",
)
concevoir_batterie = _import_attr_optional(
    (
        "backend.components.batterie.batterie",
        "backend.components.batterie",
        "components.batterie.batterie",
        "components.batterie",
        "batterie_robuste",
        "batterie",
    ),
    "concevoir_batterie",
)
construire_batterie = _import_attr_optional(
    (
        "backend.components.batterie.batterie",
        "backend.components.batterie",
        "components.batterie.batterie",
        "components.batterie",
        "batterie_robuste",
        "batterie",
    ),
    "construire_batterie",
)

Alternateur = _import_attr_optional(
    (
        "backend.components.alternateur.alternateur",
        "backend.components.alternateur",
        "components.alternateur.alternateur",
        "components.alternateur",
        "alternateur_systeme_integre",
        "alternateur",
    ),
    "Alternateur",
)
concevoir_alternateur = _import_attr_optional(
    (
        "backend.components.alternateur.alternateur",
        "backend.components.alternateur",
        "components.alternateur.alternateur",
        "components.alternateur",
        "alternateur_systeme_integre",
        "alternateur",
    ),
    "concevoir_alternateur",
)
construire_alternateur = _import_attr_optional(
    (
        "backend.components.alternateur.alternateur",
        "backend.components.alternateur",
        "components.alternateur.alternateur",
        "components.alternateur",
        "alternateur_systeme_integre",
        "alternateur",
    ),
    "construire_alternateur",
)

BoiteCrabots = _import_attr_optional(
    (
        "backend.components.boite_crabots.boite_crabots",
        "backend.components.boite_crabots",
        "components.boite_crabots.boite_crabots",
        "components.boite_crabots",
        "boite_crabots_cycle_optimal",
        "boite_crabots",
    ),
    "BoiteCrabots",
)
concevoir_boite_crabots = _import_attr_optional(
    (
        "backend.components.boite_crabots.boite_crabots",
        "backend.components.boite_crabots",
        "components.boite_crabots.boite_crabots",
        "components.boite_crabots",
        "boite_crabots_cycle_optimal",
        "boite_crabots",
    ),
    "concevoir_boite_crabots",
)
construire_boite_crabots = _import_attr_optional(
    (
        "backend.components.boite_crabots.boite_crabots",
        "backend.components.boite_crabots",
        "components.boite_crabots.boite_crabots",
        "components.boite_crabots",
        "boite_crabots_cycle_optimal",
        "boite_crabots",
    ),
    "construire_boite_crabots",
)

Architecture = _import_attr_optional(
    (
        "backend.components.architecture.architecture",
        "backend.components.architechture.architecture",
        "backend.components.architecture",
        "backend.components.architechture",
        "components.architecture.architecture",
        "components.architechture.architecture",
        "architecture_corrigee_complete",
        "architecture",
    ),
    "Architecture",
)
concevoir_architecture = _import_attr_optional(
    (
        "backend.components.architecture.architecture",
        "backend.components.architechture.architecture",
        "backend.components.architecture",
        "backend.components.architechture",
        "components.architecture.architecture",
        "components.architechture.architecture",
        "architecture_corrigee_complete",
        "architecture",
    ),
    "concevoir_architecture",
)

MoteurThermique = _import_attr_optional(
    (
        "backend.components.moteur_thermique.moteur_thermique",
        "backend.components.moteur_thermique",
        "components.moteur_thermique.moteur_thermique",
        "components.moteur_thermique",
        "orchestrateur_moteur_thermique_corrige",
        "moteur_thermique",
    ),
    "MoteurThermique",
)
OrchestrateurMoteurThermique = _import_attr_optional(
    (
        "backend.components.moteur_thermique.moteur_thermique",
        "backend.components.moteur_thermique.orchestrateur_moteur_thermique",
        "components.moteur_thermique.moteur_thermique",
        "components.moteur_thermique.orchestrateur_moteur_thermique",
        "orchestrateur_moteur_thermique_corrige",
        "moteur_thermique",
    ),
    "OrchestrateurMoteurThermique",
)
EntreesOrchestrateurMoteurThermique = _import_attr_optional(
    (
        "backend.components.moteur_thermique.moteur_thermique",
        "backend.components.moteur_thermique.orchestrateur_moteur_thermique",
        "components.moteur_thermique.moteur_thermique",
        "components.moteur_thermique.orchestrateur_moteur_thermique",
        "orchestrateur_moteur_thermique_corrige",
        "moteur_thermique",
    ),
    "EntreesOrchestrateurMoteurThermique",
)

# Données ensemble.
get_carburant = _import_attr_optional(("backend.ensemble.carburant", "ensemble.carburant", "carburant"), "get_carburant")
get_pire_carburant = _import_attr_optional(("backend.ensemble.carburant", "ensemble.carburant", "carburant"), "get_pire_carburant")
lister_carburants = _import_attr_optional(("backend.ensemble.carburant", "ensemble.carburant", "carburant"), "lister_carburants")
get_materiau = _import_attr_optional(("backend.ensemble.materiaux", "ensemble.materiaux", "materiaux"), "get_materiau")
lister_materiaux = _import_attr_optional(("backend.ensemble.materiaux", "ensemble.materiaux", "materiaux"), "lister_materiaux")

# =============================================================================
# Helpers génériques
# =============================================================================

_COMPONENT_KEYS = {
    "moteur_electrique",
    "moteurs_sortie",
    "batterie",
    "batterie_tampon",
    "alternateur",
    "boite_crabots",
    "moteur_thermique",
    "moteurs_thermiques",
    "architecture",
    "architechture",
}
_ROOT_BLOCKS = {"meta", "composants", "pieces", "analyses", "sortie", "moteurs_sortie", "moteurs_thermiques", "auxiliaires", "charges_auxiliaires", "batterie", "batterie_tampon", "transmission_generation", "generation", "cycle_croisiere", "mobilite", "cahier_des_charges"}
_POWER_ALIASES_W = (
    "puissance_sortie_moteur_electrique_w",
    "puissance_moteur_electrique_sortie_w",
    "puissance_sortie_w",
    "puissance_demandee_w",
    "puissance_traction_w",
    "puissance_utile_sortie_w",
)
_POWER_ALIASES_KW = (
    "puissance_sortie_moteur_electrique_kw",
    "puissance_sortie_kw",
    "puissance_demandee_kw",
    "puissance_traction_kw",
    "puissance_utile_sortie_kw",
)


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _sf(x: Any) -> Optional[float]:
    if _is_finite(x):
        return float(x)
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except Exception:
        return None


def _si(x: Any) -> Optional[int]:
    if isinstance(x, int) and not isinstance(x, bool):
        return int(x)
    f = _sf(x)
    if f is None:
        return None
    if abs(f - round(f)) < 1e-9:
        return int(round(f))
    return int(f)


def _safe_dict(x: Any) -> Dict[str, Any]:
    return dict(x) if isinstance(x, Mapping) else {}


def _safe_list(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    if isinstance(x, tuple):
        return list(x)
    return [x]


def _dig(obj: Any, *path: str) -> Any:
    cur = obj
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, Mapping):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return cur


def _get_any(mapping: Mapping[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in mapping:
            return mapping[k]
    return None


def _first_non_none(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def _first_finite(*vals: Any) -> Optional[float]:
    for v in vals:
        f = _sf(v)
        if f is not None:
            return f
    return None


def _deep_merge(base: Optional[Mapping[str, Any]], extra: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = copy.deepcopy(dict(base or {}))
    for k, v in dict(extra or {}).items():
        if isinstance(v, Mapping) and isinstance(out.get(k), Mapping):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _merge_missing(base: Dict[str, Any], fallback: Mapping[str, Any]) -> Dict[str, Any]:
    for k, v in dict(fallback or {}).items():
        if isinstance(v, Mapping):
            if isinstance(base.get(k), dict):
                _merge_missing(base[k], v)
            elif base.get(k) is None:
                base[k] = copy.deepcopy(dict(v))
        elif base.get(k) is None and v is not None:
            base[k] = v
    return base


def _push(rep: Dict[str, Any], cat: str, nom: str, raison: str) -> None:
    rep.setdefault("inconnues", {}).setdefault(cat, []).append({"nom": str(nom), "raison": str(raison)})


def _alert(rep: Dict[str, Any], niveau: str, nom: str, detail: str) -> None:
    rep.setdefault("alertes", {}).setdefault(niveau, []).append({"nom": str(nom), "detail": str(detail)})


def _note(rep: Dict[str, Any], message: str) -> None:
    rep.setdefault("notes_modele", []).append(str(message))


def _dedup(rep: Dict[str, Any]) -> None:
    inc = rep.setdefault("inconnues", {})
    for cat in ("impossibles", "partielles"):
        seen: set[Tuple[str, str]] = set()
        out: List[Dict[str, str]] = []
        for item in list(inc.get(cat, []) or []):
            if not isinstance(item, Mapping):
                continue
            key = (str(item.get("nom", "")), str(item.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append({"nom": key[0], "raison": key[1]})
        inc[cat] = out
    alerts = rep.setdefault("alertes", {})
    for lvl, items in list(alerts.items()):
        seen2: set[Tuple[str, str]] = set()
        out2: List[Dict[str, str]] = []
        for item in list(items or []):
            if not isinstance(item, Mapping):
                continue
            key = (str(item.get("nom", "")), str(item.get("detail", "")))
            if key not in seen2:
                seen2.add(key)
                out2.append({"nom": key[0], "detail": key[1]})
        alerts[lvl] = out2


def _merge_inconnues(dst: Dict[str, Any], src: Any, *, prefix: str) -> None:
    if not isinstance(src, Mapping):
        return
    inc = _safe_dict(src.get("inconnues"))
    for cat in ("impossibles", "partielles"):
        for item in list(inc.get(cat, []) or []):
            if isinstance(item, Mapping):
                _push(dst, cat, f"{prefix}::{item.get('nom', '')}", str(item.get("raison", "")))
    for item in list(inc.get("bloquantes", []) or []) + list(inc.get("restantes_physiques", []) or []):
        if isinstance(item, Mapping):
            _push(dst, "impossibles", f"{prefix}::{item.get('nom') or item.get('champ', '')}", str(item.get("raison", "")))
    for item in list(inc.get("non_bloquantes", []) or []) + list(inc.get("restantes_catalogue", []) or []):
        if isinstance(item, Mapping):
            _push(dst, "partielles", f"{prefix}::{item.get('nom') or item.get('champ', '')}", str(item.get("raison", "")))
    for item in list(inc.get("conflits", []) or []):
        if isinstance(item, Mapping):
            _push(dst, "impossibles", f"{prefix}::{item.get('nom') or item.get('champ', '')}", str(item.get("raison", "")))
            dst.setdefault("alertes", {}).setdefault("conflits", []).append(_to_jsonable(item, max_depth=5))


def _to_jsonable(value: Any, *, depth: int = 0, max_depth: int = 10) -> Any:
    if depth > max_depth:
        return {"type": type(value).__name__, "truncated": True}
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return str(value)
        return value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        try:
            return _to_jsonable(asdict(value), depth=depth + 1, max_depth=max_depth)
        except Exception:
            return {"type": type(value).__name__}
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v, depth=depth + 1, max_depth=max_depth) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v, depth=depth + 1, max_depth=max_depth) for v in value]
    if hasattr(value, "tolist"):
        try:
            return _to_jsonable(value.tolist(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            return _to_jsonable(value.item(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            public = {k: v for k, v in vars(value).items() if not k.startswith("_") and not callable(v)}
            return {"type": type(value).__name__, "attributs": _to_jsonable(public, depth=depth + 1, max_depth=max_depth)}
        except Exception:
            pass
    return {"type": type(value).__name__, "repr": repr(value)[:300]}


def _call_supported(fn: Callable[..., Any], /, **kwargs: Any) -> Any:
    try:
        sig = inspect.signature(fn)
        accepts_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        if accepts_varkw:
            return fn(**{k: v for k, v in kwargs.items() if v is not None})
        allowed = set(sig.parameters.keys())
        return fn(**{k: v for k, v in kwargs.items() if k in allowed and v is not None})
    except TypeError:
        return fn(**{k: v for k, v in kwargs.items() if v is not None})


def _construct_dataclass_or_class(cls: Any, payload: Mapping[str, Any]) -> Any:
    if cls is None:
        raise RuntimeError("Classe indisponible")
    if isinstance(cls, type) and is_dataclass(cls):
        allowed = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in payload.items() if k in allowed})
    try:
        sig = inspect.signature(cls)
        allowed = set(sig.parameters.keys())
        return cls(**{k: v for k, v in payload.items() if k in allowed})
    except Exception:
        return cls(**dict(payload))


def _safe_call_report(obj: Any, *, strict: bool = False, **kwargs: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    for method_name in ("analyser", "calculer", "analyser_dimensionnement", "analyser_definition"):
        fn = getattr(obj, method_name, None)
        if callable(fn):
            try:
                out = _call_supported(fn, strict=strict, **kwargs)
                if isinstance(out, Mapping):
                    return dict(out)
            except TypeError:
                try:
                    out = fn()
                    if isinstance(out, Mapping):
                        return dict(out)
                except Exception:
                    continue
            except Exception:
                continue
    return None


def _extract_p_sortie_w(config: Mapping[str, Any], resolved: Optional[Mapping[str, Any]] = None) -> Optional[float]:
    for source in (config, _safe_dict(config.get("sortie")), _safe_dict(config.get("analyses", {})).get("stho_me", {}), _safe_dict(config.get("analyses", {})).get("systeme_complet", {}), resolved or {}):
        if not isinstance(source, Mapping):
            continue
        p = _first_finite(*[source.get(k) for k in _POWER_ALIASES_W])
        if p is not None:
            return p
        pkw = _first_finite(*[source.get(k) for k in _POWER_ALIASES_KW])
        if pkw is not None:
            return pkw * 1000.0
    return None


def _extract_resolved_payload(resolution_report: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(resolution_report, Mapping):
        return {}
    for path in (("payload_resolu",), ("resolved",), ("resultats", "payload_resolu"), ("resolution", "payload_resolu")):
        cur: Any = resolution_report
        for key in path:
            cur = cur.get(key) if isinstance(cur, Mapping) else None
        if isinstance(cur, Mapping):
            return dict(cur)
    return {}


# =============================================================================
# Normalisation configuration
# =============================================================================


def _normaliser_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    cfg = copy.deepcopy(dict(config or {}))
    meta = _safe_dict(cfg.get("meta"))
    composants = _safe_dict(cfg.get("composants"))
    pieces = _safe_dict(cfg.get("pieces"))
    analyses = _safe_dict(cfg.get("analyses"))

    # Les blocs racine modernes sont recopiés dans composants/analyses selon leur rôle.
    for key in _COMPONENT_KEYS:
        if key in cfg and key not in composants:
            composants[key] = copy.deepcopy(cfg[key])
    for key in ("sortie", "moteurs_sortie", "moteurs_thermiques", "auxiliaires", "charges_auxiliaires", "batterie", "batterie_tampon", "transmission_generation", "generation", "cycle_croisiere", "mobilite"):
        if key in cfg:
            analyses[key] = copy.deepcopy(cfg[key])
    if "cahier_des_charges" in cfg:
        meta["cahier_des_charges"] = _deep_merge(_safe_dict(meta.get("cahier_des_charges")), _safe_dict(cfg.get("cahier_des_charges")))
        analyses["cahier_des_charges"] = _deep_merge(_safe_dict(analyses.get("cahier_des_charges")), _safe_dict(cfg.get("cahier_des_charges")))

    root_inputs = {k: v for k, v in cfg.items() if k not in _ROOT_BLOCKS and k not in _COMPONENT_KEYS}
    if root_inputs:
        analyses["stho_me"] = _deep_merge(_safe_dict(analyses.get("stho_me")), root_inputs)

    p_out = _extract_p_sortie_w(cfg)
    if p_out is not None:
        analyses.setdefault("stho_me", {})["puissance_sortie_moteur_electrique_w"] = p_out
        analyses.setdefault("systeme_complet", {})["puissance_sortie_moteur_electrique_w"] = p_out
        analyses.setdefault("sortie", {})["puissance_sortie_max_w"] = p_out

    return {"meta": meta, "composants": composants, "pieces": pieces, "analyses": analyses}


def _flatten_for_resolution(meta: Mapping[str, Any], composants: Mapping[str, Any], pieces: Mapping[str, Any], analyses: Mapping[str, Any]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    for block in ("stho_me", "systeme_complet", "sortie", "moteur_thermique_definition", "cahier_des_charges"):
        if isinstance(analyses.get(block), Mapping):
            flat = _deep_merge(flat, analyses[block])
    if isinstance(meta.get("cahier_des_charges"), Mapping):
        flat["cahier_des_charges"] = _deep_merge(_safe_dict(flat.get("cahier_des_charges")), _safe_dict(meta.get("cahier_des_charges")))
    flat["composants"] = _to_jsonable(composants, max_depth=6)
    flat["pieces"] = _to_jsonable(pieces, max_depth=6)
    flat["analyses"] = _to_jsonable(analyses, max_depth=6)
    flat["meta"] = _to_jsonable(meta, max_depth=5)
    return flat


def _resolved_to_component_defaults(resolved: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(resolved, Mapping):
        return {}
    p_out = _first_finite(resolved.get("puissance_sortie_moteur_electrique_w"), resolved.get("puissance_sortie_w"))
    p_bus = _first_finite(resolved.get("puissance_bus_dc_w"), resolved.get("P_bus_dc_design_w"))
    p_alt = _first_finite(resolved.get("puissance_alternateur_electrique_w"), resolved.get("production_electrique_sortie_w"))
    p_alt_m = _first_finite(resolved.get("puissance_alternateur_mecanique_w"))
    p_mt = _first_finite(resolved.get("puissance_moteur_thermique_arbre_w"), resolved.get("puissance_moteur_requise_W"))
    rpm_mt = _first_finite(resolved.get("rpm_moteur"), resolved.get("rpm_moteur_nominal"))
    rpm_alt = _first_finite(resolved.get("rpm_alternateur"), resolved.get("vitesse_alternateur_rpm"))
    ratio_alt = _first_finite(resolved.get("rapport_vitesse_alt_sur_moteur"), resolved.get("rapport_boite_alt"))
    Vbus = _first_finite(resolved.get("tension_bus_dc_v"), resolved.get("V_bus_dc_v"))
    eta_motor = _first_finite(resolved.get("rendement_moteur_electrique"))
    eta_alt = _first_finite(resolved.get("rendement_alternateur"))
    eta_boite = _first_finite(resolved.get("rendement_boite"))
    pme = _first_finite(resolved.get("pme_pa"), resolved.get("pression_moyenne_effective_pa"))
    pmax = _first_finite(resolved.get("pression_max_pa"))
    cdc = _safe_dict(resolved.get("cahier_des_charges"))
    return {
        "sortie": {"puissance_sortie_max_w": p_out},
        "moteur_electrique": {
            "puissance_max_w": p_out,
            "tension_bus_v": Vbus,
            "rendement_moteur": eta_motor,
            "regime_max_rpm": _first_finite(resolved.get("regime_max_rpm")),
            "couple_max_nm": _first_finite(resolved.get("couple_moteur_electrique_nm")),
        },
        "batterie": {
            "tension_nominale_v": Vbus,
            "energie_utile_imposee_kwh": _first_finite(resolved.get("energie_batterie_kwh"), resolved.get("energie_batterie_tampon_min_kwh")),
            "capacite_nominale_kwh": _first_finite(resolved.get("energie_batterie_kwh"), resolved.get("energie_batterie_tampon_min_kwh")),
            "nb_cellules_serie": _si(resolved.get("nb_cellules_serie")),
            "nb_cellules_parallele": _si(resolved.get("nb_cellules_parallele")),
        },
        "alternateur": {
            "rendement_alternateur_impose": eta_alt,
            "plage_regime": {
                "rpm_cible": rpm_alt,
                "rpm_min_optimal": _first_finite(resolved.get("rpm_alternateur_min_optimal")),
                "rpm_max_optimal": _first_finite(resolved.get("rpm_alternateur_max_optimal")),
            },
            "interface_bus_dc": {
                "tension_bus_dc_v": Vbus,
                "puissance_charge_max_w": p_alt,
            },
        },
        "boite_crabots": {
            "rpm_moteur_optimal": rpm_mt,
            "rpm_alternateur_cible": rpm_alt,
            "rapport_vitesse_alt_sur_moteur": ratio_alt,
            "rapports": [ratio_alt] if ratio_alt is not None else None,
            "rendement_boite_defaut": eta_boite,
        },
        "moteur_thermique": {
            "puissance_visee_w": p_mt or p_alt_m,
            "puissance_arbre_max_w": p_mt or p_alt_m,
            "rpm": rpm_mt,
            "rpm_nominal": rpm_mt,
            "pression_moyenne_effective_pa": pme,
            "pme_pa": pme,
            "pression_max_pa": pmax,
            "temps_moteur": cdc.get("temps_moteur"),
            "rendement_mecanique": cdc.get("rendement_mecanique"),
            "vitesse_piston_max_ms": cdc.get("vitesse_piston_max_ms"),
            "ratio_course_alesage_max": cdc.get("ratio_course_alesage_max"),
            "nombre_cylindres": _si(resolved.get("nombre_cylindres")),
            "alesage_m": _first_finite(resolved.get("alesage_m")),
            "course_m": _first_finite(resolved.get("course_m")),
            "architecture": _first_non_none(resolved.get("architecture_moteur"), resolved.get("architecture")),
        },
        "architecture": {
            "puissance_cible_w": p_mt or p_alt_m,
            "regime_tr_min": rpm_mt,
            "pme_pa": pme,
            "pression_max_pa": pmax,
            "vitesse_piston_max_ms": cdc.get("vitesse_piston_max_ms"),
            "longueur_dispo_m": cdc.get("longueur_dispo_m"),
            "largeur_dispo_m": cdc.get("largeur_dispo_m"),
            "hauteur_dispo_m": cdc.get("hauteur_dispo_m"),
            "architecture_forcee": _first_non_none(resolved.get("architecture_moteur"), resolved.get("architecture")),
        },
        "systeme": {
            "puissance_sortie_w": p_out,
            "puissance_bus_dc_w": p_bus,
            "puissance_alternateur_electrique_w": p_alt,
            "puissance_moteur_thermique_arbre_w": p_mt,
            "tension_bus_dc_v": Vbus,
        },
    }


def _clean_nones(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _clean_nones(v) for k, v in value.items() if v is not None and _clean_nones(v) != {}}
    if isinstance(value, list):
        return [_clean_nones(v) for v in value if v is not None]
    return value


def _build_final_system_config(composants: Mapping[str, Any], analyses: Mapping[str, Any], resolved: Mapping[str, Any]) -> Dict[str, Any]:
    defaults = _resolved_to_component_defaults(resolved)
    cfg: Dict[str, Any] = {}

    # Sortie utile.
    sortie = _deep_merge(_safe_dict(defaults.get("sortie")), _safe_dict(analyses.get("sortie")))
    sortie = _deep_merge(sortie, _safe_dict(analyses.get("stho_me")))
    p = _extract_p_sortie_w({"sortie": sortie}, resolved)
    if p is not None:
        sortie.setdefault("puissance_sortie_max_w", p)
    cfg["sortie"] = sortie

    # Moteurs sortie : priorité au bloc moderne, puis moteur électrique legacy.
    moteurs_sortie = analyses.get("moteurs_sortie") or composants.get("moteurs_sortie")
    if moteurs_sortie is None:
        me = _deep_merge(_safe_dict(defaults.get("moteur_electrique")), _safe_dict(composants.get("moteur_electrique")))
        if me:
            moteurs_sortie = [me]
    cfg["moteurs_sortie"] = _to_jsonable(moteurs_sortie, max_depth=5) if moteurs_sortie is not None else []

    # Auxiliaires.
    cfg["auxiliaires"] = _first_non_none(analyses.get("auxiliaires"), analyses.get("charges_auxiliaires"), [])
    p_aux = _first_finite(_dig(analyses, "stho_me", "puissance_auxiliaire_w"), analyses.get("puissance_auxiliaire_w"))
    if p_aux is not None:
        cfg["puissance_auxiliaire_w"] = p_aux

    # Thermique.
    sources = analyses.get("moteurs_thermiques") or composants.get("moteurs_thermiques")
    if sources is None:
        mt = _deep_merge(_safe_dict(defaults.get("moteur_thermique")), _safe_dict(composants.get("moteur_thermique")))
        if mt:
            sources = [mt]
    cfg["moteurs_thermiques"] = _to_jsonable(sources, max_depth=5) if sources is not None else []
    if sources is None and composants.get("moteur_thermique"):
        cfg["moteur_thermique"] = composants["moteur_thermique"]

    # Batterie / transmission / cycle.
    cfg["batterie"] = _deep_merge(_safe_dict(defaults.get("batterie")), _safe_dict(_first_non_none(analyses.get("batterie"), analyses.get("batterie_tampon"), composants.get("batterie"))))
    # Transmission génération attendue par systeme_hybride_final.
    # On traduit les noms internes alternateur/boîte vers les noms système.
    trans2 = _deep_merge(_safe_dict(analyses.get("transmission_generation")), _safe_dict(analyses.get("generation")))
    boite_user = _safe_dict(composants.get("boite_crabots"))
    alt_user = _safe_dict(composants.get("alternateur"))
    boite_def = _safe_dict(defaults.get("boite_crabots"))
    alt_def = _safe_dict(defaults.get("alternateur"))
    plage_alt_user = _safe_dict(alt_user.get("plage_regime"))
    plage_alt_def = _safe_dict(alt_def.get("plage_regime"))

    trans2.setdefault("rendement_boite", _first_finite(boite_user.get("rendement_boite"), boite_user.get("rendement_boite_defaut"), boite_def.get("rendement_boite_defaut")))
    trans2.setdefault("rendement_alternateur", _first_finite(alt_user.get("rendement_alternateur"), alt_user.get("rendement_alternateur_impose"), alt_def.get("rendement_alternateur_impose")))
    trans2.setdefault("rendement_redressement", _first_finite(_dig(alt_user, "interface_bus_dc", "rendement_redressement"), _dig(alt_def, "interface_bus_dc", "rendement_redressement")))
    trans2.setdefault("rendement_charge", _first_finite(_dig(alt_user, "interface_bus_dc", "rendement_charge"), _dig(alt_def, "interface_bus_dc", "rendement_charge")))
    trans2.setdefault("rpm_alternateur_cible", _first_finite(boite_user.get("rpm_alternateur_cible"), boite_def.get("rpm_alternateur_cible"), plage_alt_user.get("rpm_cible"), plage_alt_def.get("rpm_cible")))
    trans2.setdefault("rpm_alternateur_min_optimal", _first_finite(boite_user.get("rpm_alternateur_min_optimal"), plage_alt_user.get("rpm_min_optimal"), plage_alt_def.get("rpm_min_optimal")))
    trans2.setdefault("rpm_alternateur_max_optimal", _first_finite(boite_user.get("rpm_alternateur_max_optimal"), plage_alt_user.get("rpm_max_optimal"), plage_alt_def.get("rpm_max_optimal")))
    trans2.setdefault("rapports_boite", _first_non_none(boite_user.get("rapports"), boite_user.get("rapports_boite"), boite_def.get("rapports")))
    trans2.setdefault("rapport_min", _first_finite(boite_user.get("rapport_min"), boite_def.get("rapport_min")))
    trans2.setdefault("rapport_max", _first_finite(boite_user.get("rapport_max"), boite_def.get("rapport_max")))
    cfg["transmission_generation"] = _clean_nones(trans2)
    cfg["cycle_croisiere"] = _safe_dict(analyses.get("cycle_croisiere"))
    cfg["mobilite"] = _safe_dict(analyses.get("mobilite")) or _safe_dict(composants.get("mobilite"))

    return _clean_nones(cfg)


# =============================================================================
# Orchestrateur principal
# =============================================================================

@dataclass
class STHO_ME:
    composants: Dict[str, Any] = field(default_factory=dict)
    pieces: Dict[str, Any] = field(default_factory=dict)
    analyses: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    composants_obj: Dict[str, Any] = field(default_factory=dict, init=False)
    pieces_obj: Dict[str, Any] = field(default_factory=dict, init=False)

    @classmethod
    def depuis_config(cls, config: Mapping[str, Any]) -> "STHO_ME":
        norm = _normaliser_config(config)
        return cls(
            composants=_safe_dict(norm.get("composants")),
            pieces=_safe_dict(norm.get("pieces")),
            analyses=_safe_dict(norm.get("analyses")),
            meta=_safe_dict(norm.get("meta")),
        )

    def _new_report(self) -> Dict[str, Any]:
        return {
            "meta": {
                "orchestrateur": "STHO_ME.py",
                "chemin_orchestrateur": "backend/ensemble/STHO_ME.py",
                "version": "3.0.0-systeme-complet",
                "nom_projet": self.meta.get("nom_projet", "STHO-ME"),
                "meta_utilisateur": _to_jsonable(self.meta, max_depth=5),
            },
            "role_systeme": {
                "sortie_utilisateur": "puissance utile réellement disponible, ex. 100 kW à fond",
                "bus_dc": "puissance utile corrigée par rendements moteurs + auxiliaires + pertes",
                "batterie": "tampon énergie/puissance, stabilisation et pics, jamais cache-misère d'une génération trop faible",
                "alternateur": "conversion arbre -> électricité, intégré au bus DC et à la batterie",
                "boite_crabots": "maintient le thermique dans son cycle optimal et multiplie/adapte le régime alternateur",
                "moteur_thermique": "source primaire efficiente, fiable, durable, capable de soutenir pleine puissance et croisière optimale",
            },
            "entrees": {
                "composants": _to_jsonable(self.composants, max_depth=5),
                "pieces": _to_jsonable(self.pieces, max_depth=5),
                "analyses": _to_jsonable(self.analyses, max_depth=5),
            },
            "resolution_inconnues": {},
            "aboutissement_systeme": {},
            "construction": {"composants": {}, "pieces": {}},
            "rapports": {"composants": {}, "pieces": {}, "optimisation": {}, "strategie_energie": {}},
            "sous_systemes": {},
            "liaisons": {},
            "definition_complete": {},
            "synthese": {},
            "cao": {},
            "frontend": {},
            "tracabilite": {"valeurs": {}, "sources": {}},
            "inconnues": {"impossibles": [], "partielles": []},
            "alertes": {},
            "notes_modele": [],
            "imports": {"erreurs_optionnelles": dict(_IMPORT_ERRORS)},
        }

    # ------------------------------------------------------------------
    # Résolution des inconnues / CDC
    # ------------------------------------------------------------------
    def _run_resolution(self, rapport: Dict[str, Any], *, strict: bool, optimize: bool, repository: Any, project_id: Optional[str]) -> Dict[str, Any]:
        if not callable(resoudre_inconnues_systeme):
            _push(rapport, "partielles", "resolution_inconnues", "Module resolution_inconnues indisponible ; seules les valeurs fournies seront utilisées.")
            return {}
        payload = _flatten_for_resolution(self.meta, self.composants, self.pieces, self.analyses)
        cdc = _safe_dict(self.meta.get("cahier_des_charges")) or _safe_dict(self.analyses.get("cahier_des_charges"))
        try:
            try:
                out = _call_supported(
                    resoudre_inconnues_systeme,
                    entrees=payload,
                    donnees=payload,
                    payload=payload,
                    config=payload,
                    cahier_des_charges=cdc,
                    strict=strict,
                    mode="strict" if strict else "projet",
                    optimize=optimize,
                    repository=repository,
                    project_id=project_id,
                )
            except TypeError:
                out = resoudre_inconnues_systeme(payload)  # type: ignore[misc]
            if not isinstance(out, Mapping):
                if is_dataclass(out) and not isinstance(out, type):
                    out = asdict(out)
                elif hasattr(out, "__dict__"):
                    out = {k: v for k, v in vars(out).items() if not k.startswith("_")}
                else:
                    _push(rapport, "partielles", "resolution_inconnues", f"Retour non dictionnaire : {type(out).__name__}.")
                    return {}
            rapport["resolution_inconnues"] = _to_jsonable(out, max_depth=8)
            rapport["hypotheses_resolues"] = _to_jsonable(out.get("hypotheses", []), max_depth=8)
            rapport["coherence_systeme"] = _to_jsonable(out.get("coherence_systeme", {}), max_depth=6)
            _merge_inconnues(rapport, out, prefix="resolution_inconnues")
            resolved = _extract_resolved_payload(out)
            if resolved:
                rapport["tracabilite"]["sources"]["resolution_inconnues"] = "payload_resolu"
                return resolved
        except Exception as exc:
            _push(rapport, "partielles", "resolution_inconnues", str(exc))
        return {}

    # ------------------------------------------------------------------
    # Aboutissement système final
    # ------------------------------------------------------------------
    def _run_aboutissement_systeme(self, rapport: Dict[str, Any], resolved: Mapping[str, Any]) -> Dict[str, Any]:
        cfg_final = _build_final_system_config(self.composants, self.analyses, resolved)
        rapport["entrees"]["config_aboutissement_systeme"] = _to_jsonable(cfg_final, max_depth=7)
        if not callable(concevoir_systeme_hybride_final):
            _push(rapport, "partielles", "systeme_hybride_final", "Module systeme_hybride_final indisponible ; calcul global fallback limité.")
            fallback = self._fallback_aboutissement_systeme(cfg_final, rapport)
            rapport["aboutissement_systeme"] = fallback
            return fallback
        try:
            out = concevoir_systeme_hybride_final(cfg_final)  # type: ignore[misc]
            if isinstance(out, Mapping):
                rapport["aboutissement_systeme"] = _to_jsonable(out, max_depth=9)
                _merge_inconnues(rapport, out, prefix="aboutissement_systeme")
                return dict(out)
            _push(rapport, "partielles", "systeme_hybride_final", f"Retour non dictionnaire : {type(out).__name__}.")
        except Exception as exc:
            _push(rapport, "partielles", "systeme_hybride_final", str(exc))
        fallback = self._fallback_aboutissement_systeme(cfg_final, rapport)
        rapport["aboutissement_systeme"] = fallback
        return fallback

    def _fallback_aboutissement_systeme(self, cfg: Mapping[str, Any], rapport: Dict[str, Any]) -> Dict[str, Any]:
        p_out = _extract_p_sortie_w(cfg)
        moteurs = _safe_list(cfg.get("moteurs_sortie"))
        p_inst = 0.0
        p_inst_known = False
        eta_values: List[float] = []
        tensions: List[float] = []
        for m in moteurs:
            if isinstance(m, Mapping):
                q = _si(m.get("quantite")) or 1
                p = _first_finite(m.get("puissance_max_w"), m.get("puissance_sortie_max_w"))
                if p is not None:
                    p_inst += p * q
                    p_inst_known = True
                eta = _first_finite(m.get("rendement_moteur"))
                if eta is not None and 0 < eta <= 1:
                    eta_values.append(eta)
                V = _first_finite(m.get("tension_bus_v"), m.get("tension_bus_dc_v"))
                if V is not None:
                    tensions.append(V)
        p_aux = _first_finite(cfg.get("puissance_auxiliaire_w")) or 0.0
        eta_moy = min(eta_values) if eta_values else None
        p_bus = None
        if p_out is not None and eta_moy is not None:
            p_bus = p_out / eta_moy + p_aux
        elif p_out is not None:
            _push(rapport, "partielles", "rendement_moteurs_sortie", "Requis pour convertir puissance utile sortie en puissance bus DC.")
        Vbus = _first_finite(_dig(cfg, "batterie", "tension_nominale_v"), *(tensions or []))
        Ibus = p_bus / Vbus if p_bus is not None and Vbus else None
        return {
            "composant": "systeme_hybride_final_fallback",
            "synthese": {
                "puissance_sortie_max_demandee_kw": None if p_out is None else p_out / 1000.0,
                "puissance_sortie_installee_max_kw": None if not p_inst_known else p_inst / 1000.0,
                "ok_moteurs_sortie_pleine_puissance": None if p_out is None or not p_inst_known else p_inst >= p_out,
                "P_bus_dc_pleine_sortie_kw": None if p_bus is None else p_bus / 1000.0,
                "V_bus_dc_v": Vbus,
                "I_bus_dc_a": Ibus,
            },
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": ["Fallback minimal : installer systeme_hybride_final.py pour la chaîne complète."],
        }

    # ------------------------------------------------------------------
    # Construction et analyse composants spécialisés
    # ------------------------------------------------------------------
    def _build_component_cfg(self, name: str, resolved: Mapping[str, Any], systeme_final: Mapping[str, Any]) -> Dict[str, Any]:
        defaults = _resolved_to_component_defaults(resolved)
        cfg = _safe_dict(defaults.get(name))
        if name == "moteur_electrique":
            cfg = _deep_merge(cfg, _safe_dict(self.composants.get("moteur_electrique")))
            # Si le config final a un seul moteur sortie, on l'utilise aussi.
            ms = _safe_list(_dig(systeme_final, "entrees_normalisees", "moteurs_sortie")) or _safe_list(_dig(self.analyses, "moteurs_sortie"))
            if len(ms) == 1 and isinstance(ms[0], Mapping):
                cfg = _deep_merge(cfg, _safe_dict(ms[0]))
        elif name == "batterie":
            cfg = _deep_merge(cfg, _safe_dict(_first_non_none(self.composants.get("batterie"), self.analyses.get("batterie"), self.analyses.get("batterie_tampon"))))
            pbus = _first_finite(_dig(systeme_final, "sous_systemes", "sortie_et_bus_dc", "puissances", "P_bus_dc_sortie_max_total_w"))
            if pbus is not None:
                cfg.setdefault("puissance_pic_kw", pbus / 1000.0)
                cfg.setdefault("puissance_sortie_pic_kw", pbus / 1000.0)
            pcrois = _first_finite(_dig(systeme_final, "synthese", "P_bus_dc_croisiere_kw"))
            if pcrois is not None:
                cfg.setdefault("puissance_moyenne_kw", pcrois)
                cfg.setdefault("puissance_sortie_moyenne_kw", pcrois)
        elif name == "alternateur":
            cfg = _deep_merge(cfg, _safe_dict(self.composants.get("alternateur")))
        elif name == "boite_crabots":
            cfg = _deep_merge(cfg, _safe_dict(self.composants.get("boite_crabots")))
        elif name == "architecture":
            cfg = _deep_merge(cfg, _safe_dict(_first_non_none(self.composants.get("architecture"), self.composants.get("architechture"))))
            mt_user = _safe_dict(self.composants.get("moteur_thermique"))
            ptherm = _first_finite(_dig(systeme_final, "synthese", "P_arbre_thermique_requise_pleine_sortie_kw"), _dig(systeme_final, "sous_systemes", "moteurs_thermiques_pleine_sortie", "checks", "puissance_arbre_requise_w"))
            if ptherm is not None:
                # ptherm peut venir en kW depuis synthèse ou en W depuis checks ; seuil simple pour éviter double conversion.
                cfg["puissance_cible_w"] = cfg.get("puissance_cible_w") if cfg.get("puissance_cible_w") is not None else (ptherm * 1000.0 if ptherm < 10_000 else ptherm)
            cfg["regime_tr_min"] = cfg.get("regime_tr_min") if cfg.get("regime_tr_min") is not None else _first_finite(mt_user.get("rpm"), mt_user.get("rpm_nominal"), mt_user.get("regime_tr_min"), resolved.get("rpm_moteur"), resolved.get("rpm_moteur_nominal"))
            cfg["pme_pa"] = cfg.get("pme_pa") if cfg.get("pme_pa") is not None else _first_finite(mt_user.get("pression_moyenne_effective_pa"), mt_user.get("pme_pa"), resolved.get("pme_pa"), resolved.get("pression_moyenne_effective_pa"))
            cfg["pression_max_pa"] = cfg.get("pression_max_pa") if cfg.get("pression_max_pa") is not None else _first_finite(mt_user.get("pression_max_pa"), resolved.get("pression_max_pa"))
            cfg["vitesse_piston_max_ms"] = cfg.get("vitesse_piston_max_ms") if cfg.get("vitesse_piston_max_ms") is not None else _first_finite(mt_user.get("vitesse_piston_max_ms"), resolved.get("vitesse_piston_max_ms"))
            cfg["ratio_course_alesage_max"] = cfg.get("ratio_course_alesage_max") if cfg.get("ratio_course_alesage_max") is not None else _first_finite(mt_user.get("ratio_course_alesage_max"), resolved.get("ratio_course_alesage_max"))
        elif name == "moteur_thermique":
            cfg = _deep_merge(cfg, _safe_dict(self.composants.get("moteur_thermique")))
            ptherm = _first_finite(_dig(systeme_final, "synthese", "P_arbre_thermique_requise_pleine_sortie_kw"))
            if ptherm is not None:
                cfg["puissance_visee_w"] = cfg.get("puissance_visee_w") if cfg.get("puissance_visee_w") is not None else ptherm * 1000.0
                cfg["puissance_arbre_max_w"] = cfg.get("puissance_arbre_max_w") if cfg.get("puissance_arbre_max_w") is not None else ptherm * 1000.0
        return _clean_nones(cfg)

    def _run_component_analyses(self, rapport: Dict[str, Any], resolved: Mapping[str, Any], systeme_final: Mapping[str, Any], *, strict: bool) -> None:
        comps_report = rapport["rapports"]["composants"]

        # Moteur électrique.
        me_cfg = self._build_component_cfg("moteur_electrique", resolved, systeme_final)
        if me_cfg:
            comps_report["moteur_electrique"] = self._run_moteur_electrique(me_cfg, strict=strict)
            _merge_inconnues(rapport, comps_report["moteur_electrique"], prefix="moteur_electrique")
        else:
            _push(rapport, "partielles", "moteur_electrique", "Aucune définition de moteur de sortie fournie.")

        # Batterie.
        batt_cfg = self._build_component_cfg("batterie", resolved, systeme_final)
        if batt_cfg:
            comps_report["batterie"] = self._run_batterie(batt_cfg, strict=strict)
            _merge_inconnues(rapport, comps_report["batterie"], prefix="batterie")
        else:
            _push(rapport, "partielles", "batterie", "Aucune définition batterie fournie.")

        # Alternateur.
        alt_cfg = self._build_component_cfg("alternateur", resolved, systeme_final)
        alt_point = self._alternateur_point_cfg(alt_cfg, resolved, systeme_final)
        if alt_cfg or alt_point:
            comps_report["alternateur"] = self._run_alternateur(alt_cfg, alt_point, strict=strict)
            _merge_inconnues(rapport, comps_report["alternateur"], prefix="alternateur")
        else:
            _push(rapport, "partielles", "alternateur", "Aucune définition alternateur fournie.")

        # Boîte.
        boite_cfg = self._build_component_cfg("boite_crabots", resolved, systeme_final)
        boite_point = self._boite_point_cfg(boite_cfg, resolved, systeme_final)
        if boite_cfg or boite_point:
            comps_report["boite_crabots"] = self._run_boite(boite_cfg, boite_point, strict=strict)
            _merge_inconnues(rapport, comps_report["boite_crabots"], prefix="boite_crabots")
        else:
            _push(rapport, "partielles", "boite_crabots", "Aucune définition boîte à crabots fournie.")

        # Architecture.
        arch_cfg = self._build_component_cfg("architecture", resolved, systeme_final)
        if arch_cfg:
            comps_report["architecture"] = self._run_architecture(arch_cfg, strict=strict)
            _merge_inconnues(rapport, comps_report["architecture"], prefix="architecture")
        else:
            _push(rapport, "partielles", "architecture", "Contraintes d'architecture insuffisantes ou absentes.")

        # Moteur thermique.
        mt_cfg = self._build_component_cfg("moteur_thermique", resolved, systeme_final)
        # Réinjection architecture vers thermique.
        arch_rep = _safe_dict(comps_report.get("architecture"))
        arch_res = _safe_dict(_dig(arch_rep, "selection") or _dig(arch_rep, "meilleur") or _dig(arch_rep, "meilleur_candidat") or _dig(arch_rep, "resultats") or _dig(arch_rep, "synthese"))
        # Réinjection architecture : accepter les clés SI et les clés mm/N_cyl renvoyées par architecture.py.
        arch_inject = {
            "alesage_m": _first_finite(_dig(arch_res, "alesage_m"), _dig(arch_res, "bore_m"), (_dig(arch_res, "bore_mm") / 1000.0) if _is_finite(_dig(arch_res, "bore_mm")) else None),
            "course_m": _first_finite(_dig(arch_res, "course_m"), _dig(arch_res, "stroke_m"), (_dig(arch_res, "course_mm") / 1000.0) if _is_finite(_dig(arch_res, "course_mm")) else None),
            "nombre_cylindres": _first_non_none(_dig(arch_res, "nombre_cylindres"), _dig(arch_res, "N_cyl")),
            "architecture": _dig(arch_res, "architecture"),
        }
        for k_dst, v in arch_inject.items():
            if v is not None and mt_cfg.get(k_dst) is None:
                mt_cfg[k_dst] = v
        if mt_cfg:
            comps_report["moteur_thermique"] = self._run_moteur_thermique(mt_cfg, strict=strict)
            _merge_inconnues(rapport, comps_report["moteur_thermique"], prefix="moteur_thermique")
        else:
            _push(rapport, "partielles", "moteur_thermique", "Aucune définition moteur thermique fournie.")

        rapport["construction"]["composants"] = {
            name: {"cfg": _to_jsonable(self._build_component_cfg(name, resolved, systeme_final), max_depth=6), "rapport_present": name in comps_report}
            for name in ("moteur_electrique", "batterie", "alternateur", "boite_crabots", "architecture", "moteur_thermique")
        }

    def _run_moteur_electrique(self, cfg: Mapping[str, Any], *, strict: bool) -> Dict[str, Any]:
        if callable(concevoir_moteur_electrique):
            try:
                return _to_jsonable(concevoir_moteur_electrique(cfg), max_depth=8)
            except Exception as exc:
                return {"composant": "moteur_electrique", "erreur": str(exc), "inconnues": {"impossibles": [{"nom": "concevoir_moteur_electrique", "raison": str(exc)}], "partielles": []}}
        if MoteurElectrique is None:
            return {"composant": "moteur_electrique", "inconnues": {"impossibles": [{"nom": "MoteurElectrique", "raison": "Classe indisponible."}], "partielles": []}}
        try:
            obj = _construct_dataclass_or_class(MoteurElectrique, cfg)
            rep = _safe_call_report(obj, strict=strict) or {"definition": _to_jsonable(obj)}
            return _to_jsonable(rep, max_depth=8)
        except Exception as exc:
            return {"composant": "moteur_electrique", "erreur": str(exc), "inconnues": {"impossibles": [{"nom": "construction_moteur_electrique", "raison": str(exc)}], "partielles": []}}

    def _run_batterie(self, cfg: Mapping[str, Any], *, strict: bool) -> Dict[str, Any]:
        if callable(concevoir_batterie):
            try:
                return _to_jsonable(concevoir_batterie(cfg), max_depth=8)
            except Exception as exc:
                return {"composant": "batterie", "erreur": str(exc), "inconnues": {"impossibles": [{"nom": "concevoir_batterie", "raison": str(exc)}], "partielles": []}}
        if Batterie is None:
            return {"composant": "batterie", "inconnues": {"impossibles": [{"nom": "Batterie", "raison": "Classe indisponible."}], "partielles": []}}
        try:
            ctor_cfg = {k: v for k, v in cfg.items() if k not in ("energie_utile_imposee_kwh", "puissance_moyenne_kw", "puissance_pic_kw", "duree_pic_s")}
            obj = _construct_dataclass_or_class(Batterie, ctor_cfg)
            # analyser_dimensionnement est le cœur de batterie_robuste.
            fn = getattr(obj, "analyser_dimensionnement", None)
            if callable(fn):
                report = _call_supported(fn, **dict(cfg))
                return _to_jsonable(report, max_depth=8)
            rep = _safe_call_report(obj, strict=strict) or {"definition": _to_jsonable(obj)}
            return _to_jsonable(rep, max_depth=8)
        except Exception as exc:
            return {"composant": "batterie", "erreur": str(exc), "inconnues": {"impossibles": [{"nom": "construction_batterie", "raison": str(exc)}], "partielles": []}}

    def _alternateur_point_cfg(self, alt_cfg: Mapping[str, Any], resolved: Mapping[str, Any], systeme_final: Mapping[str, Any]) -> Dict[str, Any]:
        pbus = _first_finite(_dig(systeme_final, "sous_systemes", "sortie_et_bus_dc", "puissances", "P_bus_dc_sortie_max_total_w"), resolved.get("puissance_bus_dc_w"))
        vbus = _first_finite(_dig(alt_cfg, "interface_bus_dc", "tension_bus_dc_v"), _dig(systeme_final, "entrees_normalisees", "batterie", "tension_nominale_v"), resolved.get("tension_bus_dc_v"), resolved.get("V_bus_dc_v"))
        rpm_alt = _first_finite(_dig(alt_cfg, "plage_regime", "rpm_cible"), resolved.get("rpm_alternateur"), resolved.get("vitesse_alternateur_rpm"))
        return _clean_nones({"puissance_bus_dc_w": pbus, "tension_bus_dc_v": vbus, "vitesse_rotation_rpm": rpm_alt})

    def _run_alternateur(self, cfg: Mapping[str, Any], point_cfg: Mapping[str, Any], *, strict: bool) -> Dict[str, Any]:
        merged = _deep_merge({"alternateur": dict(cfg)}, {"analyse_bus_dc": dict(point_cfg)})
        if callable(concevoir_alternateur):
            try:
                return _to_jsonable(concevoir_alternateur(merged), max_depth=8)
            except Exception as exc:
                return {"composant": "alternateur", "erreur": str(exc), "inconnues": {"impossibles": [{"nom": "concevoir_alternateur", "raison": str(exc)}], "partielles": []}}
        if Alternateur is None:
            return {"composant": "alternateur", "inconnues": {"impossibles": [{"nom": "Alternateur", "raison": "Classe indisponible."}], "partielles": []}}
        try:
            obj = _construct_dataclass_or_class(Alternateur, cfg)
            if hasattr(obj, "analyser_pour_bus_dc") and point_cfg.get("puissance_bus_dc_w") is not None:
                rep = _call_supported(obj.analyser_pour_bus_dc, **dict(point_cfg))
            else:
                rep = _safe_call_report(obj, strict=strict, **dict(point_cfg)) or {"definition": _to_jsonable(obj)}
            return _to_jsonable(rep, max_depth=8)
        except Exception as exc:
            return {"composant": "alternateur", "erreur": str(exc), "inconnues": {"impossibles": [{"nom": "construction_alternateur", "raison": str(exc)}], "partielles": []}}

    def _boite_point_cfg(self, boite_cfg: Mapping[str, Any], resolved: Mapping[str, Any], systeme_final: Mapping[str, Any]) -> Dict[str, Any]:
        pbus = _first_finite(_dig(systeme_final, "sous_systemes", "sortie_et_bus_dc", "puissances", "P_bus_dc_sortie_max_total_w"), resolved.get("puissance_bus_dc_w"))
        vbus = _first_finite(_dig(systeme_final, "entrees_normalisees", "batterie", "tension_nominale_v"), resolved.get("tension_bus_dc_v"), resolved.get("V_bus_dc_v"))
        rpm_mt = _first_finite(boite_cfg.get("rpm_moteur_optimal"), resolved.get("rpm_moteur"), resolved.get("rpm_moteur_nominal"))
        rapports = _first_non_none(boite_cfg.get("rapports"), _dig(systeme_final, "entrees_normalisees", "transmission_generation", "rapports_boite"))
        return _clean_nones({
            "puissance_bus_dc_w": pbus,
            "tension_bus_dc_v": vbus,
            "rpm_moteur": rpm_mt,
            "rapports": rapports,
            "rendement_boite": _first_finite(boite_cfg.get("rendement_boite_defaut"), _dig(systeme_final, "entrees_normalisees", "transmission_generation", "rendement_boite"), resolved.get("rendement_boite")),
            "rpm_alternateur_cible": _first_finite(boite_cfg.get("rpm_alternateur_cible"), _dig(systeme_final, "entrees_normalisees", "transmission_generation", "rpm_alternateur_cible"), resolved.get("rpm_alternateur")),
            "strategie": "pareto",
        })

    def _run_boite(self, cfg: Mapping[str, Any], point_cfg: Mapping[str, Any], *, strict: bool) -> Dict[str, Any]:
        merged = _deep_merge({"boite_crabots": dict(cfg)}, {"analyse": dict(point_cfg)})
        if callable(concevoir_boite_crabots):
            try:
                return _to_jsonable(concevoir_boite_crabots(merged), max_depth=8)
            except Exception as exc:
                return {"composant": "boite_crabots", "erreur": str(exc), "inconnues": {"impossibles": [{"nom": "concevoir_boite_crabots", "raison": str(exc)}], "partielles": []}}
        if BoiteCrabots is None:
            return {"composant": "boite_crabots", "inconnues": {"impossibles": [{"nom": "BoiteCrabots", "raison": "Classe indisponible."}], "partielles": []}}
        try:
            obj = _construct_dataclass_or_class(BoiteCrabots, cfg)
            if hasattr(obj, "analyser_chaine"):
                rep = _call_supported(obj.analyser_chaine, **dict(point_cfg))
            else:
                rep = _safe_call_report(obj, strict=strict, **dict(point_cfg)) or {"definition": _to_jsonable(obj)}
            return _to_jsonable(rep, max_depth=8)
        except Exception as exc:
            return {"composant": "boite_crabots", "erreur": str(exc), "inconnues": {"impossibles": [{"nom": "construction_boite_crabots", "raison": str(exc)}], "partielles": []}}

    def _run_architecture(self, cfg: Mapping[str, Any], *, strict: bool) -> Dict[str, Any]:
        if callable(concevoir_architecture):
            try:
                return _to_jsonable(concevoir_architecture(cfg), max_depth=8)
            except Exception as exc:
                return {"composant": "architecture", "erreur": str(exc), "inconnues": {"impossibles": [{"nom": "concevoir_architecture", "raison": str(exc)}], "partielles": []}}
        if Architecture is None:
            return {"composant": "architecture", "inconnues": {"impossibles": [{"nom": "Architecture", "raison": "Classe indisponible."}], "partielles": []}}
        try:
            obj = _construct_dataclass_or_class(Architecture, cfg)
            rep = _safe_call_report(obj, strict=strict, **dict(cfg)) or {"definition": _to_jsonable(obj)}
            return _to_jsonable(rep, max_depth=8)
        except Exception as exc:
            return {"composant": "architecture", "erreur": str(exc), "inconnues": {"impossibles": [{"nom": "construction_architecture", "raison": str(exc)}], "partielles": []}}

    def _run_moteur_thermique(self, cfg: Mapping[str, Any], *, strict: bool) -> Dict[str, Any]:
        # MoteurThermique.definir_depuis_exigences si disponible.
        if MoteurThermique is not None and hasattr(MoteurThermique, "definir_depuis_exigences"):
            try:
                return _to_jsonable(_call_supported(MoteurThermique.definir_depuis_exigences, **dict(cfg)), max_depth=8)
            except Exception:
                pass
        if OrchestrateurMoteurThermique is not None:
            try:
                if EntreesOrchestrateurMoteurThermique is not None:
                    entree = _construct_dataclass_or_class(EntreesOrchestrateurMoteurThermique, cfg)
                    orch = OrchestrateurMoteurThermique(entree)
                else:
                    orch = OrchestrateurMoteurThermique(**dict(cfg))
                rep = _safe_call_report(orch, strict=strict) or {"definition": _to_jsonable(orch)}
                return _to_jsonable(rep, max_depth=8)
            except Exception as exc:
                return {"composant": "moteur_thermique", "erreur": str(exc), "inconnues": {"impossibles": [{"nom": "OrchestrateurMoteurThermique", "raison": str(exc)}], "partielles": []}}
        if MoteurThermique is not None:
            try:
                obj = _construct_dataclass_or_class(MoteurThermique, cfg)
                rep = _safe_call_report(obj, strict=strict, **dict(cfg)) or {"definition": _to_jsonable(obj)}
                return _to_jsonable(rep, max_depth=8)
            except Exception as exc:
                return {"composant": "moteur_thermique", "erreur": str(exc), "inconnues": {"impossibles": [{"nom": "construction_moteur_thermique", "raison": str(exc)}], "partielles": []}}
        return {"composant": "moteur_thermique", "inconnues": {"impossibles": [{"nom": "MoteurThermique", "raison": "Classe/orchestrateur indisponible."}], "partielles": []}}

    # ------------------------------------------------------------------
    # Pièces / optimisation / stratégie énergie
    # ------------------------------------------------------------------
    def _run_pieces(self, rapport: Dict[str, Any], *, strict: bool) -> None:
        # Ce fichier ne force pas la construction de toutes les pièces si leurs classes ne sont pas importables.
        # Les composants spécialisés moteur thermique / batterie / alternateur / boîte analysent déjà leurs pièces.
        if not self.pieces:
            _push(rapport, "partielles", "pieces", "Aucune pièce explicitement demandée dans config['pieces']; les pièces internes des composants restent analysées quand leurs modules le font.")
            return
        for name, payload in self.pieces.items():
            if not isinstance(payload, Mapping):
                _push(rapport, "partielles", f"piece.{name}", "Payload pièce non dictionnaire, construction ignorée.")
                continue
            # Import dynamique depuis nom de fichier pièce.
            cls_name_candidates = [
                "".join(part.capitalize() for part in str(name).split("_")),
                str(name),
            ]
            cls = None
            for module_base in (str(name), f"backend.components.moteur_thermique.pieces.{name}", f"components.moteur_thermique.pieces.{name}"):
                try:
                    mod = importlib.import_module(module_base)
                    for cn in cls_name_candidates:
                        if hasattr(mod, cn):
                            cls = getattr(mod, cn)
                            break
                    if cls is not None:
                        break
                except Exception:
                    continue
            if cls is None:
                _push(rapport, "partielles", f"piece.{name}", "Classe pièce non importable automatiquement.")
                continue
            try:
                contexte_piece = _deep_merge(
                    {
                        "rapport_systeme": rapport,
                        "systeme_complet": rapport,
                        "synthese_systeme": rapport.get("synthese"),
                        "sous_systemes": rapport.get("sous_systemes"),
                        "rapports_pieces": rapport.get("rapports", {}).get("pieces"),
                        "moteur_thermique": rapport.get("sous_systemes", {}).get("moteur_thermique"),
                    },
                    _safe_dict(payload),
                )
                for dep_name, dep_obj in self.pieces_obj.items():
                    contexte_piece.setdefault(dep_name, dep_obj)
                obj = _construct_dataclass_or_class(cls, contexte_piece)
                rep = _safe_call_report(obj, strict=strict, **contexte_piece) or {"definition": _to_jsonable(obj)}
                self.pieces_obj[name] = obj
                rapport["rapports"]["pieces"][name] = _to_jsonable(rep, max_depth=7)
                rapport["construction"]["pieces"][name] = {
                    "classe": getattr(cls, "__name__", str(cls)),
                    "contexte_recu": sorted(k for k in contexte_piece if k not in {"rapport_systeme", "systeme_complet"}),
                    "dependances_pieces_disponibles": sorted(self.pieces_obj.keys()),
                    "cao_present": bool(_dig(rep, "cao") or _dig(rep, "bloc_cao") or _dig(rep, "solidworks")),
                }
                _merge_inconnues(rapport, rep, prefix=f"piece.{name}")
            except Exception as exc:
                _push(rapport, "partielles", f"piece.{name}", str(exc))

    def _run_strategie_energie(self, rapport: Dict[str, Any]) -> None:
        if not callable(calculer_strategie_couplage):
            _push(rapport, "partielles", "strategie_energie", "Module strategie_energie indisponible.")
            return
        try:
            # Appel volontairement filtré : les versions du module évoluent.
            out = _call_supported(
                calculer_strategie_couplage,
                rapport_systeme=rapport,
                rapport=rapport,
                etat_systeme=rapport.get("synthese"),
                batterie=rapport.get("sous_systemes", {}).get("batterie"),
                alternateur=rapport.get("sous_systemes", {}).get("alternateur"),
                boite=rapport.get("sous_systemes", {}).get("boite_crabots"),
                moteur_thermique=rapport.get("sous_systemes", {}).get("moteur_thermique"),
            )
            if isinstance(out, Mapping):
                rapport["rapports"]["strategie_energie"] = _to_jsonable(out, max_depth=8)
                _merge_inconnues(rapport, out, prefix="strategie_energie")
        except Exception as exc:
            _push(rapport, "partielles", "strategie_energie", str(exc))

    def _run_optimisation(self, rapport: Dict[str, Any], *, strict: bool) -> None:
        if callable(optimiser_rapport_sthome):
            try:
                out = _call_supported(
                    optimiser_rapport_sthome,
                    rapport_backend=rapport,
                    rapports_pieces=_safe_dict(_dig(rapport, "rapports", "pieces")),
                    cahier_des_charges=_safe_dict(self.meta.get("cahier_des_charges")) or _safe_dict(self.analyses.get("cahier_des_charges")),
                    strict=strict,
                )
                if isinstance(out, Mapping):
                    rapport["rapports"]["optimisation"] = _to_jsonable(out, max_depth=8)
                    _merge_inconnues(rapport, out, prefix="optimisation")
                    return
            except Exception as exc:
                _push(rapport, "partielles", "optimisation", str(exc))
        if OptimisationSysteme is not None:
            try:
                obj = OptimisationSysteme()
                out = _safe_call_report(obj, strict=False, rapport=rapport)
                if isinstance(out, Mapping):
                    rapport["rapports"]["optimisation"] = _to_jsonable(out, max_depth=8)
                    _merge_inconnues(rapport, out, prefix="optimisation")
                    return
            except Exception as exc:
                _push(rapport, "partielles", "OptimisationSysteme", str(exc))
        rapport["rapports"]["optimisation"] = {"mode": "indisponible", "note": "Aucun optimiseur exploitable importé."}

    # ------------------------------------------------------------------
    # Synthèse / contrat frontend / CAO
    # ------------------------------------------------------------------
    def _build_synthese(self, rapport: Dict[str, Any], resolved: Mapping[str, Any], systeme_final: Mapping[str, Any]) -> None:
        final_syn = _safe_dict(_dig(systeme_final, "synthese"))
        comp = _safe_dict(rapport.get("rapports", {}).get("composants"))
        mt_rep = _safe_dict(comp.get("moteur_thermique"))
        arch_rep = _safe_dict(comp.get("architecture"))
        batt_rep = _safe_dict(comp.get("batterie"))
        alt_rep = _safe_dict(comp.get("alternateur"))
        boite_rep = _safe_dict(comp.get("boite_crabots"))

        synth = {
            "puissance_sortie_max_demandee_kw": _first_finite(final_syn.get("puissance_sortie_max_demandee_kw"), (_extract_p_sortie_w({"analyses": self.analyses}, resolved) or 0) / 1000.0 if _extract_p_sortie_w({"analyses": self.analyses}, resolved) is not None else None),
            "puissance_sortie_installee_max_kw": final_syn.get("puissance_sortie_installee_max_kw"),
            "ok_moteurs_sortie_pleine_puissance": final_syn.get("ok_moteurs_sortie_pleine_puissance"),
            "P_bus_dc_pleine_sortie_kw": final_syn.get("P_bus_dc_pleine_sortie_kw"),
            "P_arbre_thermique_requise_pleine_sortie_kw": final_syn.get("P_arbre_thermique_requise_pleine_sortie_kw"),
            "ok_thermique_pleine_puissance": final_syn.get("ok_thermique_pleine_puissance"),
            "puissance_croisiere_selectionnee_kw": final_syn.get("puissance_croisiere_selectionnee_kw"),
            "bsfc_croisiere_g_kwh": final_syn.get("bsfc_croisiere_g_kwh"),
            "debit_carburant_croisiere_g_h": final_syn.get("debit_carburant_croisiere_g_h"),
            "batterie_energie_utile_kwh": _first_finite(final_syn.get("batterie_energie_utile_kwh"), _dig(batt_rep, "synthese", "energie_utile_recommandee_kwh"), _dig(batt_rep, "synthese", "capacite_nominale_recommandee_kwh")),
            "batterie_ok_c_rate_pic": final_syn.get("batterie_ok_c_rate_pic"),
            "batterie_ok_temps_recharge": final_syn.get("batterie_ok_temps_recharge"),
            "architecture_moteur": _first_non_none(_dig(mt_rep, "synthese", "architecture"), _dig(arch_rep, "selection", "architecture"), _dig(arch_rep, "meilleur", "architecture"), _dig(arch_rep, "meilleur_candidat", "architecture"), resolved.get("architecture_moteur"), resolved.get("architecture")),
            "nombre_cylindres": _si(_first_non_none(_dig(mt_rep, "synthese", "nombre_cylindres"), _dig(arch_rep, "selection", "nombre_cylindres"), _dig(arch_rep, "meilleur", "nombre_cylindres"), _dig(arch_rep, "meilleur", "N_cyl"), resolved.get("nombre_cylindres"))),
            "alesage_m": _first_finite(_dig(mt_rep, "synthese", "alesage_m"), _dig(arch_rep, "selection", "alesage_m"), _dig(arch_rep, "meilleur", "alesage_m"), _dig(arch_rep, "meilleur", "bore_m"), (_dig(arch_rep, "meilleur", "bore_mm") / 1000.0) if _is_finite(_dig(arch_rep, "meilleur", "bore_mm")) else None, resolved.get("alesage_m")),
            "course_m": _first_finite(_dig(mt_rep, "synthese", "course_m"), _dig(arch_rep, "selection", "course_m"), _dig(arch_rep, "meilleur", "course_m"), _dig(arch_rep, "meilleur", "stroke_m"), (_dig(arch_rep, "meilleur", "course_mm") / 1000.0) if _is_finite(_dig(arch_rep, "meilleur", "course_mm")) else None, resolved.get("course_m")),
            "rpm_moteur_thermique": _first_finite(_dig(mt_rep, "synthese", "rpm_nominal"), resolved.get("rpm_moteur"), resolved.get("rpm_moteur_nominal")),
            "rpm_alternateur": _first_finite(_dig(alt_rep, "resultats", "vitesse_rotation_rpm"), resolved.get("rpm_alternateur"), resolved.get("vitesse_alternateur_rpm")),
            "rapport_boite_alt_sur_moteur": _first_finite(_dig(boite_rep, "selection", "rapport"), resolved.get("rapport_vitesse_alt_sur_moteur"), resolved.get("rapport_boite_alt")),
            "nb_inconnues_impossibles": len(rapport.get("inconnues", {}).get("impossibles", [])),
            "nb_inconnues_partielles": len(rapport.get("inconnues", {}).get("partielles", [])),
        }
        verdicts = _safe_dict(final_syn.get("verdicts"))
        synth["verdicts"] = verdicts or {
            "sortie_utile": "OK" if synth.get("ok_moteurs_sortie_pleine_puissance") is True else "NON_VERIFIE_OU_INSUFFISANT",
            "generation_pleine_sortie": "OK" if synth.get("ok_thermique_pleine_puissance") is True else "NON_VERIFIE_OU_INSUFFISANT",
            "cycle_croisiere": "OK" if synth.get("puissance_croisiere_selectionnee_kw") is not None else "NON_SELECTIONNE",
        }
        rapport["synthese"] = _to_jsonable(synth, max_depth=6)

        rapport["sous_systemes"] = {
            "sortie_et_bus_dc": _dig(systeme_final, "sous_systemes", "sortie_et_bus_dc"),
            "batterie": batt_rep or _dig(systeme_final, "sous_systemes", "batterie_tampon"),
            "alternateur": alt_rep or _dig(systeme_final, "sous_systemes", "alternateur_boite_modules"),
            "boite_crabots": boite_rep or _dig(systeme_final, "sous_systemes", "alternateur_boite_modules"),
            "moteur_thermique": mt_rep or _dig(systeme_final, "sous_systemes", "moteurs_thermiques_pleine_sortie"),
            "architecture": arch_rep,
            "mobilite": _dig(systeme_final, "sous_systemes", "mobilite"),
        }
        rapport["liaisons"] = _safe_dict(_dig(systeme_final, "liaisons"))
        rapport["definition_complete"] = {
            "moteur_electrique": comp.get("moteur_electrique"),
            "batterie": comp.get("batterie"),
            "alternateur": comp.get("alternateur"),
            "boite_crabots": comp.get("boite_crabots"),
            "architecture": comp.get("architecture"),
            "moteur_thermique": comp.get("moteur_thermique"),
        }

    def _build_cao_frontend(self, rapport: Dict[str, Any]) -> None:
        synth = _safe_dict(rapport.get("synthese"))
        sketch_ready = all(_sf(synth.get(k)) is not None for k in ("alesage_m", "course_m")) and synth.get("nombre_cylindres") is not None
        missing_geom = [k for k in ("alesage_m", "course_m", "nombre_cylindres") if synth.get(k) is None]
        pieces_reports = _safe_dict(_dig(rapport, "rapports", "pieces"))
        pieces_fermees: List[str] = []
        pieces_non_fermees: List[str] = []
        for pname, prep in pieces_reports.items():
            prep_map = _safe_dict(prep)
            cao_piece = _safe_dict(prep_map.get("cao") or prep_map.get("bloc_cao") or prep_map.get("solidworks"))
            closed = bool(cao_piece.get("solidworks_ready") or cao_piece.get("complete") or cao_piece.get("fermee"))
            (pieces_fermees if closed else pieces_non_fermees).append(str(pname))
        rapport["cao"] = {
            "solidworks_ready": False,
            "step_export": False,
            "sketches_available": bool(sketch_ready),
            "views_3d_available": bool(sketch_ready),
            "stress_graphs_available": bool(rapport.get("mechanical_graphs")),
            "drawing_data_available": bool(sketch_ready),
            "missing_geometry": missing_geom,
            "raison": "Le but est de fournir croquis, vues 3D et graphes de contraintes ; l'export STEP reste bloqué tant que toutes les pièces ne sont pas fermées.",
            "cotes_moteur_thermique": {
                "architecture": synth.get("architecture_moteur"),
                "nombre_cylindres": synth.get("nombre_cylindres"),
                "alesage_m": synth.get("alesage_m"),
                "course_m": synth.get("course_m"),
                "rpm_nominal": synth.get("rpm_moteur_thermique"),
            },
            "pieces_fermees": pieces_fermees,
            "pieces_non_fermees": pieces_non_fermees,
        }
        resolution_frontend = _safe_dict(_dig(rapport, "resolution_inconnues", "frontend_contract"))
        graphes = _first_non_none(
            rapport.get("mechanical_graphs"),
            _dig(rapport, "rapports", "mechanical_graphs"),
            {"available": False, "reason": "Aucune donnee de graphe mecanique calculee dans ce rapport."},
        )
        rapport["frontend"] = {
            "status": "ok" if not rapport.get("inconnues", {}).get("impossibles") else "partial",
            "resume_cards": [
                {"id": "sortie", "label": "Sortie utile", "value": synth.get("puissance_sortie_max_demandee_kw"), "unit": "kW"},
                {"id": "bus_dc", "label": "Bus DC pleine sortie", "value": synth.get("P_bus_dc_pleine_sortie_kw"), "unit": "kW"},
                {"id": "thermique", "label": "Thermique arbre requis", "value": synth.get("P_arbre_thermique_requise_pleine_sortie_kw"), "unit": "kW"},
                {"id": "croisiere", "label": "Croisière retenue", "value": synth.get("puissance_croisiere_selectionnee_kw"), "unit": "kW"},
                {"id": "batterie", "label": "Batterie utile", "value": synth.get("batterie_energie_utile_kwh"), "unit": "kWh"},
            ],
            "verdicts": synth.get("verdicts", {}),
            "inconnues": rapport.get("inconnues", {}),
            "cao": rapport.get("cao", {}),
        }
        for card in rapport["frontend"].get("resume_cards", []):
            if card.get("value") is not None:
                card["missing_reason"] = None
            elif card.get("id") == "sortie":
                card["missing_reason"] = "Puissance utile non fournie."
            elif card.get("id") == "bus_dc":
                card["missing_reason"] = "Rendements, auxiliaires ou tension bus incomplets."
            elif card.get("id") == "thermique":
                card["missing_reason"] = "Chaine alternateur/boite non fermee."
            elif card.get("id") == "croisiere":
                card["missing_reason"] = "Profil de croisiere absent ou non valide."
            elif card.get("id") == "batterie":
                card["missing_reason"] = "Enveloppe batterie non fermee."
        rapport["frontend"].update(
            {
                "alertes": rapport.get("alertes", {}),
                "resolution": resolution_frontend,
                "strategie_energie": _safe_dict(_dig(rapport, "rapports", "strategie_energie")),
                "optimisation": _safe_dict(_dig(rapport, "rapports", "optimisation")),
                "graphes": graphes,
                "statuts": {
                    "definition_complete": bool(rapport.get("definition_complete")),
                    "pieces_fermees": pieces_fermees,
                    "pieces_non_fermees": pieces_non_fermees,
                },
                "traces": rapport.get("tracabilite", {}),
            }
        )

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def analyser(
        self,
        *,
        config: Optional[Mapping[str, Any]] = None,
        cahier_des_charges: Optional[Mapping[str, Any]] = None,
        repository: Any = None,
        resolve_unknowns: bool = True,
        optimize: bool = True,
        strict: bool = False,
        frontend_contract: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if config is not None or cahier_des_charges is not None or kwargs:
            merged: Dict[str, Any] = {
                "meta": _to_jsonable(self.meta, max_depth=6),
                "composants": _to_jsonable(self.composants, max_depth=6),
                "pieces": _to_jsonable(self.pieces, max_depth=6),
                "analyses": _to_jsonable(self.analyses, max_depth=6),
            }
            if isinstance(config, Mapping):
                merged = _deep_merge(merged, config)
            if isinstance(cahier_des_charges, Mapping):
                merged["meta"] = _deep_merge(_safe_dict(merged.get("meta")), {"cahier_des_charges": dict(cahier_des_charges)})
                merged["analyses"] = _deep_merge(_safe_dict(merged.get("analyses")), {"cahier_des_charges": dict(cahier_des_charges)})
            if kwargs:
                merged["analyses"] = _deep_merge(_safe_dict(merged.get("analyses")), {"stho_me": dict(kwargs), "systeme_complet": dict(kwargs)})
            return STHO_ME.depuis_config(merged).analyser(
                repository=repository,
                resolve_unknowns=resolve_unknowns,
                optimize=optimize,
                strict=strict,
                frontend_contract=frontend_contract,
            )

        rapport = self._new_report()
        project_id = str(self.meta.get("project_id") or self.meta.get("id_projet") or self.meta.get("nom_projet") or "") or None

        resolved: Dict[str, Any] = {}
        if resolve_unknowns:
            resolved = self._run_resolution(rapport, strict=strict, optimize=optimize, repository=repository, project_id=project_id)
        rapport["donnees_auto_completees"] = _to_jsonable(resolved, max_depth=7)

        systeme_final = self._run_aboutissement_systeme(rapport, resolved)
        self._run_component_analyses(rapport, resolved, systeme_final, strict=strict)
        self._run_pieces(rapport, strict=strict)
        _dedup(rapport)
        self._build_synthese(rapport, resolved, systeme_final)
        self._run_strategie_energie(rapport)
        if optimize:
            self._run_optimisation(rapport, strict=strict)
        else:
            rapport["rapports"]["optimisation"] = {"mode": "desactive", "note": "Optimisation désactivée par appelant."}

        _dedup(rapport)
        self._build_synthese(rapport, resolved, systeme_final)
        self._build_cao_frontend(rapport)
        _dedup(rapport)
        # Mise à jour compteurs après toutes les fusions.
        rapport["synthese"]["nb_inconnues_impossibles"] = len(rapport.get("inconnues", {}).get("impossibles", []))
        rapport["synthese"]["nb_inconnues_partielles"] = len(rapport.get("inconnues", {}).get("partielles", []))
        if not frontend_contract:
            rapport.pop("frontend", None)
        return _to_jsonable(rapport, max_depth=12)

    def export_json(self, path: str | os.PathLike[str], *, indent: int = 2, **analyse_kwargs: Any) -> str:
        rapport = self.analyser(**analyse_kwargs)
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rapport, ensure_ascii=False, indent=indent), encoding="utf-8")
        return str(out)


# =============================================================================
# Fonctions haut niveau
# =============================================================================


def concevoir_systeme_stho_me(config: Mapping[str, Any], **kwargs: Any) -> Dict[str, Any]:
    return STHO_ME.depuis_config(config).analyser(**kwargs)


def sauvegarder_conception_stho_me(config: Mapping[str, Any], path_json: str | os.PathLike[str], *, indent: int = 2, **kwargs: Any) -> str:
    return STHO_ME.depuis_config(config).export_json(path_json, indent=indent, **kwargs)


def charger_config_json(path: str | os.PathLike[str]) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


__all__ = [
    "STHO_ME",
    "concevoir_systeme_stho_me",
    "sauvegarder_conception_stho_me",
    "charger_config_json",
]


# =============================================================================
# Démo minimale
# =============================================================================

if __name__ == "__main__":
    exemple_config: Dict[str, Any] = {
        "meta": {"nom_projet": "STHO-ME", "mode": "demo_100kw"},
        "sortie": {
            "puissance_sortie_max_w": 100_000.0,
            "puissance_sortie_continue_w": 65_000.0,
            "puissance_sortie_croisiere_min_w": 35_000.0,
        },
        "moteurs_sortie": [
            {
                "nom": "moteur_sortie_principal",
                "quantite": 1,
                "puissance_max_w": 110_000.0,
                "puissance_continue_w": 70_000.0,
                "rendement_moteur": 0.94,
                "rendement_transmission": 0.99,
                "tension_bus_v": 400.0,
                "regime_max_rpm": 8000.0,
                "couple_max_nm": 260.0,
            }
        ],
        "auxiliaires": [
            {"nom": "pompes_refroidissement", "puissance_continue_w": 900.0, "puissance_pic_w": 1500.0, "duty": 1.0},
            {"nom": "electronique_controle", "puissance_continue_w": 350.0, "duty": 1.0},
        ],
        "moteurs_thermiques": [
            {
                "nom": "thermique_sthome",
                "quantite": 1,
                "puissance_arbre_max_w": 145_000.0,
                "puissance_arbre_continue_w": 95_000.0,
                "rpm_optimal": 3000.0,
                "rpm_min_optimal": 2600.0,
                "rpm_max_optimal": 3400.0,
                "bsfc_g_kwh": 227.0,
                "charge_min_efficiente": 0.35,
                "charge_max_durable": 0.75,
                "duty_max": 0.50,
            }
        ],
        "batterie": {
            "tension_nominale_v": 400.0,
            "capacite_nominale_kwh": 24.0,
            "fenetre_soc": 0.70,
            "densite_energetique_kwh_kg": 0.16,
            "c_rate_decharge_continue_max": 3.0,
            "c_rate_decharge_pic_max": 6.0,
            "c_rate_charge_max": 1.2,
            "temps_recharge_max_h": 1.5,
            "autonomie_elec_min_h": 0.20,
        },
        "transmission_generation": {
            "rendement_boite": 0.94,
            "rendement_alternateur": 0.92,
            "rendement_redressement": 0.96,
            "rendement_charge": 0.95,
            "rpm_alternateur_cible": 9000.0,
            "rpm_alternateur_min_optimal": 7500.0,
            "rpm_alternateur_max_optimal": 10500.0,
            "rapports_boite": [2.5, 3.0, 3.2, 3.5, 4.0],
        },
        "cycle_croisiere": {
            "strategie": "max_puissance_sous_contraintes",
            "fractions_puissance": [0.25, 0.35, 0.45, 0.55, 0.65],
            "bsfc_max_g_kwh": 260.0,
            "charge_moteur_max_durable": 0.75,
            "duty_moteur_max": 0.50,
        },
        "composants": {
            "alternateur": {
                "nombre_poles": 8,
                "connexion": "Y",
                "rendement_alternateur_impose": 0.92,
                "interface_bus_dc": {"tension_bus_dc_v": 400.0, "rendement_redressement": 0.96},
                "plage_regime": {"rpm_cible": 9000.0, "rpm_min_optimal": 7500.0, "rpm_max_optimal": 10500.0},
            },
            "boite_crabots": {
                "rpm_moteur_optimal": 3000.0,
                "rpm_alternateur_cible": 9000.0,
                "rapports": [2.5, 3.0, 3.2, 3.5, 4.0],
                "rendement_boite_defaut": 0.94,
            },
            "moteur_thermique": {
                "rpm": 3000.0,
                "pression_moyenne_effective_pa": 800_000.0,
                "pression_max_pa": 3_600_000.0,
                "temps_moteur": 4,
                "vitesse_piston_max_ms": 25.0,
                "ratio_course_alesage_max": 1.30,
            },
            "architecture": {
                "longueur_dispo_m": 1.20,
                "largeur_dispo_m": 0.80,
                "hauteur_dispo_m": 0.75,
                "architectures_autorisees": ["L", "V", "Boxer"],
            },
        },
    }

    r = concevoir_systeme_stho_me(exemple_config, resolve_unknowns=False, optimize=False, strict=False)
    print(json.dumps(r.get("synthese", {}), ensure_ascii=False, indent=2))
