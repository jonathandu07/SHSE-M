# backend\components\moteur_electrique\moteur_electrique.py
from __future__ import annotations

"""
systeme_hybride_final.py — orchestrateur système SHSE-M / STHO-ME
===============================================================================

Rôle
----
Ce module ferme la logique système :

    sortie utile demandée
    -> un ou plusieurs moteurs de sortie
    -> bus DC + auxiliaires
    -> batterie tampon
    -> alternateur
    -> boîte à crabots
    -> moteur(s) thermique(s) au cycle optimal

Principes de conception
-----------------------
1. La puissance demandée par l'utilisateur, par exemple 100 kW, est interprétée
   comme une puissance utile de sortie, pas comme une simple puissance alternateur.
2. Les auxiliaires consomment en plus : pompes, calculateurs, refroidissement,
   capteurs, servitudes, avionique, électronique, etc.
3. La batterie est un tampon système : elle absorbe les pics, stabilise le bus DC,
   évite de faire tourner le thermique hors cycle optimal, mais ne doit pas
   masquer un alternateur ou un moteur thermique sous-dimensionné.
4. Le thermique doit pouvoir soutenir le meilleur cycle de croisière possible :
   le plus puissant possible sous contraintes de rendement, consommation,
   température, durée de vie et duty-cycle.
5. Aucune donnée de matériau, rendement, densité, BSFC ou coefficient véhicule
   n'est inventée. Quand une donnée manque, elle remonte dans `inconnues`.

Unités
------
SI strict : W, kW, Wh, kWh, V, A, N, N.m, rpm, rad/s, kg, h, s.
"""

import importlib
import inspect
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Sequence, Tuple


# =============================================================================
# Chemins / imports robustes
# =============================================================================

_THIS_FILE = Path(__file__).resolve() if "__file__" in globals() else Path.cwd() / "systeme_hybride_final.py"
_THIS_DIR = _THIS_FILE.parent
for _p in (
    _THIS_DIR,
    _THIS_DIR / "modules",
    _THIS_DIR / "components",
    _THIS_DIR.parent,
    Path.cwd(),
):
    try:
        if _p.exists() and str(_p) not in sys.path:
            sys.path.insert(0, str(_p))
    except Exception:
        pass

_IMPORT_ERRORS: Dict[str, str] = {}
_MISSING = object()


def _import_attr(module_names: Sequence[str], attr: str, default: Any = _MISSING) -> Any:
    last_exc: Optional[BaseException] = None
    for module_name in module_names:
        try:
            mod = importlib.import_module(module_name)
            return getattr(mod, attr)
        except BaseException as exc:
            last_exc = exc
    _IMPORT_ERRORS[f"{attr}@{module_names[0] if module_names else '?'}"] = f"{type(last_exc).__name__}: {last_exc}"
    if default is not _MISSING:
        return default
    raise ImportError(f"Impossible d'importer {attr} depuis {module_names}: {last_exc}")


def _alts(local_name: str, *project_paths: str) -> Tuple[str, ...]:
    return tuple(project_paths) + (local_name,)


# Modules moteur électrique / mobilité fournis
calcul_force_resistance_totale = _import_attr(
    _alts(
        "calcul_force_resistance_vitesse",
        "backend.components.moteur_electrique.modules.calcul_force_resistance_vitesse",
        "backend.modules.moteur_electrique.calcul_force_resistance_vitesse",
        "components.moteur_electrique.modules.calcul_force_resistance_vitesse",
        "modules.calcul_force_resistance_vitesse",
    ),
    "calcul_force_resistance_totale",
    default=None,
)
calcul_charges_essieux = _import_attr(
    _alts(
        "calcul_charge_essieu",
        "backend.components.moteur_electrique.modules.calcul_charge_essieu",
        "backend.modules.moteur_electrique.calcul_charge_essieu",
        "components.moteur_electrique.modules.calcul_charge_essieu",
        "modules.calcul_charge_essieu",
    ),
    "calcul_charges_essieux",
    default=None,
)
calcul_acceleration_max = _import_attr(
    _alts(
        "calcul_acceleration_max",
        "backend.components.moteur_electrique.modules.calcul_acceleration_max",
        "backend.modules.moteur_electrique.calcul_acceleration_max",
        "components.moteur_electrique.modules.calcul_acceleration_max",
        "modules.calcul_acceleration_max",
    ),
    "calcul_acceleration_max",
    default=None,
)
calcul_puissance_roue = _import_attr(
    _alts(
        "calcul_puissance_roue",
        "backend.components.moteur_electrique.modules.calcul_puissance_roue",
        "backend.modules.moteur_electrique.calcul_puissance_roue",
        "components.moteur_electrique.modules.calcul_puissance_roue",
        "modules.calcul_puissance_roue",
    ),
    "calcul_puissance_roue",
    default=None,
)
calcul_couple_roue_total = _import_attr(
    _alts(
        "calcul_puissance_roue",
        "backend.components.moteur_electrique.modules.calcul_puissance_roue",
        "backend.modules.moteur_electrique.calcul_puissance_roue",
        "components.moteur_electrique.modules.calcul_puissance_roue",
        "modules.calcul_puissance_roue",
    ),
    "calcul_couple_roue_total",
    default=None,
)
calcul_couple_par_roue = _import_attr(
    _alts(
        "calcul_puissance_roue",
        "backend.components.moteur_electrique.modules.calcul_puissance_roue",
        "backend.modules.moteur_electrique.calcul_puissance_roue",
        "components.moteur_electrique.modules.calcul_puissance_roue",
        "modules.calcul_puissance_roue",
    ),
    "calcul_couple_par_roue",
    default=None,
)
calcul_puissance_moteur_electrique = _import_attr(
    _alts(
        "calcul_puissance_moteur",
        "backend.components.moteur_electrique.modules.calcul_puissance_moteur",
        "backend.modules.moteur_electrique.calcul_puissance_moteur",
        "components.moteur_electrique.modules.calcul_puissance_moteur",
        "modules.calcul_puissance_moteur",
    ),
    "calcul_puissance_moteur_electrique",
    default=None,
)
calcul_couple_moteur = _import_attr(
    _alts(
        "calcul_puissance_moteur",
        "backend.components.moteur_electrique.modules.calcul_puissance_moteur",
        "backend.modules.moteur_electrique.calcul_puissance_moteur",
        "components.moteur_electrique.modules.calcul_puissance_moteur",
        "modules.calcul_puissance_moteur",
    ),
    "calcul_couple_moteur",
    default=None,
)
calcul_demande_nautique = _import_attr(
    _alts(
        "calcul_multi_domaine",
        "backend.components.moteur_electrique.modules.calcul_multi_domaine",
        "backend.modules.moteur_electrique.calcul_multi_domaine",
        "components.moteur_electrique.modules.calcul_multi_domaine",
        "modules.calcul_multi_domaine",
    ),
    "calcul_demande_nautique",
    default=None,
)
calcul_demande_aerien_rho = _import_attr(
    _alts(
        "calcul_multi_domaine",
        "backend.components.moteur_electrique.modules.calcul_multi_domaine",
        "backend.modules.moteur_electrique.calcul_multi_domaine",
        "components.moteur_electrique.modules.calcul_multi_domaine",
        "modules.calcul_multi_domaine",
    ),
    "calcul_demande_aerien_rho",
    default=None,
)
calcul_demande_ferroviaire_davis = _import_attr(
    _alts(
        "calcul_multi_domaine",
        "backend.components.moteur_electrique.modules.calcul_multi_domaine",
        "backend.modules.moteur_electrique.calcul_multi_domaine",
        "components.moteur_electrique.modules.calcul_multi_domaine",
        "modules.calcul_multi_domaine",
    ),
    "calcul_demande_ferroviaire_davis",
    default=None,
)
calcul_densite_air_sec = _import_attr(
    _alts(
        "calcul_multi_domaine",
        "backend.components.moteur_electrique.modules.calcul_multi_domaine",
        "backend.modules.moteur_electrique.calcul_multi_domaine",
        "components.moteur_electrique.modules.calcul_multi_domaine",
        "modules.calcul_multi_domaine",
    ),
    "calcul_densite_air_sec",
    default=None,
)

# Sous-systèmes renforcés déjà produits dans cette itération.
Batterie = _import_attr(
    _alts("batterie_robuste", "backend.components.batterie.batterie", "components.batterie.batterie"),
    "Batterie",
    default=None,
)
ContraintesEquilibreBatterie = _import_attr(
    _alts("batterie_robuste", "backend.components.batterie.batterie", "components.batterie.batterie"),
    "ContraintesEquilibreBatterie",
    default=None,
)
Alternateur = _import_attr(
    _alts("alternateur_systeme_integre", "backend.components.alternateur.alternateur", "components.alternateur.alternateur"),
    "Alternateur",
    default=None,
)
construire_alternateur = _import_attr(
    _alts("alternateur_systeme_integre", "backend.components.alternateur.alternateur", "components.alternateur.alternateur"),
    "construire_alternateur",
    default=None,
)
BoiteCrabots = _import_attr(
    _alts("boite_crabots_cycle_optimal", "backend.components.boite_crabots.boite_crabots", "components.boite_crabots.boite_crabots"),
    "BoiteCrabots",
    default=None,
)
construire_boite_crabots = _import_attr(
    _alts("boite_crabots_cycle_optimal", "backend.components.boite_crabots.boite_crabots", "components.boite_crabots.boite_crabots"),
    "construire_boite_crabots",
    default=None,
)
MoteurThermique = _import_attr(
    _alts(
        "orchestrateur_moteur_thermique_corrige",
        "backend.components.moteur_thermique.moteur_thermique",
        "components.moteur_thermique.moteur_thermique",
    ),
    "MoteurThermique",
    default=None,
)

# Architecture moteur thermique STHO-ME : registre central L/V/W/Etoile/Boxer
# + extensions MultiModulesDC / PistonLibre.
# Ce module est optionnel : si absent, le rapport remonte une inconnue et
# le reste du système continue sans inventer d'architecture.
Architecture = _import_attr(
    _alts(
        "architecture",
        "backend.components.architecture",
        "backend.components.architecture.architecture",
        "backend.components.architechture",
        "backend.components.architechture.architecture",
        "components.architecture",
    ),
    "Architecture",
    default=None,
)
concevoir_architecture = _import_attr(
    _alts(
        "architecture",
        "backend.components.architecture",
        "backend.components.architecture.architecture",
        "backend.components.architechture",
        "backend.components.architechture.architecture",
        "components.architecture",
    ),
    "concevoir_architecture",
    default=None,
)
normaliser_architecture = _import_attr(
    _alts(
        "architecture",
        "backend.components.architecture",
        "backend.components.architecture.architecture",
        "backend.components.architechture",
        "backend.components.architechture.architecture",
        "components.architecture",
    ),
    "normaliser_architecture",
    default=None,
)


# =============================================================================
# Helpers
# =============================================================================

ModeDomaine = Literal["routier", "nautique", "aerien", "ferroviaire", "stationnaire", "autre"]
ModeTransmission = Literal["traction", "propulsion", "integrale", "direct", "autre"]
StrategieCroisiere = Literal["max_puissance_sous_contraintes", "min_conso", "pareto"]

G0 = 9.80665


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _sf(x: Any) -> Optional[float]:
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except Exception:
        return None


def _si(x: Any) -> Optional[int]:
    if isinstance(x, int) and not isinstance(x, bool):
        return int(x)
    f = _sf(x)
    return int(f) if f is not None else None


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    ok = v > 0.0 if strict else v >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v


