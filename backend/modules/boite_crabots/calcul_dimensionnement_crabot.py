# backend\modules\boite_crabots\calcul_dimensionnement_crabot.py
from __future__ import annotations

import math
from typing import Literal, Optional


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


def _require_int_ge(name: str, x: int, min_value: int = 1) -> int:
    if not isinstance(x, int):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return x


def calcul_couple_transmissible_crabot(
    nombre_dents: int,
    pression_admissible: float,
    hauteur_dent: float,
    largeur_dent: float,
    rayon_moyen: float,
    *,
    # Options de robustesse, sans casser l'appel existant
    facteur_repartition: float = 1.0,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Calcule le couple maximum transmissible par un crabot avant écrasement/plastification.

    Modèle de base (inchangé) :
      T_cap = N_d * p_adm * (h * b_d) * r_m

    Extension optionnelle :
      - facteur_repartition : corrige le fait que toutes les dents ne portent pas parfaitement.
        Ex: 0.6..1.0 selon qualité d'alignement/rigidité.
        Par défaut 1.0 => comportement identique à ton code initial.

    Paramètres :
    - nombre_dents : N_d (>=1)
    - pression_admissible : p_adm (Pa) (>=0)
    - hauteur_dent : h (m) (>=0)
    - largeur_dent : b_d (m) (>=0)
    - rayon_moyen : r_m (m) (>0)
    - facteur_repartition : (0..1] typiquement (on ne bloque pas strictement)
    - clamp_non_negative : borne le résultat à >= 0
    - return_details : retourne aussi aire_contact et termes

    Retour :
    - T_cap (N·m) ou dict si return_details=True
    """
    Nd = _require_int_ge("nombre_dents", nombre_dents, 1)
    p_adm = _require_positive("pression_admissible", pression_admissible, strictly=False)
    h = _require_positive("hauteur_dent", hauteur_dent, strictly=False)
    b = _require_positive("largeur_dent", largeur_dent, strictly=False)
    r = _require_positive("rayon_moyen", rayon_moyen, strictly=True)

    k = _require_finite("facteur_repartition", facteur_repartition)
    # On reste module-friendly: on ne force pas (0,1], mais on protège des absurdités.
    if k < 0.0:
        raise ValueError("facteur_repartition doit être >= 0.")

    aire_contact = h * b
    T_cap = float(Nd) * p_adm * aire_contact * r * k

    if clamp_non_negative:
        T_cap = max(0.0, T_cap)

    if return_details:
        return {
            "T_cap": T_cap,
            "N_d": float(Nd),
            "p_adm": p_adm,
            "aire_contact": aire_contact,
            "r_m": r,
            "facteur_repartition": k,
        }
    return T_cap


def calcul_pression_contact_crabot(
    couple_nm: float,
    nombre_dents: int,
    hauteur_dent: float,
    largeur_dent: float,
    rayon_moyen: float,
    *,
    use_abs_couple: bool = True,
    facteur_repartition: float = 1.0,
    epsilon: float = 1e-18,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Calcule la pression de contact moyenne "équivalente" sur les dents du crabot.

    Modèle :
      F_par_dent = T / (N_d * r_m)
      p = F_par_dent / (h * b_d)

    Options :
    - use_abs_couple : True (défaut) -> utilise |T| (magnitude) pour éviter des pressions négatives
    - facteur_repartition : corrige la répartition réelle de charge (même logique que T_cap)
      => p augmente si k < 1 (moins de dents portent effectivement)
        Ici, on divise la capacité de partage: N_eff = N_d * k, donc p ~ 1/k.
      Par défaut 1.0 => comportement identique.
    - epsilon : seuil pour éviter division par 0 si aire ou N_eff*r est trop petit
    - return_details : renvoie force_par_dent, aire_contact, etc.

    Retour :
    - pression (Pa) ou dict si return_details=True
    """
    T = _require_finite("couple_nm", couple_nm)
    Nd = _require_int_ge("nombre_dents", nombre_dents, 1)
    h = _require_positive("hauteur_dent", hauteur_dent, strictly=False)
    b = _require_positive("largeur_dent", largeur_dent, strictly=False)
    r = _require_positive("rayon_moyen", rayon_moyen, strictly=True)

    k = _require_finite("facteur_repartition", facteur_repartition)
    if k <= 0.0:
        raise ValueError("facteur_repartition doit être > 0 pour calculer une pression.")
    eps = _require_positive("epsilon", epsilon, strictly=True)

    T_eff = abs(T) if use_abs_couple else T

    aire_contact = h * b
    if aire_contact <= eps:
        raise ValueError("Aire de contact trop faible (h*b ~ 0).")

    # Nombre effectif de dents porteuses (modèle simple)
    Nd_eff = float(Nd) * k
    denom_force = Nd_eff * r
    if abs(denom_force) <= eps:
        raise ValueError("Paramètres invalides: N_eff * r trop petit (division par ~0).")

    force_par_dent = T_eff / denom_force
    pression = force_par_dent / aire_contact

    if clamp_non_negative:
        pression = max(0.0, pression)

    if return_details:
        return {
            "p_contact": pression,
            "T_eff": T_eff,
            "N_d": float(Nd),
            "N_eff": Nd_eff,
            "facteur_repartition": k,
            "force_par_dent": force_par_dent,
            "aire_contact": aire_contact,
            "r_m": r,
        }
    return pression
