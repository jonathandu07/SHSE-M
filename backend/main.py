# backend/main.py
from __future__ import annotations

import inspect
import json
import math
import os
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


# =============================================================================
# Préparation du chemin projet
# =============================================================================

_THIS_FILE = Path(__file__).resolve()
_THIS_DIR = _THIS_FILE.parent
for candidate in (_THIS_DIR, _THIS_DIR.parent, _THIS_DIR.parent.parent, Path.cwd()):
    if str(candidate) not in sys.path:
        sys.path.append(str(candidate))


# =============================================================================
# Imports robustes
# =============================================================================


def _import_attr(module_names: Sequence[str], attr: str, default: Any = None) -> Any:
    last_error: Optional[Exception] = None
    for module_name in module_names:
        try:
            module = __import__(module_name, fromlist=[attr])
            return getattr(module, attr)
        except Exception as exc:
            last_error = exc
    return default if default is not None or last_error is not None else default


SystemeComplet = _import_attr(("backend.ensemble.systeme_complet", "systeme_complet"), "SystemeComplet", default=None)
OptimisationSysteme = _import_attr(("backend.ensemble.optimisation", "optimisation"), "OptimisationSysteme", default=None)
STHO_ME = _import_attr(("backend.ensemble.STHO_ME", "STHO_ME"), "STHO_ME", default=None)

MoteurElectrique = _import_attr(("backend.components.moteur_electrique", "moteur_electrique"), "MoteurElectrique", default=None)
AnalyserMoteurElectriqueDepuisPuissance = _import_attr(("backend.components.moteur_electrique", "moteur_electrique"), "analyser_depuis_puissance", default=None)
Batterie = _import_attr(("backend.components.batterie", "batterie"), "Batterie", default=None)
Alternateur = _import_attr(("backend.components.alternateur", "alternateur"), "Alternateur", default=None)
MoteurThermique = _import_attr(("backend.components.moteur_thermique", "moteur_thermique"), "MoteurThermique", default=None)
BoiteCrabots = _import_attr(("backend.components.boite_crabots", "boite_crabots"), "BoiteCrabots", default=None)
Architecture = _import_attr(("backend.components.architecture", "architecture"), "Architecture", default=None)

Cylindre = _import_attr(("backend.pieces.cylindre", "cylindre"), "Cylindre", default=None)
Piston = _import_attr(("backend.pieces.piston", "piston"), "Piston", default=None)
JointPiston = _import_attr(("backend.pieces.joint_piston", "joint_piston"), "JointPiston", default=None)
CorpsBielle = _import_attr(("backend.pieces.bielle", "bielle"), "CorpsBielle", default=None)
ArbrePiston = _import_attr(("backend.pieces.arbre_piston", "arbre_piston"), "ArbrePiston", default=None)
CoussinetArbrePiston = _import_attr(("backend.pieces.coussinet_arbre_piston", "coussinet_arbre_piston"), "CoussinetArbrePiston", default=None)
ArbreVilbrequin = _import_attr(("backend.pieces.arbre_vilbrequin", "arbre_vilbrequin"), "ArbreVilbrequin", default=None)
Vilbrequin = _import_attr(("backend.pieces.vilbrequin", "vilbrequin"), "Vilbrequin", default=None)
RoulementAiguilleArbre = _import_attr(("backend.pieces.roulement_aiguille_arbre", "roulement_aiguille_arbre"), "RoulementAiguilleArbre", default=None)
RoulementAiguilleArbreVilebrequin = _import_attr(("backend.pieces.roulement_aiguille_arbre_vilebrequin", "roulement_aiguille_arbre_vilebrequin"), "RoulementAiguilleArbreVilebrequin", default=None)
CouvercleCylindre = _import_attr(("backend.pieces.couvercle_cylindre", "couvercle_cylindre"), "CouvercleCylindre", default=None)
VisCouvercleCylindre = _import_attr(("backend.pieces.vis_couvercle_cylindre", "vis_couvercle_cylindre"), "VisCouvercleCylindre", default=None)
Deplaceur = _import_attr(("backend.pieces.deplaceur", "deplaceur"), "Deplaceur", default=None)
JointDeplaceur = _import_attr(("backend.pieces.joint_deplaceur", "joint_deplaceur"), "JointDeplaceur", default=None)
ArbreMoteur = _import_attr(("backend.pieces.arbre", "arbre"), "ArbreMoteur", default=None)
if ArbreMoteur is None:
    ArbreMoteur = _import_attr(("backend.pieces.arbre", "arbre"), "Arbre", default=None)
ClavetteArbre = _import_attr(("backend.pieces.clavette_arbre", "clavette_arbre"), "ClavetteArbre", default=None)

try:
    from backend.definition_pieces import dimensionner_pieces_completes  # type: ignore
except Exception:
    dimensionner_pieces_completes = None  # type: ignore

try:
    from backend.system_generator import DriveChainGenerator  # type: ignore
except Exception:
    DriveChainGenerator = None  # type: ignore


# =============================================================================
# Helpers
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
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": str(nom), "raison": str(raison)})


def _push_warning(rapport: Dict[str, Any], categorie: str, nom: str, detail: str) -> None:
    rapport.setdefault("alertes", {}).setdefault(categorie, []).append({"nom": str(nom), "detail": str(detail)})


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
            raw = {k: v for k, v in vars(value).items() if not k.startswith("_") and not callable(v)}
            return {"type": type(value).__name__, "attributs": _to_jsonable(raw, depth=depth + 1, max_depth=max_depth)}
        except Exception:
            pass
    return {"type": type(value).__name__}


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


def _required_params_for_callable(callable_obj: Any) -> Sequence[str]:
    try:
        sig = inspect.signature(callable_obj)
    except Exception:
        return ()
    required = []
    for name, p in sig.parameters.items():
        if name == "self":
            continue
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if p.default is inspect._empty:
            required.append(name)
    return tuple(required)