def _req_ratio(name: str, x: Any, *, allow_zero: bool = False) -> float:
    v = _req_finite(name, x)
    if allow_zero:
        ok = 0.0 <= v <= 1.0
        op = "[0,1]"
    else:
        ok = 0.0 < v <= 1.0
        op = "(0,1]"
    if not ok:
        raise ValueError(f"{name} doit être dans {op} (reçu: {v}).")
    return v


def _rpm_to_rad_s(rpm: float) -> float:
    return 2.0 * math.pi * _req_finite("rpm", rpm) / 60.0


def _rad_s_to_rpm(omega: float) -> float:
    return _req_finite("omega", omega) * 60.0 / (2.0 * math.pi)


def _push(rep: Dict[str, Any], cat: str, nom: str, raison: str) -> None:
    rep.setdefault("inconnues", {}).setdefault(cat, []).append({"nom": str(nom), "raison": str(raison)})


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


def _merge_inconnues(dst: Dict[str, Any], src: Any, *, prefix: str) -> None:
    if not isinstance(src, Mapping):
        return
    inc = src.get("inconnues", {}) if isinstance(src.get("inconnues", {}), Mapping) else {}
    for cat in ("impossibles", "partielles"):
        for item in list(inc.get(cat, []) or []):
            if isinstance(item, Mapping):
                _push(dst, cat, f"{prefix}::{item.get('nom', '')}", str(item.get("raison", "")))


