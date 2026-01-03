# backend\modules\batterie\calcul_temps_charge.py
from __future__ import annotations

import math


# =============================================================================
# Utilitaires robustesse (non intrusifs, API inchangée)
# =============================================================================

def _est_fini(x: float) -> bool:
    """True si x est un nombre réel fini (pas NaN, pas inf)."""
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _exiger_fini(nom: str, x: float) -> float:
    """Convertit en float et lève si NaN/inf."""
    if not _est_fini(x):
        raise ValueError(f"{nom} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _exiger_positif(nom: str, x: float, *, strict: bool = True) -> float:
    """
    Exige x > 0 (ou x >= 0 si strict=False).
    """
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def _exiger_rendement(nom: str, x: float) -> float:
    """
    Exige 0 < eta <= 1.
    """
    eta = _exiger_positif(nom, x, strict=True)
    if eta > 1.0:
        raise ValueError(f"{nom} doit être <= 1.0 (reçu: {eta}).")
    return eta


# =============================================================================
# Temps de charge (h)
# =============================================================================

def calcul_temps_charge(energie_utile_kwh: float, puissance_charge_kw: float, rendement_charge: float) -> float:
    """
    Calcule le temps de charge nécessaire pour restaurer une énergie utile donnée.

    Déduction :
        Puissance effective réellement stockée (kW) :
            P_eff = eta_chg * P_chg

        Temps (h) :
            t_chg = E_u / P_eff = E_u / (eta_chg * P_chg)

    Args:
        energie_utile_kwh (float): Énergie utile à recharger (kWh). (>= 0)
        puissance_charge_kw (float): Puissance de charge disponible (kW). (> 0)
        rendement_charge (float): Rendement global de charge (0 < eta <= 1).

    Returns:
        float: Temps de charge en heures (h).

    Remarques :
        - Ce calcul est un modèle "constant power" : il ne modélise pas la réduction de puissance
          en fin de charge (taper), ni les limites thermiques, ni la courbe CC/CV.
        - Pour du dimensionnement rapide, c'est une base fiable si eta est cohérent.
    """
    E_u = _exiger_positif("energie_utile_kwh", energie_utile_kwh, strict=False)
    P_chg = _exiger_positif("puissance_charge_kw", puissance_charge_kw, strict=True)
    eta = _exiger_rendement("rendement_charge", rendement_charge)

    # Cas limite stable : rien à recharger
    if E_u == 0.0:
        return 0.0

    puissance_effective_kw = P_chg * eta

    # Sécurité numérique (théoriquement impossible ici car P_chg>0 et eta>0)
    if puissance_effective_kw <= 0.0:
        raise ValueError("Puissance effective non positive (vérifier puissance_charge_kw et rendement_charge).")

    return E_u / puissance_effective_kw
