# backend\components\architechture\modules\architecture_sthome.py
from __future__ import annotations

"""
architecture_sthome_complete.py
===============================================================================
Solveur d'architectures moteur pour STHO-ME / SHSE-M
===============================================================================

Objectif
--------
Centraliser les architectures possibles afin que les modules de choix,
d'exploration, de CAO et de pré-dimensionnement utilisent tous le même registre.

Architectures prises en compte :
- L        : en ligne, y compris mono-cylindre si N=1 ;
- V        : deux bancs, nombre de cylindres pair ;
- W        : architecture multi-bancs compacte, N multiple de 3 ou 4 ;
- Etoile   : radial / étoile, N >= 3, idéalement impair en mono-rangée ;
- Boxer    : cylindres opposés à plat, N pair ;
- MultiModulesDC : architecture système modulaire sur bus DC ;
- PistonLibre    : branche R&D, générateur linéaire, hors bielle-vilebrequin.

Règle de conception
-------------------
Les valeurs numériques ci-dessous sont des paramètres EXPLICITES regroupés dans
des dataclasses. Elles peuvent être remplacées depuis le backend ou le cahier des
charges. Le script ne choisit pas de cote catalogue et remonte les inconnues si les
entrées minimales manquent.

Compatibilité
-------------
Ce fichier fournit des fonctions compatibles avec tes modules actuels :
- architecture_possible(...)
- evaluer_architecture(...)
- choix_architecture_optimale(...)
- resoudre_architecture_globale(...)
- Architecture().analyser(...)
"""

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Sequence, Tuple
import math

ArchitectureType = Literal["L", "V", "W", "Etoile", "Boxer", "MultiModulesDC", "PistonLibre"]


# =============================================================================
# Utilitaires robustes
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _require_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_positive(name: str, x: Any, *, strict: bool = True) -> float:
    v = _require_finite(name, x)
    ok = v > 0.0 if strict else v >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v


def _require_int(name: str, x: Any, *, min_value: int = 0) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return int(x)


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": str(nom), "raison": str(raison)})


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    inc = rapport.setdefault("inconnues", {})
    for categorie in ("impossibles", "partielles"):
        vus: set[Tuple[str, str]] = set()
        out: List[Dict[str, str]] = []
        for item in inc.get(categorie, []) or []:
            if not isinstance(item, Mapping):
                continue
            key = (str(item.get("nom", "")), str(item.get("raison", "")))
            if key in vus:
                continue
            vus.add(key)
            out.append({"nom": key[0], "raison": key[1]})
        inc[categorie] = out


def _clamp(x: float, xmin: float, xmax: float) -> float:
    return max(float(xmin), min(float(xmax), float(x)))


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    if not _is_finite(a) or not _is_finite(b) or abs(float(b)) <= 1e-18:
        return default
    return float(a) / float(b)


def _surface_piston_m2(bore_m: float) -> float:
    B = _require_positive("bore_m", bore_m, strict=False)
    return math.pi * B * B / 4.0


def _hz_cycles(regime_tr_min: float, temps_moteur: int = 4) -> float:
    rpm = _require_positive("regime_tr_min", regime_tr_min, strict=True)
    if temps_moteur == 4:
        return rpm / 120.0
    if temps_moteur == 2:
        return rpm / 60.0
    raise ValueError("temps_moteur doit être 2 ou 4.")


def _course_max_depuis_vitesse_piston(vitesse_piston_max_ms: float, regime_tr_min: float) -> float:
    # U_p = 2*S*N/60 => S_max = 30*U_p/N
    Up = _require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False)
    rpm = _require_positive("regime_tr_min", regime_tr_min, strict=True)
    return 30.0 * Up / rpm


def _bore_course_depuis_volume_ratio(volume_unitaire_m3: float, ratio_s_b: float) -> Tuple[float, float]:
    # V = pi/4 * B² * S, S = r*B => B = (4V/(pi*r))^(1/3)
    V = _require_positive("volume_unitaire_m3", volume_unitaire_m3, strict=False)
    r = _require_positive("ratio_s_b", ratio_s_b, strict=True)
    if V == 0.0:
        return 0.0, 0.0
    B = ((4.0 * V) / (math.pi * r)) ** (1.0 / 3.0)
    S = r * B
    return float(B), float(S)


def _ratio_max_compatible_vitesse_piston(volume_unitaire_m3: float, course_max_m: float) -> float:
    # S = r^(2/3) * (4V/pi)^(1/3), donc r <= (S_max/K)^(3/2)
    V = _require_positive("volume_unitaire_m3", volume_unitaire_m3, strict=False)
    Smax = _require_positive("course_max_m", course_max_m, strict=False)
    if V == 0.0:
        return float("inf")
    K = (4.0 * V / math.pi) ** (1.0 / 3.0)
    if K <= 0.0 or Smax <= 0.0:
        return 0.0
    return float((Smax / K) ** 1.5)


def calcul_cylindree_totale_requise(
    puissance_mecanique_w: float,
    pme_pa: float,
    frequence_cycles_hz: float,
    rendement_mecanique: float = 1.0,
) -> float:
    P = _require_positive("puissance_mecanique_w", puissance_mecanique_w, strict=False)
    PME = _require_positive("pme_pa", pme_pa, strict=True)
    f = _require_positive("frequence_cycles_hz", frequence_cycles_hz, strict=True)
    eta = _require_positive("rendement_mecanique", rendement_mecanique, strict=True)
    return P / (PME * f * eta)


# =============================================================================
# Registre central des architectures
# =============================================================================

@dataclass(frozen=True)
class ArchitectureDefinition:
    id: ArchitectureType
    libelle: str
    famille: Literal["moteur_classique", "radial", "systeme", "r_d"]
    description: str
    nb_cyl_min: int = 1
    nb_cyl_max: int = 24
    nb_cyl_pair: bool = False
    nb_cyl_multiple_de: Tuple[int, ...] = tuple()
    nb_cyl_impair_prefere: bool = False
    compatible_bielle_vilebrequin: bool = True
    compatible_boite_crabots: bool = True
    compatible_alternateur_rotatif: bool = True
    complexite: float = 1.0
    serviceabilite: float = 1.0
    masse_mult: float = 1.0
    frottement_mult: float = 1.0
    fiabilite_risque_mult: float = 1.0
    cout_mult: float = 1.0
    priorite_sthome: int = 99
    statut_recommande: str = "exploration"
    notes: str = ""


