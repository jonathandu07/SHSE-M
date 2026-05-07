# backend\modules\architecture\architecture_fine_multicas.py
from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np


# =============================================================================
# Imports robustes
# =============================================================================
try:
    from backend.components.architechture.modules.calcul_cylindree_totale import calcul_cylindree_totale_requise
    from backend.components.architechture.modules.calcul_cylindree_admissible import calcul_nombre_cylindres_min, calcul_bore_max_admissible, calcul_cylindree_unit_max  # type: ignore
except Exception:
    try:
        from backend.components.architechture.modules.calcul_cylindree_totale import calcul_cylindree_totale_requise  # type: ignore
        from backend.components.architechture.modules.calcul_cylindree_admissible import calcul_bore_max_admissible, calcul_cylindree_unit_max  # type: ignore
        from backend.components.architechture.modules.calcul_nombre_cylindres_min import calcul_nombre_cylindres_min  # type: ignore
    except Exception:
        here = os.path.abspath(os.path.dirname(__file__)) if "__file__" in globals() else os.getcwd()
        if here not in sys.path:
            sys.path.insert(0, here)
        from calcul_cylindree_totale import calcul_cylindree_totale_requise  # type: ignore
        from calcul_cylindree_admissible import calcul_bore_max_admissible, calcul_cylindree_unit_max  # type: ignore
        from calcul_nombre_cylindres_min import calcul_nombre_cylindres_min  # type: ignore

try:
    from backend.components.architechture.modules.calcul_cout_maintenance_archard import calcul_cout_maintenance_estime
except Exception:
    try:
        from calcul_cout_maintenance_archard import calcul_cout_maintenance_estime  # type: ignore
    except Exception:
        calcul_cout_maintenance_estime = None  # type: ignore

try:
    from backend.components.moteur_thermique.modules.calcul_cylindree import (
        CasChargePression,
        ParametresWiebe,
        evaluer_cas_charge_cylindre,
        evaluer_plusieurs_cas_charge_cylindre,
    )
except Exception:
    try:
        from calcul_cylindree_affine import (
            CasChargePression,
            ParametresWiebe,
            evaluer_cas_charge_cylindre,
            evaluer_plusieurs_cas_charge_cylindre,
        )  # type: ignore
    except Exception:
        raise


Number = Union[int, float]


# =============================================================================
# Validation
# =============================================================================

def _is_finite_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite_number(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly:
        if v <= 0.0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0.0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _req_int_ge(name: str, x: Any, min_value: int = 1) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return x


def _as_1d_array(name: str, x: Sequence[float] | np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=float).reshape(-1)
    if arr.size == 0:
        raise ValueError(f"{name} ne peut pas être vide.")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} doit être fini.")
    return arr


def _aire_disque(diametre_m: float) -> float:
    D = _req_pos("diametre_m", diametre_m, strictly=True)
    return math.pi * D * D / 4.0


def _hz_cycles_4t(regime_tr_min: float) -> float:
    n = _req_pos("regime_tr_min", regime_tr_min, strictly=True)
    return n / 120.0


def _periodic_interp(theta_query_deg: np.ndarray, theta_base_deg: np.ndarray, y_base: np.ndarray, period_deg: float = 720.0) -> np.ndarray:
    tq = np.asarray(theta_query_deg, dtype=float).reshape(-1)
    tb = np.asarray(theta_base_deg, dtype=float).reshape(-1)
    yb = np.asarray(y_base, dtype=float).reshape(-1)
    if tb.size != yb.size:
        raise ValueError("theta_base_deg et y_base doivent avoir la même taille.")
    if tb.size < 2:
        raise ValueError("Interpolation périodique impossible avec moins de 2 points.")
    x = np.mod(tq - tb[0], period_deg) + tb[0]
    tb2 = tb.copy()
    yb2 = yb.copy()
    if tb2[-1] < tb2[0] + period_deg:
        tb2 = np.append(tb2, tb2[0] + period_deg)
        yb2 = np.append(yb2, yb2[0])
    return np.interp(x, tb2, yb2)


# =============================================================================
# Paramètres modèles explicites
# =============================================================================

@dataclass(frozen=True)
class ParametresPackagingArchitecture:
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

    marge_structure_mult: float = 1.10


@dataclass(frozen=True)
class ParametresMasseArchitecture:
    densite_alliage_bloc_kg_m3: float = 2700.0
    densite_alliage_piston_kg_m3: float = 2700.0
    densite_acier_kg_m3: float = 7850.0

    contrainte_admissible_bloc_pa: float = 140e6
    contrainte_admissible_culasse_pa: float = 120e6
    contrainte_admissible_couronne_piston_pa: float = 95e6
    contrainte_admissible_torsion_vilo_pa: float = 90e6

    facteur_securite_bloc: float = 1.8
    facteur_securite_culasse: float = 2.0
    facteur_securite_piston: float = 1.8
    facteur_securite_vilo: float = 1.8

    facteur_longueur_chemise: float = 1.25
    facteur_sur_epaisseur_refroidissement: float = 1.00
    facteur_epaisseur_chemise_min_m: float = 0.0025

    coeff_plaque_culasse: float = 0.55
    epaisseur_culasse_min_m: float = 0.010
    facteur_masse_culasse: float = 2.40

    coeff_couronne_piston: float = 0.16
    epaisseur_couronne_min_m: float = 0.0040
    facteur_hauteur_jupe: float = 0.62
    facteur_epaisseur_jupe: float = 0.035
    epaisseur_jupe_min_m: float = 0.0025
    facteur_volume_couronne: float = 1.10
    facteur_volume_jupe: float = 1.00

    facteur_diametre_axe: float = 0.28
    facteur_longueur_axe: float = 0.72
    facteur_masse_segments_kg_par_m: float = 1.90

    facteur_section_bielle: float = 0.055
    facteur_masse_bielle: float = 1.15
    fraction_alternative_bielle: float = 0.33

    facteur_diametre_palier_vilo: float = 0.42
    facteur_longueur_palier_vilo: float = 0.38
    facteur_longueur_vilo_sur_pas: float = 1.15
    facteur_masse_vilo: float = 1.35

    facteur_masse_carter_par_cylindree: float = 145.0
    facteur_masse_accessoires_par_cylindre: float = 1.8
    facteur_masse_refroidissement_par_cylindre: float = 1.2

    multiplicateur_masse_architecture: Mapping[str, float] = field(
        default_factory=lambda: {
            "L": 1.00,
            "V": 1.08,
            "W": 1.18,
            "Etoile": 1.25,
            "Boxer": 1.10,
        }
    )


