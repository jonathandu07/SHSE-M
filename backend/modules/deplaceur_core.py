# -*- coding: utf-8 -*-
# backend/modules/deplaceur_core.py
"""
Cœur scalaire — Déplaceur Stirling (indépendant du frontal CLI)

Expose:
- DeplaceurInputs (dataclass)
- DeplaceurResult (dataclass)
- size_deplaceur(inputs) -> DeplaceurResult
"""

from __future__ import annotations
from dataclasses import dataclass
import math

# ----------------------------
# Données d'entrée & résultats
# ----------------------------

@dataclass
class DeplaceurInputs:
    # Géométrie cylindre de référence (le déplaceur DEPEND du cylindre)
    bore_m: float              # Alésage B (m)
    stroke_m: float            # Course S (m)

    # Cinématique / phase
    k_phase: float = 1.00      # Course déplaceur = k_phase * S (≈ 1.0 typique, 0.8–1.2)
    dome_extra_clearance_m: float = 0.02   # marge butée (m) de chaque côté (haut/bas)

    # Jeu & thermique
    radial_clearance_cold_m: float | None = None  # Jeu radial à froid (m); si None, auto
    min_hot_clearance_m: float = 0.08e-3          # Jeu radial minimal à chaud (m)
    alpha_material_1K: float = 12e-6              # α (1/K) matériau déplaceur (ex. inox ~12e-6)
    deltaT_hotK: float = 500.0                    # ΔT max zone chaude vs froid (K)
    manuf_tol_radial_m: float = 0.03e-3           # tolérance usinage / ovalisation (m)

    # Coque du déplaceur (coquille mince)
    shell_thickness_m: float = 0.5e-3             # épaisseur coque (m)
    cap_thickness_m: float = 0.6e-3               # épaisseur fonds supérieur/inférieur (m)
    material_density: float = 8000.0              # kg/m³ (inox typique)
    # Option : matériau allégé pour cœur (nid d’abeille / céramique)
    core_density: float = 50.0                    # kg/m³ (structure légère)
    use_hollow_core: bool = True                  # True: déplaceur creux (coque + cœur léger)

    # Tige de déplaceur
    rod_length_m: float | None = None             # si None => ~ course + marges + sortie
    rod_diameter_m: float = 4e-3                  # Ø tige m
    young_modulus_Pa: float = 200e9               # E acier/inox (Pa)

    # Conditions d'exploitation / checks rapides
    rpm: float = 600.0                            # régime pour vitesse max (tr/min)
    gas_dynamic_dp_Pa: float = 2000.0             # ΔP dynamique estimée agissant sur le déplaceur (Pa)

    # Heuristiques de validation
    acceptable_leak_index: float = 1.5e-4         # seuil heuristique fuite annulaire

@dataclass
class DeplaceurResult:
    ok: bool
    message: str

    # Dimensions principales
    disp_outer_diameter_cold_m: float = 0.0
    disp_outer_diameter_hot_m: float = 0.0
    disp_length_m: float = 0.0
    disp_stroke_m: float = 0.0

    # Jeux
    radial_clearance_cold_m: float = 0.0
    radial_clearance_hot_m: float = 0.0

    # Masses
    mass_shell_kg: float = 0.0
    mass_caps_kg: float = 0.0
    mass_core_kg: float = 0.0
    mass_total_kg: float = 0.0

    # Cinématique
    vmax_m_s: float = 0.0

    # Efforts simplifiés
    axial_force_PaN: float = 0.0
    rod_euler_ok: bool = True
    leak_index: float = 0.0
    leak_ok: bool = True

# ----------------------------
# Utilitaires de calcul
# ----------------------------

def _recommend_cold_clearance(bore_m: float,
                              alpha: float,
                              dT_hot: float,
                              min_hot_clearance_m: float,
                              manuf_tol_m: float) -> float:
    """
    Choisit un jeu radial à froid tel qu'à chaud (Ø augmenté), le jeu reste ≥ min_hot_clearance_m.
    """
    # ΔD_hot = α * D * ΔT  => Δrayon = 0.5*ΔD
    delta_radius_hot = 0.5 * alpha * bore_m * dT_hot
    # On veut : clearance_hot = clearance_cold - delta_radius_hot - tol >= min_hot_clearance
    clearance_cold = min_hot_clearance_m + delta_radius_hot + manuf_tol_m
    # Bornes pratiques (0.08–0.25 mm radial)
    clearance_cold = max(clearance_cold, 0.08e-3)
    clearance_cold = min(clearance_cold, 0.25e-3)
    return clearance_cold

def _thin_shell_displacer_masses(D_o: float, L: float,
                                 t_shell: float, t_caps: float,
                                 rho_shell: float,
                                 use_core: bool, rho_core: float) -> tuple[float, float, float]:
    """
    Masse : coque cylindrique mince + 2 fonds plats minces + cœur léger optionnel.
    """
    D_i = max(D_o - 2.0 * t_shell, 1e-6)
    # Coque
    V_shell = math.pi * D_o * t_shell * L
    m_shell = V_shell * rho_shell
    # Fonds
    A_disc = math.pi * (D_o * 0.5) ** 2
    V_caps = 2.0 * A_disc * t_caps
    m_caps = V_caps * rho_shell
    # Cœur
    if use_core and D_i > 0:
        V_core = math.pi * (0.5 * D_i) ** 2 * L
        m_core = V_core * rho_core
    else:
        m_core = 0.0
    return m_shell, m_caps, m_core

