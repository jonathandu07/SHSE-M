# backend/components/moteur_thermique.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Tuple, List
import math


# ============================================================
# Imports des modules "moteur_thermique" (robustes)
# ============================================================

try:
    from backend.modules.moteur_thermique.calcul_cylindree import (
        calcul_cylindree_unitaire,
        calcul_cylindree_totale,
        calcul_epaisseur_cylindre_mince,
        calcul_epaisseur_cylindre_lame,
    )
    from backend.modules.moteur_thermique.calcul_travail_indique import (
        calcul_travail_indique_pme,
        calcul_puissance_indiquee,
    )
    from backend.modules.moteur_thermique.calcul_gaz import (
        calcul_force_gaz,
        calcul_pression_gaz_parfait,
        calcul_temperature_compression_adiabatique,
        calcul_debit_fuite_annulaire,
        calcul_masse_fuite,
    )
    from backend.modules.moteur_thermique.calcul_force_inertie import (
        calcul_force_inertie_alternative,
    )
    from backend.modules.moteur_thermique.calcul_couple_vilebrequin import (
        calcul_couple_instantane,
    )
    from backend.modules.moteur_thermique.calcul_pertes_frottement import (
        calcul_puissance_frottement_segment,
        calcul_puissance_frottement_palier,
    )
    from backend.modules.moteur_thermique.calcul_precharge_vis import (
        calcul_force_separation,
        calcul_precharge_vis_totale,
        calcul_couple_serrage,
    )
    from backend.modules.moteur_thermique.calcul_vitesse_piston import (
        calcul_vitesse_moyenne_piston,
    )
    from backend.modules.moteur_thermique.calcul_usure_archard import (
        calcul_volume_usure_archard,
        calcul_perte_epaisseur,
    )
except Exception:
    from backend.modules.moteur_thermique.calcul_cylindree import (
        calcul_cylindree_unitaire,
        calcul_cylindree_totale,
        calcul_epaisseur_cylindre_mince,
        calcul_epaisseur_cylindre_lame,
    )
    from backend.modules.moteur_thermique.calcul_travail_indique import (
        calcul_travail_indique_pme,
        calcul_puissance_indiquee,
    )
    from backend.modules.moteur_thermique.calcul_gaz import (
        calcul_force_gaz,
        calcul_pression_gaz_parfait,
        calcul_temperature_compression_adiabatique,
        calcul_debit_fuite_annulaire,
        calcul_masse_fuite,
    )
    from backend.modules.moteur_thermique.calcul_force_inertie import (
        calcul_force_inertie_alternative,
    )
    from backend.modules.moteur_thermique.calcul_couple_vilebrequin import (
        calcul_couple_instantane,
    )
    from backend.modules.moteur_thermique.calcul_pertes_frottement import (
        calcul_puissance_frottement_segment,
        calcul_puissance_frottement_palier,
    )
    from backend.modules.moteur_thermique.calcul_precharge_vis import (
        calcul_force_separation,
        calcul_precharge_vis_totale,
        calcul_couple_serrage,
    )
    from backend.modules.moteur_thermique.calcul_vitesse_piston import (
        calcul_vitesse_moyenne_piston,
    )
    from backend.modules.moteur_thermique.calcul_usure_archard import (
        calcul_volume_usure_archard,
        calcul_perte_epaisseur,
    )


# ============================================================
# Imports des modules "architecture" (pour DÉFINIR le moteur)
# ============================================================

_ARCHI_OK = True
try:
    from backend.modules.architecture.calcul_cylindree_totale import (
        calcul_cylindree_totale_requise,
    )
    from backend.modules.architecture.calcul_cylindree_admissible import (
        calcul_bore_max_admissible,
        calcul_cylindree_unit_max,
    )
    from backend.modules.architecture.calcul_nombre_cylindres_min import (
        calcul_nombre_cylindres_min,
    )
    from backend.modules.architecture.choix_architecture_optimale import (
        choix_architecture_optimale,
        evaluer_architecture,
    )
except Exception:
    _ARCHI_OK = False


# ============================================================
# Helpers
# ============================================================

TempsMoteur = Literal[2, 4]
TypePuissance = Literal["indiquee", "frein"]
ArchitectureType = Literal["L", "V", "W", "Etoile"]


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _require_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_positive(name: str, x: Any, *, strictly: bool = True) -> float:
    x = _require_finite(name, x)
    ok = x > 0.0 if strictly else x >= 0.0
    if not ok:
        op = ">" if strictly else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {x}).")
    return x


def _require_between_0_1(name: str, x: Any, *, allow_1: bool = True) -> float:
    v = _require_finite(name, x)
    if allow_1:
        ok = (v > 0.0) and (v <= 1.0)
    else:
        ok = (v > 0.0) and (v < 1.0)
    if not ok:
        raise ValueError(f"{name} doit être dans ]0,1]{' ' if allow_1 else ''}(reçu: {v}).")
    return v


def _require_int_pos(name: str, x: Any) -> int:
    if not isinstance(x, int) or x <= 0:
        raise ValueError(f"{name} doit être un entier > 0 (reçu: {x!r}).")
    return int(x)


def _omega_from_rpm(rpm: float) -> float:
    return (2.0 * math.pi * rpm) / 60.0


def _cycles_par_seconde(rpm: float, temps_moteur: int) -> float:
    cps = rpm / 60.0
    if temps_moteur == 4:
        cps /= 2.0
    return cps


