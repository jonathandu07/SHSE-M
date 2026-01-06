# backend\modules\architecture\calcul_cylindree_totale.py
from __future__ import annotations

import math


# =============================================================================
# Utilitaires robustesse (cohérents avec tes autres modules)
# =============================================================================

def _est_fini(x: float) -> bool:
    """Vérifie qu'une valeur est un nombre réel fini (pas NaN, pas inf)."""
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _exiger_fini(nom: str, x: float) -> float:
    """Convertit en float et lève une erreur si NaN/inf."""
    if not _est_fini(x):
        raise ValueError(f"{nom} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _exiger_positif(nom: str, x: float, *, strict: bool = True) -> float:
    """
    Exige x > 0 (ou x >= 0 si strict=False).
    Utile pour imposer des contraintes physiques (PME, fréquence, rendements...).
    """
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


# =============================================================================
# Cylindrée totale requise à partir de P, PME, fréquence de cycles
# =============================================================================

def calcul_cylindree_totale_requise(
    puissance_mecanique_h: float,
    pme_pa: float,
    frequence_cycles_hz: float,
    rendement_mecanique: float = 1.0
) -> float:
    """
    Calcule la cylindrée totale théorique nécessaire pour atteindre une puissance mécanique cible.

    Déduction (on explicite la physique pour retirer les "inconnues") :
    - Travail indiqué (ou utile) par cycle :
        W_cycle = PME * V_tot
      (PME en Pa = N/m² ; V en m³ ; donc W en Joules)

    - Puissance = travail par cycle * nombre de cycles par seconde :
        P = W_cycle * f = (PME * V_tot) * f

    - Si on introduit un rendement mécanique η_m (pertes mécaniques, ou PME pas "net") :
        P_b = η_m * PME * V_tot * f

      => V_tot = P_b / (η_m * PME * f)

    Args:
        puissance_mecanique_h (float): Puissance mécanique au vilebrequin P_b (W).
                                       Convention : P_b >= 0.
        pme_pa (float): Pression Moyenne Effective PME (Pa). Doit être > 0.
                        (Si PME déjà "au vilebrequin", mettre rendement_mecanique=1.)
        frequence_cycles_hz (float): Fréquence des cycles f (Hz = cycles/s). Doit être > 0.
            - 4T : f = n / 120  (n en tr/min)
            - 2T : f = n / 60
        rendement_mecanique (float): η_m (0 < η_m <= 1 typiquement). Défaut 1.0.

    Returns:
        float: Cylindrée totale requise V_tot en m³.
    """
    P_b = _exiger_positif("puissance_mecanique_h", puissance_mecanique_h, strict=False)
    PME = _exiger_positif("pme_pa", pme_pa, strict=True)
    f = _exiger_positif("frequence_cycles_hz", frequence_cycles_hz, strict=True)

    # Rendement : on autorise 1.0, et on refuse <=0.
    eta_m = _exiger_positif("rendement_mecanique", rendement_mecanique, strict=True)

    # Optionnel : bornage "souple" (ne casse pas) pour éviter des erreurs de saisie grossières.
    # On ne lève pas si eta_m > 1, car certains utilisent des "facteurs" >1 (mauvaise convention).
    # Mais on peut quand même signaler via ValueError si tu préfères verrouiller.
    if eta_m == 0.0:
        raise ValueError("rendement_mecanique ne peut pas être nul.")

    return P_b / (eta_m * PME * f)
