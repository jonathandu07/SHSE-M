# backend/components/moteur_thermique/orchestrateur_moteur_thermique.py
from __future__ import annotations

"""
Orchestrateur approfondi du moteur thermique.

Rôle
----
Ce fichier ne remplace pas les calculateurs spécialisés. Il les pilote dans
un ordre cohérent : géométrie -> gaz -> cinématique -> efforts -> travail /
puissance -> frottements -> usure -> précharge -> carburant -> cycle mécanique
-> vérification d'assemblage.

Principes
---------
- Aucune cote n'est inventée.
- Si une donnée manque, elle est inscrite dans `inconnues`.
- Si un module échoue ou n'est pas importable, l'erreur est conservée dans le
  rapport au lieu de faire tomber tout le pipeline.
- Les tableaux NumPy sont convertissables en listes pour export JSON.

Placement recommandé
--------------------
- backend/components/moteur_thermique/orchestrateur_moteur_thermique.py

Il fonctionne aussi en fichier autonome si tes modules sont à côté du script
(calcul_cylindree.py, calcul_gaz.py, cycle_mecanique.py, etc.).
"""

import importlib
import inspect
import json
import math
import sys
from dataclasses import asdict, dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

try:  # NumPy est déjà requis par cycle_mecanique.py / calcul_cylindree.py
    import numpy as np
except Exception:  # pragma: no cover - l'orchestrateur reste importable sans NumPy
    np = None  # type: ignore


# =============================================================================
# Chemins et imports robustes
# =============================================================================

_THIS_FILE = Path(__file__).resolve()
_THIS_DIR = _THIS_FILE.parent
for candidate in (_THIS_DIR, _THIS_DIR.parent, _THIS_DIR.parent.parent, _THIS_DIR.parent.parent.parent, Path.cwd()):
    if str(candidate) not in sys.path:
        sys.path.append(str(candidate))


def _import_module_any(*names: str) -> Optional[Any]:
    last_error: Optional[Exception] = None
    for name in names:
        try:
            return importlib.import_module(name)
        except Exception as exc:
            last_error = exc
    return None


def _import_attr(module_candidates: Sequence[str], attr: str, default: Any = None) -> Any:
    for module_name in module_candidates:
        try:
            module = importlib.import_module(module_name)
            return getattr(module, attr)
        except Exception:
            continue
    return default


# Modules moteur thermique : chemins package + chemins plats
_CYL_MODS = (
    "backend.components.moteur_thermique.modules.calcul_cylindree",
    "backend.modules.moteur_thermique.calcul_cylindree",
    "modules.moteur_thermique.calcul_cylindree",
    "calcul_cylindree",
)
_GAZ_MODS = (
    "backend.components.moteur_thermique.modules.calcul_gaz",
    "backend.modules.moteur_thermique.calcul_gaz",
    "modules.moteur_thermique.calcul_gaz",
    "calcul_gaz",
)
_TRAVAIL_MODS = (
    "backend.components.moteur_thermique.modules.calcul_travail_indique",
    "backend.modules.moteur_thermique.calcul_travail_indique",
    "modules.moteur_thermique.calcul_travail_indique",
    "calcul_travail_indique",
)
_F_INERTIE_MODS = (
    "backend.components.moteur_thermique.modules.calcul_force_inertie",
    "backend.modules.moteur_thermique.calcul_force_inertie",
    "modules.moteur_thermique.calcul_force_inertie",
    "calcul_force_inertie",
)
_COUPLE_MODS = (
    "backend.components.moteur_thermique.modules.calcul_couple_vilebrequin",
    "backend.modules.moteur_thermique.calcul_couple_vilebrequin",
    "modules.moteur_thermique.calcul_couple_vilebrequin",
    "calcul_couple_vilebrequin",
)
_FROTTEMENT_MODS = (
    "backend.components.moteur_thermique.modules.calcul_pertes_frottement",
    "backend.modules.moteur_thermique.calcul_pertes_frottement",
    "modules.moteur_thermique.calcul_pertes_frottement",
    "calcul_pertes_frottement",
)
_PRECHARGE_MODS = (
    "backend.components.moteur_thermique.modules.calcul_precharge_vis",
    "backend.modules.moteur_thermique.calcul_precharge_vis",
    "modules.moteur_thermique.calcul_precharge_vis",
    "calcul_precharge_vis",
)
_USURE_MODS = (
    "backend.components.moteur_thermique.modules.calcul_usure_archard",
    "backend.modules.moteur_thermique.calcul_usure_archard",
    "modules.moteur_thermique.calcul_usure_archard",
    "calcul_usure_archard",
)
_VITESSE_PISTON_MODS = (
    "backend.components.moteur_thermique.modules.calcul_vitesse_piston",
    "backend.modules.moteur_thermique.calcul_vitesse_piston",
    "modules.moteur_thermique.calcul_vitesse_piston",
    "calcul_vitesse_piston",
)
_CARBURANT_MODS = (
    "backend.ensemble.carburant",
    "backend.components.moteur_thermique.modules.calcul_carburant",
    "backend.modules.moteur_thermique.calcul_carburant",
    "modules.moteur_thermique.calcul_carburant",
    "calcul_carburant",
)
_CYCLE_MODS = (
    "backend.components.moteur_thermique.modules.cycle_mecanique",
    "backend.modules.moteur_thermique.cycle_mecanique",
    "modules.moteur_thermique.cycle_mecanique",
    "cycle_mecanique",
)
_VERIF_MODS = (
    "backend.components.moteur_thermique.modules.verificateur_assemblage",
    "backend.modules.moteur_thermique.verificateur_assemblage",
    "modules.moteur_thermique.verificateur_assemblage",
    "verificateur_assemblage",
)

# Géométrie / cylindre / pression
calcul_cylindree_unitaire = _import_attr(_CYL_MODS, "calcul_cylindree_unitaire")
calcul_cylindree_totale = _import_attr(_CYL_MODS, "calcul_cylindree_totale")
calcul_volume_mort = _import_attr(_CYL_MODS, "calcul_volume_mort")
calcul_taux_compression = _import_attr(_CYL_MODS, "calcul_taux_compression")
calcul_ratio_alesage_course = _import_attr(_CYL_MODS, "calcul_ratio_alesage_course")
calcul_epaisseur_paroi_depuis_alesage = _import_attr(_CYL_MODS, "calcul_epaisseur_paroi_depuis_alesage")
verifier_hypothese_paroi_mince = _import_attr(_CYL_MODS, "verifier_hypothese_paroi_mince")
calcul_force_gaz_cyl = _import_attr(_CYL_MODS, "calcul_force_gaz")
calculer_cylindre_complet = _import_attr(_CYL_MODS, "calculer_cylindre_complet")
calculer_cycle_mecanique_depuis_modele_pression = _import_attr(_CYL_MODS, "calculer_cycle_mecanique_depuis_modele_pression")
evaluer_cycles_mecaniques_pour_cas_charge = _import_attr(_CYL_MODS, "evaluer_cycles_mecaniques_pour_cas_charge")
CasChargePression = _import_attr(_CYL_MODS, "CasChargePression")
ParametresWiebe = _import_attr(_CYL_MODS, "ParametresWiebe")
CourbePressionMesuree = _import_attr(_CYL_MODS, "CourbePressionMesuree")

# Gaz
calculer_gaz_complet = _import_attr(_GAZ_MODS, "calculer_gaz_complet")
calcul_force_gaz = _import_attr(_GAZ_MODS, "calcul_force_gaz")
calcul_densite_gaz_parfait = _import_attr(_GAZ_MODS, "calcul_densite_gaz_parfait")
calcul_masse_gaz_parfait = _import_attr(_GAZ_MODS, "calcul_masse_gaz_parfait")
calcul_temperature_compression_adiabatique = _import_attr(_GAZ_MODS, "calcul_temperature_compression_adiabatique")
calcul_debit_fuite_annulaire = _import_attr(_GAZ_MODS, "calcul_debit_fuite_annulaire")
calcul_masse_fuite = _import_attr(_GAZ_MODS, "calcul_masse_fuite")
calcul_reynolds_fuite_annulaire = _import_attr(_GAZ_MODS, "calcul_reynolds_fuite_annulaire")

# Travail, inertie, couple
calcul_travail_indique_pme = _import_attr(_TRAVAIL_MODS, "calcul_travail_indique_pme")
calcul_puissance_indiquee = _import_attr(_TRAVAIL_MODS, "calcul_puissance_indiquee")
calcul_force_inertie_alternative = _import_attr(_F_INERTIE_MODS, "calcul_force_inertie_alternative")
calcul_couple_instantane = _import_attr(_COUPLE_MODS, "calcul_couple_instantane")
calcul_vitesse_moyenne_piston = _import_attr(_VITESSE_PISTON_MODS, "calcul_vitesse_moyenne_piston")

# Frottements
calcul_puissance_frottement_segment = _import_attr(_FROTTEMENT_MODS, "calcul_puissance_frottement_segment")
calcul_puissance_frottement_palier = _import_attr(_FROTTEMENT_MODS, "calcul_puissance_frottement_palier")
calcul_vitesse_glissement_palier_depuis_diametre = _import_attr(_FROTTEMENT_MODS, "calcul_vitesse_glissement_palier_depuis_diametre")
calcul_couple_frottement_depuis_puissance = _import_attr(_FROTTEMENT_MODS, "calcul_couple_frottement_depuis_puissance")
calcul_puissance_frottement_depuis_couple = _import_attr(_FROTTEMENT_MODS, "calcul_puissance_frottement_depuis_couple")
calcul_puissance_frottement_moteur_totale = _import_attr(_FROTTEMENT_MODS, "calcul_puissance_frottement_moteur_totale")
calcul_fmep_depuis_puissance_frottement = _import_attr(_FROTTEMENT_MODS, "calcul_fmep_depuis_puissance_frottement")
calcul_rendement_mecanique_depuis_puissances = _import_attr(_FROTTEMENT_MODS, "calcul_rendement_mecanique_depuis_puissances")
calcul_puissance_frottement_visqueux_palier_concentrique = _import_attr(_FROTTEMENT_MODS, "calcul_puissance_frottement_visqueux_palier_concentrique")

# Précharge, usure
calcul_force_separation = _import_attr(_PRECHARGE_MODS, "calcul_force_separation")
calcul_precharge_vis_totale = _import_attr(_PRECHARGE_MODS, "calcul_precharge_vis_totale")
calcul_couple_serrage = _import_attr(_PRECHARGE_MODS, "calcul_couple_serrage")
calcul_volume_usure_archard = _import_attr(_USURE_MODS, "calcul_volume_usure_archard")
calcul_perte_epaisseur = _import_attr(_USURE_MODS, "calcul_perte_epaisseur")

