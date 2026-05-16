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
analyser_strategie_energie = _import_attr(("backend.ensemble.strategie_energie", "strategie_energie"), "analyser_strategie_energie", default=None)
CahierDesChargesSTHOME = _import_attr(("backend.ensemble.resolution_inconnues", "resolution_inconnues"), "CahierDesChargesSTHOME", default=None)
resoudre_inconnues_systeme = _import_attr(("backend.ensemble.resolution_inconnues", "resolution_inconnues"), "resoudre_inconnues_systeme", default=None)

MoteurElectrique = _import_attr(("backend.components.moteur_electrique.moteur_electrique", "backend.components.moteur_electrique", "moteur_electrique"), "MoteurElectrique", default=None)
AnalyserMoteurElectriqueDepuisPuissance = _import_attr(("backend.components.moteur_electrique.moteur_electrique", "backend.components.moteur_electrique", "moteur_electrique"), "analyser_depuis_puissance", default=None)
Batterie = _import_attr(("backend.components.batterie.batterie", "backend.components.batterie", "batterie"), "Batterie", default=None)
Alternateur = _import_attr(("backend.components.alternateur.alternateur", "backend.components.alternateur", "alternateur"), "Alternateur", default=None)
MoteurThermique = _import_attr(("backend.components.moteur_thermique.moteur_thermique", "backend.components.moteur_thermique", "moteur_thermique"), "MoteurThermique", default=None)
BoiteCrabots = _import_attr(("backend.components.boite_crabots.boite_crabots", "backend.components.boite_crabots", "boite_crabots"), "BoiteCrabots", default=None)
Architecture = _import_attr(("backend.components.architechture.architecture", "backend.components.architecture.architecture", "backend.components.architechture", "architecture"), "Architecture", default=None)
Carburant = _import_attr(("backend.components.moteur_thermique.modules.calcul_carburant", "backend.components.moteur_thermique.modules.calcul_carburant"), "Carburant", default=None)
CompositionElementaireCombustible = _import_attr(("backend.components.moteur_thermique.modules.calcul_carburant", "backend.components.moteur_thermique.modules.calcul_carburant"), "CompositionElementaireCombustible", default=None)

Cylindre = _import_attr(("backend.components.moteur_thermique.pieces.cylindre", "cylindre"), "Cylindre", default=None)
Piston = _import_attr(("backend.components.moteur_thermique.pieces.piston", "piston"), "Piston", default=None)
JointPiston = _import_attr(("backend.components.moteur_thermique.pieces.joint_piston", "joint_piston"), "JointPiston", default=None)
CorpsBielle = _import_attr(("backend.components.moteur_thermique.pieces.bielle", "bielle"), "CorpsBielle", default=None)
ArbrePiston = _import_attr(("backend.components.moteur_thermique.pieces.arbre_piston", "arbre_piston"), "ArbrePiston", default=None)
CoussinetArbrePiston = _import_attr(("backend.components.moteur_thermique.pieces.coussinet_arbre_piston", "coussinet_arbre_piston"), "CoussinetArbrePiston", default=None)
ArbreVilbrequin = _import_attr(("backend.components.moteur_thermique.pieces.arbre_vilbrequin", "arbre_vilbrequin"), "ArbreVilbrequin", default=None)
Vilbrequin = _import_attr(("backend.components.moteur_thermique.pieces.vilbrequin", "vilbrequin"), "Vilbrequin", default=None)
RoulementAiguilleArbre = _import_attr(("backend.components.moteur_thermique.pieces.roulement_aiguille_arbre", "roulement_aiguille_arbre"), "RoulementAiguilleArbre", default=None)
RoulementAiguilleArbreVilebrequin = _import_attr(("backend.components.moteur_thermique.pieces.roulement_aiguille_arbre_vilebrequin", "roulement_aiguille_arbre_vilebrequin"), "RoulementAiguilleArbreVilebrequin", default=None)
CouvercleCylindre = _import_attr(("backend.components.moteur_thermique.pieces.couvercle_cylindre", "couvercle_cylindre"), "CouvercleCylindre", default=None)
VisCouvercleCylindre = _import_attr(("backend.components.moteur_thermique.pieces.vis_couvercle_cylindre", "vis_couvercle_cylindre"), "VisCouvercleCylindre", default=None)
Deplaceur = _import_attr(("backend.components.moteur_thermique.pieces.deplaceur", "deplaceur"), "Deplaceur", default=None)
JointDeplaceur = _import_attr(("backend.components.moteur_thermique.pieces.joint_deplaceur", "joint_deplaceur"), "JointDeplaceur", default=None)
ArbreMoteur = _import_attr(("backend.components.moteur_thermique.pieces.arbre", "arbre"), "ArbreMoteur", default=None)
if ArbreMoteur is None:
    ArbreMoteur = _import_attr(("backend.components.moteur_thermique.pieces.arbre", "arbre"), "Arbre", default=None)
ClavetteArbre = _import_attr(("backend.components.moteur_thermique.pieces.clavette_arbre", "clavette_arbre"), "ClavetteArbre", default=None)

try:
    from backend.modules.systeme.definition_pieces import dimensionner_pieces_completes  # type: ignore
except Exception:
    dimensionner_pieces_completes = None  # type: ignore

try:
    from backend.modules.systeme.orchestrateur_pieces import (  # type: ignore
        consolider_sortie_pieces as consolider_sortie_pieces_systeme,
        extraire_rapports_pieces_composants as extraire_rapports_pieces_composants_systeme,
        construire_inventaire_pieces_imbrique as construire_inventaire_pieces_imbrique_systeme,
        enrichir_rapport_puissance_avec_pieces as enrichir_rapport_puissance_avec_pieces_systeme,
    )
except Exception:
    consolider_sortie_pieces_systeme = None  # type: ignore
    extraire_rapports_pieces_composants_systeme = None  # type: ignore
    construire_inventaire_pieces_imbrique_systeme = None  # type: ignore
    enrichir_rapport_puissance_avec_pieces_systeme = None  # type: ignore

try:
    from backend.modules.systeme.system_generator import DriveChainGenerator  # type: ignore
except Exception:
    DriveChainGenerator = None  # type: ignore

try:
    from backend.modules.systeme.analyse_puissance_sortie import analyser_puissance_sortie, normaliser_puissance, optimiser_puissance_sortie  # type: ignore
except Exception:
    analyser_puissance_sortie = None  # type: ignore
    normaliser_puissance = None  # type: ignore
    optimiser_puissance_sortie = None  # type: ignore


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


def _first_finite_nested(d: Any, *paths: Sequence[str]) -> Optional[float]:
    for path in paths:
        val = _get_nested(d, *path)
        if _is_finite(val):
            return float(val)
    return None