def _rpm_from_power_torque(power_w: float, torque_nm: float) -> float:
    P = _require_finite("power_w", power_w)
    T = _require_finite("torque_nm", torque_nm)
    if T == 0.0:
        raise ValueError("torque_nm ne peut pas être 0 (division).")
    return (P / T) * (60.0 / (2.0 * math.pi))


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport["inconnues"][categorie].append({"nom": nom, "raison": raison})


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    def dedup(lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set[Tuple[str, str]] = set()
        out: List[Dict[str, Any]] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out

    rapport["inconnues"]["impossibles"] = dedup(rapport["inconnues"]["impossibles"])
    rapport["inconnues"]["partielles"] = dedup(rapport["inconnues"]["partielles"])


def _archard_depuis_vitesse(
    *,
    k: Optional[float],
    W_n: Optional[float],
    v_ms: Optional[float],
    H_pa: Optional[float],
    aire_contact_m2: Optional[float],
) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {
        "dV_dt_m3_s": None,
        "dh_dt_m_s": None,
        "dV_par_heure_m3_h": None,
        "dh_par_heure_m_h": None,
    }
    if k is None or W_n is None or v_ms is None or H_pa is None:
        return out

    V_1s = calcul_volume_usure_archard(
        coefficient_usure_k=k,
        charge_normale_w=W_n,
        distance_glissement_ls=max(0.0, float(v_ms)),
        durete_h=H_pa,
    )
    out["dV_dt_m3_s"] = float(V_1s)
    out["dV_par_heure_m3_h"] = float(V_1s) * 3600.0

    if aire_contact_m2 is not None:
        dh_1s = calcul_perte_epaisseur(volume_use_m3=V_1s, aire_contact_m2=aire_contact_m2)
        out["dh_dt_m_s"] = float(dh_1s)
        out["dh_par_heure_m_h"] = float(dh_1s) * 3600.0

    return out


def _bore_stroke_from_Vd_ratio(Vd_m3: float, ratio_course_alesage: float) -> Tuple[float, float]:
    Vd = _require_positive("Vd_m3", Vd_m3, strictly=True)
    r = _require_positive("ratio_course_alesage", ratio_course_alesage, strictly=True)
    B = (4.0 * Vd / (math.pi * r)) ** (1.0 / 3.0)
    S = r * B
    return float(B), float(S)


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    if not _is_finite(a) or not _is_finite(b):
        return None
    if float(b) == 0.0:
        return None
    return float(a) / float(b)


def _clamp01(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    return max(0.0, min(1.0, float(x)))


def _facteur_complexite_architecture(architecture: Optional[str]) -> Optional[float]:
    if architecture is None:
        return None
    a = str(architecture)
    mapping = {
        "L": 1.00,
        "V": 1.10,
        "W": 1.25,
        "Etoile": 1.35,
    }
    return mapping.get(a)


def _estimer_indice_maintenance(
    *,
    nombre_cylindres: Optional[int],
    architecture: Optional[str],
) -> Optional[float]:
    """
    Proxy déterministe et EXPLICITE :
    - plus il y a de cylindres, plus l'entretien est lourd ;
    - certaines architectures sont plus complexes d'accès/assemblage.

    Cet indice n'est PAS une vérité industrielle universelle.
    Il sert uniquement d'indice de complexité de maintenance relatif.
    Plus l'indice est faible, mieux c'est.
    """
    if nombre_cylindres is None or nombre_cylindres <= 0:
        return None
    f_arch = _facteur_complexite_architecture(architecture)
    if f_arch is None:
        return None
    return float(nombre_cylindres) * f_arch


def _estimer_masse_cylindres(
    *,
    alesage_m: Optional[float],
    course_m: Optional[float],
    nombre_cylindres: Optional[int],
    epaisseur_paroi_m: Optional[float],
    densite_materiau_kg_m3: Optional[float],
    facteur_longueur_masse: float = 1.15,
) -> Dict[str, Optional[float]]:
    """
    Estimation volontairement bornée et expliquée :
    - masse de virole de cylindre seule,
    - longueur prise = course * facteur_longueur_masse,
    - n'inclut pas culasse, carter, ailettes, renforts, goujons, paliers, vilebrequin.

    Le but est d'obtenir une estimation de matière minimale pour arbitrage.
    """
    out = {
        "volume_matiere_total_m3": None,
        "masse_estimee_kg": None,
        "notes": None,
    }
    if (
        alesage_m is None
        or course_m is None
        or nombre_cylindres is None
        or epaisseur_paroi_m is None
        or densite_materiau_kg_m3 is None
    ):
        return out
    if alesage_m <= 0.0 or course_m <= 0.0 or nombre_cylindres <= 0 or epaisseur_paroi_m < 0.0 or densite_materiau_kg_m3 < 0.0:
        return out

    ri = 0.5 * alesage_m
    re = ri + epaisseur_paroi_m
    longueur = course_m * facteur_longueur_masse

    volume_unitaire = math.pi * (re * re - ri * ri) * longueur
    volume_total = volume_unitaire * float(nombre_cylindres)
    masse = volume_total * densite_materiau_kg_m3

    out["volume_matiere_total_m3"] = float(volume_total)
    out["masse_estimee_kg"] = float(masse)
    out["notes"] = (
        "Estimation de masse limitée aux viroles de cylindres. "
        "Ne comprend ni culasse, ni carter, ni vilebrequin, ni bielles, ni fixations."
    )
    return out


def _estimer_cout_matiere(
    *,
    masse_kg: Optional[float],
    cout_matiere_eur_kg: Optional[float],
) -> Optional[float]:
    if masse_kg is None or cout_matiere_eur_kg is None:
        return None
    if masse_kg < 0.0 or cout_matiere_eur_kg < 0.0:
        return None
    return float(masse_kg) * float(cout_matiere_eur_kg)


def _booleen_contrainte_max(
    *,
    valeur: Optional[float],
    limite_max: Optional[float],
) -> Optional[bool]:
    if valeur is None or limite_max is None:
        return None
    return float(valeur) <= float(limite_max)


def _booleen_contrainte_min(
    *,
    valeur: Optional[float],
    limite_min: Optional[float],
) -> Optional[bool]:
    if valeur is None or limite_min is None:
        return None
    return float(valeur) >= float(limite_min)


# ============================================================
# Composant moteur thermique (calcul + définition)
# ============================================================

@dataclass(frozen=True)
class MoteurThermique:
    """
    - analyser_point_de_fonctionnement(): calcule un point (forces, couple, pertes, usure, etc.)
    - definir_depuis_exigences(): définit un moteur (B, S, N, archi) UNIQUEMENT si calculable.
      Si une info manque, elle est listée comme inconnue et AUCUNE valeur n'est inventée.

    Ajout important :
    - le moteur peut désormais être défini aussi par des critères de conception explicites :
      fiabilité / rendement / masse / maintenance / coût.
    - lorsque ces critères ne sont pas entièrement calculables, le rapport le dit explicitement.
    """

    # --- Géométrie de base ---
    alesage_m: Optional[float] = None
    course_m: Optional[float] = None
    nombre_cylindres: int = 1
    temps_moteur: TempsMoteur = 4
    architecture: Optional[str] = None

    # --- Point nominal / définition ---
    rpm_nominal: Optional[float] = None
    pme_nominale_pa: Optional[float] = None
    puissance_nominale_visee_w: Optional[float] = None
    type_puissance_nominale: Optional[TypePuissance] = None
    rendement_mecanique_nominal: Optional[float] = None
    pression_max_pa: Optional[float] = None

    # --- Cinématique bielle-manivelle (pour inertie) ---
    longueur_bielle_m: Optional[float] = None
    rayon_manivelle_m: Optional[float] = None
    masse_alternative_kg: Optional[float] = None

    # --- Dimensionnement cylindre / matériau ---
    contrainte_admissible_pa: Optional[float] = None
    facteur_securite_cylindre: float = 1.5
    densite_materiau_kg_m3: Optional[float] = None
    cout_matiere_eur_kg: Optional[float] = None

    # --- Critères de projet / cahier des charges ---
    rendement_indique_cible_min: Optional[float] = None
    rendement_mecanique_cible_min: Optional[float] = None
    masse_estimee_max_kg: Optional[float] = None
    cout_matiere_max_eur: Optional[float] = None
    indice_maintenance_max: Optional[float] = None
    duree_vie_cible_h: Optional[float] = None

    # --- Fuite ---
    viscosite_pa_s: Optional[float] = None
    densite_kg_m3: Optional[float] = None

    # --- Frottements ---
    coef_frottement_segment: Optional[float] = None
    coef_frottement_palier: Optional[float] = None

    # --- Usure Archard ---
    coefficient_usure_segment_k: Optional[float] = None
    durete_contact_segment_pa: Optional[float] = None
    aire_contact_segment_m2: Optional[float] = None

    coefficient_usure_palier_k: Optional[float] = None
    durete_contact_palier_pa: Optional[float] = None
    aire_contact_palier_m2: Optional[float] = None

    # --- Précharge vis (couvercle) ---
    facteur_securite_vis: float = 1.5
    facteur_frottement_vis_k: float = 0.2

    clamp_non_negative: bool = True

    # ============================================================
    # DÉFINITION DU MOTEUR PAR LE CALCUL (aucune invention)
    # ============================================================

    @classmethod
    def definir_depuis_exigences(
        cls,
        *,
        # Besoin de performance
        puissance_visee_w: Optional[float],
        type_puissance: TypePuissance,
        rpm: Optional[float],
        pression_moyenne_effective_pa: Optional[float],
        temps_moteur: TempsMoteur,

        # Pour convertir "frein" -> "indiquée" si nécessaire
        rendement_mecanique: Optional[float] = None,

        # Contraintes de dimensionnement dynamique/géométrique
        vitesse_piston_max_ms: Optional[float] = None,
        ratio_course_alesage_max: Optional[float] = None,

        # Si tu veux une géométrie unique
        ratio_course_alesage_cible: Optional[float] = None,

        # Packaging / architecture
        L_max_m: Optional[float] = None,
        W_max_m: Optional[float] = None,
        architectures_autorisees: Optional[Tuple[str, ...]] = None,
        architecture_forcee: Optional[str] = None,

        # Critères de fiabilité / efficience / masse / coût / maintenance
        pression_max_pa: Optional[float] = None,
        contrainte_admissible_pa: Optional[float] = None,
        facteur_securite_cylindre: float = 1.5,
        densite_materiau_kg_m3: Optional[float] = None,
        cout_matiere_eur_kg: Optional[float] = None,
        rendement_indique_cible_min: Optional[float] = None,
        rendement_mecanique_cible_min: Optional[float] = None,
        masse_estimee_max_kg: Optional[float] = None,
        cout_matiere_max_eur: Optional[float] = None,
        indice_maintenance_max: Optional[float] = None,
        duree_vie_cible_h: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Retourne un rapport complet :
        - moteur_defini: instance cls(...) si et seulement si B,S,N sont calculables
        - sinon: moteur_defini = None + liste d'inconnues

        Aucune valeur n'est supposée si non fournie.
        Les critères de conception sont portés ici et vérifiés quand ils sont calculables.
        """
        rapport: Dict[str, Any] = {
            "entrees": {},
            "dimensionnement": {},
            "architecture": {},
            "criteres_conception": {},
            "evaluation_conception": {},
            "estimations": {},
            "moteur_defini": None,
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        rapport["entrees"].update(
            {
                "puissance_visee_w": puissance_visee_w,
                "type_puissance": type_puissance,
                "rpm": rpm,
                "pression_moyenne_effective_pa": pression_moyenne_effective_pa,
                "temps_moteur": int(temps_moteur),
                "rendement_mecanique": rendement_mecanique,
                "vitesse_piston_max_ms": vitesse_piston_max_ms,
                "ratio_course_alesage_max": ratio_course_alesage_max,
                "ratio_course_alesage_cible": ratio_course_alesage_cible,
                "L_max_m": L_max_m,
                "W_max_m": W_max_m,
                "architectures_autorisees": architectures_autorisees,
                "architecture_forcee": architecture_forcee,
                "pression_max_pa": pression_max_pa,
                "contrainte_admissible_pa": contrainte_admissible_pa,
                "facteur_securite_cylindre": facteur_securite_cylindre,
                "densite_materiau_kg_m3": densite_materiau_kg_m3,
                "cout_matiere_eur_kg": cout_matiere_eur_kg,
                "rendement_indique_cible_min": rendement_indique_cible_min,
                "rendement_mecanique_cible_min": rendement_mecanique_cible_min,
                "masse_estimee_max_kg": masse_estimee_max_kg,
                "cout_matiere_max_eur": cout_matiere_max_eur,
                "indice_maintenance_max": indice_maintenance_max,
                "duree_vie_cible_h": duree_vie_cible_h,
                "modules_architecture_disponibles": _ARCHI_OK,
            }
        )

        rapport["criteres_conception"].update(
            {
                "objectif_fiabilite": {
                    "pression_max_pa": pression_max_pa,
                    "contrainte_admissible_pa": contrainte_admissible_pa,
                    "facteur_securite_cylindre": facteur_securite_cylindre,
                    "vitesse_piston_max_ms": vitesse_piston_max_ms,
                    "duree_vie_cible_h": duree_vie_cible_h,
                },
                "objectif_efficience": {
                    "type_puissance": type_puissance,
                    "rendement_mecanique_entree": rendement_mecanique,
                    "rendement_indique_cible_min": rendement_indique_cible_min,
                    "rendement_mecanique_cible_min": rendement_mecanique_cible_min,
                },
                "objectif_masse": {
                    "densite_materiau_kg_m3": densite_materiau_kg_m3,
                    "masse_estimee_max_kg": masse_estimee_max_kg,
                },
                "objectif_cout": {
                    "cout_matiere_eur_kg": cout_matiere_eur_kg,
                    "cout_matiere_max_eur": cout_matiere_max_eur,
                },
                "objectif_maintenance": {
                    "indice_maintenance_max": indice_maintenance_max,
                },
            }
        )

        if not _ARCHI_OK:
            _push_inconnue(
                rapport,
                "impossibles",
                "dimensionnement global (architecture)",
                "Modules backend.modules.architecture.* indisponibles : impossible de définir B/S/N par ces calculs.",
            )
            _dedup_inconnues(rapport)
            return rapport

        # --- validations minimales ---
        if puissance_visee_w is None:
            _push_inconnue(rapport, "impossibles", "puissance_visee_w", "Obligatoire pour dimensionner la cylindrée requise.")
        if rpm is None:
            _push_inconnue(rapport, "impossibles", "rpm", "Obligatoire pour la fréquence de cycle et les contraintes piston.")
        if pression_moyenne_effective_pa is None:
            _push_inconnue(rapport, "impossibles", "pression_moyenne_effective_pa", "Obligatoire pour relier puissance <-> cylindrée.")
        if vitesse_piston_max_ms is None:
            _push_inconnue(rapport, "impossibles", "vitesse_piston_max_ms", "Obligatoire pour borner le dimensionnement (cinématique).")
        if ratio_course_alesage_max is None:
            _push_inconnue(rapport, "impossibles", "ratio_course_alesage_max", "Obligatoire pour borner la géométrie (S/B).")

        if rapport["inconnues"]["impossibles"]:
            _dedup_inconnues(rapport)
            return rapport

        # --- validations des objectifs si fournis ---
        if rendement_mecanique is not None:
            _require_between_0_1("rendement_mecanique", rendement_mecanique, allow_1=True)
        if rendement_indique_cible_min is not None:
            _require_between_0_1("rendement_indique_cible_min", rendement_indique_cible_min, allow_1=True)
        if rendement_mecanique_cible_min is not None:
            _require_between_0_1("rendement_mecanique_cible_min", rendement_mecanique_cible_min, allow_1=True)
        if densite_materiau_kg_m3 is not None:
            _require_positive("densite_materiau_kg_m3", densite_materiau_kg_m3, strictly=False)
        if cout_matiere_eur_kg is not None:
            _require_positive("cout_matiere_eur_kg", cout_matiere_eur_kg, strictly=False)
        if masse_estimee_max_kg is not None:
            _require_positive("masse_estimee_max_kg", masse_estimee_max_kg, strictly=False)
        if cout_matiere_max_eur is not None:
            _require_positive("cout_matiere_max_eur", cout_matiere_max_eur, strictly=False)
        if indice_maintenance_max is not None:
            _require_positive("indice_maintenance_max", indice_maintenance_max, strictly=False)
        if duree_vie_cible_h is not None:
            _require_positive("duree_vie_cible_h", duree_vie_cible_h, strictly=False)
        if contrainte_admissible_pa is not None:
            _require_positive("contrainte_admissible_pa", contrainte_admissible_pa, strictly=True)
        if pression_max_pa is not None:
            _require_positive("pression_max_pa", pression_max_pa, strictly=False)
        _require_positive("facteur_securite_cylindre", facteur_securite_cylindre, strictly=True)

        # --- conversion puissance frein -> indiquée ---
        P_visee = _require_positive("puissance_visee_w", puissance_visee_w, strictly=True)
        if type_puissance == "frein":
            if rendement_mecanique is None:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "rendement_mecanique",
                    "Nécessaire pour convertir une puissance frein en puissance indiquée (P_i = P_frein / η_meca).",
                )
                _dedup_inconnues(rapport)
                return rapport
            eta_m = _require_between_0_1("rendement_mecanique", rendement_mecanique, allow_1=True)
            P_indiquee = P_visee / eta_m
        else:
            P_indiquee = P_visee
            eta_m = rendement_mecanique

        # --- fréquence de cycles ---
        rpm_val = _require_positive("rpm", rpm, strictly=True)
        freq_cycle_hz = _cycles_par_seconde(rpm_val, int(temps_moteur))

        # --- cylindrée totale requise ---
        pme = _require_positive("pression_moyenne_effective_pa", pression_moyenne_effective_pa, strictly=True)
        Vd_tot_req = float(
            calcul_cylindree_totale_requise(
                puissance_w=P_indiquee,
                pression_moyenne_effective_pa=pme,
                frequence_cycle_hz=freq_cycle_hz,
                rendement_mecanique=1.0,
            )
        )

        # --- cylindrée unitaire max admissible ---
        Umax = _require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strictly=False)
        r_max = _require_positive("ratio_course_alesage_max", ratio_course_alesage_max, strictly=True)

        bore_max_m = float(calcul_bore_max_admissible(Umax, rpm_val, r_max))
        Vd_unit_max = float(calcul_cylindree_unit_max(bore_max_m, r_max))

        if Vd_unit_max <= 0.0:
            _push_inconnue(
                rapport,
                "impossibles",
                "cylindree_unitaire_max",
                "Le calcul donne une cylindrée unitaire max <= 0 (vérifie Umax, rpm, r_max).",
            )
            _dedup_inconnues(rapport)
            return rapport

        # --- nombre de cylindres minimal ---
        n_min = int(calcul_nombre_cylindres_min(Vd_tot_req, Vd_unit_max))
        Vd_unit_limite = Vd_tot_req / float(n_min)

        # --- géométrie unitaire ---
        bore_m: Optional[float] = None
        stroke_m: Optional[float] = None
        ratio_utilise: Optional[float] = None

        if ratio_course_alesage_cible is not None:
            r_cible = _require_positive("ratio_course_alesage_cible", ratio_course_alesage_cible, strictly=True)
            if r_cible > r_max:
                raise ValueError(
                    f"ratio_course_alesage_cible ({r_cible}) > ratio_course_alesage_max ({r_max}) : incohérent."
                )
            bore_m, stroke_m = _bore_stroke_from_Vd_ratio(Vd_unit_limite, r_cible)
            ratio_utilise = r_cible
        else:
            bore_m, stroke_m = _bore_stroke_from_Vd_ratio(Vd_unit_limite, r_max)
            ratio_utilise = r_max
            rapport["notes_modele"].append(
                "Géométrie définie avec ratio_course_alesage = ratio_course_alesage_max "
                "(dimensionnement aux limites, déterministe). "
                "Si tu veux une autre géométrie, fournis ratio_course_alesage_cible."
            )

        # --- vérification vitesse moyenne piston ---
        v_piston_moy = 2.0 * float(stroke_m) * (rpm_val / 60.0)
        if v_piston_moy > Umax + 1e-12:
            raise ValueError(
                f"Incohérence: vitesse moyenne piston {v_piston_moy:.6g} m/s > Umax {Umax:.6g} m/s "
                f"(stroke={stroke_m}, rpm={rpm_val})."
            )

        reserve_vitesse_piston = None
        if Umax > 0.0:
            reserve_vitesse_piston = 1.0 - (v_piston_moy / Umax)

        # --- architecture ---
        archi_choisie: Optional[str] = None
        details_archis: Dict[str, Any] = {}

        if architecture_forcee is not None:
            archi_choisie = str(architecture_forcee)
            rapport["notes_modele"].append(
                "Architecture imposée par l'entrée utilisateur ; aucun arbitrage automatique n'a été réalisé."
            )
        else:
            if L_max_m is None or W_max_m is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "choix architecture",
                    "Calculable si L_max_m et W_max_m sont fournis (sinon pas de sélection L/V/W/Étoile).",
                )
            else:
                Lm = _require_positive("L_max_m", L_max_m, strictly=True)
                Wm = _require_positive("W_max_m", W_max_m, strictly=True)

                archis = architectures_autorisees or ("L", "V", "W", "Etoile")
                for a in archis:
                    try:
                        details_archis[str(a)] = evaluer_architecture(str(a), n_min, Lm, Wm)
                    except Exception as e:
                        details_archis[str(a)] = {"erreur": str(e)}

                try:
                    archi_choisie = str(choix_architecture_optimale(n_min, Lm, Wm))
                except Exception as e:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "choix architecture",
                        f"Échec du module de choix d'architecture: {e}",
                    )

        # --- fiabilité / masse / coût : ce qui est réellement calculable ici ---
        epaisseur_cylindre_mince = None
        epaisseur_cylindre_lame = None
        epaisseur_cylindre_retenue = None

        if (
            pression_max_pa is not None
            and contrainte_admissible_pa is not None
            and bore_m is not None
        ):
            ri = 0.5 * bore_m
            epaisseur_cylindre_mince = float(
                calcul_epaisseur_cylindre_mince(
                    pression_pa=_require_positive("pression_max_pa", pression_max_pa, strictly=False),
                    rayon_interne_m=ri,
                    contrainte_admissible_pa=_require_positive("contrainte_admissible_pa", contrainte_admissible_pa, strictly=True),
                    include_longitudinale=False,
                    facteur_securite=_require_positive("facteur_securite_cylindre", facteur_securite_cylindre, strictly=True),
                    clamp_non_negative=True,
                    return_details=False,
                )
            )
            epaisseur_cylindre_lame = float(
                calcul_epaisseur_cylindre_lame(
                    pression_interne_pa=_require_positive("pression_max_pa", pression_max_pa, strictly=False),
                    rayon_interne_m=ri,
                    contrainte_admissible_pa=_require_positive("contrainte_admissible_pa", contrainte_admissible_pa, strictly=True),
                    facteur_securite=_require_positive("facteur_securite_cylindre", facteur_securite_cylindre, strictly=True),
                    clamp_non_negative=True,
                    return_details=False,
                )
            )
            epaisseur_cylindre_retenue = max(epaisseur_cylindre_mince, epaisseur_cylindre_lame)
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "épaisseur cylindre de définition",
                "Calculable si pression_max_pa et contrainte_admissible_pa sont fournis.",
            )

        estimation_masse = _estimer_masse_cylindres(
            alesage_m=bore_m,
            course_m=stroke_m,
            nombre_cylindres=n_min,
            epaisseur_paroi_m=epaisseur_cylindre_retenue,
            densite_materiau_kg_m3=densite_materiau_kg_m3,
        )
        masse_estimee_kg = estimation_masse["masse_estimee_kg"]
        cout_matiere_estime_eur = _estimer_cout_matiere(
            masse_kg=masse_estimee_kg,
            cout_matiere_eur_kg=cout_matiere_eur_kg,
        )
        indice_maintenance = _estimer_indice_maintenance(
            nombre_cylindres=n_min,
            architecture=archi_choisie,
        )

        if densite_materiau_kg_m3 is None:
            _push_inconnue(
                rapport,
                "partielles",
                "masse estimée",
                "Calculable si densite_materiau_kg_m3 est fournie, en plus de la pression max et de la contrainte admissible.",
            )
        if cout_matiere_eur_kg is None:
            _push_inconnue(
                rapport,
                "partielles",
                "coût matière estimé",
                "Calculable si cout_matiere_eur_kg est fourni, en plus de la masse estimée.",
            )
        if archi_choisie is None:
            _push_inconnue(
                rapport,
                "partielles",
                "indice de maintenance",
                "Calculable si l'architecture du moteur est connue.",
            )

        # --- évaluations de conformité aux objectifs ---
        ok_masse = _booleen_contrainte_max(valeur=masse_estimee_kg, limite_max=masse_estimee_max_kg)
        ok_cout = _booleen_contrainte_max(valeur=cout_matiere_estime_eur, limite_max=cout_matiere_max_eur)
        ok_maintenance = _booleen_contrainte_max(valeur=indice_maintenance, limite_max=indice_maintenance_max)
        ok_rendement_meca = _booleen_contrainte_min(valeur=eta_m, limite_min=rendement_mecanique_cible_min)

        if rendement_indique_cible_min is not None:
            _push_inconnue(
                rapport,
                "partielles",
                "validation rendement indiqué cible",
                "Ce script ne peut pas conclure sur un rendement indiqué réel sans cycle thermodynamique complet ou données indicatrices.",
            )

        if duree_vie_cible_h is not None:
            _push_inconnue(
                rapport,
                "partielles",
                "validation durée de vie cible",
                "La durée de vie cible exige ensuite les calculs d'usure, fatigue, matériaux, états de surface et historique de charge.",
            )

        rapport["dimensionnement"].update(
            {
                "P_indiquee_calculee_W": float(P_indiquee),
                "frequence_cycle_hz": float(freq_cycle_hz),
                "Vd_totale_requise_m3": float(Vd_tot_req),
                "bore_max_admissible_m": float(bore_max_m),
                "Vd_unitaire_max_m3": float(Vd_unit_max),
                "nombre_cylindres_min": int(n_min),
                "Vd_unitaire_choisie_m3": float(Vd_unit_limite),
                "ratio_course_alesage_utilise": float(ratio_utilise) if ratio_utilise is not None else None,
                "alesage_defini_m": float(bore_m) if bore_m is not None else None,
                "course_definie_m": float(stroke_m) if stroke_m is not None else None,
                "vitesse_moyenne_piston_ms": float(v_piston_moy),
                "reserve_vitesse_piston_fraction": float(reserve_vitesse_piston) if reserve_vitesse_piston is not None else None,
                "epaisseur_cylindre_mince_m": float(epaisseur_cylindre_mince) if epaisseur_cylindre_mince is not None else None,
                "epaisseur_cylindre_lame_m": float(epaisseur_cylindre_lame) if epaisseur_cylindre_lame is not None else None,
                "epaisseur_cylindre_retenue_m": float(epaisseur_cylindre_retenue) if epaisseur_cylindre_retenue is not None else None,
            }
        )

        rapport["architecture"].update(
            {
                "details_par_architecture": details_archis,
                "architecture_choisie": archi_choisie,
            }
        )

        rapport["estimations"].update(
            {
                "masse": estimation_masse,
                "cout_matiere_estime_eur": float(cout_matiere_estime_eur) if cout_matiere_estime_eur is not None else None,
                "indice_maintenance": float(indice_maintenance) if indice_maintenance is not None else None,
            }
        )

        rapport["evaluation_conception"].update(
            {
                "respecte_masse_max": ok_masse,
                "respecte_cout_matiere_max": ok_cout,
                "respecte_indice_maintenance_max": ok_maintenance,
                "respecte_rendement_mecanique_min": ok_rendement_meca,
                "rendement_indique_reel_verifiable": None,
                "duree_vie_cible_verifiable": None,
                "commentaires": [
                    "Les conformités rendements/masse/coût/maintenance sont évaluées uniquement quand les données nécessaires existent.",
                    "La fiabilité complète ne peut pas être validée ici sans la suite des pièces et des lois de fatigue/usure détaillées.",
                ],
            }
        )

        # --- moteur défini ---
        moteur = cls(
            alesage_m=float(bore_m),
            course_m=float(stroke_m),
            nombre_cylindres=int(n_min),
            temps_moteur=temps_moteur,
            architecture=archi_choisie,
            rpm_nominal=float(rpm_val),
            pme_nominale_pa=float(pme),
            puissance_nominale_visee_w=float(P_visee),
            type_puissance_nominale=type_puissance,
            rendement_mecanique_nominal=float(eta_m) if eta_m is not None else None,
            pression_max_pa=float(pression_max_pa) if pression_max_pa is not None else None,
            contrainte_admissible_pa=float(contrainte_admissible_pa) if contrainte_admissible_pa is not None else None,
            facteur_securite_cylindre=float(facteur_securite_cylindre),
            densite_materiau_kg_m3=float(densite_materiau_kg_m3) if densite_materiau_kg_m3 is not None else None,
            cout_matiere_eur_kg=float(cout_matiere_eur_kg) if cout_matiere_eur_kg is not None else None,
            rendement_indique_cible_min=float(rendement_indique_cible_min) if rendement_indique_cible_min is not None else None,
            rendement_mecanique_cible_min=float(rendement_mecanique_cible_min) if rendement_mecanique_cible_min is not None else None,
            masse_estimee_max_kg=float(masse_estimee_max_kg) if masse_estimee_max_kg is not None else None,
            cout_matiere_max_eur=float(cout_matiere_max_eur) if cout_matiere_max_eur is not None else None,
            indice_maintenance_max=float(indice_maintenance_max) if indice_maintenance_max is not None else None,
            duree_vie_cible_h=float(duree_vie_cible_h) if duree_vie_cible_h is not None else None,
        )
        rapport["moteur_defini"] = moteur

        _dedup_inconnues(rapport)
        return rapport

    # ============================================================
    # ANALYSE POINT DE FONCTIONNEMENT
    # ============================================================

    def analyser_point_de_fonctionnement(
        self,
        *,
        rpm: Optional[float] = None,

        # Travail indiqué
        pression_moyenne_effective_pa: Optional[float] = None,

        # Instantané
        pression_cylindre_pa: Optional[float] = None,
        angle_vilebrequin_deg: Optional[float] = None,

        # Thermo gaz parfait
        masse_gaz_kg: Optional[float] = None,
        volume_gaz_m3: Optional[float] = None,
        temperature_gaz_k: Optional[float] = None,
        constante_gaz_r: float = 287.05,

        # Adiabatique
        t1_k: Optional[float] = None,
        p1_pa: Optional[float] = None,
        p2_pa: Optional[float] = None,
        gamma: float = 1.4,

        # Fuite annulaire
        delta_p_fuite_pa: Optional[float] = None,
        jeu_radial_h_m: Optional[float] = None,
        rayon_fuite_m: Optional[float] = None,
        longueur_fuite_m: Optional[float] = None,

        # Frottements
        force_normale_segment_n: Optional[float] = None,
        vitesse_glissement_palier_ms: Optional[float] = None,
        charge_palier_n: Optional[float] = None,

        # Usure cumulée
        duree_fonctionnement_s: Optional[float] = None,

        # Couvercle / vis
        pression_max_pa: Optional[float] = None,
        aire_effective_couvercle_m2: Optional[float] = None,
        force_joint_n: Optional[float] = None,
        nombre_vis: Optional[int] = None,
        diametre_nominal_vis_m: Optional[float] = None,
    ) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "cylindree": {},
            "cinematique": {},
            "resultats": {},
            "thermo": {},
            "forces": {},
            "couple": {},
            "pertes": {},
            "usure": {},
            "dimensionnement": {},
            "assemblage": {},
            "conception": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ============================================================
        # 1) Entrées de base
        # ============================================================
        rpm_effectif = rpm if rpm is not None else self.rpm_nominal
        pme_effective = pression_moyenne_effective_pa if pression_moyenne_effective_pa is not None else self.pme_nominale_pa
        pression_max_effective = pression_max_pa if pression_max_pa is not None else self.pression_max_pa

        rapport["entrees"].update(
            {
                "rpm": rpm_effectif,
                "pression_moyenne_effective_pa": pme_effective,
                "pression_cylindre_pa": pression_cylindre_pa,
                "angle_vilebrequin_deg": angle_vilebrequin_deg,
                "duree_fonctionnement_s": duree_fonctionnement_s,
                "temps_moteur": int(self.temps_moteur),
                "nombre_cylindres": int(self.nombre_cylindres),
                "alesage_m": self.alesage_m,
                "course_m": self.course_m,
                "architecture": self.architecture,
                "rpm_nominal": self.rpm_nominal,
                "pme_nominale_pa": self.pme_nominale_pa,
                "pression_max_nominale_pa": self.pression_max_pa,
            }
        )

        # ============================================================
        # 2) Cylindrée
        # ============================================================
        Vd_unit: Optional[float] = None
        Vd_tot: Optional[float] = None

        if self.alesage_m is not None and self.course_m is not None:
            Vd_unit = float(
                calcul_cylindree_unitaire(
                    alesage_m=self.alesage_m,
                    course_m=self.course_m,
                    allow_zero=False,
                    return_details=False,
                )
            )
            Vd_tot = float(
                calcul_cylindree_totale(
                    cylindree_unitaire_m3=Vd_unit,
                    nombre_cylindres=int(self.nombre_cylindres),
                    allow_zero_cylindres=False,
                    return_details=False,
                )
            )
        else:
            _push_inconnue(rapport, "impossibles", "cylindrée", "Impossible sans alesage_m et course_m.")

        rapport["cylindree"]["Vd_unitaire_m3"] = Vd_unit
        rapport["cylindree"]["Vd_totale_m3"] = Vd_tot

        # ============================================================
        # 3) Cinématique
        # ============================================================
        omega: Optional[float] = None
        cps: Optional[float] = None
        v_piston_moy: Optional[float] = None

        if rpm_effectif is not None:
            rpm_val = _require_positive("rpm", rpm_effectif, strictly=False)
            omega = _omega_from_rpm(rpm_val)
            cps = _cycles_par_seconde(rpm_val, int(self.temps_moteur))

            if self.course_m is not None:
                v_piston_moy = float(
                    calcul_vitesse_moyenne_piston(
                        course_m=self.course_m,
                        vitesse_rotation_tr_min=rpm_val,
                    )
                )
            else:
                _push_inconnue(rapport, "partielles", "vitesse moyenne piston", "Calculable si course_m est fournie.")
        else:
            _push_inconnue(rapport, "partielles", "cinématique", "ω/cycles/s/vitesse piston calculables si rpm est fourni.")

        rapport["cinematique"]["omega_rad_s"] = omega
        rapport["cinematique"]["cycles_par_seconde"] = cps
        rapport["cinematique"]["vitesse_moyenne_piston_ms"] = v_piston_moy
        if v_piston_moy is not None:
            rapport["cinematique"]["distance_glissement_piston_par_heure_m"] = v_piston_moy * 3600.0

        # ============================================================
        # 4) Travail indiqué / Puissance indiquée
        # ============================================================
        W_i: Optional[float] = None
        P_i: Optional[float] = None
        P_frein_estimee: Optional[float] = None

        if pme_effective is not None and Vd_tot is not None:
            W_i = float(calcul_travail_indique_pme(pme_effective, Vd_tot))

            if rpm_effectif is not None:
                P_i = float(
                    calcul_puissance_indiquee(
                        W_i,
                        _require_positive("rpm", rpm_effectif, strictly=False),
                        temps_moteur=int(self.temps_moteur),
                    )
                )
                if self.rendement_mecanique_nominal is not None:
                    P_frein_estimee = P_i * self.rendement_mecanique_nominal
            else:
                _push_inconnue(rapport, "partielles", "puissance indiquée", "Calculable si rpm est fourni.")
        else:
            _push_inconnue(rapport, "partielles", "travail/power indiqué", "Calculables si PME et alesage/course sont fournis.")

        rapport["resultats"]["travail_indique_par_cycle_J"] = W_i
        rapport["resultats"]["puissance_indiquee_W"] = P_i
        rapport["resultats"]["puissance_frein_estimee_W"] = P_frein_estimee

        # ============================================================
        # 5) Force gaz / inertie / couple instantané
        # ============================================================
        F_gaz: Optional[float] = None
        F_inertie: Optional[float] = None
        F_bielle: Optional[float] = None
        T_inst: Optional[float] = None

        if pression_cylindre_pa is not None and self.alesage_m is not None:
            F_gaz = float(
                calcul_force_gaz(
                    pression_pa=_require_finite("pression_cylindre_pa", pression_cylindre_pa),
                    alesage_m=self.alesage_m,
                    allow_negative_pression=True,
                    allow_zero_alesage=False,
                    clamp_non_negative=False,
                    return_details=False,
                )
            )
        else:
            _push_inconnue(rapport, "partielles", "force gaz instantanée", "Calculable si pression_cylindre_pa et alesage_m sont fournis.")

        r_manivelle: Optional[float] = None
        if self.rayon_manivelle_m is not None:
            r_manivelle = float(self.rayon_manivelle_m)
        elif self.course_m is not None:
            r_manivelle = 0.5 * float(self.course_m)
            rapport["notes_modele"].append("rayon_manivelle_m approx = course/2 (si non fourni).")

        if (
            self.masse_alternative_kg is not None
            and r_manivelle is not None
            and rpm_effectif is not None
            and self.longueur_bielle_m is not None
            and angle_vilebrequin_deg is not None
        ):
            F_inertie = float(
                calcul_force_inertie_alternative(
                    masse_alternative_kg=self.masse_alternative_kg,
                    rayon_manivelle_m=r_manivelle,
                    vitesse_rotation_tr_min=_require_positive("rpm", rpm_effectif, strictly=False),
                    longueur_bielle_m=self.longueur_bielle_m,
                    angle_vilebrequin_deg=_require_finite("angle_vilebrequin_deg", angle_vilebrequin_deg),
                    angle_unite="deg",
                    input_vitesse="rpm",
                    clamp_ratio_r_sur_l=False,
                    return_details=False,
                )
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "force inertie alternative",
                "Calculable si (masse_alternative_kg, course/rayon_manivelle_m, rpm, longueur_bielle_m, angle_vilebrequin_deg) sont fournis.",
            )

        if F_gaz is not None and F_inertie is not None:
            F_bielle = F_gaz - F_inertie
        else:
            _push_inconnue(rapport, "partielles", "force bielle effective", "Déductible si force gaz ET force inertie sont calculées.")

        if F_bielle is not None and r_manivelle is not None and angle_vilebrequin_deg is not None:
            T_inst = float(
                calcul_couple_instantane(
                    force_bielle_n=F_bielle,
                    rayon_manivelle_m=r_manivelle,
                    angle_vilebrequin_deg=_require_finite("angle_vilebrequin_deg", angle_vilebrequin_deg),
                    angle_unite="deg",
                    use_abs_rayon=True,
                    clamp_non_negative=False,
                    return_details=False,
                )
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "couple instantané",
                "Calculable si (force bielle, rayon_manivelle_m/course, angle_vilebrequin_deg) sont fournis.",
            )

        rapport["forces"]["F_gaz_N"] = F_gaz
        rapport["forces"]["F_inertie_N"] = F_inertie
        rapport["forces"]["F_bielle_effective_N"] = F_bielle
        rapport["couple"]["T_instantane_Nm"] = T_inst
        rapport["cinematique"]["rayon_manivelle_m_effectif"] = r_manivelle

        # ============================================================
        # 6) Thermo
        # ============================================================
        P_gaz: Optional[float] = None
        if masse_gaz_kg is not None and volume_gaz_m3 is not None and temperature_gaz_k is not None:
            P_gaz = float(
                calcul_pression_gaz_parfait(
                    masse_kg=_require_positive("masse_gaz_kg", masse_gaz_kg, strictly=False),
                    volume_m3=_require_positive("volume_gaz_m3", volume_gaz_m3, strictly=True),
                    temperature_k=_require_positive("temperature_gaz_k", temperature_gaz_k, strictly=True),
                    constante_gaz_r=_require_positive("constante_gaz_r", constante_gaz_r, strictly=True),
                )
            )
        else:
            _push_inconnue(rapport, "partielles", "pression gaz parfait", "Calculable si masse_gaz_kg, volume_gaz_m3, temperature_gaz_k sont fournis.")

        T2: Optional[float] = None
        if t1_k is not None and p1_pa is not None and p2_pa is not None:
            T2 = float(
                calcul_temperature_compression_adiabatique(
                    t1_k=_require_positive("t1_k", t1_k, strictly=True),
                    p1_pa=_require_positive("p1_pa", p1_pa, strictly=True),
                    p2_pa=_require_positive("p2_pa", p2_pa, strictly=True),
                    gamma=_require_positive("gamma", gamma, strictly=True),
                )
            )
        else:
            _push_inconnue(rapport, "partielles", "température adiabatique T2", "Calculable si t1_k, p1_pa, p2_pa sont fournis (et gamma).")

        rapport["thermo"]["pression_gaz_parfait_pa"] = P_gaz
        rapport["thermo"]["temperature_adiabatique_T2_k"] = T2

        # ============================================================
        # 7) Fuite annulaire
        # ============================================================
        Q_fuite: Optional[float] = None
        m_dot_fuite: Optional[float] = None

        if (
            delta_p_fuite_pa is not None
            and jeu_radial_h_m is not None
            and rayon_fuite_m is not None
            and longueur_fuite_m is not None
            and self.viscosite_pa_s is not None
        ):
            Q_fuite = float(
                calcul_debit_fuite_annulaire(
                    delta_p_pa=_require_finite("delta_p_fuite_pa", delta_p_fuite_pa),
                    jeu_radial_h_m=_require_positive("jeu_radial_h_m", jeu_radial_h_m, strictly=False),
                    rayon_m=_require_positive("rayon_fuite_m", rayon_fuite_m, strictly=False),
                    longueur_fuite_l_m=_require_positive("longueur_fuite_m", longueur_fuite_m, strictly=True),
                    viscosite_dynamique_pa_s=_require_positive("viscosite_pa_s", self.viscosite_pa_s, strictly=True),
                    use_abs_delta_p=True,
                    clamp_non_negative=True,
                    return_details=False,
                )
            )

            if self.densite_kg_m3 is not None:
                m_dot_fuite = float(
                    calcul_masse_fuite(
                        debit_volumique_m3s=Q_fuite,
                        densite_kg_m3=_require_positive("densite_kg_m3", self.densite_kg_m3, strictly=False),
                        use_abs_debit=True,
                        clamp_non_negative=True,
                        return_details=False,
                    )
                )
            else:
                _push_inconnue(rapport, "partielles", "débit massique de fuite", "Calculable si densite_kg_m3 est fournie (en plus de Q_fuite).")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "débit de fuite annulaire",
                "Calculable si delta_p_fuite_pa, jeu_radial_h_m, rayon_fuite_m, longueur_fuite_m, viscosite_pa_s sont fournis.",
            )

        rapport["resultats"]["Q_fuite_m3_s"] = Q_fuite
        rapport["resultats"]["m_dot_fuite_kg_s"] = m_dot_fuite

        # ============================================================
        # 8) Pertes par frottement
        # ============================================================
        P_frott_seg: Optional[float] = None
        P_frott_palier: Optional[float] = None

        if force_normale_segment_n is not None and self.coef_frottement_segment is not None and v_piston_moy is not None:
            P_frott_seg = float(
                calcul_puissance_frottement_segment(
                    force_normale_n=_require_positive("force_normale_segment_n", force_normale_segment_n, strictly=False),
                    vitesse_moyenne_ms=_require_positive("v_piston_moy", v_piston_moy, strictly=False),
                    coef_frottement=_require_positive("coef_frottement_segment", self.coef_frottement_segment, strictly=False),
                )
            )
        else:
            _push_inconnue(rapport, "partielles", "pertes frottement segment", "Calculables si force_normale_segment_n, coef_frottement_segment, rpm et course_m sont fournis.")

        if charge_palier_n is not None and vitesse_glissement_palier_ms is not None and self.coef_frottement_palier is not None:
            P_frott_palier = float(
                calcul_puissance_frottement_palier(
                    charge_w=_require_positive("charge_palier_n", charge_palier_n, strictly=False),
                    vitesse_glissement_ms=_require_positive("vitesse_glissement_palier_ms", vitesse_glissement_palier_ms, strictly=False),
                    coef_frottement_f=_require_positive("coef_frottement_palier", self.coef_frottement_palier, strictly=False),
                )
            )
        else:
            _push_inconnue(rapport, "partielles", "pertes frottement palier", "Calculables si charge_palier_n, vitesse_glissement_palier_ms et coef_frottement_palier sont fournis.")

        P_frott_total: Optional[float] = None
        if P_frott_seg is not None or P_frott_palier is not None:
            P_frott_total = float((P_frott_seg or 0.0) + (P_frott_palier or 0.0))

        rapport["pertes"]["P_frottement_segment_W"] = P_frott_seg
        rapport["pertes"]["P_frottement_palier_W"] = P_frott_palier
        rapport["pertes"]["P_frottement_total_W"] = P_frott_total

        rendement_mecanique_estime = None
        if P_i is not None and P_i > 0.0 and P_frott_total is not None:
            rendement_mecanique_estime = max(0.0, (P_i - P_frott_total) / P_i)

        rapport["pertes"]["rendement_mecanique_estime"] = rendement_mecanique_estime

        # ============================================================
        # 9) Usure Archard
        # ============================================================
        usure_seg = _archard_depuis_vitesse(
            k=self.coefficient_usure_segment_k,
            W_n=force_normale_segment_n,
            v_ms=v_piston_moy,
            H_pa=self.durete_contact_segment_pa,
            aire_contact_m2=self.aire_contact_segment_m2,
        )
        usure_pal = _archard_depuis_vitesse(
            k=self.coefficient_usure_palier_k,
            W_n=charge_palier_n,
            v_ms=vitesse_glissement_palier_ms,
            H_pa=self.durete_contact_palier_pa,
            aire_contact_m2=self.aire_contact_palier_m2,
        )

        rapport["usure"]["segments"] = usure_seg
        rapport["usure"]["palier"] = usure_pal

        if duree_fonctionnement_s is not None:
            t_s = _require_positive("duree_fonctionnement_s", duree_fonctionnement_s, strictly=False)

            if (
                self.coefficient_usure_segment_k is not None
                and force_normale_segment_n is not None
                and v_piston_moy is not None
                and self.durete_contact_segment_pa is not None
            ):
                V_seg = calcul_volume_usure_archard(
                    coefficient_usure_k=self.coefficient_usure_segment_k,
                    charge_normale_w=force_normale_segment_n,
                    distance_glissement_ls=max(0.0, v_piston_moy) * t_s,
                    durete_h=self.durete_contact_segment_pa,
                )
                rapport["usure"]["segments"]["volume_use_total_m3"] = float(V_seg)
                if self.aire_contact_segment_m2 is not None:
                    dh_seg = calcul_perte_epaisseur(volume_use_m3=V_seg, aire_contact_m2=self.aire_contact_segment_m2)
                    rapport["usure"]["segments"]["perte_epaisseur_totale_m"] = float(dh_seg)
            else:
                _push_inconnue(rapport, "partielles", "usure cumulée segments", "Calculable si (k, W, H) segments + vitesse piston sont fournis (et aire pour épaisseur).")

            if (
                self.coefficient_usure_palier_k is not None
                and charge_palier_n is not None
                and vitesse_glissement_palier_ms is not None
                and self.durete_contact_palier_pa is not None
            ):
                V_pal = calcul_volume_usure_archard(
                    coefficient_usure_k=self.coefficient_usure_palier_k,
                    charge_normale_w=charge_palier_n,
                    distance_glissement_ls=max(0.0, vitesse_glissement_palier_ms) * t_s,
                    durete_h=self.durete_contact_palier_pa,
                )
                rapport["usure"]["palier"]["volume_use_total_m3"] = float(V_pal)
                if self.aire_contact_palier_m2 is not None:
                    dh_pal = calcul_perte_epaisseur(volume_use_m3=V_pal, aire_contact_m2=self.aire_contact_palier_m2)
                    rapport["usure"]["palier"]["perte_epaisseur_totale_m"] = float(dh_pal)
            else:
                _push_inconnue(rapport, "partielles", "usure cumulée palier", "Calculable si (k, W, H) palier + vitesse palier sont fournis (et aire pour épaisseur).")
        else:
            _push_inconnue(rapport, "partielles", "usure cumulée", "Une durée (duree_fonctionnement_s) est nécessaire pour passer des taux (dV/dt) à un total.")

        if self.coefficient_usure_segment_k is None or self.durete_contact_segment_pa is None:
            _push_inconnue(rapport, "impossibles", "usure segments (valeur absolue)", "Impossible sans coefficient d'usure k et dureté H (tribologie/datasheet).")
        if self.coefficient_usure_palier_k is None or self.durete_contact_palier_pa is None:
            _push_inconnue(rapport, "impossibles", "usure palier (valeur absolue)", "Impossible sans coefficient d'usure k et dureté H (tribologie/datasheet).")

        # ============================================================
        # 10) Dimensionnement paroi cylindre
        # ============================================================
        t_mince: Optional[float] = None
        t_lame: Optional[float] = None

        p_dim: Optional[float] = None
        if pression_max_effective is not None:
            p_dim = _require_positive("pression_max_pa", pression_max_effective, strictly=False)
        elif pression_cylindre_pa is not None:
            p_dim = _require_finite("pression_cylindre_pa", pression_cylindre_pa)

        if p_dim is not None and self.alesage_m is not None and self.contrainte_admissible_pa is not None:
            ri = 0.5 * _require_positive("alesage_m", self.alesage_m, strictly=True)

            t_mince = float(
                calcul_epaisseur_cylindre_mince(
                    pression_pa=p_dim,
                    rayon_interne_m=ri,
                    contrainte_admissible_pa=_require_positive("contrainte_admissible_pa", self.contrainte_admissible_pa, strictly=True),
                    include_longitudinale=False,
                    facteur_securite=_require_positive("facteur_securite_cylindre", self.facteur_securite_cylindre, strictly=True),
                    clamp_non_negative=True,
                    return_details=False,
                )
            )
            t_lame = float(
                calcul_epaisseur_cylindre_lame(
                    pression_interne_pa=p_dim,
                    rayon_interne_m=ri,
                    contrainte_admissible_pa=_require_positive("contrainte_admissible_pa", self.contrainte_admissible_pa, strictly=True),
                    facteur_securite=_require_positive("facteur_securite_cylindre", self.facteur_securite_cylindre, strictly=True),
                    clamp_non_negative=True,
                    return_details=False,
                )
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "épaisseur paroi cylindre",
                "Calculable si (pression_max_pa ou pression_cylindre_pa), alesage_m et contrainte_admissible_pa sont fournis.",
            )

        rapport["dimensionnement"]["pression_dimensionnement_pa"] = p_dim
        rapport["dimensionnement"]["epaisseur_cylindre_mince_m"] = t_mince
        rapport["dimensionnement"]["epaisseur_cylindre_lame_m"] = t_lame
        if t_mince is not None or t_lame is not None:
            rapport["dimensionnement"]["epaisseur_cylindre_retenue_m"] = max(
                t_mince or 0.0,
                t_lame or 0.0,
            )

        # ============================================================
        # 11) Précharge vis couvercle
        # ============================================================
        F_sep: Optional[float] = None
        F_pre_tot: Optional[float] = None
        F_par_vis: Optional[float] = None
        M_serrage: Optional[float] = None

        if pression_max_effective is not None and aire_effective_couvercle_m2 is not None:
            F_sep = float(
                calcul_force_separation(
                    pression_max_pa=_require_positive("pression_max_pa", pression_max_effective, strictly=False),
                    aire_effective_m2=_require_positive("aire_effective_couvercle_m2", aire_effective_couvercle_m2, strictly=False),
                )
            )

            if force_joint_n is not None:
                F_pre_tot = float(
                    calcul_precharge_vis_totale(
                        force_separation_n=F_sep,
                        force_joint_n=_require_positive("force_joint_n", force_joint_n, strictly=False),
                        facteur_securite=_require_positive("facteur_securite_vis", self.facteur_securite_vis, strictly=True),
                    )
                )
            else:
                _push_inconnue(rapport, "partielles", "précharge totale vis", "Calculable si force_joint_n est fournie (en plus de F_sep).")

            if F_pre_tot is not None and nombre_vis is not None:
                n_vis = _require_int_pos("nombre_vis", nombre_vis)
                F_par_vis = F_pre_tot / float(n_vis)
            else:
                _push_inconnue(rapport, "partielles", "précharge par vis", "Calculable si F_pre_tot et nombre_vis sont fournis.")

            if F_par_vis is not None and diametre_nominal_vis_m is not None:
                M_serrage = float(
                    calcul_couple_serrage(
                        force_precharge_vis_n=F_par_vis,
                        diametre_nominal_m=_require_positive("diametre_nominal_vis_m", diametre_nominal_vis_m, strictly=True),
                        facteur_frottement_k=_require_positive("facteur_frottement_vis_k", self.facteur_frottement_vis_k, strictly=False),
                    )
                )
            else:
                _push_inconnue(rapport, "partielles", "couple de serrage vis", "Calculable si F_par_vis et diametre_nominal_vis_m sont fournis.")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "dimensionnement vis couvercle",
                "Calculable si pression_max_pa et aire_effective_couvercle_m2 sont fournis (et force_joint_n, nombre_vis, diametre_nominal_vis_m pour aller plus loin).",
            )

        rapport["assemblage"]["force_separation_N"] = F_sep
        rapport["assemblage"]["precharge_totale_N"] = F_pre_tot
        rapport["assemblage"]["precharge_par_vis_N"] = F_par_vis
        rapport["assemblage"]["couple_serrage_par_vis_Nm"] = M_serrage

        # ============================================================
        # 12) Synthèse conception (fiabilité / efficience / masse / coût / maintenance)
        # ============================================================
        reserve_vitesse_piston = None
        if v_piston_moy is not None and self.rpm_nominal is not None and self.course_m is not None:
            # pas de limite si elle n'est pas connue ; on ne force rien
            pass

        indice_maintenance = _estimer_indice_maintenance(
            nombre_cylindres=self.nombre_cylindres,
            architecture=self.architecture,
        )

        epaisseur_retenue = None
        if t_mince is not None or t_lame is not None:
            epaisseur_retenue = max(t_mince or 0.0, t_lame or 0.0)

        estimation_masse = _estimer_masse_cylindres(
            alesage_m=self.alesage_m,
            course_m=self.course_m,
            nombre_cylindres=self.nombre_cylindres,
            epaisseur_paroi_m=epaisseur_retenue,
            densite_materiau_kg_m3=self.densite_materiau_kg_m3,
        )
        masse_estimee_kg = estimation_masse["masse_estimee_kg"]
        cout_matiere_estime_eur = _estimer_cout_matiere(
            masse_kg=masse_estimee_kg,
            cout_matiere_eur_kg=self.cout_matiere_eur_kg,
        )

        rapport["conception"].update(
            {
                "masse": estimation_masse,
                "cout_matiere_estime_eur": cout_matiere_estime_eur,
                "indice_maintenance": indice_maintenance,
                "respecte_masse_estimee_max": _booleen_contrainte_max(
                    valeur=masse_estimee_kg,
                    limite_max=self.masse_estimee_max_kg,
                ),
                "respecte_cout_matiere_max": _booleen_contrainte_max(
                    valeur=cout_matiere_estime_eur,
                    limite_max=self.cout_matiere_max_eur,
                ),
                "respecte_indice_maintenance_max": _booleen_contrainte_max(
                    valeur=indice_maintenance,
                    limite_max=self.indice_maintenance_max,
                ),
                "respecte_rendement_mecanique_min": _booleen_contrainte_min(
                    valeur=rendement_mecanique_estime,
                    limite_min=self.rendement_mecanique_cible_min,
                ),
                "commentaires": [
                    "La masse et le coût ici restent des estimations limitées à la matière des viroles de cylindres lorsque les données sont présentes.",
                    "L'indice de maintenance est un proxy déterministe de complexité, pas un coût d'atelier réel.",
                    "La fiabilité absolue reste impossible à conclure ici sans fatigue détaillée, états de surface, matériaux de chaque pièce et spectres de charge.",
                ],
            }
        )

        # ============================================================
        # 13) Inconnues réellement impossibles sans données externes
        # ============================================================
        _push_inconnue(
            rapport,
            "impossibles",
            "rendement global réel",
            "Sans p(θ) (diagramme indicateur), pertes de pompage, transferts thermiques, accessoires, on ne peut pas calculer un rendement global fiable.",
        )
        _push_inconnue(
            rapport,
            "impossibles",
            "fatigue/longévité complète",
            "Sans matériaux précis, états de surface, concentrations de contraintes, et cycles de charge, on ne peut pas conclure sur la fatigue/longévité.",
        )

        _dedup_inconnues(rapport)
        return rapport