# Carburant
CompositionElementaireCombustible = _import_attr(_CARBURANT_MODS, "CompositionElementaireCombustible")
Carburant = _import_attr(_CARBURANT_MODS, "Carburant")
get_pire_carburant = _import_attr(_CARBURANT_MODS, "get_pire_carburant")
calcul_bilan_carburant_simple = _import_attr(_CARBURANT_MODS, "calcul_bilan_carburant_simple")
calcul_debit_massique_carburant_depuis_puissance_utile = _import_attr(_CARBURANT_MODS, "calcul_debit_massique_carburant_depuis_puissance_utile")
calcul_puissance_chimique_combustion = _import_attr(_CARBURANT_MODS, "calcul_puissance_chimique_combustion")
calcul_puissance_thermique_utile_combustion = _import_attr(_CARBURANT_MODS, "calcul_puissance_thermique_utile_combustion")
calcul_debit_volumique_carburant = _import_attr(_CARBURANT_MODS, "calcul_debit_volumique_carburant")

# Cycle direct
CycleMecaniqueParams = _import_attr(_CYCLE_MODS, "CycleMecaniqueParams")
calculer_cycle_mecanique = _import_attr(_CYCLE_MODS, "calculer_cycle_mecanique")

# Vérificateur assemblage
VerificateurAssemblage = _import_attr(_VERIF_MODS, "VerificateurAssemblage")
AssemblyIssue = _import_attr(_VERIF_MODS, "AssemblyIssue")


# =============================================================================
# Helpers généraux
# =============================================================================

Number = Union[int, float]


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _safe_float(x: Any) -> Optional[float]:
    try:
        if _is_finite(x):
            return float(x)
    except Exception:
        pass
    return None


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


def _first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _first_finite(*values: Any) -> Optional[float]:
    for value in values:
        if _is_finite(value):
            return float(value)
    return None


def _safe_div(num: Optional[float], den: Optional[float]) -> Optional[float]:
    if num is None or den is None:
        return None
    if not _is_finite(num) or not _is_finite(den):
        return None
    if abs(float(den)) <= 1e-18:
        return None
    return float(num) / float(den)


def _sum_finite(values: Iterable[Any]) -> Optional[float]:
    xs = [float(v) for v in values if _is_finite(v)]
    return sum(xs) if xs else None


def _callable_present(fn: Any) -> bool:
    return callable(fn)


def _filter_kwargs_for_callable(fn: Callable[..., Any], kwargs: Mapping[str, Any]) -> Dict[str, Any]:
    """Évite les TypeError si un module ancien ne possède pas encore un paramètre."""
    try:
        sig = inspect.signature(fn)
    except Exception:
        return {k: v for k, v in kwargs.items() if v is not None}

    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return {k: v for k, v in kwargs.items() if v is not None}

    accepted = set(sig.parameters.keys())
    return {k: v for k, v in kwargs.items() if k in accepted and v is not None}


def _to_jsonable(value: Any, *, tableaux_en_listes: bool = True, depth: int = 0, max_depth: int = 8) -> Any:
    if depth > max_depth:
        return {"type": type(value).__name__, "truncated": True}
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        return value
    if isinstance(value, Path):
        return str(value)
    if np is not None and isinstance(value, np.ndarray):
        return value.tolist() if tableaux_en_listes else {"type": "ndarray", "shape": list(value.shape)}
    if is_dataclass(value):
        try:
            return _to_jsonable(asdict(value), tableaux_en_listes=tableaux_en_listes, depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "as_dict") and callable(getattr(value, "as_dict")):
        try:
            return _to_jsonable(value.as_dict(), tableaux_en_listes=tableaux_en_listes, depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "en_dict") and callable(getattr(value, "en_dict")):
        try:
            return _to_jsonable(value.en_dict(), tableaux_en_listes=tableaux_en_listes, depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v, tableaux_en_listes=tableaux_en_listes, depth=depth + 1, max_depth=max_depth) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v, tableaux_en_listes=tableaux_en_listes, depth=depth + 1, max_depth=max_depth) for v in value]
    if hasattr(value, "__dict__"):
        try:
            return {
                "type": type(value).__name__,
                "attributs": _to_jsonable(
                    {k: v for k, v in vars(value).items() if not k.startswith("_") and not callable(v)},
                    tableaux_en_listes=tableaux_en_listes,
                    depth=depth + 1,
                    max_depth=max_depth,
                ),
            }
        except Exception:
            pass
    return str(value)


def _push_item(report: Dict[str, Any], section: str, category: str, nom: str, raison: str) -> None:
    report.setdefault(section, {}).setdefault(category, []).append({"nom": str(nom), "raison": str(raison)})


def _push_inconnue(report: Dict[str, Any], category: str, nom: str, raison: str) -> None:
    _push_item(report, "inconnues", category, nom, raison)


def _push_alerte(report: Dict[str, Any], category: str, nom: str, detail: str) -> None:
    report.setdefault("alertes", {}).setdefault(category, []).append({"nom": str(nom), "detail": str(detail)})


def _append_note(report: Dict[str, Any], note: str) -> None:
    report.setdefault("notes_modele", []).append(str(note))


def _dedup_report(report: Dict[str, Any]) -> None:
    for section in ("inconnues", "alertes"):
        bloc = _safe_dict(report.get(section))
        for category, values in list(bloc.items()):
            seen = set()
            out = []
            for item in list(values or []):
                if not isinstance(item, dict):
                    continue
                sig = tuple(sorted((str(k), str(v)) for k, v in item.items()))
                if sig in seen:
                    continue
                seen.add(sig)
                out.append(item)
            bloc[category] = out
        report[section] = bloc


def _try(label: str, report: Dict[str, Any], fn: Callable[[], Any], *, target_section: Optional[str] = None) -> Any:
    try:
        result = fn()
        if target_section is not None:
            report[target_section] = _to_jsonable(result)
        return result
    except Exception as exc:
        _push_inconnue(report, "impossibles", label, str(exc))
        return None


def _require_values(report: Dict[str, Any], label: str, values: Mapping[str, Any]) -> bool:
    missing = []
    for name, value in values.items():
        if value is None:
            missing.append(name)
        elif isinstance(value, float) and not math.isfinite(value):
            missing.append(name)
    if missing:
        _push_inconnue(report, "impossibles", label, "Données manquantes: " + ", ".join(missing))
        return False
    return True


def _module_status() -> Dict[str, bool]:
    return {
        "calcul_cylindree": callable(calcul_cylindree_unitaire) and callable(calculer_cylindre_complet),
        "calcul_gaz": callable(calculer_gaz_complet),
        "calcul_travail_indique": callable(calcul_travail_indique_pme) and callable(calcul_puissance_indiquee),
        "calcul_force_inertie": callable(calcul_force_inertie_alternative),
        "calcul_couple_vilebrequin": callable(calcul_couple_instantane),
        "calcul_pertes_frottement": callable(calcul_puissance_frottement_segment),
        "calcul_precharge_vis": callable(calcul_force_separation),
        "calcul_usure_archard": callable(calcul_volume_usure_archard),
        "calcul_vitesse_piston": callable(calcul_vitesse_moyenne_piston),
        "calcul_carburant": callable(calcul_bilan_carburant_simple) and Carburant is not None,
        "cycle_mecanique": callable(calculer_cycle_mecanique) and CycleMecaniqueParams is not None,
        "verificateur_assemblage": VerificateurAssemblage is not None,
    }


# =============================================================================
# Entrées unifiées
# =============================================================================

@dataclass(frozen=True)
class ConfigurationCarburant:
    nom: str
    pci_j_kg: float
    densite_kg_m3: Optional[float] = None
    pcs_j_kg: Optional[float] = None
    composition: Optional[Dict[str, float]] = None
    rapport_air_carburant_stoech_massique: Optional[float] = None
    rapport_oxygene_carburant_stoech_massique: Optional[float] = None
    commentaire: str = ""


@dataclass(frozen=True)
class EntreesOrchestrateurMoteurThermique:
    # Géométrie principale
    alesage_m: Optional[float] = None
    course_m: Optional[float] = None
    nombre_cylindres: Optional[int] = None
    temps_moteur: int = 4
    longueur_bielle_m: Optional[float] = None
    rayon_manivelle_m: Optional[float] = None
    axe_decale_m: float = 0.0

    # Cycle / chambre
    taux_compression: Optional[float] = None
    volume_mort_m3: Optional[float] = None
    ordre_allumage: Optional[Union[str, Sequence[int]]] = None
    regime_tr_min: Optional[float] = None
    masse_alternative_kg: Optional[float] = None
    masse_tournante_equivalente_kg: float = 0.0
    pression_reference_pa: Optional[float] = None
    pression_admission_pa: Optional[float] = None
    pression_echappement_pa: Optional[float] = None
    n_polytropique_compression: float = 1.32
    n_polytropique_detente: float = 1.25
    pas_angle_deg: float = 1.0

    # Loi de pression / cylindre
    mode_pression: Optional[str] = None  # "constante", "enveloppe", "tableau", "mesuree", "wiebe" selon tes modules
    pression_cylindre_pa: Optional[float] = None
    pression_moyenne_effective_pa: Optional[float] = None
    pression_constante_pa: Optional[float] = None
    pression_max_pa: Optional[float] = None
    angle_pic_deg: float = 5.0
    largeur_pic_deg: float = 18.0
    forme_pic: str = "gaussienne"
    theta_tableau_deg: Optional[Sequence[float]] = None
    pression_tableau_pa: Optional[Sequence[float]] = None
    courbe_mesuree: Optional[Any] = None
    parametres_wiebe: Optional[Any] = None
    cas_de_charge: Optional[Sequence[Any]] = None
    temperature_gaz_utile_k: Optional[float] = None

    # Résistance cylindre
    contrainte_admissible_pa: Optional[float] = None
    modele_paroi: str = "auto"
    facteur_securite_cylindre: float = 1.5
    include_longitudinale: bool = False
    ratio_mince_max: float = 0.1

    # Gaz parfait / fuite
    masse_gaz_kg: Optional[float] = None
    volume_gaz_m3: Optional[float] = None
    temperature_gaz_k: Optional[float] = None
    constante_gaz_r: float = 287.05
    t1_k: Optional[float] = None
    p1_pa: Optional[float] = None
    p2_pa: Optional[float] = None
    t2_k: Optional[float] = None
    gamma: float = 1.4
    delta_p_fuite_pa: Optional[float] = None
    jeu_radial_h_m: Optional[float] = None
    rayon_fuite_m: Optional[float] = None
    longueur_fuite_m: Optional[float] = None
    viscosite_dynamique_pa_s: Optional[float] = None
    densite_gaz_kg_m3: Optional[float] = None

    # Frottements
    force_normale_segment_n: Optional[float] = None
    coef_frottement_segment: Optional[float] = None
    vitesse_moyenne_segment_ms: Optional[float] = None
    charge_palier_n: Optional[float] = None
    coef_frottement_palier: Optional[float] = None
    vitesse_glissement_palier_ms: Optional[float] = None
    diametre_palier_m: Optional[float] = None
    rayon_arbre_palier_m: Optional[float] = None
    longueur_palier_m: Optional[float] = None
    jeu_radial_palier_m: Optional[float] = None
    autres_puissances_frottement_w: Tuple[float, ...] = tuple()

    # Usure
    coefficient_usure_segment_k: Optional[float] = None
    durete_contact_segment_pa: Optional[float] = None
    aire_contact_segment_m2: Optional[float] = None
    coefficient_usure_palier_k: Optional[float] = None
    durete_contact_palier_pa: Optional[float] = None
    aire_contact_palier_m2: Optional[float] = None
    duree_fonctionnement_s: Optional[float] = None

    # Couvercle / vis
    aire_effective_couvercle_m2: Optional[float] = None
    force_joint_n: Optional[float] = None
    facteur_securite_vis: float = 1.5
    nombre_vis: Optional[int] = None
    diametre_nominal_vis_m: Optional[float] = None
    facteur_frottement_vis_k: float = 0.2

    # Carburant
    carburant: Optional[Any] = None
    carburant_config: Optional[ConfigurationCarburant] = None
    debit_massique_carburant_kg_s: Optional[float] = None
    puissance_utile_w: Optional[float] = None
    rendement_global: Optional[float] = None
    lambda_exces_air: Optional[float] = None
    co2_ppm_air: float = 420.0
    cp_gaz_echappement_j_kg_k: Optional[float] = None
    temperature_gaz_echappement_in_k: Optional[float] = None
    temperature_gaz_echappement_out_k: Optional[float] = None
    efficacite_echangeur_echappement: float = 1.0

    # Assemblage minimal si aucun rapport pièce externe n'est fourni
    diametre_piston_m: Optional[float] = None
    diametre_axe_piston_m: Optional[float] = None
    diametre_axe_exterieur_m: Optional[float] = None
    diametre_maneton_bielle_m: Optional[float] = None
    diametre_maneton_vilebrequin_m: Optional[float] = None
    diametre_cylindre_exterieur_m: Optional[float] = None
    diametre_couvercle_exterieur_m: Optional[float] = None

    # Rapports pièces réels, si disponibles depuis tes classes de pièces
    rapports_pieces: Optional[Dict[str, Dict[str, Any]]] = None
    pieces_instances: Optional[Dict[str, Any]] = None

    # Sortie
    tableaux_en_listes: bool = True

    def with_overrides(self, **overrides: Any) -> "EntreesOrchestrateurMoteurThermique":
        allowed = {f.name for f in fields(self)}
        clean = {k: v for k, v in overrides.items() if k in allowed}
        return replace(self, **clean) if clean else self