@dataclass(frozen=True)
class ParametresPertesArchitecture:
    fmep_a0_pa: float = 45_000.0
    fmep_a1_pa_par_ms: float = 7_000.0
    fmep_a2_pa_par_ms2: float = 220.0
    fmep_par_cylindre_pa: float = 1_200.0

    multiplicateur_frottement_architecture: Mapping[str, float] = field(
        default_factory=lambda: {
            "L": 1.00,
            "V": 1.05,
            "W": 1.12,
            "Etoile": 1.18,
            "Boxer": 1.03,
        }
    )

    multiplicateur_surface_architecture: Mapping[str, float] = field(
        default_factory=lambda: {
            "L": 1.00,
            "V": 0.96,
            "W": 1.02,
            "Etoile": 1.15,
            "Boxer": 0.94,
        }
    )

    coeff_surface_vers_pertes: float = 0.14
    sv_ref_m2_m3: float = 65.0


@dataclass(frozen=True)
class ParametresFiabiliteArchitecture:
    pression_admissible_jupe_pa: float = 1.8e6
    pv_admissible_segments: float = 180e6
    pression_admissible_palier_pa: float = 16e6
    contrainte_admissible_bielle_pa: float = 180e6
    contrainte_fatigue_bielle_pa: float = 90e6
    contrainte_admissible_vilo_pa: float = 110e6
    contrainte_fatigue_vilo_pa: float = 55e6
    line_load_admissible_joint_n_m: float = 140_000.0

    exposant_charge: float = 1.50
    exposant_vitesse: float = 1.15
    exposant_thermique: float = 1.20

    multiplicateur_risque_architecture: Mapping[str, float] = field(
        default_factory=lambda: {
            "L": 1.00,
            "V": 1.04,
            "W": 1.10,
            "Etoile": 1.16,
            "Boxer": 0.98,
        }
    )


@dataclass(frozen=True)
class ParametresScoreArchitecture:
    poids_masse: float = 0.30
    poids_rendement: float = 0.28
    poids_fiabilite: float = 0.30
    poids_packaging: float = 0.07
    poids_maintenance: float = 0.05


@dataclass(frozen=True)
class OptionsExplorationArchitecture:
    architectures: Tuple[str, ...] = ("L", "V", "W", "Etoile", "Boxer")
    ratios_course_alesage: Tuple[float, ...] = (0.75, 0.90, 1.00, 1.10, 1.20)
    delta_cylindres: int = 6
    n_max_absolu: int = 24
    longueur_bielle_sur_course: float = 1.75
    axe_decale_m: float = 0.0
    nb_cyl_reference_maintenance: int = 4


# =============================================================================
# Gabarit
# =============================================================================

def _architecture_possible(type_arch: str, nb_cylindres: int) -> bool:
    nb = _req_int_ge("nb_cylindres", nb_cylindres, 1)
    if type_arch == "L":
        return True
    if type_arch == "V":
        return (nb % 2) == 0
    if type_arch == "W":
        return nb >= 6 and ((nb % 3) == 0 or (nb % 4) == 0)
    if type_arch == "Etoile":
        return nb >= 3
    if type_arch == "Boxer":
        return (nb % 2) == 0
    return False


def _pitch_cylindre_m(alesage_m: float, course_m: float, p: ParametresPackagingArchitecture) -> float:
    B = _req_pos("alesage_m", alesage_m, strictly=True)
    S = _req_pos("course_m", course_m, strictly=True)
    return p.pas_bore_mult * B + p.pas_course_mult * S + p.marge_pas_m


def estimer_gabarit_architecture(
    type_arch: str,
    nb_cylindres: int,
    alesage_m: float,
    course_m: float,
    params: ParametresPackagingArchitecture = ParametresPackagingArchitecture(),
) -> Dict[str, float]:
    if not _architecture_possible(type_arch, nb_cylindres):
        raise ValueError(f"Architecture impossible/incohérente: {type_arch} avec {nb_cylindres} cylindres.")

    B = _req_pos("alesage_m", alesage_m, strictly=True)
    S = _req_pos("course_m", course_m, strictly=True)
    N = _req_int_ge("nb_cylindres", nb_cylindres, 1)

    pitch = _pitch_cylindre_m(B, S, params)
    bank_width = params.largeur_banc_mult * B
    h_engine = params.hauteur_haut_moteur_mult * B + S + params.hauteur_carter_mult * B
    crank_w = 0.9 * B + params.largeur_accessoires_m

    if type_arch == "L":
        L = N * pitch + params.longueur_accessoires_m
        W = bank_width + crank_w
        H = h_engine

    elif type_arch == "V":
        banks = N // 2
        a = math.radians(params.angle_v_deg)
        L = banks * pitch + params.longueur_accessoires_m
        W = 2.0 * bank_width * math.sin(0.5 * a) + crank_w
        H = bank_width * math.cos(0.5 * a) + S + params.hauteur_carter_mult * B

    elif type_arch == "W":
        banks = math.ceil(N / 3.0)
        a = math.radians(params.angle_w_deg)
        L = banks * pitch + params.longueur_accessoires_m
        W = 2.8 * bank_width * math.sin(0.5 * a) + crank_w + 0.35 * B
        H = 1.25 * bank_width + S + params.hauteur_carter_mult * B

    elif type_arch == "Etoile":
        diamètre = params.radial_diametre_mult * B + 1.2 * S
        L = params.radial_longueur_mult * B + 0.75 * S + params.longueur_accessoires_m
        W = diamètre
        H = diamètre

    elif type_arch == "Boxer":
        banks = N // 2
        L = banks * pitch + params.longueur_accessoires_m
        W = 2.0 * bank_width + crank_w
        H = 0.90 * B + S + params.hauteur_carter_mult * B

    else:
        raise ValueError(f"Architecture non supportée: {type_arch!r}")

    volume = L * W * H
    return {
        "longueur_m": params.marge_structure_mult * L,
        "largeur_m": params.marge_structure_mult * W,
        "hauteur_m": params.marge_structure_mult * H,
        "volume_boite_m3": params.marge_structure_mult ** 3 * volume,
        "pas_cylindre_m": pitch,
    }


# =============================================================================
# Masse mobiles et structure
# =============================================================================

