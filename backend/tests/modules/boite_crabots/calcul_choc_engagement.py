# backend\modules\boite_crabots\calcul_choc_engagement.py
from __future__ import annotations

import math
from typing import Optional


def _is_finite(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _require_finite(name: str, x: float) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_non_negative(name: str, x: float) -> float:
    x = _require_finite(name, x)
    if x < 0.0:
        raise ValueError(f"{name} doit être >= 0 (reçu: {x}).")
    return x


def _require_positive(name: str, x: float) -> float:
    x = _require_finite(name, x)
    if x <= 0.0:
        raise ValueError(f"{name} doit être > 0 (reçu: {x}).")
    return x


def calcul_inertie_equivalente(
    inertie_primaire: float,
    inertie_secondaire: float,
    *,
    clamp_non_negative: bool = True,
    epsilon: float = 1e-12,
) -> float:
    """
    Calcule l'inertie équivalente "vue" lors d'un choc d'accouplement (deux inerties en interaction).

    Formule :
      J_eq = (J1 * J2) / (J1 + J2)

    Paramètres :
    - inertie_primaire : J1 (kg·m²)
    - inertie_secondaire : J2 (kg·m²)
    - clamp_non_negative : True -> borne J_eq à >= 0 (sécurité)
    - epsilon : seuil anti-division par 0

    Retour :
    - J_eq (kg·m²)
    """
    J1 = _require_finite("inertie_primaire", inertie_primaire)
    J2 = _require_finite("inertie_secondaire", inertie_secondaire)

    denom = J1 + J2
    if abs(denom) <= float(epsilon):
        # cas dégénéré (ou entrées très petites / opposées)
        return 0.0

    Jeq = (J1 * J2) / denom
    return max(0.0, Jeq) if clamp_non_negative else Jeq


def calcul_energie_choc(
    inertie_eq: float,
    delta_omega_rad_s: float,
    *,
    clamp_non_negative: bool = True,
) -> float:
    """
    Calcule l'énergie à dissiper lors du choc d'engagement.

    Formule :
      ΔE = 0.5 * J_eq * (Δω)²

    Paramètres :
    - inertie_eq : J_eq (kg·m²) (souvent >= 0)
    - delta_omega_rad_s : Δω (rad/s) (peut être signé, la formule utilise le carré)

    Retour :
    - énergie (J)
    """
    Jeq = _require_finite("inertie_eq", inertie_eq)
    d_omega = _require_finite("delta_omega_rad_s", delta_omega_rad_s)

    E = 0.5 * Jeq * (d_omega ** 2)
    return max(0.0, E) if clamp_non_negative else E


def calcul_couple_synchronisation_moyen(
    inertie_eq: float,
    delta_omega_rad_s: float,
    temps_engagement_s: float,
    *,
    use_abs_delta_omega: bool = True,
    epsilon_t: float = 1e-12,
    clamp_non_negative: bool = False,
) -> float:
    """
    Estime le couple moyen nécessaire pour synchroniser deux vitesses (couple "lissé").

    Formule :
      T_sync = (J_eq * Δω) / t_eng

    Paramètres :
    - inertie_eq : J_eq (kg·m²)
    - delta_omega_rad_s : Δω (rad/s)
    - temps_engagement_s : t_eng (s) (>0)
    - use_abs_delta_omega : True (défaut) -> utilise |Δω| (retourne un couple magnitude)
                            False -> conserve le signe (utile si tu veux une convention directionnelle)
    - epsilon_t : seuil anti-division par 0
    - clamp_non_negative : True -> borne T >= 0

    Retour :
    - couple moyen (N·m)
    """
    Jeq = _require_finite("inertie_eq", inertie_eq)
    d_omega = _require_finite("delta_omega_rad_s", delta_omega_rad_s)
    t = _require_finite("temps_engagement_s", temps_engagement_s)

    if t <= float(epsilon_t):
        raise ValueError("Le temps d'engagement doit être > 0.")

    d = abs(d_omega) if use_abs_delta_omega else d_omega
    T = (Jeq * d) / t
    return max(0.0, T) if clamp_non_negative else T
