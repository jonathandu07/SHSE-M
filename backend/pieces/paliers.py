# -*- coding: utf-8 -*-
# backend/pieces/paliers.py
"""
Pré-dimensionnement des paliers lisses d'un moteur Stirling (journaux).
- Paliers traités : principaux (vilebrequin) et tête de bielle (big-end).
- Basé sur : pression projetée p = W/(D*L), contrainte PV, clairance c = ε*D,
  vitesse de glissement v = π D n / 60, nombre de Sommerfeld (ordre de grandeur).
- Dimensionnement d’arbre (torsion+flexion simplifiés) pour proposer un D_arbre >= D_palier.

NOTA : ce module vise l'avant-projet. Affinez ensuite avec un calcul elastohydrodynamique,
la distribution d'alimentation, les tolérances et la tenue en température.
"""

from __future__ import annotations
from dataclasses import dataclass
import math

# ----------------------------
# Données d'entrée / sortie
# ----------------------------

@dataclass
class BearingInputs:
    # Géométrie et cycle
    bore_m: float                # Alésage cylindre B (m)
    stroke_m: float              # Course S (m)
    rpm: float                   # Régime (tr/min)
    n_cyl: int = 1               # Nombre de cylindres (répartit la charge moyenne sur le vilebrequin)
    conrod_ratio: float = 3.5    # L_bielle / S (3.0–4.0 typique)

    # Pressions gaz (estimations)
    p_mean_cycle_Pa: float = 200e3   # ~ BMEP (Pa)
    p_peak_gas_Pa: float = 1.2e6     # pic pression gaz (Pa)
    dyn_load_factor: float = 1.3     # facteur dynamique (inertie, chocs) sur charge radiale

    # Huile / clairance / matériaux
    oil_viscosity_Pa_s: float = 0.02     # viscosité dynamique à T_fonctionnement (Pa·s) (≈ 20 mPa·s)
    clearance_ratio: float = 0.0015      # clairance radiale relative ε = c/D (1.0–2.5 ‰ selon jeux)
    p_allow_Pa: float = 10e6             # pression portante admissible (Pa), bronze/AlSn typ. 8–12 MPa
    PV_allow_W_m2: float = 2.0e6         # limite PV (W/m²) pour revêtements standard (ordre de grandeur)
    sommerfeld_min: float = 0.05         # seuil indicatif (dépend L/D, cf. tables)

    # Architecture paliers
    n_main_bearings: int = 2             # nb de paliers principaux
    main_bearing_L_over_D: float = 0.7   # ratio L/D initial (0.5–1.0 courant)
    bigend_L_over_D: float = 0.6         # ratio L/D initial tête de bielle

    # Résistance arbre (acier)
    shaft_tau_allow_Pa: float = 120e6    # contrainte de torsion admissible (Pa)
    shaft_sigma_allow_Pa: float = 180e6  # contrainte de flexion admissible (Pa)
    k_bending: float = 1.3               # facteurs de concentration approx
    k_torsion: float = 1.2

@dataclass
class BearingResult:
    ok: bool
    message: str

    # Forces & cinématique
    gas_area_m2: float = 0.0
    F_mean_per_cyl_N: float = 0.0
    F_peak_per_cyl_N: float = 0.0
    crank_radius_m: float = 0.0
    torque_mean_per_cyl_Nm: float = 0.0

    # Vilebrequin — paliers principaux (moyenne par palier)
    main_D_m: float = 0.0
    main_L_m: float = 0.0
    main_clearance_m: float = 0.0
    main_unit_pressure_Pa: float = 0.0
    main_surface_speed_m_s: float = 0.0
    main_PV_W_m2: float = 0.0
    main_Sommerfeld: float = 0.0

    # Tête de bielle (big-end)
    bigend_D_m: float = 0.0
    bigend_L_m: float = 0.0
    bigend_clearance_m: float = 0.0
    bigend_unit_pressure_Pa: float = 0.0
    bigend_surface_speed_m_s: float = 0.0
    bigend_PV_W_m2: float = 0.0
    bigend_Sommerfeld: float = 0.0

    # Arbre — vérif simplifiée
    shaft_min_diameter_m: float = 0.0