def estimer_masses_mobiles(
    alesage_m: float,
    course_m: float,
    longueur_bielle_m: float,
    p_max_pa: float,
    params: ParametresMasseArchitecture = ParametresMasseArchitecture(),
) -> Dict[str, float]:
    B = _req_pos("alesage_m", alesage_m, strictly=True)
    S = _req_pos("course_m", course_m, strictly=True)
    Lb = _req_pos("longueur_bielle_m", longueur_bielle_m, strictly=True)
    pmax = _req_pos("p_max_pa", p_max_pa, strictly=False)

    A = _aire_disque(B)

    sigma_crown = params.contrainte_admissible_couronne_piston_pa / params.facteur_securite_piston
    t_crown = max(
        params.epaisseur_couronne_min_m,
        params.coeff_couronne_piston * B * math.sqrt(max(pmax, 0.0) / max(sigma_crown, 1e-12)),
    )
    h_skirt = params.facteur_hauteur_jupe * B
    t_skirt = max(params.epaisseur_jupe_min_m, params.facteur_epaisseur_jupe * B)

    V_crown = params.facteur_volume_couronne * A * t_crown
    V_skirt = params.facteur_volume_jupe * math.pi * B * h_skirt * t_skirt

    d_pin = params.facteur_diametre_axe * B
    l_pin = params.facteur_longueur_axe * B
    V_pin = math.pi * d_pin * d_pin * l_pin / 4.0

    m_segments = params.facteur_masse_segments_kg_par_m * B
    m_piston = params.densite_alliage_piston_kg_m3 * (V_crown + V_skirt) + params.densite_acier_kg_m3 * V_pin + m_segments

    A_rod = params.facteur_section_bielle * B * B
    V_rod = params.facteur_masse_bielle * A_rod * Lb
    m_rod = params.densite_acier_kg_m3 * V_rod

    m_alt = m_piston + params.fraction_alternative_bielle * m_rod
    m_rot = (1.0 - params.fraction_alternative_bielle) * m_rod

    return {
        "m_piston_kg": m_piston,
        "m_bielle_totale_kg": m_rod,
        "m_alternative_equivalente_kg": m_alt,
        "m_tournante_equivalente_kg": m_rot,
        "section_bielle_equivalente_m2": A_rod,
        "diametre_axe_m": d_pin,
        "longueur_axe_m": l_pin,
        "hauteur_jupe_m": h_skirt,
        "epaisseur_couronne_m": t_crown,
        "epaisseur_jupe_m": t_skirt,
    }


def estimer_masse_architecture(
    type_arch: str,
    nb_cylindres: int,
    alesage_m: float,
    course_m: float,
    longueur_bielle_m: float,
    pression_dimensionnante_pa: float,
    torque_max_nm: float,
    params_masse: ParametresMasseArchitecture = ParametresMasseArchitecture(),
    params_pack: ParametresPackagingArchitecture = ParametresPackagingArchitecture(),
) -> Dict[str, float]:
    if not _architecture_possible(type_arch, nb_cylindres):
        raise ValueError(f"Architecture impossible: {type_arch} / {nb_cylindres}")

    B = _req_pos("alesage_m", alesage_m, strictly=True)
    S = _req_pos("course_m", course_m, strictly=True)
    Lb = _req_pos("longueur_bielle_m", longueur_bielle_m, strictly=True)
    N = _req_int_ge("nb_cylindres", nb_cylindres, 1)
    pmax = _req_pos("pression_dimensionnante_pa", pression_dimensionnante_pa, strictly=False)
    Tmax = _req_pos("torque_max_nm", torque_max_nm, strictly=False)

    A = _aire_disque(B)
    ri = 0.5 * B
    sigma_block = params_masse.contrainte_admissible_bloc_pa / params_masse.facteur_securite_bloc

    # chemise / bloc local
    t_chemise = max(
        params_masse.facteur_epaisseur_chemise_min_m,
        (pmax * ri) / max(sigma_block, 1e-12),
    )
    barrel_length = params_masse.facteur_longueur_chemise * S
    ro_eq = ri + t_chemise * (1.0 + params_masse.facteur_sur_epaisseur_refroidissement)
    V_barrel = math.pi * (ro_eq * ro_eq - ri * ri) * barrel_length * N
    m_barrels = params_masse.densite_alliage_bloc_kg_m3 * V_barrel

    # culasses : plaque équivalente sous pression, puis facteur de masse pour eau/ailettes/renforts
    sigma_head = params_masse.contrainte_admissible_culasse_pa / params_masse.facteur_securite_culasse
    t_head = max(
        params_masse.epaisseur_culasse_min_m,
        params_masse.coeff_plaque_culasse * B * math.sqrt(max(pmax, 0.0) / max(sigma_head, 1e-12)),
    )
    V_heads = N * A * t_head * params_masse.facteur_masse_culasse
    m_heads = params_masse.densite_alliage_bloc_kg_m3 * V_heads

    # vilebrequin
    gabarit = estimer_gabarit_architecture(type_arch, N, B, S, params_pack)
    pitch = gabarit["pas_cylindre_m"]
    L_vilo = max(pitch * N * params_masse.facteur_longueur_vilo_sur_pas, 0.25)
    tau_eff = params_masse.contrainte_admissible_torsion_vilo_pa / params_masse.facteur_securite_vilo
    d_vilo = max(
        params_masse.facteur_diametre_palier_vilo * B,
        ((16.0 * max(Tmax, 1.0)) / (math.pi * max(tau_eff, 1e-12))) ** (1.0 / 3.0),
    )
    V_vilo = params_masse.facteur_masse_vilo * (math.pi * d_vilo * d_vilo / 4.0) * L_vilo
    m_vilo = params_masse.densite_acier_kg_m3 * V_vilo

    # masses mobiles
    mobiles = estimer_masses_mobiles(B, S, Lb, pmax, params_masse)
    m_recip_total = N * mobiles["m_alternative_equivalente_kg"]
    m_rot_total = N * mobiles["m_tournante_equivalente_kg"]

    Vd_unit = A * S
    Vd_tot = Vd_unit * N
    m_carter = params_masse.facteur_masse_carter_par_cylindree * Vd_tot
    m_accessoires = N * params_masse.facteur_masse_accessoires_par_cylindre
    m_refroidissement = N * params_masse.facteur_masse_refroidissement_par_cylindre

    m_raw = m_barrels + m_heads + m_vilo + m_recip_total + m_rot_total + m_carter + m_accessoires + m_refroidissement
    mult = params_masse.multiplicateur_masse_architecture.get(type_arch, 1.0)
    m_total = mult * m_raw

    return {
        "masse_totale_estimee_kg": m_total,
        "masse_bloc_chemises_kg": m_barrels,
        "masse_culasses_kg": m_heads,
        "masse_vilebrequin_kg": m_vilo,
        "masse_mobile_alternative_totale_kg": m_recip_total,
        "masse_mobile_tournante_totale_kg": m_rot_total,
        "masse_carter_kg": m_carter,
        "masse_accessoires_kg": m_accessoires,
        "masse_refroidissement_kg": m_refroidissement,
        "epaisseur_chemise_eq_m": t_chemise,
        "epaisseur_culasse_eq_m": t_head,
        "diametre_vilebrequin_eq_m": d_vilo,
        "longueur_vilebrequin_eq_m": L_vilo,
        **mobiles,
    }