ARCHITECTURES: Dict[str, ArchitectureDefinition] = {
    "L": ArchitectureDefinition(
        id="L",
        libelle="En ligne / mono-cylindre",
        famille="moteur_classique",
        description="Cylindres alignés ; N=1 correspond au mono-cylindre prototype.",
        nb_cyl_min=1,
        complexite=1.00,
        serviceabilite=1.00,
        masse_mult=1.00,
        frottement_mult=1.00,
        fiabilite_risque_mult=1.00,
        cout_mult=1.00,
        priorite_sthome=1,
        statut_recommande="V1 mono, V2 bicylindre, V3 quatre cylindres",
    ),
    "V": ArchitectureDefinition(
        id="V",
        libelle="En V",
        famille="moteur_classique",
        description="Deux bancs de cylindres ; plus compact en longueur, plus complexe qu'un L.",
        nb_cyl_min=2,
        nb_cyl_pair=True,
        complexite=1.20,
        serviceabilite=0.82,
        masse_mult=1.08,
        frottement_mult=1.05,
        fiabilite_risque_mult=1.04,
        cout_mult=1.18,
        priorite_sthome=5,
        statut_recommande="compact puissance après validation L",
    ),
    "W": ArchitectureDefinition(
        id="W",
        libelle="En W",
        famille="moteur_classique",
        description="Architecture multi-bancs très compacte mais complexe.",
        nb_cyl_min=6,
        nb_cyl_multiple_de=(3, 4),
        complexite=1.65,
        serviceabilite=0.62,
        masse_mult=1.18,
        frottement_mult=1.12,
        fiabilite_risque_mult=1.10,
        cout_mult=1.55,
        priorite_sthome=8,
        statut_recommande="à garder seulement en exploration avancée",
    ),
    "Etoile": ArchitectureDefinition(
        id="Etoile",
        libelle="En étoile / radial",
        famille="radial",
        description="Cylindres disposés radialement autour du vilebrequin ; très court axialement, large frontalement.",
        nb_cyl_min=3,
        nb_cyl_impair_prefere=True,
        complexite=1.38,
        serviceabilite=0.90,
        masse_mult=1.25,
        frottement_mult=1.18,
        fiabilite_risque_mult=1.16,
        cout_mult=1.32,
        priorite_sthome=6,
        statut_recommande="faisable, utile si refroidissement/compacité axiale prioritaires",
        notes="Pour une étoile mono-rangée, un nombre impair de cylindres est préférable ; un nombre pair reste autorisé ici mais signalé.",
    ),
    "Boxer": ArchitectureDefinition(
        id="Boxer",
        libelle="Boxer / à plat opposé",
        famille="moteur_classique",
        description="Cylindres opposés horizontalement ; bon équilibrage, largeur importante.",
        nb_cyl_min=2,
        nb_cyl_pair=True,
        complexite=1.12,
        serviceabilite=0.86,
        masse_mult=1.10,
        frottement_mult=1.03,
        fiabilite_risque_mult=0.98,
        cout_mult=1.20,
        priorite_sthome=4,
        statut_recommande="bon équilibrage, pertinent si hauteur faible exigée",
    ),
    "MultiModulesDC": ArchitectureDefinition(
        id="MultiModulesDC",
        libelle="Multi-modules thermiques sur bus DC",
        famille="systeme",
        description="Plusieurs modules mono/bicylindres alimentent un bus DC commun avec batterie tampon.",
        nb_cyl_min=1,
        compatible_bielle_vilebrequin=True,
        compatible_boite_crabots=True,
        compatible_alternateur_rotatif=True,
        complexite=1.42,
        serviceabilite=1.12,
        masse_mult=1.14,
        frottement_mult=1.06,
        fiabilite_risque_mult=0.92,
        cout_mult=1.28,
        priorite_sthome=3,
        statut_recommande="meilleure architecture système long terme",
        notes="Ce n'est pas une géométrie de bloc unique : le solveur la traite comme groupement de modules L/Bicylindre.",
    ),
    "PistonLibre": ArchitectureDefinition(
        id="PistonLibre",
        libelle="Piston libre + générateur linéaire",
        famille="r_d",
        description="Architecture sans vilebrequin classique ; adaptée à une branche R&D séparée.",
        nb_cyl_min=1,
        compatible_bielle_vilebrequin=False,
        compatible_boite_crabots=False,
        compatible_alternateur_rotatif=False,
        complexite=1.75,
        serviceabilite=0.70,
        masse_mult=0.92,
        frottement_mult=0.92,
        fiabilite_risque_mult=1.28,
        cout_mult=1.50,
        priorite_sthome=7,
        statut_recommande="R&D séparée, non compatible pipeline vilebrequin",
    ),
}

_ARCH_ALIASES = {
    "ligne": "L",
    "en_ligne": "L",
    "mono": "L",
    "mono_cylindre": "L",
    "monocylindre": "L",
    "bicylindre_ligne": "L",
    "4_ligne": "L",
    "inline": "L",
    "i": "L",
    "l": "L",
    "v": "V",
    "v4": "V",
    "v6": "V",
    "v8": "V",
    "w": "W",
    "w12": "W",
    "etoile": "Etoile",
    "étoile": "Etoile",
    "radial": "Etoile",
    "radiale": "Etoile",
    "etoile_radial": "Etoile",
    "boxer": "Boxer",
    "flat": "Boxer",
    "a_plat": "Boxer",
    "à_plat": "Boxer",
    "opposes": "Boxer",
    "opposés": "Boxer",
    "multi": "MultiModulesDC",
    "multi_modules": "MultiModulesDC",
    "multi_modules_dc": "MultiModulesDC",
    "modules_dc": "MultiModulesDC",
    "piston_libre": "PistonLibre",
    "free_piston": "PistonLibre",
}


