# backend/modules/moteur_thermique/cycle_mecanique.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Union

import numpy as np


ArrayLike = Union[Sequence[float], np.ndarray]
PressureLaw = Union[
    ArrayLike,
    Mapping[str, ArrayLike],
    Callable[[np.ndarray, np.ndarray, Dict[str, Any]], np.ndarray],
]
CombustionModel = Callable[[np.ndarray, np.ndarray, Dict[str, Any]], np.ndarray]


@dataclass
class CycleMecaniqueParams:
    """
    Paramètres du calcul de cycle mécanique.

    Hypothèses et limites :
    - cycle 4 temps : 720° vilebrequin
    - theta = 0° au PMH combustion du cylindre de référence
    - la cinématique piston/bielle est calculée exactement sur la géométrie
      bielle-manivelle avec éventuel décalage d'axe
    - le couplage multi-cylindres est reconstruit en répartissant les phases
      d'allumage uniformément sur 720° selon l'ordre d'allumage
    - les réactions de paliers sont "équivalentes" tant que la géométrie axiale
      réelle du vilebrequin n'est pas fournie
    """

    alesage_m: float
    course_m: float
    longueur_bielle_m: float
    nombre_cylindres: int
    ordre_allumage: Union[str, Sequence[int]]
    regime_tr_min: float

    masse_alternative_kg: float
    masse_tournante_equivalente_kg: float = 0.0

    axe_decale_m: float = 0.0
    rapport_volumetrique: float = 10.0

    loi_pression_cylindre: Optional[PressureLaw] = None
    modele_combustion: Optional[CombustionModel] = None

    pression_admission_pa: float = 101325.0
    pression_echappement_pa: float = 101325.0
    pression_reference_pa: float = 101325.0

    temperature_gaz_utile_k: Optional[float] = None

    cycle_deg: int = 720
    pas_angle_deg: float = 1.0

    # Modèle interne simple si aucune loi de pression n'est fournie
    n_polytropique_compression: float = 1.32
    n_polytropique_detente: float = 1.25

    rayon_maneton_m: Optional[float] = None

    def __post_init__(self) -> None:
        if self.alesage_m <= 0.0:
            raise ValueError("alesage_m doit être > 0")
        if self.course_m <= 0.0:
            raise ValueError("course_m doit être > 0")
        if self.longueur_bielle_m <= 0.0:
            raise ValueError("longueur_bielle_m doit être > 0")
        if self.nombre_cylindres <= 0:
            raise ValueError("nombre_cylindres doit être > 0")
        if self.regime_tr_min <= 0.0:
            raise ValueError("regime_tr_min doit être > 0")
        if self.rapport_volumetrique <= 1.0:
            raise ValueError("rapport_volumetrique doit être > 1")
        if self.pas_angle_deg <= 0.0:
            raise ValueError("pas_angle_deg doit être > 0")

        r = self.rayon_manivelle_m
        e = abs(self.axe_decale_m)
        L = self.longueur_bielle_m

        if e >= L:
            raise ValueError("axe_decale_m doit être strictement inférieur à longueur_bielle_m")
        if (r + e) >= L:
            raise ValueError("géométrie impossible : r + |axe_decale_m| doit être < longueur_bielle_m")

        if self.rayon_maneton_m is None:
            self.rayon_maneton_m = r

    @property
    def rayon_manivelle_m(self) -> float:
        return self.course_m / 2.0

    @property
    def rapport_lambda(self) -> float:
        return self.rayon_manivelle_m / self.longueur_bielle_m

    @property
    def omega_rad_s(self) -> float:
        return 2.0 * np.pi * self.regime_tr_min / 60.0

    @property
    def section_piston_m2(self) -> float:
        return np.pi * (self.alesage_m ** 2) / 4.0

    @property
    def cylindree_unitaire_m3(self) -> float:
        return self.section_piston_m2 * self.course_m

    @property
    def volume_residuel_m3(self) -> float:
        return self.cylindree_unitaire_m3 / (self.rapport_volumetrique - 1.0)

    def firing_order_list(self) -> list[int]:
        if isinstance(self.ordre_allumage, str):
            raw = self.ordre_allumage.replace(";", "-").replace(",", "-").replace(" ", "")
            order = [int(x) for x in raw.split("-") if x]
        else:
            order = [int(x) for x in self.ordre_allumage]

        if len(order) != self.nombre_cylindres:
            raise ValueError(
                "ordre_allumage doit contenir exactement nombre_cylindres valeurs"
            )

        expected = set(range(1, self.nombre_cylindres + 1))
        if set(order) != expected:
            raise ValueError(
                f"ordre_allumage invalide, attendu une permutation de {sorted(expected)}"
            )

        return order