# =============================================================================
# Cycle mécanique local à partir d'un cas de pression
# =============================================================================

def _phases_allumage(ordre_allumage: Sequence[int] | str, nb_cylindres: int) -> Dict[int, float]:
    N = _req_int_ge("nb_cylindres", nb_cylindres, 1)
    if isinstance(ordre_allumage, str):
        items = [int(x) for x in ordre_allumage.replace(";", "-").replace(",", "-").replace(" ", "").split("-") if x]
    else:
        items = [int(x) for x in ordre_allumage]
    if len(items) != N:
        raise ValueError("ordre_allumage incompatible avec nb_cylindres.")
    expected = set(range(1, N + 1))
    if set(items) != expected:
        raise ValueError("ordre_allumage doit être une permutation complète des cylindres.")
    step = 720.0 / N
    return {cyl: i * step for i, cyl in enumerate(items)}


def _cinematique_exacte(theta_deg: np.ndarray, r_m: float, L_m: float, omega_rad_s: float, axe_decale_m: float = 0.0) -> Dict[str, np.ndarray]:
    theta_mech_deg = np.mod(theta_deg, 360.0)
    theta_rad = np.deg2rad(theta_mech_deg)

    s = r_m * np.sin(theta_rad) - axe_decale_m
    g2 = np.clip(L_m * L_m - s * s, 1e-18, None)
    g = np.sqrt(g2)

    y = r_m * np.cos(theta_rad) + g
    y_tdc = r_m + math.sqrt(max(L_m * L_m - axe_decale_m * axe_decale_m, 1e-18))
    x = y_tdc - y

    dx_dtheta = r_m * np.sin(theta_rad) + (r_m * np.cos(theta_rad) * s / g)
    q_prime = (
        (-r_m * s * np.sin(theta_rad) + (r_m ** 2) * (np.cos(theta_rad) ** 2)) / g
        + ((r_m ** 2) * (np.cos(theta_rad) ** 2) * (s ** 2)) / (g ** 3)
    )
    d2x_dtheta2 = r_m * np.cos(theta_rad) + q_prime

    v = dx_dtheta * omega_rad_s
    a = d2x_dtheta2 * (omega_rad_s ** 2)

    sin_beta = np.clip(s / L_m, -1.0, 1.0)
    beta = np.arcsin(sin_beta)
    cos_beta = np.sqrt(np.clip(1.0 - sin_beta ** 2, 1e-18, None))
    tan_beta = sin_beta / cos_beta

    return {
        "theta_rad": theta_rad,
        "x_piston_m": x,
        "v_piston_ms": v,
        "a_piston_ms2": a,
        "beta_rad": beta,
        "sin_beta": sin_beta,
        "cos_beta": cos_beta,
        "tan_beta": tan_beta,
    }


def calcul_cycle_mecanique_depuis_pression(
    *,
    theta_deg: Sequence[float] | np.ndarray,
    pression_cylindre_pa: Sequence[float] | np.ndarray,
    alesage_m: float,
    course_m: float,
    longueur_bielle_m: float,
    nombre_cylindres: int,
    ordre_allumage: Sequence[int] | str,
    regime_tr_min: float,
    masse_alternative_kg: float,
    masse_tournante_equivalente_kg: float,
    axe_decale_m: float = 0.0,
    pression_reference_pa: float = 101325.0,
) -> Dict[str, Any]:
    theta = _as_1d_array("theta_deg", theta_deg)
    pbase = _as_1d_array("pression_cylindre_pa", pression_cylindre_pa)
    if theta.size != pbase.size:
        raise ValueError("theta_deg et pression_cylindre_pa doivent avoir la même taille.")
    if theta.size < 3:
        raise ValueError("Le cycle doit comporter au moins 3 points.")

    B = _req_pos("alesage_m", alesage_m, strictly=True)
    S = _req_pos("course_m", course_m, strictly=True)
    Lb = _req_pos("longueur_bielle_m", longueur_bielle_m, strictly=True)
    N = _req_int_ge("nombre_cylindres", nombre_cylindres, 1)
    rpm = _req_pos("regime_tr_min", regime_tr_min, strictly=True)
    m_alt = _req_pos("masse_alternative_kg", masse_alternative_kg, strictly=False)
    m_rot = _req_pos("masse_tournante_equivalente_kg", masse_tournante_equivalente_kg, strictly=False)
    p_ref = _req_pos("pression_reference_pa", pression_reference_pa, strictly=False)

    omega = 2.0 * math.pi * rpm / 60.0
    r = 0.5 * S
    A = _aire_disque(B)
    phases = _phases_allumage(ordre_allumage, N)

    kin_ref = _cinematique_exacte(theta, r, Lb, omega, axe_decale_m)
    p_ref_cyl = _periodic_interp(theta, theta, pbase)

    T_total = np.zeros_like(theta)
    Fx_total = np.zeros_like(theta)
    Fy_total = np.zeros_like(theta)

    for _, phase_deg in phases.items():
        theta_local = np.mod(theta - phase_deg, 720.0)
        p_local = _periodic_interp(theta_local, theta, pbase)
        kin = _cinematique_exacte(theta_local, r, Lb, omega, axe_decale_m)

        F_gaz = (p_local - p_ref) * A
        F_inertie = m_alt * kin["a_piston_ms2"]
        F_piston = F_gaz - F_inertie
        F_bielle = F_piston / kin["cos_beta"]
        F_lat = F_piston * kin["tan_beta"]

        F_tan = F_bielle * np.sin(kin["theta_rad"] + kin["beta_rad"])
        T_inst = F_tan * r

        F_c = m_rot * r * omega * omega
        Fx = F_lat + F_c * np.sin(kin["theta_rad"])
        Fy = -F_piston - F_c * np.cos(kin["theta_rad"])

        T_total += T_inst
        Fx_total += Fx
        Fy_total += Fy

    R_eq = np.sqrt(Fx_total ** 2 + Fy_total ** 2)

    F_gaz_ref = (p_ref_cyl - p_ref) * A
    F_inertie_ref = m_alt * kin_ref["a_piston_ms2"]
    F_piston_ref = F_gaz_ref - F_inertie_ref
    F_bielle_ref = F_piston_ref / kin_ref["cos_beta"]
    F_lat_ref = F_piston_ref * kin_ref["tan_beta"]

    torque_mean = float(np.mean(T_total))
    torque_max = float(np.max(T_total))
    torque_min = float(np.min(T_total))
    torque_alt = 0.5 * (torque_max - torque_min)
    theta_rad_cycle = np.deg2rad(theta)
    energy_cycle = float(np.trapz(T_total, theta_rad_cycle))

    return {
        "theta_deg": theta,
        "p_cyl_pa": p_ref_cyl,
        "x_piston_m": kin_ref["x_piston_m"],
        "v_piston_ms": kin_ref["v_piston_ms"],
        "a_piston_ms2": kin_ref["a_piston_ms2"],
        "obliquite_bielle_rad": kin_ref["beta_rad"],
        "F_gaz_N": F_gaz_ref,
        "F_inertie_N": F_inertie_ref,
        "F_axiale_bielle_N": F_bielle_ref,
        "F_laterale_piston_N": F_lat_ref,
        "T_inst_Nm": T_total,
        "R_palier_1_N": 0.5 * R_eq,
        "R_palier_2_N": 0.5 * R_eq,
        "T_moy_Nm": torque_mean,
        "T_max_Nm": torque_max,
        "T_min_Nm": torque_min,
        "T_alterne_Nm": torque_alt,
        "energie_cycle_J": energy_cycle,
        "irregularite_couple": float(np.std(T_total) / max(abs(torque_mean), 1e-12)),
    }