def _to_jsonable(value: Any, *, depth: int = 0, max_depth: int = 8) -> Any:
    if depth > max_depth:
        return {"type": type(value).__name__, "truncated": True}
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        try:
            return _to_jsonable(asdict(value), depth=depth + 1, max_depth=max_depth)
        except Exception:
            return {"type": type(value).__name__}
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v, depth=depth + 1, max_depth=max_depth) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v, depth=depth + 1, max_depth=max_depth) for v in value]
    if hasattr(value, "en_dict") and callable(getattr(value, "en_dict")):
        try:
            return _to_jsonable(value.en_dict(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return {"type": type(value).__name__, "attributs": _to_jsonable(vars(value), depth=depth + 1, max_depth=max_depth)}
        except Exception:
            pass
    return str(value)


def _safe_dict(x: Any) -> Dict[str, Any]:
    return dict(x) if isinstance(x, Mapping) else {}


def _get_path(obj: Any, *path: str) -> Any:
    cur = obj
    for p in path:
        if cur is None:
            return None
        if isinstance(cur, Mapping):
            cur = cur.get(p)
        else:
            cur = getattr(cur, p, None)
    return cur


def _call_supported(fn: Any, kwargs: Mapping[str, Any]) -> Any:
    if not callable(fn):
        raise TypeError("fonction non appelable")
    try:
        sig = inspect.signature(fn)
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            return fn(**dict(kwargs))
        accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return fn(**accepted)
    except (TypeError, ValueError):
        return fn(**dict(kwargs))


def _piece_report(module_names: Sequence[str], class_name: str, kwargs: Mapping[str, Any]) -> Dict[str, Any]:
    cls = _import_attr(module_names, class_name, default=None)
    if cls is None:
        return {
            "piece": class_name,
            "inconnues": {
                "impossibles": [
                    {"nom": class_name, "raison": "Classe de piece moteur electrique indisponible."}
                ],
                "partielles": [],
            },
            "notes_modele": [],
        }
    obj = cls(**dict(kwargs))
    if hasattr(obj, "analyser") and callable(getattr(obj, "analyser")):
        return _to_jsonable(obj.analyser())
    return _to_jsonable(obj)


def _normaliser_nom_architecture(value: Any) -> Any:
    if value is None:
        return None
    if callable(normaliser_architecture):
        try:
            return normaliser_architecture(value)
        except Exception:
            pass
    return value


def _first_source_rpm_optimal(sources: Sequence[Any]) -> Optional[float]:
    for src in sources:
        rpm = _sf(getattr(src, "rpm_optimal", None))
        if rpm is not None:
            return rpm
    for src in sources:
        rpm = _sf(getattr(src, "rpm_min_optimal", None))
        if rpm is not None:
            return rpm
    return None


def _cfg_get_multi(*mappings: Any, keys: Sequence[str], default: Any = None) -> Any:
    for mapping in mappings:
        if isinstance(mapping, Mapping):
            for key in keys:
                if key in mapping and mapping[key] is not None:
                    return mapping[key]
    return default


def _classement_architecture_depuis_rapport(rapport_arch: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """
    Transforme l'exploration de architecture.py en classement lisible.

    Le score de architecture.py est un coût relatif : plus il est bas, meilleur est
    le candidat. L'indice `efficacite_relative_100` est donc un indicateur de
    classement interne, pas un rendement thermodynamique.
    """
    rows: List[Dict[str, Any]] = []
    raw = rapport_arch.get("exploration", []) if isinstance(rapport_arch, Mapping) else []
    if not isinstance(raw, Sequence):
        raw = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        score = _sf(item.get("score_global"))
        score_multi = _sf(item.get("score_multi_criteres"))
        score_module = _sf(item.get("score_module_externe"))
        rank_score = score if score is not None else (score_multi if score_multi is not None else score_module)
        arch = _normaliser_nom_architecture(item.get("architecture"))
        rows.append({
            "architecture": arch,
            "N_cyl": item.get("N_cyl"),
            "score_global": score,
            "score_multi_criteres": score_multi,
            "score_module_externe": score_module,
            "score_classement": rank_score,
            "valide": item.get("valide"),
            "cylindree_tot_cc": item.get("cylindree_tot_cc"),
            "cylindree_unit_cc": item.get("cylindree_unit_cc"),
            "bore_mm": item.get("bore_mm"),
            "course_mm": item.get("course_mm"),
            "ratio_S_B": item.get("ratio_S_B"),
            "L_pkg_m_estimee": item.get("L_pkg_m_estimee"),
            "W_pkg_m_estimee": item.get("W_pkg_m_estimee"),
            "H_pkg_m_estimee": item.get("H_pkg_m_estimee"),
            "rendement_indice": item.get("rendement_indice"),
            "fiabilite_indice": item.get("fiabilite_indice"),
            "maintenance_indice": item.get("maintenance_indice"),
            "cout_maintenance_eur": item.get("cout_maintenance_eur"),
            "architecture_notes": item.get("architecture_notes"),
            "consequences_architecture": item.get("consequences_architecture"),
        })

    rows.sort(key=lambda r: (
        r.get("score_classement") is None,
        float(r.get("score_classement") or 1e18),
        str(r.get("architecture")),
        int(r.get("N_cyl") or 0),
    ))

    finite_scores = [float(r["score_classement"]) for r in rows if _sf(r.get("score_classement")) is not None]
    best_score = min(finite_scores) if finite_scores else None
    for idx, row in enumerate(rows, start=1):
        row["rang"] = idx
        sc = _sf(row.get("score_classement"))
        if best_score is not None and sc is not None and sc > 0.0:
            row["efficacite_relative_100"] = max(0.0, min(100.0, 100.0 * best_score / sc))
        elif idx == 1 and best_score is not None:
            row["efficacite_relative_100"] = 100.0
        else:
            row["efficacite_relative_100"] = None
    return rows


def _meilleurs_par_architecture_depuis_classement(classement: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}
    for row in classement:
        arch = str(row.get("architecture"))
        if not arch or arch == "None":
            continue
        current = best.get(arch)
        sc = _sf(row.get("score_classement"))
        cur_sc = _sf(current.get("score_classement")) if current else None
        if current is None or (sc is not None and (cur_sc is None or sc < cur_sc)):
            best[arch] = dict(row)
    return sorted(best.values(), key=lambda r: (
        r.get("score_classement") is None,
        float(r.get("score_classement") or 1e18),
        str(r.get("architecture")),
    ))


def analyser_architecture_moteur_thermique(
    config: Mapping[str, Any],
    sources: Sequence["MoteurThermiqueSource"],
    P_arbre_thermique_requise_w: Optional[float],
    rapport: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Appelle architecture.py pour choisir l'architecture moteur thermique.

    La première ligne du classement est le choix proposé. Les autres candidats
    restent calculés et classés pour permettre l'arbitrage CAO/SolidWorks.
    """
    bloc: Dict[str, Any] = {
        "disponible": bool(callable(concevoir_architecture)),
        "entrees_utilisees": {},
        "rapport_architecture": None,
        "meilleur_choix": None,
        "classement_par_efficacite": [],
        "meilleurs_par_architecture": [],
        "architecture_actuelle": None,
        "architecture_actuelle_est_optimale": None,
        "inconnues": {"impossibles": [], "partielles": []},
        "notes_modele": [],
    }

    if not callable(concevoir_architecture):
        _push(rapport, "partielles", "architecture.concevoir_architecture", "Module architecture.py indisponible ; classement architecture non calculé.")
        return bloc

    arch_cfg = _safe_dict(config.get("architecture"))
    mt_cfg = _safe_dict(config.get("moteur_thermique"))
    analyse_cfg = _safe_dict(arch_cfg.get("analyse"))
    if not analyse_cfg:
        analyse_cfg = dict(arch_cfg)

    rpm_source = _first_source_rpm_optimal(sources)
    puissance_cible_w = _cfg_get_multi(
        analyse_cfg, arch_cfg, mt_cfg, config,
        keys=("puissance_cible_w", "puissance_mecanique_requise_w", "puissance_thermique_mecanique_w"),
        default=P_arbre_thermique_requise_w,
    )
    regime_tr_min = _cfg_get_multi(
        analyse_cfg, arch_cfg, mt_cfg, config,
        keys=("regime_tr_min", "rpm_moteur", "rpm_nominal", "rpm_optimal"),
        default=rpm_source,
    )

    # Ne force pas l'architecture existante par défaut : elle sert seulement de
    # comparaison. On force uniquement si l'utilisateur fournit explicitement
    # `architecture_forcee`.
    architecture_actuelle = _normaliser_nom_architecture(_cfg_get_multi(
        mt_cfg, arch_cfg, config,
        keys=("architecture", "architecture_moteur"),
        default=None,
    ))
    architecture_forcee = _cfg_get_multi(
        analyse_cfg, arch_cfg, config,
        keys=("architecture_forcee",),
        default=None,
    )
    if architecture_forcee is not None:
        architecture_forcee = _normaliser_nom_architecture(architecture_forcee)

    call_cfg: Dict[str, Any] = {
        "puissance_cible_w": puissance_cible_w,
        "regime_tr_min": regime_tr_min,
        "pme_pa": _cfg_get_multi(analyse_cfg, arch_cfg, mt_cfg, config, keys=("pme_pa", "PME_pa")),
        "vitesse_piston_max_ms": _cfg_get_multi(analyse_cfg, arch_cfg, mt_cfg, config, keys=("vitesse_piston_max_ms", "Up_max_ms")),
        "longueur_dispo_m": _cfg_get_multi(analyse_cfg, arch_cfg, mt_cfg, config, keys=("longueur_dispo_m", "L_max_m", "longueur_max_m")),
        "largeur_dispo_m": _cfg_get_multi(analyse_cfg, arch_cfg, mt_cfg, config, keys=("largeur_dispo_m", "W_max_m", "largeur_max_m")),
        "hauteur_dispo_m": _cfg_get_multi(analyse_cfg, arch_cfg, mt_cfg, config, keys=("hauteur_dispo_m", "H_max_m", "hauteur_max_m")),
        "horizon_usage_h": _cfg_get_multi(analyse_cfg, arch_cfg, mt_cfg, config, keys=("horizon_usage_h",)),
        "taux_compression": _cfg_get_multi(analyse_cfg, arch_cfg, mt_cfg, config, keys=("taux_compression",)),
        "cas_de_charge": _cfg_get_multi(analyse_cfg, arch_cfg, mt_cfg, config, keys=("cas_de_charge",)),
        "ordre_allumage_map": _cfg_get_multi(analyse_cfg, arch_cfg, mt_cfg, config, keys=("ordre_allumage_map",)),
        "ponderations_cas": _cfg_get_multi(analyse_cfg, arch_cfg, mt_cfg, config, keys=("ponderations_cas",)),
        "architectures_autorisees": _cfg_get_multi(analyse_cfg, arch_cfg, mt_cfg, config, keys=("architectures_autorisees",)),
        "architecture_forcee": architecture_forcee,
        "inclure_architectures_systeme": _cfg_get_multi(analyse_cfg, arch_cfg, config, keys=("inclure_architectures_systeme",), default=False),
        "poids_maintenance": _cfg_get_multi(analyse_cfg, arch_cfg, config, keys=("poids_maintenance",)),
        "poids_masse": _cfg_get_multi(analyse_cfg, arch_cfg, config, keys=("poids_masse",)),
        "poids_cout_matiere": _cfg_get_multi(analyse_cfg, arch_cfg, config, keys=("poids_cout_matiere",)),
        "poids_compacite": _cfg_get_multi(analyse_cfg, arch_cfg, config, keys=("poids_compacite",)),
        "poids_fiabilite": _cfg_get_multi(analyse_cfg, arch_cfg, config, keys=("poids_fiabilite",)),
        "poids_rendement": _cfg_get_multi(analyse_cfg, arch_cfg, config, keys=("poids_rendement",)),
        "usage": _cfg_get_multi(analyse_cfg, arch_cfg, config, keys=("usage",)),
        "domaine_mobilite": _cfg_get_multi(analyse_cfg, arch_cfg, config, keys=("domaine_mobilite",)),
        "type_vehicule": _cfg_get_multi(analyse_cfg, arch_cfg, config, keys=("type_vehicule",)),
        "mode_transmission": _cfg_get_multi(analyse_cfg, arch_cfg, config, keys=("mode_transmission",)),
        "demande_mobilite": _cfg_get_multi(analyse_cfg, arch_cfg, config, keys=("demande_mobilite",)),
        "commentaire_usage": _cfg_get_multi(analyse_cfg, arch_cfg, config, keys=("commentaire_usage",)),
    }
    call_cfg = {k: v for k, v in call_cfg.items() if v is not None}
    if architecture_forcee is None:
        # Retire toute clé vide pour laisser architecture.py explorer tous les candidats.
        call_cfg.pop("architecture_forcee", None)

    bloc["entrees_utilisees"] = _to_jsonable(call_cfg)
    bloc["architecture_actuelle"] = architecture_actuelle

    try:
        rep_arch = concevoir_architecture({"analyse": call_cfg})
    except Exception as exc:
        _push(rapport, "partielles", "architecture.concevoir_architecture", f"Analyse architecture impossible : {exc}")
        bloc["erreur"] = str(exc)
        return bloc

    rep_arch = _to_jsonable(rep_arch)
    bloc["rapport_architecture"] = rep_arch
    _merge_inconnues(rapport, rep_arch, prefix="architecture")

    classement = _classement_architecture_depuis_rapport(_safe_dict(rep_arch))
    meilleurs_par_arch = _meilleurs_par_architecture_depuis_classement(classement)
    meilleur = classement[0] if classement else None

    # Si architecture.py fournit explicitement `meilleur`, il est conservé comme
    # source principale mais le classement complet reste disponible.
    meilleur_src = _safe_dict(_safe_dict(rep_arch).get("meilleur"))
    if meilleur_src:
        meilleur_arch = _normaliser_nom_architecture(meilleur_src.get("architecture"))
        for row in classement:
            if (row.get("architecture") == meilleur_arch and row.get("N_cyl") == meilleur_src.get("N_cyl")):
                meilleur = row
                break
        if meilleur is None:
            meilleur = {
                "architecture": meilleur_arch,
                "N_cyl": meilleur_src.get("N_cyl"),
                "score_global": meilleur_src.get("score_global"),
                "score_classement": meilleur_src.get("score_global"),
                "efficacite_relative_100": 100.0,
                "source": "rapport_architecture.meilleur",
            }

    bloc["meilleur_choix"] = meilleur
    bloc["classement_par_efficacite"] = classement
    bloc["meilleurs_par_architecture"] = meilleurs_par_arch

    if meilleur and architecture_actuelle is not None:
        bloc["architecture_actuelle_est_optimale"] = (architecture_actuelle == meilleur.get("architecture"))
        if bloc["architecture_actuelle_est_optimale"] is False:
            rapport.setdefault("alertes", {}).setdefault("architecture", []).append({
                "nom": "architecture_non_optimale",
                "detail": f"Architecture actuelle {architecture_actuelle!r} différente du meilleur choix {meilleur.get('architecture')!r}.",
            })

    if meilleur is None:
        _push(rapport, "partielles", "architecture.classement", "Aucun candidat d'architecture classable avec les données fournies.")

    return bloc


# =============================================================================
# Dataclasses système
# =============================================================================

@dataclass(frozen=True)
class MoteurSortie:
    """Moteur utile de sortie : traction, propulsion, hélice, pompe hydraulique, etc."""

    nom: str = "moteur_sortie"
    quantite: int = 1
    puissance_max_w: Optional[float] = None              # puissance utile mécanique maximale par moteur
    puissance_continue_w: Optional[float] = None         # puissance utile continue par moteur
    rendement_moteur: Optional[float] = None             # utile mécanique / électrique bus
    rendement_transmission: float = 1.0                  # sortie finale / arbre moteur
    regime_max_rpm: Optional[float] = None
    regime_base_rpm: Optional[float] = None
    couple_max_nm: Optional[float] = None
    tension_bus_v: Optional[float] = None
    courant_max_a: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.quantite, int) or self.quantite < 1:
            raise ValueError("MoteurSortie.quantite doit être un entier >= 1.")
        for name in ("puissance_max_w", "puissance_continue_w", "regime_max_rpm", "regime_base_rpm", "couple_max_nm", "tension_bus_v", "courant_max_a"):
            v = getattr(self, name)
            if v is not None:
                _req_pos(name, v, strict=False if name.startswith("puissance") else True)
        if self.rendement_moteur is not None:
            _req_ratio("rendement_moteur", self.rendement_moteur)
        _req_ratio("rendement_transmission", self.rendement_transmission)

    @property
    def puissance_max_totale_w(self) -> Optional[float]:
        return None if self.puissance_max_w is None else self.puissance_max_w * self.quantite

    @property
    def puissance_continue_totale_w(self) -> Optional[float]:
        p = self.puissance_continue_w if self.puissance_continue_w is not None else self.puissance_max_w
        return None if p is None else p * self.quantite


class MoteurElectrique(MoteurSortie):
    """Compatibilite composant unitaire moteur electrique.

    Cette classe n'ajoute pas de valeur par defaut metier. Elle expose seulement
    le rapport attendu par les consommateurs historiques quand les entrees sont
    fournies explicitement.
    """

    @property
    def couple_max_nm_calcule(self) -> Optional[float]:
        return self.couple_max_nm

    @property
    def regime_base_rpm_calcule(self) -> Optional[float]:
        if self.regime_base_rpm is not None:
            return self.regime_base_rpm
        if self.puissance_max_w is not None and self.couple_max_nm is not None and self.couple_max_nm > 0.0:
            return float(self.puissance_max_w) * 60.0 / (2.0 * math.pi * float(self.couple_max_nm))
        return None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rotor_report = _piece_report(
            (
                "backend.components.moteur_electrique.pieces.rotor_moteur_electrique",
                "components.moteur_electrique.pieces.rotor_moteur_electrique",
            ),
            "RotorMoteurElectrique",
            {"moteur": self},
        )
        stator_report = _piece_report(
            (
                "backend.components.moteur_electrique.pieces.stator_moteur_electrique",
                "components.moteur_electrique.pieces.stator_moteur_electrique",
            ),
            "StatorMoteurElectrique",
            {"moteur": self},
        )
        report: Dict[str, Any] = {
            "composant": "moteur_electrique",
            "definition": {
                "puissance_max_w": self.puissance_max_w,
                "regime_max_rpm": self.regime_max_rpm,
                "regime_base_rpm": self.regime_base_rpm_calcule,
                "couple_max_nm": self.couple_max_nm,
                "rendement_moteur": self.rendement_moteur,
                "tension_bus_v": self.tension_bus_v,
                "courant_max_a": self.courant_max_a,
            },
            "pieces": {
                "rotor": rotor_report,
                "stator": stator_report,
            },
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }
        for name in ("puissance_max_w", "regime_max_rpm", "couple_max_nm"):
            if report["definition"].get(name) is None:
                report["inconnues"]["partielles"].append({"nom": name, "raison": "Donnee moteur electrique non fournie."})
        return _to_jsonable(report)


@dataclass(frozen=True)
class ChargeAuxiliaire:
    nom: str
    puissance_continue_w: float
    puissance_pic_w: Optional[float] = None
    critique: bool = True
    duty: float = 1.0

    def __post_init__(self) -> None:
        _req_pos("puissance_continue_w", self.puissance_continue_w, strict=False)
        if self.puissance_pic_w is not None:
            _req_pos("puissance_pic_w", self.puissance_pic_w, strict=False)
        _req_ratio("duty", self.duty, allow_zero=True)

    @property
    def puissance_moyenne_w(self) -> float:
        return self.puissance_continue_w * self.duty

    @property
    def puissance_max_w(self) -> float:
        return max(self.puissance_continue_w, self.puissance_pic_w if self.puissance_pic_w is not None else 0.0)


@dataclass(frozen=True)
class MoteurThermiqueSource:
    nom: str = "moteur_thermique"
    quantite: int = 1
    puissance_arbre_max_w: Optional[float] = None
    puissance_arbre_continue_w: Optional[float] = None
    rpm_optimal: Optional[float] = None
    rpm_min_optimal: Optional[float] = None
    rpm_max_optimal: Optional[float] = None
    couple_max_nm: Optional[float] = None
    rendement_global: Optional[float] = None
    bsfc_g_kwh: Optional[float] = None
    bsfc_map: Optional[Sequence[Mapping[str, Any]]] = None
    charge_min_efficiente: Optional[float] = None
    charge_max_durable: Optional[float] = None
    duty_max: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.quantite, int) or self.quantite < 1:
            raise ValueError("MoteurThermiqueSource.quantite doit être >= 1.")
        for name in ("puissance_arbre_max_w", "puissance_arbre_continue_w", "rpm_optimal", "rpm_min_optimal", "rpm_max_optimal", "couple_max_nm", "bsfc_g_kwh"):
            v = getattr(self, name)
            if v is not None:
                _req_pos(name, v, strict=True)
        if self.rendement_global is not None:
            _req_ratio("rendement_global", self.rendement_global)
        for name in ("charge_min_efficiente", "charge_max_durable", "duty_max"):
            v = getattr(self, name)
            if v is not None:
                _req_ratio(name, v)

    @property
    def puissance_max_totale_w(self) -> Optional[float]:
        return None if self.puissance_arbre_max_w is None else self.puissance_arbre_max_w * self.quantite

    @property
    def puissance_continue_totale_w(self) -> Optional[float]:
        p = self.puissance_arbre_continue_w if self.puissance_arbre_continue_w is not None else self.puissance_arbre_max_w
        return None if p is None else p * self.quantite


@dataclass(frozen=True)
class ExigenceSortie:
    puissance_sortie_max_w: float
    puissance_sortie_continue_w: Optional[float] = None
    puissance_sortie_croisiere_min_w: Optional[float] = None
    puissance_sortie_croisiere_pref_w: Optional[float] = None
    marge_puissance: float = 0.0
    duree_pic_s: Optional[float] = None

    def __post_init__(self) -> None:
        _req_pos("puissance_sortie_max_w", self.puissance_sortie_max_w, strict=False)
        for name in ("puissance_sortie_continue_w", "puissance_sortie_croisiere_min_w", "puissance_sortie_croisiere_pref_w", "duree_pic_s"):
            v = getattr(self, name)
            if v is not None:
                _req_pos(name, v, strict=False)
        _req_ratio("marge_puissance", self.marge_puissance, allow_zero=True)


@dataclass(frozen=True)
class BatterieTamponSpec:
    capacite_nominale_kwh: Optional[float] = None
    fenetre_soc: float = 0.8
    tension_nominale_v: Optional[float] = None
    tension_charge_v: Optional[float] = None
    densite_energetique_kwh_kg: Optional[float] = None
    c_rate_decharge_continue_max: Optional[float] = None
    c_rate_decharge_pic_max: Optional[float] = None
    c_rate_charge_max: Optional[float] = None
    masse_pack_max_kg: Optional[float] = None
    temps_recharge_max_h: Optional[float] = None
    autonomie_elec_min_h: Optional[float] = None
    energie_tampon_min_kwh: Optional[float] = None

    def __post_init__(self) -> None:
        _req_ratio("fenetre_soc", self.fenetre_soc)
        for name in (
            "capacite_nominale_kwh", "tension_nominale_v", "tension_charge_v", "densite_energetique_kwh_kg",
            "c_rate_decharge_continue_max", "c_rate_decharge_pic_max", "c_rate_charge_max", "masse_pack_max_kg",
            "temps_recharge_max_h", "autonomie_elec_min_h", "energie_tampon_min_kwh",
        ):
            v = getattr(self, name)
            if v is not None:
                _req_pos(name, v, strict=True)


@dataclass(frozen=True)
class TransmissionGenerationSpec:
    rendement_boite: Optional[float] = None
    rendement_alternateur: Optional[float] = None
    rendement_redressement: Optional[float] = None
    rendement_charge: Optional[float] = None
    rpm_alternateur_cible: Optional[float] = None
    rpm_alternateur_min_optimal: Optional[float] = None
    rpm_alternateur_max_optimal: Optional[float] = None
    rapports_boite: Optional[Sequence[float]] = None
    rapport_min: Optional[float] = None
    rapport_max: Optional[float] = None

    def __post_init__(self) -> None:
        for name in ("rendement_boite", "rendement_alternateur", "rendement_redressement", "rendement_charge"):
            v = getattr(self, name)
            if v is not None:
                _req_ratio(name, v)
        for name in ("rpm_alternateur_cible", "rpm_alternateur_min_optimal", "rpm_alternateur_max_optimal", "rapport_min", "rapport_max"):
            v = getattr(self, name)
            if v is not None:
                _req_pos(name, v, strict=True)


@dataclass(frozen=True)
class CycleCroisiereSpec:
    strategie: StrategieCroisiere = "max_puissance_sous_contraintes"
    candidats_puissance_sortie_w: Optional[Sequence[float]] = None
    fractions_puissance: Optional[Sequence[float]] = None
    conso_max_g_h: Optional[float] = None
    bsfc_max_g_kwh: Optional[float] = None
    charge_moteur_max_durable: Optional[float] = None
    charge_moteur_min_efficiente: Optional[float] = None
    duty_moteur_max: Optional[float] = None
    puissance_recharge_batterie_croisiere_w: float = 0.0

    def __post_init__(self) -> None:
        if self.strategie not in ("max_puissance_sous_contraintes", "min_conso", "pareto"):
            raise ValueError("strategie croisiere invalide")
        for name in ("conso_max_g_h", "bsfc_max_g_kwh", "puissance_recharge_batterie_croisiere_w"):
            v = getattr(self, name)
            if v is not None:
                _req_pos(name, v, strict=False)
        for name in ("charge_moteur_max_durable", "charge_moteur_min_efficiente", "duty_moteur_max"):
            v = getattr(self, name)
            if v is not None:
                _req_ratio(name, v)


# =============================================================================
# Construction depuis dict
# =============================================================================

def _listify(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    if isinstance(x, tuple):
        return list(x)
    return [x]


def _build_dataclass(cls: Any, payload: Any, *, default: Optional[Mapping[str, Any]] = None) -> Any:
    data = dict(default or {})
    if isinstance(payload, Mapping):
        data.update(dict(payload))
    elif payload is not None and is_dataclass(payload):
        return payload
    elif payload is not None:
        return payload
    allowed = set(inspect.signature(cls).parameters.keys())
    return cls(**{k: v for k, v in data.items() if k in allowed})


def normaliser_moteurs_sortie(config: Mapping[str, Any]) -> List[MoteurSortie]:
    blocs = _listify(config.get("moteurs_sortie"))
    if not blocs:
        # Compatibilité : un ancien bloc moteur_electrique + nb_moteurs.
        me = config.get("moteur_electrique", config.get("moteur_sortie", None))
        if isinstance(me, Mapping):
            data = dict(me)
            if "quantite" not in data and "nb_moteurs_electriques" in config:
                data["quantite"] = config.get("nb_moteurs_electriques")
            if "puissance_max_w" not in data and "puissance_sortie_max_w" in data:
                data["puissance_max_w"] = data["puissance_sortie_max_w"]
            blocs = [data]
    return [_build_dataclass(MoteurSortie, b) for b in blocs]


def normaliser_auxiliaires(config: Mapping[str, Any]) -> List[ChargeAuxiliaire]:
    out: List[ChargeAuxiliaire] = []
    for b in _listify(config.get("auxiliaires", config.get("charges_auxiliaires"))):
        if isinstance(b, Mapping):
            out.append(_build_dataclass(ChargeAuxiliaire, b))
    p_aux = _sf(config.get("puissance_auxiliaire_w"))
    if p_aux is not None and p_aux > 0:
        out.append(ChargeAuxiliaire(nom="auxiliaires_global", puissance_continue_w=p_aux))
    return out


def normaliser_sources_thermiques(config: Mapping[str, Any]) -> List[MoteurThermiqueSource]:
    blocs = _listify(config.get("moteurs_thermiques"))
    if not blocs:
        mt = config.get("moteur_thermique", config.get("source_thermique"))
        if isinstance(mt, Mapping):
            blocs = [mt]
    return [_build_dataclass(MoteurThermiqueSource, b) for b in blocs]


# =============================================================================
# Calculs cœur
# =============================================================================

def repartir_puissance_sur_moteurs(
    moteurs: Sequence[MoteurSortie],
    puissance_sortie_w: float,
    rapport: Dict[str, Any],
    *,
    prefix: str,
) -> Tuple[List[Dict[str, Any]], Optional[float]]:
    """Répartit une puissance utile sur les moteurs selon leur puissance max."""
    P = _req_pos("puissance_sortie_w", puissance_sortie_w, strict=False)
    rows: List[Dict[str, Any]] = []
    total_rating = 0.0
    missing_rating = False
    for m in moteurs:
        if m.puissance_max_totale_w is None:
            missing_rating = True
        else:
            total_rating += m.puissance_max_totale_w
    if missing_rating or total_rating <= 0:
        _push(rapport, "impossibles", f"{prefix}.repartition_moteurs", "Toutes les puissances_max_w des moteurs de sortie sont requises pour répartir la puissance utile.")
        return rows, None

    P_bus_total = 0.0
    bus_ok = True
    for m in moteurs:
        assert m.puissance_max_totale_w is not None
        part = m.puissance_max_totale_w / total_rating
        P_sortie_m = P * part
        P_arbre_moteur = P_sortie_m / m.rendement_transmission
        P_bus_m = None
        if m.rendement_moteur is not None:
            P_bus_m = P_arbre_moteur / m.rendement_moteur
            P_bus_total += P_bus_m
        else:
            bus_ok = False
            _push(rapport, "partielles", f"{prefix}.{m.nom}.rendement_moteur", "Requis pour convertir puissance utile -> puissance bus DC.")
        rows.append({
            "nom": m.nom,
            "quantite": m.quantite,
            "part_puissance": part,
            "puissance_sortie_w": P_sortie_m,
            "puissance_arbre_moteur_w": P_arbre_moteur,
            "puissance_bus_dc_w": P_bus_m,
            "rendement_moteur": m.rendement_moteur,
            "rendement_transmission": m.rendement_transmission,
        })
    return rows, P_bus_total if bus_ok else None


def calculer_sortie_et_bus(
    moteurs: Sequence[MoteurSortie],
    auxiliaires: Sequence[ChargeAuxiliaire],
    exigence: ExigenceSortie,
    rapport: Dict[str, Any],
) -> Dict[str, Any]:
    bloc: Dict[str, Any] = {"moteurs": [], "auxiliaires": [], "checks": {}, "puissances": {}}

    P_inst_max: Optional[float] = None
    P_inst_cont: Optional[float] = None
    if moteurs:
        vals_max = [m.puissance_max_totale_w for m in moteurs]
        vals_cont = [m.puissance_continue_totale_w for m in moteurs]
        if all(v is not None for v in vals_max):
            P_inst_max = float(sum(v for v in vals_max if v is not None))
        else:
            _push(rapport, "impossibles", "puissance_installee_sortie_max", "puissance_max_w requise pour chaque moteur de sortie.")
        if all(v is not None for v in vals_cont):
            P_inst_cont = float(sum(v for v in vals_cont if v is not None))
        else:
            _push(rapport, "partielles", "puissance_installee_sortie_continue", "puissance_continue_w ou puissance_max_w requise pour chaque moteur.")
    else:
        _push(rapport, "impossibles", "moteurs_sortie", "Au moins un moteur de sortie est requis.")

    P_req_max = exigence.puissance_sortie_max_w * (1.0 + exigence.marge_puissance)
    P_req_cont = (exigence.puissance_sortie_continue_w or exigence.puissance_sortie_max_w) * (1.0 + exigence.marge_puissance)

    bloc["checks"].update({
        "puissance_sortie_max_demandee_w": exigence.puissance_sortie_max_w,
        "puissance_sortie_max_avec_marge_w": P_req_max,
        "puissance_sortie_continue_demandee_w": exigence.puissance_sortie_continue_w,
        "puissance_installee_sortie_max_w": P_inst_max,
        "puissance_installee_sortie_continue_w": P_inst_cont,
        "ok_sortie_max": None if P_inst_max is None else bool(P_inst_max >= P_req_max),
        "ok_sortie_continue": None if P_inst_cont is None else bool(P_inst_cont >= P_req_cont),
    })
    if P_inst_max is not None and P_inst_max < P_req_max:
        _push(rapport, "impossibles", "moteurs_sortie.sous_dimensionnes", f"Puissance installée {P_inst_max:.1f} W < demande avec marge {P_req_max:.1f} W.")

    aux_continue = sum(a.puissance_continue_w for a in auxiliaires)
    aux_moyenne = sum(a.puissance_moyenne_w for a in auxiliaires)
    aux_max = sum(a.puissance_max_w for a in auxiliaires)
    bloc["auxiliaires"] = [_to_jsonable(a) for a in auxiliaires]

    repart_max, P_bus_moteurs_max = repartir_puissance_sur_moteurs(moteurs, exigence.puissance_sortie_max_w, rapport, prefix="sortie_max")
    P_bus_max = None if P_bus_moteurs_max is None else P_bus_moteurs_max + aux_max

    P_cont = exigence.puissance_sortie_continue_w if exigence.puissance_sortie_continue_w is not None else exigence.puissance_sortie_max_w
    repart_cont, P_bus_moteurs_cont = repartir_puissance_sur_moteurs(moteurs, P_cont, rapport, prefix="sortie_continue")
    P_bus_cont = None if P_bus_moteurs_cont is None else P_bus_moteurs_cont + aux_continue

    bloc["moteurs"] = [_to_jsonable(m) for m in moteurs]
    bloc["puissances"].update({
        "auxiliaires_continue_w": aux_continue,
        "auxiliaires_moyenne_w": aux_moyenne,
        "auxiliaires_max_w": aux_max,
        "repartition_sortie_max": repart_max,
        "repartition_sortie_continue": repart_cont,
        "P_bus_moteurs_sortie_max_w": P_bus_moteurs_max,
        "P_bus_moteurs_continue_w": P_bus_moteurs_cont,
        "P_bus_dc_sortie_max_total_w": P_bus_max,
        "P_bus_dc_continue_total_w": P_bus_cont,
        "P_bus_dc_min_theorique_sortie_max_w": exigence.puissance_sortie_max_w + aux_max,
    })
    return bloc


def _bsfc_depuis_map(source: MoteurThermiqueSource, puissance_arbre_par_moteur_w: float) -> Optional[float]:
    if source.bsfc_map:
        # Interpolation linéaire par puissance_w ou charge.
        pts: List[Tuple[float, float]] = []
        pmax = source.puissance_arbre_max_w
        for item in source.bsfc_map:
            if not isinstance(item, Mapping):
                continue
            bsfc = _sf(item.get("bsfc_g_kwh", item.get("bsfc")))
            p = _sf(item.get("puissance_w"))
            ch = _sf(item.get("charge"))
            if p is None and ch is not None and pmax is not None:
                p = ch * pmax
            if p is not None and bsfc is not None:
                pts.append((p, bsfc))
        pts.sort(key=lambda t: t[0])
        if not pts:
            return None
        P = float(puissance_arbre_par_moteur_w)
        if P <= pts[0][0]:
            return pts[0][1]
        if P >= pts[-1][0]:
            return pts[-1][1]
        for (p0, b0), (p1, b1) in zip(pts, pts[1:]):
            if p0 <= P <= p1:
                if abs(p1 - p0) <= 1e-12:
                    return b0
                t = (P - p0) / (p1 - p0)
                return b0 + t * (b1 - b0)
    return source.bsfc_g_kwh


def evaluer_sources_thermiques(
    sources: Sequence[MoteurThermiqueSource],
    puissance_arbre_requise_w: Optional[float],
    rapport: Dict[str, Any],
    *,
    contexte: str,
) -> Dict[str, Any]:
    bloc: Dict[str, Any] = {"sources": [_to_jsonable(s) for s in sources], "checks": {}, "repartition": []}
    if not sources:
        _push(rapport, "impossibles", f"{contexte}.moteur_thermique", "Au moins une source thermique est requise pour dimensionner la génération.")
        return bloc
    Pmax_vals = [s.puissance_max_totale_w for s in sources]
    Pcont_vals = [s.puissance_continue_totale_w for s in sources]
    Pmax_total = sum(v for v in Pmax_vals if v is not None) if all(v is not None for v in Pmax_vals) else None
    Pcont_total = sum(v for v in Pcont_vals if v is not None) if all(v is not None for v in Pcont_vals) else None
    if Pmax_total is None:
        _push(rapport, "impossibles", f"{contexte}.puissance_thermique_max", "puissance_arbre_max_w requise pour chaque moteur thermique.")
    if Pcont_total is None:
        _push(rapport, "partielles", f"{contexte}.puissance_thermique_continue", "puissance_arbre_continue_w ou puissance_arbre_max_w requise pour chaque moteur thermique.")

    bloc["checks"].update({
        "puissance_arbre_requise_w": puissance_arbre_requise_w,
        "puissance_arbre_max_totale_w": Pmax_total,
        "puissance_arbre_continue_totale_w": Pcont_total,
        "ok_puissance_max": None if (Pmax_total is None or puissance_arbre_requise_w is None) else bool(Pmax_total >= puissance_arbre_requise_w),
        "ok_puissance_continue": None if (Pcont_total is None or puissance_arbre_requise_w is None) else bool(Pcont_total >= puissance_arbre_requise_w),
    })
    if puissance_arbre_requise_w is not None and Pmax_total is not None and Pmax_total < puissance_arbre_requise_w:
        _push(rapport, "impossibles", f"{contexte}.thermique_sous_dimensionne", f"Puissance thermique max {Pmax_total:.1f} W < requise {puissance_arbre_requise_w:.1f} W.")

    if puissance_arbre_requise_w is not None and Pmax_total and Pmax_total > 0:
        for s in sources:
            if s.puissance_max_totale_w is None or s.puissance_arbre_max_w is None:
                continue
            part = s.puissance_max_totale_w / Pmax_total
            P_total_source = puissance_arbre_requise_w * part
            P_par_moteur = P_total_source / s.quantite
            charge = P_par_moteur / s.puissance_arbre_max_w
            bsfc = _bsfc_depuis_map(s, P_par_moteur)
            fuel_g_h = None if bsfc is None else bsfc * (P_par_moteur / 1000.0) * s.quantite
            bloc["repartition"].append({
                "nom": s.nom,
                "quantite": s.quantite,
                "part_puissance": part,
                "puissance_arbre_totale_source_w": P_total_source,
                "puissance_arbre_par_moteur_w": P_par_moteur,
                "charge_par_moteur": charge,
                "bsfc_g_kwh": bsfc,
                "debit_carburant_g_h": fuel_g_h,
                "dans_plage_charge_durable": None if s.charge_max_durable is None else charge <= s.charge_max_durable,
                "dans_plage_charge_efficiente_min": None if s.charge_min_efficiente is None else charge >= s.charge_min_efficiente,
            })
    return bloc


def calculer_generation_depuis_bus(
    P_bus_dc_w: Optional[float],
    transmission: TransmissionGenerationSpec,
    rapport: Dict[str, Any],
    *,
    contexte: str,
    puissance_recharge_batterie_w: float = 0.0,
) -> Dict[str, Any]:
    bloc: Dict[str, Any] = {"entrees": {}, "resultats": {}, "manquants": []}
    if P_bus_dc_w is None:
        _push(rapport, "impossibles", f"{contexte}.P_bus_dc_w", "Puissance bus DC requise pour calculer alternateur/boîte/thermique.")
        return bloc
    Pdc = _req_pos("P_bus_dc_w", P_bus_dc_w, strict=False) + _req_pos("puissance_recharge_batterie_w", puissance_recharge_batterie_w, strict=False)

    eta_red = transmission.rendement_redressement
    eta_alt = transmission.rendement_alternateur
    eta_boite = transmission.rendement_boite
    bloc["entrees"] = {"P_bus_dc_w": P_bus_dc_w, "puissance_recharge_batterie_w": puissance_recharge_batterie_w, "Pdc_total_w": Pdc, "eta_redressement": eta_red, "eta_alternateur": eta_alt, "eta_boite": eta_boite}

    P_elec_alt_ac_w = None
    P_arbre_alt_w = None
    P_arbre_thermique_w = None
    if eta_red is not None:
        P_elec_alt_ac_w = Pdc / eta_red
    else:
        bloc["manquants"].append("rendement_redressement")
        _push(rapport, "partielles", f"{contexte}.rendement_redressement", "Requis pour convertir bus DC -> puissance électrique alternateur.")
    if P_elec_alt_ac_w is not None and eta_alt is not None:
        P_arbre_alt_w = P_elec_alt_ac_w / eta_alt
    else:
        if eta_alt is None:
            bloc["manquants"].append("rendement_alternateur")
            _push(rapport, "partielles", f"{contexte}.rendement_alternateur", "Requis pour convertir puissance électrique alternateur -> puissance arbre alternateur.")
    if P_arbre_alt_w is not None and eta_boite is not None:
        P_arbre_thermique_w = P_arbre_alt_w / eta_boite
    else:
        if eta_boite is None:
            bloc["manquants"].append("rendement_boite")
            _push(rapport, "partielles", f"{contexte}.rendement_boite", "Requis pour convertir arbre alternateur -> arbre moteur thermique.")

    bloc["resultats"] = {
        "P_bus_dc_total_w": Pdc,
        "P_electrique_alternateur_requise_w": P_elec_alt_ac_w,
        "P_arbre_alternateur_requise_w": P_arbre_alt_w,
        "P_arbre_thermique_requise_w": P_arbre_thermique_w,
        "P_arbre_thermique_min_theorique_w": Pdc,
    }
    return bloc


def generer_candidats_croisiere(exigence: ExigenceSortie, spec: CycleCroisiereSpec, rapport: Dict[str, Any]) -> List[float]:
    if spec.candidats_puissance_sortie_w:
        vals = [_req_pos("candidat_puissance_sortie_w", v, strict=False) for v in spec.candidats_puissance_sortie_w]
    else:
        if spec.fractions_puissance:
            fractions = [_req_ratio("fraction_puissance", f, allow_zero=True) for f in spec.fractions_puissance]
        else:
            # Ce sont des points de recherche, pas des hypothèses physiques.
            fractions = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
            rapport.setdefault("notes_modele", []).append("Candidats croisière générés comme fractions algorithmiques de la puissance max, faute de liste fournie.")
        vals = [exigence.puissance_sortie_max_w * f for f in fractions]
    # filtre selon mini requis si fourni
    if exigence.puissance_sortie_croisiere_min_w is not None:
        vals = [v for v in vals if v >= exigence.puissance_sortie_croisiere_min_w]
    return sorted(set(float(v) for v in vals if math.isfinite(v) and v >= 0.0))


def analyser_cycle_croisiere(
    moteurs: Sequence[MoteurSortie],
    auxiliaires: Sequence[ChargeAuxiliaire],
    sources: Sequence[MoteurThermiqueSource],
    exigence: ExigenceSortie,
    transmission: TransmissionGenerationSpec,
    cycle: CycleCroisiereSpec,
    rapport: Dict[str, Any],
) -> Dict[str, Any]:
    bloc: Dict[str, Any] = {"candidats": [], "selection": None, "pareto": []}
    candidats = generer_candidats_croisiere(exigence, cycle, rapport)
    if not candidats:
        _push(rapport, "impossibles", "cycle_croisiere.candidats", "Aucun candidat de puissance croisière disponible.")
        return bloc

    for P_sortie in candidats:
        local_notes: List[str] = []
        rep_local: Dict[str, Any] = {"inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        repart, P_bus_moteurs = repartir_puissance_sur_moteurs(moteurs, P_sortie, rep_local, prefix="croisiere")
        aux_moy = sum(a.puissance_moyenne_w for a in auxiliaires)
        P_bus = None if P_bus_moteurs is None else P_bus_moteurs + aux_moy
        gen = calculer_generation_depuis_bus(
            P_bus,
            transmission,
            rep_local,
            contexte="croisiere",
            puissance_recharge_batterie_w=cycle.puissance_recharge_batterie_croisiere_w,
        )
        P_therm = _sf(_get_path(gen, "resultats", "P_arbre_thermique_requise_w"))
        therm = evaluer_sources_thermiques(sources, P_therm, rep_local, contexte="croisiere")

        conso_g_h = 0.0
        has_conso = False
        bsfc_equiv = None
        for row in therm.get("repartition", []) or []:
            fg = _sf(row.get("debit_carburant_g_h"))
            if fg is not None:
                has_conso = True
                conso_g_h += fg
        if has_conso and P_therm and P_therm > 0:
            bsfc_equiv = conso_g_h / (P_therm / 1000.0)

        # Contraintes
        ok = True
        reasons: List[str] = []
        ok_therm_cont = _get_path(therm, "checks", "ok_puissance_continue")
        if ok_therm_cont is False:
            ok = False; reasons.append("thermique_continue_insuffisant")
        ok_therm_max = _get_path(therm, "checks", "ok_puissance_max")
        if ok_therm_max is False:
            ok = False; reasons.append("thermique_max_insuffisant")
        if cycle.conso_max_g_h is not None and has_conso and conso_g_h > cycle.conso_max_g_h:
            ok = False; reasons.append("conso_g_h_depassee")
        if cycle.bsfc_max_g_kwh is not None and bsfc_equiv is not None and bsfc_equiv > cycle.bsfc_max_g_kwh:
            ok = False; reasons.append("bsfc_depasse")

        # Contraintes de charge moteur : cycle > source spécifique si fourni.
        charge_max = cycle.charge_moteur_max_durable
        charge_min = cycle.charge_moteur_min_efficiente
        if charge_max is None:
            vals = [s.charge_max_durable for s in sources if s.charge_max_durable is not None]
            charge_max = min(vals) if vals else None
        if charge_min is None:
            vals = [s.charge_min_efficiente for s in sources if s.charge_min_efficiente is not None]
            charge_min = max(vals) if vals else None
        max_charge_observed = None
        min_charge_observed = None
        charges: List[float] = []
        for row in therm.get("repartition", []) or []:
            ch = _sf(row.get("charge_par_moteur"))
            if ch is not None:
                charges.append(ch)
        if charges:
            max_charge_observed = max(charges)
            min_charge_observed = min(charges)
            if charge_max is not None and max_charge_observed > charge_max:
                ok = False; reasons.append("charge_moteur_durable_depassee")
            if charge_min is not None and min_charge_observed < charge_min:
                local_notes.append("sous_charge_efficiente_possible")

        # Remonte les inconnues du candidat seulement en synthèse locale pour ne pas polluer tout si candidat non retenu.
        cand = {
            "puissance_sortie_w": P_sortie,
            "repartition_moteurs": repart,
            "P_bus_dc_w": P_bus,
            "generation": gen,
            "thermique": therm,
            "debit_carburant_g_h": conso_g_h if has_conso else None,
            "bsfc_equivalent_g_kwh": bsfc_equiv,
            "charge_moteur_max_observee": max_charge_observed,
            "charge_moteur_min_observee": min_charge_observed,
            "ok": ok,
            "raisons_rejet": reasons,
            "notes": local_notes,
            "inconnues": rep_local.get("inconnues", {}),
        }
        bloc["candidats"].append(cand)

    ok_candidates = [c for c in bloc["candidats"] if c.get("ok") is True]
    if not ok_candidates:
        _push(rapport, "partielles", "cycle_croisiere.selection", "Aucun candidat ne respecte toutes les contraintes connues ; voir candidats et raisons_rejet.")
        return bloc

    # Pareto simple : puissance max et conso min si conso connue.
    pareto: List[Dict[str, Any]] = []
    for c in ok_candidates:
        dominated = False
        P_i = float(c["puissance_sortie_w"])
        F_i = _sf(c.get("debit_carburant_g_h"))
        for d in ok_candidates:
            if d is c:
                continue
            P_j = float(d["puissance_sortie_w"])
            F_j = _sf(d.get("debit_carburant_g_h"))
            if F_i is not None and F_j is not None:
                if (P_j >= P_i and F_j <= F_i) and (P_j > P_i or F_j < F_i):
                    dominated = True
                    break
        if not dominated:
            pareto.append({"puissance_sortie_w": P_i, "debit_carburant_g_h": F_i, "bsfc_equivalent_g_kwh": c.get("bsfc_equivalent_g_kwh")})
    bloc["pareto"] = pareto

    if cycle.strategie == "min_conso":
        with_fuel = [c for c in ok_candidates if _sf(c.get("debit_carburant_g_h")) is not None]
        selection = min(with_fuel, key=lambda c: float(c["debit_carburant_g_h"])) if with_fuel else max(ok_candidates, key=lambda c: float(c["puissance_sortie_w"]))
    elif cycle.strategie == "pareto":
        selection = max(ok_candidates, key=lambda c: float(c["puissance_sortie_w"]))
    else:
        selection = max(ok_candidates, key=lambda c: float(c["puissance_sortie_w"]))
    bloc["selection"] = selection
    return bloc


def analyser_batterie_tampon(
    batterie: BatterieTamponSpec,
    P_bus_max_w: Optional[float],
    P_bus_continue_w: Optional[float],
    P_source_recharge_w: Optional[float],
    exigence: ExigenceSortie,
    transmission: TransmissionGenerationSpec,
    rapport: Dict[str, Any],
) -> Dict[str, Any]:
    bloc: Dict[str, Any] = {"spec": _to_jsonable(batterie), "calculs_directs": {}, "checks": {}, "rapport_module_batterie": None}
    cap = batterie.capacite_nominale_kwh
    usable = cap * batterie.fenetre_soc if cap is not None else None
    bloc["calculs_directs"]["energie_utile_kwh"] = usable

    if P_bus_max_w is not None and P_bus_continue_w is not None and exigence.duree_pic_s is not None:
        surplus_kw = max(0.0, (P_bus_max_w - P_bus_continue_w) / 1000.0)
        e_peak = surplus_kw * (exigence.duree_pic_s / 3600.0)
        bloc["calculs_directs"]["energie_pic_requise_kwh"] = e_peak
        if usable is not None:
            bloc["checks"]["ok_energie_pic"] = usable >= e_peak
    elif exigence.duree_pic_s is not None:
        _push(rapport, "partielles", "batterie.energie_pic", "Calculable si P_bus_max_w et P_bus_continue_w sont connus.")

    if cap is not None and P_bus_continue_w is not None and batterie.c_rate_decharge_continue_max is not None:
        c_dis = (P_bus_continue_w / 1000.0) / cap if cap > 0 else float("inf")
        bloc["calculs_directs"]["c_rate_decharge_continue"] = c_dis
        bloc["checks"]["ok_c_rate_decharge_continue"] = c_dis <= batterie.c_rate_decharge_continue_max
    elif P_bus_continue_w is not None:
        _push(rapport, "partielles", "batterie.c_rate_decharge_continue", "Calculable si capacite_nominale_kwh et c_rate_decharge_continue_max sont fournis.")

    if cap is not None and P_bus_max_w is not None and batterie.c_rate_decharge_pic_max is not None:
        c_pic = (P_bus_max_w / 1000.0) / cap if cap > 0 else float("inf")
        bloc["calculs_directs"]["c_rate_decharge_pic"] = c_pic
        bloc["checks"]["ok_c_rate_decharge_pic"] = c_pic <= batterie.c_rate_decharge_pic_max
    elif P_bus_max_w is not None:
        _push(rapport, "partielles", "batterie.c_rate_decharge_pic", "Calculable si capacite_nominale_kwh et c_rate_decharge_pic_max sont fournis.")

    eta_charge = transmission.rendement_charge
    if cap is not None and P_source_recharge_w is not None and batterie.temps_recharge_max_h is not None:
        eta = eta_charge if eta_charge is not None else 1.0
        if eta_charge is None:
            _push(rapport, "partielles", "batterie.rendement_charge", "Rendement de charge absent : temps recharge calculé sur borne optimiste eta=1.")
        t_h = (usable if usable is not None else cap) / max(P_source_recharge_w / 1000.0 * eta, 1e-12)
        bloc["calculs_directs"]["temps_recharge_estime_h"] = t_h
        bloc["checks"]["ok_temps_recharge"] = t_h <= batterie.temps_recharge_max_h
    elif cap is not None:
        _push(rapport, "partielles", "batterie.temps_recharge", "Calculable si P_source_recharge_w et temps_recharge_max_h sont fournis.")

    if cap is not None and batterie.densite_energetique_kwh_kg is not None:
        masse = cap / batterie.densite_energetique_kwh_kg
        bloc["calculs_directs"]["masse_pack_estimee_kg"] = masse
        if batterie.masse_pack_max_kg is not None:
            bloc["checks"]["ok_masse_pack"] = masse <= batterie.masse_pack_max_kg
    elif cap is not None:
        _push(rapport, "partielles", "batterie.masse_pack", "Calculable si densite_energetique_kwh_kg est fournie.")

    # Appel du module batterie robuste s'il est disponible.
    if Batterie is not None:
        try:
            batt_obj = Batterie(
                fenetre_soc=batterie.fenetre_soc,
                densite_energetique_kwh_kg=batterie.densite_energetique_kwh_kg,
                rendement_charge=eta_charge if eta_charge is not None else 1.0,
                tension_nominale_v=batterie.tension_nominale_v,
                tension_charge_v=batterie.tension_charge_v,
            )
            kwargs = {
                "energie_utile_imposee_kwh": usable,
                "puissance_sortie_continue_kw": None if P_bus_continue_w is None else P_bus_continue_w / 1000.0,
                "puissance_sortie_moyenne_kw": None if P_bus_continue_w is None else P_bus_continue_w / 1000.0,
                "puissance_sortie_pic_kw": None if P_bus_max_w is None else P_bus_max_w / 1000.0,
                "puissance_recharge_source_kw": None if P_source_recharge_w is None else P_source_recharge_w / 1000.0,
                "temps_recharge_max_h": batterie.temps_recharge_max_h,
                "autonomie_elec_min_h": batterie.autonomie_elec_min_h,
                "energie_tampon_min_kwh": batterie.energie_tampon_min_kwh,
                "capacite_nominale_preferee_kwh": cap,
                "capacite_nominale_min_kwh": cap,
                "capacite_nominale_max_kwh": cap,
                "masse_pack_max_kg": batterie.masse_pack_max_kg,
                "c_rate_decharge_continue_max": batterie.c_rate_decharge_continue_max,
                "c_rate_decharge_pic_max": batterie.c_rate_decharge_pic_max,
                "c_rate_charge_max": batterie.c_rate_charge_max,
                "rendement_recharge_source": eta_charge if eta_charge is not None else 1.0,
            }
            bloc["rapport_module_batterie"] = batt_obj.analyser_dimensionnement(**kwargs)
        except Exception as exc:
            bloc["rapport_module_batterie"] = {"erreur": str(exc)}
    return bloc


def analyser_mobilite(config: Mapping[str, Any], rapport: Dict[str, Any]) -> Dict[str, Any]:
    """Analyse optionnelle des domaines véhicule/navire/avion/rail depuis les modules moteur électrique."""
    mob = _safe_dict(config.get("mobilite", config.get("vehicule")))
    if not mob:
        return {"actif": False}
    domaine = str(mob.get("domaine", "routier")).strip().lower()
    out: Dict[str, Any] = {"actif": True, "domaine": domaine, "resultats": {}}
    try:
        if domaine == "routier":
            if calcul_force_resistance_totale is None:
                _push(rapport, "impossibles", "mobilite.routier", "Module calcul_force_resistance_totale indisponible.")
                return out
            req = ["masse_kg", "vitesse_ms", "angle_pente", "coef_roulement", "coef_trainee_aero_cda", "densite_air"]
            missing = [k for k in req if k not in mob]
            if missing:
                _push(rapport, "partielles", "mobilite.routier", f"Paramètres manquants: {missing}")
                return out
            forces = calcul_force_resistance_totale(
                masse_kg=mob["masse_kg"],
                vitesse_ms=mob["vitesse_ms"],
                angle_pente=mob.get("angle_pente", 0.0),
                coef_roulement=mob["coef_roulement"],
                coef_trainee_aero_cda=mob["coef_trainee_aero_cda"],
                densite_air=mob["densite_air"],
                gravite=mob.get("gravite", G0),
                angle_unite=mob.get("angle_unite", "rad"),
                return_details=True,
            )
            out["resultats"]["forces"] = forces
            if "rayon_roue_m" in mob and calcul_puissance_roue is not None and calcul_couple_roue_total is not None:
                F_req = forces["F_totale"] + float(mob.get("masse_kg", 0.0)) * float(mob.get("acceleration_ms2", 0.0))
                out["resultats"]["puissance_roue_w"] = calcul_puissance_roue(F_req, mob["vitesse_ms"], use_abs_speed=True, clamp_non_negative=True)
                out["resultats"]["couple_roue_total_nm"] = calcul_couple_roue_total(F_req, mob["rayon_roue_m"], clamp_non_negative=True)
            if all(k in mob for k in ("mu_adherence", "hauteur_cg_m", "empattement_m", "lr_m", "lf_m", "type_milieu")) and calcul_charges_essieux is not None and calcul_acceleration_max is not None:
                charges = calcul_charges_essieux(
                    masse_kg=mob["masse_kg"], acceleration_ms2=0.0, angle_pente=mob.get("angle_pente", 0.0),
                    empattement_l_m=mob["empattement_m"], dist_cg_arriere_lr_m=mob["lr_m"], dist_cg_avant_lf_m=mob["lf_m"],
                    hauteur_cg_h_m=mob["hauteur_cg_m"], angle_unite=mob.get("angle_unite", "rad"), return_details=True,
                )
                mode = str(mob["type_milieu"]).lower()
                if mode in ("traction", "fwd", "avant", "front"):
                    Ndrive = charges["N_avant"]; mode_calc = "FWD"
                elif mode in ("propulsion", "propultion", "rwd", "arriere", "arrière", "rear"):
                    Ndrive = charges["N_arriere"]; mode_calc = "RWD"
                else:
                    Ndrive = charges["N_avant"] + charges["N_arriere"]; mode_calc = "AWD"
                out["resultats"]["charges_essieux"] = charges
                out["resultats"]["acceleration_max_adherence_ms2"] = calcul_acceleration_max(
                    mu_adherence=mob["mu_adherence"], charge_essieu_moteur_n=Ndrive, force_resistance_n=forces["F_totale"],
                    masse_kg=mob["masse_kg"], hauteur_cg_m=mob["hauteur_cg_m"], empattement_m=mob["empattement_m"],
                    type_milieu=mode_calc, include_transfert=True, clamp_non_negative=True,
                )
        elif domaine == "nautique" and calcul_demande_nautique is not None:
            out["resultats"] = calcul_demande_nautique(**{k: v for k, v in mob.items() if k != "domaine"})
        elif domaine == "aerien" and calcul_demande_aerien_rho is not None:
            data = dict(mob)
            data.pop("domaine", None)
            if "rho_air_kg_m3" not in data and "pression_pa" in data and "temperature_c" in data and calcul_densite_air_sec is not None:
                data["rho_air_kg_m3"] = calcul_densite_air_sec(data.pop("pression_pa"), data.pop("temperature_c"))
            out["resultats"] = calcul_demande_aerien_rho(**data)
        elif domaine == "ferroviaire" and calcul_demande_ferroviaire_davis is not None:
            out["resultats"] = calcul_demande_ferroviaire_davis(**{k: v for k, v in mob.items() if k != "domaine"})
        else:
            _push(rapport, "partielles", "mobilite.domaine", f"Domaine {domaine!r} non calculé : module absent ou domaine non supporté.")
    except Exception as exc:
        _push(rapport, "partielles", "mobilite", str(exc))
    return out


def analyser_alternateur_boite_modules(
    config: Mapping[str, Any],
    transmission: TransmissionGenerationSpec,
    sources: Sequence[MoteurThermiqueSource],
    P_bus_design_w: Optional[float],
    V_bus_v: Optional[float],
    rapport: Dict[str, Any],
) -> Dict[str, Any]:
    """Appelle, si possible, les modules alternateur et boîte déjà renforcés."""
    bloc: Dict[str, Any] = {"alternateur": None, "boite_crabots": None, "chaine": None}
    if P_bus_design_w is None:
        return bloc

    alt_cfg = _safe_dict(config.get("alternateur"))
    boite_cfg = _safe_dict(config.get("boite_crabots"))
    alt_obj = None
    if Alternateur is not None:
        try:
            if construire_alternateur is not None:
                alt_obj = construire_alternateur(alt_cfg)
            else:
                alt_obj = Alternateur(**alt_cfg)
            rpm_alt = _sf(alt_cfg.get("vitesse_rotation_rpm", alt_cfg.get("rpm_alternateur", transmission.rpm_alternateur_cible)))
            bloc["alternateur"] = alt_obj.analyser_pour_bus_dc(
                puissance_bus_dc_w=P_bus_design_w,
                vitesse_rotation_rpm=rpm_alt,
                tension_bus_dc_v=V_bus_v,
            )
            _merge_inconnues(rapport, bloc["alternateur"], prefix="alternateur")
        except Exception as exc:
            bloc["alternateur"] = {"erreur": str(exc)}
            _push(rapport, "partielles", "alternateur.module", str(exc))

    if BoiteCrabots is not None:
        try:
            if construire_boite_crabots is not None:
                boite_obj = construire_boite_crabots(boite_cfg)
            else:
                boite_obj = BoiteCrabots(**boite_cfg)
            rpm_moteur = None
            for s in sources:
                if s.rpm_optimal is not None:
                    rpm_moteur = s.rpm_optimal
                    break
            rapports = list(transmission.rapports_boite or boite_cfg.get("rapports", []) or []) or None
            if alt_obj is not None and rpm_moteur is not None:
                bloc["chaine"] = boite_obj.analyser_chaine_moteur_alternateur(
                    alternateur=alt_obj,
                    puissance_bus_dc_w=P_bus_design_w,
                    rpm_moteur=rpm_moteur,
                    rapports=rapports,
                    rendement_boite=transmission.rendement_boite,
                    tension_bus_dc_v=V_bus_v,
                    rpm_alternateur_cible=transmission.rpm_alternateur_cible,
                    rpm_alternateur_min_optimal=transmission.rpm_alternateur_min_optimal,
                    rpm_alternateur_max_optimal=transmission.rpm_alternateur_max_optimal,
                    rapport_min=transmission.rapport_min,
                    rapport_max=transmission.rapport_max,
                )
                _merge_inconnues(rapport, bloc["chaine"], prefix="boite_chaine")
            else:
                _push(rapport, "partielles", "boite_crabots.chaine", "Chaîne calculable si alternateur instancié et rpm_optimal moteur thermique connu.")
        except Exception as exc:
            bloc["boite_crabots"] = {"erreur": str(exc)}
            _push(rapport, "partielles", "boite_crabots.module", str(exc))
    return bloc


# =============================================================================
# API haut niveau
# =============================================================================

def concevoir_systeme_hybride_final(config: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Point d'entrée principal.

    Exemple minimal :
        rapport = concevoir_systeme_hybride_final({
            "sortie": {"puissance_sortie_max_w": 100_000},
            "moteurs_sortie": [{"nom": "traction", "quantite": 1,
                                 "puissance_max_w": 100_000,
                                 "rendement_moteur": 0.94}],
            "moteur_thermique": {"puissance_arbre_max_w": 140_000,
                                  "rpm_optimal": 2800,
                                  "bsfc_g_kwh": 230},
            "transmission_generation": {"rendement_boite": 0.94,
                                          "rendement_alternateur": 0.92,
                                          "rendement_redressement": 0.96},
        })
    """
    rapport: Dict[str, Any] = {
        "composant": "systeme_hybride_final",
        "role": {
            "sortie_utilisateur": "puissance utile réellement disponible pour la traction/propulsion/charge mécanique",
            "bus_dc": "sortie utile corrigée par les rendements moteurs + auxiliaires + pertes",
            "batterie": "tampon énergétique et puissance, pas correcteur magique d'une génération sous-dimensionnée",
            "boite_crabots": "maintien du moteur thermique en cycle optimal et adaptation du régime alternateur",
            "moteur_thermique": "source primaire efficiente, durable, capable de soutenir pleine puissance ou croisière selon scénario",
        },
        "entrees_normalisees": {},
        "sous_systemes": {},
        "liaisons": {},
        "cycle_croisiere": {},
        "synthese": {},
        "inconnues": {"impossibles": [], "partielles": []},
        "notes_modele": [],
        "imports": {"erreurs_optionnelles": dict(_IMPORT_ERRORS)},
    }

    try:
        sortie_payload = config.get("sortie", config)
        exigence = _build_dataclass(ExigenceSortie, sortie_payload)
        moteurs = normaliser_moteurs_sortie(config)
        auxiliaires = normaliser_auxiliaires(config)
        sources = normaliser_sources_thermiques(config)
        batterie = _build_dataclass(BatterieTamponSpec, config.get("batterie", config.get("batterie_tampon", {})))
        transmission = _build_dataclass(TransmissionGenerationSpec, config.get("transmission_generation", config.get("generation", {})))
        cycle = _build_dataclass(CycleCroisiereSpec, config.get("cycle_croisiere", {}))
    except Exception as exc:
        _push(rapport, "impossibles", "normalisation_config", str(exc))
        _dedup(rapport)
        return _to_jsonable(rapport)

    rapport["entrees_normalisees"] = {
        "exigence_sortie": _to_jsonable(exigence),
        "moteurs_sortie": [_to_jsonable(m) for m in moteurs],
        "auxiliaires": [_to_jsonable(a) for a in auxiliaires],
        "moteurs_thermiques": [_to_jsonable(s) for s in sources],
        "batterie": _to_jsonable(batterie),
        "transmission_generation": _to_jsonable(transmission),
        "cycle_croisiere": _to_jsonable(cycle),
    }

    # 1) Sortie utile + bus DC
    sortie_bloc = calculer_sortie_et_bus(moteurs, auxiliaires, exigence, rapport)
    rapport["sous_systemes"]["sortie_et_bus_dc"] = sortie_bloc
    P_bus_max = _sf(_get_path(sortie_bloc, "puissances", "P_bus_dc_sortie_max_total_w"))
    P_bus_cont = _sf(_get_path(sortie_bloc, "puissances", "P_bus_dc_continue_total_w"))

    # 2) Génération nécessaire à pleine sortie
    gen_full = calculer_generation_depuis_bus(P_bus_max, transmission, rapport, contexte="pleine_sortie")
    rapport["liaisons"]["generation_pleine_sortie"] = gen_full
    P_therm_full = _sf(_get_path(gen_full, "resultats", "P_arbre_thermique_requise_w"))
    therm_full = evaluer_sources_thermiques(sources, P_therm_full, rapport, contexte="pleine_sortie")
    rapport["sous_systemes"]["moteurs_thermiques_pleine_sortie"] = therm_full

    # 2.5) Architecture moteur thermique : proposition optimale + classement complet.
    # Le moteur thermique n'est plus seulement une source de puissance ; il reçoit
    # une architecture calculée par architecture.py selon puissance/régime/PME/gabarit.
    rapport["sous_systemes"]["architecture_moteur_thermique"] = analyser_architecture_moteur_thermique(
        config=config,
        sources=sources,
        P_arbre_thermique_requise_w=P_therm_full,
        rapport=rapport,
    )

    # 3) Cycle croisière : recherche du plus puissant possible sous contraintes connues.
    rapport["cycle_croisiere"] = analyser_cycle_croisiere(
        moteurs=moteurs,
        auxiliaires=auxiliaires,
        sources=sources,
        exigence=exigence,
        transmission=transmission,
        cycle=cycle,
        rapport=rapport,
    )
    selection_croisiere = rapport["cycle_croisiere"].get("selection") if isinstance(rapport.get("cycle_croisiere"), Mapping) else None
    P_bus_croisiere = _sf(_get_path(selection_croisiere, "P_bus_dc_w")) if isinstance(selection_croisiere, Mapping) else P_bus_cont
    gen_croisiere = _get_path(selection_croisiere, "generation", "resultats") if isinstance(selection_croisiere, Mapping) else None
    P_source_recharge_w = _sf(_get_path(gen_full, "resultats", "P_bus_dc_total_w"))

    # 4) Batterie tampon
    batterie_bloc = analyser_batterie_tampon(
        batterie=batterie,
        P_bus_max_w=P_bus_max,
        P_bus_continue_w=P_bus_croisiere if P_bus_croisiere is not None else P_bus_cont,
        P_source_recharge_w=P_source_recharge_w,
        exigence=exigence,
        transmission=transmission,
        rapport=rapport,
    )
    rapport["sous_systemes"]["batterie_tampon"] = batterie_bloc
    _merge_inconnues(rapport, batterie_bloc.get("rapport_module_batterie"), prefix="batterie_module")

    # 5) Mobilité optionnelle : routier/nautique/aérien/ferroviaire.
    rapport["sous_systemes"]["mobilite"] = analyser_mobilite(config, rapport)

    # 6) Appel des modules alternateur/boîte renforcés si possible.
    Vbus = batterie.tension_nominale_v or batterie.tension_charge_v
    if Vbus is None:
        # récupérer depuis moteurs si homogène
        tensions = [m.tension_bus_v for m in moteurs if m.tension_bus_v is not None]
        if tensions:
            Vbus = tensions[0]
    if Vbus is None:
        _push(rapport, "partielles", "tension_bus_dc_v", "Requise pour analyser précisément alternateur et courant bus.")
    rapport["sous_systemes"]["alternateur_boite_modules"] = analyser_alternateur_boite_modules(config, transmission, sources, P_bus_max, Vbus, rapport)

    # 7) Synthèse finale lisible.
    sortie_checks = _safe_dict(sortie_bloc.get("checks"))
    gen_full_res = _safe_dict(gen_full.get("resultats"))
    croisiere_sel = selection_croisiere if isinstance(selection_croisiere, Mapping) else {}
    rapport["synthese"] = {
        "puissance_sortie_max_demandee_kw": exigence.puissance_sortie_max_w / 1000.0,
        "puissance_sortie_installee_max_kw": None if sortie_checks.get("puissance_installee_sortie_max_w") is None else sortie_checks["puissance_installee_sortie_max_w"] / 1000.0,
        "ok_moteurs_sortie_pleine_puissance": sortie_checks.get("ok_sortie_max"),
        "P_bus_dc_pleine_sortie_kw": None if P_bus_max is None else P_bus_max / 1000.0,
        "P_bus_dc_min_theorique_kw": _get_path(sortie_bloc, "puissances", "P_bus_dc_min_theorique_sortie_max_w") / 1000.0 if _sf(_get_path(sortie_bloc, "puissances", "P_bus_dc_min_theorique_sortie_max_w")) is not None else None,
        "P_arbre_thermique_requise_pleine_sortie_kw": None if gen_full_res.get("P_arbre_thermique_requise_w") is None else gen_full_res["P_arbre_thermique_requise_w"] / 1000.0,
        "ok_thermique_pleine_puissance": _get_path(therm_full, "checks", "ok_puissance_max"),
        "architecture_thermique_optimale": _get_path(rapport, "sous_systemes", "architecture_moteur_thermique", "meilleur_choix", "architecture"),
        "architecture_thermique_optimale_N_cyl": _get_path(rapport, "sous_systemes", "architecture_moteur_thermique", "meilleur_choix", "N_cyl"),
        "architecture_thermique_optimale_score": _get_path(rapport, "sous_systemes", "architecture_moteur_thermique", "meilleur_choix", "score_global"),
        "architecture_thermique_optimale_efficacite_relative_100": _get_path(rapport, "sous_systemes", "architecture_moteur_thermique", "meilleur_choix", "efficacite_relative_100"),
        "classement_architectures_par_efficacite": _get_path(rapport, "sous_systemes", "architecture_moteur_thermique", "classement_par_efficacite"),
        "meilleurs_candidats_par_architecture": _get_path(rapport, "sous_systemes", "architecture_moteur_thermique", "meilleurs_par_architecture"),
        "puissance_croisiere_selectionnee_kw": None if not croisiere_sel else croisiere_sel.get("puissance_sortie_w", 0.0) / 1000.0,
        "P_bus_dc_croisiere_kw": None if _sf(croisiere_sel.get("P_bus_dc_w")) is None else croisiere_sel["P_bus_dc_w"] / 1000.0,
        "debit_carburant_croisiere_g_h": None if not croisiere_sel else croisiere_sel.get("debit_carburant_g_h"),
        "bsfc_croisiere_g_kwh": None if not croisiere_sel else croisiere_sel.get("bsfc_equivalent_g_kwh"),
        "batterie_energie_utile_kwh": _get_path(batterie_bloc, "calculs_directs", "energie_utile_kwh"),
        "batterie_ok_c_rate_pic": _get_path(batterie_bloc, "checks", "ok_c_rate_decharge_pic"),
        "batterie_ok_temps_recharge": _get_path(batterie_bloc, "checks", "ok_temps_recharge"),
        "inconnues_impossibles_count": len(rapport.get("inconnues", {}).get("impossibles", [])),
        "inconnues_partielles_count": len(rapport.get("inconnues", {}).get("partielles", [])),
    }

    # Verdicts systèmes.
    verdicts: Dict[str, Any] = {}
    verdicts["sortie_utile"] = "OK" if sortie_checks.get("ok_sortie_max") is True else "NON_VERIFIE_OU_INSUFFISANT"
    verdicts["generation_pleine_sortie"] = "OK" if _get_path(therm_full, "checks", "ok_puissance_max") is True else "NON_VERIFIE_OU_INSUFFISANT"
    arch_best = _get_path(rapport, "sous_systemes", "architecture_moteur_thermique", "meilleur_choix")
    verdicts["architecture_thermique"] = "OK" if isinstance(arch_best, Mapping) and arch_best.get("architecture") else "NON_CALCULEE_OU_INSUFFISANTE"
    verdicts["cycle_croisiere"] = "OK" if rapport["cycle_croisiere"].get("selection") else "NON_SELECTIONNE"
    bad_batt = [k for k, v in _safe_dict(batterie_bloc.get("checks")).items() if v is False]
    verdicts["batterie_tampon"] = "OK" if not bad_batt else f"A_CORRIGER:{','.join(bad_batt)}"
    rapport["synthese"]["verdicts"] = verdicts

    _dedup(rapport)
    return _to_jsonable(rapport)


def exporter_rapport_json(rapport: Mapping[str, Any], chemin: str | os.PathLike[str]) -> Path:
    path = Path(chemin)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_jsonable(dict(rapport)), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


__all__ = [
    "MoteurElectrique",
    "MoteurSortie",
    "ChargeAuxiliaire",
    "MoteurThermiqueSource",
    "ExigenceSortie",
    "BatterieTamponSpec",
    "TransmissionGenerationSpec",
    "CycleCroisiereSpec",
    "analyser_architecture_moteur_thermique",
    "concevoir_systeme_hybride_final",
    "exporter_rapport_json",
]


if __name__ == "__main__":
    # Démonstration contrôlée : toutes les valeurs ci-dessous sont des entrées explicites
    # de test, pas des valeurs par défaut de conception.
    demo = {
        "sortie": {
            "puissance_sortie_max_w": 100_000.0,
            "puissance_sortie_continue_w": 55_000.0,
            "marge_puissance": 0.05,
            "duree_pic_s": 30.0,
        },
        "moteurs_sortie": [
            {
                "nom": "moteur_traction_principal",
                "quantite": 1,
                "puissance_max_w": 110_000.0,
                "puissance_continue_w": 60_000.0,
                "rendement_moteur": 0.94,
                "rendement_transmission": 0.97,
                "tension_bus_v": 400.0,
            }
        ],
        "auxiliaires": [
            {"nom": "pompes_refroidissement", "puissance_continue_w": 900.0, "puissance_pic_w": 1200.0},
            {"nom": "electronique_controle", "puissance_continue_w": 450.0},
        ],
        "moteur_thermique": {
            "nom": "stho_me_1",
            "quantite": 1,
            "puissance_arbre_max_w": 145_000.0,
            "puissance_arbre_continue_w": 95_000.0,
            "rpm_optimal": 2800.0,
            "rpm_min_optimal": 2600.0,
            "rpm_max_optimal": 3000.0,
            "charge_min_efficiente": 0.35,
            "charge_max_durable": 0.75,
            "bsfc_map": [
                {"charge": 0.30, "bsfc_g_kwh": 275.0},
                {"charge": 0.45, "bsfc_g_kwh": 238.0},
                {"charge": 0.60, "bsfc_g_kwh": 225.0},
                {"charge": 0.75, "bsfc_g_kwh": 232.0},
                {"charge": 1.00, "bsfc_g_kwh": 260.0},
            ],
        },
        "transmission_generation": {
            "rendement_boite": 0.94,
            "rendement_alternateur": 0.92,
            "rendement_redressement": 0.96,
            "rendement_charge": 0.90,
            "rpm_alternateur_cible": 9000.0,
            "rpm_alternateur_min_optimal": 7500.0,
            "rpm_alternateur_max_optimal": 10500.0,
            "rapports_boite": [2.5, 3.0, 3.2, 3.5, 4.0],
        },
        "batterie": {
            "capacite_nominale_kwh": 18.0,
            "fenetre_soc": 0.80,
            "tension_nominale_v": 400.0,
            "densite_energetique_kwh_kg": 0.18,
            "c_rate_decharge_continue_max": 3.0,
            "c_rate_decharge_pic_max": 8.0,
            "c_rate_charge_max": 2.0,
            "temps_recharge_max_h": 1.0,
            "masse_pack_max_kg": 150.0,
        },
        "cycle_croisiere": {
            "strategie": "max_puissance_sous_contraintes",
            "fractions_puissance": [0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85],
            "charge_moteur_max_durable": 0.75,
            "charge_moteur_min_efficiente": 0.35,
            "puissance_recharge_batterie_croisiere_w": 5_000.0,
        },
        "alternateur": {
            "nombre_poles": 8,
            "connexion": "Y",
            "rendement_alternateur_impose": 0.92,
            "interface_bus_dc": {"tension_bus_dc_v": 400.0},
            "plage_regime": {"rpm_cible": 9000.0, "rpm_min_optimal": 7500.0, "rpm_max_optimal": 10500.0},
        },
        "boite_crabots": {
            "rpm_moteur_optimal": 2800.0,
            "rpm_alternateur_cible": 9000.0,
            "rpm_alternateur_min_optimal": 7500.0,
            "rpm_alternateur_max_optimal": 10500.0,
            "rendement_boite_defaut": 0.94,
        },
    }
    r = concevoir_systeme_hybride_final(demo)
    print(json.dumps(r["synthese"], ensure_ascii=False, indent=2))
