# backend/pieces/deplaceur.py
# -*- coding: utf-8 -*-
"""
Définition et pré-dimensionnement d’un déplaceur pour moteur Stirling.

Résumé pratique :
- Ø déplaceur ≈ B - 2*jeu_radial à froid.
- La course du déplaceur est souvent proche de S (selon angle de phase), on garde un facteur k_phase.
- On vérifie que, à chaud, l’expansion thermique ne ferme pas le jeu.
- Estimation de masse (coque mince + deux fonds), inertie de translation, vitesse max.
- Sanity checks : fuite annulaire (heuristique), flambage simple de la tige, effort ΔP.

NB : Ce module vise le **pré-dimensionnement**. Pour le dessin final, il faudra préciser :
  - Matériau (ρ, E, α, limite), épaisseur réelle, perçages, fond bombé/plat, fixation tige.
  - Les zones chaude/froide, longueurs d’échangeurs et régénérateur (influant la longueur utile).
"""

from dataclasses import dataclass
import math

# ----------------------------
# Données d'entrée & résultats
# ----------------------------

@dataclass
class DeplaceurInputs:
    # Géométrie cylindre de référence
    bore_m: float              # Alésage B (m)
    stroke_m: float            # Course S (m)

    # Cinématique / phase
    k_phase: float = 1.00      # Course déplaceur = k_phase * S (≈ 1.0 typique, 0.8–1.2)
    dome_extra_clearance_m: float = 0.02   # marge butée (m) de chaque côté (haut/bas)

    # Jeu & thermique
    radial_clearance_cold_m: float = None  # Jeu radial à froid (m); si None, auto
    min_hot_clearance_m: float = 0.08e-3   # Jeu radial minimal à chaud (m)
    alpha_material_1K: float = 12e-6       # α (1/K) matériau déplaceur (ex. inox ~12e-6)
    deltaT_hotK: float = 500.0             # ΔT max zone chaude vs froid (K)
    manuf_tol_radial_m: float = 0.03e-3    # tolérance usinage / ovalisation (m)

    # Coque du déplaceur (coquille mince)
    shell_thickness_m: float = 0.5e-3      # épaisseur coque (m) — à ajuster selon Ø et matériau
    cap_thickness_m: float = 0.6e-3        # épaisseur fonds supérieur/inférieur (m)
    material_density: float = 8000.0       # kg/m³ (inox typique)
    # Option : matériau allégé pour cœur (nid d’abeille / céramique)
    core_density: float = 50.0             # kg/m³ (structure très légère, si utilisée)
    use_hollow_core: bool = True           # True: déplaceur creux (coque + cœur léger)

    # Tige de déplaceur
    rod_length_m: float = None             # si None => ~ course + marges + sortie
    rod_diameter_m: float = 4e-3           # Ø tige m (à affiner selon effort/flambage)
    young_modulus_Pa: float = 200e9        # E acier/inox (Pa)

    # Explotation / checks rapides
    rpm: float = 600.0                     # régime pour vitesse max (tr/min)
    gas_dynamic_dp_Pa: float = 2000.0      # ΔP dynamique estimée agissant sur le déplaceur (Pa)
    max_allowable_slenderness: float = 200 # rapport élancement L/i (indicatif flambage)
    # Heuristique fuite annulaire
    acceptable_leak_index: float = 1.5e-4  # seuil heuristique (sans unité)

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

def recommend_cold_clearance(bore_m: float,
                             alpha: float,
                             dT_hot: float,
                             min_hot_clearance_m: float,
                             manuf_tol_m: float) -> float:
    """
    Choisit un jeu radial à froid tel qu'à chaud (Ø augmenté), le jeu reste ≥ min_hot_clearance_m.
    On ajoute une marge de fabrication.
    """
    # ΔD_hot = α * D * ΔT  => Δrayon = 0.5*ΔD
    delta_radius_hot = 0.5 * alpha * bore_m * dT_hot
    # On veut : clearance_hot = clearance_cold - delta_radius_hot - tol >= min_hot_clearance
    clearance_cold = min_hot_clearance_m + delta_radius_hot + manuf_tol_m
    # Bornes pratiques (0.08–0.25 mm radial selon Ø et matériaux)
    clearance_cold = max(clearance_cold, 0.08e-3)
    clearance_cold = min(clearance_cold, 0.25e-3)
    return clearance_cold