# =============================================================================
# Rendement / pertes
# =============================================================================

def _surface_exposee_sur_cylindree(type_arch: str, nb_cylindres: int, gabarit: Mapping[str, float], cylindree_totale_m3: float) -> float:
    if cylindree_totale_m3 <= 0.0:
        return float("inf")
    mult = {
        "L": 1.00,
        "V": 0.96,
        "W": 1.02,
        "Etoile": 1.15,
        "Boxer": 0.94,
    }.get(type_arch, 1.0)
    area_box = 2.0 * (
        gabarit["longueur_m"] * gabarit["largeur_m"]
        + gabarit["longueur_m"] * gabarit["hauteur_m"]
        + gabarit["largeur_m"] * gabarit["hauteur_m"]
    )
    return mult * area_box / cylindree_totale_m3


def estimer_performance_architecture(
    *,
    type_arch: str,
    nb_cylindres: int,
    cylindree_totale_m3: float,
    course_m: float,
    regime_tr_min: float,
    pmi_pa: float,
    gabarit: Mapping[str, float],
    params: ParametresPertesArchitecture = ParametresPertesArchitecture(),
) -> Dict[str, float]:
    N = _req_int_ge("nb_cylindres", nb_cylindres, 1)
    Vtot = _req_pos("cylindree_totale_m3", cylindree_totale_m3, strictly=True)
    S = _req_pos("course_m", course_m, strictly=True)
    rpm = _req_pos("regime_tr_min", regime_tr_min, strictly=True)
    PMI = _req_finite("pmi_pa", pmi_pa)
    f = _hz_cycles_4t(rpm)
    up = 2.0 * S * rpm / 60.0

    fmep = (
        params.fmep_a0_pa
        + params.fmep_a1_pa_par_ms * up
        + params.fmep_a2_pa_par_ms2 * up * up
        + params.fmep_par_cylindre_pa * N
    ) * params.multiplicateur_frottement_architecture.get(type_arch, 1.0)

    bmep = max(PMI - fmep, 0.0)
    eta_meca = bmep / max(PMI, 1e-12) if PMI > 0.0 else 0.0

    sv = _surface_exposee_sur_cylindree(type_arch, N, gabarit, Vtot)
    sv_ratio = sv / max(params.sv_ref_m2_m3, 1e-12)
    heat_mult = params.multiplicateur_surface_architecture.get(type_arch, 1.0)
    eta_thermal_proxy = 1.0 / (1.0 + params.coeff_surface_vers_pertes * heat_mult * max(sv_ratio - 1.0, 0.0))
    eta_global_proxy = eta_meca * eta_thermal_proxy
    pertes_frottement_w = fmep * Vtot * f

    return {
        "up_moyenne_ms": up,
        "fmep_pa": fmep,
        "bmep_pa": bmep,
        "eta_mecanique_proxy": eta_meca,
        "eta_thermique_proxy": eta_thermal_proxy,
        "eta_globale_proxy": eta_global_proxy,
        "pertes_frottement_w": pertes_frottement_w,
        "surface_sur_cylindree_m2_m3": sv,
    }


# =============================================================================
# Fiabilité multi-organes
# =============================================================================

