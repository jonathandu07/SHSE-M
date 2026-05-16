"""Adaptateur strict backend -> frontend pour les rapports STHO/SHSE-M.

Principe non négociable :
- ce module ne lance aucun calcul physique ;
- il ne transforme jamais une absence en zéro ;
- il ne fabrique jamais de cote, de rendement, de score ou de chemin CAO ;
- il expose au frontend ce qui existe déjà dans le rapport backend, avec source,
  statut, chemin brut et raison d'indisponibilité.

Rôle :
- normaliser les rapports backend hétérogènes ;
- construire un modèle UI stable : dashboard, sous-systèmes, pièces, ressources,
  exports, paramètres éditables, inconnues, alertes, arbre JSON ;
- faciliter le branchement de frontend/components sur les données issues du
  backend/components, sans invention côté interface.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# =============================================================================
# Configuration
# =============================================================================

SCHEMA_VERSION = "report_adapter.v2.strict"

_HEAVY_KEYS = {
    "objets_serialises",
    "toutes_les_donnees_pieces",
    "toutes_les_donnees_composants",
    "raw",
    "raw_json",
    "__object__",
}

_NONE_LIKE = {"", "none", "null", "nan", "n/a", "na", "inconnu", "indisponible"}

_COMPONENT_ALIASES: Dict[str, Tuple[str, ...]] = {
    "batterie": (
        "batterie",
        "batterie_dimensionnement",
        "enveloppe_batterie",
    ),
    "moteur_electrique": (
        "moteur_electrique",
        "moteur_electrique_orchestrateur",
        "traction",
    ),
    "alternateur": (
        "alternateur",
        "alternateur_bus_dc",
        "alternateur_orchestrateur",
    ),
    "boite_crabots": (
        "boite_crabots",
        "boite_point",
        "boite_chaine",
        "boite_crabots_orchestrateur",
        "transmission",
    ),
    "moteur_thermique": (
        "moteur_thermique",
        "moteur_thermique_geometrie",
        "moteur_thermique_cycle",
        "moteur_thermique_point",
        "moteur_thermique_bilan_carburant",
        "construction_moteur_thermique",
    ),
    "architecture": (
        "architecture",
        "architecture_orchestrateur",
    ),
    "strategie_energie": (
        "strategie_energie",
        "energie",
        "bus_dc",
    ),
}

_PIECE_VISUAL_MODULES: Dict[str, Tuple[str, ...]] = {
    "sketches": ("sketches_2d.py", "croquis_2d.py", "sketches.py"),
    "charts": ("charts.py", "graphiques.py", "plots.py"),
    "three_d": ("views_3d.py", "mesh_3d.py", "three_d.py", "model_3d.py"),
}

_VISUAL_REPORT_KEYS: Dict[str, Tuple[str, ...]] = {
    "sketches": ("sketches", "croquis", "croquis_2d", "esquisses", "visualisation_2d"),
    "charts": ("charts", "graphiques", "courbes", "plots", "visualisation_graphique"),
    "three_d": ("three_d", "3d", "mesh_3d", "cao", "solidworks", "modele_3d", "visualisation_3d"),
}

_EXPORT_KEYS = (
    "exports",
    "export",
    "fichiers_export",
    "files",
    "artifacts",
    "artefacts",
)


def _project_root() -> Path:
    """Déduit la racine projet sans planter si le fichier est déplacé."""
    try:
        here = Path(__file__).resolve()
        parents = list(here.parents)
        if len(parents) >= 3:
            return parents[2]
        return parents[-1] if parents else Path.cwd()
    except Exception:
        return Path.cwd()


PROJECT_ROOT = _project_root()


# =============================================================================
# Helpers de base : typage, chemins, JSON
# =============================================================================

_MISSING = object()


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _is_sequence_but_not_text(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _is_present(value: Any, *, accept_empty_string: bool = False) -> bool:
    """Vrai si la valeur est réellement exploitable.

    Important : 0 et False sont des valeurs présentes.
    """
    if value is _MISSING or value is None:
        return False
    if isinstance(value, str) and not accept_empty_string:
        return value.strip().lower() not in _NONE_LIKE
    return True


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _split_path(path: str | Iterable[str]) -> List[str]:
    if isinstance(path, str):
        return [part for part in path.replace("[", ".").replace("]", "").split(".") if part != ""]
    return [str(part) for part in path]


def get_nested(data: Any, path: str | Iterable[str], default: Any = None) -> Any:
    """Lit un chemin pointé dans dict/list/objet sans lever d'exception.

    Exemples :
    - "a.b.c"
    - "pieces.0.nom"
    - ("a", "b", "c")
    """
    cur = data
    for key in _split_path(path):
        if isinstance(cur, Mapping):
            cur = cur.get(key, _MISSING)
        elif isinstance(cur, list):
            try:
                idx = int(key)
            except Exception:
                return default
            if idx < 0 or idx >= len(cur):
                return default
            cur = cur[idx]
        else:
            cur = getattr(cur, key, _MISSING)

        if cur is _MISSING:
            return default
    return cur


def first_present(report: Mapping[str, Any], *paths: str) -> tuple[Any, Optional[str]]:
    """Renvoie la première valeur présente avec son chemin source."""
    for path in paths:
        value = get_nested(report, path, _MISSING)
        if _is_present(value, accept_empty_string=True):
            return value, path
    return None, None


def _to_jsonable(value: Any, *, depth: int = 0, max_depth: int = 8) -> Any:
    """Convertit prudemment une valeur en objet sérialisable JSON."""
    if depth > max_depth:
        return {"truncated": True, "type": type(value).__name__}
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if key in _HEAVY_KEYS:
                out[key] = {"truncated": True, "reason": "section volontairement masquée côté frontend"}
                continue
            out[key] = _to_jsonable(v, depth=depth + 1, max_depth=max_depth)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v, depth=depth + 1, max_depth=max_depth) for v in value]
    if hasattr(value, "en_dict") and callable(getattr(value, "en_dict")):
        try:
            return _to_jsonable(value.en_dict(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return {
                "type": type(value).__name__,
                "attributs": _to_jsonable(
                    {k: v for k, v in vars(value).items() if not str(k).startswith("_")},
                    depth=depth + 1,
                    max_depth=max_depth,
                ),
            }
        except Exception:
            pass
    return {"type": type(value).__name__, "repr": str(value)[:500]}


def _dedup_dicts(items: Iterable[Dict[str, Any]], keys: Tuple[str, ...]) -> List[Dict[str, Any]]:
    seen: set[Tuple[str, ...]] = set()
    out: List[Dict[str, Any]] = []
    for item in items:
        sig = tuple(str(item.get(k, "")) for k in keys)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(item)
    return out


def _status_from_presence(value: Any, *, unknowns: Optional[List[Any]] = None, explicit: Any = None) -> str:
    if explicit:
        return str(explicit)
    if unknowns:
        return "partiel"
    if _is_present(value, accept_empty_string=True):
        return "ok"
    return "indisponible"


# =============================================================================
# Métriques
# =============================================================================

def _read_detail_value(raw: Any) -> Tuple[Any, Optional[str], Optional[str], Optional[str]]:
    """Lit les formats backend de type {'valeur': ..., 'unite': ..., 'statut': ...}."""
    if not isinstance(raw, Mapping):
        return raw, None, None, None

    value_key = None
    for key in ("valeur", "value", "resultat", "result", "data"):
        if key in raw:
            value_key = key
            break

    if value_key is None:
        return raw, None, None, None

    value = raw.get(value_key)
    unit = raw.get("unite", raw.get("unit"))
    status = raw.get("statut", raw.get("status"))
    source = raw.get("source", raw.get("origine"))
    return value, str(unit) if unit is not None else None, str(status) if status is not None else None, str(source) if source is not None else None


def resolve_metric(report: Mapping[str, Any], candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Résout une métrique depuis plusieurs chemins candidats.

    Règles :
    - première valeur présente ;
    - 0 et False sont acceptés ;
    - None reste absent ;
    - aucune unité n'est convertie ;
    - le chemin brut et les candidats sont conservés.
    """
    first_candidate = candidates[0] if candidates else {}
    label = str(first_candidate.get("label", "Inconnu"))
    default_unit = str(first_candidate.get("unit", ""))

    tried: List[str] = []
    for candidate in candidates:
        raw_path = candidate.get("raw_path")
        if not raw_path:
            continue

        path = str(raw_path)
        tried.append(path)
        raw = get_nested(report, path, _MISSING)
        if raw is _MISSING:
            continue

        value, unit_from_detail, status_from_detail, source_from_detail = _read_detail_value(raw)
        if not _is_present(value, accept_empty_string=False):
            continue

        unit = str(candidate.get("unit", unit_from_detail or default_unit or ""))
        status = str(candidate.get("status", status_from_detail or "ok"))
        source = str(candidate.get("source_type", source_from_detail or "backend"))

        return {
            "label": label,
            "value": _to_jsonable(value),
            "unit": unit,
            "status": status,
            "source": source,
            "raw_path": path,
            "resolved": True,
            "candidates": tried,
        }

    return {
        "label": label,
        "value": None,
        "unit": default_unit,
        "status": "missing",
        "source": None,
        "raw_path": tried[0] if tried else None,
        "resolved": False,
        "missing_reason": "Donnée non trouvée dans les chemins backend testés",
        "candidates": tried,
    }


