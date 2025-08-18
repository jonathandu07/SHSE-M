# -*- coding: utf-8 -*-
# backend/modules/deplaceur_vector.py
"""
Couche NumPy vectorisée — Déplaceur Stirling

message_id:
  0 = OK
  1 = Jeu à chaud insuffisant
  2 = Flambage tige (Euler)
  3 = Fuite annulaire (indice > seuil)
"""

from __future__ import annotations
import numpy as np

def _ensure_array(x):
    if isinstance(x, np.ndarray):
        return x
    return np.asarray(x)

def _broadcast(*arrs):
    return np.broadcast_arrays(*[ _ensure_array(a) for a in arrs ])

def _recommend_cold_clearance(bore_m, alpha, dT_hot, min_hot_clearance_m, manuf_tol_m):
    # Δrayon_chaud = 0.5 * α * D * ΔT
    delta_radius_hot = 0.5 * alpha * bore_m * dT_hot
    clearance_cold = min_hot_clearance_m + delta_radius_hot + manuf_tol_m
    clearance_cold = np.maximum(clearance_cold, 0.08e-3)
    clearance_cold = np.minimum(clearance_cold, 0.25e-3)
    return clearance_cold

def size_deplaceur_vector(
    bore_m, stroke_m,
    k_phase=1.0, dome_extra_clearance_m=0.02,
    radial_clearance_cold_m=None,
    min_hot_clearance_m=0.08e-3,
    alpha_material_1K=12e-6, deltaT_hotK=500.0, manuf_tol_radial_m=0.03e-3,
    shell_thickness_m=0.5e-3, cap_thickness_m=0.6e-3, material_density=8000.0,
    use_hollow_core=True, core_density=50.0,
    rod_length_m=None, rod_diameter_m=4e-3, young_modulus_Pa=200e9,
    rpm=600.0, gas_dynamic_dp_Pa=2000.0,
    acceptable_leak_index=1.5e-4
) -> dict[str, np.ndarray]:

    # ---- Broadcast de toutes les entrées utiles ----
    (bore_m, stroke_m, k_phase, dome_extra_clearance_m,
     min_hot_clearance_m, alpha_material_1K, deltaT_hotK, manuf_tol_radial_m,
     shell_thickness_m, cap_thickness_m, material_density, core_density,
     use_hollow_core, rod_diameter_m, young_modulus_Pa, rpm,
     gas_dynamic_dp_Pa, acceptable_leak_index) = _broadcast(
        bore_m, stroke_m, k_phase, dome_extra_clearance_m,
        min_hot_clearance_m, alpha_material_1K, deltaT_hotK, manuf_tol_radial_m,
        shell_thickness_m, cap_thickness_m, material_density, core_density,
        use_hollow_core, rod_diameter_m, young_modulus_Pa, rpm,
        gas_dynamic_dp_Pa, acceptable_leak_index
    )

    # radial_clearance_cold_m et rod_length_m peuvent être None -> auto
    if radial_clearance_cold_m is None:
        cr_cold = _recommend_cold_clearance(bore_m, alpha_material_1K, deltaT_hotK,
                                            min_hot_clearance_m, manuf_tol_radial_m)
    else:
        cr_cold, = _broadcast(radial_clearance_cold_m)

    # ---- Géométrie principale ----
    disp_stroke = k_phase * stroke_m
    L = disp_stroke + 2.0 * dome_extra_clearance_m

    D_cold = np.maximum(bore_m - 2.0 * cr_cold, 1e-9)
    deltaD_hot = alpha_material_1K * D_cold * deltaT_hotK
    D_hot = D_cold + deltaD_hot
    cr_hot = np.maximum(0.5 * (bore_m - D_hot), 0.0)

    # ---- Vérif jeu à chaud ----
    ok_hot = cr_hot >= min_hot_clearance_m

    # ---- Masses (coque + 2 fonds + cœur optionnel) ----
    # Coque: V = π * D_o * t * L
    V_shell = np.pi * D_cold * shell_thickness_m * L
    m_shell = V_shell * material_density
    # Fonds: 2 * (π (D/2)^2 t)
    A_disc = np.pi * (0.5 * D_cold) ** 2
    V_caps = 2.0 * A_disc * cap_thickness_m
    m_caps = V_caps * material_density
    # Cœur
    D_i = np.maximum(D_cold - 2.0 * shell_thickness_m, 0.0)
    V_core = np.pi * (0.5 * D_i) ** 2 * L
    use_core_mask = (use_hollow_core.astype(bool)) & (D_i > 0)
    m_core = np.where(use_core_mask, V_core * core_density, 0.0)
    m_total = m_shell + m_caps + m_core

    # ---- Vitesse max (sinus) ----
    omega = 2.0 * np.pi * (rpm / 60.0)
    vmax = omega * (disp_stroke / 2.0)

    # ---- Effort axial ΔP ----
    area = np.pi * (0.5 * D_cold) ** 2
    axial_force = area * gas_dynamic_dp_Pa

    # ---- Longueur de tige ----
    if rod_length_m is None:
        rod_L = disp_stroke + 2.0 * dome_extra_clearance_m + 0.03
    else:
        rod_L, = _broadcast(rod_length_m)

    # ---- Flambage Euler (encastrement-libre ~ π²/4) ----
    I = np.pi * (rod_diameter_m ** 4) / 64.0
    Pcr = (np.pi ** 2) * young_modulus_Pa * I / (4.0 * (rod_L ** 2))
    rod_ok = axial_force < 0.3 * Pcr  # marge

    # ---- Fuite annulaire (indice heuristique) ----
    perimeter = np.pi * bore_m
    leak_index = (perimeter * (cr_hot ** 3)) / np.maximum(L, 1e-9)
    leak_ok = leak_index <= acceptable_leak_index

    # ---- Agrégation des verdicts ----
    ok = ok_hot & rod_ok & leak_ok
    msg = np.full(ok.shape, 0, dtype=np.int8)
    msg[~ok_hot] = 1
    msg[ ok_hot & (~rod_ok)] = 2
    msg[ ok_hot & rod_ok & (~leak_ok)] = 3

    return {
        "ok": ok,
        "message_id": msg,
        "disp_outer_diameter_cold_m": D_cold,
        "disp_outer_diameter_hot_m": D_hot,
        "disp_length_m": L,
        "disp_stroke_m": disp_stroke,
        "radial_clearance_cold_m": cr_cold,
        "radial_clearance_hot_m": cr_hot,
        "mass_shell_kg": m_shell,
        "mass_caps_kg": m_caps,
        "mass_core_kg": m_core,
        "mass_total_kg": m_total,
        "vmax_m_s": vmax,
        "axial_force_PaN": axial_force,
        "rod_euler_ok": rod_ok,
        "leak_index": leak_index,
        "leak_ok": leak_ok,
    }