def thin_shell_displacer_masses(D_o: float, L: float,
                                t_shell: float, t_caps: float,
                                rho_shell: float,
                                use_core: bool, rho_core: float) -> tuple[float, float, float]:
    """
    Estime la masse : coque cylindrique mince + 2 fonds plats minces + cœur léger optionnel.
    - Coque : V ≈ (π * D_o * t_shell) * L
    - Fonds : 2 * (π * (D_o/2)^2 * t_caps)
    - Cœur : V ≈ π * (D_i/2)^2 * L (si utilisé)
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

def max_piston_speed(stroke_m: float, rpm: float) -> float:
    # Vitesse moyenne *π/2 pour sinus ? On donne la vmax sinus = ω * (S/2)
    # S mouvement crête-à-crête => amplitude = S/2
    omega = 2.0 * math.pi * (rpm / 60.0)
    vmax = omega * (stroke_m / 2.0)
    return vmax

def simple_annular_leak_index(bore_m: float, gap_radial_m: float, length_m: float) -> float:
    """
    Indice heuristique de fuite annulaire (sans dimension) :
    ~ (périmètre * gap^3) / longueur caractéristique.
    Plus c’est grand, plus la fuite potentielle est forte.
    Sert juste à comparer des options (pas une CFD !).
    """
    perimeter = math.pi * bore_m
    return (perimeter * (gap_radial_m ** 3)) / max(length_m, 1e-6)

def euler_buckling_ok(rod_d: float, rod_L: float, E: float, axial_force: float) -> bool:
    """
    Vérif ultra-simple de flambage Euler en encastrement-libre (coefficient π^2/4).
    Charge critique Pcr = π^2 * E * I / (4 * L^2), I = π d^4 / 64.
    """
    I = math.pi * (rod_d ** 4) / 64.0
    Pcr = (math.pi ** 2) * E * I / (4.0 * (rod_L ** 2))
    return axial_force < 0.3 * Pcr  # marge 70% (indicatif)

# ----------------------------
# Calcul principal
# ----------------------------

def size_deplaceur(inp: DeplaceurInputs) -> DeplaceurResult:
    # 1) Course du déplaceur
    disp_stroke = inp.k_phase * inp.stroke_m

    # 2) Longueur utile du déplaceur (doit couvrir la zone d’échange chaud/froid).
    #    On prend : L = S + 2* marge_butée (enveloppe) — tu ajusteras selon ton stack échangeurs.
    L = disp_stroke + 2.0 * inp.dome_extra_clearance_m

    # 3) Jeu radial à froid (auto si non fourni)
    if inp.radial_clearance_cold_m is None:
        cr_cold = recommend_cold_clearance(
            bore_m=inp.bore_m,
            alpha=inp.alpha_material_1K,
            dT_hot=inp.deltaT_hotK,
            min_hot_clearance_m=inp.min_hot_clearance_m,
            manuf_tol_m=inp.manuf_tol_radial_m
        )
    else:
        cr_cold = inp.radial_clearance_cold_m

    # 4) Diamètres
    D_cold = max(inp.bore_m - 2.0 * cr_cold, 1e-6)
    # Dilatation Ø à chaud (approx sur Ø déplaceur)
    deltaD_hot = inp.alpha_material_1K * D_cold * inp.deltaT_hotK
    D_hot = D_cold + deltaD_hot
    # Jeu à chaud (radial)
    cr_hot = max(0.5 * (inp.bore_m - D_hot), 0.0)

    # 5) Vérif jeu à chaud
    if cr_hot < inp.min_hot_clearance_m:
        return DeplaceurResult(
            ok=False,
            message=("Jeu à chaud insuffisant. Augmenter le jeu à froid, réduire ΔT, "
                     "ou changer matériau (α plus faible) / épaisseur.")
        )

    # 6) Masses
    m_shell, m_caps, m_core = thin_shell_displacer_masses(
        D_o=D_cold,
        L=L,
        t_shell=inp.shell_thickness_m,
        t_caps=inp.cap_thickness_m,
        rho_shell=inp.material_density,
        use_core=inp.use_hollow_core,
        rho_core=inp.core_density
    )
    m_total = m_shell + m_caps + m_core

    # 7) Vitesse max (sinusoïdal)
    vmax = max_piston_speed(disp_stroke, inp.rpm)

    # 8) Effort axial simplifié dû à ΔP dynamique (ordre de grandeur)
    area = math.pi * (D_cold * 0.5) ** 2
    axial_force = area * inp.gas_dynamic_dp_Pa

    # 9) Tige : longueur si None
    if inp.rod_length_m is None:
        rod_L = disp_stroke + 2.0 * inp.dome_extra_clearance_m + 0.03  # +30 mm de sortie/rotule
    else:
        rod_L = inp.rod_length_m

    # 10) Flambage rudimentaire
    rod_ok = euler_buckling_ok(inp.rod_diameter_m, rod_L, inp.young_modulus_Pa, axial_force)

    # 11) Fuite annulaire — heuristique
    leak_idx = simple_annular_leak_index(inp.bore_m, cr_hot, L)
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

# ----------------------------
# Exemple d'utilisation
# ----------------------------
if __name__ == "__main__":
    # Exemple : alésage 80 mm, course 80 mm, régime 600 rpm, ΔT ~ 500 K
    inp = DeplaceurInputs(
        bore_m=0.080,
        stroke_m=0.080,
        k_phase=1.0,
        dome_extra_clearance_m=0.010,  # 10 mm de marge haut/bas
        radial_clearance_cold_m=None,  # auto en fonction de ΔT et α
        min_hot_clearance_m=0.08e-3,
        alpha_material_1K=12e-6,
        deltaT_hotK=500.0,
        manuf_tol_radial_m=0.03e-3,
        shell_thickness_m=0.40e-3,
        cap_thickness_m=0.50e-3,
        material_density=7900.0,
        core_density=60.0,
        use_hollow_core=True,
        rod_length_m=None,
        rod_diameter_m=4e-3,
        young_modulus_Pa=190e9,
        rpm=600.0,
        gas_dynamic_dp_Pa=2000.0,
        max_allowable_slenderness=200,
        acceptable_leak_index=1.5e-4
    )
    res = size_deplaceur(inp)

    print("=== DÉPLACEUR ===")
    if res.ok:
        print(f"Ø froid (ext.)         : {res.disp_outer_diameter_cold_m*1000:.2f} mm")
        print(f"Ø chaud (ext. estimé)  : {res.disp_outer_diameter_hot_m*1000:.2f} mm")
        print(f"Jeu radial à froid     : {res.radial_clearance_cold_m*1e3:.3f} mm")
        print(f"Jeu radial à chaud     : {res.radial_clearance_hot_m*1e3:.3f} mm (≥ min?)")
        print(f"Longueur utile L       : {res.disp_length_m*1000:.1f} mm")
        print(f"Course déplaceur       : {res.disp_stroke_m*1000:.1f} mm")
        print(f"Masse coque            : {res.mass_shell_kg*1e3:.1f} g")
        print(f"Masse fonds            : {res.mass_caps_kg*1e3:.1f} g")
        print(f"Masse cœur             : {res.mass_core_kg*1e3:.1f} g")
        print(f"Masse totale           : {res.mass_total_kg*1e3:.1f} g")
        print(f"Vitesse max (rpm={inp.rpm:.0f}) : {res.vmax_m_s:.2f} m/s")
        print(f"Effort axial (ΔP~)     : {res.axial_force_PaN:.1f} N")
        print(f"Tige : flambage OK ?   : {'Oui' if res.rod_euler_ok else 'Non'}")
        print(f"Indice fuite heur.     : {res.leak_index:.3e} (ok? {'Oui' if res.leak_ok else 'Non'})")
        print(res.message)
    else:
        print("ÉCHEC :", res.message)
