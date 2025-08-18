# -*- coding: utf-8 -*-
# backend/pieces/bielle.py
"""
Bielle — pré-dimensionnement pour moteur Stirling

Hypothèses/portée :
- Longueur de bielle L_b = k_len * (S/2) (k_len ~ 3–4 typique).
- Effort axial max ~ F_peak = p_peak * A_piston (+ optionnel inertie alternative simple).
- Section de tige : profil en I simplifié (âme + 2 semelles) → vérif sigma_axiale, flambage Euler.
- Coussinet de pied (petit bout) et de tête (gros bout) : pression moyenne et PV.
- Vitesse de glissement ~ ω * r pour le maneton (ordre de grandeur).
- Pré-étude : à valider par un calcul dynamique plus fin (inerties, phases, flexion locale, fatigue).

Auteur : ChatGPT (GPT-5 Thinking)
"""

from __future__ import annotations
from dataclasses import dataclass
import math

# ======================
# Entrées / Sorties
# ======================

@dataclass
class RodInputs:
    # Géométrie cylindre / cinématique
    bore_m: float                 # B (m)
    stroke_m: float               # S (m)
    rpm: float                    # régime (tr/min)

    # Charges gaz
    p_mean_cycle_Pa: float = 200e3
    p_peak_gas_Pa: float = 1.2e6

    # Choix longueur
    k_len: float = 3.5            # L_b = k_len * (S/2)

    # Matériau bielle (tige)
    sigma_allow_Pa: float = 350e6 # admissible traction/comp (Pa) (ex. 42CrMo4 QT)
    E_Pa: float = 210e9           # Young (Pa)
    density_kg_m3: float = 7850.0

    # Profil en I (proportions initiales – optimisées à la marge)
    web_thickness_m: float = None     # si None → auto ≈ 0.10 * B
    flange_width_m: float = None      # si None → auto ≈ 0.30 * B
    flange_thickness_m: float = None  # si None → auto ≈ 0.12 * web_thickness

    # Coussinet petit bout (axe/piston)
    pin_diameter_m: float = None      # si None → auto ≈ 0.28 * B
    pin_length_m: float = None        # si None → auto ≈ 0.55 * pin_diameter
    pin_bearing_allow_Pa: float = 45e6   # pression moyenne admissible (AlSn/bronze)
    pin_PV_allow_W_m2: float = 1.6e6     # limite PV (ordre)

    # Coussinet gros bout (maneton)
    crank_pin_diameter_m: float = None   # si None → auto ≈ 0.36 * B
    crank_pin_length_m: float = None     # si None → auto ≈ 0.8 * d_maneton
    big_end_bearing_allow_Pa: float = 60e6
    big_end_PV_allow_W_m2: float = 2.0e6

    # Sécurité / flambage
    slenderness_max: float = 160.0   # L/k <= valeur limite indicative
    euler_safety: float = 0.6        # P_work <= 0.6 * Pcr (marge)

    # Options d'inertie alternative (approx simple)
    add_recip_mass_kg: float = 0.0   # masse alternative prise en compte pour F_inertie
    balance_factor: float = 0.5      # part compensée par équilibrage (0..1)

@dataclass
class RodResult:
    ok: bool
    message: str

    # Géométrie principale
    L_bielle_m: float
    r_crank_m: float

    # Profil en I
    web_t_m: float
    flange_w_m: float
    flange_t_m: float
    area_m2: float
    Ixx_m4: float
    k_radius_m: float     # rayon de giration (pour flambage)

    # Masse tige (sans chape/écrous)
    mass_rod_kg: float

    # Efforts
    A_piston_m2: float
    F_peak_N: float
    F_inertia_peak_N: float
    F_design_N: float     # max (traction/comp) utilisé pour dimensionnement

    # Flambage
    euler_Pcr_N: float
    euler_ok: bool

    # Coussinet petit bout
    pin_d_m: float
    pin_L_m: float
    pin_pressure_Pa: float
    pin_PV_W_m2: float
    pin_ok: bool

    # Coussinet gros bout
    cpin_d_m: float
    cpin_L_m: float
    cpin_pressure_Pa: float
    cpin_PV_W_m2: float
    big_end_ok: bool

# ======================
# Utilitaires
# ======================