def metric_from_paths(
    report: Mapping[str, Any],
    label: str,
    paths: Iterable[str],
    unit: str = "",
    *,
    include_missing: bool = True,
) -> Dict[str, Any]:
    metric = resolve_metric(
        report,
        [{"raw_path": p, "label": label, "unit": unit} for p in paths],
    )
    if include_missing:
        return metric
    return metric if metric["resolved"] else {}


def _metric_specs() -> Dict[str, List[Tuple[str, Tuple[str, ...], str]]]:
    return {
        "kpis": [
            (
                "Puissance demandée",
                (
                    "derivees_chaine_energie.details.sortie_utilisateur_w.valeur",
                    "derivees_chaine_energie.sortie_utilisateur_w",
                    "entrees.puissance.valeur_entree",
                    "entrees.puissance_traction_kw",
                ),
                "W",
            ),
            (
                "Architecture",
                (
                    "resume_gui.Architecture",
                    "resume_gui.architecture",
                    "systeme_complet.synthese.architecture.nom",
                    "systeme_complet.synthese.moteur_thermique.architecture",
                    "stho_me_secondaire.synthese.moteur_thermique.architecture",
                ),
                "",
            ),
            (
                "Efficacité globale",
                (
                    "strategie_energie.bilan_bus_dc.rendement_global_calcule",
                    "systeme_complet.synthese.rendement_global",
                    "resume_gui.rendement_global",
                ),
                "",
            ),
            (
                "Score technique",
                (
                    "resume_gui.score_global_100",
                    "optimisation.synthese_optimisation.score_global_100",
                    "strategie_energie.score_global_100",
                ),
                "/100",
            ),
        ],
        "energy_chain": [
            (
                "Cible traction",
                (
                    "entrees.puissance_traction_kw",
                    "entrees.puissance.kw",
                    "derivees_chaine_energie.details.p_traction_w.valeur",
                    "derivees_chaine_energie.details.p_traction_w",
                ),
                "kW/W",
            ),
            (
                "Mode énergétique",
                (
                    "strategie_energie.mode_energetique",
                    "strategie_energie.mode",
                    "systeme_complet.liaisons.bus_dc.scenario_bus_dc",
                ),
                "",
            ),
            (
                "Puissance traction",
                (
                    "derivees_chaine_energie.details.p_traction_w.valeur",
                    "derivees_chaine_energie.details.p_traction_w",
                    "derivees_chaine_energie.sortie_utilisateur_w",
                    "strategie_energie.bilan_bus_dc.puissance_electrique_usage_w",
                ),
                "W",
            ),
            (
                "Puissance bus DC",
                (
                    "derivees_chaine_energie.details.p_bus_total.valeur",
                    "derivees_chaine_energie.details.p_bus_total",
                    "derivees_chaine_energie.puissance_bus_dc_totale_w",
                    "strategie_energie.bilan_bus_dc.puissance_bus_dc_totale_w",
                    "systeme_complet.synthese.vehicule.puissance_bus_dc_design_w",
                ),
                "W",
            ),
            (
                "Recharge batterie",
                (
                    "strategie_energie.bilan_bus_dc.puissance_recharge_retenue_w",
                    "derivees_chaine_energie.puissance_recharge_batterie_w",
                    "systeme_complet.synthese.batterie.puissance_charge_w",
                ),
                "W",
            ),
            (
                "Limitation batterie",
                (
                    "strategie_energie.enveloppe_batterie.raison_limitante",
                    "systeme_complet.synthese.batterie.raison_limitante",
                ),
                "",
            ),
            (
                "Alternateur électrique requis",
                (
                    "strategie_energie.bilan_bus_dc.puissance_alternateur_electrique_requise_w",
                    "systeme_complet.synthese.alternateur.P_out_W",
                    "systeme_complet.synthese.alternateur.puissance_electrique_cible_w",
                ),
                "W",
            ),
            (
                "Alternateur mécanique requis",
                (
                    "derivees_chaine_energie.puissance_mecanique_alternateur_requise_w",
                    "strategie_energie.bilan_bus_dc.puissance_mecanique_alternateur_requise_w",
                    "systeme_complet.synthese.alternateur.P_mecanique_W",
                ),
                "W",
            ),
            (
                "Moteur thermique requis",
                (
                    "derivees_chaine_energie.puissance_moteur_thermique_requise_w",
                    "strategie_energie.bilan_bus_dc.puissance_moteur_thermique_requise_w",
                    "systeme_complet.synthese.moteur_thermique.puissance_requise_W",
                    "systeme_complet.synthese.moteur_thermique.puissance_nominale_visee_w",
                ),
                "W",
            ),
            (
                "Rendement global calculé",
                (
                    "strategie_energie.bilan_bus_dc.rendement_global_calcule",
                    "systeme_complet.synthese.rendement_global",
                ),
                "",
            ),
        ],
    }