def _norm_token(x: Any) -> str:
    s = "" if x is None else str(x)
    s = s.strip().lower()
    tr = str.maketrans({
        "à": "a", "â": "a", "ä": "a", "é": "e", "è": "e", "ê": "e", "ë": "e",
        "î": "i", "ï": "i", "ô": "o", "ö": "o", "ù": "u", "û": "u", "ü": "u", "ç": "c",
    })
    s = s.translate(tr)
    for ch in (" ", "-", "/", "\\"):
        s = s.replace(ch, "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s


def normaliser_architecture(architecture: Any) -> str:
    if architecture in ARCHITECTURES:
        return str(architecture)
    token = _norm_token(architecture)
    if token in _ARCH_ALIASES:
        return _ARCH_ALIASES[token]
    # Respecter la casse canonique si elle arrive déjà presque bonne.
    for key in ARCHITECTURES:
        if _norm_token(key) == token:
            return key
    return str(architecture)


def architectures_moteur_classique() -> Tuple[str, ...]:
    return tuple(k for k, v in ARCHITECTURES.items() if v.famille in ("moteur_classique", "radial"))


# =============================================================================
# Paramètres explicites de gabarit / score
# =============================================================================

@dataclass(frozen=True)
class ParametresArchitectureSTHOME:
    # Cycle / géométrie
    temps_moteur: int = 4
    rendement_mecanique: float = 0.85
    ratio_course_alesage_max: float = 1.20
    ratios_course_alesage: Tuple[float, ...] = (0.75, 0.90, 1.00, 1.10, 1.20)

    # Exploration
    delta_cylindres: int = 6
    min_exploration: int = 16
    n_max_absolu: int = 24

    # Packaging explicite
    pas_bore_mult: float = 1.35
    pas_course_mult: float = 0.35
    marge_pas_m: float = 0.015
    largeur_banc_mult: float = 1.55
    hauteur_haut_moteur_mult: float = 1.60
    hauteur_carter_mult: float = 0.45
    longueur_accessoires_m: float = 0.22
    largeur_accessoires_m: float = 0.08
    angle_v_deg: float = 60.0
    angle_w_deg: float = 40.0
    radial_diametre_mult: float = 2.80
    radial_longueur_mult: float = 1.90
    radial_croissance_diametre_par_cyl: float = 0.025
    marge_structure_mult: float = 1.10

    # Maintenance / coûts relatifs
    horizon_usage_h: float = 20_000.0
    duree_vie_joint_base_h: float = 5_000.0
    joints_par_cylindre: int = 3
    cout_intervention_base_eur: float = 2_000.0
    echelle_eur_par_point: float = 1_000.0

    # Référence score
    masse_reference_kg: float = 80.0
    puissance_reference_w: float = 100_000.0


@dataclass(frozen=True)
class PoidsScoreArchitecture:
    poids_maintenance: float = 1.0
    poids_masse: float = 1.0
    poids_cout_matiere: float = 1.0
    poids_compacite: float = 1.0
    poids_fiabilite: float = 1.0
    poids_rendement: float = 1.0
    poids_priorite_sthome: float = 0.35


# =============================================================================
# Contraintes et gabarit
# =============================================================================

def architecture_possible(type_arch: Any, nb_cylindres: int, *, inclure_systeme: bool = False) -> Tuple[bool, List[str]]:
    arch = normaliser_architecture(type_arch)
    nb = _require_int("nb_cylindres", nb_cylindres, min_value=1)
    messages: List[str] = []

    definition = ARCHITECTURES.get(arch)
    if definition is None:
        return False, [f"Architecture inconnue: {type_arch!r}."]

    if definition.famille in ("systeme", "r_d") and not inclure_systeme:
        return False, [f"{arch} n'est pas une architecture de bloc moteur classique ; l'activer via inclure_systeme=True."]

    if nb < definition.nb_cyl_min:
        return False, [f"{arch} exige au moins {definition.nb_cyl_min} cylindre(s)."]
    if nb > definition.nb_cyl_max:
        return False, [f"{arch} dépasse nb_cyl_max={definition.nb_cyl_max}."]
    if definition.nb_cyl_pair and (nb % 2 != 0):
        return False, [f"{arch} exige un nombre pair de cylindres."]
    if definition.nb_cyl_multiple_de:
        if not any(nb % m == 0 for m in definition.nb_cyl_multiple_de):
            return False, [f"{arch} exige un nombre de cylindres multiple de {definition.nb_cyl_multiple_de}."]
    if definition.nb_cyl_impair_prefere and (nb % 2 == 0):
        messages.append(f"{arch}: nombre pair accepté par le modèle, mais un nombre impair est préférable en étoile mono-rangée.")

    return True, messages


def _pitch_cylindre_m(alesage_m: float, course_m: float, p: ParametresArchitectureSTHOME) -> float:
    B = _require_positive("alesage_m", alesage_m, strict=True)
    S = _require_positive("course_m", course_m, strict=True)
    return p.pas_bore_mult * B + p.pas_course_mult * S + p.marge_pas_m


def estimer_gabarit_architecture(
    type_arch: Any,
    nb_cylindres: int,
    alesage_m: float,
    course_m: float,
    params: ParametresArchitectureSTHOME = ParametresArchitectureSTHOME(),
    *,
    inclure_systeme: bool = False,
) -> Dict[str, Any]:
    arch = normaliser_architecture(type_arch)
    ok, notes = architecture_possible(arch, nb_cylindres, inclure_systeme=inclure_systeme)
    if not ok:
        raise ValueError("; ".join(notes))

    B = _require_positive("alesage_m", alesage_m, strict=True)
    S = _require_positive("course_m", course_m, strict=True)
    N = _require_int("nb_cylindres", nb_cylindres, min_value=1)
    pitch = _pitch_cylindre_m(B, S, params)
    bank_width = params.largeur_banc_mult * B
    h_engine = params.hauteur_haut_moteur_mult * B + S + params.hauteur_carter_mult * B
    crank_w = 0.9 * B + params.largeur_accessoires_m

    if arch == "L":
        L = N * pitch + params.longueur_accessoires_m
        W = bank_width + crank_w
        H = h_engine
        banks = 1
    elif arch == "V":
        banks = 2
        cyl_par_banc = math.ceil(N / 2.0)
        a = math.radians(params.angle_v_deg)
        L = cyl_par_banc * pitch + params.longueur_accessoires_m
        W = 2.0 * bank_width * math.sin(0.5 * a) + crank_w
        H = bank_width * math.cos(0.5 * a) + S + params.hauteur_carter_mult * B
    elif arch == "W":
        banks = 3 if N % 3 == 0 else 4
        cyl_par_banc = math.ceil(N / float(banks))
        a = math.radians(params.angle_w_deg)
        L = cyl_par_banc * pitch + params.longueur_accessoires_m
        W = 2.8 * bank_width * math.sin(0.5 * a) + crank_w + 0.35 * B
        H = 1.25 * bank_width + S + params.hauteur_carter_mult * B
    elif arch == "Etoile":
        banks = "radial"
        growth = 1.0 + params.radial_croissance_diametre_par_cyl * max(0, N - 5)
        diametre = growth * (params.radial_diametre_mult * B + 1.2 * S)
        L = params.radial_longueur_mult * B + 0.75 * S + params.longueur_accessoires_m
        W = diametre
        H = diametre
    elif arch == "Boxer":
        banks = 2
        cyl_par_banc = math.ceil(N / 2.0)
        L = cyl_par_banc * pitch + params.longueur_accessoires_m
        W = 2.0 * bank_width + crank_w
        H = 0.90 * B + S + params.hauteur_carter_mult * B
    elif arch == "MultiModulesDC":
        # Groupement de modules en ligne : estimation système, pas bloc unique.
        modules = max(1, math.ceil(N / 2.0))
        L_module = min(2, N) * pitch + params.longueur_accessoires_m
        W_module = bank_width + crank_w
        H_module = h_engine
        L = L_module
        W = modules * W_module * 0.72
        H = H_module
        banks = modules
    elif arch == "PistonLibre":
        L = 1.15 * S + params.longueur_accessoires_m
        W = bank_width + 0.35 * B
        H = h_engine * 0.80
        banks = 1
    else:
        raise ValueError(f"Architecture non supportée: {type_arch!r}")

    marge = params.marge_structure_mult
    return {
        "architecture": arch,
        "nb_cylindres": N,
        "nb_bancs_ou_modules": banks,
        "longueur_m": marge * L,
        "largeur_m": marge * W,
        "hauteur_m": marge * H,
        "volume_boite_m3": (marge ** 3) * L * W * H,
        "pas_cylindre_m": pitch,
        "notes": notes,
    }


# =============================================================================
# Conséquences pièces architecture
# =============================================================================

def consequences_pieces_architecture(type_arch: Any, nb_cylindres: int, pas_cylindre_m: float) -> Dict[str, Any]:
    arch = normaliser_architecture(type_arch)
    N = _require_int("nb_cylindres", nb_cylindres, min_value=1)
    pas = _require_positive("pas_cylindre_m", pas_cylindre_m, strict=True)

    if arch == "V":
        nb_manetons = math.ceil(N / 2.0)
        nb_paliers = nb_manetons + 1
        f_long = 0.55
        nb_culasses = 2
        complexite_usinage = "haute"
    elif arch == "W":
        nb_manetons = math.ceil(N / 3.0)
        nb_paliers = nb_manetons + 1
        f_long = 0.35
        nb_culasses = 3 if N % 3 == 0 else 4
        complexite_usinage = "tres_haute"
    elif arch == "Etoile":
        nb_manetons = 1
        nb_paliers = 2
        f_long = 0.20
        nb_culasses = N
        complexite_usinage = "haute_bielle_maitresse"
    elif arch == "Boxer":
        nb_manetons = N
        nb_paliers = N + 1
        f_long = 0.60
        nb_culasses = 2
        complexite_usinage = "standard_plus"
    elif arch == "MultiModulesDC":
        modules = max(1, math.ceil(N / 2.0))
        nb_manetons = N
        nb_paliers = modules * 3
        f_long = 0.50
        nb_culasses = modules
        complexite_usinage = "modulaire"
    elif arch == "PistonLibre":
        nb_manetons = 0
        nb_paliers = 0
        f_long = 0.0
        nb_culasses = N
        complexite_usinage = "specifique_generateur_lineaire"
    else:
        nb_manetons = N
        nb_paliers = N + 1
        f_long = 1.0
        nb_culasses = 1
        complexite_usinage = "standard"

    return {
        "bloc_moteur_arch": {
            "architecture": arch,
            "nb_plans_de_joint_culasse": nb_culasses,
        },
        "culasse_arch": {
            "nb_culasses": nb_culasses,
            "nb_soupapes_totales_si_4_par_cyl": N * 4,
            "complexite_distribution": "standard" if nb_culasses == 1 else "elevee",
        },
        "vilebrequin_arch": {
            "compatible_vilebrequin": ARCHITECTURES[arch].compatible_bielle_vilebrequin,
            "longueur_vilebrequin_m_estimee": N * pas * f_long,
            "nb_manetons_estimes": nb_manetons,
            "nb_paliers_estimes": nb_paliers,
            "complexite_usinage": complexite_usinage,
        },
    }


# =============================================================================
# Évaluation / scoring
# =============================================================================

def _cout_maintenance_estime(
    *,
    horizon_usage_h: float,
    duree_vie_joint_base_h: float,
    charge_ref_n: float,
    charge_actuelle_n: float,
    nb_joints_ref: int,
    nb_joints_actuel: int,
    cout_intervention_base_eur: float,
    architecture: str,
) -> float:
    if charge_actuelle_n <= 0.0:
        return 0.0
    beta = 1.5
    L0 = max(float(duree_vie_joint_base_h), 1e-12)
    W0 = max(float(charge_ref_n), 1e-12)
    W = max(float(charge_actuelle_n), 1e-12)
    life_h = L0 * ((W0 / W) ** beta)
    nb_interventions = max(float(horizon_usage_h), 0.0) / max(life_h, 1e-12)
    joint_factor = max(int(nb_joints_actuel), 0) / max(int(nb_joints_ref), 1)
    return nb_interventions * float(cout_intervention_base_eur) * joint_factor * ARCHITECTURES[architecture].cout_mult


def evaluer_candidat_architecture(
    *,
    type_arch: Any,
    nb_cylindres: int,
    cylindree_totale_m3: float,
    ratio_course_alesage: float,
    pme_pa: float,
    regime_tr_min: float,
    vitesse_piston_max_ms: float,
    longueur_dispo_m: float,
    largeur_dispo_m: float,
    hauteur_dispo_m: Optional[float] = None,
    params: ParametresArchitectureSTHOME = ParametresArchitectureSTHOME(),
    poids: PoidsScoreArchitecture = PoidsScoreArchitecture(),
    charge_ref_n: Optional[float] = None,
    n_ref: Optional[int] = None,
    inclure_systeme: bool = False,
) -> Dict[str, Any]:
    arch = normaliser_architecture(type_arch)
    ok, notes = architecture_possible(arch, nb_cylindres, inclure_systeme=inclure_systeme)
    if not ok:
        raise ValueError("; ".join(notes))

    N = _require_int("nb_cylindres", nb_cylindres, min_value=1)
    Vtot = _require_positive("cylindree_totale_m3", cylindree_totale_m3, strict=True)
    ratio = _require_positive("ratio_course_alesage", ratio_course_alesage, strict=True)
    PME = _require_positive("pme_pa", pme_pa, strict=True)
    rpm = _require_positive("regime_tr_min", regime_tr_min, strict=True)
    Up_max = _require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False)
    Lmax = _require_positive("longueur_dispo_m", longueur_dispo_m, strict=True)
    Wmax = _require_positive("largeur_dispo_m", largeur_dispo_m, strict=True)
    Hmax = _require_positive("hauteur_dispo_m", hauteur_dispo_m, strict=True) if hauteur_dispo_m is not None else None

    Vunit = Vtot / N
    bore_m, course_m = _bore_course_depuis_volume_ratio(Vunit, ratio)
    up_moy_ms = 2.0 * course_m * rpm / 60.0
    if up_moy_ms > Up_max + 1e-12:
        raise ValueError(f"Vitesse piston dépassée: {up_moy_ms:.3f} > {Up_max:.3f} m/s.")

    gabarit = estimer_gabarit_architecture(arch, N, bore_m, course_m, params, inclure_systeme=inclure_systeme)
    valide_packaging = gabarit["longueur_m"] <= Lmax and gabarit["largeur_m"] <= Wmax
    if Hmax is not None:
        valide_packaging = valide_packaging and gabarit["hauteur_m"] <= Hmax

    surface = _surface_piston_m2(bore_m)
    charge_moy_n = PME * surface
    if charge_ref_n is None or charge_ref_n <= 0.0:
        charge_ref_n = max(charge_moy_n, 1.0)
    if n_ref is None or n_ref <= 0:
        n_ref = max(1, N)

    definition = ARCHITECTURES[arch]
    joints_ref = max(1, int(n_ref) * params.joints_par_cylindre)
    joints_actuel = max(1, N * params.joints_par_cylindre)
    cout_maintenance = _cout_maintenance_estime(
        horizon_usage_h=params.horizon_usage_h,
        duree_vie_joint_base_h=params.duree_vie_joint_base_h,
        charge_ref_n=charge_ref_n,
        charge_actuelle_n=charge_moy_n,
        nb_joints_ref=joints_ref,
        nb_joints_actuel=joints_actuel,
        cout_intervention_base_eur=params.cout_intervention_base_eur,
        architecture=arch,
    )

    # Indices explicites, relatifs : pas des masses industrielles finales.
    volume_geom = N * bore_m * bore_m * max(course_m, 1e-12)
    masse_relative = definition.masse_mult * volume_geom * 7850.0 * 0.18
    cout_matiere_relatif = masse_relative * definition.cout_mult
    compacite_score = max(
        gabarit["longueur_m"] / Lmax,
        gabarit["largeur_m"] / Wmax,
        gabarit["hauteur_m"] / Hmax if Hmax else 0.0,
    )
    charge_ratio = charge_moy_n / max(charge_ref_n, 1e-12)
    fiabilite_indice = definition.fiabilite_risque_mult * (1.0 + 0.06 * max(0, N - 1)) * charge_ratio
    rendement_indice = definition.frottement_mult * (1.0 + 0.025 * max(0, N - 1)) * (1.0 + 0.08 * max(0.0, ratio - 1.0))
    maintenance_score = cout_maintenance / max(params.echelle_eur_par_point, 1e-12)
    priorite_score = definition.priorite_sthome / 10.0

    score_brut = (
        poids.poids_maintenance * maintenance_score
        + poids.poids_masse * masse_relative
        + poids.poids_cout_matiere * cout_matiere_relatif
        + poids.poids_compacite * compacite_score
        + poids.poids_fiabilite * fiabilite_indice
        + poids.poids_rendement * rendement_indice
        + poids.poids_priorite_sthome * priorite_score
    )
    if not valide_packaging:
        score_brut += 1000.0
    if arch == "Etoile" and (N % 2 == 0):
        score_brut += 0.25  # avertissement léger : possible mais moins conseillé.

    return {
        "architecture": arch,
        "libelle": definition.libelle,
        "statut_recommande": definition.statut_recommande,
        "nb_cylindres": N,
        "ratio_S_B": ratio,
        "alesage_m": bore_m,
        "alesage_mm": bore_m * 1000.0,
        "course_m": course_m,
        "course_mm": course_m * 1000.0,
        "cylindree_totale_m3": Vtot,
        "cylindree_totale_cm3": Vtot * 1e6,
        "cylindree_unitaire_cm3": Vunit * 1e6,
        "vitesse_piston_moyenne_ms": up_moy_ms,
        "charge_moy_piston_n": charge_moy_n,
        "valide_packaging": bool(valide_packaging),
        "gabarit": gabarit,
        "pieces_architecture": consequences_pieces_architecture(arch, N, gabarit["pas_cylindre_m"]),
        "indices": {
            "cout_maintenance_eur": cout_maintenance,
            "maintenance_score": maintenance_score,
            "masse_relative": masse_relative,
            "cout_matiere_relatif": cout_matiere_relatif,
            "compacite_score": compacite_score,
            "fiabilite_indice": fiabilite_indice,
            "rendement_indice": rendement_indice,
            "priorite_score": priorite_score,
        },
        "score_brut": score_brut,
        "notes": [*notes, definition.notes] if definition.notes else notes,
    }


