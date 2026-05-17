# backend/ensemble/STHO_ME.py
from __future__ import annotations

"""
STHO_ME.py
===============================================================================
Orchestrateur haut niveau STHO-ME
===============================================================================

Rôle du fichier :
- assembler les composants fournis : moteur électrique, batterie, alternateur,
  moteur thermique, boîte à crabots, architecture ;
- intégrer un rapport SystemeComplet hérité s'il est fourni, sinon produire
  une synthèse interne STHO_ME sans dépendre de l'ancien module ;
- appeler les analyses spécialisées des composants uniquement quand les paramètres
  correspondants sont fournis ;
- construire les pièces moteur quand elles sont déclarées dans la configuration ;
- réinjecter les grandeurs déjà calculées par le système complet dans les pièces
  sans inventer de dimensions ;
- agréger les rapports, les inconnues, les alertes et une synthèse exploitable ;
- rester importable même si une partie de l'arborescence n'est pas présente.

Contrat :
- aucune hypothèse cachée ;
- aucun défaut métier inventé ;
- les données absentes deviennent des inconnues explicites ;
- les signatures des sous-modules sont respectées par filtrage prudent des kwargs.
"""

import importlib
import inspect
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


# =============================================================================
# Préparation du chemin projet
# =============================================================================

_THIS_FILE = Path(__file__).resolve()
_THIS_DIR = _THIS_FILE.parent

# Cas nominal : backend/ensemble/STHO_ME.py
# Cas de test : fichier lancé depuis un dossier isolé contenant les scripts.
for candidate in (
    _THIS_DIR,
    _THIS_DIR.parent,
    _THIS_DIR.parent.parent,
    Path.cwd(),
):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.append(candidate_str)


# =============================================================================
# Imports robustes et non bloquants
# =============================================================================

_IMPORT_ERRORS: Dict[str, str] = {}


def _import_attr_optional(module_names: Sequence[str], attr: str) -> Any:
    """
    Essaie plusieurs chemins d'import et retourne l'attribut demandé.
    Ne bloque jamais l'import de STHO_ME.py : l'erreur est enregistrée et sera
    remontée dans le rapport d'analyse.
    """
    last_error: Optional[BaseException] = None
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            value = getattr(module, attr)
            return value
        except BaseException as exc:  # volontairement large : robustesse d'orchestrateur
            last_error = exc
            continue

    _IMPORT_ERRORS[attr] = str(last_error) if last_error is not None else "chemin d'import absent"
    return None


# SystemeComplet n'est plus importe comme orchestrateur principal.
# La variable reste presente pour compatibilite avec les anciens rapports/tests,
# mais STHO_ME porte le flux complet.
SystemeComplet = None

OptimisationSysteme = _import_attr_optional(
    (
        "backend.ensemble.optimisation",
        "ensemble.optimisation",
        "optimisation",
    ),
    "OptimisationSysteme",
)

optimiser_rapport_sthome = _import_attr_optional(
    (
        "backend.ensemble.optimisation",
        "ensemble.optimisation",
        "optimisation",
    ),
    "optimiser_rapport_sthome",
)

CahierDesChargesSTHOME = _import_attr_optional(
    (
        "backend.ensemble.resolution_inconnues",
        "ensemble.resolution_inconnues",
        "resolution_inconnues",
    ),
    "CahierDesChargesSTHOME",
)

resoudre_inconnues_systeme = _import_attr_optional(
    (
        "backend.ensemble.resolution_inconnues",
        "ensemble.resolution_inconnues",
        "resolution_inconnues",
    ),
    "resoudre_inconnues_systeme",
)

resoudre_inconnues_systeme_modules = _import_attr_optional(
    (
        "backend.modules.systeme.resolution_inconnues",
        "modules.systeme.resolution_inconnues",
    ),
    "resoudre_inconnues_systeme",
)

build_frontend_contract_backend = _import_attr_optional(
    (
        "backend.modules.systeme.frontend_contract",
        "modules.systeme.frontend_contract",
    ),
    "build_frontend_contract",
)

generer_graphiques_mecaniques_backend = _import_attr_optional(
    (
        "backend.modules.systeme.mechanical_graphs",
        "modules.systeme.mechanical_graphs",
    ),
    "generer_graphiques_mecaniques",
)

construire_dossier_cao_sthome_backend = _import_attr_optional(
    (
        "backend.modules.systeme.cao_dossier",
        "modules.systeme.cao_dossier",
    ),
    "construire_dossier_cao_sthome",
)

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

Batterie = _import_attr_optional(
    (
        "backend.components.batterie.batterie",
        "backend.components.batterie",
        "components.batterie.batterie",
        "components.batterie",
        "batterie",
    ),
    "Batterie",
)

Alternateur = _import_attr_optional(
    (
        "backend.components.alternateur.alternateur",
        "backend.components.alternateur",
        "components.alternateur.alternateur",
        "components.alternateur",
        "alternateur",
    ),
    "Alternateur",
)

MoteurThermique = _import_attr_optional(
    (
        "backend.components.moteur_thermique.moteur_thermique",
        "backend.components.moteur_thermique",
        "components.moteur_thermique.moteur_thermique",
        "components.moteur_thermique",
        "moteur_thermique",
    ),
    "MoteurThermique",
)

BoiteCrabots = _import_attr_optional(
    (
        "backend.components.boite_crabots.boite_crabots",
        "backend.components.boite_crabots",
        "components.boite_crabots.boite_crabots",
        "components.boite_crabots",
        "boite_crabots",
    ),
    "BoiteCrabots",
)

Architecture = _import_attr_optional(
    (
        "backend.components.architechture.architecture",  # orthographe utilisée par plusieurs scripts du projet
        "backend.components.architecture.architecture",
        "backend.components.architechture",
        "backend.components.architecture",
        "components.architechture.architecture",
        "components.architecture.architecture",
        "architecture",
    ),
    "Architecture",
)


# Constructeurs / orchestrateurs haut niveau des composants.
# Ils sont utilisés quand disponibles afin que STHO_ME pilote les scripts complets,
# et non seulement les classes internes.
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

construire_batterie = _import_attr_optional(
    (
        "backend.components.batterie.batterie",
        "backend.components.batterie",
        "components.batterie.batterie",
        "components.batterie",
        "batterie",
    ),
    "construire_batterie",
)
concevoir_batterie = _import_attr_optional(
    (
        "backend.components.batterie.batterie",
        "backend.components.batterie",
        "components.batterie.batterie",
        "components.batterie",
        "batterie",
    ),
    "concevoir_batterie",
)

construire_alternateur = _import_attr_optional(
    (
        "backend.components.alternateur.alternateur",
        "backend.components.alternateur",
        "components.alternateur.alternateur",
        "components.alternateur",
        "alternateur",
    ),
    "construire_alternateur",
)
concevoir_alternateur = _import_attr_optional(
    (
        "backend.components.alternateur.alternateur",
        "backend.components.alternateur",
        "components.alternateur.alternateur",
        "components.alternateur",
        "alternateur",
    ),
    "concevoir_alternateur",
)

construire_boite_crabots = _import_attr_optional(
    (
        "backend.components.boite_crabots.boite_crabots",
        "backend.components.boite_crabots",
        "components.boite_crabots.boite_crabots",
        "components.boite_crabots",
        "boite_crabots",
    ),
    "construire_boite_crabots",
)
concevoir_boite_crabots = _import_attr_optional(
    (
        "backend.components.boite_crabots.boite_crabots",
        "backend.components.boite_crabots",
        "components.boite_crabots.boite_crabots",
        "components.boite_crabots",
        "boite_crabots",
    ),
    "concevoir_boite_crabots",
)

concevoir_architecture = _import_attr_optional(
    (
        "backend.components.architechture.architecture",
        "backend.components.architecture.architecture",
        "backend.components.architechture",
        "backend.components.architecture",
        "components.architechture.architecture",
        "components.architecture.architecture",
        "architecture",
    ),
    "concevoir_architecture",
)

OrchestrateurMoteurThermique = _import_attr_optional(
    (
        "backend.components.moteur_thermique.moteur_thermique",
        "backend.components.moteur_thermique.orchestrateur_moteur_thermique",
        "components.moteur_thermique.moteur_thermique",
        "components.moteur_thermique.orchestrateur_moteur_thermique",
        "moteur_thermique",
        "orchestrateur_moteur_thermique",
    ),
    "OrchestrateurMoteurThermique",
)
EntreesOrchestrateurMoteurThermique = _import_attr_optional(
    (
        "backend.components.moteur_thermique.moteur_thermique",
        "backend.components.moteur_thermique.orchestrateur_moteur_thermique",
        "components.moteur_thermique.moteur_thermique",
        "components.moteur_thermique.orchestrateur_moteur_thermique",
        "moteur_thermique",
        "orchestrateur_moteur_thermique",
    ),
    "EntreesOrchestrateurMoteurThermique",
)

get_carburant = _import_attr_optional(("backend.ensemble.carburant", "ensemble.carburant", "carburant"), "get_carburant")
get_pire_carburant = _import_attr_optional(("backend.ensemble.carburant", "ensemble.carburant", "carburant"), "get_pire_carburant")
creer_melange = _import_attr_optional(("backend.ensemble.carburant", "ensemble.carburant", "carburant"), "creer_melange")
lister_carburants = _import_attr_optional(("backend.ensemble.carburant", "ensemble.carburant", "carburant"), "lister_carburants")
calculer_strategie_couplage = _import_attr_optional(("backend.ensemble.strategie_energie", "ensemble.strategie_energie", "strategie_energie"), "calculer_strategie_couplage")


# Fallback de compatibilité : ton fichier moteur_thermique.py récent expose
# OrchestrateurMoteurThermique plutôt qu'une classe MoteurThermique. Ce wrapper
# garde l'API attendue par STHO_ME et par certains anciens orchestrateurs.
if MoteurThermique is None and OrchestrateurMoteurThermique is not None:
    class MoteurThermique:  # type: ignore[no-redef]
        def __init__(self, **kwargs: Any) -> None:
            if EntreesOrchestrateurMoteurThermique is not None:
                filt = _filter_kwargs_for_callable(EntreesOrchestrateurMoteurThermique, kwargs)
                self.entrees = EntreesOrchestrateurMoteurThermique(**filt)
            else:
                self.entrees = kwargs
            self.orchestrateur = OrchestrateurMoteurThermique(self.entrees) if EntreesOrchestrateurMoteurThermique is not None else OrchestrateurMoteurThermique()
            for key, value in kwargs.items():
                setattr(self, key, value)

        @classmethod
        def definir_depuis_exigences(cls, **kwargs: Any) -> Dict[str, Any]:
            moteur = cls(**kwargs)
            rapport = moteur.analyser(strict=False)
            return {
                "moteur_defini": moteur,
                "rapport": rapport,
                "synthese": _safe_dict(rapport.get("synthese")),
                "inconnues": _safe_dict(rapport.get("inconnues")),
                "notes_modele": ["Moteur thermique défini via OrchestrateurMoteurThermique fallback."],
            }

        def analyser(self, *, strict: bool = False, **overrides: Any) -> Dict[str, Any]:
            return self.orchestrateur.analyser(strict=strict, **overrides)

        def calculer(self, *, strict: bool = False, **overrides: Any) -> Dict[str, Any]:
            return self.analyser(strict=strict, **overrides)

        def analyser_geometrie_definition(self, **kwargs: Any) -> Dict[str, Any]:
            return self.analyser(**kwargs)

        def analyser_cycle_mecanique(self, **kwargs: Any) -> Dict[str, Any]:
            return self.analyser(**kwargs)

        def analyser_point_de_fonctionnement(self, **kwargs: Any) -> Dict[str, Any]:
            return self.analyser(**kwargs)

        def analyser_bilan_carburant(self, **kwargs: Any) -> Dict[str, Any]:
            return self.analyser(**kwargs)