def _section_I_profile(t: float, bf: float, tf: float, h: float):
    """
    Profil en I symétrique : âme ép. t, hauteur h, semelles largeur bf et épaisseur tf.
    Retourne (A, Ixx).
    """
    # aire
    A = t * (h - 2*tf) + 2 * (bf * tf)
    # Ixx : âme + 2 semelles (avec théorème de Huygens)
    I_web = (t * (h - 2*tf)**3) / 12.0
    # semelle : inertie propre + déport
    I_flange_self = (bf * tf**3) / 12.0
    y = (h/2 - tf/2)  # distance centre semelle -> axe neutre
    I_flange = 2 * (I_flange_self + bf*tf*(y**2))
    Ixx = I_web + I_flange
    return A, Ixx

def _rpm_to_omega(rpm: float) -> float:
    return 2.0 * math.pi * (rpm / 60.0)

# ======================
# Calcul principal
# ======================

def size_conrod(inp: RodInputs) -> RodResult:
    # 1) Longueur de bielle et géométrie de base
    r = inp.stroke_m / 2.0
    Lb = inp.k_len * r
    h_ref = 0.40 * inp.bore_m                 # hauteur utile du profil en I (ordres de grandeur)
    t_web = inp.web_thickness_m or (0.10 * inp.bore_m)
    t_fl  = inp.flange_thickness_m or (0.12 * t_web)
    b_fl  = inp.flange_width_m or (0.30 * inp.bore_m)

    # 2) Section & inertie du profil en I
    A, Ixx = _section_I_profile(t_web, b_fl, t_fl, h_ref)
    if A <= 0.0 or Ixx <= 0.0:
        raise ValueError("Profil en I invalide (aire/inertie <= 0).")

    k = math.sqrt(Ixx / A)  # rayon de giration

    # 3) Efforts gaz (piston)
    A_p = math.pi * (inp.bore_m**2) / 4.0
    F_peak = inp.p_peak_gas_Pa * A_p  # traction sur bielle quand gaz pousse piston

    # 4) Inertie alternative (option simple)
    omega = _rpm_to_omega(inp.rpm)
    F_inert = (inp.add_recip_mass_kg * (1.0 - inp.balance_factor)) * (r * (omega**2))
    # (F_inertie maxi ~ m * r * ω² ; phase ignorée ici → borne sup)

    # 5) Effort de calcul (max traction/comp)
    F_design = F_peak + F_inert  # côté sûr

    # 6) Vérif contrainte axiale (traction) sur la tige
    sigma_ax = F_design / A
    # Ajuste si > admissible -> agrandir âme (t_web) de façon simple
    if sigma_ax > inp.sigma_allow_Pa:
        # facteur pour revenir dans l'admissible
        scale = sigma_ax / inp.sigma_allow_Pa
        t_web *= math.sqrt(scale)
        # recalc A/I
        A, Ixx = _section_I_profile(t_web, b_fl, t_fl, h_ref)
        k = math.sqrt(Ixx / A)
        sigma_ax = F_design / A  # mis à jour

    # 7) Flambage Euler (pinned–pinned par défaut → K=1)
    K = 1.0
    Pcr = (math.pi**2) * inp.E_Pa * Ixx / ((K * Lb)**2)
    euler_ok = (F_design <= inp.euler_safety * Pcr)

    # 8) Petit bout (pied de bielle, axe de piston)
    pin_d = inp.pin_diameter_m or (0.28 * inp.bore_m)
    pin_L = inp.pin_length_m or (0.55 * pin_d)
    A_bearing_pin = pin_d * pin_L
    p_pin = F_design / max(A_bearing_pin, 1e-12)
    v_pin = omega * r  # ordre de grandeur
    PV_pin = p_pin * v_pin
    pin_ok = (p_pin <= inp.pin_bearing_allow_Pa) and (PV_pin <= inp.pin_PV_allow_W_m2)

    # 9) Gros bout (maneton vilebrequin)
    cpin_d = inp.crank_pin_diameter_m or (0.36 * inp.bore_m)
    cpin_L = inp.crank_pin_length_m or (0.80 * cpin_d)
    A_bearing_be = cpin_d * cpin_L
    p_be = F_design / max(A_bearing_be, 1e-12)
    v_be = omega * r
    PV_be = p_be * v_be
    big_end_ok = (p_be <= inp.big_end_bearing_allow_Pa) and (PV_be <= inp.big_end_PV_allow_W_m2)

    # 10) Masse tige (approx 2D * épaisseur moyenne)
    # Volume ~ A_moyen * Lb ; A_moyen ≈ A (profil constant)
    mass = inp.density_kg_m3 * (A * Lb)

    # 11) Slenderness check
    slenderness = (Lb / max(k, 1e-9))
    if slenderness > inp.slenderness_max:
        # avertissement implicite via message
        euler_ok = False

    ok = (sigma_ax <= inp.sigma_allow_Pa) and euler_ok and pin_ok and big_end_ok
    reasons = []
    if sigma_ax > inp.sigma_allow_Pa: reasons.append("sigma_ax")
    if not euler_ok: reasons.append("flambage")
    if not pin_ok: reasons.append("pied_bielle")
    if not big_end_ok: reasons.append("gros_bout")

    msg = "OK" if ok else (" / ".join(reasons) if reasons else "Non conforme")

    return RodResult(
        ok=ok, message=msg,
        L_bielle_m=Lb, r_crank_m=r,
        web_t_m=t_web, flange_w_m=b_fl, flange_t_m=t_fl,
        area_m2=A, Ixx_m4=Ixx, k_radius_m=k,
        mass_rod_kg=mass,
        A_piston_m2=A_p, F_peak_N=F_peak, F_inertia_peak_N=F_inert, F_design_N=F_design,
        euler_Pcr_N=Pcr, euler_ok=euler_ok,
        pin_d_m=pin_d, pin_L_m=pin_L, pin_pressure_Pa=p_pin, pin_PV_W_m2=PV_pin, pin_ok=pin_ok,
        cpin_d_m=cpin_d, cpin_L_m=cpin_L, cpin_pressure_Pa=p_be, cpin_PV_W_m2=PV_be, big_end_ok=big_end_ok
    )