def _normaliser_scores(candidats: List[Dict[str, Any]]) -> None:
    champs = [
        ("cout_maintenance_eur", ("indices", "cout_maintenance_eur")),
        ("maintenance_score", ("indices", "maintenance_score")),
        ("masse_relative", ("indices", "masse_relative")),
        ("cout_matiere_relatif", ("indices", "cout_matiere_relatif")),
        ("compacite_score", ("indices", "compacite_score")),
        ("fiabilite_indice", ("indices", "fiabilite_indice")),
        ("rendement_indice", ("indices", "rendement_indice")),
        ("priorite_score", ("indices", "priorite_score")),
        ("score_brut", ("score_brut",)),
    ]
    for out_name, path in champs:
        values: List[float] = []
        for c in candidats:
            cur: Any = c
            for key in path:
                cur = cur.get(key) if isinstance(cur, Mapping) else None
            if _is_finite(cur):
                values.append(float(cur))
        if not values:
            for c in candidats:
                c[out_name + "_norm"] = None
            continue
        vmin, vmax = min(values), max(values)
        if abs(vmax - vmin) <= 1e-15:
            for c in candidats:
                c[out_name + "_norm"] = 0.0
            continue
        for c in candidats:
            cur: Any = c
            for key in path:
                cur = cur.get(key) if isinstance(cur, Mapping) else None
            c[out_name + "_norm"] = (float(cur) - vmin) / (vmax - vmin) if _is_finite(cur) else None