# Pièces moteur thermique — optionnelles.
Cylindre = _import_attr_optional(("backend.components.moteur_thermique.pieces.cylindre", "components.moteur_thermique.pieces.cylindre", "cylindre"), "Cylindre")
Piston = _import_attr_optional(("backend.components.moteur_thermique.pieces.piston", "components.moteur_thermique.pieces.piston", "piston"), "Piston")
JointPiston = _import_attr_optional(("backend.components.moteur_thermique.pieces.joint_piston", "components.moteur_thermique.pieces.joint_piston", "joint_piston"), "JointPiston")
CorpsBielle = _import_attr_optional(("backend.components.moteur_thermique.pieces.bielle", "components.moteur_thermique.pieces.bielle", "bielle"), "CorpsBielle")
ArbrePiston = _import_attr_optional(("backend.components.moteur_thermique.pieces.arbre_piston", "components.moteur_thermique.pieces.arbre_piston", "arbre_piston"), "ArbrePiston")
CoussinetArbrePiston = _import_attr_optional(("backend.components.moteur_thermique.pieces.coussinet_arbre_piston", "components.moteur_thermique.pieces.coussinet_arbre_piston", "coussinet_arbre_piston"), "CoussinetArbrePiston")
ArbreVilbrequin = _import_attr_optional(("backend.components.moteur_thermique.pieces.arbre_vilbrequin", "components.moteur_thermique.pieces.arbre_vilbrequin", "arbre_vilbrequin"), "ArbreVilbrequin")
Vilbrequin = _import_attr_optional(("backend.components.moteur_thermique.pieces.vilbrequin", "components.moteur_thermique.pieces.vilbrequin", "vilbrequin"), "Vilbrequin")
RoulementAiguilleArbre = _import_attr_optional(("backend.components.moteur_thermique.pieces.roulement_aiguille_arbre", "components.moteur_thermique.pieces.roulement_aiguille_arbre", "roulement_aiguille_arbre"), "RoulementAiguilleArbre")
RoulementAiguilleArbreVilebrequin = _import_attr_optional(("backend.components.moteur_thermique.pieces.roulement_aiguille_arbre_vilebrequin", "components.moteur_thermique.pieces.roulement_aiguille_arbre_vilebrequin", "roulement_aiguille_arbre_vilebrequin"), "RoulementAiguilleArbreVilebrequin")
CouvercleCylindre = _import_attr_optional(("backend.components.moteur_thermique.pieces.couvercle_cylindre", "components.moteur_thermique.pieces.couvercle_cylindre", "couvercle_cylindre"), "CouvercleCylindre")
VisCouvercleCylindre = _import_attr_optional(("backend.components.moteur_thermique.pieces.vis_couvercle_cylindre", "components.moteur_thermique.pieces.vis_couvercle_cylindre", "vis_couvercle_cylindre"), "VisCouvercleCylindre")
Deplaceur = _import_attr_optional(("backend.components.moteur_thermique.pieces.deplaceur", "components.moteur_thermique.pieces.deplaceur", "deplaceur"), "Deplaceur")
JointDeplaceur = _import_attr_optional(("backend.components.moteur_thermique.pieces.joint_deplaceur", "components.moteur_thermique.pieces.joint_deplaceur", "joint_deplaceur"), "JointDeplaceur")
ArbreMoteur = _import_attr_optional(("backend.components.moteur_thermique.pieces.arbre", "components.moteur_thermique.pieces.arbre", "arbre"), "ArbreMoteur")
if ArbreMoteur is None:
    ArbreMoteur = _import_attr_optional(("backend.components.moteur_thermique.pieces.arbre", "components.moteur_thermique.pieces.arbre", "arbre"), "Arbre")
ClavetteArbre = _import_attr_optional(("backend.components.moteur_thermique.pieces.clavette_arbre", "components.moteur_thermique.pieces.clavette_arbre", "clavette_arbre"), "ClavetteArbre")


# =============================================================================
# Helpers généraux
# =============================================================================


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _safe_float(x: Any) -> Optional[float]:
    return float(x) if _is_finite(x) else None


def _safe_int(x: Any) -> Optional[int]:
    if isinstance(x, int) and not isinstance(x, bool):
        return int(x)
    if _is_finite(x):
        xf = float(x)
        if abs(xf - round(xf)) <= 1e-9:
            return int(round(xf))
    return None


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _deep_get(x: Any, *path: str) -> Any:
    cur = x
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return cur


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


def _deep_merge(base: Optional[Mapping[str, Any]], extra: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Fusion récursive simple : extra écrase base uniquement aux clés fournies."""
    out: Dict[str, Any] = dict(base or {})
    for key, value in dict(extra or {}).items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = _deep_merge(out[key], value)  # type: ignore[arg-type]
        else:
            out[key] = value
    return out


_CONFIG_ROOT_BLOCKS = {"meta", "composants", "pieces", "analyses"}
_POWER_INPUT_KEYS = {
    "puissance_sortie_kw",
    "puissance_sortie_w",
    "puissance_sortie_moteur_electrique_kw",
    "puissance_sortie_moteur_electrique_w",
    "puissance_moteur_electrique_sortie_w",
    "puissance_demandee_kw",
    "puissance_demandee_w",
    "puissance_traction_kw",
    "puissance_traction_w",
}


def _normaliser_config_entree(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Conserve les entrees racine utiles dans les blocs analyses STHO_ME."""
    cfg = dict(config or {})
    meta = dict(_safe_dict(cfg.get("meta")))
    composants = dict(_safe_dict(cfg.get("composants")))
    pieces = dict(_safe_dict(cfg.get("pieces")))
    analyses = dict(_safe_dict(cfg.get("analyses")))

    root_inputs = {str(k): v for k, v in cfg.items() if k not in _CONFIG_ROOT_BLOCKS}
    if root_inputs:
        analyses["stho_me"] = _deep_merge(_safe_dict(analyses.get("stho_me")), root_inputs)

    power_inputs = {k: v for k, v in root_inputs.items() if k in _POWER_INPUT_KEYS}
    if power_inputs:
        analyses["systeme_complet"] = _deep_merge(
            _safe_dict(analyses.get("systeme_complet")),
            _normaliser_puissance_sortie_config(power_inputs),
        )

    return {
        "meta": meta,
        "composants": composants,
        "pieces": pieces,
        "analyses": analyses,
    }


def _normaliser_puissance_sortie_config(values: Mapping[str, Any]) -> Dict[str, Any]:
    p_w = _first_finite(
        values.get("puissance_sortie_moteur_electrique_w"),
        values.get("puissance_moteur_electrique_sortie_w"),
        values.get("puissance_sortie_w"),
        values.get("puissance_demandee_w"),
        values.get("puissance_traction_w"),
    )
    p_kw = _first_finite(
        values.get("puissance_sortie_moteur_electrique_kw"),
        values.get("puissance_sortie_kw"),
        values.get("puissance_demandee_kw"),
        values.get("puissance_traction_kw"),
    )
    if p_w is None and p_kw is not None:
        p_w = p_kw * 1000.0
    if p_kw is None and p_w is not None:
        p_kw = p_w / 1000.0

    out = dict(values)
    if p_w is not None:
        out.setdefault("puissance_sortie_moteur_electrique_w", p_w)
        out.setdefault("puissance_sortie_w", p_w)
        out.setdefault("puissance_pic_kw", p_w / 1000.0)
        out.setdefault("puissance_moyenne_kw", p_w / 1000.0)
    if p_kw is not None:
        out.setdefault("puissance_sortie_moteur_electrique_kw", p_kw)
        out.setdefault("puissance_sortie_kw", p_kw)
    return out


def _flatten_resolution_inputs(
    composants: Mapping[str, Any],
    pieces: Mapping[str, Any],
    analyses: Mapping[str, Any],
    meta: Mapping[str, Any],
) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    for block_name in ("stho_me", "systeme_complet", "moteur_thermique_definition"):
        block = analyses.get(block_name)
        if isinstance(block, Mapping):
            flat = _deep_merge(flat, block)
    cdc = _deep_merge(_safe_dict(meta.get("cahier_des_charges")), _safe_dict(analyses.get("cahier_des_charges")))
    if cdc:
        flat["cahier_des_charges"] = cdc
    flat["composants"] = _to_jsonable(composants, max_depth=6)
    flat["pieces"] = _to_jsonable(pieces, max_depth=6)
    flat["analyses"] = _to_jsonable(analyses, max_depth=6)
    flat["meta"] = _to_jsonable(meta, max_depth=4)
    return flat


def _merge_missing_values(base: Dict[str, Any], fallback: Mapping[str, Any]) -> Dict[str, Any]:
    for key, value in dict(fallback or {}).items():
        if isinstance(value, Mapping):
            current = base.get(key)
            if isinstance(current, dict):
                _merge_missing_values(current, value)
            elif current is None:
                base[key] = _to_jsonable(value)
        elif base.get(key) is None and value is not None:
            base[key] = value
    return base


def _resolution_payload_from_report(rapport: Mapping[str, Any]) -> Dict[str, Any]:
    return _safe_dict(_deep_get(rapport, "resolution_inconnues", "payload_resolu"))


def _synthese_from_resolution_payload(resolved: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(resolved, Mapping):
        return {}
    return {
        "systeme": {
            "P_bus_dc_design_w": _first_finite(resolved.get("puissance_bus_dc_w"), resolved.get("P_bus_dc_design_w")),
            "V_bus_dc_v": _first_finite(resolved.get("tension_bus_dc_v"), resolved.get("V_bus_dc_v")),
            "courant_bus_dc_a": _first_finite(resolved.get("courant_bus_dc_a")),
            "puissance_sortie_moteur_electrique_w": _first_finite(resolved.get("puissance_sortie_moteur_electrique_w")),
        },
        "moteur_electrique": {
            "puissance_sortie_w": _first_finite(resolved.get("puissance_sortie_moteur_electrique_w")),
            "puissance_entree_dc_w": _first_finite(resolved.get("puissance_moteur_electrique_entree_dc_w")),
            "rendement_moteur_electrique": _first_finite(resolved.get("rendement_moteur_electrique")),
            "rendement_onduleur": _first_finite(resolved.get("rendement_onduleur")),
        },
        "batterie": _deep_merge(
            _safe_dict(_deep_get(resolved, "synthese", "batterie")),
            {
                "energie_utile_kwh": _first_finite(resolved.get("energie_batterie_kwh"), _deep_get(resolved, "synthese", "batterie", "energie_utile_kwh")),
                "nb_cellules_serie": _safe_int(resolved.get("nb_cellules_serie")),
                "nb_cellules_parallele": _safe_int(resolved.get("nb_cellules_parallele")),
            },
        ),
        "alternateur": _deep_merge(
            _safe_dict(_deep_get(resolved, "synthese", "alternateur")),
            {
                "puissance_electrique_design_w": _first_finite(resolved.get("puissance_alternateur_electrique_w")),
                "P_mecanique_W": _first_finite(resolved.get("puissance_alternateur_mecanique_w")),
                "couple_mecanique_Nm": _first_finite(resolved.get("couple_alternateur_nm")),
                "rpm_nominal": _first_finite(resolved.get("rpm_alternateur"), resolved.get("vitesse_alternateur_rpm")),
            },
        ),
        "moteur_thermique": _deep_merge(
            _safe_dict(_deep_get(resolved, "synthese", "moteur_thermique")),
            {
                "architecture": _first_non_none(resolved.get("architecture"), resolved.get("architecture_moteur")),
                "nombre_cylindres": _safe_int(resolved.get("nombre_cylindres")),
                "alesage_m": _first_finite(resolved.get("alesage_m")),
                "course_m": _first_finite(resolved.get("course_m")),
                "rpm_nominal": _first_finite(resolved.get("rpm_moteur"), resolved.get("rpm_moteur_nominal")),
                "pression_max_pa": _first_finite(resolved.get("pression_max_pa")),
                "pme_pa": _first_finite(resolved.get("pme_pa"), resolved.get("pression_moyenne_effective_pa")),
                "couple_requis_Nm": _first_finite(resolved.get("couple_moteur_nm")),
                "puissance_requise_W": _first_finite(resolved.get("puissance_moteur_thermique_arbre_w"), resolved.get("puissance_moteur_requise_W")),
                "source": "resolution_inconnues",
            },
        ),
        "boite_crabots": {
            "rapport_vitesse_alt_sur_moteur": _first_finite(resolved.get("rapport_vitesse_alt_sur_moteur"), resolved.get("rapport_boite_alt")),
            "rpm_moteur": _first_finite(resolved.get("rpm_moteur"), resolved.get("rpm_moteur_nominal")),
            "rpm_alternateur": _first_finite(resolved.get("rpm_alternateur"), resolved.get("vitesse_alternateur_rpm")),
        },
    }


def _analyses_from_resolution_payload(resolved: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(resolved, Mapping) or not resolved:
        return {}
    p_out = _first_finite(resolved.get("puissance_sortie_moteur_electrique_w"))
    p_bus = _first_finite(resolved.get("puissance_bus_dc_w"), resolved.get("P_bus_dc_design_w"))
    p_alt = _first_finite(resolved.get("puissance_alternateur_electrique_w"), resolved.get("production_electrique_sortie_w"))
    p_mt = _first_finite(resolved.get("puissance_moteur_thermique_arbre_w"), resolved.get("puissance_moteur_requise_W"))
    rpm_mt = _first_finite(resolved.get("rpm_moteur"), resolved.get("rpm_moteur_nominal"))
    rpm_alt = _first_finite(resolved.get("rpm_alternateur"), resolved.get("vitesse_alternateur_rpm"))
    ratio = _first_finite(resolved.get("rapport_vitesse_alt_sur_moteur"), resolved.get("rapport_boite_alt"))
    tension = _first_finite(resolved.get("tension_bus_dc_v"), resolved.get("V_bus_dc_v"))
    pme = _first_finite(resolved.get("pme_pa"), resolved.get("pression_moyenne_effective_pa"))
    pression_max = _first_finite(resolved.get("pression_max_pa"))
    cdc = _safe_dict(resolved.get("cahier_des_charges"))

    systeme = {
        "puissance_sortie_moteur_electrique_w": p_out,
        "puissance_pic_kw": p_out / 1000.0 if p_out is not None else None,
        "puissance_moyenne_kw": p_out / 1000.0 if p_out is not None else None,
        "puissance_bus_dc_w": p_bus,
        "puissance_elec_alt_cible_w": p_alt,
        "tension_bus_dc_v": tension,
        "vitesse_moteur_thermique_rpm": rpm_mt,
        "rapport_vitesse_alt_sur_moteur": ratio,
        "pme_pa": pme,
        "pression_max_pa": pression_max,
        "energie_utile_imposee_kwh": _first_finite(resolved.get("energie_batterie_kwh")),
    }
    moteur_thermique = {
        "puissance_visee_w": p_mt,
        "type_puissance": "frein",
        "rpm": rpm_mt,
        "pression_moyenne_effective_pa": pme,
        "temps_moteur": cdc.get("temps_moteur"),
        "rendement_mecanique": cdc.get("rendement_mecanique"),
        "vitesse_piston_max_ms": cdc.get("vitesse_piston_max_ms"),
        "ratio_course_alesage_max": cdc.get("ratio_course_alesage_max"),
        "ratio_course_alesage_cible": cdc.get("ratio_course_alesage_cible"),
        "architectures_autorisees": cdc.get("architectures_autorisees"),
        "architecture_forcee": resolved.get("architecture"),
        "pression_max_pa": pression_max,
        "contrainte_admissible_pa": cdc.get("contrainte_admissible_pa"),
    }
    batterie = {
        "tension_nominale_v": tension,
        "energie_utile_imposee_kwh": _first_finite(resolved.get("energie_batterie_kwh")),
        "puissance_sortie_continue_kw": p_out / 1000.0 if p_out is not None else None,
        "puissance_sortie_moyenne_kw": p_out / 1000.0 if p_out is not None else None,
        "puissance_sortie_pic_kw": p_out / 1000.0 if p_out is not None else None,
        "puissance_recharge_source_kw": p_alt / 1000.0 if p_alt is not None else None,
        "duty_moteur_thermique_max": cdc.get("duty_cycle_moteur_thermique_max"),
        "marge_usage_wltp": cdc.get("marge_wltp"),
    }
    alternateur = {
        "puissance_bus_dc_w": p_bus,
        "tension_bus_dc_v": tension,
        "vitesse_rotation_rpm": rpm_alt,
        "rendement_alternateur_impose": _first_finite(resolved.get("rendement_alternateur")),
    }
    boite = {
        "puissance_bus_dc_w": p_bus,
        "rpm_moteur": rpm_mt,
        "rapports": [ratio] if ratio is not None else None,
        "rendement_boite": _first_finite(resolved.get("rendement_boite")),
        "tension_bus_dc_v": tension,
    }
    strategie = {
        "puissance_traction_roue_w": p_out,
        "v_bus_dc_v": tension,
        "fraction_temps_generation_beta": cdc.get("duty_cycle_moteur_thermique_max"),
        "puissance_auxiliaire_w": cdc.get("puissance_auxiliaire_w"),
        "derivees_chaine_energie": {
            "puissance_bus_dc_totale_w": p_bus,
            "puissance_alternateur_electrique_requise_w": p_alt,
            "puissance_moteur_thermique_requise_w": p_mt,
        },
    }

    return {
        "stho_me": _clean_none(dict(resolved)),
        "systeme_complet": _clean_none(systeme),
        "moteur_thermique_definition": _clean_none(moteur_thermique),
        "batterie": _clean_none(batterie),
        "alternateur_bus_dc": _clean_none(alternateur),
        "boite_chaine": _clean_none(boite),
        "strategie_energie": _clean_none(strategie),
    }


def _clean_none(data: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, Mapping):
            nested = _clean_none(value)
            if nested:
                out[str(key)] = nested
        else:
            out[str(key)] = value
    return out


def _extract_first_report_value(report: Optional[Dict[str, Any]], *paths: str) -> Any:
    for path in paths:
        cur: Any = report
        ok = True
        for part in path.split("."):
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                cur = getattr(cur, part, None)
            if cur is None:
                ok = False
                break
        if ok and cur is not None:
            return cur
    return None


def _append_unique(dst: List[Any], value: Any) -> None:
    if value not in dst:
        dst.append(value)


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append(
        {"nom": str(nom), "raison": str(raison)}
    )


def _push_alerte(rapport: Dict[str, Any], categorie: str, nom: str, detail: str) -> None:
    rapport.setdefault("alertes", {}).setdefault(categorie, []).append(
        {"nom": str(nom), "detail": str(detail)}
    )


def _add_note(rapport: Dict[str, Any], note: str) -> None:
    rapport.setdefault("notes_modele", [])
    _append_unique(rapport["notes_modele"], str(note))


def _dedup_items(items: Iterable[Any], keys: Tuple[str, ...]) -> List[Any]:
    seen: set[Tuple[str, ...]] = set()
    out: List[Any] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        sig = tuple(str(item.get(k, "")) for k in keys)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(item)
    return out


def _dedup_report_lists(rapport: Dict[str, Any]) -> None:
    inc = rapport.setdefault("inconnues", {})
    for categorie in ("impossibles", "partielles"):
        inc[categorie] = _dedup_items(list(inc.get(categorie, []) or []), ("nom", "raison"))

    alerts = rapport.setdefault("alertes", {})
    for categorie, items in list(alerts.items()):
        alerts[categorie] = _dedup_items(list(items or []), ("nom", "detail"))

    notes = []
    for note in list(rapport.get("notes_modele", []) or []):
        _append_unique(notes, str(note))
    rapport["notes_modele"] = notes


def _merge_inconnues(dst: Dict[str, Any], src_report: Optional[Dict[str, Any]], *, prefix: str) -> None:
    if not isinstance(src_report, dict):
        return
    inc = _safe_dict(src_report.get("inconnues"))
    for categorie in ("impossibles", "partielles"):
        for item in list(inc.get(categorie, []) or []):
            if isinstance(item, dict):
                _push_inconnue(
                    dst,
                    categorie,
                    f"{prefix} :: {item.get('nom', '')}",
                    str(item.get("raison", "")),
                )

    alerts = _safe_dict(src_report.get("alertes"))
    for categorie, items in alerts.items():
        for item in list(items or []):
            if isinstance(item, dict):
                _push_alerte(
                    dst,
                    str(categorie),
                    f"{prefix} :: {item.get('nom', '')}",
                    str(item.get("detail", item.get("raison", ""))),
                )

    for note in list(src_report.get("notes_modele", []) or []):
        _add_note(dst, f"{prefix} :: {note}")


def _to_jsonable(value: Any, *, depth: int = 0, max_depth: int = 8) -> Any:
    """Convertit un objet technique en structure JSON sûre, sans récursion infinie."""
    if depth > max_depth:
        return {"type": type(value).__name__, "truncated": True}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v, depth=depth + 1, max_depth=max_depth) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v, depth=depth + 1, max_depth=max_depth) for v in value]
    if is_dataclass(value) and not isinstance(value, type):
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
            attrs = {
                k: v
                for k, v in vars(value).items()
                if not k.startswith("_") and not callable(v)
            }
            simple_attrs = {}
            for k, v in attrs.items():
                if v is None or isinstance(v, (str, int, float, bool)):
                    simple_attrs[k] = v
                elif isinstance(v, (list, tuple, dict)):
                    simple_attrs[k] = _to_jsonable(v, depth=depth + 1, max_depth=max_depth)
                else:
                    simple_attrs[k] = {"type": type(v).__name__}
            return {"type": type(value).__name__, "attributs": simple_attrs}
        except Exception:
            pass
    return {"type": type(value).__name__}


