# -*- coding: utf-8 -*-
# backend/pieces/vilebrequin.py
"""
Pré-dimensionnement d'un vilebrequin pour moteur Stirling.

- r = S/2 (rayon de manivelle)
- Maneton (crankpin) : diamètre et largeur depuis charge radiale (∝ B^2), régime (inertie), et limites
  de pression de palier et de contrainte en flexion.
- Joues/contrepoids : règles de pouce + masse de contrepoids pour un facteur d'équilibrage donné.

Hypothèses simplifiées :
- Force radiale sur maneton W ≈ F_gaz,peak ± F_inertie,peak. On prend le pire cas (somme).
- Flexion du maneton : schéma "appuis simples – charge centrée" -> M_max ≈ W * L_support / 4.
- Le couple transmis pic T_peak ≈ F_gaz,peak * r (ordre de grandeur).
- Joues : contrôle Von Mises simplifié avec une section "col" b_web × t_web.

Pour un design final :
- utiliser un calcul de fatigue (Goodman), facteurs de concentration réels (congés, perçages),
- calcul hydrodynamique du palier big-end, et une CAO pour les inerties exactes.
"""

from __future__ import annotations
from dataclasses import dataclass
import math

# ----------------------------
# Entrées / Sorties
# ----------------------------

@dataclass
class CrankInputs:
    # Géométrie & cycle
    bore_m: float                 # B (m)
    stroke_m: float               # S (m)
    rpm: float                    # régime (tr/min)
    n_cyl: int = 1

    # Pressions / inerties
    p_mean_cycle_Pa: float = 200e3     # Pa
    p_peak_gas_Pa: float = 1.2e6       # Pa
    dyn_load_factor: float = 1.15      # facteur dynamique additionnel sur W (bielles, jeux)

    # Masse alternative à équilibrer (par cylindre)
    mass_recip_kg: float = 0.35        # piston + segments + axe + petite partie bielle (kg)
    balance_factor: float = 0.5        # fraction de masse alternative équilibrée (0..1)
    cw_radius_ratio: float = 0.9       # r_cw ≈ 0.9*r (rayon CG contrepoids)

    # Palier big-end (portée sur maneton)
    pin_L_over_D: float = 0.65         # L = (L/D)*d_pin
    pin_p_allow_Pa: float = 12e6       # pression portante admissible (Pa)
    pin_PV_allow_W_m2: float = 2.5e6   # limite PV indicative (W/m²)

    # Matériau & contraintes admissibles
    steel_sigma_allow_Pa: float = 220e6   # flexion admissible (Pa)
    steel_tau_allow_Pa: float = 120e6     # cisaillement admissible (Pa)
    steel_density: float = 7850.0         # kg/m3

    # Joues (règles de pouce + congés)
    web_thickness_k: float = 0.7         # t_web ≈ 0.7 * d_pin
    web_width_k: float = 1.2             # b_web ≈ 1.2 * d_pin
    fillet_ratio: float = 0.08           # rayon congé ≈ 0.08 * d_pin

@dataclass
class CrankResult:
    ok: bool
    message: str

    # Cinématique & forces
    r_m: float = 0.0
    A_piston_m2: float = 0.0
    F_mean_N: float = 0.0
    F_peak_N: float = 0.0
    F_inertia_peak_N: float = 0.0
    W_crankpin_peak_N: float = 0.0
    T_mean_total_Nm: float = 0.0
    T_peak_per_cyl_Nm: float = 0.0

    # Maneton (dimensions & checks)
    pin_diameter_m: float = 0.0
    pin_length_m: float = 0.0
    pin_clearance_m: float = 0.0
    pin_unit_pressure_Pa: float = 0.0
    pin_surface_speed_m_s: float = 0.0
    pin_PV_W_m2: float = 0.0
    pin_sigma_bend_Pa: float = 0.0
    pin_vm_utilization: float = 0.0

    # Joues & couple
    web_thickness_m: float = 0.0
    web_width_m: float = 0.0
    web_vonmises_Pa: float = 0.0

    # Contrepoids
    cw_radius_m: float = 0.0
    cw_mass_kg: float = 0.0

# ----------------------------
# Utilitaires
# ----------------------------

def mean_piston_speed(stroke_m: float, rpm: float) -> float:
    return 2.0 * stroke_m * rpm / 60.0

def peak_inertia_force(m_recip: float, stroke_m: float, rpm: float) -> float:
    # F_inertie_max ≈ m * r * ω^2, r = S/2
    omega = 2.0 * math.pi * (rpm / 60.0)
    r = 0.5 * stroke_m
    return m_recip * r * (omega ** 2)