def extract_energy_chain(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [
        metric_from_paths(report, label, paths, unit)
        for label, paths, unit in _metric_specs()["energy_chain"]
    ]


def _count_present_leaves(value: Any, *, depth: int = 0, max_depth: int = 8) -> int:
    if depth > max_depth:
        return 0
    if isinstance(value, Mapping):
        return sum(_count_present_leaves(v, depth=depth + 1, max_depth=max_depth) for k, v in value.items() if str(k) not in _HEAVY_KEYS)
    if isinstance(value, list):
        return sum(_count_present_leaves(v, depth=depth + 1, max_depth=max_depth) for v in value)
    return 1 if _is_present(value, accept_empty_string=False) else 0


def dashboard_specs_count(report: Mapping[str, Any]) -> List[str]:
    """Compatibilité ancienne API : renvoie une liste de marqueurs calculés."""
    count = 0
    for key in ("resume_gui", "derivees_chaine_energie", "entrees", "strategie_energie", "systeme_complet"):
        count += _count_present_leaves(get_nested(report, key, {}))
    return ["v"] * count


# =============================================================================
# Inconnues et alertes
# =============================================================================

def flatten_unknowns(report: Any, *, max_depth: int = 10) -> List[Dict[str, str]]:
    if not isinstance(report, Mapping):
        return []

    flat: List[Dict[str, str]] = []

    def visit(node: Any, prefix: str = "", depth: int = 0) -> None:
        if depth > max_depth or not isinstance(node, Mapping):
            return

        inc = node.get("inconnues")
        if isinstance(inc, Mapping):
            for category, items in inc.items():
                for item in _as_list(items):
                    if isinstance(item, Mapping):
                        flat.append(
                            {
                                "category": str(category),
                                "name": str(item.get("nom", item.get("champ", item.get("name", "?")))),
                                "reason": str(item.get("raison", item.get("detail", item.get("message", "")))),
                                "piece": str(item.get("piece", item.get("composant", ""))),
                                "severity": str(item.get("gravite", item.get("severity", "missing"))),
                                "path": prefix,
                            }
                        )
                    else:
                        flat.append(
                            {
                                "category": str(category),
                                "name": str(item),
                                "reason": "Donnée signalée comme inconnue par le backend",
                                "piece": "",
                                "severity": "missing",
                                "path": prefix,
                            }
                        )

        for key, value in node.items():
            key_s = str(key)
            if key_s in _HEAVY_KEYS:
                continue
            if isinstance(value, Mapping):
                visit(value, f"{prefix}.{key_s}" if prefix else key_s, depth + 1)
            elif isinstance(value, list):
                for i, child in enumerate(value):
                    if isinstance(child, Mapping):
                        visit(child, f"{prefix}.{key_s}.{i}" if prefix else f"{key_s}.{i}", depth + 1)

    visit(report)
    return _dedup_dicts(flat, keys=("category", "name", "reason", "path"))


def flatten_alerts(report: Any, *, max_depth: int = 10) -> List[Dict[str, str]]:
    if not isinstance(report, Mapping):
        return []

    flat: List[Dict[str, str]] = []

    def visit(node: Any, prefix: str = "", depth: int = 0) -> None:
        if depth > max_depth or not isinstance(node, Mapping):
            return

        alerts = node.get("alertes", node.get("alerts"))
        if isinstance(alerts, Mapping):
            for category, items in alerts.items():
                for item in _as_list(items):
                    if isinstance(item, Mapping):
                        flat.append(
                            {
                                "category": str(category),
                                "name": str(item.get("nom", item.get("name", "?"))),
                                "detail": str(item.get("detail", item.get("raison", item.get("message", "")))),
                                "severity": str(item.get("gravite", item.get("severity", "warning"))),
                                "path": prefix,
                            }
                        )
                    else:
                        flat.append(
                            {
                                "category": str(category),
                                "name": str(item),
                                "detail": "Alerte signalée par le backend",
                                "severity": "warning",
                                "path": prefix,
                            }
                        )

        for key, value in node.items():
            key_s = str(key)
            if key_s in _HEAVY_KEYS:
                continue
            if isinstance(value, Mapping):
                visit(value, f"{prefix}.{key_s}" if prefix else key_s, depth + 1)
            elif isinstance(value, list):
                for i, child in enumerate(value):
                    if isinstance(child, Mapping):
                        visit(child, f"{prefix}.{key_s}.{i}" if prefix else f"{key_s}.{i}", depth + 1)

    visit(report)
    return _dedup_dicts(flat, keys=("category", "name", "detail", "path"))


# =============================================================================
# Rapports composants / sous-systèmes
# =============================================================================

def _find_first_dict(report: Mapping[str, Any], paths: Iterable[str]) -> Tuple[Dict[str, Any], Optional[str]]:
    for path in paths:
        value = get_nested(report, path, _MISSING)
        if isinstance(value, Mapping) and value:
            return dict(value), path
    return {}, None


def _component_candidate_paths(component_key: str) -> List[str]:
    aliases = _COMPONENT_ALIASES.get(component_key, (component_key,))
    roots = (
        "analyses_composants",
        "sous_systemes",
        "systeme_complet.sous_systemes",
        "stho_me_secondaire.rapports.composants",
        "rapports.composants",
        "composants",
    )

    paths: List[str] = []
    for root in roots:
        for alias in aliases:
            paths.append(f"{root}.{alias}")

    # Chemins synthèse connus.
    if component_key == "batterie":
        paths.extend(("strategie_energie.enveloppe_batterie", "systeme_complet.synthese.batterie"))
    elif component_key == "moteur_thermique":
        paths.extend(("systeme_complet.synthese.moteur_thermique", "stho_me_secondaire.synthese.moteur_thermique"))
    elif component_key == "alternateur":
        paths.extend(("systeme_complet.synthese.alternateur", "stho_me_secondaire.synthese.alternateur"))
    elif component_key == "architecture":
        paths.extend(("systeme_complet.synthese.architecture", "stho_me_secondaire.synthese.architecture"))
    elif component_key == "strategie_energie":
        paths.extend(("strategie_energie", "stho_me_secondaire.rapports.strategie_energie"))

    return paths


def extract_subsystems(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    specs = [
        ("batterie", "Batterie", True),
        ("moteur_electrique", "Moteur électrique", False),
        ("alternateur", "Alternateur", False),
        ("boite_crabots", "Boîte / transmission", False),
        ("moteur_thermique", "Moteur thermique", False),
        ("architecture", "Architecture", True),
        ("strategie_energie", "Stratégie énergétique", True),
    ]

    out: List[Dict[str, Any]] = []
    for key, label, modifiable in specs:
        data, source = _find_first_dict(report, _component_candidate_paths(key))
        unknowns = flatten_unknowns(data)
        alerts = flatten_alerts(data)

        resolved_data = {
            str(k): _to_jsonable(v)
            for k, v in data.items()
            if str(k) not in {"inconnues", "alertes", "alerts", "notes", "notes_modele"}
            and _is_present(v, accept_empty_string=True)
        }

        out.append(
            {
                "key": key,
                "name": label,
                "status": _status_from_presence(data, unknowns=unknowns),
                "source": source,
                "data": _to_jsonable(data),
                "resolved_data": resolved_data,
                "resolved_count": _count_present_leaves(resolved_data),
                "missing_count": len(unknowns),
                "alert_count": len(alerts),
                "unknowns": unknowns,
                "alerts": alerts,
                "modifiable": modifiable,
                "candidate_paths": _component_candidate_paths(key),
            }
        )
    return out


def subsystem_metrics(subsystems: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "label": str(item.get("name", item.get("key", ""))),
            "value": str(item.get("status", "indisponible")).upper(),
            "unit": "",
            "status": str(item.get("status", "indisponible")),
            "source": item.get("source"),
            "raw_path": item.get("source"),
            "resolved": bool(item.get("source")),
        }
        for item in subsystems
    ]


# =============================================================================
# Architecture
# =============================================================================

def extract_architecture_candidates(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    paths = [
        "systeme_complet.synthese.architectures_candidates",
        "systeme_complet.synthese.architecture.candidats",
        "stho_me_secondaire.rapports.composants.architecture_orchestrateur.candidats",
        "stho_me_secondaire.rapports.composants.architecture_orchestrateur.synthese.candidats",
        "optimisation.architectures_candidates",
        "optimisation.synthese_optimisation.architectures_candidates",
        "analyses_composants.architecture.exploration.candidats",
        "sous_systemes.architecture.exploration.candidats",
        "architecture.candidats",
    ]
    for path in paths:
        candidates = get_nested(report, path, _MISSING)
        if isinstance(candidates, list) and candidates:
            out = []
            for i, candidate in enumerate(candidates):
                if isinstance(candidate, Mapping):
                    c = dict(candidate)
                    c.setdefault("source", path)
                    c.setdefault("index", i)
                    out.append(_to_jsonable(c))
            if out:
                return out

    solo, solo_path = first_present(
        report,
        "resume_gui.Architecture",
        "resume_gui.architecture",
        "systeme_complet.synthese.architecture.nom",
        "systeme_complet.synthese.moteur_thermique.architecture",
    )
    if solo is not None:
        return [
            {
                "nom": solo,
                "description": "Architecture retenue par le backend ; aucun classement complet fourni.",
                "score": None,
                "source": solo_path,
                "index": 0,
                "status": "retenue_sans_candidats",
            }
        ]

    return []


# =============================================================================
# Pièces
# =============================================================================

def _collect_piece_reports(report: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    buckets: Dict[str, Dict[str, Any]] = {}

    direct_paths = [
        "rapports_pieces",
        "construction_pieces.rapports_pieces",
        "systeme_complet.rapports_pieces",
        "stho_me_secondaire.rapports.pieces",
        "pieces",
    ]

    for path in direct_paths:
        block = get_nested(report, path, _MISSING)
        if isinstance(block, Mapping):
            for name, rep in block.items():
                if isinstance(rep, Mapping):
                    buckets[str(name)] = dict(rep)

    # Rapports pièces imbriqués dans les composants.
    comp_paths = [
        "analyses_composants",
        "sous_systemes",
        "systeme_complet.sous_systemes",
        "stho_me_secondaire.rapports.composants",
    ]
    for comp_path in comp_paths:
        components = get_nested(report, comp_path, _MISSING)
        if not isinstance(components, Mapping):
            continue
        for comp_name, comp_report in components.items():
            if not isinstance(comp_report, Mapping):
                continue
            pieces = comp_report.get("pieces")
            if not isinstance(pieces, Mapping):
                continue
            for piece_name, piece_report in pieces.items():
                if isinstance(piece_report, Mapping):
                    buckets.setdefault(f"{comp_name}.{piece_name}", dict(piece_report))

    return buckets


def _collect_piece_inventory(report: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    inventory = get_nested(report, "inventaire.pieces", {})
    if isinstance(inventory, Mapping):
        return {str(k): dict(v) if isinstance(v, Mapping) else {"value": v} for k, v in inventory.items()}
    return {}


def extract_piece_list(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    reports_pieces = _collect_piece_reports(report)
    inventory = _collect_piece_inventory(report)

    names = sorted(set(reports_pieces.keys()) | set(inventory.keys()))
    out: List[Dict[str, Any]] = []

    for name in names:
        rep = reports_pieces.get(name, {})
        inv = inventory.get(name, {})
        unknowns = flatten_unknowns(rep)
        alerts = flatten_alerts(rep)

        out.append(
            {
                "name": name,
                "short_name": str(name).split(".")[-1],
                "type": rep.get("piece") or rep.get("type") or inv.get("type") or str(name).split(".")[-1],
                "status": _status_from_presence(rep, unknowns=unknowns),
                "dimensions": extract_dimensions(rep),
                "material": first_material(rep),
                "constraints": extract_constraints(rep),
                "unknowns": unknowns,
                "alerts": alerts,
                "data": _to_jsonable(rep),
                "inventory": _to_jsonable(inv),
                "backend_report_available": bool(rep),
                "pdf_available": bool(rep),
            }
        )

    return out


def extract_dimensions(piece_report: Mapping[str, Any]) -> Dict[str, Any]:
    dims: Dict[str, Any] = {}

    tokens = (
        "diametre",
        "diameter",
        "longueur",
        "length",
        "largeur",
        "width",
        "hauteur",
        "height",
        "epaisseur",
        "thickness",
        "rayon",
        "radius",
        "course",
        "stroke",
        "alesage",
        "bore",
        "_m",
        "_mm",
    )

    for section in ("dimensions", "geometrie", "géométrie", "cao", "resultats", "dimensionnement", "assemblage"):
        block = piece_report.get(section) if isinstance(piece_report, Mapping) else None
        if not isinstance(block, Mapping):
            continue

        for key, value in block.items():
            key_s = str(key)
            if any(token in key_s.lower() for token in tokens) and _is_present(value, accept_empty_string=True):
                dims[key_s] = _to_jsonable(value)

    return dims


def first_material(piece_report: Mapping[str, Any]) -> Any:
    for path in (
        "materiau",
        "matériau",
        "materiau_cle",
        "construction.materiau",
        "construction.materiau_cle",
        "entrees.materiau",
        "entrees.materiau_cle",
        "donnees.materiau",
        "données.materiau",
    ):
        value = get_nested(piece_report, path, _MISSING)
        if _is_present(value, accept_empty_string=False):
            return _to_jsonable(value)
    return None


def extract_constraints(piece_report: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for section in ("contraintes", "resistance", "résistance", "efforts", "charges", "securite", "sécurité", "coherences", "cohérences"):
        block = piece_report.get(section) if isinstance(piece_report, Mapping) else None
        if isinstance(block, Mapping):
            for key, value in block.items():
                if _is_present(value, accept_empty_string=True):
                    out[str(key)] = _to_jsonable(value)
    return out


# =============================================================================
# Exports et ressources visuelles
# =============================================================================

def _path_exists(path: Any) -> bool:
    if not isinstance(path, (str, os.PathLike)):
        return False
    try:
        return Path(path).expanduser().exists()
    except Exception:
        return False


def _normalise_artifact(item: Any, *, key: str, label: str, source: str) -> Optional[Dict[str, Any]]:
    if item is None:
        return None

    if isinstance(item, Mapping):
        value = item.get("path", item.get("filepath", item.get("file", item.get("url", item.get("value")))))
        available = bool(item.get("available", item.get("disponible", _is_present(value, accept_empty_string=False))))
        return {
            "key": key,
            "label": str(item.get("label", label)),
            "available": available,
            "status": str(item.get("status", "disponible" if available else "indisponible")),
            "path": str(value) if value is not None else None,
            "reason": str(item.get("reason", item.get("raison", "" if available else "Artefact référencé sans chemin exploitable."))),
            "source": source,
            "data": _to_jsonable(item),
        }

    if isinstance(item, (str, os.PathLike)):
        item_s = str(item)
        return {
            "key": key,
            "label": label,
            "available": bool(item_s),
            "status": "disponible" if item_s else "indisponible",
            "path": item_s or None,
            "reason": "" if item_s else "Chemin vide.",
            "source": source,
            "data": item_s,
        }

    return None


def _extract_declared_exports(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    declared: List[Dict[str, Any]] = []

    for root in _EXPORT_KEYS:
        block = get_nested(report, root, _MISSING)
        if isinstance(block, Mapping):
            for key, value in block.items():
                artifact = _normalise_artifact(value, key=str(key), label=str(key), source=root)
                if artifact:
                    declared.append(artifact)
        elif isinstance(block, list):
            for i, value in enumerate(block):
                artifact = _normalise_artifact(value, key=f"{root}_{i}", label=f"{root} {i}", source=root)
                if artifact:
                    declared.append(artifact)

    return declared


def extract_exports(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    declared = _extract_declared_exports(report)
    declared_keys = {str(item.get("key")) for item in declared}

    pieces_ready = bool(_collect_piece_reports(report))
    pdf_ready = bool(get_nested(report, "resume_gui", None) or pieces_ready)
    json_ready = bool(report)

    cao_detail = get_nested(report, "cao.solidworks_ready_detaille", _MISSING)
    cao_ready = bool(cao_detail) if cao_detail is not _MISSING else bool(get_nested(report, "cao.solidworks_ready", False))

    defaults = [
        {
            "key": "pdf",
            "label": "PDF global",
            "available": pdf_ready,
            "status": "disponible" if pdf_ready else "indisponible",
            "path": None,
            "reason": "" if pdf_ready else "Résumé ou rapports pièces indisponibles.",
            "source": "adapter",
        },
        {
            "key": "pieces_pdf",
            "label": "PDF pièces",
            "available": pieces_ready,
            "status": "disponible" if pieces_ready else "indisponible",
            "path": None,
            "reason": "" if pieces_ready else "Aucun rapport de pièce fourni.",
            "source": "adapter",
        },
        {
            "key": "json",
            "label": "JSON brut",
            "available": json_ready,
            "status": "disponible" if json_ready else "indisponible",
            "path": None,
            "reason": "" if json_ready else "Rapport vide.",
            "source": "adapter",
        },
        {
            "key": "cao",
            "label": "CAO / 3D",
            "available": cao_ready,
            "status": "disponible" if cao_ready else "indisponible",
            "path": None,
            "reason": "" if cao_ready else str(get_nested(report, "cao.raison_detaille", "CAO détaillée non fournie.")),
            "source": "rapport.cao",
        },
        {
            "key": "charts",
            "label": "Graphiques",
            "available": bool(extract_visual_resources(report, "charts")),
            "status": "partiel",
            "path": None,
            "reason": "Selon modules frontend/backend et données disponibles.",
            "source": "adapter.visual_resources",
        },
    ]

    merged = [item for item in defaults if item["key"] not in declared_keys] + declared
    return _dedup_dicts(merged, keys=("key", "label", "path"))


def extract_export_availability(report: Mapping[str, Any]) -> Dict[str, Any]:
    exports = extract_exports(report)
    out: Dict[str, Any] = {}
    for item in exports:
        key = str(item.get("key"))
        out[key] = bool(item.get("available"))
        out[f"{key}_reason"] = str(item.get("reason", ""))
        out[f"{key}_source"] = item.get("source")
    return out


def _frontend_component_dirs(piece_short_name: str) -> List[Path]:
    return [
        PROJECT_ROOT / "frontend" / "components" / "moteur_thermique" / "pieces" / piece_short_name,
        PROJECT_ROOT / "frontend" / "gui" / "components" / "moteur_thermique" / "pieces" / piece_short_name,
        PROJECT_ROOT / "frontend" / "components" / "pieces" / piece_short_name,
    ]


def _backend_component_dirs(piece_short_name: str) -> List[Path]:
    return [
        PROJECT_ROOT / "backend" / "components" / "moteur_thermique" / "pieces" / piece_short_name,
        PROJECT_ROOT / "backend" / "components" / "pieces" / piece_short_name,
        PROJECT_ROOT / "backend" / "components" / "moteur_thermique" / "modules",
    ]


def _find_module_file(piece_short_name: str, kind: str) -> Tuple[Optional[Path], List[str]]:
    candidates: List[Path] = []
    for base in _frontend_component_dirs(piece_short_name):
        for filename in _PIECE_VISUAL_MODULES.get(kind, (f"{kind}.py",)):
            candidates.append(base / filename)
    for base in _backend_component_dirs(piece_short_name):
        for filename in _PIECE_VISUAL_MODULES.get(kind, (f"{kind}.py",)):
            candidates.append(base / filename)

    for path in candidates:
        if path.exists():
            return path, [str(p) for p in candidates]
    return None, [str(p) for p in candidates]


def _extract_visual_declarations(piece_report: Mapping[str, Any], kind: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for key in _VISUAL_REPORT_KEYS.get(kind, (kind,)):
        value = get_nested(piece_report, key, _MISSING)
        if value is _MISSING:
            continue

        for i, item in enumerate(_as_list(value)):
            artifact = _normalise_artifact(item, key=f"{kind}_{i}", label=kind, source=key)
            if artifact:
                out.append(artifact)
    return out


def extract_visual_resources(report: Mapping[str, Any], kind: str) -> List[Dict[str, Any]]:
    """Expose les ressources nécessaires au frontend pour croquis, graphiques et 3D.

    Ce module ne rend rien lui-même : il indique au frontend quelle donnée backend
    et quel module éventuel peuvent être utilisés.
    """
    resources: List[Dict[str, Any]] = []
    pieces = extract_piece_list(report)

    for piece in pieces:
        short_name = str(piece.get("short_name") or piece.get("name", "")).split(".")[-1]
        piece_data = _as_dict(piece.get("data"))
        module_path, module_candidates = _find_module_file(short_name, kind)
        declarations = _extract_visual_declarations(piece_data, kind)
        has_backend_data = bool(piece_data)
        has_declared_artifact = any(bool(item.get("available")) for item in declarations)

        available = bool((module_path and has_backend_data) or has_declared_artifact)

        reason = ""
        if not available:
            missing = []
            if not module_path and not has_declared_artifact:
                missing.append("module frontend/backend ou artefact déclaré")
            if not has_backend_data:
                missing.append("rapport backend de pièce")
            reason = "Manquant : " + ", ".join(missing) + "."

        resources.append(
            {
                "name": piece.get("name"),
                "piece_type": piece.get("type"),
                "type": kind,
                "status": "disponible" if available else "indisponible",
                "available": available,
                "can_render": available,
                "module_path": str(module_path) if module_path else None,
                "module_candidates": module_candidates,
                "declared_artifacts": declarations,
                "backend_data_available": has_backend_data,
                "backend_piece_data_path": f"pieces.{piece.get('name')}",
                "reason": reason,
            }
        )

    return resources


# =============================================================================
# Paramètres éditables
# =============================================================================

def _editable_param(
    report: Mapping[str, Any],
    *,
    key: str,
    label: str,
    paths: Tuple[str, ...],
    unit: str = "",
    editable: bool = True,
    kind: str = "number",
    choices: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    value, source = first_present(report, *paths)
    return {
        "key": key,
        "label": label,
        "value": _to_jsonable(value),
        "unit": unit,
        "source": source,
        "candidate_paths": list(paths),
        "editable": bool(editable),
        "kind": kind,
        "choices": choices or [],
        "status": "ok" if source else "missing",
    }


def extract_editable_parameters(
    report: Mapping[str, Any],
    arch_candidates: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    arch_candidates = arch_candidates or []
    arch_choices = [
        c.get("nom", c.get("architecture"))
        for c in arch_candidates
        if isinstance(c, Mapping) and (c.get("nom") is not None or c.get("architecture") is not None)
    ]

    return [
        _editable_param(
            report,
            key="puissance_entree",
            label="Puissance demandée",
            paths=("entrees.puissance_traction_kw", "entrees.puissance.kw", "entrees.puissance.valeur_entree"),
            unit="kW/W",
            kind="number",
        ),
        _editable_param(
            report,
            key="unite_entree",
            label="Unité",
            paths=("entrees.unite_entree", "entrees.puissance.unite_entree", "meta.unite_entree"),
            kind="text",
        ),
        _editable_param(
            report,
            key="architecture",
            label="Architecture choisie",
            paths=("resume_gui.Architecture", "systeme_complet.synthese.architecture.nom", "systeme_complet.synthese.moteur_thermique.architecture"),
            editable=bool(arch_choices),
            kind="choice" if arch_choices else "text",
            choices=arch_choices,
        ),
        _editable_param(
            report,
            key="nombre_cylindres",
            label="Nombre de cylindres",
            paths=("resume_gui.N_cyl", "resume_gui.nombre_cylindres", "systeme_complet.synthese.moteur_thermique.nombre_cylindres"),
            kind="integer",
        ),
        _editable_param(
            report,
            key="alesage_mm",
            label="Alésage",
            paths=("resume_gui.Bore_mm", "resume_gui.alesage_mm", "systeme_complet.cao.moteur_thermique.alesage_mm"),
            unit="mm",
            kind="number",
        ),
        _editable_param(
            report,
            key="course_mm",
            label="Course",
            paths=("resume_gui.Stroke_mm", "resume_gui.course_mm", "systeme_complet.cao.moteur_thermique.course_mm"),
            unit="mm",
            kind="number",
        ),
        _editable_param(
            report,
            key="rpm_nominal",
            label="Régime nominal",
            paths=("resume_gui.RPM", "systeme_complet.synthese.moteur_thermique.rpm_nominal", "donnees_connues.rpm_moteur"),
            unit="tr/min",
            kind="number",
        ),
        _editable_param(
            report,
            key="pme_pa",
            label="PME",
            paths=("resume_gui.PME_Pa", "systeme_complet.synthese.moteur_thermique.pme_pa", "systeme_complet.liaisons.pme.pme_pa_utilisee_ou_requise"),
            unit="Pa",
            kind="number",
        ),
    ]


# =============================================================================
# Arbre de données frontend
# =============================================================================

def _section_summary(value: Any) -> Dict[str, Any]:
    if value is None:
        return {"status": "inconnu", "present_leaves": 0, "mapping_keys": 0, "list_items": 0}
    if isinstance(value, Mapping):
        return {
            "status": "ok",
            "present_leaves": _count_present_leaves(value),
            "mapping_keys": len(value),
            "list_items": 0,
        }
    if isinstance(value, list):
        return {
            "status": "ok",
            "present_leaves": _count_present_leaves(value),
            "mapping_keys": 0,
            "list_items": len(value),
        }
    return {
        "status": "ok" if _is_present(value, accept_empty_string=True) else "inconnu",
        "present_leaves": 1 if _is_present(value, accept_empty_string=True) else 0,
        "mapping_keys": 0,
        "list_items": 0,
    }


def build_data_tree(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    sections = []
    for key in (
        "meta",
        "entrees",
        "resume_gui",
        "derivees_chaine_energie",
        "strategie_energie",
        "systeme_complet",
        "analyses_composants",
        "construction_pieces",
        "rapports_pieces",
        "inventaire",
        "cao",
        "optimisation",
        "stho_me_secondaire",
        "inconnues",
        "alertes",
        "notes_modele",
    ):
        value = get_nested(report, key, _MISSING)
        if value is _MISSING:
            value = None
        summary = _section_summary(value)
        sections.append(
            {
                "name": key,
                "status": summary["status"],
                "summary": summary,
                "value": _to_jsonable(value, max_depth=6),
                "source": f"rapport.{key}",
            }
        )
    return sections


# =============================================================================
# Adaptation principale
# =============================================================================

def _empty_ui(error: str = "Rapport vide ou inexistant") -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "error": error,
        "is_empty": True,
        "meta": {},
        "dashboard": {
            "title": "STHOME COCKPIT - RAPPORT VIDE",
            "kpis": [],
            "energy_chain": [],
            "subsystems": [],
            "actions": [],
            "summary": {
                "values_calculated": 0,
                "missing_count": 0,
                "alert_count": 0,
                "piece_count": 0,
                "visual_resource_count": 0,
            },
        },
        "missing_requirements": [],
        "alerts": [],
        "raw_sections": [],
        "architecture_candidates": [],
        "pieces": [],
        "charts": [],
        "sketches": [],
        "three_d": [],
        "exports": [],
        "editable_parameters": [],
        "notes": [],
    }


def _dashboard_actions() -> List[Dict[str, Any]]:
    return [
        {"label": "Données techniques", "target": "energy_audit", "requires": "rapport"},
        {"label": "Pièces", "target": "piece_library", "requires": "pieces"},
        {"label": "Architecture", "target": "architecture_choice", "requires": "architecture_candidates"},
        {"label": "Croquis", "target": "sketches", "requires": "visual_resources"},
        {"label": "Graphiques", "target": "charts", "requires": "visual_resources"},
        {"label": "3D", "target": "three_d", "requires": "visual_resources"},
        {"label": "Exports", "target": "exports", "requires": "exports"},
        {"label": "JSON brut", "target": "raw_json", "requires": "rapport"},
        {"label": "Données à compléter", "target": "missing_requirements", "requires": "unknowns"},
        {"label": "Édition", "target": "edit_parameters", "requires": "editable_parameters"},
    ]


def adapt_backend_report(report: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(report, Mapping) or not report:
        return _empty_ui()

    unknowns = flatten_unknowns(report)
    alerts = flatten_alerts(report)
    pieces = extract_piece_list(report)
    arch_candidates = extract_architecture_candidates(report)
    subsystems = extract_subsystems(report)
    exports = extract_exports(report)

    sketches = extract_visual_resources(report, "sketches")
    charts = extract_visual_resources(report, "charts")
    three_d = extract_visual_resources(report, "three_d")
    editable = extract_editable_parameters(report, arch_candidates)

    kpis = [
        metric_from_paths(report, label, paths, unit, include_missing=False)
        for label, paths, unit in _metric_specs()["kpis"]
    ]
    kpis = [m for m in kpis if m]

    energy_chain = extract_energy_chain(report)
    visual_resource_count = sum(1 for group in (sketches, charts, three_d) for item in group if item.get("available"))

    project_name = get_nested(report, "meta.nom_projet", None) or get_nested(report, "meta.project_name", None) or "PROJET SANS NOM"

    ui = {
        "schema_version": SCHEMA_VERSION,
        "is_empty": False,
        "meta": _to_jsonable(report.get("meta", {})),
        "dashboard": {
            "title": f"STHOME COCKPIT - {project_name}",
            "kpis": kpis,
            "energy_chain": [m for m in energy_chain if m.get("resolved")],
            "energy_chain_all": energy_chain,
            "subsystems": subsystems,
            "subsystem_metrics": subsystem_metrics(subsystems),
            "actions": _dashboard_actions(),
            "summary": {
                "values_calculated": len(dashboard_specs_count(report)),
                "missing_count": len(unknowns),
                "alert_count": len(alerts),
                "piece_count": len(pieces),
                "subsystem_count": len(subsystems),
                "architecture_candidate_count": len(arch_candidates),
                "visual_resource_count": visual_resource_count,
                "export_count": len(exports),
            },
        },
        "missing_requirements": unknowns,
        "alerts": alerts,
        "raw_sections": build_data_tree(report),
        "architecture_candidates": arch_candidates,
        "pieces": pieces,
        "charts": charts,
        "sketches": sketches,
        "three_d": three_d,
        "exports": exports,
        "export_availability": extract_export_availability(report),
        "editable_parameters": editable,
        "notes": _as_list(report.get("notes_modele")) if isinstance(report.get("notes_modele"), list) else [],
        "audit": {
            "strict_no_physics_calculation": True,
            "none_preserved": True,
            "zero_preserved": True,
            "source_paths_preserved": True,
            "adapter": SCHEMA_VERSION,
        },
    }

    return _to_jsonable(ui, max_depth=12)


# =============================================================================
# Validation / sauvegarde
# =============================================================================

def validate_ui_report(ui_report: Mapping[str, Any]) -> Dict[str, Any]:
    """Contrôle léger pour détecter les erreurs d'adaptation avant affichage UI."""
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(ui_report, Mapping):
        return {"ok": False, "errors": ["ui_report n'est pas un dictionnaire"], "warnings": []}

    for key in ("dashboard", "missing_requirements", "alerts", "pieces", "exports"):
        if key not in ui_report:
            errors.append(f"Clé UI manquante: {key}")

    dashboard = ui_report.get("dashboard")
    if isinstance(dashboard, Mapping):
        for key in ("kpis", "energy_chain", "subsystems", "actions", "summary"):
            if key not in dashboard:
                errors.append(f"dashboard.{key} manquant")
    else:
        errors.append("dashboard n'est pas un dictionnaire")

    if ui_report.get("schema_version") != SCHEMA_VERSION:
        warnings.append("schema_version différente de l'adaptateur courant")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def save_json_report(report: Mapping[str, Any], path: str | os.PathLike[str]) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_to_jsonable(report, max_depth=20), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out)


# Alias explicite pour le frontend.
adapter_rapport_backend = adapt_backend_report