@dataclass
class EnvelopeStats:
    minimum: float
    maximum: float
    rms: float
    alternee: float
    moyenne: float

    @classmethod
    def from_array(cls, values: np.ndarray) -> "EnvelopeStats":
        arr = np.asarray(values, dtype=float)
        vmax = float(np.max(arr))
        vmin = float(np.min(arr))
        vmoy = float(np.mean(arr))
        vrms = float(np.sqrt(np.mean(arr ** 2)))
        valt = 0.5 * (vmax - vmin)
        return cls(
            minimum=vmin,
            maximum=vmax,
            rms=vrms,
            alternee=valt,
            moyenne=vmoy,
        )

    def as_dict(self) -> Dict[str, float]:
        return {
            "min": self.minimum,
            "max": self.maximum,
            "rms": self.rms,
            "alternee": self.alternee,
            "moyenne": self.moyenne,
        }


@dataclass
class TorqueCycleStats:
    T_moy_Nm: float
    T_max_Nm: float
    T_min_Nm: float
    T_rms_Nm: float
    fluctuation_couple_Nm: float
    coefficient_fluctuation_couple: float
    energie_cycle_J: float
    irregularite_couple: float

    def as_dict(self) -> Dict[str, float]:
        return {
            "T_moy_Nm": self.T_moy_Nm,
            "T_max_Nm": self.T_max_Nm,
            "T_min_Nm": self.T_min_Nm,
            "T_rms_Nm": self.T_rms_Nm,
            "fluctuation_couple_Nm": self.fluctuation_couple_Nm,
            "coefficient_fluctuation_couple": self.coefficient_fluctuation_couple,
            "energie_cycle_J": self.energie_cycle_J,
            "irregularite_couple": self.irregularite_couple,
        }


@dataclass
class CycleMecaniqueResult:
    theta_deg: np.ndarray
    p_cyl_pa: np.ndarray
    x_piston_m: np.ndarray
    v_piston_ms: np.ndarray
    a_piston_ms2: np.ndarray
    obliquite_bielle_rad: np.ndarray
    F_gaz_N: np.ndarray
    F_inertie_N: np.ndarray
    F_axiale_bielle_N: np.ndarray
    F_laterale_piston_N: np.ndarray
    T_inst_Nm: np.ndarray
    R_palier_1_N: np.ndarray
    R_palier_2_N: np.ndarray
    enveloppes: Dict[str, Dict[str, float]]
    statistiques_cycle: Dict[str, float]
    extras: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "theta_deg": self.theta_deg,
            "p_cyl_pa": self.p_cyl_pa,
            "x_piston_m": self.x_piston_m,
            "v_piston_ms": self.v_piston_ms,
            "a_piston_ms2": self.a_piston_ms2,
            "obliquite_bielle_rad": self.obliquite_bielle_rad,
            "F_gaz_N": self.F_gaz_N,
            "F_inertie_N": self.F_inertie_N,
            "F_axiale_bielle_N": self.F_axiale_bielle_N,
            "F_laterale_piston_N": self.F_laterale_piston_N,
            "T_inst_Nm": self.T_inst_Nm,
            "R_palier_1_N": self.R_palier_1_N,
            "R_palier_2_N": self.R_palier_2_N,
            "enveloppes": self.enveloppes,
            "statistiques_cycle": self.statistiques_cycle,
            "extras": self.extras,
        }


def _build_theta_deg(cycle_deg: int, pas_angle_deg: float) -> np.ndarray:
    n = int(round(cycle_deg / pas_angle_deg))
    return np.linspace(0.0, float(cycle_deg), n + 1)


