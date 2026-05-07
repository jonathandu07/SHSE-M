# backend/pieces/piston.py
# =============================================================================
# PISTON (côté froid) — SHSE-M
# =============================================================================
# Objectif :
# - sortir des cotes géométriques exploitables pour la CAO / SolidWorks
# - réutiliser les données calculées par le cylindre quand elles existent
# - calculer les jeux froid/chaud
# - calculer tête / jupe si les entrées mécaniques le permettent
# - définir complètement les rainures de joints toriques sur Ø extérieur :
#   profondeur, largeur, diamètre de fond, positions axiales, entraxes
# - produire un bloc "cao" cohérent
#
# Principe :
# - aucune valeur "cachée" issue d'une norme non explicitée
# - les géométries manquantes sont déduites depuis :
#   * le cylindre déjà calculé,
#   * les modules du projet,
#   * des règles de conception EXPLICITES regroupées dans des dataclasses.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Literal, Tuple, List
import math

# =============================================================================
# Imports projet (robustes)
# =============================================================================

# --- Matériaux ---
try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None


# --- Cylindre ---
try:
    from backend.components.moteur_thermique.pieces.cylindre import Cylindre  # type: ignore
except Exception:  # pragma: no cover
    try:
        from pieces.cylindre import Cylindre  # type: ignore
    except Exception:  # pragma: no cover
        Cylindre = None  # type: ignore


# --- Modules moteur thermique ---
try:
    from backend.components.moteur_thermique.modules.calcul_vitesse_piston import calcul_vitesse_moyenne_piston
except Exception:  # pragma: no cover
    def calcul_vitesse_moyenne_piston(course_m: float, vitesse_rotation_tr_min: float) -> float:
        return 2.0 * float(course_m) * (float(vitesse_rotation_tr_min) / 60.0)


try:
    from backend.components.moteur_thermique.modules.calcul_gaz import (
        calcul_force_gaz,
        calcul_debit_fuite_annulaire,
        calcul_masse_fuite,
    )
except Exception:  # pragma: no cover
    def calcul_force_gaz(
        pression_pa: float,
        alesage_m: float,
        *,
        allow_negative_pression: bool = True,
        allow_zero_alesage: bool = False,
        clamp_non_negative: bool = False,
        return_details: bool = False,
    ) -> float | Dict[str, float]:
        A = math.pi * (float(alesage_m) ** 2) / 4.0
        F = float(pression_pa) * A
        if clamp_non_negative:
            F = max(0.0, F)
        if return_details:
            return {"force_gaz_n": F, "aire_piston_m2": A}
        return F

    def calcul_debit_fuite_annulaire(
        delta_p_pa: float,
        jeu_radial_h_m: float,
        rayon_m: float,
        longueur_fuite_l_m: float,
        viscosite_dynamique_pa_s: float,
        *,
        use_abs_delta_p: bool = True,
        epsilon: float = 1e-18,
        clamp_non_negative: bool = True,
        return_details: bool = False,
    ) -> float | Dict[str, float]:
        dP = abs(float(delta_p_pa)) if use_abs_delta_p else float(delta_p_pa)
        Q = (math.pi * float(rayon_m) * (float(jeu_radial_h_m) ** 3) * dP) / (
            6.0 * float(viscosite_dynamique_pa_s) * float(longueur_fuite_l_m)
        )
        if use_abs_delta_p and clamp_non_negative:
            Q = max(0.0, Q)
        if return_details:
            return {"Q_m3_s": Q}
        return Q

    def calcul_masse_fuite(
        debit_volumique_m3s: float,
        densite_kg_m3: float,
        *,
        use_abs_debit: bool = True,
        clamp_non_negative: bool = True,
        return_details: bool = False,
    ) -> float | Dict[str, float]:
        Q = abs(float(debit_volumique_m3s)) if use_abs_debit else float(debit_volumique_m3s)
        mdot = Q * float(densite_kg_m3)
        if clamp_non_negative:
            mdot = max(0.0, mdot)
        if return_details:
            return {"debit_massique_kg_s": mdot}
        return mdot


try:
    from backend.components.moteur_thermique.modules.calcul_pertes_frottement import (
        calcul_puissance_frottement_segment,
    )
except Exception:  # pragma: no cover
    def calcul_puissance_frottement_segment(
        force_normale_n: float,
        vitesse_moyenne_ms: float,
        coef_frottement: float,
    ) -> float:
        return float(force_normale_n) * float(vitesse_moyenne_ms) * float(coef_frottement)


try:
    from backend.components.moteur_thermique.modules.calcul_force_inertie import calcul_force_inertie_alternative
except Exception:  # pragma: no cover
    def calcul_force_inertie_alternative(
        masse_alternative_kg: float,
        rayon_manivelle_m: float,
        vitesse_rotation_tr_min: float,
        longueur_bielle_m: float,
        angle_vilebrequin_deg: float,
        *,
        angle_unite: Literal["deg", "rad"] = "deg",
        input_vitesse: Literal["rpm", "rad_s"] = "rpm",
        clamp_ratio_r_sur_l: bool = False,
        max_ratio_r_sur_l: float = 0.5,
        return_details: bool = False,
    ) -> float | Dict[str, float]:
        if input_vitesse == "rpm":
            omega = (2.0 * math.pi * float(vitesse_rotation_tr_min)) / 60.0
        else:
            omega = float(vitesse_rotation_tr_min)

        th = math.radians(float(angle_vilebrequin_deg)) if angle_unite == "deg" else float(angle_vilebrequin_deg)
        r = float(rayon_manivelle_m)
        l = float(longueur_bielle_m)
        lam = r / l
        Fi = float(masse_alternative_kg) * r * omega * omega * (math.cos(th) + lam * math.cos(2.0 * th))
        if return_details:
            return {"F_i": Fi}
        return Fi


try:
    from backend.components.moteur_thermique.modules.calcul_usure_archard import (
        calcul_volume_usure_archard,
        calcul_perte_epaisseur,
    )
except Exception:  # pragma: no cover
    def calcul_volume_usure_archard(
        coefficient_usure_k: float,
        charge_normale_w: float,
        distance_glissement_ls: float,
        durete_h: float,
    ) -> float:
        return float(coefficient_usure_k) * (float(charge_normale_w) * float(distance_glissement_ls)) / float(durete_h)

    def calcul_perte_epaisseur(volume_use_m3: float, aire_contact_m2: float) -> float:
        return float(volume_use_m3) / float(aire_contact_m2)


# --- Air (pour viscosité) ---
try:
    from backend.ensemble.air import dynamic_viscosity_air_Pa_s
except Exception:  # pragma: no cover
    dynamic_viscosity_air_Pa_s = None  # type: ignore


R_AIR_J_KG_K = 287.058


# =============================================================================
# Helpers robustes
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    if strict and v <= 0.0:
        raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    if (not strict) and v < 0.0:
        raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _req_int_ge(name: str, x: Any, min_value: int = 0) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return int(x)


def _push_inc(rap: Dict[str, Any], cat: str, nom: str, raison: str) -> None:
    rap["inconnues"][cat].append({"nom": nom, "raison": raison})


def _dedup_inconnues(rap: Dict[str, Any]) -> None:
    def dedup(lst: List[dict]) -> List[dict]:
        seen: set[Tuple[str, str]] = set()
        out: List[dict] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out

    rap["inconnues"]["impossibles"] = dedup(list(rap["inconnues"].get("impossibles", []) or []))
    rap["inconnues"]["partielles"] = dedup(list(rap["inconnues"].get("partielles", []) or []))


def _borne(x: float, xmin: float, xmax: float) -> float:
    return max(float(xmin), min(float(xmax), float(x)))