def _extract_cylindre_values(rapport_cylindre: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(rapport_cylindre, dict):
        return {}
    return {
        "alesage_m": _first_finite_nested(rapport_cylindre, ("entrees", "alesage_m"), ("geometrie", "diametre_interieur_nominal_m")),
        "course_m": _first_finite_nested(rapport_cylindre, ("entrees", "course_m")),
        "pression_max_pa": _first_finite_nested(rapport_cylindre, ("entrees", "pression_max_pa")),
    }


def _extract_piston_values(rapport_piston: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(rapport_piston, dict):
        return {}
    return {
        "force_gaz_n": _first_finite_nested(rapport_piston, ("cinematique", "force_gaz_n"), ("dimensionnement", "force_pression_piston_max_N")),
        "force_axiale_nette_n": _first_finite_nested(rapport_piston, ("cinematique", "force_axiale_nette_n")),
    }


def _extract_bielle_values(rapport_bielle: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(rapport_bielle, dict):
        return {}
    return {
        "longueur_bielle_m": _first_finite_nested(rapport_bielle, ("geometrie", "longueur_bielle_m"), ("entrees", "longueur_bielle_m")),
    }


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


def _default_piece_definitions() -> Dict[str, Any]:
    """
    Standards explicites du projet pour fermer les calculs mécaniques sans
    injecter de nombres arbitraires pièce par pièce au runtime.

    Ces valeurs correspondent à des choix de familles matériau/catalogue déjà
    présentes dans `backend.ensemble.materiaux`.
    """
    return {
        "cylindre": {"longueur_utile_m": 0.18, "materiau_cle": "acier_42crmo4_qt"},
        "piston": {
            "materiau_piston_cle": "alu_6061_t6",
            "materiau_cylindre_cle": "acier_42crmo4_qt",
            "materiau_joint_cle": "ptfe",
            "materiau_axe_cle": "acier_42crmo4_qt",
        },
        "bielle": {"materiau_cle": "acier_42crmo4_qt", "longueur_bielle_m": 0.24},
        "arbre_piston": {
            "materiau_cle": "acier_42crmo4_qt",
            "longueur_totale_m": 0.30,
            "longueur_fut_central_m": 0.16,
        },
        "coussinet_arbre_piston": {"materiau_coussinet": "bronze_cusn12"},
        "deplaceur": {"longueur_totale_m": 0.14, "materiau_cle": "inox_304"},
        "joint_piston": {"materiau_joint_cle": "ptfe"},
        "joint_deplaceur": {"materiau_joint_cle": "ptfe"},
        "arbre_vilebrequin": {"materiau_cle": "acier_42crmo4_qt"},
        "vilbrequin": {"materiau_cle": "acier_42crmo4_qt"},
        "roulement_aiguille_arbre": {"duree_vie_cible_h": 5000.0, "exposant_vie_p": 10.0 / 3.0},
        "arbre": {
            "materiau_arbre_cle": "acier_42crmo4_qt",
            "materiau_clavette_cle": "acier_42crmo4_qt",
            "materiau_moyeu_cle": "acier_100cr6",
        },
        "clavette_arbre": {
            "materiau_clavette_cle": "acier_42crmo4_qt",
            "materiau_anneau_interieur_cle": "acier_100cr6",
        },
        "couvercle_cylindre": {"materiau_cle": "acier_42crmo4_qt"},
        "vis_couvercle_cylindre": {"classe_vis_iso898": "10.9"},
    }


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": str(nom), "raison": str(raison)})


def _push_warning(rapport: Dict[str, Any], categorie: str, nom: str, detail: str) -> None:
    rapport.setdefault("alertes", {}).setdefault(categorie, []).append({"nom": str(nom), "detail": str(detail)})


def _append_note(rapport: Dict[str, Any], note: str) -> None:
    rapport.setdefault("notes_modele", []).append(str(note))


def _attr_first_finite(obj: Any, *names: str) -> Optional[float]:
    if obj is None:
        return None
    for name in names:
        try:
            value = getattr(obj, name, None)
        except Exception:
            value = None
        value = _safe_float(value)
        if value is not None:
            return value
    return None


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
    def _push_local_inconnue(categorie: str, nom: str, raison: str) -> None:
        derived.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": str(nom), "raison": str(raison)})

    def _set_detail(
        nom: str,
        *,
        valeur: Any,
        statut: str,
        source: Optional[str] = None,
        calcul: Optional[str] = None,
        inconnues: Optional[List[str]] = None,
        notes: Optional[List[str]] = None,
    ) -> None:
        derived.setdefault("details", {})[nom] = {
            "valeur": valeur,
            "statut": str(statut),
            "source": source,
            "calcul": calcul,
            "inconnues": list(inconnues or []),
            "notes": list(notes or []),
        }

    derived: Dict[str, Any] = {
        "sortie_utilisateur_w": None,
        "puissance_elec_usage_w": None,
        "puissance_auxiliaire_w": _safe_float(puissance_auxiliaire_w),
        "energie_batterie_cible_kwh": None,
        "puissance_recharge_batterie_w": None,
        "tension_bus_dc_v": _safe_float(tension_bus_dc_v),
        "courant_bus_dc_a": None,
        "puissance_bus_dc_totale_w": _safe_float(puissance_bus_dc_w),
        "fraction_temps_generation_beta": _safe_float(fraction_temps_generation_beta),
        "puissance_bus_dc_instantanee_w": None,
        "puissance_mecanique_alternateur_borne_basse_w": None,
        "puissance_mecanique_alternateur_requise_w": None,
        "puissance_moteur_thermique_borne_basse_w": None,
        "puissance_moteur_thermique_requise_w": None,
        "source_puissance_recharge": None,
        "source_puissance_usage": None,
        "source_tension_bus": None,
        "details": {},
        "inconnues": {"impossibles": [], "partielles": []},
        "notes": [],
    }

    p_sortie_w = _first_finite(
        _safe_float(production_electrique_sortie_w),
        (_safe_float(puissance_traction_kw) * 1000.0) if _is_finite(puissance_traction_kw) else None,
    )
    derived["sortie_utilisateur_w"] = p_sortie_w
    _set_detail(
        "sortie_utilisateur_w",
        valeur=p_sortie_w,
        statut="ok" if p_sortie_w is not None else "impossible",
        source="production_electrique_sortie_w" if production_electrique_sortie_w is not None else "puissance_traction_kw",
        calcul="normalisation vers W",
        inconnues=[] if p_sortie_w is not None else ["puissance_sortie"],
    )

    eta_mot = _attr_first_finite(moteur_electrique, "rendement_moteur")
    pertes_mot_w = _attr_first_finite(moteur_electrique, "pertes_fixes_w")
    if p_sortie_w is not None:
        if production_electrique_sortie_w is not None:
            derived["puissance_elec_usage_w"] = p_sortie_w
            derived["source_puissance_usage"] = "production_electrique_sortie_w"
        elif eta_mot is not None and eta_mot > 0.0:
            if pertes_mot_w is not None:
                derived["puissance_elec_usage_w"] = (p_sortie_w + pertes_mot_w) / eta_mot
                derived["source_puissance_usage"] = "puissance_traction_kw + pertes_fixes / rendement_moteur"
            else:
                derived["puissance_elec_usage_w"] = p_sortie_w / eta_mot
                derived["source_puissance_usage"] = "puissance_traction_kw / rendement_moteur"
            derived["notes"].append("Puissance electrique d'usage deduite du moteur electrique a partir de la puissance de sortie cible.")
        else:
            _push_local_inconnue(
                "partielles",
                "puissance_elec_usage_w",
                "Le rendement du moteur electrique est requis pour remonter de la puissance de sortie a la puissance electrique d'usage.",
            )
    _set_detail(
        "puissance_elec_usage_w",
        valeur=derived["puissance_elec_usage_w"],
        statut="ok" if _is_finite(derived["puissance_elec_usage_w"]) else ("partiel" if p_sortie_w is not None else "impossible"),
        source=derived.get("source_puissance_usage"),
        calcul="P_sortie / rendement_moteur (+ pertes fixes si connues)",
        inconnues=[] if _is_finite(derived["puissance_elec_usage_w"]) else ["rendement_moteur"],
    )

    eta_charge = _attr_first_finite(batterie, "rendement_charge")
    p_charge_nom_kw = _attr_first_finite(batterie, "puissance_charge_kw")
    if energie_utile_imposee_kwh is None and charger_batterie and _is_finite(temps_charge_cible_h) and _is_finite(p_charge_nom_kw) and _is_finite(eta_charge):
        derived["energie_batterie_cible_kwh"] = p_charge_nom_kw * float(temps_charge_cible_h) * eta_charge
        derived["notes"].append("Energie batterie cible deduite du temps de charge vise et de la puissance de charge nominale de la batterie.")
    else:
        derived["energie_batterie_cible_kwh"] = _safe_float(energie_utile_imposee_kwh)

    if charger_batterie:
        e_kwh = derived["energie_batterie_cible_kwh"]
        if _is_finite(e_kwh) and _is_finite(temps_charge_cible_h) and _is_finite(eta_charge) and eta_charge > 0.0:
            derived["puissance_recharge_batterie_w"] = (float(e_kwh) / float(temps_charge_cible_h) / eta_charge) * 1000.0
            derived["source_puissance_recharge"] = "energie_cible / temps_charge / rendement_charge"
        elif _is_finite(p_charge_nom_kw):
            derived["puissance_recharge_batterie_w"] = p_charge_nom_kw * 1000.0
            derived["source_puissance_recharge"] = "batterie.puissance_charge_kw"
            derived["notes"].append("Puissance de recharge reprise depuis la batterie faute de cible energie/temps complete.")
        else:
            _push_local_inconnue(
                "partielles",
                "puissance_recharge_batterie_w",
                "La puissance de recharge exige soit energie cible + temps + rendement de charge, soit une puissance de charge explicite.",
            )
    else:
        derived["puissance_recharge_batterie_w"] = 0.0
        derived["source_puissance_recharge"] = "decision_mode_sans_recharge"

    _set_detail(
        "puissance_recharge_batterie_w",
        valeur=derived["puissance_recharge_batterie_w"],
        statut="ok" if _is_finite(derived["puissance_recharge_batterie_w"]) else ("partiel" if charger_batterie else "ok"),
        source=derived.get("source_puissance_recharge"),
        calcul="energie_batterie_cible_kwh / temps_charge_cible_h / rendement_charge",
        inconnues=[] if _is_finite(derived["puissance_recharge_batterie_w"]) else ["energie_batterie_cible_kwh", "temps_charge_cible_h", "rendement_charge"],
        notes=["Recharge explicitement inactive."] if not charger_batterie else [],
    )

    if derived["tension_bus_dc_v"] is None:
        tension_candidate = _first_finite(
            _attr_first_finite(batterie, "tension_charge_v", "tension_nominale_v"),
            _attr_first_finite(moteur_electrique, "tension_bus_v"),
        )
        if tension_candidate is not None:
            derived["tension_bus_dc_v"] = tension_candidate
            if _attr_first_finite(batterie, "tension_charge_v") == tension_candidate:
                derived["source_tension_bus"] = "batterie.tension_charge_v"
            elif _attr_first_finite(batterie, "tension_nominale_v") == tension_candidate:
                derived["source_tension_bus"] = "batterie.tension_nominale_v"
            else:
                derived["source_tension_bus"] = "moteur_electrique.tension_bus_v"
    _set_detail(
        "tension_bus_dc_v",
        valeur=derived["tension_bus_dc_v"],
        statut="ok" if _is_finite(derived["tension_bus_dc_v"]) else "partiel",
        source=derived.get("source_tension_bus") or ("entree_utilisateur" if _is_finite(tension_bus_dc_v) else None),
        calcul="reprise explicite ou caracteristique composant",
        inconnues=[] if _is_finite(derived["tension_bus_dc_v"]) else ["tension_bus_dc_v"],
    )

    if derived["puissance_bus_dc_totale_w"] is None:
        p_usage = _safe_float(derived.get("puissance_elec_usage_w"))
        p_aux = _safe_float(derived.get("puissance_auxiliaire_w"))
        p_recharge = _safe_float(derived.get("puissance_recharge_batterie_w"))
        if p_usage is None:
            _push_local_inconnue("impossibles", "puissance_bus_dc_totale_w", "Impossible sans puissance electrique d'usage.")
        elif p_aux is None:
            _push_local_inconnue("partielles", "puissance_bus_dc_totale_w", "Puissance auxiliaire absente : la puissance bus DC totale ne peut pas etre fermee.")
        elif charger_batterie and p_recharge is None:
            _push_local_inconnue("partielles", "puissance_bus_dc_totale_w", "Recharge batterie demandee mais puissance de recharge inconnue.")
        else:
            p_bus_total = p_usage + p_aux + p_recharge
            if p_bus_total > 0.0:
                derived["puissance_bus_dc_totale_w"] = p_bus_total
    _set_detail(
        "puissance_bus_dc_totale_w",
        valeur=derived["puissance_bus_dc_totale_w"],
        statut="ok" if _is_finite(derived["puissance_bus_dc_totale_w"]) else "partiel",
        source="entree_utilisateur" if _is_finite(puissance_bus_dc_w) else "somme_usage_auxiliaires_recharge",
        calcul="puissance_elec_usage_w + puissance_auxiliaire_w + puissance_recharge_batterie_w",
        inconnues=[] if _is_finite(derived["puissance_bus_dc_totale_w"]) else ["puissance_elec_usage_w", "puissance_auxiliaire_w", "puissance_recharge_batterie_w"],
    )

    if _is_finite(derived.get("puissance_bus_dc_totale_w")) and _is_finite(derived.get("tension_bus_dc_v")) and float(derived["tension_bus_dc_v"]) > 0.0:
        derived["courant_bus_dc_a"] = float(derived["puissance_bus_dc_totale_w"]) / float(derived["tension_bus_dc_v"])

    p_bus_design_w = _safe_float(derived.get("puissance_bus_dc_totale_w"))
    beta = _safe_float(fraction_temps_generation_beta)
    if p_bus_design_w is not None:
        if beta is not None and 0.0 < beta <= 1.0:
            derived["puissance_bus_dc_instantanee_w"] = p_bus_design_w / beta
            derived["notes"].append("Puissance instantanee de generation appliquee via la fraction de fonctionnement beta.")
        elif fraction_temps_generation_beta is None:
            _push_local_inconnue(
                "partielles",
                "puissance_bus_dc_instantanee_w",
                "beta absent : la puissance instantanee de generation n'est pas deduite.",
            )
        else:
            _push_local_inconnue(
                "impossibles",
                "fraction_temps_generation_beta",
                "beta doit etre dans ]0, 1].",
            )
    _set_detail(
        "puissance_bus_dc_instantanee_w",
        valeur=derived["puissance_bus_dc_instantanee_w"],
        statut="ok" if _is_finite(derived["puissance_bus_dc_instantanee_w"]) else "partiel",
        source="fraction_temps_generation_beta" if beta is not None else None,
        calcul="puissance_bus_dc_totale_w / beta",
        inconnues=[] if _is_finite(derived["puissance_bus_dc_instantanee_w"]) else ["fraction_temps_generation_beta"],
    )

    p_bus_inst_w = _safe_float(derived.get("puissance_bus_dc_instantanee_w"))
    if p_bus_inst_w is not None:
        derived["puissance_mecanique_alternateur_borne_basse_w"] = p_bus_inst_w
        eta_alt = _attr_first_finite(alternateur, "rendement_alternateur_impose")
        if eta_alt is not None and eta_alt > 0.0:
            derived["puissance_mecanique_alternateur_requise_w"] = p_bus_inst_w / eta_alt
        else:
            _push_local_inconnue(
                "partielles",
                "puissance_mecanique_alternateur_requise_w",
                "Le rendement alternateur est requis pour conclure la puissance mecanique alternateur requise.",
            )
        eta_chaine_meca = None
        rendements = []
        manquants = []
        eta_liaison = _safe_float(rendement_liaison_meca_alt)
        eta_boite = _safe_float(rendement_boite)
        if eta_liaison is None:
            manquants.append("rendement_liaison_meca_alt")
        elif eta_liaison > 0.0:
            rendements.append(eta_liaison)
        else:
            manquants.append("rendement_liaison_meca_alt")
        if eta_boite is None:
            manquants.append("rendement_boite")
        elif eta_boite > 0.0:
            rendements.append(eta_boite)
        else:
            manquants.append("rendement_boite")
        if manquants:
            _push_local_inconnue(
                "partielles",
                "rendement_chaine_mecanique",
                f"Rendements manquants ou invalides : {', '.join(manquants)}.",
            )
        else:
            eta_chaine_meca = math.prod(rendements)

        derived["rendement_chaine_mecanique"] = eta_chaine_meca
        derived["puissance_moteur_thermique_borne_basse_w"] = p_bus_inst_w
        p_alt_req = _safe_float(derived.get("puissance_mecanique_alternateur_requise_w"))
        if p_alt_req is not None and eta_chaine_meca is not None:
            derived["puissance_moteur_thermique_requise_w"] = p_alt_req / eta_chaine_meca
        else:
            _push_local_inconnue(
                "partielles",
                "puissance_moteur_thermique_requise_w",
                "La puissance thermique requise depend du rendement alternateur puis des rendements liaison/boite explicites.",
            )
        _set_detail(
            "puissance_mecanique_alternateur_requise_w",
            valeur=derived["puissance_mecanique_alternateur_requise_w"],
            statut="ok" if _is_finite(derived["puissance_mecanique_alternateur_requise_w"]) else "partiel",
            source="rendement_alternateur_impose",
            calcul="puissance_bus_dc_instantanee_w / rendement_alternateur",
            inconnues=[] if _is_finite(derived["puissance_mecanique_alternateur_requise_w"]) else ["rendement_alternateur_impose"],
        )
        _set_detail(
            "puissance_moteur_thermique_requise_w",
            valeur=derived["puissance_moteur_thermique_requise_w"],
            statut="ok" if _is_finite(derived["puissance_moteur_thermique_requise_w"]) else "partiel",
            source="rendement_chaine_mecanique",
            calcul="puissance_mecanique_alternateur_requise_w / (rendement_liaison_meca_alt * rendement_boite)",
            inconnues=[] if _is_finite(derived["puissance_moteur_thermique_requise_w"]) else ["rendement_alternateur_impose", "rendement_liaison_meca_alt", "rendement_boite"],
        )
    else:
        _set_detail(
            "puissance_mecanique_alternateur_requise_w",
            valeur=None,
            statut="partiel",
            source=None,
            calcul="puissance_bus_dc_instantanee_w / rendement_alternateur",
            inconnues=["puissance_bus_dc_instantanee_w", "rendement_alternateur_impose"],
        )
        _set_detail(
            "puissance_moteur_thermique_requise_w",
            valeur=None,
            statut="partiel",
            source=None,
            calcul="puissance_mecanique_alternateur_requise_w / (rendement_liaison_meca_alt * rendement_boite)",
            inconnues=["puissance_mecanique_alternateur_requise_w", "rendement_liaison_meca_alt", "rendement_boite"],
        )

    return derived


def _dedup_report_lists(rapport: Dict[str, Any]) -> None:
    for section in ("inconnues", "alertes"):
        bloc = _safe_dict(rapport.get(section))
        new_bloc: Dict[str, Any] = {}
        for category, values in bloc.items():
            seen = set()
            kept = []
            for item in list(values or []):
                if not isinstance(item, dict):
                    continue
                # Hash the complete dictionary content to avoid duplicate reasons with same names
                sig = tuple(sorted((str(k), str(v)) for k, v in item.items()))
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


def _get_piece_ref(obj: Any) -> Optional[str]:
    cls_name = type(obj).__name__
    mapping = {
        "Cylindre": "cylindre", "Piston": "piston", "JointPiston": "joint_piston",
        "CorpsBielle": "bielle", "Deplaceur": "deplaceur", "JointDeplaceur": "joint_deplaceur",
        "ArbrePiston": "arbre_piston", "CoussinetArbrePiston": "coussinet_arbre_piston",
        "ArbreVilbrequin": "arbre_vilebrequin", "Vilbrequin": "vilbrequin",
        "RoulementAiguilleArbre": "roulement_aiguille_arbre",
        "RoulementAiguilleArbreVilebrequin": "roulement_aiguille_arbre_vilebrequin",
        "CouvercleCylindre": "couvercle_cylindre", "VisCouvercleCylindre": "vis_couvercle_cylindre",
        "ArbreMoteur": "arbre", "ClavetteArbre": "clavette_arbre"
    }
    return mapping.get(cls_name)


def _serialize_ref(obj: Any, depth: int = 0, max_depth: int = 1) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        if depth > max_depth:
            return {"truncated": True}
        return {str(k): _serialize_ref(v, depth=depth + 1, max_depth=max_depth) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        if depth > max_depth:
            return []
        return [_serialize_ref(v, depth=depth + 1, max_depth=max_depth) for v in obj]
    if hasattr(obj, "__dataclass_fields__") or hasattr(obj, "__dict__"):
        type_name = type(obj).__name__
        ref_name = _get_piece_ref(obj)
        res: Dict[str, Any] = {"type": type_name}
        if ref_name:
            res["ref"] = f"pieces.{ref_name}"
        res["truncated"] = True
        
        if depth <= max_depth:
            resume = {}
            try:
                attrs = asdict(obj) if is_dataclass(obj) else vars(obj)
                for k, v in attrs.items():
                    if isinstance(v, (int, float, str, bool)) and not k.startswith("_"):
                        resume[k] = v
                if resume:
                    res["resume"] = resume
            except Exception:
                pass
        return res
    return str(obj)


def _callable_accepts_varkw(callable_obj: Any) -> bool:
    try:
        sig = inspect.signature(callable_obj)
    except Exception:
        return True
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())


def _filter_kwargs_for_callable(callable_obj: Any, kwargs: Mapping[str, Any]) -> Dict[str, Any]:
    if _callable_accepts_varkw(callable_obj):
        return dict(kwargs)
    clean = {k: v for k, v in dict(kwargs).items() if v is not None}
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


def _fuel_catalog() -> Dict[str, Any]:
    if Carburant is None or CompositionElementaireCombustible is None:
        return {}
    return {
        "diesel": Carburant(
            nom="diesel",
            pci_j_kg=42.7e6,
            densite_kg_m3=835.0,
            composition=CompositionElementaireCombustible(carbone_mol=12.0, hydrogene_mol=23.0),
        ),
        "essence": Carburant(
            nom="essence",
            pci_j_kg=43.0e6,
            densite_kg_m3=745.0,
            composition=CompositionElementaireCombustible(carbone_mol=8.0, hydrogene_mol=18.0),
        ),
        "ethanol": Carburant(
            nom="ethanol",
            pci_j_kg=26.8e6,
            densite_kg_m3=789.0,
            composition=CompositionElementaireCombustible(carbone_mol=2.0, hydrogene_mol=6.0, oxygene_mol=1.0),
        ),
        "methanol": Carburant(
            nom="methanol",
            pci_j_kg=19.9e6,
            densite_kg_m3=792.0,
            composition=CompositionElementaireCombustible(carbone_mol=1.0, hydrogene_mol=4.0, oxygene_mol=1.0),
        ),
        "gpl": Carburant(
            nom="gpl",
            pci_j_kg=46.1e6,
            densite_kg_m3=540.0,
            composition=CompositionElementaireCombustible(carbone_mol=3.0, hydrogene_mol=8.0),
        ),
        "gnv": Carburant(
            nom="gnv",
            pci_j_kg=50.0e6,
            densite_kg_m3=0.72,
            composition=CompositionElementaireCombustible(carbone_mol=1.0, hydrogene_mol=4.0),
        ),
        "hydrogene": Carburant(
            nom="hydrogene",
            pci_j_kg=120.0e6,
            densite_kg_m3=0.084,
            composition=CompositionElementaireCombustible(carbone_mol=0.0, hydrogene_mol=2.0),
        ),
    }


def _normalize_multifuel_names(
    carburant: Optional[Any],
    carburants_autorises: Optional[Sequence[Any]] = None,
    *,
    mode_carburant: Optional[str] = None,
) -> Tuple[str, ...]:
    catalog = _fuel_catalog()
    if not catalog:
        return ()

    names: list[str] = []
    for raw in list(carburants_autorises or []):
        key = str(raw).strip().lower()
        if key in catalog and key not in names:
            names.append(key)

    fuel_token = None if carburant is None else str(carburant).strip().lower()
    mode_token = None if mode_carburant is None else str(mode_carburant).strip().lower()
    is_multi = mode_token in {"multi", "multicarburant", "multi_carburant", "multi_optimise_pire_cas"} or fuel_token in {None, "", "multi", "multicarburant", "multi_carburant"}

    if names:
        return tuple(names)
    if is_multi:
        return tuple(catalog.keys())
    if fuel_token in catalog:
        return (fuel_token,)
    return ()


def _build_multifuel_strategy_report(
    *,
    moteur_thermique: Any,
    definition_moteur: Mapping[str, Any],
    puissance_utile_w: Optional[float],
) -> Optional[Dict[str, Any]]:
    fuel_names = _normalize_multifuel_names(
        definition_moteur.get("carburant"),
        definition_moteur.get("carburants_autorises"),
        mode_carburant=definition_moteur.get("mode_carburant"),
    )
    if len(fuel_names) <= 1:
        return None

    catalog = _fuel_catalog()
    rendement_global = _safe_float(definition_moteur.get("rendement_global"))
    resultats: Dict[str, Any] = {}
    dimensionnant_nom: Optional[str] = None
    dimensionnant_sig: Tuple[float, float, float] = (-1.0, -1.0, -1.0)
    meilleur_nom: Optional[str] = None
    meilleur_sig: Tuple[float, float, float] = (float("inf"), float("inf"), float("inf"))

    for fuel_name in fuel_names:
        carburant_obj = catalog.get(fuel_name)
        if carburant_obj is None:
            continue

        item: Dict[str, Any] = {
            "carburant": fuel_name,
            "intrinseque": {
                "pci_mj_kg": carburant_obj.pci_j_kg / 1e6,
                "densite_kg_m3": carburant_obj.densite_kg_m3,
                "densite_energetique_volumique_mj_l": (
                    carburant_obj.densite_energetique_volumique_j_m3() / 1e9
                    if carburant_obj.densite_kg_m3 is not None
                    else None
                ),
                "afr_stoech_massique": carburant_obj.rapport_air_stoech_massique() if carburant_obj.composition is not None else carburant_obj.rapport_air_carburant_stoech_massique,
            },
        }

        bilan = None
        if moteur_thermique is not None and hasattr(moteur_thermique, "analyser_bilan_carburant"):
            kwargs = _filter_kwargs_for_callable(
                moteur_thermique.analyser_bilan_carburant,
                {
                    "carburant": carburant_obj,
                    "puissance_utile_w": puissance_utile_w,
                    "rendement_global": rendement_global,
                },
            )
            try:
                bilan = moteur_thermique.analyser_bilan_carburant(**kwargs)
            except Exception as exc:
                bilan = {"erreur": str(exc)}
        item["bilan"] = bilan

        bilan_block = _safe_dict(_safe_dict(bilan).get("bilan"))
        debit_massique = _safe_float(bilan_block.get("debit_massique_carburant_kg_s"))
        debit_volumique = _safe_float(bilan_block.get("debit_volumique_carburant_m3_s"))
        puissance_chimique = _safe_float(bilan_block.get("puissance_chimique_w"))
        debit_massique_proxy = None
        debit_volumique_proxy = None
        if _is_finite(puissance_utile_w):
            debit_massique_proxy = float(puissance_utile_w) / float(carburant_obj.pci_j_kg)
            if _is_finite(carburant_obj.densite_kg_m3) and float(carburant_obj.densite_kg_m3) > 0.0:
                debit_volumique_proxy = debit_massique_proxy / float(carburant_obj.densite_kg_m3)
        item["dimensionnement"] = {
            "debit_massique_carburant_kg_s": debit_massique,
            "debit_volumique_carburant_m3_s": debit_volumique,
            "puissance_chimique_w": puissance_chimique,
            "debit_massique_proxy_kg_s_sans_rendement": debit_massique_proxy,
            "debit_volumique_proxy_m3_s_sans_rendement": debit_volumique_proxy,
        }
        resultats[fuel_name] = item

        worst_sig = (
            -1.0 if (debit_volumique is None and debit_volumique_proxy is None) else float(debit_volumique if debit_volumique is not None else debit_volumique_proxy),
            -1.0 if (debit_massique is None and debit_massique_proxy is None) else float(debit_massique if debit_massique is not None else debit_massique_proxy),
            -1.0 if puissance_chimique is None else float(puissance_chimique),
        )
        if worst_sig > dimensionnant_sig:
            dimensionnant_sig = worst_sig
            dimensionnant_nom = fuel_name

        best_sig = (
            float("inf") if (debit_volumique is None and debit_volumique_proxy is None) else float(debit_volumique if debit_volumique is not None else debit_volumique_proxy),
            float("inf") if (debit_massique is None and debit_massique_proxy is None) else float(debit_massique if debit_massique is not None else debit_massique_proxy),
            float("inf") if puissance_chimique is None else float(puissance_chimique),
        )
        if best_sig < meilleur_sig:
            meilleur_sig = best_sig
            meilleur_nom = fuel_name

    return {
        "mode": "multi_carburant_optimise_sur_pire_cas",
        "carburants_consideres": list(fuel_names),
        "carburant_dimensionnant": dimensionnant_nom,
        "carburant_optimal": meilleur_nom,
        "comparatif": resultats,
        "notes_modele": [
            "Le dimensionnement conservatif retient le carburant le plus penalisant en debit massique et volumique.",
            "Le carburant optimal est le plus favorable parmi ceux explicitement compares sur les donnees calculables disponibles.",
        ],
    }


def _extract_component_piece_reports(rapports_composants: Mapping[str, Any]) -> Dict[str, Any]:
    nested: Dict[str, Any] = {}
    for composant_nom, composant_rapport in dict(rapports_composants or {}).items():
        if not isinstance(composant_rapport, Mapping):
            continue
        pieces_block = composant_rapport.get("pieces")
        if not isinstance(pieces_block, Mapping):
            continue
        for piece_nom, piece_rapport in pieces_block.items():
            nested[f"{composant_nom}.{piece_nom}"] = piece_rapport
    return nested


def _build_nested_piece_inventory(rapports_pieces: Mapping[str, Any]) -> Dict[str, Any]:
    inventory: Dict[str, Any] = {}
    for full_name, rapport in dict(rapports_pieces or {}).items():
        if "." not in str(full_name):
            continue
        composant_nom, piece_nom = str(full_name).split(".", 1)
        piece_type = None
        if isinstance(rapport, Mapping):
            piece_type = rapport.get("piece")
        inventory[full_name] = {
            "type": piece_type or piece_nom,
            "construit": True,
            "rapport_disponible": isinstance(rapport, Mapping) and "inconnues" in rapport,
            "source_composant": composant_nom,
            "piece_nom": piece_nom,
        }
    return inventory


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


def construire_moteur_electrique(**kwargs: Any) -> Any:
    defaults = {
        "puissance_max_w": 100000.0,
        "regime_max_rpm": 6000.0,
        "couple_max_nm": 300.0,
        "tension_bus_v": 400.0,
        "rendement_moteur": 0.92,
        "pertes_fixes_w": 500.0,
    }
    defaults.update(kwargs)
    return MoteurElectrique(**_filter_kwargs_for_callable(MoteurElectrique, defaults))


def construire_batterie(**kwargs: Any) -> Any:
    defaults = {
        "tension_nominale_v": 400.0,
        "tension_charge_v": 420.0,
        "rendement_charge": 0.90,
        "densite_energetique_kwh_kg": 0.18,
        "puissance_charge_kw": 20.0,
    }
    defaults.update(kwargs)
    return Batterie(**_filter_kwargs_for_callable(Batterie, defaults))


def construire_alternateur(**kwargs: Any) -> Any:
    defaults = {
        "connexion": "Y",
        "nombre_poles": 12,
    }
    defaults.update(kwargs)
    return Alternateur(**_filter_kwargs_for_callable(Alternateur, defaults))


def construire_moteur_thermique_base(**kwargs: Any) -> Any:
    defaults = {
        "temps_moteur": 4,
        "nombre_cylindres": 4,
        "alesage_m": 0.08,
        "course_m": 0.08,
        "rpm_nominal": 3000.0,
        "pme_nominale_pa": 8.0e5,
        "rendement_mecanique_nominal": 0.85,
    }
    defaults.update(kwargs)
    return MoteurThermique(**_filter_kwargs_for_callable(MoteurThermique, defaults))


def construire_boite_crabots(**kwargs: Any) -> Any:
    return BoiteCrabots(**_filter_kwargs_for_callable(BoiteCrabots, kwargs))


def construire_architecture(**kwargs: Any) -> Any:
    return Architecture(**_filter_kwargs_for_callable(Architecture, kwargs))


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
    import traceback
    if "construction_debug" not in rapport:
        rapport["construction_debug"] = {}
        
    debug_info = {
        "kwargs": _serialize_ref(_filter_kwargs_for_callable(piece_cls, raw_kwargs)) if piece_cls else {},
        "kwargs_bruts": _to_jsonable({k: v for k, v in raw_kwargs.items() if v is not None}, max_depth=2),
        "construit": False,
        "rapport_disponible": False,
        "type": piece_cls.__name__ if piece_cls else None,
        "erreur": None,
        "trace": None
    }
    
    if piece_cls is None:
        debug_info["erreur"] = f"Classe indisponible pour {nom}."
        rapport["construction_debug"][nom] = debug_info
        _push_inconnue(rapport, "impossibles", nom, f"Classe indisponible pour {nom}.")
        return None
        
    kwargs = _filter_kwargs_for_callable(piece_cls, raw_kwargs)
    required = [p for p in _required_params_for_callable(piece_cls) if p not in kwargs]
    if required:
        debug_info["erreur"] = f"Construction impossible sans {required}."
        rapport["construction_debug"][nom] = debug_info
        _push_inconnue(rapport, "partielles", nom, f"Construction impossible sans {required}.")
        return None
        
    try:
        obj = piece_cls(**kwargs)
        debug_info["construit"] = True
        debug_info["rapport_disponible"] = True
        rapport["construction_debug"][nom] = debug_info
        rapport["construction"][nom] = {
            "construit": True,
            "type": debug_info["type"],
            "kwargs": _serialize_ref(kwargs, max_depth=1)
        }
        return obj
    except Exception as exc:
        debug_info["erreur"] = str(exc)
        debug_info["trace"] = traceback.format_exc()
        rapport["construction_debug"][nom] = debug_info
        rapport["construction"][nom] = {
            "construit": False,
            "type": debug_info["type"],
            "erreur": str(exc),
            "kwargs": _serialize_ref(kwargs, max_depth=1)
        }
        _push_inconnue(rapport, "impossibles", f"construction {nom}", str(exc))
        return None


def construire_pieces_depuis_systeme(
    *,
    rapport_systeme: Dict[str, Any],
    definition_moteur_thermique: Optional[Dict[str, Any]] = None,
    pieces_definition: Optional[Dict[str, Any]] = None,
    moteur_thermique_obj: Any = None,
    systeme_obj: Any = None,
    puissance_traction_kw_for_fallback: Optional[float] = None,
    rapports_composants: Optional[Dict[str, Any]] = None,
    return_report: bool = False,
) -> Any:
    synth = _safe_dict(rapport_systeme.get("synthese"))
    mt_systeme = _safe_dict(synth.get("moteur_thermique"))
    definition_mt = _normaliser_definition_moteur_thermique(definition_moteur_thermique)
    mt = _merge_dict_non_none(mt_systeme, definition_mt)
    piece_defaults = _default_piece_definitions()
    pieces_def = _merge_dict_non_none(piece_defaults, _safe_dict(pieces_definition))

    rapport: Dict[str, Any] = {
        "construction": {},
        "inconnues": {"impossibles": [], "partielles": []},
        "notes_modele": [],
        "propagation_debug": {},
        "rapports_pieces": {},
    }
    if piece_defaults:
        rapport["notes_modele"].append(
            "Standards projet appliques aux pieces mecaniques pour fermer les calculs "
            "(materiaux/catalogues explicites issus de la bibliotheque interne)."
        )

    def _trace(nom: str, valeur: Any, source: str, statut: str = "calculée") -> None:
        if valeur is not None:
            rapport["propagation_debug"][nom] = {"valeur": valeur, "source": source, "statut": statut}

    # Données système initiales
    alesage_sys = _first_finite(mt.get("alesage_m"), _get_nested(rapport_systeme, "cao", "moteur_thermique", "alesage_mm"))
    if alesage_sys is not None and alesage_sys > 1.0:
        alesage_sys = alesage_sys / 1000.0
    course_sys = _first_finite(mt.get("course_m"), _get_nested(rapport_systeme, "cao", "moteur_thermique", "course_mm"))
    if course_sys is not None and course_sys > 1.0:
        course_sys = course_sys / 1000.0
    rpm_sys = _first_finite(mt.get("rpm_nominal"), mt.get("rpm"))
    pme_sys = _first_finite(mt.get("pme_pa"), mt.get("pme_nominale_pa"))
    pression_max_sys = _first_finite(
        mt.get("pression_max_pa"),
        _get_nested(rapport_systeme, "entrees", "moteur_thermique_criteres", "pression_max_pa"),
    )
    epaisseur_cylindre_sys = _first_finite(
        mt.get("epaisseur_cylindre_retenue_m"),
        _get_nested(rapports_composants or {}, "moteur_thermique_point", "dimensionnement", "epaisseur_cylindre_retenue_m"),
    )
    couple_max_sys = _first_finite(mt.get("couple_max_Nm"), mt.get("couple_requis_Nm"))
    force_bielle_sys = _safe_float(mt.get("force_bielle_N"))

    _trace("rpm", rpm_sys, "Systeme / Input")
    _trace("couple_max_Nm", couple_max_sys, "Systeme / Input")

    pieces: Dict[str, Any] = {}

    _trace("alesage_m", alesage_sys, "definition_moteur_thermique.alesage_m", "entrée_directe")
    _trace("course_m", course_sys, "definition_moteur_thermique.course_m", "entrée_directe")

    # Calcul des puissances et couples
    puissance_indiquee_W = _get_nested(rapports_composants or {}, "moteur_thermique_point", "resultats", "puissance_indiquee_W")
    puissance_cible_systeme_W = None
    if _is_finite(puissance_traction_kw_for_fallback):
        puissance_cible_systeme_W = puissance_traction_kw_for_fallback * 1000.0
        _trace("puissance_cible_systeme_W", puissance_cible_systeme_W, "entrees.puissance_traction_kw * 1000", "cible_systeme")

    couple_moyen_Nm = None
    if _is_finite(rpm_sys) and rpm_sys > 0:
        omega_rad_s = 2 * math.pi * rpm_sys / 60.0
        
        if _is_finite(puissance_indiquee_W):
            _trace("couple_indique_moyen_Nm", puissance_indiquee_W / omega_rad_s, "moteur_thermique_point.resultats.puissance_indiquee_W / omega_rad_s", "calculée")
            
        if _is_finite(puissance_cible_systeme_W):
            _trace("couple_cible_moyen_Nm", puissance_cible_systeme_W / omega_rad_s, "puissance_cible_systeme_W / omega_rad_s", "calculée")
            
        puissance_W = _first_finite(mt_systeme.get("puissance_requise_W"), puissance_indiquee_W, puissance_cible_systeme_W)
        if _is_finite(puissance_W):
            couple_moyen_Nm = puissance_W / omega_rad_s
            _trace("couple_moyen_Nm", couple_moyen_Nm, "puissance priorisée / omega_rad_s", "calculée")

    # 1. Cylindre
    longueur_utile_input = _get_nested(pieces_def, "cylindre", "longueur_utile_m")
    if longueur_utile_input is None and _is_finite(course_sys):
        longueur_utile_input = course_sys * 1.5
        _trace("longueur_utile_m", longueur_utile_input, "fallback géométrique minimal : longueur_utile_m absente, utilisation de course_m pour permettre la construction du Cylindre", "fallback_minimal")
    else:
        _trace("longueur_utile_m", longueur_utile_input, "definition_moteur_thermique.longueur_utile_m", "entrée_directe")

    raw = _merge_dict_non_none({
        "alesage_m": alesage_sys,
        "course_m": course_sys,
        "longueur_utile_m": longueur_utile_input,
        "pression_service_pa": pme_sys,
        "pression_max_pa": pression_max_sys,
        "epaisseur_imposee_m": epaisseur_cylindre_sys,
        "materiau_cle": _get_nested(pieces_def, "cylindre", "materiau_cle"),
        "contrainte_admissible_pa": mt.get("contrainte_admissible_pa"),
        "densite_kg_m3": mt.get("densite_materiau_kg_m3"),
    }, _safe_dict(pieces_def.get("cylindre")))
    pieces["cylindre"] = _build_piece_instance(Cylindre, raw, rapport, "cylindre")
    if pieces.get("cylindre") is not None:
        _trace("cylindre_objet", True, "Cylindre(**kwargs_cyl)", "propagée")
    
    rapport_cyl = _safe_call_report(pieces.get("cylindre"))
    rapport["rapports_pieces"]["cylindre"] = rapport_cyl
    vals_cyl = _extract_cylindre_values(rapport_cyl)

    alesage_prop = _first_finite(vals_cyl.get("alesage_m"), alesage_sys)
    course_prop = _first_finite(vals_cyl.get("course_m"), course_sys)
    pression_max_prop = _first_finite(vals_cyl.get("pression_max_pa"), pression_max_sys)

    _trace("alesage_m", alesage_prop, "Cylindre")
    _trace("course_m", course_prop, "Cylindre")
    _trace("pression_max_pa", pression_max_prop, "Cylindre")

    # 2. Deplaceur
    raw = _merge_dict_non_none({
        "cylindre": pieces.get("cylindre"),
        "pression_froid_pa": pression_max_prop,
        "materiau_cle": _get_nested(pieces_def, "deplaceur", "materiau_cle"),
    }, _safe_dict(pieces_def.get("deplaceur")))
    pieces["deplaceur"] = _build_piece_instance(Deplaceur, raw, rapport, "deplaceur")
    # 3. Joint Deplaceur
    raw = _merge_dict_non_none({
        "deplaceur": pieces.get("deplaceur"),
        "cylindre": pieces.get("cylindre"),
        "materiau_joint_cle": _get_nested(pieces_def, "joint_deplaceur", "materiau_joint_cle"),
    }, _safe_dict(pieces_def.get("joint_deplaceur")))
    pieces["joint_deplaceur"] = _build_piece_instance(JointDeplaceur, raw, rapport, "joint_deplaceur")
    # 4. Piston
    raw = _merge_dict_non_none({
        "cylindre": pieces.get("cylindre"),
        "materiau_piston_cle": _get_nested(pieces_def, "piston", "materiau_piston_cle"),
        "pression_max_pa": pression_max_prop,
        "alesage_nominal_m": alesage_prop,
        "course_m": course_prop,
        "rpm": rpm_sys,
        "materiau_joint_cle": _get_nested(pieces_def, "piston", "materiau_joint_cle"),
    }, _safe_dict(pieces_def.get("piston")))
    pieces["piston"] = _build_piece_instance(Piston, raw, rapport, "piston")
    rapport_pist = _safe_call_report(pieces.get("piston"))
    rapport["rapports_pieces"]["piston"] = rapport_pist
    vals_pist = _extract_piston_values(rapport_pist)

    force_gaz_prop = vals_pist.get("force_gaz_n")
    force_nette_prop = vals_pist.get("force_axiale_nette_n")
    _trace("force_gaz_n", force_gaz_prop, "Piston")
    _trace("force_axiale_nette_n", force_nette_prop, "Piston")

    # Calcul de la force axiale pour la bielle
    force_axiale_bielle = None
    if force_nette_prop is not None and force_gaz_prop is not None:
        force_axiale_bielle = max(abs(force_nette_prop), abs(force_gaz_prop))
        _trace("force_axiale_max_N", force_axiale_bielle, "max(abs(Piston.force_nette), abs(Piston.force_gaz))")
    elif force_nette_prop is not None:
        force_axiale_bielle = abs(force_nette_prop)
        _trace("force_axiale_max_N", force_axiale_bielle, "Piston.force_nette")
    elif force_gaz_prop is not None:
        force_axiale_bielle = abs(force_gaz_prop)
        _trace("force_axiale_max_N", force_axiale_bielle, "Piston.force_gaz")
    elif force_bielle_sys is not None:
        force_axiale_bielle = force_bielle_sys
        _trace("force_axiale_max_N", force_axiale_bielle, "Systeme.force_bielle")

    # 5. Joint Piston
    raw = _merge_dict_non_none({
        "piston": pieces.get("piston"),
        "cylindre": pieces.get("cylindre"),
        "materiau_joint_cle": _get_nested(pieces_def, "joint_piston", "materiau_joint_cle"),
    }, _safe_dict(pieces_def.get("joint_piston")))
    pieces["joint_piston"] = _build_piece_instance(JointPiston, raw, rapport, "joint_piston")
    # 6. Arbre Piston
    raw = _merge_dict_non_none({
        "piston": pieces.get("piston"),
        "cylindre": pieces.get("cylindre"),
        "rpm": rpm_sys,
        "materiau_cle": _get_nested(pieces_def, "arbre_piston", "materiau_cle"),
    }, _safe_dict(pieces_def.get("arbre_piston")))
    pieces["arbre_piston"] = _build_piece_instance(ArbrePiston, raw, rapport, "arbre_piston")
    # 7. Bielle
    longueur_bielle_input = _first_finite(_get_nested(pieces_def, "bielle", "longueur_bielle_m"), definition_mt.get("longueur_bielle_m"))

    raw = _merge_dict_non_none({
        "piston": pieces.get("piston"),
        "arbre_piston": pieces.get("arbre_piston"),
        "cylindre": pieces.get("cylindre"),
        "moteur_thermique": moteur_thermique_obj if moteur_thermique_obj is not None else mt,
        "longueur_bielle_m": longueur_bielle_input,
        "force_axiale_max_N": force_axiale_bielle,
        "rpm": rpm_sys,
        "materiau_cle": _get_nested(pieces_def, "bielle", "materiau_cle"),
    }, _safe_dict(pieces_def.get("bielle")))
    pieces["bielle"] = _build_piece_instance(CorpsBielle, raw, rapport, "bielle")
    rapport_bielle = _safe_call_report(pieces.get("bielle"))
    rapport["rapports_pieces"]["bielle"] = rapport_bielle
    vals_bielle = _extract_bielle_values(rapport_bielle)
    
    longueur_bielle_prop = _first_finite(vals_bielle.get("longueur_bielle_m"), longueur_bielle_input)
    _trace("longueur_bielle_m", longueur_bielle_prop, "Bielle / input")

    # 8. Coussinet Arbre Piston
    raw = _merge_dict_non_none({
        "arbre_piston": pieces.get("arbre_piston"),
        "rpm": rpm_sys,
        "materiau_coussinet": _get_nested(pieces_def, "coussinet_arbre_piston", "materiau_coussinet"),
    }, _safe_dict(pieces_def.get("coussinet_arbre_piston")))
    pieces["coussinet_arbre_piston"] = _build_piece_instance(CoussinetArbrePiston, raw, rapport, "coussinet_arbre_piston")
    # 9. Arbre Vilebrequin
    raw = _merge_dict_non_none({
        "cylindre": pieces.get("cylindre"),
        "piston": pieces.get("piston"),
        "bielle": pieces.get("bielle"),
        "moteur_thermique": moteur_thermique_obj,
        "rpm": rpm_sys,
        "couple_max_Nm": couple_max_sys,
        "course_m": course_prop,
        "force_bielle_effective_N": force_axiale_bielle,
        "materiau_cle": _get_nested(pieces_def, "arbre_vilebrequin", "materiau_cle") or mt.get("materiau_cle"),
        "limite_fatigue_pa": _get_nested(pieces_def, "arbre_vilebrequin", "limite_fatigue_pa") or mt.get("limite_fatigue_pa"),
        "limite_elastique_pa": _get_nested(pieces_def, "arbre_vilebrequin", "limite_elastique_pa") or mt.get("limite_elastique_pa"),
    }, _safe_dict(pieces_def.get("arbre_vilebrequin")))
    pieces["arbre_vilebrequin"] = _build_piece_instance(ArbreVilbrequin, raw, rapport, "arbre_vilebrequin")
    # 10. Vilbrequin
    raw = _merge_dict_non_none({
        "arbre": pieces.get("arbre_vilebrequin"),
        "cylindre": pieces.get("cylindre"),
        "piston": pieces.get("piston"),
        "bielle": pieces.get("bielle"),
        "deplaceur": pieces.get("deplaceur"),
        "systeme_complet": systeme_obj,
        "moteur_thermique": moteur_thermique_obj,
        "course_m": course_prop,
        "rpm": rpm_sys,
        "couple_max_Nm": couple_max_sys,
        "nb_manetons": _safe_int(mt.get("nombre_cylindres")),
        "nb_journaux_principaux": (_safe_int(mt.get("nombre_cylindres")) + 1) if _safe_int(mt.get("nombre_cylindres")) is not None else None,
        "materiau_cle": _get_nested(pieces_def, "vilbrequin", "materiau_cle") or mt.get("materiau_cle"),
        "limite_fatigue_pa": _get_nested(pieces_def, "vilbrequin", "limite_fatigue_pa") or mt.get("limite_fatigue_pa"),
        "limite_elastique_pa": _get_nested(pieces_def, "vilbrequin", "limite_elastique_pa") or mt.get("limite_elastique_pa"),
    }, _safe_dict(pieces_def.get("vilbrequin")))
    pieces["vilbrequin"] = _build_piece_instance(Vilbrequin, raw, rapport, "vilbrequin")
    # 11. Roulement Aiguille Arbre
    raw = _merge_dict_non_none({
        "vilbrequin": pieces.get("vilbrequin"),
        "arbre_vilbrequin": pieces.get("arbre_vilebrequin"),
        "bielle": pieces.get("bielle"),
        "piston": pieces.get("piston"),
        "cylindre": pieces.get("cylindre"),
        "rpm": rpm_sys,
        "couple_max_Nm": couple_max_sys,
        "rayon_manivelle_m": (0.5 * course_prop) if _is_finite(course_prop) else None,
    }, _safe_dict(pieces_def.get("roulement_aiguille_arbre")))
    pieces["roulement_aiguille_arbre"] = _build_piece_instance(RoulementAiguilleArbre, raw, rapport, "roulement_aiguille_arbre")
    # 12. Roulement Aiguille Arbre Vilebrequin
    raw = _merge_dict_non_none({
        "corps_bielle": pieces.get("bielle"),
        "arbre_vilebrequin": pieces.get("arbre_vilebrequin"),
        "moteur_thermique": moteur_thermique_obj,
        "rpm_vilebrequin": rpm_sys,
    }, _safe_dict(pieces_def.get("roulement_aiguille_arbre_vilebrequin")))
    pieces["roulement_aiguille_arbre_vilebrequin"] = _build_piece_instance(RoulementAiguilleArbreVilebrequin, raw, rapport, "roulement_aiguille_arbre_vilebrequin")
    # 13. Couvercle Cylindre
    raw = _merge_dict_non_none({
        "cylindre": pieces.get("cylindre"),
        "pression_max_pa": pression_max_prop,
        "materiau_cle": _get_nested(pieces_def, "couvercle_cylindre", "materiau_cle"),
    }, _safe_dict(pieces_def.get("couvercle_cylindre")))
    pieces["couvercle_cylindre"] = _build_piece_instance(CouvercleCylindre, raw, rapport, "couvercle_cylindre")
    # 14. Vis Couvercle Cylindre
    raw = _merge_dict_non_none({
        "cylindre": pieces.get("cylindre"),
        "couvercle": pieces.get("couvercle_cylindre"),
        "pression_max_pa": pression_max_prop,
        "classe_vis_iso898": _get_nested(pieces_def, "vis_couvercle_cylindre", "classe_vis_iso898"),
    }, _safe_dict(pieces_def.get("vis_couvercle_cylindre")))
    pieces["vis_couvercle_cylindre"] = _build_piece_instance(VisCouvercleCylindre, raw, rapport, "vis_couvercle_cylindre")
    # 15. Arbre
    raw = _merge_dict_non_none({
        "cylindre": pieces.get("cylindre"),
        "moteur_thermique": moteur_thermique_obj,
        "systeme_complet": systeme_obj,
        "vilbrequin": pieces.get("vilbrequin"),
        "roulement_aiguille": pieces.get("roulement_aiguille_arbre"),
        "couple_max_Nm": couple_max_sys,
        "rpm": rpm_sys,
        "nombre_cylindres": _safe_int(mt.get("nombre_cylindres")),
        "materiau_arbre_cle": _get_nested(pieces_def, "arbre", "materiau_arbre_cle"),
    }, _safe_dict(pieces_def.get("arbre")))
    pieces["arbre"] = _build_piece_instance(ArbreMoteur, raw, rapport, "arbre")
    # 16. Clavette Arbre
    raw = _merge_dict_non_none({
        "arbre": pieces.get("arbre"),
        "arbre_vilbrequin": pieces.get("arbre_vilebrequin"),
        "roulement_aiguille_arbre": pieces.get("roulement_aiguille_arbre"),
        "vilbrequin": pieces.get("vilbrequin"),
        "moteur_thermique": moteur_thermique_obj,
        "couple_transmis_Nm": couple_max_sys,
        "materiau_clavette_cle": _get_nested(pieces_def, "clavette_arbre", "materiau_clavette_cle"),
    }, _safe_dict(pieces_def.get("clavette_arbre")))
    pieces["clavette_arbre"] = _build_piece_instance(ClavetteArbre, raw, rapport, "clavette_arbre")

    # 17. Raffinement : seconde passe de propagation entre portees, arbre et clavette
    raw = _merge_dict_non_none({
        "vilbrequin": pieces.get("vilbrequin"),
        "arbre_vilbrequin": pieces.get("arbre_vilebrequin"),
        "bielle": pieces.get("bielle"),
        "piston": pieces.get("piston"),
        "cylindre": pieces.get("cylindre"),
        "rpm": rpm_sys,
        "couple_max_Nm": couple_max_sys,
        "rayon_manivelle_m": (0.5 * course_prop) if _is_finite(course_prop) else None,
    }, _safe_dict(pieces_def.get("roulement_aiguille_arbre")))
    pieces["roulement_aiguille_arbre"] = _build_piece_instance(RoulementAiguilleArbre, raw, rapport, "roulement_aiguille_arbre")
    rapport["rapports_pieces"]["roulement_aiguille_arbre"] = _safe_call_report(pieces.get("roulement_aiguille_arbre"))

    raw = _merge_dict_non_none({
        "cylindre": pieces.get("cylindre"),
        "piston": pieces.get("piston"),
        "bielle": pieces.get("bielle"),
        "moteur_thermique": moteur_thermique_obj,
        "roulement_aiguille": pieces.get("roulement_aiguille_arbre"),
        "rpm": rpm_sys,
        "couple_max_Nm": couple_max_sys,
        "course_m": course_prop,
        "force_bielle_effective_N": force_axiale_bielle,
        "materiau_cle": _get_nested(pieces_def, "arbre_vilebrequin", "materiau_cle") or mt.get("materiau_cle"),
        "limite_fatigue_pa": _get_nested(pieces_def, "arbre_vilebrequin", "limite_fatigue_pa") or mt.get("limite_fatigue_pa"),
        "limite_elastique_pa": _get_nested(pieces_def, "arbre_vilebrequin", "limite_elastique_pa") or mt.get("limite_elastique_pa"),
    }, _safe_dict(pieces_def.get("arbre_vilebrequin")))
    pieces["arbre_vilebrequin"] = _build_piece_instance(ArbreVilbrequin, raw, rapport, "arbre_vilebrequin")
    rapport["rapports_pieces"]["arbre_vilebrequin"] = _safe_call_report(pieces.get("arbre_vilebrequin"))

    raw = _merge_dict_non_none({
        "vilbrequin": pieces.get("vilbrequin"),
        "arbre_vilbrequin": pieces.get("arbre_vilebrequin"),
        "bielle": pieces.get("bielle"),
        "piston": pieces.get("piston"),
        "cylindre": pieces.get("cylindre"),
        "rpm": rpm_sys,
        "couple_max_Nm": couple_max_sys,
        "rayon_manivelle_m": (0.5 * course_prop) if _is_finite(course_prop) else None,
    }, _safe_dict(pieces_def.get("roulement_aiguille_arbre")))
    pieces["roulement_aiguille_arbre"] = _build_piece_instance(RoulementAiguilleArbre, raw, rapport, "roulement_aiguille_arbre")
    rapport["rapports_pieces"]["roulement_aiguille_arbre"] = _safe_call_report(pieces.get("roulement_aiguille_arbre"))

    raw = _merge_dict_non_none({
        "cylindre": pieces.get("cylindre"),
        "moteur_thermique": moteur_thermique_obj,
        "systeme_complet": systeme_obj,
        "vilbrequin": pieces.get("vilbrequin"),
        "roulement_aiguille": pieces.get("roulement_aiguille_arbre"),
        "couple_max_Nm": couple_max_sys,
        "rpm": rpm_sys,
        "nombre_cylindres": _safe_int(mt.get("nombre_cylindres")),
        "materiau_arbre_cle": _get_nested(pieces_def, "arbre", "materiau_arbre_cle"),
        "materiau_clavette_cle": _get_nested(pieces_def, "arbre", "materiau_clavette_cle"),
        "materiau_moyeu_cle": _get_nested(pieces_def, "arbre", "materiau_moyeu_cle"),
    }, _safe_dict(pieces_def.get("arbre")))
    pieces["arbre"] = _build_piece_instance(ArbreMoteur, raw, rapport, "arbre")
    rapport["rapports_pieces"]["arbre"] = _safe_call_report(pieces.get("arbre"))

    raw = _merge_dict_non_none({
        "arbre": pieces.get("arbre"),
        "arbre_vilbrequin": pieces.get("arbre_vilebrequin"),
        "roulement_aiguille_arbre": pieces.get("roulement_aiguille_arbre"),
        "vilbrequin": pieces.get("vilbrequin"),
        "moteur_thermique": moteur_thermique_obj,
        "couple_transmis_Nm": couple_max_sys,
        "materiau_clavette_cle": _get_nested(pieces_def, "clavette_arbre", "materiau_clavette_cle"),
        "materiau_anneau_interieur_cle": _get_nested(pieces_def, "clavette_arbre", "materiau_anneau_interieur_cle"),
    }, _safe_dict(pieces_def.get("clavette_arbre")))
    pieces["clavette_arbre"] = _build_piece_instance(ClavetteArbre, raw, rapport, "clavette_arbre")
    rapport["rapports_pieces"]["clavette_arbre"] = _safe_call_report(pieces.get("clavette_arbre"))
    _dedup_report_lists(rapport)
    if return_report:
        return pieces, rapport
    compat_hidden = {"arbre", "clavette_arbre"}
    return {k: v for k, v in pieces.items() if v is not None and k not in compat_hidden}


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
        p_bus_dc = _first_finite(
            _get_nested(rapport_systeme or {}, "entrees", "puissance_bus_dc_w"),
            _get_nested(rapport_systeme or {}, "entrees", "production_electrique_sortie_w"),
            veh_synth.get("puissance_bus_dc_design_w"),
            _get_nested(rapport_systeme or {}, "liaisons", "bus_dc", "P_bus_dc_design_w"),
            definition_moteur.get("puissance_elec_alt_cible_w")
        )
            
        if p_bus_dc is not None:
            kwargs = _merge_dict_non_none({
                "puissance_bus_dc_w": p_bus_dc,
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
        else:
            rapports["alternateur_bus_dc"] = {"inconnues": {"impossibles": [{"nom": "Alternateur.analyser_pour_bus_dc", "raison": "Manque puissance_bus_dc_w ou puissance_elec_alt_cible_w pour lancer l'analyse."}]}}

    if (
        batterie is not None
        and hasattr(batterie, "analyser_recharge_systeme")
        and isinstance(rapports.get("batterie_dimensionnement"), dict)
        and isinstance(analyses_user.get("strategie_energie"), dict)
    ):
        strategie_user = _safe_dict(analyses_user.get("strategie_energie"))
        kwargs = _merge_dict_non_none(
            {
                "rapport_alternateur": _safe_dict(rapports.get("alternateur_bus_dc")),
                "rapport_moteur_elec": _safe_dict(rapports.get("moteur_electrique")),
                "rapport_batterie": _safe_dict(rapports.get("batterie_dimensionnement")),
                "soc_actuel": _safe_float(strategie_user.get("batterie_soc")),
                "temperature_pack_c": _safe_float(strategie_user.get("batterie_temp_c")),
            },
            _safe_dict(analyses_user.get("batterie_recharge_systeme")),
        )
        if kwargs.get("soc_actuel") is not None or kwargs.get("temperature_pack_c") is not None:
            try:
                rapports["batterie_recharge_systeme"] = batterie.analyser_recharge_systeme(
                    **_filter_kwargs_for_callable(batterie.analyser_recharge_systeme, kwargs)
                )
            except Exception as exc:
                rapports["batterie_recharge_systeme"] = {"erreur": str(exc)}

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
            puissance_utile_w = _first_finite(mt_synth.get("puissance_requise_W"), definition_moteur.get("puissance_requise_W"))
            strategie_multi = _build_multifuel_strategy_report(
                moteur_thermique=moteur_thermique,
                definition_moteur=definition_moteur,
                puissance_utile_w=puissance_utile_w,
            )
            if strategie_multi is not None:
                dimensionnant_nom = strategie_multi.get("carburant_dimensionnant")
                kwargs = _merge_dict_non_none({
                    "carburant": _fuel_catalog().get(str(dimensionnant_nom)) if dimensionnant_nom else None,
                    "puissance_utile_w": puissance_utile_w,
                    "rendement_global": _safe_float(definition_moteur.get("rendement_global")),
                }, _safe_dict(analyses_user.get("moteur_thermique_bilan_carburant")))
                try:
                    bilan_dimensionnant = moteur_thermique.analyser_bilan_carburant(**_filter_kwargs_for_callable(moteur_thermique.analyser_bilan_carburant, kwargs))
                except Exception as exc:
                    bilan_dimensionnant = {"erreur": str(exc)}
                rapports["moteur_thermique_bilan_carburant"] = _merge_dict_non_none(
                    strategie_multi,
                    {
                        "bilan_dimensionnant": bilan_dimensionnant,
                        "carburant_utilise_pour_dimensionnement": dimensionnant_nom,
                    },
                )
            else:
                kwargs = _merge_dict_non_none({
                    "carburant": definition_moteur.get("carburant"),
                    "puissance_utile_w": puissance_utile_w,
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

    electronique_puissance: Dict[str, Any] = {
        "bus_dc": {},
        "redressement": {},
        "inconnues": {"partielles": [], "impossibles": []},
    }
    bus_dc_design_w = _first_finite(
        _get_nested(rapport_systeme or {}, "liaisons", "bus_dc", "P_bus_dc_design_w"),
        veh_synth.get("puissance_bus_dc_design_w"),
        _get_nested(rapports, "alternateur_bus_dc", "bus_dc", "puissance_bus_dc_W"),
    )
    bus_dc_tension_v = _first_finite(
        _get_nested(rapport_systeme or {}, "liaisons", "bus_dc", "V_bus_dc_v"),
        veh_synth.get("tension_bus_dc_v"),
        batt_synth.get("tension_nominale_v"),
        _get_nested(rapports, "alternateur_bus_dc", "bus_dc", "tension_bus_dc_V"),
    )
    courant_bus_dc_a = None
    if bus_dc_design_w is not None and bus_dc_tension_v is not None and float(bus_dc_tension_v) > 0.0:
        courant_bus_dc_a = float(bus_dc_design_w) / float(bus_dc_tension_v)
    else:
        electronique_puissance["inconnues"]["partielles"].append(
            {
                "nom": "courant_bus_dc_a",
                "raison": "Calculable si P_bus_dc_design_w et V_bus_dc_v sont disponibles.",
            }
        )

    electronique_puissance["bus_dc"] = {
        "puissance_design_w": bus_dc_design_w,
        "tension_nominale_v": bus_dc_tension_v,
        "courant_nominal_a": courant_bus_dc_a,
        "scenario": _get_nested(rapport_systeme or {}, "liaisons", "bus_dc", "scenario_bus_dc"),
        "energie_a_recharger_kwh": _get_nested(rapport_systeme or {}, "liaisons", "bus_dc", "energie_a_recharger_kwh"),
    }
    electronique_puissance["redressement"] = {
        "source": "alternateur_triphasé_vers_bus_dc",
        "puissance_entree_w": _first_finite(
            _get_nested(rapports, "alternateur_bus_dc", "alternateur", "P_entree_mecanique_W"),
            _get_nested(rapports, "alternateur_bus_dc", "alternateur", "P_entree_W"),
        ),
        "puissance_sortie_dc_w": _first_finite(
            _get_nested(rapports, "alternateur_bus_dc", "bus_dc", "puissance_bus_dc_W"),
            bus_dc_design_w,
        ),
        "tension_sortie_dc_v": _first_finite(
            _get_nested(rapports, "alternateur_bus_dc", "bus_dc", "tension_bus_dc_V"),
            bus_dc_tension_v,
        ),
        "courant_sortie_dc_a": _first_finite(
            _get_nested(rapports, "alternateur_bus_dc", "bus_dc", "courant_bus_dc_A"),
            courant_bus_dc_a,
        ),
    }
    rapports["electronique_puissance"] = electronique_puissance

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
    charger_batterie: bool = True,

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
    fraction_temps_generation_beta: Optional[float] = None,
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
    carburants_autorises: Optional[Sequence[str]] = None,
    mode_carburant: Optional[str] = None,
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
    lancer_pipeline_legacy: bool = True,
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
    rapport_resolution_inconnues: Optional[Any] = None
    rapport_resolution_inconnues_dict: Dict[str, Any] = {}

    if callable(resoudre_inconnues_systeme):
        payload_resolution = _merge_dict_non_none(
            {
                "puissance_traction_kw": puissance_traction_kw,
                "production_electrique_sortie_w": production_electrique_sortie_w,
                "puissance_bus_dc_w": puissance_bus_dc_w,
                "puissance_moteur_requise_W": puissance_moteur_requise_W,
                "distance_km": distance_km,
                "vitesse_moyenne_kmh": vitesse_moyenne_kmh,
                "masse_kg": masse_kg,
                "conso_kwh_km": conso_kwh_km,
                "energie_utile_imposee_kwh": energie_utile_imposee_kwh,
                "temps_charge_cible_h": temps_charge_cible_h,
                "tension_bus_dc_v": tension_bus_dc_v,
                "vitesse_alternateur_rpm": vitesse_alternateur_rpm,
                "rapport_vitesse_alt_sur_moteur": rapport_vitesse_alt_sur_moteur,
                "vitesse_moteur_thermique_rpm": vitesse_moteur_thermique_rpm,
                "rendement_boite": rendement_boite,
                "pme_pa": pme_pa,
                "pression_moyenne_effective_pa": pme_pa,
                "pression_max_pa": pression_max_pa,
                "contrainte_service_pa": contrainte_admissible_pa,
                "contrainte_admissible_pa": contrainte_admissible_pa,
                "densite_materiau_kg_m3": densite_materiau_kg_m3,
                "nombre_cylindres": nombre_cylindres,
                "architecture_moteur": architecture_moteur,
                "architecture_forcee": architecture_forcee,
                "alesage_m": alesage_m,
                "course_m": course_m,
                "rpm_moteur_nominal": rpm_moteur_nominal,
                "couple_moteur_max_Nm": couple_moteur_max_Nm,
                "force_bielle_N": force_bielle_N,
                "moteur_thermique_definition": _safe_dict(moteur_thermique_definition),
                "pieces_definition": _safe_dict(pieces_definition),
                "analyses_complementaires": _safe_dict(analyses_complementaires),
                "composants": composants_def,
            },
            {},
        )
        try:
            cdc_kwargs = {
                "tension_bus_dc_v": tension_bus_dc_v,
                "architectures_autorisees": tuple(architectures_autorisees) if architectures_autorisees else None,
                "ratio_course_alesage_max": ratio_course_alesage_max,
                "ratio_course_alesage_cible": ratio_course_alesage_cible,
                "vitesse_piston_max_ms": vitesse_piston_max_ms,
                "temperature_service_max_c": None,
                "contrainte_service_pa": contrainte_admissible_pa,
                "rendement_boite_reference": rendement_boite,
                "rendement_liaison_meca_alt_reference": rendement_liaison_meca_alt,
            }
            if CahierDesChargesSTHOME is not None:
                allowed_cdc = set(getattr(CahierDesChargesSTHOME, "__dataclass_fields__", {}).keys())
                cdc = CahierDesChargesSTHOME(**{k: v for k, v in cdc_kwargs.items() if k in allowed_cdc and v is not None})
            else:
                cdc = {k: v for k, v in cdc_kwargs.items() if v is not None}
            rapport_resolution_inconnues = resoudre_inconnues_systeme(payload_resolution, {}, cdc)
            if hasattr(rapport_resolution_inconnues, "en_dict"):
                rapport_resolution_inconnues_dict = rapport_resolution_inconnues.en_dict()
            elif isinstance(rapport_resolution_inconnues, dict):
                rapport_resolution_inconnues_dict = rapport_resolution_inconnues
            payload_resolu = _safe_dict(rapport_resolution_inconnues_dict.get("payload_resolu"))

            def _apply_resolved_scalar(name: str, current: Any) -> Any:
                value = payload_resolu.get(name)
                return value if current is None and value is not None else current

            puissance_moteur_requise_W = _apply_resolved_scalar("puissance_moteur_requise_W", puissance_moteur_requise_W)
            vitesse_alternateur_rpm = _apply_resolved_scalar("vitesse_alternateur_rpm", vitesse_alternateur_rpm)
            rapport_vitesse_alt_sur_moteur = _apply_resolved_scalar("rapport_vitesse_alt_sur_moteur", rapport_vitesse_alt_sur_moteur)
            vitesse_moteur_thermique_rpm = _apply_resolved_scalar("vitesse_moteur_thermique_rpm", vitesse_moteur_thermique_rpm)
            nombre_cylindres = _apply_resolved_scalar("nombre_cylindres", nombre_cylindres)
            architecture_moteur = _apply_resolved_scalar("architecture_moteur", architecture_moteur)
            alesage_m = _apply_resolved_scalar("alesage_m", alesage_m)
            course_m = _apply_resolved_scalar("course_m", course_m)
            rpm_moteur_nominal = _apply_resolved_scalar("rpm_moteur_nominal", rpm_moteur_nominal)
            couple_moteur_max_Nm = _apply_resolved_scalar("couple_moteur_max_Nm", couple_moteur_max_Nm)
            force_bielle_N = _apply_resolved_scalar("force_bielle_N", force_bielle_N)
            energie_utile_imposee_kwh = _apply_resolved_scalar("energie_utile_imposee_kwh", energie_utile_imposee_kwh)
            densite_materiau_kg_m3 = _apply_resolved_scalar("densite_materiau_kg_m3", densite_materiau_kg_m3)
            if isinstance(payload_resolu.get("moteur_thermique_definition"), dict):
                moteur_thermique_definition = _merge_dict_non_none(
                    _safe_dict(payload_resolu.get("moteur_thermique_definition")),
                    moteur_thermique_definition,
                )
            _append_note(rapport_global, "Resolution centrale des inconnues appliquee avant orchestration backend.")
        except Exception as exc:
            _push_inconnue(
                rapport_global,
                "partielles",
                "resolution_inconnues",
                f"Resolution centrale non appliquee : {exc}",
            )

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
                "puissance_nominale_visee_w": _first_non_none(
                    puissance_moteur_requise_W,
                    (puissance_traction_kw * 1000.0) if puissance_traction_kw is not None else None,
                ),
                "type_puissance_nominale": type_puissance_nominale,
                "pme_nominale_pa": pme_pa,
                "pression_max_pa": pression_max_pa,
                "force_bielle_N": force_bielle_N,
                "rendement_mecanique_nominal": rendement_mecanique_cible_min,
                "carburant": carburant,
                "carburants_autorises": tuple(carburants_autorises) if carburants_autorises else None,
                "mode_carburant": mode_carburant,
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
    # -------------------------------------------------------------------------
    # Optimisation Multi-Carburant / Dimensionnement par le "Pire Cas"
    # -------------------------------------------------------------------------
    rapport_optimisation_carburant: Optional[Dict[str, Any]] = None
    fuel_list = _normalize_multifuel_names(
        definition_moteur.get("carburant"),
        definition_moteur.get("carburants_autorises"),
        mode_carburant=definition_moteur.get("mode_carburant"),
    )

    if len(fuel_list) > 1 and optimiser_puissance_sortie is not None:
        p_cible_w = _first_finite(
            definition_moteur.get("puissance_nominale_visee_w"),
            puissance_moteur_requise_W,
            (puissance_traction_kw * 1000.0 if puissance_traction_kw else None),
        )
        
        if p_cible_w is not None:
            _append_note(rapport_global, f"Lancement de l'optimisation multi-carburant sur {list(fuel_list)} pour identifier le pire cas dimensionnant.")
            
            search_space = {
                "carburant": list(fuel_list),
                "rpm_moteur": [definition_moteur.get("rpm_nominal")] if definition_moteur.get("rpm_nominal") else [3000.0],
                "temps_moteur": [definition_moteur.get("temps_moteur")] if definition_moteur.get("temps_moteur") else [4],
                "type_puissance_moteur": ["frein"],
            }
            
            # Injection des contraintes si présentes pour guider l'optimiseur
            known_data = {}
            for k in ("pme_pa", "vitesse_piston_max_ms", "ratio_course_alesage_max", "ratio_course_alesage_cible", "nombre_cylindres", "pression_max_pa"):
                if definition_moteur.get(k) is not None:
                    known_data[k] = definition_moteur[k]

            try:
                opt_report = optimiser_puissance_sortie(
                    puissance=p_cible_w,
                    unite="w",
                    donnees_connues=known_data,
                    espace_recherche=search_space,
                )
                rapport_optimisation_carburant = opt_report
                
                # Extraction du Pire Cas pour sécuriser la géométrie (Worst Case Design)
                selection = _safe_dict(_safe_dict(opt_report).get("selection"))
                pire_cas = selection.get("pire_cas_dimensionnant")
                if pire_cas:
                    metrics = _safe_dict(pire_cas.get("metriques"))
                    _append_note(rapport_global, f"Dimensionnement base sur le pire cas (robustesse structurelle) : {pire_cas.get('note')}")
                    
                    # On surcharge la définition moteur avec l'enveloppe maximale nécessaire
                    if _is_finite(metrics.get("alesage_mm")):
                        definition_moteur["alesage_m"] = float(metrics["alesage_mm"]) / 1000.0
                    if _is_finite(metrics.get("course_mm")):
                        definition_moteur["course_m"] = float(metrics["course_mm"]) / 1000.0
                    if _is_finite(metrics.get("pression_max_pa")):
                        definition_moteur["pression_max_pa"] = float(metrics["pression_max_pa"])
                    
                    # On conserve la trace du carburant "pire" pour l'affichage
                    definition_moteur["pire_cas_dimensionnant"] = pire_cas
            except Exception as exc:
                _push_inconnue(rapport_global, "partielles", "optimisation_multi_carburant", f"Erreur lors de l'optimisation: {exc}")

    if definition_moteur.get("architecture_forcee") is None and definition_moteur.get("architecture") is None:
        _append_note(
            rapport_global,
            "Aucune architecture n'est forcee : l'architecture moteur doit etre retenue par calcul a partir des contraintes et objectifs fournis.",
        )

    # Cibles dérivables sans invention
    if puissance_bus_dc_w is None and production_electrique_sortie_w is not None:
        puissance_bus_dc_w = production_electrique_sortie_w
        _append_note(rapport_global, "puissance_bus_dc_w reprise exactement depuis production_electrique_sortie_w.")

    if puissance_auxiliaire_w is None:
        puissance_auxiliaire_eval_w = None
        _push_inconnue(
            rapport_global,
            "partielles",
            "puissance_auxiliaire_w",
            "Non fournie : l'analyse systeme est menee hors auxiliaires, sans charge auxiliaire inventee.",
        )
        _append_note(
            rapport_global,
            "puissance_auxiliaire_w absente : le calcul systeme complet exclut les auxiliaires au lieu d'inventer une charge fixe.",
        )
    else:
        puissance_auxiliaire_eval_w = puissance_auxiliaire_w
    if scenario_bus_dc is None:
        scenario_bus_dc = "traction_plus_charge" if charger_batterie else "traction"
    if rapports_boite_candidates is None:
        _append_note(
            rapport_global,
            "rapports_boite_candidates absents : aucune optimisation de chaine moteur-alternateur n'est forcee.",
        )

    if definition_moteur.get("puissance_nominale_visee_w") is None and puissance_moteur_requise_W is None:
        if puissance_bus_dc_w is not None:
            _append_note(rapport_global, "La puissance moteur thermique n'est pas déduite automatiquement depuis la puissance électrique : cela dépend des rendements alternateur/liaisons/mécanique, donc aucune valeur n'est inventée.")
        if puissance_traction_kw is not None:
            _append_note(rapport_global, "La puissance moteur thermique n'est pas déduite automatiquement depuis la puissance traction : cela dépend de la chaîne complète et des rendements, donc aucune valeur n'est inventée.")
    elif puissance_traction_kw is not None and puissance_moteur_requise_W is None:
        _append_note(
            rapport_global,
            "La puissance demandee sert de cible minimale de dimensionnement moteur ; la chaine complete peut ensuite imposer une puissance thermique superieure.",
        )

    # Construction stricte des composants
    moteur_electrique = composants_def.get("moteur_electrique")
    if moteur_electrique is None and composants_def.get("moteur_electrique_kwargs"):
        moteur_electrique = _build_component_instance(MoteurElectrique, _safe_dict(composants_def.get("moteur_electrique_kwargs")), rapport_global, "moteur_electrique")
    elif moteur_electrique is None:
        try:
            moteur_electrique = construire_moteur_electrique()
        except Exception as exc:
            _push_inconnue(rapport_global, "partielles", "moteur_electrique", f"Construction compatibilite impossible: {exc}")

    batterie = composants_def.get("batterie")
    if batterie is None and composants_def.get("batterie_kwargs"):
        batterie = _build_component_instance(Batterie, _safe_dict(composants_def.get("batterie_kwargs")), rapport_global, "batterie")
    elif batterie is None:
        try:
            batterie = construire_batterie()
        except Exception as exc:
            _push_inconnue(rapport_global, "partielles", "batterie", f"Construction compatibilite impossible: {exc}")

    alternateur = composants_def.get("alternateur")
    if alternateur is None and composants_def.get("alternateur_kwargs"):
        alternateur = _build_component_instance(Alternateur, _safe_dict(composants_def.get("alternateur_kwargs")), rapport_global, "alternateur")
    elif alternateur is None:
        try:
            alternateur = construire_alternateur()
        except Exception as exc:
            _push_inconnue(rapport_global, "partielles", "alternateur", f"Construction compatibilite impossible: {exc}")

    boite_crabots = composants_def.get("boite_crabots")
    if boite_crabots is None and composants_def.get("boite_crabots_kwargs"):
        boite_crabots = _build_component_instance(BoiteCrabots, _safe_dict(composants_def.get("boite_crabots_kwargs")), rapport_global, "boite_crabots")
    elif boite_crabots is None:
        try:
            boite_crabots = construire_boite_crabots()
        except Exception as exc:
            _push_inconnue(rapport_global, "partielles", "boite_crabots", f"Construction compatibilite impossible: {exc}")

    architecture = composants_def.get("architecture")
    if architecture is None and composants_def.get("architecture_kwargs"):
        architecture = _build_component_instance(Architecture, _safe_dict(composants_def.get("architecture_kwargs")), rapport_global, "architecture")
    elif architecture is None:
        try:
            architecture = construire_architecture()
        except Exception as exc:
            _push_inconnue(rapport_global, "partielles", "architecture", f"Construction compatibilite impossible: {exc}")

    derivees_chaine_energie = _derive_chain_energy_targets(
        puissance_traction_kw=puissance_traction_kw,
        production_electrique_sortie_w=production_electrique_sortie_w,
        puissance_bus_dc_w=puissance_bus_dc_w,
        puissance_auxiliaire_w=puissance_auxiliaire_eval_w,
        energie_utile_imposee_kwh=energie_utile_imposee_kwh,
        temps_charge_cible_h=temps_charge_cible_h,
        charger_batterie=charger_batterie,
        tension_bus_dc_v=tension_bus_dc_v,
        rendement_liaison_meca_alt=rendement_liaison_meca_alt,
        rendement_boite=rendement_boite,
        fraction_temps_generation_beta=fraction_temps_generation_beta,
        moteur_electrique=moteur_electrique,
        batterie=batterie,
        alternateur=alternateur,
    )
    for note in list(derivees_chaine_energie.get("notes") or []):
        _append_note(rapport_global, str(note))
    for categorie, items in _safe_dict(derivees_chaine_energie.get("inconnues")).items():
        for item in list(items or []):
            if isinstance(item, dict):
                _push_inconnue(rapport_global, categorie, item.get("nom", "?"), item.get("raison", ""))

    if energie_utile_imposee_kwh is None and _is_finite(derivees_chaine_energie.get("energie_batterie_cible_kwh")):
        energie_utile_imposee_kwh = float(derivees_chaine_energie["energie_batterie_cible_kwh"])
        _append_note(rapport_global, "energie_utile_imposee_kwh deduite depuis la strategie de recharge de la batterie.")

    if tension_bus_dc_v is None and _is_finite(derivees_chaine_energie.get("tension_bus_dc_v")):
        tension_bus_dc_v = float(derivees_chaine_energie["tension_bus_dc_v"])
        _append_note(rapport_global, "tension_bus_dc_v deduite des caracteristiques explicites batterie/moteur electrique.")

    if puissance_bus_dc_w is None and _is_finite(derivees_chaine_energie.get("puissance_bus_dc_totale_w")):
        puissance_bus_dc_w = float(derivees_chaine_energie["puissance_bus_dc_totale_w"])
        _append_note(rapport_global, "puissance_bus_dc_w deduite de la sortie demandee, des auxiliaires et de la recharge batterie.")

    puissance_moteur_derivee_w = _first_finite(derivees_chaine_energie.get("puissance_moteur_thermique_requise_w"))
    if _is_finite(puissance_moteur_derivee_w):
        puissance_reference = _safe_float(definition_moteur.get("puissance_nominale_visee_w"))
        if puissance_reference is None or float(puissance_moteur_derivee_w) > puissance_reference:
            definition_moteur["puissance_nominale_visee_w"] = float(puissance_moteur_derivee_w)
            _append_note(rapport_global, "puissance_nominale_visee_w du moteur thermique relevee depuis la chaine complete de generation.")

    moteur_thermique = composants_def.get("moteur_thermique")
    rapport_construction_moteur: Dict[str, Any] = {}
    if moteur_thermique is None:
        try:
            moteur_thermique, rapport_construction_moteur = construire_moteur_thermique_complet(moteur_thermique_definition=definition_moteur, rapport=rapport_global)
            if moteur_thermique is None:
                moteur_thermique = construire_moteur_thermique_base()
                rapport_construction_moteur = _merge_dict_non_none(
                    rapport_construction_moteur,
                    {"mode_construction_fallback": "compatibilite_base"},
                )
        except Exception:
            moteur_thermique = construire_moteur_thermique_base()
            rapport_construction_moteur = {"mode_construction": "compatibilite_base"}

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

    # Analyse système : SystemeComplet est un chemin legacy ; STHO_ME prend le relais
    # quand ce module n'existe plus dans le dépôt.
    rapport_systeme: Dict[str, Any] = {"note": "Synthèse système non lancée."}
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
                "puissance_auxiliaire_w": puissance_auxiliaire_eval_w,
                "distance_km": distance_km,
                "conso_kwh_km": conso_kwh_km,
                "puissance_moyenne_kw": puissance_traction_kw,
                "vitesse_moyenne_kmh": vitesse_moyenne_kmh,
                "temps_charge_cible_h": temps_charge_cible_h,
                "puissance_pic_kw": puissance_pic_kw,
                "duree_pic_s": duree_pic_s,
                "energie_utile_imposee_kwh": energie_utile_imposee_kwh,
                "calculer_puissance_charge_requise": bool(charger_batterie),
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
            _append_note(
                rapport_global,
                "SystemeComplet legacy absent : l'orchestration globale doit passer par STHO_ME ou par une synthèse déjà fournie.",
            )
        else:
            manquants = [k for k in ("moteur_electrique", "batterie", "alternateur", "moteur_thermique") if composants.get(k) is None]
            _push_inconnue(rapport_global, "impossibles", "SystemeComplet", f"Impossible de lancer le système complet sans {manquants}.")

    rapport_stho_me: Dict[str, Any] = {"note": "Pipeline STHO_ME non lancé."}
    st_ho_me_deja_lance = False
    st_ho_me_requis = bool(lancer_stho_me_secondaire or (SystemeComplet is None and STHO_ME is not None))
    if st_ho_me_requis and STHO_ME is not None:
        try:
            analyses_stho = {
                "moteur_thermique_definition": _definition_moteur_pour_exigences(definition_moteur),
                "systeme_complet": _merge_dict_non_none(
                    {
                        "puissance_moyenne_kw": puissance_traction_kw,
                        "puissance_pic_kw": puissance_pic_kw,
                        "scenario_bus_dc": scenario_bus_dc,
                        "tension_bus_dc_v": tension_bus_dc_v,
                        "puissance_elec_alt_cible_w": puissance_bus_dc_w,
                        "vitesse_moteur_thermique_rpm": vitesse_moteur_thermique_rpm,
                        "vitesse_alternateur_rpm": vitesse_alternateur_rpm,
                        "rapport_vitesse_alt_sur_moteur": rapport_vitesse_alt_sur_moteur,
                        "pme_pa": _first_finite(definition_moteur.get("pme_pa"), pme_pa),
                        "pression_max_pa": _first_finite(definition_moteur.get("pression_max_pa"), pression_max_pa),
                        "puissance_auxiliaire_w": puissance_auxiliaire_eval_w,
                        "energie_utile_imposee_kwh": energie_utile_imposee_kwh,
                    },
                    _safe_dict(analyses_complementaires).get("systeme_complet") if isinstance(_safe_dict(analyses_complementaires).get("systeme_complet"), dict) else {},
                ),
            }
            config_stho = {
                "meta": {
                    "backend": "main.py",
                    "source": "config_generee_depuis_main",
                    "role": "orchestrateur_principal_si_systeme_complet_legacy_absent",
                },
                "composants": composants,
                "pieces": _safe_dict(pieces_definition),
                "analyses": analyses_stho,
            }
            rapport_stho_me = STHO_ME.depuis_config(config_stho).analyser()
            st_ho_me_deja_lance = True
            rep_stho_sys = _get_nested(rapport_stho_me, "rapports", "composants", "systeme_complet")
            if isinstance(rep_stho_sys, dict) and "synthese" in rep_stho_sys:
                rapport_systeme = rep_stho_sys
        except Exception as exc:
            rapport_stho_me = {"erreur": str(exc)}
    elif SystemeComplet is None and STHO_ME is None:
        _push_inconnue(
            rapport_global,
            "impossibles",
            "orchestrateur_systeme",
            "SystemeComplet legacy absent et STHO_ME indisponible : aucune synthèse globale ne peut être lancée.",
        )

    # Pièces
    pieces: Dict[str, Any] = {}
    rapport_construction_pieces: Dict[str, Any] = {"note": "Construction pièces non lancée."}
    rapports_pieces: Dict[str, Any] = {}
    if isinstance(rapport_systeme, dict) and "synthese" in rapport_systeme:
        try:
            pieces, rapport_construction_pieces = construire_pieces_depuis_systeme(
                rapport_systeme=rapport_systeme,
                definition_moteur_thermique=definition_moteur,
                pieces_definition=pieces_definition,
                moteur_thermique_obj=moteur_thermique,
                systeme_obj=systeme,
                puissance_traction_kw_for_fallback=puissance_traction_kw,
                return_report=True,
            )
        except TypeError:
            pieces = construire_pieces_depuis_systeme(rapport_systeme=rapport_systeme)
            rapport_construction_pieces = {"note": "Construction pieces appelee en mode compatibilite."}
        rapports_pieces = _merge_dict_non_none(
            _safe_dict(rapport_construction_pieces.get("rapports_pieces")),
            analyser_pieces(pieces),
        )
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
    if callable(extraire_rapports_pieces_composants_systeme):
        rapports_pieces_composants = extraire_rapports_pieces_composants_systeme(rapports_composants)
    else:
        rapports_pieces_composants = _extract_component_piece_reports(rapports_composants)
    if rapports_pieces_composants:
        rapports_pieces = _merge_dict_non_none(rapports_pieces, rapports_pieces_composants)

    rapport_strategie_energie: Dict[str, Any]
    if callable(analyser_strategie_energie):
        try:
            strategie_user = _safe_dict(_safe_dict(analyses_complementaires).get("strategie_energie"))
            etat_strategie = _merge_dict_non_none(
                {
                    "puissance_sortie_demandee_w": _first_finite(
                        derivees_chaine_energie.get("sortie_utilisateur_w"),
                        production_electrique_sortie_w,
                        (puissance_traction_kw * 1000.0) if _is_finite(puissance_traction_kw) else None,
                    ),
                    "puissance_elec_usage_w": _safe_float(derivees_chaine_energie.get("puissance_elec_usage_w")),
                    "puissance_auxiliaire_w": _safe_float(derivees_chaine_energie.get("puissance_auxiliaire_w")),
                    "p_recharge_demandee_w": _safe_float(derivees_chaine_energie.get("puissance_recharge_batterie_w")),
                    "puissance_bus_dc_totale_w": _safe_float(derivees_chaine_energie.get("puissance_bus_dc_totale_w")),
                    "v_bus_dc_v": _safe_float(derivees_chaine_energie.get("tension_bus_dc_v")),
                    "fraction_temps_generation_beta": _safe_float(derivees_chaine_energie.get("fraction_temps_generation_beta")),
                    "rpm_moteur": _safe_float(_get_nested(rapport_systeme or {}, "synthese", "moteur_thermique", "rpm_nominal")),
                    "temps_disponible_s": _safe_float(strategie_user.get("temps_disponible_s")),
                    "point_actuel_thermique": _safe_dict(strategie_user.get("point_actuel_thermique")),
                    "batterie_soc": _safe_float(strategie_user.get("batterie_soc")),
                    "batterie_soh": _safe_float(strategie_user.get("batterie_soh")),
                    "batterie_temp_c": _safe_float(strategie_user.get("batterie_temp_c")),
                    "temperature_limite_pack_c": _safe_float(strategie_user.get("temperature_limite_pack_c")),
                    "resistance_interne_batterie_ohm": _safe_float(strategie_user.get("resistance_interne_batterie_ohm")),
                    "p_charge_max_soh_w": _safe_float(strategie_user.get("p_charge_max_soh_w")),
                    "p_charge_max_bus_w": _safe_float(strategie_user.get("p_charge_max_bus_w")),
                    "c_rate_charge_max": _safe_float(strategie_user.get("c_rate_charge_max")),
                },
                strategie_user,
            )
            composants_strategie = dict(composants)
            if pieces.get("deplaceur") is not None:
                composants_strategie["deplaceur"] = pieces.get("deplaceur")
            rapport_strategie_energie = analyser_strategie_energie(
                etat_systeme=etat_strategie,
                composants=composants_strategie,
                derivees_chaine_energie=derivees_chaine_energie,
                rapport_batterie=_safe_dict(rapports_composants.get("batterie_dimensionnement")),
                rapport_alternateur=_safe_dict(rapports_composants.get("alternateur_bus_dc")),
                rapport_boite=_safe_dict(rapports_composants.get("boite_chaine")),
                rapport_recharge_batterie=_safe_dict(rapports_composants.get("batterie_recharge_systeme")),
                point_actuel=_safe_dict(strategie_user.get("point_actuel_thermique")),
                mode_force=strategie_user.get("mode_force"),
                autoriser_soutien_traction_si_recharge_interdite=bool(strategie_user.get("autoriser_soutien_traction_si_recharge_interdite", False)),
                poids_cout=_safe_dict(strategie_user.get("poids_cout")) or None,
            )
        except Exception as exc:
            rapport_strategie_energie = {"erreur": str(exc)}
    else:
        rapport_strategie_energie = {"note": "Strategie energie non disponible."}

    # Optimisation
    rapport_optimisation: Dict[str, Any]
    if OptimisationSysteme is not None and (systeme is not None or isinstance(rapport_systeme, dict)):
        try:
            optimiseur = OptimisationSysteme(
                systeme_complet=systeme if systeme is not None else rapport_systeme,
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
                rapport_backend=rapport_systeme,
                rapports_pieces=rapports_pieces,
                analyses_composants=rapports_composants,
            )
            rapport_optimisation = optimiseur.analyser()
        except Exception as exc:
            rapport_optimisation = {"erreur": str(exc)}
    else:
        rapport_optimisation = {"note": "Optimisation non lancée."}

    if (not st_ho_me_deja_lance) and lancer_stho_me_secondaire and STHO_ME is not None:
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
    elif not st_ho_me_deja_lance:
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
                pme_pa=_first_finite(_get_nested(mt_syn, "pme_pa"), _get_nested(mt_syn, "pme_nominale_pa")),
                alesage_m=_get_nested(mt_syn, "alesage_m"),
                course_m=_get_nested(mt_syn, "course_m"),
                longueur_bielle_m=definition_moteur.get("longueur_bielle_m"),
                definition_moteur_thermique=definition_moteur,
                pieces_definition=pieces_definition,
                rapport_systeme=rapport_systeme,
                moteur_thermique_obj=moteur_thermique,
                systeme_obj=systeme,
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
    for source in (rapport_systeme, rapports_composants, rapport_construction_pieces, rapports_pieces, rapport_strategie_energie, rapport_optimisation, rapport_stho_me):
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
        "pieces": {nom: {"type": None if obj is None else type(obj).__name__, "construit": obj is not None, "rapport_disponible": isinstance(rapports_pieces.get(nom), dict) and "inconnues" in rapports_pieces.get(nom, {})} for nom, obj in pieces.items()},
    }
    if callable(construire_inventaire_pieces_imbrique_systeme):
        inventaire["pieces"].update(
            construire_inventaire_pieces_imbrique_systeme(
                rapports_pieces=rapports_pieces_composants,
                main_mod=sys.modules[__name__],
            )
        )
    else:
        inventaire["pieces"].update(_build_nested_piece_inventory(rapports_pieces_composants))

    synth = _safe_dict(_safe_dict(rapport_systeme).get("synthese"))
    mt_syn = _safe_dict(synth.get("moteur_thermique"))
    
    mt_point = _safe_dict(_get_nested(rapports_composants, "moteur_thermique_point", "resultats"))
    if mt_syn.get("puissance_indiquee_W") is None and mt_point.get("puissance_indiquee_W") is not None:
        mt_syn["puissance_indiquee_W"] = mt_point["puissance_indiquee_W"]
    if _is_finite(puissance_traction_kw):
        mt_syn["puissance_cible_systeme_W"] = puissance_traction_kw * 1000.0
        
    if isinstance(rapport_systeme, dict) and isinstance(rapport_systeme.get("synthese"), dict):
        rapport_systeme["synthese"]["moteur_thermique"] = mt_syn
        
    veh_syn = _safe_dict(synth.get("vehicule"))
    batt_syn = _safe_dict(synth.get("batterie"))
    opt_syn = _safe_dict(_safe_dict(rapport_optimisation).get("synthese_optimisation"))
    strategie_syn = _safe_dict(rapport_strategie_energie)

    force_bielle = _get_nested(rapport_construction_pieces, "propagation_debug", "force_axiale_max_N", "valeur")
    if force_bielle is None:
        force_bielle = _first_non_none(mt_syn.get("force_bielle_N"), definition_moteur.get("force_bielle_N"))

    inconnues_globales = _safe_dict(rapport_global.get("inconnues"))
    nb_inconnues_total = sum(len(v) for v in inconnues_globales.values())
    inconnues_resume = {
        "total": nb_inconnues_total,
        "systeme": len(inconnues_globales.get("systeme", [])),
        "pieces": len(inconnues_globales.get("pieces", [])),
        "cao": len(inconnues_globales.get("cao", [])),
        "scenario": len(inconnues_globales.get("scenario", [])),
        "materiaux": len(inconnues_globales.get("materiaux", [])),
        "impossibles": len(inconnues_globales.get("impossibles", [])),
        "partielles": len(inconnues_globales.get("partielles", []))
    }

    rpm_val = mt_syn.get("rpm_nominal")
    couple_indique = None
    couple_cible = None
    if _is_finite(rpm_val) and rpm_val > 0:
        omega = 2 * math.pi * rpm_val / 60.0
        if _is_finite(mt_syn.get("puissance_indiquee_W")):
            couple_indique = mt_syn["puissance_indiquee_W"] / omega
        if _is_finite(mt_syn.get("puissance_cible_systeme_W")):
            couple_cible = mt_syn["puissance_cible_systeme_W"] / omega

    resume_gui = {
        "N_cyl": mt_syn.get("nombre_cylindres"),
        "Architecture": mt_syn.get("architecture"),
        "Bore_mm": _safe_float(mt_syn.get("alesage_m")) * 1000.0 if _is_finite(mt_syn.get("alesage_m")) else None,
        "Stroke_mm": _safe_float(mt_syn.get("course_m")) * 1000.0 if _is_finite(mt_syn.get("course_m")) else None,
        "RPM": rpm_val,
        "PME": mt_syn.get("pme_pa"),
        "PME_Pa": mt_syn.get("pme_pa"),
        "Pmax_Pa": mt_syn.get("pression_max_pa"),
        "Couple_max_Nm": mt_syn.get("couple_max_Nm"),
        "couple_moyen_Nm": _first_finite(couple_indique, couple_cible, _get_nested(rapport_construction_pieces, "propagation_debug", "couple_moyen_Nm", "valeur")),
        "couple_indique_moyen_Nm": couple_indique,
        "couple_cible_moyen_Nm": couple_cible,
        "Force_bielle_N": force_bielle,
        "vd_tot_cc": _first_non_none(mt_syn.get("cylindree_totale_cc"), definition_moteur.get("cylindree_totale_cc")),
        "P_bus_dc_design_w": veh_syn.get("puissance_bus_dc_design_w"),
        "energie_batterie_kwh": batt_syn.get("energie_utile_kwh"),
        "score_coherence_100": opt_syn.get("score_coherence_100"),
        "score_global_100": opt_syn.get("score_global_100"),
        "mode_energetique": strategie_syn.get("mode_energetique"),
        "limitation_batterie": _get_nested(strategie_syn, "enveloppe_batterie", "raison_limitante"),
        "puissance_recharge_retenue_w": _get_nested(strategie_syn, "bilan_bus_dc", "puissance_recharge_retenue_w"),
        "nb_pieces_construites": sum(1 for obj in pieces.values() if obj is not None),
        "nb_alertes": sum(len(v) for v in _safe_dict(rapport_global.get("alertes")).values()),
        "nb_inconnues": nb_inconnues_total,
    }
    
    epaisseur_cyl_m = _get_nested(rapports_pieces.get("cylindre", {}), "dimensionnement", "epaisseur_retenue_m")
    if epaisseur_cyl_m is not None:
        epaisseur_cyl = epaisseur_cyl_m * 1000.0
    else:
        epaisseur_cyl = None
    
    if epaisseur_cyl is None:
        ep_m = _first_finite(
            _get_nested(rapports_composants, "moteur_thermique_point", "dimensionnement", "epaisseur_cylindre_retenue_m"),
            _get_nested(rapports_composants, "moteur_thermique_geometrie", "cylindre_complet", "epaisseur_lame_m")
        )
        if ep_m is not None:
            epaisseur_cyl = ep_m * 1000.0
            
    longueur_bielle = _get_nested(rapports_pieces.get("bielle", {}), "geometrie", "longueur_bielle_m")
    if longueur_bielle is None:
        longueur_bielle = _first_finite(
            _get_nested(rapport_construction_pieces, "propagation_debug", "longueur_bielle_m", "valeur"),
            _get_nested(rapports_pieces.get("bielle", {}), "entrees", "longueur_bielle_m"),
            _get_nested(rapports_pieces.get("bielle", {}), "cao", "entraxe_centres_m"),
            definition_moteur.get("longueur_bielle_m")
        )

    inconnues_cao = list(inconnues_globales.get("cao", []))
    if epaisseur_cyl is None:
        inconnues_cao.append({"piece": "cylindre", "champ": "epaisseur_cylindre_mm", "raison": "Épaisseur paroi inconnue."})
    if longueur_bielle is None:
        inconnues_cao.append({"piece": "bielle", "champ": "longueur_bielle_m", "raison": "Longueur de bielle inconnue."})

    cotes_detaillees = [
        ("piston", "diametre_axe_m", "geometrie.diametre_axe_m", "Diamètre axe piston inconnu."),
        ("bielle", "diametre_maneton_m", "geometrie.diametre_maneton_m", "Diamètre maneton inconnu."),
        ("bielle", "largeur_petite_tete_m", "geometrie.largeur_petite_tete_m", "Largeur petite tête inconnue."),
        ("bielle", "largeur_grande_tete_m", "geometrie.largeur_grande_tete_m", "Largeur grande tête inconnue."),
        ("bielle", "section_fut_m2", "geometrie.section_fut_m2", "Section de fût de bielle inconnue."),
        ("arbre_vilebrequin", "diametre_journal_principal_m", "geometrie.diametre_journal_principal_m", "Diamètre journal principal inconnu."),
        ("roulement_aiguille_arbre", "diametre_portee_m", "geometrie.diametre_portee_m", "Portées de roulements inconnues."),
        ("piston", "hauteur_totale_m", "geometrie.hauteur_totale_m", "Dimensions piston principales (hauteur) inconnues."),
        ("joint_piston", "profondeur_rainure_m", "geometrie.profondeur_rainure_m", "Rainures segments/joints inconnues."),
        ("arbre", "diametre_m", "geometrie.diametre_m", "Dimensions d'arbre inconnues."),
        ("clavette_arbre", "largeur_m", "geometrie.largeur_m", "Dimensions clavette inconnues."),
        ("vis_couvercle_cylindre", "diametre_nominal_m", "geometrie.diametre_nominal_m", "Visserie couvercle complète inconnue.")
    ]
    
    missing_detail_count = 0
    for piece_nom, champ, path, raison in cotes_detaillees:
        keys = path.split('.')
        val = _get_nested(rapports_pieces.get(piece_nom, {}), *keys)
        if val is None:
            inconnues_cao.append({"piece": piece_nom, "champ": champ, "raison": raison})
            missing_detail_count += 1

    solidworks_ready_detaille = (missing_detail_count == 0)

    cao_block = {
        "solidworks_ready_minimal": True,
        "solidworks_ready_pre_dimensionnement": True,
        "solidworks_ready_detaille": solidworks_ready_detaille,
    }
    if not solidworks_ready_detaille:
        cao_block["raison_detaille"] = "Certaines cotes détaillées de piston, maneton, portées, roulements, visserie et rainures restent absentes."

    cao_block.update({
        "moteur_thermique": {
            "alesage_mm": resume_gui["Bore_mm"],
            "course_mm": resume_gui["Stroke_mm"],
        },
        "pieces": {},
        "inconnues_cao": inconnues_cao
    })
    if "cylindre" in rapports_pieces:
        cao_block["pieces"]["cylindre"] = {"epaisseur_cylindre_mm": epaisseur_cyl}
    if "piston" in rapports_pieces:
        cao_block["pieces"]["piston"] = {"force_gaz_n": _get_nested(rapports_pieces["piston"], "cinematique", "force_gaz_n")}
    if "bielle" in rapports_pieces:
        cao_block["pieces"]["bielle"] = {
            "longueur_bielle_m": longueur_bielle,
            "force_axiale_max_N": force_bielle
        }

    derivees_chaine_energie = _merge_dict_non_none(
        derivees_chaine_energie,
        _safe_dict(rapport_strategie_energie.get("derivees_chaine_energie")),
    )

    inconnues_resolution = _safe_dict(rapport_resolution_inconnues_dict.get("inconnues"))
    inconnues_finales = {
        "impossibles": list(_safe_dict(rapport_global.get("inconnues")).get("impossibles") or []),
        "partielles": list(_safe_dict(rapport_global.get("inconnues")).get("partielles") or []),
        "resolues_automatiquement": list(inconnues_resolution.get("resolues_automatiquement") or []),
        "restantes_catalogue": list(inconnues_resolution.get("restantes_catalogue") or []),
        "restantes_physiques": list(inconnues_resolution.get("restantes_physiques") or []),
        "conflits": list(inconnues_resolution.get("conflits") or []),
        "bloquantes": list(inconnues_resolution.get("bloquantes") or []),
        "non_bloquantes": list(inconnues_resolution.get("non_bloquantes") or []),
    }
    coherence_resolution = _safe_dict(rapport_resolution_inconnues_dict.get("coherence_systeme"))

    resultat = {
        "optimisation_carburant": rapport_optimisation_carburant,
        "meta": _merge_dict_non_none(
            rapport_global.get("meta"),
            {"version": "3.0.0", "modele": "orchestrateur strict SHSE-M", "orchestrateur": "STHO_ME + OptimisationSysteme"},
        ),
        "entrees": {
            "puissance_traction_kw": puissance_traction_kw,
            "production_electrique_sortie_w": production_electrique_sortie_w,
            "puissance_bus_dc_w": puissance_bus_dc_w,
            "derivees_chaine_energie": derivees_chaine_energie,
            "definition_moteur_thermique": definition_moteur,
            "pieces_definition": _safe_dict(pieces_definition),
            "analyses_complementaires": _safe_dict(analyses_complementaires),
            "composants_definition": _safe_dict(composants_definition),
        },
        "raw_sections": {
            "systeme_complet": rapport_systeme,
            "analyses_composants": rapports_composants,
            "construction_pieces": rapport_construction_pieces,
            "strategie_energie": rapport_strategie_energie,
            "optimisation": rapport_optimisation,
        },
        "inventaire": inventaire,
        "resume_gui": resume_gui,
        "systeme_complet": rapport_systeme,
        "composants": {nom: _to_jsonable(obj) for nom, obj in composants.items()},
        "cao": cao_block,
        "graphiques": {},
        "donnees_3d": {
            "solidworks_ready_minimal": cao_block.get("solidworks_ready_minimal"),
            "solidworks_ready_pre_dimensionnement": cao_block.get("solidworks_ready_pre_dimensionnement"),
            "solidworks_ready_detaille": cao_block.get("solidworks_ready_detaille"),
            "pieces": cao_block.get("pieces", {}),
        },
        "analyses_composants": rapports_composants,
        "construction_pieces": rapport_construction_pieces,
        "pieces": pieces,
        "rapports_pieces": rapports_pieces,
        "strategie_energie": rapport_strategie_energie,
        "optimisation": rapport_optimisation,
        "optimisations": {
            "carburant": rapport_optimisation_carburant,
            "systeme": rapport_optimisation,
        },
        "stho_me_secondaire": rapport_stho_me,
        "legacy": legacy,
        "resolution_inconnues": rapport_resolution_inconnues_dict,
        "hypotheses_resolues": rapport_resolution_inconnues_dict.get("hypotheses", []),
        "hypotheses": rapport_resolution_inconnues_dict.get("hypotheses", []),
        "donnees_auto_completees": rapport_resolution_inconnues_dict.get("donnees_auto_completees", {}),
        "coherence_systeme": coherence_resolution,
        "objets_serialises": {
            "composants": {nom: _to_jsonable(obj) for nom, obj in composants.items()},
            "pieces": {nom: _to_jsonable(obj) for nom, obj in pieces.items()},
        },
        "toutes_les_donnees_composants": {nom: _collect_public_data(obj) for nom, obj in composants.items()},
        "toutes_les_donnees_pieces": {nom: _collect_public_data(obj) for nom, obj in pieces.items()},
        "toutes_les_donnees_systeme": _collect_public_data(systeme),
        "inconnues": inconnues_finales,
        "inconnues_legacy": rapport_global.get("inconnues"),
        "alertes": rapport_global.get("alertes"),
        "notes_modele": rapport_global.get("notes_modele"),
        "inconnues_resume": inconnues_resume,
        "derivees_chaine_energie": derivees_chaine_energie,
        "synthese": {
            "systeme": synth,
            "moteur_thermique": mt_syn,
            "strategie_energie": {
                "mode": strategie_syn.get("mode_energetique"),
                "raison_limitante_batterie": _get_nested(strategie_syn, "enveloppe_batterie", "raison_limitante"),
                "puissance_recharge_retenue_w": _get_nested(strategie_syn, "bilan_bus_dc", "puissance_recharge_retenue_w"),
            },
            "optimisation": opt_syn,
            "inventaire": inventaire,
        },
    }
    return resultat


def dimensionner_systeme_shsem_simple(puissance_traction_kw: float, charger_batterie: bool = True) -> Dict[str, Any]:
    """Compatibility path for the Kivy GUI.

    The main orchestrator above stays strict and needs a full engineering
    scenario. The GUI currently asks only for target traction power, so this
    helper builds an explicit first-pass scenario and returns the legacy flat
    keys consumed by the screens.
    """

    from backend.modules.systeme.definition_pieces import dimensionner_pieces_completes
    from backend.modules.systeme.engineering_model import DimensioningEngine
    from backend.modules.systeme.system_generator import DriveChainGenerator

    p_kw = _req_pos("puissance_traction_kw", puissance_traction_kw)
    hypotheses_mode_simple = [
        "Mode simple GUI : premier pre-dimensionnement coherent, non scenario strict complet.",
        "Rendement onduleur fixe a 0.97.",
        "Rendement moteur electrique fixe a 0.92.",
        "Charge auxiliaire fixe a 5000 W.",
        "Charge batterie fixe a 20000 W quand la recharge est active.",
        "Regime nominal fixe a 1000 rpm, PME a 20 bar, 4 cylindres, ratio BN = 0.15.",
    ]
    hypotheses_mode_simple_details = [
        {
            "nom": "rendement_onduleur",
            "valeur": 0.97,
            "type": "HYPOTHESE_ASSISTEE",
            "raison": "Mode simple de pre-dimensionnement ; valeur non utilisee dans le flux strict.",
        },
        {
            "nom": "rendement_moteur_electrique",
            "valeur": 0.92,
            "type": "HYPOTHESE_ASSISTEE",
            "raison": "Mode simple de pre-dimensionnement ; valeur non utilisee dans le flux strict.",
        },
        {
            "nom": "puissance_auxiliaire_w",
            "valeur": 5000.0,
            "type": "HYPOTHESE_ASSISTEE",
            "raison": "Charge auxiliaire assistee pour le mode simple GUI.",
        },
        {
            "nom": "puissance_charge_batterie_w",
            "valeur": 20000.0 if charger_batterie else 0.0,
            "type": "HYPOTHESE_ASSISTEE" if charger_batterie else "DECISION_SCENARIO",
            "raison": "Recharge de batterie assistee dans le mode simple GUI." if charger_batterie else "Scenario explicite sans recharge batterie.",
        },
        {
            "nom": "rpm_nominal",
            "valeur": 1000.0,
            "type": "HYPOTHESE_ASSISTEE",
            "raison": "Regime nominal impose par le mode simple de pre-dimensionnement.",
        },
        {
            "nom": "pme_bar",
            "valeur": 20.0,
            "type": "HYPOTHESE_ASSISTEE",
            "raison": "PME imposee par le mode simple de pre-dimensionnement.",
        },
        {
            "nom": "nombre_cylindres",
            "valeur": 4,
            "type": "HYPOTHESE_ASSISTEE",
            "raison": "Nombre de cylindres impose par le mode simple de pre-dimensionnement.",
        },
        {
            "nom": "ratio_bn",
            "valeur": 0.15,
            "type": "HYPOTHESE_ASSISTEE",
            "raison": "Ratio BN impose par le mode simple de pre-dimensionnement.",
        },
    ]

    eta_inv = 0.97
    eta_mot = 0.92
    p_aux_w = 5000.0
    p_charge_bat_w = 20000.0 if charger_batterie else 0.0
    p_dc_total_w = (p_kw * 1000.0 / (eta_mot * eta_inv)) + p_charge_bat_w + p_aux_w
    p_elec_cible_kw = p_dc_total_w / 1000.0

    eng = DimensioningEngine(
        p_elec_kw=p_elec_cible_kw,
        rpm=1000.0,
        p_mean_bar=20.0,
        n_cyl=4,
        bn=0.15,
    )

    pieces_report = dimensionner_pieces_completes(
        puissance_cible_w=eng.p_meca_needed_w,
        regime_tr_min=eng.rpm,
        n_cyl=eng.n_cyl,
        pression_max_pa=eng.p_safety_bar * 1.0e5,
        pme_pa=eng.p_mean_pa,
        alesage_m=eng.bore_m,
        course_m=eng.stroke_m,
        definition_moteur_thermique={
            "temps_moteur": 4,
            "nombre_cylindres": eng.n_cyl,
            "alesage_m": eng.bore_m,
            "course_m": eng.stroke_m,
            "rpm_nominal": eng.rpm,
            "pme_nominale_pa": eng.p_mean_pa,
            "pression_max_pa": eng.p_safety_bar * 1.0e5,
            "puissance_nominale_visee_w": eng.p_meca_needed_w,
        },
    )

    gen = DriveChainGenerator()
    gen.compute(p_kw, charger_batterie=charger_batterie)
    battery_mass = float(str(gen.results["batterie"]["masse_estimee"]).split()[0])

    mass_engine = 250.0 + (eng.vd_total_liters * 20.0)
    l_max_m = eng.bore_m * 1.5 * eng.n_cyl + 0.3
    w_max_m = 0.6
    h_max_m = max(eng.stroke_m * 3.0, 0.35)

    return {
        "meta": {
            "mode_calcul": "assiste_pre_dimensionnement",
            "strict": False,
            "non_strict": True,
        },
        "N_cyl": eng.n_cyl,
        "Architecture": f"L{eng.n_cyl}",
        "Score": 100.0,
        "Cout_Maint_Estime": 1500.0,
        "Bore_mm": eng.bore_mm,
        "Stroke_mm": eng.stroke_mm,
        "RPM": eng.rpm,
        "PME": eng.p_mean_pa,
        "PME_bar": eng.p_mean_bar,
        "P_max": eng.p_safety_bar * 1.0e5,
        "Displacement_L": eng.vd_total_liters,
        "vd_tot_cc": eng.vd_total_liters * 1000.0,
        "masse_totale_kg": mass_engine + battery_mass,
        "masse_pieces_kg": pieces_report.get("masse_pieces_kg"),
        "L_max_m": l_max_m,
        "W_max_m": w_max_m,
        "volume_total_m3": l_max_m * w_max_m * h_max_m,
        "couple_moyen_Nm": eng.torque_mean_nm,
        "drivetrain": gen.results,
        "pieces": pieces_report.get("pieces", {}),
        "inventaire": pieces_report.get("inventaire", {}),
        "construction_pieces": pieces_report.get("construction_pieces", {}),
        "rapports_pieces": pieces_report.get("rapports_pieces", {}),
        "objets_serialises": pieces_report.get("objets_serialises", {}),
        "pieces_db_error": pieces_report.get("db_error"),
        "notes_modele": hypotheses_mode_simple,
        "hypotheses_utilisees": hypotheses_mode_simple_details,
        "resume_gui": {
            "N_cyl": eng.n_cyl,
            "Architecture": f"L{eng.n_cyl}",
            "Bore_mm": eng.bore_mm,
            "Stroke_mm": eng.stroke_mm,
            "RPM": eng.rpm,
            "PME_Pa": eng.p_mean_pa,
            "Pmax_Pa": eng.p_safety_bar * 1.0e5,
            "couple_moyen_Nm": eng.torque_mean_nm,
            "vd_tot_cc": eng.vd_total_liters * 1000.0,
            "modele": "simple_gui",
        },
    }


realiser_systeme_complet = dimensionner_systeme_shsem
concevoir_systeme_complet = dimensionner_systeme_shsem
analyser_systeme_depuis_puissance = analyser_puissance_sortie
optimiser_systeme_depuis_puissance = optimiser_puissance_sortie


def exporter_rapport_json(rapport: Mapping[str, Any], path: str | os.PathLike[str], *, indent: int = 2) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_to_jsonable(dict(rapport), max_depth=12), ensure_ascii=False, indent=indent), encoding="utf-8")
    return str(out)


def _slug_part(value: Any) -> str:
    text = str(value).strip().lower().replace(",", ".")
    out = []
    last_sep = False
    for char in text:
        if char.isalnum():
            out.append(char)
            last_sep = False
        elif char in (".", "-", "_", " "):
            if not last_sep:
                out.append("_")
                last_sep = True
    return "".join(out).strip("_") or "rapport"


def _power_report_name(puissance: float, unite: str) -> str:
    value = f"{float(puissance):g}".replace(".", "p")
    return f"moteur_{_slug_part(value)}_{_slug_part(unite or 'kw')}"


def generer_rapport_puissance_json_bdd(
    puissance: float,
    unite: str = "kw",
    *,
    type_sortie: str = "sortie_utilisateur",
    donnees_connues: Optional[Mapping[str, Any]] = None,
    espace_recherche: Optional[Mapping[str, Any]] = None,
    contraintes: Optional[Mapping[str, Any]] = None,
    max_candidats: int = 50000,
    report_name: Optional[str] = None,
    output_dir: str | os.PathLike[str] | None = None,
    output_path: str | os.PathLike[str] | None = None,
    db_path: str | os.PathLike[str] | None = None,
    key_path: str | os.PathLike[str] | None = None,
    exporter_json_file: bool = True,
    sauvegarder_bdd: bool = True,
) -> Dict[str, Any]:
    """Genere le rapport strict puissance -> JSON + BDD.

    Cette porte d'entree ne cree aucun regime, aucune tension et aucune
    geometrie par defaut. Les meilleurs candidats sont choisis uniquement dans
    `espace_recherche` ou parmi les valeurs deja fournies dans `donnees_connues`.
    """
    if normaliser_puissance is None or optimiser_puissance_sortie is None:
        raise RuntimeError("Le module d'analyse de puissance n'est pas disponible.")

    power = normaliser_puissance(puissance, unite)
    name = _slug_part(report_name) if report_name else _power_report_name(float(power["valeur_entree"]), str(power["unite_entree"]))

    rapport = optimiser_puissance_sortie(
        float(power["valeur_entree"]),
        str(power["unite_entree"]),
        type_sortie=type_sortie,
        donnees_connues=dict(donnees_connues or {}),
        espace_recherche=dict(espace_recherche or {}),
        contraintes=dict(contraintes or {}),
        max_candidats=max_candidats,
    )
    if callable(enrichir_rapport_puissance_avec_pieces_systeme):
        rapport = enrichir_rapport_puissance_avec_pieces_systeme(rapport)
    rapport = _to_jsonable(dict(rapport), max_depth=12)
    rapport.setdefault("meta", {})
    rapport["meta"].update(
        {
            "orchestrateur": "backend.main.generer_rapport_puissance_json_bdd",
            "contrat": "calcul_strict_sans_invention",
        }
    )
    rapport["stockage"] = {
        "report_name": name,
        "json": {"active": bool(exporter_json_file), "path": None},
        "bdd": {"active": bool(sauvegarder_bdd), "db_path": None, "records_saved": 0, "record_ids": {}},
    }

    json_path: Optional[str] = None
    if exporter_json_file:
        if output_path is not None:
            json_file = Path(output_path)
        else:
            out_dir = Path(output_dir) if output_dir is not None else _THIS_DIR / "outputs"
            json_file = out_dir / f"{name}.json"
        json_path = str(json_file.resolve())
        rapport["stockage"]["json"]["path"] = json_path

    record_ids: Dict[str, int] = {}
    db_file_path: Optional[str] = None
    if sauvegarder_bdd:
        from backend.modules.systeme.database import SecureDatabase

        db_file = Path(db_path).resolve() if db_path is not None else (_THIS_DIR / "shse_technical_data.db").resolve()
        key_file = Path(key_path).resolve() if key_path is not None else (_THIS_DIR / "secret.key").resolve()
        db = SecureDatabase(db_path=str(db_file), key_path=str(key_file))
        db_file_path = db.db_path
        record_ids = db.save_power_report(rapport, report_name=name)
        rapport["stockage"]["bdd"] = {
            "active": True,
            "db_path": db_file_path,
            "records_saved": len(record_ids),
            "record_ids": record_ids,
        }

    if json_path is not None:
        exporter_rapport_json(rapport, json_path)

    return {
        "report_name": name,
        "json_path": json_path,
        "db_path": db_file_path,
        "records_saved": len(record_ids),
        "record_ids": record_ids,
        "rapport": rapport,
    }


generer_moteur_depuis_puissance = generer_rapport_puissance_json_bdd


def realiser_systeme_et_exporter_json(path_json: str | os.PathLike[str], *args: Any, **kwargs: Any) -> Dict[str, Any]:
    rapport = dimensionner_systeme_shsem(*args, **kwargs)
    exporter_rapport_json(rapport, path_json)
    return rapport


def _print_resume_console(config: Dict[str, Any]) -> None:
    gui = _safe_dict(config.get("resume_gui"))
    opt = _safe_dict(_safe_dict(config.get("optimisation")).get("synthese_optimisation"))
    pme_value = _first_non_none(gui.get("PME_Pa"), gui.get("PME"))
    score_coherence = _first_non_none(gui.get("score_coherence_100"), opt.get("score_coherence_100"))
    score_global = _first_non_none(gui.get("score_global_100"), opt.get("score_global_100"))
    print("=== DIMENSIONNEMENT SYSTÈME SHSE-M ===")
    print(f"Architecture   : {gui.get('Architecture')}")
    print(f"N cylindres    : {gui.get('N_cyl')}")
    print(f"Alésage        : {gui.get('Bore_mm')} mm")
    print(f"Course         : {gui.get('Stroke_mm')} mm")
    print(f"Régime         : {gui.get('RPM')} rpm")
    print(f"PME            : {pme_value} Pa")
    print(f"Pmax           : {gui.get('Pmax_Pa')} Pa")
    print(f"Couple max     : {gui.get('Couple_max_Nm')} Nm")
    print(f"Couple moyen   : {gui.get('couple_moyen_Nm')} Nm")
    print(f"Force bielle   : {gui.get('Force_bielle_N')} N")
    print(f"Cylindrée      : {gui.get('vd_tot_cc')} cc")
    print(f"Bus DC design  : {gui.get('P_bus_dc_design_w')} W")
    print(f"Batterie utile : {gui.get('energie_batterie_kwh')} kWh")
    print(f"Score cohérence: {gui.get('score_coherence_100')}")
    print(f"Score cohÃ©rence: {score_coherence}")
    print(f"Score coh\u00c3\u00a9rence: {score_coherence}")
    print(f"Score coh\u00e9rence: {score_coherence}")
    print(f"Score global   : {score_global}")
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
        print("Aucun JSON fourni : execution d'un exemple explicite de smoke test CLI.")
        kwargs = {
            "puissance_traction_kw": 100.0,
            "charger_batterie": True,
            "puissance_auxiliaire_w": 5000.0,
            "energie_utile_imposee_kwh": 20.0,
            "temps_charge_cible_h": 1.0,
            "vitesse_moteur_thermique_rpm": 3000.0,
            "pme_pa": 9.0e5,
            "rendement_liaison_meca_alt": 0.97,
            "rendement_boite": 0.96,
            "fraction_temps_generation_beta": 0.5,
            "pression_max_pa": 4.0e6,
            "contrainte_admissible_pa": 1.2e8,
        }

    try:
        rep = dimensionner_systeme_shsem(**kwargs)
        _print_resume_console(rep)

        if len(sys.argv) > 2 and sys.argv[2].endswith(".json"):
            exporter_rapport_json(rep, sys.argv[2])
            print(f"Rapport exporté vers {sys.argv[2]}")
    except Exception as e:
        print(f"Erreur d'exécution: {e}")
        sys.exit(1)