def _cinematique_bielle_manivelle_exacte(
    theta_cycle_deg: np.ndarray,
    r_m: float,
    L_m: float,
    omega_rad_s: float,
    axe_decale_m: float = 0.0,
) -> Dict[str, np.ndarray]:
    """
    Cinématique exacte de la géométrie bielle-manivelle.

    Convention :
    - theta = 0° au PMH
    - x_piston_m = 0 au PMH
    - x_piston_m > 0 vers le PMB
    - axe_decale_m : décalage latéral de l'axe cylindre par rapport au centre vilebrequin
    """

    theta_mech_deg = np.mod(theta_cycle_deg, 360.0)
    theta_rad = np.deg2rad(theta_mech_deg)

    s = r_m * np.sin(theta_rad) - axe_decale_m
    g2 = L_m ** 2 - s ** 2
    g2 = np.clip(g2, 1e-18, None)
    g = np.sqrt(g2)

    # Position absolue du piston par rapport au centre vilebrequin
    y = r_m * np.cos(theta_rad) + g

    # Position absolue au PMH
    y_tdc = r_m + np.sqrt(np.clip(L_m ** 2 - axe_decale_m ** 2, 1e-18, None))

    # Déplacement depuis le PMH
    x = y_tdc - y

    # Obliquité de bielle
    sin_beta = np.clip(s / L_m, -1.0, 1.0)
    beta_rad = np.arcsin(sin_beta)
    cos_beta = np.sqrt(np.clip(1.0 - sin_beta ** 2, 1e-18, None))
    tan_beta = sin_beta / cos_beta

    # Dérivées exactes en theta
    # x'(theta) = r sin(theta) + r cos(theta) * s / g
    dx_dtheta = r_m * np.sin(theta_rad) + (r_m * np.cos(theta_rad) * s / g)

    # x''(theta)
    # q = r cos(theta) * s / g
    # q' = (-r s sin(theta) + r² cos²(theta))/g + r² cos²(theta) s² / g³
    q_prime = (
        (-r_m * s * np.sin(theta_rad) + (r_m ** 2) * (np.cos(theta_rad) ** 2)) / g
        + ((r_m ** 2) * (np.cos(theta_rad) ** 2) * (s ** 2)) / (g ** 3)
    )
    d2x_dtheta2 = r_m * np.cos(theta_rad) + q_prime

    # Conversion temporelle
    v = dx_dtheta * omega_rad_s
    a = d2x_dtheta2 * (omega_rad_s ** 2)

    return {
        "theta_mech_deg": theta_mech_deg,
        "theta_rad": theta_rad,
        "x_piston_m": x,
        "v_piston_ms": v,
        "a_piston_ms2": a,
        "beta_rad": beta_rad,
        "sin_beta": sin_beta,
        "cos_beta": cos_beta,
        "tan_beta": tan_beta,
    }


def _volume_cylindre(
    x_piston_m: np.ndarray,
    section_piston_m2: float,
    volume_residuel_m3: float,
) -> np.ndarray:
    return volume_residuel_m3 + section_piston_m2 * x_piston_m


def _modele_pression_interne_simple(
    theta_deg: np.ndarray,
    volume_m3: np.ndarray,
    params: CycleMecaniqueParams,
) -> np.ndarray:
    """
    Modèle interne simple 4 temps sans loi de combustion détaillée.
    Suffisant pour faire tourner le module, pas pour valider un moteur réel.

    Phases :
    0..180   détente
    180..360 échappement
    360..540 admission
    540..720 compression
    """
    v_tdc = params.volume_residuel_m3
    v_bdc = params.volume_residuel_m3 + params.section_piston_m2 * params.course_m

    p = np.empty_like(theta_deg, dtype=float)

    mask_det = (theta_deg >= 0.0) & (theta_deg < 180.0)
    mask_ech = (theta_deg >= 180.0) & (theta_deg < 360.0)
    mask_adm = (theta_deg >= 360.0) & (theta_deg < 540.0)
    mask_comp = (theta_deg >= 540.0) & (theta_deg <= 720.0)

    p_tdc_comp = params.pression_admission_pa * (v_bdc / v_tdc) ** params.n_polytropique_compression

    p[mask_det] = p_tdc_comp * (v_tdc / volume_m3[mask_det]) ** params.n_polytropique_detente
    p[mask_ech] = params.pression_echappement_pa
    p[mask_adm] = params.pression_admission_pa
    p[mask_comp] = params.pression_admission_pa * (v_bdc / volume_m3[mask_comp]) ** params.n_polytropique_compression

    return p