def _is_report_like(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    # Indices forts d'un rapport déjà calculé, par opposition à des paramètres.
    report_keys = {"synthese", "rapports", "construction", "inconnues", "alertes", "meta"}
    return len(report_keys.intersection(payload.keys())) >= 2 or "synthese" in payload


def _callable_signature(fn: Callable[..., Any]) -> Optional[inspect.Signature]:
    try:
        return inspect.signature(fn)
    except Exception:
        return None


def _callable_accepts_varkw(fn: Callable[..., Any]) -> bool:
    sig = _callable_signature(fn)
    if sig is None:
        return True
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())


def _filter_kwargs_for_callable(fn: Callable[..., Any], kwargs: Mapping[str, Any]) -> Dict[str, Any]:
    clean = {str(k): v for k, v in dict(kwargs or {}).items() if k is not None}
    if _callable_accepts_varkw(fn):
        return clean
    sig = _callable_signature(fn)
    if sig is None:
        return clean
    accepted = set(sig.parameters.keys())
    accepted.discard("self")
    accepted.discard("cls")
    return {k: v for k, v in clean.items() if k in accepted}


def _missing_required_kwargs(fn: Callable[..., Any], kwargs: Mapping[str, Any]) -> List[str]:
    sig = _callable_signature(fn)
    if sig is None:
        return []
    missing: List[str] = []
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        if param.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
            continue
        if param.default is inspect._empty and name not in kwargs:
            missing.append(name)
    return missing


def _call_method_filtered(
    obj: Any,
    method_name: str,
    kwargs: Optional[Mapping[str, Any]],
    *,
    rapport: Optional[Dict[str, Any]] = None,
    label: Optional[str] = None,
    add_strict_false: bool = False,
) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    fn = getattr(obj, method_name, None)
    if not callable(fn):
        return None

    raw_kwargs = dict(kwargs or {})
    call_kwargs = _filter_kwargs_for_callable(fn, raw_kwargs)
    sig = _callable_signature(fn)
    if add_strict_false and sig is not None and "strict" in sig.parameters and "strict" not in call_kwargs:
        call_kwargs["strict"] = False

    missing = _missing_required_kwargs(fn, call_kwargs)
    if missing:
        if rapport is not None:
            _push_inconnue(
                rapport,
                "partielles",
                label or method_name,
                "Paramètres obligatoires manquants pour l'appel : " + ", ".join(missing),
            )
        return None

    try:
        out = fn(**call_kwargs)
    except TypeError:
        # Dernier recours pour méthodes sans paramètre ou méthodes ne supportant pas strict=False.
        if call_kwargs:
            try:
                out = fn()
            except Exception as exc:
                if rapport is not None:
                    _push_inconnue(rapport, "impossibles", label or method_name, str(exc))
                return None
        else:
            raise
    except Exception as exc:
        if rapport is not None:
            _push_inconnue(rapport, "impossibles", label or method_name, str(exc))
        return None

    if isinstance(out, dict):
        return out
    return {"resultat": _to_jsonable(out)}


def _safe_call_report(obj: Any, *, rapport: Optional[Dict[str, Any]] = None, label: str = "analyse") -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    for method_name in (
        "analyser",
        "calculer",
        "analyser_definition",
        "analyser_dimensionnement",
        "analyser_geometrie_definition",
        "analyser_point_de_fonctionnement",
        "analyser_point",
    ):
        rep = _call_method_filtered(
            obj,
            method_name,
            {},
            rapport=rapport,
            label=f"{label}.{method_name}",
            add_strict_false=True,
        )
        if rep is not None:
            return rep
    return None


def _construct_from_payload(
    cls: Any,
    payload: Any,
    *,
    rapport: Dict[str, Any],
    nom: str,
) -> Any:
    if payload is None:
        return None

    if cls is not None:
        try:
            if isinstance(payload, cls):
                return payload
        except TypeError:
            # cls peut être typing.Any dans certains environnements.
            pass

    if not isinstance(payload, dict):
        return payload

    if cls is None:
        _push_inconnue(
            rapport,
            "impossibles",
            f"construction {nom}",
            "Classe introuvable : import du module impossible dans l'environnement courant.",
        )
        return None

    try:
        return cls(**payload)
    except Exception as direct_exc:
        # Si la classe ne supporte pas certains champs, on tente un filtrage par signature.
        try:
            kwargs = _filter_kwargs_for_callable(cls, payload)
            obj = cls(**kwargs)
            ignored = sorted(set(payload.keys()) - set(kwargs.keys()))
            if ignored:
                _add_note(
                    rapport,
                    f"{nom} : champs ignorés par filtrage de signature : {', '.join(map(str, ignored))}.",
                )
            return obj
        except Exception as filtered_exc:
            _push_inconnue(
                rapport,
                "impossibles",
                f"construction {nom}",
                f"Instantiation impossible avec les paramètres fournis : {direct_exc} ; après filtrage : {filtered_exc}",
            )
            return None


