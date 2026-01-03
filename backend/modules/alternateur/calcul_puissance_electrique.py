# backend\modules\alternateur\calcul_puissance_electrique.py
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


def _require_pf(facteur_puissance: float) -> float:
    pf = _require_finite("facteur_puissance", facteur_puissance)
    # On reste "module-friendly": on tolère un peu, mais on protège les cas absurdes.
    if abs(pf) > 1.0 + 1e-9:
        raise ValueError("facteur_puissance (cos phi) doit être dans [-1, 1].")
    # Petite correction numérique si pf est très légèrement > 1 par flottants.
    return max(-1.0, min(1.0, pf))


def calcul_puissance_triphase(
    tension_composee: float,
    courant_ligne: float,
    facteur_puissance: float = 1.0,
    *,
    # Pour les cas où tu fournis des grandeurs phase (tension simple ou courant de phase)
    entree: Literal["VLL_IL", "Vph_Iph"] = "VLL_IL",
    connexion: Literal["Y", "Delta"] = "Y",
    # Si True, renvoie aussi S et Q en plus de P
    return_details: bool = False,
    clamp_non_negative: bool = False,
) -> float | dict[str, float]:
    """
    Calcule la puissance active en triphasé.

    Cas standard :
      P = sqrt(3) * V_LL * I_L * cos(phi)

    Alternatives (si entree="Vph_Iph") :
      - En étoile (Y)   : V_LL = sqrt(3)*V_ph,  I_L = I_ph
      - En triangle (Δ) : V_LL = V_ph,          I_L = sqrt(3)*I_ph

    Paramètres :
    - tension_composee : V_LL (V) si entree="VLL_IL", sinon V_ph (V)
    - courant_ligne    : I_L (A)  si entree="VLL_IL", sinon I_ph (A)
    - facteur_puissance: cos(phi) dans [-1, 1] (défaut 1.0)
    - entree           : "VLL_IL" (défaut) ou "Vph_Iph"
    - connexion        : "Y" ou "Delta" (utilisé seulement si entree="Vph_Iph")
    - return_details   : si True, retourne {"P":..., "S":..., "Q":..., "V_LL":..., "I_L":..., "pf":...}
    - clamp_non_negative: si True, borne P à >= 0

    Retour :
    - P (W) ou dict si return_details=True
    """
    V_in = _require_finite("tension_composee", tension_composee)
    I_in = _require_finite("courant_ligne", courant_ligne)
    pf = _require_pf(facteur_puissance)

    if entree == "VLL_IL":
        V_LL = V_in
        I_L = I_in
    elif entree == "Vph_Iph":
        V_ph = V_in
        I_ph = I_in
        if connexion == "Y":
            V_LL = math.sqrt(3.0) * V_ph
            I_L = I_ph
        elif connexion == "Delta":
            V_LL = V_ph
            I_L = math.sqrt(3.0) * I_ph
        else:
            raise ValueError("connexion doit être 'Y' ou 'Delta'.")
    else:
        raise ValueError("entree doit être 'VLL_IL' ou 'Vph_Iph'.")

    S = math.sqrt(3.0) * V_LL * I_L  # VA
    P = S * pf                       # W
    # Q = S*sin(phi) et sin(phi) = sqrt(1 - cos²(phi)) (on prend la magnitude)
    sin_phi = math.sqrt(max(0.0, 1.0 - pf * pf))
    Q = S * sin_phi                  # var (magnitude)

    if clamp_non_negative:
        P = max(0.0, P)

    if return_details:
        return {
            "P": P,
            "S": S,
            "Q": Q,
            "V_LL": V_LL,
            "I_L": I_L,
            "pf": pf,
        }
    return P


def calcul_puissance_monophase(
    tension: float,
    courant: float,
    facteur_puissance: float = 1.0,
    *,
    return_details: bool = False,
    clamp_non_negative: bool = False,
) -> float | dict[str, float]:
    """
    Calcule la puissance active en monophasé.

      P = V * I * cos(phi)

    Options :
    - return_details : renvoie aussi S (VA) et Q (var magnitude)
    - clamp_non_negative : borne P à >= 0

    Retour :
    - P (W) ou dict si return_details=True
    """
    V = _require_finite("tension", tension)
    I = _require_finite("courant", courant)
    pf = _require_pf(facteur_puissance)

    S = V * I
    P = S * pf
    sin_phi = math.sqrt(max(0.0, 1.0 - pf * pf))
    Q = S * sin_phi

    if clamp_non_negative:
        P = max(0.0, P)

    if return_details:
        return {"P": P, "S": S, "Q": Q, "pf": pf}
    return P


def calcul_puissance_dc(
    tension_dc: float,
    courant_dc: float,
    *,
    clamp_non_negative: bool = False,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Calcule la puissance en courant continu (DC).

      P = V_DC * I_DC

    Options :
    - clamp_non_negative : borne P à >= 0
    - return_details : renvoie aussi V et I

    Retour :
    - P (W) ou dict si return_details=True
    """
    V = _require_finite("tension_dc", tension_dc)
    I = _require_finite("courant_dc", courant_dc)

    P = V * I
    if clamp_non_negative:
        P = max(0.0, P)

    if return_details:
        return {"P": P, "V": V, "I": I}
    return P
