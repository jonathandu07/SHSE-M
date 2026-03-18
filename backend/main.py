# backend/main.py
from __future__ import annotations

import inspect
import json
import math
import os
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


# =============================================================================
# Préparation du chemin projet
# =============================================================================

_THIS_FILE = Path(__file__).resolve()
_THIS_DIR = _THIS_FILE.parent

for candidate in (
    _THIS_DIR,
    _THIS_DIR.parent,
    _THIS_DIR.parent.parent,
    Path.cwd(),
):
    sc = str(candidate)
    if sc not in sys.path:
        sys.path.append(sc)


# =============================================================================
# Imports robustes
# =============================================================================

_MISSING = object()


def _import_attr(module_names: Sequence[str], attr: str, default: Any = _MISSING) -> Any:
    last_error: Optional[Exception] = None
    for module_name in module_names:
        try:
            module = __import__(module_name, fromlist=[attr])
            return getattr(module, attr)
        except Exception as exc:
            last_error = exc
            continue
    if default is not _MISSING:
        return default
    if last_error is None:
        raise ImportError(f"Impossible d'importer {attr}.")
    raise ImportError(f"Impossible d'importer {attr}: {last_error}") from last_error


# Orchestrateurs
SystemeComplet = _import_attr(("backend.ensemble.systeme_complet", "systeme_complet"), "SystemeComplet", default=None)
OptimisationSysteme = _import_attr(("backend.ensemble.optimisation", "optimisation"), "OptimisationSysteme", default=None)
STHO_ME = _import_attr(("backend.ensemble.STHO_ME", "STHO_ME"), "STHO_ME", default=None)

# Composants
MoteurElectrique = _import_attr(("backend.components.moteur_electrique", "moteur_electrique"), "MoteurElectrique", default=None)
Batterie = _import_attr(("backend.components.batterie", "batterie"), "Batterie", default=None)
Alternateur = _import_attr(("backend.components.alternateur", "alternateur"), "Alternateur", default=None)
MoteurThermique = _import_attr(("backend.components.moteur_thermique", "moteur_thermique"), "MoteurThermique", default=None)
BoiteCrabots = _import_attr(("backend.components.boite_crabots", "boite_crabots"), "BoiteCrabots", default=None)
Architecture = _import_attr(("backend.components.architecture", "architecture"), "Architecture", default=None)

# Pièces
Cylindre = _import_attr(("backend.pieces.cylindre", "cylindre"), "Cylindre", default=None)
Piston = _import_attr(("backend.pieces.piston", "piston"), "Piston", default=None)
JointPiston = _import_attr(("backend.pieces.joint_piston", "joint_piston"), "JointPiston", default=None)
CorpsBielle = _import_attr(("backend.pieces.bielle", "bielle"), "CorpsBielle", default=None)
ArbrePiston = _import_attr(("backend.pieces.arbre_piston", "arbre_piston"), "ArbrePiston", default=None)
CoussinetArbrePiston = _import_attr(
    ("backend.pieces.coussinet_arbre_piston", "coussinet_arbre_piston"),
    "CoussinetArbrePiston",
    default=None,
)
ArbreVilbrequin = _import_attr(("backend.pieces.arbre_vilbrequin", "arbre_vilbrequin"), "ArbreVilbrequin", default=None)
Vilbrequin = _import_attr(("backend.pieces.vilbrequin", "vilbrequin"), "Vilbrequin", default=None)
RoulementAiguilleArbre = _import_attr(
    ("backend.pieces.roulement_aiguille_arbre", "roulement_aiguille_arbre"),
    "RoulementAiguilleArbre",
    default=None,
)
RoulementAiguilleArbreVilebrequin = _import_attr(
    ("backend.pieces.roulement_aiguille_arbre_vilebrequin", "roulement_aiguille_arbre_vilebrequin"),
    "RoulementAiguilleArbreVilebrequin",
    default=None,
)
CouvercleCylindre = _import_attr(("backend.pieces.couvercle_cylindre", "couvercle_cylindre"), "CouvercleCylindre", default=None)
VisCouvercleCylindre = _import_attr(
    ("backend.pieces.vis_couvercle_cylindre", "vis_couvercle_cylindre"),
    "VisCouvercleCylindre",
    default=None,
)
Deplaceur = _import_attr(("backend.pieces.deplaceur", "deplaceur"), "Deplaceur", default=None)
JointDeplaceur = _import_attr(("backend.pieces.joint_deplaceur", "joint_deplaceur"), "JointDeplaceur", default=None)
ArbreMoteur = _import_attr(("backend.pieces.arbre", "arbre"), "ArbreMoteur", default=None)
if ArbreMoteur is None:
    ArbreMoteur = _import_attr(("backend.pieces.arbre", "arbre"), "Arbre", default=None)
ClavetteArbre = _import_attr(("backend.pieces.clavette_arbre", "clavette_arbre"), "ClavetteArbre", default=None)

# Héritage ancien pipeline
try:
    from backend.definition_pieces import dimensionner_pieces_completes  # type: ignore
except Exception:
    dimensionner_pieces_completes = None  # type: ignore

try:
    from backend.system_generator import DriveChainGenerator  # type: ignore
except Exception:
    DriveChainGenerator = None  # type: ignore


# =============================================================================
# Helpers généraux
# =============================================================================


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    if strict and v <= 0.0:
        raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    if (not strict) and v < 0.0:
        raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _safe_float(x: Any) -> Optional[float]:
    return float(x) if _is_finite(x) else None