# ----------------------------
# Utilitaires
# ----------------------------

def surface_speed(D_m: float, rpm: float) -> float:
    # v_surface = π D n / 60
    return math.pi * D_m * rpm / 60.0

def sommerfeld_number(eta: float, rpm: float, radius_m: float, clearance_m: float, unit_pressure_Pa: float) -> float:
    """
    Sommerfeld S ≈ (η * N * (r/c)^2) / p  avec N en tr/s, p = W/(L*D)
    C'est une forme usuelle pour juger du régime hydrodynamique (ordre de grandeur).
    """
    N = rpm / 60.0
    r_over_c_sq = (radius_m / max(clearance_m, 1e-12)) ** 2
    return (eta * N * r_over_c_sq) / max(unit_pressure_Pa, 1.0)

def shaft_min_diameter_torsion_flexion(T_Nm: float, M_Nm: float, tau_allow: float, sigma_allow: float,
                                       k_t: float, k_b: float) -> float:
    """
    Arbre circulaire plein — critère de Von Mises simplifié avec facteurs Kt/Kb :
    τ = 16 T / (π d^3), σ = 32 M / (π d^3).
    σ_eq ≈ sqrt( (Kb*σ)^2 + 3*(Kt*τ)^2 ) <= σ_allow  (approx prudente)
    On résout numériquement d.
    """
    T = abs(T_Nm)
    M = abs(M_Nm)
    if max(T, M) <= 0:
        return 0.0

    # Recherche par dichotomie
    d_min, d_max = 1e-3, 0.2  # 1 mm .. 200 mm
    for _ in range(80):
        d = 0.5 * (d_min + d_max)
        tau = (16.0 * T) / (math.pi * d**3)
        sigma = (32.0 * M) / (math.pi * d**3)
        sigma_eq = math.sqrt((k_b * sigma)**2 + 3.0 * (k_t * tau)**2)
        if sigma_eq > sigma_allow:
            d_min = d
        else:
            d_max = d
    # Vérif torsion pure vs tau_allow (second garde-fou)
    d_sol = d_max
    tau = (16.0 * T) / (math.pi * d_sol**3)
    if tau > tau_allow:
        # augmente d pour passer le cisaillement pur
        while tau > tau_allow and d_sol < 0.5:
            d_sol *= 1.02
            tau = (16.0 * T) / (math.pi * d_sol**3)
    return d_sol

# ----------------------------
# Calcul principal
# ----------------------------

