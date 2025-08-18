# -*- coding: utf-8 -*-
# backend/modules/deplaceur_vector.py
"""
Couche vectorisée NumPy pour dimensionner des lots de déplaceurs.
Toutes les entrées peuvent être des scalaires ou des arrays broadcastables.
"""

from __future__ import annotations
import numpy as np

def _arr(x):
    return np.asarray(x) if np.ndim(x) else np.asarray([x]) if np.isscalar(x) else np.asarray(x)

def recommend_cold_clearance_array(bore_m, alpha, dT_hot, min_hot_clearance_m, manuf_tol_m):
    delta_radius_hot = 0.5 * alpha * bore_m * dT_hot
    clearance_cold = min_hot_clearance_m + delta_radius_hot + manuf_tol_m
    clearance_cold = np.maximum(clearance_cold, 0.08e-3)
    clearance_cold = np.minimum(clearance_cold, 0.25e-3)
    return clearance_cold

def thin_shell_displacer_masses_array(D_o, L, t_shell, t_caps, rho_shell, use_core, rho_core):
    D_i = np.maximum(D_o - 2.0 * t_shell, 1e-9)
    V_shell = np.pi * D_o * t_shell * L
    m_shell = V_shell * rho_shell
    A_disc = np.pi * (D_o * 0.5) ** 2
    V_caps = 2.0 * A_disc * t_caps
    m_caps = V_caps * rho_shell
    m_core = np.where(use_core & (D_i > 0), (np.pi * (0.5 * D_i) ** 2 * L) * rho_core, 0.0)
    return m_shell, m_caps, m_core

def max_piston_speed_array(stroke, rpm):
    omega = 2.0 * np.pi * (rpm / 60.0)
    return omega * (stroke / 2.0)

def simple_annular_leak_index_array(bore_m, gap_radial_m, length_m):
    perimeter = np.pi * bore_m
    return (perimeter * (gap_radial_m ** 3)) / np.maximum(length_m, 1e-9)

def euler_buckling_ok_array(rod_d, rod_L, E, axial_force):
    I = np.pi * (rod_d ** 4) / 64.0
    Pcr = (np.pi ** 2) * E * I / (4.0 * (rod_L ** 2))
    return axial_force < 0.3 * Pcr

def size_deplaceur_vector(
    bore_m, stroke_m,
    k_phase=1.0, dome_extra_clearance_m=0.02,
    radial_clearance_cold_m=None, min_hot_clearance_m=0.08e-3,
    alpha_material_1K=12e-6, deltaT_hotK=500.0, manuf_tol_radial_m=0.03e-3,
    shell_thickness_m=0.5e-3, cap_thickness_m=0.6e-3, material_density=8000.0,
    use_hollow_core=True, core_density=50.0,
    rod_length_m=None, rod_diameter_m=4e-3, young_modulus_Pa=200e9,
    rpm=600.0, gas_dynamic_dp_Pa=2000.0,
    acceptable_leak_index=1.5e-4
) -> dict[str, np.ndarray]:

    # Broadcast des entrées
    bore_m  = _arr(bore_m)
    stroke_m= _arr(stroke_m)
    k_phase = _arr(k_phase)
    dome_extra_clearance_m = _arr(dome_extra_clearance_m)
    min_hot_clearance_m = _arr(min_hot_clearance_m)
    alpha_material_1K = _arr(alpha_material_1K)
    deltaT_hotK = _arr(deltaT_hotK)
    manuf_tol_radial_m = _arr(manuf_tol_radial_m)
    shell_thickness_m = _arr(shell_thickness_m)
    cap_thickness_m = _arr(cap_thickness_m)
    material_density = _arr(material_density)
    use_hollow_core = _arr(use_hollow_core).astype(bool)
    core_density = _arr(core_density)
    rod_diameter_m = _arr(rod_diameter_m)
    young_modulus_Pa = _arr(young_modulus_Pa)
    rpm = _arr(rpm)
    gas_dynamic_dp_Pa = _arr(gas_dynamic_dp_Pa)
    acceptable_leak_index = _arr(acceptable_leak_index)

    if radial_clearance_cold_m is None:
        # calcul auto
        cr_cold = recommend_cold_clearance_array(
            bore_m, alpha_material_1K, deltaT_hotK,
            min_hot_clearance_m, manuf_tol_radial_m
        )
    else:
        cr_cold = _arr(radial_clearance_cold_m)

    # Broadcasting général
    (bore_m, stroke_m, k_phase, dome_extra_clearance_m, cr_cold, min_hot_clearance_m,
     alpha_material_1K, deltaT_hotK, manuf_tol_radial_m, shell_thickness_m, cap_thickness_m,
     material_density, use_hollow_core, core_density, rod_diameter_m, young_modulus_Pa,
     rpm, gas_dynamic_dp_Pa, acceptable_leak_index) = np.broadcast_arrays(
        bore_m, stroke_m, k_phase, dome_extra_clearance_m, cr_cold, min_hot_clearance_m,
        alpha_material_1K, deltaT_hotK, manuf_tol_radial_m, shell_thickness_m, cap_thickness_m,
        material_density, use_hollow_core, core_density, rod_diameter_m, young_modulus_Pa,
        rpm, gas_dynamic_dp_Pa, acceptable_leak_index
    )

    disp_stroke = k_phase * stroke_m
    L = disp_stroke + 2.0 * dome_extra_clearance_m

    D_cold = np.maximum(bore_m - 2.0 * cr_cold, 1e-9)
    deltaD_hot = alpha_material_1K * D_cold * deltaT_hotK
    D_hot = D_cold + deltaD_hot
    cr_hot = np.maximum(0.5 * (bore_m - D_hot), 0.0)

    # Validité thermique (jeu à chaud)
    ok_hot = cr_hot >= min_hot_clearance_m

    m_shell, m_caps, m_core = thin_shell_displacer_masses_array(
        D_cold, L, shell_thickness_m, cap_thickness_m, material_density,
        use_hollow_core, core_density
    )
    m_total = m_shell + m_caps + m_core

    vmax = max_piston_speed_array(disp_stroke, rpm)
    area = np.pi * (D_cold * 0.5) ** 2
    axial_force = area * gas_dynamic_dp_Pa

    rod_L = np.where(True, disp_stroke + 2.0*dome_extra_clearance_m + 0.03, 0.0) \
            if (rod_length_m is None) else _arr(rod_length_m)
    rod_L, = np.broadcast_arrays(rod_L, D_cold)

    rod_ok = euler_buckling_ok_array(rod_diameter_m, rod_L, young_modulus_Pa, axial_force)

    leak_idx = simple_annular_leak_index_array(bore_m, cr_hot, L)
    leak_ok = leak_idx <= acceptable_leak_index

    ok = ok_hot & rod_ok & leak_ok

    # message_id : 0 OK, 1 jeu_chaud_insuffisant, 2 flambage, 3 fuite
    msg = np.zeros(ok.shape, dtype=np.int8)
    msg[~ok_hot] = 1
    msg[ok_hot & ~rod_ok] = 2
    msg[ok_hot & rod_ok & ~leak_ok] = 3

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
        "leak_index": leak_idx,
        "leak_ok": leak_ok,
    }