def _safe_int(x: Any) -> Optional[int]:
    if isinstance(x, int) and not isinstance(x, bool):
        return int(x)
    if _is_finite(x):
        xf = float(x)
        if abs(xf - round(xf)) < 1e-12:
            return int(round(xf))
    return None


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _safe_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _first_non_none(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def _first_finite(*vals: Any) -> Optional[float]:
    for v in vals:
        if _is_finite(v):
            return float(v)
    return None


def _get_nested(d: Any, *path: str) -> Any:
    cur = d
    for key in path:
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
        if cur is None:
            return None
    return cur


def _merge_dict_non_none(base: Optional[Dict[str, Any]], extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(base or {})
    for k, v in (extra or {}).items():
        if v is None:
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dict_non_none(_safe_dict(out.get(k)), v)
        else:
            out[k] = v
    return out


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append(
        {"nom": str(nom), "raison": str(raison)}
    )


def _push_warning(rapport: Dict[str, Any], categorie: str, nom: str, detail: str) -> None:
    rapport.setdefault("alertes", {}).setdefault(categorie, []).append(
        {"nom": str(nom), "detail": str(detail)}
    )


def _append_note(rapport: Dict[str, Any], note: str) -> None:
    rapport.setdefault("notes_modele", []).append(str(note))


def _dedup_report_lists(rapport: Dict[str, Any]) -> None:
    for section, keyset in (("inconnues", ("nom", "raison")), ("alertes", ("nom", "detail"))):
        bloc = _safe_dict(rapport.get(section))
        new_bloc: Dict[str, Any] = {}
        for category, values in bloc.items():
            seen = set()
            kept = []
            for item in list(values or []):
                if not isinstance(item, dict):
                    continue
                sig = tuple(str(item.get(k, "")) for k in keyset)
                if sig in seen:
                    continue
                seen.add(sig)
                kept.append(item)
            new_bloc[category] = kept
        rapport[section] = new_bloc
    if "notes_modele" in rapport:
        notes_seen = set()
        deduped = []
        for note in list(rapport.get("notes_modele") or []):
            s = str(note)
            if s not in notes_seen:
                notes_seen.add(s)
                deduped.append(s)
        rapport["notes_modele"] = deduped


# =============================================================================
# Sérialisation / introspection exhaustive
# =============================================================================


def _to_jsonable(value: Any, *, depth: int = 0, max_depth: int = 5) -> Any:
    if depth > max_depth:
        return {"type": type(value).__name__}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v, depth=depth + 1, max_depth=max_depth) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v, depth=depth + 1, max_depth=max_depth) for v in value]
    if is_dataclass(value):
        try:
            return _to_jsonable(asdict(value), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "en_dict") and callable(getattr(value, "en_dict")):
        try:
            return _to_jsonable(value.en_dict(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            raw = {
                k: v for k, v in vars(value).items()
                if not k.startswith("_") and not callable(v)
            }
            return {
                "type": type(value).__name__,
                "module": getattr(type(value), "__module__", None),
                "attributs": _to_jsonable(raw, depth=depth + 1, max_depth=max_depth),
            }
        except Exception:
            pass
    return {"type": type(value).__name__}


def _extract_public_attrs(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    try:
        return {
            k: v for k, v in vars(obj).items()
            if not k.startswith("_") and not callable(v)
        }
    except Exception:
        return {}


def _extract_properties(obj: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if obj is None:
        return out
    try:
        cls = type(obj)
        for name, member in vars(cls).items():
            if name.startswith("_"):
                continue
            if isinstance(member, property):
                try:
                    out[name] = getattr(obj, name)
                except Exception as exc:
                    out[name] = {"erreur": str(exc)}
    except Exception:
        pass
    return out


def _extract_dataclass_fields(obj: Any) -> Dict[str, Any]:
    if obj is None or not is_dataclass(obj):
        return {}
    try:
        return {k: getattr(obj, k) for k in getattr(obj, "__dataclass_fields__", {}).keys()}
    except Exception:
        return {}


def _callable_accepts_varkw(callable_obj: Any) -> bool:
    try:
        sig = inspect.signature(callable_obj)
    except Exception:
        return True
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())


def _filter_kwargs_for_callable(callable_obj: Any, kwargs: Mapping[str, Any]) -> Dict[str, Any]:
    clean = {k: v for k, v in dict(kwargs).items() if v is not None}
    if _callable_accepts_varkw(callable_obj):
        return clean
    try:
        sig = inspect.signature(callable_obj)
    except Exception:
        return clean
    accepted = set(sig.parameters.keys())
    return {k: v for k, v in clean.items() if k in accepted}


def _safe_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    for name in ("analyser", "calculer"):
        fn = getattr(obj, name, None)
        if callable(fn):
            try:
                out = fn(strict=False)
                if isinstance(out, dict):
                    return out
            except TypeError:
                try:
                    out = fn()
                    if isinstance(out, dict):
                        return out
                except Exception:
                    pass
            except Exception:
                pass
    return None


def _safe_run_method(obj: Any, method_name: str, kwargs: Mapping[str, Any]) -> Dict[str, Any]:
    if obj is None:
        return {"note": "Objet absent."}
    fn = getattr(obj, method_name, None)
    if not callable(fn):
        return {"note": f"Méthode {method_name} absente."}
    call_kwargs = _filter_kwargs_for_callable(fn, kwargs)
    try:
        out = fn(**call_kwargs)
        return out if isinstance(out, dict) else {"resultat": _to_jsonable(out)}
    except Exception as exc:
        return {"erreur": str(exc), "kwargs": _to_jsonable(call_kwargs)}


def _build_common_analysis_context(
    *,
    systeme_obj: Any,
    rapport_systeme: Mapping[str, Any],
    definition_moteur: Mapping[str, Any],
    composants: Mapping[str, Any],
    pieces: Mapping[str, Any],
    analyses_complementaires: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    synth = _safe_dict(rapport_systeme.get("synthese"))
    mt_syn = _safe_dict(synth.get("moteur_thermique"))
    veh_syn = _safe_dict(synth.get("vehicule"))
    batt_syn = _safe_dict(synth.get("batterie"))
    alt_syn = _safe_dict(synth.get("alternateur"))
    ctx = {
        "systeme_complet": systeme_obj,
        "moteur": composants.get("moteur_electrique"),
        "moteur_electrique": composants.get("moteur_electrique"),
        "batterie": composants.get("batterie"),
        "alternateur": composants.get("alternateur"),
        "moteur_thermique": composants.get("moteur_thermique"),
        "architecture": composants.get("architecture"),
        "boite": composants.get("boite_crabots"),
        "boite_crabots": composants.get("boite_crabots"),
        "piston": pieces.get("piston"),
        "cylindre": pieces.get("cylindre"),
        "bielle": pieces.get("bielle"),
        "arbre_piston": pieces.get("arbre_piston"),
        "couvercle": pieces.get("couvercle_cylindre"),
        "deplaceur": pieces.get("deplaceur"),
        "joint_deplaceur": pieces.get("joint_deplaceur"),
        "vilbrequin": pieces.get("vilbrequin"),
        "arbre_vilebrequin": pieces.get("arbre_vilebrequin"),
        "pression_pa": _safe_float(definition_moteur.get("pression_max_pa")),
        "pression_max_pa": _safe_float(definition_moteur.get("pression_max_pa")),
        "pression_moyenne_effective_pa": _first_finite(mt_syn.get("pme_pa"), definition_moteur.get("pme_pa")),
        "taux_compression": _safe_float(definition_moteur.get("taux_compression_nominal")),
        "volume_mort_m3": _safe_float(definition_moteur.get("volume_mort_nominal_m3")),
        "rpm": _first_finite(mt_syn.get("rpm_nominal"), definition_moteur.get("rpm_nominal")),
        "vitesse_rotation_rpm": _first_finite(mt_syn.get("rpm_nominal"), alt_syn.get("vitesse_rotation_rpm")),
        "vitesse_rotation_tr_min": _first_finite(mt_syn.get("rpm_nominal"), alt_syn.get("vitesse_rotation_rpm")),
        "puissance_bus_dc_w": _first_finite(veh_syn.get("puissance_bus_dc_design_w"), alt_syn.get("P_electrique_sortie_W")),
        "puissance_electrique_cible_w": _first_finite(alt_syn.get("P_electrique_sortie_W"), veh_syn.get("puissance_bus_dc_design_w")),
        "tension_bus_dc_v": _first_finite(veh_syn.get("tension_bus_dc_v"), batt_syn.get("tension_nominale_v")),
        "tension_v": _first_finite(veh_syn.get("tension_bus_dc_v"), batt_syn.get("tension_nominale_v")),
        "couple_nm": _first_finite(mt_syn.get("couple_requis_Nm"), mt_syn.get("couple_max_Nm"), definition_moteur.get("couple_requis_Nm"), definition_moteur.get("couple_max_Nm")),
        "carburant": definition_moteur.get("carburant"),
        "puissance_utile_w": _first_finite(mt_syn.get("puissance_requise_W"), definition_moteur.get("puissance_requise_W"), definition_moteur.get("puissance_nominale_visee_w")),
        "rendement_global": _safe_float(definition_moteur.get("rendement_global")),
        "rapport_piston": _safe_dict(_safe_dict(analyses_complementaires).get("moteur_thermique_geometrie")).get("rapport_piston"),
        "rapports": _safe_list(_safe_dict(rapport_systeme.get("entrees")).get("rapports_boite_candidates")) or [1.0, 1.5, 2.0, 2.5, 3.0],
    }
    return ctx


def _discover_analysis_methods(obj: Any) -> List[str]:
    if obj is None:
        return []
    names: List[str] = []
    for name in dir(obj):
        if name.startswith("_"):
            continue
        low = name.lower()
        if low in {"analyser", "calculer", "optimiser"}:
            names.append(name)
            continue
        if low.startswith("analyser_") or low.startswith("calculer_") or low.startswith("verifie"):
            names.append(name)
    return sorted(set(names))


def _run_discovered_methods(obj: Any, context: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name in _discover_analysis_methods(obj):
        out[name] = _safe_run_method(obj, name, context)
    return out


def _decrire_objet(obj: Any, context: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    ctx = dict(context or {})
    return {
        "type": None if obj is None else type(obj).__name__,
        "module": None if obj is None else getattr(type(obj), "__module__", None),
        "dataclass_fields": _to_jsonable(_extract_dataclass_fields(obj)),
        "attributs_publics": _to_jsonable(_extract_public_attrs(obj)),
        "proprietes": _to_jsonable(_extract_properties(obj)),
        "rapport_simple": _to_jsonable(_safe_call_report(obj)),
        "rapports_methodes": _to_jsonable(_run_discovered_methods(obj, ctx)),
    }


# =============================================================================
# Définition moteur thermique
# =============================================================================


def _normaliser_definition_moteur_thermique(definition: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    d = _merge_dict_non_none({}, _safe_dict(definition))

    alias_map = {
        "temps_moteur": ("cycle_temps", "temps"),
        "nombre_cylindres": ("nb_cyl", "n_cyl", "n_cylindres"),
        "architecture": ("architecture_moteur", "type_architecture"),
        "alesage_m": ("bore_m", "diametre_cylindre_m", "diametre_alesage_m"),
        "course_m": ("stroke_m",),
        "rpm_nominal": ("rpm", "regime_nominal_rpm", "vitesse_rotation_rpm"),
        "puissance_nominale_visee_w": ("puissance_requise_W", "puissance_w", "power_w", "puissance_moteur_w"),
        "type_puissance_nominale": ("type_puissance",),
        "pme_nominale_pa": ("pme_pa", "pression_moyenne_effective_pa", "PME_pa"),
        "pression_max_pa": ("p_max_pa",),
        "rendement_mecanique_nominal": ("rendement_mecanique", "eta_mecanique"),
        "masse_estimee_max_kg": ("masse_estimee_kg", "masse_kg"),
        "longueur_bielle_m": ("bielle_longueur_m",),
        "contrainte_admissible_pa": ("sigma_adm_pa",),
    }

    for canonical, aliases in alias_map.items():
        if d.get(canonical) is None:
            for alias in aliases:
                if d.get(alias) is not None:
                    d[canonical] = d[alias]
                    break

    if d.get("temps_moteur") is not None:
        d["temps_moteur"] = _safe_int(d.get("temps_moteur")) or d.get("temps_moteur")
    if d.get("nombre_cylindres") is not None:
        d["nombre_cylindres"] = _safe_int(d.get("nombre_cylindres")) or d.get("nombre_cylindres")

    if d.get("type_puissance_nominale") is None and d.get("puissance_nominale_visee_w") is not None:
        d["type_puissance_nominale"] = "frein"

    if d.get("pme_pa") is None and d.get("pme_nominale_pa") is not None:
        d["pme_pa"] = d["pme_nominale_pa"]
    if d.get("pme_nominale_pa") is None and d.get("pme_pa") is not None:
        d["pme_nominale_pa"] = d["pme_pa"]

    if d.get("puissance_requise_W") is None and d.get("puissance_nominale_visee_w") is not None:
        d["puissance_requise_W"] = d["puissance_nominale_visee_w"]
    if d.get("puissance_nominale_visee_w") is None and d.get("puissance_requise_W") is not None:
        d["puissance_nominale_visee_w"] = d["puissance_requise_W"]

    alesage_m = _safe_float(d.get("alesage_m"))
    course_m = _safe_float(d.get("course_m"))
    nb_cyl = _safe_int(d.get("nombre_cylindres"))
    rpm_nominal = _safe_float(d.get("rpm_nominal"))
    puissance_w = _safe_float(d.get("puissance_nominale_visee_w"))
    couple_nm = _safe_float(d.get("couple_max_Nm"))

    if alesage_m is not None and course_m is not None and nb_cyl is not None and nb_cyl > 0:
        cylindree_unitaire_m3 = (math.pi * alesage_m * alesage_m / 4.0) * course_m
        d.setdefault("cylindree_unitaire_m3", cylindree_unitaire_m3)
        d.setdefault("cylindree_totale_m3", cylindree_unitaire_m3 * nb_cyl)
        d.setdefault("cylindree_totale_cc", d["cylindree_totale_m3"] * 1e6)
        d.setdefault("rayon_manivelle_m", 0.5 * course_m)

    if course_m is not None and rpm_nominal is not None:
        d.setdefault("vitesse_piston_moyenne_ms", 2.0 * course_m * (rpm_nominal / 60.0))

    if couple_nm is None and puissance_w is not None and rpm_nominal is not None and rpm_nominal > 0.0:
        omega = 2.0 * math.pi * rpm_nominal / 60.0
        if omega > 0.0:
            couple_nm = puissance_w / omega
            d.setdefault("couple_max_Nm", couple_nm)
            d.setdefault("couple_requis_Nm", couple_nm)

    if d.get("couple_requis_Nm") is None and d.get("couple_max_Nm") is not None:
        d["couple_requis_Nm"] = d["couple_max_Nm"]

    if d.get("force_bielle_N") is None and couple_nm is not None and course_m is not None and course_m > 0.0:
        rayon = 0.5 * course_m
        if rayon > 0.0:
            d["force_bielle_N"] = abs(couple_nm) / rayon

    return d


def _definition_moteur_pour_exigences(definition: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "puissance_visee_w": _first_finite(definition.get("puissance_nominale_visee_w"), definition.get("puissance_requise_W")),
        "type_puissance": _first_non_none(definition.get("type_puissance_nominale"), "frein"),
        "rpm": _safe_float(definition.get("rpm_nominal")),
        "pression_moyenne_effective_pa": _first_finite(definition.get("pme_nominale_pa"), definition.get("pme_pa")),
        "temps_moteur": _safe_int(definition.get("temps_moteur")),
        "rendement_mecanique": _safe_float(definition.get("rendement_mecanique_nominal")),
        "vitesse_piston_max_ms": _safe_float(definition.get("vitesse_piston_max_ms")),
        "ratio_course_alesage_max": _safe_float(definition.get("ratio_course_alesage_max")),
        "ratio_course_alesage_cible": _safe_float(definition.get("ratio_course_alesage_cible")),
        "L_max_m": _safe_float(definition.get("L_max_m")),
        "W_max_m": _safe_float(definition.get("W_max_m")),
        "architectures_autorisees": definition.get("architectures_autorisees"),
        "architecture_forcee": definition.get("architecture_forcee") or definition.get("architecture"),
        "pression_max_pa": _safe_float(definition.get("pression_max_pa")),
        "contrainte_admissible_pa": _safe_float(definition.get("contrainte_admissible_pa")),
        "facteur_securite_cylindre": _safe_float(definition.get("facteur_securite_cylindre")),
        "densite_materiau_kg_m3": _safe_float(definition.get("densite_materiau_kg_m3")),
        "cout_matiere_eur_kg": _safe_float(definition.get("cout_matiere_eur_kg")),
        "rendement_indique_cible_min": _safe_float(definition.get("rendement_indique_cible_min")),
        "rendement_mecanique_cible_min": _safe_float(definition.get("rendement_mecanique_cible_min")),
        "masse_estimee_max_kg": _safe_float(definition.get("masse_estimee_max_kg")),
        "cout_matiere_max_eur": _safe_float(definition.get("cout_matiere_max_eur")),
        "indice_maintenance_max": _safe_float(definition.get("indice_maintenance_max")),
        "duree_vie_cible_h": _safe_float(definition.get("duree_vie_cible_h")),
    }


def _proposer_puissance_moteur_depuis_besoin(
    puissance_traction_kw: float,
    *,
    charger_batterie: bool,
    puissance_auxiliaire_w: float,
    rendement_global_approx: float = 0.88,
    marge: float = 0.10,
) -> float:
    p = float(puissance_traction_kw) * 1000.0 + max(0.0, float(puissance_auxiliaire_w))
    if charger_batterie:
        p += 20_000.0
    p /= max(0.5, float(rendement_global_approx))
    p *= 1.0 + max(0.0, float(marge))
    return p


# =============================================================================
# Construction composants
# =============================================================================


def construire_moteur_electrique(
    *,
    tension_bus_v: float = 400.0,
    rendement_moteur: float = 0.92,
    pertes_fixes_w: float = 150.0,
    puissance_max_w: float = 120_000.0,
    regime_max_rpm: float = 10_000.0,
    couple_max_nm: float = 300.0,
    courant_max_a: Optional[float] = None,
) -> Any:
    if MoteurElectrique is None:
        raise ImportError("MoteurElectrique est indisponible.")
    kwargs = {
        "puissance_max_w": puissance_max_w,
        "regime_max_rpm": regime_max_rpm,
        "couple_max_nm": couple_max_nm,
        "tension_bus_v": tension_bus_v,
        "rendement_moteur": rendement_moteur,
        "pertes_fixes_w": pertes_fixes_w,
        "courant_max_a": courant_max_a,
    }
    return MoteurElectrique(**_filter_kwargs_for_callable(MoteurElectrique, kwargs))



def construire_batterie(
    *,
    tension_nominale_v: float = 400.0,
    rendement_charge: float = 0.94,
    tension_charge_v: float = 420.0,
    fenetre_soc: float = 0.8,
    densite_energetique_kwh_kg: Optional[float] = None,
) -> Any:
    if Batterie is None:
        raise ImportError("Batterie est indisponible.")
    kwargs = {
        "tension_nominale_v": tension_nominale_v,
        "rendement_charge": rendement_charge,
        "tension_charge_v": tension_charge_v,
        "fenetre_soc": fenetre_soc,
        "densite_energetique_kwh_kg": densite_energetique_kwh_kg,
    }
    return Batterie(**_filter_kwargs_for_callable(Batterie, kwargs))



def construire_alternateur(
    *,
    connexion: str = "Y",
    nombre_poles: int = 12,
    pertes_fixes_w: float = 500.0,
) -> Any:
    if Alternateur is None:
        raise ImportError("Alternateur est indisponible.")
    kwargs = {
        "connexion": connexion,
        "nombre_poles": nombre_poles,
        "pertes_fixes_w": pertes_fixes_w,
    }
    return Alternateur(**_filter_kwargs_for_callable(Alternateur, kwargs))



def construire_boite_crabots() -> Any:
    if BoiteCrabots is None:
        raise ImportError("BoiteCrabots est indisponible.")
    return BoiteCrabots()



def construire_architecture(
    *,
    temps_moteur: int = 4,
    rendement_mecanique: float = 0.85,
    ratio_course_alesage_max: float = 1.20,
) -> Any:
    if Architecture is None:
        raise ImportError("Architecture est indisponible.")
    kwargs = {
        "temps_moteur": temps_moteur,
        "rendement_mecanique": rendement_mecanique,
        "ratio_course_alesage_max": ratio_course_alesage_max,
    }
    return Architecture(**_filter_kwargs_for_callable(Architecture, kwargs))



def construire_moteur_thermique_complet(
    *,
    moteur_thermique_definition: Optional[Dict[str, Any]] = None,
    allow_definition_from_requirements: bool = True,
) -> Tuple[Any, Dict[str, Any]]:
    if MoteurThermique is None:
        raise ImportError("MoteurThermique est indisponible.")

    definition = _normaliser_definition_moteur_thermique(moteur_thermique_definition)
    rapport: Dict[str, Any] = {
        "definition_utilisee": definition,
        "mode_construction": None,
        "rapport_definition_exigences": None,
    }

    has_direct_geometry = (
        _safe_float(definition.get("alesage_m")) is not None
        and _safe_float(definition.get("course_m")) is not None
    )

    if has_direct_geometry:
        ctor_kwargs = _filter_kwargs_for_callable(MoteurThermique, definition)
        moteur = MoteurThermique(**ctor_kwargs)
        rapport["mode_construction"] = "direct"
        return moteur, rapport

    if allow_definition_from_requirements and hasattr(MoteurThermique, "definir_depuis_exigences"):
        kwargs_req = _filter_kwargs_for_callable(
            MoteurThermique.definir_depuis_exigences,
            _definition_moteur_pour_exigences(definition),
        )
        if kwargs_req.get("puissance_visee_w") is not None and kwargs_req.get("rpm") is not None:
            rapport_def = MoteurThermique.definir_depuis_exigences(**kwargs_req)
            rapport["rapport_definition_exigences"] = rapport_def
            moteur = _get_nested(rapport_def, "moteur_defini")
            if moteur is not None:
                rapport["mode_construction"] = "definir_depuis_exigences"
                return moteur, rapport

    ctor_kwargs = _filter_kwargs_for_callable(MoteurThermique, definition)
    moteur = MoteurThermique(**ctor_kwargs)
    rapport["mode_construction"] = "minimal"
    return moteur, rapport


# =============================================================================
# Construction des pièces
# =============================================================================


def _build_piece_instance(piece_cls: Any, raw_kwargs: Dict[str, Any], rapport: Dict[str, Any], nom: str) -> Any:
    if piece_cls is None:
        _push_inconnue(rapport, "impossibles", nom, f"Classe indisponible pour {nom}.")
        return None
    kwargs = _filter_kwargs_for_callable(piece_cls, raw_kwargs)
    try:
        return piece_cls(**kwargs)
    except Exception as exc:
        _push_inconnue(rapport, "impossibles", f"construction {nom}", str(exc))
        return None



def construire_pieces_depuis_systeme(
    *,
    rapport_systeme: Dict[str, Any],
    definition_moteur_thermique: Optional[Dict[str, Any]] = None,
    pieces_definition: Optional[Dict[str, Any]] = None,
    moteur_thermique_obj: Any = None,
    systeme_obj: Any = None,
    autoriser_approximations_geom: bool = False,
    materiau_metal_cle: str = "acier_42crmo4_qt",
    materiau_piston_cle: str = "alu_6061_t6",
    materiau_joint_cle: str = "ptfe",
    materiau_coussinet_cle: str = "bronze_cusn12",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    synth = _safe_dict(rapport_systeme.get("synthese"))
    mt_systeme = _safe_dict(synth.get("moteur_thermique"))
    definition_mt = _normaliser_definition_moteur_thermique(definition_moteur_thermique)
    mt = _merge_dict_non_none(mt_systeme, definition_mt)
    pieces_def = _safe_dict(pieces_definition)

    rapport: Dict[str, Any] = {
        "inputs": {
            "autoriser_approximations_geom": autoriser_approximations_geom,
        },
        "construction": {},
        "inconnues": {"impossibles": [], "partielles": []},
        "notes_modele": [],
    }

    alesage_m = _first_finite(mt.get("alesage_m"), _get_nested(rapport_systeme, "cao", "moteur_thermique", "alesage_mm"))
    if alesage_m is not None and alesage_m > 1.0:
        alesage_m = alesage_m / 1000.0

    course_m = _first_finite(mt.get("course_m"), _get_nested(rapport_systeme, "cao", "moteur_thermique", "course_mm"))
    if course_m is not None and course_m > 1.0:
        course_m = course_m / 1000.0

    rpm = _first_finite(mt.get("rpm_nominal"), mt.get("rpm"))
    pme_pa = _first_finite(mt.get("pme_pa"), mt.get("pme_nominale_pa"))
    pression_max_pa = _safe_float(mt.get("pression_max_pa"))
    couple_max_nm = _first_finite(mt.get("couple_max_Nm"), mt.get("couple_requis_Nm"))
    force_bielle_N = _safe_float(mt.get("force_bielle_N"))

    longueur_utile_m = _first_finite(
        _get_nested(pieces_def, "cylindre", "longueur_utile_m"),
        _get_nested(pieces_def, "cylindre", "longueur_m"),
    )
    if longueur_utile_m is None and autoriser_approximations_geom and course_m is not None:
        longueur_utile_m = 1.5 * course_m
        _append_note(rapport, "longueur_utile_m du cylindre approchée à 1.5 * course_m.")

    longueur_bielle_m = _first_finite(
        _get_nested(pieces_def, "bielle", "longueur_bielle_m"),
        definition_mt.get("longueur_bielle_m"),
    )
    if longueur_bielle_m is None and autoriser_approximations_geom and course_m is not None:
        longueur_bielle_m = 3.0 * course_m
        _append_note(rapport, "longueur_bielle_m approchée à 3.0 * course_m.")

    longueur_deplaceur_m = _first_finite(_get_nested(pieces_def, "deplaceur", "longueur_totale_m"))
    if longueur_deplaceur_m is None and autoriser_approximations_geom and longueur_utile_m is not None:
        longueur_deplaceur_m = 0.8 * longueur_utile_m
        _append_note(rapport, "longueur_totale_m du déplaceur approchée à 0.8 * longueur_utile_m.")

    pieces: Dict[str, Any] = {}

    # Cylindre
    raw = _merge_dict_non_none(
        {
            "alesage_m": alesage_m,
            "course_m": course_m,
            "longueur_utile_m": longueur_utile_m,
            "pression_service_pa": pme_pa,
            "pression_max_pa": pression_max_pa,
            "materiau_cle": materiau_metal_cle,
        },
        _safe_dict(pieces_def.get("cylindre")),
    )
    if raw.get("alesage_m") is None or raw.get("course_m") is None or raw.get("longueur_utile_m") is None:
        _push_inconnue(rapport, "partielles", "cylindre", "Construction partielle impossible sans alesage_m, course_m et longueur_utile_m.")
    else:
        pieces["cylindre"] = _build_piece_instance(Cylindre, raw, rapport, "cylindre")
    rapport["construction"]["cylindre"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("cylindre") is not None}

    # Piston
    raw = _merge_dict_non_none(
        {
            "cylindre": pieces.get("cylindre"),
            "materiau_piston_cle": materiau_piston_cle,
            "pression_max_pa": pression_max_pa,
            "alesage_nominal_m": alesage_m,
            "course_m": course_m,
            "rpm": rpm,
            "materiau_joint_cle": materiau_joint_cle,
        },
        _safe_dict(pieces_def.get("piston")),
    )
    pieces["piston"] = _build_piece_instance(Piston, raw, rapport, "piston")
    rapport["construction"]["piston"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("piston") is not None}

    # Joint piston
    raw = _merge_dict_non_none(
        {
            "piston": pieces.get("piston"),
            "cylindre": pieces.get("cylindre"),
            "materiau_joint_cle": materiau_joint_cle,
        },
        _safe_dict(pieces_def.get("joint_piston")),
    )
    pieces["joint_piston"] = _build_piece_instance(JointPiston, raw, rapport, "joint_piston")
    rapport["construction"]["joint_piston"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("joint_piston") is not None}

    # Arbre piston
    raw = _merge_dict_non_none(
        {
            "piston": pieces.get("piston"),
            "bielle": None,
            "cylindre": pieces.get("cylindre"),
            "materiau_cle": materiau_metal_cle,
            "rpm": rpm,
        },
        _safe_dict(pieces_def.get("arbre_piston")),
    )
    pieces["arbre_piston"] = _build_piece_instance(ArbrePiston, raw, rapport, "arbre_piston")
    rapport["construction"]["arbre_piston"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("arbre_piston") is not None}

    # Bielle
    raw = _merge_dict_non_none(
        {
            "piston": pieces.get("piston"),
            "arbre_piston": pieces.get("arbre_piston"),
            "cylindre": pieces.get("cylindre"),
            "moteur_thermique": moteur_thermique_obj if moteur_thermique_obj is not None else mt,
            "longueur_bielle_m": longueur_bielle_m,
            "force_axiale_max_N": force_bielle_N,
            "materiau_cle": materiau_metal_cle,
        },
        _safe_dict(pieces_def.get("bielle")),
    )
    pieces["bielle"] = _build_piece_instance(CorpsBielle, raw, rapport, "bielle")
    rapport["construction"]["bielle"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("bielle") is not None}

    if pieces.get("arbre_piston") is not None and pieces.get("bielle") is not None:
        try:
            if getattr(pieces["arbre_piston"], "bielle", None) is None:
                object.__setattr__(pieces["arbre_piston"], "bielle", pieces["bielle"])
        except Exception:
            pass

    # Coussinet arbre-piston
    raw = _merge_dict_non_none(
        {
            "arbre_piston": pieces.get("arbre_piston"),
            "materiau_coussinet": materiau_coussinet_cle,
            "rpm": rpm,
        },
        _safe_dict(pieces_def.get("coussinet_arbre_piston")),
    )
    pieces["coussinet_arbre_piston"] = _build_piece_instance(CoussinetArbrePiston, raw, rapport, "coussinet_arbre_piston")
    rapport["construction"]["coussinet_arbre_piston"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("coussinet_arbre_piston") is not None}

    # Couvercle cylindre
    raw = _merge_dict_non_none(
        {
            "cylindre": pieces.get("cylindre"),
            "materiau_cle": materiau_metal_cle,
            "pression_max_pa": pression_max_pa,
        },
        _safe_dict(pieces_def.get("couvercle_cylindre")),
    )
    pieces["couvercle_cylindre"] = _build_piece_instance(CouvercleCylindre, raw, rapport, "couvercle_cylindre")
    rapport["construction"]["couvercle_cylindre"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("couvercle_cylindre") is not None}

    # Vis couvercle cylindre
    raw = _merge_dict_non_none(
        {
            "cylindre": pieces.get("cylindre"),
            "couvercle": pieces.get("couvercle_cylindre"),
            "pression_max_pa": pression_max_pa,
            "classe_vis_iso898": "10.9",
        },
        _safe_dict(pieces_def.get("vis_couvercle_cylindre")),
    )
    pieces["vis_couvercle_cylindre"] = _build_piece_instance(VisCouvercleCylindre, raw, rapport, "vis_couvercle_cylindre")
    rapport["construction"]["vis_couvercle_cylindre"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("vis_couvercle_cylindre") is not None}

    # Déplaceur
    raw = _merge_dict_non_none(
        {
            "cylindre": pieces.get("cylindre"),
            "pression_froid_pa": pression_max_pa,
            "materiau_cle": materiau_metal_cle,
            "longueur_totale_m": longueur_deplaceur_m,
        },
        _safe_dict(pieces_def.get("deplaceur")),
    )
    pieces["deplaceur"] = _build_piece_instance(Deplaceur, raw, rapport, "deplaceur")
    rapport["construction"]["deplaceur"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("deplaceur") is not None}

    # Joint déplaceur
    raw = _merge_dict_non_none(
        {
            "deplaceur": pieces.get("deplaceur"),
            "cylindre": pieces.get("cylindre"),
            "materiau_joint_cle": materiau_joint_cle,
        },
        _safe_dict(pieces_def.get("joint_deplaceur")),
    )
    pieces["joint_deplaceur"] = _build_piece_instance(JointDeplaceur, raw, rapport, "joint_deplaceur")
    rapport["construction"]["joint_deplaceur"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("joint_deplaceur") is not None}

    # Arbre vilebrequin
    raw = _merge_dict_non_none(
        {
            "cylindre": pieces.get("cylindre"),
            "piston": pieces.get("piston"),
            "bielle": pieces.get("bielle"),
            "moteur_thermique": moteur_thermique_obj,
            "materiau_cle": materiau_metal_cle,
            "rpm": rpm,
            "couple_max_Nm": couple_max_nm,
            "course_m": course_m,
            "force_bielle_effective_N": force_bielle_N,
        },
        _safe_dict(pieces_def.get("arbre_vilebrequin")),
    )
    pieces["arbre_vilebrequin"] = _build_piece_instance(ArbreVilbrequin, raw, rapport, "arbre_vilebrequin")
    rapport["construction"]["arbre_vilebrequin"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("arbre_vilebrequin") is not None}

    # Vilbrequin
    raw = _merge_dict_non_none(
        {
            "arbre": pieces.get("arbre_vilebrequin"),
            "cylindre": pieces.get("cylindre"),
            "piston": pieces.get("piston"),
            "bielle": pieces.get("bielle"),
            "deplaceur": pieces.get("deplaceur"),
            "systeme_complet": systeme_obj,
            "moteur_thermique": moteur_thermique_obj,
            "course_m": course_m,
            "rpm": rpm,
            "couple_max_Nm": couple_max_nm,
            "materiau_cle": materiau_metal_cle,
        },
        _safe_dict(pieces_def.get("vilbrequin")),
    )
    pieces["vilbrequin"] = _build_piece_instance(Vilbrequin, raw, rapport, "vilbrequin")
    rapport["construction"]["vilbrequin"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("vilbrequin") is not None}

    # Roulement aiguille arbre
    raw = _merge_dict_non_none(
        {
            "vilbrequin": pieces.get("vilbrequin"),
            "arbre_vilebrequin": pieces.get("arbre_vilebrequin"),
            "bielle": pieces.get("bielle"),
            "piston": pieces.get("piston"),
            "cylindre": pieces.get("cylindre"),
            "rpm": rpm,
            "couple_max_Nm": couple_max_nm,
            "rayon_manivelle_m": (0.5 * course_m) if _is_finite(course_m) else None,
            "duree_vie_cible_h": 5000.0,
            "exposant_vie_p": 10.0 / 3.0,
        },
        _safe_dict(pieces_def.get("roulement_aiguille_arbre")),
    )
    pieces["roulement_aiguille_arbre"] = _build_piece_instance(RoulementAiguilleArbre, raw, rapport, "roulement_aiguille_arbre")
    rapport["construction"]["roulement_aiguille_arbre"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("roulement_aiguille_arbre") is not None}

    # Roulement aiguille arbre vilebrequin
    raw = _merge_dict_non_none(
        {
            "corps_bielle": pieces.get("bielle"),
            "arbre_vilebrequin": pieces.get("arbre_vilebrequin"),
            "moteur_thermique": moteur_thermique_obj,
            "rpm_vilebrequin": rpm,
            "vie_cible_heures": 5000.0,
            "exposant_p_iso281": 10.0 / 3.0,
        },
        _safe_dict(pieces_def.get("roulement_aiguille_arbre_vilebrequin")),
    )
    pieces["roulement_aiguille_arbre_vilebrequin"] = _build_piece_instance(
        RoulementAiguilleArbreVilebrequin,
        raw,
        rapport,
        "roulement_aiguille_arbre_vilebrequin",
    )
    rapport["construction"]["roulement_aiguille_arbre_vilebrequin"] = {
        "kwargs": _to_jsonable(raw),
        "construit": pieces.get("roulement_aiguille_arbre_vilebrequin") is not None,
    }

    # Arbre moteur
    raw = _merge_dict_non_none(
        {
            "cylindre": pieces.get("cylindre"),
            "moteur_thermique": moteur_thermique_obj,
            "systeme_complet": systeme_obj,
            "vilbrequin": pieces.get("vilbrequin"),
            "roulement_aiguille": pieces.get("roulement_aiguille_arbre"),
            "couple_max_Nm": couple_max_nm,
            "rpm": rpm,
            "nombre_cylindres": _safe_int(mt.get("nombre_cylindres")),
            "materiau_arbre_cle": materiau_metal_cle,
        },
        _safe_dict(pieces_def.get("arbre")),
    )
    pieces["arbre"] = _build_piece_instance(ArbreMoteur, raw, rapport, "arbre")
    rapport["construction"]["arbre"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("arbre") is not None}

    # Clavette arbre
    if ClavetteArbre is not None:
        raw = _merge_dict_non_none(
            {
                "arbre_vilbrequin": pieces.get("arbre_vilebrequin"),
                "roulement_aiguille_arbre": pieces.get("roulement_aiguille_arbre"),
                "vilbrequin": pieces.get("vilbrequin"),
                "moteur_thermique": moteur_thermique_obj,
                "couple_transmis_Nm": couple_max_nm,
                "materiau_clavette_cle": materiau_metal_cle,
                "limite_elastique_anneau_interieur_pa": 900e6,
            },
            _safe_dict(pieces_def.get("clavette_arbre")),
        )
        pieces["clavette_arbre"] = _build_piece_instance(ClavetteArbre, raw, rapport, "clavette_arbre")
        rapport["construction"]["clavette_arbre"] = {
            "kwargs": _to_jsonable(raw),
            "construit": pieces.get("clavette_arbre") is not None,
        }
    else:
        pieces["clavette_arbre"] = None
        _push_inconnue(rapport, "partielles", "clavette_arbre", "Module ou classe ClavetteArbre indisponible.")

    _dedup_report_lists(rapport)
    return pieces, rapport


# =============================================================================
# Analyses détaillées
# =============================================================================


def analyser_pieces(pieces: Mapping[str, Any]) -> Dict[str, Any]:
    rapports: Dict[str, Any] = {}
    for nom, obj in pieces.items():
        if obj is None:
            rapports[nom] = {"note": "Pièce non construite."}
            continue
        rep = _safe_call_report(obj)
        rapports[nom] = rep if rep is not None else {"note": "Pas de rapport dict retourné."}
    return rapports



def analyser_pieces_exhaustif(
    *,
    pieces: Mapping[str, Any],
    context: Mapping[str, Any],
    rapport_construction_pieces: Mapping[str, Any],
    rapports_pieces: Mapping[str, Any],
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    construction = _safe_dict(rapport_construction_pieces.get("construction"))
    for nom, obj in pieces.items():
        out[nom] = {
            "construction": _to_jsonable(construction.get(nom)),
            "rapport_principal": _to_jsonable(rapports_pieces.get(nom)),
            "objet": _decrire_objet(obj, context),
        }
    return out



def analyser_composants_complementaires(
    *,
    systeme_obj: Any,
    composants: Mapping[str, Any],
    definition_moteur: Dict[str, Any],
    rapport_systeme: Dict[str, Any],
    analyses_complementaires: Optional[Dict[str, Any]] = None,
    pieces: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    analyses_user = _safe_dict(analyses_complementaires)
    pieces = pieces or {}
    rapports: Dict[str, Any] = {}
    moteur_thermique = composants.get("moteur_thermique")
    batterie = composants.get("batterie")
    alternateur = composants.get("alternateur")
    architecture = composants.get("architecture")
    boite = composants.get("boite_crabots")
    moteur_electrique = composants.get("moteur_electrique")

    mt_synth = _safe_dict(_get_nested(rapport_systeme, "synthese", "moteur_thermique"))
    veh_synth = _safe_dict(_get_nested(rapport_systeme, "synthese", "vehicule"))
    batt_synth = _safe_dict(_get_nested(rapport_systeme, "synthese", "batterie"))
    alt_synth = _safe_dict(_get_nested(rapport_systeme, "synthese", "alternateur"))

    if batterie is not None and hasattr(batterie, "analyser_dimensionnement"):
        kwargs = _merge_dict_non_none(
            {
                "distance_km": _safe_float(_get_nested(rapport_systeme, "entrees", "mission_batterie", "distance_km")),
                "conso_kwh_km": _safe_float(_get_nested(rapport_systeme, "entrees", "mission_batterie", "conso_kwh_km")),
                "puissance_moyenne_kw": _safe_float(_get_nested(rapport_systeme, "entrees", "mission_batterie", "puissance_moyenne_kw")),
                "vitesse_moyenne_kmh": _safe_float(_get_nested(rapport_systeme, "entrees", "mission_batterie", "vitesse_moyenne_kmh")),
                "temps_charge_cible_h": _safe_float(_get_nested(rapport_systeme, "entrees", "mission_batterie", "temps_charge_cible_h")),
                "puissance_pic_kw": _safe_float(_get_nested(rapport_systeme, "entrees", "mission_batterie", "puissance_pic_kw")),
                "duree_pic_s": _safe_float(_get_nested(rapport_systeme, "entrees", "mission_batterie", "duree_pic_s")),
                "energie_utile_imposee_kwh": _safe_float(_get_nested(rapport_systeme, "entrees", "mission_batterie", "energie_utile_imposee_kwh")),
                "calculer_puissance_charge_requise": True,
            },
            _safe_dict(analyses_user.get("batterie")),
        )
        rapports["batterie_dimensionnement"] = _safe_run_method(batterie, "analyser_dimensionnement", kwargs)

    if alternateur is not None:
        kwargs = _merge_dict_non_none(
            {
                "puissance_bus_dc_w": _first_finite(veh_synth.get("puissance_bus_dc_design_w"), alt_synth.get("P_electrique_sortie_W")),
                "vitesse_rotation_rpm": _first_finite(alt_synth.get("vitesse_rotation_rpm"), _get_nested(rapport_systeme, "liaisons", "alternateur", "vitesse_rotation_rpm")),
                "tension_bus_dc_v": _first_finite(veh_synth.get("tension_bus_dc_v"), batt_synth.get("tension_nominale_v")),
                "batterie": batterie,
                "moteur": moteur_electrique,
                "energie_a_recharger_kwh": _safe_float(batt_synth.get("energie_utile_kwh")),
            },
            _safe_dict(analyses_user.get("alternateur_bus_dc")),
        )
        rapports["alternateur_bus_dc"] = _safe_run_method(alternateur, "analyser_pour_bus_dc", kwargs)

        kwargs = _merge_dict_non_none(
            {
                "vitesse_rotation_rpm": _first_finite(alt_synth.get("vitesse_rotation_rpm"), _get_nested(rapport_systeme, "liaisons", "alternateur", "vitesse_rotation_rpm")),
                "puissance_electrique_cible_w": _first_finite(alt_synth.get("P_electrique_sortie_W"), veh_synth.get("puissance_bus_dc_design_w")),
                "tension_v": _first_finite(veh_synth.get("tension_bus_dc_v"), batt_synth.get("tension_nominale_v")),
            },
            _safe_dict(analyses_user.get("alternateur_point")),
        )
        rapports["alternateur_point"] = _safe_run_method(alternateur, "analyser_point_de_fonctionnement", kwargs)

    if architecture is not None:
        kwargs = _merge_dict_non_none(
            {
                "puissance_cible_w": _first_finite(mt_synth.get("puissance_requise_W"), definition_moteur.get("puissance_nominale_visee_w")),
                "regime_tr_min": _safe_float(mt_synth.get("rpm_nominal")),
                "pme_pa": _first_finite(mt_synth.get("pme_pa"), definition_moteur.get("pme_pa")),
                "vitesse_piston_max_ms": _safe_float(definition_moteur.get("vitesse_piston_max_ms")),
                "longueur_dispo_m": _safe_float(_get_nested(rapport_systeme, "entrees", "architecture", "longueur_dispo_m")),
                "largeur_dispo_m": _safe_float(_get_nested(rapport_systeme, "entrees", "architecture", "largeur_dispo_m")),
                "architectures_autorisees": definition_moteur.get("architectures_autorisees"),
                "architecture_forcee": _first_non_none(definition_moteur.get("architecture_forcee"), definition_moteur.get("architecture")),
            },
            _safe_dict(analyses_user.get("architecture")),
        )
        rapports["architecture"] = _safe_run_method(architecture, "analyser", kwargs)

    if boite is not None:
        kwargs = _merge_dict_non_none(
            {
                "couple_nm": _first_finite(mt_synth.get("couple_requis_Nm"), definition_moteur.get("couple_requis_Nm"), definition_moteur.get("couple_max_Nm")),
                "vitesse_rotation_tr_min": _safe_float(mt_synth.get("rpm_nominal")),
                "moment_flechissant_nm": _safe_float(_get_nested(rapport_systeme, "entrees", "boite", "moment_flechissant_nm")),
            },
            _safe_dict(analyses_user.get("boite_point")),
        )
        rapports["boite_point"] = _safe_run_method(boite, "analyser_point", kwargs)

        kwargs = _merge_dict_non_none(
            {
                "alternateur": alternateur,
                "puissance_bus_dc_w": _first_finite(veh_synth.get("puissance_bus_dc_design_w"), alt_synth.get("P_electrique_sortie_W")),
                "rpm_moteur": _safe_float(mt_synth.get("rpm_nominal")),
                "rapports": _first_non_none(_get_nested(rapport_systeme, "entrees", "boite", "rapports_boite_candidates"), (1.0, 1.5, 2.0, 2.5, 3.0)),
                "tension_bus_dc_v": _first_finite(veh_synth.get("tension_bus_dc_v"), batt_synth.get("tension_nominale_v")),
                "batterie": batterie,
                "moteur": moteur_electrique,
            },
            _safe_dict(analyses_user.get("boite_chaine")),
        )
        rapports["boite_chaine"] = _safe_run_method(boite, "analyser_chaine_moteur_alternateur", kwargs)

    if moteur_thermique is not None:
        piston = pieces.get("piston")
        kwargs = _merge_dict_non_none(
            {
                "pression_pa": _safe_float(definition_moteur.get("pression_max_pa")),
                "taux_compression": _safe_float(definition_moteur.get("taux_compression_nominal")),
                "volume_mort_m3": _safe_float(definition_moteur.get("volume_mort_nominal_m3")),
            },
            _safe_dict(analyses_user.get("moteur_thermique_geometrie")),
        )
        rapports["moteur_thermique_geometrie"] = _safe_run_method(moteur_thermique, "analyser_geometrie_definition", kwargs)

        kwargs = _merge_dict_non_none(
            {
                "rpm": _safe_float(mt_synth.get("rpm_nominal")),
                "piston": piston,
                "rapport_piston": _safe_dict(rapports.get("moteur_thermique_geometrie")).get("rapport_piston"),
                "rayon_maneton_m": _safe_float(definition_moteur.get("rayon_manivelle_m")),
                "taux_compression": _safe_float(definition_moteur.get("taux_compression_nominal")),
                "volume_mort_m3": _safe_float(definition_moteur.get("volume_mort_nominal_m3")),
            },
            _safe_dict(analyses_user.get("moteur_thermique_cycle")),
        )
        rapports["moteur_thermique_cycle"] = _safe_run_method(moteur_thermique, "analyser_cycle_mecanique", kwargs)

        kwargs = _merge_dict_non_none(
            {
                "rpm": _safe_float(mt_synth.get("rpm_nominal")),
                "piston": piston,
                "rapport_piston": _safe_dict(rapports.get("moteur_thermique_cycle")).get("rapport_piston"),
                "pression_moyenne_effective_pa": _first_finite(mt_synth.get("pme_pa"), definition_moteur.get("pme_pa")),
                "pression_max_pa": _safe_float(definition_moteur.get("pression_max_pa")),
            },
            _safe_dict(analyses_user.get("moteur_thermique_point")),
        )
        rapports["moteur_thermique_point"] = _safe_run_method(moteur_thermique, "analyser_point_de_fonctionnement", kwargs)

        kwargs = _merge_dict_non_none(
            {
                "carburant": definition_moteur.get("carburant"),
                "puissance_utile_w": _first_finite(mt_synth.get("puissance_requise_W"), definition_moteur.get("puissance_requise_W"), definition_moteur.get("puissance_nominale_visee_w")),
                "rendement_global": _safe_float(definition_moteur.get("rendement_global")),
            },
            _safe_dict(analyses_user.get("moteur_thermique_bilan_carburant")),
        )
        rapports["moteur_thermique_bilan_carburant"] = _safe_run_method(moteur_thermique, "analyser_bilan_carburant", kwargs)

    return rapports



def decrire_composants_exhaustif(
    *,
    composants: Mapping[str, Any],
    context: Mapping[str, Any],
    analyses_composants: Mapping[str, Any],
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for nom, obj in composants.items():
        out[nom] = {
            "analyses_ciblees": _to_jsonable({k: v for k, v in analyses_composants.items() if k.startswith(nom) or nom in k}),
            "objet": _decrire_objet(obj, context),
        }
    return out


# =============================================================================
# Config STHO_ME secondaire
# =============================================================================


def construire_config_stho_me(
    *,
    composants: Mapping[str, Any],
    pieces_definition: Optional[Dict[str, Any]],
    definition_moteur: Dict[str, Any],
    analyse_systeme: Dict[str, Any],
    analyses_complementaires: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    analyses_extra = _safe_dict(analyses_complementaires)
    cfg: Dict[str, Any] = {
        "meta": {
            "backend": "main.py",
            "source": "config_generee_depuis_main",
        },
        "composants": {
            "moteur_electrique": composants.get("moteur_electrique"),
            "batterie": composants.get("batterie"),
            "alternateur": composants.get("alternateur"),
            "moteur_thermique": composants.get("moteur_thermique"),
            "boite_crabots": composants.get("boite_crabots"),
            "architecture": composants.get("architecture"),
        },
        "pieces": _safe_dict(pieces_definition),
        "analyses": {
            "moteur_thermique_definition": _definition_moteur_pour_exigences(definition_moteur),
            "systeme_complet": analyse_systeme,
        },
    }
    for key in (
        "batterie",
        "alternateur_bus_dc",
        "alternateur_point",
        "architecture",
        "moteur_thermique_geometrie",
        "moteur_thermique_cycle",
        "moteur_thermique_point",
        "moteur_thermique_bilan_carburant",
        "boite_point",
        "boite_chaine",
    ):
        if analyses_extra.get(key):
            cfg["analyses"][key] = analyses_extra[key]
    return cfg


# =============================================================================
# Orchestration principale
# =============================================================================


def dimensionner_systeme_shsem(
    puissance_traction_kw: float,
    *,
    # Mission véhicule / électrique
    charger_batterie: bool = True,
    distance_km: Optional[float] = None,
    vitesse_moyenne_kmh: Optional[float] = None,
    temps_charge_cible_h: float = 1.0,
    masse_kg: Optional[float] = None,
    vitesse_ms: Optional[float] = None,
    acceleration_ms2: Optional[float] = None,
    angle_pente: float = 0.0,
    angle_unite: str = "rad",
    coef_roulement: Optional[float] = None,
    coef_trainee_aero_cda: Optional[float] = None,
    rayon_roue_m: Optional[float] = None,
    rapport_reduction_global: Optional[float] = None,
    rendement_transmission: Optional[float] = None,
    nb_roues_motrices: int = 2,
    nb_moteurs_electriques: int = 1,
    pertes_fixes_transmission_w: float = 0.0,
    couple_pertes_transmission_nm: float = 0.0,
    marge_puissance: float = 0.0,
    marge_couple: float = 0.0,
    puissance_auxiliaire_w: float = 5000.0,
    conso_kwh_km: Optional[float] = None,
    puissance_pic_kw: Optional[float] = None,
    duree_pic_s: Optional[float] = None,
    energie_utile_imposee_kwh: Optional[float] = None,
    scenario_bus_dc: str = "traction_plus_charge",
    tension_bus_dc_v: Optional[float] = None,
    rapport_vitesse_alt_sur_moteur: float = 2.0,
    vitesse_moteur_thermique_rpm: float = 3000.0,
    tension_alt_v: Optional[float] = None,
    courant_alt_a: Optional[float] = None,
    facteur_puissance_alt: float = 1.0,
    courant_est_ligne: bool = True,
    rendement_liaison_meca_alt: float = 1.0,
    rapports_boite_candidates: Sequence[float] = (1.0, 1.5, 2.0, 2.5, 3.0),
    rendement_boite: Optional[float] = None,
    facteur_service_boite: float = 1.2,
    moment_flechissant_nm: Optional[float] = None,
    inertie_primaire_kg_m2: Optional[float] = None,
    inertie_secondaire_kg_m2: Optional[float] = None,
    delta_omega_rad_s: Optional[float] = None,
    temps_engagement_s: Optional[float] = None,
    force_axiale_roulement_N: Optional[float] = None,
    force_radiale_roulement_N: Optional[float] = None,

    # Architecture / thermique / matière
    pme_pa: float = 8.0e5,
    vitesse_piston_max_ms: float = 10.0,
    longueur_dispo_m: float = 1.2,
    largeur_dispo_m: float = 0.8,
    horizon_usage_h: float = 20_000.0,
    architectures_autorisees: Optional[Sequence[str]] = None,
    architecture_forcee: Optional[str] = None,
    poids_maintenance: float = 1.0,
    poids_masse: float = 1.0,
    poids_cout_matiere: float = 1.0,
    poids_compacite: float = 1.0,
    poids_fiabilite: float = 1.0,
    poids_rendement: float = 1.0,
    pression_max_pa: float = 3.0e6,
    contrainte_admissible_pa: float = 1.2e8,
    densite_materiau_kg_m3: float = 7800.0,
    cout_matiere_eur_kg: float = 2.0,
    rendement_indique_cible_min: Optional[float] = None,
    rendement_mecanique_cible_min: float = 0.80,
    masse_estimee_max_kg: Optional[float] = None,
    cout_matiere_max_eur: Optional[float] = None,
    indice_maintenance_max: Optional[float] = None,
    duree_vie_cible_h: Optional[float] = None,

    # Définition moteur thermique
    moteur_thermique_definition: Optional[Dict[str, Any]] = None,
    temps_moteur: int = 4,
    nombre_cylindres: int = 1,
    architecture_moteur: Optional[str] = None,
    alesage_m: Optional[float] = None,
    course_m: Optional[float] = None,
    rpm_moteur_nominal: Optional[float] = None,
    couple_moteur_max_Nm: Optional[float] = None,
    puissance_moteur_requise_W: Optional[float] = None,
    force_bielle_N: Optional[float] = None,
    carburant: Optional[str] = None,
    ratio_course_alesage_max: float = 1.20,
    ratio_course_alesage_cible: Optional[float] = None,
    taux_compression_nominal: Optional[float] = None,
    volume_mort_nominal_m3: Optional[float] = None,

    # Définition des pièces / analyses complémentaires
    pieces_definition: Optional[Dict[str, Any]] = None,
    analyses_complementaires: Optional[Dict[str, Any]] = None,
    composants_definition: Optional[Dict[str, Any]] = None,
    autoriser_approximations_geom: bool = False,

    # Options d'orchestration
    lancer_pipeline_legacy: bool = True,
    lancer_stho_me_secondaire: bool = True,
) -> Dict[str, Any]:
    """
    Orchestrateur backend principal.

    En donnant au minimum une puissance de traction, il tente de :
    1) définir le moteur thermique depuis les exigences si la géométrie n'est pas fournie ;
    2) analyser le système complet ;
    3) construire toutes les pièces calculables ;
    4) récupérer les rapports détaillés de chaque composant et de chaque pièce ;
    5) agréger les inconnues et alertes au lieu de masquer ce qui manque.

    Le script n'invente pas les données fondamentales manquantes. En revanche,
    si aucune définition géométrique secondaire n'est fournie, il peut activer
    des approximations simples de second rang pour maximiser les rapports pièces,
    uniquement si `autoriser_approximations_geom=True` ou si la géométrie a été
    définie automatiquement depuis les exigences et qu'aucune définition de pièces
    n'a été donnée.
    """
    if SystemeComplet is None:
        raise ImportError("SystemeComplet est indisponible. Impossible de lancer l'orchestrateur.")

    p_trac_kw = _req_pos("puissance_traction_kw", puissance_traction_kw)
    composants_def = _safe_dict(composants_definition)

    rapport_global: Dict[str, Any] = {
        "meta": {
            "backend": "main.py",
            "orchestrateur": "SystemeComplet + pièces + optimisation + STHO_ME(optionnel)",
            "repertoire": str(_THIS_DIR),
        },
        "inconnues": {"impossibles": [], "partielles": []},
        "alertes": {},
        "notes_modele": [],
    }

    # 0) Définition moteur thermique
    puissance_nominale_auto_w = _proposer_puissance_moteur_depuis_besoin(
        p_trac_kw,
        charger_batterie=charger_batterie,
        puissance_auxiliaire_w=puissance_auxiliaire_w,
    )
    definition_moteur = _normaliser_definition_moteur_thermique(
        _merge_dict_non_none(
            {
                "temps_moteur": temps_moteur,
                "nombre_cylindres": nombre_cylindres,
                "architecture": architecture_moteur,
                "alesage_m": alesage_m,
                "course_m": course_m,
                "rpm_nominal": rpm_moteur_nominal if rpm_moteur_nominal is not None else vitesse_moteur_thermique_rpm,
                "couple_max_Nm": couple_moteur_max_Nm,
                "puissance_nominale_visee_w": puissance_moteur_requise_W if puissance_moteur_requise_W is not None else puissance_nominale_auto_w,
                "pme_nominale_pa": pme_pa,
                "pression_max_pa": pression_max_pa,
                "force_bielle_N": force_bielle_N,
                "rendement_mecanique_nominal": rendement_mecanique_cible_min,
                "carburant": carburant,
                "ratio_course_alesage_max": ratio_course_alesage_max,
                "ratio_course_alesage_cible": ratio_course_alesage_cible,
                "taux_compression_nominal": taux_compression_nominal,
                "volume_mort_nominal_m3": volume_mort_nominal_m3,
                "contrainte_admissible_pa": contrainte_admissible_pa,
                "densite_materiau_kg_m3": densite_materiau_kg_m3,
                "cout_matiere_eur_kg": cout_matiere_eur_kg,
                "rendement_indique_cible_min": rendement_indique_cible_min,
                "rendement_mecanique_cible_min": rendement_mecanique_cible_min,
                "masse_estimee_max_kg": masse_estimee_max_kg,
                "cout_matiere_max_eur": cout_matiere_max_eur,
                "indice_maintenance_max": indice_maintenance_max,
                "duree_vie_cible_h": duree_vie_cible_h,
                "vitesse_piston_max_ms": vitesse_piston_max_ms,
                "L_max_m": longueur_dispo_m,
                "W_max_m": largeur_dispo_m,
                "architectures_autorisees": tuple(architectures_autorisees) if architectures_autorisees else None,
                "architecture_forcee": architecture_forcee,
            },
            moteur_thermique_definition,
        )
    )

    # 1) Construction des composants
    moteur_electrique = composants_def.get("moteur_electrique")
    if moteur_electrique is None:
        moteur_electrique = construire_moteur_electrique(**_safe_dict(composants_def.get("moteur_electrique_kwargs")))

    batterie = composants_def.get("batterie")
    if batterie is None:
        batterie = construire_batterie(**_safe_dict(composants_def.get("batterie_kwargs")))

    alternateur = composants_def.get("alternateur")
    if alternateur is None:
        alternateur = construire_alternateur(**_safe_dict(composants_def.get("alternateur_kwargs")))

    moteur_thermique = composants_def.get("moteur_thermique")
    rapport_construction_moteur: Dict[str, Any] = {}
    if moteur_thermique is None:
        moteur_thermique, rapport_construction_moteur = construire_moteur_thermique_complet(
            moteur_thermique_definition=definition_moteur,
            allow_definition_from_requirements=True,
        )

    boite_crabots = composants_def.get("boite_crabots")
    if boite_crabots is None and BoiteCrabots is not None:
        boite_crabots = construire_boite_crabots()

    architecture = composants_def.get("architecture")
    if architecture is None and Architecture is not None:
        architecture = construire_architecture(
            temps_moteur=int(_safe_int(definition_moteur.get("temps_moteur")) or temps_moteur),
            rendement_mecanique=float(_first_finite(definition_moteur.get("rendement_mecanique_nominal"), rendement_mecanique_cible_min) or rendement_mecanique_cible_min),
            ratio_course_alesage_max=float(_first_finite(definition_moteur.get("ratio_course_alesage_max"), ratio_course_alesage_max) or ratio_course_alesage_max),
        )

    composants = {
        "moteur_electrique": moteur_electrique,
        "batterie": batterie,
        "alternateur": alternateur,
        "moteur_thermique": moteur_thermique,
        "boite_crabots": boite_crabots,
        "architecture": architecture,
    }

    systeme = SystemeComplet(
        moteur_electrique=moteur_electrique,
        batterie=batterie,
        alternateur=alternateur,
        moteur_thermique=moteur_thermique,
        boite_crabots=boite_crabots,
        architecture=architecture,
    )

    # 2) Analyse du système complet
    puissance_charge_kw = 20.0 if charger_batterie else 0.0
    analyse_systeme = {
        "masse_kg": masse_kg,
        "vitesse_ms": vitesse_ms,
        "acceleration_ms2": acceleration_ms2,
        "angle_pente": angle_pente,
        "angle_unite": angle_unite,
        "coef_roulement": coef_roulement,
        "coef_trainee_aero_cda": coef_trainee_aero_cda,
        "rayon_roue_m": rayon_roue_m,
        "rapport_reduction_global": rapport_reduction_global,
        "rendement_transmission": rendement_transmission,
        "nb_roues_motrices": nb_roues_motrices,
        "nb_moteurs_electriques": nb_moteurs_electriques,
        "pertes_fixes_transmission_w": pertes_fixes_transmission_w,
        "couple_pertes_transmission_nm": couple_pertes_transmission_nm,
        "marge_puissance": marge_puissance,
        "marge_couple": marge_couple,
        "puissance_auxiliaire_w": puissance_auxiliaire_w,
        "distance_km": distance_km,
        "conso_kwh_km": conso_kwh_km,
        "puissance_moyenne_kw": p_trac_kw,
        "vitesse_moyenne_kmh": vitesse_moyenne_kmh,
        "temps_charge_cible_h": temps_charge_cible_h,
        "puissance_pic_kw": puissance_pic_kw if puissance_pic_kw is not None else p_trac_kw,
        "duree_pic_s": duree_pic_s,
        "energie_utile_imposee_kwh": energie_utile_imposee_kwh,
        "calculer_puissance_charge_requise": charger_batterie,
        "scenario_bus_dc": scenario_bus_dc if scenario_bus_dc else ("traction_plus_charge" if charger_batterie else "traction"),
        "tension_bus_dc_v": tension_bus_dc_v,
        "vitesse_moteur_thermique_rpm": _first_finite(definition_moteur.get("rpm_nominal"), vitesse_moteur_thermique_rpm),
        "rapport_vitesse_alt_sur_moteur": rapport_vitesse_alt_sur_moteur,
        "puissance_elec_alt_cible_w": (puissance_charge_kw * 1000.0) if charger_batterie else None,
        "tension_alt_v": tension_alt_v,
        "courant_alt_a": courant_alt_a,
        "facteur_puissance_alt": facteur_puissance_alt,
        "courant_est_ligne": courant_est_ligne,
        "rendement_liaison_meca_alt": rendement_liaison_meca_alt,
        "rapports_boite_candidates": rapports_boite_candidates,
        "rendement_boite": rendement_boite,
        "facteur_service_boite": facteur_service_boite,
        "moment_flechissant_nm": moment_flechissant_nm,
        "inertie_primaire_kg_m2": inertie_primaire_kg_m2,
        "inertie_secondaire_kg_m2": inertie_secondaire_kg_m2,
        "delta_omega_rad_s": delta_omega_rad_s,
        "temps_engagement_s": temps_engagement_s,
        "force_axiale_roulement_N": force_axiale_roulement_N,
        "force_radiale_roulement_N": force_radiale_roulement_N,
        "pme_pa": _first_finite(definition_moteur.get("pme_pa"), pme_pa),
        "vitesse_piston_max_ms": vitesse_piston_max_ms,
        "longueur_dispo_m": longueur_dispo_m,
        "largeur_dispo_m": largeur_dispo_m,
        "horizon_usage_h": horizon_usage_h,
        "architectures_autorisees": tuple(architectures_autorisees) if architectures_autorisees else None,
        "architecture_forcee": architecture_forcee,
        "poids_maintenance": poids_maintenance,
        "poids_masse": poids_masse,
        "poids_cout_matiere": poids_cout_matiere,
        "poids_compacite": poids_compacite,
        "poids_fiabilite": poids_fiabilite,
        "poids_rendement": poids_rendement,
        "pression_max_pa": _first_finite(definition_moteur.get("pression_max_pa"), pression_max_pa),
        "contrainte_admissible_pa": contrainte_admissible_pa,
        "densite_materiau_kg_m3": densite_materiau_kg_m3,
        "cout_matiere_eur_kg": cout_matiere_eur_kg,
        "rendement_indique_cible_min": rendement_indique_cible_min,
        "rendement_mecanique_cible_min": rendement_mecanique_cible_min,
        "masse_estimee_max_kg": masse_estimee_max_kg,
        "cout_matiere_max_eur": cout_matiere_max_eur,
        "indice_maintenance_max": indice_maintenance_max,
        "duree_vie_cible_h": duree_vie_cible_h,
    }
    rapport_systeme = systeme.analyser(**_filter_kwargs_for_callable(systeme.analyser, analyse_systeme))

    # réinjecte la définition moteur dans le rapport système
    rapport_systeme.setdefault("entrees", {})
    rapport_systeme["entrees"]["definition_moteur_thermique"] = _to_jsonable(definition_moteur)
    rapport_systeme.setdefault("synthese", {})
    rapport_systeme["synthese"]["moteur_thermique"] = _merge_dict_non_none(
        _safe_dict(rapport_systeme["synthese"].get("moteur_thermique")),
        definition_moteur,
    )

    # 3) Pièces + analyses détaillées
    approx_auto = bool(autoriser_approximations_geom)
    if (not approx_auto) and not pieces_definition:
        mode_constr = str(rapport_construction_moteur.get("mode_construction") or "")
        if mode_constr == "definir_depuis_exigences":
            approx_auto = True
            _append_note(rapport_global, "Approximations géométriques secondaires activées automatiquement pour maximiser les rapports pièces à partir de la puissance seule.")

    pieces, rapport_construction_pieces = construire_pieces_depuis_systeme(
        rapport_systeme=rapport_systeme,
        definition_moteur_thermique=definition_moteur,
        pieces_definition=pieces_definition,
        moteur_thermique_obj=moteur_thermique,
        systeme_obj=systeme,
        autoriser_approximations_geom=approx_auto,
    )
    rapports_pieces = analyser_pieces(pieces)

    # 4) Analyses complémentaires composants
    rapports_composants = analyser_composants_complementaires(
        systeme_obj=systeme,
        composants=composants,
        definition_moteur=definition_moteur,
        rapport_systeme=rapport_systeme,
        analyses_complementaires=analyses_complementaires,
        pieces=pieces,
    )
    if rapport_construction_moteur:
        rapports_composants["construction_moteur_thermique"] = rapport_construction_moteur

    # 4bis) Descriptions exhaustives objets
    ctx = _build_common_analysis_context(
        systeme_obj=systeme,
        rapport_systeme=rapport_systeme,
        definition_moteur=definition_moteur,
        composants=composants,
        pieces=pieces,
        analyses_complementaires=rapports_composants,
    )
    toutes_les_donnees_pieces = analyser_pieces_exhaustif(
        pieces=pieces,
        context=ctx,
        rapport_construction_pieces=rapport_construction_pieces,
        rapports_pieces=rapports_pieces,
    )
    toutes_les_donnees_composants = decrire_composants_exhaustif(
        composants=composants,
        context=ctx,
        analyses_composants=rapports_composants,
    )
    donnees_systeme_exhaustif = {
        "systeme_obj": _decrire_objet(systeme, ctx),
        "rapport_systeme": _to_jsonable(rapport_systeme),
    }

    # 5) Optimisation inter-pièces
    rapport_optimisation: Dict[str, Any]
    if OptimisationSysteme is not None:
        try:
            optimiseur = OptimisationSysteme(
                systeme_complet=systeme,
                moteur_thermique=moteur_thermique,
                cylindre=pieces.get("cylindre"),
                piston=pieces.get("piston"),
                joint_piston=pieces.get("joint_piston"),
                deplaceur=pieces.get("deplaceur"),
                joint_deplaceur=pieces.get("joint_deplaceur"),
                bielle=pieces.get("bielle"),
                arbre_piston=pieces.get("arbre_piston"),
                coussinet_arbre_piston=pieces.get("coussinet_arbre_piston"),
                arbre_vilebrequin=pieces.get("arbre_vilebrequin"),
                vilbrequin=pieces.get("vilbrequin"),
                roulement_aiguille_arbre=pieces.get("roulement_aiguille_arbre"),
                roulement_aiguille_arbre_vilebrequin=pieces.get("roulement_aiguille_arbre_vilebrequin"),
                couvercle_cylindre=pieces.get("couvercle_cylindre"),
                vis_couvercle_cylindre=pieces.get("vis_couvercle_cylindre"),
                arbre=pieces.get("arbre"),
                clavette_arbre=pieces.get("clavette_arbre"),
            )
            rapport_optimisation = optimiseur.analyser()
        except Exception as exc:
            rapport_optimisation = {"erreur": str(exc)}
    else:
        rapport_optimisation = {"note": "OptimisationSysteme indisponible."}

    # 6) Pipeline STHO_ME secondaire
    rapport_stho_me: Dict[str, Any]
    if lancer_stho_me_secondaire and STHO_ME is not None:
        try:
            config_stho = construire_config_stho_me(
                composants=composants,
                pieces_definition=pieces_definition,
                definition_moteur=definition_moteur,
                analyse_systeme=analyse_systeme,
                analyses_complementaires=analyses_complementaires,
            )
            rapport_stho_me = STHO_ME.depuis_config(config_stho).analyser()
        except Exception as exc:
            rapport_stho_me = {"erreur": str(exc)}
    else:
        rapport_stho_me = {"note": "Pipeline STHO_ME non lancé."}

    # 7) Pipeline legacy
    legacy: Dict[str, Any] = {}
    if lancer_pipeline_legacy and callable(dimensionner_pieces_completes):
        try:
            mt_syn = _safe_dict(_safe_dict(rapport_systeme.get("synthese")).get("moteur_thermique"))
            legacy["dimensionner_pieces_completes"] = dimensionner_pieces_completes(
                puissance_cible_w=mt_syn.get("puissance_requise_W"),
                regime_tr_min=mt_syn.get("rpm_nominal"),
                n_cyl=mt_syn.get("nombre_cylindres"),
                pression_max_pa=pression_max_pa,
            )
        except Exception as exc:
            legacy["dimensionner_pieces_completes_erreur"] = str(exc)

    if lancer_pipeline_legacy and DriveChainGenerator is not None:
        try:
            gen = DriveChainGenerator()
            gen.compute(p_trac_kw)
            legacy["drivechain"] = _to_jsonable(getattr(gen, "results", None))
        except Exception as exc:
            legacy["drivechain_erreur"] = str(exc)

    # 8) Fusion des inconnues / alertes
    for source in (
        rapport_construction_pieces,
        rapport_systeme,
        rapports_composants,
        rapports_pieces,
        rapport_optimisation,
        rapport_stho_me,
    ):
        if isinstance(source, dict):
            for cat, items in _safe_dict(source.get("inconnues")).items():
                for item in list(items or []):
                    if isinstance(item, dict):
                        _push_inconnue(rapport_global, cat, item.get("nom", "?"), item.get("raison", ""))
            for cat, items in _safe_dict(source.get("alertes")).items():
                for item in list(items or []):
                    if isinstance(item, dict):
                        _push_warning(rapport_global, cat, item.get("nom", "?"), item.get("detail", ""))
            for note in list(source.get("notes_modele", []) or []):
                _append_note(rapport_global, str(note))

    _dedup_report_lists(rapport_global)

    # 9) Inventaire / synthèse
    inventaire = {
        "composants": {
            nom: {
                "type": None if obj is None else type(obj).__name__,
                "construit": obj is not None,
            }
            for nom, obj in composants.items()
        },
        "pieces": {
            nom: {
                "type": None if obj is None else type(obj).__name__,
                "construit": obj is not None,
                "rapport_disponible": isinstance(rapports_pieces.get(nom), dict),
            }
            for nom, obj in pieces.items()
        },
    }

    synth = _safe_dict(rapport_systeme.get("synthese"))
    mt_syn = _safe_dict(synth.get("moteur_thermique"))
    veh_syn = _safe_dict(synth.get("vehicule"))
    batt_syn = _safe_dict(synth.get("batterie"))
    opt_syn = _safe_dict(rapport_optimisation.get("synthese_optimisation"))

    resume_gui = {
        "N_cyl": mt_syn.get("nombre_cylindres"),
        "Architecture": mt_syn.get("architecture"),
        "Bore_mm": (_safe_float(mt_syn.get("alesage_m")) or 0.0) * 1000.0 if _is_finite(mt_syn.get("alesage_m")) else None,
        "Stroke_mm": (_safe_float(mt_syn.get("course_m")) or 0.0) * 1000.0 if _is_finite(mt_syn.get("course_m")) else None,
        "RPM": mt_syn.get("rpm_nominal"),
        "PME_Pa": mt_syn.get("pme_pa"),
        "Pmax_Pa": mt_syn.get("pression_max_pa"),
        "Couple_max_Nm": _first_non_none(mt_syn.get("couple_max_Nm"), mt_syn.get("couple_requis_Nm")),
        "Force_bielle_N": _first_non_none(mt_syn.get("force_bielle_N"), definition_moteur.get("force_bielle_N")),
        "vd_tot_cc": _first_non_none(mt_syn.get("cylindree_totale_cc"), definition_moteur.get("cylindree_totale_cc")),
        "P_bus_dc_design_w": veh_syn.get("puissance_bus_dc_design_w"),
        "energie_batterie_kwh": batt_syn.get("energie_utile_kwh"),
        "score_coherence_100": opt_syn.get("score_coherence_100"),
        "score_global_100": opt_syn.get("score_global_100"),
        "mode_definition_moteur": rapport_construction_moteur.get("mode_construction"),
        "nb_pieces_construites": sum(1 for obj in pieces.values() if obj is not None),
        "nb_alertes": sum(len(v) for v in _safe_dict(rapport_global.get("alertes")).values()),
        "nb_inconnues": sum(len(v) for v in _safe_dict(rapport_global.get("inconnues")).values()),
    }

    resultat = {
        "meta": _merge_dict_non_none(
            rapport_global.get("meta"),
            {
                "version": "3.0.0",
                "modele": "orchestrateur principal SHSE-M",
            },
        ),
        "entrees": {
            "puissance_traction_kw": p_trac_kw,
            "definition_moteur_thermique": definition_moteur,
            "analyse_systeme": analyse_systeme,
            "pieces_definition": _safe_dict(pieces_definition),
            "analyses_complementaires": _safe_dict(analyses_complementaires),
            "autoriser_approximations_geom": approx_auto,
        },
        "inventaire": inventaire,
        "resume_gui": resume_gui,
        "systeme_complet": rapport_systeme,
        "analyses_composants": rapports_composants,
        "construction_pieces": rapport_construction_pieces,
        "rapports_pieces": rapports_pieces,
        "toutes_les_donnees_composants": toutes_les_donnees_composants,
        "toutes_les_donnees_pieces": toutes_les_donnees_pieces,
        "toutes_les_donnees_systeme": donnees_systeme_exhaustif,
        "optimisation": rapport_optimisation,
        "stho_me_secondaire": rapport_stho_me,
        "legacy": legacy,
        "objets_serialises": {
            "composants": {nom: _to_jsonable(obj) for nom, obj in composants.items()},
            "pieces": {nom: _to_jsonable(obj) for nom, obj in pieces.items()},
            "systeme": _to_jsonable(systeme),
        },
        "inconnues": rapport_global.get("inconnues"),
        "alertes": rapport_global.get("alertes"),
        "notes_modele": rapport_global.get("notes_modele"),
        "synthese": {
            "systeme": synth,
            "moteur_thermique": mt_syn,
            "optimisation": opt_syn,
            "inventaire": inventaire,
        },
    }
    return resultat


# Alias lisibles
realiser_systeme_complet = dimensionner_systeme_shsem
concevoir_systeme_complet = dimensionner_systeme_shsem


# =============================================================================
# Export / console
# =============================================================================


def exporter_rapport_json(rapport: Mapping[str, Any], path: str | os.PathLike[str], *, indent: int = 2) -> str:
    out = Path(path)
    out.write_text(json.dumps(_to_jsonable(dict(rapport)), ensure_ascii=False, indent=indent), encoding="utf-8")
    return str(out)



def realiser_systeme_et_exporter_json(path_json: str | os.PathLike[str], *args: Any, **kwargs: Any) -> Dict[str, Any]:
    rapport = dimensionner_systeme_shsem(*args, **kwargs)
    exporter_rapport_json(rapport, path_json)
    return rapport



def _print_resume_console(config: Dict[str, Any]) -> None:
    gui = _safe_dict(config.get("resume_gui"))
    print("=== DIMENSIONNEMENT SYSTÈME SHSE-M ===")
    print(f"Architecture   : {gui.get('Architecture')}")
    print(f"N cylindres    : {gui.get('N_cyl')}")
    print(f"Alésage        : {gui.get('Bore_mm')} mm")
    print(f"Course         : {gui.get('Stroke_mm')} mm")
    print(f"Régime         : {gui.get('RPM')} rpm")
    print(f"PME            : {gui.get('PME_Pa')} Pa")
    print(f"Pmax           : {gui.get('Pmax_Pa')} Pa")
    print(f"Couple max     : {gui.get('Couple_max_Nm')} Nm")
    print(f"Force bielle   : {gui.get('Force_bielle_N')} N")
    print(f"Cylindrée      : {gui.get('vd_tot_cc')} cc")
    print(f"Bus DC design  : {gui.get('P_bus_dc_design_w')} W")
    print(f"Batterie utile : {gui.get('energie_batterie_kwh')} kWh")
    print(f"Mode moteur    : {gui.get('mode_definition_moteur')}")
    print(f"Score cohérence: {gui.get('score_coherence_100')}")
    print(f"Score global   : {gui.get('score_global_100')}")
    print(f"Pièces constr. : {gui.get('nb_pieces_construites')}")
    print(f"Alertes        : {gui.get('nb_alertes')}")
    print(f"Inconnues      : {gui.get('nb_inconnues')}")


if __name__ == "__main__":
    puissance_kw = 40.0
    if len(sys.argv) > 1:
        try:
            puissance_kw = float(sys.argv[1])
        except ValueError:
            pass

    rep = dimensionner_systeme_shsem(
        puissance_traction_kw=puissance_kw,
        charger_batterie=True,
        temps_charge_cible_h=1.0,
        vitesse_moteur_thermique_rpm=3000.0,
        rapport_vitesse_alt_sur_moteur=2.0,
        pme_pa=8.0e5,
        vitesse_piston_max_ms=10.0,
        longueur_dispo_m=1.2,
        largeur_dispo_m=0.8,
        pression_max_pa=3.0e6,
        contrainte_admissible_pa=1.2e8,
        densite_materiau_kg_m3=7800.0,
        cout_matiere_eur_kg=2.0,
        rendement_mecanique_cible_min=0.80,
        moteur_thermique_definition={
            "temps_moteur": 4,
            "nombre_cylindres": 1,
            "architecture": "mono",
            "rpm_nominal": 3000.0,
            "pme_pa": 8.0e5,
            "pression_max_pa": 3.0e6,
            "carburant": "essence",
        },
        pieces_definition={},
        lancer_pipeline_legacy=False,
    )
    _print_resume_console(rep)