def _build_pressure_array(
    theta_deg: np.ndarray,
    theta_rad: np.ndarray,
    volume_m3: np.ndarray,
    params: CycleMecaniqueParams,
) -> np.ndarray:
    """
    Priorité :
    1) loi_pression_cylindre
    2) modele_combustion
    3) modèle interne simple
    """
    if params.loi_pression_cylindre is not None:
        law = params.loi_pression_cylindre

        if callable(law):
            p = law(
                theta_deg,
                theta_rad,
                {
                    "volume_m3": volume_m3,
                    "params": params,
                },
            )
            p = np.asarray(p, dtype=float)

        elif isinstance(law, Mapping):
            if "theta_deg" not in law or "p_pa" not in law:
                raise ValueError(
                    "loi_pression_cylindre mapping doit contenir 'theta_deg' et 'p_pa'"
                )
            theta_src = np.asarray(law["theta_deg"], dtype=float)
            p_src = np.asarray(law["p_pa"], dtype=float)
            if theta_src.ndim != 1 or p_src.ndim != 1 or theta_src.size != p_src.size:
                raise ValueError("theta_deg et p_pa doivent être 1D et de même taille")
            p = np.interp(theta_deg, theta_src, p_src)

        else:
            p = np.asarray(law, dtype=float)
            if p.shape != theta_deg.shape:
                raise ValueError(
                    "loi_pression_cylindre tableau doit avoir la même forme que theta_deg"
                )

        if np.any(p < 0.0):
            raise ValueError("pression cylindre négative détectée")
        return p

    if params.modele_combustion is not None:
        p = params.modele_combustion(
            theta_deg,
            theta_rad,
            {
                "volume_m3": volume_m3,
                "params": params,
            },
        )
        p = np.asarray(p, dtype=float)
        if p.shape != theta_deg.shape:
            raise ValueError("modele_combustion doit retourner un tableau de même taille")
        if np.any(p < 0.0):
            raise ValueError("modele_combustion a produit une pression négative")
        return p

    return _modele_pression_interne_simple(theta_deg, volume_m3, params)


def _phases_allumage_deg(params: CycleMecaniqueParams) -> Dict[int, float]:
    """
    Répartition uniforme des temps moteur sur 720° à partir de l'ordre d'allumage.
    """
    order = params.firing_order_list()
    pas = params.cycle_deg / params.nombre_cylindres
    return {cyl: i * pas for i, cyl in enumerate(order)}