def _max_piston_speed(stroke_m: float, rpm: float) -> float:
    # Mouvement sinus : vmax = ω * (S/2)
    omega = 2.0 * math.pi * (rpm / 60.0)
    return omega * (stroke_m / 2.0)

def _simple_annular_leak_index(bore_m: float, gap_radial_m: float, length_m: float) -> float:
    """
    Indice heuristique de fuite annulaire (sans dimension) :
    ~ (périmètre * gap^3) / longueur caractéristique.
    """
    perimeter = math.pi * bore_m
    return (perimeter * (gap_radial_m ** 3)) / max(length_m, 1e-6)

def _euler_buckling_ok(rod_d: float, rod_L: float, E: float, axial_force: float) -> bool:
    """
    Vérif ultra-simple de flambage Euler en encastrement-libre (π²/4).
    Pcr = π² * E * I / (4 * L²), I = π d⁴ / 64.
    """
    I = math.pi * (rod_d ** 4) / 64.0
    Pcr = (math.pi ** 2) * E * I / (4.0 * (rod_L ** 2))
    return axial_force < 0.3 * Pcr  # marge 70%

# ----------------------------
# Calcul principal
# ----------------------------

def size_deplaceur(inp: DeplaceurInputs) -> DeplaceurResult:
    # 1) Course & longueur utile
    disp_stroke = inp.k_phase * inp.stroke_m
    L = disp_stroke + 2.0 * inp.dome_extra_clearance_m

    # 2) Jeu radial à froid (auto si non fourni)
    if inp.radial_clearance_cold_m is None:
        cr_cold = _recommend_cold_clearance(
            bore_m=inp.bore_m,
            alpha=inp.alpha_material_1K,
            dT_hot=inp.deltaT_hotK,
            min_hot_clearance_m=inp.min_hot_clearance_m,
            manuf_tol_m=inp.manuf_tol_radial_m
        )
    else:
        cr_cold = inp.radial_clearance_cold_m

    # 3) Diamètres & jeu à chaud
    D_cold = max(inp.bore_m - 2.0 * cr_cold, 1e-6)
    deltaD_hot = inp.alpha_material_1K * D_cold * inp.deltaT_hotK  # dilatation Ø déplaceur
    D_hot = D_cold + deltaD_hot
    cr_hot = max(0.5 * (inp.bore_m - D_hot), 0.0)

    if cr_hot < inp.min_hot_clearance_m:
        return DeplaceurResult(
            ok=False,
            message=("Jeu à chaud insuffisant. Augmenter le jeu à froid, réduire ΔT, "
                     "ou choisir matériau/épaisseur différent(s).")
        )

    # 4) Masses
    m_shell, m_caps, m_core = _thin_shell_displacer_masses(
        D_o=D_cold, L=L,
        t_shell=inp.shell_thickness_m, t_caps=inp.cap_thickness_m,
        rho_shell=inp.material_density,
        use_core=inp.use_hollow_core, rho_core=inp.core_density
    )
    m_total = m_shell + m_caps + m_core

    # 5) Vitesse max (sinus)
    # Remarque: on utilise le rpm fourni (du cylindre si calculé en amont)
    vmax = _max_piston_speed(disp_stroke, inp.rpm)

    # 6) Effort axial simplifié dû à ΔP dynamique
    area = math.pi * (D_cold * 0.5) ** 2
    axial_force = area * inp.gas_dynamic_dp_Pa

    # 7) Tige : longueur si None
    if inp.rod_length_m is None:
        rod_L = disp_stroke + 2.0 * inp.dome_extra_clearance_m + 0.03  # +30 mm de sortie/rotule
    else:
        rod_L = inp.rod_length_m

    # 8) Flambage rudimentaire
    rod_ok = _euler_buckling_ok(inp.rod_diameter_m, rod_L, inp.young_modulus_Pa, axial_force)

    # 9) Fuite annulaire — heuristique
    leak_idx = _simple_annular_leak_index(inp.bore_m, cr_hot, L)
    leak_ok = leak_idx <= inp.acceptable_leak_index

    return DeplaceurResult(
        ok=True,
        message="Déplaceur dimensionné (pré-étude). Vérifier le stack chaud/froid réel et le régénérateur.",
        disp_outer_diameter_cold_m=D_cold,
        disp_outer_diameter_hot_m=D_hot,
        disp_length_m=L,
        disp_stroke_m=disp_stroke,
        radial_clearance_cold_m=cr_cold,
        radial_clearance_hot_m=cr_hot,
        mass_shell_kg=m_shell,
        mass_caps_kg=m_caps,
        mass_core_kg=m_core,
        mass_total_kg=m_total,
        vmax_m_s=vmax,
        axial_force_PaN=axial_force,
        rod_euler_ok=rod_ok,
        leak_index=leak_idx,
        leak_ok=leak_ok
    )