# ======================
# Démo
# ======================

if __name__ == "__main__":
    # Exemple : B=80 mm, S=80 mm, 900 rpm, p_mean=200 kPa, p_peak=1.2 MPa
    inp = RodInputs(
        bore_m=0.080, stroke_m=0.080, rpm=900.0,
        p_mean_cycle_Pa=200e3, p_peak_gas_Pa=1.2e6,
        k_len=3.6,
        add_recip_mass_kg=0.25, balance_factor=0.5,
        sigma_allow_Pa=450e6,  # acier allié traité
    )
    res = size_conrod(inp)

    print("=== BIELLE ===")
    print(f"L_bielle (mm)        : {res.L_bielle_m*1000:.1f}  | r=S/2 (mm): {res.r_crank_m*1000:.1f}")
    print(f"Section A (mm²)      : {res.area_m2*1e6:.1f}  | Ixx (cm⁴): {res.Ixx_m4*1e8:.2f}")
    print(f"k (mm)               : {res.k_radius_m*1000:.2f}  | L/k : {res.L_bielle_m/res.k_radius_m:.1f}")
    print(f"σ_ax (MPa) (calc)    : {(res.F_design_N/res.area_m2)/1e6:.1f}  | σ_allow (MPa)≈ {inp.sigma_allow_Pa/1e6:.0f}")
    print(f"Pcr Euler (kN)       : {res.euler_Pcr_N/1e3:.1f}   | OK flambage ? {'Oui' if res.euler_ok else 'Non'}")
    print(f"Petit bout d (mm)    : {res.pin_d_m*1000:.1f}, L (mm): {res.pin_L_m*1000:.1f} | p (MPa): {res.pin_pressure_Pa/1e6:.1f} | PV (MW/m²): {res.pin_PV_W_m2/1e6:.2f} | OK? {'Oui' if res.pin_ok else 'Non'}")
    print(f"Gros bout d (mm)     : {res.cpin_d_m*1000:.1f}, L (mm): {res.cpin_L_m*1000:.1f} | p (MPa): {res.cpin_pressure_Pa/1e6:.1f} | PV (MW/m²): {res.cpin_PV_W_m2/1e6:.2f} | OK? {'Oui' if res.big_end_ok else 'Non'}")
    print(f"Masse tige (g)       : {res.mass_rod_kg*1e3:.1f}")
    print(res.message)
