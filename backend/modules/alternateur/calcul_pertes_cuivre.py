# backend\modules\alternateur\calcul_pertes_cuivre.py
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


def calcul_resistance_enroulement(
    resistivite: float,
    longueur_fil: float,
    section_fil: float,
    *,
    # Optionnel : ajustement simple de la résistivité avec la température
    temperature_c: Optional[float] = None,
    temperature_ref_c: float = 20.0,
    coef_temperature: float = 0.00393,
    clamp_non_negative: bool = True,
) -> float:
    """
    Calcule la résistance d'un enroulement.

    Formule :
      R = rho * L / A

    Options température (si temperature_c est fourni) :
      rho(T) = rho_ref * (1 + alpha * (T - T_ref))
    (alpha ~ 0.00393 1/°C pour le cuivre autour de 20°C)

    Paramètres :
    - resistivite : rho (Ω·m) à T_ref (par défaut 20°C)
    - longueur_fil : L (m)
    - section_fil : A (m²)
    - temperature_c : température du conducteur (°C) (optionnel)
    - temperature_ref_c : T_ref (°C)
    - coef_temperature : alpha (1/°C)
    - clamp_non_negative : borne R à >= 0 (sécurité)

    Retour :
    - résistance (Ω)
    """
    rho = _require_positive("resistivite", resistivite, strictly=False)
    L = _require_positive("longueur_fil", longueur_fil, strictly=False)
    A = _require_positive("section_fil", section_fil, strictly=True)

    if temperature_c is not None:
        T = _require_finite("temperature_c", temperature_c)
        Tref = _require_finite("temperature_ref_c", temperature_ref_c)
        alpha = _require_finite("coef_temperature", coef_temperature)
        rho = rho * (1.0 + alpha * (T - Tref))

    R = rho * L / A
    return max(0.0, R) if clamp_non_negative else R


def calcul_pertes_cuivre_phase(
    courant: float,
    resistance: float,
    *,
    courant_type: Literal["rms", "peak"] = "rms",
    clamp_non_negative: bool = True,
) -> float:
    """
    Calcule les pertes cuivre pour une phase/enroulement.

    Formule (avec courant RMS) :
      P = I_rms² * R

    Options :
    - courant_type='peak' : convertit I_peak -> I_rms = I_peak / sqrt(2) (sinusoïdal)

    Paramètres :
    - courant : A
    - resistance : Ω
    - courant_type : 'rms' (défaut) ou 'peak'
    - clamp_non_negative : borne P à >= 0

    Retour :
    - pertes (W)
    """
    I = _require_finite("courant", courant)
    R = _require_finite("resistance", resistance)

    if courant_type == "peak":
        I = I / math.sqrt(2.0)
    elif courant_type != "rms":
        raise ValueError("courant_type doit être 'rms' ou 'peak'.")

    P = (I ** 2) * R
    return max(0.0, P) if clamp_non_negative else P


def calcul_pertes_cuivre_triphase(
    courant_phase: float,
    resistance_phase: float,
    *,
    courant_type: Literal["rms", "peak"] = "rms",
    connexion: Literal["Y", "Delta"] = "Y",
    # Si tu fournis un courant de ligne en étoile/triangle, tu peux activer ce mode.
    courant_est_ligne: bool = False,
    clamp_non_negative: bool = True,
) -> float:
    """
    Calcule les pertes cuivre totales (système triphasé).

    Base (courant de phase RMS) :
      P_cu = 3 * I_ph² * R_ph

    Options de connexion (si courant_est_ligne=True) :
    - En étoile (Y) : I_ligne = I_phase
    - En triangle (Delta) : I_ligne = sqrt(3) * I_phase  => I_phase = I_ligne / sqrt(3)

    Paramètres :
    - courant_phase : courant (A) (phase ou ligne selon courant_est_ligne)
    - resistance_phase : résistance par phase (Ω)
    - courant_type : 'rms' (défaut) ou 'peak'
    - connexion : 'Y' ou 'Delta' (utile uniquement si courant_est_ligne=True)
    - courant_est_ligne : si True, interprète courant_phase comme courant de ligne
    - clamp_non_negative : borne P à >= 0

    Retour :
    - pertes cuivre totales (W)
    """
    I = _require_finite("courant_phase", courant_phase)
    Rph = _require_finite("resistance_phase", resistance_phase)

    # Conversion peak->rms si besoin
    if courant_type == "peak":
        I = I / math.sqrt(2.0)
    elif courant_type != "rms":
        raise ValueError("courant_type doit être 'rms' ou 'peak'.")

    # Si on a un courant de ligne, convertir en courant de phase suivant la connexion
    if courant_est_ligne:
        if connexion == "Y":
            I_phase = I
        elif connexion == "Delta":
            I_phase = I / math.sqrt(3.0)
        else:
            raise ValueError("connexion doit être 'Y' ou 'Delta'.")
    else:
        I_phase = I

    P = 3.0 * (I_phase ** 2) * Rph
    return max(0.0, P) if clamp_non_negative else P
