from __future__ import annotations

import math
from typing import Literal, Mapping


_G0 = 9.80665  # m/s²


def _is_finite(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _require_finite(name: str, x: float) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_positive(name: str, x: float, *, strictly: bool = True) -> float:
    x = _require_finite(name, x)
    ok = x > 0.0 if strictly else x >= 0.0
    if not ok:
        op = ">" if strictly else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {x}).")
    return x


def calcul_charges_essieux(
    masse_kg: float,
    acceleration_ms2: float,
    angle_pente: float,
    empattement_l_m: float,
    dist_cg_arriere_lr_m: float,
    dist_cg_avant_lf_m: float,
    hauteur_cg_h_m: float,
    gravite: float = _G0,
    *,
    angle_unite: Literal["rad", "deg"] = "rad",
    clamp_non_negative: bool = True,
    check_consistance: bool = True,
    return_details: bool = False,
) -> dict[str, float]:
    """
    Calcule les charges normales sur essieu avant et arrière (modèle quasi-statique 2D),
    avec transfert de charge dû à l'accélération longitudinale et à la pente.

    Conventions :
    - acceleration_ms2 > 0 : accélération (transfert vers l'arrière)
    - acceleration_ms2 < 0 : freinage (transfert vers l'avant)
    - angle_pente > 0 : montée (si angle_unite='rad' : radians, sinon degrés)
      (Ce modèle suit les équations usuelles où la composante longitudinale de poids peut
       contribuer via un terme en sin(theta)*h.)

    Paramètres (SI) :
    - masse_kg: masse du véhicule (kg)
    - acceleration_ms2: accélération longitudinale (m/s²)
    - angle_pente: pente (rad par défaut, ou degrés)
    - empattement_l_m: empattement total L (m)
    - dist_cg_arriere_lr_m: distance CG -> essieu arrière lr (m)
    - dist_cg_avant_lf_m: distance CG -> essieu avant lf (m)
    - hauteur_cg_h_m: hauteur du CG h (m)
    - gravite: g (m/s²)

    Options :
    - angle_unite: 'rad' ou 'deg'
    - clamp_non_negative: borne N_avant/N_arriere à >= 0 (évite des sorties non physiques)
    - check_consistance: vérifie lr+lf ≈ L (tolérance 2%) et avertit via ValueError si incohérent
    - return_details: inclut des termes intermédiaires utiles au debug

    Retour :
    - dict avec au minimum {"N_avant": ..., "N_arriere": ...} (N)
      et si return_details=True, ajoute des clés "details_*".
    """
    m = _require_positive("masse_kg", masse_kg, strictly=True)
    a = _require_finite("acceleration_ms2", acceleration_ms2)
    L = _require_positive("empattement_l_m", empattement_l_m, strictly=True)
    lr = _require_positive("dist_cg_arriere_lr_m", dist_cg_arriere_lr_m, strictly=False)
    lf = _require_positive("dist_cg_avant_lf_m", dist_cg_avant_lf_m, strictly=False)
    h = _require_positive("hauteur_cg_h_m", hauteur_cg_h_m, strictly=False)
    g = _require_positive("gravite", gravite, strictly=True)

    theta = math.radians(angle_pente) if angle_unite == "deg" else _require_finite("angle_pente", angle_pente)

    if check_consistance and lr > 0.0 and lf > 0.0:
        s = lr + lf
        if abs(s - L) / max(L, 1e-9) > 0.02:  # 2%
            raise ValueError(f"Incohérence: lr+lf={s} m ne correspond pas à L={L} m (tolérance 2%).")

    # Termes utiles
    mg = m * g
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)

    # Force normale totale (projection sur l'axe normal à la route)
    # Somme N_avant + N_arriere = m*g*cos(theta) (dans ce modèle)
    N_total = mg * cos_t

    # Termes de moment autour du CG (modèle simplifié)
    # terme_inertie = m*a*h
    terme_inertie = m * a * h

    # terme_pente_h = m*g*sin(theta)*h
    # (ce terme modélise l'effet de la composante longitudinale du poids appliquée au CG à hauteur h)
    terme_pente_h = mg * sin_t * h

    # Formules (comme ton code, en conservant la structure)
    # N_f = (m g cos(theta) * lr - m a h - m g sin(theta) * h) / L
    N_avant = (mg * cos_t * lr - terme_inertie - terme_pente_h) / L

    # N_r = (m g cos(theta) * lf + m a h + m g sin(theta) * h) / L
    N_arriere = (mg * cos_t * lf + terme_inertie + terme_pente_h) / L

    if clamp_non_negative:
        N_avant = max(0.0, N_avant)
        N_arriere = max(0.0, N_arriere)

    # Optionnel : re-normaliser si on a clampé (sinon somme != N_total)
    # Ici on ne renormalise pas par défaut, car le clamp est un garde-fou.
    # Si tu veux renormaliser: active un paramètre dédié (non fourni) ou traite en amont.

    out: dict[str, float] = {
        "N_avant": N_avant,
        "N_arriere": N_arriere,
    }

    if return_details:
        out.update(
            {
                "details_theta_rad": theta,
                "details_cos_theta": cos_t,
                "details_sin_theta": sin_t,
                "details_mg": mg,
                "details_N_total": N_total,
                "details_terme_inertie_m_a_h": terme_inertie,
                "details_terme_pente_m_g_sin_h": terme_pente_h,
                "details_check_sum_N": N_avant + N_arriere,
            }
        )

    return out
