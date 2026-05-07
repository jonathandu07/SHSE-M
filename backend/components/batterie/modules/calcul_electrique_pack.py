# backend/modules/batterie/calcul_electrique_pack.py
from __future__ import annotations

"""
Outils électriques génériques pour batteries.

Ce module reste volontairement sans hypothèse cachée : il convertit, vérifie et
estime à partir de valeurs fournies par l'appelant. Les constantes propres à une
cellule, par exemple Samsung INR18650-25R, sont portées dans
`dimensionner_pack_cellules.py` pour éviter de mélanger données cellule et
formules électriques générales.
"""

import math
from typing import Optional


# =============================================================================
# Utilitaires robustesse
# =============================================================================

def _est_fini(x: object) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _exiger_fini(nom: str, x: object) -> float:
    if not _est_fini(x):
        raise ValueError(f"{nom} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _exiger_positif(nom: str, x: object, *, strict: bool = True) -> float:
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def _exiger_rendement(nom: str, x: object) -> float:
    eta = _exiger_positif(nom, x, strict=True)
    if eta > 1.0:
        raise ValueError(f"{nom} doit être <= 1.0 (reçu: {eta}).")
    return eta


def _exiger_ratio_0_1(nom: str, x: object, *, strict_min: bool = False) -> float:
    v = _exiger_fini(nom, x)
    ok = (0.0 < v <= 1.0) if strict_min else (0.0 <= v <= 1.0)
    if not ok:
        borne = "0 < x <= 1" if strict_min else "0 <= x <= 1"
        raise ValueError(f"{nom} doit vérifier {borne} (reçu: {v}).")
    return v


# =============================================================================
# Conversions / estimations électriques pack
# =============================================================================

def calcul_conso_kwh_km_depuis_puissance_vitesse(
    puissance_moyenne_kw: float,
    vitesse_moyenne_kmh: float,
) -> float:
    """
    Déduit une consommation moyenne (kWh/km) depuis puissance moyenne (kW)
    et vitesse moyenne (km/h).

    conso(kWh/km) = P(kW) / v(km/h)
    """
    P = _exiger_positif("puissance_moyenne_kw", puissance_moyenne_kw, strict=False)
    v = _exiger_positif("vitesse_moyenne_kmh", vitesse_moyenne_kmh, strict=True)
    if P == 0.0:
        return 0.0
    return P / v


def calcul_ah_depuis_kwh_tension(capacite_kwh: float, tension_v: float) -> float:
    """
    Convertit une énergie (kWh) en capacité (Ah) à tension nominale constante.
    Ah = kWh * 1000 / V
    """
    E_kwh = _exiger_positif("capacite_kwh", capacite_kwh, strict=False)
    V = _exiger_positif("tension_v", tension_v, strict=True)
    if E_kwh == 0.0:
        return 0.0
    return (E_kwh * 1000.0) / V


def calcul_kwh_depuis_ah_tension(capacite_ah: float, tension_v: float) -> float:
    """
    Convertit capacité Ah + tension V en énergie kWh.
    kWh = Ah * V / 1000
    """
    Ah = _exiger_positif("capacite_ah", capacite_ah, strict=False)
    V = _exiger_positif("tension_v", tension_v, strict=True)
    if Ah == 0.0:
        return 0.0
    return (Ah * V) / 1000.0


def calcul_courant_depuis_kw_tension(puissance_kw: float, tension_v: float) -> float:
    """
    Calcule un courant (A) depuis puissance (kW) et tension (V).
    I = P / V
    """
    P_kw = _exiger_positif("puissance_kw", puissance_kw, strict=False)
    V = _exiger_positif("tension_v", tension_v, strict=True)
    if P_kw == 0.0:
        return 0.0
    return (P_kw * 1000.0) / V


def calcul_puissance_kw_depuis_tension_courant(tension_v: float, courant_a: float) -> float:
    """
    Calcule une puissance (kW) depuis tension (V) et courant (A).
    P(kW) = V * I / 1000
    """
    V = _exiger_positif("tension_v", tension_v, strict=False)
    I = _exiger_positif("courant_a", courant_a, strict=False)
    if V == 0.0 or I == 0.0:
        return 0.0
    return (V * I) / 1000.0


def calcul_c_rate_depuis_kw_kwh(puissance_kw: float, capacite_kwh: float) -> float:
    """
    Estime un C-rate global depuis P(kW) et E(kWh).
    C_rate ≈ P / E
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
    Puissance effective réellement stockée en charge.
    P_eff = eta * P_charge
    """
    P = _exiger_positif("puissance_charge_kw", puissance_charge_kw, strict=True)
    eta = _exiger_rendement("rendement_charge", rendement_charge)
    return P * eta


def calcul_puissance_charge_requise(
    energie_utile_kwh: float,
    temps_charge_h: float,
    rendement_charge: float,
) -> float:
    """
    Inversion du modèle de charge à puissance constante.
    P = E_u / (eta * t)
    """
    E = _exiger_positif("energie_utile_kwh", energie_utile_kwh, strict=False)
    t = _exiger_positif("temps_charge_h", temps_charge_h, strict=True)
    eta = _exiger_rendement("rendement_charge", rendement_charge)
    if E == 0.0:
        return 0.0
    return E / (eta * t)


def calcul_temps_charge_constant_power(
    energie_kwh: float,
    puissance_charge_kw: float,
    rendement_charge: float = 1.0,
    fraction_a_recharger: float = 1.0,
) -> float:
    """
    Temps de charge simplifié à puissance constante.

    Ce modèle ne remplace pas la vraie courbe CC/CV : il sert au pré-dimensionnement.
    La fin de charge CV peut rallonger le temps 0-100%.
    """
    E = _exiger_positif("energie_kwh", energie_kwh, strict=False)
    P = _exiger_positif("puissance_charge_kw", puissance_charge_kw, strict=True)
    eta = _exiger_rendement("rendement_charge", rendement_charge)
    f = _exiger_ratio_0_1("fraction_a_recharger", fraction_a_recharger, strict_min=False)
    if E == 0.0 or f == 0.0:
        return 0.0
    return (E * f) / (P * eta)


def calcul_puissance_charge_pack_kw(
    nb_series: int,
    nb_parallele: int,
    tension_cellule_v: float,
    courant_charge_cellule_a: float,
) -> float:
    """
    Puissance de charge pack approximative depuis courant de charge par cellule.

    V_pack = Ns * V_cell
    I_pack = Np * I_cell_charge
    P = V_pack * I_pack
    """
    ns = int(_exiger_positif("nb_series", nb_series, strict=True))
    np_ = int(_exiger_positif("nb_parallele", nb_parallele, strict=True))
    Vcell = _exiger_positif("tension_cellule_v", tension_cellule_v, strict=True)
    Icell = _exiger_positif("courant_charge_cellule_a", courant_charge_cellule_a, strict=False)
    return calcul_puissance_kw_depuis_tension_courant(ns * Vcell, np_ * Icell)


def calcul_section_cuivre_estimee_mm2(
    courant_a: float,
    densite_courant_a_mm2: float = 3.0,
) -> float:
    """
    Estimation très simple de section cuivre.

    Ne remplace pas une norme, une étude thermique, un choix d'isolant ou une
    homologation. Utilise plutôt 3 A/mm² pour une valeur prudente et 5 A/mm²
    pour une estimation plus compacte.
    """
    I = _exiger_positif("courant_a", courant_a, strict=False)
    J = _exiger_positif("densite_courant_a_mm2", densite_courant_a_mm2, strict=True)
    if I == 0.0:
        return 0.0
    return I / J


__all__ = [
    "calcul_conso_kwh_km_depuis_puissance_vitesse",
    "calcul_ah_depuis_kwh_tension",
    "calcul_kwh_depuis_ah_tension",
    "calcul_courant_depuis_kw_tension",
    "calcul_puissance_kw_depuis_tension_courant",
    "calcul_c_rate_depuis_kw_kwh",
    "calcul_puissance_effective_stockee",
    "calcul_puissance_charge_requise",
    "calcul_temps_charge_constant_power",
    "calcul_puissance_charge_pack_kw",
    "calcul_section_cuivre_estimee_mm2",
]
