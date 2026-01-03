# backend\modules\moteur_thermique\calcul_travail_indique.py
from __future__ import annotations

import math


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
    Utile pour imposer des contraintes physiques (volumes, régimes, etc.).
    """
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def calcul_travail_indique_pme(pression_moyenne_effective_pa: float, cylindree_m3: float) -> float:
    """
    Calcule le travail indiqué par cycle (W_i).

    Formule (inchangée) :
      W_i = PME * V_d

    Où :
    - W_i : travail indiqué par cycle (J)
    - PME : pression moyenne effective (Pa) (souvent >= 0 en moteur)
    - V_d : cylindrée balayée (m³) (>= 0)

    Remarque :
    - Si V_d = 0 => travail nul.
    - Si PME < 0 (cas atypique), le travail devient négatif (convention possible en freinage/pompage).
      Ici, on n'interdit pas PME négative : on valide seulement la finitude.
    """
    pme = _exiger_fini("pression_moyenne_effective_pa", pression_moyenne_effective_pa)
    Vd = _exiger_positif("cylindree_m3", cylindree_m3, strict=False)
    return pme * Vd


def calcul_puissance_indiquee(travail_indique_j: float, vitesse_rotation_tr_min: float, temps_moteur: int = 4) -> float:
    """
    Calcule la puissance indiquée (P_i) à partir du travail indiqué par cycle.

    Formule (inchangée) :
      P_i = W_i * (cycles/s)

    Définition des cycles/s :
    - cycles/s = n / 60 pour un 2-temps (un cycle par tour)
    - cycles/s = (n / 60) / 2 pour un 4-temps (un cycle toutes les 2 révolutions)

    Paramètres :
    - travail_indique_j : W_i (J) (peut être signé selon conventions)
    - vitesse_rotation_tr_min : n (tr/min) (>= 0)
    - temps_moteur : 2 ou 4 (défaut 4)

    Retour :
    - puissance indiquée P_i (W)
    """
    W_i = _exiger_fini("travail_indique_j", travail_indique_j)
    n_rpm = _exiger_positif("vitesse_rotation_tr_min", vitesse_rotation_tr_min, strict=False)

    if temps_moteur not in (2, 4):
        raise ValueError("temps_moteur doit valoir 2 ou 4.")

    cycles_par_seconde = n_rpm / 60.0
    if temps_moteur == 4:
        cycles_par_seconde /= 2.0

    return W_i * cycles_par_seconde
