# backend\modules\batterie\calcul_dimensionnement_batterie.py
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
    Utile pour éviter divisions par zéro et valeurs physiquement impossibles.
    """
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


# =============================================================================
# Dimensionnement batterie (kWh, kg)
# =============================================================================

def calcul_capacite_totale_batterie(energie_utile_kwh: float, fenetre_soc: float) -> float:
    """
    Calcule la capacité totale de la batterie (E_b) à partir de l'énergie utile (E_u)
    et de la fenêtre SOC utilisable (w).

    Déduction :
        E_u = w * E_b  =>  E_b = E_u / w

    Args:
        energie_utile_kwh (float): Énergie utile réellement exploitable (kWh). (>= 0)
        fenetre_soc (float): Fenêtre SOC utilisable w (0 < w <= 1).
            Exemples :
            - 0.60 signifie : on n'utilise que 60% de la capacité totale (pour préserver la durée de vie)
            - 0.80 signifie : usage plus large, potentiellement plus d'usure

    Returns:
        float: Capacité totale de batterie E_b (kWh).
    """
    E_u = _exiger_positif("energie_utile_kwh", energie_utile_kwh, strict=False)

    # Fenêtre SOC : strictement >0 et <=1
    w = _exiger_positif("fenetre_soc", fenetre_soc, strict=True)
    if w > 1.0:
        raise ValueError("La fenêtre SOC doit être <= 1.0 (100%).")

    # Cas stable : si E_u == 0 => E_b == 0, évite du bruit numérique
    if E_u == 0.0:
        return 0.0

    return E_u / w


def calcul_poids_batterie(capacite_totale_kwh: float, densite_energetique_kwh_kg: float) -> float:
    """
    Calcule la masse de la batterie à partir de sa capacité totale et de sa densité énergétique.

    Déduction :
        densité énergétique ρ_E = E_b / m_b  =>  m_b = E_b / ρ_E

    Args:
        capacite_totale_kwh (float): Capacité totale E_b (kWh). (>= 0)
        densite_energetique_kwh_kg (float): Densité énergétique ρ_E (kWh/kg). (> 0)
            Remarque : selon la techno et le niveau pack (cellule vs pack complet),
            la densité au niveau pack est plus faible (structure, BMS, refroidissement).

    Returns:
        float: Masse batterie (kg).
    """
    E_b = _exiger_positif("capacite_totale_kwh", capacite_totale_kwh, strict=False)
    rho_E = _exiger_positif("densite_energetique_kwh_kg", densite_energetique_kwh_kg, strict=True)

    if E_b == 0.0:
        return 0.0

    return E_b / rho_E