def _score_final(c: Mapping[str, Any], poids: PoidsScoreArchitecture) -> float:
    def g(key: str) -> float:
        v = c.get(key + "_norm")
        return 1.0 if v is None or not _is_finite(v) else float(v)

    return float(
        poids.poids_maintenance * g("maintenance_score")
        + poids.poids_masse * g("masse_relative")
        + poids.poids_cout_matiere * g("cout_matiere_relatif")
        + poids.poids_compacite * g("compacite_score")
        + poids.poids_fiabilite * g("fiabilite_indice")
        + poids.poids_rendement * g("rendement_indice")
        + poids.poids_priorite_sthome * g("priorite_score")
        + 0.10 * g("score_brut")
    )


# =============================================================================
# Exploration globale
# =============================================================================

def explorer_architectures(
    *,
    puissance_cible_w: float,
    regime_tr_min: float,
    pme_pa: float,
    vitesse_piston_max_ms: float,
    longueur_dispo_m: float,
    largeur_dispo_m: float,
    hauteur_dispo_m: Optional[float] = None,
    architectures_autorisees: Optional[Sequence[Any]] = None,
    architecture_forcee: Optional[Any] = None,
    inclure_systeme: bool = False,
    params: ParametresArchitectureSTHOME = ParametresArchitectureSTHOME(),
    poids: PoidsScoreArchitecture = PoidsScoreArchitecture(),
) -> Dict[str, Any]:
    rapport: Dict[str, Any] = {
        "entrees": {},
        "hypotheses_explicites": asdict(params),
        "poids_score": asdict(poids),
        "cylindree": {},
        "contraintes": {},
        "architectures_connues": {k: asdict(v) for k, v in ARCHITECTURES.items()},
        "exploration": [],
        "meilleurs_par_architecture": {},
        "meilleur": None,
        "inconnues": {"impossibles": [], "partielles": []},
        "notes_modele": [],
    }

    for name, value, strict in [
        ("puissance_cible_w", puissance_cible_w, False),
        ("regime_tr_min", regime_tr_min, True),
        ("pme_pa", pme_pa, True),
        ("vitesse_piston_max_ms", vitesse_piston_max_ms, False),
        ("longueur_dispo_m", longueur_dispo_m, True),
        ("largeur_dispo_m", largeur_dispo_m, True),
    ]:
        try:
            _require_positive(name, value, strict=strict)
        except Exception as exc:
            _push_inconnue(rapport, "impossibles", name, str(exc))

    if rapport["inconnues"]["impossibles"]:
        _dedup_inconnues(rapport)
        return rapport

    P = _require_positive("puissance_cible_w", puissance_cible_w, strict=False)
    rpm = _require_positive("regime_tr_min", regime_tr_min, strict=True)
    PME = _require_positive("pme_pa", pme_pa, strict=True)
    Upmax = _require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False)
    Lmax = _require_positive("longueur_dispo_m", longueur_dispo_m, strict=True)
    Wmax = _require_positive("largeur_dispo_m", largeur_dispo_m, strict=True)
    Hmax = _require_positive("hauteur_dispo_m", hauteur_dispo_m, strict=True) if hauteur_dispo_m is not None else None

    f_hz = _hz_cycles(rpm, params.temps_moteur)
    Vtot = calcul_cylindree_totale_requise(P, PME, f_hz, params.rendement_mecanique)
    course_max_m = _course_max_depuis_vitesse_piston(Upmax, rpm)

    # Estimation du nombre minimal via la plus grosse cylindrée unitaire admissible.
    B_lim = course_max_m / max(params.ratio_course_alesage_max, 1e-12)
    Vunit_max = (math.pi / 4.0) * (B_lim ** 2) * course_max_m if B_lim > 0.0 else 0.0
    if Vunit_max <= 0.0:
        _push_inconnue(rapport, "impossibles", "cylindree_unitaire_max", "Vitesse piston ou régime incohérent : Vunit_max <= 0.")
        _dedup_inconnues(rapport)
        return rapport

    n_min = max(1, int(math.ceil(Vtot / Vunit_max)))
    if n_min > params.n_max_absolu:
        _push_inconnue(
            rapport,
            "impossibles",
            "n_min",
            f"n_min={n_min} > n_max_absolu={params.n_max_absolu}. Augmenter Up_max, PME, régime, ou réduire puissance.",
        )
        _dedup_inconnues(rapport)
        return rapport

    rapport["entrees"] = {
        "puissance_cible_w": P,
        "regime_tr_min": rpm,
        "pme_pa": PME,
        "vitesse_piston_max_ms": Upmax,
        "longueur_dispo_m": Lmax,
        "largeur_dispo_m": Wmax,
        "hauteur_dispo_m": Hmax,
        "architectures_autorisees": list(architectures_autorisees) if architectures_autorisees else None,
        "architecture_forcee": architecture_forcee,
        "inclure_systeme": inclure_systeme,
    }
    rapport["cylindree"] = {
        "frequence_cycles_hz": f_hz,
        "cylindree_totale_m3": Vtot,
        "cylindree_totale_cm3": Vtot * 1e6,
        "cylindree_unitaire_max_m3": Vunit_max,
        "cylindree_unitaire_max_cm3": Vunit_max * 1e6,
        "n_min": n_min,
    }
    rapport["contraintes"] = {
        "course_max_m": course_max_m,
        "course_max_mm": course_max_m * 1000.0,
        "bore_limite_depuis_ratio_max_m": B_lim,
        "bore_limite_depuis_ratio_max_mm": B_lim * 1000.0,
    }

    if architecture_forcee is not None:
        archs = [normaliser_architecture(architecture_forcee)]
    elif architectures_autorisees is not None:
        archs = [normaliser_architecture(a) for a in architectures_autorisees]
    else:
        archs = list(architectures_moteur_classique())
        if inclure_systeme:
            archs.extend(["MultiModulesDC", "PistonLibre"])

    n_max = min(params.n_max_absolu, max(params.min_exploration, n_min + params.delta_cylindres))

    # Référence charge pour maintenance / fiabilité : N_min avec ratio max compatible.
    Vunit_ref = Vtot / n_min
    ratio_lim_ref = _ratio_max_compatible_vitesse_piston(Vunit_ref, course_max_m)
    ratio_ref = min(params.ratio_course_alesage_max, ratio_lim_ref) if math.isfinite(ratio_lim_ref) else params.ratio_course_alesage_max
    ratio_ref = max(1e-6, ratio_ref)
    B_ref, _S_ref = _bore_course_depuis_volume_ratio(Vunit_ref, ratio_ref)
    charge_ref_n = PME * _surface_piston_m2(B_ref)

    for N in range(n_min, n_max + 1):
        Vunit = Vtot / N
        ratio_lim = _ratio_max_compatible_vitesse_piston(Vunit, course_max_m)
        ratios = list(params.ratios_course_alesage)
        # Ajouter automatiquement le ratio maximal compatible si absent.
        if math.isfinite(ratio_lim):
            ratios.append(min(params.ratio_course_alesage_max, ratio_lim))
        ratios = sorted({round(max(1e-6, min(params.ratio_course_alesage_max, r)), 6) for r in ratios if r > 0.0})

        for ratio in ratios:
            try:
                B, S = _bore_course_depuis_volume_ratio(Vunit, ratio)
                if 2.0 * S * rpm / 60.0 > Upmax + 1e-12:
                    continue
                for arch in archs:
                    ok, _msgs = architecture_possible(arch, N, inclure_systeme=inclure_systeme)
                    if not ok:
                        continue
                    cand = evaluer_candidat_architecture(
                        type_arch=arch,
                        nb_cylindres=N,
                        cylindree_totale_m3=Vtot,
                        ratio_course_alesage=ratio,
                        pme_pa=PME,
                        regime_tr_min=rpm,
                        vitesse_piston_max_ms=Upmax,
                        longueur_dispo_m=Lmax,
                        largeur_dispo_m=Wmax,
                        hauteur_dispo_m=Hmax,
                        params=params,
                        poids=poids,
                        charge_ref_n=charge_ref_n,
                        n_ref=n_min,
                        inclure_systeme=inclure_systeme,
                    )
                    if cand["valide_packaging"]:
                        rapport["exploration"].append(cand)
            except Exception as exc:
                rapport["notes_modele"].append(f"Candidat ignoré N={N}, ratio={ratio}: {exc}")
                continue

    if not rapport["exploration"]:
        _push_inconnue(rapport, "impossibles", "solution", "Aucune architecture valide dans le gabarit et sous contraintes.")
        _dedup_inconnues(rapport)
        return rapport

    _normaliser_scores(rapport["exploration"])
    for cand in rapport["exploration"]:
        cand["score_final"] = _score_final(cand, poids)

    rapport["exploration"].sort(key=lambda c: float(c.get("score_final", float("inf"))))
    rapport["meilleur"] = rapport["exploration"][0]

    best_by_arch: Dict[str, Dict[str, Any]] = {}
    for cand in rapport["exploration"]:
        arch = str(cand["architecture"])
        if arch not in best_by_arch:
            best_by_arch[arch] = cand
    rapport["meilleurs_par_architecture"] = best_by_arch

    rapport["notes_modele"].append(
        "L'architecture en étoile/radiale est bien explorée. Elle est courte axialement mais pénalisée en largeur/hauteur et complexité."
    )
    rapport["notes_modele"].append(
        "MultiModulesDC et PistonLibre sont séparés des blocs classiques : les activer avec inclure_systeme=True."
    )
    _dedup_inconnues(rapport)
    return rapport