def _collect_public_data(obj: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {"type": type(obj).__name__ if obj is not None else None}
    if obj is None:
        return data
    try:
        attrs = vars(obj)
        data["attributs"] = _to_jsonable({k: v for k, v in attrs.items() if not k.startswith("_")})
    except Exception:
        data["attributs"] = {}
    methods: Dict[str, str] = {}
    for name in (
        "analyser",
        "calculer",
        "analyser_definition",
        "analyser_dimensionnement",
        "analyser_recharge_systeme",
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


def _context_moteur(systeme_report: Optional[Dict[str, Any]], moteur_thermique: Any) -> Dict[str, Any]:
    synth = _safe_dict(_deep_get(systeme_report, "synthese"))
    synth_mt = _safe_dict(synth.get("moteur_thermique"))
    cao = _safe_dict(_deep_get(systeme_report, "cao", "moteur_thermique"))
    liaisons = _safe_dict(_deep_get(systeme_report, "liaisons"))
    pme_bloc = _safe_dict(liaisons.get("pme"))

    return {
        "alesage_m": _first_finite(
            synth_mt.get("alesage_m"),
            cao.get("alesage_m"),
            cao.get("alesage_mm") / 1000.0 if _is_finite(cao.get("alesage_mm")) else None,
            getattr(moteur_thermique, "alesage_m", None),
        ),
        "course_m": _first_finite(
            synth_mt.get("course_m"),
            cao.get("course_m"),
            cao.get("course_mm") / 1000.0 if _is_finite(cao.get("course_mm")) else None,
            getattr(moteur_thermique, "course_m", None),
        ),
        "pression_max_pa": _first_finite(
            synth_mt.get("pression_max_pa"),
            liaisons.get("pression_max_pa"),
            getattr(moteur_thermique, "pression_max_pa", None),
        ),
        "pme_pa": _first_finite(
            synth_mt.get("pme_pa"),
            synth_mt.get("pme_nominale_pa"),
            pme_bloc.get("pme_pa_utilisee_ou_requise"),
            getattr(moteur_thermique, "pme_nominale_pa", None),
            getattr(moteur_thermique, "pression_moyenne_effective_pa", None),
        ),
        "rpm_nominal": _first_finite(
            synth_mt.get("rpm_nominal"),
            liaisons.get("rpm_moteur_thermique"),
            getattr(moteur_thermique, "rpm_nominal", None),
        ),
        "nombre_cylindres": _safe_int(
            _first_non_none(
                synth_mt.get("nombre_cylindres"),
                getattr(moteur_thermique, "nombre_cylindres", None),
            )
        ),
        "architecture": _first_non_none(
            synth_mt.get("architecture"),
            getattr(moteur_thermique, "architecture", None),
        ),
        "couple_requis_Nm": _first_finite(
            synth_mt.get("couple_requis_Nm"),
            synth_mt.get("couple_moteur_thermique_Nm"),
        ),
        "puissance_requise_W": _first_finite(
            synth_mt.get("puissance_requise_W"),
            synth_mt.get("puissance_moteur_thermique_W"),
        ),
    }


# =============================================================================
# Cartographie des sous-ensembles
# =============================================================================

COMPONENT_CLASSES: Dict[str, Any] = {
    "moteur_electrique": MoteurElectrique,
    "batterie": Batterie,
    "alternateur": Alternateur,
    "moteur_thermique": MoteurThermique,
    "boite_crabots": BoiteCrabots,
    "architecture": Architecture,
}

CORE_COMPONENTS: Tuple[str, ...] = (
    "moteur_electrique",
    "batterie",
    "alternateur",
    "moteur_thermique",
)

PIECE_CLASSES: Dict[str, Any] = {
    "cylindre": Cylindre,
    "piston": Piston,
    "joint_piston": JointPiston,
    "bielle": CorpsBielle,
    "arbre_piston": ArbrePiston,
    "coussinet_arbre_piston": CoussinetArbrePiston,
    "arbre_vilebrequin": ArbreVilbrequin,
    "vilbrequin": Vilbrequin,
    "roulement_aiguille_arbre": RoulementAiguilleArbre,
    "roulement_aiguille_arbre_vilebrequin": RoulementAiguilleArbreVilebrequin,
    "couvercle_cylindre": CouvercleCylindre,
    "vis_couvercle_cylindre": VisCouvercleCylindre,
    "deplaceur": Deplaceur,
    "joint_deplaceur": JointDeplaceur,
    "arbre": ArbreMoteur,
    "clavette_arbre": ClavetteArbre,
}

PIECE_BUILD_ORDER: Tuple[str, ...] = (
    "cylindre",
    "piston",
    "joint_piston",
    "arbre_piston",
    "bielle",
    "coussinet_arbre_piston",
    "couvercle_cylindre",
    "vis_couvercle_cylindre",
    "deplaceur",
    "joint_deplaceur",
    "arbre_vilebrequin",
    "vilbrequin",
    "roulement_aiguille_arbre",
    "roulement_aiguille_arbre_vilebrequin",
    "arbre",
    "clavette_arbre",
)

PIECE_DEPENDENCIES: Dict[str, Dict[str, str]] = {
    "piston": {"cylindre": "cylindre"},
    "joint_piston": {"piston": "piston", "cylindre": "cylindre"},
    "arbre_piston": {"piston": "piston", "bielle": "bielle", "cylindre": "cylindre"},
    "bielle": {
        "piston": "piston",
        "arbre_piston": "arbre_piston",
        "cylindre": "cylindre",
        "moteur_thermique": "moteur_thermique",
    },
    "coussinet_arbre_piston": {"arbre_piston": "arbre_piston"},
    "couvercle_cylindre": {"cylindre": "cylindre"},
    "vis_couvercle_cylindre": {"cylindre": "cylindre", "couvercle": "couvercle_cylindre"},
    "deplaceur": {"cylindre": "cylindre"},
    "joint_deplaceur": {"deplaceur": "deplaceur", "cylindre": "cylindre"},
    "arbre_vilebrequin": {
        "cylindre": "cylindre",
        "piston": "piston",
        "bielle": "bielle",
        "moteur_thermique": "moteur_thermique",
        "roulement_aiguille": "roulement_aiguille_arbre",
    },
    "vilbrequin": {
        "arbre": "arbre_vilebrequin",
        "cylindre": "cylindre",
        "piston": "piston",
        "bielle": "bielle",
        "deplaceur": "deplaceur",
        "systeme_complet": "systeme_complet_obj",
        "moteur_thermique": "moteur_thermique",
    },
    "roulement_aiguille_arbre": {
        "vilbrequin": "vilbrequin",
        "arbre_vilbrequin": "arbre_vilebrequin",
        "bielle": "bielle",
        "piston": "piston",
        "cylindre": "cylindre",
    },
    "roulement_aiguille_arbre_vilebrequin": {
        "corps_bielle": "bielle",
        "arbre_vilebrequin": "arbre_vilebrequin",
        "moteur_thermique": "moteur_thermique",
    },
    "arbre": {
        "cylindre": "cylindre",
        "moteur_thermique": "moteur_thermique",
        "systeme_complet": "systeme_complet_obj",
        "vilbrequin": "vilbrequin",
        "roulement_aiguille": "roulement_aiguille_arbre",
    },
}


# =============================================================================
# Orchestrateur principal
# =============================================================================

@dataclass
class STHO_ME:
    """
    Orchestrateur haut niveau pour la conception du système STHO-ME.

    Entrée attendue :
    {
      "meta": {...},
      "composants": {
        "moteur_electrique": {...},
        "batterie": {...},
        "alternateur": {...},
        "moteur_thermique": {...},
        "boite_crabots": {...},
        "architecture": {...}
      },
      "analyses": {
        "systeme_complet": {... paramètres OU rapport déjà calculé ...},
        "moteur_thermique_definition": {...},
        "batterie": {...},
        "alternateur_bus_dc": {...},
        "alternateur_point": {...},
        "architecture": {...},
        "boite_point": {...},
        "boite_chaine": {...}
      },
      "pieces": {
        "cylindre": {...},
        "piston": {...}
      }
    }
    """

    composants: Dict[str, Any] = field(default_factory=dict)
    pieces: Dict[str, Any] = field(default_factory=dict)
    analyses: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    composants_obj: Dict[str, Any] = field(default_factory=dict, init=False)
    pieces_obj: Dict[str, Any] = field(default_factory=dict, init=False)
    systeme_complet_obj: Optional[Any] = field(default=None, init=False)
    rapport_definition_moteur_thermique: Optional[Dict[str, Any]] = field(default=None, init=False)

    def _reset_runtime(self) -> None:
        self.composants_obj = {}
        self.pieces_obj = {}
        self.systeme_complet_obj = None
        self.rapport_definition_moteur_thermique = None

    def _new_report(self) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "meta": {
                "orchestrateur": "STHO_ME.py",
                "classe": type(self).__name__,
                "version": "2.0.0-corrige",
                "repertoire": str(_THIS_DIR),
                "meta_utilisateur": _to_jsonable(self.meta),
                "contrat": "calcul_strict_sans_invention",
            },
            "imports": {
                "ok": sorted([name for name, cls in {**COMPONENT_CLASSES, **PIECE_CLASSES, "SystemeComplet": SystemeComplet, "OptimisationSysteme": OptimisationSysteme}.items() if cls is not None]),
                "erreurs": dict(_IMPORT_ERRORS),
            },
            "construction": {"composants": {}, "pieces": {}},
            "objets": {"composants": {}, "pieces": {}},
            "rapports": {"composants": {}, "pieces": {}, "optimisation": None},
            "entrees": {},
            "donnees": {},
            "sous_systemes": {},
            "pieces": {},
            "liaisons": {},
            "synthese": {},
            "criteres_conception": {},
            "optimisation": {},
            "cao": {},
            "frontend": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "resolution_inconnues": {},
            "hypotheses_resolues": [],
            "donnees_auto_completees": {},
            "coherence_systeme": {},
            "alertes": {},
            "notes_modele": [],
            "tracabilite": {"valeurs": {}, "candidates": [], "rejected_candidates": [], "optimization_runs": []},
            "traçabilite": {"valeurs": {}, "candidates": [], "rejected_candidates": [], "optimization_runs": []},
        }
        return rapport

    # ------------------------------------------------------------------
    # Construction des composants
    # ------------------------------------------------------------------
    def _build_components(self, rapport: Dict[str, Any]) -> None:
        for name, cls in COMPONENT_CLASSES.items():
            if name not in self.composants:
                continue
            obj = _construct_from_payload(cls, self.composants.get(name), rapport=rapport, nom=name)
            if obj is None:
                continue
            self.composants_obj[name] = obj
            rapport["construction"]["composants"][name] = {
                "type": type(obj).__name__,
                "source": "dict" if isinstance(self.composants.get(name), dict) else "objet",
            }
            rapport["objets"]["composants"][name] = _collect_public_data(obj)

        # Moteur thermique défini par exigences si aucun objet n'est fourni.
        if self.composants_obj.get("moteur_thermique") is None:
            self._build_moteur_thermique_from_requirements(rapport)

        # SystemeComplet déjà fourni explicitement.
        explicit_system = self.composants.get("systeme_complet")
        if explicit_system is not None:
            self.systeme_complet_obj = explicit_system
            rapport["construction"]["composants"]["systeme_complet"] = {
                "type": type(explicit_system).__name__,
                "source": "objet_explicitement_fourni",
            }
            return

        if SystemeComplet is None:
            rapport["construction"]["composants"]["systeme_complet"] = {
                "type": None,
                "source": "module_legacy_absent",
                "statut": "remplace_par_fallback_STHO_ME",
            }
            _add_note(
                rapport,
                "Module legacy SystemeComplet absent : STHO_ME reste l'orchestrateur principal et générera une synthèse interne sans inventer de données.",
            )
            return

        missing = [n for n in CORE_COMPONENTS if self.composants_obj.get(n) is None]
        if missing:
            _push_inconnue(
                rapport,
                "partielles",
                "systeme_complet",
                "Assemblage incomplet : composants manquants = " + ", ".join(missing),
            )
            return

        try:
            self.systeme_complet_obj = SystemeComplet(
                moteur_electrique=self.composants_obj["moteur_electrique"],
                batterie=self.composants_obj["batterie"],
                alternateur=self.composants_obj["alternateur"],
                moteur_thermique=self.composants_obj["moteur_thermique"],
                boite_crabots=self.composants_obj.get("boite_crabots"),
                architecture=self.composants_obj.get("architecture"),
            )
            rapport["construction"]["composants"]["systeme_complet"] = {
                "type": type(self.systeme_complet_obj).__name__,
                "source": "assemblage_composants",
            }
            rapport["objets"]["composants"]["systeme_complet"] = _collect_public_data(self.systeme_complet_obj)
        except Exception as exc:
            _push_inconnue(
                rapport,
                "impossibles",
                "systeme_complet",
                f"Assemblage de SystemeComplet impossible : {exc}",
            )

    def _build_moteur_thermique_from_requirements(self, rapport: Dict[str, Any]) -> None:
        definition = self.analyses.get("moteur_thermique_definition")
        if not isinstance(definition, dict) or not definition:
            return
        if MoteurThermique is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "moteur_thermique_definition",
                "MoteurThermique indisponible : définition depuis exigences impossible.",
            )
            return

        fn = getattr(MoteurThermique, "definir_depuis_exigences", None)
        if not callable(fn):
            _push_inconnue(
                rapport,
                "impossibles",
                "moteur_thermique_definition",
                "La méthode MoteurThermique.definir_depuis_exigences est absente.",
            )
            return

        params = _filter_kwargs_for_callable(fn, definition)
        missing = _missing_required_kwargs(fn, params)
        if missing:
            _push_inconnue(
                rapport,
                "partielles",
                "moteur_thermique_definition",
                "Paramètres obligatoires manquants : " + ", ".join(missing),
            )
            return

        try:
            rep_def = fn(**params)
        except Exception as exc:
            _push_inconnue(
                rapport,
                "impossibles",
                "moteur_thermique_definition",
                f"Définition par exigences impossible : {exc}",
            )
            return

        if isinstance(rep_def, dict):
            self.rapport_definition_moteur_thermique = rep_def
            rapport["rapports"]["composants"]["moteur_thermique_definition"] = _to_jsonable(rep_def)
            _merge_inconnues(rapport, rep_def, prefix="moteur_thermique_definition")
            moteur_defini = _deep_get(rep_def, "moteur_defini")
        else:
            self.rapport_definition_moteur_thermique = {"resultat": _to_jsonable(rep_def)}
            moteur_defini = rep_def

        if moteur_defini is not None:
            self.composants_obj["moteur_thermique"] = moteur_defini
            rapport["construction"]["composants"]["moteur_thermique"] = {
                "type": type(moteur_defini).__name__,
                "source": "definition_depuis_exigences",
            }
            rapport["objets"]["composants"]["moteur_thermique"] = _collect_public_data(moteur_defini)
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "moteur_thermique",
                "La définition par exigences n'a pas retourné de moteur exploitable.",
            )

    # ------------------------------------------------------------------
    # Orchestrateurs complets des composants
    # ------------------------------------------------------------------
    def _component_full_config(self, name: str, *extra_keys: str) -> Dict[str, Any]:
        cfg: Dict[str, Any] = {}
        bloc = self.composants.get(name)
        if isinstance(bloc, Mapping):
            cfg = _deep_merge(cfg, bloc)
        elif bloc is not None:
            cfg["instance"] = bloc

        # Analyses explicitement liées au composant.
        for key in (name, f"{name}_analyse", f"{name}_orchestrateur", *extra_keys):
            bloc_a = self.analyses.get(key)
            if isinstance(bloc_a, Mapping):
                cfg = _deep_merge(cfg, bloc_a)
        return cfg

    def _run_component_orchestrateurs_directs(self, rapport: Dict[str, Any]) -> None:
        """
        Lance les fonctions concevoir_* quand elles existent. C'est ce qui fait
        de STHO_ME l'orchestrateur des scripts complets, au lieu de seulement
        instancier des classes et d'appeler une méthode générique.
        """
        runners: Dict[str, Tuple[Any, Tuple[str, ...]]] = {
            "moteur_electrique": (concevoir_moteur_electrique, ("moteur_electrique_puissance", "moteur_electrique_vehicule")),
            "batterie": (concevoir_batterie, ("batterie_dimensionnement", "batterie_recharge_systeme")),
            "alternateur": (concevoir_alternateur, ("alternateur_point", "alternateur_bus_dc")),
            "boite_crabots": (concevoir_boite_crabots, ("boite_point", "boite_chaine")),
            "architecture": (concevoir_architecture, ("architecture_profil",)),
        }

        for name, (runner, aliases) in runners.items():
            if not callable(runner):
                continue
            cfg = self._component_full_config(name, *aliases)
            if not cfg and self.composants_obj.get(name) is None:
                continue
            if self.composants_obj.get(name) is not None and "instance" not in cfg:
                cfg["instance"] = self.composants_obj[name]
            # Les fonctions concevoir_* des composants filtrent déjà leurs clés.
            try:
                rep = runner(cfg)
            except Exception as exc:
                _push_inconnue(rapport, "partielles", f"{name}.concevoir", f"Orchestrateur composant non concluant : {exc}")
                continue
            if isinstance(rep, dict):
                key = f"{name}_orchestrateur"
                rapport["rapports"]["composants"][key] = _to_jsonable(rep)
                _merge_inconnues(rapport, rep, prefix=key)

        # Moteur thermique : pas de concevoir_* dans ton fichier actuel, mais
        # l'objet wrapper / OrchestrateurMoteurThermique produit un rapport complet.
        mt_obj = self.composants_obj.get("moteur_thermique")
        if mt_obj is not None:
            params = self._component_full_config("moteur_thermique", "moteur_thermique_definition", "moteur_thermique_point")
            rep_mt = _call_method_filtered(
                mt_obj,
                "analyser",
                params,
                rapport=rapport,
                label="moteur_thermique.analyser",
                add_strict_false=True,
            )
            if rep_mt is not None:
                rapport["rapports"]["composants"]["moteur_thermique_orchestrateur"] = _to_jsonable(rep_mt)
                _merge_inconnues(rapport, rep_mt, prefix="moteur_thermique_orchestrateur")

    def _run_carburant_analysis(self, rapport: Dict[str, Any]) -> None:
        cfg = self.analyses.get("carburant")
        if not isinstance(cfg, Mapping) or not cfg:
            return
        bloc: Dict[str, Any] = {"configuration": _to_jsonable(dict(cfg))}
        try:
            if cfg.get("melange") and callable(creer_melange):
                melange_cfg = cfg.get("melange")
                if isinstance(melange_cfg, Mapping):
                    composants = melange_cfg.get("composants")
                    nom = str(melange_cfg.get("nom", "Melange Personnalise"))
                    if isinstance(composants, Mapping):
                        carburant = creer_melange(dict(composants), nom=nom)
                        bloc["melange"] = _to_jsonable(carburant.resume() if hasattr(carburant, "resume") else carburant)
            if cfg.get("cle") and callable(get_carburant):
                carburant = get_carburant(str(cfg.get("cle")))
                bloc["carburant"] = _to_jsonable(carburant.resume() if hasattr(carburant, "resume") else carburant)
            if cfg.get("pire_cas") and callable(get_pire_carburant):
                pire_cfg = cfg.get("pire_cas")
                if isinstance(pire_cfg, Mapping):
                    cles = pire_cfg.get("cles")
                    objectif = str(pire_cfg.get("objectif", "puissance"))
                else:
                    cles = cfg.get("cles")
                    objectif = str(cfg.get("objectif", "puissance"))
                carburant = get_pire_carburant(cles=cles, objectif=objectif)
                bloc["pire_cas"] = _to_jsonable(carburant.resume() if hasattr(carburant, "resume") else carburant)
            if cfg.get("lister") and callable(lister_carburants):
                bloc["bibliotheque"] = _to_jsonable(lister_carburants())
        except Exception as exc:
            bloc["erreur"] = str(exc)
            _push_inconnue(rapport, "partielles", "carburant", str(exc))
        rapport["rapports"]["composants"]["carburant"] = bloc

    def _build_systeme_complet_fallback(self, rapport: Dict[str, Any]) -> None:
        """
        Synthèse système interne utilisée seulement quand SystemeComplet ne tourne pas.
        Elle ne remplace pas les calculs spécialisés : elle agrège ce qui existe déjà.
        """
        if isinstance(_deep_get(rapport, "rapports", "composants", "systeme_complet"), dict):
            return

        composants = _safe_dict(_deep_get(rapport, "rapports", "composants"))
        analyses_sys = self.analyses.get("systeme_complet") if isinstance(self.analyses.get("systeme_complet"), Mapping) else {}

        rep_me = _safe_dict(composants.get("moteur_electrique_orchestrateur") or composants.get("moteur_electrique"))
        rep_batt = _safe_dict(composants.get("batterie_orchestrateur") or composants.get("batterie"))
        rep_alt = _safe_dict(composants.get("alternateur_orchestrateur") or composants.get("alternateur_bus_dc") or composants.get("alternateur_point"))
        rep_mt = _safe_dict(composants.get("moteur_thermique_orchestrateur") or composants.get("moteur_thermique_definition"))
        rep_boite = _safe_dict(composants.get("boite_crabots_orchestrateur") or composants.get("boite_point") or composants.get("boite_chaine"))
        rep_arch = _safe_dict(composants.get("architecture_orchestrateur") or composants.get("architecture"))

        tension_bus = _first_finite(
            _extract_first_report_value(rep_me, "definition.tension_bus_v", "entree.tension_systeme_v"),
            _extract_first_report_value(rep_batt, "entrees.tension_nominale_v", "electrique.tension_nominale_v", "dimensionnement_fin.rapport.tension_nominale_pack_v"),
            _extract_first_report_value(rep_alt, "sortie_electrique.tension_v"),
            _safe_dict(analyses_sys).get("tension_bus_dc_v"),
        )
        puissance_bus = _first_finite(
            _extract_first_report_value(rep_alt, "sortie_electrique.puissance_utile_w", "mecanique.puissance_mecanique_dimensionnante_w"),
            _extract_first_report_value(rep_me, "synthese.puissance_max_w", "definition.puissance_max_w"),
            _safe_dict(analyses_sys).get("puissance_elec_alt_cible_w"),
            _safe_dict(analyses_sys).get("puissance_pic_kw") * 1000.0 if _is_finite(_safe_dict(analyses_sys).get("puissance_pic_kw")) else None,
        )

        # Contexte moteur thermique, directement compatible avec _context_moteur.
        mt_entrees = _safe_dict(rep_mt.get("entrees"))
        mt_synth = _safe_dict(rep_mt.get("synthese"))
        mt_entrees_geom = _safe_dict(mt_entrees.get("alesage_m"))
        mt_alesage = _first_finite(
            mt_entrees.get("alesage_m"),
            mt_entrees_geom.get("alesage_m"),
            _deep_get(rep_mt, "geometrie", "alesage_m"),
            _safe_dict(analyses_sys).get("alesage_m"),
        )
        mt_course = _first_finite(
            mt_entrees.get("course_m"),
            mt_entrees_geom.get("course_m"),
            _deep_get(rep_mt, "geometrie", "course_m"),
            _safe_dict(analyses_sys).get("course_m"),
        )
        mt_nombre_cylindres = _safe_int(_first_non_none(
            mt_entrees.get("nombre_cylindres"),
            mt_entrees_geom.get("nombre_cylindres"),
            _deep_get(rep_mt, "geometrie", "nombre_cylindres"),
            _safe_dict(analyses_sys).get("nombre_cylindres"),
        ))
        mt_puissance = _first_finite(
            mt_synth.get("puissance_frein_estimee_w"),
            mt_synth.get("puissance_indiquee_w"),
            mt_entrees.get("puissance_utile_w"),
            mt_entrees_geom.get("puissance_utile_w"),
            _safe_dict(analyses_sys).get("puissance_utile_w"),
            _safe_dict(self.analyses.get("moteur_thermique_definition")).get("puissance_visee_w"),
        )
        mt_rpm = _first_finite(
            mt_entrees.get("regime_tr_min"),
            mt_entrees_geom.get("regime_tr_min"),
            _safe_dict(analyses_sys).get("vitesse_moteur_thermique_rpm"),
            _safe_dict(self.analyses.get("moteur_thermique_definition")).get("rpm"),
        )
        mt_couple = None
        if mt_puissance is not None and mt_rpm is not None and mt_rpm > 0:
            mt_couple = mt_puissance / (2.0 * math.pi * mt_rpm / 60.0)
        mt_force_bielle = None
        if mt_couple is not None and mt_course is not None and mt_course > 0.0:
            rayon_manivelle = 0.5 * mt_course
            if rayon_manivelle > 0.0:
                mt_force_bielle = abs(mt_couple) / rayon_manivelle

        fallback = {
            "meta": {
                "mode": "fallback_STHO_ME_sans_SystemeComplet",
                "role": "agrégation des rapports composants déjà calculés",
            },
            "synthese": {
                "vehicule": {
                    "tension_bus_dc_v": tension_bus,
                    "puissance_bus_dc_design_w": puissance_bus,
                },
                "moteur_thermique": {
                    "architecture": _first_non_none(mt_entrees.get("architecture"), mt_entrees_geom.get("architecture"), _safe_dict(analyses_sys).get("architecture_forcee")),
                    "nombre_cylindres": mt_nombre_cylindres,
                    "alesage_m": mt_alesage,
                    "course_m": mt_course,
                    "rpm_nominal": mt_rpm,
                    "pression_max_pa": _first_finite(mt_entrees.get("pression_max_pa"), mt_entrees_geom.get("pression_max_pa"), _safe_dict(analyses_sys).get("pression_max_pa")),
                    "pme_pa": _first_finite(mt_entrees.get("pression_moyenne_effective_pa"), mt_entrees_geom.get("pression_moyenne_effective_pa"), _safe_dict(analyses_sys).get("pme_pa")),
                    "couple_requis_Nm": mt_couple,
                    "couple_max_Nm": mt_couple,
                    "force_bielle_N": mt_force_bielle,
                    "puissance_requise_W": mt_puissance,
                },
                "batterie": {
                    "energie_utile_kwh": _first_finite(
                        _extract_first_report_value(rep_batt, "energies_utiles.energie_utile_finale_kwh", "dimensionnement.capacite_totale_kwh"),
                        _safe_dict(analyses_sys).get("energie_utile_imposee_kwh"),
                    ),
                },
                "alternateur": {
                    "P_mecanique_W": _first_finite(_extract_first_report_value(rep_alt, "mecanique.puissance_mecanique_dimensionnante_w", "mecanique.puissance_mecanique_sur_pertes_connues_w")),
                    "couple_mecanique_Nm": _first_finite(_extract_first_report_value(rep_alt, "mecanique.couple_mecanique_dimensionnant_nm", "mecanique.couple_sur_pertes_connues_nm")),
                },
                "boite_crabots": _safe_dict(rep_boite.get("synthese")),
                "architecture": _safe_dict(rep_arch.get("synthese")),
            },
            "liaisons": {
                "bus_dc": {"V_bus_dc_v": tension_bus, "P_bus_dc_design_w": puissance_bus},
                "rpm_moteur_thermique": mt_rpm,
                "pression_max_pa": _first_finite(mt_entrees.get("pression_max_pa"), _safe_dict(analyses_sys).get("pression_max_pa")),
                "pme": {"pme_pa_utilisee_ou_requise": _first_finite(mt_entrees.get("pression_moyenne_effective_pa"), _safe_dict(analyses_sys).get("pme_pa"))},
            },
            "sources": sorted(k for k, v in composants.items() if isinstance(v, dict)),
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [
                "SystemeComplet n'est pas disponible ou n'a pas retourné de rapport ; STHO_ME produit une synthèse de secours sans ajouter de cotes.",
                "Cette synthèse de secours agrège seulement les grandeurs déjà présentes dans les composants et analyses.",
            ],
        }
        if tension_bus is None:
            _push_inconnue(fallback, "partielles", "tension_bus_dc_v", "Non trouvée dans moteur électrique, batterie, alternateur ou analyses systeme_complet.")
        if puissance_bus is None:
            _push_inconnue(fallback, "partielles", "puissance_bus_dc_design_w", "Non trouvée dans alternateur, moteur électrique ou analyses systeme_complet.")
        if mt_rpm is None:
            _push_inconnue(fallback, "partielles", "rpm_moteur_thermique", "Non trouvé dans moteur thermique ou analyses systeme_complet.")

        rapport["rapports"]["composants"]["systeme_complet"] = _to_jsonable(fallback)
        _merge_inconnues(rapport, fallback, prefix="systeme_complet_fallback")
        _add_note(rapport, "Synthèse systeme_complet générée par fallback interne STHO_ME.")

    # ------------------------------------------------------------------
    # Analyses des composants
    # ------------------------------------------------------------------
    def _run_component_analyses(self, rapport: Dict[str, Any]) -> None:
        self._run_carburant_analysis(rapport)
        self._run_component_orchestrateurs_directs(rapport)
        self._run_systeme_complet_analysis(rapport)
        self._run_optional_component_analysis(rapport, "moteur_electrique", "moteur_electrique", "analyser")
        self._run_optional_component_analysis(rapport, "batterie", "batterie", "analyser_dimensionnement")
        self._run_optional_component_analysis(rapport, "batterie_recharge_systeme", "batterie", "analyser_recharge_systeme")
        self._run_optional_component_analysis(rapport, "alternateur_bus_dc", "alternateur", "analyser_pour_bus_dc")
        self._run_optional_component_analysis(rapport, "alternateur_point", "alternateur", "analyser_point_de_fonctionnement")
        self._run_optional_component_analysis(rapport, "architecture", "architecture", "analyser")
        self._run_optional_component_analysis(rapport, "architecture_profil", "architecture", "recommander_pour_profil")
        self._run_optional_component_analysis(rapport, "moteur_thermique_geometrie", "moteur_thermique", "analyser_geometrie_definition")
        self._run_optional_component_analysis(rapport, "moteur_thermique_cycle", "moteur_thermique", "analyser_cycle_mecanique")
        self._run_optional_component_analysis(rapport, "moteur_thermique_point", "moteur_thermique", "analyser_point_de_fonctionnement")
        self._run_optional_component_analysis(rapport, "moteur_thermique_bilan_carburant", "moteur_thermique", "analyser_bilan_carburant")
        self._run_optional_component_analysis(rapport, "boite_point", "boite_crabots", "analyser_point")
        self._run_optional_component_analysis(rapport, "boite_chaine", "boite_crabots", "analyser_chaine_moteur_alternateur")
        self._run_strategie_energie(rapport)
        self._build_systeme_complet_fallback(rapport)

    def _run_strategie_energie(self, rapport: Dict[str, Any]) -> None:
        """
        Déclenche l'arbitrage énergétique Stratégie (SoH vs Pmax).
        """
        if not callable(calculer_strategie_couplage):
            return

        params = self.analyses.get("strategie_energie")
        if not isinstance(params, dict) or not params:
            # On tente quand même avec les données système si non fournies explicitement
            params = self.analyses.get("systeme_complet", {})

        # Extraction de l'état dynamique depuis les analyses ou les composants
        etat = {
            "puissance_traction_roue_w": _first_finite(
                params.get("puissance_traction_roue_w"),
                (params.get("puissance_moyenne_kw") * 1000.0) if _is_finite(params.get("puissance_moyenne_kw")) else None,
            ),
            "batterie_soc": _first_finite(params.get("batterie_soc")),
            "batterie_soh": _first_finite(params.get("batterie_soh")),
            "batterie_temp_c": _first_finite(params.get("batterie_temp_c")),
            "v_bus_dc_v": _first_finite(params.get("v_bus_dc_v")),
            "temps_disponible_s": _first_finite(params.get("temps_disponible_s")),
            "p_recharge_demandee_w": _first_finite(params.get("p_recharge_demandee_w")),
            "puissance_auxiliaire_w": _first_finite(params.get("puissance_auxiliaire_w")),
            "fraction_temps_generation_beta": _first_finite(params.get("fraction_temps_generation_beta")),
            "point_actuel_thermique": _safe_dict(params.get("point_actuel_thermique")),
        }

        try:
            rep = calculer_strategie_couplage(
                etat_systeme=etat,
                composants={**self.composants_obj, **self.pieces_obj},
                derivees_chaine_energie=_safe_dict(params.get("derivees_chaine_energie")),
                rapport_batterie=_safe_dict(_deep_get(rapport, "rapports", "composants", "batterie_dimensionnement")),
                rapport_alternateur=_safe_dict(_deep_get(rapport, "rapports", "composants", "alternateur_bus_dc")),
                rapport_boite=_safe_dict(_deep_get(rapport, "rapports", "composants", "boite_chaine")),
                point_actuel=_safe_dict(params.get("point_actuel_thermique")),
                mode_force=params.get("mode_force"),
                autoriser_soutien_traction_si_recharge_interdite=bool(params.get("autoriser_soutien_traction_si_recharge_interdite", False)),
            )
            rapport["rapports"]["strategie_energie"] = rep
            _merge_inconnues(rapport, rep, prefix="strategie_energie")
        except Exception as exc:
            _push_inconnue(rapport, "partielles", "strategie_energie", f"Échec de l'arbitrage énergétique : {exc}")

    def _run_systeme_complet_analysis(self, rapport: Dict[str, Any]) -> None:
        payload = self.analyses.get("systeme_complet")
        if _is_report_like(payload):
            rapport["rapports"]["composants"]["systeme_complet"] = _to_jsonable(payload)
            _merge_inconnues(rapport, payload, prefix="systeme_complet_importe")
            _add_note(rapport, "Rapport systeme_complet déjà fourni : il est intégré sans recalcul.")
            return

        if self.systeme_complet_obj is None:
            return

        params = dict(payload or {}) if isinstance(payload, dict) else {}
        rep = _call_method_filtered(
            self.systeme_complet_obj,
            "analyser",
            params,
            rapport=rapport,
            label="systeme_complet.analyser",
        )
        if rep is not None:
            rapport["rapports"]["composants"]["systeme_complet"] = _to_jsonable(rep)
            _merge_inconnues(rapport, rep, prefix="systeme_complet")

    def _run_optional_component_analysis(
        self,
        rapport: Dict[str, Any],
        analysis_key: str,
        component_key: str,
        method_name: str,
    ) -> None:
        params = self.analyses.get(analysis_key)
        if not isinstance(params, dict) or not params:
            return
        obj = self.composants_obj.get(component_key)
        if obj is None:
            _push_inconnue(
                rapport,
                "partielles",
                analysis_key,
                f"Analyse demandée mais composant {component_key!r} absent ou non construit.",
            )
            return
        rep = _call_method_filtered(
            obj,
            method_name,
            params,
            rapport=rapport,
            label=f"{component_key}.{method_name}",
        )
        if rep is not None:
            rapport["rapports"]["composants"][analysis_key] = _to_jsonable(rep)
            _merge_inconnues(rapport, rep, prefix=analysis_key)

    # ------------------------------------------------------------------
    # Construction des pièces
    # ------------------------------------------------------------------
    def _prepare_piece_kwargs(self, name: str, rapport: Dict[str, Any]) -> Dict[str, Any]:
        raw = self.pieces.get(name)
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            return {"__passthrough__": raw}

        kwargs = dict(raw)
        sys_rep = _deep_get(rapport, "rapports", "composants", "systeme_complet")
        mt_ctx = _context_moteur(sys_rep, self.composants_obj.get("moteur_thermique"))

        # Dépendances objets déjà construits.
        for param_name, source_name in PIECE_DEPENDENCIES.get(name, {}).items():
            value = self.pieces_obj.get(source_name)
            if value is None and source_name == "moteur_thermique":
                value = self.composants_obj.get("moteur_thermique")
            if value is None and source_name == "systeme_complet_obj":
                value = self.systeme_complet_obj
            if value is not None:
                kwargs.setdefault(param_name, value)

        # Enrichissements uniquement déduits du rapport global ou du moteur défini.
        if name == "cylindre":
            if mt_ctx["alesage_m"] is not None:
                kwargs.setdefault("alesage_m", mt_ctx["alesage_m"])
            if mt_ctx["course_m"] is not None:
                kwargs.setdefault("course_m", mt_ctx["course_m"])
            if mt_ctx["pression_max_pa"] is not None:
                kwargs.setdefault("pression_max_pa", mt_ctx["pression_max_pa"])
            if mt_ctx["pme_pa"] is not None:
                kwargs.setdefault("pression_service_pa", mt_ctx["pme_pa"])

        if name in {"piston", "arbre_piston", "coussinet_arbre_piston", "arbre_vilebrequin", "vilbrequin", "roulement_aiguille_arbre", "arbre"}:
            if mt_ctx["rpm_nominal"] is not None:
                kwargs.setdefault("rpm", mt_ctx["rpm_nominal"])

        if name == "piston":
            if mt_ctx["pression_max_pa"] is not None:
                kwargs.setdefault("pression_max_pa", mt_ctx["pression_max_pa"])
            if mt_ctx["alesage_m"] is not None:
                kwargs.setdefault("alesage_nominal_m", mt_ctx["alesage_m"])
            if mt_ctx["course_m"] is not None:
                kwargs.setdefault("course_m", mt_ctx["course_m"])

        if name == "bielle":
            if mt_ctx["course_m"] is not None and "longueur_bielle_m" not in kwargs:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "bielle.longueur_bielle_m",
                    "Aucune longueur de bielle fournie ; aucune règle interne n'est appliquée automatiquement.",
                )

        if name in {"arbre_vilebrequin", "vilbrequin", "roulement_aiguille_arbre", "arbre"}:
            if mt_ctx["course_m"] is not None:
                kwargs.setdefault("course_m", mt_ctx["course_m"])
            if mt_ctx["couple_requis_Nm"] is not None:
                kwargs.setdefault("couple_max_Nm", mt_ctx["couple_requis_Nm"])

        if name == "roulement_aiguille_arbre" and mt_ctx["course_m"] is not None:
            kwargs.setdefault("rayon_manivelle_m", 0.5 * float(mt_ctx["course_m"]))

        if name == "roulement_aiguille_arbre_vilebrequin" and mt_ctx["rpm_nominal"] is not None:
            kwargs.setdefault("rpm_vilebrequin", mt_ctx["rpm_nominal"])

        if name in {"couvercle_cylindre", "vis_couvercle_cylindre"}:
            if mt_ctx["pression_max_pa"] is not None:
                kwargs.setdefault("pression_max_pa", mt_ctx["pression_max_pa"])
            if name == "couvercle_cylindre" and mt_ctx["pme_pa"] is not None:
                kwargs.setdefault("pression_service_pa", mt_ctx["pme_pa"])

        if name == "deplaceur" and mt_ctx["pression_max_pa"] is not None:
            kwargs.setdefault("pression_froid_pa", mt_ctx["pression_max_pa"])

        if name == "arbre" and mt_ctx["nombre_cylindres"] is not None:
            kwargs.setdefault("nombre_cylindres", mt_ctx["nombre_cylindres"])

        return kwargs

    def _build_pieces(self, rapport: Dict[str, Any]) -> None:
        for name in PIECE_BUILD_ORDER:
            if name not in self.pieces:
                continue
            cls = PIECE_CLASSES.get(name)
            kwargs = self._prepare_piece_kwargs(name, rapport)
            passthrough = kwargs.pop("__passthrough__", None)
            payload = passthrough if passthrough is not None else kwargs
            obj = _construct_from_payload(cls, payload, rapport=rapport, nom=f"pièce {name}")
            if obj is None:
                continue
            self.pieces_obj[name] = obj
            rapport["construction"]["pieces"][name] = {
                "type": type(obj).__name__,
                "source": "dict_enrichi" if isinstance(payload, dict) else "objet",
            }
            rapport["objets"]["pieces"][name] = _collect_public_data(obj)

    # ------------------------------------------------------------------
    # Analyses des pièces
    # ------------------------------------------------------------------
    def _run_piece_analyses(self, rapport: Dict[str, Any]) -> None:
        for name in PIECE_BUILD_ORDER:
            obj = self.pieces_obj.get(name)
            if obj is None:
                continue
            specific_params = self.analyses.get(f"piece_{name}", {})
            rep = None
            if isinstance(specific_params, dict) and specific_params:
                for method_name in ("analyser", "calculer"):
                    rep = _call_method_filtered(
                        obj,
                        method_name,
                        specific_params,
                        rapport=rapport,
                        label=f"piece_{name}.{method_name}",
                        add_strict_false=True,
                    )
                    if rep is not None:
                        break
            if rep is None:
                rep = _safe_call_report(obj, rapport=rapport, label=f"piece_{name}")

            if rep is not None:
                rapport["rapports"]["pieces"][name] = _to_jsonable(rep)
                _merge_inconnues(rapport, rep, prefix=name)
            else:
                rapport["rapports"]["pieces"][name] = {"note": "Aucune méthode d'analyse exploitable n'a retourné de dict."}

    # ------------------------------------------------------------------
    # Optimisation inter-pièces optionnelle
    # ------------------------------------------------------------------
    def _run_optimisation(self, rapport: Dict[str, Any]) -> None:
        should_run = bool(self.analyses.get("optimisation", {}).get("active", False)) if isinstance(self.analyses.get("optimisation"), dict) else False
        if not should_run:
            rapport["rapports"]["optimisation"] = {"note": "Optimisation inter-pièces non demandée."}
            return
        if OptimisationSysteme is None:
            rapport["rapports"]["optimisation"] = {"note": "OptimisationSysteme indisponible."}
            _push_inconnue(rapport, "partielles", "optimisation", "Classe OptimisationSysteme indisponible.")
            return

        kwargs = {
            "systeme_complet": self.systeme_complet_obj or _deep_get(rapport, "rapports", "composants", "systeme_complet"),
            "moteur_thermique": self.composants_obj.get("moteur_thermique"),
            "moteur_electrique": self.composants_obj.get("moteur_electrique"),
            "batterie": self.composants_obj.get("batterie"),
            "alternateur": self.composants_obj.get("alternateur"),
            "boite_crabots": self.composants_obj.get("boite_crabots"),
            "architecture": self.composants_obj.get("architecture"),
            "rapport_backend": _deep_get(rapport, "rapports", "composants", "systeme_complet"),
            "rapports_pieces": _safe_dict(_deep_get(rapport, "rapports", "pieces")),
            "analyses_composants": _safe_dict(_deep_get(rapport, "rapports", "composants")),
            "objets_serialises": _safe_dict(rapport.get("objets")),
            "configs_composants": _safe_dict(self.composants),
            "configs_analyses": _safe_dict(self.analyses),
            **{k: self.pieces_obj.get(k) for k in PIECE_BUILD_ORDER},
        }
        try:
            opt = OptimisationSysteme(**_filter_kwargs_for_callable(OptimisationSysteme, kwargs))
        except Exception as exc:
            _push_inconnue(rapport, "impossibles", "optimisation", f"Construction OptimisationSysteme impossible : {exc}")
            rapport["rapports"]["optimisation"] = {"erreur": str(exc)}
            return

        opt_params = dict(self.analyses.get("optimisation", {}) or {})
        active_method = "optimiser_et_recalculer" if hasattr(opt, "optimiser_et_recalculer") else ("optimiser_composants" if hasattr(opt, "optimiser_composants") else "analyser")
        rep = _call_method_filtered(
            opt,
            active_method,
            opt_params,
            rapport=rapport,
            label=f"optimisation.{active_method}",
        )
        if rep is None and active_method != "analyser":
            rep = _call_method_filtered(opt, "analyser", {}, rapport=rapport, label="optimisation.analyser")
        rapport["rapports"]["optimisation"] = _to_jsonable(rep) if rep is not None else {"note": "Aucun rapport d'optimisation retourné."}
        if rep is not None:
            _merge_inconnues(rapport, rep, prefix="optimisation")

    # ------------------------------------------------------------------
    # Synthèse
    # ------------------------------------------------------------------
    def _build_synthesis(self, rapport: Dict[str, Any]) -> None:
        rep_sys = _deep_get(rapport, "rapports", "composants", "systeme_complet")
        rep_mt_def = _deep_get(rapport, "rapports", "composants", "moteur_thermique_definition")
        mt_ctx = _context_moteur(rep_sys, self.composants_obj.get("moteur_thermique"))

        pieces_analysees = sorted(
            [k for k, v in _safe_dict(_deep_get(rapport, "rapports", "pieces")).items() if isinstance(v, dict)]
        )
        pieces_demandees = sorted([k for k in self.pieces.keys() if k in PIECE_CLASSES])
        pieces_non_fermees = sorted([k for k in pieces_demandees if k not in pieces_analysees])

        rapport["synthese"] = {
            "etat": {
                "systeme_complet_analyse": isinstance(rep_sys, dict),
                "moteur_thermique_defini_depuis_exigences": isinstance(rep_mt_def, dict),
                "optimisation_lancee": bool(isinstance(_deep_get(rapport, "rapports", "optimisation"), dict) and _deep_get(rapport, "rapports", "optimisation", "note") is None),
                "nb_inconnues_impossibles": len(_safe_dict(rapport.get("inconnues")).get("impossibles", []) or []),
                "nb_inconnues_partielles": len(_safe_dict(rapport.get("inconnues")).get("partielles", []) or []),
            },
            "moteur_thermique": {
                "architecture": mt_ctx.get("architecture"),
                "nombre_cylindres": mt_ctx.get("nombre_cylindres"),
                "alesage_m": mt_ctx.get("alesage_m"),
                "course_m": mt_ctx.get("course_m"),
                "rpm_nominal": mt_ctx.get("rpm_nominal"),
                "pression_max_pa": mt_ctx.get("pression_max_pa"),
                "pme_pa": mt_ctx.get("pme_pa"),
                "couple_requis_Nm": mt_ctx.get("couple_requis_Nm"),
                "puissance_requise_W": mt_ctx.get("puissance_requise_W"),
                "source": "systeme_complet" if isinstance(rep_sys, dict) else ("definition_depuis_exigences" if isinstance(rep_mt_def, dict) else None),
            },
            "systeme_complet": _deep_get(rep_sys, "synthese") if isinstance(rep_sys, dict) else None,
            "composants_construits": sorted(self.composants_obj.keys()),
            "pieces_demandees": pieces_demandees,
            "pieces_analysees": pieces_analysees,
            "pieces_non_fermees": pieces_non_fermees,
            "strategie_energie": {
                "mode": rapport["rapports"].get("strategie_energie", {}).get("mode_energetique"),
                "p_charge_cible_w": rapport["rapports"].get("strategie_energie", {}).get("bilan_bus_dc", {}).get("p_charge_cible_w"),
                "statut_transitoire": rapport["rapports"].get("strategie_energie", {}).get("validation_transitoire", {}).get("statut"),
            },
            "imports_indisponibles": sorted(_safe_dict(rapport.get("imports", {})).get("erreurs", {}).keys()),
        }
        resolved_synth = _synthese_from_resolution_payload(_resolution_payload_from_report(rapport))
        if resolved_synth:
            for section, values in resolved_synth.items():
                current = rapport["synthese"].get(section)
                if isinstance(current, dict) and isinstance(values, Mapping):
                    _merge_missing_values(current, values)
                elif current is None:
                    rapport["synthese"][section] = _to_jsonable(values)

        if not isinstance(rep_sys, dict):
            _add_note(rapport, "Le système complet n'a pas produit de rapport ; la synthèse dépend uniquement des briques disponibles.")
        if pieces_non_fermees:
            _add_note(rapport, "Certaines pièces demandées ne sont pas fermées faute de classe, de paramètres ou de dépendances disponibles.")

    # ------------------------------------------------------------------
    # Resolution centrale des inconnues
    # ------------------------------------------------------------------
    def _run_resolution_inconnues(
        self,
        rapport: Dict[str, Any],
        *,
        repository: Any = None,
        project_id: Optional[str] = None,
    ) -> None:
        if not callable(resoudre_inconnues_systeme):
            _push_inconnue(
                rapport,
                "partielles",
                "resolution_inconnues",
                "Module backend.ensemble.resolution_inconnues indisponible.",
            )
            return

        payload = _flatten_resolution_inputs(self.composants, self.pieces, self.analyses, self.meta)
        if repository is not None and project_id:
            try:
                repo_params = repository.get_project_parameters(project_id)
            except Exception as exc:
                repo_params = {}
                _push_inconnue(rapport, "partielles", "repository", f"Lecture repository impossible : {exc}")
            if isinstance(repo_params, Mapping) and repo_params:
                self.analyses = _deep_merge(_safe_dict(repo_params.get("analyses")), self.analyses)
                self.composants = _deep_merge(_safe_dict(repo_params.get("composants")), self.composants)
                self.pieces = _deep_merge(_safe_dict(repo_params.get("pieces")), self.pieces)
                payload = _flatten_resolution_inputs(self.composants, self.pieces, self.analyses, self.meta)
        cdc_cfg = _deep_merge(
            _safe_dict(self.meta.get("cahier_des_charges")),
            _safe_dict(self.analyses.get("cahier_des_charges")),
        )

        try:
            if CahierDesChargesSTHOME is not None and cdc_cfg:
                allowed = set(getattr(CahierDesChargesSTHOME, "__dataclass_fields__", {}).keys())
                cdc = CahierDesChargesSTHOME(**{k: v for k, v in cdc_cfg.items() if k in allowed})
            elif CahierDesChargesSTHOME is not None:
                cdc = CahierDesChargesSTHOME()
            else:
                cdc = cdc_cfg
            rep = resoudre_inconnues_systeme(payload, {}, cdc)
        except Exception as exc:
            _push_inconnue(rapport, "partielles", "resolution_inconnues", f"Resolution centrale impossible : {exc}")
            return

        rep_dict = rep.en_dict() if hasattr(rep, "en_dict") else _safe_dict(rep)
        rapport["resolution_inconnues"] = _to_jsonable(rep_dict, max_depth=10)
        rapport["hypotheses_resolues"] = list(_safe_dict(rep_dict).get("hypotheses") or [])
        rapport["donnees_auto_completees"] = _safe_dict(rep_dict.get("donnees_auto_completees"))
        rapport["coherence_systeme"] = _safe_dict(rep_dict.get("coherence_systeme"))

        payload_resolu = _safe_dict(rep_dict.get("payload_resolu"))
        composants_resolus = _safe_dict(payload_resolu.get("composants"))
        pieces_resolues = _safe_dict(payload_resolu.get("pieces"))
        analyses_resolues = _safe_dict(payload_resolu.get("analyses"))
        analyses_patch = _analyses_from_resolution_payload(payload_resolu)
        if composants_resolus:
            self.composants = _deep_merge(self.composants, composants_resolus)
        if pieces_resolues:
            self.pieces = _deep_merge(self.pieces, pieces_resolues)
        if analyses_resolues:
            self.analyses = _deep_merge(self.analyses, analyses_resolues)
        if analyses_patch:
            self.analyses = _deep_merge(self.analyses, analyses_patch)

        inconnues_resolution = _safe_dict(rep_dict.get("inconnues"))
        for key, items in inconnues_resolution.items():
            if key == "resolues_automatiquement":
                continue
            if isinstance(items, list) and items:
                rapport.setdefault("inconnues_resolution", {})[key] = items
        _add_note(rapport, "Resolution centrale des inconnues appliquee par STHO_ME avant construction des composants.")

    def _run_resolution_candidates_pipeline(
        self,
        rapport: Dict[str, Any],
        *,
        repository: Any = None,
        project_id: Optional[str] = None,
        strict: bool = True,
        optimize: bool = True,
    ) -> None:
        if not callable(resoudre_inconnues_systeme_modules):
            return
        cdc = _deep_merge(
            _safe_dict(self.meta.get("cahier_des_charges")),
            _safe_dict(self.analyses.get("cahier_des_charges")),
        )
        config = {
            "meta": _to_jsonable(self.meta, max_depth=6),
            "composants": _to_jsonable(self.composants, max_depth=6),
            "pieces": _to_jsonable(self.pieces, max_depth=6),
            "analyses": _to_jsonable(self.analyses, max_depth=6),
        }

        def _recalculer(cfg: Dict[str, Any]) -> Dict[str, Any]:
            return STHO_ME.depuis_config(cfg).analyser(
                resolve_unknowns=False,
                optimize=optimize,
                strict=strict,
                frontend_contract=False,
            )

        def _optimiser(rep: Dict[str, Any]) -> Dict[str, Any]:
            if not optimize or not callable(optimiser_rapport_sthome):
                return {"status": "error", "erreur": "optimisation indisponible ou desactivee"}
            out = optimiser_rapport_sthome(
                rapport_backend=rep,
                rapports_pieces=_safe_dict(_deep_get(rep, "rapports", "pieces")),
                objets=_safe_dict(rep.get("objets")),
                cahier_des_charges=cdc,
                strict=strict,
            )
            rep.setdefault("tracabilite", {}).setdefault("optimization_runs", []).append(out)
            return out

        try:
            result = resoudre_inconnues_systeme_modules(
                config=config,
                rapport=rapport,
                cahier_des_charges=cdc,
                repository=repository,
                project_id=project_id,
                recalculer=_recalculer,
                optimiser=_optimiser if optimize else None,
                strict=strict,
                max_iterations=int(cdc.get("max_iterations", 5) or 5),
            )
        except Exception as exc:
            _push_inconnue(rapport, "partielles", "resolution_candidates", f"Pipeline candidats impossible : {exc}")
            return

        result_dict = result.en_dict() if hasattr(result, "en_dict") else _safe_dict(result)
        rapport["resolution_candidates"] = _to_jsonable(result_dict, max_depth=10)
        trace = _safe_dict(rapport.setdefault("tracabilite", {}))
        trace.setdefault("candidates", []).extend(result_dict.get("candidates", []) or [])
        trace.setdefault("rejected_candidates", []).extend(
            _safe_dict(_safe_dict(result_dict.get("rapport_apres")).get("tracabilite")).get("rejected_candidates", []) or []
        )
        rapport["tracabilite"] = trace
        rapport["traçabilite"] = trace
        if result_dict.get("accepte"):
            _add_note(rapport, "Pipeline de candidats : au moins une donnee candidate a ete acceptee apres validation.")

    def _finalize_contract_sections(
        self,
        rapport: Dict[str, Any],
        *,
        frontend_contract: bool,
        project_id: Optional[str],
        strict: bool,
    ) -> None:
        composants_reports = _safe_dict(_deep_get(rapport, "rapports", "composants"))
        pieces_reports = _safe_dict(_deep_get(rapport, "rapports", "pieces"))
        rapport["entrees"] = {
            "meta": _to_jsonable(self.meta, max_depth=4),
            "composants": _to_jsonable(self.composants, max_depth=4),
            "pieces": _to_jsonable(self.pieces, max_depth=4),
            "analyses": _to_jsonable(self.analyses, max_depth=4),
        }
        rapport["donnees"] = {
            "composants": _to_jsonable(composants_reports, max_depth=5),
            "pieces": _to_jsonable(pieces_reports, max_depth=5),
            "auto_completees": _safe_dict(rapport.get("donnees_auto_completees")),
        }
        synth = _safe_dict(rapport.get("synthese"))
        rapport["sous_systemes"] = {
            "moteur_electrique": composants_reports.get("moteur_electrique_orchestrateur") or composants_reports.get("moteur_electrique") or synth.get("moteur_electrique"),
            "batterie": composants_reports.get("batterie_orchestrateur") or composants_reports.get("batterie") or synth.get("batterie"),
            "alternateur": composants_reports.get("alternateur_orchestrateur") or composants_reports.get("alternateur_bus_dc") or synth.get("alternateur"),
            "moteur_thermique": composants_reports.get("moteur_thermique_orchestrateur") or composants_reports.get("moteur_thermique_definition") or synth.get("moteur_thermique"),
            "boite_crabots": composants_reports.get("boite_crabots_orchestrateur") or composants_reports.get("boite_chaine") or synth.get("boite_crabots"),
            "architecture": composants_reports.get("architecture_orchestrateur") or composants_reports.get("architecture"),
        }
        rapport["pieces"] = pieces_reports
        rapport["liaisons"] = _safe_dict(_deep_get(composants_reports, "systeme_complet", "liaisons"))
        rapport["criteres_conception"] = _deep_merge(
            _safe_dict(self.meta.get("cahier_des_charges")),
            _safe_dict(self.analyses.get("cahier_des_charges")),
        )
        rapport["optimisation"] = _safe_dict(_deep_get(rapport, "rapports", "optimisation"))
        rapport["cao"] = _safe_dict(_deep_get(composants_reports, "systeme_complet", "cao"))
        rapport["strategie_energie"] = _safe_dict(rapport["rapports"].get("strategie_energie")) or _safe_dict(synth.get("strategie_energie"))
        if callable(generer_graphiques_mecaniques_backend):
            try:
                rapport["mechanical_graphs"] = generer_graphiques_mecaniques_backend(rapport, strict=strict)
            except Exception as exc:
                rapport["mechanical_graphs"] = {
                    "status": "error",
                    "error": str(exc),
                    "graphiques": [],
                }
        if callable(construire_dossier_cao_sthome_backend):
            try:
                rapport["cao_dossier"] = construire_dossier_cao_sthome_backend(rapport, strict=strict)
                resume_cao = _safe_dict(_deep_get(rapport, "cao_dossier", "resume"))
                rapport["cao"] = _deep_merge(_safe_dict(rapport.get("cao")), resume_cao)
                rapport["cao"]["step_export"] = False
                rapport["cao"]["solidworks_ready"] = False
            except Exception as exc:
                rapport["cao_dossier"] = {
                    "mode": "indisponible",
                    "error": str(exc),
                    "resume": {
                        "step_export": False,
                        "solidworks_ready": False,
                        "sketches_available": False,
                        "views_3d_available": False,
                        "stress_graphs_available": False,
                        "drawing_data_available": False,
                    },
                }
                rapport["cao"] = _deep_merge(
                    _safe_dict(rapport.get("cao")),
                    _safe_dict(_deep_get(rapport, "cao_dossier", "resume")),
                )
        trace = _safe_dict(rapport.get("tracabilite"))
        for hyp in rapport.get("hypotheses_resolues", []) if isinstance(rapport.get("hypotheses_resolues"), list) else []:
            if isinstance(hyp, Mapping) and hyp.get("champ"):
                trace.setdefault("valeurs", {})[str(hyp["champ"])] = {
                    "source": hyp.get("type_resolution"),
                    "from": hyp.get("source"),
                    "formula": hyp.get("formule"),
                    "dependencies": hyp.get("dependances", {}),
                    "validated_by": hyp.get("validation", {}),
                }
        rapport["tracabilite"] = trace
        rapport["traçabilite"] = trace
        if frontend_contract and callable(build_frontend_contract_backend):
            try:
                rapport["frontend"] = build_frontend_contract_backend(rapport, project_id=project_id)
            except Exception as exc:
                rapport["frontend"] = {"error": str(exc), "raw_available": True}

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def analyser(
        self,
        *,
        config: Optional[dict] = None,
        cahier_des_charges: Optional[dict] = None,
        repository: Any = None,
        resolve_unknowns: bool = True,
        optimize: bool = True,
        strict: bool = True,
        frontend_contract: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if config is not None or cahier_des_charges is not None or kwargs:
            merged = {
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
                merged["analyses"] = _deep_merge(_safe_dict(merged.get("analyses")), {"systeme_complet": dict(kwargs)})
            return STHO_ME.depuis_config(merged).analyser(
                repository=repository,
                resolve_unknowns=resolve_unknowns,
                optimize=optimize,
                strict=strict,
                frontend_contract=frontend_contract,
            )

        self._reset_runtime()
        rapport = self._new_report()

        project_id = str(self.meta.get("project_id") or self.meta.get("id_projet") or "") or None
        if resolve_unknowns:
            self._run_resolution_inconnues(rapport, repository=repository, project_id=project_id)
        self._build_components(rapport)
        self._run_component_analyses(rapport)
        self._build_pieces(rapport)
        self._run_piece_analyses(rapport)
        if optimize:
            if isinstance(self.analyses.get("optimisation"), dict):
                self.analyses["optimisation"].setdefault("active", True)
            else:
                self.analyses["optimisation"] = {"active": True}
            self._run_optimisation(rapport)
        else:
            rapport["rapports"]["optimisation"] = {"note": "Optimisation desactivee par appelant."}
        _dedup_report_lists(rapport)
        self._build_synthesis(rapport)
        if resolve_unknowns:
            self._run_resolution_candidates_pipeline(
                rapport,
                repository=repository,
                project_id=project_id,
                strict=strict,
                optimize=optimize,
            )
        self._finalize_contract_sections(rapport, frontend_contract=frontend_contract, project_id=project_id, strict=strict)
        _dedup_report_lists(rapport)
        return _to_jsonable(rapport, max_depth=12)

    def export_json(self, path: str | os.PathLike[str], *, indent: int = 2) -> str:
        rapport = self.analyser()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rapport, ensure_ascii=False, indent=indent), encoding="utf-8")
        return str(out)

    @classmethod
    def depuis_config(cls, config: Mapping[str, Any]) -> "STHO_ME":
        normalized = _normaliser_config_entree(config)
        return cls(
            composants=dict(_safe_dict(normalized.get("composants"))),
            pieces=dict(_safe_dict(normalized.get("pieces"))),
            analyses=dict(_safe_dict(normalized.get("analyses"))),
            meta=dict(_safe_dict(normalized.get("meta"))),
        )


