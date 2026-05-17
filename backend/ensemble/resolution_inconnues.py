from __future__ import annotations

"""resolution_inconnues.py — Résolveur STHO-ME renforcé.

But du module
-------------
Ce fichier remplace/renforce le résolveur d'inconnues STHO-ME.
Il transforme une demande de puissance en sortie moteur électrique
(ex. 100 kW mécaniques à l'arbre du moteur électrique) en pré-dimensionnement
système complet : bus DC, batterie tampon, alternateur, liaison mécanique,
moteur thermique, carburant, géométrie moteur et matériaux.

Règles de conception
--------------------
- Le frontend ne calcule rien : il consomme les champs et les traces produits ici.
- Le résolveur ne remplace pas les calculateurs métier : il prépare, complète,
  trace et propose des candidats.
- En mode strict, aucune valeur de profil n'est injectée. Les profils sont seulement
  exposés comme candidats.
- En mode pré-dimensionnement/projet, les profils de puissance peuvent être utilisés,
  mais chaque valeur injectée porte un statut traçable.
- Un candidat n'est jamais marqué validé par optimisation sans callback `optimiser`.
- Les formules déjà présentes dans backend/ensemble/calcul_stho_me.py sont utilisées
  quand elles sont importables ; sinon le fallback local reste strictement tracé.

Intégration recommandée
-----------------------
- backend/modules/systeme/resolution_inconnues.py
- ou backend/ensemble/resolution_inconnues.py selon ton arborescence actuelle.

Entrée minimale utile
--------------------
resoudre_inconnues_systeme({"puissance_sortie_kw": 100}, strict=False)

La sortie contient :
- payload_resolu : dictionnaire enrichi ;
- hypotheses : traces des valeurs ajoutées ;
- profils_preconfigures : tableau des profils puissance disponibles ;
- candidates : valeurs candidates CDC/profil ;
- inconnues : inconnues restantes ;
- coherence_systeme : score et points bloquants ;
- frontend_contract : contrat directement lisible côté UI.
"""

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Callable, Dict, Iterable, List, Literal, Mapping, Optional, Sequence, Tuple
import copy
import importlib
import inspect
import json
import math
from pathlib import Path
from datetime import datetime, timezone

# =============================================================================
# Statuts publics normalisés
# =============================================================================

STATUS_INPUT = "input"
STATUS_DATABASE = "database"
STATUS_COMPUTED = "computed"
STATUS_DERIVED = "derived"
STATUS_CONTRAINTE_CDC = "contrainte_cdc"
STATUS_CANDIDATE_FROM_CDC = "candidate_from_cdc"
STATUS_CANDIDATE_FROM_POWER_PROFILE = "candidate_from_power_profile"
STATUS_VALIDATED_BY_OPTIMIZATION = "validated_by_optimization"
STATUS_REJECTED_BY_OPTIMIZATION = "rejected_by_optimization"
STATUS_MISSING_REQUIRED = "missing_required"
STATUS_MISSING_OPTIONAL = "missing_optional"
STATUS_PARTIAL = "partial"
STATUS_IMPOSSIBLE = "impossible"
STATUS_ERROR = "error"

PUBLIC_STATUSES = {
    STATUS_INPUT,
    STATUS_DATABASE,
    STATUS_COMPUTED,
    STATUS_DERIVED,
    STATUS_CONTRAINTE_CDC,
    STATUS_CANDIDATE_FROM_CDC,
    STATUS_CANDIDATE_FROM_POWER_PROFILE,
    STATUS_VALIDATED_BY_OPTIMIZATION,
    STATUS_REJECTED_BY_OPTIMIZATION,
    STATUS_MISSING_REQUIRED,
    STATUS_MISSING_OPTIONAL,
    STATUS_PARTIAL,
    STATUS_IMPOSSIBLE,
    STATUS_ERROR,
}

INTERNAL_TO_PUBLIC_STATUS = {
    "calculable": STATUS_COMPUTED,
    "deduite": STATUS_DERIVED,
    "deduit": STATUS_DERIVED,
    "contrainte_cdc": STATUS_CONTRAINTE_CDC,
    "profil_puissance": STATUS_CANDIDATE_FROM_POWER_PROFILE,
    "candidate_from_power_profile": STATUS_CANDIDATE_FROM_POWER_PROFILE,
    "candidate_from_cdc": STATUS_CANDIDATE_FROM_CDC,
    "optimisee": STATUS_CANDIDATE_FROM_CDC,  # ancien terme : ne pas exposer comme validé
    "materiau": STATUS_DERIVED,
    "database": STATUS_DATABASE,
    "input": STATUS_INPUT,
    "validated_by_optimization": STATUS_VALIDATED_BY_OPTIMIZATION,
    "rejected_by_optimization": STATUS_REJECTED_BY_OPTIMIZATION,
}

ModeResolution = Literal["strict", "pre_dimensionnement", "projet"]


# =============================================================================
# Alias champs : évite les chemins legacy dispersés
# =============================================================================

ALIASES_CHAMPS: Dict[str, Tuple[str, ...]] = {
    "puissance_sortie_moteur_electrique_w": (
        "puissance_sortie_moteur_electrique_w",
        "puissance_sortie_w",
        "puissance_demandee_w",
        "puissance_moteur_electrique_sortie_w",
        "synthese.moteur_electrique.puissance_sortie_w",
        "synthese.vehicule.puissance_traction_w",
    ),
    "puissance_sortie_kw": (
        "puissance_sortie_kw",
        "puissance_demandee_kw",
        "puissance_traction_kw",
        "entrees.puissance_sortie_kw",
        "entrees.puissance_traction_kw",
    ),
    "puissance_bus_dc_w": (
        "puissance_bus_dc_w",
        "P_bus_dc_design_w",
        "bus_dc.puissance_w",
        "synthese.bus_dc.puissance_design_w",
        "liaisons.bus_dc.P_bus_dc_design_w",
    ),
    "puissance_moteur_thermique_arbre_w": (
        "puissance_moteur_thermique_arbre_w",
        "puissance_moteur_requise_W",
        "puissance_moteur_w",
        "analyses.moteur_thermique_definition.puissance_visee_w",
        "analyses.moteur_thermique_definition.puissance_requise_W",
        "moteur_thermique_definition.puissance_visee_w",
        "moteur_thermique_definition.puissance_requise_W",
    ),
    "tension_bus_dc_v": (
        "tension_bus_dc_v",
        "V_bus_dc_v",
        "bus_dc.tension_bus_dc_v",
        "synthese.bus_dc.tension_v",
        "liaisons.bus_dc.V_bus_dc_v",
    ),
    "rpm_moteur": (
        "rpm_moteur",
        "rpm_moteur_nominal",
        "vitesse_moteur_thermique_rpm",
        "regime_moteur_rpm",
        "moteur_thermique_definition.rpm_nominal",
        "moteur_thermique_definition.rpm",
        "analyses.moteur_thermique_definition.rpm_nominal",
        "analyses.moteur_thermique_definition.rpm",
        "synthese.moteur_thermique.rpm_nominal",
        "liaisons.rpm_moteur_thermique",
        "analyses.stho_me.vitesse_moteur_thermique_rpm",
    ),
    "rpm_alternateur": (
        "rpm_alternateur",
        "vitesse_alternateur_rpm",
        "rpm_alternateur_cible",
        "alternateur.rpm_nominal",
        "synthese.alternateur.rpm_nominal",
    ),
    "omega_moteur_rad_s": (
        "omega_moteur_rad_s",
        "moteur_thermique.omega_rad_s",
        "synthese.moteur_thermique.omega_rad_s",
    ),
    "couple_moteur_nm": (
        "couple_moteur_nm",
        "couple_moteur_max_Nm",
        "couple_moteur_thermique_Nm",
        "synthese.moteur_thermique.couple_requis_Nm",
        "synthese.moteur_thermique.couple_moteur_thermique_Nm",
    ),
    "couple_alternateur_nm": (
        "couple_alternateur_nm",
        "couple_alternateur_Nm",
        "synthese.alternateur.couple_mecanique_Nm",
        "alternateur.couple_mecanique_Nm",
    ),
    "pme_pa": (
        "pme_pa",
        "pression_moyenne_effective_pa",
        "moteur_thermique_definition.pme_nominale_pa",
        "moteur_thermique_definition.pression_moyenne_effective_pa",
        "analyses.moteur_thermique_definition.pme_nominale_pa",
        "analyses.moteur_thermique_definition.pression_moyenne_effective_pa",
        "synthese.moteur_thermique.pme_pa",
        "liaisons.pme.pme_pa_utilisee_ou_requise",
    ),
    "pression_max_pa": (
        "pression_max_pa",
        "moteur_thermique_definition.pression_max_pa",
        "synthese.moteur_thermique.pression_max_pa",
        "liaisons.pression_max_pa",
    ),
    "alesage_m": (
        "alesage_m",
        "moteur_thermique_definition.alesage_m",
        "synthese.moteur_thermique.alesage_m",
        "cao.moteur_thermique.alesage_m",
    ),
    "course_m": (
        "course_m",
        "moteur_thermique_definition.course_m",
        "synthese.moteur_thermique.course_m",
        "cao.moteur_thermique.course_m",
    ),
    "nombre_cylindres": (
        "nombre_cylindres",
        "moteur_thermique_definition.nombre_cylindres",
        "synthese.moteur_thermique.nombre_cylindres",
    ),
    "architecture_moteur": (
        "architecture_moteur",
        "architecture",
        "moteur_thermique_definition.architecture",
        "synthese.moteur_thermique.architecture",
    ),
    "materiau_cle": (
        "materiau_cle",
        "materiau",
        "materiau_structure_cle",
        "moteur_thermique_definition.materiau_cle",
    ),
    "carburant_cle": (
        "carburant_cle",
        "carburant",
        "moteur_thermique_definition.carburant_cle",
        "energie.carburant_cle",
    ),
    "energie_batterie_kwh": (
        "energie_batterie_kwh",
        "energie_utile_imposee_kwh",
        "batterie.energie_utile_kwh",
        "synthese.batterie.energie_utile_kwh",
    ),
    "nb_cellules_serie": (
        "nb_cellules_serie",
        "batterie.nb_cellules_serie",
        "synthese.batterie.nb_cellules_serie",
    ),
    "nb_cellules_parallele": (
        "nb_cellules_parallele",
        "batterie.nb_cellules_parallele",
        "synthese.batterie.nb_cellules_parallele",
    ),
    "rapport_vitesse_alt_sur_moteur": (
        "rapport_vitesse_alt_sur_moteur",
        "rapport_boite_alt",
        "boite_crabots.rapport_vitesse_alt_sur_moteur",
        "liaisons.rapport_vitesse_alt_sur_moteur",
    ),
    "solidworks_ready": (
        "solidworks_ready",
        "cao.solidworks_ready",
        "cao.solidworks_ready_minimal",
        "synthese.cao.solidworks_ready",
    ),
}


def get_alias_paths(field_name: str) -> Tuple[str, ...]:
    return ALIASES_CHAMPS.get(field_name, (field_name,))


# =============================================================================
# Imports optionnels vers tes autres modules
# =============================================================================


def _import_any(module_names: Sequence[str]) -> Any:
    last: Optional[BaseException] = None
    for name in module_names:
        try:
            return importlib.import_module(name)
        except BaseException as exc:  # robustesse orchestrateur
            last = exc
    return None


phys = _import_any(("backend.ensemble.calcul_stho_me", "ensemble.calcul_stho_me", "calcul_stho_me"))
mod_carburant = _import_any(("backend.ensemble.carburant", "ensemble.carburant", "carburant"))
mod_materiaux = _import_any(("backend.ensemble.materiaux", "ensemble.materiaux", "materiaux"))
mod_air = _import_any(("backend.ensemble.air", "ensemble.air", "air"))


# =============================================================================
# Données de référence explicites : profils de puissance
# =============================================================================

@dataclass(frozen=True)
class ProfilPuissance:
    """Préconfiguration par classe de puissance.

    Les valeurs ne sont pas des résultats finaux. Ce sont des hypothèses de
    pré-dimensionnement, injectables seulement hors mode strict, puis à corriger
    par recalcul + optimisation.
    """

    nom: str
    p_sortie_min_kw: float
    p_sortie_max_kw: float
    tension_bus_dc_v: float
    rendement_onduleur: float
    rendement_moteur_electrique: float
    rendement_alternateur: float
    rendement_boite: float
    rendement_liaison_meca_alt: float
    rendement_thermique_global: float
    rpm_moteur_prefere: float
    regimes_moteur_candidats_rpm: Tuple[float, ...]
    rpm_alternateur_prefere: float
    pme_pa: float
    pression_max_pa: float
    nombres_cylindres_autorises: Tuple[int, ...]
    alesage_min_m: float
    alesage_max_m: float
    course_min_m: float
    course_max_m: float
    ratio_course_alesage_min: float
    ratio_course_alesage_max: float
    materiaux_autorises: Tuple[str, ...]
    carburants_autorises: Tuple[str, ...]
    cellule_reference: str = "samsung_25r"