# =============================================================================
# API compatible avec les anciens modules
# =============================================================================

def evaluer_architecture(
    type_arch: str,
    nb_cylindres: int,
    longueur_dispo_m: float,
    largeur_dispo_m: float,
    cout_maintenance_estime: float = 0.0,
) -> Tuple[float, bool]:
    """
    API compatible avec choix_architecture_optimale.py.
    Ne connaît pas alésage/course : évaluation packaging simplifiée.
    """
    arch = normaliser_architecture(type_arch)
    ok, _notes = architecture_possible(arch, nb_cylindres, inclure_systeme=False)
    if not ok:
        return 9999.0, False

    nb = _require_int("nb_cylindres", nb_cylindres, min_value=1)
    Lmax = _require_positive("longueur_dispo_m", longueur_dispo_m, strict=True)
    Wmax = _require_positive("largeur_dispo_m", largeur_dispo_m, strict=True)
    cout = _require_positive("cout_maintenance_estime", cout_maintenance_estime, strict=False)
    d = ARCHITECTURES[arch]

    pas = 0.15
    largeur_base = 0.40
    if arch == "L":
        L_pkg, W_pkg = nb * pas, largeur_base
    elif arch == "V":
        L_pkg, W_pkg = (nb / 2.0) * pas, 1.50 * largeur_base
    elif arch == "W":
        bancs = 3 if nb % 3 == 0 else 4
        L_pkg, W_pkg = (nb / bancs) * pas, 2.00 * largeur_base
    elif arch == "Etoile":
        L_pkg, W_pkg = 1.50 * pas, 2.50 * largeur_base * (1.0 + 0.025 * max(0, nb - 5))
    elif arch == "Boxer":
        L_pkg, W_pkg = (nb / 2.0) * pas, 2.10 * largeur_base
    else:
        return 9999.0, False

    valide = L_pkg <= Lmax and W_pkg <= Wmax
    score = (L_pkg / Lmax) + (W_pkg / Wmax) + 0.5 * d.complexite + (cout / 1000.0) / max(d.serviceabilite, 0.1)
    if not valide:
        score += 1000.0
    return float(score), bool(valide)