def evaluer_fiabilite_organes(
    *,
    type_arch: str,
    alesage_m: float,
    course_m: float,
    masse_mobiles: Mapping[str, float],
    cycle: Mapping[str, Any],
    temperature_gaz_k: Optional[float],
    facteur_fatigue: Optional[float],
    facteur_thermique: Optional[float],
    params: ParametresFiabiliteArchitecture = ParametresFiabiliteArchitecture(),
) -> Dict[str, Any]:
    B = _req_pos("alesage_m", alesage_m, strictly=True)
    S = _req_pos("course_m", course_m, strictly=True)

    F_lat = _as_1d_array("F_laterale_piston_N", cycle["F_laterale_piston_N"])
    F_ax = _as_1d_array("F_axiale_bielle_N", cycle["F_axiale_bielle_N"])
    T_inst = _as_1d_array("T_inst_Nm", cycle["T_inst_Nm"])
    R1 = _as_1d_array("R_palier_1_N", cycle["R_palier_1_N"])
    R2 = _as_1d_array("R_palier_2_N", cycle["R_palier_2_N"])
    p = _as_1d_array("p_cyl_pa", cycle["p_cyl_pa"])
    v = _as_1d_array("v_piston_ms", cycle["v_piston_ms"])

    h_skirt = float(masse_mobiles["hauteur_jupe_m"])
    A_skirt = max(math.pi * B * h_skirt, 1e-12)
    p_skirt_eq = float(np.sqrt(np.mean(F_lat ** 2)) / A_skirt)

    up_peak = float(np.max(np.abs(v)))
    pv_segments = float(np.max(p) * max(np.mean(np.abs(v)), 1e-12))

    A_rod = max(float(masse_mobiles["section_bielle_equivalente_m2"]), 1e-12)
    sigma_rod_max = float(np.max(np.abs(F_ax)) / A_rod)
    sigma_rod_alt = float(0.5 * (np.max(F_ax) - np.min(F_ax)) / A_rod)

    d_vilo = max(float(masse_mobiles.get("diametre_vilebrequin_eq_m", 0.42 * B)), 1e-12)
    tau_vilo_max = float(16.0 * np.max(np.abs(T_inst)) / (math.pi * d_vilo ** 3))
    tau_vilo_alt = float(16.0 * 0.5 * (np.max(T_inst) - np.min(T_inst)) / (math.pi * d_vilo ** 3))

    d_b = max(0.42 * B, 1e-12)
    l_b = max(0.38 * B, 1e-12)
    A_bearing = d_b * l_b
    p_bearing_eq = float(max(np.sqrt(np.mean(R1 ** 2)), np.sqrt(np.mean(R2 ** 2))) / A_bearing)

    line_load_joint = float(np.max(p) * (_aire_disque(B) / max(math.pi * B, 1e-12)))

    temp_mult = max(1.0, (temperature_gaz_k or 700.0) / 700.0)
    fatigue_mult = max(1.0, facteur_fatigue or 1.0)
    thermal_mult = max(1.0, facteur_thermique or 1.0)
    arch_mult = params.multiplicateur_risque_architecture.get(type_arch, 1.0)

    charge_exp = params.exposant_charge
    speed_exp = params.exposant_vitesse
    therm_exp = params.exposant_thermique

    sev_jupe = arch_mult * (p_skirt_eq / max(params.pression_admissible_jupe_pa, 1e-12)) ** charge_exp \
        * max(up_peak / 15.0, 1e-12) ** (0.35 * speed_exp) * (temp_mult * thermal_mult) ** therm_exp

    sev_segments = arch_mult * (pv_segments / max(params.pv_admissible_segments, 1e-12)) ** charge_exp \
        * (temp_mult * thermal_mult) ** therm_exp

    sev_bielle = arch_mult * (
        (sigma_rod_max / max(params.contrainte_admissible_bielle_pa, 1e-12)) ** charge_exp
        + (sigma_rod_alt / max(params.contrainte_fatigue_bielle_pa, 1e-12)) ** charge_exp
    ) * fatigue_mult * (temp_mult * thermal_mult) ** (0.30 * therm_exp)

    sev_paliers = arch_mult * (p_bearing_eq / max(params.pression_admissible_palier_pa, 1e-12)) ** charge_exp \
        * fatigue_mult * max(up_peak / 15.0, 1e-12) ** (0.20 * speed_exp)

    sev_vilo = arch_mult * (
        (tau_vilo_max / max(params.contrainte_admissible_vilo_pa, 1e-12)) ** charge_exp
        + (tau_vilo_alt / max(params.contrainte_fatigue_vilo_pa, 1e-12)) ** charge_exp
    ) * fatigue_mult

    sev_joint = arch_mult * (line_load_joint / max(params.line_load_admissible_joint_n_m, 1e-12)) ** charge_exp \
        * (temp_mult * thermal_mult) ** therm_exp

    severities = {
        "jupe_piston": float(sev_jupe),
        "segments": float(sev_segments),
        "bielle": float(sev_bielle),
        "paliers": float(sev_paliers),
        "vilebrequin": float(sev_vilo),
        "joint_culasse": float(sev_joint),
    }
    worst_organe = max(severities, key=lambda k: severities[k])

    return {
        "severites": severities,
        "marges": {k: (1.0 / v if v > 0.0 else float("inf")) for k, v in severities.items()},
        "organe_dimensionnant": worst_organe,
        "severite_globale": float(severities[worst_organe]),
        "diagnostic": {
            "pression_equivalente_jupe_pa": p_skirt_eq,
            "pv_segments": pv_segments,
            "contrainte_max_bielle_pa": sigma_rod_max,
            "contrainte_alt_bielle_pa": sigma_rod_alt,
            "pression_equivalente_palier_pa": p_bearing_eq,
            "cisaillement_max_vilo_pa": tau_vilo_max,
            "cisaillement_alt_vilo_pa": tau_vilo_alt,
            "line_load_joint_n_m": line_load_joint,
        },
    }


# =============================================================================
# Candidat complet
# =============================================================================

def _ordre_allumage_defaut(nb_cyl: int) -> List[int]:
    N = _req_int_ge("nb_cyl", nb_cyl, 1)
    return list(range(1, N + 1))