def surface_speed(D_m: float, rpm: float) -> float:
    # v = π D n / 60
    return math.pi * D_m * rpm / 60.0

# ----------------------------
# Dimensionnement
# ----------------------------

def size_crankshaft(inp: CrankInputs) -> CrankResult:
    r = 0.5 * inp.stroke_m
    A = math.pi * (inp.bore_m ** 2) / 4.0
    F_mean = inp.p_mean_cycle_Pa * A
    F_peak = inp.p_peak_gas_Pa * A

    # Inertie alternative (primaire) — pic
    F_inert = peak_inertia_force(inp.mass_recip_kg, inp.stroke_m, inp.rpm)

    # Charge radiale sur maneton (pire cas)
    W = (F_peak + F_inert) * inp.dyn_load_factor

    # Couple
    T_mean_per_cyl = F_mean * r
    T_peak_per_cyl = F_peak * r
    T_mean_total = inp.n_cyl * T_mean_per_cyl

    # --- Maneton : dimensionnement par pression de palier ---
    # p = W / (d * L) = W / (d * (k * d)) = W / (k * d^2)  => d >= sqrt( W / (k * p_allow) )
    d_pin_bearing = math.sqrt(max(W, 1.0) / (inp.pin_L_over_D * max(inp.pin_p_allow_Pa, 1.0)))
    d_pin = max(d_pin_bearing, 0.010)  # borne pratique 10 mm min
    L_pin = inp.pin_L_over_D * d_pin

    # PV (info)
    v_pin = surface_speed(d_pin, inp.rpm)
    p_unit = W / (d_pin * L_pin)
    PV = p_unit * v_pin

    # --- Maneton : flexion entre joues ---
    fillet = inp.fillet_ratio * d_pin
    span = L_pin + 2.0 * fillet  # distance entre appuis approx
    M_max = W * span / 4.0
    sigma_b = (32.0 * M_max) / (math.pi * d_pin**3)

    # Von Mises avec cisaillement pur négligeable dans le maneton (torsion passe surtout par les joues)
    sigma_vm_pin = sigma_b  # simplification (prudente)

    # Ajuste si contrainte dépasse l'admissible : grossière montée d
    if sigma_vm_pin > inp.steel_sigma_allow_Pa:
        d_req = ( (32.0 * M_max) / (math.pi * max(inp.steel_sigma_allow_Pa,1.0)) ) ** (1.0/3.0)
        d_pin = max(d_pin, d_req)
        L_pin = inp.pin_L_over_D * d_pin
        v_pin = surface_speed(d_pin, inp.rpm)
        p_unit = W / (d_pin * L_pin)
        PV = p_unit * v_pin
        sigma_b = (32.0 * M_max) / (math.pi * d_pin**3)
        sigma_vm_pin = sigma_b

    # --- Joues : règles de pouce + contrôle Von Mises ---
    t_web = inp.web_thickness_k * d_pin
    b_web = inp.web_width_k * d_pin
    # Bending in web "neck": approx section rectangulaire (b_web × t_web)
    # module de flexion Z ≈ b * t^2 / 6 (flexion selon épaisseur)
    Z = b_web * (t_web ** 2) / 6.0
    # Torsion: module polaire approx J ≈ b * t^3 / 3 (rectangle mince, torsion St-Venant)
    J = b_web * (t_web ** 3) / 3.0

    # Moments/torque dans la joue : M_web ~ W * (t_web/2) (charge transmise via maneton) – très simplifié
    M_web = W * (t_web / 2.0)
    T_web = T_peak_per_cyl  # ordre de grandeur : le couple passe via la joue

    sigma_web = M_web / max(Z, 1e-12)
    tau_web = T_web * (t_web / 2.0) / max(J, 1e-12)  # τ ≈ T*r/J avec r ≈ t/2
    sigma_vm_web = math.sqrt(sigma_web**2 + 3.0 * tau_web**2)

    # Si dépassement, augmenter t_web
    if sigma_vm_web > inp.steel_sigma_allow_Pa:
        scale = (sigma_vm_web / inp.steel_sigma_allow_Pa) ** (1.0/2.0)
        t_web *= scale
        # Recalcule
        Z = b_web * (t_web ** 2) / 6.0
        J = b_web * (t_web ** 3) / 3.0
        sigma_web = M_web / max(Z, 1e-12)
        tau_web = T_web * (t_web / 2.0) / max(J, 1e-12)
        sigma_vm_web = math.sqrt(sigma_web**2 + 3.0 * tau_web**2)

    # --- Contrepoids primaire ---
    r_cw = inp.cw_radius_ratio * r
    # Équilibre primaire : m_cw * r_cw ≈ f_b * m_rec * r
    m_cw = (inp.balance_factor * inp.mass_recip_kg * r) / max(r_cw, 1e-9)

    # --- Verdict & message ---
    issues = []
    if p_unit > inp.pin_p_allow_Pa: issues.append("p_pin>p_allow")
    if PV > inp.pin_PV_allow_W_m2: issues.append("PV_pin>limite")
    if sigma_vm_pin > inp.steel_sigma_allow_Pa: issues.append("σ_pin>σ_allow")
    if sigma_vm_web > inp.steel_sigma_allow_Pa: issues.append("σ_vm_web>σ_allow")

    ok = len(issues) == 0
    msg = "OK" if ok else "Ajuster d_pin / L_pin / t_web / matériaux : " + ", ".join(issues)

    return CrankResult(
        ok=ok, message=msg,
        r_m=r, A_piston_m2=A,
        F_mean_N=F_mean, F_peak_N=F_peak, F_inertia_peak_N=F_inert,
        W_crankpin_peak_N=W,
        T_mean_total_Nm=T_mean_total,
        T_peak_per_cyl_Nm=T_peak_per_cyl,
        pin_diameter_m=d_pin, pin_length_m=L_pin, pin_clearance_m=0.0015*d_pin,
        pin_unit_pressure_Pa=p_unit, pin_surface_speed_m_s=v_pin, pin_PV_W_m2=PV,
        pin_sigma_bend_Pa=sigma_b, pin_vm_utilization=sigma_vm_pin / max(inp.steel_sigma_allow_Pa,1.0),
        web_thickness_m=t_web, web_width_m=b_web, web_vonmises_Pa=sigma_vm_web,
        cw_radius_m=r_cw, cw_mass_kg=m_cw
    )