def size_bearings(inp: BearingInputs) -> BearingResult:
    # 1) Forces gaz élémentaires
    A = math.pi * (inp.bore_m ** 2) / 4.0
    F_mean = inp.p_mean_cycle_Pa * A
    F_peak = inp.p_peak_gas_Pa * A
    r = 0.5 * inp.stroke_m
    T_mean_per_cyl = F_mean * r  # couple moyen par cylindre (ordre de grandeur)
    M_bend_per_cyl = F_peak * r  # moment de flexion local (ordre de grandeur)

    # 2) Dimensionnement arbre (min) — on se base sur un seul maneton chargé au pic
    #    Couple total ≈ n_cyl * T_mean_per_cyl (pour une estimation moyenne)
    T_total = inp.n_cyl * T_mean_per_cyl
    #    Moment de flexion : pic local ~ F_peak*r (représentatif) — très simplifié
    d_shaft = shaft_min_diameter_torsion_flexion(
        T_Nm=T_total, M_Nm=M_bend_per_cyl,
        tau_allow=inp.shaft_tau_allow_Pa, sigma_allow=inp.shaft_sigma_allow_Pa,
        k_t=inp.k_torsion, k_b=inp.k_bending
    )

    # 3) Choix d’un D de journal (palier) >= d_shaft, avec marge
    D_main = max(d_shaft * 1.10, 0.015)  # borne mini 15 mm
    D_be   = max(D_main * 0.9,  0.012)   # big-end souvent un peu plus petit

    # 4) Longueurs initiales L via L/D cibles
    L_main = inp.main_bearing_L_over_D * D_main
    L_be   = inp.bigend_L_over_D * D_be

    # 5) Charges par palier
    #    Répartition très simplifiée :
    #    - Paliers principaux : la somme des charges gaz se partage sur n_main_bearings → moyenne statique
    #    - Tête de bielle : reprend la charge radiale de SA bielle (au pic), amplifiée dynamiquement
    W_main = (inp.n_cyl * F_mean) / max(inp.n_main_bearings, 1)       # moyenne
    W_main_peak = (inp.n_cyl * F_peak * 0.5) / max(inp.n_main_bearings, 1)  # pic simplifié (≈ 50% du pic global)
    W_be = F_peak * inp.dyn_load_factor  # charge radiale sur tête de bielle (pic)

    # 6) Pressions projetées p = W/(D*L)
    p_main = W_main / (D_main * L_main)
    p_main_peak = W_main_peak / (D_main * L_main)
    p_be = W_be / (D_be * L_be)

    # 7) Vitesse de glissement & PV
    v_main = surface_speed(D_main, inp.rpm)
    v_be   = surface_speed(D_be,   inp.rpm)
    PV_main = p_main * v_main
    PV_be   = p_be * v_be

    # 8) Clairances
    c_main = inp.clearance_ratio * D_main
    c_be   = inp.clearance_ratio * D_be

    # 9) Nombre de Sommerfeld (ordre de grandeur)
    #    S ≈ (η * N * (r/c)^2) / p, avec r = D/2, p = W/(L*D)
    S_main = sommerfeld_number(inp.oil_viscosity_Pa_s, inp.rpm, D_main/2.0, c_main, p_main)
    S_be   = sommerfeld_number(inp.oil_viscosity_Pa_s, inp.rpm, D_be/2.0,   c_be,   p_be)

    # 10) Vérifs / itérations simples sur L si besoin (pression & PV)
    #     On augmente L jusqu’à respecter p_allow et PV_allow (sans toucher D pour rester compatible arbre)
    def adjust_length(D, L, W, v, p_allow, PV_allow):
        p = W / (D * L)
        PV = p * v
        # Étendre L si p>p_allow ou PV>PV_allow
        if p > p_allow or PV > PV_allow:
            # Longueur requise pour pression : Lp >= W/(D*p_allow)
            Lp = W / (D * p_allow)
            # Longueur requise pour PV : LPV >= (p * v <= PV_allow) → p <= PV_allow/v → L >= W/(D*(PV_allow/v))
            if v <= 1e-9:
                LPV = Lp
            else:
                p_limit = PV_allow / v
                LPV = W / (D * max(p_limit, 1.0))
            L = max(L, Lp, LPV)
        return L

    L_main = adjust_length(D_main, L_main, W_main, v_main, inp.p_allow_Pa, inp.PV_allow_W_m2)
    L_be   = adjust_length(D_be,   L_be,   W_be,   v_be,   inp.p_allow_Pa, inp.PV_allow_W_m2)

    # Recalcule pressions/PV après ajustement
    p_main = W_main / (D_main * L_main)
    p_main_peak = W_main_peak / (D_main * L_main)
    p_be = W_be / (D_be * L_be)
    PV_main = p_main * v_main
    PV_be   = p_be * v_be

    # Sommerfeld après ajustement (p change)
    S_main = sommerfeld_number(inp.oil_viscosity_Pa_s, inp.rpm, D_main/2.0, c_main, p_main)
    S_be   = sommerfeld_number(inp.oil_viscosity_Pa_s, inp.rpm, D_be/2.0,   c_be,   p_be)

    # 11) Verdict
    checks = []
    if p_main > inp.p_allow_Pa: checks.append("p_main>p_allow")
    if PV_main > inp.PV_allow_W_m2: checks.append("PV_main>PV_allow")
    if p_be > inp.p_allow_Pa: checks.append("p_bigend>p_allow")
    if PV_be > inp.PV_allow_W_m2: checks.append("PV_bigend>PV_allow")
    if S_main < inp.sommerfeld_min: checks.append("Sommerfeld_main bas")
    if S_be   < inp.sommerfeld_min: checks.append("Sommerfeld_bigend bas")

    ok = len(checks) == 0
    msg = "OK" if ok else "Ajuster D/L/huile : " + ", ".join(checks)

    return BearingResult(
        ok=ok, message=msg,
        gas_area_m2=A, F_mean_per_cyl_N=F_mean, F_peak_per_cyl_N=F_peak,
        crank_radius_m=r, torque_mean_per_cyl_Nm=T_mean_per_cyl,
        main_D_m=D_main, main_L_m=L_main, main_clearance_m=c_main,
        main_unit_pressure_Pa=p_main, main_surface_speed_m_s=v_main, main_PV_W_m2=PV_main,
        main_Sommerfeld=S_main,
        bigend_D_m=D_be, bigend_L_m=L_be, bigend_clearance_m=c_be,
        bigend_unit_pressure_Pa=p_be, bigend_surface_speed_m_s=v_be, bigend_PV_W_m2=PV_be,
        bigend_Sommerfeld=S_be,
        shaft_min_diameter_m=d_shaft
    )