def _collect_public_data(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {"type": None}
    data: Dict[str, Any] = {"type": type(obj).__name__}
    try:
        attrs = {k: v for k, v in vars(obj).items() if not k.startswith("_") and not callable(v)}
        data["attributs"] = _to_jsonable(attrs)
    except Exception:
        data["attributs"] = {}
    methods: Dict[str, Any] = {}
    for name in (
        "analyser",
        "calculer",
        "analyser_dimensionnement",
        "analyser_pour_bus_dc",
        "analyser_point_de_fonctionnement",
        "analyser_geometrie_definition",
        "analyser_cycle_mecanique",
        "analyser_bilan_carburant",
        "analyser_point",
        "analyser_chaine_moteur_alternateur",
    ):
        fn = getattr(obj, name, None)
        if callable(fn):
            try:
                methods[name] = str(inspect.signature(fn))
            except Exception:
                methods[name] = "signature_indisponible"
    data["methodes"] = methods
    return data


def _safe_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    for name in (
        "analyser",
        "calculer",
        "analyser_dimensionnement",
        "analyser_pour_bus_dc",
        "analyser_point_de_fonctionnement",
        "analyser_geometrie_definition",
        "analyser_cycle_mecanique",
        "analyser_bilan_carburant",
        "analyser_point",
        "analyser_chaine_moteur_alternateur",
    ):
        fn = getattr(obj, name, None)
        if not callable(fn):
            continue
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
    if d.get("puissance_requise_W") is None and d.get("puissance_nominale_visee_w") is not None:
        d["puissance_requise_W"] = d["puissance_nominale_visee_w"]

    # dérivés exacts seulement si toutes les données nécessaires existent
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
        d.setdefault("vitesse_piston_moyenne_ms", 2.0 * course_m * rpm_nominal / 60.0)
    if couple_nm is None and puissance_w is not None and rpm_nominal is not None and rpm_nominal > 0.0:
        omega = 2.0 * math.pi * rpm_nominal / 60.0
        if omega > 0.0:
            couple_nm = puissance_w / omega
            d.setdefault("couple_max_Nm", couple_nm)
            d.setdefault("couple_requis_Nm", couple_nm)
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
        "architecture_forcee": _first_non_none(definition.get("architecture_forcee"), definition.get("architecture")),
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


# =============================================================================
# Construction stricte des composants
# =============================================================================


def _build_component_instance(component_cls: Any, kwargs: Optional[Dict[str, Any]], rapport: Dict[str, Any], nom: str) -> Any:
    if component_cls is None:
        _push_inconnue(rapport, "impossibles", nom, f"Classe {nom} indisponible.")
        return None
    raw = _safe_dict(kwargs)
    ctor_kwargs = _filter_kwargs_for_callable(component_cls, raw)
    required = [p for p in _required_params_for_callable(component_cls) if p not in ctor_kwargs]
    if required:
        _push_inconnue(rapport, "impossibles", nom, f"Impossible de construire {nom} sans {required}.")
        return None
    try:
        return component_cls(**ctor_kwargs)
    except Exception as exc:
        _push_inconnue(rapport, "impossibles", nom, str(exc))
        return None


def construire_moteur_thermique_complet(*, moteur_thermique_definition: Optional[Dict[str, Any]], rapport: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
    if MoteurThermique is None:
        _push_inconnue(rapport, "impossibles", "moteur_thermique", "Classe MoteurThermique indisponible.")
        return None, {"erreur": "classe indisponible"}
    definition = _normaliser_definition_moteur_thermique(moteur_thermique_definition)
    r: Dict[str, Any] = {"definition_utilisee": definition, "mode_construction": None, "rapport_definition_exigences": None}

    has_direct_geometry = _safe_float(definition.get("alesage_m")) is not None and _safe_float(definition.get("course_m")) is not None
    if has_direct_geometry:
        ctor_kwargs = _filter_kwargs_for_callable(MoteurThermique, definition)
        try:
            moteur = MoteurThermique(**ctor_kwargs)
            r["mode_construction"] = "direct"
            return moteur, r
        except Exception as exc:
            _push_inconnue(rapport, "impossibles", "moteur_thermique_direct", str(exc))

    if hasattr(MoteurThermique, "definir_depuis_exigences"):
        kwargs_req = _filter_kwargs_for_callable(MoteurThermique.definir_depuis_exigences, _definition_moteur_pour_exigences(definition))
        try:
            rapport_def = MoteurThermique.definir_depuis_exigences(**kwargs_req)
            r["rapport_definition_exigences"] = rapport_def
            moteur = _get_nested(rapport_def, "moteur_defini")
            if moteur is not None:
                r["mode_construction"] = "definir_depuis_exigences"
                return moteur, r
            for cat, items in _safe_dict(rapport_def.get("inconnues")).items():
                for item in items:
                    if isinstance(item, dict):
                        _push_inconnue(rapport, cat, item.get("nom", "moteur_thermique"), item.get("raison", ""))
        except Exception as exc:
            _push_inconnue(rapport, "impossibles", "moteur_thermique_definir_depuis_exigences", str(exc))

    # tentative minimale seulement si on a au moins un paramètre explicite
    ctor_kwargs = _filter_kwargs_for_callable(MoteurThermique, definition)
    if ctor_kwargs:
        try:
            moteur = MoteurThermique(**ctor_kwargs)
            r["mode_construction"] = "minimal"
            return moteur, r
        except Exception as exc:
            _push_inconnue(rapport, "impossibles", "moteur_thermique_minimal", str(exc))

    _push_inconnue(rapport, "impossibles", "moteur_thermique", "Aucune géométrie directe suffisante ni définition par exigences calculable.")
    return None, r


# =============================================================================
# Construction des pièces (sans approximation imposée par main)
# =============================================================================


def _build_piece_instance(piece_cls: Any, raw_kwargs: Dict[str, Any], rapport: Dict[str, Any], nom: str) -> Any:
    if piece_cls is None:
        _push_inconnue(rapport, "impossibles", nom, f"Classe indisponible pour {nom}.")
        return None
    kwargs = _filter_kwargs_for_callable(piece_cls, raw_kwargs)
    required = [p for p in _required_params_for_callable(piece_cls) if p not in kwargs]
    if required:
        _push_inconnue(rapport, "partielles", nom, f"Construction impossible sans {required}.")
        return None
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
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    synth = _safe_dict(rapport_systeme.get("synthese"))
    mt_systeme = _safe_dict(synth.get("moteur_thermique"))
    definition_mt = _normaliser_definition_moteur_thermique(definition_moteur_thermique)
    mt = _merge_dict_non_none(mt_systeme, definition_mt)
    pieces_def = _safe_dict(pieces_definition)

    rapport: Dict[str, Any] = {
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

    pieces: Dict[str, Any] = {}

    raw = _merge_dict_non_none({
        "alesage_m": alesage_m,
        "course_m": course_m,
        "longueur_utile_m": _get_nested(pieces_def, "cylindre", "longueur_utile_m"),
        "pression_service_pa": pme_pa,
        "pression_max_pa": pression_max_pa,
        "materiau_cle": _get_nested(pieces_def, "cylindre", "materiau_cle"),
    }, _safe_dict(pieces_def.get("cylindre")))
    pieces["cylindre"] = _build_piece_instance(Cylindre, raw, rapport, "cylindre")
    rapport["construction"]["cylindre"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("cylindre") is not None}

    raw = _merge_dict_non_none({
        "cylindre": pieces.get("cylindre"),
        "materiau_piston_cle": _get_nested(pieces_def, "piston", "materiau_piston_cle"),
        "pression_max_pa": pression_max_pa,
        "alesage_nominal_m": alesage_m,
        "course_m": course_m,
        "rpm": rpm,
        "materiau_joint_cle": _get_nested(pieces_def, "piston", "materiau_joint_cle"),
    }, _safe_dict(pieces_def.get("piston")))
    pieces["piston"] = _build_piece_instance(Piston, raw, rapport, "piston")
    rapport["construction"]["piston"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("piston") is not None}

    raw = _merge_dict_non_none({
        "piston": pieces.get("piston"),
        "cylindre": pieces.get("cylindre"),
        "materiau_joint_cle": _get_nested(pieces_def, "joint_piston", "materiau_joint_cle"),
    }, _safe_dict(pieces_def.get("joint_piston")))
    pieces["joint_piston"] = _build_piece_instance(JointPiston, raw, rapport, "joint_piston")
    rapport["construction"]["joint_piston"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("joint_piston") is not None}

    raw = _merge_dict_non_none({
        "piston": pieces.get("piston"),
        "cylindre": pieces.get("cylindre"),
        "rpm": rpm,
        "materiau_cle": _get_nested(pieces_def, "arbre_piston", "materiau_cle"),
    }, _safe_dict(pieces_def.get("arbre_piston")))
    pieces["arbre_piston"] = _build_piece_instance(ArbrePiston, raw, rapport, "arbre_piston")
    rapport["construction"]["arbre_piston"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("arbre_piston") is not None}

    raw = _merge_dict_non_none({
        "piston": pieces.get("piston"),
        "arbre_piston": pieces.get("arbre_piston"),
        "cylindre": pieces.get("cylindre"),
        "moteur_thermique": moteur_thermique_obj if moteur_thermique_obj is not None else mt,
        "longueur_bielle_m": _first_finite(_get_nested(pieces_def, "bielle", "longueur_bielle_m"), definition_mt.get("longueur_bielle_m")),
        "force_axiale_max_N": force_bielle_N,
        "materiau_cle": _get_nested(pieces_def, "bielle", "materiau_cle"),
    }, _safe_dict(pieces_def.get("bielle")))
    pieces["bielle"] = _build_piece_instance(CorpsBielle, raw, rapport, "bielle")
    rapport["construction"]["bielle"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("bielle") is not None}

    raw = _merge_dict_non_none({
        "arbre_piston": pieces.get("arbre_piston"),
        "rpm": rpm,
        "materiau_coussinet": _get_nested(pieces_def, "coussinet_arbre_piston", "materiau_coussinet"),
    }, _safe_dict(pieces_def.get("coussinet_arbre_piston")))
    pieces["coussinet_arbre_piston"] = _build_piece_instance(CoussinetArbrePiston, raw, rapport, "coussinet_arbre_piston")
    rapport["construction"]["coussinet_arbre_piston"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("coussinet_arbre_piston") is not None}

    raw = _merge_dict_non_none({
        "cylindre": pieces.get("cylindre"),
        "piston": pieces.get("piston"),
        "bielle": pieces.get("bielle"),
        "moteur_thermique": moteur_thermique_obj,
        "rpm": rpm,
        "couple_max_Nm": couple_max_nm,
        "course_m": course_m,
        "force_bielle_effective_N": force_bielle_N,
        "materiau_cle": _get_nested(pieces_def, "arbre_vilebrequin", "materiau_cle"),
    }, _safe_dict(pieces_def.get("arbre_vilebrequin")))
    pieces["arbre_vilebrequin"] = _build_piece_instance(ArbreVilbrequin, raw, rapport, "arbre_vilebrequin")
    rapport["construction"]["arbre_vilebrequin"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("arbre_vilebrequin") is not None}

    raw = _merge_dict_non_none({
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
        "materiau_cle": _get_nested(pieces_def, "vilbrequin", "materiau_cle"),
    }, _safe_dict(pieces_def.get("vilbrequin")))
    pieces["vilbrequin"] = _build_piece_instance(Vilbrequin, raw, rapport, "vilbrequin")
    rapport["construction"]["vilbrequin"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("vilbrequin") is not None}

    raw = _merge_dict_non_none({
        "vilbrequin": pieces.get("vilbrequin"),
        "arbre_vilbrequin": pieces.get("arbre_vilebrequin"),
        "bielle": pieces.get("bielle"),
        "piston": pieces.get("piston"),
        "cylindre": pieces.get("cylindre"),
        "rpm": rpm,
        "couple_max_Nm": couple_max_nm,
        "rayon_manivelle_m": (0.5 * course_m) if _is_finite(course_m) else None,
    }, _safe_dict(pieces_def.get("roulement_aiguille_arbre")))
    pieces["roulement_aiguille_arbre"] = _build_piece_instance(RoulementAiguilleArbre, raw, rapport, "roulement_aiguille_arbre")
    rapport["construction"]["roulement_aiguille_arbre"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("roulement_aiguille_arbre") is not None}

    raw = _merge_dict_non_none({
        "corps_bielle": pieces.get("bielle"),
        "arbre_vilebrequin": pieces.get("arbre_vilebrequin"),
        "moteur_thermique": moteur_thermique_obj,
        "rpm_vilebrequin": rpm,
    }, _safe_dict(pieces_def.get("roulement_aiguille_arbre_vilebrequin")))
    pieces["roulement_aiguille_arbre_vilebrequin"] = _build_piece_instance(RoulementAiguilleArbreVilebrequin, raw, rapport, "roulement_aiguille_arbre_vilebrequin")
    rapport["construction"]["roulement_aiguille_arbre_vilebrequin"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("roulement_aiguille_arbre_vilebrequin") is not None}

    raw = _merge_dict_non_none({
        "cylindre": pieces.get("cylindre"),
        "pression_max_pa": pression_max_pa,
        "materiau_cle": _get_nested(pieces_def, "couvercle_cylindre", "materiau_cle"),
    }, _safe_dict(pieces_def.get("couvercle_cylindre")))
    pieces["couvercle_cylindre"] = _build_piece_instance(CouvercleCylindre, raw, rapport, "couvercle_cylindre")
    rapport["construction"]["couvercle_cylindre"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("couvercle_cylindre") is not None}

    raw = _merge_dict_non_none({
        "cylindre": pieces.get("cylindre"),
        "couvercle": pieces.get("couvercle_cylindre"),
        "pression_max_pa": pression_max_pa,
        "classe_vis_iso898": _get_nested(pieces_def, "vis_couvercle_cylindre", "classe_vis_iso898"),
    }, _safe_dict(pieces_def.get("vis_couvercle_cylindre")))
    pieces["vis_couvercle_cylindre"] = _build_piece_instance(VisCouvercleCylindre, raw, rapport, "vis_couvercle_cylindre")
    rapport["construction"]["vis_couvercle_cylindre"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("vis_couvercle_cylindre") is not None}

    raw = _merge_dict_non_none({
        "cylindre": pieces.get("cylindre"),
        "pression_froid_pa": pression_max_pa,
        "materiau_cle": _get_nested(pieces_def, "deplaceur", "materiau_cle"),
    }, _safe_dict(pieces_def.get("deplaceur")))
    pieces["deplaceur"] = _build_piece_instance(Deplaceur, raw, rapport, "deplaceur")
    rapport["construction"]["deplaceur"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("deplaceur") is not None}

    raw = _merge_dict_non_none({
        "deplaceur": pieces.get("deplaceur"),
        "cylindre": pieces.get("cylindre"),
        "materiau_joint_cle": _get_nested(pieces_def, "joint_deplaceur", "materiau_joint_cle"),
    }, _safe_dict(pieces_def.get("joint_deplaceur")))
    pieces["joint_deplaceur"] = _build_piece_instance(JointDeplaceur, raw, rapport, "joint_deplaceur")
    rapport["construction"]["joint_deplaceur"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("joint_deplaceur") is not None}

    raw = _merge_dict_non_none({
        "cylindre": pieces.get("cylindre"),
        "moteur_thermique": moteur_thermique_obj,
        "systeme_complet": systeme_obj,
        "vilbrequin": pieces.get("vilbrequin"),
        "roulement_aiguille": pieces.get("roulement_aiguille_arbre"),
        "couple_max_Nm": couple_max_nm,
        "rpm": rpm,
        "nombre_cylindres": _safe_int(mt.get("nombre_cylindres")),
        "materiau_arbre_cle": _get_nested(pieces_def, "arbre", "materiau_arbre_cle"),
    }, _safe_dict(pieces_def.get("arbre")))
    pieces["arbre"] = _build_piece_instance(ArbreMoteur, raw, rapport, "arbre")
    rapport["construction"]["arbre"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("arbre") is not None}

    raw = _merge_dict_non_none({
        "arbre_vilbrequin": pieces.get("arbre_vilebrequin"),
        "roulement_aiguille_arbre": pieces.get("roulement_aiguille_arbre"),
        "vilbrequin": pieces.get("vilbrequin"),
        "moteur_thermique": moteur_thermique_obj,
        "couple_transmis_Nm": couple_max_nm,
        "materiau_clavette_cle": _get_nested(pieces_def, "clavette_arbre", "materiau_clavette_cle"),
    }, _safe_dict(pieces_def.get("clavette_arbre")))
    pieces["clavette_arbre"] = _build_piece_instance(ClavetteArbre, raw, rapport, "clavette_arbre")
    rapport["construction"]["clavette_arbre"] = {"kwargs": _to_jsonable(raw), "construit": pieces.get("clavette_arbre") is not None}

    _dedup_report_lists(rapport)
    return pieces, rapport


# =============================================================================
# Analyses complémentaires
# =============================================================================


def analyser_pieces(pieces: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for nom, obj in pieces.items():
        out[nom] = _safe_call_report(obj) if obj is not None else {"note": "Pièce non construite."}
        if out[nom] is None:
            out[nom] = {"note": "Pas de rapport dict retourné."}
    return out


def analyser_composants_complementaires(*, composants: Mapping[str, Any], rapport_systeme: Optional[Dict[str, Any]], definition_moteur: Dict[str, Any], analyses_complementaires: Optional[Dict[str, Any]] = None, pieces: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    analyses_user = _safe_dict(analyses_complementaires)
    pieces = pieces or {}
    rapports: Dict[str, Any] = {}

    moteur_thermique = composants.get("moteur_thermique")
    batterie = composants.get("batterie")
    alternateur = composants.get("alternateur")
    architecture = composants.get("architecture")
    boite = composants.get("boite_crabots")
    moteur_electrique = composants.get("moteur_electrique")

    mt_synth = _safe_dict(_get_nested(rapport_systeme or {}, "synthese", "moteur_thermique"))
    veh_synth = _safe_dict(_get_nested(rapport_systeme or {}, "synthese", "vehicule"))
    batt_synth = _safe_dict(_get_nested(rapport_systeme or {}, "synthese", "batterie"))
    alt_synth = _safe_dict(_get_nested(rapport_systeme or {}, "synthese", "alternateur"))

    if batterie is not None and hasattr(batterie, "analyser_dimensionnement"):
        kwargs = _merge_dict_non_none({
            "distance_km": _safe_float(_get_nested(rapport_systeme or {}, "entrees", "mission_batterie", "distance_km")),
            "conso_kwh_km": _safe_float(_get_nested(rapport_systeme or {}, "entrees", "mission_batterie", "conso_kwh_km")),
            "puissance_moyenne_kw": _safe_float(_get_nested(rapport_systeme or {}, "entrees", "mission_batterie", "puissance_moyenne_kw")),
            "vitesse_moyenne_kmh": _safe_float(_get_nested(rapport_systeme or {}, "entrees", "mission_batterie", "vitesse_moyenne_kmh")),
            "temps_charge_cible_h": _safe_float(_get_nested(rapport_systeme or {}, "entrees", "mission_batterie", "temps_charge_cible_h")),
            "puissance_pic_kw": _safe_float(_get_nested(rapport_systeme or {}, "entrees", "mission_batterie", "puissance_pic_kw")),
            "duree_pic_s": _safe_float(_get_nested(rapport_systeme or {}, "entrees", "mission_batterie", "duree_pic_s")),
            "energie_utile_imposee_kwh": _safe_float(_get_nested(rapport_systeme or {}, "entrees", "mission_batterie", "energie_utile_imposee_kwh")),
        }, _safe_dict(analyses_user.get("batterie")))
        try:
            rapports["batterie_dimensionnement"] = batterie.analyser_dimensionnement(**_filter_kwargs_for_callable(batterie.analyser_dimensionnement, kwargs))
        except Exception as exc:
            rapports["batterie_dimensionnement"] = {"erreur": str(exc)}

    if alternateur is not None and hasattr(alternateur, "analyser_pour_bus_dc"):
        kwargs = _merge_dict_non_none({
            "puissance_bus_dc_w": _first_finite(veh_synth.get("puissance_bus_dc_design_w"), alt_synth.get("P_electrique_sortie_W")),
            "vitesse_rotation_rpm": _first_finite(alt_synth.get("vitesse_rotation_rpm"), _get_nested(rapport_systeme or {}, "liaisons", "alternateur", "vitesse_rotation_rpm")),
            "tension_bus_dc_v": _first_finite(veh_synth.get("tension_bus_dc_v"), batt_synth.get("tension_nominale_v")),
            "batterie": batterie,
            "moteur": moteur_electrique,
            "energie_a_recharger_kwh": _safe_float(batt_synth.get("energie_utile_kwh")),
        }, _safe_dict(analyses_user.get("alternateur_bus_dc")))
        try:
            rapports["alternateur_bus_dc"] = alternateur.analyser_pour_bus_dc(**_filter_kwargs_for_callable(alternateur.analyser_pour_bus_dc, kwargs))
        except Exception as exc:
            rapports["alternateur_bus_dc"] = {"erreur": str(exc)}

    if architecture is not None and hasattr(architecture, "analyser"):
        kwargs = _merge_dict_non_none({
            "puissance_cible_w": _first_finite(mt_synth.get("puissance_requise_W"), definition_moteur.get("puissance_nominale_visee_w")),
            "regime_tr_min": _safe_float(mt_synth.get("rpm_nominal")),
            "pme_pa": _first_finite(mt_synth.get("pme_pa"), definition_moteur.get("pme_pa")),
            "vitesse_piston_max_ms": _safe_float(definition_moteur.get("vitesse_piston_max_ms")),
            "longueur_dispo_m": _safe_float(_get_nested(rapport_systeme or {}, "entrees", "architecture", "longueur_dispo_m")),
            "largeur_dispo_m": _safe_float(_get_nested(rapport_systeme or {}, "entrees", "architecture", "largeur_dispo_m")),
            "architectures_autorisees": definition_moteur.get("architectures_autorisees"),
            "architecture_forcee": _first_non_none(definition_moteur.get("architecture_forcee"), definition_moteur.get("architecture")),
        }, _safe_dict(analyses_user.get("architecture")))
        try:
            rapports["architecture"] = architecture.analyser(**_filter_kwargs_for_callable(architecture.analyser, kwargs))
        except Exception as exc:
            rapports["architecture"] = {"erreur": str(exc)}

    if boite is not None and hasattr(boite, "analyser_point"):
        kwargs = _merge_dict_non_none({
            "couple_nm": _first_finite(mt_synth.get("couple_requis_Nm"), definition_moteur.get("couple_requis_Nm"), definition_moteur.get("couple_max_Nm")),
            "vitesse_rotation_tr_min": _safe_float(mt_synth.get("rpm_nominal")),
            "moment_flechissant_nm": _safe_float(_get_nested(rapport_systeme or {}, "entrees", "boite", "moment_flechissant_nm")),
        }, _safe_dict(analyses_user.get("boite_point")))
        try:
            rapports["boite_point"] = boite.analyser_point(**_filter_kwargs_for_callable(boite.analyser_point, kwargs))
        except Exception as exc:
            rapports["boite_point"] = {"erreur": str(exc)}

    if boite is not None and hasattr(boite, "analyser_chaine_moteur_alternateur") and alternateur is not None:
        kwargs = _merge_dict_non_none({
            "alternateur": alternateur,
            "puissance_bus_dc_w": _first_finite(veh_synth.get("puissance_bus_dc_design_w"), alt_synth.get("P_electrique_sortie_W")),
            "rpm_moteur": _safe_float(mt_synth.get("rpm_nominal")),
            "rapports": _get_nested(rapport_systeme or {}, "entrees", "boite", "rapports_boite_candidates"),
            "tension_bus_dc_v": _first_finite(veh_synth.get("tension_bus_dc_v"), batt_synth.get("tension_nominale_v")),
            "batterie": batterie,
            "moteur": moteur_electrique,
        }, _safe_dict(analyses_user.get("boite_chaine")))
        try:
            rapports["boite_chaine"] = boite.analyser_chaine_moteur_alternateur(**_filter_kwargs_for_callable(boite.analyser_chaine_moteur_alternateur, kwargs))
        except Exception as exc:
            rapports["boite_chaine"] = {"erreur": str(exc)}

    if moteur_thermique is not None:
        if hasattr(moteur_thermique, "analyser_geometrie_definition"):
            kwargs = _merge_dict_non_none({
                "pression_pa": _safe_float(definition_moteur.get("pression_max_pa")),
                "taux_compression": _safe_float(definition_moteur.get("taux_compression_nominal")),
                "volume_mort_m3": _safe_float(definition_moteur.get("volume_mort_nominal_m3")),
            }, _safe_dict(analyses_user.get("moteur_thermique_geometrie")))
            try:
                rapports["moteur_thermique_geometrie"] = moteur_thermique.analyser_geometrie_definition(**_filter_kwargs_for_callable(moteur_thermique.analyser_geometrie_definition, kwargs))
            except Exception as exc:
                rapports["moteur_thermique_geometrie"] = {"erreur": str(exc)}

        if hasattr(moteur_thermique, "analyser_cycle_mecanique"):
            kwargs = _merge_dict_non_none({
                "rpm": _safe_float(mt_synth.get("rpm_nominal")),
                "piston": pieces.get("piston"),
                "rapport_piston": _safe_dict(rapports.get("moteur_thermique_geometrie")).get("rapport_piston"),
                "rayon_maneton_m": _safe_float(definition_moteur.get("rayon_manivelle_m")),
                "taux_compression": _safe_float(definition_moteur.get("taux_compression_nominal")),
                "volume_mort_m3": _safe_float(definition_moteur.get("volume_mort_nominal_m3")),
            }, _safe_dict(analyses_user.get("moteur_thermique_cycle")))
            try:
                rapports["moteur_thermique_cycle"] = moteur_thermique.analyser_cycle_mecanique(**_filter_kwargs_for_callable(moteur_thermique.analyser_cycle_mecanique, kwargs))
            except Exception as exc:
                rapports["moteur_thermique_cycle"] = {"erreur": str(exc)}

        if hasattr(moteur_thermique, "analyser_point_de_fonctionnement"):
            kwargs = _merge_dict_non_none({
                "rpm": _safe_float(mt_synth.get("rpm_nominal")),
                "piston": pieces.get("piston"),
                "rapport_piston": _safe_dict(rapports.get("moteur_thermique_cycle")).get("rapport_piston"),
                "pression_moyenne_effective_pa": _first_finite(mt_synth.get("pme_pa"), definition_moteur.get("pme_pa")),
                "pression_max_pa": _safe_float(definition_moteur.get("pression_max_pa")),
            }, _safe_dict(analyses_user.get("moteur_thermique_point")))
            try:
                rapports["moteur_thermique_point"] = moteur_thermique.analyser_point_de_fonctionnement(**_filter_kwargs_for_callable(moteur_thermique.analyser_point_de_fonctionnement, kwargs))
            except Exception as exc:
                rapports["moteur_thermique_point"] = {"erreur": str(exc)}

        if hasattr(moteur_thermique, "analyser_bilan_carburant"):
            kwargs = _merge_dict_non_none({
                "carburant": definition_moteur.get("carburant"),
                "puissance_utile_w": _first_finite(mt_synth.get("puissance_requise_W"), definition_moteur.get("puissance_requise_W")),
                "rendement_global": _safe_float(definition_moteur.get("rendement_global")),
            }, _safe_dict(analyses_user.get("moteur_thermique_bilan_carburant")))
            try:
                rapports["moteur_thermique_bilan_carburant"] = moteur_thermique.analyser_bilan_carburant(**_filter_kwargs_for_callable(moteur_thermique.analyser_bilan_carburant, kwargs))
            except Exception as exc:
                rapports["moteur_thermique_bilan_carburant"] = {"erreur": str(exc)}

    if moteur_electrique is not None:
        rep = _safe_call_report(moteur_electrique)
        if rep is not None:
            rapports["moteur_electrique"] = rep

    return rapports


# =============================================================================
# Orchestration principale stricte
# =============================================================================


def dimensionner_systeme_shsem(
    puissance_traction_kw: Optional[float] = None,
    *,
    production_electrique_sortie_w: Optional[float] = None,
    puissance_bus_dc_w: Optional[float] = None,
    puissance_moteur_requise_W: Optional[float] = None,
    type_puissance_nominale: Optional[str] = None,

    # Mission / véhicule
    distance_km: Optional[float] = None,
    vitesse_moyenne_kmh: Optional[float] = None,
    masse_kg: Optional[float] = None,
    vitesse_ms: Optional[float] = None,
    acceleration_ms2: Optional[float] = None,
    angle_pente: Optional[float] = None,
    angle_unite: Optional[str] = None,
    coef_roulement: Optional[float] = None,
    coef_trainee_aero_cda: Optional[float] = None,
    rayon_roue_m: Optional[float] = None,
    rapport_reduction_global: Optional[float] = None,
    rendement_transmission: Optional[float] = None,
    nb_roues_motrices: Optional[int] = None,
    nb_moteurs_electriques: Optional[int] = None,
    pertes_fixes_transmission_w: Optional[float] = None,
    couple_pertes_transmission_nm: Optional[float] = None,
    marge_puissance: Optional[float] = None,
    marge_couple: Optional[float] = None,
    puissance_auxiliaire_w: Optional[float] = None,
    conso_kwh_km: Optional[float] = None,
    puissance_pic_kw: Optional[float] = None,
    duree_pic_s: Optional[float] = None,
    energie_utile_imposee_kwh: Optional[float] = None,
    temps_charge_cible_h: Optional[float] = None,
    scenario_bus_dc: Optional[str] = None,
    tension_bus_dc_v: Optional[float] = None,

    # Alternateur / boîte
    vitesse_alternateur_rpm: Optional[float] = None,
    rapport_vitesse_alt_sur_moteur: Optional[float] = None,
    vitesse_moteur_thermique_rpm: Optional[float] = None,
    tension_alt_v: Optional[float] = None,
    courant_alt_a: Optional[float] = None,
    facteur_puissance_alt: Optional[float] = None,
    courant_est_ligne: Optional[bool] = None,
    rendement_liaison_meca_alt: Optional[float] = None,
    rapports_boite_candidates: Optional[Sequence[float]] = None,
    rendement_boite: Optional[float] = None,
    facteur_service_boite: Optional[float] = None,
    moment_flechissant_nm: Optional[float] = None,
    inertie_primaire_kg_m2: Optional[float] = None,
    inertie_secondaire_kg_m2: Optional[float] = None,
    delta_omega_rad_s: Optional[float] = None,
    temps_engagement_s: Optional[float] = None,
    force_axiale_roulement_N: Optional[float] = None,
    force_radiale_roulement_N: Optional[float] = None,

    # Architecture / thermique
    pme_pa: Optional[float] = None,
    vitesse_piston_max_ms: Optional[float] = None,
    longueur_dispo_m: Optional[float] = None,
    largeur_dispo_m: Optional[float] = None,
    hauteur_dispo_m: Optional[float] = None,
    horizon_usage_h: Optional[float] = None,
    architectures_autorisees: Optional[Sequence[str]] = None,
    architecture_forcee: Optional[str] = None,
    poids_maintenance: Optional[float] = None,
    poids_masse: Optional[float] = None,
    poids_cout_matiere: Optional[float] = None,
    poids_compacite: Optional[float] = None,
    poids_fiabilite: Optional[float] = None,
    poids_rendement: Optional[float] = None,
    pression_max_pa: Optional[float] = None,
    contrainte_admissible_pa: Optional[float] = None,
    densite_materiau_kg_m3: Optional[float] = None,
    cout_matiere_eur_kg: Optional[float] = None,
    rendement_indique_cible_min: Optional[float] = None,
    rendement_mecanique_cible_min: Optional[float] = None,
    masse_estimee_max_kg: Optional[float] = None,
    cout_matiere_max_eur: Optional[float] = None,
    indice_maintenance_max: Optional[float] = None,
    duree_vie_cible_h: Optional[float] = None,

    # Définition moteur thermique
    moteur_thermique_definition: Optional[Dict[str, Any]] = None,
    temps_moteur: Optional[int] = None,
    nombre_cylindres: Optional[int] = None,
    architecture_moteur: Optional[str] = None,
    alesage_m: Optional[float] = None,
    course_m: Optional[float] = None,
    rpm_moteur_nominal: Optional[float] = None,
    couple_moteur_max_Nm: Optional[float] = None,
    force_bielle_N: Optional[float] = None,
    carburant: Optional[str] = None,
    ratio_course_alesage_max: Optional[float] = None,
    ratio_course_alesage_cible: Optional[float] = None,
    taux_compression_nominal: Optional[float] = None,
    volume_mort_nominal_m3: Optional[float] = None,

    # Définitions utilisateur
    pieces_definition: Optional[Dict[str, Any]] = None,
    analyses_complementaires: Optional[Dict[str, Any]] = None,
    composants_definition: Optional[Dict[str, Any]] = None,
    usage_moteur_electrique_depuis_puissance: Optional[Dict[str, Any]] = None,

    # Options
    lancer_pipeline_legacy: bool = False,
    lancer_stho_me_secondaire: bool = False,
) -> Dict[str, Any]:
    """
    Orchestrateur strict.

    Philosophie :
    - `main.py` n'injecte plus de chiffres de conception par défaut ;
    - il calcule tout ce que les modules savent déduire ;
    - s'il manque des données pour fermer un calcul, elles remontent dans `inconnues`.

    Attention : avec les modules actuels, une puissance seule ne suffit pas toujours à définir
    un moteur thermique unique. Pour `MoteurThermique.definir_depuis_exigences`, il faut au
    minimum la puissance cible, le régime, la PME, la vitesse piston max et un ratio S/B max.
    """
    if puissance_traction_kw is None and production_electrique_sortie_w is None and puissance_bus_dc_w is None and puissance_moteur_requise_W is None:
        raise ValueError("Donne au moins une cible parmi puissance_traction_kw, production_electrique_sortie_w, puissance_bus_dc_w ou puissance_moteur_requise_W.")

    rapport_global: Dict[str, Any] = {
        "meta": {
            "backend": "main.py",
            "mode": "strict_sans_invention",
            "repertoire": str(_THIS_DIR),
        },
        "inconnues": {"impossibles": [], "partielles": []},
        "alertes": {},
        "notes_modele": [],
    }

    composants_def = _safe_dict(composants_definition)

    if puissance_traction_kw is not None:
        _req_pos("puissance_traction_kw", puissance_traction_kw)
    if production_electrique_sortie_w is not None:
        _req_pos("production_electrique_sortie_w", production_electrique_sortie_w)
    if puissance_bus_dc_w is not None:
        _req_pos("puissance_bus_dc_w", puissance_bus_dc_w)
    if puissance_moteur_requise_W is not None:
        _req_pos("puissance_moteur_requise_W", puissance_moteur_requise_W)

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
                "puissance_nominale_visee_w": puissance_moteur_requise_W,
                "type_puissance_nominale": type_puissance_nominale,
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

    # Cibles dérivables sans invention
    if puissance_bus_dc_w is None and production_electrique_sortie_w is not None:
        puissance_bus_dc_w = production_electrique_sortie_w
        _append_note(rapport_global, "puissance_bus_dc_w reprise exactement depuis production_electrique_sortie_w.")

    if definition_moteur.get("puissance_nominale_visee_w") is None and puissance_moteur_requise_W is None:
        if puissance_bus_dc_w is not None:
            _append_note(rapport_global, "La puissance moteur thermique n'est pas déduite automatiquement depuis la puissance électrique : cela dépend des rendements alternateur/liaisons/mécanique, donc aucune valeur n'est inventée.")
        if puissance_traction_kw is not None:
            _append_note(rapport_global, "La puissance moteur thermique n'est pas déduite automatiquement depuis la puissance traction : cela dépend de la chaîne complète et des rendements, donc aucune valeur n'est inventée.")

    # Construction stricte des composants
    moteur_electrique = composants_def.get("moteur_electrique")
    if moteur_electrique is None and composants_def.get("moteur_electrique_kwargs"):
        moteur_electrique = _build_component_instance(MoteurElectrique, _safe_dict(composants_def.get("moteur_electrique_kwargs")), rapport_global, "moteur_electrique")
    elif moteur_electrique is None:
        _push_inconnue(rapport_global, "partielles", "moteur_electrique", "Aucun objet ni kwargs fournis. main.py n'invente pas puissance_max_w/regime_max_rpm.")

    batterie = composants_def.get("batterie")
    if batterie is None and composants_def.get("batterie_kwargs"):
        batterie = _build_component_instance(Batterie, _safe_dict(composants_def.get("batterie_kwargs")), rapport_global, "batterie")

    alternateur = composants_def.get("alternateur")
    if alternateur is None and composants_def.get("alternateur_kwargs"):
        alternateur = _build_component_instance(Alternateur, _safe_dict(composants_def.get("alternateur_kwargs")), rapport_global, "alternateur")

    boite_crabots = composants_def.get("boite_crabots")
    if boite_crabots is None and composants_def.get("boite_crabots_kwargs"):
        boite_crabots = _build_component_instance(BoiteCrabots, _safe_dict(composants_def.get("boite_crabots_kwargs")), rapport_global, "boite_crabots")

    architecture = composants_def.get("architecture")
    if architecture is None and composants_def.get("architecture_kwargs"):
        architecture = _build_component_instance(Architecture, _safe_dict(composants_def.get("architecture_kwargs")), rapport_global, "architecture")

    moteur_thermique = composants_def.get("moteur_thermique")
    rapport_construction_moteur: Dict[str, Any] = {}
    if moteur_thermique is None:
        moteur_thermique, rapport_construction_moteur = construire_moteur_thermique_complet(moteur_thermique_definition=definition_moteur, rapport=rapport_global)

    composants = {
        "moteur_electrique": moteur_electrique,
        "batterie": batterie,
        "alternateur": alternateur,
        "moteur_thermique": moteur_thermique,
        "boite_crabots": boite_crabots,
        "architecture": architecture,
    }

    # Analyse partielle moteur électrique depuis puissance si possible
    rapports_partiels: Dict[str, Any] = {}
    if moteur_electrique is None and callable(AnalyserMoteurElectriqueDepuisPuissance) and production_electrique_sortie_w is not None and usage_moteur_electrique_depuis_puissance:
        try:
            rapports_partiels["moteur_electrique_depuis_puissance"] = AnalyserMoteurElectriqueDepuisPuissance(
                puissance_elec_dispo_w=production_electrique_sortie_w,
                config=_safe_dict(usage_moteur_electrique_depuis_puissance),
                tension_systeme_v=tension_bus_dc_v,
            )
        except Exception as exc:
            rapports_partiels["moteur_electrique_depuis_puissance"] = {"erreur": str(exc)}

    # Analyse système complet seulement si tous les composants cœur existent
    rapport_systeme: Dict[str, Any] = {"note": "SystemeComplet non lancé."}
    systeme = None
    systeme_possible = all(composants.get(k) is not None for k in ("moteur_electrique", "batterie", "alternateur", "moteur_thermique")) and SystemeComplet is not None
    if systeme_possible:
        try:
            systeme = SystemeComplet(
                moteur_electrique=moteur_electrique,
                batterie=batterie,
                alternateur=alternateur,
                moteur_thermique=moteur_thermique,
                boite_crabots=boite_crabots,
                architecture=architecture,
            )
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
                "puissance_moyenne_kw": puissance_traction_kw,
                "vitesse_moyenne_kmh": vitesse_moyenne_kmh,
                "temps_charge_cible_h": temps_charge_cible_h,
                "puissance_pic_kw": puissance_pic_kw,
                "duree_pic_s": duree_pic_s,
                "energie_utile_imposee_kwh": energie_utile_imposee_kwh,
                "calculer_puissance_charge_requise": True if temps_charge_cible_h is not None else None,
                "scenario_bus_dc": scenario_bus_dc,
                "tension_bus_dc_v": tension_bus_dc_v,
                "vitesse_alternateur_rpm": vitesse_alternateur_rpm,
                "vitesse_moteur_thermique_rpm": vitesse_moteur_thermique_rpm,
                "rapport_vitesse_alt_sur_moteur": rapport_vitesse_alt_sur_moteur,
                "puissance_elec_alt_cible_w": puissance_bus_dc_w,
                "tension_alt_v": tension_alt_v,
                "courant_alt_a": courant_alt_a,
                "facteur_puissance_alt": facteur_puissance_alt,
                "courant_est_ligne": courant_est_ligne,
                "rendement_liaison_meca_alt": rendement_liaison_meca_alt,
                "rapports_boite_candidates": list(rapports_boite_candidates) if rapports_boite_candidates is not None else None,
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
                "hauteur_dispo_m": hauteur_dispo_m,
                "horizon_usage_h": horizon_usage_h,
                "architectures_autorisees": list(architectures_autorisees) if architectures_autorisees is not None else None,
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
                "moteur_thermique_params": definition_moteur,
            }
            rapport_systeme = systeme.analyser(**_filter_kwargs_for_callable(systeme.analyser, analyse_systeme))
        except Exception as exc:
            rapport_systeme = {"erreur": str(exc)}
    else:
        if SystemeComplet is None:
            _push_inconnue(rapport_global, "impossibles", "SystemeComplet", "Classe SystemeComplet indisponible.")
        else:
            manquants = [k for k in ("moteur_electrique", "batterie", "alternateur", "moteur_thermique") if composants.get(k) is None]
            _push_inconnue(rapport_global, "impossibles", "SystemeComplet", f"Impossible de lancer le système complet sans {manquants}.")

    # Pièces
    pieces: Dict[str, Any] = {}
    rapport_construction_pieces: Dict[str, Any] = {"note": "Construction pièces non lancée."}
    rapports_pieces: Dict[str, Any] = {}
    if isinstance(rapport_systeme, dict) and "synthese" in rapport_systeme:
        pieces, rapport_construction_pieces = construire_pieces_depuis_systeme(
            rapport_systeme=rapport_systeme,
            definition_moteur_thermique=definition_moteur,
            pieces_definition=pieces_definition,
            moteur_thermique_obj=moteur_thermique,
            systeme_obj=systeme,
        )
        rapports_pieces = analyser_pieces(pieces)
    else:
        _push_inconnue(rapport_global, "partielles", "pieces", "Construction des pièces impossible tant que le rapport système n'expose pas une synthèse exploitable.")

    rapports_composants = analyser_composants_complementaires(
        composants=composants,
        rapport_systeme=rapport_systeme if isinstance(rapport_systeme, dict) else None,
        definition_moteur=definition_moteur,
        analyses_complementaires=analyses_complementaires,
        pieces=pieces,
    )
    if rapport_construction_moteur:
        rapports_composants["construction_moteur_thermique"] = rapport_construction_moteur
    rapports_composants.update(rapports_partiels)

    # Optimisation
    rapport_optimisation: Dict[str, Any]
    if OptimisationSysteme is not None and systeme is not None:
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
        rapport_optimisation = {"note": "Optimisation non lancée."}

    rapport_stho_me: Dict[str, Any]
    if lancer_stho_me_secondaire and STHO_ME is not None and systeme is not None:
        try:
            config_stho = {
                "meta": {"backend": "main.py", "source": "config_generee_depuis_main"},
                "composants": composants,
                "pieces": _safe_dict(pieces_definition),
                "analyses": {"moteur_thermique_definition": _definition_moteur_pour_exigences(definition_moteur), "systeme_complet": rapport_systeme},
            }
            rapport_stho_me = STHO_ME.depuis_config(config_stho).analyser()
        except Exception as exc:
            rapport_stho_me = {"erreur": str(exc)}
    else:
        rapport_stho_me = {"note": "Pipeline STHO_ME non lancé."}

    legacy: Dict[str, Any] = {}
    if lancer_pipeline_legacy and callable(dimensionner_pieces_completes):
        try:
            mt_syn = _safe_dict(_safe_dict(rapport_systeme).get("synthese")).get("moteur_thermique")
            legacy["dimensionner_pieces_completes"] = dimensionner_pieces_completes(
                puissance_cible_w=_get_nested(mt_syn, "puissance_requise_W"),
                regime_tr_min=_get_nested(mt_syn, "rpm_nominal"),
                n_cyl=_get_nested(mt_syn, "nombre_cylindres"),
                pression_max_pa=pression_max_pa,
            )
        except Exception as exc:
            legacy["dimensionner_pieces_completes_erreur"] = str(exc)
    if lancer_pipeline_legacy and DriveChainGenerator is not None and puissance_traction_kw is not None:
        try:
            gen = DriveChainGenerator()
            gen.compute(puissance_traction_kw)
            legacy["drivechain"] = _to_jsonable(getattr(gen, "results", None))
        except Exception as exc:
            legacy["drivechain_erreur"] = str(exc)

    # Fusion inconnues / alertes
    for source in (rapport_systeme, rapports_composants, rapport_construction_pieces, rapports_pieces, rapport_optimisation, rapport_stho_me):
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

    inventaire = {
        "composants": {nom: {"type": None if obj is None else type(obj).__name__, "construit": obj is not None} for nom, obj in composants.items()},
        "pieces": {nom: {"type": None if obj is None else type(obj).__name__, "construit": obj is not None, "rapport_disponible": isinstance(rapports_pieces.get(nom), dict)} for nom, obj in pieces.items()},
    }

    synth = _safe_dict(_safe_dict(rapport_systeme).get("synthese"))
    mt_syn = _safe_dict(synth.get("moteur_thermique"))
    veh_syn = _safe_dict(synth.get("vehicule"))
    batt_syn = _safe_dict(synth.get("batterie"))
    opt_syn = _safe_dict(_safe_dict(rapport_optimisation).get("synthese_optimisation"))

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
        "nb_pieces_construites": sum(1 for obj in pieces.values() if obj is not None),
        "nb_alertes": sum(len(v) for v in _safe_dict(rapport_global.get("alertes")).values()),
        "nb_inconnues": sum(len(v) for v in _safe_dict(rapport_global.get("inconnues")).values()),
    }

    resultat = {
        "meta": _merge_dict_non_none(rapport_global.get("meta"), {"version": "3.0.0", "modele": "orchestrateur strict SHSE-M"}),
        "entrees": {
            "puissance_traction_kw": puissance_traction_kw,
            "production_electrique_sortie_w": production_electrique_sortie_w,
            "puissance_bus_dc_w": puissance_bus_dc_w,
            "definition_moteur_thermique": definition_moteur,
            "pieces_definition": _safe_dict(pieces_definition),
            "analyses_complementaires": _safe_dict(analyses_complementaires),
            "composants_definition": _safe_dict(composants_definition),
        },
        "inventaire": inventaire,
        "resume_gui": resume_gui,
        "systeme_complet": rapport_systeme,
        "analyses_composants": rapports_composants,
        "construction_pieces": rapport_construction_pieces,
        "rapports_pieces": rapports_pieces,
        "optimisation": rapport_optimisation,
        "stho_me_secondaire": rapport_stho_me,
        "legacy": legacy,
        "objets_serialises": {
            "composants": {nom: _to_jsonable(obj) for nom, obj in composants.items()},
            "pieces": {nom: _to_jsonable(obj) for nom, obj in pieces.items()},
        },
        "toutes_les_donnees_composants": {nom: _collect_public_data(obj) for nom, obj in composants.items()},
        "toutes_les_donnees_pieces": {nom: _collect_public_data(obj) for nom, obj in pieces.items()},
        "toutes_les_donnees_systeme": _collect_public_data(systeme),
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


realiser_systeme_complet = dimensionner_systeme_shsem
concevoir_systeme_complet = dimensionner_systeme_shsem


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
    print(f"Score cohérence: {gui.get('score_coherence_100')}")
    print(f"Score global   : {gui.get('score_global_100')}")
    print(f"Pièces constr. : {gui.get('nb_pieces_construites')}")
    print(f"Alertes        : {gui.get('nb_alertes')}")
    print(f"Inconnues      : {gui.get('nb_inconnues')}")


if __name__ == "__main__":
    import sys
    import os
    import json

    kwargs = {}
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        try:
            if arg.endswith(".json") and os.path.isfile(arg):
                with open(arg, "r", encoding="utf-8") as f:
                    kwargs = json.load(f)
            else:
                print("Le script attend un fichier JSON riche pour configurer l'orchestrateur. Aucun argument par défaut n'est toléré.")
                sys.exit(1)
        except Exception as e:
            print(f"Erreur lors du chargement du fichier JSON: {e}")
            sys.exit(1)
    else:
        print("Usage: python main.py <config.json> [sortie.json]\nAucune valeur par défaut n'est injectée, vous devez tout définir (ex: cibles de puissance) dans le JSON.")
        sys.exit(1)

    try:
        rep = dimensionner_systeme_shsem(**kwargs)
        _print_resume_console(rep)

        if len(sys.argv) > 2 and sys.argv[2].endswith(".json"):
            exporter_rapport_json(rep, sys.argv[2])
            print(f"Rapport exporté vers {sys.argv[2]}")
    except Exception as e:
        print(f"Erreur d'exécution: {e}")