# =============================================================================
# Fonctions utilitaires haut niveau
# =============================================================================


def concevoir_systeme_stho_me(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Entrée haut niveau recommandée depuis API, GUI, notebook ou script main.py."""
    return STHO_ME.depuis_config(config).analyser()


def sauvegarder_conception_stho_me(
    config: Mapping[str, Any],
    path_json: str | os.PathLike[str],
    *,
    indent: int = 2,
) -> str:
    """Construit le rapport STHO-ME et le sauvegarde en JSON UTF-8."""
    return STHO_ME.depuis_config(config).export_json(path_json, indent=indent)


# =============================================================================
# CLI minimale
# =============================================================================

if __name__ == "__main__":
    exemple_config: Dict[str, Any] = {
        "meta": {
            "nom_projet": "STHO-ME",
            "mode": "exemple_minimal",
        },
        "composants": {
            "moteur_electrique": {
                "puissance_max_w": 80_000.0,
                "regime_max_rpm": 8_000.0,
                "couple_max_nm": 220.0,
                "tension_bus_v": 400.0,
                "rendement_moteur": 0.93,
            },
            "batterie": {
                "tension_nominale_v": 400.0,
                "fenetre_soc": 0.8,
                "rendement_charge": 0.94,
                "tension_charge_v": 420.0,
            },
            "alternateur": {
                "nombre_poles": 12,
                "connexion": "Y",
            },
            "architecture": {
                "temps_moteur": 4,
                "rendement_mecanique": 0.85,
            },
        },
        "analyses": {
            "moteur_thermique_definition": {
                "puissance_visee_w": 70_000.0,
                "type_puissance": "frein",
                "rpm": 3_000.0,
                "pression_moyenne_effective_pa": 8.0e5,
                "temps_moteur": 4,
                "rendement_mecanique": 0.85,
                "vitesse_piston_max_ms": 10.0,
                "ratio_course_alesage_max": 1.2,
                "L_max_m": 1.2,
                "W_max_m": 0.8,
                "architectures_autorisees": ("L", "V", "Etoile", "Boxer"),
                "pression_max_pa": 3.0e6,
                "contrainte_admissible_pa": 1.2e8,
            },
            "systeme_complet": {
                "puissance_moyenne_kw": 50.0,
                "puissance_pic_kw": 80.0,
                "scenario_bus_dc": "max",
                "vitesse_moteur_thermique_rpm": 3_000.0,
                "rapport_vitesse_alt_sur_moteur": 2.0,
                "pme_pa": 8.0e5,
                "vitesse_piston_max_ms": 10.0,
                "longueur_dispo_m": 1.2,
                "largeur_dispo_m": 0.8,
                "pression_max_pa": 3.0e6,
                "contrainte_admissible_pa": 1.2e8,
                "puissance_auxiliaire_w": 2_000.0,
            },
        },
        "pieces": {
            "cylindre": {"longueur_utile_m": 0.18, "materiau_cle": "acier_42crmo4_qt"},
            "piston": {"materiau_piston_cle": "alu_6061_t6"},
            "joint_piston": {"materiau_joint_cle": "ptfe"},
            "bielle": {"materiau_cle": "acier_42crmo4_qt", "longueur_bielle_m": 0.24},
            "arbre_piston": {"materiau_cle": "acier_42crmo4_qt", "longueur_totale_m": 0.30, "longueur_fut_central_m": 0.16},
            "coussinet_arbre_piston": {"materiau_coussinet": "bronze_cusn12"},
            "couvercle_cylindre": {"materiau_cle": "acier_42crmo4_qt"},
            "vis_couvercle_cylindre": {"classe_vis_iso898": "10.9"},
            "deplaceur": {"longueur_totale_m": 0.14, "materiau_cle": "inox_316l"},
            "joint_deplaceur": {"materiau_joint_cle": "ptfe"},
            "arbre_vilebrequin": {"materiau_cle": "acier_42crmo4_qt"},
            "vilbrequin": {"materiau_cle": "acier_42crmo4_qt"},
            "roulement_aiguille_arbre": {"duree_vie_cible_h": 5_000.0, "exposant_vie_p": 10.0 / 3.0},
            "roulement_aiguille_arbre_vilebrequin": {"vie_cible_heures": 5_000.0},
            "arbre": {"materiau_arbre_cle": "acier_42crmo4_qt"},
        },
    }

    rapport = concevoir_systeme_stho_me(exemple_config)
    print(json.dumps(rapport.get("synthese", {}), ensure_ascii=False, indent=2))