def evaluer_candidat_architecture(
    *,
    type_arch: str,
    nb_cylindres: int,
    ratio_course_alesage: float,
    cylindree_totale_m3: float,
    taux_compression: float,
    cas_de_charge: Sequence[CasChargePression],
    L_max_m: float,
    W_max_m: float,
    H_max_m: Optional[float] = None,
    horizon_usage_h: float = 20_000.0,
    ordre_allumage: Optional[Sequence[int] | str] = None,
    params_packaging: ParametresPackagingArchitecture = ParametresPackagingArchitecture(),
    params_masse: ParametresMasseArchitecture = ParametresMasseArchitecture(),
    params_pertes: ParametresPertesArchitecture = ParametresPertesArchitecture(),
    params_fiabilite: ParametresFiabiliteArchitecture = ParametresFiabiliteArchitecture(),
    params_score: ParametresScoreArchitecture = ParametresScoreArchitecture(),
    options: OptionsExplorationArchitecture = OptionsExplorationArchitecture(),
    ponderations_cas: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    if not cas_de_charge:
        raise ValueError("cas_de_charge ne peut pas être vide.")
    if not _architecture_possible(type_arch, nb_cylindres):
        raise ValueError(f"Architecture invalide pour ce nombre de cylindres: {type_arch}/{nb_cylindres}")

    N = _req_int_ge("nb_cylindres", nb_cylindres, 1)
    ratio = _req_pos("ratio_course_alesage", ratio_course_alesage, strictly=True)
    Vtot = _req_pos("cylindree_totale_m3", cylindree_totale_m3, strictly=True)
    B = ((4.0 * (Vtot / N)) / (math.pi * ratio)) ** (1.0 / 3.0)
    S = ratio * B
    Lb = options.longueur_bielle_sur_course * S

    gabarit = estimer_gabarit_architecture(type_arch, N, B, S, params_packaging)
    valide_packaging = gabarit["longueur_m"] <= L_max_m and gabarit["largeur_m"] <= W_max_m
    if H_max_m is not None:
        valide_packaging = valide_packaging and (gabarit["hauteur_m"] <= H_max_m)

    synth_p = evaluer_plusieurs_cas_charge_cylindre(
        alesage_m=B,
        course_m=S,
        taux_compression=taux_compression,
        cas_de_charge=cas_de_charge,
        pas_angle_deg=0.5,
        longueur_bielle_m=Lb,
        axe_decale_m=options.axe_decale_m,
    )
    p_dim = float(synth_p["pression_dimensionnante_pa"])

    # Première estimation masses
    masse_guess = estimer_masses_mobiles(B, S, Lb, p_dim, params_masse)
    ordre = ordre_allumage if ordre_allumage is not None else _ordre_allumage_defaut(N)

    cas_results: Dict[str, Any] = {}
    perf_weighted = 0.0
    rel_weighted = 0.0
    pmi_weighted = 0.0
    tot_weight = 0.0
    torque_max_global = 0.0
    maintenance_charge_ref = None
    maintenance_charge_worst = 0.0
    worst_case_name = ""
    worst_sev = -1.0
    worst_organe = ""
    maintenance_cases: Dict[str, float] = {}

    for i, case in enumerate(cas_de_charge):
        p_case = evaluer_cas_charge_cylindre(
            alesage_m=B,
            course_m=S,
            taux_compression=taux_compression,
            cas=case,
            pas_angle_deg=0.5,
            longueur_bielle_m=Lb,
            axe_decale_m=options.axe_decale_m,
        )
        theta = np.asarray(p_case["theta_deg"], dtype=float)
        p_arr = np.asarray(p_case["pression_cylindre_pa"], dtype=float)

        cycle = calcul_cycle_mecanique_depuis_pression(
            theta_deg=theta,
            pression_cylindre_pa=p_arr,
            alesage_m=B,
            course_m=S,
            longueur_bielle_m=Lb,
            nombre_cylindres=N,
            ordre_allumage=ordre,
            regime_tr_min=float(case.regime_tr_min),
            masse_alternative_kg=float(masse_guess["m_alternative_equivalente_kg"]),
            masse_tournante_equivalente_kg=float(masse_guess["m_tournante_equivalente_kg"]),
            axe_decale_m=options.axe_decale_m,
        )

        torque_max_global = max(torque_max_global, float(np.max(np.abs(cycle["T_inst_Nm"]))))

        perf = estimer_performance_architecture(
            type_arch=type_arch,
            nb_cylindres=N,
            cylindree_totale_m3=Vtot,
            course_m=S,
            regime_tr_min=float(case.regime_tr_min),
            pmi_pa=float(p_case["pmi_pa"]),
            gabarit=gabarit,
            params=params_pertes,
        )

        fiab = evaluer_fiabilite_organes(
            type_arch=type_arch,
            alesage_m=B,
            course_m=S,
            masse_mobiles=masse_guess,
            cycle=cycle,
            temperature_gaz_k=case.temperature_gaz_k,
            facteur_fatigue=case.facteur_fatigue,
            facteur_thermique=case.facteur_thermique,
            params=params_fiabilite,
        )

        weight = float(ponderations_cas.get(case.nom, 1.0) if ponderations_cas is not None else 1.0)
        tot_weight += weight
        perf_weighted += weight * float(perf["eta_globale_proxy"])
        rel_weighted += weight * float(fiab["severite_globale"])
        pmi_weighted += weight * float(p_case["pmi_pa"])

        if i == 0:
            maintenance_charge_ref = float(p_case["cas_dimensionnant_force"])
        maintenance_charge_worst = max(maintenance_charge_worst, float(p_case["cas_dimensionnant_force"]))

        if float(fiab["severite_globale"]) > worst_sev:
            worst_sev = float(fiab["severite_globale"])
            worst_case_name = case.nom
            worst_organe = str(fiab["organe_dimensionnant"])

        if calcul_cout_maintenance_estime is not None and maintenance_charge_ref is not None:
            maintenance_cases[case.nom] = float(
                calcul_cout_maintenance_estime(
                    duree_usage_h=horizon_usage_h,
                    duree_vie_joint_base_h=5000.0,
                    charge_nominale_n=max(maintenance_charge_ref, 1.0),
                    charge_actuelle_n=max(float(p_case["cas_dimensionnant_force"]), 0.0),
                    nb_joints_base=max(3 * options.nb_cyl_reference_maintenance, 1),
                    nb_joints_actuel=max(3 * N, 1),
                    cout_inter_eur=2000.0,
                )
            )

        cas_results[case.nom] = {
            "pression": p_case,
            "cycle": {
                "T_moy_Nm": cycle["T_moy_Nm"],
                "T_max_Nm": cycle["T_max_Nm"],
                "T_min_Nm": cycle["T_min_Nm"],
                "T_alterne_Nm": cycle["T_alterne_Nm"],
                "energie_cycle_J": cycle["energie_cycle_J"],
                "irregularite_couple": cycle["irregularite_couple"],
                "F_laterale_max_N": float(np.max(np.abs(cycle["F_laterale_piston_N"]))),
                "R_palier_max_N": float(np.max(np.maximum(cycle["R_palier_1_N"], cycle["R_palier_2_N"]))),
            },
            "performance": perf,
            "fiabilite": fiab,
            "maintenance_estimee_eur": maintenance_cases.get(case.nom, 0.0),
        }

    # Estimation structurelle finale avec couple global
    masse = estimer_masse_architecture(
        type_arch=type_arch,
        nb_cylindres=N,
        alesage_m=B,
        course_m=S,
        longueur_bielle_m=Lb,
        pression_dimensionnante_pa=p_dim,
        torque_max_nm=torque_max_global,
        params_masse=params_masse,
        params_pack=params_packaging,
    )

    eta_weighted = perf_weighted / max(tot_weight, 1e-12)
    rel_weighted /= max(tot_weight, 1e-12)
    pmi_weighted /= max(tot_weight, 1e-12)

    maintenance_worst = max(maintenance_cases.values()) if maintenance_cases else 0.0
    packaging_penalty = max(gabarit["longueur_m"] / max(L_max_m, 1e-12), gabarit["largeur_m"] / max(W_max_m, 1e-12))
    if H_max_m is not None:
        packaging_penalty = max(packaging_penalty, gabarit["hauteur_m"] / max(H_max_m, 1e-12))

    mass_norm = masse["masse_totale_estimee_kg"] / max(80.0, 1e-12)
    eff_penalty = 1.0 - eta_weighted
    rel_penalty = rel_weighted
    maint_penalty = maintenance_worst / max(8000.0, 1e-12)

    score = (
        params_score.poids_masse * mass_norm
        + params_score.poids_rendement * eff_penalty
        + params_score.poids_fiabilite * rel_penalty
        + params_score.poids_packaging * packaging_penalty
        + params_score.poids_maintenance * maint_penalty
    )
    if not valide_packaging:
        score += 1000.0

    return {
        "architecture": type_arch,
        "nb_cylindres": N,
        "ratio_course_alesage": ratio,
        "alesage_m": B,
        "course_m": S,
        "longueur_bielle_m": Lb,
        "cylindree_totale_m3": Vtot,
        "cylindree_totale_cm3": Vtot * 1e6,
        "cylindree_unitaire_cm3": Vtot * 1e6 / N,
        "valide_packaging": valide_packaging,
        "gabarit": gabarit,
        "masse": masse,
        "performance_moyenne": {
            "pmi_moyenne_pa": pmi_weighted,
            "eta_globale_proxy_moyenne": eta_weighted,
        },
        "fiabilite_globale": {
            "severite_moyenne_ponderee": rel_weighted,
            "severite_dimensionnante": worst_sev,
            "cas_dimensionnant": worst_case_name,
            "organe_dimensionnant": worst_organe,
        },
        "maintenance": {
            "cout_max_estime_eur": maintenance_worst,
            "couts_par_cas_eur": maintenance_cases,
        },
        "cas": cas_results,
        "pression_dimensionnante_pa": p_dim,
        "torque_max_global_nm": torque_max_global,
        "score": score,
        "details_score": {
            "mass_norm": mass_norm,
            "eff_penalty": eff_penalty,
            "rel_penalty": rel_penalty,
            "packaging_penalty": packaging_penalty,
            "maint_penalty": maint_penalty,
        },
    }


# =============================================================================
# Résolution globale fine
# =============================================================================

def resoudre_architecture_fine_multicas(
    *,
    puissance_cible_w: float,
    regime_nominal_tr_min: float,
    pme_nominale_pa: float,
    vitesse_piston_max_ms: float,
    L_max_m: float,
    W_max_m: float,
    taux_compression: float,
    cas_de_charge: Sequence[CasChargePression],
    H_max_m: Optional[float] = None,
    horizon_usage_h: float = 20_000.0,
    ordre_allumage_map: Optional[Mapping[int, Sequence[int] | str]] = None,
    params_packaging: ParametresPackagingArchitecture = ParametresPackagingArchitecture(),
    params_masse: ParametresMasseArchitecture = ParametresMasseArchitecture(),
    params_pertes: ParametresPertesArchitecture = ParametresPertesArchitecture(),
    params_fiabilite: ParametresFiabiliteArchitecture = ParametresFiabiliteArchitecture(),
    params_score: ParametresScoreArchitecture = ParametresScoreArchitecture(),
    options: OptionsExplorationArchitecture = OptionsExplorationArchitecture(),
    ponderations_cas: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    P = _req_pos("puissance_cible_w", puissance_cible_w, strictly=False)
    rpm_nom = _req_pos("regime_nominal_tr_min", regime_nominal_tr_min, strictly=True)
    PME = _req_pos("pme_nominale_pa", pme_nominale_pa, strictly=True)
    _req_pos("vitesse_piston_max_ms", vitesse_piston_max_ms, strictly=False)
    _req_pos("L_max_m", L_max_m, strictly=True)
    _req_pos("W_max_m", W_max_m, strictly=True)
    if H_max_m is not None:
        _req_pos("H_max_m", H_max_m, strictly=True)
    _req_pos("taux_compression", taux_compression, strictly=True)
    _req_pos("horizon_usage_h", horizon_usage_h, strictly=False)

    if not cas_de_charge:
        raise ValueError("cas_de_charge ne peut pas être vide.")

    freq_nom = _hz_cycles_4t(rpm_nom)
    cyl_tot_m3 = calcul_cylindree_totale_requise(
        puissance_mecanique_h=P,
        pme_pa=PME,
        frequence_cycles_hz=freq_nom,
        rendement_mecanique=0.85,
    )

    # Contrainte vitesse piston sur le pire régime des cas
    rpm_max = max(float(c.regime_tr_min) for c in cas_de_charge)
    bore_max = calcul_bore_max_admissible(vitesse_piston_max_ms, rpm_max, max(options.ratios_course_alesage))
    cyl_unit_max = calcul_cylindree_unit_max(bore_max, max(options.ratios_course_alesage))
    n_min = calcul_nombre_cylindres_min(cyl_tot_m3, cyl_unit_max)

    if n_min >= 999 or n_min > options.n_max_absolu:
        raise ValueError("Paramètres incohérents : N_min impossible ou trop élevé.")

    results: List[Dict[str, Any]] = []
    n_upper = min(options.n_max_absolu, max(n_min + options.delta_cylindres, n_min))

    course_max = 30.0 * vitesse_piston_max_ms / rpm_max if rpm_max > 0.0 else float("inf")

    for N in range(n_min, n_upper + 1):
        Vunit = cyl_tot_m3 / N
        for arch in options.architectures:
            if not _architecture_possible(arch, N):
                continue
            for ratio in options.ratios_course_alesage:
                B = ((4.0 * Vunit) / (math.pi * ratio)) ** (1.0 / 3.0)
                S = ratio * B
                if S > course_max + 1e-12:
                    continue

                ordre = None
                if ordre_allumage_map is not None and N in ordre_allumage_map:
                    ordre = ordre_allumage_map[N]

                try:
                    res = evaluer_candidat_architecture(
                        type_arch=arch,
                        nb_cylindres=N,
                        ratio_course_alesage=ratio,
                        cylindree_totale_m3=cyl_tot_m3,
                        taux_compression=taux_compression,
                        cas_de_charge=cas_de_charge,
                        L_max_m=L_max_m,
                        W_max_m=W_max_m,
                        H_max_m=H_max_m,
                        horizon_usage_h=horizon_usage_h,
                        ordre_allumage=ordre,
                        params_packaging=params_packaging,
                        params_masse=params_masse,
                        params_pertes=params_pertes,
                        params_fiabilite=params_fiabilite,
                        params_score=params_score,
                        options=options,
                        ponderations_cas=ponderations_cas,
                    )
                    results.append(res)
                except Exception:
                    continue

    if not results:
        raise ValueError("Aucun candidat valide n'a pu être évalué.")

    results.sort(key=lambda d: float(d["score"]))
    best = results[0]

    return {
        "hypotheses": {
            "cylindree_totale_requise_m3": cyl_tot_m3,
            "cylindree_totale_requise_cm3": cyl_tot_m3 * 1e6,
            "n_min": n_min,
            "rpm_max_considere": rpm_max,
            "course_max_m": course_max,
            "modele": "comparatif multi-cas semi-physique",
            "attention": (
                "Le score est calculé, mais les sous-modèles masse/pertes/fiabilité "
                "restent explicites et calibrables. Pour un niveau industriel, il faut "
                "des lois matériaux, des géométries réelles, des mesures de pression et "
                "des données thermiques/tribologiques propres au projet."
            ),
        },
        "meilleur_candidat": best,
        "candidats_tries": results,
    }


__all__ = [
    "ParametresPackagingArchitecture",
    "ParametresMasseArchitecture",
    "ParametresPertesArchitecture",
    "ParametresFiabiliteArchitecture",
    "ParametresScoreArchitecture",
    "OptionsExplorationArchitecture",
    "estimer_gabarit_architecture",
    "estimer_masses_mobiles",
    "estimer_masse_architecture",
    "calcul_cycle_mecanique_depuis_pression",
    "estimer_performance_architecture",
    "evaluer_fiabilite_organes",
    "evaluer_candidat_architecture",
    "resoudre_architecture_fine_multicas",
]