def choix_architecture_optimale(
    nb_cylindres: int,
    L_max: float,
    W_max: float,
    cout_maintenance_estime: float = 0.0,
    *,
    architectures: Sequence[str] = ("L", "V", "W", "Etoile", "Boxer"),
) -> str:
    nb = _require_int("nb_cylindres", nb_cylindres, min_value=1)
    _require_positive("L_max", L_max, strict=True)
    _require_positive("W_max", W_max, strict=True)
    _require_positive("cout_maintenance_estime", cout_maintenance_estime, strict=False)

    best_arch = "Inconnue"
    best_score = float("inf")
    for arch_raw in architectures:
        arch = normaliser_architecture(arch_raw)
        ok, _notes = architecture_possible(arch, nb, inclure_systeme=False)
        if not ok:
            continue
        score, valide = evaluer_architecture(arch, nb, L_max, W_max, cout_maintenance_estime)
        if valide and score < best_score:
            best_score = score
            best_arch = arch
    return best_arch


def resoudre_architecture_globale(
    puissance_cible_w: float,
    regime_tr_min: float,
    pme_pa: float,
    vitesse_piston_max_ms: float,
    L_max_m: float,
    W_max_m: float,
    horizon_usage_h: float = 20_000.0,
) -> Dict[str, Any]:
    params = replace(ParametresArchitectureSTHOME(), horizon_usage_h=float(horizon_usage_h))
    rapport = explorer_architectures(
        puissance_cible_w=puissance_cible_w,
        regime_tr_min=regime_tr_min,
        pme_pa=pme_pa,
        vitesse_piston_max_ms=vitesse_piston_max_ms,
        longueur_dispo_m=L_max_m,
        largeur_dispo_m=W_max_m,
        params=params,
    )
    best = rapport.get("meilleur") or {}
    return {
        "N_cyl": best.get("nb_cylindres"),
        "Architecture": best.get("architecture"),
        "Score": best.get("score_final"),
        "Cout_Maint_Estime": (best.get("indices") or {}).get("cout_maintenance_eur"),
        "Bore_mm": best.get("alesage_mm"),
        "Course_mm": best.get("course_mm"),
        "Ratio_Sur_B": best.get("ratio_S_B"),
        "rapport_complet": rapport,
    }