def _efforts_cylindre(
    theta_global_deg: np.ndarray,
    phase_deg: float,
    params: CycleMecaniqueParams,
) -> Dict[str, np.ndarray]:
    theta_local_deg = np.mod(theta_global_deg - phase_deg, params.cycle_deg)

    kin = _cinematique_bielle_manivelle_exacte(
        theta_cycle_deg=theta_local_deg,
        r_m=params.rayon_manivelle_m,
        L_m=params.longueur_bielle_m,
        omega_rad_s=params.omega_rad_s,
        axe_decale_m=params.axe_decale_m,
    )

    volume_m3 = _volume_cylindre(
        x_piston_m=kin["x_piston_m"],
        section_piston_m2=params.section_piston_m2,
        volume_residuel_m3=params.volume_residuel_m3,
    )

    p_cyl_pa = _build_pressure_array(
        theta_deg=theta_local_deg,
        theta_rad=kin["theta_rad"],
        volume_m3=volume_m3,
        params=params,
    )

    # Force gaz utile nette par rapport à la pression de référence
    F_gaz_N = (p_cyl_pa - params.pression_reference_pa) * params.section_piston_m2

    # Force d'inertie sur la masse alternative
    F_inertie_N = params.masse_alternative_kg * kin["a_piston_ms2"]

    # Force nette sur l'axe du piston
    F_piston_net_N = F_gaz_N - F_inertie_N

    # Effort axial dans la bielle
    F_axiale_bielle_N = F_piston_net_N / kin["cos_beta"]

    # Force latérale sur la jupe
    F_laterale_piston_N = F_piston_net_N * kin["tan_beta"]

    # Efforts au maneton
    F_tangentielle_maneton_N = F_axiale_bielle_N * np.sin(kin["theta_rad"] + kin["beta_rad"])
    F_radiale_maneton_N = F_axiale_bielle_N * np.cos(kin["theta_rad"] + kin["beta_rad"])

    # Couple instantané
    T_inst_Nm = F_tangentielle_maneton_N * params.rayon_manivelle_m

    # Effets de la masse tournante équivalente
    F_centrifuge_N = (
        params.masse_tournante_equivalente_kg
        * params.rayon_maneton_m
        * (params.omega_rad_s ** 2)
    )

    # Repère moteur simple :
    # - axe Y = axe cylindre
    # - axe X = transversal
    # composantes approximatives de l'effort ramené au vilebrequin
    Fx_crank_N = F_laterale_piston_N + F_centrifuge_N * np.sin(kin["theta_rad"])
    Fy_crank_N = -F_piston_net_N - F_centrifuge_N * np.cos(kin["theta_rad"])

    return {
        "theta_local_deg": theta_local_deg,
        "volume_m3": volume_m3,
        "p_cyl_pa": p_cyl_pa,
        "x_piston_m": kin["x_piston_m"],
        "v_piston_ms": kin["v_piston_ms"],
        "a_piston_ms2": kin["a_piston_ms2"],
        "beta_rad": kin["beta_rad"],
        "F_gaz_N": F_gaz_N,
        "F_inertie_N": F_inertie_N,
        "F_piston_net_N": F_piston_net_N,
        "F_axiale_bielle_N": F_axiale_bielle_N,
        "F_laterale_piston_N": F_laterale_piston_N,
        "F_tangentielle_maneton_N": F_tangentielle_maneton_N,
        "F_radiale_maneton_N": F_radiale_maneton_N,
        "T_inst_Nm": T_inst_Nm,
        "Fx_crank_N": Fx_crank_N,
        "Fy_crank_N": Fy_crank_N,
    }


def _compute_torque_cycle_stats(theta_deg: np.ndarray, T_inst_Nm: np.ndarray) -> TorqueCycleStats:
    theta_rad_cycle = np.deg2rad(theta_deg)

    T_moy = float(np.mean(T_inst_Nm))
    T_max = float(np.max(T_inst_Nm))
    T_min = float(np.min(T_inst_Nm))
    T_rms = float(np.sqrt(np.mean(T_inst_Nm ** 2)))

    fluctuation = T_max - T_min

    denom = max(abs(T_moy), 1e-12)
    coeff_fluctuation = fluctuation / denom

    # Travail / énergie sur un cycle 720°
    energie_cycle_J = float(np.trapz(T_inst_Nm, theta_rad_cycle))

    # Indicateur d'irrégularité de couple (ripple intrinsèque)
    # Ce n'est PAS l'irrégularité de vitesse du volant, qui nécessite J_total et le couple résistant.
    irregularite_couple = float(np.std(T_inst_Nm) / denom)

    return TorqueCycleStats(
        T_moy_Nm=T_moy,
        T_max_Nm=T_max,
        T_min_Nm=T_min,
        T_rms_Nm=T_rms,
        fluctuation_couple_Nm=fluctuation,
        coefficient_fluctuation_couple=coeff_fluctuation,
        energie_cycle_J=energie_cycle_J,
        irregularite_couple=irregularite_couple,
    )


