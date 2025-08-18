# -*- coding: utf-8 -*-
# backend/pieces/volant_inertie.py
"""
Dimensionnement d'un volant d'inertie pour lisser l'ondulation de couple d'un moteur Stirling.

Entrées possibles:
  A) Directes: T_mean (couple moyen) + T1 (amplitude fondamentale de couple ondulant)
     Option: T1 par cylindre + phases -> T1_eq = |somme vectorielle|
  B) Cycle: p_me, Vs_total_par_tour, eta_mech -> T_mean = p_me * Vs_total * eta / (2π)
     + alpha = T1/T_mean

Calculs principaux:
  - ΔE ≈ 2*T1/k  (harmonique k, k=1 par défaut)
  - J_req = ΔE / (ω^2 * c)  avec c = coefficient d'irrégularité cible
  - Dimensionnement masse/rayon pour volant "rim" (kshape=1) ou "solid" (kshape=1/2)
  - Checks: vitesse de jante, contrainte cerceau (σ ≈ ρ v^2), énergie stockée.

NOTA: pré-dimensionnement. Affiner ensuite (répartition de masse, rayons de congé, perçages,
fixations, équilibrages, fatigue).
"""

from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Iterable, Optional

# =========================
# Données d'entrée / sortie
# =========================

@dataclass
class FlywheelInputs:
    # Mode A : direct
    T_mean_Nm: Optional[float] = None     # Couple moyen (Nm)
    T1_Nm: Optional[float] = None         # Amplitude fondamentale (Nm) (après sommation multi-cylindres)
    # Ou bien (T1 par cylindre + phases) :
    T1_per_cyl_Nm: Optional[Iterable[float]] = None   # liste/tuple
    phase_per_cyl_deg: Optional[Iterable[float]] = None  # mêmes longueurs, en ° (0..360)

    # Mode B : depuis p_me et Vs_total
    p_me_Pa: Optional[float] = None       # Pa
    Vs_total_per_rev_m3: Optional[float] = None  # m³ par tour (somme de tous les cylindres)
    eta_mech: float = 1.0                 # rendement mécanique (facteur sur Tm)
    alpha_ripple: Optional[float] = None  # alpha = T1 / T_mean (si T1 inconnu)

    # Harmoniques & objectifs
    k_harmonic: int = 1                   # rang harmonique dominant (1 par défaut)
    coeff_irregularity: float = 0.02      # c = (ωmax-ωmin)/ωmoy (ex: 0.02 = ±1%)

    # Régime
    rpm: float = 600.0

    # Choix de conception volant
    shape: str = "rim"                    # "rim" (couronne mince) ou "solid" (disque plein)
    radius_m: float = 0.15                # rayon extérieur (m) disponible
    material_density: float = 7850.0      # kg/m³ (acier)
    rim_speed_limit_m_s: float = 80.0     # m/s (prudence acier)
    # (optionnel) contrainte cerceau limite (~ρ v^2); si 0 -> pas de check supplémentaire
    hoop_stress_allow_Pa: float = 0.0

@dataclass
class FlywheelResult:
    ok: bool
    message: str
    # base cinématique
    omega_rad_s: float = 0.0
    T_mean_Nm: float = 0.0
    T1_equiv_Nm: float = 0.0
    harmonic_k: int = 1
    deltaE_J: float = 0.0
    coeff_irregularity: float = 0.0

    # Inertie requise
    J_required_kg_m2: float = 0.0
    energy_stored_J: float = 0.0

    # Dimension géométrique associée
    shape: str = "rim"
    radius_m: float = 0.0
    k_shape: float = 1.0
    mass_required_kg: float = 0.0

    # Checks
    rim_speed_m_s: float = 0.0
    hoop_stress_Pa: float = 0.0
    speed_ok: bool = True
    hoop_ok: bool = True

# ================
# Utilitaires
# ================

def _deg2rad(a_deg: float) -> float:
    return a_deg * math.pi / 180.0

def combine_T1_phased(T1_list: Iterable[float], phase_deg_list: Iterable[float]) -> float:
    """
    Combine des sinusoïdes de même fréquence (harmonique k), amplitudes T1_i et phases φ_i (en °).
    Retourne l'amplitude équivalente |Σ T1_i * e^{jφ_i}|.
    """
    T1x = 0.0
    T1y = 0.0
    for Ti, ph in zip(T1_list, phase_deg_list):
        ang = _deg2rad(ph)
        T1x += Ti * math.cos(ang)
        T1y += Ti * math.sin(ang)
    return math.hypot(T1x, T1y)

def mean_torque_from_bmep(p_me_Pa: float, Vs_total_per_rev_m3: float, eta_mech: float = 1.0) -> float:
    """
    T_mean = P/ω, P = p_me * Vs_total * rps * eta, ω = 2π * rps -> T_mean = p_me * Vs_total * eta / (2π)
    """
    return (p_me_Pa * Vs_total_per_rev_m3 * eta_mech) / (2.0 * math.pi)

def shape_k(shape: str) -> float:
    """
    Coefficient J = k * m * r^2
      - rim (couronne mince) : k=1
      - solid (disque plein) : k=1/2
    """
    s = shape.lower()
    if s == "rim":
        return 1.0
    if s == "solid":
        return 0.5
    raise ValueError("shape doit être 'rim' ou 'solid'.")

# =======================
# Calcul principal
# =======================

