# backend/modules/batterie/calcul_energie_utile.py
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
# Énergie utile (kWh)
# =============================================================================

def calcul_energie_utile_cible(temps_charge_cible_h: float, puissance_charge_kw: float, rendement_charge: float) -> float:
    """
    Calcule l'énergie utile dimensionnée par une cible de temps de recharge.
    (C’est une contrainte "je veux recharger X kWh utiles en t heures avec P kW".)

    Déduction :
        Énergie électrique délivrée par le chargeur : E_in = P_chg * t_chg  (kWh, si P en kW et t en h)
        Énergie utile stockée : E_u = eta_chg * E_in

        => E_u = eta_chg * P_chg * t_chg

    Args:
        temps_charge_cible_h (float): Durée de charge visée (h). (>= 0)
        puissance_charge_kw (float): Puissance de charge (kW). (>= 0)
        rendement_charge (float): Rendement global charge (0 < eta <= 1).
            Inclut pertes chargeur, conversion, batteries, etc.

    Returns:
        float: Énergie utile (kWh).
    """
    t = _exiger_positif("temps_charge_cible_h", temps_charge_cible_h, strict=False)
    P = _exiger_positif("puissance_charge_kw", puissance_charge_kw, strict=False)
    eta = _exiger_rendement("rendement_charge", rendement_charge)

    # Cas limites stables
    if t == 0.0 or P == 0.0:
        return 0.0

    return eta * P * t


def calcul_energie_utile_trajet(distance_km: float, conso_kwh_km: float) -> float:
    """
    Calcule l'énergie utile pour une autonomie (trajet) donnée.

    Déduction :
        E_u = d * conso

    Args:
        distance_km (float): Distance (km). (>= 0)
        conso_kwh_km (float): Consommation moyenne (kWh/km). (>= 0)

    Returns:
        float: Énergie utile (kWh).
    """
    d = _exiger_positif("distance_km", distance_km, strict=False)
    c = _exiger_positif("conso_kwh_km", conso_kwh_km, strict=False)

    if d == 0.0 or c == 0.0:
        return 0.0

    return d * c


def calcul_energie_utile_pic(puissance_pic_kw: float, duree_secondes: float) -> float:
    """
    Calcule l'énergie utile "tampon" nécessaire pour absorber un pic de puissance.

    Déduction :
        E (kWh) = P (kW) * t (h)
        avec t(h) = t(s) / 3600

        => E = P_kw * t_s / 3600

    Args:
        puissance_pic_kw (float): Puissance du pic (kW). (>= 0)
        duree_secondes (float): Durée du pic (s). (>= 0)

    Returns:
        float: Énergie utile (kWh).
    """
    P = _exiger_positif("puissance_pic_kw", puissance_pic_kw, strict=False)
    t_s = _exiger_positif("duree_secondes", duree_secondes, strict=False)

    if P == 0.0 or t_s == 0.0:
        return 0.0

    return (P * t_s) / 3600.0


def choisir_energie_utile_finale(*args) -> float:
    """
    Retourne la valeur maximale parmi plusieurs critères d'énergie utile.

    But :
        On dimensionne souvent la batterie sur le critère le plus contraignant :
        - autonomie,
        - contrainte de recharge,
        - tampon de puissance, etc.

    Compatibilité :
        - même signature, même retour (float).
        - amélioration : validation des entrées (finitude) + gestion du cas vide.

    Args:
        *args: Valeurs d'énergie utile (kWh).

    Returns:
        float: max(args) ou 0.0 si aucun argument.
    """
    if len(args) == 0:
        return 0.0

    valeurs = []
    for i, v in enumerate(args):
        v = _exiger_fini(f"energie_utile_arg_{i}", v)
        # Une énergie utile négative n'a pas de sens dans ce contexte => on interdit.
        if v < 0.0:
            raise ValueError(f"energie_utile_arg_{i} doit être >= 0 (reçu: {v}).")
        valeurs.append(v)

    return max(valeurs)