@dataclass(frozen=True)
class Architecture:
    params: ParametresArchitectureSTHOME = ParametresArchitectureSTHOME()
    poids: PoidsScoreArchitecture = PoidsScoreArchitecture()

    def analyser(
        self,
        *,
        puissance_cible_w: Optional[float] = None,
        regime_tr_min: Optional[float] = None,
        pme_pa: Optional[float] = None,
        vitesse_piston_max_ms: Optional[float] = None,
        longueur_dispo_m: Optional[float] = None,
        largeur_dispo_m: Optional[float] = None,
        hauteur_dispo_m: Optional[float] = None,
        architectures_autorisees: Optional[Sequence[Any]] = None,
        architecture_forcee: Optional[Any] = None,
        inclure_systeme: bool = False,
        horizon_usage_h: Optional[float] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "mode_analyse": "architecture_sthome_complete",
            "inconnues": {"impossibles": [], "partielles": []},
        }
        for nom, val in {
            "puissance_cible_w": puissance_cible_w,
            "regime_tr_min": regime_tr_min,
            "pme_pa": pme_pa,
            "vitesse_piston_max_ms": vitesse_piston_max_ms,
            "longueur_dispo_m": longueur_dispo_m,
            "largeur_dispo_m": largeur_dispo_m,
        }.items():
            if val is None:
                _push_inconnue(rapport, "impossibles", nom, "Entrée requise pour explorer les architectures.")
        if rapport["inconnues"]["impossibles"]:
            _dedup_inconnues(rapport)
            return rapport

        params = self.params
        if horizon_usage_h is not None:
            params = replace(params, horizon_usage_h=float(horizon_usage_h))

        return explorer_architectures(
            puissance_cible_w=float(puissance_cible_w),
            regime_tr_min=float(regime_tr_min),
            pme_pa=float(pme_pa),
            vitesse_piston_max_ms=float(vitesse_piston_max_ms),
            longueur_dispo_m=float(longueur_dispo_m),
            largeur_dispo_m=float(largeur_dispo_m),
            hauteur_dispo_m=float(hauteur_dispo_m) if hauteur_dispo_m is not None else None,
            architectures_autorisees=architectures_autorisees,
            architecture_forcee=architecture_forcee,
            inclure_systeme=inclure_systeme,
            params=params,
            poids=self.poids,
        )


if __name__ == "__main__":
    # Exemple minimal : 100 kW à 3000 tr/min, PME 8 bar, Up max 8 m/s, gabarit 1.2 x 1.0 x 0.9 m.
    rep = Architecture().analyser(
        puissance_cible_w=100_000,
        regime_tr_min=3000,
        pme_pa=800_000,
        vitesse_piston_max_ms=8.0,
        longueur_dispo_m=1.20,
        largeur_dispo_m=1.00,
        hauteur_dispo_m=0.90,
    )
    best = rep.get("meilleur") or {}
    print({
        "meilleur": best.get("architecture"),
        "N": best.get("nb_cylindres"),
        "bore_mm": best.get("alesage_mm"),
        "course_mm": best.get("course_mm"),
        "score": best.get("score_final"),
        "meilleurs_par_arch": list((rep.get("meilleurs_par_architecture") or {}).keys()),
    })