# ----------------------------
# Exemple d'utilisation
# ----------------------------

if __name__ == "__main__":
    # Exemple : B=80 mm, S=80 mm, 600 tr/min, 1 cylindre, BMEP 200 kPa, pic 1.2 MPa
    inp = BearingInputs(
        bore_m=0.080, stroke_m=0.080, rpm=600.0, n_cyl=1,
        p_mean_cycle_Pa=200e3, p_peak_gas_Pa=1.2e6,
        oil_viscosity_Pa_s=0.02, clearance_ratio=0.0015,
        p_allow_Pa=10e6, PV_allow_W_m2=2.0e6,
        n_main_bearings=2, main_bearing_L_over_D=0.7, bigend_L_over_D=0.6
    )
    res = size_bearings(inp)

    print("=== PALIERS ===")
    print(f"A piston (cm²)             : {res.gas_area_m2*1e4:.2f}")
    print(f"F_mean / cyl (N)           : {res.F_mean_per_cyl_N:.1f}")
    print(f"F_peak / cyl (N)           : {res.F_peak_per_cyl_N:.1f}")
    print(f"r (mm)                      : {res.crank_radius_m*1000:.1f}")
    print(f"T_moy / cyl (N·m)          : {res.torque_mean_per_cyl_Nm:.2f}")
    print("--- Principaux ---")
    print(f"D_main (mm)                : {res.main_D_m*1000:.2f}")
    print(f"L_main (mm)                : {res.main_L_m*1000:.2f}")
    print(f"Jeu rad. main (µm)         : {res.main_clearance_m*1e6:.1f}")
    print(f"p_main (MPa)               : {res.main_unit_pressure_Pa/1e6:.2f}")
    print(f"PV_main (MW/m²)            : {res.main_PV_W_m2/1e6:.2f}")
    print(f"S_main                     : {res.main_Sommerfeld:.3f}")
    print("--- Tête de bielle ---")
    print(f"D_big-end (mm)             : {res.bigend_D_m*1000:.2f}")
    print(f"L_big-end (mm)             : {res.bigend_L_m*1000:.2f}")
    print(f"Jeu rad. big-end (µm)      : {res.bigend_clearance_m*1e6:.1f}")
    print(f"p_big-end (MPa)            : {res.bigend_unit_pressure_Pa/1e6:.2f}")
    print(f"PV_big-end (MW/m²)         : {res.bigend_PV_W_m2/1e6:.2f}")
    print(f"S_big-end                  : {res.bigend_Sommerfeld:.3f}")
    print("--- Arbre ---")
    print(f"Ø arbre min (mm)           : {res.shaft_min_diameter_m*1000:.2f}")
    print(res.message)
