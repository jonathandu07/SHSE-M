# -*- coding: utf-8 -*-
# backend/pieces/piston.py
"""
Pré-dimensionnement d'un piston de moteur Stirling (partie puissance)
- Ø piston ≈ B (moins jeu), surface A = π B²/4 → force gaz F ≈ p·A
- Segments/joints : nombre et dimensions sur base de B et p
- Axe (goujon) : diamètre et portée par vérifs cisaillement & pression de contact
- Contrôles : vitesse piston, effort inertie (si masse connue), poussée latérale (approx)

Ce module vise le pré-dimensionnement. Pour un dessin final :
- préciser matériaux, traitements, tolérances, état de surface, lubrification,
- vérifier la tenue thermo-mécanique (dilatations, gradients, flambage jupe), et
- intégrer la cinématique exacte (phase, L_bielle, jeux à l’axe).
"""

from __future__ import annotations
from dataclasses import dataclass
import math

# ----------------------------
# Entrées / Sorties
# ----------------------------

@dataclass
class PistonInputs:
    # Géométrie principale
    bore_m: float                 # Alésage cylindre B (m)
    stroke_m: float               # Course S (m)

    # Cinématique / usage
    rpm: float = 600.0            # régime (tr/min)
    conrod_ratio: float = 3.5     # L_bielle / S (3.0–4.0 typ.)
    mean_piston_clearance_radial_m: float = 0.02e-3  # jeu radial moyen à froid (m)

    # Pressions (estimations)
    p_mean_cycle_Pa: float = 200e3    # pression effective moyenne (Pa) ~ BMEP
    p_peak_gas_Pa: float = 1.2e6      # pic de pression gaz (Pa) (ajuste selon design)

    # Segments (heuristiques par défaut)
    n_rings: int = 2
    ring_axial_height_frac: float = 0.04   # h_axial ≈ 0.04*B
    ring_radial_thickness_frac: float = 0.05  # t_radial ≈ 0.05*B
    ring_tension_N_per_mm_circ: float = 0.02  # tension radiale ~ N/mm de circonférence (ordre de grandeur)
    ring_friction_mu: float = 0.12          # coefficient friction segments (lubrifié)

    # Axe de piston (goujon)
    pin_material_tau_allow_Pa: float = 180e6  # contrainte de cisaillement admissible (Pa)
    pin_bearing_p_allow_Pa: float = 60e6      # pression de contact bossage/axe admissible (Pa)
    pin_wall_clearance_m: float = 0.01e-3     # jeu fonctionnel (m)
    boss_wall_thickness_frac: float = 0.20    # épaisseur mini bossage ≈ 0.2*D_pin

    # Masses (optionnel pour inertie)
    mass_recip_kg: float | None = None        # masse alternative (piston+axe+segments) pour F_inertie
    # Si None, on peut estimer grossièrement ~ densité alu * volume disque mince (optionnel) — laissé à False par défaut
    estimate_mass: bool = False
    piston_crown_thickness_m: float = 6e-3    # si estimate_mass=True, épaisseur calotte
    piston_density: float = 2700.0            # kg/m³ (alu)

    # Jupe / poussée latérale
    skirt_length_m: float | None = None       # si None ⇒ heuristique ~ 0.4*B
    skirt_bearing_p_allow_Pa: float = 8e6     # pression portante admissible jupe (Pa)
    skirt_friction_mu: float = 0.08           # friction jupe

@dataclass
class PistonResult:
    ok: bool
    message: str

    # Géométrie & surface
    piston_diameter_cold_m: float = 0.0
    piston_area_m2: float = 0.0

    # Forces gaz
    F_mean_N: float = 0.0
    F_peak_N: float = 0.0

    # Segments
    ring_count: int = 0
    ring_axial_height_m: float = 0.0
    ring_radial_thickness_m: float = 0.0
    ring_circumference_m: float = 0.0
    ring_total_friction_N: float = 0.0

    # Axe (goujon)
    pin_diameter_m: float = 0.0
    pin_half_bearing_length_m: float = 0.0  # longueur de portée par bossage (chaque côté)
    pin_shear_utilization: float = 0.0      # F / F_admissible
    pin_bearing_utilization: float = 0.0    # p_contact / p_allow
    boss_wall_thickness_m: float = 0.0

    # Cinématique & inerties
    mean_piston_speed_m_s: float = 0.0
    F_inertia_peak_N: float = 0.0

    # Poussée latérale & jupe
    side_thrust_peak_N: float = 0.0
    skirt_bearing_pressure_Pa: float = 0.0
    skirt_ok: bool = True

# ----------------------------
# Outils de calcul
# ----------------------------

