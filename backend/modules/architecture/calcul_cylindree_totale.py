import math

def calcul_cylindree_totale_requise(puissance_mecanique_h: float, pme_pa: float, frequence_cycles_hz: float, rendement_mecanique: float = 1.0) -> float:
    """
    Calcule la cylindrée totale théorique nécessaire pour atteindre une puissance cible.

    Formule : V_tot = P_b / (eta_m * pmi * f)

    Args:
        puissance_mecanique_h (float): Puissance mécanique au vilebrequin (P_b) en Watts (W).
        pme_pa (float): Pression Moyenne Effective (pmi) en Pascals (Pa).
        frequence_cycles_hz (float): Fréquence des cycles (f).
                                     Pour 4T: f = n/120 (n en tr/min / 60 / 2)
                                     Pour 2T: f = n/60
        rendement_mecanique (float): Rendement mécanique (eta_m), défaut 1.0 (si PME déjà net).

    Returns:
        float: Cylindrée totale requise en mètres cubes (m3).
    """
    if pme_pa == 0 or frequence_cycles_hz == 0 or rendement_mecanique == 0:
        raise ValueError("Les paramètres PME, Fréquence et Rendement ne peuvent être nuls.")
        
    return puissance_mecanique_h / (rendement_mecanique * pme_pa * frequence_cycles_hz)