# Ces profils sont volontairement conservateurs et doivent être exposés comme
# candidats. Ils servent à éviter un backend bloqué dès qu'une puissance sortie
# est fournie, tout en gardant la traçabilité.
PROFILS_PUISSANCE: Tuple[ProfilPuissance, ...] = (
    ProfilPuissance(
        nom="P10_micro",
        p_sortie_min_kw=0.0,
        p_sortie_max_kw=15.0,
        tension_bus_dc_v=96.0,
        rendement_onduleur=0.94,
        rendement_moteur_electrique=0.90,
        rendement_alternateur=0.86,
        rendement_boite=0.95,
        rendement_liaison_meca_alt=0.97,
        rendement_thermique_global=0.24,
        rpm_moteur_prefere=2400.0,
        regimes_moteur_candidats_rpm=(1200.0, 1800.0, 2400.0, 3000.0),
        rpm_alternateur_prefere=3600.0,
        pme_pa=450_000.0,
        pression_max_pa=2_200_000.0,
        nombres_cylindres_autorises=(1, 2),
        alesage_min_m=0.035,
        alesage_max_m=0.090,
        course_min_m=0.035,
        course_max_m=0.100,
        ratio_course_alesage_min=0.75,
        ratio_course_alesage_max=1.35,
        materiaux_autorises=("alu_6061_t6", "alu_7075_t6", "acier_42crmo4_qt"),
        carburants_autorises=("essence", "ethanol", "methane"),
    ),
    ProfilPuissance(
        nom="P25_leger",
        p_sortie_min_kw=15.0,
        p_sortie_max_kw=35.0,
        tension_bus_dc_v=192.0,
        rendement_onduleur=0.95,
        rendement_moteur_electrique=0.91,
        rendement_alternateur=0.88,
        rendement_boite=0.95,
        rendement_liaison_meca_alt=0.97,
        rendement_thermique_global=0.25,
        rpm_moteur_prefere=2600.0,
        regimes_moteur_candidats_rpm=(1500.0, 2000.0, 2600.0, 3200.0),
        rpm_alternateur_prefere=4200.0,
        pme_pa=520_000.0,
        pression_max_pa=2_600_000.0,
        nombres_cylindres_autorises=(1, 2, 3),
        alesage_min_m=0.040,
        alesage_max_m=0.105,
        course_min_m=0.040,
        course_max_m=0.120,
        ratio_course_alesage_min=0.75,
        ratio_course_alesage_max=1.35,
        materiaux_autorises=("alu_7075_t6", "acier_42crmo4_qt", "fonte_en_gjl_250"),
        carburants_autorises=("essence", "diesel", "ethanol", "methane"),
    ),
    ProfilPuissance(
        nom="P50_vehicule_leger",
        p_sortie_min_kw=35.0,
        p_sortie_max_kw=65.0,
        tension_bus_dc_v=300.0,
        rendement_onduleur=0.96,
        rendement_moteur_electrique=0.92,
        rendement_alternateur=0.90,
        rendement_boite=0.96,
        rendement_liaison_meca_alt=0.98,
        rendement_thermique_global=0.26,
        rpm_moteur_prefere=2800.0,
        regimes_moteur_candidats_rpm=(1800.0, 2400.0, 2800.0, 3200.0, 3600.0),
        rpm_alternateur_prefere=4800.0,
        pme_pa=620_000.0,
        pression_max_pa=3_000_000.0,
        nombres_cylindres_autorises=(2, 3, 4),
        alesage_min_m=0.050,
        alesage_max_m=0.125,
        course_min_m=0.050,
        course_max_m=0.140,
        ratio_course_alesage_min=0.75,
        ratio_course_alesage_max=1.30,
        materiaux_autorises=("alu_7075_t6", "acier_42crmo4_qt", "fonte_en_gjl_250"),
        carburants_autorises=("essence", "diesel", "ethanol", "methane"),
    ),
    ProfilPuissance(
        nom="P100_cible",
        p_sortie_min_kw=65.0,
        p_sortie_max_kw=125.0,
        tension_bus_dc_v=400.0,
        rendement_onduleur=0.96,
        rendement_moteur_electrique=0.93,
        rendement_alternateur=0.91,
        rendement_boite=0.96,
        rendement_liaison_meca_alt=0.98,
        rendement_thermique_global=0.28,
        rpm_moteur_prefere=3000.0,
        regimes_moteur_candidats_rpm=(1800.0, 2400.0, 3000.0, 3600.0, 4200.0),
        rpm_alternateur_prefere=6000.0,
        pme_pa=750_000.0,
        pression_max_pa=3_600_000.0,
        nombres_cylindres_autorises=(4, 6, 8),
        alesage_min_m=0.060,
        alesage_max_m=0.150,
        course_min_m=0.055,
        course_max_m=0.170,
        ratio_course_alesage_min=0.75,
        ratio_course_alesage_max=1.25,
        materiaux_autorises=("acier_42crmo4_qt", "alu_7075_t6", "fonte_en_gjl_250"),
        carburants_autorises=("essence", "diesel", "ethanol", "methane"),
    ),
    ProfilPuissance(
        nom="P150_renforce",
        p_sortie_min_kw=125.0,
        p_sortie_max_kw=180.0,
        tension_bus_dc_v=500.0,
        rendement_onduleur=0.965,
        rendement_moteur_electrique=0.935,
        rendement_alternateur=0.92,
        rendement_boite=0.96,
        rendement_liaison_meca_alt=0.98,
        rendement_thermique_global=0.30,
        rpm_moteur_prefere=3200.0,
        regimes_moteur_candidats_rpm=(2200.0, 2800.0, 3200.0, 3800.0, 4400.0),
        rpm_alternateur_prefere=7000.0,
        pme_pa=850_000.0,
        pression_max_pa=4_200_000.0,
        nombres_cylindres_autorises=(4, 6, 8),
        alesage_min_m=0.070,
        alesage_max_m=0.170,
        course_min_m=0.060,
        course_max_m=0.190,
        ratio_course_alesage_min=0.70,
        ratio_course_alesage_max=1.25,
        materiaux_autorises=("acier_42crmo4_qt", "fonte_en_gjl_250"),
        carburants_autorises=("diesel", "essence", "methane"),
    ),
    ProfilPuissance(
        nom="P250_lourd",
        p_sortie_min_kw=180.0,
        p_sortie_max_kw=300.0,
        tension_bus_dc_v=650.0,
        rendement_onduleur=0.965,
        rendement_moteur_electrique=0.94,
        rendement_alternateur=0.925,
        rendement_boite=0.965,
        rendement_liaison_meca_alt=0.98,
        rendement_thermique_global=0.31,
        rpm_moteur_prefere=3400.0,
        regimes_moteur_candidats_rpm=(2400.0, 3000.0, 3400.0, 4000.0, 4600.0),
        rpm_alternateur_prefere=8000.0,
        pme_pa=950_000.0,
        pression_max_pa=4_800_000.0,
        nombres_cylindres_autorises=(6, 8, 10, 12),
        alesage_min_m=0.080,
        alesage_max_m=0.190,
        course_min_m=0.070,
        course_max_m=0.220,
        ratio_course_alesage_min=0.70,
        ratio_course_alesage_max=1.25,
        materiaux_autorises=("acier_42crmo4_qt", "fonte_en_gjl_250"),
        carburants_autorises=("diesel", "methane", "essence"),
    ),
)


# Cellule de référence utilisée seulement si CDC autorise explicitement la cellule.
# Les valeurs Samsung INR18650-25R : nominal 3.6 V, capacité 2.5 Ah, décharge cont. 20 A.
CELLULES_REFERENCE: Dict[str, Dict[str, Any]] = {
    "samsung_25r": {
        "cle": "samsung_25r",
        "nom": "Samsung INR18650-25R",
        "u_nominale_v": 3.6,
        "capacite_ah": 2.5,
        "courant_decharge_continu_a": 20.0,
        "courant_charge_max_a": 4.0,
        "masse_kg": 0.045,
        "source": "Samsung INR18650-25R datasheet",
    }
}


# =============================================================================
# Dataclasses publiques
# =============================================================================

@dataclass(frozen=True)
class CahierDesChargesSTHOME:
    """Contraintes globales exploitées par le résolveur.

    En strict=True/mode_resolution='strict', les profils sont listés mais pas injectés.
    En strict=False ou mode 'pre_dimensionnement'/'projet', les profils peuvent
    produire des candidats tracés.
    """

    mode_resolution: ModeResolution = "pre_dimensionnement"
    autoriser_profils_puissance: bool = True
    autoriser_cellule_reference: bool = True
    autoriser_choix_materiau: bool = True
    autoriser_pire_carburant: bool = True

    duty_cycle_moteur_thermique_max: float = 0.50
    marge_wltp: float = 0.20
    marge_puissance_bus: float = 0.08
    marge_alternateur: float = 0.10
    marge_moteur_thermique: float = 0.10
    scenario_pire_cas: str = "batterie_vide_traction_electrique_pleine_puissance"
    systeme_multi_energies: bool = True
    compatibilite_solidworks_requise: bool = True

    # Si None, le profil de puissance peut proposer une valeur hors mode strict.
    tension_bus_dc_v: Optional[float] = None
    tension_bus_dc_min_v: float = 96.0
    tension_bus_dc_max_v: float = 850.0

    # Moteur thermique / géométrie
    nombres_cylindres_autorises: Tuple[int, ...] = tuple()
    alesage_min_m: Optional[float] = None
    alesage_max_m: Optional[float] = None
    course_min_m: Optional[float] = None
    course_max_m: Optional[float] = None
    ratio_course_alesage_min: Optional[float] = None
    ratio_course_alesage_max: Optional[float] = None
    ratio_course_alesage_cible: Optional[float] = None
    vitesse_piston_max_ms: Optional[float] = 16.0
    cycle_diviseur_puissance: float = 120.0  # P = pme*Vd*rpm/120 pour 4T équivalent

    rpm_moteur_min: Optional[float] = None
    rpm_moteur_max: Optional[float] = None
    rpm_moteur_prefere: Optional[float] = None
    regimes_moteur_candidats_rpm: Tuple[float, ...] = tuple()
    rpm_alternateur_prefere: Optional[float] = None

    rapport_boite_min: float = 0.40
    rapport_boite_max: float = 6.00
    architectures_autorisees: Tuple[str, ...] = ("L", "V", "Boxer", "Etoile")

    rendement_onduleur: Optional[float] = None
    rendement_moteur_electrique: Optional[float] = None
    rendement_alternateur: Optional[float] = None
    rendement_boite: Optional[float] = None
    rendement_liaison_meca_alt: Optional[float] = None
    rendement_thermique_global: Optional[float] = None

    pme_pa: Optional[float] = None
    pression_max_pa: Optional[float] = None

    materiaux_autorises: Tuple[str, ...] = tuple()
    familles_materiaux_autorisees: Tuple[str, ...] = ("metal",)
    temperature_service_max_c: Optional[float] = None
    contrainte_service_pa: Optional[float] = None
    facteur_securite_materiau: float = 1.5

    carburants_autorises: Tuple[str, ...] = tuple()
    objectif_pire_carburant: str = "puissance"

    cellule_reference: str = "samsung_25r"
    soc_min: float = 0.10
    soc_max: float = 0.90
    derating_courant_cellule: float = 0.75
    duree_tampon_duty_cycle_s: float = 300.0
    energie_batterie_min_kwh: Optional[float] = None

    max_iterations_resolution: int = 4


@dataclass(frozen=True)
class HypotheseResolue:
    champ: str
    valeur: Any
    unite: str
    type_resolution: str
    source: str
    formule: str
    dependances: Dict[str, Any]
    justification: str
    niveau_confiance: str
    validation: Dict[str, Any] = field(default_factory=dict)
    status: str = STATUS_DERIVED
    locked: bool = False


@dataclass(frozen=True)
class DonneeCandidate:
    champ: str
    valeur: Any
    unite: str
    source: str
    statut: str
    formule: str
    dependances: Dict[str, Any]
    justification: str
    domaine: Dict[str, Any]
    score_local: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolutionInconnuesReport:
    payload_resolu: Dict[str, Any]
    hypotheses: List[HypotheseResolue] = field(default_factory=list)
    candidates: List[DonneeCandidate] = field(default_factory=list)
    candidates_rejetes: List[Dict[str, Any]] = field(default_factory=list)
    profils_preconfigures: List[Dict[str, Any]] = field(default_factory=list)
    donnees_auto_completees: Dict[str, Any] = field(default_factory=dict)
    inconnues: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    coherence_systeme: Dict[str, Any] = field(default_factory=dict)
    frontend_contract: Dict[str, Any] = field(default_factory=dict)
    iterations: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    tracabilite: Dict[str, Any] = field(default_factory=dict)

    def en_dict(self) -> Dict[str, Any]:
        return _jsonable(
            {
                "payload_resolu": self.payload_resolu,
                "hypotheses": self.hypotheses,
                "candidates": self.candidates,
                "candidates_rejetes": self.candidates_rejetes,
                "profils_preconfigures": self.profils_preconfigures,
                "donnees_auto_completees": self.donnees_auto_completees,
                "inconnues": self.inconnues,
                "coherence_systeme": self.coherence_systeme,
                "frontend_contract": self.frontend_contract,
                "iterations": self.iterations,
                "notes": self.notes,
                "tracabilite": self.tracabilite,
            }
        )


# =============================================================================
# État interne
# =============================================================================