def _aire_disque(diametre_m: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    return math.pi * (0.5 * D) ** 2


def _perimetre(diametre_m: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    return math.pi * D


def _vol_cylindre(diametre_m: float, hauteur_m: float) -> float:
    return _aire_disque(diametre_m) * _req_pos("hauteur_m", hauteur_m)


def _moment_inertie_disque_plein_axe(diametre_m: float, masse_kg: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    m = _req_pos("masse_kg", masse_kg, strict=False)
    r = 0.5 * D
    return 0.5 * m * r * r


def _moment_inertie_cylindre_plein_transversal_cg(diametre_m: float, hauteur_m: float, masse_kg: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    H = _req_pos("hauteur_m", hauteur_m)
    m = _req_pos("masse_kg", masse_kg, strict=False)
    r = 0.5 * D
    return m * ((3.0 * r * r) + (H * H)) / 12.0


def _volume_tore_m3(diametre_moyen_m: float, section_m: float) -> float:
    Dm = _req_pos("diametre_moyen_m", diametre_moyen_m)
    d = _req_pos("section_m", section_m)
    R = 0.5 * Dm
    r = 0.5 * d
    return 2.0 * math.pi * math.pi * R * r * r


def _moment_inertie_tore_axe(diametre_moyen_m: float, section_m: float, masse_kg: float) -> float:
    Dm = _req_pos("diametre_moyen_m", diametre_moyen_m)
    d = _req_pos("section_m", section_m)
    m = _req_pos("masse_kg", masse_kg, strict=False)
    R = 0.5 * Dm
    r = 0.5 * d
    return m * (R * R + 0.75 * r * r)


def _angle_bielle_rad(rayon_manivelle_m: float, longueur_bielle_m: float, angle_vilebrequin_deg: float) -> float:
    r = _req_pos("rayon_manivelle_m", rayon_manivelle_m, strict=False)
    l = _req_pos("longueur_bielle_m", longueur_bielle_m, strict=True)
    th = math.radians(_req_finite("angle_vilebrequin_deg", angle_vilebrequin_deg))
    arg = _borne((r / l) * math.sin(th), -1.0, 1.0)
    return math.asin(arg)


def _force_laterale_piston(F_axiale_n: float, rayon_manivelle_m: float, longueur_bielle_m: float, angle_vilebrequin_deg: float) -> Dict[str, float]:
    F = _req_finite("F_axiale_n", F_axiale_n)
    beta = _angle_bielle_rad(rayon_manivelle_m, longueur_bielle_m, angle_vilebrequin_deg)
    Fl = F * math.tan(beta)
    return {"angle_bielle_rad": beta, "angle_bielle_deg": math.degrees(beta), "force_laterale_n": Fl}


def _aire_projectee_contact_jupe(diametre_m: float, longueur_m: float, fraction_circonference: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    L = _req_pos("longueur_m", longueur_m)
    f = _req_pos("fraction_circonference", fraction_circonference, strict=False)
    if f > 1.0:
        raise ValueError(f"fraction_circonference doit être <= 1 (reçu: {f}).")
    return _perimetre(D) * L * f


def _contrainte_tete_plaque_pa(k_sigma_plaque: float, pression_pa: float, alesage_m: float, epaisseur_tete_m: float) -> float:
    k = _req_pos("k_sigma_plaque", k_sigma_plaque)
    p = _req_pos("pression_pa", pression_pa, strict=False)
    D = _req_pos("alesage_m", alesage_m)
    t = _req_pos("epaisseur_tete_m", epaisseur_tete_m)
    a = 0.5 * D
    return k * p * (a * a) / (t * t)


def _gradient_thermique_k_m(T_chaud_k: float, T_froid_k: float, epaisseur_m: float) -> float:
    Tch = _req_pos("T_chaud_k", T_chaud_k)
    Tfr = _req_pos("T_froid_k", T_froid_k)
    e = _req_pos("epaisseur_m", epaisseur_m)
    return (Tch - Tfr) / e


def _contrainte_thermique_biaxiale_pa(E_pa: float, alpha_1_k: float, delta_t_k: float, poisson: float, facteur_contrainte: float = 1.0) -> float:
    E = _req_pos("E_pa", E_pa)
    a = _req_pos("alpha_1_k", alpha_1_k)
    nu = _req_finite("poisson", poisson)
    k = _req_pos("facteur_contrainte", facteur_contrainte, strict=False)
    if abs(1.0 - nu) < 1e-12:
        raise ValueError("poisson ne doit pas être égal à 1 pour la contrainte thermique biaxiale.")
    return k * E * a * float(delta_t_k) / (1.0 - nu)


def _somme_masses(points: List[Tuple[float, float]]) -> Tuple[float, Optional[float]]:
    m_tot = sum(max(0.0, float(m)) for m, _ in points)
    if m_tot <= 0.0:
        return 0.0, None
    xg = sum(max(0.0, float(m)) * float(x) for m, x in points) / m_tot
    return m_tot, xg


# =============================================================================
# ISO 286 (version volontairement limitée à H/h comme ton code actuel)
# =============================================================================

_IT_MULT: Dict[int, int] = {
    5: 7, 6: 10, 7: 16, 8: 25, 9: 40, 10: 64, 11: 100, 12: 160, 13: 250, 14: 400, 15: 640, 16: 1000,
}


def iso286_i_um(D_mm: float) -> float:
    D = _req_pos("D_mm", D_mm)
    return 0.45 * (D ** (1.0 / 3.0)) + 0.001 * D


def iso286_IT_um(D_mm: float, grade: int) -> float:
    if grade not in _IT_MULT:
        raise ValueError(f"Grade IT non supporté: {grade}. Supportés: {sorted(_IT_MULT)}")
    return float(_IT_MULT[grade]) * iso286_i_um(D_mm)


def iso286_hole_H(D_mm: float, grade: int) -> Tuple[float, float]:
    IT = iso286_IT_um(D_mm, grade)
    return (0.0, IT)


def iso286_shaft_h(D_mm: float, grade: int) -> Tuple[float, float]:
    IT = iso286_IT_um(D_mm, grade)
    return (-IT, 0.0)


# =============================================================================
# Matériaux
# =============================================================================

def _materiau_props(
    cle: Optional[str],
    *,
    mode: Literal["min", "typique", "max"] = "typique",
) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {
        "densite_kg_m3": None,
        "limite_elastique_pa": None,
        "module_young_pa": None,
        "poisson": None,
        "alpha_dilatation_1_k": None,
        "conductivite_w_mk": None,
        "module_elastomere_pa": None,
    }
    if not cle or get_materiau is None:
        return out

    m = get_materiau(cle)
    if m is None:
        return out

    lim_el = None
    try:
        if hasattr(m, "limite_elastique_effective_pa"):
            lim_el = m.limite_elastique_effective_pa(mode="min", section_mm=None)
    except Exception:
        lim_el = None

    if lim_el is None:
        lim_el = valeur(getattr(m, "limite_elastique_pa", None), mode=mode)

    out["densite_kg_m3"] = valeur(getattr(m, "densite_kg_m3", None), mode=mode)
    out["limite_elastique_pa"] = lim_el
    out["module_young_pa"] = valeur(getattr(m, "module_young_pa", None), mode=mode)
    out["poisson"] = valeur(getattr(m, "poisson", None), mode=mode)
    out["alpha_dilatation_1_k"] = valeur(getattr(m, "alpha_dilatation_1_k", None), mode=mode)
    out["conductivite_w_mk"] = valeur(getattr(m, "conductivite_thermique_w_mk", None), mode=mode)

    out["module_elastomere_pa"] = valeur(getattr(m, "module_elastomere_pa", None), mode=mode)
    if out["module_elastomere_pa"] is None:
        out["module_elastomere_pa"] = out["module_young_pa"]

    return out


# =============================================================================
# Rainure joint torique
# =============================================================================
# Convention :
# - piston Ø extérieur = D_piston
# - cylindre alésage = D_alesage
# - jeu radial c = (D_alesage - D_piston) / 2
# - section tore = d
# - squeeze radial s = (d - pr - c)/d
#   => profondeur radiale pr = d*(1-s) - c
# - largeur gorge = facteur_largeur * d

def rainure_profondeur_radiale_m(section_joint_m: float, squeeze: float, jeu_radial_m: float) -> float:
    d = _req_pos("section_joint_m", section_joint_m)
    s = _req_pos("squeeze", squeeze, strict=False)
    if not (0.0 < s < 1.0):
        raise ValueError("squeeze doit être dans (0,1).")
    c = _req_pos("jeu_radial_m", jeu_radial_m, strict=False)
    return d * (1.0 - s) - c


def rainure_largeur_m(section_joint_m: float, facteur_largeur: float) -> float:
    return _req_pos("facteur_largeur", facteur_largeur) * _req_pos("section_joint_m", section_joint_m)


def volume_gorge_annulaire_m3(D_fond_gorge_m: float, largeur_m: float, profondeur_radiale_m: float) -> float:
    return _perimetre(_req_pos("D_fond_gorge_m", D_fond_gorge_m)) * _req_pos("largeur_m", largeur_m) * _req_pos("profondeur_radiale_m", profondeur_radiale_m)


# =============================================================================
# Règles explicites de conception piston
# =============================================================================

PositionPremierJoint = Literal["proche_tete", "centre_jupe"]


@dataclass(frozen=True)
class ReglesFabricationPiston:
    coefficient_hauteur_mini_sur_diametre: float = 0.70
    surlongueur_mini_apres_derniere_rainure_m: float = 0.004
    marge_tete_avant_premiere_rainure_m: float = 0.004
    marge_fond_jupe_m: float = 0.004

    position_premier_joint: PositionPremierJoint = "proche_tete"
    entraxe_joints_min_m: float = 0.004
    entraxe_joints_multiple_largeur: float = 1.50
    marge_axiale_rainure_min_m: float = 0.002
    coefficient_largeur_bande_contact_joint: float = 1.00

    chanfrein_min_m: float = 0.0005
    chanfrein_max_m: float = 0.0020
    ratio_chanfrein_sur_jeu: float = 8.0

    rayon_fond_rainure_min_m: float = 0.0002
    rayon_fond_rainure_max_m: float = 0.0010
    ratio_rayon_fond_rainure_sur_profondeur: float = 0.20

    rayon_conge_tete_jupe_min_m: float = 0.0005
    rayon_conge_tete_jupe_max_m: float = 0.0030
    ratio_conge_sur_epaisseur_tete: float = 0.25

    rugosite_exterieure_ra_um: float = 0.8
    rugosite_faces_ra_um: float = 1.6
    rugosite_fond_rainure_ra_um: float = 1.6

    tolerance_diametre_exterieur_m: float = 0.00003
    tolerance_hauteur_m: float = 0.00010
    tolerance_position_rainure_m: float = 0.00005
    tolerance_largeur_rainure_m: float = 0.00005
    tolerance_profondeur_rainure_m: float = 0.00005


# =============================================================================
# Résolution robuste depuis le cylindre
# =============================================================================

def _resoudre_depuis_cylindre(cylindre: Optional[Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "rapport": None,
        "alesage_m": None,
        "course_m": None,
        "pression_max_pa": None,
        "temperature_fonctionnement_k": None,
        "materiau_cle": None,
        "geo_cao": None,
        "diametre_interieur_nominal_m": None,
        "jeu_piston_cylindre_m": None,
        "chanfrein_entree_piston_m": None,
        "rayon_conge_m": None,
        "rugosite_alesage_ra_um": None,
        "tolerance_alesage_m": None,
    }

    if cylindre is None:
        return out

    rep: Optional[Dict[str, Any]] = None
    try:
        if hasattr(cylindre, "analyser") and callable(getattr(cylindre, "analyser")):
            rep = cylindre.analyser(strict=False)  # type: ignore
        elif isinstance(cylindre, dict):
            rep = cylindre
    except Exception:
        rep = None

    if not isinstance(rep, dict):
        return out

    out["rapport"] = rep
    ent = rep.get("entrees", {}) if isinstance(rep.get("entrees", {}), dict) else {}
    geo = rep.get("geometrie", {}) if isinstance(rep.get("geometrie", {}), dict) else {}
    cao = geo.get("cao", {}) if isinstance(geo.get("cao", {}), dict) else {}

    out["alesage_m"] = ent.get("alesage_m")
    out["course_m"] = ent.get("course_m")
    out["pression_max_pa"] = ent.get("pression_max_pa")
    out["materiau_cle"] = ent.get("materiau_cle")
    out["geo_cao"] = cao if cao else None

    t_serv_c = ent.get("temperature_service_C")
    if _is_finite(t_serv_c):
        out["temperature_fonctionnement_k"] = float(t_serv_c) + 273.15

    if cao:
        out["diametre_interieur_nominal_m"] = cao.get("diametre_interieur_nominal_m")
        out["jeu_piston_cylindre_m"] = cao.get("jeu_piston_cylindre_m")
        out["chanfrein_entree_piston_m"] = cao.get("chanfrein_entree_piston_m")
        out["rayon_conge_m"] = cao.get("rayon_conge_m")
        out["rugosite_alesage_ra_um"] = cao.get("rugosite_alesage_ra_um")
        out["tolerance_alesage_m"] = cao.get("tolerance_alesage_m")

    if out["diametre_interieur_nominal_m"] is None:
        out["diametre_interieur_nominal_m"] = geo.get("diametre_interne_m")

    return out


# =============================================================================
# Positions de rainures
# =============================================================================

def _calcul_positions_rainures_piston(
    *,
    hauteur_totale_m: float,
    epaisseur_tete_m: float,
    longueur_jupe_m: float,
    nb_joints: int,
    largeur_rainure_m: float,
    marge_tete_avant_premiere_rainure_m: float,
    marge_fond_jupe_m: float,
    entraxe_rainures_m: float,
    position_premier_joint: PositionPremierJoint,
) -> List[float]:
    H = _req_pos("hauteur_totale_m", hauteur_totale_m)
    et = _req_pos("epaisseur_tete_m", epaisseur_tete_m, strict=False)
    Lj = _req_pos("longueur_jupe_m", longueur_jupe_m, strict=False)
    n = _req_int_ge("nb_joints", nb_joints, min_value=1)
    w = _req_pos("largeur_rainure_m", largeur_rainure_m)
    mt = _req_pos("marge_tete_avant_premiere_rainure_m", marge_tete_avant_premiere_rainure_m, strict=False)
    mf = _req_pos("marge_fond_jupe_m", marge_fond_jupe_m, strict=False)
    e = _req_pos("entraxe_rainures_m", entraxe_rainures_m)

    if position_premier_joint == "proche_tete":
        x0 = et + mt + 0.5 * w
    else:
        x0 = H - mf - Lj + 0.5 * w

    xs = [x0 + i * e for i in range(n)]

    for xc in xs:
        x_min = xc - 0.5 * w
        x_max = xc + 0.5 * w
        if x_min < 0.0 or x_max > H:
            raise ValueError(
                "Position de rainure hors hauteur totale du piston "
                f"(xc={xc}, w={w}, H={H})."
            )
    return xs


# =============================================================================
# Piston
# =============================================================================

@dataclass
class Piston:
    cylindre: Optional[Any] = None

    materiau_piston_cle: Optional[str] = None
    materiau_cylindre_cle: Optional[str] = None
    mode_materiau: Literal["min", "typique", "max"] = "typique"

    temperature_ref_k: float = 293.15

    pression_max_pa: Optional[float] = None
    temperature_fonctionnement_k: Optional[float] = None

    # Températures locales piston / cylindre
    temperature_tete_k: Optional[float] = None
    temperature_zone_segments_k: Optional[float] = None
    temperature_jupe_k: Optional[float] = None
    temperature_axe_k: Optional[float] = None
    temperature_cylindre_tete_k: Optional[float] = None
    temperature_cylindre_zone_segments_k: Optional[float] = None
    temperature_cylindre_jupe_k: Optional[float] = None
    temperature_tete_face_chaude_k: Optional[float] = None
    temperature_tete_face_froide_k: Optional[float] = None
    temperature_cycle_tete_min_k: Optional[float] = None

    # Géométrie locale de référence
    diametre_tete_ref_m: Optional[float] = None
    diametre_zone_segments_ref_m: Optional[float] = None
    diametre_jupe_ref_m: Optional[float] = None
    diametre_axe_ref_m: Optional[float] = None
    diametre_jupe_poussee_ref_m: Optional[float] = None
    diametre_jupe_contre_poussee_ref_m: Optional[float] = None

    alesage_nominal_m: Optional[float] = None
    course_m: Optional[float] = None
    rpm: Optional[float] = None

    fit_hole: Optional[str] = None
    fit_shaft: Optional[str] = None

    k_sigma_plaque: Optional[float] = None
    contrainte_admissible_pa: Optional[float] = None
    facteur_securite: float = 2.0
    epaisseur_tete_m: Optional[float] = None

    effort_lateral_N: Optional[float] = None
    pression_palier_admissible_pa: Optional[float] = None
    longueur_jupe_m: Optional[float] = None

    hauteur_totale_m: Optional[float] = None

    # Axe / masses locales
    materiau_axe_cle: Optional[str] = None
    diametre_axe_m: Optional[float] = None
    longueur_axe_m: Optional[float] = None
    position_axe_depuis_face_tete_m: Optional[float] = None
    densite_axe_kg_m3: Optional[float] = None
    poisson_axe: Optional[float] = None
    coef_dilatation_axe_1_k: Optional[float] = None

    # Efforts latéraux / contact jupe
    aire_zone_poussee_m2: Optional[float] = None
    aire_zone_contre_poussee_m2: Optional[float] = None
    fraction_circonference_zone_poussee: Optional[float] = None
    fraction_circonference_zone_contre_poussee: Optional[float] = None
    pression_contact_jupe_admissible_pa: Optional[float] = None

    nb_joints: Optional[int] = None
    section_joint_mm: Optional[float] = None
    squeeze: Optional[float] = None
    facteur_largeur_rainure: Optional[float] = None

    materiau_joint_cle: Optional[str] = None
    module_elastomere_pa: Optional[float] = None
    coeff_frottement_joint: Optional[float] = None
    largeur_bande_contact_joint_m: Optional[float] = None
    PV_admissible_pa_ms: Optional[float] = None
    type_etancheite: Literal["joint_torique", "segment"] = "joint_torique"
    epaisseur_levre_superieure_m: Optional[float] = None
    epaisseur_levre_inferieure_m: Optional[float] = None
    pression_matage_admissible_pa: Optional[float] = None
    contrainte_levre_admissible_pa: Optional[float] = None
    masse_joints_kg: Optional[float] = None
    masse_segments_kg: Optional[float] = None
    masse_segment_unitaire_kg: Optional[float] = None
    force_appui_segment_n: Optional[float] = None
    jeu_axial_segment_m: Optional[float] = None

    longueur_portee_etanche_m: Optional[float] = None
    pression_aval_pa: Optional[float] = None

    masse_alternative_kg: Optional[float] = None
    longueur_bielle_m: Optional[float] = None
    angle_vilebrequin_deg: Optional[float] = None
    masse_bielle_kg: Optional[float] = None
    fraction_bielle_alternative: Optional[float] = None

    coefficient_usure_joint_k: Optional[float] = None
    durete_contact_joint_pa: Optional[float] = None
    duree_fonctionnement_s: Optional[float] = None

    # Thermo-mécanique tête
    facteur_contrainte_thermique_tete: Optional[float] = None
    poisson_piston: Optional[float] = None

    regles_fabrication: ReglesFabricationPiston = field(default_factory=ReglesFabricationPiston)

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rap: Dict[str, Any] = {
            "piece": "piston",
            "entrees": {},
            "liaisons": {},
            "materiaux": {},
            "iso286": {},
            "dimensions": {},
            "jeux": {},
            "thermique": {},
            "thermique_zonee": {},
            "contraintes": {},
            "contraintes_tete": {},
            "joints": {},
            "rainures": {},
            "efforts_lateraux": {},
            "frottements": {},
            "masses": {},
            "fuites": {},
            "cinematique": {},
            "usure": {},
            "notes_modele": [],
            "inconnues": {"impossibles": [], "partielles": []},
        }

        # ---------------------------------------------------------------------
        # 1) Lecture cylindre
        # ---------------------------------------------------------------------
        cyl = _resoudre_depuis_cylindre(self.cylindre)

        Dcyl = self.alesage_nominal_m if self.alesage_nominal_m is not None else (cyl["diametre_interieur_nominal_m"] or cyl["alesage_m"])
        Pmax = self.pression_max_pa if self.pression_max_pa is not None else cyl["pression_max_pa"]
        Tfn = self.temperature_fonctionnement_k if self.temperature_fonctionnement_k is not None else cyl["temperature_fonctionnement_k"]
        course = self.course_m if self.course_m is not None else cyl["course_m"]

        materiau_cylindre_cle_effectif = self.materiau_cylindre_cle
        if materiau_cylindre_cle_effectif is None and cyl["materiau_cle"]:
            materiau_cylindre_cle_effectif = str(cyl["materiau_cle"])

        rap["liaisons"]["cylindre"] = {
            "cylindre_fournit": self.cylindre is not None,
            "alesage_nominal_m": Dcyl,
            "pression_max_pa": Pmax,
            "temperature_fonctionnement_k": Tfn,
            "course_m": course,
            "materiau_cylindre_cle": materiau_cylindre_cle_effectif,
            "geo_cao_disponible": cyl["geo_cao"] is not None,
            "jeu_piston_cylindre_m": cyl["jeu_piston_cylindre_m"],
            "chanfrein_entree_piston_m": cyl["chanfrein_entree_piston_m"],
            "rayon_conge_m": cyl["rayon_conge_m"],
            "rugosite_alesage_ra_um": cyl["rugosite_alesage_ra_um"],
            "tolerance_alesage_m": cyl["tolerance_alesage_m"],
        }

        if Dcyl is None:
            _push_inc(rap, "impossibles", "alesage_nominal_m", "Requis ou déductible depuis un cylindre analysable.")
        else:
            Dcyl = _req_pos("alesage_nominal_m", Dcyl)

        if Pmax is None:
            _push_inc(rap, "partielles", "pression_max_pa", "Utile pour force gaz, tête, étanchéité et fuite.")
        else:
            Pmax = _req_pos("pression_max_pa", Pmax, strict=False)

        if Tfn is None:
            _push_inc(rap, "partielles", "temperature_fonctionnement_k", "Utile pour jeu à chaud et viscosité.")
        else:
            Tfn = _req_pos("temperature_fonctionnement_k", Tfn)

        if course is None:
            _push_inc(rap, "partielles", "course_m", "Utile pour vitesse piston, PV et usure.")
        else:
            course = _req_pos("course_m", course, strict=False)

        # ---------------------------------------------------------------------
        # 2) ISO 286
        # ---------------------------------------------------------------------
        D_hole_min = D_hole_max = None
        D_piston_min = D_piston_max = None
        D_piston_cao = None

        if Dcyl is not None and self.fit_hole and self.fit_shaft:
            def parse_fit(s: str) -> Tuple[str, int]:
                s = s.strip()
                if len(s) < 2:
                    raise ValueError(f"Fit invalide: {s!r}")
                return s[0], int(s[1:])

            hole_L, hole_g = parse_fit(self.fit_hole)
            shaft_L, shaft_g = parse_fit(self.fit_shaft)

            if hole_L != "H":
                _push_inc(rap, "impossibles", "fit_hole", "Seul H est implémenté ici.")
            if shaft_L != "h":
                _push_inc(rap, "impossibles", "fit_shaft", "Seul h est implémenté ici.")

            if hole_L == "H" and shaft_L == "h":
                D_mm = Dcyl * 1e3
                EI_h_um, ES_h_um = iso286_hole_H(D_mm, hole_g)
                ei_s_um, es_s_um = iso286_shaft_h(D_mm, shaft_g)

                D_hole_min = Dcyl + EI_h_um * 1e-6
                D_hole_max = Dcyl + ES_h_um * 1e-6
                D_piston_min = Dcyl + ei_s_um * 1e-6
                D_piston_max = Dcyl + es_s_um * 1e-6
                D_piston_cao = 0.5 * (D_piston_min + D_piston_max)

                jeu_diam_min = D_hole_min - D_piston_max
                jeu_diam_max = D_hole_max - D_piston_min

                rap["iso286"] = {
                    "D_mm": D_mm,
                    "hole": {"fit": self.fit_hole, "EI_um": EI_h_um, "ES_um": ES_h_um},
                    "shaft": {"fit": self.fit_shaft, "ei_um": ei_s_um, "es_um": es_s_um},
                }
                rap["dimensions"]["alesage_min_m"] = D_hole_min
                rap["dimensions"]["alesage_max_m"] = D_hole_max
                rap["dimensions"]["diametre_piston_min_m"] = D_piston_min
                rap["dimensions"]["diametre_piston_max_m"] = D_piston_max
                rap["dimensions"]["diametre_piston_cao_centre_m"] = D_piston_cao

                rap["jeux"]["jeu_diametral_min_m"] = jeu_diam_min
                rap["jeux"]["jeu_diametral_max_m"] = jeu_diam_max
                rap["jeux"]["jeu_radial_min_m"] = 0.5 * jeu_diam_min
                rap["jeux"]["jeu_radial_max_m"] = 0.5 * jeu_diam_max
        else:
            jeu_cyl = cyl["jeu_piston_cylindre_m"]
            if Dcyl is not None and _is_finite(jeu_cyl):
                jeu_nom = _req_pos("jeu_piston_cylindre_m", jeu_cyl, strict=False)
                D_piston_cao = Dcyl - 2.0 * jeu_nom
                rap["dimensions"]["diametre_piston_cao_centre_m"] = D_piston_cao
                rap["jeux"]["jeu_radial_nominal_m"] = jeu_nom
                rap["notes_modele"].append("Diamètre piston CAO déduit du jeu nominal fourni par le cylindre.")
            else:
                _push_inc(
                    rap,
                    "impossibles",
                    "diametre_piston_min_max",
                    "Fournir fit_hole + fit_shaft, ou un cylindre avec jeu_piston_cylindre_m exploitable."
                )

        # ---------------------------------------------------------------------
        # 3) Matériaux piston / cylindre / joint
        # ---------------------------------------------------------------------
        props_p = _materiau_props(self.materiau_piston_cle, mode=self.mode_materiau)
        props_c = _materiau_props(materiau_cylindre_cle_effectif, mode=self.mode_materiau)
        props_j = _materiau_props(self.materiau_joint_cle, mode=self.mode_materiau)
        props_a = _materiau_props(self.materiau_axe_cle, mode=self.mode_materiau)

        rap["materiaux"]["piston"] = {
            "materiau_piston_cle": self.materiau_piston_cle,
            **props_p,
        }
        rap["materiaux"]["cylindre"] = {
            "materiau_cylindre_cle": materiau_cylindre_cle_effectif,
            **props_c,
        }
        rap["materiaux"]["joint"] = {
            "materiau_joint_cle": self.materiau_joint_cle,
            **props_j,
        }
        rap["materiaux"]["axe"] = {
            "materiau_axe_cle": self.materiau_axe_cle,
            **props_a,
        }

        # ---------------------------------------------------------------------
        # 4) Jeu à chaud
        # ---------------------------------------------------------------------
        alpha_p = props_p["alpha_dilatation_1_k"]
        alpha_c = props_c["alpha_dilatation_1_k"]

        if Dcyl is not None and Tfn is not None:
            rap["thermique"]["T_ref_k"] = self.temperature_ref_k
            rap["thermique"]["T_fonctionnement_k"] = Tfn
            rap["thermique"]["alpha_piston_1_k"] = alpha_p
            rap["thermique"]["alpha_cylindre_1_k"] = alpha_c

            if alpha_p is None:
                _push_inc(rap, "partielles", "alpha_piston_1_k", "Requis pour le jeu à chaud.")
            if alpha_c is None:
                _push_inc(rap, "partielles", "alpha_cylindre_1_k", "Requis pour le jeu à chaud.")

            if (
                alpha_p is not None and alpha_c is not None and
                D_hole_min is not None and D_hole_max is not None and
                D_piston_min is not None and D_piston_max is not None
            ):
                dT = Tfn - float(self.temperature_ref_k)

                def dil(D_ref: float, a: float) -> float:
                    return D_ref * (1.0 + a * dT)

                D_hole_min_hot = dil(D_hole_min, float(alpha_c))
                D_hole_max_hot = dil(D_hole_max, float(alpha_c))
                D_pis_min_hot = dil(D_piston_min, float(alpha_p))
                D_pis_max_hot = dil(D_piston_max, float(alpha_p))

                jeu_diam_min_hot = D_hole_min_hot - D_pis_max_hot
                jeu_diam_max_hot = D_hole_max_hot - D_pis_min_hot

                rap["thermique"]["alesage_min_hot_m"] = D_hole_min_hot
                rap["thermique"]["alesage_max_hot_m"] = D_hole_max_hot
                rap["thermique"]["piston_min_hot_m"] = D_pis_min_hot
                rap["thermique"]["piston_max_hot_m"] = D_pis_max_hot
                rap["thermique"]["jeu_diam_min_hot_m"] = jeu_diam_min_hot
                rap["thermique"]["jeu_diam_max_hot_m"] = jeu_diam_max_hot
                rap["thermique"]["jeu_rad_min_hot_m"] = 0.5 * jeu_diam_min_hot
                rap["thermique"]["jeu_rad_max_hot_m"] = 0.5 * jeu_diam_max_hot

                rap["contraintes"]["non_grippage_hot_ok"] = (jeu_diam_min_hot > 0.0)
            else:
                _push_inc(rap, "partielles", "jeu_chaud", "Calculable si bornes ISO + alpha piston/cylindre + T sont connus.")

        # ---------------------------------------------------------------------
        # 4 bis) Thermique par zones + dilatation locale / conicité / ovalisation
        # ---------------------------------------------------------------------
        H_tot_dim = rap["dimensions"].get("hauteur_totale_m")
        alpha_axe = self.coef_dilatation_axe_1_k if self.coef_dilatation_axe_1_k is not None else props_a.get("alpha_dilatation_1_k")
        if D_piston_cao is not None:
            zones = {
                "tete": {
                    "diam_ref_m": self.diametre_tete_ref_m if self.diametre_tete_ref_m is not None else D_piston_cao,
                    "T_piston_k": self.temperature_tete_k,
                    "T_cylindre_k": self.temperature_cylindre_tete_k if self.temperature_cylindre_tete_k is not None else Tfn,
                    "alpha_piston_1_k": alpha_p,
                    "alpha_cylindre_1_k": alpha_c,
                    "diam_cyl_ref_m": Dcyl,
                },
                "zone_segments": {
                    "diam_ref_m": self.diametre_zone_segments_ref_m if self.diametre_zone_segments_ref_m is not None else D_piston_cao,
                    "T_piston_k": self.temperature_zone_segments_k,
                    "T_cylindre_k": self.temperature_cylindre_zone_segments_k if self.temperature_cylindre_zone_segments_k is not None else Tfn,
                    "alpha_piston_1_k": alpha_p,
                    "alpha_cylindre_1_k": alpha_c,
                    "diam_cyl_ref_m": Dcyl,
                },
                "jupe": {
                    "diam_ref_m": self.diametre_jupe_ref_m if self.diametre_jupe_ref_m is not None else D_piston_cao,
                    "T_piston_k": self.temperature_jupe_k,
                    "T_cylindre_k": self.temperature_cylindre_jupe_k if self.temperature_cylindre_jupe_k is not None else Tfn,
                    "alpha_piston_1_k": alpha_p,
                    "alpha_cylindre_1_k": alpha_c,
                    "diam_cyl_ref_m": Dcyl,
                },
                "axe": {
                    "diam_ref_m": self.diametre_axe_ref_m if self.diametre_axe_ref_m is not None else self.diametre_axe_m,
                    "T_piston_k": self.temperature_axe_k,
                    "T_cylindre_k": None,
                    "alpha_piston_1_k": alpha_axe,
                    "alpha_cylindre_1_k": None,
                    "diam_cyl_ref_m": None,
                },
            }
            for nom_zone, z in zones.items():
                diam_ref = z["diam_ref_m"]
                T_zone = z["T_piston_k"]
                a_zone = z["alpha_piston_1_k"]
                if diam_ref is None:
                    _push_inc(rap, "partielles", f"zone_{nom_zone}", f"Diamètre de référence manquant pour la zone {nom_zone}.")
                    continue
                rap["thermique_zonee"][nom_zone] = {
                    "diametre_ref_m": diam_ref,
                    "temperature_piston_k": T_zone,
                    "temperature_cylindre_k": z["T_cylindre_k"],
                    "alpha_piston_1_k": a_zone,
                    "alpha_cylindre_1_k": z["alpha_cylindre_1_k"],
                }
                if T_zone is None or a_zone is None:
                    _push_inc(rap, "partielles", f"dilatation_{nom_zone}", f"Calculable si température locale et alpha sont connus pour {nom_zone}.")
                    continue
                dT_zone = float(T_zone) - float(self.temperature_ref_k)
                diam_hot = float(diam_ref) * (1.0 + float(a_zone) * dT_zone)
                rap["thermique_zonee"][nom_zone].update({
                    "delta_t_k": dT_zone,
                    "dilatation_locale_m": diam_hot - float(diam_ref),
                    "diametre_hot_m": diam_hot,
                })
                if z["diam_cyl_ref_m"] is not None and z["T_cylindre_k"] is not None and z["alpha_cylindre_1_k"] is not None:
                    dT_cyl = float(z["T_cylindre_k"]) - float(self.temperature_ref_k)
                    diam_cyl_hot = float(z["diam_cyl_ref_m"]) * (1.0 + float(z["alpha_cylindre_1_k"]) * dT_cyl)
                    jeu_diam = diam_cyl_hot - diam_hot
                    rap["thermique_zonee"][nom_zone].update({
                        "delta_t_cylindre_k": dT_cyl,
                        "diametre_cylindre_hot_m": diam_cyl_hot,
                        "jeu_diametral_fonctionnel_reel_m": jeu_diam,
                        "jeu_radial_fonctionnel_reel_m": 0.5 * jeu_diam,
                    })
            zt = rap["thermique_zonee"].get("tete", {})
            zj = rap["thermique_zonee"].get("jupe", {})
            if zt.get("diametre_hot_m") is not None and zj.get("diametre_hot_m") is not None and H_tot_dim is not None:
                conicite = float(zt["diametre_hot_m"]) - float(zj["diametre_hot_m"])
                rap["thermique_zonee"]["conicite_theorique_m"] = conicite
                if float(H_tot_dim) > 0.0:
                    rap["thermique_zonee"]["conicite_theorique_m_par_m"] = conicite / float(H_tot_dim)
            else:
                _push_inc(rap, "partielles", "conicite_theorique", "Calculable si diamètres chauds tête/jupe et hauteur totale sont connus.")
            if self.diametre_jupe_poussee_ref_m is not None and self.diametre_jupe_contre_poussee_ref_m is not None and self.temperature_jupe_k is not None and alpha_p is not None:
                dTj = float(self.temperature_jupe_k) - float(self.temperature_ref_k)
                Dp_hot = float(self.diametre_jupe_poussee_ref_m) * (1.0 + float(alpha_p) * dTj)
                Dc_hot = float(self.diametre_jupe_contre_poussee_ref_m) * (1.0 + float(alpha_p) * dTj)
                rap["thermique_zonee"].setdefault("jupe", {})
                rap["thermique_zonee"]["jupe"].update({
                    "diametre_poussee_hot_m": Dp_hot,
                    "diametre_contre_poussee_hot_m": Dc_hot,
                    "ovalisation_theorique_m": Dp_hot - Dc_hot,
                })
            else:
                _push_inc(rap, "partielles", "ovalisation_theorique", "Calculable si diamètres jupe poussée/contre-poussée et température de jupe sont fournis.")

        # ---------------------------------------------------------------------
        # 5) Tête
        # ---------------------------------------------------------------------
        ep_tete = None
        if self.epaisseur_tete_m is not None:
            ep_tete = _req_pos("epaisseur_tete_m", self.epaisseur_tete_m)
            rap["dimensions"]["epaisseur_tete_m"] = ep_tete
        else:
            if Dcyl is None or Pmax is None or self.k_sigma_plaque is None:
                _push_inc(rap, "partielles", "epaisseur_tete_min_m", "Calculable si alesage, pression_max et k_sigma_plaque sont fournis.")
            else:
                sigma_adm = self.contrainte_admissible_pa
                if sigma_adm is None and props_p["limite_elastique_pa"] is not None:
                    sigma_adm = float(props_p["limite_elastique_pa"]) / _req_pos("facteur_securite", self.facteur_securite)
                    rap["notes_modele"].append("Contrainte admissible piston déduite de Re / facteur_securite.")

                if sigma_adm is None:
                    _push_inc(rap, "partielles", "contrainte_admissible_pa", "Fournir contrainte_admissible_pa ou matériau piston avec Re.")
                else:
                    a = 0.5 * Dcyl
                    ksig = _req_pos("k_sigma_plaque", self.k_sigma_plaque)
                    ep_tete = a * math.sqrt(ksig * float(Pmax) / float(sigma_adm))
                    rap["dimensions"]["epaisseur_tete_min_m"] = ep_tete
                    rap["notes_modele"].append("Épaisseur tête issue du modèle explicite sigma = k*p*(a²/t²).")

        # ---------------------------------------------------------------------
        # 5 bis) Thermo-mécanique tête de piston
        # ---------------------------------------------------------------------
        if ep_tete is not None and self.k_sigma_plaque is not None and Pmax is not None and Dcyl is not None:
            rap["contraintes_tete"]["contrainte_pression_pa"] = _contrainte_tete_plaque_pa(self.k_sigma_plaque, Pmax, Dcyl, ep_tete)
        else:
            _push_inc(rap, "partielles", "contrainte_pression_tete", "Calculable si epaisseur_tete, k_sigma_plaque, pression_max et alesage sont connus.")

        E_p = props_p.get("module_young_pa")
        nu_p = self.poisson_piston if self.poisson_piston is not None else props_p.get("poisson")
        if self.temperature_tete_face_chaude_k is not None and self.temperature_tete_face_froide_k is not None and ep_tete is not None:
            grad = _gradient_thermique_k_m(self.temperature_tete_face_chaude_k, self.temperature_tete_face_froide_k, ep_tete)
            rap["contraintes_tete"]["gradient_thermique_k_m"] = grad
            rap["contraintes_tete"]["delta_t_travers_epaisseur_k"] = float(self.temperature_tete_face_chaude_k) - float(self.temperature_tete_face_froide_k)
            if E_p is not None and alpha_p is not None and nu_p is not None and self.facteur_contrainte_thermique_tete is not None:
                sigma_th = _contrainte_thermique_biaxiale_pa(E_p, alpha_p, float(self.temperature_tete_face_chaude_k) - float(self.temperature_tete_face_froide_k), nu_p, self.facteur_contrainte_thermique_tete)
                rap["contraintes_tete"]["contrainte_thermique_pa"] = sigma_th
                if rap["contraintes_tete"].get("contrainte_pression_pa") is not None:
                    rap["contraintes_tete"]["contrainte_combinee_pression_thermique_pa"] = float(rap["contraintes_tete"]["contrainte_pression_pa"]) + sigma_th
            else:
                _push_inc(rap, "partielles", "contrainte_thermique_tete", "Calculable si E, alpha, poisson et facteur_contrainte_thermique_tete sont connus.")
        else:
            _push_inc(rap, "partielles", "gradient_thermique_tete", "Calculable si températures face chaude/froide et épaisseur de tête sont connues.")

        if self.temperature_tete_k is not None and self.temperature_cycle_tete_min_k is not None:
            alt = 0.5 * (float(self.temperature_tete_k) - float(self.temperature_cycle_tete_min_k))
            rap["contraintes_tete"]["alternance_thermique_k"] = alt
            if E_p is not None and alpha_p is not None and nu_p is not None and self.facteur_contrainte_thermique_tete is not None:
                rap["contraintes_tete"]["contrainte_alternee_thermique_pa"] = abs(_contrainte_thermique_biaxiale_pa(E_p, alpha_p, 2.0 * alt, nu_p, self.facteur_contrainte_thermique_tete)) * 0.5
        else:
            _push_inc(rap, "partielles", "alternance_thermique_tete", "Calculable si température tête max et température mini de cycle sont fournies.")

        # ---------------------------------------------------------------------
        # 6) Jupe
        # ---------------------------------------------------------------------
        L_jupe = None
        F_lateral_design: Optional[float] = None
        if self.effort_lateral_N is not None:
            F_lateral_design = _req_pos("effort_lateral_N", self.effort_lateral_N, strict=False)
        elif Pmax is not None and Dcyl is not None and self.longueur_bielle_m is not None and self.angle_vilebrequin_deg is not None and course is not None:
            F_gaz_design = float(calcul_force_gaz(pression_pa=Pmax, alesage_m=Dcyl, allow_negative_pression=True, allow_zero_alesage=False, clamp_non_negative=False, return_details=False))
            F_in_design = None
            if self.masse_alternative_kg is not None and self.rpm is not None:
                F_in_design = float(calcul_force_inertie_alternative(masse_alternative_kg=self.masse_alternative_kg, rayon_manivelle_m=0.5 * float(course), vitesse_rotation_tr_min=self.rpm, longueur_bielle_m=self.longueur_bielle_m, angle_vilebrequin_deg=self.angle_vilebrequin_deg, angle_unite="deg", input_vitesse="rpm", clamp_ratio_r_sur_l=False, return_details=False))
            F_ax_design = F_gaz_design - (F_in_design or 0.0)
            F_lateral_design = abs(_force_laterale_piston(F_ax_design, 0.5 * float(course), self.longueur_bielle_m, self.angle_vilebrequin_deg)["force_laterale_n"])
            rap["notes_modele"].append("Effort latéral de jupe déduit de F_axiale * tan(beta) quand effort_lateral_N n'est pas fourni.")
        if self.longueur_jupe_m is not None:
            L_jupe = _req_pos("longueur_jupe_m", self.longueur_jupe_m)
            rap["dimensions"]["longueur_jupe_m"] = L_jupe
        else:
            if Dcyl is None or F_lateral_design is None or self.pression_palier_admissible_pa is None:
                _push_inc(rap, "partielles", "longueur_jupe_min_m", "Calculable si alesage, effort latéral de jupe et pression_palier_admissible_pa sont fournis ou déductibles.")
            else:
                p_adm = _req_pos("pression_palier_admissible_pa", self.pression_palier_admissible_pa)
                L_jupe = F_lateral_design / (_perimetre(Dcyl) * p_adm) if p_adm > 0 else None
                if L_jupe is not None:
                    rap["dimensions"]["longueur_jupe_min_m"] = L_jupe
                    rap["notes_modele"].append("Longueur jupe issue du modèle p = F_lateral / (πDL).")

        # ---------------------------------------------------------------------
        # 7) Joints / rainures / positions axiales
        # ---------------------------------------------------------------------
        nbj = None
        if self.nb_joints is None:
            self.nb_joints = max(2, int((Dcyl * 1000) // 25)) if Dcyl is not None else 3
            rap["notes_modele"].append(f"nb_joints déduit (défaut intelligent={self.nb_joints}).")

        nbj = _req_int_ge("nb_joints", self.nb_joints, min_value=0)

        jeu_radial_ref = rap["jeux"].get("jeu_radial_min_m", rap["jeux"].get("jeu_radial_nominal_m"))
        rainures: List[Dict[str, Any]] = []

        if nbj is not None and nbj > 0:
            if self.section_joint_mm is None and Dcyl is not None:
                self.section_joint_mm = max(1.5, min(6.0, Dcyl * 1000 * 0.05))  # ex: proportionnel à Dcyl
                rap["notes_modele"].append(f"section_joint_mm déduite ({self.section_joint_mm:.2f} mm).")
            if self.squeeze is None:
                self.squeeze = 0.15
                rap["notes_modele"].append("squeeze déduit par défaut (0.15).")
            if self.facteur_largeur_rainure is None:
                self.facteur_largeur_rainure = 1.3
                rap["notes_modele"].append("facteur_largeur_rainure déduit par défaut (1.3).")

            if self.section_joint_mm is None or self.squeeze is None or self.facteur_largeur_rainure is None:
                _push_inc(
                    rap,
                    "impossibles",
                    "rainures_joint",
                    "Impossible sans section_joint_mm, squeeze et facteur_largeur_rainure."
                )
            elif D_piston_cao is None or Dcyl is None or jeu_radial_ref is None:
                _push_inc(
                    rap,
                    "impossibles",
                    "rainures_joint",
                    "Impossible sans diamètre piston CAO, diamètre cylindre et jeu radial."
                )
            else:
                d = _req_pos("section_joint_mm", self.section_joint_mm) * 1e-3
                s = _req_pos("squeeze", self.squeeze, strict=False)
                if not (0.0 < s < 1.0):
                    raise ValueError("squeeze doit être dans (0,1).")

                fw = _req_pos("facteur_largeur_rainure", self.facteur_largeur_rainure)
                c = _req_pos("jeu_radial_ref", jeu_radial_ref, strict=False)

                pr = rainure_profondeur_radiale_m(d, s, c)
                w = rainure_largeur_m(d, fw)

                if pr <= 0.0:
                    _push_inc(
                        rap,
                        "impossibles",
                        "profondeur_rainure",
                        "Profondeur <= 0 : couple section_joint/squeeze/jeu incohérent."
                    )
                else:
                    D_pis = _req_pos("D_piston_cao", D_piston_cao)
                    D_fond = D_pis - 2.0 * pr
                    if D_fond <= 0.0:
                        _push_inc(
                            rap,
                            "impossibles",
                            "diametre_fond_rainure_m",
                            "Diamètre fond de rainure <= 0."
                        )

                    r_fond = _borne(
                        self.regles_fabrication.ratio_rayon_fond_rainure_sur_profondeur * pr,
                        self.regles_fabrication.rayon_fond_rainure_min_m,
                        self.regles_fabrication.rayon_fond_rainure_max_m,
                    )

                    bande_contact = self.largeur_bande_contact_joint_m
                    if bande_contact is None:
                        bande_contact = self.regles_fabrication.coefficient_largeur_bande_contact_joint * d

                    entraxe = max(
                        self.regles_fabrication.entraxe_joints_min_m,
                        self.regles_fabrication.entraxe_joints_multiple_largeur * w,
                    )

                    H_min_geom = max(
                        self.regles_fabrication.coefficient_hauteur_mini_sur_diametre * D_pis,
                        (ep_tete or 0.0)
                        + self.regles_fabrication.marge_tete_avant_premiere_rainure_m
                        + nbj * w
                        + max(0, nbj - 1) * entraxe
                        + (L_jupe or 0.0)
                        + self.regles_fabrication.marge_fond_jupe_m,
                    )

                    H_tot = self.hauteur_totale_m
                    if H_tot is None:
                        H_tot = H_min_geom
                        rap["notes_modele"].append(
                            "Hauteur totale piston déduite des règles explicites tête + rainures + jupe."
                        )
                    H_tot = _req_pos("hauteur_totale_m", H_tot)
                    rap["dimensions"]["hauteur_totale_m"] = H_tot
                    rap["dimensions"]["hauteur_totale_min_geometrique_m"] = H_min_geom

                    if L_jupe is None:
                        zone_rainures = nbj * w + max(0, nbj - 1) * entraxe
                        L_jupe_calc = (
                            H_tot
                            - (ep_tete or 0.0)
                            - self.regles_fabrication.marge_tete_avant_premiere_rainure_m
                            - zone_rainures
                            - self.regles_fabrication.marge_fond_jupe_m
                        )
                        if L_jupe_calc > 0.0:
                            L_jupe = L_jupe_calc
                            rap["dimensions"]["longueur_jupe_calculee_depuis_hauteur_m"] = L_jupe
                        else:
                            _push_inc(
                                rap,
                                "impossibles",
                                "longueur_jupe_calculee",
                                "Hauteur totale insuffisante pour loger tête + rainures."
                            )

                    if L_jupe is None:
                        _push_inc(
                            rap,
                            "impossibles",
                            "positions_rainures",
                            "Impossible de positionner correctement les rainures sans longueur_jupe."
                        )
                    else:
                        positions_centres = _calcul_positions_rainures_piston(
                            hauteur_totale_m=H_tot,
                            epaisseur_tete_m=(ep_tete or 0.0),
                            longueur_jupe_m=L_jupe,
                            nb_joints=nbj,
                            largeur_rainure_m=w,
                            marge_tete_avant_premiere_rainure_m=self.regles_fabrication.marge_tete_avant_premiere_rainure_m,
                            marge_fond_jupe_m=self.regles_fabrication.marge_fond_jupe_m,
                            entraxe_rainures_m=entraxe,
                            position_premier_joint=self.regles_fabrication.position_premier_joint,
                        )

                        h_dispo = 0.5 * (Dcyl - D_fond)
                        squeeze_reconstruit = ((d - h_dispo) / d) if d > 0.0 else None
                        D_moy_monte = D_fond + d
                        D_montage = D_fond

                        for i, x_c in enumerate(positions_centres):
                            x_min = x_c - 0.5 * w
                            x_max = x_c + 0.5 * w

                            rainure_i = {
                                "index": i + 1,
                                "orientation": "gorge_externe_sur_piston",
                                "position_centre_depuis_face_tete_m": x_c,
                                "position_debut_depuis_face_tete_m": x_min,
                                "position_fin_depuis_face_tete_m": x_max,
                                "largeur_m": w,
                                "profondeur_radiale_m": pr,
                                "diametre_fond_rainure_m": D_fond,
                                "rayon_fond_rainure_m": r_fond,
                                "diametre_zone_hors_rainure_m": D_pis,
                                "diametre_interieur_cylindre_m": Dcyl,
                                "hauteur_radiale_disponible_m": h_dispo,
                                "section_joint_m": d,
                                "squeeze_cible": s,
                                "squeeze_reconstruit": squeeze_reconstruit,
                                "jeu_radial_ref_m": c,
                                "diametre_montage_joint_m": D_montage,
                                "diametre_moyen_joint_monte_m": D_moy_monte,
                                "largeur_bande_contact_joint_m": bande_contact,
                                "volume_gorge_m3": volume_gorge_annulaire_m3(D_fond, w, pr),
                            }
                            rainures.append(rainure_i)

                        rap["joints"]["nb_joints"] = nbj
                        rap["joints"]["section_joint_m"] = d
                        rap["joints"]["squeeze"] = s
                        rap["joints"]["facteur_largeur_rainure"] = fw
                        rap["joints"]["jeu_radial_ref_m"] = c
                        rap["joints"]["profondeur_radiale_rainure_m"] = pr
                        rap["joints"]["largeur_rainure_m"] = w
                        rap["joints"]["diametre_piston_zone_hors_rainure_m"] = D_pis
                        rap["joints"]["diametre_fond_rainure_m"] = D_fond
                        rap["joints"]["rayon_fond_rainure_m"] = r_fond
                        rap["joints"]["diametre_interieur_cylindre_m"] = Dcyl
                        rap["joints"]["hauteur_radiale_disponible_m"] = h_dispo
                        rap["joints"]["diametre_montage_joint_m"] = D_montage
                        rap["joints"]["diametre_moyen_joint_monte_m"] = D_moy_monte
                        rap["joints"]["entraxe_rainures_m"] = entraxe
                        rap["joints"]["positions_centres_depuis_face_tete_m"] = positions_centres
                        rap["joints"]["rainures"] = rainures
                        rap["joints"]["volume_gorge_unitaire_m3"] = volume_gorge_annulaire_m3(D_fond, w, pr)
                        rap["joints"]["volume_gorges_total_m3"] = rap["joints"]["volume_gorge_unitaire_m3"] * nbj

                        rap["joints"]["verif"] = {
                            "profondeur_radiale_positive": (pr > 0.0),
                            "diametre_fond_rainure_positif": (D_fond > 0.0),
                            "squeeze_reconstruit": squeeze_reconstruit,
                            "rainures_dans_hauteur": all(
                                (ri["position_debut_depuis_face_tete_m"] >= 0.0) and
                                (ri["position_fin_depuis_face_tete_m"] <= H_tot)
                                for ri in rainures
                            ),
                            "hauteur_radiale_disponible_positive": (h_dispo > 0.0),
                        }

                        Eel = self.module_elastomere_pa if self.module_elastomere_pa is not None else props_j.get("module_elastomere_pa")
                        if Eel is not None:
                            Eel = _req_pos("module_elastomere_pa", Eel)
                            p_contact = Eel * s
                            rap["joints"]["module_elastomere_pa"] = Eel
                            rap["joints"]["pression_contact_estimee_pa"] = p_contact
                            if Pmax is not None:
                                rap["joints"]["etancheite_contact_ok_si_p_contact_sup_pmax"] = (p_contact > float(Pmax))

                            per_joint = _perimetre(D_pis)
                            F_joint_unitaire = p_contact * per_joint * bande_contact
                            A_fond = _perimetre(D_fond) * w
                            p_fond = F_joint_unitaire / A_fond if A_fond > 0.0 else None
                            rap["rainures"].update({
                                "force_radiale_unitaire_joint_n": F_joint_unitaire,
                                "aire_fond_rainure_m2": A_fond,
                                "pression_contact_fond_rainure_pa": p_fond,
                            })
                            if self.pression_matage_admissible_pa is not None and p_fond is not None:
                                rap["rainures"]["matage_ok"] = p_fond <= _req_pos("pression_matage_admissible_pa", self.pression_matage_admissible_pa)
                            elif props_p.get("limite_elastique_pa") is not None and p_fond is not None:
                                rap["rainures"]["matage_ok_vs_re_piston"] = p_fond <= float(props_p["limite_elastique_pa"])
                            if self.epaisseur_levre_superieure_m is not None:
                                sigma_levre_sup = F_joint_unitaire / (_perimetre(D_fond) * _req_pos("epaisseur_levre_superieure_m", self.epaisseur_levre_superieure_m))
                                rap["rainures"]["contrainte_levre_superieure_pa"] = sigma_levre_sup
                                if self.contrainte_levre_admissible_pa is not None:
                                    rap["rainures"]["levre_superieure_ok"] = sigma_levre_sup <= _req_pos("contrainte_levre_admissible_pa", self.contrainte_levre_admissible_pa)
                            if self.epaisseur_levre_inferieure_m is not None:
                                sigma_levre_inf = F_joint_unitaire / (_perimetre(D_fond) * _req_pos("epaisseur_levre_inferieure_m", self.epaisseur_levre_inferieure_m))
                                rap["rainures"]["contrainte_levre_inferieure_pa"] = sigma_levre_inf
                                if self.contrainte_levre_admissible_pa is not None:
                                    rap["rainures"]["levre_inferieure_ok"] = sigma_levre_inf <= _req_pos("contrainte_levre_admissible_pa", self.contrainte_levre_admissible_pa)
                            if self.coefficient_usure_joint_k is not None and self.durete_contact_joint_pa is not None and self.duree_fonctionnement_s is not None and course is not None and self.rpm is not None and p_fond is not None:
                                v_moy_r = float(calcul_vitesse_moyenne_piston(float(course), float(self.rpm)))
                                distance_r = v_moy_r * _req_pos("duree_fonctionnement_s", self.duree_fonctionnement_s, strict=False)
                                Vw_r = calcul_volume_usure_archard(coefficient_usure_k=self.coefficient_usure_joint_k, charge_normale_w=F_joint_unitaire, distance_glissement_ls=distance_r, durete_h=self.durete_contact_joint_pa)
                                dh_r = calcul_perte_epaisseur(Vw_r, A_fond)
                                rap["rainures"]["usure_fond_rainure"] = {"distance_glissement_m": distance_r, "volume_use_m3": Vw_r, "perte_epaisseur_m": dh_r}
                            if self.type_etancheite == "segment" and self.masse_segment_unitaire_kg is not None and self.force_appui_segment_n is not None and r_manivelle is not None and self.longueur_bielle_m is not None and self.rpm is not None and self.angle_vilebrequin_deg is not None:
                                acc_unit = float(calcul_force_inertie_alternative(masse_alternative_kg=1.0, rayon_manivelle_m=r_manivelle, vitesse_rotation_tr_min=self.rpm, longueur_bielle_m=self.longueur_bielle_m, angle_vilebrequin_deg=self.angle_vilebrequin_deg, angle_unite="deg", input_vitesse="rpm", clamp_ratio_r_sur_l=False, return_details=False))
                                F_seg_in = abs(acc_unit) * _req_pos("masse_segment_unitaire_kg", self.masse_segment_unitaire_kg, strict=False)
                                rap["rainures"]["segment"] = {
                                    "force_inertie_segment_n": F_seg_in,
                                    "force_appui_segment_n": _req_pos("force_appui_segment_n", self.force_appui_segment_n, strict=False),
                                    "flottement_probable": F_seg_in > _req_pos("force_appui_segment_n", self.force_appui_segment_n, strict=False),
                                    "jeu_axial_segment_m": self.jeu_axial_segment_m,
                                }
                        else:
                            _push_inc(
                                rap,
                                "partielles",
                                "pression_contact_joint",
                                "Estimable si module_elastomere_pa ou matériau joint avec module."
                            )

        elif nbj == 0:
            rap["notes_modele"].append("nb_joints=0 : aucune rainure de joint torique.")
            if self.hauteur_totale_m is not None:
                rap["dimensions"]["hauteur_totale_m"] = _req_pos("hauteur_totale_m", self.hauteur_totale_m)

        # ---------------------------------------------------------------------
        # 8) Hauteur totale si pas encore fixée
        # ---------------------------------------------------------------------
        if "hauteur_totale_m" not in rap["dimensions"]:
            if self.hauteur_totale_m is not None:
                rap["dimensions"]["hauteur_totale_m"] = _req_pos("hauteur_totale_m", self.hauteur_totale_m)
            else:
                _push_inc(rap, "partielles", "hauteur_totale_m", "Calculable si les rainures sont définies, ou à fournir explicitement.")

        # ---------------------------------------------------------------------
        # 9) Masse
        # ---------------------------------------------------------------------
        rho_p = props_p["densite_kg_m3"]
        H_tot_dim = rap["dimensions"].get("hauteur_totale_m")
        masse_corps = None
        if rho_p is not None and D_piston_cao is not None and H_tot_dim is not None:
            V_plein = _vol_cylindre(D_piston_cao, float(H_tot_dim))
            V_gorges = float(rap["joints"].get("volume_gorges_total_m3", 0.0) or 0.0)
            V_net = max(0.0, V_plein - V_gorges)
            masse_corps = float(rho_p) * V_net
            rap["masses"]["volume_plein_m3"] = V_plein
            rap["masses"]["volume_gorges_total_m3"] = V_gorges
            rap["masses"]["volume_net_corps_m3"] = V_net
            rap["masses"]["masse_corps_piston_kg"] = masse_corps
            rap["masses"]["inertie_rotation_axe_corps_kg_m2"] = _moment_inertie_disque_plein_axe(D_piston_cao, masse_corps)
            rap["masses"]["inertie_transversale_cg_corps_kg_m2"] = _moment_inertie_cylindre_plein_transversal_cg(D_piston_cao, float(H_tot_dim), masse_corps)
        else:
            _push_inc(rap, "partielles", "masse_corps_piston", "Calculable si densité piston + diamètre CAO + hauteur totale sont connus.")

        masse_axe = None
        if self.diametre_axe_m is not None and self.longueur_axe_m is not None:
            rho_a = self.densite_axe_kg_m3 if self.densite_axe_kg_m3 is not None else props_a.get("densite_kg_m3")
            if rho_a is not None:
                V_axe = _vol_cylindre(self.diametre_axe_m, self.longueur_axe_m)
                masse_axe = float(rho_a) * V_axe
                rap["masses"]["volume_axe_m3"] = V_axe
                rap["masses"]["masse_axe_kg"] = masse_axe
            else:
                _push_inc(rap, "partielles", "masse_axe", "Calculable si densité axe ou matériau axe sont fournis.")

        masse_joints = self.masse_joints_kg
        if masse_joints is None and self.type_etancheite == "joint_torique" and nbj is not None and nbj > 0 and props_j.get("densite_kg_m3") is not None and rap["joints"].get("diametre_moyen_joint_monte_m") is not None and rap["joints"].get("section_joint_m") is not None:
            vol_joint = _volume_tore_m3(float(rap["joints"]["diametre_moyen_joint_monte_m"]), float(rap["joints"]["section_joint_m"]))
            masse_joints = float(props_j["densite_kg_m3"]) * vol_joint * float(nbj)
            rap["masses"]["volume_joint_unitaire_m3"] = vol_joint
        elif masse_joints is None and self.type_etancheite == "joint_torique":
            _push_inc(rap, "partielles", "masse_joints", "Calculable si densité joint, diamètre moyen monté, section et nb_joints sont connus.")
        if masse_joints is not None:
            rap["masses"]["masse_joints_kg"] = float(masse_joints)

        masse_segments = self.masse_segments_kg
        if masse_segments is None and self.type_etancheite == "segment" and self.masse_segment_unitaire_kg is not None and nbj is not None:
            masse_segments = float(self.masse_segment_unitaire_kg) * float(nbj)
        if masse_segments is not None:
            rap["masses"]["masse_segments_kg"] = float(masse_segments)

        points_cg: List[Tuple[float, float]] = []
        if masse_corps is not None and H_tot_dim is not None:
            points_cg.append((masse_corps, 0.5 * float(H_tot_dim)))
        if masse_axe is not None and self.position_axe_depuis_face_tete_m is not None:
            points_cg.append((masse_axe, float(self.position_axe_depuis_face_tete_m)))
        elif masse_axe is not None:
            _push_inc(rap, "partielles", "centre_gravite_total", "Position de l'axe requise pour le CG exact avec l'axe inclus.")
        if masse_joints is not None and nbj is not None and nbj > 0 and rainures:
            mj = float(masse_joints) / float(nbj)
            for ri in rainures:
                points_cg.append((mj, float(ri["position_centre_depuis_face_tete_m"])))
        if masse_segments is not None and nbj is not None and nbj > 0 and rainures:
            ms = float(masse_segments) / float(nbj)
            for ri in rainures:
                points_cg.append((ms, float(ri["position_centre_depuis_face_tete_m"])))

        masse_tot_alt, xg_alt = _somme_masses(points_cg)
        if masse_tot_alt > 0.0:
            rap["masses"]["masse_alternative_calculee_kg"] = masse_tot_alt
        if xg_alt is not None:
            rap["masses"]["centre_gravite_depuis_face_tete_m"] = xg_alt

        if D_piston_cao is not None and masse_corps is not None:
            rap["masses"]["inertie_rotation_axe_piston_kg_m2"] = _moment_inertie_disque_plein_axe(D_piston_cao, masse_corps)
        if self.masse_bielle_kg is not None and self.fraction_bielle_alternative is not None:
            m_b_alt = _req_pos("masse_bielle_kg", self.masse_bielle_kg, strict=False) * _req_pos("fraction_bielle_alternative", self.fraction_bielle_alternative, strict=False)
            rap["masses"]["masse_bielle_alternative_kg"] = m_b_alt
            if rap["masses"].get("masse_alternative_calculee_kg") is not None:
                rap["masses"]["masse_alternative_totale_avec_bielle_kg"] = float(rap["masses"]["masse_alternative_calculee_kg"]) + m_b_alt

        # ---------------------------------------------------------------------
        # 10) Force gaz / inertie / force nette
        # ---------------------------------------------------------------------
        if Pmax is not None and Dcyl is not None:
            F_gaz = calcul_force_gaz(
                pression_pa=Pmax,
                alesage_m=Dcyl,
                allow_negative_pression=True,
                allow_zero_alesage=False,
                clamp_non_negative=False,
                return_details=False,
            )
            rap["cinematique"]["force_gaz_n"] = float(F_gaz)
        else:
            _push_inc(rap, "partielles", "force_gaz_n", "Calculable si pression_max_pa et alesage_nominal_m sont connus.")

        r_manivelle = None
        if course is not None:
            r_manivelle = 0.5 * float(course)
            rap["cinematique"]["rayon_manivelle_m"] = r_manivelle

        if (
            self.masse_alternative_kg is not None and
            r_manivelle is not None and
            self.rpm is not None and
            self.longueur_bielle_m is not None and
            self.angle_vilebrequin_deg is not None
        ):
            F_in = calcul_force_inertie_alternative(
                masse_alternative_kg=self.masse_alternative_kg,
                rayon_manivelle_m=r_manivelle,
                vitesse_rotation_tr_min=self.rpm,
                longueur_bielle_m=self.longueur_bielle_m,
                angle_vilebrequin_deg=self.angle_vilebrequin_deg,
                angle_unite="deg",
                input_vitesse="rpm",
                clamp_ratio_r_sur_l=False,
                return_details=False,
            )
            rap["cinematique"]["force_inertie_alternative_n"] = float(F_in)

            if "force_gaz_n" in rap["cinematique"]:
                rap["cinematique"]["force_axiale_nette_n"] = float(rap["cinematique"]["force_gaz_n"]) - float(F_in)
        else:
            _push_inc(rap, "partielles", "force_inertie_alternative_n", "Calculable si masse_alternative_kg, course/rayon, rpm, longueur_bielle_m et angle_vilebrequin_deg sont fournis.")

        # ---------------------------------------------------------------------
        # 10 bis) Effort latéral piston / pression de jupe / poussée / contre-poussée
        # ---------------------------------------------------------------------
        if rap["cinematique"].get("force_axiale_nette_n") is not None and r_manivelle is not None and self.longueur_bielle_m is not None and self.angle_vilebrequin_deg is not None:
            rep_lat = _force_laterale_piston(rap["cinematique"]["force_axiale_nette_n"], r_manivelle, self.longueur_bielle_m, self.angle_vilebrequin_deg)
            F_lat = float(rep_lat["force_laterale_n"])
            rap["efforts_lateraux"].update(rep_lat)
            rap["efforts_lateraux"]["charge_zone_poussee_n"] = max(0.0, F_lat)
            rap["efforts_lateraux"]["charge_zone_contre_poussee_n"] = max(0.0, -F_lat)
            if D_piston_cao is not None and L_jupe is not None:
                A_p = self.aire_zone_poussee_m2
                A_c = self.aire_zone_contre_poussee_m2
                if A_p is None and self.fraction_circonference_zone_poussee is not None:
                    A_p = _aire_projectee_contact_jupe(D_piston_cao, L_jupe, self.fraction_circonference_zone_poussee)
                if A_c is None and self.fraction_circonference_zone_contre_poussee is not None:
                    A_c = _aire_projectee_contact_jupe(D_piston_cao, L_jupe, self.fraction_circonference_zone_contre_poussee)
                rap["efforts_lateraux"]["aire_zone_poussee_m2"] = A_p
                rap["efforts_lateraux"]["aire_zone_contre_poussee_m2"] = A_c
                if A_p is not None and A_p > 0.0:
                    rap["efforts_lateraux"]["pression_jupe_poussee_pa"] = max(0.0, F_lat) / A_p
                if A_c is not None and A_c > 0.0:
                    rap["efforts_lateraux"]["pression_jupe_contre_poussee_pa"] = max(0.0, -F_lat) / A_c
                if self.pression_contact_jupe_admissible_pa is not None:
                    p_adm_loc = _req_pos("pression_contact_jupe_admissible_pa", self.pression_contact_jupe_admissible_pa)
                    if rap["efforts_lateraux"].get("pression_jupe_poussee_pa") is not None:
                        rap["efforts_lateraux"]["contact_local_poussee_ok"] = float(rap["efforts_lateraux"]["pression_jupe_poussee_pa"]) <= p_adm_loc
                    if rap["efforts_lateraux"].get("pression_jupe_contre_poussee_pa") is not None:
                        rap["efforts_lateraux"]["contact_local_contre_poussee_ok"] = float(rap["efforts_lateraux"]["pression_jupe_contre_poussee_pa"]) <= p_adm_loc
            else:
                _push_inc(rap, "partielles", "pression_jupe", "Calculable si diamètre piston et longueur de jupe sont connus, avec aire ou fraction de contact locale.")
        else:
            _push_inc(rap, "partielles", "effort_lateral_piston", "Calculable si force axiale nette, bielle, rayon manivelle et angle vilebrequin sont connus.")

        # ---------------------------------------------------------------------
        # 11) Frottements joints + PV + usure
        # ---------------------------------------------------------------------
        if (
            rap["joints"].get("pression_contact_estimee_pa") is not None and
            self.coeff_frottement_joint is not None and
            D_piston_cao is not None and
            nbj is not None and nbj > 0
        ):
            p_contact = float(rap["joints"]["pression_contact_estimee_pa"])
            mu = _req_pos("coeff_frottement_joint", self.coeff_frottement_joint, strict=False)

            bande = self.largeur_bande_contact_joint_m
            if bande is None and rainures:
                bande = float(rainures[0]["largeur_bande_contact_joint_m"])

            if bande is None:
                _push_inc(rap, "partielles", "frottement_joint", "Largeur bande contact manquante.")
            else:
                bande = _req_pos("largeur_bande_contact_joint_m", bande)
                A_contact = _perimetre(D_piston_cao) * bande * nbj
                F_normal_tot = p_contact * A_contact

                v_moy = None
                if course is not None and self.rpm is not None:
                    v_moy = float(calcul_vitesse_moyenne_piston(float(course), float(self.rpm)))

                rap["frottements"]["joint"] = {
                    "mu": mu,
                    "bande_contact_m": bande,
                    "aire_contact_m2": A_contact,
                    "force_normale_totale_estimee_n": F_normal_tot,
                }

                if v_moy is not None:
                    Pfr = calcul_puissance_frottement_segment(
                        force_normale_n=F_normal_tot,
                        vitesse_moyenne_ms=v_moy,
                        coef_frottement=mu,
                    )
                    rap["frottements"]["joint"]["vitesse_moyenne_ms"] = v_moy
                    rap["frottements"]["joint"]["puissance_frottement_w"] = Pfr

                    PV = p_contact * v_moy
                    rap["frottements"]["joint"]["PV_pa_ms"] = PV
                    if self.PV_admissible_pa_ms is not None:
                        PVadm = _req_pos("PV_admissible_pa_ms", self.PV_admissible_pa_ms)
                        rap["frottements"]["joint"]["PV_admissible_pa_ms"] = PVadm
                        rap["frottements"]["joint"]["PV_ok"] = (PV <= PVadm)
                else:
                    _push_inc(rap, "partielles", "PV_joint", "Calculable si course_m et rpm sont connus.")

                if (
                    self.coefficient_usure_joint_k is not None and
                    self.durete_contact_joint_pa is not None and
                    course is not None and self.rpm is not None and
                    self.duree_fonctionnement_s is not None
                ):
                    v_moy_usure = float(calcul_vitesse_moyenne_piston(float(course), float(self.rpm)))
                    distance = v_moy_usure * _req_pos("duree_fonctionnement_s", self.duree_fonctionnement_s, strict=False)
                    Vw = calcul_volume_usure_archard(
                        coefficient_usure_k=self.coefficient_usure_joint_k,
                        charge_normale_w=F_normal_tot,
                        distance_glissement_ls=distance,
                        durete_h=self.durete_contact_joint_pa,
                    )
                    dh = calcul_perte_epaisseur(Vw, A_contact)
                    rap["usure"]["joint"] = {
                        "coefficient_usure_k": self.coefficient_usure_joint_k,
                        "durete_contact_pa": self.durete_contact_joint_pa,
                        "distance_glissement_m": distance,
                        "volume_use_m3": Vw,
                        "perte_epaisseur_m": dh,
                    }
        else:
            _push_inc(rap, "partielles", "frottements_joints", "Calculables si p_contact joint, mu, diamètre piston et nb_joints sont connus.")

        # ---------------------------------------------------------------------
        # 12) Fuites annulaires
        # ---------------------------------------------------------------------
        if (
            D_piston_cao is not None and
            self.longueur_portee_etanche_m is not None and
            Pmax is not None and
            self.pression_aval_pa is not None and
            Tfn is not None
        ):
            c_fuite = rap["jeux"].get("jeu_radial_max_m", rap["jeux"].get("jeu_radial_nominal_m"))
            if c_fuite is None:
                _push_inc(rap, "partielles", "debit_fuite_m3_s", "Jeu radial manquant pour calculer la fuite.")
            else:
                if dynamic_viscosity_air_Pa_s is None:
                    _push_inc(rap, "partielles", "debit_fuite_m3_s", "Viscosité air indisponible.")
                else:
                    mu_air = float(dynamic_viscosity_air_Pa_s(float(Tfn)))
                    dP = max(float(Pmax) - _req_pos("pression_aval_pa", self.pression_aval_pa, strict=False), 0.0)
                    Q = calcul_debit_fuite_annulaire(
                        delta_p_pa=dP,
                        jeu_radial_h_m=float(c_fuite),
                        rayon_m=0.5 * float(D_piston_cao),
                        longueur_fuite_l_m=self.longueur_portee_etanche_m,
                        viscosite_dynamique_pa_s=mu_air,
                        use_abs_delta_p=True,
                        clamp_non_negative=True,
                        return_details=False,
                    )
                    rap["fuites"]["modele"] = "Q = (π*r*h^3*ΔP)/(6*μ*L)"
                    rap["fuites"]["jeu_radial_m"] = float(c_fuite)
                    rap["fuites"]["mu_air_pa_s"] = mu_air
                    rap["fuites"]["dP_pa"] = dP
                    rap["fuites"]["debit_fuite_m3_s"] = float(Q)

                    rho_air = float(Pmax) / (R_AIR_J_KG_K * float(Tfn)) if float(Tfn) > 0 else None
                    if rho_air is not None and rho_air > 0:
                        rap["fuites"]["densite_air_kg_m3_est"] = rho_air
                        mdot = calcul_masse_fuite(
                            debit_volumique_m3s=float(Q),
                            densite_kg_m3=rho_air,
                            use_abs_debit=True,
                            clamp_non_negative=True,
                            return_details=False,
                        )
                        rap["fuites"]["debit_fuite_kg_s_est"] = float(mdot)
        else:
            _push_inc(rap, "partielles", "debit_fuite_m3_s", "Calculable si diamètre piston, jeu, longueur portée, ΔP, T et viscosité air sont connus.")

        # ---------------------------------------------------------------------
        # 13) Fabrication / bloc CAO
        # ---------------------------------------------------------------------
        if D_piston_cao is not None:
            jeu_ref = rap["jeux"].get("jeu_radial_min_m", rap["jeux"].get("jeu_radial_nominal_m", 0.0))

            chanfrein = cyl["chanfrein_entree_piston_m"]
            if not _is_finite(chanfrein):
                chanfrein = _borne(
                    self.regles_fabrication.ratio_chanfrein_sur_jeu * max(float(jeu_ref or 0.0), 1e-6),
                    self.regles_fabrication.chanfrein_min_m,
                    self.regles_fabrication.chanfrein_max_m,
                )

            conge = cyl["rayon_conge_m"]
            if not _is_finite(conge):
                conge = _borne(
                    self.regles_fabrication.ratio_conge_sur_epaisseur_tete * max(float(ep_tete or 0.001), 1e-6),
                    self.regles_fabrication.rayon_conge_tete_jupe_min_m,
                    self.regles_fabrication.rayon_conge_tete_jupe_max_m,
                )

            rug_ext = self.regles_fabrication.rugosite_exterieure_ra_um
            if _is_finite(cyl["rugosite_alesage_ra_um"]):
                rug_ext = float(cyl["rugosite_alesage_ra_um"])

            tol_D = self.regles_fabrication.tolerance_diametre_exterieur_m
            tol_alesage = cyl["tolerance_alesage_m"]
            if _is_finite(tol_alesage):
                tol_D = max(float(tol_alesage), self.regles_fabrication.tolerance_diametre_exterieur_m)

            rap["dimensions"]["cao"] = {
                "diametre_exterieur_nominal_m": D_piston_cao,
                "diametre_exterieur_min_m": D_piston_min,
                "diametre_exterieur_max_m": D_piston_max,
                "hauteur_totale_m": rap["dimensions"].get("hauteur_totale_m"),
                "epaisseur_tete_m": ep_tete if ep_tete is not None else rap["dimensions"].get("epaisseur_tete_min_m"),
                "longueur_jupe_m": L_jupe if L_jupe is not None else rap["dimensions"].get("longueur_jupe_min_m"),
                "chanfrein_extremites_m": chanfrein,
                "rayon_conge_tete_jupe_m": conge,
                "rugosite_exterieure_ra_um": rug_ext,
                "rugosite_faces_ra_um": self.regles_fabrication.rugosite_faces_ra_um,
                "rugosite_fond_rainure_ra_um": self.regles_fabrication.rugosite_fond_rainure_ra_um,
                "tolerance_diametre_exterieur_m": tol_D,
                "tolerance_hauteur_m": self.regles_fabrication.tolerance_hauteur_m,
                "tolerance_position_rainure_m": self.regles_fabrication.tolerance_position_rainure_m,
                "tolerance_largeur_rainure_m": self.regles_fabrication.tolerance_largeur_rainure_m,
                "tolerance_profondeur_rainure_m": self.regles_fabrication.tolerance_profondeur_rainure_m,
                "joints": {
                    "nb_joints": rap["joints"].get("nb_joints"),
                    "section_joint_m": rap["joints"].get("section_joint_m"),
                    "squeeze": rap["joints"].get("squeeze"),
                    "diametre_fond_rainure_m": rap["joints"].get("diametre_fond_rainure_m"),
                    "largeur_rainure_m": rap["joints"].get("largeur_rainure_m"),
                    "profondeur_radiale_rainure_m": rap["joints"].get("profondeur_radiale_rainure_m"),
                    "diametre_montage_joint_m": rap["joints"].get("diametre_montage_joint_m"),
                    "diametre_moyen_joint_monte_m": rap["joints"].get("diametre_moyen_joint_monte_m"),
                    "hauteur_radiale_disponible_m": rap["joints"].get("hauteur_radiale_disponible_m"),
                    "positions_centres_depuis_face_tete_m": rap["joints"].get("positions_centres_depuis_face_tete_m"),
                    "rainures": rainures,
                },
                "rainures": rainures,
            }

        # ---------------------------------------------------------------------
        # 14) Entrées récap
        # ---------------------------------------------------------------------
        rap["entrees"] = {
            "alesage_nominal_m": self.alesage_nominal_m,
            "course_m": self.course_m,
            "rpm": self.rpm,
            "fit_hole": self.fit_hole,
            "fit_shaft": self.fit_shaft,
            "pression_max_pa": self.pression_max_pa,
            "temperature_fonctionnement_k": self.temperature_fonctionnement_k,
            "temperature_tete_k": self.temperature_tete_k,
            "temperature_zone_segments_k": self.temperature_zone_segments_k,
            "temperature_jupe_k": self.temperature_jupe_k,
            "temperature_axe_k": self.temperature_axe_k,
            "temperature_cylindre_tete_k": self.temperature_cylindre_tete_k,
            "temperature_cylindre_zone_segments_k": self.temperature_cylindre_zone_segments_k,
            "temperature_cylindre_jupe_k": self.temperature_cylindre_jupe_k,
            "temperature_tete_face_chaude_k": self.temperature_tete_face_chaude_k,
            "temperature_tete_face_froide_k": self.temperature_tete_face_froide_k,
            "temperature_cycle_tete_min_k": self.temperature_cycle_tete_min_k,
            "materiau_piston_cle": self.materiau_piston_cle,
            "materiau_cylindre_cle": self.materiau_cylindre_cle,
            "mode_materiau": self.mode_materiau,
            "temperature_ref_k": self.temperature_ref_k,
            "effort_lateral_N": self.effort_lateral_N,
            "pression_palier_admissible_pa": self.pression_palier_admissible_pa,
            "k_sigma_plaque": self.k_sigma_plaque,
            "contrainte_admissible_pa": self.contrainte_admissible_pa,
            "facteur_securite": self.facteur_securite,
            "hauteur_totale_m": self.hauteur_totale_m,
            "epaisseur_tete_m": self.epaisseur_tete_m,
            "longueur_jupe_m": self.longueur_jupe_m,
            "materiau_axe_cle": self.materiau_axe_cle,
            "diametre_axe_m": self.diametre_axe_m,
            "longueur_axe_m": self.longueur_axe_m,
            "position_axe_depuis_face_tete_m": self.position_axe_depuis_face_tete_m,
            "densite_axe_kg_m3": self.densite_axe_kg_m3,
            "coef_dilatation_axe_1_k": self.coef_dilatation_axe_1_k,
            "aire_zone_poussee_m2": self.aire_zone_poussee_m2,
            "aire_zone_contre_poussee_m2": self.aire_zone_contre_poussee_m2,
            "fraction_circonference_zone_poussee": self.fraction_circonference_zone_poussee,
            "fraction_circonference_zone_contre_poussee": self.fraction_circonference_zone_contre_poussee,
            "pression_contact_jupe_admissible_pa": self.pression_contact_jupe_admissible_pa,
            "nb_joints": self.nb_joints,
            "section_joint_mm": self.section_joint_mm,
            "squeeze": self.squeeze,
            "facteur_largeur_rainure": self.facteur_largeur_rainure,
            "materiau_joint_cle": self.materiau_joint_cle,
            "module_elastomere_pa": self.module_elastomere_pa,
            "coeff_frottement_joint": self.coeff_frottement_joint,
            "largeur_bande_contact_joint_m": self.largeur_bande_contact_joint_m,
            "PV_admissible_pa_ms": self.PV_admissible_pa_ms,
            "type_etancheite": self.type_etancheite,
            "epaisseur_levre_superieure_m": self.epaisseur_levre_superieure_m,
            "epaisseur_levre_inferieure_m": self.epaisseur_levre_inferieure_m,
            "pression_matage_admissible_pa": self.pression_matage_admissible_pa,
            "contrainte_levre_admissible_pa": self.contrainte_levre_admissible_pa,
            "masse_joints_kg": self.masse_joints_kg,
            "masse_segments_kg": self.masse_segments_kg,
            "masse_segment_unitaire_kg": self.masse_segment_unitaire_kg,
            "force_appui_segment_n": self.force_appui_segment_n,
            "jeu_axial_segment_m": self.jeu_axial_segment_m,
            "longueur_portee_etanche_m": self.longueur_portee_etanche_m,
            "pression_aval_pa": self.pression_aval_pa,
            "masse_alternative_kg": self.masse_alternative_kg,
            "longueur_bielle_m": self.longueur_bielle_m,
            "angle_vilebrequin_deg": self.angle_vilebrequin_deg,
            "masse_bielle_kg": self.masse_bielle_kg,
            "fraction_bielle_alternative": self.fraction_bielle_alternative,
            "coefficient_usure_joint_k": self.coefficient_usure_joint_k,
            "durete_contact_joint_pa": self.durete_contact_joint_pa,
            "duree_fonctionnement_s": self.duree_fonctionnement_s,
            "facteur_contrainte_thermique_tete": self.facteur_contrainte_thermique_tete,
            "poisson_piston": self.poisson_piston,
        }

        _dedup_inconnues(rap)
        if strict and (rap["inconnues"]["impossibles"] or rap["inconnues"]["partielles"]):
            raise ValueError(
                "Piston(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rap['inconnues']['impossibles']}\n"
                f"Partielles: {rap['inconnues']['partielles']}"
            )
        return rap


# =============================================================================
# Exemple
# =============================================================================
if __name__ == "__main__":
    p = Piston(
        alesage_nominal_m=0.080,
        fit_hole="H7",
        fit_shaft="h6",
        pression_max_pa=15e5,
        temperature_fonctionnement_k=350.0,
        course_m=0.060,
        rpm=1200.0,
        materiau_piston_cle="alu_7075_t6",
        materiau_cylindre_cle="acier_42crmo4_qt",
        nb_joints=2,
        section_joint_mm=3.0,
        squeeze=0.20,
        facteur_largeur_rainure=1.5,
        materiau_joint_cle="nbr_70",
        coeff_frottement_joint=0.15,
        PV_admissible_pa_ms=2.0e6,
        longueur_portee_etanche_m=0.010,
        pression_aval_pa=1e5,
    )

    from pprint import pprint
    pprint(p.analyser(strict=False))