def calculer_cycle_mecanique(params: CycleMecaniqueParams) -> CycleMecaniqueResult:
    theta_deg = _build_theta_deg(params.cycle_deg, params.pas_angle_deg)
    phase_map = _phases_allumage_deg(params)

    par_cylindre: Dict[int, Dict[str, np.ndarray]] = {}

    T_total_Nm = np.zeros_like(theta_deg, dtype=float)
    Fx_total_N = np.zeros_like(theta_deg, dtype=float)
    Fy_total_N = np.zeros_like(theta_deg, dtype=float)

    for cyl, phase_deg in phase_map.items():
        d = _efforts_cylindre(theta_deg, phase_deg, params)
        par_cylindre[cyl] = d

        T_total_Nm += d["T_inst_Nm"]
        Fx_total_N += d["Fx_crank_N"]
        Fy_total_N += d["Fy_crank_N"]

    # Réactions de paliers équivalentes :
    # on répartit la résultante moteur sur 2 paliers 50/50
    R_eq_N = np.sqrt(Fx_total_N ** 2 + Fy_total_N ** 2)
    R_palier_1_N = 0.5 * R_eq_N
    R_palier_2_N = 0.5 * R_eq_N

    cyl_ref = params.firing_order_list()[0]
    ref = par_cylindre[cyl_ref]

    torque_stats = _compute_torque_cycle_stats(theta_deg, T_total_Nm)

    enveloppes = {
        "p_cyl_pa": EnvelopeStats.from_array(ref["p_cyl_pa"]).as_dict(),
        "x_piston_m": EnvelopeStats.from_array(ref["x_piston_m"]).as_dict(),
        "v_piston_ms": EnvelopeStats.from_array(ref["v_piston_ms"]).as_dict(),
        "a_piston_ms2": EnvelopeStats.from_array(ref["a_piston_ms2"]).as_dict(),
        "obliquite_bielle_rad": EnvelopeStats.from_array(ref["beta_rad"]).as_dict(),
        "F_gaz_N": EnvelopeStats.from_array(ref["F_gaz_N"]).as_dict(),
        "F_inertie_N": EnvelopeStats.from_array(ref["F_inertie_N"]).as_dict(),
        "F_axiale_bielle_N": EnvelopeStats.from_array(ref["F_axiale_bielle_N"]).as_dict(),
        "F_laterale_piston_N": EnvelopeStats.from_array(ref["F_laterale_piston_N"]).as_dict(),
        "T_inst_Nm": EnvelopeStats.from_array(T_total_Nm).as_dict(),
        "R_palier_1_N": EnvelopeStats.from_array(R_palier_1_N).as_dict(),
        "R_palier_2_N": EnvelopeStats.from_array(R_palier_2_N).as_dict(),
    }

    extras = {
        "rapport_lambda": params.rapport_lambda,
        "section_piston_m2": params.section_piston_m2,
        "volume_residuel_m3": params.volume_residuel_m3,
        "phases_cylindres_deg": phase_map,
        "par_cylindre": par_cylindre,
        "Fx_total_N": Fx_total_N,
        "Fy_total_N": Fy_total_N,
        "hypotheses": {
            "cinematique": "exacte bielle-manivelle",
            "force_gaz": "p(theta) * A_piston",
            "force_inertie": "m_alternative * a(theta)",
            "couple_instantane": "F_tangentielle_maneton * r",
            "paliers": "modele equivalent 2 paliers, partage 50/50",
            "irregularite_couple": "std(T_inst)/|T_moy|, indicateur de ripple de couple",
            "note_irregularite_vitesse": "non calculable sans inertie totale + couple resistant",
        },
    }

    return CycleMecaniqueResult(
        theta_deg=theta_deg,
        p_cyl_pa=ref["p_cyl_pa"],
        x_piston_m=ref["x_piston_m"],
        v_piston_ms=ref["v_piston_ms"],
        a_piston_ms2=ref["a_piston_ms2"],
        obliquite_bielle_rad=ref["beta_rad"],
        F_gaz_N=ref["F_gaz_N"],
        F_inertie_N=ref["F_inertie_N"],
        F_axiale_bielle_N=ref["F_axiale_bielle_N"],
        F_laterale_piston_N=ref["F_laterale_piston_N"],
        T_inst_Nm=T_total_Nm,
        R_palier_1_N=R_palier_1_N,
        R_palier_2_N=R_palier_2_N,
        enveloppes=enveloppes,
        statistiques_cycle=torque_stats.as_dict(),
        extras=extras,
    )


__all__ = [
    "CycleMecaniqueParams",
    "CycleMecaniqueResult",
    "EnvelopeStats",
    "TorqueCycleStats",
    "calculer_cycle_mecanique",
]