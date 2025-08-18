# backend\modules\cylindre_vector.py
"""
Couche vectorisée NumPy pour dimensionner des lots de cylindres Stirling.
- Entrées: scalaires ou arrays broadcastables (power_W, rpm, etc.)
- Sorties: dictionnaire de ndarrays alignés.
"""

from __future__ import annotations
import numpy as np

def _ensure_array(x):
    return np.asarray(x) if np.ndim(x) else np.asarray([x]) if np.isscalar(x) else np.asarray(x)

def solve_bore_stroke_from_Vs_array(Vs, S_over_B):
    # B = [4*Vs / (pi * S_over_B)]^(1/3), S = S_over_B * B
    B = np.power(4.0 * Vs / (np.pi * S_over_B), 1.0/3.0)
    S = S_over_B * B
    return B, S

def mean_piston_speed_array(S, rpm):
    return 2.0 * S * rpm / 60.0

def size_stirling_cylinders_vector(
    power_W, rpm, eta_mech,
    p_me=200e3, use_pmean_model=False, p_mean=1.0e6, k_me=0.20,
    upiston_max=2.0, bore_max=0.10, stroke_to_bore=1.0,
    n_cyl_max=12, allow_rpm_reduce=True, min_rpm=300.0
) -> dict[str, np.ndarray]:
    """
    Retourne un dict d'arrays: ok, message_id, n_cyl, rpm, bore_m, stroke_m, Vs_cyl_m3, Vs_total_m3, p_me_used_Pa.
    message_id: 0=OK, 1=Param invalides, 2=Vs<=0, 3=aucune solution
    """

    # ----- Broadcast des entrées -----
    power_W  = _ensure_array(power_W)
    rpm      = _ensure_array(rpm)
    eta_mech = _ensure_array(eta_mech)

    # Les autres peuvent être scalaires (broadcast implicite)
    if use_pmean_model:
        p_me_used = k_me * p_mean
    else:
        p_me_used = p_me

    # Alignement des shapes par broadcasting
    power_W, rpm, eta_mech, p_me_used = np.broadcast_arrays(power_W, rpm, eta_mech, p_me_used)

    # ----- Calcul de base -----
    rps = rpm / 60.0
    denom = p_me_used * rps * eta_mech

    # Messages & sorties init
    shape = power_W.shape
    msg = np.zeros(shape, dtype=np.int8)  # 0 ok, 1 invalid, 2 Vs<=0, 3 no-solution
    ok = np.zeros(shape, dtype=bool)
    out_n_cyl = np.full(shape, fill_value=-1, dtype=np.int16)
    out_rpm = np.full(shape, fill_value=np.nan, dtype=float)
    out_B = np.full(shape, fill_value=np.nan, dtype=float)
    out_S = np.full(shape, fill_value=np.nan, dtype=float)
    out_Vs_cyl = np.full(shape, fill_value=np.nan, dtype=float)
    out_Vs_tot = np.full(shape, fill_value=np.nan, dtype=float)
    out_pme = p_me_used.copy()

    invalid = denom <= 0
    msg[invalid] = 1
    valid_mask = ~invalid

    Vs_total = np.empty(shape, dtype=float)
    Vs_total[valid_mask] = power_W[valid_mask] / denom[valid_mask]
    nonpos = valid_mask & (Vs_total <= 0)
    msg[nonpos] = 2
    valid_mask &= ~nonpos

    # Rien de valide ?
    if not np.any(valid_mask):
        return {
            "ok": ok, "message_id": msg, "n_cyl": out_n_cyl, "rpm": out_rpm,
            "bore_m": out_B, "stroke_m": out_S, "Vs_cyl_m3": out_Vs_cyl,
            "Vs_total_m3": out_Vs_tot, "p_me_used_Pa": out_pme
        }

    # ----- Essai au régime nominal -----
    # Pour chaque n_cyl candidate
    n_range = np.arange(1, n_cyl_max + 1, dtype=np.int16)  # (Nn,)
    # On va empiler (broadcast) par un nouvel axe
    Vs_tot_stack = np.expand_dims(Vs_total, axis=-1)  # (...,1)
    Vs_cyl = Vs_tot_stack / n_range  # (..., Nn)

    B, S = solve_bore_stroke_from_Vs_array(Vs_cyl, stroke_to_bore)
    Up = mean_piston_speed_array(S, np.expand_dims(rpm, -1))
    # Contraintes
    ok_B = (B <= bore_max)
    ok_Up = (Up <= upiston_max)
    feasible = ok_B & ok_Up & np.isfinite(B) & np.isfinite(S)

    # Choix du plus petit n_cyl faisable (argmin sur l’indice faisable)
    any_feasible = feasible.any(axis=-1)  # (...)
    # Indice n_cyl minimal faisable
    idx_min = np.where(any_feasible, feasible.argmax(axis=-1), -1)  # first True -> argmax trick
    # Masque où nominal passe
    nominal_pass = valid_mask & any_feasible

    # Renseigner sorties pour nominal
    sel = nominal_pass
    out_n_cyl[sel] = n_range[idx_min[sel]]
    out_B[sel] = B[sel, idx_min[sel]]
    out_S[sel] = S[sel, idx_min[sel]]
    out_Vs_cyl[sel] = Vs_cyl[sel, idx_min[sel]]
    out_Vs_tot[sel] = Vs_total[sel]
    out_rpm[sel] = rpm[sel]
    ok[sel] = True
    msg[sel] = 0

    # ----- Option : essai avec réduction de régime -----
    reduce_needed = valid_mask & (~nominal_pass) & allow_rpm_reduce
    if np.any(reduce_needed):
        # Liste de paliers (comme le scalaire)
        rpm_cand = np.stack([
            np.maximum(min_rpm, (rpm * f).astype(int))
            for f in (0.8, 0.6, 0.5, 0.4, 0.33, 0.25)
        ], axis=-1)  # (..., Nr)
        # Recalcule rps et Vs_total ne changent pas (p_me, eta idem) => seule Up dépend du rpm
        # On reprend les mêmes B,S mais on change Up avec rpm_cand
        # Ajouter un axe pour matcher (..., Nn, Nr)
        Up_red = mean_piston_speed_array(
            np.expand_dims(S, -1),   # (..., Nn, 1)
            np.expand_dims(rpm_cand, -2)  # (..., 1, Nr)
        )

        ok_Up_red = (Up_red <= upiston_max)
        feasible_red = np.expand_dims(ok_B, -1) & ok_Up_red & np.isfinite(Up_red)

        any_feasible_red = feasible_red.any(axis=(-2, -1))
        red_pass = reduce_needed & any_feasible_red
        if np.any(red_pass):
            # On cherche le couple (n_cyl, rpm_cand) lexicographiquement minimal en n_cyl puis en rpm_cand
            # On construit un grand masque et on prend l’argmin d’un score
            Nn = n_range.size
            Nr = rpm_cand.shape[-1]
            # Score = n_idx * (Nr+1) + r_idx, et on masque l’infaisable par +inf
            scores = np.broadcast_to(
                np.arange(Nn)[:, None] * (Nr + 1) + np.arange(Nr)[None, :],
                feasible_red.shape
            ).astype(float)
            scores[~feasible_red] = np.inf

            # Trouver r_idx, n_idx minimaux
            # On a shape (..., Nn, Nr); on vectorise en 2D sur l’axe final
            scores_2d = scores.reshape(scores.shape[:-2] + (Nn * Nr,))
            best_flat = np.nanargmin(scores_2d, axis=-1)  # (...)
            # Convertir en indices (n_idx, r_idx)
            best_n = (best_flat // Nr).astype(int)
            best_r = (best_flat % Nr).astype(int)

            # Appliquer uniquement aux cas red_pass
            sel2 = red_pass
            out_n_cyl[sel2] = n_range[best_n[sel2]]
            out_B[sel2] = B[sel2, best_n[sel2]]
            out_S[sel2] = S[sel2, best_n[sel2]]
            out_Vs_cyl[sel2] = Vs_cyl[sel2, best_n[sel2]]
            out_Vs_tot[sel2] = Vs_total[sel2]
            out_rpm[sel2] = rpm_cand[sel2, best_r[sel2]]
            ok[sel2] = True
            msg[sel2] = 0

    # Marquer les restants valides comme “aucune solution”
    remaining = valid_mask & (~ok)
    msg[remaining] = 3

    return {
        "ok": ok,
        "message_id": msg,
        "n_cyl": out_n_cyl,
        "rpm": out_rpm,
        "bore_m": out_B,
        "stroke_m": out_S,
        "Vs_cyl_m3": out_Vs_cyl,
        "Vs_total_m3": out_Vs_tot,
        "p_me_used_Pa": out_pme
    }