def size_flywheel(inp: FlywheelInputs) -> FlywheelResult:
    omega = 2.0 * math.pi * (inp.rpm / 60.0)

    # --- Coupled inputs resolution ---
    # 1) T_mean
    if inp.T_mean_Nm is not None:
        Tm = inp.T_mean_Nm
    elif (inp.p_me_Pa is not None) and (inp.Vs_total_per_rev_m3 is not None):
        Tm = mean_torque_from_bmep(inp.p_me_Pa, inp.Vs_total_per_rev_m3, inp.eta_mech)
    else:
        return FlywheelResult(ok=False, message="Fournir T_mean ou (p_me & Vs_total_par_tour).")

    # 2) T1 (amplitude fondamentale)
    if inp.T1_Nm is not None:
        T1 = inp.T1_Nm
    elif (inp.T1_per_cyl_Nm is not None) and (inp.phase_per_cyl_deg is not None):
        T1 = combine_T1_phased(inp.T1_per_cyl_Nm, inp.phase_per_cyl_deg)
    elif inp.alpha_ripple is not None:
        T1 = abs(inp.alpha_ripple) * abs(Tm)
    else:
        return FlywheelResult(ok=False, message="Fournir T1, ou (T1_i + phases), ou alpha_ripple.")

    # 3) Énergie fluctuation (harmonique k)
    k = max(1, int(inp.k_harmonic))
    deltaE = 2.0 * T1 / k  # J (Nm·rad avec rad sans dimension)

    # 4) Inertie requise
    c = max(1e-6, float(inp.coeff_irregularity))
    Jreq = deltaE / (omega**2 * c)

    # 5) Conversion en masse pour un rayon donné
    ksh = shape_k(inp.shape)
    r = max(inp.radius_m, 1e-6)
    mreq = Jreq / (ksh * r * r)

    # 6) Checks vitesse de jante & contrainte cerceau
    v = omega * r
    hoop = inp.material_density * v * v if inp.hoop_stress_allow_Pa > 0.0 else 0.0
    speed_ok = v <= inp.rim_speed_limit_m_s
    hoop_ok = True if inp.hoop_stress_allow_Pa <= 0.0 else (hoop <= inp.hoop_stress_allow_Pa)

    # 7) Énergie stockée au régime
    Estore = 0.5 * Jreq * omega * omega

    issues = []
    if not speed_ok:
        issues.append("vitesse de jante > limite")
    if not hoop_ok:
        issues.append("contrainte cerceau > admissible")

    ok = len(issues) == 0
    msg = "OK" if ok else "Attention : " + ", ".join(issues)

    return FlywheelResult(
        ok=ok, message=msg,
        omega_rad_s=omega, T_mean_Nm=Tm, T1_equiv_Nm=T1, harmonic_k=k, deltaE_J=deltaE, coeff_irregularity=c,
        J_required_kg_m2=Jreq, energy_stored_J=Estore,
        shape=inp.shape, radius_m=r, k_shape=ksh, mass_required_kg=mreq,
        rim_speed_m_s=v, hoop_stress_Pa=hoop, speed_ok=speed_ok, hoop_ok=hoop_ok
    )

# =======================
# Exemple d'utilisation
# =======================

if __name__ == "__main__":
    # Exemple 1 : à partir de p_me et Vs_total
    inp = FlywheelInputs(
        p_me_Pa=200e3,
        Vs_total_per_rev_m3=0.00025,  # 250 cm3 par tour (tous cylindres)
        eta_mech=0.9,
        alpha_ripple=0.25,            # T1 ~ 25% de Tm (ordre de grandeur)
        k_harmonic=1,
        coeff_irregularity=0.02,      # ±1% de variation
        rpm=600.0,
        shape="rim",
        radius_m=0.18,
        material_density=7850.0,
        rim_speed_limit_m_s=80.0,
        hoop_stress_allow_Pa=0.0
    )
    res = size_flywheel(inp)
    print("=== VOLANT D'INERTIE — Exemple 1 ===")
    print(f"ω (rad/s)                  : {res.omega_rad_s:.2f}")
    print(f"T_mean (Nm)                : {res.T_mean_Nm:.2f}")
    print(f"T1 équiv. (Nm)             : {res.T1_equiv_Nm:.2f}")
    print(f"ΔE (J)                     : {res.deltaE_J:.2f}")
    print(f"c (irrégularité)           : {res.coeff_irregularity:.4f}")
    print(f"J requis (kg·m²)           : {res.J_required_kg_m2:.4f}")
    print(f"E stockée (J)              : {res.energy_stored_J:.1f}")
    print(f"Type / r (m)               : {res.shape} / {res.radius_m:.3f}")
    print(f"Masse requise (kg)         : {res.mass_required_kg:.2f}")
    print(f"v_jante (m/s)              : {res.rim_speed_m_s:.1f}  (OK? {'Oui' if res.speed_ok else 'Non'})")
    print(res.message)

    # Exemple 2 : T1 par cylindre + phases
    inp2 = FlywheelInputs(
        T_mean_Nm=30.0,
        T1_per_cyl_Nm=[12.0, 12.0],      # 2 cylindres identiques
        phase_per_cyl_deg=[0.0, 90.0],   # déphasés de 90°
        k_harmonic=1, coeff_irregularity=0.015,
        rpm=900.0, shape="solid", radius_m=0.12,
        material_density=7850.0, rim_speed_limit_m_s=70.0
    )
    res2 = size_flywheel(inp2)
    print("\n=== VOLANT D'INERTIE — Exemple 2 ===")
    print(f"T1 équiv. (Nm)             : {res2.T1_equiv_Nm:.2f}")
    print(f"J requis (kg·m²)           : {res2.J_required_kg_m2:.4f}")
    print(f"Masse req. (kg, disque)    : {res2.mass_required_kg:.2f}")
    print(f"v_jante (m/s)              : {res2.rim_speed_m_s:.1f}  (OK? {'Oui' if res2.speed_ok else 'Non'})")