@dataclass
class _ResolutionState:
    payload: Dict[str, Any]
    rapports: Dict[str, Any]
    cdc: CahierDesChargesSTHOME
    strict: bool
    repository: Any = None
    project_id: Optional[str] = None
    hypotheses: List[HypotheseResolue] = field(default_factory=list)
    candidates: List[DonneeCandidate] = field(default_factory=list)
    candidates_rejetes: List[Dict[str, Any]] = field(default_factory=list)
    completed: Dict[str, Any] = field(default_factory=dict)
    profils_preconfigures: List[Dict[str, Any]] = field(default_factory=list)
    inconnues: Dict[str, List[Dict[str, Any]]] = field(
        default_factory=lambda: {
            "resolues_automatiquement": [],
            "restantes_catalogue": [],
            "restantes_physiques": [],
            "bloquantes": [],
            "non_bloquantes": [],
            "conflits": [],
        }
    )
    iterations: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    conflits: List[Dict[str, Any]] = field(default_factory=list)
    tracabilite: Dict[str, Any] = field(
        default_factory=lambda: {
            "valeurs": {},
            "candidats": [],
            "candidats_rejetes": [],
            "optimisations": [],
            "sources": [],
            "repository": {},
            "cdc": {},
        }
    )

    def get(self, field_or_path: str, *extra_paths: str) -> Any:
        paths: List[str] = []
        paths.extend(get_alias_paths(field_or_path))
        for p in extra_paths:
            paths.extend(get_alias_paths(p))
        return _first_non_missing(self.payload, self.rapports, *paths)

    def number(self, field_or_path: str, *extra_paths: str) -> Optional[float]:
        value = self.get(field_or_path, *extra_paths)
        return float(value) if _is_number(value) else None

    def integer(self, field_or_path: str, *extra_paths: str) -> Optional[int]:
        value = self.number(field_or_path, *extra_paths)
        if value is None:
            return None
        rounded = int(round(value))
        return rounded if abs(value - rounded) <= 1e-9 else None

    def add(
        self,
        champ: str,
        valeur: Any,
        *,
        unite: str,
        type_resolution: str,
        source: str,
        formule: str,
        dependances: Mapping[str, Any],
        justification: str,
        niveau_confiance: str,
        validation: Optional[Mapping[str, Any]] = None,
        aliases: Sequence[str] = (),
        overwrite: bool = False,
        locked: bool = False,
    ) -> bool:
        if _is_missing_value(valeur):
            return False
        public_status = normalize_status(type_resolution)
        added = False
        for path in (champ, *aliases):
            current = _get_path(self.payload, path)
            if _is_missing_value(current) or overwrite:
                if not _is_missing_value(current) and overwrite:
                    self.notes.append(f"{path} écrasé explicitement par {source}.")
                _set_path(self.payload, path, valeur)
                self.completed[path] = valeur
                hyp = HypotheseResolue(
                    champ=path,
                    valeur=valeur,
                    unite=unite,
                    type_resolution=type_resolution,
                    source=source,
                    formule=formule,
                    dependances=dict(dependances),
                    justification=justification,
                    niveau_confiance=niveau_confiance,
                    validation=dict(validation or {}),
                    status=public_status,
                    locked=locked,
                )
                self.hypotheses.append(hyp)
                self.inconnues["resolues_automatiquement"].append(_jsonable(hyp))
                self.tracabilite["valeurs"][path] = _jsonable(hyp)
                _append_unique_source(self, source)
                added = True
            else:
                _record_conflict_if_needed(self, path, current, valeur, source)
        return added

    def add_candidate(self, candidate: DonneeCandidate) -> None:
        self.candidates.append(candidate)
        self.tracabilite["candidats"].append(_jsonable(candidate))
        _append_unique_source(self, candidate.source)

    def reject_candidate(self, candidate: DonneeCandidate, reason: str, details: Optional[Mapping[str, Any]] = None) -> None:
        item = {"candidate": _jsonable(candidate), "raison": reason, "details": _jsonable(dict(details or {}))}
        self.candidates_rejetes.append(item)
        self.tracabilite["candidats_rejetes"].append(item)

    def unresolved(self, bucket: str, champ: str, raison: str, *, bloquant: bool = False, metadata: Optional[Mapping[str, Any]] = None) -> None:
        item = {"champ": champ, "raison": raison, "metadata": _jsonable(dict(metadata or {}))}
        self.inconnues.setdefault(bucket, []).append(item)
        self.inconnues["bloquantes" if bloquant else "non_bloquantes"].append(item)


# =============================================================================
# API publique principale
# =============================================================================


def resoudre_inconnues_systeme(
    entrees: Mapping[str, Any] | None,
    rapports_existants: Mapping[str, Any] | None = None,
    cahier_des_charges: CahierDesChargesSTHOME | Mapping[str, Any] | None = None,
    *,
    repository: Any | None = None,
    project_id: str | None = None,
    recalculer: Callable[[Dict[str, Any]], Dict[str, Any]] | None = None,
    optimiser: Callable[[Dict[str, Any]], Dict[str, Any]] | None = None,
    strict: bool = True,
    max_iterations: Optional[int] = None,
) -> ResolutionInconnuesReport:
    """Résout les inconnues STHO-ME sans masquer les hypothèses.

    Si `strict=True` et `cdc.mode_resolution == 'strict'`, les profils de puissance
    sont exposés mais non injectés. Pour créer un pré-dimensionnement à partir
    d'une puissance demandée, appeler avec `strict=False` ou cdc.mode_resolution
    à `pre_dimensionnement`.
    """

    cdc = _coerce_cdc(cahier_des_charges)
    payload = _deepcopy_dict(entrees)
    rapports = _deepcopy_dict(rapports_existants)

    state = _ResolutionState(
        payload=payload,
        rapports=rapports,
        cdc=cdc,
        strict=bool(strict and cdc.mode_resolution == "strict"),
        repository=repository,
        project_id=project_id,
    )
    state.tracabilite["cdc"] = _jsonable(cdc)

    _charger_repository(state)
    _normaliser_entrees_puissance(state)
    _exposer_profils_puissance(state)

    iterations = max_iterations if max_iterations is not None else cdc.max_iterations_resolution
    iterations = max(1, int(iterations))

    for index in range(iterations):
        before = len(state.hypotheses)
        _resoudre_depuis_profil_puissance(state)
        _resoudre_puissances_systeme(state)
        _resoudre_air_si_possible(state)
        _resoudre_carburant(state)
        _resoudre_rotation_couple(state)
        _resoudre_geometrie_moteur(state)
        _resoudre_alternateur_boite(state)
        _resoudre_batterie(state)
        _resoudre_materiaux(state)
        _traiter_candidats_par_recalcul_optimisation(state, recalculer=recalculer, optimiser=optimiser)
        after = len(state.hypotheses)
        state.iterations.append(
            {
                "iteration": index + 1,
                "valeurs_ajoutees": after - before,
                "candidats": len(state.candidates),
                "candidats_rejetes": len(state.candidates_rejetes),
                "arret": "point_fixe" if after == before else "nouvelles_valeurs",
            }
        )
        # Réinjecter le payload dans le contexte rapports pour permettre les passes suivantes.
        state.rapports = _deep_merge(state.rapports, copy.deepcopy(state.payload))
        if after == before:
            break

    _classer_inconnues_restantes(state)
    coherence = verifier_coherence_resolution(state.payload, cdc, candidates=state.candidates, strict=state.strict)
    frontend_contract = build_frontend_contract_from_resolution(state, coherence)
    _dedup_state(state)

    return ResolutionInconnuesReport(
        payload_resolu=state.payload,
        hypotheses=state.hypotheses,
        candidates=state.candidates,
        candidates_rejetes=state.candidates_rejetes,
        profils_preconfigures=state.profils_preconfigures,
        donnees_auto_completees=dict(state.completed),
        inconnues=state.inconnues,
        coherence_systeme=coherence,
        frontend_contract=frontend_contract,
        iterations=state.iterations,
        notes=state.notes,
        tracabilite=state.tracabilite,
    )


# =============================================================================
# Fonctions publiques auxiliaires
# =============================================================================


def generer_table_profils_puissance(puissance_sortie_kw: Optional[float] = None) -> List[Dict[str, Any]]:
    """Renvoie le tableau complet des profils préconfigurés.

    Si `puissance_sortie_kw` est fourni, ajoute `selectionne=True` au profil
    couvrant la puissance demandée.
    """
    rows: List[Dict[str, Any]] = []
    selected = choisir_profil_puissance(puissance_sortie_kw) if puissance_sortie_kw is not None else None
    for p in PROFILS_PUISSANCE:
        row = _profile_to_public_row(p)
        row["selectionne"] = bool(selected is not None and selected.nom == p.nom)
        rows.append(row)
    return rows


def choisir_profil_puissance(puissance_sortie_kw: Optional[float]) -> Optional[ProfilPuissance]:
    if puissance_sortie_kw is None or not _is_number(puissance_sortie_kw):
        return None
    p_kw = float(puissance_sortie_kw)
    for profil in PROFILS_PUISSANCE:
        if profil.p_sortie_min_kw <= p_kw <= profil.p_sortie_max_kw:
            return profil
    if p_kw > PROFILS_PUISSANCE[-1].p_sortie_max_kw:
        return PROFILS_PUISSANCE[-1]
    if p_kw < PROFILS_PUISSANCE[0].p_sortie_min_kw:
        return PROFILS_PUISSANCE[0]
    return None