# =============================================================================
# Orchestrateur principal
# =============================================================================

@dataclass(frozen=True)
class OrchestrateurMoteurThermique(EntreesOrchestrateurMoteurThermique):

    # ------------------------------------------------------------------
    # API principale
    # ------------------------------------------------------------------
    def analyser(self, *, strict: bool = False, **overrides: Any) -> Dict[str, Any]:
        e = self.with_overrides(**overrides)
        report = self._nouveau_rapport(e)

        self._analyser_geometrie(e, report)
        self._analyser_cylindre_complet(e, report)
        self._analyser_gaz(e, report)
        self._analyser_cinematique(e, report)
        self._analyser_efforts(e, report)
        self._analyser_travail_puissance(e, report)
        self._analyser_frottements(e, report)
        self._analyser_usure(e, report)
        self._analyser_precharge_vis(e, report)
        self._analyser_carburant(e, report)
        self._analyser_cycle_mecanique(e, report)
        self._verifier_assemblage(e, report)
        self._synthese_finale(e, report)

        _dedup_report(report)
        if strict and report.get("inconnues", {}).get("impossibles"):
            raise ValueError(json.dumps(report["inconnues"]["impossibles"], ensure_ascii=False, indent=2))
        return _to_jsonable(report, tableaux_en_listes=e.tableaux_en_listes)

    def export_json(self, chemin: Union[str, Path], *, indent: int = 2, **overrides: Any) -> Path:
        path = Path(chemin)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.analyser(**overrides)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # Rapport
    # ------------------------------------------------------------------
    def _nouveau_rapport(self, e: EntreesOrchestrateurMoteurThermique) -> Dict[str, Any]:
        return {
            "meta": {
                "orchestrateur": "OrchestrateurMoteurThermique",
                "mode": "calcul_approfondi_sans_invention",
                "modules_disponibles": _module_status(),
            },
            "entrees": _to_jsonable(e),
            "geometrie": {},
            "cylindre": {},
            "gaz": {},
            "cinematique": {},
            "efforts": {},
            "travail_puissance": {},
            "frottements": {},
            "usure": {},
            "precharge_vis": {},
            "carburant": {},
            "cycle_mecanique": {},
            "assemblage": {},
            "synthese": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "alertes": {"coherence": [], "modele": []},
            "notes_modele": [],
        }

    # ------------------------------------------------------------------
    # 1) Géométrie de base
    # ------------------------------------------------------------------
    def _analyser_geometrie(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> None:
        if not callable(calcul_cylindree_unitaire):
            _push_inconnue(r, "impossibles", "calcul_cylindree_unitaire", "Module indisponible.")
            return

        B = e.alesage_m
        S = e.course_m
        N = e.nombre_cylindres

        if _require_values(r, "géométrie cylindrée", {"alesage_m": B, "course_m": S}):
            vd_unit = _try(
                "cylindrée unitaire",
                r,
                lambda: calcul_cylindree_unitaire(B, S, return_details=True),
            )
            if isinstance(vd_unit, dict):
                r["geometrie"]["cylindree_unitaire"] = vd_unit
                vd_unit_val = _safe_float(vd_unit.get("V_d"))
            else:
                vd_unit_val = _safe_float(vd_unit)
                r["geometrie"]["cylindree_unitaire_m3"] = vd_unit_val

            if vd_unit_val is not None and N is not None and callable(calcul_cylindree_totale):
                r["geometrie"]["cylindree_totale_m3"] = _try(
                    "cylindrée totale",
                    r,
                    lambda: calcul_cylindree_totale(vd_unit_val, int(N)),
                )
            elif N is None:
                _push_inconnue(r, "partielles", "nombre_cylindres", "Requis pour la cylindrée totale.")

            if callable(calcul_ratio_alesage_course):
                r["geometrie"]["ratio_alesage_course"] = _try(
                    "ratio alésage/course",
                    r,
                    lambda: calcul_ratio_alesage_course(B, S, return_details=True),
                )

            # Rayon de manivelle explicite ou déduit de la course
            rayon = _first_finite(e.rayon_manivelle_m, 0.5 * S if _is_finite(S) else None)
            if rayon is not None:
                r["geometrie"]["rayon_manivelle_effectif_m"] = rayon

            # Taux compression / volume mort
            if e.taux_compression is not None and callable(calcul_volume_mort):
                r["geometrie"]["volume_mort_m3"] = _try(
                    "volume mort depuis taux compression",
                    r,
                    lambda: calcul_volume_mort(vd_unit_val, e.taux_compression),
                ) if vd_unit_val is not None else None
            elif e.volume_mort_m3 is not None and callable(calcul_taux_compression):
                r["geometrie"]["taux_compression"] = _try(
                    "taux compression depuis volume mort",
                    r,
                    lambda: calcul_taux_compression(vd_unit_val, e.volume_mort_m3),
                ) if vd_unit_val is not None else None
            else:
                _push_inconnue(r, "partielles", "taux_compression / volume_mort_m3", "Requis pour le volume mort et le cycle mécanique.")

        # Dimensionnement paroi si le triplet minimum existe
        if B is not None and e.pression_max_pa is not None and e.contrainte_admissible_pa is not None and callable(calcul_epaisseur_paroi_depuis_alesage):
            r["geometrie"]["epaisseur_paroi"] = _try(
                "épaisseur paroi cylindre",
                r,
                lambda: calcul_epaisseur_paroi_depuis_alesage(
                    pression_pa=e.pression_max_pa,
                    alesage_m=B,
                    contrainte_admissible_pa=e.contrainte_admissible_pa,
                    modele=e.modele_paroi,
                    facteur_securite=e.facteur_securite_cylindre,
                    include_longitudinale=e.include_longitudinale,
                    ratio_mince_max=e.ratio_mince_max,
                    return_details=True,
                ),
            )
            ep = _extract_first_number(r["geometrie"].get("epaisseur_paroi"), "t", "epaisseur_m", "epaisseur_retenue_m")
            if ep is not None and callable(verifier_hypothese_paroi_mince):
                r["geometrie"]["hypothese_paroi_mince"] = _try(
                    "hypothèse paroi mince",
                    r,
                    lambda: verifier_hypothese_paroi_mince(ep, float(B) / 2.0, ratio_max=e.ratio_mince_max),
                )
        else:
            missing = [k for k, v in {
                "alesage_m": B,
                "pression_max_pa": e.pression_max_pa,
                "contrainte_admissible_pa": e.contrainte_admissible_pa,
            }.items() if v is None]
            if missing:
                _push_inconnue(r, "partielles", "dimensionnement paroi cylindre", "Données manquantes: " + ", ".join(missing))

    # ------------------------------------------------------------------
    # 2) Agrégateur cylindre complet
    # ------------------------------------------------------------------
    def _analyser_cylindre_complet(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> None:
        if not callable(calculer_cylindre_complet):
            _push_inconnue(r, "partielles", "calculer_cylindre_complet", "Agrégateur cylindre indisponible.")
            return

        minimum = {
            "alesage_m": e.alesage_m,
            "course_m": e.course_m,
            "nombre_cylindres": e.nombre_cylindres,
            "taux_compression/volume_mort_m3": _first_non_none(e.taux_compression, e.volume_mort_m3),
        }
        if not _require_values(r, "calculer_cylindre_complet", minimum):
            return

        kwargs = {
            "alesage_m": e.alesage_m,
            "course_m": e.course_m,
            "nombre_cylindres": e.nombre_cylindres,
            "taux_compression": e.taux_compression,
            "volume_mort_m3": e.volume_mort_m3,
            "pression_pa": e.pression_cylindre_pa,
            "contrainte_admissible_pa": e.contrainte_admissible_pa,
            "modele_paroi": e.modele_paroi,
            "facteur_securite": e.facteur_securite_cylindre,
            "include_longitudinale": e.include_longitudinale,
            "ratio_mince_max": e.ratio_mince_max,
            "mode_pression": e.mode_pression,
            "pas_angle_deg": e.pas_angle_deg,
            "longueur_bielle_m": e.longueur_bielle_m,
            "axe_decale_m": e.axe_decale_m,
            "courbe_mesuree": e.courbe_mesuree,
            "theta_tableau_deg": e.theta_tableau_deg,
            "pression_tableau_pa": e.pression_tableau_pa,
            "parametres_wiebe": e.parametres_wiebe,
            "pression_constante_pa": e.pression_constante_pa,
            "pression_max_pa": e.pression_max_pa,
            "angle_pic_deg": e.angle_pic_deg,
            "largeur_pic_deg": e.largeur_pic_deg,
            "pression_admission_pa": e.pression_admission_pa,
            "pression_echappement_pa": e.pression_echappement_pa,
            "forme_pic": e.forme_pic,
            "cas_de_charge": e.cas_de_charge,
        }
        r["cylindre"]["calcul_complet"] = _try(
            "calculer_cylindre_complet",
            r,
            lambda: calculer_cylindre_complet(**_filter_kwargs_for_callable(calculer_cylindre_complet, kwargs)),
        )

    # ------------------------------------------------------------------
    # 3) Gaz parfait / fuite
    # ------------------------------------------------------------------
    def _analyser_gaz(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> None:
        if callable(calculer_gaz_complet):
            any_gas = any(v is not None for v in (
                e.pression_cylindre_pa, e.masse_gaz_kg, e.volume_gaz_m3, e.temperature_gaz_k,
                e.t1_k, e.p1_pa, e.p2_pa, e.t2_k,
                e.delta_p_fuite_pa, e.jeu_radial_h_m, e.rayon_fuite_m, e.longueur_fuite_m, e.viscosite_dynamique_pa_s,
            ))
            if any_gas:
                kwargs = {
                    "pression_pa": e.pression_cylindre_pa,
                    "masse_kg": e.masse_gaz_kg,
                    "volume_m3": e.volume_gaz_m3,
                    "temperature_k": e.temperature_gaz_k,
                    "constante_gaz_r": e.constante_gaz_r,
                    "t1_k": e.t1_k,
                    "p1_pa": e.p1_pa,
                    "p2_pa": e.p2_pa,
                    "t2_k": e.t2_k,
                    "gamma": e.gamma,
                    "alesage_m": e.alesage_m,
                    "delta_p_pa": e.delta_p_fuite_pa,
                    "jeu_radial_h_m": e.jeu_radial_h_m,
                    "rayon_fuite_m": e.rayon_fuite_m,
                    "longueur_fuite_m": e.longueur_fuite_m,
                    "viscosite_dynamique_pa_s": e.viscosite_dynamique_pa_s,
                }
                r["gaz"]["calcul_complet"] = _try(
                    "calculer_gaz_complet",
                    r,
                    lambda: calculer_gaz_complet(**_filter_kwargs_for_callable(calculer_gaz_complet, kwargs)),
                )

        # Force gaz instantanée utile aux efforts
        if e.pression_cylindre_pa is not None and e.alesage_m is not None and callable(calcul_force_gaz):
            r["gaz"]["force_gaz"] = _try(
                "force gaz",
                r,
                lambda: calcul_force_gaz(e.pression_cylindre_pa, e.alesage_m, clamp_non_negative=False, return_details=True),
            )

        # Densité gaz déductible si non fournie
        if e.densite_gaz_kg_m3 is None and e.pression_cylindre_pa is not None and e.temperature_gaz_k is not None and callable(calcul_densite_gaz_parfait):
            r["gaz"]["densite_deduite_kg_m3"] = _try(
                "densité gaz parfait",
                r,
                lambda: calcul_densite_gaz_parfait(e.pression_cylindre_pa, e.temperature_gaz_k, e.constante_gaz_r),
            )

    # ------------------------------------------------------------------
    # 4) Cinématique
    # ------------------------------------------------------------------
    def _analyser_cinematique(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> None:
        if e.course_m is not None and e.regime_tr_min is not None and callable(calcul_vitesse_moyenne_piston):
            r["cinematique"]["vitesse_moyenne_piston_ms"] = _try(
                "vitesse moyenne piston",
                r,
                lambda: calcul_vitesse_moyenne_piston(e.course_m, e.regime_tr_min),
            )
        else:
            _push_inconnue(r, "partielles", "vitesse moyenne piston", "Requiert course_m et regime_tr_min.")

        rayon = _first_finite(e.rayon_manivelle_m, 0.5 * e.course_m if _is_finite(e.course_m) else None)
        if rayon is not None:
            r["cinematique"]["rayon_manivelle_m"] = rayon
        if e.regime_tr_min is not None:
            r["cinematique"]["omega_rad_s"] = 2.0 * math.pi * float(e.regime_tr_min) / 60.0

    # ------------------------------------------------------------------
    # 5) Efforts instantanés
    # ------------------------------------------------------------------
    def _analyser_efforts(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> None:
        rayon = _first_finite(e.rayon_manivelle_m, 0.5 * e.course_m if _is_finite(e.course_m) else None)

        # Force gaz depuis pression/alésage
        F_gaz = _extract_first_number(r.get("gaz", {}).get("force_gaz"), "F_g", "force_gaz_n")
        if F_gaz is None and e.pression_cylindre_pa is not None and e.alesage_m is not None and callable(calcul_force_gaz):
            F_gaz = _try("force gaz simple", r, lambda: calcul_force_gaz(e.pression_cylindre_pa, e.alesage_m))
        if F_gaz is not None:
            r["efforts"]["force_gaz_n"] = F_gaz

        # Inertie alternative à l'angle choisi, si fourni
        if (
            e.masse_alternative_kg is not None
            and rayon is not None
            and e.regime_tr_min is not None
            and e.longueur_bielle_m is not None
            and e.angle_pic_deg is not None
            and callable(calcul_force_inertie_alternative)
        ):
            angle_eff = e.angle_pic_deg if e.pression_max_pa is not None else 0.0
            r["efforts"]["force_inertie_alternative_angle_reference"] = _try(
                "force inertie alternative",
                r,
                lambda: calcul_force_inertie_alternative(
                    e.masse_alternative_kg,
                    rayon,
                    e.regime_tr_min,
                    e.longueur_bielle_m,
                    angle_eff,
                    return_details=True,
                ),
            )
        else:
            _push_inconnue(
                r,
                "partielles",
                "force inertie alternative",
                "Requiert masse_alternative_kg, rayon/course, regime_tr_min, longueur_bielle_m.",
            )

        F_inertie = _extract_first_number(r["efforts"].get("force_inertie_alternative_angle_reference"), "F_i", "force_inertie_n", "F")
        F_bielle = None
        if F_gaz is not None and F_inertie is not None:
            F_bielle = F_gaz - F_inertie
            r["efforts"]["force_bielle_nette_n"] = F_bielle
        elif F_gaz is not None:
            F_bielle = F_gaz
            r["efforts"]["force_bielle_nette_n"] = F_bielle
            _append_note(r, "Force bielle prise égale à la force gaz, faute de force d'inertie calculable.")

        # Couple instantané au vilebrequin
        if F_bielle is not None and rayon is not None and callable(calcul_couple_instantane):
            angle_couple = e.angle_pic_deg if e.angle_pic_deg is not None else 90.0
            r["efforts"]["couple_instantane_reference"] = _try(
                "couple instantané vilebrequin",
                r,
                lambda: calcul_couple_instantane(F_bielle, rayon, angle_couple, return_details=True),
            )

    # ------------------------------------------------------------------
    # 6) Travail / puissance
    # ------------------------------------------------------------------
    def _analyser_travail_puissance(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> None:
        Vd_total = _extract_first_number(r.get("geometrie", {}), "cylindree_totale_m3")
        Vd_unit = _extract_first_number(r.get("geometrie", {}).get("cylindree_unitaire"), "V_d")
        if Vd_total is None and Vd_unit is not None and e.nombre_cylindres is not None:
            Vd_total = Vd_unit * int(e.nombre_cylindres)

        if e.pression_moyenne_effective_pa is not None and Vd_total is not None and callable(calcul_travail_indique_pme):
            Wi = _try(
                "travail indiqué PME",
                r,
                lambda: calcul_travail_indique_pme(e.pression_moyenne_effective_pa, Vd_total),
            )
            r["travail_puissance"]["travail_indique_cycle_total_j"] = Wi

            if Wi is not None and e.regime_tr_min is not None and callable(calcul_puissance_indiquee):
                Pi = _try(
                    "puissance indiquée",
                    r,
                    lambda: calcul_puissance_indiquee(Wi, e.regime_tr_min, int(e.temps_moteur)),
                )
                r["travail_puissance"]["puissance_indiquee_w"] = Pi
        else:
            _push_inconnue(
                r,
                "partielles",
                "travail/puissance indiquée",
                "Requiert pression_moyenne_effective_pa, cylindree_totale et regime_tr_min pour aller jusqu'à la puissance.",
            )

    # ------------------------------------------------------------------
    # 7) Frottements
    # ------------------------------------------------------------------
    def _analyser_frottements(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> None:
        P_segment = None
        P_palier = None
        P_visqueux = None

        vitesse_segment = _first_finite(e.vitesse_moyenne_segment_ms, r.get("cinematique", {}).get("vitesse_moyenne_piston_ms"))
        if e.force_normale_segment_n is not None and vitesse_segment is not None and e.coef_frottement_segment is not None and callable(calcul_puissance_frottement_segment):
            P_segment = _try(
                "frottement segment",
                r,
                lambda: calcul_puissance_frottement_segment(e.force_normale_segment_n, vitesse_segment, e.coef_frottement_segment),
            )
            r["frottements"]["P_frottement_segment_W"] = P_segment
        else:
            _push_inconnue(r, "partielles", "frottement segment", "Requiert force_normale_segment_n, vitesse segment/piston et coef_frottement_segment.")

        vitesse_palier = e.vitesse_glissement_palier_ms
        if vitesse_palier is None and e.diametre_palier_m is not None and e.regime_tr_min is not None and callable(calcul_vitesse_glissement_palier_depuis_diametre):
            vitesse_palier = _try(
                "vitesse glissement palier",
                r,
                lambda: calcul_vitesse_glissement_palier_depuis_diametre(e.diametre_palier_m, e.regime_tr_min),
            )
            r["frottements"]["vitesse_glissement_palier_ms"] = vitesse_palier

        if e.charge_palier_n is not None and vitesse_palier is not None and e.coef_frottement_palier is not None and callable(calcul_puissance_frottement_palier):
            P_palier = _try(
                "frottement palier",
                r,
                lambda: calcul_puissance_frottement_palier(e.charge_palier_n, vitesse_palier, e.coef_frottement_palier),
            )
            r["frottements"]["P_frottement_palier_W"] = P_palier
        else:
            _push_inconnue(r, "partielles", "frottement palier Coulomb", "Requiert charge_palier_n, vitesse_glissement_palier_ms/diametre_palier_m, coef_frottement_palier.")

        if (
            e.viscosite_dynamique_pa_s is not None
            and e.rayon_arbre_palier_m is not None
            and e.longueur_palier_m is not None
            and e.jeu_radial_palier_m is not None
            and e.regime_tr_min is not None
            and callable(calcul_puissance_frottement_visqueux_palier_concentrique)
        ):
            P_visqueux = _try(
                "frottement visqueux palier concentrique",
                r,
                lambda: calcul_puissance_frottement_visqueux_palier_concentrique(
                    e.viscosite_dynamique_pa_s,
                    e.rayon_arbre_palier_m,
                    e.longueur_palier_m,
                    e.jeu_radial_palier_m,
                    e.regime_tr_min,
                ),
            )
            r["frottements"]["P_frottement_visqueux_palier_W"] = P_visqueux

        total = _sum_finite([P_segment, P_palier, P_visqueux, *e.autres_puissances_frottement_w])
        if total is not None:
            r["frottements"]["P_frottement_total_W"] = total
            if e.regime_tr_min is not None and callable(calcul_couple_frottement_depuis_puissance):
                r["frottements"]["couple_frottement_total_Nm"] = _try(
                    "couple frottement total",
                    r,
                    lambda: calcul_couple_frottement_depuis_puissance(total, e.regime_tr_min),
                )

            Vd_total = _extract_first_number(r.get("geometrie", {}), "cylindree_totale_m3")
            if Vd_total is not None and e.regime_tr_min is not None and callable(calcul_fmep_depuis_puissance_frottement):
                r["frottements"]["fmep_pa"] = _try(
                    "FMEP",
                    r,
                    lambda: calcul_fmep_depuis_puissance_frottement(total, Vd_total, e.regime_tr_min, temps_moteur=int(e.temps_moteur)),
                )

            Pi = _safe_float(r.get("travail_puissance", {}).get("puissance_indiquee_w"))
            if Pi is not None and callable(calcul_rendement_mecanique_depuis_puissances):
                r["frottements"]["rendement_mecanique_estime"] = _try(
                    "rendement mécanique depuis frottements",
                    r,
                    lambda: calcul_rendement_mecanique_depuis_puissances(Pi, total),
                )
                r["travail_puissance"]["puissance_frein_estimee_w"] = Pi - total

    # ------------------------------------------------------------------
    # 8) Usure Archard
    # ------------------------------------------------------------------
    def _analyser_usure(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> None:
        distance_segment = None
        vitesse_segment = _first_finite(e.vitesse_moyenne_segment_ms, r.get("cinematique", {}).get("vitesse_moyenne_piston_ms"))
        if vitesse_segment is not None and e.duree_fonctionnement_s is not None:
            distance_segment = vitesse_segment * e.duree_fonctionnement_s
            r["usure"]["distance_glissement_segment_m"] = distance_segment

        if (
            e.coefficient_usure_segment_k is not None
            and e.force_normale_segment_n is not None
            and distance_segment is not None
            and e.durete_contact_segment_pa is not None
            and callable(calcul_volume_usure_archard)
        ):
            Vw = _try(
                "usure segment Archard",
                r,
                lambda: calcul_volume_usure_archard(
                    e.coefficient_usure_segment_k,
                    e.force_normale_segment_n,
                    distance_segment,
                    e.durete_contact_segment_pa,
                ),
            )
            r["usure"]["volume_usure_segment_m3"] = Vw
            if Vw is not None and e.aire_contact_segment_m2 is not None and callable(calcul_perte_epaisseur):
                r["usure"]["perte_epaisseur_segment_m"] = _try(
                    "perte épaisseur segment",
                    r,
                    lambda: calcul_perte_epaisseur(Vw, e.aire_contact_segment_m2),
                )
        else:
            _push_inconnue(r, "partielles", "usure segment", "Requiert coefficient_usure_segment_k, charge, distance, dureté et aire pour l'épaisseur.")

        distance_palier = None
        vitesse_palier = _first_finite(e.vitesse_glissement_palier_ms, r.get("frottements", {}).get("vitesse_glissement_palier_ms"))
        if vitesse_palier is not None and e.duree_fonctionnement_s is not None:
            distance_palier = vitesse_palier * e.duree_fonctionnement_s
            r["usure"]["distance_glissement_palier_m"] = distance_palier

        if (
            e.coefficient_usure_palier_k is not None
            and e.charge_palier_n is not None
            and distance_palier is not None
            and e.durete_contact_palier_pa is not None
            and callable(calcul_volume_usure_archard)
        ):
            Vw = _try(
                "usure palier Archard",
                r,
                lambda: calcul_volume_usure_archard(
                    e.coefficient_usure_palier_k,
                    e.charge_palier_n,
                    distance_palier,
                    e.durete_contact_palier_pa,
                ),
            )
            r["usure"]["volume_usure_palier_m3"] = Vw
            if Vw is not None and e.aire_contact_palier_m2 is not None and callable(calcul_perte_epaisseur):
                r["usure"]["perte_epaisseur_palier_m"] = _try(
                    "perte épaisseur palier",
                    r,
                    lambda: calcul_perte_epaisseur(Vw, e.aire_contact_palier_m2),
                )

    # ------------------------------------------------------------------
    # 9) Précharge vis couvercle
    # ------------------------------------------------------------------
    def _analyser_precharge_vis(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> None:
        pmax = e.pression_max_pa or e.pression_cylindre_pa
        if pmax is not None and e.aire_effective_couvercle_m2 is not None and callable(calcul_force_separation):
            Fsep = _try(
                "force séparation couvercle",
                r,
                lambda: calcul_force_separation(pmax, e.aire_effective_couvercle_m2),
            )
            r["precharge_vis"]["force_separation_n"] = Fsep
        else:
            Fsep = None
            _push_inconnue(r, "partielles", "force séparation couvercle", "Requiert pression_max_pa/pression_cylindre_pa et aire_effective_couvercle_m2.")

        if Fsep is not None and e.force_joint_n is not None and callable(calcul_precharge_vis_totale):
            Ftot = _try(
                "précharge totale vis",
                r,
                lambda: calcul_precharge_vis_totale(Fsep, e.force_joint_n, e.facteur_securite_vis),
            )
            r["precharge_vis"]["precharge_totale_n"] = Ftot
            if Ftot is not None and e.nombre_vis is not None and int(e.nombre_vis) > 0:
                Fvis = Ftot / int(e.nombre_vis)
                r["precharge_vis"]["precharge_par_vis_n"] = Fvis
                if e.diametre_nominal_vis_m is not None and callable(calcul_couple_serrage):
                    r["precharge_vis"]["couple_serrage_par_vis_nm"] = _try(
                        "couple serrage par vis",
                        r,
                        lambda: calcul_couple_serrage(Fvis, e.diametre_nominal_vis_m, e.facteur_frottement_vis_k),
                    )
        elif Fsep is not None:
            _push_inconnue(r, "partielles", "précharge vis", "Requiert force_joint_n, nombre_vis et diametre_nominal_vis_m pour aller jusqu'au couple de serrage.")

    # ------------------------------------------------------------------
    # 10) Carburant
    # ------------------------------------------------------------------
    def _build_carburant(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> Optional[Any]:
        if e.carburant is not None:
            return e.carburant
        
        # Logique "Pire Carburant" par défaut si rien n'est fourni
        if e.carburant_config is None and get_pire_carburant is not None:
            # On cherche le carburant le plus contraignant (ex: Ammoniac pour la taille/puissance)
            pire = get_pire_carburant(objectif="puissance")
            if pire:
                r["notes_modele"].append(f"Aucun carburant défini : utilisation du 'pire carburant' ({pire.nom}) pour le dimensionnement.")
                return pire

        if e.carburant_config is None:
            return None
        if Carburant is None:
            _push_inconnue(r, "impossibles", "Carburant", "Classe Carburant indisponible.")
            return None

        comp_obj = None
        if e.carburant_config.composition is not None:
            if CompositionElementaireCombustible is None:
                _push_inconnue(r, "impossibles", "CompositionElementaireCombustible", "Classe de composition indisponible.")
                return None
            comp_obj = CompositionElementaireCombustible(**e.carburant_config.composition)

        return Carburant(
            nom=e.carburant_config.nom,
            pci_j_kg=e.carburant_config.pci_j_kg,
            densite_kg_m3=e.carburant_config.densite_kg_m3,
            pcs_j_kg=e.carburant_config.pcs_j_kg,
            composition=comp_obj,
            rapport_air_carburant_stoech_massique=e.carburant_config.rapport_air_carburant_stoech_massique,
            rapport_oxygene_carburant_stoech_massique=e.carburant_config.rapport_oxygene_carburant_stoech_massique,
            commentaire=e.carburant_config.commentaire,
        )

    def _analyser_carburant(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> None:
        carburant = self._build_carburant(e, r)
        if carburant is None:
            _push_inconnue(r, "partielles", "carburant", "Aucun carburant ou carburant_config fourni.")
            return

        mdot = e.debit_massique_carburant_kg_s
        if mdot is None and e.puissance_utile_w is not None and e.rendement_global is not None and callable(calcul_debit_massique_carburant_depuis_puissance_utile):
            pci = getattr(carburant, "pci_j_kg", None)
            if pci is not None:
                mdot = _try(
                    "débit carburant depuis puissance utile",
                    r,
                    lambda: calcul_debit_massique_carburant_depuis_puissance_utile(e.puissance_utile_w, pci, e.rendement_global),
                )
                r["carburant"]["debit_massique_deduit_kg_s"] = mdot

        if mdot is None:
            _push_inconnue(r, "partielles", "débit carburant", "Fournis debit_massique_carburant_kg_s ou puissance_utile_w + rendement_global.")
            return

        if callable(calcul_bilan_carburant_simple):
            r["carburant"]["bilan"] = _try(
                "bilan carburant simple",
                r,
                lambda: calcul_bilan_carburant_simple(
                    carburant=carburant,
                    debit_massique_carburant_kg_s=mdot,
                    lambda_exces_air=e.lambda_exces_air if e.lambda_exces_air is not None else 1.0,
                    co2_ppm_air=e.co2_ppm_air,
                    cp_gaz_j_kg_k=e.cp_gaz_echappement_j_kg_k,
                    temperature_gaz_in_k=e.temperature_gaz_echappement_in_k,
                    temperature_gaz_out_k=e.temperature_gaz_echappement_out_k,
                    efficacite_echangeur=e.efficacite_echangeur_echappement,
                ),
            )

        if callable(calcul_debit_volumique_carburant):
            rho = getattr(carburant, "densite_kg_m3", None)
            if rho is not None:
                r["carburant"]["debit_volumique_m3_s"] = _try(
                    "débit volumique carburant",
                    r,
                    lambda: calcul_debit_volumique_carburant(mdot, rho),
                )

    # ------------------------------------------------------------------
    # 11) Cycle mécanique 720°
    # ------------------------------------------------------------------
    def _analyser_cycle_mecanique(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> None:
        # Cas de charge multiples : on privilégie l'agrégateur de calcul_cylindree.py s'il est fourni
        if e.cas_de_charge and callable(evaluer_cycles_mecaniques_pour_cas_charge):
            required = {
                "alesage_m": e.alesage_m,
                "course_m": e.course_m,
                "longueur_bielle_m": e.longueur_bielle_m,
                "nombre_cylindres": e.nombre_cylindres,
                "ordre_allumage": e.ordre_allumage,
                "masse_alternative_kg": e.masse_alternative_kg,
                "taux_compression/volume_mort_m3": _first_non_none(e.taux_compression, e.volume_mort_m3),
            }
            if _require_values(r, "cycles mécaniques multi-cas", required):
                try:
                    _multi_payload = evaluer_cycles_mecaniques_pour_cas_charge(
                        alesage_m=e.alesage_m,
                        course_m=e.course_m,
                        longueur_bielle_m=e.longueur_bielle_m,
                        nombre_cylindres=int(e.nombre_cylindres),
                        ordre_allumage=e.ordre_allumage,
                        masse_alternative_kg=e.masse_alternative_kg,
                        cas_de_charge=e.cas_de_charge,
                        taux_compression=e.taux_compression,
                        volume_mort_m3=e.volume_mort_m3,
                        masse_tournante_equivalente_kg=e.masse_tournante_equivalente_kg,
                        axe_decale_m=e.axe_decale_m,
                        pression_reference_pa=e.pression_reference_pa if e.pression_reference_pa is not None else 101325.0,
                        pas_angle_deg=e.pas_angle_deg,
                        rayon_maneton_m=_first_finite(e.rayon_manivelle_m, 0.5 * e.course_m if _is_finite(e.course_m) else None),
                    )
                except Exception as exc:
                    _multi_payload = None
                    _append_note(r, "Pont multi-cas calcul_cylindree -> cycle_mecanique indisponible ou incompatible: " + str(exc))
                if _multi_payload is not None:
                    r["cycle_mecanique"]["multi_cas"] = _multi_payload
                    return

        # Mode de pression explicite via calcul_cylindree.py : utile si enveloppe/wiebe/tableau
        if e.mode_pression is not None and callable(calculer_cycle_mecanique_depuis_modele_pression):
            required = {
                "alesage_m": e.alesage_m,
                "course_m": e.course_m,
                "longueur_bielle_m": e.longueur_bielle_m,
                "nombre_cylindres": e.nombre_cylindres,
                "ordre_allumage": e.ordre_allumage,
                "regime_tr_min": e.regime_tr_min,
                "masse_alternative_kg": e.masse_alternative_kg,
                "taux_compression/volume_mort_m3": _first_non_none(e.taux_compression, e.volume_mort_m3),
            }
            if _require_values(r, "cycle mécanique depuis modèle de pression", required):
                try:
                    _modele_payload = calculer_cycle_mecanique_depuis_modele_pression(
                        alesage_m=e.alesage_m,
                        course_m=e.course_m,
                        longueur_bielle_m=e.longueur_bielle_m,
                        nombre_cylindres=int(e.nombre_cylindres),
                        ordre_allumage=e.ordre_allumage,
                        regime_tr_min=e.regime_tr_min,
                        masse_alternative_kg=e.masse_alternative_kg,
                        mode_pression=e.mode_pression,
                        taux_compression=e.taux_compression,
                        volume_mort_m3=e.volume_mort_m3,
                        masse_tournante_equivalente_kg=e.masse_tournante_equivalente_kg,
                        axe_decale_m=e.axe_decale_m,
                        pression_reference_pa=e.pression_reference_pa if e.pression_reference_pa is not None else 101325.0,
                        temperature_gaz_utile_k=e.temperature_gaz_utile_k,
                        pas_angle_deg=e.pas_angle_deg,
                        n_polytropique_compression=e.n_polytropique_compression,
                        n_polytropique_detente=e.n_polytropique_detente,
                        rayon_maneton_m=_first_finite(e.rayon_manivelle_m, 0.5 * e.course_m if _is_finite(e.course_m) else None),
                        courbe_mesuree=e.courbe_mesuree,
                        theta_tableau_deg=e.theta_tableau_deg,
                        pression_tableau_pa=e.pression_tableau_pa,
                        parametres_wiebe=e.parametres_wiebe,
                        pression_constante_pa=e.pression_constante_pa,
                        pression_max_pa=e.pression_max_pa,
                        angle_pic_deg=e.angle_pic_deg,
                        largeur_pic_deg=e.largeur_pic_deg,
                        pression_admission_pa=e.pression_admission_pa if e.pression_admission_pa is not None else 101325.0,
                        pression_echappement_pa=e.pression_echappement_pa if e.pression_echappement_pa is not None else 101325.0,
                        forme_pic=e.forme_pic,
                    )
                except Exception as exc:
                    _modele_payload = None
                    _append_note(r, "Pont calcul_cylindree -> cycle_mecanique indisponible ou incompatible: " + str(exc))
                if _modele_payload is not None:
                    r["cycle_mecanique"]["modele_pression"] = _modele_payload
                    return
                _append_note(r, "Le pont calcul_cylindree -> cycle_mecanique a échoué ; tentative de repli sur CycleMecaniqueParams direct.")

        # Cycle direct : fonctionne même sans loi de pression externe, mais on signale l'hypothèse interne
        if not (callable(calculer_cycle_mecanique) and CycleMecaniqueParams is not None):
            _push_inconnue(r, "partielles", "cycle_mecanique", "Module cycle_mecanique indisponible.")
            return

        required = {
            "alesage_m": e.alesage_m,
            "course_m": e.course_m,
            "longueur_bielle_m": e.longueur_bielle_m,
            "nombre_cylindres": e.nombre_cylindres,
            "ordre_allumage": e.ordre_allumage,
            "regime_tr_min": e.regime_tr_min,
            "masse_alternative_kg": e.masse_alternative_kg,
            "taux_compression/volume_mort_m3": _first_non_none(e.taux_compression, e.volume_mort_m3, r.get("geometrie", {}).get("taux_compression")),
        }
        if not _require_values(r, "cycle mécanique direct", required):
            return

        cr = _first_finite(e.taux_compression, r.get("geometrie", {}).get("taux_compression"))
        if cr is None and e.volume_mort_m3 is not None and e.alesage_m is not None and e.course_m is not None and callable(calcul_cylindree_unitaire) and callable(calcul_taux_compression):
            vd_unit = calcul_cylindree_unitaire(e.alesage_m, e.course_m)
            cr = calcul_taux_compression(vd_unit, e.volume_mort_m3)

        params_kwargs = {
            "alesage_m": float(e.alesage_m),
            "course_m": float(e.course_m),
            "longueur_bielle_m": float(e.longueur_bielle_m),
            "nombre_cylindres": int(e.nombre_cylindres),
            "ordre_allumage": e.ordre_allumage,
            "regime_tr_min": float(e.regime_tr_min),
            "masse_alternative_kg": float(e.masse_alternative_kg),
            "masse_tournante_equivalente_kg": float(e.masse_tournante_equivalente_kg),
            "axe_decale_m": float(e.axe_decale_m),
            "rapport_volumetrique": float(cr),
            "pression_admission_pa": float(e.pression_admission_pa if e.pression_admission_pa is not None else 101325.0),
            "pression_echappement_pa": float(e.pression_echappement_pa if e.pression_echappement_pa is not None else 101325.0),
            "pression_reference_pa": float(e.pression_reference_pa if e.pression_reference_pa is not None else 101325.0),
            "temperature_gaz_utile_k": e.temperature_gaz_utile_k,
            "pas_angle_deg": float(e.pas_angle_deg),
            "n_polytropique_compression": float(e.n_polytropique_compression),
            "n_polytropique_detente": float(e.n_polytropique_detente),
            "rayon_maneton_m": _first_finite(e.rayon_manivelle_m, 0.5 * e.course_m if _is_finite(e.course_m) else None),
        }

        params = _try("construction CycleMecaniqueParams", r, lambda: CycleMecaniqueParams(**params_kwargs))
        if params is None:
            return
        resultat = _try("calculer_cycle_mecanique", r, lambda: calculer_cycle_mecanique(params))
        if resultat is not None:
            r["cycle_mecanique"]["direct"] = _to_jsonable(resultat, tableaux_en_listes=e.tableaux_en_listes)
            _append_note(r, "Cycle direct calculé avec le modèle interne de cycle_mecanique.py si aucune loi de pression externe n'a été fournie.")

    # ------------------------------------------------------------------
    # 12) Vérification assemblage
    # ------------------------------------------------------------------
    def _build_rapports_pieces_minimaux(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        rapports = dict(e.rapports_pieces or {})

        B = e.alesage_m
        d_cyl_ext = _first_finite(
            e.diametre_cylindre_exterieur_m,
            _extract_first_number(r.get("geometrie", {}).get("epaisseur_paroi"), "diametre_exterieur_m"),
        )
        if d_cyl_ext is None and B is not None:
            ep = _extract_first_number(r.get("geometrie", {}).get("epaisseur_paroi"), "t", "epaisseur_m", "epaisseur_retenue_m")
            if ep is not None:
                d_cyl_ext = float(B) + 2.0 * ep

        rapports.setdefault("cylindre", {
            "entrees": {"alesage_m": B, "course_m": e.course_m, "pression_max_pa": e.pression_max_pa},
            "geometrie": {"alesage_m": B, "diametre_exterieur_m": d_cyl_ext},
        })
        rapports.setdefault("piston", {
            "entrees": {"alesage_m": B},
            "geometrie": {
                "diametre_piston_m": _first_finite(e.diametre_piston_m, B),
                "diametre_axe_m": e.diametre_axe_piston_m,
            },
        })
        rapports.setdefault("arbre_piston", {
            "geometrie": {"diametre_exterieur_m": e.diametre_axe_exterieur_m},
        })
        rapports.setdefault("bielle", {
            "geometrie": {
                "longueur_bielle_m": e.longueur_bielle_m,
                "diametre_axe_piston_m": e.diametre_axe_piston_m,
                "diametre_maneton_m": e.diametre_maneton_bielle_m,
            },
        })
        # Le vérificateur fourni utilise la clé "vilbrequin".
        rapports.setdefault("vilbrequin", {
            "geometrie": {"diametre_maneton_m": e.diametre_maneton_vilebrequin_m},
        })
        rapports.setdefault("couvercle_cylindre", {
            "geometrie": {"diametre_exterieur_m": e.diametre_couvercle_exterieur_m},
        })
        return rapports

    def _verifier_assemblage(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> None:
        if VerificateurAssemblage is None:
            _push_inconnue(r, "partielles", "VerificateurAssemblage", "Module indisponible.")
            return
        rapports = self._build_rapports_pieces_minimaux(e, r)
        verif = VerificateurAssemblage(rapports, pieces_instances=e.pieces_instances)
        issues = _try("vérification assemblage", r, lambda: verif.verifier_tout())
        
        # Export pour l'optimiseur système (top-level)
        r["rapports_pieces"] = _to_jsonable(rapports, tableaux_en_listes=e.tableaux_en_listes)
        
        r["assemblage"]["rapports_pieces_utilises"] = r["rapports_pieces"]
        r["assemblage"]["issues"] = _to_jsonable(issues, tableaux_en_listes=e.tableaux_en_listes)
        r["assemblage"]["ok"] = bool(not issues)
        if issues:
            for issue in issues:
                grav = getattr(issue, "gravite", "erreur")
                _push_alerte(r, "coherence", f"assemblage {grav}", getattr(issue, "message", str(issue)))

    def resoudre_assemblage_et_relancer(
        self,
        callback_dimensionnement: Callable[[Dict[str, Any]], Dict[str, Dict[str, Any]]],
        *,
        max_iterations: int = 3,
        **overrides: Any,
    ) -> Dict[str, Any]:
        """
        Boucle optionnelle : exploite VerificateurAssemblage.resoudre_et_relancer.
        Le callback doit accepter un dictionnaire de paramètres et renvoyer des rapports pièces.
        """
        e = self.entrees.with_overrides(**overrides)
        base = self.analyser(**overrides)
        if VerificateurAssemblage is None:
            base.setdefault("inconnues", {}).setdefault("partielles", []).append({
                "nom": "VerificateurAssemblage.resoudre_et_relancer",
                "raison": "Module indisponible.",
            })
            return base
        rapports = _safe_dict(base.get("assemblage", {}).get("rapports_pieces_utilises"))
        verif = VerificateurAssemblage(rapports, pieces_instances=e.pieces_instances)
        params_initiaux = {k: v for k, v in asdict(e).items() if v is not None}
        try:
            rapports_corriges, issues = verif.resoudre_et_relancer(params_initiaux, callback_dimensionnement, max_iterations=max_iterations)
            base["assemblage_resolution"] = {
                "rapports_corriges": _to_jsonable(rapports_corriges),
                "issues_restantes": _to_jsonable(issues),
                "ok": not bool(issues),
            }
        except Exception as exc:
            base.setdefault("inconnues", {}).setdefault("impossibles", []).append({
                "nom": "résolution assemblage récursive",
                "raison": str(exc),
            })
        return base

    # ------------------------------------------------------------------
    # Synthèse finale
    # ------------------------------------------------------------------
    def _synthese_finale(self, e: EntreesOrchestrateurMoteurThermique, r: Dict[str, Any]) -> None:
        cycle = _safe_dict(r.get("cycle_mecanique"))
        cycle_payload = _first_non_none(cycle.get("modele_pression"), cycle.get("direct"), cycle.get("multi_cas"))
        stats = _extract_nested(cycle_payload, "cycle", "statistiques_cycle") or _extract_nested(cycle_payload, "statistiques_cycle")

        r["synthese"] = {
            "cylindree_unitaire_m3": _extract_first_number(r.get("geometrie", {}).get("cylindree_unitaire"), "V_d"),
            "cylindree_totale_m3": _extract_first_number(r.get("geometrie", {}), "cylindree_totale_m3"),
            "volume_mort_m3": _first_finite(r.get("geometrie", {}).get("volume_mort_m3"), e.volume_mort_m3),
            "taux_compression": _first_finite(r.get("geometrie", {}).get("taux_compression"), e.taux_compression),
            "vitesse_moyenne_piston_ms": _safe_float(r.get("cinematique", {}).get("vitesse_moyenne_piston_ms")),
            "force_gaz_reference_n": _safe_float(r.get("efforts", {}).get("force_gaz_n")),
            "couple_reference_nm": _extract_first_number(r.get("efforts", {}).get("couple_instantane_reference"), "T"),
            "puissance_indiquee_w": _safe_float(r.get("travail_puissance", {}).get("puissance_indiquee_w")),
            "puissance_frottement_total_w": _safe_float(r.get("frottements", {}).get("P_frottement_total_W")),
            "puissance_frein_estimee_w": _safe_float(r.get("travail_puissance", {}).get("puissance_frein_estimee_w")),
            "rendement_mecanique_estime": _safe_float(r.get("frottements", {}).get("rendement_mecanique_estime")),
            "assemblage_ok": bool(r.get("assemblage", {}).get("ok")) if "ok" in r.get("assemblage", {}) else None,
            "cycle_statistiques": stats,
        }

        # Cohérences simples
        Pi = r["synthese"].get("puissance_indiquee_w")
        Pf = r["synthese"].get("puissance_frottement_total_w")
        if Pi is not None and Pf is not None and Pf > Pi:
            _push_alerte(r, "coherence", "frottements > puissance indiquée", "Le modèle donne des pertes supérieures à la puissance indiquée : vérifier les coefficients et charges.")
        if e.taux_compression is not None and e.taux_compression <= 1.0:
            _push_alerte(r, "coherence", "taux_compression", "Un taux de compression <= 1 est physiquement invalide pour ce modèle.")
        if e.longueur_bielle_m is not None and e.course_m is not None:
            rayon = 0.5 * e.course_m
            if e.longueur_bielle_m <= rayon + abs(e.axe_decale_m):
                _push_alerte(r, "coherence", "bielle/manivelle", "Géométrie impossible : longueur_bielle_m <= rayon_manivelle + |axe_decale_m|.")


# =============================================================================
# Helpers d'extraction rapport
# =============================================================================

def _extract_nested(obj: Any, *path: str) -> Any:
    cur = obj
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, Mapping):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return cur


def _extract_first_number(obj: Any, *keys: str) -> Optional[float]:
    if obj is None:
        return None
    if _is_finite(obj):
        return float(obj)
    if isinstance(obj, Mapping):
        for key in keys:
            val = obj.get(key)
            if _is_finite(val):
                return float(val)
        # Recherche récursive prudente sur un niveau utile
        for value in obj.values():
            if isinstance(value, Mapping):
                out = _extract_first_number(value, *keys)
                if out is not None:
                    return out
    return None


# =============================================================================
# Exemple minimal volontairement explicite
# =============================================================================

def exemple_minimal() -> Dict[str, Any]:
    """Exemple de fumée : il ne valide pas un moteur réel, il vérifie le câblage."""
    orch = OrchestrateurMoteurThermique(
        EntreesOrchestrateurMoteurThermique(
            alesage_m=0.08,
            course_m=0.07,
            nombre_cylindres=4,
            temps_moteur=4,
            longueur_bielle_m=0.14,
            taux_compression=10.0,
            ordre_allumage=(1, 3, 4, 2),
            regime_tr_min=3000.0,
            masse_alternative_kg=0.55,
            pression_moyenne_effective_pa=8.0e5,
            pression_cylindre_pa=3.0e6,
            pression_max_pa=5.0e6,
            contrainte_admissible_pa=180e6,
            force_normale_segment_n=120.0,
            coef_frottement_segment=0.08,
            charge_palier_n=800.0,
            coef_frottement_palier=0.04,
            diametre_palier_m=0.04,
            aire_effective_couvercle_m2=0.005,
            force_joint_n=2000.0,
            nombre_vis=8,
            diametre_nominal_vis_m=0.008,
            mode_pression="enveloppe",
            pression_admission_pa=101325.0,
            pression_echappement_pa=120000.0,
            tableaux_en_listes=False,
        )
    )
    return orch.analyser()


@dataclass
class MoteurThermique:
    nombre_cylindres: Optional[int] = None
    temps_moteur: int = 4
    alesage_m: Optional[float] = None
    course_m: Optional[float] = None
    rpm_nominal: Optional[float] = None
    pme_nominale_pa: Optional[float] = None
    rendement_mecanique_nominal: Optional[float] = 0.85
    architecture: Optional[str] = None
    puissance_nominale_visee_w: Optional[float] = None
    type_puissance_nominale: Optional[str] = "frein"
    pression_max_pa: Optional[float] = None
    contrainte_admissible_pa: Optional[float] = None
    densite_materiau_kg_m3: Optional[float] = None
    cout_matiere_eur_kg: Optional[float] = None
    rendement_indique_cible_min: Optional[float] = None
    rendement_mecanique_cible_min: Optional[float] = None
    masse_estimee_max_kg: Optional[float] = None
    cout_matiere_max_eur: Optional[float] = None
    indice_maintenance_max: Optional[float] = None
    duree_vie_cible_h: Optional[float] = None
    vitesse_piston_max_ms: Optional[float] = None
    ratio_course_alesage_max: Optional[float] = None
    ratio_course_alesage_cible: Optional[float] = None
    taux_compression_nominal: Optional[float] = None
    volume_mort_nominal_m3: Optional[float] = None
    facteur_securite_cylindre: float = 1.5
    carburant: Optional[Any] = None
    architectures_autorisees: Optional[Tuple[str, ...]] = None
    architecture_forcee: Optional[str] = None

    def _to_entrees(self, **overrides: Any) -> EntreesOrchestrateurMoteurThermique:
        regime = _first_finite(overrides.get("rpm"), overrides.get("regime_tr_min"), self.rpm_nominal)
        pme = _first_finite(
            overrides.get("pression_moyenne_effective_pa"),
            overrides.get("pme_pa"),
            self.pme_nominale_pa,
        )
        return EntreesOrchestrateurMoteurThermique(
            alesage_m=_first_finite(overrides.get("alesage_m"), self.alesage_m),
            course_m=_first_finite(overrides.get("course_m"), self.course_m),
            nombre_cylindres=_safe_int(_first_non_none(overrides.get("nombre_cylindres"), self.nombre_cylindres)),
            temps_moteur=_safe_int(_first_non_none(overrides.get("temps_moteur"), self.temps_moteur)) or 4,
            regime_tr_min=regime,
            pression_moyenne_effective_pa=pme,
            pression_max_pa=_first_finite(overrides.get("pression_max_pa"), self.pression_max_pa),
            rendement_global=_first_finite(overrides.get("rendement_global"), self.rendement_mecanique_nominal, self.rendement_mecanique_cible_min),
            puissance_utile_w=_first_finite(overrides.get("puissance_utile_w"), self.puissance_nominale_visee_w),
            taux_compression=_first_finite(overrides.get("taux_compression"), self.taux_compression_nominal),
            volume_mort_m3=_first_finite(overrides.get("volume_mort_m3"), self.volume_mort_nominal_m3),
            ratio_mince_max=0.1,
            contrainte_admissible_pa=_first_finite(overrides.get("contrainte_admissible_pa"), self.contrainte_admissible_pa),
            facteur_securite_cylindre=float(_first_non_none(overrides.get("facteur_securite_cylindre"), self.facteur_securite_cylindre, 1.5)),
            carburant=_first_non_none(overrides.get("carburant"), self.carburant),
        )

    @staticmethod
    def _from_orchestrateur_report(report: Dict[str, Any]) -> Dict[str, Any]:
        synth = _safe_dict(report.get("synthese"))
        geo = _safe_dict(report.get("geometrie"))
        bore_m = _first_finite(_extract_first_number(report.get("entrees"), "alesage_m"), _extract_first_number(geo.get("cylindree_unitaire"), "B"))
        course_m = _first_finite(_extract_first_number(report.get("entrees"), "course_m"), _extract_first_number(geo.get("cylindree_unitaire"), "S"))
        cyl_tot = _first_finite(synth.get("cylindree_totale_m3"), geo.get("cylindree_totale_m3"))
        couple = _first_finite(synth.get("couple_reference_nm"))
        p_ind = _first_finite(synth.get("puissance_indiquee_w"))
        p_frein = _first_finite(synth.get("puissance_frein_estimee_w"), p_ind)
        ep = _first_finite(_extract_first_number(geo.get("epaisseur_paroi"), "t", "epaisseur_m", "epaisseur_retenue_m"))
        return {
            "conception": {
                "alesage_m": bore_m,
                "course_m": course_m,
                "nombre_cylindres": _safe_int(_extract_first_number(report.get("entrees"), "nombre_cylindres")),
                "temps_moteur": _safe_int(_extract_first_number(report.get("entrees"), "temps_moteur")),
            },
            "dimensionnement": {
                "cylindree_totale_m3": cyl_tot,
                "cylindree_totale_cc": cyl_tot * 1e6 if cyl_tot is not None else None,
                "epaisseur_cylindre_retenue_m": ep,
                "couple_max_Nm": couple,
            },
            "resultats": {
                "puissance_indiquee_W": p_ind,
                "puissance_frein_estimee_W": p_frein,
                "couple_estime_Nm": couple,
                "rendement_mecanique_estime": _first_finite(synth.get("rendement_mecanique_estime")),
            },
            "pertes": {
                "puissance_frottement_total_W": _first_finite(synth.get("puissance_frottement_total_w")),
            },
            "rapport_brut": report,
            "inconnues": _safe_dict(report.get("inconnues")),
            "alertes": _safe_dict(report.get("alertes")),
            "notes_modele": list(report.get("notes_modele", []) or []),
        }

    @classmethod
    def definir_depuis_exigences(
        cls,
        *,
        puissance_visee_w: float,
        type_puissance: str = "frein",
        rpm: float,
        pression_moyenne_effective_pa: float,
        temps_moteur: int,
        rendement_mecanique: Optional[float] = None,
        vitesse_piston_max_ms: Optional[float] = None,
        ratio_course_alesage_max: Optional[float] = None,
        ratio_course_alesage_cible: Optional[float] = None,
        L_max_m: Optional[float] = None,
        W_max_m: Optional[float] = None,
        architectures_autorisees: Optional[Tuple[str, ...]] = None,
        architecture_forcee: Optional[str] = None,
        pression_max_pa: Optional[float] = None,
        contrainte_admissible_pa: Optional[float] = None,
        facteur_securite_cylindre: Optional[float] = None,
        densite_materiau_kg_m3: Optional[float] = None,
        cout_matiere_eur_kg: Optional[float] = None,
        rendement_indique_cible_min: Optional[float] = None,
        rendement_mecanique_cible_min: Optional[float] = None,
        masse_estimee_max_kg: Optional[float] = None,
        cout_matiere_max_eur: Optional[float] = None,
        indice_maintenance_max: Optional[float] = None,
        duree_vie_cible_h: Optional[float] = None,
    ) -> Dict[str, Any]:
        report: Dict[str, Any] = {"inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        try:
            P = _safe_float(puissance_visee_w)
            n = _safe_float(rpm)
            pme = _safe_float(pression_moyenne_effective_pa)
            if P is None or P <= 0.0:
                raise ValueError("puissance_visee_w doit etre > 0.")
            if n is None or n <= 0.0:
                raise ValueError("rpm doit etre > 0.")
            if pme is None or pme <= 0.0:
                raise ValueError("pression_moyenne_effective_pa doit etre > 0.")
            tm = _safe_int(temps_moteur) or 4
            eta = _first_finite(rendement_mecanique, rendement_mecanique_cible_min, 0.85) or 0.85
            f = (n / 120.0) if tm == 4 else (n / 60.0)
            vd_tot = P / max(pme * f * eta, 1e-12)
            allowed = tuple(architectures_autorisees or ("L", "V", "W", "Etoile", "Boxer"))
            arch = architecture_forcee or allowed[0]
            n_cyl = 4 if arch in {"L", "Boxer"} else 6 if arch == "V" else 8
            if L_max_m is not None and W_max_m is not None:
                arch_mod = _import_module_any("backend.components.architechture.architecture", "backend.components.architecture")
                ArchCls = getattr(arch_mod, "Architecture", None) if arch_mod else None
                if ArchCls is not None:
                    try:
                        arch_report = ArchCls().analyser(
                            puissance_cible_w=P,
                            regime_tr_min=n,
                            pme_pa=pme,
                            vitesse_piston_max_ms=vitesse_piston_max_ms,
                            longueur_dispo_m=L_max_m,
                            largeur_dispo_m=W_max_m,
                            architectures_autorisees=list(allowed),
                            architecture_forcee=architecture_forcee,
                        )
                        best = _safe_dict(arch_report.get("meilleur"))
                        n_cyl = _safe_int(best.get("N_cyl")) or n_cyl
                        arch = str(best.get("architecture") or arch)
                        report["evaluation_conception"] = arch_report
                    except Exception as exc:
                        report["notes_modele"].append(f"Analyse architecture indisponible: {exc}")
            ratio = _first_finite(ratio_course_alesage_cible, ratio_course_alesage_max, 1.0) or 1.0
            bore = ((4.0 * (vd_tot / max(n_cyl, 1))) / (math.pi * ratio)) ** (1.0 / 3.0)
            course = ratio * bore
            moteur = cls(
                nombre_cylindres=n_cyl,
                temps_moteur=tm,
                alesage_m=bore,
                course_m=course,
                rpm_nominal=n,
                pme_nominale_pa=pme,
                rendement_mecanique_nominal=eta,
                architecture=arch,
                puissance_nominale_visee_w=P,
                type_puissance_nominale=type_puissance,
                pression_max_pa=pression_max_pa,
                contrainte_admissible_pa=contrainte_admissible_pa,
                densite_materiau_kg_m3=densite_materiau_kg_m3,
                cout_matiere_eur_kg=cout_matiere_eur_kg,
                rendement_indique_cible_min=rendement_indique_cible_min,
                rendement_mecanique_cible_min=rendement_mecanique_cible_min,
                masse_estimee_max_kg=masse_estimee_max_kg,
                cout_matiere_max_eur=cout_matiere_max_eur,
                indice_maintenance_max=indice_maintenance_max,
                duree_vie_cible_h=duree_vie_cible_h,
                vitesse_piston_max_ms=vitesse_piston_max_ms,
                ratio_course_alesage_max=ratio_course_alesage_max,
                ratio_course_alesage_cible=ratio_course_alesage_cible,
                facteur_securite_cylindre=float(facteur_securite_cylindre or 1.5),
                architectures_autorisees=allowed,
                architecture_forcee=architecture_forcee,
            )
            report["moteur_defini"] = moteur
            report["dimensionnement"] = {
                "cylindree_totale_m3": vd_tot,
                "cylindree_totale_cc": vd_tot * 1e6,
                "alesage_m": bore,
                "course_m": course,
                "nombre_cylindres": n_cyl,
                "architecture": arch,
            }
            return report
        except Exception as exc:
            _push_inconnue(report, "impossibles", "moteur_thermique_definition", str(exc))
            return report

    def analyser(self, *, strict: bool = False, **overrides: Any) -> Dict[str, Any]:
        return OrchestrateurMoteurThermique(self._to_entrees(**overrides)).analyser(strict=strict)

    def analyser_geometrie_definition(self, **kwargs: Any) -> Dict[str, Any]:
        report = self.analyser(**kwargs)
        return {
            "geometrie": _safe_dict(report.get("geometrie")),
            "cylindre_complet": _safe_dict(report.get("cylindre")),
            "rapport_brut": report,
            "inconnues": _safe_dict(report.get("inconnues")),
            "notes_modele": list(report.get("notes_modele", []) or []),
        }

    def analyser_cycle_mecanique(self, **kwargs: Any) -> Dict[str, Any]:
        report = self.analyser(**kwargs)
        return {
            "cinematique": _safe_dict(report.get("cinematique")),
            "efforts": _safe_dict(report.get("efforts")),
            "cycle_mecanique": _safe_dict(report.get("cycle_mecanique")),
            "rapport_piston": _safe_dict(report.get("assemblage")).get("rapport_piston"),
            "rapport_brut": report,
            "inconnues": _safe_dict(report.get("inconnues")),
            "notes_modele": list(report.get("notes_modele", []) or []),
        }

    def analyser_point_de_fonctionnement(self, **kwargs: Any) -> Dict[str, Any]:
        report = self.analyser(**kwargs)
        out = self._from_orchestrateur_report(report)
        out["entrees"] = _safe_dict(report.get("entrees"))
        return out

    def analyser_bilan_carburant(self, *, carburant: Optional[Any] = None, puissance_utile_w: Optional[float] = None, rendement_global: Optional[float] = None, **kwargs: Any) -> Dict[str, Any]:
        fuel = carburant if carburant is not None else self.carburant
        power = _first_finite(puissance_utile_w, self.puissance_nominale_visee_w)
        eta = _first_finite(rendement_global, self.rendement_mecanique_nominal, self.rendement_mecanique_cible_min)
        report: Dict[str, Any] = {"entrees": {}, "bilan": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        if fuel is None:
            _push_inconnue(report, "partielles", "carburant", "Carburant requis pour evaluer le bilan.")
            return report
        pci = _first_finite(getattr(fuel, "pci_j_kg", None))
        rho = _first_finite(getattr(fuel, "densite_kg_m3", None))
        report["entrees"]["carburant"] = getattr(fuel, "nom", str(fuel))
        report["entrees"]["puissance_utile_w"] = power
        report["entrees"]["rendement_global"] = eta
        if power is None or pci is None or eta is None or eta <= 0.0:
            _push_inconnue(report, "partielles", "debit_carburant", "Puissance utile, PCI et rendement global sont requis.")
            return report
        pchim = power / eta
        mdot = pchim / pci
        vdot = mdot / rho if rho is not None and rho > 0.0 else None
        report["bilan"] = {
            "puissance_chimique_w": pchim,
            "debit_massique_carburant_kg_s": mdot,
            "debit_volumique_carburant_m3_s": vdot,
        }
        return report


__all__ = [
    "ConfigurationCarburant",
    "EntreesOrchestrateurMoteurThermique",
    "OrchestrateurMoteurThermique",
    "MoteurThermique",
    "exemple_minimal",
]


if __name__ == "__main__":
    print(json.dumps(exemple_minimal(), ensure_ascii=False, indent=2))
