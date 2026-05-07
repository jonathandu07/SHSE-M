# backend\modules\boite_crabots\calcul_contact_dent.py
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


def calcul_contrainte_contact_hertz(
    force_tangentielle: float,
    largeur_denture_b: float,
    diametre_primitif_moyen: float,
    coefficient_zh: float,
    *,
    # Options "module-friendly" : ne changent rien au comportement par défaut
    use_abs_force: bool = True,
    epsilon: float = 1e-18,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Estime la contrainte de contact (pression de Hertz) sous forme simplifiée.

    Formule :
      σ_H = Z_H * sqrt( F_t / (b * d_m) )

    Paramètres (SI) :
    - force_tangentielle : F_t (N). Peut être signée selon conventions ; par défaut on prend |F_t|.
    - largeur_denture_b : b (m) > 0
    - diametre_primitif_moyen : d_m (m) > 0
    - coefficient_zh : Z_H (facteur matériau/géométrie), généralement > 0

    Options :
    - use_abs_force : True (défaut) -> utilise |F_t| (évite racine d'un négatif si convention signée)
    - epsilon : seuil pour éviter division par 0 si b*d_m est très petit
    - clamp_non_negative : True -> borne σ_H à >= 0 (sécurité)
    - return_details : True -> renvoie un dict avec termes intermédiaires utiles au debug

    Retour :
    - σ_H en Pa (float) ou dict si return_details=True
    """
    Ft = _require_finite("force_tangentielle", force_tangentielle)
    b = _require_positive("largeur_denture_b", largeur_denture_b, strictly=True)
    dm = _require_positive("diametre_primitif_moyen", diametre_primitif_moyen, strictly=True)
    Zh = _require_positive("coefficient_zh", coefficient_zh, strictly=True)
    eps = _require_positive("epsilon", epsilon, strictly=True)

    Ft_eff = abs(Ft) if use_abs_force else Ft

    denom = b * dm
    if denom <= eps:
        raise ValueError("Dimensions invalides: b * d_m trop petit (risque de division par ~0).")

    terme_sous_racine = Ft_eff / denom

    # Si use_abs_force=False et Ft_eff<0, on évite un sqrt d'un négatif
    if terme_sous_racine < 0.0:
        raise ValueError(
            "Terme sous la racine négatif. Active use_abs_force=True ou vérifie la convention de signe de F_t."
        )

    sigma_h = Zh * math.sqrt(terme_sous_racine)
    if clamp_non_negative:
        sigma_h = max(0.0, sigma_h)

    if return_details:
        return {
            "sigma_H": sigma_h,
            "F_t_eff": Ft_eff,
            "b": b,
            "d_m": dm,
            "Z_H": Zh,
            "terme_sous_racine": terme_sous_racine,
        }
    return sigma_h