def mean_piston_speed(stroke_m: float, rpm: float) -> float:
    # Upiston = 2*S*RPM/60
    return 2.0 * stroke_m * rpm / 60.0

def peak_inertia_force(m_recip: float, stroke_m: float, rpm: float) -> float:
    # F_inertie_max ≈ m * r * ω^2, avec r = S/2
    omega = 2.0 * math.pi * (rpm / 60.0)
    r = 0.5 * stroke_m
    return m_recip * r * (omega ** 2)

def side_thrust_peak(F_gas_peak: float, conrod_ratio: float) -> float:
    """
    Poussée latérale max ~ F_gas_peak * tan(theta_max) avec sin(theta_max) ≈ r/L = (S/2)/(conrod_ratio*S) = 1/(2*conrod_ratio).
    Donc tan(theta_max) ≈ sin / sqrt(1 - sin^2)
    """
    s = 1.0 / (2.0 * conrod_ratio)
    s = max(1e-6, min(0.25, s))  # borne raisonnable
    tan_theta = s / math.sqrt(1.0 - s*s)
    return F_gas_peak * tan_theta

def _ring_dimensions(bore_m: float, h_frac: float, t_frac: float):
    h_axial = h_frac * bore_m
    t_radial = t_frac * bore_m
    return h_axial, t_radial

def _ring_circumference(bore_m: float) -> float:
    return math.pi * bore_m

def _ring_friction(n_rings: int, circumference_m: float, tension_N_per_mm_circ: float, mu: float) -> float:
    """
    Force friction segments ≈ μ * (N_normal segments)
    N_normal ≈ n_rings * tension_par_longueur * longueur
    tension param en N/mm => convertir en N/m
    """
    N_per_m = tension_N_per_mm_circ * 1000.0
    N_normal = n_rings * N_per_m * circumference_m
    return mu * N_normal

def size_piston(inp: PistonInputs) -> PistonResult:
    # 1) Ø piston à froid
    D_piston = max(inp.bore_m - 2.0 * inp.mean_piston_clearance_radial_m, 1e-6)
    A = math.pi * (inp.bore_m ** 2) / 4.0

    # 2) Forces gaz
    F_mean = inp.p_mean_cycle_Pa * A
    F_peak = inp.p_peak_gas_Pa * A

    # 3) Segments
    ring_h, ring_t = _ring_dimensions(inp.bore_m, inp.ring_axial_height_frac, inp.ring_radial_thickness_frac)
    ring_circ = _ring_circumference(inp.bore_m)
    ring_fric = _ring_friction(inp.n_rings, ring_circ, inp.ring_tension_N_per_mm_circ, inp.ring_friction_mu)

    # 4) Axe (goujon) — dimensionnement par cisaillement double & pression de contact
    # cisaillement admissible : tau_allow, aire cisaillement = 2 * (π d^2 / 4)
    # => d >= sqrt( F_peak / (0.5 π tau_allow) )
    d_pin_shear = math.sqrt(max(F_peak, 1e-9) / (0.5 * math.pi * max(inp.pin_material_tau_allow_Pa, 1.0)))
    # pression de contact bossage/axe : p = F / (2 * d * L)  => L >= F / (2 d p_allow)
    # (L = longueur de portée par bossage ; on dimensionne pour le pic)
    # on prend d_pin = max(d_shear, d_bearing_min) où d_bearing_min dépendra de L choisi ;
    # stratégie: prendre d_pin = d_pin_shear initialement, calculer L requis, puis corriger bossage/jeu.
    d_pin = max(d_pin_shear, 0.004)  # borne mini pratique (4 mm)
    L_half = F_peak / (2.0 * d_pin * max(inp.pin_bearing_p_allow_Pa, 1.0))  # m
    # épaisseur paroi bossage indicative
    boss_wall = inp.boss_wall_thickness_frac * d_pin

    # 5) Cinématique & inerties
    Up = mean_piston_speed(inp.stroke_m, inp.rpm)

    if inp.mass_recip_kg is not None:
        m_rec = inp.mass_recip_kg
    elif inp.estimate_mass:
        # estimation très grossière : disque (Ø D_piston, épaisseur crown) + jupe (cylindre mince ~10% de crown)
        vol_crown = A * inp.piston_crown_thickness_m
        vol_skirt = (math.pi * D_piston * 0.0015) * (0.4 * inp.bore_m)  # jupe t~1.5mm, L~0.4B
        m_rec = inp.piston_density * (vol_crown + vol_skirt)
    else:
        m_rec = 0.0

    F_inertia = peak_inertia_force(m_rec, inp.stroke_m, inp.rpm) if m_rec > 0 else 0.0

    # 6) Poussée latérale & jupe
    F_side = side_thrust_peak(F_peak, inp.conrod_ratio)
    skirt_L = (0.4 * inp.bore_m) if inp.skirt_length_m is None else inp.skirt_length_m
    # surface portante approximative jupe (projetée) ~ π * D * L * (1/π) ≈ D * L * (facteur ~ 1 pour ordre de grandeur)
    # on reste conservatif: A_portée ≈ 0.5 * D * L
    bearing_area = 0.5 * D_piston * max(skirt_L, 1e-6)
    p_skirt = F_side / max(bearing_area, 1e-9)
    skirt_ok = p_skirt <= inp.skirt_bearing_p_allow_Pa

    # 7) Vérifs axe : taux d’utilisation (cisaillement & contact)
    A_shear = 0.5 * math.pi * (d_pin ** 2)
    shear_util = F_peak / max(A_shear * inp.pin_material_tau_allow_Pa, 1.0)
    p_contact = F_peak / max(2.0 * d_pin * L_half, 1e-9)
    bearing_util = p_contact / max(inp.pin_bearing_p_allow_Pa, 1.0)

    return PistonResult(
        ok=True,
        message="Piston pré-dimensionné (ordre de grandeur). Ajuster matériaux, tolérances et détails CAO.",
        piston_diameter_cold_m=D_piston,
        piston_area_m2=A,
        F_mean_N=F_mean,
        F_peak_N=F_peak,
        ring_count=inp.n_rings,
        ring_axial_height_m=ring_h,
        ring_radial_thickness_m=ring_t,
        ring_circumference_m=ring_circ,
        ring_total_friction_N=ring_fric,
        pin_diameter_m=d_pin,
        pin_half_bearing_length_m=L_half,
        pin_shear_utilization=shear_util,
        pin_bearing_utilization=bearing_util,
        boss_wall_thickness_m=boss_wall,
        mean_piston_speed_m_s=Up,
        F_inertia_peak_N=F_inertia,
        side_thrust_peak_N=F_side,
        skirt_bearing_pressure_Pa=p_skirt,
        skirt_ok=skirt_ok,
    )