def appliquer_resolution_inconnues(
    payload: Mapping[str, Any] | None,
    resolutions: ResolutionInconnuesReport | Sequence[HypotheseResolue] | Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    out = _deepcopy_dict(payload)
    hypotheses: Iterable[Any]
    hypotheses = resolutions.hypotheses if isinstance(resolutions, ResolutionInconnuesReport) else resolutions
    for item in hypotheses:
        if isinstance(item, HypotheseResolue):
            champ, valeur = item.champ, item.valeur
        elif isinstance(item, Mapping):
            champ, valeur = str(item.get("champ", "")), item.get("valeur")
        else:
            continue
        if champ:
            _set_path(out, champ, valeur)
    return out


def tracer_resolution_inconnues(
    resolutions: ResolutionInconnuesReport | Sequence[HypotheseResolue] | Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    hypotheses = resolutions.hypotheses if isinstance(resolutions, ResolutionInconnuesReport) else list(resolutions)
    return [_jsonable(h) for h in hypotheses]


def verifier_coherence_resolution(
    payload_resolu: Mapping[str, Any] | None,
    cahier_des_charges: CahierDesChargesSTHOME | Mapping[str, Any] | None = None,
    *,
    candidates: Optional[Sequence[DonneeCandidate]] = None,
    strict: bool = True,
) -> Dict[str, Any]:
    cdc = _coerce_cdc(cahier_des_charges)
    payload = _deepcopy_dict(payload_resolu)
    blockers: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    scores = {
        "puissance": _score_puissance(payload, cdc, blockers, actions),
        "energie": _score_energie(payload, actions),
        "mecanique": _score_mecanique(payload, blockers, actions),
        "thermique": _score_thermique(payload, actions),
        "geometrie": _score_geometrie(payload, blockers, actions),
        "materiaux": _score_materiaux(payload, cdc, actions),
        "carburant": _score_carburant(payload, cdc, actions),
        "cao": _score_cao(payload, cdc, actions),
        "cdc": _score_cdc(payload, cdc, blockers, actions),
    }
    score_global = sum(scores.values()) / max(1, len(scores))
    if blockers:
        statut = "invalide"
    elif score_global >= 0.88:
        statut = "exploitable"
    elif score_global >= 0.68:
        statut = "partiel"
    else:
        statut = "incomplet"
    return {
        "score_global": round(_clamp01(score_global), 4),
        "score_global_100": round(100.0 * _clamp01(score_global), 2),
        "statut": statut,
        "strict": strict,
        "scores": {k: round(_clamp01(v), 4) for k, v in scores.items()},
        "points_bloquants": _dedup_items(blockers),
        "actions_recommandees": _dedup_items(actions),
        "nb_candidates": len(candidates or []),
    }


# =============================================================================
# Résolution repository / profil / puissance
# =============================================================================


def _charger_repository(state: _ResolutionState) -> None:
    repo = state.repository
    project_id = state.project_id
    if repo is None or not project_id:
        if repo is not None and not project_id:
            state.unresolved("restantes_catalogue", "project_id", "project_id requis pour interroger le repository.", bloquant=False)
        return
    getter = getattr(repo, "get_project_parameters", None)
    if not callable(getter):
        state.unresolved("restantes_catalogue", "repository", "repository sans méthode get_project_parameters(project_id).", bloquant=False)
        return
    try:
        params = getter(project_id)
    except Exception as exc:
        state.unresolved("restantes_catalogue", "repository", f"Lecture repository impossible : {exc}", bloquant=False)
        return
    if not isinstance(params, Mapping):
        return
    state.tracabilite["repository"] = {"project_id": project_id, "nb_parametres": len(params)}
    for path, value in params.items():
        # Accepte soit {path: value}, soit {path: {value, unit, locked, ...}}
        unit = ""
        locked = False
        actual = value
        if isinstance(value, Mapping) and "value" in value:
            actual = value.get("value")
            unit = str(value.get("unit") or "")
            locked = bool(value.get("locked", False))
        state.add(
            str(path),
            actual,
            unite=unit,
            type_resolution=STATUS_DATABASE,
            source="SystemDataRepository",
            formule="lecture repository",
            dependances={"project_id": project_id, "path": str(path)},
            justification="Valeur connue chargée depuis la base/projet.",
            niveau_confiance="projet",
            validation={"locked": locked},
            locked=locked,
        )


def _normaliser_entrees_puissance(state: _ResolutionState) -> None:
    p_w = state.number("puissance_sortie_moteur_electrique_w")
    p_kw = state.number("puissance_sortie_kw")
    if p_w is None and p_kw is not None:
        state.add(
            "puissance_sortie_moteur_electrique_w",
            p_kw * 1000.0,
            unite="W",
            type_resolution=STATUS_COMPUTED,
            source="resolution_inconnues.normalisation_puissance",
            formule="puissance_sortie_kw * 1000",
            dependances={"puissance_sortie_kw": p_kw},
            justification="Conversion exacte de la puissance sortie moteur électrique demandée.",
            niveau_confiance="exact",
            aliases=("puissance_traction_w", "synthese.moteur_electrique.puissance_sortie_w"),
        )
    elif p_w is not None:
        state.add(
            "synthese.moteur_electrique.puissance_sortie_w",
            p_w,
            unite="W",
            type_resolution=STATUS_INPUT,
            source="entree_utilisateur",
            formule="propagation puissance sortie moteur électrique",
            dependances={"puissance_sortie_moteur_electrique_w": p_w},
            justification="Puissance de sortie mécanique demandée au moteur électrique.",
            niveau_confiance="input",
        )


def _exposer_profils_puissance(state: _ResolutionState) -> None:
    p_w = state.number("puissance_sortie_moteur_electrique_w")
    p_kw = p_w / 1000.0 if p_w is not None else state.number("puissance_sortie_kw")
    state.profils_preconfigures = generer_table_profils_puissance(p_kw)


def _resoudre_depuis_profil_puissance(state: _ResolutionState) -> None:
    p_w = state.number("puissance_sortie_moteur_electrique_w")
    if p_w is None or p_w <= 0.0:
        state.unresolved(
            "restantes_physiques",
            "puissance_sortie_moteur_electrique_w",
            "Puissance de sortie moteur électrique requise pour dimensionner le système complet.",
            bloquant=True,
        )
        return
    p_kw = p_w / 1000.0
    profil = choisir_profil_puissance(p_kw)
    if profil is None:
        return
    if not state.cdc.autoriser_profils_puissance:
        state.add_candidate(_candidate_from_profile("profil_puissance", profil.nom, "", "profil puissance disponible mais non autorisé par CDC", {}, {}))
        return

    # Hors mode strict : les profils peuvent alimenter les champs manquants, mais jamais comme résultat final.
    inject_allowed = not state.strict
    state.notes.append(f"Profil puissance sélectionné pour {p_kw:.3g} kW sortie : {profil.nom}.")

    candidate_fields: List[Tuple[str, Any, str, str, Dict[str, Any], Sequence[str]]] = [
        ("tension_bus_dc_v", state.cdc.tension_bus_dc_v or profil.tension_bus_dc_v, "V", "tension bus proposée par profil puissance", {"profil": profil.nom}, ("V_bus_dc_v",)),
        ("rendement_onduleur", state.cdc.rendement_onduleur or profil.rendement_onduleur, "", "rendement onduleur profil", {"profil": profil.nom}, ()),
        ("rendement_moteur_electrique", state.cdc.rendement_moteur_electrique or profil.rendement_moteur_electrique, "", "rendement moteur électrique profil", {"profil": profil.nom}, ()),
        ("rendement_alternateur", state.cdc.rendement_alternateur or profil.rendement_alternateur, "", "rendement alternateur profil", {"profil": profil.nom}, ()),
        ("rendement_boite", state.cdc.rendement_boite or profil.rendement_boite, "", "rendement boîte profil", {"profil": profil.nom}, ()),
        ("rendement_liaison_meca_alt", state.cdc.rendement_liaison_meca_alt or profil.rendement_liaison_meca_alt, "", "rendement liaison mécanique profil", {"profil": profil.nom}, ()),
        ("rendement_thermique_global", state.cdc.rendement_thermique_global or profil.rendement_thermique_global, "", "rendement thermique global profil", {"profil": profil.nom}, ()),
        ("rpm_moteur_nominal", state.cdc.rpm_moteur_prefere or profil.rpm_moteur_prefere, "rpm", "régime moteur candidat profil", {"profil": profil.nom}, ("rpm_moteur", "vitesse_moteur_thermique_rpm")),
        ("vitesse_alternateur_rpm", state.cdc.rpm_alternateur_prefere or profil.rpm_alternateur_prefere, "rpm", "régime alternateur candidat profil", {"profil": profil.nom}, ("rpm_alternateur",)),
        ("pme_pa", state.cdc.pme_pa or profil.pme_pa, "Pa", "PME candidate profil", {"profil": profil.nom}, ("pression_moyenne_effective_pa", "moteur_thermique_definition.pme_nominale_pa")),
        ("pression_max_pa", state.cdc.pression_max_pa or profil.pression_max_pa, "Pa", "pression max candidate profil", {"profil": profil.nom}, ("moteur_thermique_definition.pression_max_pa",)),
    ]
    for champ, valeur, unite, justification, deps, aliases in candidate_fields:
        cand = DonneeCandidate(
            champ=champ,
            valeur=valeur,
            unite=unite,
            source=f"PROFILS_PUISSANCE.{profil.nom}",
            statut=STATUS_CANDIDATE_FROM_POWER_PROFILE,
            formule="sélection par plage de puissance demandée",
            dependances={"puissance_sortie_kw": p_kw, **deps},
            justification=justification,
            domaine={"p_sortie_min_kw": profil.p_sortie_min_kw, "p_sortie_max_kw": profil.p_sortie_max_kw},
            score_local=1.0,
        )
        state.add_candidate(cand)
        if inject_allowed:
            state.add(
                champ,
                valeur,
                unite=unite,
                type_resolution=STATUS_CANDIDATE_FROM_POWER_PROFILE,
                source=cand.source,
                formule=cand.formule,
                dependances=cand.dependances,
                justification=cand.justification,
                niveau_confiance="candidat",
                validation={"profil": profil.nom, "doit_etre_valide_par_optimisation": True},
                aliases=aliases,
            )

    # Répercuter les domaines CDC/profil dans le payload, mais uniquement comme contraintes traçables.
    domain_payload = {
        "nombres_cylindres_autorises": state.cdc.nombres_cylindres_autorises or profil.nombres_cylindres_autorises,
        "regimes_moteur_candidats_rpm": state.cdc.regimes_moteur_candidats_rpm or profil.regimes_moteur_candidats_rpm,
        "alesage_min_m": state.cdc.alesage_min_m or profil.alesage_min_m,
        "alesage_max_m": state.cdc.alesage_max_m or profil.alesage_max_m,
        "course_min_m": state.cdc.course_min_m or profil.course_min_m,
        "course_max_m": state.cdc.course_max_m or profil.course_max_m,
        "ratio_course_alesage_min": state.cdc.ratio_course_alesage_min or profil.ratio_course_alesage_min,
        "ratio_course_alesage_max": state.cdc.ratio_course_alesage_max or profil.ratio_course_alesage_max,
        "materiaux_autorises": state.cdc.materiaux_autorises or profil.materiaux_autorises,
        "carburants_autorises": state.cdc.carburants_autorises or profil.carburants_autorises,
        "cellule_reference": state.cdc.cellule_reference or profil.cellule_reference,
    }
    _set_path(state.payload, "contraintes_resolution", domain_payload)


# =============================================================================
# Résolution physique système
# =============================================================================


def _resoudre_puissances_systeme(state: _ResolutionState) -> None:
    p_out = state.number("puissance_sortie_moteur_electrique_w")
    if p_out is None:
        return
    eta_inv = state.number("rendement_onduleur")
    eta_motor = state.number("rendement_moteur_electrique")
    eta_alt = state.number("rendement_alternateur")
    eta_boite = state.number("rendement_boite")
    eta_link = state.number("rendement_liaison_meca_alt")
    eta_th = state.number("rendement_thermique_global")

    if eta_inv is not None and eta_motor is not None and eta_inv > 0 and eta_motor > 0:
        p_bus_nom = p_out / (eta_inv * eta_motor)
        p_bus_design = p_bus_nom * (1.0 + state.cdc.marge_puissance_bus)
        state.add(
            "puissance_moteur_electrique_entree_dc_w",
            p_bus_nom,
            unite="W",
            type_resolution=STATUS_COMPUTED,
            source="resolution_inconnues.chaine_puissance",
            formule="P_bus_nom = P_sortie_moteur_elec / (eta_onduleur * eta_moteur_elec)",
            dependances={"P_sortie_w": p_out, "eta_onduleur": eta_inv, "eta_moteur_electrique": eta_motor},
            justification="La puissance sortie est une puissance mécanique moteur électrique ; le bus doit fournir davantage selon les rendements.",
            niveau_confiance="calcul",
        )
        state.add(
            "puissance_bus_dc_w",
            p_bus_design,
            unite="W",
            type_resolution=STATUS_COMPUTED,
            source="resolution_inconnues.chaine_puissance",
            formule="P_bus_design = P_bus_nom * (1 + marge_puissance_bus)",
            dependances={"P_bus_nom_w": p_bus_nom, "marge_puissance_bus": state.cdc.marge_puissance_bus},
            justification="Puissance design bus DC incluant marge explicite du cahier des charges.",
            niveau_confiance="calcul",
            aliases=("P_bus_dc_design_w", "synthese.bus_dc.puissance_design_w"),
        )

        duty = state.cdc.duty_cycle_moteur_thermique_max
        if duty <= 0 or duty > 1:
            state.unresolved("conflits", "duty_cycle_moteur_thermique_max", "Duty-cycle moteur thermique invalide.", bloquant=True)
        else:
            p_alt_elec_cont = p_bus_design
            p_alt_elec_duty = p_bus_design / duty
            p_alt_elec_design = max(p_alt_elec_cont, p_alt_elec_duty) * (1.0 + state.cdc.marge_alternateur)
            state.add(
                "puissance_alternateur_electrique_w",
                p_alt_elec_design,
                unite="W",
                type_resolution=STATUS_COMPUTED,
                source="resolution_inconnues.pire_cas_duty_cycle",
                formule="P_alt_elec = max(P_bus, P_bus/duty_max) * (1 + marge_alternateur)",
                dependances={"P_bus_design_w": p_bus_design, "duty_max": duty, "marge_alternateur": state.cdc.marge_alternateur},
                justification="Dimensionnement pour batterie vide + traction pleine puissance avec moteur thermique limité à 50% de fonctionnement.",
                niveau_confiance="calcul_cdc",
                aliases=("production_electrique_sortie_w", "synthese.alternateur.puissance_electrique_design_w"),
            )

            cycle_h = state.cdc.duree_tampon_duty_cycle_s / 3600.0
            soc_window = max(1e-9, state.cdc.soc_max - state.cdc.soc_min)
            e_buffer = p_bus_design * (1.0 - duty) * cycle_h / 1000.0 / soc_window
            if state.cdc.energie_batterie_min_kwh is not None:
                e_buffer = max(e_buffer, state.cdc.energie_batterie_min_kwh)
            state.add(
                "energie_batterie_tampon_min_kwh",
                e_buffer,
                unite="kWh",
                type_resolution=STATUS_COMPUTED,
                source="resolution_inconnues.buffer_duty_cycle",
                formule="E_buffer = P_bus*(1-duty)*duree_cycle_h/(SOCmax-SOCmin)",
                dependances={"P_bus_design_w": p_bus_design, "duty": duty, "duree_s": state.cdc.duree_tampon_duty_cycle_s, "soc_min": state.cdc.soc_min, "soc_max": state.cdc.soc_max},
                justification="Batterie tampon minimale pour couvrir les phases moteur thermique arrêté du cycle de duty.",
                niveau_confiance="calcul_cdc",
            )

    p_alt_elec = state.number("puissance_alternateur_electrique_w")
    if p_alt_elec is not None and eta_alt is not None and eta_alt > 0:
        p_alt_mech = p_alt_elec / eta_alt
        state.add(
            "puissance_alternateur_mecanique_w",
            p_alt_mech,
            unite="W",
            type_resolution=STATUS_COMPUTED,
            source="resolution_inconnues.alternateur",
            formule="P_alt_meca = P_alt_elec / rendement_alternateur",
            dependances={"P_alt_elec_w": p_alt_elec, "eta_alt": eta_alt},
            justification="Puissance mécanique requise à l'alternateur.",
            niveau_confiance="calcul",
            aliases=("synthese.alternateur.P_mecanique_W",),
        )

        if eta_boite is not None and eta_link is not None and eta_boite > 0 and eta_link > 0:
            p_thermique_arbre = p_alt_mech / (eta_boite * eta_link) * (1.0 + state.cdc.marge_moteur_thermique)
            state.add(
                "puissance_moteur_thermique_arbre_w",
                p_thermique_arbre,
                unite="W",
                type_resolution=STATUS_COMPUTED,
                source="resolution_inconnues.chaine_mecanique",
                formule="P_mt_arbre = P_alt_meca/(eta_boite*eta_liaison)*(1+marge_mt)",
                dependances={"P_alt_meca_w": p_alt_mech, "eta_boite": eta_boite, "eta_liaison": eta_link, "marge_mt": state.cdc.marge_moteur_thermique},
                justification="Le moteur thermique doit alimenter mécaniquement l'alternateur à travers les pertes mécaniques.",
                niveau_confiance="calcul",
                aliases=("puissance_moteur_w", "puissance_moteur_requise_W", "synthese.moteur_thermique.puissance_requise_W"),
            )

            if eta_th is not None and eta_th > 0:
                p_chimique = p_thermique_arbre / eta_th
                state.add(
                    "puissance_chimique_carburant_w",
                    p_chimique,
                    unite="W",
                    type_resolution=STATUS_COMPUTED,
                    source="resolution_inconnues.bilan_energetique",
                    formule="P_chimique = P_mt_arbre / rendement_thermique_global",
                    dependances={"P_mt_arbre_w": p_thermique_arbre, "eta_thermique_global": eta_th},
                    justification="Puissance chimique carburant estimée à partir du rendement thermique global fourni/profilé.",
                    niveau_confiance="calcul_cdc",
                )

    tension = state.number("tension_bus_dc_v")
    p_bus = state.number("puissance_bus_dc_w")
    if tension is not None and p_bus is not None and tension > 0:
        current = _phys_courant_pack(p_bus, tension)
        state.add(
            "courant_bus_dc_a",
            current,
            unite="A",
            type_resolution=STATUS_COMPUTED,
            source="calcul_stho_me.courant_pack",
            formule="I = P / U",
            dependances={"P_bus_dc_w": p_bus, "U_bus_v": tension},
            justification="Courant design bus DC.",
            niveau_confiance="exact",
        )


def _resoudre_air_si_possible(state: _ResolutionState) -> None:
    altitude = state.number("altitude_m", "air.altitude_m")
    temp_k = state.number("temperature_air_k", "air.temperature_k")
    pression = state.number("pression_air_pa", "air.pression_pa")
    if altitude is None and (temp_k is None or pression is None):
        return
    if mod_air is None:
        state.unresolved("restantes_physiques", "air", "Module air.py non importable.", bloquant=False)
        return
    try:
        if altitude is not None and (temp_k is None or pression is None):
            fn = getattr(mod_air, "isa_dry_temperature_pressure", None)
            if callable(fn):
                temp_k, pression = fn(float(altitude))
                state.add(
                    "air.temperature_isa_k",
                    temp_k,
                    unite="K",
                    type_resolution=STATUS_COMPUTED,
                    source="air.isa_dry_temperature_pressure",
                    formule="atmosphère ISA depuis altitude",
                    dependances={"altitude_m": altitude},
                    justification="Température ISA calculée depuis le module air.py.",
                    niveau_confiance="modele",
                )
                state.add(
                    "air.pression_isa_pa",
                    pression,
                    unite="Pa",
                    type_resolution=STATUS_COMPUTED,
                    source="air.isa_dry_temperature_pressure",
                    formule="atmosphère ISA depuis altitude",
                    dependances={"altitude_m": altitude},
                    justification="Pression ISA calculée depuis le module air.py.",
                    niveau_confiance="modele",
                )
        if temp_k is not None and pression is not None:
            fn_rho = getattr(mod_air, "isa_density", None)
            if callable(fn_rho):
                rho = fn_rho(float(pression), float(temp_k))
                state.add(
                    "air.densite_kg_m3",
                    rho,
                    unite="kg/m3",
                    type_resolution=STATUS_COMPUTED,
                    source="air.isa_density",
                    formule="rho = p/(R*T)",
                    dependances={"pression_air_pa": pression, "temperature_air_k": temp_k},
                    justification="Densité air utile aux comparaisons combustion/refroidissement.",
                    niveau_confiance="modele",
                )
    except Exception as exc:
        state.unresolved("restantes_physiques", "air", f"Analyse air impossible : {exc}", bloquant=False)


def _resoudre_carburant(state: _ResolutionState) -> None:
    carburant_cle = state.get("carburant_cle")
    autorises = _ensure_tuple(state.get("contraintes_resolution.carburants_autorises")) or state.cdc.carburants_autorises
    carburant_obj = None
    source = "input"
    if mod_carburant is None:
        state.unresolved("restantes_catalogue", "carburant", "Module carburant.py non importable.", bloquant=False)
        return
    try:
        if not _is_missing_value(carburant_cle):
            carburant_obj = mod_carburant.get_carburant(str(carburant_cle))
            source = "carburant_cle"
        elif autorises and state.cdc.autoriser_pire_carburant and callable(getattr(mod_carburant, "get_pire_carburant", None)):
            carburant_obj = mod_carburant.get_pire_carburant(autorises, objectif=state.cdc.objectif_pire_carburant)
            source = "get_pire_carburant"
            # Hors strict seulement : on injecte la clé retenue, sinon candidate seulement.
            cand = DonneeCandidate(
                champ="carburant_cle",
                valeur=getattr(carburant_obj, "cle", None),
                unite="",
                source="carburant.get_pire_carburant",
                statut=STATUS_CANDIDATE_FROM_CDC,
                formule=f"minimise objectif {state.cdc.objectif_pire_carburant} parmi carburants autorisés",
                dependances={"carburants_autorises": list(autorises), "objectif": state.cdc.objectif_pire_carburant},
                justification="Carburant pénalisant retenu comme candidat de pire cas multi-carburant.",
                domaine={"carburants_autorises": list(autorises)},
                score_local=None,
            )
            state.add_candidate(cand)
            if not state.strict:
                state.add(
                    "carburant_cle",
                    getattr(carburant_obj, "cle", None),
                    unite="",
                    type_resolution=STATUS_CANDIDATE_FROM_CDC,
                    source="carburant.get_pire_carburant",
                    formule=cand.formule,
                    dependances=cand.dependances,
                    justification=cand.justification,
                    niveau_confiance="candidat",
                )
        else:
            state.unresolved("restantes_catalogue", "carburant_cle", "Carburant absent et aucun pire cas autorisé/configuré.", bloquant=False)
            return
    except Exception as exc:
        state.unresolved("restantes_catalogue", "carburant_cle", f"Carburant impossible : {exc}", bloquant=True)
        return

    if carburant_obj is None:
        return
    pci = getattr(carburant_obj, "pci_j_kg", None)
    if pci is None and _is_number(getattr(carburant_obj, "pci_mj_kg", None)):
        pci = float(getattr(carburant_obj, "pci_mj_kg")) * 1e6
    state.add(
        "carburant.pci_j_kg",
        pci,
        unite="J/kg",
        type_resolution=STATUS_DERIVED,
        source=f"carburant.{source}",
        formule="propriété catalogue carburant",
        dependances={"carburant_cle": getattr(carburant_obj, "cle", None)},
        justification="PCI carburant extrait du module carburant.py.",
        niveau_confiance="catalogue",
    )
    afr = getattr(carburant_obj, "afr_stoechiometrique", None)
    if _is_number(afr):
        state.add(
            "carburant.afr_stoechiometrique",
            float(afr),
            unite="kg_air/kg_carburant",
            type_resolution=STATUS_DERIVED,
            source=f"carburant.{source}",
            formule="propriété catalogue carburant",
            dependances={"carburant_cle": getattr(carburant_obj, "cle", None)},
            justification="AFR stœchiométrique extrait du module carburant.py.",
            niveau_confiance="catalogue",
        )
    p_chim = state.number("puissance_chimique_carburant_w")
    if p_chim is not None and _is_number(pci) and float(pci) > 0:
        mdot = p_chim / float(pci)
        state.add(
            "debit_massique_carburant_kg_s",
            mdot,
            unite="kg/s",
            type_resolution=STATUS_COMPUTED,
            source="resolution_inconnues.carburant",
            formule="mdot_f = P_chimique / PCI",
            dependances={"P_chimique_w": p_chim, "PCI_j_kg": pci},
            justification="Débit carburant requis pour fournir la puissance chimique calculée.",
            niveau_confiance="calcul",
        )


def _resoudre_rotation_couple(state: _ResolutionState) -> None:
    rpm = state.number("rpm_moteur")
    p_mt = state.number("puissance_moteur_thermique_arbre_w", "puissance_moteur_w", "puissance_moteur_requise_W")
    if rpm is not None and rpm > 0:
        omega = _phys_pulsation(rpm)
        state.add(
            "omega_moteur_rad_s",
            omega,
            unite="rad/s",
            type_resolution=STATUS_COMPUTED,
            source="calcul_stho_me.pulsation",
            formule="omega = 2*pi*rpm/60",
            dependances={"rpm_moteur": rpm},
            justification="Conversion cinématique exacte.",
            niveau_confiance="exact",
        )
    omega = state.number("omega_moteur_rad_s")
    if p_mt is not None and omega is not None and omega > 0:
        couple = _phys_couple_moteur(p_mt, omega)
        state.add(
            "couple_moteur_nm",
            couple,
            unite="N.m",
            type_resolution=STATUS_COMPUTED,
            source="calcul_stho_me.couple_moteur",
            formule="T = P / omega",
            dependances={"P_mt_arbre_w": p_mt, "omega_rad_s": omega},
            justification="Couple moteur thermique requis à l'arbre.",
            niveau_confiance="exact",
            aliases=("couple_moteur_max_Nm", "synthese.moteur_thermique.couple_requis_Nm"),
        )

    rpm_alt = state.number("rpm_alternateur")
    p_alt_meca = state.number("puissance_alternateur_mecanique_w")
    if rpm_alt is not None and rpm_alt > 0 and p_alt_meca is not None:
        omega_alt = _phys_pulsation(rpm_alt)
        t_alt = p_alt_meca / omega_alt
        state.add(
            "couple_alternateur_nm",
            t_alt,
            unite="N.m",
            type_resolution=STATUS_COMPUTED,
            source="resolution_inconnues.alternateur",
            formule="T_alt = P_alt_meca / omega_alt",
            dependances={"P_alt_meca_w": p_alt_meca, "rpm_alt": rpm_alt},
            justification="Couple mécanique requis par l'alternateur.",
            niveau_confiance="exact",
            aliases=("synthese.alternateur.couple_mecanique_Nm",),
        )


def _resoudre_geometrie_moteur(state: _ResolutionState) -> None:
    p_mt = state.number("puissance_moteur_thermique_arbre_w", "puissance_moteur_w", "puissance_moteur_requise_W")
    rpm = state.number("rpm_moteur")
    pme = state.number("pme_pa")
    bore = state.number("alesage_m")
    stroke = state.number("course_m")
    nb_cyl = state.integer("nombre_cylindres")

    domain = _geometry_domain_from_state(state)
    if (bore is None or stroke is None or nb_cyl is None) and p_mt and rpm and pme:
        candidates = _generer_candidates_geometrie(
            puissance_w=float(p_mt),
            rpm=float(rpm),
            pme_pa=float(pme),
            bore_known=bore,
            stroke_known=stroke,
            nb_cyl_known=nb_cyl,
            cdc=state.cdc,
            domain=domain,
        )
        for cand in candidates:
            state.add_candidate(cand)
        if candidates and not state.strict:
            best = min(candidates, key=lambda c: float(c.score_local if c.score_local is not None else 1e9))
            geom = best.metadata
            if nb_cyl is None:
                state.add(
                    "nombre_cylindres",
                    geom["nombre_cylindres"],
                    unite="",
                    type_resolution=STATUS_CANDIDATE_FROM_CDC,
                    source=best.source,
                    formule=best.formule,
                    dependances=best.dependances,
                    justification="Nombre de cylindres candidat issu du meilleur candidat géométrique.",
                    niveau_confiance="candidat",
                    validation={"doit_etre_valide_par_optimisation": True, "score_local": best.score_local, "domaine": best.domaine},
                    aliases=("moteur_thermique_definition.nombre_cylindres",),
                )
            if bore is None:
                state.add(
                    "alesage_m",
                    geom["alesage_m"],
                    unite="m",
                    type_resolution=STATUS_CANDIDATE_FROM_CDC,
                    source=best.source,
                    formule=best.formule,
                    dependances=best.dependances,
                    justification="Alésage candidat issu du meilleur candidat géométrique.",
                    niveau_confiance="candidat",
                    validation={"doit_etre_valide_par_optimisation": True, "score_local": best.score_local, "domaine": best.domaine},
                    aliases=("moteur_thermique_definition.alesage_m",),
                )
            if stroke is None:
                state.add(
                    "course_m",
                    geom["course_m"],
                    unite="m",
                    type_resolution=STATUS_CANDIDATE_FROM_CDC,
                    source=best.source,
                    formule=best.formule,
                    dependances=best.dependances,
                    justification="Course candidate issue du meilleur candidat géométrique.",
                    niveau_confiance="candidat",
                    validation={"doit_etre_valide_par_optimisation": True, "score_local": best.score_local, "domaine": best.domaine},
                    aliases=("moteur_thermique_definition.course_m",),
                )

    bore = state.number("alesage_m")
    stroke = state.number("course_m")
    nb_cyl = state.integer("nombre_cylindres")
    rpm = state.number("rpm_moteur")
    pmax = state.number("pression_max_pa")
    if bore is not None:
        surface = _phys_surface_piston(bore)
        state.add(
            "surface_piston_m2",
            surface,
            unite="m2",
            type_resolution=STATUS_COMPUTED,
            source="calcul_stho_me.surface_piston",
            formule="A = pi*B^2/4",
            dependances={"alesage_m": bore},
            justification="Surface piston calculée depuis l'alésage.",
            niveau_confiance="exact",
        )
        if pmax is not None:
            state.add(
                "force_gaz_n",
                _phys_force_pression(pmax, surface),
                unite="N",
                type_resolution=STATUS_COMPUTED,
                source="calcul_stho_me.force_pression",
                formule="F = pmax * surface_piston",
                dependances={"pression_max_pa": pmax, "surface_piston_m2": surface},
                justification="Effort gaz maximal sur piston.",
                niveau_confiance="exact",
                aliases=("force_bielle_N",),
            )
    if bore is not None and stroke is not None:
        vb = _phys_volume_balayage(bore, stroke)
        state.add(
            "cylindree_unitaire_m3",
            vb,
            unite="m3",
            type_resolution=STATUS_COMPUTED,
            source="calcul_stho_me.volume_balayage",
            formule="Vb = surface_piston * course",
            dependances={"alesage_m": bore, "course_m": stroke},
            justification="Cylindrée unitaire calculée depuis alésage/course.",
            niveau_confiance="exact",
        )
        if nb_cyl is not None:
            vd = vb * nb_cyl
            state.add(
                "cylindree_totale_m3",
                vd,
                unite="m3",
                type_resolution=STATUS_COMPUTED,
                source="calcul_stho_me.volume_balayage",
                formule="Vd_total = Vb * nombre_cylindres",
                dependances={"Vb_m3": vb, "nombre_cylindres": nb_cyl},
                justification="Cylindrée totale calculée depuis la géométrie candidate/connue.",
                niveau_confiance="exact",
                aliases=("synthese.moteur_thermique.cylindree_totale_m3",),
            )
            state.add(
                "cylindree_totale_cc",
                vd * 1_000_000.0,
                unite="cm3",
                type_resolution=STATUS_COMPUTED,
                source="resolution_inconnues.conversion",
                formule="cylindree_totale_m3 * 1e6",
                dependances={"cylindree_totale_m3": vd},
                justification="Conversion m3 vers cm3.",
                niveau_confiance="exact",
            )
    if stroke is not None and rpm is not None:
        state.add(
            "vitesse_piston_m_s",
            _phys_vitesse_piston(stroke, rpm),
            unite="m/s",
            type_resolution=STATUS_COMPUTED,
            source="calcul_stho_me.vitesse_piston",
            formule="Up = 2*S*rpm/60",
            dependances={"course_m": stroke, "rpm_moteur": rpm},
            justification="Vitesse moyenne piston.",
            niveau_confiance="exact",
        )
        state.add(
            "rayon_manivelle_m",
            stroke / 2.0,
            unite="m",
            type_resolution=STATUS_COMPUTED,
            source="resolution_inconnues.geometrie",
            formule="rayon_manivelle = course/2",
            dependances={"course_m": stroke},
            justification="Rayon manivelle déduit de la course.",
            niveau_confiance="exact",
        )

    arch = state.get("architecture_moteur")
    if _is_missing_value(arch) and nb_cyl is not None:
        chosen = _choisir_architecture(nb_cyl, state.cdc.architectures_autorisees)
        if chosen is not None and not state.strict:
            state.add(
                "architecture_moteur",
                chosen,
                unite="",
                type_resolution=STATUS_CANDIDATE_FROM_CDC,
                source="resolution_inconnues.architecture",
                formule="choix compatible avec nombre_cylindres et architectures_autorisees",
                dependances={"nombre_cylindres": nb_cyl, "architectures_autorisees": state.cdc.architectures_autorisees},
                justification="Architecture moteur candidate compatible avec le nombre de cylindres.",
                niveau_confiance="candidat",
                aliases=("moteur_thermique_definition.architecture", "architecture"),
            )


def _resoudre_alternateur_boite(state: _ResolutionState) -> None:
    rpm_mt = state.number("rpm_moteur")
    rpm_alt = state.number("rpm_alternateur")
    rapport = state.number("rapport_vitesse_alt_sur_moteur")
    if rpm_mt is not None and rpm_alt is not None and rpm_mt > 0:
        ratio = rpm_alt / rpm_mt
        if state.cdc.rapport_boite_min <= ratio <= state.cdc.rapport_boite_max:
            state.add(
                "rapport_vitesse_alt_sur_moteur",
                ratio,
                unite="",
                type_resolution=STATUS_COMPUTED,
                source="resolution_inconnues.chaine_alternateur_boite",
                formule="rapport = rpm_alternateur / rpm_moteur",
                dependances={"rpm_alternateur": rpm_alt, "rpm_moteur": rpm_mt},
                justification="Rapport cinématique requis pour relier alternateur et moteur thermique.",
                niveau_confiance="exact",
                aliases=("rapport_boite_alt",),
            )
        else:
            state.unresolved("conflits", "rapport_vitesse_alt_sur_moteur", f"Rapport {ratio:.4g} hors CDC [{state.cdc.rapport_boite_min}, {state.cdc.rapport_boite_max}].", bloquant=True)
    elif rpm_mt is not None and rapport is not None:
        state.add(
            "vitesse_alternateur_rpm",
            rpm_mt * rapport,
            unite="rpm",
            type_resolution=STATUS_COMPUTED,
            source="resolution_inconnues.chaine_alternateur_boite",
            formule="rpm_alternateur = rpm_moteur * rapport",
            dependances={"rpm_moteur": rpm_mt, "rapport": rapport},
            justification="Propagation cinématique moteur/boîte/alternateur.",
            niveau_confiance="exact",
            aliases=("rpm_alternateur",),
        )


def _resoudre_batterie(state: _ResolutionState) -> None:
    tension = state.number("tension_bus_dc_v")
    p_bus = state.number("puissance_bus_dc_w")
    e_buffer = state.number("energie_batterie_tampon_min_kwh")
    e_user = state.number("energie_batterie_kwh")
    cell_key = str(state.get("cellule_reference", "contraintes_resolution.cellule_reference") or state.cdc.cellule_reference)

    if not state.cdc.autoriser_cellule_reference:
        state.unresolved("restantes_catalogue", "cellule_reference", "Cellule référence non autorisée par CDC.", bloquant=False)
        return
    cell = CELLULES_REFERENCE.get(cell_key)
    if cell is None:
        state.unresolved("restantes_catalogue", "cellule_reference", f"Cellule référence inconnue : {cell_key}.", bloquant=False)
        return
    # Exposer les données cellule comme catalogue, pas comme invention.
    for path, value, unit in (
        ("cellule.cle", cell["cle"], ""),
        ("cellule.u_nominale_v", cell["u_nominale_v"], "V"),
        ("cellule.capacite_ah", cell["capacite_ah"], "Ah"),
        ("cellule.courant_decharge_continu_a", cell["courant_decharge_continu_a"], "A"),
        ("cellule.courant_charge_max_a", cell["courant_charge_max_a"], "A"),
        ("cellule.masse_kg", cell["masse_kg"], "kg"),
    ):
        state.add(
            path,
            value,
            unite=unit,
            type_resolution=STATUS_DERIVED,
            source=cell["source"],
            formule="propriété catalogue cellule",
            dependances={"cellule_reference": cell_key},
            justification="Donnée cellule de référence explicitement autorisée par CDC.",
            niveau_confiance="catalogue",
        )

    if tension is None or tension <= 0:
        return
    ns = int(math.ceil(tension / float(cell["u_nominale_v"])))
    state.add(
        "nb_cellules_serie",
        ns,
        unite="",
        type_resolution=STATUS_COMPUTED,
        source="resolution_inconnues.batterie",
        formule="Ns = ceil(Ubus / Ucell_nom)",
        dependances={"Ubus_v": tension, "Ucell_v": cell["u_nominale_v"]},
        justification="Nombre de cellules en série pour atteindre la tension bus.",
        niveau_confiance="calcul",
        aliases=("batterie.nb_cellules_serie",),
    )

    np_candidates: List[int] = []
    if p_bus is not None:
        pack_current = p_bus / tension
        i_cell_allow = float(cell["courant_decharge_continu_a"]) * max(0.05, min(1.0, state.cdc.derating_courant_cellule))
        np_power = int(math.ceil(pack_current / i_cell_allow))
        np_candidates.append(np_power)
        state.add(
            "batterie.nb_cellules_parallele_puissance_min",
            np_power,
            unite="",
            type_resolution=STATUS_COMPUTED,
            source="resolution_inconnues.batterie",
            formule="Np_power = ceil(I_pack / (I_cell_cont * derating))",
            dependances={"I_pack_a": pack_current, "I_cell_cont_a": cell["courant_decharge_continu_a"], "derating": state.cdc.derating_courant_cellule},
            justification="Branches parallèles minimales pour tenir le courant de décharge bus.",
            niveau_confiance="calcul",
        )
    e_req = max([x for x in (e_buffer, e_user, state.cdc.energie_batterie_min_kwh) if x is not None], default=None)
    if e_req is not None:
        soc_window = max(1e-9, state.cdc.soc_max - state.cdc.soc_min)
        wh_per_parallel = ns * float(cell["u_nominale_v"]) * float(cell["capacite_ah"]) * soc_window
        np_energy = int(math.ceil((e_req * 1000.0) / max(1e-9, wh_per_parallel)))
        np_candidates.append(np_energy)
        state.add(
            "batterie.nb_cellules_parallele_energie_min",
            np_energy,
            unite="",
            type_resolution=STATUS_COMPUTED,
            source="resolution_inconnues.batterie",
            formule="Np_energy = ceil(E_req_Wh / (Ns*Ucell*Ahcell*SOC_window))",
            dependances={"E_req_kwh": e_req, "Ns": ns, "Ucell_v": cell["u_nominale_v"], "Ahcell": cell["capacite_ah"], "soc_window": soc_window},
            justification="Branches parallèles minimales pour l'énergie tampon/projet.",
            niveau_confiance="calcul",
        )
    if np_candidates:
        np_final = max(np_candidates)
        total_cells = ns * np_final
        mass = total_cells * float(cell["masse_kg"])
        energy_nominal_kwh = ns * np_final * float(cell["u_nominale_v"]) * float(cell["capacite_ah"]) / 1000.0
        state.add("nb_cellules_parallele", np_final, unite="", type_resolution=STATUS_COMPUTED, source="resolution_inconnues.batterie", formule="Np = max(Np_power, Np_energy)", dependances={"candidats_np": np_candidates}, justification="Dimensionnement parallèle retenu par contrainte la plus sévère.", niveau_confiance="calcul", aliases=("batterie.nb_cellules_parallele",))
        state.add("batterie.nb_cellules_total", total_cells, unite="", type_resolution=STATUS_COMPUTED, source="resolution_inconnues.batterie", formule="Ntotal = Ns*Np", dependances={"Ns": ns, "Np": np_final}, justification="Nombre total de cellules du pack.", niveau_confiance="calcul")
        state.add("batterie.masse_cellules_kg", mass, unite="kg", type_resolution=STATUS_COMPUTED, source="resolution_inconnues.batterie", formule="masse = Ntotal*masse_cellule", dependances={"Ntotal": total_cells, "masse_cellule_kg": cell["masse_kg"]}, justification="Masse cellules hors BMS/structure/refroidissement.", niveau_confiance="calcul")
        state.add("energie_batterie_kwh", energy_nominal_kwh, unite="kWh", type_resolution=STATUS_COMPUTED, source="resolution_inconnues.batterie", formule="E = Ns*Np*Ucell*Ahcell/1000", dependances={"Ns": ns, "Np": np_final, "Ucell_v": cell["u_nominale_v"], "Ahcell": cell["capacite_ah"]}, justification="Énergie nominale du pack calculée depuis topologie cellules.", niveau_confiance="calcul", aliases=("synthese.batterie.energie_utile_kwh",))


def _resoudre_materiaux(state: _ResolutionState) -> None:
    if not state.cdc.autoriser_choix_materiau:
        return
    mat_key = state.get("materiau_cle")
    allowed = _ensure_tuple(state.get("contraintes_resolution.materiaux_autorises")) or state.cdc.materiaux_autorises
    stress = state.number("contrainte_service_pa", "contrainte_admissible_pa") or state.cdc.contrainte_service_pa
    temp = state.number("temperature_service_max_c") or state.cdc.temperature_service_max_c
    if mod_materiaux is None:
        state.unresolved("restantes_catalogue", "materiau_cle", "Module materiaux.py non importable.", bloquant=False)
        return
    if _is_missing_value(mat_key) and not allowed:
        state.unresolved("restantes_catalogue", "materiau_cle", "Matériau absent et aucun domaine matériaux autorisé.", bloquant=False)
        return
    if _is_missing_value(mat_key) and (stress is None and temp is None):
        state.unresolved("restantes_physiques", "materiau_cle", "Choix matériau impossible sans contrainte, température ou matériau imposé.", bloquant=False)
        return

    chosen_key = str(mat_key) if not _is_missing_value(mat_key) else None
    if chosen_key is None:
        # Utiliser l'API riche si disponible ; sinon fallback simple.
        chooser = getattr(mod_materiaux, "choisir_materiau_par_objectif", None)
        if callable(chooser):
            try:
                rows = chooser(
                    famille="metal" if not state.cdc.familles_materiaux_autorisees else state.cdc.familles_materiaux_autorisees[0],
                    contrainte_sigma_min_pa=stress,
                    temperature_service_c=temp,
                    objectif="resistant",
                    coef_securite=state.cdc.facteur_securite_materiau,
                )
                rows = [r for r in rows if not allowed or r.get("cle") in allowed]
                if rows:
                    chosen_key = str(rows[0].get("cle"))
            except Exception:
                chosen_key = None
        if chosen_key is None and allowed:
            chosen_key = str(allowed[0])
        if chosen_key and not state.strict:
            state.add(
                "materiau_cle",
                chosen_key,
                unite="",
                type_resolution=STATUS_CANDIDATE_FROM_CDC,
                source="materiaux.choisir_materiau_par_objectif",
                formule="sélection matériau sous contraintes disponibles",
                dependances={"materiaux_autorises": list(allowed), "contrainte_service_pa": stress, "temperature_service_c": temp},
                justification="Matériau candidat issu du catalogue matériaux et des contraintes disponibles.",
                niveau_confiance="candidat",
                validation={"doit_etre_valide_par_optimisation": True},
                aliases=("materiau_structure_cle",),
            )
    if chosen_key is None:
        return
    try:
        resume = None
        if hasattr(mod_materiaux, "resume_materiau"):
            resume = mod_materiaux.resume_materiau(
                chosen_key,
                mode="typique",
                coef_securite=state.cdc.facteur_securite_materiau,
                temperature_service_c=temp,
            )
        elif hasattr(mod_materiaux, "get_materiau"):
            m = mod_materiaux.get_materiau(chosen_key)
            resume = m.resume_dimensionnement(coef_securite=state.cdc.facteur_securite_materiau, temperature_service_c=temp)
        if isinstance(resume, Mapping):
            for key, unit in (
                ("densite_kg_m3", "kg/m3"),
                ("module_young_pa", "Pa"),
                ("module_cisaillement_pa", "Pa"),
                ("limite_elastique_pa", "Pa"),
                ("sigma_admissible_elastique_pa", "Pa"),
                ("tau_admissible_von_mises_pa", "Pa"),
                ("conductivite_thermique_w_mk", "W/(m.K)"),
                ("alpha_dilatation_1_k", "1/K"),
                ("cout_matiere_eur_kg", "EUR/kg"),
            ):
                if not _is_missing_value(resume.get(key)):
                    state.add(
                        f"materiau.{key}",
                        resume.get(key),
                        unite=unit,
                        type_resolution=STATUS_DERIVED,
                        source="materiaux.resume_materiau",
                        formule=f"propriété {key} du matériau {chosen_key}",
                        dependances={"materiau_cle": chosen_key},
                        justification="Propriété issue du catalogue matériaux.",
                        niveau_confiance="catalogue",
                    )
    except Exception as exc:
        state.unresolved("restantes_catalogue", "materiau_cle", f"Extraction matériau impossible : {exc}", bloquant=False)


# =============================================================================
# Candidats / optimisation
# =============================================================================


def _traiter_candidats_par_recalcul_optimisation(
    state: _ResolutionState,
    *,
    recalculer: Callable[[Dict[str, Any]], Dict[str, Any]] | None,
    optimiser: Callable[[Dict[str, Any]], Dict[str, Any]] | None,
) -> None:
    # Si pas de callbacks, les candidats restent candidats. Ne jamais les valider.
    if recalculer is None or optimiser is None:
        return
    # Évite de retraiter les mêmes candidats à chaque itération.
    candidates_to_try = [c for c in state.candidates if not c.metadata.get("validation_tentee")]
    for cand in candidates_to_try[:20]:
        cand.metadata["validation_tentee"] = True
        payload_test = copy.deepcopy(state.payload)
        _set_path(payload_test, cand.champ, cand.valeur)
        try:
            rapport_test = recalculer(payload_test)
            opt = optimiser(rapport_test)
        except Exception as exc:
            state.reject_candidate(cand, f"Recalcul/optimisation impossible : {exc}")
            continue
        state.tracabilite["optimisations"].append(_jsonable(opt))
        validation = _valider_candidate_simple(cand, state.payload, rapport_test, opt, state.cdc)
        if validation["ok"]:
            state.add(
                cand.champ,
                cand.valeur,
                unite=cand.unite,
                type_resolution=STATUS_VALIDATED_BY_OPTIMIZATION,
                source=cand.source,
                formule=cand.formule,
                dependances=cand.dependances,
                justification=cand.justification + " Validé par recalcul + optimisation.",
                niveau_confiance="validated_by_optimization",
                validation=validation,
                overwrite=False,
            )
        else:
            state.reject_candidate(cand, validation.get("raison", "candidat rejeté"), validation)


def _valider_candidate_simple(candidate: DonneeCandidate, rapport_avant: Mapping[str, Any], rapport_apres: Mapping[str, Any], optimisation: Mapping[str, Any], cdc: CahierDesChargesSTHOME) -> Dict[str, Any]:
    if not candidate.source or not candidate.justification or not candidate.dependances or not candidate.domaine:
        return {"ok": False, "raison": "source, justification, dépendances ou domaine manquants", "score": None}
    before_inc = _count_inconnues(rapport_avant)
    after_inc = _count_inconnues(rapport_apres)
    if after_inc > before_inc + 1:
        return {"ok": False, "raison": "le candidat augmente les inconnues", "score": None, "before_inc": before_inc, "after_inc": after_inc}
    score = _extract_score_optimisation(optimisation)
    if score is not None and score < 40.0:
        return {"ok": False, "raison": "score optimisation trop faible", "score": score}
    cao_after = _first_non_missing(rapport_apres, {}, "cao.solidworks_ready", "solidworks_ready")
    if cdc.compatibilite_solidworks_requise and cao_after is False:
        return {"ok": False, "raison": "candidat dégrade ou bloque la CAO", "score": score}
    return {"ok": True, "raison": None, "score": score, "statut": STATUS_VALIDATED_BY_OPTIMIZATION}


# =============================================================================
# Classification / frontend
# =============================================================================


def _classer_inconnues_restantes(state: _ResolutionState) -> None:
    requirements = {
        "puissance_sortie_moteur_electrique_w": (("puissance_sortie_moteur_electrique_w", "puissance_sortie_kw"), "Puissance sortie moteur électrique requise.", True),
        "puissance_bus_dc_w": (("puissance_sortie_moteur_electrique_w", "rendement_onduleur", "rendement_moteur_electrique"), "Puissance bus calculable depuis sortie moteur + rendements.", True),
        "tension_bus_dc_v": (("tension_bus_dc_v",), "Tension bus requise pour courant, batterie et alternateur.", True),
        "courant_bus_dc_a": (("puissance_bus_dc_w", "tension_bus_dc_v"), "Courant bus calculable si P et U sont connus.", True),
        "puissance_moteur_thermique_arbre_w": (("puissance_alternateur_electrique_w", "rendement_alternateur", "rendement_boite", "rendement_liaison_meca_alt"), "Puissance moteur thermique calculable depuis chaîne alternateur.", True),
        "rpm_moteur": (("rpm_moteur",), "Régime moteur thermique requis ou candidat profil.", True),
        "couple_moteur_nm": (("puissance_moteur_thermique_arbre_w", "omega_moteur_rad_s"), "Couple moteur calculable si puissance et régime sont connus.", True),
        "couple_alternateur_nm": (("puissance_alternateur_mecanique_w", "rpm_alternateur"), "Couple alternateur calculable si puissance mécanique et rpm alternateur sont connus.", True),
        "cylindree_totale_m3": (("alesage_m", "course_m", "nombre_cylindres"), "Géométrie moteur requise pour CAO et pièces.", True),
        "nb_cellules_parallele": (("tension_bus_dc_v", "puissance_bus_dc_w", "cellule.capacite_ah"), "Topologie batterie calculable si tension, puissance et cellule sont connus.", False),
        "carburant_cle": (("carburant_cle", "contraintes_resolution.carburants_autorises"), "Carburant imposé ou domaine multi-carburant requis.", False),
        "materiau_cle": (("materiau_cle", "contraintes_resolution.materiaux_autorises"), "Matériau imposé ou domaine matériau requis.", False),
    }
    for champ, (deps, reason, blocking) in requirements.items():
        if not _is_missing_value(state.get(champ)):
            continue
        missing = [d for d in deps if _is_missing_value(state.get(d))]
        state.unresolved(
            "restantes_physiques" if blocking else "restantes_catalogue",
            champ,
            reason,
            bloquant=blocking,
            metadata={"donnees_manquantes": missing},
        )
    for conflict in state.conflits:
        state.inconnues["conflits"].append(conflict)
        state.inconnues["bloquantes"].append(conflict)


def build_frontend_contract_from_resolution(state: _ResolutionState, coherence: Mapping[str, Any]) -> Dict[str, Any]:
    fields: List[Dict[str, Any]] = []
    labels = {
        "puissance_sortie_moteur_electrique_w": "Puissance sortie moteur électrique",
        "puissance_bus_dc_w": "Puissance bus DC design",
        "tension_bus_dc_v": "Tension bus DC",
        "courant_bus_dc_a": "Courant bus DC",
        "puissance_alternateur_electrique_w": "Puissance alternateur électrique",
        "puissance_moteur_thermique_arbre_w": "Puissance moteur thermique arbre",
        "rpm_moteur_nominal": "Régime moteur thermique",
        "couple_moteur_nm": "Couple moteur thermique",
        "couple_alternateur_nm": "Couple alternateur",
        "alesage_m": "Alésage",
        "course_m": "Course",
        "nombre_cylindres": "Nombre de cylindres",
        "cylindree_totale_m3": "Cylindrée totale",
        "energie_batterie_kwh": "Énergie batterie",
        "nb_cellules_serie": "Cellules série",
        "nb_cellules_parallele": "Cellules parallèle",
        "carburant_cle": "Carburant",
        "materiau_cle": "Matériau",
    }
    for path, label in labels.items():
        value = _get_path(state.payload, path)
        trace = state.tracabilite["valeurs"].get(path, {})
        status = trace.get("status") or (STATUS_MISSING_REQUIRED if path in {"puissance_sortie_moteur_electrique_w", "puissance_bus_dc_w", "tension_bus_dc_v"} and _is_missing_value(value) else STATUS_MISSING_OPTIONAL if _is_missing_value(value) else STATUS_INPUT)
        fields.append(
            {
                "path": path,
                "label": label,
                "value": _jsonable(value),
                "unit": trace.get("unite", ""),
                "status": status,
                "source": trace.get("source"),
                "editable": status in {STATUS_CANDIDATE_FROM_CDC, STATUS_CANDIDATE_FROM_POWER_PROFILE, STATUS_MISSING_REQUIRED, STATUS_MISSING_OPTIONAL},
                "blocking": status in {STATUS_MISSING_REQUIRED, STATUS_IMPOSSIBLE},
                "reason": trace.get("justification") if trace else ("Donnée manquante." if _is_missing_value(value) else None),
                "confidence": trace.get("niveau_confiance"),
                "trace": trace,
            }
        )
    cao_ready = bool(state.get("solidworks_ready"))
    required_cao = ["alesage_m", "course_m", "nombre_cylindres", "cylindree_totale_m3", "materiau_cle"]
    missing_cao = [p for p in required_cao if _is_missing_value(state.get(p))]
    cao_available = cao_ready and not missing_cao
    return {
        "meta": {"generated_at": _now_iso(), "source": "resolution_inconnues_musclee"},
        "summary": {
            "status": coherence.get("statut"),
            "score_global_100": coherence.get("score_global_100"),
            "nb_missing_blocking": len(state.inconnues.get("bloquantes", [])),
            "nb_candidates": len(state.candidates),
        },
        "fields": fields,
        "unknowns": _jsonable(state.inconnues),
        "alerts": {"conflits": _jsonable(state.conflits)},
        "cao": {
            "available": bool(cao_available),
            "solidworks_ready": cao_ready,
            "mode": "reel_cote" if cao_available else "conceptuel_non_cote" if not missing_cao else "indisponible",
            "missing_fields": missing_cao,
            "reason": None if cao_available else "CAO non fermée : cotes, matériau ou validation SolidWorks absents.",
        },
        "actions": _jsonable(coherence.get("actions_recommandees", [])),
        "raw_available": True,
    }


# =============================================================================
# Scores cohérence
# =============================================================================


def _score_puissance(payload: Mapping[str, Any], cdc: CahierDesChargesSTHOME, blockers: List[Dict[str, Any]], actions: List[Dict[str, Any]]) -> float:
    p_out = _first_number(payload, {}, *get_alias_paths("puissance_sortie_moteur_electrique_w"))
    p_bus = _first_number(payload, {}, *get_alias_paths("puissance_bus_dc_w"))
    u = _first_number(payload, {}, *get_alias_paths("tension_bus_dc_v"))
    i = _first_number(payload, {}, "courant_bus_dc_a")
    score = 0.0
    if p_out is not None:
        score += 0.25
    else:
        blockers.append({"champ": "puissance_sortie_moteur_electrique_w", "raison": "puissance demandée absente"})
    if p_bus is not None:
        score += 0.25
    else:
        actions.append({"champ": "puissance_bus_dc_w", "action": "résoudre depuis puissance sortie + rendements"})
    if u is not None:
        score += 0.20
        if not (cdc.tension_bus_dc_min_v <= u <= cdc.tension_bus_dc_max_v):
            blockers.append({"champ": "tension_bus_dc_v", "raison": "hors bornes CDC"})
            return 0.0
    else:
        actions.append({"champ": "tension_bus_dc_v", "action": "fournir tension ou autoriser profil puissance"})
    if p_bus is not None and u is not None and i is not None:
        expected = p_bus / max(u, 1e-12)
        if _relative_error(i, expected) <= 0.05:
            score += 0.30
        else:
            blockers.append({"champ": "courant_bus_dc_a", "raison": "incohérent avec P/U"})
    elif p_bus is not None and u is not None:
        score += 0.15
    return _clamp01(score)


def _score_energie(payload: Mapping[str, Any], actions: List[Dict[str, Any]]) -> float:
    e = _first_number(payload, {}, *get_alias_paths("energie_batterie_kwh"), "energie_batterie_tampon_min_kwh")
    ns = _first_number(payload, {}, "nb_cellules_serie")
    np = _first_number(payload, {}, "nb_cellules_parallele")
    score = 0.25
    if e is not None:
        score += 0.35
    else:
        actions.append({"champ": "energie_batterie_kwh", "action": "dimensionner batterie tampon ou mission"})
    if ns is not None:
        score += 0.20
    if np is not None:
        score += 0.20
    return _clamp01(score)


def _score_mecanique(payload: Mapping[str, Any], blockers: List[Dict[str, Any]], actions: List[Dict[str, Any]]) -> float:
    rpm = _first_number(payload, {}, *get_alias_paths("rpm_moteur"))
    omega = _first_number(payload, {}, *get_alias_paths("omega_moteur_rad_s"))
    couple = _first_number(payload, {}, *get_alias_paths("couple_moteur_nm"))
    p = _first_number(payload, {}, "puissance_moteur_thermique_arbre_w", "puissance_moteur_w")
    score = 0.20
    if rpm is not None:
        score += 0.20
    else:
        actions.append({"champ": "rpm_moteur", "action": "fournir régime ou autoriser profil puissance"})
    if rpm is not None and omega is not None and _relative_error(omega, 2 * math.pi * rpm / 60) <= 0.03:
        score += 0.20
    if p is not None and omega is not None and couple is not None and omega > 0:
        if _relative_error(couple, p / omega) <= 0.05:
            score += 0.25
        else:
            blockers.append({"champ": "couple_moteur_nm", "raison": "incohérent avec P/omega"})
    else:
        actions.append({"champ": "couple_moteur_nm", "action": "compléter puissance et régime"})
    if _first_number(payload, {}, "couple_alternateur_nm") is not None:
        score += 0.15
    return _clamp01(score)


def _score_thermique(payload: Mapping[str, Any], actions: List[Dict[str, Any]]) -> float:
    p_chim = _first_number(payload, {}, "puissance_chimique_carburant_w")
    mdot = _first_number(payload, {}, "debit_massique_carburant_kg_s")
    eta = _first_number(payload, {}, "rendement_thermique_global")
    score = 0.25
    if eta is not None:
        score += 0.25
    else:
        actions.append({"champ": "rendement_thermique_global", "action": "fournir rendement ou autoriser profil puissance"})
    if p_chim is not None:
        score += 0.25
    if mdot is not None:
        score += 0.25
    return _clamp01(score)


def _score_geometrie(payload: Mapping[str, Any], blockers: List[Dict[str, Any]], actions: List[Dict[str, Any]]) -> float:
    bore = _first_number(payload, {}, *get_alias_paths("alesage_m"))
    stroke = _first_number(payload, {}, *get_alias_paths("course_m"))
    nb = _first_number(payload, {}, *get_alias_paths("nombre_cylindres"))
    vd = _first_number(payload, {}, "cylindree_totale_m3")
    score = 0.0
    if bore is not None:
        score += 0.25
    if stroke is not None:
        score += 0.25
    if nb is not None:
        score += 0.20
    if bore is not None and stroke is not None and nb is not None:
        calc = math.pi / 4 * bore * bore * stroke * nb
        if vd is not None and _relative_error(vd, calc) > 0.05:
            blockers.append({"champ": "cylindree_totale_m3", "raison": "incohérente avec alésage/course/cylindres"})
        else:
            score += 0.30
    else:
        actions.append({"champ": "geometrie_moteur", "action": "résoudre alésage/course/cylindres"})
    return _clamp01(score)


def _score_materiaux(payload: Mapping[str, Any], cdc: CahierDesChargesSTHOME, actions: List[Dict[str, Any]]) -> float:
    mat = _first_non_missing(payload, {}, *get_alias_paths("materiau_cle"))
    sigma = _first_number(payload, {}, "materiau.sigma_admissible_elastique_pa")
    density = _first_number(payload, {}, "materiau.densite_kg_m3")
    score = 0.25
    if not _is_missing_value(mat):
        score += 0.35
    else:
        actions.append({"champ": "materiau_cle", "action": "fournir matériau ou contraintes de choix"})
    if sigma is not None:
        score += 0.25
    if density is not None:
        score += 0.15
    return _clamp01(score)


def _score_carburant(payload: Mapping[str, Any], cdc: CahierDesChargesSTHOME, actions: List[Dict[str, Any]]) -> float:
    fuel = _first_non_missing(payload, {}, *get_alias_paths("carburant_cle"))
    pci = _first_number(payload, {}, "carburant.pci_j_kg")
    afr = _first_number(payload, {}, "carburant.afr_stoechiometrique")
    score = 0.20
    if not _is_missing_value(fuel):
        score += 0.30
    else:
        actions.append({"champ": "carburant_cle", "action": "fournir carburant ou autoriser pire cas multi-carburant"})
    if pci is not None:
        score += 0.30
    if afr is not None:
        score += 0.20
    return _clamp01(score)


def _score_cao(payload: Mapping[str, Any], cdc: CahierDesChargesSTHOME, actions: List[Dict[str, Any]]) -> float:
    sw = _first_non_missing(payload, {}, *get_alias_paths("solidworks_ready"))
    required = ["alesage_m", "course_m", "nombre_cylindres", "materiau_cle"]
    known = sum(0 if _is_missing_value(_first_non_missing(payload, {}, *get_alias_paths(r))) else 1 for r in required)
    score = known / len(required) * 0.8
    if sw is True:
        score = 1.0
    elif cdc.compatibilite_solidworks_requise:
        actions.append({"champ": "cao.solidworks_ready", "action": "valider cotes CAO et interfaces pièces"})
    return _clamp01(score)


def _score_cdc(payload: Mapping[str, Any], cdc: CahierDesChargesSTHOME, blockers: List[Dict[str, Any]], actions: List[Dict[str, Any]]) -> float:
    score = 0.55
    duty = cdc.duty_cycle_moteur_thermique_max
    if duty <= 0 or duty > 1:
        blockers.append({"champ": "duty_cycle_moteur_thermique_max", "raison": "hors domaine (0,1]"})
        return 0.0
    if duty <= 0.5:
        score += 0.20
    else:
        actions.append({"champ": "duty_cycle_moteur_thermique_max", "action": "revenir au cahier des charges <= 50%"})
    if cdc.marge_wltp >= 0.20:
        score += 0.15
    if cdc.systeme_multi_energies:
        score += 0.10
    return _clamp01(score)


# =============================================================================
# Génération géométrie
# =============================================================================


def _geometry_domain_from_state(state: _ResolutionState) -> Dict[str, Any]:
    p = choisir_profil_puissance((state.number("puissance_sortie_moteur_electrique_w") or 0.0) / 1000.0) if state.number("puissance_sortie_moteur_electrique_w") else None
    cr = _safe_dict(_get_path(state.payload, "contraintes_resolution"))
    return {
        "nombres_cylindres": tuple(cr.get("nombres_cylindres_autorises") or state.cdc.nombres_cylindres_autorises or (p.nombres_cylindres_autorises if p else ())),
        "alesage_min_m": cr.get("alesage_min_m") or state.cdc.alesage_min_m or (p.alesage_min_m if p else None),
        "alesage_max_m": cr.get("alesage_max_m") or state.cdc.alesage_max_m or (p.alesage_max_m if p else None),
        "course_min_m": cr.get("course_min_m") or state.cdc.course_min_m or (p.course_min_m if p else None),
        "course_max_m": cr.get("course_max_m") or state.cdc.course_max_m or (p.course_max_m if p else None),
        "ratio_min": cr.get("ratio_course_alesage_min") or state.cdc.ratio_course_alesage_min or (p.ratio_course_alesage_min if p else None),
        "ratio_max": cr.get("ratio_course_alesage_max") or state.cdc.ratio_course_alesage_max or (p.ratio_course_alesage_max if p else None),
        "ratio_cible": state.cdc.ratio_course_alesage_cible or (1.0 if p else None),
    }


def _generer_candidates_geometrie(
    *,
    puissance_w: float,
    rpm: float,
    pme_pa: float,
    bore_known: Optional[float],
    stroke_known: Optional[float],
    nb_cyl_known: Optional[int],
    cdc: CahierDesChargesSTHOME,
    domain: Mapping[str, Any],
) -> List[DonneeCandidate]:
    required = ["nombres_cylindres", "alesage_min_m", "alesage_max_m", "course_min_m", "course_max_m", "ratio_min", "ratio_max"]
    if any(_is_missing_value(domain.get(k)) for k in required):
        return []
    if puissance_w <= 0 or rpm <= 0 or pme_pa <= 0:
        return []
    vd_total = puissance_w * cdc.cycle_diviseur_puissance / (pme_pa * rpm)
    ratios = _linspace(float(domain["ratio_min"]), float(domain["ratio_max"]), 25)
    n_values = [nb_cyl_known] if nb_cyl_known else [int(n) for n in domain["nombres_cylindres"]]
    candidates: List[DonneeCandidate] = []
    for n in n_values:
        if n is None or int(n) <= 0:
            continue
        vd_cyl = vd_total / int(n)
        for ratio in ratios:
            if bore_known is not None and stroke_known is not None:
                bore = bore_known
                stroke = stroke_known
                ratio_eff = stroke / bore if bore > 0 else ratio
            elif bore_known is not None:
                bore = bore_known
                stroke = vd_cyl / (math.pi / 4 * bore * bore)
                ratio_eff = stroke / bore if bore > 0 else ratio
            elif stroke_known is not None:
                stroke = stroke_known
                bore = math.sqrt(vd_cyl / (math.pi / 4 * stroke))
                ratio_eff = stroke / bore if bore > 0 else ratio
            else:
                bore = (4 * vd_cyl / (math.pi * ratio)) ** (1 / 3)
                stroke = ratio * bore
                ratio_eff = ratio
            piston_speed = 2 * stroke * rpm / 60
            valid = (
                float(domain["alesage_min_m"]) <= bore <= float(domain["alesage_max_m"])
                and float(domain["course_min_m"]) <= stroke <= float(domain["course_max_m"])
                and float(domain["ratio_min"]) <= ratio_eff <= float(domain["ratio_max"])
                and (cdc.vitesse_piston_max_ms is None or piston_speed <= cdc.vitesse_piston_max_ms)
            )
            if not valid:
                continue
            p_calc = pme_pa * (math.pi / 4 * bore * bore * stroke * int(n)) * rpm / cdc.cycle_diviseur_puissance
            error = abs(p_calc - puissance_w) / max(abs(puissance_w), 1e-12)
            ratio_target = float(domain.get("ratio_cible") or 1.0)
            score = error + 0.03 * abs(ratio_eff - ratio_target) + 0.0015 * int(n) + 0.02 * max(0.0, piston_speed / max(cdc.vitesse_piston_max_ms or 99.0, 1e-9) - 0.75)
            metadata = {
                "nombre_cylindres": int(n),
                "alesage_m": float(bore),
                "course_m": float(stroke),
                "ratio_course_alesage": float(ratio_eff),
                "cylindree_unitaire_m3": float(vd_cyl),
                "cylindree_totale_m3": float(vd_total),
                "vitesse_piston_m_s": float(piston_speed),
                "erreur_relative_puissance": float(error),
            }
            candidates.append(
                DonneeCandidate(
                    champ="geometrie_moteur",
                    valeur={"nombre_cylindres": int(n), "alesage_m": float(bore), "course_m": float(stroke)},
                    unite="SI",
                    source="resolution_inconnues.generation_geometrie",
                    statut=STATUS_CANDIDATE_FROM_CDC,
                    formule="P = pme * (pi/4*B^2*S*Ncyl) * rpm / cycle_diviseur",
                    dependances={"puissance_w": puissance_w, "rpm": rpm, "pme_pa": pme_pa, "cycle_diviseur": cdc.cycle_diviseur_puissance},
                    justification="Candidat géométrique moteur généré dans les bornes du cahier des charges/profil.",
                    domaine=_jsonable(dict(domain)),
                    score_local=float(score),
                    metadata=metadata,
                )
            )
    candidates.sort(key=lambda c: float(c.score_local if c.score_local is not None else 1e9))
    return candidates[:20]


# =============================================================================
# Helpers divers
# =============================================================================


def normalize_status(value: str) -> str:
    if value in PUBLIC_STATUSES:
        return value
    return INTERNAL_TO_PUBLIC_STATUS.get(str(value), STATUS_DERIVED)


def _coerce_cdc(value: CahierDesChargesSTHOME | Mapping[str, Any] | None) -> CahierDesChargesSTHOME:
    if isinstance(value, CahierDesChargesSTHOME):
        return value
    if isinstance(value, Mapping):
        allowed = set(CahierDesChargesSTHOME.__dataclass_fields__.keys())
        kwargs = {k: v for k, v in value.items() if k in allowed}
        tuple_keys = {
            "nombres_cylindres_autorises",
            "regimes_moteur_candidats_rpm",
            "architectures_autorisees",
            "materiaux_autorises",
            "familles_materiaux_autorisees",
            "carburants_autorises",
        }
        for key in tuple_keys:
            if key in kwargs and kwargs[key] is not None and not isinstance(kwargs[key], tuple):
                kwargs[key] = tuple(kwargs[key])
        return CahierDesChargesSTHOME(**kwargs)
    return CahierDesChargesSTHOME()


def _profile_to_public_row(p: ProfilPuissance) -> Dict[str, Any]:
    return _jsonable(asdict(p))


def _candidate_from_profile(champ: str, valeur: Any, unite: str, justification: str, deps: Mapping[str, Any], domaine: Mapping[str, Any]) -> DonneeCandidate:
    return DonneeCandidate(
        champ=champ,
        valeur=valeur,
        unite=unite,
        source="PROFILS_PUISSANCE",
        statut=STATUS_CANDIDATE_FROM_POWER_PROFILE,
        formule="table préconfigurée par puissance",
        dependances=dict(deps),
        justification=justification,
        domaine=dict(domaine),
    )


def _phys_surface_piston(bore: float) -> float:
    if phys is not None and callable(getattr(phys, "surface_piston", None)):
        return float(phys.surface_piston(bore))
    return math.pi * bore * bore / 4.0


def _phys_volume_balayage(bore: float, stroke: float) -> float:
    if phys is not None and callable(getattr(phys, "volume_balayage", None)):
        return float(phys.volume_balayage(bore, stroke))
    return _phys_surface_piston(bore) * stroke


def _phys_force_pression(p: float, surface: float) -> float:
    if phys is not None and callable(getattr(phys, "force_pression", None)):
        return float(phys.force_pression(p, surface))
    return p * surface


def _phys_pulsation(rpm: float) -> float:
    if phys is not None and callable(getattr(phys, "pulsation", None)):
        return float(phys.pulsation(rpm))
    return 2.0 * math.pi * rpm / 60.0


def _phys_vitesse_piston(stroke: float, rpm: float) -> float:
    if phys is not None and callable(getattr(phys, "vitesse_piston", None)):
        return float(phys.vitesse_piston(stroke, rpm))
    return 2.0 * stroke * rpm / 60.0


def _phys_couple_moteur(power_w: float, omega: float) -> float:
    if phys is not None and callable(getattr(phys, "couple_moteur", None)):
        return float(phys.couple_moteur(power_w, omega))
    return power_w / omega


def _phys_courant_pack(power_w: float, voltage_v: float) -> float:
    if phys is not None and callable(getattr(phys, "courant_pack", None)):
        return float(phys.courant_pack(power_w, voltage_v))
    return power_w / voltage_v


def _choisir_architecture(nb_cyl: int, architectures: Sequence[str]) -> Optional[str]:
    if not architectures:
        return None
    normalized = {str(a).lower(): str(a) for a in architectures}
    if nb_cyl <= 6:
        for key in ("l", "ligne", "inline"):
            if key in normalized:
                return normalized[key]
    if nb_cyl >= 6:
        for key in ("v", "vee"):
            if key in normalized:
                return normalized[key]
    return str(architectures[0])


def _deepcopy_dict(value: Mapping[str, Any] | None) -> Dict[str, Any]:
    return copy.deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def _deep_merge(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(left)
    for k, v in right.items():
        if isinstance(v, Mapping) and isinstance(out.get(k), Mapping):
            out[k] = _deep_merge(dict(out[k]), dict(v))
        else:
            out[k] = copy.deepcopy(v)
    return out


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in {"", "-", "none", "null", "inconnu", "unknown", "n/a"}:
        return True
    return False


def _get_path(data: Mapping[str, Any] | None, path: str) -> Any:
    if not isinstance(data, Mapping) or not path:
        return None
    if path in data:
        return data[path]
    current: Any = data
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return None
    return current


def _set_path(data: Dict[str, Any], path: str, value: Any) -> None:
    if not path:
        return
    parts = path.split(".")
    cur: Dict[str, Any] = data
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _first_non_missing(payload: Mapping[str, Any], rapports: Mapping[str, Any], *paths: str) -> Any:
    for path in paths:
        for root in (payload, rapports):
            value = _get_path(root, path)
            if not _is_missing_value(value):
                return value
    return None


def _first_number(payload: Mapping[str, Any], rapports: Mapping[str, Any], *paths: str) -> Optional[float]:
    value = _first_non_missing(payload, rapports, *paths)
    return float(value) if _is_number(value) else None


def _relative_error(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-12)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _linspace(start: float, stop: float, count: int) -> List[float]:
    if count <= 1:
        return [float(start)]
    step = (stop - start) / float(count - 1)
    return [float(start + i * step) for i in range(count)]


def _dedup_items(items: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for item in items:
        js = _jsonable(item)
        key = json.dumps(js, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(js))
    return out


def _dedup_state(state: _ResolutionState) -> None:
    for k in list(state.inconnues):
        state.inconnues[k] = _dedup_items(state.inconnues[k])
    state.conflits[:] = _dedup_items(state.conflits)


def _record_conflict_if_needed(state: _ResolutionState, path: str, current: Any, proposed: Any, source: str) -> None:
    if _is_number(current) and _is_number(proposed):
        if _relative_error(float(current), float(proposed)) <= 0.05:
            return
    elif current == proposed:
        return
    item = {
        "champ": path,
        "type_inconnue": "inconnue_conflit",
        "valeur_existante": _jsonable(current),
        "valeur_calculee": _jsonable(proposed),
        "source_calculee": source,
        "raison": "Valeur existante incompatible avec la valeur résolue/proposée.",
    }
    state.conflits.append(item)


def _append_unique_source(state: _ResolutionState, source: str) -> None:
    if source and source not in state.tracabilite["sources"]:
        state.tracabilite["sources"].append(source)


def _ensure_tuple(value: Any) -> Tuple[Any, ...]:
    if value is None:
        return tuple()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, str):
        return (value,)
    return tuple(value) if isinstance(value, Iterable) else (value,)


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _count_inconnues(report: Mapping[str, Any]) -> int:
    inc = _safe_dict(report.get("inconnues")) if isinstance(report, Mapping) else {}
    total = 0
    for key in ("impossibles", "partielles", "bloquantes", "restantes_physiques", "restantes_catalogue"):
        total += len(inc.get(key, []) or [])
    return total


def _extract_score_optimisation(opt: Mapping[str, Any]) -> Optional[float]:
    candidates = (
        _get_path(opt, "synthese_optimisation.score_global_100"),
        _get_path(opt, "synthese_optimisation.score_coherence_100"),
        _get_path(opt, "score_global_100"),
        _get_path(opt, "coherence_systeme.score_global_100"),
    )
    for v in candidates:
        if _is_number(v):
            return float(v)
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "CahierDesChargesSTHOME",
    "HypotheseResolue",
    "DonneeCandidate",
    "ResolutionInconnuesReport",
    "ProfilPuissance",
    "PROFILS_PUISSANCE",
    "CELLULES_REFERENCE",
    "ALIASES_CHAMPS",
    "get_alias_paths",
    "generer_table_profils_puissance",
    "choisir_profil_puissance",
    "resoudre_inconnues_systeme",
    "appliquer_resolution_inconnues",
    "tracer_resolution_inconnues",
    "verifier_coherence_resolution",
    "build_frontend_contract_from_resolution",
]


if __name__ == "__main__":
    # Démo locale rapide : 100 kW en sortie moteur électrique.
    report = resoudre_inconnues_systeme(
        {"puissance_sortie_kw": 100.0},
        cahier_des_charges={"mode_resolution": "pre_dimensionnement"},
        strict=False,
    )
    print(json.dumps(report.en_dict(), ensure_ascii=False, indent=2))