# ----------------------------
# Démo / exécution directe
# ----------------------------

if __name__ == "__main__":
    # Exemple : B=80 mm, S=80 mm, 600 tr/min, 1 cylindre
    inp = CrankInputs(
        bore_m=0.080, stroke_m=0.080, rpm=600.0, n_cyl=1,
        p_mean_cycle_Pa=200e3, p_peak_gas_Pa=1.2e6,
        mass_recip_kg=0.35, balance_factor=0.5
    )
    res = size_crankshaft(inp)

    print("=== VILEBREQUIN ===")
    print(f"r = S/2 (mm)               : {res.r_m*1000:.2f}")
    print(f"A piston (cm²)             : {res.A_piston_m2*1e4:.2f}")
    print(f"F_mean / cyl (N)           : {res.F_mean_N:.1f}")
    print(f"F_peak / cyl (N)           : {res.F_peak_N:.1f}")
    print(f"F_inertie_peak (N)         : {res.F_inertia_peak_N:.1f}")
    print(f"W maneton (N)              : {res.W_crankpin_peak_N:.1f}")
    print(f"T_mean total (N·m)         : {res.T_mean_total_Nm:.2f}")
    print(f"T_peak / cyl (N·m)         : {res.T_peak_per_cyl_Nm:.2f}")
    print("--- Maneton ---")
    print(f"d_pin (mm)                 : {res.pin_diameter_m*1000:.2f}")
    print(f"L_pin (mm)                 : {res.pin_length_m*1000:.2f}")
    print(f"Jeu radial estimé (µm)     : {res.pin_clearance_m*1e6:.1f}")
    print(f"p_pin (MPa)                : {res.pin_unit_pressure_Pa/1e6:.2f}")
    print(f"PV_pin (MW/m²)             : {res.pin_PV_W_m2/1e6:.2f}")
    print(f"σ_bend_pin (MPa)           : {res.pin_sigma_bend_Pa/1e6:.1f}")
    print(f"Utilisation σ_VM pin       : {res.pin_vm_utilization*100:.1f} %")
    print("--- Joues ---")
    print(f"t_web (mm)                 : {res.web_thickness_m*1000:.2f}")
    print(f"b_web (mm)                 : {res.web_width_m*1000:.2f}")
    print(f"σ_VM web (MPa)             : {res.web_vonmises_Pa/1e6:.1f}")
    print("--- Contrepoids ---")
    print(f"r_cw (mm)                  : {res.cw_radius_m*1000:.2f}")
    print(f"m_cw (kg)                  : {res.cw_mass_kg:.3f}")
    print(res.message)
