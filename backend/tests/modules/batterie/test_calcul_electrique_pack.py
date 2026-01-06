# backend/modules/batterie/calcul_electrique_pack.py
from __future__ import annotations

import math


# =============================================================================
# Utilitaires robustesse (même philosophie que tes modules batterie)
# =============================================================================

def _est_fini(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _exiger_fini(nom: str, x: float) -> float:
    if not _est_fini(x):
        raise ValueError(f"{nom} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _exiger_positif(nom: str, x: float, *, strict: bool = True) -> float:
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def _exiger_rendement(nom: str, x: float) -> float:
    eta = _exiger_positif(nom, x, strict=True)
    if eta > 1.0:
        raise ValueError(f"{nom} doit être <= 1.0 (reçu: {eta}).")
    return eta


# =============================================================================
# Conversions / estimations électriques pack
# =============================================================================

def calcul_conso_kwh_km_depuis_puissance_vitesse(puissance_moyenne_kw: float, vitesse_moyenne_kmh: float) -> float:
    """
    Déduit une consommation moyenne (kWh/km) depuis puissance moyenne (kW) et vitesse moyenne (km/h).

    Déduction :
        conso(kWh/km) = P(kW) / v(km/h)

    Hypothèse (à expliciter côté appelant) :
        - puissance_moyenne_kw représente la puissance électrique moyenne réellement tirée (ou équivalente)
          sur le système (pack / chaîne), sur la phase considérée.
        - vitesse moyenne stable sur la phase considérée.

    Args:
        puissance_moyenne_kw (float): (>= 0)
        vitesse_moyenne_kmh (float): (> 0 si puissance > 0)

    Returns:
        float: conso (kWh/km)
    """
    P = _exiger_positif("puissance_moyenne_kw", puissance_moyenne_kw, strict=False)
    v = _exiger_positif("vitesse_moyenne_kmh", vitesse_moyenne_kmh, strict=True)

    if P == 0.0:
        return 0.0

    return P / v


def calcul_ah_depuis_kwh_tension(capacite_kwh: float, tension_v: float) -> float:
    """
    Convertit une énergie (kWh) en capacité (Ah) à tension nominale constante.

    Déduction :
        Wh = kWh * 1000
        Ah = Wh / V

    Args:
        capacite_kwh (float): énergie (>= 0)
        tension_v (float): (> 0)

    Returns:
        float: capacité (Ah)
    """
    E_kwh = _exiger_positif("capacite_kwh", capacite_kwh, strict=False)
    V = _exiger_positif("tension_v", tension_v, strict=True)

    if E_kwh == 0.0:
        return 0.0

    return (E_kwh * 1000.0) / V


def calcul_courant_depuis_kw_tension(puissance_kw: float, tension_v: float) -> float:
    """
    Calcule un courant (A) depuis puissance (kW) et tension (V).

    Déduction :
        P(W) = kW * 1000
        I(A) = P(W) / V

    Args:
        puissance_kw (float): (>= 0)
        tension_v (float): (> 0)

    Returns:
        float: courant (A)
    """
    P_kw = _exiger_positif("puissance_kw", puissance_kw, strict=False)
    V = _exiger_positif("tension_v", tension_v, strict=True)

    if P_kw == 0.0:
        return 0.0

    return (P_kw * 1000.0) / V


def calcul_c_rate_depuis_kw_kwh(puissance_kw: float, capacite_kwh: float) -> float:
    """
    Estime un C-rate à partir de P(kW) et E(kWh).

    Déduction (énergie/puissance) :
        C_rate ≈ P(kW) / E(kWh)

    Remarque :
        - C-rate exact dépend de la tension (et de la capacité en Ah), mais ce ratio est cohérent
          comme indicateur global au niveau pack.

    Args:
        puissance_kw (float): (>= 0)
        capacite_kwh (float): (>= 0)

    Returns:
        float: C-rate (h^-1)
    """
    P = _exiger_positif("puissance_kw", puissance_kw, strict=False)
    E = _exiger_positif("capacite_kwh", capacite_kwh, strict=False)

    if P == 0.0:
        return 0.0
    if E == 0.0:
        raise ValueError("Impossible de calculer un C-rate avec capacite_kwh == 0 et puissance_kw > 0.")

    return P / E


def calcul_puissance_effective_stockee(puissance_charge_kw: float, rendement_charge: float) -> float:
    """
    Puissance effective réellement stockée (kW) en charge.

    Déduction :
        P_eff = eta * P_charge

    Args:
        puissance_charge_kw (float): (> 0)
        rendement_charge (float): (0 < eta <= 1)

    Returns:
        float: P_eff (kW)
    """
    P = _exiger_positif("puissance_charge_kw", puissance_charge_kw, strict=True)
    eta = _exiger_rendement("rendement_charge", rendement_charge)
    return P * eta


def calcul_puissance_charge_requise(energie_utile_kwh: float, temps_charge_h: float, rendement_charge: float) -> float:
    """
    Inversion du modèle de charge à puissance constante.

    Déduction :
        E_u = eta * P * t  =>  P = E_u / (eta * t)

    Args:
        energie_utile_kwh (float): (>= 0)
        temps_charge_h (float): (> 0 si energie > 0)
        rendement_charge (float): (0 < eta <= 1)

    Returns:
        float: P (kW)
    """
    E = _exiger_positif("energie_utile_kwh", energie_utile_kwh, strict=False)
    t = _exiger_positif("temps_charge_h", temps_charge_h, strict=True)
    eta = _exiger_rendement("rendement_charge", rendement_charge)

    if E == 0.0:
        return 0.0

    return E / (eta * t)
