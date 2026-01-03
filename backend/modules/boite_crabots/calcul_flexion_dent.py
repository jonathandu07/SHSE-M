# backend\modules\boite_crabots\calcul_flexion_dent.py
from __future__ import annotations

import math
from typing import Optional


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


def calcul_contrainte_flexion_lewis(
    force_tangentielle: float,
    largeur_denture_b: float,
    module_m: float,
    facteur_forme_y: float,
    *,
    use_abs_force: bool = True,
    epsilon: float = 1e-18,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Estime la contrainte de flexion en pied de dent (formule de Lewis simplifiée).

    Formule :
      σ_F = F_t / (b * m * Y)

    Paramètres (SI) :
    - force_tangentielle : F_t (N). Peut être signée selon conventions ; par défaut on prend |F_t|.
    - largeur_denture_b  : b (m) > 0
    - module_m           : m (m) > 0
    - facteur_forme_y    : Y (sans dimension) > 0

    Options (fiabilisation sans casser l'usage) :
    - use_abs_force : True (défaut) -> utilise |F_t| (évite σ négative si convention signée)
    - epsilon : seuil pour éviter division par ~0 si b*m*Y est trop petit
    - clamp_non_negative : True -> borne σ_F à >= 0
    - return_details : True -> renvoie un dict avec termes intermédiaires (debug/dimensionnement)

    Retour :
    - σ_F (Pa) ou dict si return_details=True
    """
    Ft = _require_finite("force_tangentielle", force_tangentielle)
    b = _require_positive("largeur_denture_b", largeur_denture_b, strictly=True)
    m = _require_positive("module_m", module_m, strictly=True)
    Y = _require_positive("facteur_forme_y", facteur_forme_y, strictly=True)
    eps = _require_positive("epsilon", epsilon, strictly=True)

    Ft_eff = abs(Ft) if use_abs_force else Ft

    denom = b * m * Y
    if denom <= eps:
        raise ValueError("Paramètres invalides: b*m*Y trop petit (risque de division par ~0).")

    sigma_f = Ft_eff / denom
    if clamp_non_negative:
        sigma_f = max(0.0, sigma_f)

    if return_details:
        return {
            "sigma_F": sigma_f,
            "F_t_eff": Ft_eff,
            "b": b,
            "module_m": m,
            "Y": Y,
            "denominateur": denom,
        }
    return sigma_f