# ----------------------------
# Démo / utilisation directe
# ----------------------------

if __name__ == "__main__":
    # Exemple : B = 80 mm, S = 80 mm, 600 tr/min, BMEP 200 kPa, pic 1.2 MPa
    inp = PistonInputs(
        bore_m=0.080,
        stroke_m=0.080,
        rpm=600.0,
        p_mean_cycle_Pa=200e3,
        p_peak_gas_Pa=1.2e6,
        n_rings=2,
        ring_friction_mu=0.12,
        mass_recip_kg=0.35,     # si connu; sinon mettre None et estimate_mass=True pour une estimation grossière
        estimate_mass=False,
    )
    res = size_piston(inp)

    print("=== PISTON ===")
    print(f"Ø piston (froid)       : {res.piston_diameter_cold_m*1000:.2f} mm")
    print(f"Surface A               : {res.piston_area_m2*1e4:.2f} cm²")
    print(f"F_gaz moyenne           : {res.F_mean_N:.1f} N")
    print(f"F_gaz pic               : {res.F_peak_N:.1f} N")
    print(f"Segments : nb           : {res.ring_count}")
    print(f"  - h_axial             : {res.ring_axial_height_m*1000:.2f} mm")
    print(f"  - t_radial            : {res.ring_radial_thickness_m*1000:.2f} mm")
    print(f"  - circonférence       : {res.ring_circumference_m*1000:.2f} mm")
    print(f"  - F_friction (est.)   : {res.ring_total_friction_N:.1f} N")
    print(f"Axe (goujon) :")
    print(f"  - Ø pin               : {res.pin_diameter_m*1000:.2f} mm")
    print(f"  - L portée/côté       : {res.pin_half_bearing_length_m*1000:.2f} mm")
    print(f"  - Util. cisaillement  : {res.pin_shear_utilization*100:.1f} %")
    print(f"  - Util. contact       : {res.pin_bearing_utilization*100:.1f} %")
    print(f"  - Ép. paroi bossage   : {res.boss_wall_thickness_m*1000:.2f} mm")
    print(f"Cinématique :")
    print(f"  - Upiston moy.        : {res.mean_piston_speed_m_s:.3f} m/s")
    print(f"  - F_inertie (si m)    : {res.F_inertia_peak_N:.1f} N")
    print(f"Poussée latérale :")
    print(f"  - F_side (pic)        : {res.side_thrust_peak_N:.1f} N")
    print(f"  - p_jupe              : {res.skirt_bearing_pressure_Pa/1e6:.2f} MPa (OK? {'Oui' if res.skirt_ok else 'Non'})")
    print(res.message)
